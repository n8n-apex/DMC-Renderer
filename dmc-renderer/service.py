"""dmc-renderer: HTTP service that turns an n8n {payload, images, brand_tokens}
envelope into a rendered print-ready PDF, end to end, with no manual step.

Wires the n8n pipeline to the real system: `build_live` runs the actual
preprocessor stage pipeline IN-PROCESS (structure -> assets -> components ->
layout -> assemble -> route) to produce the real package, then the v7 engine
(`research/v7-renderer/assembler.py::render_package`) renders it with Chromium.

QC MODEL (Path B, 2026-07-10 code review): the request renders the real
Chromium+treatments deck ONCE, grades THOSE EXACT BYTES, and ships them. Every
response field, header, and the strict gate is derived from the shipped artifact.
There is no inline auto-redo: the old converge/compose loop graded a WeasyPrint,
treatments-OFF render (an artifact that never shipped) and shipped an un-QC'd
composed deck. The density auto-fix loop (research/quality_loop) is a separate
offline tool, not wired into the ship path. See docs/code-review-2026-07-10.md.

Run:  DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib \
      .venv/bin/python -m uvicorn service:app --app-dir /Users/utkarsh/Projects/richard/dmc-renderer --port 8099
"""
from __future__ import annotations

import os
import json
import hashlib
import importlib
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable

# The v7 engine (`assembler`) must be importable for build_and_render.
# Env-overridable so the SAME code runs locally (default: this checkout) and in
# the container (Dockerfile sets DMC_RENDERER_ROOT=/app/research/v7-renderer).
RENDERER_ROOT = Path(os.environ.get(
    "DMC_RENDERER_ROOT", "/Users/utkarsh/Projects/richard/research/v7-renderer"))
if str(RENDERER_ROOT) not in sys.path:
    sys.path.insert(0, str(RENDERER_ROOT))


V3_IMPORT_MODULES = (
    "build_v3",
    "composition_registry.registry",
    "contracts_v3.render_contract",
    "design_policy.schema",
    "postprocessor.export_digital",
    "quality_loop.ship_gate_v3",
)
V3_IMMUTABLE_JSON_FILES = {
    "composition_registry": "research/composition_registry/families/dmc-v1.json",
    "reference_atlas": "research/reference-atlas/reference-atlas.json",
    "composition_policy": "research/preprocessor/policies/composition_scoring_v1.json",
    "product_profile": "research/preprocessor/policies/dmc_house_20_face.json",
    "pixel_policy": "research/quality_loop/policies/pixel_policy_v1.json",
    "design_policy": "research/design_policy/policies/dmc-print-v1.json",
    "design_policy_sources": "research/design_policy/sources.json",
    "workflow_contract": "docs/n8n/workflow-contract-v3.json",
}
V3_WORKFLOW_ARTIFACT_IDS = (
    "writer_prompt",
    "schema_resolver",
    "writer_gate",
    "source_ledger",
    "claim_gate",
)
V3_SYSTEM_TOOL_COMMANDS = {
    "ghostscript": ("gs", "--version"),
    "pdfinfo": ("pdfinfo", "-v"),
    "pdftotext": ("pdftotext", "-v"),
    "pdffonts": ("pdffonts", "-v"),
    "pdfimages": ("pdfimages", "-v"),
}


def _runtime_module_ready(module_name: str) -> bool:
    try:
        importlib.import_module(module_name)
    except Exception:  # noqa: BLE001 - readiness must report every import failure
        return False
    return True


def _system_tool_ready(_tool_name: str, command: tuple[str, ...]) -> bool:
    if shutil.which(command[0]) is None:
        return False
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            check=False,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return completed.returncode == 0


def _playwright_chromium_ready() -> bool:
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            executable_path = Path(playwright.chromium.executable_path)
        return executable_path.is_file() and os.access(executable_path, os.X_OK)
    except Exception:  # noqa: BLE001 - readiness must fail closed
        return False


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _immutable_runtime_file_checks(project_root: Path) -> tuple[dict, list[str]]:
    items: dict[str, dict] = {}
    failures: list[str] = []
    for artifact_id, relative_path in V3_IMMUTABLE_JSON_FILES.items():
        path = project_root / relative_path
        try:
            json.loads(path.read_text(encoding="utf-8"))
            items[artifact_id] = {"ok": True, "sha256": _sha256_path(path)}
        except (OSError, UnicodeError, json.JSONDecodeError):
            items[artifact_id] = {"ok": False}
            failures.append(f"immutable_file:{artifact_id}")

    workflow_artifacts: dict[str, dict] = {}
    contract_path = project_root / V3_IMMUTABLE_JSON_FILES["workflow_contract"]
    try:
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        contract = {"artifacts": []}
    contract_artifacts = contract.get("artifacts", [])
    artifact_ids = [
        artifact.get("artifact_id")
        for artifact in contract_artifacts
        if isinstance(artifact, dict)
    ]
    if (
        len(artifact_ids) != len(V3_WORKFLOW_ARTIFACT_IDS)
        or set(artifact_ids) != set(V3_WORKFLOW_ARTIFACT_IDS)
    ):
        failures.append("workflow_contract:artifact_set")
    resolved_root = project_root.resolve()
    for artifact in contract_artifacts:
        if not isinstance(artifact, dict):
            continue
        artifact_id = str(artifact.get("artifact_id", "unknown"))
        expected_hash = artifact.get("sha256")
        repository_path = artifact.get("repository_path")
        actual_hash = None
        path_is_scoped = False
        if isinstance(repository_path, str):
            artifact_path = (project_root / repository_path).resolve()
            path_is_scoped = (
                artifact_path == resolved_root
                or resolved_root in artifact_path.parents
            )
            if path_is_scoped:
                try:
                    actual_hash = _sha256_path(artifact_path)
                except OSError:
                    pass
        ok = (
            path_is_scoped
            and isinstance(expected_hash, str)
            and actual_hash == expected_hash
        )
        workflow_artifacts[artifact_id] = {
            "ok": ok,
            "sha256": actual_hash,
        }
        if not ok:
            failures.append(f"workflow_artifact:{artifact_id}")

    return {
        "ok": not failures,
        "items": items,
        "workflow_artifacts": workflow_artifacts,
    }, failures


def _v3_runtime_readiness(
    *,
    project_root: Path | None = None,
    import_probe: Callable[[str], bool] = _runtime_module_ready,
    browser_probe: Callable[[], bool] = _playwright_chromium_ready,
    tool_probe: Callable[[str, tuple[str, ...]], bool] = _system_tool_ready,
) -> dict:
    """Verify the frozen v3 runtime without building or rendering a report."""
    root = project_root or Path(__file__).resolve().parent.parent
    failures: list[str] = []

    import_items: dict[str, dict[str, bool]] = {}
    for module_name in V3_IMPORT_MODULES:
        try:
            ok = bool(import_probe(module_name))
        except Exception:  # noqa: BLE001 - readiness must fail closed
            ok = False
        import_items[module_name] = {"ok": ok}
        if not ok:
            failures.append(f"import:{module_name}")

    immutable_files, file_failures = _immutable_runtime_file_checks(root)
    failures.extend(file_failures)

    try:
        browser_ok = bool(browser_probe())
    except Exception:  # noqa: BLE001 - readiness must fail closed
        browser_ok = False
    if not browser_ok:
        failures.append("browser:chromium")

    tool_items: dict[str, dict[str, bool]] = {}
    for tool_name, command in V3_SYSTEM_TOOL_COMMANDS.items():
        try:
            ok = bool(tool_probe(tool_name, command))
        except Exception:  # noqa: BLE001 - readiness must fail closed
            ok = False
        tool_items[tool_name] = {"ok": ok}
        if not ok:
            failures.append(f"tool:{tool_name}")

    checks = {
        "imports": {"ok": all(item["ok"] for item in import_items.values()), "items": import_items},
        "immutable_files": immutable_files,
        "browser": {"ok": browser_ok},
        "tools": {"ok": all(item["ok"] for item in tool_items.values()), "items": tool_items},
    }
    return {
        "schema_version": "1.0",
        "ok": not failures,
        "checks": checks,
        "failures": failures,
    }


def _grade_deck_data(package_dir: Path) -> dict:
    """DATA-grounded QC report on the shipped deck. Uses only the ENGINE-AGNOSTIC
    checks that read the page DATA (not the rendered PDF), so they are correct on
    the Chromium ship artifact. Two owner-actionable signals per page:
      * N01 required_slots_missing -> a required slot (e.g. a case-study client
        photo) is absent  -> owner: asset_gen (supply the portrait)
      * N15 non_numeral_stat_values -> a stat callout value is prose, not a numeral
        -> owner: writer/preprocessor (put the figure in the stat slot)

    Why data-only: the full VISUAL grade (font embedding, dead space, contrast,
    reference-image comparison in research/quality_loop) is WeasyPrint-calibrated
    and cannot read a Chromium PDF's font table (PyMuPDF returns no fonts), so run
    on the ship path it reports a clean deck as 0-cleared. That visual grade stays
    an OFFLINE design-QA tool (its CLI, against a WeasyPrint render). The ship
    path grades only what is provably correct on the shipped bytes. See
    docs/code-review-2026-07-10.md. Never raises."""
    try:
        import json
        ql = RENDERER_ROOT.parent / "quality_loop"
        if str(ql) not in sys.path:
            sys.path.insert(0, str(ql))
        from perception import required_slots_missing, _non_numeral_stat_values  # noqa: E402

        pkg = json.loads((package_dir / "resolved_package.json").read_text(encoding="utf-8"))
        pages = pkg.get("pages", []) or []
        flags_by_owner: dict[str, list[str]] = {}
        needs_photo: list[str] = []
        prose_stats: list[str] = []
        clean = 0
        for i, page in enumerate(pages):
            page_had_flag = False
            for slot in required_slots_missing(page):
                msg = f"p{i} ({page.get('st_type')}) missing required slot: {slot}"
                flags_by_owner.setdefault("asset_gen", []).append(msg)
                needs_photo.append(msg)
                page_had_flag = True
            for val in _non_numeral_stat_values(page):
                msg = f"p{i} ({page.get('st_type')}) stat value is prose, not a numeral: {val!r}"
                flags_by_owner.setdefault("writer", []).append(msg)
                prose_stats.append(msg)
                page_had_flag = True
            if not page_had_flag:
                clean += 1
        return {
            "cleared": clean,
            "total": len(pages),
            "flags_by_owner": flags_by_owner,
            "needs_photo": needs_photo,
            "prose_stats": prose_stats,
            # the N01 missing-slot flags ARE the latching hard-fails (a case study
            # with no client photo). Surfaced so X-QC-Hard-Fails carries real data;
            # they are reported, NOT ship-blocking (see the gate).
            "hard_fails": needs_photo,
            "note": "data-grounded checks only; visual grade is an offline tool",
        }
    except Exception as e:  # noqa: BLE001 - the report is best-effort, not the gate
        return {"error": f"{type(e).__name__}: {e}", "hard_fails": [], "flags_by_owner": {}}


def build_and_render(envelope: dict, engine: str = "chromium",
                     grade: bool = True, cleanup: bool = False) -> dict:
    """Core middleware: {payload, images, brand_tokens} -> rendered PDF.

    Renders the REAL Chromium+treatments deck ONCE (build_live builds the actual
    preprocessor package in-process). QC (overflow, content defects, and the
    optional reference grade) is computed on THAT render. The returned pdf_bytes
    ARE the shipped bytes and every field describes them.

    cleanup=True (the HTTP path) reads the bytes and then removes the temp package
    dir in a finally, so no request leaks its working tree. cleanup=False (offline
    callers, tests) leaves pdf_path on disk for inspection.
    """
    from assembler import render_package  # imported here so import-time stays light
    import build_live
    import tempfile

    # The service OWNS the working dir so the finally can reclaim it even when
    # build_live_package raises mid-build (it used to mkdtemp internally and only
    # return the path on success, orphaning the dir on any build failure).
    pkg = Path(tempfile.mkdtemp(prefix="dmc_req_"))
    try:
        built = build_live.build_live_package(envelope, output_dir=pkg)
        out = pkg / "out"
        out.mkdir(parents=True, exist_ok=True)
        result = render_package(pkg, out, engine=engine, treatments=True)

        # STRUCTURAL ship gate, computed on the shipped render, always:
        #   overflow  = physical sheets != logical pages (a real spill)
        #   content   = CONTENT-QC warnings (literal None / raw container reprs)
        overflow = list(getattr(result, "overflow", []) or [])
        content_defects = [w for w in (getattr(result, "warnings", None) or [])
                           if str(w).startswith("CONTENT-QC")]

        # QUALITY report from the package DATA (best-effort; never gates shipping).
        qc = _grade_deck_data(pkg) if grade else None

        pdf_bytes = Path(result.pdf_path).read_bytes()
        return {
            "pdf_bytes": pdf_bytes,
            "pdf_path": None if cleanup else str(result.pdf_path),
            "page_count": result.page_count,                       # logical fragments
            "physical_pages": len(getattr(result, "png_paths", None) or []),  # real sheets
            "package_dir": None if cleanup else str(pkg),
            "component_count": built.get("component_count", 0),
            "report_assets": built.get("report_assets", 0),
            "overflow": overflow,
            "content_defects": content_defects,
            "reference_qc": qc,
        }
    finally:
        if cleanup:
            shutil.rmtree(pkg, ignore_errors=True)


def build_and_render_v3(envelope: dict, *, cleanup: bool = True, **kwargs) -> dict:
    """Run the isolated frozen-contract pipeline without changing v2 routing."""
    from build_v3 import build_and_render_v3 as run_v3

    return run_v3(envelope, cleanup=cleanup, **kwargs)


def _supported_workflow_versions_v3() -> dict[str, str]:
    contract_path = Path(__file__).resolve().parent.parent / "docs" / "n8n" / "workflow-contract-v3.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    supported = {"workflow_contract_version": contract["contract_version"]}
    supported.update(
        {
            artifact["envelope_version_field"]: artifact["semantic_version"]
            for artifact in contract["artifacts"]
        }
    )
    return supported


def _validate_workflow_versions_v3(body: dict) -> None:
    supported = _supported_workflow_versions_v3()
    missing = [field for field in supported if field not in body]
    if missing:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "workflow_versions_missing",
                "fields": missing,
            },
        )
    for field, expected in supported.items():
        if body[field] != expected:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "workflow_version_unsupported",
                    "field": field,
                    "expected": expected,
                    "received": body[field],
                },
            )


def expected_workflow_verification_bundle_v3() -> dict:
    contract_path = Path(__file__).resolve().parent.parent / "docs" / "n8n" / "workflow-contract-v3.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    return {
        "schema_version": "1.0",
        "workflow_contract_version": contract["contract_version"],
        "artifacts": [
            {
                "artifact_id": artifact["artifact_id"],
                "semantic_version": artifact["semantic_version"],
                "sha256": artifact["sha256"],
                "expected_node_name": artifact["expected_node_name"],
                "input_schema_version": artifact["input_schema_version"],
                "output_schema_version": artifact["output_schema_version"],
            }
            for artifact in contract["artifacts"]
        ],
    }


def _validate_workflow_verification_v3(body: dict) -> str:
    submitted = body.get("workflow_verification_v3")
    expected = expected_workflow_verification_bundle_v3()
    required_keys = set(expected) | {"verification_bundle_sha256"}
    if not isinstance(submitted, dict) or set(submitted) != required_keys:
        raise HTTPException(
            status_code=409,
            detail={"code": "workflow_verification_bundle_invalid"},
        )
    unsigned = {key: value for key, value in submitted.items() if key != "verification_bundle_sha256"}
    actual_hash = hashlib.sha256(
        json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if actual_hash != submitted["verification_bundle_sha256"]:
        raise HTTPException(
            status_code=409,
            detail={"code": "workflow_verification_bundle_hash_mismatch"},
        )
    if unsigned != expected:
        raise HTTPException(
            status_code=409,
            detail={"code": "workflow_artifact_mismatch"},
        )
    return actual_hash


# --- HTTP layer (optional import so the core is testable without fastapi) ------
try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import JSONResponse, Response

    app = FastAPI(title="dmc-renderer", version="0.2.0")

    # G8: every render route is a paid-fal + LLM trigger. Anyone who can reach
    # the port could spend credits / do unbounded work, so all three render
    # routes require `Authorization: Bearer ${RENDERER_SHARED_SECRET}` (read
    # via the _env_or_dotenv fallback, never logged). Health is exempt (it is
    # the liveness probe).
    _RENDER_ROUTES = {"/render", "/render-v3", "/render-legacy-v2"}

    def _shared_secret() -> str | None:
        """RENDERER_SHARED_SECRET from env, then the preprocessor .env."""
        value = os.environ.get("RENDERER_SHARED_SECRET")
        if value:
            return value
        try:
            env_path = (
                Path(__file__).resolve().parent.parent
                / "research" / "preprocessor" / ".env"
            )
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if line.startswith("RENDERER_SHARED_SECRET="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'") or None
        except OSError:
            pass
        return None

    @app.middleware("http")
    async def require_auth(request: Request, call_next):
        if request.url.path not in _RENDER_ROUTES:
            return await call_next(request)
        expected = _shared_secret()
        if not expected:
            # Fail closed: a missing secret must never open the door.
            return JSONResponse(
                status_code=500,
                content={
                    "error": "server_misconfigured",
                    "detail": "RENDERER_SHARED_SECRET is not set; refusing to serve render routes",
                },
            )
        auth = request.headers.get("Authorization", "")
        if auth != f"Bearer {expected}":
            return JSONResponse(
                status_code=401,
                content={"error": "unauthorized", "detail": "missing or invalid bearer token"},
            )
        return await call_next(request)

    @app.get("/health")
    def health():
        return {"ok": True, "engine_default": "chromium", "mode": "build_live (real package)"}

    @app.get("/health/v3")
    def health_v3_endpoint():
        readiness = _v3_runtime_readiness()
        return JSONResponse(
            status_code=200 if readiness["ok"] else 503,
            content=readiness,
        )

    @app.post("/render")
    def render_endpoint(body: dict):
        for k in ("payload", "images", "brand_tokens"):
            if k not in body:
                raise HTTPException(status_code=400, detail=f"missing required field '{k}'")
        engine = body.get("_engine", "chromium")
        if engine not in ("chromium", "weasyprint"):
            raise HTTPException(
                status_code=400,
                detail=f"unknown _engine {engine!r} (supported: chromium, weasyprint)")
        try:
            r = build_and_render(body, engine=engine,
                                 grade=body.get("_grade", True), cleanup=True)
        except Exception as e:  # noqa: BLE001
            raise HTTPException(status_code=500, detail=f"render failed: {type(e).__name__}: {e}")

        # STRICT ship gate: overflow + content defects are STRUCTURAL corruption,
        # always computed on the shipped render. The reference-QC hard-fails
        # (missing photo, dead space) are quality flags surfaced in headers +
        # body for the owner to act on; they do NOT block shipping (a deck with
        # the initials-avatar fallback is shippable, just not ideal).
        qc = r.get("reference_qc") or {}
        hard_fails = qc.get("hard_fails") or []
        qc_error = qc.get("error")
        # STRICT gate: block on structural corruption (overflow / content) AND on a
        # grader ERROR (the data-QC could not run) — the caller asked for strict QC,
        # so a QC leg that failed to run must FAIL CLOSED, not ship silently (C3).
        if body.get("_strict") and (r["overflow"] or r["content_defects"] or qc_error):
            raise HTTPException(status_code=422, detail={
                "error": ("overflow" if r["overflow"]
                          else "content_defects" if r["content_defects"]
                          else "qc_error"),
                "overflow": r["overflow"],
                "content_defects": r["content_defects"],
                "qc_error": qc_error,
                "reference_qc": qc,
                "logical_pages": r["page_count"],
                "physical_pages": r["physical_pages"],
            })
        return Response(
            content=r["pdf_bytes"],
            media_type="application/pdf",
            headers={
                "Content-Disposition": 'attachment; filename="report.pdf"',
                "X-Logical-Pages": str(r["page_count"]),
                "X-Physical-Pages": str(r["physical_pages"]),
                "X-Component-Count": str(r["component_count"]),
                "X-Overflow": str(len(r["overflow"])),
                "X-Content-Defects": str(len(r["content_defects"])),
                "X-QC-Cleared": f"{qc.get('cleared', '?')}/{qc.get('total', '?')}",
                "X-QC-Needs-Photo": str(len(hard_fails)),
                "X-QC-Prose-Stats": str(len(qc.get("prose_stats") or [])),
                "X-DMC-Pipeline-Version": "legacy-v2",
                "X-DMC-Release-State": "legacy-draft",
                # HTTP headers are latin-1 encoded; an exception message can carry
                # non-latin-1 glyphs (em dash, curly quotes, emoji from German copy)
                # -> encode-replace so a QC error string never 500s the response.
                "X-QC-Error": (qc_error or "").encode("ascii", "replace").decode("ascii")[:120],
            },
        )

    @app.post("/render-legacy-v2")
    def render_legacy_v2_endpoint(body: dict):
        """Named compatibility route while /render still defaults to v2."""
        return render_endpoint(body)

    @app.post("/render-v3")
    def render_v3_endpoint(body: dict):
        for key in ("payload", "images", "brand_tokens"):
            if key not in body:
                raise HTTPException(
                    status_code=400,
                    detail=f"missing required field '{key}'",
                )
        _validate_workflow_versions_v3(body)
        workflow_verification_hash = _validate_workflow_verification_v3(body)
        verified_body = {
            **body,
            "workflow_verification_bundle_sha256": workflow_verification_hash,
        }
        artifact_store_root = Path(
            os.environ.get("DMC_V3_ARTIFACT_ROOT")
            or Path(__file__).resolve().parent.parent / "research" / "artifacts" / "runs"
        )
        try:
            result = build_and_render_v3(
                verified_body,
                cleanup=True,
                artifact_store_root=artifact_store_root,
            )
        except Exception as error:  # noqa: BLE001 - converted to a stable API failure
            owner_stage = getattr(error, "owner_stage", None)
            code = getattr(error, "code", None)
            face_ids = tuple(getattr(error, "face_ids", ()) or ())
            element_ids = tuple(getattr(error, "element_ids", ()) or ())
            failures = tuple(getattr(error, "failures", ()) or ())
            if failures and owner_stage is None:
                first = failures[0]
                owner_stage = getattr(first, "owner_stage", "precomposition")
                code = getattr(first, "code", type(error).__name__)
                face_id = getattr(first, "face_id", None)
                face_ids = (face_id,) if face_id else ()
            raise HTTPException(
                status_code=422,
                detail={
                    "owner_stage": owner_stage or "v3_pipeline",
                    "code": code or type(error).__name__,
                    "face_ids": list(face_ids),
                    "element_ids": list(element_ids),
                    "detail": str(error),
                },
            ) from error

        hashes = result["hashes"]
        # Release state must be explicit. A missing or unknown state is a
        # server fault, never an implicit ship approval.
        release_state = result.get("release_state")
        if release_state is None:
            raise HTTPException(
                status_code=500,
                detail={"code": "release_state_missing"},
            )
        if release_state not in {"rejected", "draft", "review_candidate", "ship_ready"}:
            raise HTTPException(
                status_code=500,
                detail={"code": "release_state_unknown", "release_state": release_state},
            )
        gate_report_hash = result.get("gate_report_sha256", "")
        artifact_manifest = result.get("artifact_manifest") or {}
        provenance_headers = {
            "X-DMC-Release-State": release_state,
            "X-DMC-Gate-Report-SHA256": gate_report_hash,
            "X-DMC-Contract-Version": "3.0",
            "X-DMC-Contract-Hash": hashes["contract"],
            "X-DMC-Composition-Policy-Hash": hashes["composition_policy"],
            "X-DMC-Family-Registry-Hash": hashes["family_registry"],
            "X-DMC-Build-Hash": hashes["build"],
            "X-DMC-Artifact-Manifest-SHA256": artifact_manifest.get("manifest_sha256", ""),
            "X-DMC-Workflow-Verification-SHA256": result.get(
                "workflow_verification_bundle_sha256",
                workflow_verification_hash,
            ),
        }
        if release_state in {"rejected", "draft"}:
            return JSONResponse(
                status_code=422 if release_state == "rejected" else 202,
                content={
                    "release_state": release_state,
                    "delivery_pdf_available": False,
                    "failures": result.get("failures", []),
                    "hashes": hashes,
                    "gate_report_sha256": gate_report_hash,
                    "artifact_manifest": artifact_manifest,
                },
                headers=provenance_headers,
            )

        review_only = release_state == "review_candidate"
        if review_only:
            # Review candidates ship only the visibly marked review copy.
            pdf_bytes = result.get("review_pdf_bytes")
            if pdf_bytes is None:
                raise HTTPException(
                    status_code=500,
                    detail={"code": "review_artifact_missing"},
                )
        else:
            pdf_bytes = result.get("delivery_pdf_bytes") or result.get("pdf_bytes")
            if pdf_bytes is None:
                raise HTTPException(
                    status_code=500,
                    detail="v3 release result has no permitted PDF artifact",
                )
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": (
                    'attachment; filename="report-v3-review.pdf"'
                    if review_only
                    else 'attachment; filename="report-v3.pdf"'
                ),
                "X-Logical-Faces": str(result["face_count"]),
                "X-Rendered-Fragments": str(result["fragment_count"]),
                "X-Physical-Pages": str(result["physical_pages"]),
                "X-DMC-Review-Only": str(review_only).lower(),
                "X-DMC-Review-PNGs": str(
                    result.get("review_png_count", len(result.get("review_png_paths", [])))
                ),
                **provenance_headers,
            },
        )
except ModuleNotFoundError:
    app = None  # fastapi not installed yet; core build_and_render still usable
