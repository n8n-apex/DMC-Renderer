"""FastAPI app — pre-processor Layer 1.

Two endpoints:

  POST /onboard   Mode 1 — visual brand extraction. Playwright
                  screenshots → pixel palette + DOM fonts → vision model
                  (role assignment) → BrandProfile POSTed to the n8n
                  webhook. Async: returns 202, delivers on completion.

  POST /render    Runs Stages 1-4, 5, 6, 7, 8 and assembles the
                  resolved package on disk. Returns paths + summaries
                  in JSON; the renderer (Layer 2) consumes the package
                  directory directly.

Input-driven principle: no client name appears in this module's logic.
The route hands the request to the stages and returns the result.
"""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from pathlib import Path
from typing import Optional
from uuid import uuid4

# Allow flat imports from research/preprocessor/ regardless of cwd
# (mirrors the chassis pattern in research/v7-renderer/render.py).
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import httpx  # noqa: E402
from contextlib import asynccontextmanager  # noqa: E402
from fastapi import BackgroundTasks, Depends, FastAPI, Request  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402

from settings import Settings  # noqa: E402
from logging_setup import bind_job_id, clear_job_id, configure_logging, get_logger  # noqa: E402
from errors import PreprocessorError, error_payload  # noqa: E402

from models import (  # noqa: E402
    AssetSummary,
    LayoutPlanSummary,
    RenderRequest,
    RenderResponse,
)
from stages.assemble_package import assemble_package  # noqa: E402
from stages.generate_assets import generate_assets  # noqa: E402
from stages.generate_components import generate_components_for_report  # noqa: E402
from stages.local_assets import client_assets_dir, list_client_assets  # noqa: E402
from stages.plan_layout import layout_plan_to_summary, plan_layout  # noqa: E402
from stages.resolve_axes import resolve_axes  # noqa: E402
from stages.resolve_fonts import resolve_fonts  # noqa: E402
from stages.resolve_slots import resolve_slots  # noqa: E402
from stages.structure_content import structure_content  # noqa: E402
from stages.validate_copy import validate_copy  # noqa: E402
from stages.validate_copyfit import validate_copyfit  # noqa: E402
from stages.validate_cover import validate_cover  # noqa: E402
from stages.validate_input import validate_and_resolve_brand_tokens  # noqa: E402
from stages.onboard.pipeline import run_onboard_pipeline  # noqa: E402
from models_onboard import OnboardAccepted, OnboardRequest, OnboardResult  # noqa: E402
import orchestrator  # noqa: E402  (flat import; preprocessor root is on sys.path)


_settings = Settings()


def get_settings() -> Settings:
    return _settings


async def get_http_client(req: Request) -> httpx.AsyncClient:
    client = getattr(req.app.state, "http_client", None)
    if client is None:
        # lifespan not active (e.g. a unit test using TestClient without a
        # context manager) → lazily create one so /render still works.
        # Production ALWAYS enters lifespan, so this branch is test-only; the
        # lazily-created client is not pooled and not closed (fine for tests).
        client = httpx.AsyncClient(timeout=_settings.http_timeout_s)
        req.app.state.http_client = client
    return client


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    app.state.http_client = httpx.AsyncClient(
        timeout=_settings.http_timeout_s,
        limits=httpx.Limits(max_connections=_settings.http_max_connections),
    )
    # US-2026-08-24: the WEEKLY Supabase catalog sync — internally triggered,
    # not a human job. The background loop owns the cadence (default 7 days;
    # SUPABASE_SYNC_INTERVAL_SECONDS overrides). It starts immediately (boot
    # catch-up), wakes every CHECK_INTERVAL, and re-ingests the reference
    # corpus + anatomy + storage record when due. A paused/missing Supabase
    # warns loudly and schedules the next attempt — never fails the app.
    _sync_task = None
    try:
        from stages.supabase_sync import run_sync_loop, dsn_from_env

        def _sync_dsn() -> Optional[str]:
            return (_settings.supabase_pooler_url_str()
                    or dsn_from_env())

        _sync_task = asyncio.create_task(
            run_sync_loop(
                _sync_dsn,
                interval=max(60, _settings.supabase_sync_check_seconds),
                project_url=_settings.supabase_url or "",
                storage_key=_settings.supabase_service_role_key_str() or "",
            )
        )
    except Exception as _sync_exc:  # noqa: BLE001 -- never break boot
        print(f"[supabase-sync] loop not started: {_sync_exc}")
    try:
        yield
    finally:
        if _sync_task is not None:
            _sync_task.cancel()
        await app.state.http_client.aclose()


app = FastAPI(
    title="DMC report pre-processor (Layer 1)",
    description=(
        "Prepares a render package for the Layer 2 chassis "
        "(research/v7-renderer/). Phase A built Stages 1-2 "
        "(validate_input, resolve_fonts). Phase B added Stages 3-4 "
        "(validate_copy §3.9, validate_cover 11_Cover_Headlines). Phase "
        "C added Stages 6-7 (generate_components, plan_layout). Phase D "
        "adds Stage 5 (generate_assets — inventory + download + stubbed "
        "AI generators) and Stage 8 (assemble_package — writes a "
        "self-contained directory + resolved_package.json for the "
        "renderer to consume). Mode 1 (/onboard) extracts a visual "
        "BrandProfile from a client's website (screenshots → pixel "
        "palette + DOM fonts → vision model)."
    ),
    version="0.5.0-onboard",
    lifespan=lifespan,
)


@app.get("/health")
async def health() -> dict:
    """Liveness probe for the platform (Railway / Docker healthcheck). The
    renderer is a subprocess on the same container, so a reachable app == a
    healthy ship path. Never touches secrets; no side effects."""
    return {"status": "ok", "app": "dmc-preprocessor", "version": "0.5.0-onboard"}


@app.post("/sync-catalog")
async def sync_catalog(force: bool = False) -> dict:
    """Manually trigger the reference-catalog sync (boot/CI/SRE).

    The weekly loop runs it automatically; this route exists for an
    immediate refresh. `force=true` bypasses the due-check. When Supabase
    is absent/paused the response is a LOUD {"state": "no_dsn" |
    "unavailable"} — the app keeps running on the legacy index; it never
    fabricates references."""
    from stages.supabase_sync import run_catalog_sync, maybe_sync_catalog

    _dsn = _settings.supabase_pooler_url_str()
    if force:
        return await run_catalog_sync(
            _dsn,
            project_url=_settings.supabase_url or "",
            storage_key=_settings.supabase_service_role_key_str() or "",
        )
    return await maybe_sync_catalog(
        _dsn,
        project_url=_settings.supabase_url or "",
        storage_key=_settings.supabase_service_role_key_str() or "",
    )


@app.middleware("http")
async def _bind_job_id(request: Request, call_next):
    # Correlation id for this request: bound to the structlog contextvar
    # (for log lines) AND stashed on request.state (scope-backed, so it
    # survives to the exception handlers even though the contextvar is
    # cleared in `finally` before an outer handler runs).
    job_id = uuid4().hex
    request.state.job_id = job_id
    bind_job_id(job_id)
    try:
        return await call_next(request)
    finally:
        clear_job_id()


@app.exception_handler(PreprocessorError)
async def _handle_preprocessor_error(request: Request, exc: PreprocessorError):
    job_id = getattr(request.state, "job_id", None)
    get_logger().error("preprocessor_error", code=exc.code, detail=exc.detail, **exc.context)
    return JSONResponse(
        status_code=exc.http_status, content=error_payload(exc, job_id=job_id)
    )


@app.exception_handler(Exception)
async def _handle_unexpected(request: Request, exc: Exception):
    job_id = getattr(request.state, "job_id", None)
    get_logger().error("unexpected_error", error=str(exc))
    return JSONResponse(status_code=500, content=error_payload(exc, job_id=job_id))


# ─────────────────────────────────────────────────────────────────────────────
# Mode 1 — onboarding (visual brand extraction)
# ─────────────────────────────────────────────────────────────────────────────


_WEBHOOK_RETRIES = 2


@app.post("/onboard", status_code=202, response_model=OnboardAccepted)
async def onboard(
    request: OnboardRequest, background_tasks: BackgroundTasks
) -> OnboardAccepted:
    """Mode 1 — visual brand extraction.

    Returns 202 immediately and runs the 5-layer pipeline in the
    background; on completion POSTs the OnboardResult to the
    report-generator webhook (n8n persists it to Airtable).
    """
    job_id = uuid4().hex
    background_tasks.add_task(_run_and_deliver, request, job_id)
    return OnboardAccepted(job_id=job_id, record_id=request.record_id)


async def _run_and_deliver(request: OnboardRequest, job_id: str) -> None:
    output_dir = Path(
        _settings.onboard_output_dir or tempfile.mkdtemp(prefix="dmc_onboard_")
    )
    result = await run_onboard_pipeline(
        request,
        output_dir=output_dir,
        api_key=_settings.openrouter_key_str(),
        model=_settings.openrouter_vision_model,
        brief_model=_settings.openrouter_brief_model,
    )
    result.job_id = job_id
    webhook = request.callback_url or _settings.report_generator_webhook
    await _deliver_result(result, webhook, output_dir)


async def _deliver_result(
    result: OnboardResult, webhook: Optional[str], output_dir: Path
) -> None:
    """POST the result to the webhook (`_WEBHOOK_RETRIES` retries → up to
    `_WEBHOOK_RETRIES + 1` total attempts); on final failure persist it to
    disk so it is never lost. The disk write is itself guarded so a
    background task never raises.
    """
    payload = result.model_dump()
    if webhook:
        async with httpx.AsyncClient(timeout=30.0) as client:
            for _attempt in range(_WEBHOOK_RETRIES + 1):
                try:
                    resp = await client.post(webhook, json=payload)
                    if resp.status_code < 400:
                        return
                except httpx.HTTPError:
                    pass
    try:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        (Path(output_dir) / "onboard_result.json").write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        # Last-resort: webhook unreachable AND disk unwritable. Nothing
        # left to do but avoid crashing the background task.
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Autonomy spine — render + grade + ship a built package (Phase 4b)
# ─────────────────────────────────────────────────────────────────────────────

# Tests override this with a fake runner; None -> the real subprocess runner.
_SHIP_RUNNER = None


def _post_webhook_sync(url: str, payload: dict) -> None:
    """Sync webhook POST with a few retries -- used inside the ship background task
    (which runs in a worker thread). Never raises; a final failure is swallowed so
    the background task cannot crash the worker.

    When local PDF/IDML paths are on the payload, they are attached as multipart
    files so n8n can email them without a separate file host.
    """
    import json as _json

    for _attempt in range(3):
        handles: list = []
        try:
            files = {}
            pdf = payload.get("pdf_path")
            idml = payload.get("idml_zip_path")
            if pdf and Path(pdf).exists():
                fh = open(pdf, "rb")  # noqa: SIM115
                handles.append(fh)
                files["pdf"] = (Path(pdf).name, fh, "application/pdf")
            if idml and Path(idml).exists():
                fh = open(idml, "rb")  # noqa: SIM115
                handles.append(fh)
                files["idml"] = (Path(idml).name, fh, "application/zip")
            if files:
                resp = httpx.post(
                    url,
                    data={"payload": _json.dumps(payload)},
                    files=files,
                    timeout=120.0,
                )
            else:
                resp = httpx.post(url, json=payload, timeout=30.0)
            if resp.status_code < 400:
                return
        except httpx.HTTPError:
            pass
        finally:
            for fh in handles:
                try:
                    fh.close()
                except Exception:
                    pass


async def _orchestrate_and_deliver(
    package_dir: Path, webhook: Optional[str], job_id: str
) -> None:
    """Background task: render + grade + compose the built package, gate it, and
    deliver the ship-or-escalate outcome to the webhook. The blocking subprocess
    render runs in a worker thread so the event loop is never blocked."""
    runner = _SHIP_RUNNER or orchestrator.SubprocessRenderRunner()
    ship_out = Path(tempfile.mkdtemp(prefix="dmc_ship_"))
    # US-2026-08-19 (n8n outtake): upload the deliverable PDF + editable IDML
    # ZIP to the shared file host and send the public URLs back to n8n.
    _cfg = get_settings()
    await asyncio.to_thread(
        orchestrator.run_and_deliver,
        package_dir, ship_out, webhook, job_id,
        runner=runner, post_fn=_post_webhook_sync,
        upload_url=_cfg.artifact_upload_url,
        public_base=_cfg.artifact_public_base,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Founder-asset scraper — OUT-OF-BAND background task for /render
# ─────────────────────────────────────────────────────────────────────────────


async def _scrape_founder_and_place(
    client_input,
    client_slug: str,
    cfg: Settings,
    route_fn=None,
) -> None:
    """Scrape founder assets and place them under client_assets/<slug>/.

    Runs DETACHED as a /render background task (the response is already
    sent). It MUST never raise — a background failure must not crash the
    worker — so the whole body is wrapped in try/except and swallows.

    - No-op if neither founder URL is present.
    - Idempotent: if `founder.jpg` or `team.jpg` already exists for this
      client, skip (the client already has scraped assets).
    - `route_fn` lets tests inject a fake `understand_and_route`; production
      lazily imports the real one.
    """
    try:
        youtube_url = getattr(client_input, "founder_youtube_url", None)
        instagram_url = getattr(client_input, "founder_instagram_url", None)
        if not youtube_url and not instagram_url:
            return

        client_dir = client_assets_dir(client_slug, base=cfg.client_assets_dir)
        if (client_dir / "founder.jpg").exists() or (
            client_dir / "team.jpg"
        ).exists():
            get_logger().debug(
                "founder_scrape_skip_existing", client_slug=client_slug
            )
            return

        if route_fn is None:
            from stages.scrape_founder_assets.orchestrator import (
                understand_and_route,
            )

            route_fn = understand_and_route

        scratch_dir = tempfile.mkdtemp(prefix="dmc_founder_scrape_")
        result = await route_fn(
            youtube_url=youtube_url,
            instagram_url=instagram_url,
            founder_id=client_slug,
            scratch_dir=scratch_dir,
            dest_root=cfg.client_assets_dir,
        )
        get_logger().info(
            "founder_scrape_done",
            client_slug=client_slug,
            flags=getattr(result, "flags", None),
        )
    except Exception as exc:  # detached task — must never crash the worker
        get_logger().error(
            "founder_scrape_failed", client_slug=client_slug, error=str(exc)
        )


# ─────────────────────────────────────────────────────────────────────────────
# Mode 2 — render preparation (Phase A: stages 1 + 2)
# ─────────────────────────────────────────────────────────────────────────────


@app.post("/render", response_model=RenderResponse)
async def render(
    request: RenderRequest,
    background_tasks: BackgroundTasks,
    http_client: httpx.AsyncClient = Depends(get_http_client),
    cfg: Settings = Depends(get_settings),
) -> RenderResponse:
    """Run Stages 1-4, 5, 6, 7, 8 in order. Async because Stage 5
    downloads images via httpx.

    Pydantic + FastAPI handles "REJECT LOUD on missing required field"
    at the route layer — missing keys raise 422 with a structured
    validation error before this handler runs.

    Within this handler:
      - Stage 1 maps n8n-shape input to chassis BrandConfig 10-field
        shape and runs the grammar's semantic checks.
      - Stage 2 fills font fields (heading + body).
      - Stage 3 walks every text field on every page → copy warnings.
      - Stage 4 scores the cover stack → CoverValidation.
      - Stage 5 inventories required images, downloads what's already
        in the manifest, stubs the rest. WRITES TO A TEMP DIRECTORY.
      - Stage 6 generates SVG components per slot.
      - Stage 7 verifies structural rules + enriches each page.
      - Stage 8 assembles everything into a resolved_package.json plus
        a `components/` + `assets/` + `fonts/` directory tree at the
        same temp directory. The renderer consumes that directory.

    `status` is "error" when Stage 1 raised critical issues, "warn"
    when warnings only, "success" otherwise.
    """
    # Out-of-band founder-asset scrape: schedule when a founder URL is present
    # so it populates client_assets/<slug>/ for subsequent renders. This only
    # registers a detached background task — it does NOT block /render and does
    # NOT change this response.
    if request.client.founder_youtube_url or request.client.founder_instagram_url:
        background_tasks.add_task(
            _scrape_founder_and_place,
            request.client,
            request.report_json.meta.client_slug,
            cfg,
        )

    brand_tokens, errors, warnings = validate_and_resolve_brand_tokens(request)

    if brand_tokens is None:
        return RenderResponse(
            status="error",
            validated_brand_tokens=None,
            font_config=None,
            errors=errors,
            warnings=warnings,
        )

    # Stage 2
    font_config = resolve_fonts(request.client.brand_profile)
    brand_tokens = brand_tokens.model_copy(
        update={
            "font_heading": font_config.font_heading_name,
            "font_body": font_config.font_body_name,
        }
    )

    # Stage 2.5 — resolve the 7 design axes (DNA §B) + provenance. Feeds the
    # package's `axes`/`brand_axes`/`provenance` blocks (Stage 8).
    axes, axes_provenance = resolve_axes(
        brand_profile=request.client.brand_profile,
        brand_primary=brand_tokens.brand_primary,
        brand_accent=brand_tokens.brand_accent,
    )

    # Stage 3 (+ 3.5 copy-fit pre-check — advisory overflow early-warning)
    copy_warnings = validate_copy(request.report_json.pages)
    copy_warnings = copy_warnings + validate_copyfit(request.report_json.pages)

    # Stage 4
    cover_validation = None
    cover_page = None
    for page in request.report_json.pages:
        if page.slot == 1 or page.type == "ST-01":
            cover_page = page
            break
    if cover_page is not None and isinstance(cover_page.data, dict):
        cover_validation = validate_cover(
            cover_page.data,
            awareness_level=request.report_json.meta.awareness_level,
        )

    # Stage 4.5 — typed structured content + human-photo slot resolution.
    # structure_content gives per-page typed data / charts / social_proof;
    # resolve_slots binds each page's drive SlotSpecs against the client's
    # local Drive-substitute folder. `case_index` is derived from the
    # Fallstudie ordinal (`data.fallstudie_number`) with a positional
    # fallback so ST-07A portraits map to case-study-<n>.
    structured = structure_content(request.report_json.pages)
    client_dir = client_assets_dir(
        request.report_json.meta.client_slug, base=Path(cfg.client_assets_dir)
    )
    drive_listing = list_client_assets(client_dir)
    page_slots: dict[int, list] = {}
    case_counter = 0
    for page in request.report_json.pages:
        case_index = None
        if page.type == "ST-07A":
            case_counter += 1
            fn = page.data.get("fallstudie_number") if isinstance(page.data, dict) else None
            case_index = int(fn) if (isinstance(fn, int) or (isinstance(fn, str) and fn.isdigit())) else case_counter
        page_slots[page.slot] = resolve_slots(page.type, drive_listing, case_index=case_index)

    # Stage 5 — asset inventory + download + stub generation.
    # Temp dir lives until the renderer consumes it. We do NOT delete
    # here; in production this is a request-scoped directory the
    # renderer picks up. (Locally, leaking under /var/folders is fine.)
    output_dir = Path(tempfile.mkdtemp(prefix="dmc_render_"))
    asset_plan = await generate_assets(
        pages=request.report_json.pages,
        image_manifest=request.image_manifest.model_dump(),
        brand_primary=brand_tokens.brand_primary,
        brand_accent=brand_tokens.brand_accent,
        brand_profile=request.client.brand_profile,
        design_brief=request.client.design_brief,
        output_dir=output_dir,
        http_client=http_client,
        openrouter_key=cfg.openrouter_key_str(),
        prompt_model=cfg.openrouter_prompt_model,
        fal_key=cfg.fal_key_str(),
        fal_model=cfg.fal_image_model,
        fal_resolution=cfg.fal_image_resolution,
        cache_dir=Path(cfg.asset_cache_dir),
        max_generations_per_report=cfg.max_generations_per_report,
    )

    # Stage 6
    components = generate_components_for_report(
        request.report_json.pages,
        brand_primary=brand_tokens.brand_primary,
        brand_accent=brand_tokens.brand_accent,
        brand_neutral_light=brand_tokens.brand_neutral_light,
        structured=structured,
    )

    # Stage 7
    plan = plan_layout(
        request.report_json.pages,
        components=components,
        page_count_target=request.report_json.meta.page_count_target,
    )
    layout_summary = LayoutPlanSummary(**layout_plan_to_summary(plan))
    component_count = sum(len(v) for v in components.values())

    # Stage 8 — write the resolved package to `output_dir`.
    report_json_dict = request.report_json.model_dump()
    resolved = await assemble_package(
        brand_tokens=brand_tokens.model_dump(),
        font_config=font_config,
        copy_warnings=copy_warnings,
        cover_validation=cover_validation,
        asset_plan=asset_plan,
        components=components,
        layout_plan=plan,
        report_json=report_json_dict,
        output_dir=output_dir,
        axes=axes,
        axes_provenance=axes_provenance,
        structured=structured,
        page_slots=page_slots,
        client_dir=client_dir,
    )

    # Stage 8.5 — intelligent routing shared with the fixture builder (dark-divider
    # cadence + diagram proof layer + SOCIAL routing). The live path has no
    # hand-authored classification, so the manifest is DERIVED deterministically
    # from the client's IG folder (build_manifest_from_folder: filename-pattern
    # roles, client-name containment, testimonial markers — no LLM, no credits,
    # no fabrication). A client without an IG folder yields an empty manifest and
    # zero bindings (graceful: the deck renders with no social placements).
    from stages.route_package import route_package
    from stages.plan_social import build_manifest_from_folder
    _pkg_path = Path(resolved.package_path)
    _pkg = json.loads(_pkg_path.read_text(encoding="utf-8"))
    _manifest = build_manifest_from_folder(client_dir / "ig", handle=client_dir.name)
    await route_package(
        _pkg, manifest=_manifest, social_root=client_dir / "ig",
        assets_dir=output_dir / "assets",
        openrouter_key=cfg.openrouter_key_str(),
        restructure_model=cfg.openrouter_restructure_model,
        restructure_cache_dir=Path(cfg.restructure_cache_dir),
    )
    _pkg_path.write_text(json.dumps(_pkg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    asset_summary = AssetSummary(**resolved.asset_summary)
    response_status = "warn" if warnings else "success"

    # Opt-in autonomy spine (non-breaking): render + grade + ship the built
    # package in the background, delivering the outcome to the webhook. Existing
    # callers (ship unset/false) are unaffected and still get the package path now.
    if getattr(request, "ship", False):
        background_tasks.add_task(
            _orchestrate_and_deliver,
            Path(resolved.output_dir),
            request.ship_webhook or cfg.report_generator_webhook,
            request.record_id,
        )

    return RenderResponse(
        status=response_status,
        validated_brand_tokens=brand_tokens,
        font_config=font_config,
        cover_validation=cover_validation,
        copy_warnings=copy_warnings,
        layout_plan=layout_summary,
        component_count=component_count,
        asset_summary=asset_summary,
        package_path=str(resolved.package_path),
        output_dir=str(resolved.output_dir),
        page_count=resolved.page_count,
        total_warnings=resolved.total_warnings,
        errors=errors,
        warnings=warnings,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Health check
# ─────────────────────────────────────────────────────────────────────────────


@app.get("/")
def root() -> dict:
    return {
        "service": "dmc-preprocessor",
        "layer": 1,
        "version": app.version,
        "phase": "D",
        "endpoints": ["/render", "/onboard"],
    }
