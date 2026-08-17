# Bake-In the Generative Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the shipped apex deck (and any live `/render` client) actually USE the generative capability we already built (fal/Nano Banana imagery + textures, intelligent social/diagram/restructure routing, the code-drawn infographic families), instead of leaving ~two thirds of it unwired.

**Architecture:** The disconnect is one fault line plus several unwired leaves. `research/v7-renderer/render.py` rasterizes a FROZEN `fixtures/apex/resolved_package.json` built by a hand-run `fixtures/apex/build_package.py`; the live `research/preprocessor/main.py:/render` writes to a throwaway temp dir nobody reads. The rich post-assemble routing (`plan_social`/`apply_social_plan`, ST-07B `page_mode` dark dividers, `restructure_page`, `plan_diagrams`/`apply_diagram_plan`) lives ONLY in `build_package.py`; fal generation is wired ONLY into `/render`. We unify them: extract a shared brand-agnostic `route_package()` both callers invoke, teach `render.py` to consume any built package, activate fal in hybrid mode (fal draws imagery + textures, code draws all data viz), expand the code-drawn infographic coverage, then surface the dormant assets/textures.

**Tech Stack:** Python 3 (FastAPI preprocessor + Jinja/WeasyPrint+Chromium renderer), pydantic v2, pytest, fal.ai (`fal-ai/nano-banana-pro`), OpenRouter (restructure/prompt LLM), Pillow/numpy (procedural texture). Two venvs: `research/preprocessor/.venv`, `research/v7-renderer/.venv`. Always `export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib`. No git in this repo. API keys ONLY in `research/preprocessor/.env`; never print/log them. Brand-agnostic: no client name/hex/font literal in shared pipeline logic.

**Decisions locked with the user (2026-06-17):**
- Infographics = HYBRID: code-drawn SVG for anything with real numbers (exact, no hallucinated digits); fal for imagery + textures only.
- Scope = BOTH: unify so the apex fixture AND live per-client `/render` both run the full routing + fal.

---

## Phasing (this is a multi-subsystem effort; each phase ships working, testable software)

- **Phase 1 (keystone, detailed below): Unify the routing.** Extract `route_package()` used by BOTH `/render` and `build_package.py`. After this, production renders get the same intelligent routing the fixture has.
- **Phase 2: Ship-build-path.** `render.py --package-dir` so the renderer can rasterize any freshly built package, not just the frozen fixture.
- **Phase 3: fal activation (hybrid).** `build_package.py --fal` calls real `generate_assets` (Nano Banana) for imagery + textures; regenerate apex with fal ON; budget-capped.
- **Phase 4: Hybrid infographic expansion.** Finish MAGNITUDE + PROCESS code-drawn families (curation + host wiring) and back-fill grounded chart specs so more than 6/20 pages carry real data viz.
- **Phase 5: Surface dormant assets + page texture.** Wire `procedural_texture.generate_brand_texture` into asset generation, route the unused report_assets onto photo-less pages, apply the user-approved page texture (marble/pattern, legibility-safe), and resolve `composite_device_mockup` (wire or delete).

Phases 2-5 each become their own detailed plan at execution time (each needs a deep read of its target files). Phase 1 is fully specified here because it unblocks everything and the divergent code already exists to extract.

---

## Phase 1: Unify the post-assemble routing into `route_package()`

**Why first:** Converts the four "fixture-only" routing capabilities into genuinely shippable ones and stops `build_package.py` and `/render` from diverging. Pure refactor + re-wire; no new behavior, so it is verifiable against the existing fixture output (the regenerated package must be byte-equivalent on the routed fields).

**Files:**
- Create: `research/preprocessor/stages/route_package.py` (the shared routing function)
- Create: `research/preprocessor/tests/test_route_package.py`
- Modify: `research/v7-renderer/fixtures/apex/build_package.py:140-298` (replace inline routing with a `route_package(...)` call; keep apex-only `apply_apex_viz` after it)
- Modify: `research/preprocessor/main.py:452` (call `route_package(...)` after `assemble_package`, before building the response)

**Interface (the one function both callers use):**
```python
# research/preprocessor/stages/route_package.py
async def route_package(
    pkg: dict,                       # the parsed resolved_package.json (mutated in place)
    *,
    manifest: "AssetManifest | None", # social asset manifest; None -> skip social routing
    social_root: Path,                # dir holding the social source images (client_dir/"ig")
    assets_dir: Path,                 # package assets dir (output_dir/"assets")
    enable_profile_grid: bool = False,
    openrouter_key: str = "",         # "" -> skip LLM restructure (pages left verbatim)
    restructure_model: str = "",
    restructure_cache_dir: Path | None = None,
    dark_divider_types: frozenset[str] = frozenset({"ST-07B"}),
) -> "RouteReport":
    """Brand-agnostic post-assemble routing: social placement -> page_mode dark
    cadence -> LLM restructure (optional) -> diagram proof layer. Mutates pkg.
    NO client literals; every name/home is derived from pkg data. Returns a
    RouteReport (bindings + dropped + restructured slots) for logging/asserts."""
```
The body is the EXACT logic currently at `build_package.py:151-298` (derive social homes from pkg, `plan_social`, `apply_social_plan`, set `page_mode="dark_divider"` on `dark_divider_types`, restructure flagged over-budget pages when `openrouter_key`, `plan_diagrams`/`apply_diagram_plan`). It must NOT include `apply_apex_viz` (apex-specific; stays in build_package.py after the call).

- [ ] **Step 1: Write the failing test** — `research/preprocessor/tests/test_route_package.py`

```python
import asyncio, json
from pathlib import Path
from stages.route_package import route_package
from models_social import AssetManifest

FIX = Path(__file__).resolve().parents[2] / "v7-renderer" / "fixtures" / "apex"

def _load(n): return json.loads((FIX / n).read_text(encoding="utf-8"))

def test_route_package_applies_social_and_diagram_bindings():
    # a package BEFORE routing: load the fixture and strip the routed fields
    pkg = _load("resolved_package.json")
    for p in pkg["pages"]:
        (p.get("data") or {}).pop("social_post", None)
        (p.get("data") or {}).pop("diagram", None)
        p.pop("page_mode", None)
    manifest = AssetManifest(**_load("asset_manifest.json"))
    report = asyncio.run(route_package(
        pkg, manifest=manifest, social_root=FIX.parent.parent.parent /
        "preprocessor" / "client_assets" / "apex" / "ig",
        assets_dir=FIX / "assets", enable_profile_grid=False,
        openrouter_key="",  # skip LLM so the test is offline + deterministic
    ))
    # ST-07B pages became dark dividers
    assert any(p.get("page_mode") == "dark_divider"
               for p in pkg["pages"] if p["st_type"] == "ST-07B")
    # exactly one ST-07A page got the matched social_post
    case_posts = [p for p in pkg["pages"]
                  if p["st_type"] == "ST-07A" and (p.get("data") or {}).get("social_post")]
    assert len(case_posts) == 1
    # every breather became a scene photo (apex: profile grid disabled)
    st31 = [p for p in pkg["pages"] if p["st_type"] == "ST-31"]
    assert all(any(a.get("image_type") == "scene" for a in (p.get("assets") or []))
               for p in st31)
    assert report.bindings  # non-empty
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd research/preprocessor && export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib && .venv/bin/python -m pytest tests/test_route_package.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'stages.route_package'`.

- [ ] **Step 3: Create `stages/route_package.py`** by MOVING the routing block out of `build_package.py`. Copy `build_package.py:151-298` verbatim into the function body, replacing: `pkg` is the parameter (not re-read from disk); `client_dir / "ig"` becomes `social_root`; `HERE / "assets"` becomes `assets_dir`; the `_Settings()` reads become the `openrouter_key`/`restructure_model`/`restructure_cache_dir` params; `manifest` is the param (skip the whole social+diagram block when `manifest is None`). Define a small `RouteReport` dataclass `(bindings: list, dropped: list, restructured: list[int])`. Add `from __future__ import annotations`. Brand-agnostic: keep deriving `case_clients`/`breather_slots`/`founder_name` from `pkg` exactly as the original does.

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd research/preprocessor && export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib && .venv/bin/python -m pytest tests/test_route_package.py -v`
Expected: PASS.

- [ ] **Step 5: Re-wire `build_package.py`** to call the shared function. Replace `build_package.py:151-298` with:
```python
        from stages.route_package import route_package
        from settings import Settings as _Settings
        _cfg = _Settings()
        report = await route_package(
            pkg, manifest=manifest, social_root=social_root,
            assets_dir=HERE / "assets", enable_profile_grid=False,
            openrouter_key=_cfg.openrouter_key_str(),
            restructure_model=_cfg.openrouter_restructure_model,
            restructure_cache_dir=HERE.parent.parent / _cfg.restructure_cache_dir,
        )
        from fixtures.apex.viz_curation import apply_apex_viz
        apply_apex_viz(pkg)            # apex-specific, stays here
        (HERE / "resolved_package.json").write_text(
            json.dumps(pkg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
```

- [ ] **Step 6: Regenerate the fixture and assert no regression** (the routed fields must be unchanged vs the committed fixture, proving the extraction was behavior-preserving)

Run: `cd research/preprocessor && export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib && set -a; . ./.env; set +a; .venv/bin/python ../v7-renderer/fixtures/apex/build_package.py`
Expected: the build_package sanity assertions (`build_package.py:314-385`) all pass; the `[social]`/`[diagram]`/`[viz]` logs match the prior run.

- [ ] **Step 7: Wire `route_package` into `main.py /render`** after `assemble_package` (`main.py:452`). The package was written to `output_dir`; re-read it, route it, write it back:
```python
    # Stage 8.5 — intelligent routing (shared with the fixture builder)
    from stages.route_package import route_package
    pkg_path = Path(resolved.package_path)
    pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
    manifest = request.asset_manifest if getattr(request, "asset_manifest", None) else None
    await route_package(
        pkg, manifest=manifest, social_root=client_dir / "ig",
        assets_dir=output_dir / "assets",
        openrouter_key=cfg.openrouter_key_str(),
        restructure_model=cfg.openrouter_restructure_model,
        restructure_cache_dir=Path(cfg.restructure_cache_dir),
    )
    pkg_path.write_text(json.dumps(pkg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
```
(If `RenderRequest` has no `asset_manifest` field yet, pass `manifest=None` for now; Phase 3/4 adds the manifest plumbing. With `manifest=None`, `route_package` still applies the data-driven diagram + dark-divider routing.)

- [ ] **Step 8: Verify the preprocessor suite + a live `/render` smoke**

Run: `cd research/preprocessor && export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib && .venv/bin/python -m pytest tests/test_route_package.py tests/test_plan_social.py tests/test_plan_diagrams.py -q`
Expected: all pass. Then a curl `/render` (or the existing endpoint test) returns `package_path` whose `resolved_package.json` now carries `data.diagram` on at least one page (proving routing reached production).

- [ ] **Step 9: Commit**
```bash
git add research/preprocessor/stages/route_package.py research/preprocessor/tests/test_route_package.py research/v7-renderer/fixtures/apex/build_package.py research/preprocessor/main.py
git commit -m "refactor: extract shared route_package() so /render and build_package stop diverging

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Phase 2: Ship-build-path (`render.py --package-dir`)

**Goal:** `render.py` can rasterize ANY built package, so the renderer is no longer permanently bound to the frozen fixture.
**Files:** Modify `research/v7-renderer/render.py:25,101` (add `--package-dir` argparse arg defaulting to `FIXTURES_APEX_DIR`; pass to `render_package`). Test: `research/v7-renderer/tests/test_render_cli.py` (argparse resolves an alternate dir; falls back to fixture when omitted).
**Verification:** `render.py --package-dir /tmp/somepkg` rasterizes that package; omitting it reproduces today's fixture render. No change to default behavior.

## Phase 3: fal activation (hybrid imagery + textures)

**Goal:** Generate the deck's imagery + textures through Nano Banana instead of re-feeding pre-baked photos; fal NEVER touches data viz.
**Files:** Modify `research/v7-renderer/fixtures/apex/build_package.py` (add a `--fal` flag: when set and `FAL_KEY` present, call the real `generate_assets(...)` from `main.py:399-415` with `fal_key`/`openrouter_key` instead of `_build_asset_plan`; default stays offline/reproducible). Confirm `/render` already does this (it does, `main.py:399-415`). `research/preprocessor/.env`: ensure `FAL_KEY` is set (user-provided; never printed). Budget `max_generations_per_report` default 12.
**Verification:** `build_package.py --fal` produces a package whose generate-class assets carry fal metadata (not "reused apex fixture image"); rendered cover/scene/fazit/textures are the fal images; offline default path unchanged; budget respected. Verify on pixels vs `refs/`.

## Phase 4: Hybrid infographic expansion (code-drawn)

**Goal:** Lift data-viz coverage past 6/20 pages with the already-built families, all code-drawn (numbers exact).
**Files:** Extend `research/v7-renderer/fixtures/apex/viz_curation.py` (bind MAGNITUDE `mega_numeral`/`money_bar`/`stat_strip` + PROCESS `phase_timeline`/`step_cascade` to ST-02/06/09 with VERBATIM grounded figures); add `data['viz']` read + `render_viz` dispatch to `patterns/st_02.py`, `st_06.py`, `st_09.py` (mirror `st_07a.py:307-319`); complete tasks VIZ-2b/3a/3b/4. Back-fill `report_content.json` chart-spec fields only where the narrative already states the figure (no fabrication; the grounding guard must stay green).
**Verification:** N>6 pages render a grounded data viz; the no-fabrication grounding guard passes; conformance + literals green; verified on pixels.

## Phase 5: Surface dormant assets + page texture + device mockup

**Goal:** Use what's built: page texture (the user's marble/pattern request), the orphaned report_assets, and a decision on the dead Pillow mockup compositor.
**Files:** Wire `research/preprocessor/stages/procedural_texture.py:generate_brand_texture` into `generate_assets.py` (texture dispatch: procedural vs fal); route unused `report_assets` (`atmospheric_gradient`/`extra_wide`/`extra_square`) onto photo-less pages via the existing `resolve_report_asset` fallbacks (`patterns/st_31.py`, `st_22.py`); apply USER-APPROVED page texture (generate swatches first, legibility-safe, behind content); either wire `composite_device_mockup` into a generator or delete it.
**Verification:** texture swatches approved by the user BEFORE deck-wide application; textures never drop text contrast below the panel-contrast threshold; report_assets paint on the intended pages; verified on pixels vs `refs/`.

---

## Self-Review notes
- **Spec coverage:** fal activation (P3), social/diagram/restructure routing (P1), ship-build-path (P2), hybrid infographics (P4), textures + dormant assets + mockups (P5). All audit gaps mapped to a phase.
- **No fabrication:** P3 fal imagery is decorative only; P4 viz binds verbatim figures behind the existing grounding guard; never generate a face for a real named person.
- **Brand-agnostic:** `route_package` (P1) derives every name from `pkg`; `apply_apex_viz` stays apex-only; no client literals enter shared pipeline logic.
- **Reproducibility:** offline defaults preserved (build_package without `--fal` still uses pre-baked images; `route_package` with `manifest=None` still routes diagrams). fal/LLM paths gated on keys present in `.env`.
