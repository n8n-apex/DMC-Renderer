"""Regenerate fixtures/apex/resolved_package.json from structured apex DATA.

Reuses the REAL pre-processor stages (resolve_fonts, generate_components,
plan_layout, assemble_package) so the package schema cannot drift from
what /render produces. NO fal / NO network / NO API keys: the existing
apex images in fixtures/apex/assets/ are fed in directly as already-
generated AssetResults.

Run (pre-processor venv):
    cd research/preprocessor && .venv/bin/python ../v7-renderer/fixtures/apex/build_package.py

Phase 3 — fal activation (hybrid imagery + textures):
    The default build is OFFLINE and reproducible: the pre-baked apex images
    in fixtures/apex/assets/ are fed in directly via `_build_asset_plan` (no
    network, no keys). Passing `--fal` instead calls the REAL `generate_assets`
    (Nano Banana) for the generate-class assets (cover_hero, status_quo_scene,
    fazit_background, background_texture, atmospheric_gradient) using the
    FAL_KEY / OPENROUTER_API_KEY from research/preprocessor/.env. The REAL human
    photos (founder / proof / case-study) still come from resolve_slots — fal
    never fabricates a face for a named person, and fal never touches data viz.

    cd research/preprocessor && set -a; . ./.env; set +a; \\
        .venv/bin/python ../v7-renderer/fixtures/apex/build_package.py --fal
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent              # research/v7-renderer/fixtures/apex
V7 = HERE.parent.parent                              # research/v7-renderer
RESEARCH = V7.parent                                 # research
PREPROCESSOR = RESEARCH / "preprocessor"
sys.path.insert(0, str(PREPROCESSOR))
sys.path.insert(0, str(V7))  # so `fixtures.apex.viz_curation` (apply_apex_viz) resolves

from models import ReportJson, BrandProfile          # noqa: E402
from stages.resolve_fonts import resolve_fonts        # noqa: E402
from stages.generate_components import generate_components_for_report  # noqa: E402
from stages.plan_layout import plan_layout            # noqa: E402
from stages.assemble_package import assemble_package  # noqa: E402
from stages.generate_assets import AssetPlan, AssetResult, generate_assets, FAL_GENERATE_TIMEOUT_S  # noqa: E402
from stages.validate_copy import validate_copy        # noqa: E402
from stages.validate_copyfit import validate_copyfit  # noqa: E402
from stages.resolve_axes import resolve_axes            # noqa: E402
from stages.structure_content import structure_content  # noqa: E402
from stages.resolve_slots import resolve_slots          # noqa: E402
from stages.local_assets import client_assets_dir, list_client_assets  # noqa: E402
from models_social import AssetManifest                  # noqa: E402
from stages.plan_social import plan_social, apply_social_plan  # noqa: E402


# Phase 5: page texture. The light-page GROUND becomes a SUBTLE procedural
# BRAND MARBLE (user-approved swatch "C": ~16% marble over cream). The alpha
# constant + the blend helper live in the import-light ground_marble module so
# they can be exercised without build_package's heavy (pydantic) imports; we
# re-export the constant here so the Phase-5 step reads naturally.
from fixtures.apex.ground_marble import (  # noqa: E402
    GROUND_MARBLE_ALPHA,
    blend_marble_over_cream as _blend_marble_over_cream,
)


def _load(name: str) -> dict:
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse build_package CLI flags.

    Default (no flag) keeps the OFFLINE reproducible path (`_build_asset_plan`,
    pre-baked images, no keys). `--fal` switches to the REAL `generate_assets`
    (Nano Banana) for the generate-class imagery + textures.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Regenerate fixtures/apex/resolved_package.json. Offline by "
            "default; --fal generates imagery + textures via fal Nano Banana."
        )
    )
    parser.add_argument(
        "--fal",
        action="store_true",
        help=(
            "Generate the generate-class assets (cover_hero, status_quo_scene, "
            "fazit_background, background_texture, atmospheric_gradient) via the "
            "real fal/Nano Banana generator using FAL_KEY from .env. Without "
            "this flag the build is offline and re-feeds the pre-baked images."
        ),
    )
    return parser.parse_args(argv)


def _build_asset_plan(image_map: dict) -> AssetPlan:
    assets: list[AssetResult] = []
    assets_dir = HERE / "assets"
    for entry in image_map.get("page_assets", []):
        f = assets_dir / entry["file"]
        if not f.exists():
            raise FileNotFoundError(f"page asset missing: {f}")
        assets.append(AssetResult(
            slot_id=entry["slot_id"], status="generated", path=f,
            message="reused apex fixture image (R1 generator)",
            page_slot=int(entry["slot"]), image_type=entry["image_type"],
            prompt=None, negative_prompt=None,
        ))
    for entry in image_map.get("report_assets", []):
        f = assets_dir / entry["file"]
        if not f.exists():
            raise FileNotFoundError(f"report asset missing: {f}")
        assets.append(AssetResult(
            slot_id=entry["slot_id"], status="generated", path=f,
            message="reused apex fixture image (R1 generator)",
            page_slot=None, image_type=entry["image_type"],
            prompt=None, negative_prompt=None,
        ))
    return AssetPlan(
        assets=assets,
        total_required=len(assets), total_downloaded=0, total_stubbed=0,
        total_client_upload_needed=0, total_failed=0, total_generated=len(assets),
        warnings=[],
    )


async def main(use_fal: bool = False) -> int:
    brand_input = _load("brand_input.json")
    image_map = _load("image_map.json")
    report_content = _load("report_content.json")

    brand_tokens = brand_input["brand_tokens"]
    brand_profile = BrandProfile(**brand_input["brand_profile"])

    report_model = ReportJson(**report_content)
    pages = report_model.pages
    page_count_target = report_model.meta.page_count_target

    # v2.0: resolve the 7 design axes (replaces the old inline brand_axes dict).
    axes, axes_provenance = resolve_axes(
        brand_profile=brand_profile,
        brand_primary=brand_tokens["brand_primary"],
        brand_accent=brand_tokens["brand_accent"],
    )
    # v2.0: typed per-page data + rhetorical charts + social-proof.
    structured = structure_content(pages)
    # A3 case-study spreads: the case-study pages are ST-07A "casestudy_hero"
    # Doppelseiten (Richard's spread model for apex case studies) — an explicit
    # per-page hint so plan_layout resolves the variant AND the a3 sheet format
    # (the hand-edited JSON re-bakes reproducibly now).
    for page in pages:
        if page.type == "ST-07A":
            page.layout_variant = "casestudy_hero"
    # v2.0: resolve human-photo slots from the apex Client Assets folder
    # (renamed photos live in research/preprocessor/client_assets/apex/).
    client_dir = client_assets_dir("apex", base=PREPROCESSOR / "client_assets")
    drive_listing = list_client_assets(client_dir)
    page_slots: dict[int, list] = {}
    case_counter = 0
    for page in pages:
        case_index = None
        if page.type == "ST-07A":
            case_counter += 1
            fn = page.data.get("fallstudie_number") if isinstance(page.data, dict) else None
            case_index = int(fn) if (isinstance(fn, int) or (isinstance(fn, str) and fn.isdigit())) else case_counter
        page_slots[page.slot] = resolve_slots(page.type, drive_listing, case_index=case_index)

    # Supporting SCENE slot per case study (fal-generated brand-toned abstract,
    # US-303): a "case_scene" entry on each A3 spread page — the renderer's
    # .csh-scene band fills the void between narrative sections. The asset
    # files come from the OFFLINE image_map (the fal run already baked them
    # into fixtures/apex/assets/), so a re-bake stays reproducible with no keys.
    for page in pages:
        if page.type != "ST-07A":
            continue
        fs = None
        fn = page.data.get("fallstudie_number") if isinstance(page.data, dict) else None
        if isinstance(fn, int) or (isinstance(fn, str) and fn.isdigit()):
            fs = int(fn)
        if not fs:
            continue
        scene_file = HERE / "assets" / f"{fs}_cs{fs}_scene.png"
        if scene_file.exists():
            page_slots[page.slot] = page_slots.get(page.slot, []) + [
                {"slot_id": "case_scene", "status": "resolved", "path": f"assets/{fs}_cs{fs}_scene.png"}
            ]

    font_config = resolve_fonts(brand_profile)
    components = generate_components_for_report(
        pages,
        brand_primary=brand_tokens["brand_primary"],
        brand_accent=brand_tokens["brand_accent"],
        brand_neutral_light=brand_tokens["brand_neutral_light"],
        structured=structured,  # so data-driven chart SVGs are generated per page
    )
    plan = plan_layout(pages, components=components, page_count_target=page_count_target)

    # Stage 5 — asset plan. Two paths:
    #   default  → OFFLINE: re-feed the pre-baked apex images (reproducible, no
    #              keys, no network).
    #   --fal    → REAL: call generate_assets (Nano Banana) for the generate-class
    #              imagery + textures, mirroring main.py:/render (lines ~399-415).
    #              The REAL human photos (founder/proof/case-study) still come from
    #              resolve_slots above; fal never fabricates a named person's face
    #              and never touches data viz.
    if use_fal:
        from settings import Settings as _Settings  # noqa: PLC0415
        _cfg = _Settings()
        # generate_assets builds the generate-class assets from PROMPTS, not from
        # downloaded URLs, so the apex fixture needs no image_manifest — pass an
        # empty one (no URLs to download → no human-photo fabrication here).
        async with httpx.AsyncClient(
            # 2K Nano Banana generations routinely exceed the 30s http default;
            # give the read a generous window so concurrent gens don't ReadTimeout.
            timeout=httpx.Timeout(max(FAL_GENERATE_TIMEOUT_S, 300.0), connect=15.0),
            follow_redirects=True,
        ) as _http_client:
            asset_plan = await generate_assets(
                pages=pages,
                image_manifest={"images": []},
                brand_primary=brand_tokens["brand_primary"],
                brand_accent=brand_tokens["brand_accent"],
                brand_profile=brand_profile,
                design_brief=brand_input.get("design_brief"),
                output_dir=HERE,
                http_client=_http_client,
                openrouter_key=_cfg.openrouter_key_str(),
                prompt_model=_cfg.openrouter_prompt_model,
                fal_key=_cfg.fal_key_str(),
                fal_model=_cfg.fal_image_model,
                fal_resolution=_cfg.fal_image_resolution,
                cache_dir=PREPROCESSOR / _cfg.asset_cache_dir,
                max_generations_per_report=_cfg.max_generations_per_report,
            )
        print(
            f"[fal] generated={asset_plan.total_generated} "
            f"stubbed={asset_plan.total_stubbed} failed={asset_plan.total_failed}"
        )
    else:
        asset_plan = _build_asset_plan(image_map)

    # COURSE-CORRECTION (2026-06-17): rip out fal AI SCENE/BACKGROUND/GRADIENT
    # imagery. These rendered as slop — Nano Banana literally drew the raw German
    # page text, because the Sonnet prompt-builder (stages/build_image_prompts.py)
    # returns {} without a design_brief and apex has none, so generate_assets fell
    # back to dumping the page text as the subject. They were also mostly unrendered.
    # We keep REAL photos (slots) + the procedural marble ground (background_texture,
    # image_type "texture"). fal stays WIRED (--fal) for when we add a design_brief
    # and art-direct it; until then NO AI scene/background reaches the deck.
    # Target the 4 AI generate-class slots by slot_id (surgical: does NOT touch the
    # real Instagram breather "scene" photos, which are social-routed under other ids).
    # fazit_background removed from this set AND from generate_assets (G7): ST-FAZIT
    # grounds on the panel_texture report asset; the per-page background had no reader.
    _SUPPRESS_SLOTS = {
        "cover_hero", "status_quo_scene", "atmospheric_gradient",
        "status_quo_scene_b", "extra_square", "extra_wide",
    }
    asset_plan.assets = [
        a for a in asset_plan.assets if a.slot_id not in _SUPPRESS_SLOTS
    ]

    copy_warnings = validate_copy(pages) + validate_copyfit(pages)

    resolved = await assemble_package(
        brand_tokens=brand_tokens,
        font_config=font_config,
        copy_warnings=copy_warnings,
        cover_validation=None,
        asset_plan=asset_plan,
        components=components,
        layout_plan=plan,
        report_json=report_content,
        output_dir=HERE,
        axes=axes,
        axes_provenance=axes_provenance,
        structured=structured,
        page_slots=page_slots,
        client_dir=client_dir,
    )

    # ---- intelligent asset-routing (Phase 1 — Social Layout Planner) ----
    # Load the hand-authored classified manifest (the Phase-2 interceptor's
    # output, simulated for apex), decide social placements deterministically,
    # and write them onto the package. The manifest source files live in the
    # apex IG Client Assets folder (= source_root for staging).
    pkg = json.loads((HERE / "resolved_package.json").read_text(encoding="utf-8"))
    social_root = client_dir / "ig"
    manifest_path = HERE / "asset_manifest.json"
    manifest = AssetManifest(**_load("asset_manifest.json")) if manifest_path.exists() else None

    from stages.route_package import route_package
    from settings import Settings as _Settings
    _cfg = _Settings()
    _report = await route_package(
        pkg, manifest=manifest, social_root=social_root, assets_dir=HERE / "assets",
        enable_profile_grid=False, openrouter_key=_cfg.openrouter_key_str(),
        restructure_model=_cfg.openrouter_restructure_model,
        restructure_cache_dir=HERE.parent.parent / _cfg.restructure_cache_dir,
    )
    print(f"[route] social_bindings={len(_report.bindings)} restructured={_report.restructured}")

    from fixtures.apex.viz_curation import apply_apex_viz
    apply_apex_viz(pkg)

    # ---- US-606 Director page briefs (the contract object, persisted) ----
    # ONE brief per physical page: client/report identity + the selected
    # reference (from the legacy index when no Supabase DSN) + the visual job
    # + verbatim must_show + deterministic page_arc/region_plan/devices. The
    # renderer + QA consume these from the package.
    from stages.director import compose_page_brief
    from stages.assemble_package import _write_director_brief

    _dsn = None
    try:
        from settings import Settings as _S
        _cfg = _S()
        _dsn = _cfg.supabase_pooler_url or None
    except Exception:
        _dsn = None
    for page in pkg["pages"]:
        _st = str(page.get("st_type") or "")
        _data = page.get("data") or {}
        _ref = None
        try:
            from stages.director import _legacy_select
            _cands = _legacy_select(_st, 1)
            _ref = _cands[0] if _cands else None
        except Exception:
            _ref = None
        _brief = compose_page_brief(
            st_type=_st, data=_data,
            client_slug="apex", report_id="APEX-R1",
            page_key=str(page.get("page_id") or f"slot.{page.get('slot')}"),
            section_id=str(page.get("section_id") or f"section.{page.get('slot')}"),
            reference=_ref,
            continuation_role=str(page.get("continuation_role") or ""),
        )
        _write_director_brief(page, _brief)

    # ---- A3 case-study supporting SCENES (US-303) ----
    # The fal-generated brand-toned abstract scenes (assets/<n>_cs<n>_scene.png)
    # ride the package as a `case_scene` slot on each A3 spread page — the
    # renderer's .csh-scene band fills the void between narrative sections.
    # Pure post-mutation (like apply_apex_viz): deterministic, no keys, and a
    # re-bake reproduces it because the files are baked into the fixture.
    for page in pkg["pages"]:
        if page.get("st_type") != "ST-07A":
            continue
        fn = (page.get("data") or {}).get("fallstudie_number")
        if isinstance(fn, int) or (isinstance(fn, str) and fn.isdigit()):
            fs = int(fn)
        else:
            continue
        scene_path = HERE / "assets" / f"{fs}_cs{fs}_scene.png"
        if not scene_path.exists():
            continue
        existing = [s for s in page.get("slots", []) if s.get("slot_id") == "case_scene"]
        if not existing:
            page.setdefault("slots", []).append(
                {"slot_id": "case_scene", "status": "resolved",
                 "path": f"assets/{fs}_cs{fs}_scene.png"}
            )

    (HERE / "resolved_package.json").write_text(
        json.dumps(pkg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )

    # ---- Phase 5: page texture (subtle procedural BRAND MARBLE) ----------
    # Runs AFTER the asset plan + routing, for BOTH the offline and --fal paths.
    # The light-page GROUND is fed by the package's `background_texture`
    # report-asset (assembler.py: resolve_report_asset(("background_texture",
    # "atmospheric_gradient")) -> report_ground_uri -> [data-ground-mode="light"]
    # .page background-image). So whatever PNG that report-asset points to BECOMES
    # the page ground. Here we OVERWRITE that PNG with a subtle brand marble:
    # generate the procedural marble at the ground's existing pixel size, blend it
    # over a solid cream (brand_neutral_light) at GROUND_MARBLE_ALPHA (0.16,
    # swatch "C"), and write it back. Brand-agnostic: all colours from
    # brand_tokens; the only literal is the alpha. Graceful: if the package has no
    # background_texture asset, skip (do not crash).
    _bg_asset = next(
        (a for a in pkg.get("report_assets", [])
         if a.get("slot_id") == "background_texture" and a.get("path")),
        None,
    )
    if _bg_asset is None:
        print("[ground] no background_texture report-asset, skipping marble ground")
    else:
        from PIL import Image  # noqa: PLC0415
        _ground_path = HERE / _bg_asset["path"]
        # Match the existing ground image dimensions (apex ~1792x2400); fall back
        # to the print floor if the file is somehow absent.
        if _ground_path.exists():
            with Image.open(_ground_path) as _existing:
                _gw, _gh = _existing.size
        else:
            _gw, _gh = 1792, 2400
        _marble_ground = _blend_marble_over_cream(
            width=_gw,
            height=_gh,
            brand_neutral_light=brand_tokens["brand_neutral_light"],
            brand_accent=brand_tokens["brand_accent"],
            brand_primary=brand_tokens["brand_primary"],
            alpha=GROUND_MARBLE_ALPHA,
        )
        _ground_path.parent.mkdir(parents=True, exist_ok=True)
        _marble_ground.save(_ground_path, format="PNG")
        print(
            f"[ground] wrote subtle brand marble ({_gw}x{_gh}, "
            f"alpha={GROUND_MARBLE_ALPHA}) -> {_bg_asset['path']}"
        )

    # ---- sanity assertions (FAIL LOUD if the package is wrong) ----
    st_types = [p["st_type"] for p in pkg["pages"]]
    # US-603: the physical page count may EXCEED the logical 20 — ST-06's copy
    # exceeds its per-page capacity and the section legitimately expands into
    # a second physical page (user directive: sections may use as many pages
    # as required). The count is only floor-checked; identity fields mark the
    # continuation.
    assert len(pkg["pages"]) >= 20, f"expected >=20 pages, got {len(pkg['pages'])}"
    assert st_types[0] == "ST-01" and st_types[-1] == "ST-03", st_types
    assert st_types.count("ST-07A") == 5, st_types
    # Case-study pages are the A3 casestudy_hero spreads; the other fill-default
    # ST types (ST-07B/22/FAZIT) must carry the "fill" hint; every OTHER ST
    # type must NOT be forced one.
    _FILL_DEFAULT_TYPES = {"ST-07B", "ST-22", "ST-FAZIT"}
    fill_variants = [
        (p["slot"], p["st_type"], p.get("layout_variant")) for p in pkg["pages"]
        if p["st_type"] in _FILL_DEFAULT_TYPES
    ]
    assert all(v == "fill" for _, _, v in fill_variants), fill_variants
    case_variants = [
        (p["slot"], p.get("layout_variant"), p.get("page_format"))
        for p in pkg["pages"] if p["st_type"] == "ST-07A"
    ]
    assert all(v == "casestudy_hero" and fmt == "a3" for _, v, fmt in case_variants), case_variants
    assert not any(
        "layout_variant" in p for p in pkg["pages"]
        if p["st_type"] not in _FILL_DEFAULT_TYPES and p["st_type"] != "ST-07A"
    ), "a non-fill-default page was forced a layout_variant"
    assert all("page_numbers" in p for p in pkg["pages"]), "page_numbers missing"
    cover_assets = [a["slot_id"] for a in pkg["pages"][0]["assets"]]
    # The fal AI cover_hero is ripped out; the real founder PHOTO (slot) is the
    # cover hero (the founder slot is asserted resolved below).
    assert "cover_hero" not in cover_assets, cover_assets
    # After the AI scene/background rip-out the only report ground is the
    # procedural marble (background_texture), so require >=1.
    assert len(pkg["report_assets"]) >= 1, pkg["report_assets"]

    # ---- v2.0 contract assertions ----
    assert pkg["version"] == "2.0", pkg["version"]
    assert "axes" in pkg and len(pkg["axes"]) == 7, pkg.get("axes")
    assert "slot_summary" in pkg, "slot_summary missing"
    cover_slots = {s["slot_id"]: s for s in pkg["pages"][0].get("slots", [])}
    assert cover_slots.get("founder", {}).get("status") == "resolved", cover_slots
    about_page = next(p for p in pkg["pages"] if p["st_type"] == "ST-05")
    about_proofs = [
        s for s in about_page.get("slots", [])
        if s["slot_id"] == "proof" and s["status"] == "resolved"
    ]
    assert len(about_proofs) == 3, about_page.get("slots", [])

    # ---- social-routing contract assertions (Phase 1, INTENDED bindings) ----
    # These shifted the package by exactly the planner's social bindings; they
    # assert the planner reproduced the deck's social layout.
    st31_pages = [p for p in pkg["pages"] if p["st_type"] == "ST-31"]
    # The profile grid is DISABLED for apex (enable_profile_grid=False) — EVERY
    # breather is a full-bleed founder-in-action scene photo; NO grid is present.
    assert not any(
        ((p.get("data") or {}).get("social_post") or {}).get("grid")
        for p in st31_pages
    ), "profile grid must be disabled for apex"
    scene_breathers = [
        p for p in st31_pages
        if any(a.get("image_type") == "scene"
               and str(a.get("path", "")).startswith("assets/ig_")
               for a in (p.get("assets") or []))
    ]
    assert len(scene_breathers) == len(st31_pages) and len(scene_breathers) >= 3, (
        f"expected every breather to be a scene photo; "
        f"got {len(scene_breathers)}/{len(st31_pages)}"
    )
    # ST-05 testimonials present + body trimmed to 2 paragraphs (copy-fit).
    about_testimonials = (about_page.get("data") or {}).get("testimonials") or []
    assert len(about_testimonials) == 2, about_testimonials
    about_body = (about_page.get("data") or {}).get("body") or ""
    assert isinstance(about_body, str) and about_body.count("\n\n") <= 1, (
        "ST-05 body must be trimmed to ≤2 paragraphs when testimonials bound"
    )
    # the matched case-study post landed on exactly one ST-07A page.
    case_posts = [
        p for p in pkg["pages"]
        if p["st_type"] == "ST-07A" and (p.get("data") or {}).get("social_post")
    ]
    assert len(case_posts) == 1, [p["slot"] for p in case_posts]
    # FAZIT author sign-off present.
    fazit_page = next(p for p in pkg["pages"] if p["st_type"] == "ST-FAZIT")
    assert (fazit_page.get("data") or {}).get("author", {}).get("name"), "FAZIT author missing"

    print(f"[build_apex] wrote {resolved.package_path}")
    print(f"[build_apex] pages={len(pkg['pages'])} st07a={st_types.count('ST-07A')} "
          f"report_assets={len(pkg['report_assets'])} warnings={resolved.total_warnings}")

    # Provenance marker: ONLY a successful --fal build writes .fal_active, which
    # arms the wiring gate's anti-cache provenance row
    # (test_phase3_no_stale_fixture_provenance_when_fal_on). A plain offline
    # build never touches it, so the row stays dormant until fal really ran.
    if use_fal:
        (HERE / ".fal_active").write_text(
            "fal generation active for the apex deck (Phase 3)\n", encoding="utf-8",
        )
        print("[fal] wrote .fal_active marker")

    return 0


if __name__ == "__main__":
    _args = _parse_args()
    raise SystemExit(asyncio.run(main(use_fal=_args.fal)))
