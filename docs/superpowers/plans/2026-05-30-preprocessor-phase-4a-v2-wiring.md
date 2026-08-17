# Pre-Processor Phase 4a — Package v2.0 Wiring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Wire the built-but-unwired Phase 2–3 capabilities (axes, typed page-data, charts, social-proof, slot-resolved real photos, fal cache + budget + texture templates) into the `/render` flow and promote `resolved_package.json` from a hand-built v1.0 dict to a validated `ResolvedPackageManifest` **v2.0**.

**Architecture:** Phase 4a of the cross-layer Phase 4 (4b = the renderer expansion, separate plan). The package gains `axes` (7 fields incl. `ground_mode`), a transitional `brand_axes` (4-field, for the not-yet-upgraded renderer), `provenance`, a `slot_summary`, and per-page `data`(typed) / `charts` / `social_proof` / `slots[]` — with real photos resolved from a local `client_assets/<client>/` folder (the Drive substitute) and **copied into the package**. `/render` stays **synchronous** (an async flip would break the n8n caller).

**Tech Stack:** Python 3.11, FastAPI, Pydantic v2. No new deps.

> **★ THIS PLAN WAS CORRECTED 2026-06-02 after a deep md-grounded review (3 review agents + code reading).** The review proved the original Tasks 4–7 had the wrong integration design. The corrected design (Tasks 4–9 below) fixes four verified contract gaps:
> 1. **Axes key/shape mismatch** — the renderer reads `brand_axes` and whitelists only 4 fields; it has NO reader for `palette`/`qr_enabled`/`density`. v2.0 emits the canonical 7-field `axes` for 4b AND a derived 4-field `brand_axes` so the current renderer keeps theming (no regression in the 4a→4b gap).
> 2. **Slot-id contract gap** — `ResolvedSlot` had no `slot_id`/`image_type`/`aspect_ratio`; the renderer scans `case_study_portrait` (ST-07A) + `_PORTRAIT_SLOTS={about_portrait,founder_portrait,founder,about_founder}` (ST-05). Fix: `SlotSpec` declares the renderer-facing `slot_id`+`image_type`; `resolve_slots` carries them; the package emits a clean per-page `slots[]` (drive photos only) with files copied in. 4b reads `slots[]`.
> 3. **Two competing slot systems** — legacy `IMAGE_REQUIREMENTS` (wired) vs `slot_registry` (unwired) disagreed on `required`. Fix: separate by SOURCE — `resolve_slots` owns human/drive photos (`slots[]`); `generate_assets` owns fal generate/composite + manifest downloads (`assets[]`/`report_assets`). The human "client" entries (`cover_author`, `about_logo`, `case_study_portrait`) are REMOVED from `IMAGE_REQUIREMENTS`.
> 4. **`case_index` had no producer** — derive it from `data.fallstudie_number` (present in the Apex fixture) with a positional fallback.

---

## Conventions (same as Phases 1–3)
- **Working dir:** `/Users/utkarsh/Projects/richard/research/preprocessor/`; interpreter `.venv/bin/python`; run pytest from that dir.
- **Full suite:** `.venv/bin/python -m pytest tests/ -q` — baseline entering 4a integration: **343 passed** (after the 2026-06-02 review-fix wave).
- **Guard:** `tests/test_no_client_name_in_logic.py`. **Golden:** `tests/test_resolved_package_contract.py` (this phase **intentionally re-baselines** it to v2.0 — the one phase where the golden changes on purpose).
- **NO GIT.** Per-task checkpoint = new tests pass AND full suite green AND guard green.
- **Async tests:** `@pytest.mark.anyio` + a module-local `anyio_backend` fixture returning `"asyncio"`.
- **Downstream safety:** the renderer (`research/v7-renderer/`) reads v1.0; with the transitional `brand_axes` it keeps theming, but it will NOT show the new per-page `slots[]`/`charts`/`social_proof` until Phase 4b. That is expected. Do NOT touch the renderer in 4a.

## Verified facts the corrected design relies on (from the review)
- Golden fixture `tests/fixtures/sample_render_request.json` has `client_slug = "mein-werkzeugkoffer"`, and there is **no `client_assets/mein-werkzeugkoffer/` folder** → wiring `local_assets` keeps the golden hermetic (every drive slot → `absent`/`missing_required`), deterministic, offline. No fixture change needed.
- `client_assets/apex/` holds 5 real files: `founder.png`, `case-study-3.png`, `proof-1.png`, `proof-2.png`, `proof-3.png`.
- Renderer scans: ST-07A `assets[] where slot_id=="case_study_portrait"`; ST-05 `_PORTRAIT_SLOTS={about_portrait,founder_portrait,founder,about_founder}` + logos by `image_type=="logo"`. The v2.0 `slots[]` uses these exact `slot_id`s so 4b can bind without guesswork.

---

## Reconciliation decisions (LOCKED, corrected)
1. **`ground_mode` stays an axis (7 total).** `ResolvedAxes`: `headline_type, palette, accent_mechanic, texture, ground_mode, qr_enabled, density`. `ground_mode` is explicit-or-default-`"light"` (NOT token-derived — DNA §C3: the page ground is light by default; dark is a panel/renderer concern). [done in Task 1]
2. **Emit BOTH axes blocks.** Top-level `axes` = the canonical 7-field `ResolvedAxes` dump (the 4b contract). Top-level `brand_axes` = the legacy 4 keys (`headline_type/ground_mode/texture/accent_mechanic`) derived from `axes`, so the current renderer's `package_loader` keeps working in the 4a→4b gap. `provenance` = the `{axis: source}` map.
3. **Two systems, separated by source.** `resolve_slots` (drive/local-folder) is the SOLE authority for human photos → per-page `slots[]`. `generate_assets` owns fal generate/composite + manifest downloads → per-page `assets[]` + top-level `report_assets`. No slot is owned by both.
4. **`/render` stays synchronous.** No async flip (n8n contract).

---

## File Structure (Phase 4a corrected)
- `stages/resolve_axes.py` — `ground_mode` axis + 6→7 doc fix. **[done: Tasks 1 + review-fix]**
- `models_package.py` — `ResolvedPackageManifest` v2.0 + `ResolvedPageV2`. **[done: Task 2; Task 6 adds `brand_axes` + `slot_summary` fields]**
- `stages/local_assets.py` — `list_client_assets` + `client_assets_dir`. **[done: Task 3]**
- `stages/slot_registry.py` — **MODIFY** (Task 4): add `slot_id` + `image_type` to `SlotSpec`; add an optional client-own `logo` slot to the ST-05 recipe; set `slot_id`s.
- `stages/resolve_slots.py` — **MODIFY** (Task 4): carry `slot_id`/`image_type`/`aspect_ratio` onto `ResolvedSlot`.
- `settings.py` — **MODIFY** (Task 5): add `client_assets_dir: str = "client_assets"`.
- `stages/generate_assets.py` — **MODIFY** (Task 5): remove the 3 human "client" entries from `IMAGE_REQUIREMENTS`.
- `main.py` — **MODIFY** (Task 5): wire `resolve_axes`, `structure_content`, `resolve_slots` (local + `case_index`), cache/budget kwargs; pass v2 inputs + `client_dir` to `assemble_package`.
- `stages/assemble_package.py` — **MODIFY** (Task 6): build + validate the v2.0 manifest (validate-then-dump), copy resolved drive files into `assets/`, emit `slots[]`/`axes`/`brand_axes`/`provenance`/`slot_summary` + per-page typed `data`/`charts`/`social_proof`, bump to `"2.0"`.
- `tests/test_resolved_package_contract.py` + `tests/golden/` — **MODIFY** (Task 7): re-baseline to v2.0.
- `tests/test_package_photo_resolution.py` — **CREATE** (Task 8): the real Apex photo-resolution integration test.
- `stages/onboard/reconcile.py` — **MODIFY** (Task 9): plumb `palette`/`qr_enabled`/`density`.

---

## Task 1 — `ResolvedAxes` gains `ground_mode` ✅ DONE
(7 axes; `ground_mode` explicit-or-`light`; 6→7 docstrings fixed in the review-fix wave.)

## Task 2 — `ResolvedPackageManifest` v2.0 contract ✅ DONE (extended in Task 6)
`models_package.py` exists with `ResolvedPackageManifest` (`extra="forbid"`, `version: Literal["2.0"]`, `axes: ResolvedAxes`, `provenance`, `pages: list[ResolvedPageV2]`, …) + `ResolvedPageV2` (`extra="allow"` + `data`/`charts`/`social_proof`/`slots`/`assets`/`components`). Task 6 ADDS `brand_axes: dict = {}` + `slot_summary: dict = {}`.

## Task 3 — Local-folder asset lister ✅ DONE
`stages/local_assets.py`: `client_assets_dir(slug, *, base)` + `list_client_assets(folder)` (image files, sorted, junk-filtered).

---

## Task 4: Slot contract — `SlotSpec` declares `slot_id`+`image_type`; `ResolvedSlot` carries them

**Files:** Modify `stages/slot_registry.py`, `stages/resolve_slots.py`; Modify `tests/test_slot_registry.py`, `tests/test_resolve_slots.py`.

- [ ] **Step 1 (test, red):** in `tests/test_resolve_slots.py`, assert that resolving ST-07A with `case_index=2` against a listing containing `case-study-2.png` yields a `ResolvedSlot` with `slot_kind=="client_portrait"`, `slot_id=="case_study_portrait"`, `image_type=="portrait"`, `aspect_ratio=="1x1"`, `status=="resolved"`, `index==2`. In `tests/test_slot_registry.py`, assert every `SlotSpec` in every recipe has a non-empty `slot_id` and `image_type`, and that ST-05 now has a `slot_kind=="logo"` spec (`slot_id=="about_logo"`, source `drive`, optional, `drive_key=="logo"`).
- [ ] **Step 2:** Run → fail (fields absent).
- [ ] **Step 3 (implement):**
  - In `slot_registry.py`: add `slot_id: str` and `image_type: str` to `SlotSpec`. Populate every recipe entry with the renderer-facing values:
    `founder_hero`→`slot_id="founder"`,`image_type="portrait"`; `client_portrait`→`"case_study_portrait"`,`"portrait"`; `team`→`"about_portrait"`,`"portrait"`; `proof`→`"proof"`,`"photo"`; `press_logo`→`"press_logo"`,`"logo"`; `client_logo`→`"client_logo"`,`"logo"`; `scene`→`"scene"`,`"scene"`; `device_mockup`→`"device_mockup"`,`"device"`; `texture`→`"texture"`,`"texture"`; `gradient`→`"gradient"`,`"gradient"`. Add to ST-05: `SlotSpec(slot_kind="logo", source="drive", required=False, aspect_ratio="1x1", drive_key="logo", slot_id="about_logo", image_type="logo")`.
  - In `resolve_slots.py`: add `slot_id`, `image_type`, `aspect_ratio` to `ResolvedSlot` (all `str`/optional). Every `ResolvedSlot(...)` construction (the resolved path, the `_miss` helper, the generate/composite branch) copies `slot_id=spec.slot_id, image_type=spec.image_type, aspect_ratio=spec.aspect_ratio` from the `SlotSpec`.
- [ ] **Step 4:** Run the two test files → green.
- [ ] **Step 5: Checkpoint** — full suite green; guard green; golden still v1.0 green (resolve_slots/slot_registry not yet wired into the package).

## Task 5: Settings + `main.py` wiring (produce the v2 inputs; remove double-sourced human slots)

This task makes `/render` PRODUCE the v2.0 inputs and pass them (plus `client_dir`) to `assemble_package`. `assemble_package` (still v1.0 until Task 6) accepts + ignores the new kwargs via a temporary `**_v2` until Task 6 consumes them — so the golden stays v1.0-green at this checkpoint.

**Files:** Modify `settings.py`, `stages/generate_assets.py`, `main.py`; Modify `tests/test_render_endpoint.py`, `tests/test_generate_assets.py` (the count-invariant tests lose the 3 removed slots).

- [ ] **Step 1:** `settings.py` — add `client_assets_dir: str = "client_assets"`.
- [ ] **Step 2:** `generate_assets.py` — remove the human "client"-source entries from `IMAGE_REQUIREMENTS`: delete `cover_author` (ST-01), `about_logo` (ST-05), and the `case_study_portrait` (ST-07A) entry. Keep `cover_hero`(generate), `status_quo_scene`(generate), `fazit_background`(generate) + `REPORT_LEVEL_GENERATED`. Update `tests/test_generate_assets.py` assertions that referenced the removed slots (note each change).
- [ ] **Step 3:** `main.py` — add imports: `from stages.resolve_axes import resolve_axes`, `from stages.structure_content import structure_content`, `from stages.resolve_slots import resolve_slots`, `from stages.local_assets import client_assets_dir, list_client_assets`.
- [ ] **Step 4:** After Stage 2, resolve axes (replaces the inline `brand_axes` dict at ~325-330):
```python
    axes, axes_provenance = resolve_axes(
        brand_profile=request.client.brand_profile,
        brand_primary=brand_tokens.brand_primary,
        brand_accent=brand_tokens.brand_accent,
    )
```
- [ ] **Step 5:** After Stage 4, structure the content + resolve human-photo slots from the local folder, deriving `case_index` from `data.fallstudie_number` with a positional fallback:
```python
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
            case_index = int(fn) if isinstance(fn, (int, str)) and str(fn).isdigit() else case_counter
        page_slots[page.slot] = resolve_slots(page.type, drive_listing, case_index=case_index)
```
- [ ] **Step 6:** Pass cache/budget into the Stage-5 `generate_assets(...)` call: add `cache_dir=Path(cfg.asset_cache_dir)`, `max_generations_per_report=cfg.max_generations_per_report`.
- [ ] **Step 7:** Replace the `assemble_package(...)` call: drop `brand_axes=brand_axes`; pass `axes=axes`, `axes_provenance=axes_provenance`, `structured=structured`, `page_slots=page_slots`, `client_dir=client_dir`. (Task 6 adds these params; for THIS checkpoint give `assemble_package` a temporary `**_v2` catch-all so it ignores them and still emits v1.0.)
- [ ] **Step 8:** `tests/test_render_endpoint.py` — if a test asserts the old inline 4-key `brand_axes`, relax it to assert 200 + a package path (package content is the golden's job). Run full suite.
- [ ] **Step 9: Checkpoint** — full suite green; golden STILL v1.0 green (assemble_package hasn't changed its output yet); guard green. *(If the golden drifts here it means removing the 3 IMAGE_REQUIREMENTS entries changed the v1 package — that IS expected output drift; fold it into the Task-7 re-baseline rather than fighting it, but confirm it's ONLY those 3 slots disappearing from `pages[].assets`/`asset_summary`.)*

## Task 6: `assemble_package` → v2.0 (validate-then-dump; copy photos; emit everything)

**Files:** Modify `stages/assemble_package.py`, `models_package.py`; Modify `tests/test_assemble_package.py`.

- [ ] **Step 1:** `models_package.py` — add `brand_axes: dict = Field(default_factory=dict)` and `slot_summary: dict = Field(default_factory=dict)` to `ResolvedPackageManifest` (extra="forbid" requires them declared since Task 6 emits them).
- [ ] **Step 2:** `assemble_package` + `_build_manifest` — change signatures: accept `axes: ResolvedAxes`, `axes_provenance: dict`, `structured`, `page_slots: dict[int, list]`, `client_dir: Path` (replacing `brand_axes`). Set `PACKAGE_SCHEMA_VERSION = "2.0"`.
- [ ] **Step 3 — copy resolved drive photos into the package.** Add a helper that, for each page's `page_slots[slot]`, takes the entries with `source=="drive"`, and for `status=="resolved"` copies `client_dir / slot.path` → `output_dir/assets/<slot_id>[_<index>].<ext>` (deterministic dest name) and rewrites the emitted slot's `path` to the package-relative `assets/<dest>`; for `missing_required`/`absent` emits `path=None` + the status. Build the per-page `slots[]` from ONLY the `source=="drive"` entries (generate/composite slots are represented in `assets[]`, not here). Guard the copy with try/except → on failure mark `status="failed"` + a warning (never raise).
- [ ] **Step 4 — per-page typed blocks.** Build `structured_by_slot = {p.slot: p for p in structured.pages}`. For each manifest page add: `data` = `structured_by_slot[slot].data.model_dump()` (fall back to the raw dict if absent), `charts` = `[c.model_dump() for c in sp.charts]`, `social_proof` = `sp.social_proof.model_dump() if sp.social_proof else None`, `slots` = the copied drive-slot dumps from Step 3. Keep `assets` = the generate_assets entries (unchanged), `components`, `css_template`, `has_cta`, `page_numbers`, `cover_validation`.
- [ ] **Step 5 — top-level.** Emit `axes = axes.model_dump()`; `brand_axes = {k: getattr(axes, k) for k in ("headline_type","ground_mode","texture","accent_mechanic")}` (the transitional 4-field block); `provenance = axes_provenance`; `slot_summary` = counts across all pages' drive slots: `{resolved, missing_required, absent, total}` plus the per-`missing_required` named list `[{page_slot, slot_id, expected}]` so QA sees the exact files to add (PRD §7.3). Keep `report_assets`, `validation`, `asset_summary`, `asset_warnings`.
- [ ] **Step 6 — validate-then-dump.** Build the dict, then `ResolvedPackageManifest.model_validate(manifest)` BEFORE writing; write `json.dumps(validated.model_dump(mode="json"), …)`. A contract typo now fails loudly at assembly.
- [ ] **Step 7:** `tests/test_assemble_package.py` — update the version assertion to `"2.0"`; the key-presence asserts use `>=` so they hold; add a test asserting `axes` (7 fields) + `brand_axes` (4 keys) + `provenance` + `slot_summary` present, a page carries `data`/`charts`/`social_proof`/`slots`, and the manifest validates against `ResolvedPackageManifest`. Add a test that a `resolved` drive slot results in a copied file + a package-relative `slots[].path`.
- [ ] **Step 8: Checkpoint** — `tests/test_assemble_package.py` green; full suite green except the golden (now FAILS — expected; Task 7 re-baselines); guard green.

## Task 7: Re-baseline the golden to v2.0

**Files:** Modify `tests/test_resolved_package_contract.py`; replace `tests/golden/resolved_package.v1.json` → `resolved_package.v2.json`.

- [ ] **Step 1:** Point `_GOLDEN` at `golden/resolved_package.v2.json`; add `"axes"`, `"brand_axes"`, `"provenance"`, `"slot_summary"` to `_TOP_LEVEL_KEYS`; change the version assertion to `"2.0"`. The hermetic run uses `client_slug="mein-werkzeugkoffer"` (no local folder) → all drive slots `absent`/`missing_required`, no file copies → deterministic.
- [ ] **Step 2:** Delete the old `resolved_package.v1.json`. Run the contract test once → it self-creates `resolved_package.v2.json` ("created; re-run").
- [ ] **Step 3:** Inspect the snapshot: `version=="2.0"`; `axes` 7 fields; `brand_axes` 4 fields; `provenance` present; `slot_summary` present (mein-werkzeugkoffer: founder/case-study/etc. as missing_required/absent, named); a page carries `data`/`charts`/`social_proof`/`slots`; NO `/Users/` or `/tmp/` paths anywhere.
- [ ] **Step 4:** Run the contract test again → PASS. Run full suite.
- [ ] **Step 5: Checkpoint** — full suite green; guard green; golden green at v2.0.

## Task 8: Real Apex photo-resolution integration test (the "real test", not the hermetic golden)

**Files:** Create `tests/test_package_photo_resolution.py` (+ a small fixture request with `client_slug="apex"`).

- [ ] **Step 1 (test, red):** build a `/render` request (or call `assemble_package` directly with real upstream outputs) whose `client_slug="apex"` and run it against the real `client_assets/apex/` folder (point `Settings.client_assets_dir` at the repo's `client_assets`). Assert on the resulting package: the founder slot on ST-01 resolves (`slots[]` entry `slot_id=="founder"`, `status=="resolved"`, `path` starts `assets/`, and the file exists on disk in the package); the ST-07A page whose `fallstudie_number==3` has a resolved `case_study_portrait`; the ST-05 page carries 3 resolved `proof` slots; case studies 1/2/4/5 carry `missing_required` proof/portrait entries naming the expected file; `slot_summary.resolved >= 5`.
- [ ] **Step 2:** Run → it should pass once Tasks 4–6 are correct (this test is the proof the feature works end-to-end on real files). If red, debug (systematic-debugging) — do NOT weaken the assertions.
- [ ] **Step 3: Checkpoint** — full suite green (golden v2.0 + this new real test); guard green. *(This test must NOT make the golden non-hermetic — it uses its own apex request, not the sample fixture.)*

## Task 9: Fix `/onboard` reconcile — plumb palette/qr_enabled/density

**Files:** Modify `stages/onboard/reconcile.py`; Modify `tests/test_onboard_reconcile.py`.

- [ ] **Step 1 (test, red):** a `VisionReading.axes` carrying `palette="dual_contrasting"`, `qr_enabled=True`, `density="packed"` → assert the reconciled `BrandProfile` carries all three (today dropped).
- [ ] **Step 2:** Run → fail.
- [ ] **Step 3:** In `reconcile.py` where `BrandProfile(...)` is built from `vision.axes`, add `palette`, `qr_enabled`, `density` (guard for `None`).
- [ ] **Step 4:** Run → pass.
- [ ] **Step 5: Checkpoint** — full suite green; guard green; golden green.

---

## Phase 4a self-review (corrected)
- **Four verified gaps fixed:** axes both-emit (Tasks 5+6 §5), slot-id contract + clean `slots[]` (Tasks 4+6 §3-4), two-system merge by source (Task 5 §2 + Task 6 §3-4), `case_index` from `fallstudie_number` (Task 5 §5). The v2.0 contract (Task 2 + Task 6 §1) + validate-then-dump (Task 6 §6) lock the seam; the local lister (Task 3) substitutes for Drive; the golden re-baselines hermetically (Task 7); the real photo path is proven on Apex (Task 8); `/onboard` axes plumbed (Task 9); the §7.3 named-miss invariant lands in `slot_summary` (Task 6 §5).
- **Determinism:** golden hermetic (no apex folder for `mein-werkzeugkoffer`); pure resolvers; cache-pinned fal; file copies deterministic dest names; `model_dump(mode="json")` stable.
- **No-regression:** Tasks 1–5 keep the golden v1.0-green; it changes exactly once, on purpose, in Task 7. `brand_axes` keeps the current renderer theming until 4b.
- **Out of scope (Phase 4b / gated):** the renderer consuming `slots[]`/`charts`/`social_proof`/7-field `axes` (4b); live Drive adapter (creds); device-frame art; social-proof 2nd pass; Testimonials/Logo-wall page TYPES (no Apex page uses them — general-purpose, deferred to 4b spec); the `StatItem.value` int-coercion quirk (verify against real Apex data during Task 8; fix if it drops stats).
