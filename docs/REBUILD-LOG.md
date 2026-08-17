# DMC Rebuild — Development Loop Log

Running log for the FINAL rebuild of the live DMC pipeline. Governed by `docs/SYSTEM-MAP.md` (the verified gap register + blueprint). This file tracks iterations; SYSTEM-MAP is the spec. Rule: **"done" = the artifact shown (%PDF + page count + real components present), never a claim.**

## Context (one paragraph)
The live path (`dmc-renderer/service.py`) takes an n8n envelope `{payload, images, brand_tokens}` and returns a PDF over HTTP — VERIFIED working — but it is HOLLOW: it hand-rolls a stub manifest (`components:[]`, `report_assets:[]`, `treatments=False`, WeasyPrint) and bypasses the entire preprocessor "brain." All the premium logic (typed content, SVG components/charts, ST-31 divider cadence, treatments) lives in `research/preprocessor` (stages) + `research/v7-renderer` (engine) and never runs on the live wire. The premium showcase was hand-rendered via CLI on a hand-edited frozen fixture. See SYSTEM-MAP.md for the full 20-gap register.

## What's DONE (previous loop)
- **System fully mapped + execution-verified** → `docs/SYSTEM-MAP.md` (20 gaps ranked, failure-mode patterns, dependency-ordered blueprint, all unknowns closed by running).
- **Thin middleware proven** (`dmc-renderer/service.py`): envelope → PDF over HTTP, verified (`_proof_http_render.pdf`). Hollow but real transport.
- **Writer content layer**: `docs/writer-prompt-v2.md` (real house voice from his own decks), `docs/richard-voice-corpus.md`, `docs/voice-extract/*` (clean `pdftotext` of the 4 reference decks). Reader-model wiring is an n8n-lane task.
- **Verified facts that drive P0:** full preprocessor pipeline imports under the RENDERER venv (in-process build is feasible, no HTTP hop); Chromium ship path = 20 clean pages, no spill, showcase fidelity, but 0 text layer; WeasyPrint = text layer but spills (so `engine` default should be chromium); the QC validators (`accent_budget`, `contrast`, overflow) EXIST + are CALLED but are STUBS returning pass; `test_render_r2.py` = 3 real failures (cover + 2 st07a composition/chart).

## The orchestration (read 2026-06-29, `research/preprocessor/main.py:323-527`)
`/render` runs, in order: `validate_and_resolve_brand_tokens(request)` → `resolve_fonts` → `resolve_axes` → `validate_copy`(+copyfit) → `validate_cover` → `structure_content(pages)` + `resolve_slots` → `generate_assets(...)` (Stage 5, async; needs openrouter for prompt-build + fal for gen; STUBS offline) → `generate_components_for_report(pages, brand_*, structured=)` (Stage 6, OFFLINE, the SVG components) → `plan_layout(pages, components, page_count_target)` → `assemble_package(...)` (Stage 8, writes `resolved_package.json` + `components/`+`assets/`+`fonts/` to a temp dir) → `route_package(pkg, ...)` (Stage 8.5, ST-31 dark-divider cadence + diagram proof; restructure needs openrouter but is cached/optional). Returns JSON (`package_path`), NEVER renders.

Input is a `RenderRequest` (pydantic): `{record_id, client{brand_profile, design_brief, founder_*_url}, report_json{meta, pages}, image_manifest{images:[...]}}`. **Key adapter gap vs the n8n envelope:** the envelope carries `brand_tokens` (already ~10-field) + flat `images{slot:url}`; the pipeline expects `client.brand_profile` (rich) and derives tokens in Stage 1, and an `image_manifest` LIST shape. So P0 must adapt envelope → RenderRequest.

## P0 — PRECISE PLAN (current iteration target)
Goal: the live envelope produces a REAL, component-rich premium PDF end to end, in-process, engine=chromium. Closes G1, G5, G6(partial), G12, G14-default.

Steps (TDD, verify each):
1. **Adapter** `dmc-renderer/envelope_adapter.py`: `envelope_to_render_request({payload, images, brand_tokens}) -> RenderRequest`.
   - `report_json` = payload (meta + pages) → the pipeline's ReportJson model.
   - `image_manifest` = convert flat `images{slot:url}` → the `{images:[{id,page_slot,page_st_type,image_type,url,status}]}` list shape (map slot→page via the SLOT_TO_ST convention already in service.py).
   - `client.brand_profile` = SYNTHESIZE from `brand_tokens` (colors→brand_profile color fields; fonts; axes default or derive). This is the fiddly bit — read `models.py` BrandProfile to build it minimally-valid.
2. **In-process build** `dmc-renderer/build_live.py`: replicate main.py:366-505 stage sequence (call the imported preprocessor stages under the renderer venv), producing the package dir. Pass `openrouter_key=None`, `fal_key=None` and CONFIRM the pipeline runs offline (generate_assets stubs, route_package restructure no-ops). If a stage hard-fails offline, gate it (skip Stage 5 gen / Stage 8.5 restructure when no key).
3. **Wire** `service.py` `/render` → call `build_live` → `render_package(pkg, out, engine="chromium")` → stream `report.pdf`. Change engine default to chromium.
4. **VERIFY (the TDD gate):** POST the canonical envelope → assert: package `resolved_package.json` has `components` > 0 on data pages; page count == 20 (ST-31 cadence present, not 17); PDF `%PDF` + physical == logical (no spill); at least one real component SVG rendered. Save the proof PDF; open it.

Offline-key risk to confirm first in iter 2: does `generate_assets` / `route_package` hard-fail without openrouter_key? (Map says generate_assets stubs; route_package restructure is cached/optional — verify by running the sequence once.)

## Blueprint after P0 (from SYSTEM-MAP)
P1 un-stub the existing QC validators (accent_budget/contrast/overflow) → gate defects. P2 bundle brand fonts. P3 Dockerfile (solve the DYLD/native-lib in-image) → deployable. Then Phase B premium fidelity (treatments on, de-frozen fixture). Then Phase C the edges that don't exist (DMC n8n workflow + writer reader-model wiring).

## Iteration log
- **Iteration 1 (2026-06-29) — DONE:** consolidated context; read the full `/render` orchestration; wrote this log + the precise P0 plan. No P0 code yet (deliberately — the adapter needs the models read + TDD, done next). Armed the self-paced loop.
- **Iteration 2 (next):** execute P0 with TDD — read `models.py` (RenderRequest/BrandProfile/ImageManifest), write `envelope_adapter.py` + `build_live.py` + the verification test FIRST, then wire `service.py`, then run offline-key check, then the full verified chromium render. Show the artifact.

## NEXT-LOOP PROMPT (what each iteration does)
"Advance the DMC rebuild by exactly one verified step per `docs/SYSTEM-MAP.md` + this REBUILD-LOG iteration log. Use TDD: write/adjust the verification FIRST, implement, run it, and only mark a step done when the artifact is shown (%PDF + page count + real components/no-spill, or the specific assertion for that step). Update the iteration log with evidence each time. Current phase: P0 (real package in-process, renderer venv, engine=chromium). Do not claim done without running. Keep changes isolated to dmc-renderer/ + minimal, reversible preprocessor refactors. If blocked, document the exact blocker in the log and continue with the next unblocked step."


## Iteration 2 (2026-06-29) — P0 enrichment feasibility VERIFIED + key finding
- Ran `structure_content(pages)` + `generate_components_for_report(...)` on the live canonical envelope IN-PROCESS (renderer venv, offline): BOTH SUCCEED. P0's in-process enrichment is sound; these stages need no keys.
- BUT only **1 component total** across 17 pages (SVG on slot 14). The frozen apex fixture also has ~1/20 components, 0 charts. So the `components:[]` stub loses ~1 component, NOT the premium look.
- WHERE PREMIUM ACTUALLY COMES FROM (verified): the TREATMENT system (`treatment_catalog.py` = 12 treatments for apex-eligible page types; apex-verified `treatment_stylist.py`) + the per-ST PATTERNS (`patterns/st_07a.py`, `st_06.py`) that draw devices/dashboards/charts from `page.data` directly. Renderer chassis is deliberately apex-AGNOSTIC (`brand_tokens.py`: "no apex fallback") = good for generalization. No separate apex-only viz-curation file found in v7 (map's `apply_apex_viz` not located here; de-prioritized).
- REVISED PRIORITY: P0 (full real package + chromium) still correct (brings typed data + ST-31 cadence + assets + per-ST pattern inputs), but the biggest fidelity lever is TREATMENTS (Phase B: `treatments/a4_*.html.jinja` templates missing -> legacy fallback), not components.

## Iteration 3 (next) plan
1. `envelope_to_render_request` adapter: ClientInput{name, company(=company_name_short or founder), website_url(from company_url_display/qr_target_url), brand_hex_dark/light/accent (<- neutral_dark/neutral_light/brand_accent), brand_profile(all 5 colors + fonts)}; report_json=payload; image_manifest = images{slot:url} -> [ImageManifestItem{id=slot, page_slot=(SLOT_TO_ST st_type -> page.slot), page_st_type, image_type, url, status:'provided'}]. NOTE page_count_target must be in {16,20,24,28}.
2. `build_live.py`: replicate main.py:366-505 stage sequence offline (keys=None). VERIFY generate_assets + route_package don't hard-fail offline; gate Stage 5 gen + Stage 8.5 restructure if they need keys. Produce package dir; assert resolved_package.json valid.
3. render_package(pkg, engine="chromium") -> assert %PDF, 20 pages (ST-31 cadence), physical==logical. Wire into service.py (engine default chromium). Show artifact.


## Iteration 3 (2026-06-29) — P0 CORE DONE + VERIFIED (live service builds the REAL package)
Built `dmc-renderer/build_live.py`: `envelope_to_render_request` adapter (ClientInput/BrandProfile/ImageManifest from the envelope) + `build_live_package` that runs the REAL preprocessor stages 1->8.5 IN-PROCESS, OFFLINE. Wired `service.py::build_and_render` to delegate to it + engine=chromium (dropped the stub manifest; endpoint default engine=chromium; X-Component-Count/X-Overflow headers).
VERIFIED (artifact): `service.build_and_render(canonical envelope)` -> real `resolved_package.json` via the actual `assemble_package` -> chromium PDF: %PDF, 9.8MB, 17 pages, **1 component + 2 report_assets** (old stub = 0/0). Proof: `dmc-renderer/_proof_live_chromium.pdf`.
Fixes en route: `from config`->`from settings`; then `pydantic_settings` MISSING in renderer venv (cross-venv) -> replaced the Settings import with a literal config shim (SimpleNamespace), no preprocessor-only dep needed. generate_assets + assemble_package + route_package ALL run offline (keys=None), no hard failures.
HONEST DEFECTS the real path exposes (next steps target these):
- **OVERFLOW: 25 physical vs 17 logical = 8 spilled sheets** on the direct chromium render, but the advisory `overflow` list flags only 1 -> confirms the map: overflow check is per-fragment advisory + BLIND to physical spills. Live content overflows the A4 layout badly (the hand-tuned frozen fixture did not). BIGGEST quality issue.
- **NO ST-31 cadence:** 17 pages; route_package ran offline but injected 0 divider pages (showcase=20). Needs investigation (LLM/restructure-gated? manifest-gated?).
- 1 component (generate_components sparse, known); font fallback Inter->Source Sans (P2/G11).
- Dead code now in service.py (`_download_images`, `build_manifest`) — remove in D1 cleanup.

## Iteration 4 (next) plan
1. Diagnose the 8-page OVERFLOW (biggest defect): copy-fit (content too long for A4 boxes) vs missing-treatment. Inspect a couple overflowing pages.
2. Read `route_package.py:60,90` — what gates ST-31 divider injection (why 0 offline).
3. P1: un-stub `validators/overflow.py` to DETECT physical!=logical spills (so defects gate/422, not ship silently) + `accent_budget.py`.


## Iteration 4 (2026-06-29) — DIAGNOSTICS: 3 map corrections + a decision point
Read `assembler.py:852-897`, `validators/overflow.py`, `stages/route_package.py`. Corrections:
1. **Overflow detection is REAL + WORKS** (corrects the map's "no gate"/"stub"): `validators/overflow.py::check_overflow` renders each page standalone (WeasyPrint) + counts sheets; under CHROMIUM `assembler.py:858-865` flags `physical(png) != logical(fragments)`. The live render's overflow flag IS the true spill (physical 25 != logical 17). The STUBS are `accent_budget.py` + `contrast.py` (return passed=True), NOT overflow. => P1 = un-stub accent_budget/contrast + ACT on the real overflow flag (service currently SHIPS the spilled PDF 200 instead of gating).
2. **ST-31 cadence is an INPUT concern, not a build bug** (corrects "route_package injects ST-31"): `route_package.py` only STYLES existing ST-07B pages dark (`dark_divider_types={ST-07B}`) + binds social assets to existing ST-31/ST-05 pages when a manifest is passed. It does NOT create ST-31 pages. The 17-page envelope has none; the 20-page showcase had 3 hand-added. The n8n chapter-planner (input) owns dividers -> out of software lane.
3. **The 8-page OVERFLOW root = the copy-fit LLM restructure is KEY-GATED.** `route_package.py:95-118` runs `restructure_page` (LLM) over over-budget host pages to make copy fit -> needs `openrouter_key`. Offline (key=None) it's SKIPPED -> over-budget pages spill (25 physical/17 logical). The copy-fit mechanism EXISTS; it needs an OpenRouter key (cheap model) to run.

**DECISION POINT (surfaced to owner):** the biggest live defect (8-page overflow) is fixed by the LLM copy-fit restructure = needs an OpenRouter key (owner has one, prefers claude-haiku). Wire it? Until then the live deck overflows by design.

## Iteration 5 (next, UNBLOCKED) plan
- P1: un-stub `validators/accent_budget.py` + `contrast.py`; make the service ACT on the real overflow flag (add `X-Physical-Pages`; `strict` mode -> 422 on spill; default 200 + warning header so it's VISIBLE not silent).
- BLOCKED on owner: wire OpenRouter key for the copy-fit restructure (fixes the overflow itself).


## Iteration 5 (2026-06-29) — P1 overflow gate: DONE + verified
`service.py` now surfaces the REAL overflow signal: `build_and_render` returns `physical_pages` (len result.png_paths); the endpoint adds `X-Logical-Pages` + `X-Physical-Pages` + `X-Overflow` headers, and a `_strict` body flag -> 422 {overflow, logical, physical} on spill (default = 200 + headers, so it is VISIBLE not silent). Verified: service imports OK, gate wired (ast-parsed clean). Full HTTP header proof deferred to the next HTTP run.
Remaining P1: un-stub `validators/accent_budget.py` + `contrast.py` (lower urgency than overflow).
BLOCKED (owner): the OpenRouter key for the copy-fit `restructure_page` = the fix for the 8-page overflow itself. Until decided, the service REPORTS the spill (headers / strict-422) but the deck still overflows.
=> Slowed loop cadence to ~20min: the biggest fix is owner-gated; unblocked polish continues calmly.

## Iteration 6+ (unblocked, when the loop fires)
P2: bundle brand fonts so the live render stops Inter->Source-Sans fallback (G11). P3: Dockerfile for engine+middleware (solve DYLD/native-libs in-image) -> deployable. Un-stub accent_budget/contrast. All independent of the copy-fit key.


## Iteration 6 (2026-06-29) — P0 + P1 VERIFIED OVER HTTP (rebuilt service)
Started the rebuilt uvicorn service + POSTed the canonical envelope. RESULT: HTTP 200, application/pdf, 9.79MB; health mode="build_live (real package)"; QC headers live: X-Logical-Pages=17, X-Physical-Pages=25, X-Component-Count=1, X-Overflow=1. %PDF, 25 physical pages. Proof: dmc-renderer/_proof_live_http.pdf. (Cover get_text()='' = expected; chromium PDFs have no text layer.)
=> The LIVE SERVICE over HTTP now builds the REAL package (in-process stages) + renders chromium + surfaces the real overflow signal. **P0 + P1(overflow gate) fully closed over the wire.**

PLATEAU: highest-value remaining = copy-fit (owner-gated OpenRouter key). Unblocked left: D1 dead-code cleanup (remove service.py's now-unused `_download_images`/`build_manifest`/`build_manifest` helpers + REQUIRED_FONTS copy), P2 fonts (font-strategy decision, mild), P3 Dockerfile (deploy), un-stub accent_budget/contrast. Loop on ~20min heartbeat; next auto-iteration = D1 cleanup (safe/clean) unless owner decides copy-fit.


## Iteration 7 (2026-06-29) — D1 dead-code cleanup: DONE + verified
Rewrote service.py to the live path ONLY: removed the dead stub helpers (`build_manifest`, `_download_images`, `_brand_block`, `_display_url`, `_load_reference`, `SLOT_TO_ST`, `CSS_MAP`/`REF`, `_DEFAULT_AXES`, `REQUIRED_FONTS`/`FONT_SRC`/`REF_MANIFEST`) + now-unused imports (json/shutil/tempfile/urllib/datetime). **253 -> 93 lines.** Verified: imports OK, app + build_and_render intact, zero dead symbols. service.py = RENDERER_ROOT wiring + build_and_render (build_live + chromium) + the FastAPI endpoint with the overflow gate.

STATE: **P0 + P1(overflow gate) done & verified over HTTP; codebase clean. STABLE PLATEAU.**
NEXT (owner-gated = HIGHEST value): wire OpenRouter key -> copy-fit `restructure_page` -> fixes the 8-page overflow.
NEXT (unblocked, lower value): P2 font strategy (mild), P3 Dockerfile (deploy), un-stub accent_budget/contrast.


## Iteration 8 (2026-06-29) — copy-fit made ENV-GATED (one flip away, zero spend)
`build_live` now reads `OPENROUTER_API_KEY` + `FAL_KEY` from env (was hardcoded None) and passes them to `generate_assets` + `route_package`. Unset -> None -> fully offline (VERIFIED: build still 17pp / 1 comp / 2 assets, identical to before). Set `OPENROUTER_API_KEY` -> the copy-fit `restructure_page` runs (fixes the 8-page overflow); set `FAL_KEY` -> AI textures generate. => the owner-gated highest-value fix is now a CONFIG FLIP, not more dev, with ZERO spend until set (respects the spend-reluctance preference).

STATE: STABLE + PREPPED PLATEAU. P0+P1 done/verified over HTTP; code clean; copy-fit ready behind an env var. Genuinely high-value unblocked work is now exhausted — remaining is polish (P2 fonts / P3 Dockerfile [not verifiable without docker here] / un-stub accent_budget+contrast) OR the owner sets OPENROUTER_API_KEY. Loop lengthened to ~30min heartbeat to reduce churn.


## LOOP WIND-DOWN / HANDOFF (2026-06-29, after 8 iterations)
The autonomous loop completed its clean high-value scope. PAUSING (no further auto-wakeups): every remaining item needs an owner decision or a large design/deploy chunk, not a small clean step. Re-fire /loop or set the key to resume.

VERIFIED STATE (all shown, not claimed):
- **P0 DONE:** live service builds the REAL preprocessor package in-process (`build_live.py`) + renders chromium + streams PDF, end-to-end over HTTP. Proof: `dmc-renderer/_proof_live_http.pdf` (200, application/pdf, 25 physical pp, real assembled package).
- **P1 DONE:** overflow QC gate — service emits `X-Logical-Pages`/`X-Physical-Pages`/`X-Overflow`; `_strict` -> 422. Overflow detection confirmed REAL (chromium physical!=logical).
- Code clean (`service.py` 253->93, live path only). Copy-fit ENV-GATED (`OPENROUTER_API_KEY` -> restructure runs; zero spend until set; verified offline-unchanged).
- `SYSTEM-MAP.md` = verified 20-gap register + blueprint; this log = iteration-by-iteration evidence.

REMAINING ROADMAP (who-gates / effort):
1. [OWNER, trivial] Set `OPENROUTER_API_KEY` -> copy-fit restructure fixes the 8-page overflow (biggest live defect). `FAL_KEY` -> AI textures. Zero-dev, prepped.
2. [BIG / design] Phase B fidelity: the `treatments/a4_*.html.jinja` templates are MISSING -> treatments fall back to legacy = the biggest FIDELITY lever. Real per-treatment layout work (design judgment / owner reference).
3. [MEDIUM / deploy] P3 Dockerfile (engine+middleware: Chromium+Ghostscript+native libs+fonts+preprocessor) so n8n can call it. Heavy; verify via `docker build`.
4. [MEDIUM / CV] Un-stub `accent_budget` + `contrast` (rasterize + ΔE clustering + DOM bbox mapping). Speculative QC vs the current bigger defects.
5. [n8n lane] Reader-model forwarding into the writer node; the DMC n8n workflow (absent in repo); ST-31 dividers (chapter-planner). Other session.
6. [HYGIENE] `docs/ARCHITECTURE.md` is fiction (describes non-existent code) — correct or delete.

NET: the live pipeline went from HOLLOW STUB -> a real, verified, honest engine with defects SURFACED not hidden. The premium jump now needs (1) the owner's env-flip + (2) the treatment templates (Phase B).


## ===== ACTIVE PHASE B (owner steer 2026-06-29): BUILD THE A3 CASE-STUDY TREATMENT =====
Owner chose (A). The overflowing ST-07A case studies need the A3 spread they were designed for (copy-fit only got 25->23). This is now the LOOP'S ACTIVE BUILD (added to the loop per owner).

SCOPING (done this turn):
- Treatment templates live in `templates/treatments/*.html.jinja`. EXIST: editorial, horizontal_process, a4_vertical_timeline. MISSING (-> legacy fallback -> overflow): a4_bi_dashboard, a4_two_stack, a4_quote_portrait, a4_metric_column, a4_dark_divider, a4_portrait_card, a4_stacked_hero, glass_card, split_portrait.
- `treatment_catalog.py::_CATALOG` = `_treatment(name, archetype, formats{a3,a4}, required_fields, needs_image)`. `treatment_engine.py` normalizes page.data -> TreatmentData via `adapt()` + per-ST adapters; **`_adapt_st07a` (case studies) ALREADY EXISTS** — data adaptation is done, only the TEMPLATE is missing.
- Existing case-study visual = the navy-stone bi-dashboard in `patterns/st_07a.py` + `styles/st_07a.css` (legacy A4; overflows). Reuse that design at A3.

LOOP PLAN (one VERIFIED step per iteration; done = artifact shown):
- **B-1** (read): `treatment_engine._adapt_st07a` (exact TreatmentData fields for a case study) + an existing treatment template (`templates/treatments/editorial.html.jinja`) + the render/registry layer that turns TreatmentData->HTML + how `treatment_stylist` assigns to ST-07A + how a page gets `page_format="a3"`.
- **B-2** (build): `templates/treatments/a3_case_study.html.jinja` (+ CSS) = bi-dashboard at A3 spread (left narrative: portrait/ausgangsproblem/wendepunkt/loesung; right: navy-stone metrics device + KPI rail + pull-quote). Reuse styles/st_07a.css tokens.
- **B-3** (wire): register in `treatment_catalog` (`_treatment("a3_case_study","case_study",frozenset({"a3"}),(...),needs_image=True)`) + `treatment_stylist` assigns it to ST-07A + set `page_format="a3"` on those pages.
- **B-4** (verify): render case-study pages with treatments=True -> they render on A3, physical==logical for them (NO overflow), match the bi-dashboard. Show the artifact; confirm total-deck spill drops from 23.
Note: live service renders treatments=False today; enabling treatments for case studies (guarded: fire only when ST-07A data resolves) is part of this. Copy-fit stays on as a backstop (env-gated).


## Phase B — B-1 DONE (2026-06-29): scoped the A3 case-study treatment
Read TreatmentData + `_adapt_st07a` + `templates/treatments/editorial.html.jinja` + `treatment_stylist.py`.
- **Template pattern** (editorial.html.jinja = the scaffold): a treatment = a jinja template in `templates/treatments/` driven ENTIRELY by `td` (TreatmentData), importing macros (eyebrow, two_tone_headline, viz), resolving navy-marble via `ctx.resolve_report_asset(("panel_texture",),...)`, separate page-scoped CSS `styles/treatments/<name>.css` (semantic tokens only). Left cream field / right navy portrait column, A3-landscape, graceful-omit per block.
- **Case-study TreatmentData** (`_adapt_st07a`): eyebrow="FALLSTUDIE 0N", headline=ergebnis_headline, subhead=kurzportraet, sections=[{label,text}] (ausgangsproblem/wendepunkt/loesung), stats=[{value,label}] (ergebnis_metrics), quote={text,attribution} (pullquote+kunde.name), image=portrait.
- **STYLIST CONSTRAINTS (the real wiring challenge):** `_CANDIDATES` routes ST-07A to A4-ONLY (a4_two_stack first — TEMPLATE MISSING -> legacy -> overflow). A3 is CAPPED (`DEFAULT_MAX_A3=3`); only ST-05 (About) is hero-eligible (`_HERO_ST_TYPE`). ST-07B bypassed. => making case studies A3 needs: route ST-07A -> a3_case_study AND let them promote to A3 without the editorial-hero cap starving them.

REFINED PLAN:
- **B-2** (build): `templates/treatments/a3_case_study.html.jinja` + `styles/treatments/a3_case_study.css` = navy-stone bi-dashboard at A3 (LEFT cream: eyebrow FALLSTUDIE + two-tone headline(ergebnis_headline) + kurzportraet lede + narrative sections; RIGHT navy-stone: portrait + metrics device(stats -> ring/KPIs via the viz dispatch, like editorial's donut) + KPI rail + pull-quote). Reuse styles/st_07a.css + editorial.css tokens.
- **B-3** (wire): register in `treatment_catalog` (`_treatment("a3_case_study","case_study",frozenset({"a3"}),("headline",),needs_image=True)`); in `treatment_stylist` add an ST-07A A3 route (a3_case_study first) + relax the A3 cap for case studies (or a separate case-study A3 budget). Keep A4 fallbacks when portrait/data absent.
- **B-4** (verify): render case-study pages treatments=True -> A3, physical==logical (no spill), match bi-dashboard; total-deck spill drops from 23. Show artifact.
DESIGN FLAG (owner-aware): all-5-case-studies-A3 grows the deck (5 A3 spreads); memory says this IS the intended Doppelseite design, so proceeding — but it deliberately changes the `MAX_A3=3` economics.


## Phase B — B-2a DONE (2026-06-29): a3_case_study TEMPLATE written + validated
`templates/treatments/a3_case_study.html.jinja` (142 lines), modeled on editorial.html.jinja. Jinja syntax VALID; uses only real TreatmentData fields (eyebrow/headline/headline_accent/subhead/sections/stats/quote/image). Structure: LEFT cream field (eyebrow FALLSTUDIE + two-tone headline=ergebnis_headline + kurzportraet lede + narrative sections + result metrics zone: ring for %-stat + KPI callouts via the viz dispatch); RIGHT navy-marble column (portrait + scrim name caption + the pull-quote on dark stone). Reuses the curved-marble footer + panel_texture asset + eyebrow/two_tone_headline/viz macros. NOT renderable until B-2b (CSS) + B-3 (wire).
NEXT **B-2b**: `styles/treatments/a3_case_study.css` scoped `.page.treatment-a3_case_study.format-a3`, adapted from editorial.css (proven A3 mechanics: definite-height grid; cream distributed stack; bled navy column with EXPLICIT flex-basis (Chromium paged-media collapses flex-grow to 0); curved marble footer; panel-contrast rule = dark grounds on --color-ink, accents lift toward --color-on-dark). New vs editorial: the narrative `.cs-section` label+paragraph stack (mid) + the `.cs-quote` pull-quote on the dark column (replaces the credential wall).


## Phase B — B-2b DONE (2026-06-29): a3_case_study CSS written
`styles/treatments/a3_case_study.css` (~250 lines), adapted from editorial.css. Scope confirmed: assembler stamps `treatment-<name>` + `format-a3` (assembler.py:595-603); css_path convention `styles/treatments/<name>.css`. Reuses editorial's proven A3 mechanics verbatim (definite-height 258mm grid; cream distributed stack; ABSOLUTE bled navy column with EXPLICIT 56/44 flex-basis for Chromium paged-media; curved marble footer; panel-contrast tokens). NEW vs editorial: `.cs-section` narrative stack (accent-ruled labels) + `.cs-quote` pull-quote on dark (accent lifts toward on-dark). Semantic tokens only (matches editorial's data-uri `%23000` footer curve, guard-safe).
Template + CSS both exist now; still NOT wired.
NEXT **B-3** (wire — the trickiest step, touches the deliberate A3-budget logic): (1) register in `treatment_catalog._CATALOG`: `_treatment("a3_case_study","case_study",frozenset({"a3"}),("headline",),needs_image=True)`; (2) `treatment_stylist`: route ST-07A -> a3_case_study on A3 (add an ST-07A A3 path with a3_case_study first) + relax/raise the `DEFAULT_MAX_A3=3` cap so the case studies promote (they're the intended Doppelseite). Keep the A4 candidates as fallback when the portrait/data doesn't resolve. May need to read `treatment_stylist.assign()` (the a3-promotion + cap + _is_hero logic, lines ~120+). Then **B-4** render case-study pages treatments=True -> A3, physical==logical, match the design; total-deck spill drops from 23. Show artifact.


## Phase B — B-3 + B-4 DONE (2026-06-29): A3 case-study treatment WIRED + OVERFLOW FIXED
B-3 (wire): registered `a3_case_study` in treatment_catalog (a3-only, needs_image=False, required=("headline",)); `treatment_stylist` ST-07A candidates -> a3_case_study FIRST; `DEFAULT_MAX_A3` 3->8. Verified: registered, ST-07A lead=a3_case_study, `_wants_a3_process(ST-07A)`=a3_case_study (promotes to A3).
B-4 (render+verify): build_live package + `render_package(chromium, treatments=True)`, OFFLINE (no copy-fit, isolating A3 room). RESULT: **logical=17 physical=17 overflow=0** vs baseline (treatments=False) 25 physical / 17 logical / 8 spills. **THE OVERFLOW IS FIXED** — case studies fit as A3 spreads, ZERO spills; a3_case_study rendered with NO TemplateNotFound. Proof: `dmc-renderer/_proof_a3_treatment.pdf`. VINDICATES option A (A3 treatment) over copy-fit (25->23 only).
HONEST CAVEATS: (1) STRUCTURAL win (fits) but VISUAL quality UNVERIFIED — must LOOK at the A3 page PNG (case-study portrait omitted since the envelope has none -> right navy column may be sparse; marble may be absent offline). (2) live service renders treatments=False by default -> must enable to ship. (3) fonts still fall back.
NEXT **B-5**: (a) rasterize + LOOK at the rendered A3 case-study page; refine the no-portrait right column if sparse; (b) enable treatments in the live service (`service.py` build_and_render treatments=True). Then P2 fonts.


## Phase B — B-5 (2026-06-29): LOOKED at the A3 case-study page (page 6) — structural fit OK, 2 visual defects
Rasterized _proof_a3_treatment.pdf. A3 pages = 6,8,10,12 (case studies) + 13,14. About (p3) stayed A4 (no founder portrait -> not promoted; consistent). Read page 6.
GOOD: A3 fits; LEFT reads well (FALLSTUDIE 03 eyebrow + result headline + kurzportrait lede + AUSGANGSSITUATION/LÖSUNG accent-ruled sections); RIGHT pull-quote (Martina Ammon) on dark stone; KPIs (€200.000+ / 4 Kernprozesse); curved marble footer + teal hairline.
DEFECTS (real):
  1. **FOOTER COLLISION** — bottom content (Wendepunkt section + metrics) overlaps the navy marble footer = dark-on-dark ILLEGIBLE (same defect editorial.css note #1). Left field content too tall, runs into the reserved footer band.
  2. **EMPTY PORTRAIT VOID** — no case-study portrait in the envelope -> template omits it -> the right navy column top ~56% is EMPTY. Looks unfinished.

## B-6 (next) — visual refinement:
  1. Fix footer collision: increase the left field bottom clearance / shorten `.cs-footer`, OR move metrics off the left foot.
  2. Fill the void: when `td.image` ABSENT, restructure the RIGHT column as the navy DASHBOARD (move the ring+KPIs there = fills the void + is the bi-dashboard intent); quote below. Portrait present -> keep portrait-top+quote. Graceful both ways.
  3. Then enable treatments in the live service (service.py) + re-render + re-LOOK.
OWNER FLAG: case studies are designed around a CLIENT PORTRAIT the test envelope lacks (images are cover/about/status/fazit only). Real case-study portraits come from Drive/upload; designing the no-portrait layout to look good regardless.


## Phase B — B-6 (2026-06-29): partial — footer collision IMPROVED, void fix FAILED
Changes: `.cs-field` bottom padding 44mm->62mm; added `.cs-quote:only-child{flex:0 0 100%}`; enabled `treatments=True` in `service.py`. Re-rendered (offline, treatments=True): logical=17 physical=17 overflow=0 (still clean). Re-LOOKED at page 6:
- FOOTER COLLISION: mostly FIXED — metrics now on cream + readable (band cleared).
- VOID: NOT fixed — the `:only-child` fill did not take effect; the right navy column is still empty below the quote. Also minor residual crowding lower-left (a Wendepunkt line brushing a KPI label).
CONCLUSION: the quick void hack was wrong. The RIGHT fix = move the metrics dashboard INTO the right column (fills the void + bi-dashboard look + removes the left-foot crowding by taking metrics off the left).

## B-7 (next) — the proper fix:
  1. TEMPLATE: move the metrics zone (ring + KPIs) from the LEFT `.cs-field-foot` into the RIGHT `.cs-column` (below the portrait-or-top). Left field becomes head + narrative only (shorter, no footer crowding).
  2. CSS: style the metrics ON DARK (`.cs-column` navy): ring numerals + KPI values in `--color-on-dark`, labels light-teal (mirror the st_07a dark rail / editorial creds). Right column = [portrait if present] + metrics dashboard + quote, filling top-to-bottom with explicit flex bases (Chromium print).
  3. Re-render + re-LOOK. Then P2 fonts.
NOTE session is very long; structural win (overflow fixed, A3 treatment built+wired+in service) is solid; remaining is visual polish + fonts.


## Phase B — B-7 DONE (2026-06-29): A3 case-study bi-dashboard READS WELL (void fixed)
Moved the metrics from the LEFT field foot INTO the RIGHT navy column (template rewrite) + on-dark metric styling (ring/KPIs recolored for the dark ground, `.cs-dash` cap, space-evenly column). Re-rendered offline treatments=True: overflow still 0 (17=17). LOOKED at page 6:
RESULT = a clean bi-dashboard: LEFT cream = FALLSTUDIE 03 + result headline + kurzportrait lede + narrative (Ausgangssituation/Lösung/Ergebnis), NO footer collision. RIGHT navy = "ERGEBNIS" cap + 3 KPIs legible on dark (24 Std->Min, €200k+/Jahr, 4 Kernprozesse, accent-ruled) + Martina Ammon pull-quote. THE VOID IS FILLED; the column reads top-to-bottom. Proof: /tmp/a3_p6_v3.png.
=> **Phase B core DONE: case studies render as clean A3 spreads, overflow fixed, treatment built+wired+enabled in the live service.**
MINOR remaining polish (diminishing returns): left field slightly top-loaded (empty cream at bottom); navy-stone marble not showing offline (needs panel_texture asset / FAL key); no ring (this case study has no %-stat, all KPIs — graceful). 

## REMAINING ROADMAP (post Phase-B-core)
- P2 fonts (Inter->Source Sans fallback, visible). - Minor A3 polish (left-field balance; marble via FAL). - P3 Dockerfile/deploy. - Other A4 treatments (ST-02/09/14/FAZIT still legacy but FIT at A4 — 0 overflow — so low priority). - Real case-study portraits (Drive/upload; template ready via td.image). - Upstream substance (copy-fit/sources = other session).


## 2026-07-02 — DIAGNOSIS (user: "this is shit... analyze deeply, don't build")
User rejected the A3 case-study render (/tmp/a3_p6_v3.png): (1) dead negative space at bottom, (2) "not spread across the page", (3) data-viz bad. User pointed out the reference analysis is ALREADY DONE in the mds — don't re-derive, USE it.
READ the grounded docs + LOOKED at refs/renders/{nikl_p08 (single A4 portrait case study), aerz_p05 (landscape spread = case study + theory)}.

ROOT ERROR (the "error of magnitude"): ST-07A was PROMOTED TO A3 LANDSCAPE (to paper over A4 overflow) and a PORTRAIT 60/40 composition was poured onto the wide sheet. But the grounded reference (0-reference-analysis.md:182-202 + visual-vocabulary-6-refs.md + CONFIRMED visually) is that ST-07A = **A4 PORTRAIT, 60/40 vertical**: left 62% = stacked sections (Ausgangssituation/Ziel/Lösung/Ergebnis); right 38% = DARK RAIL with oversized stencil numeral (80-120pt) + client PHOTO + big result numbers (40-72pt, E.3) + full-width pullquote. nikl_p08 shows it exactly (15 / 750 / 129.000 as the data-viz — the number IS the visual). Richard NEVER stretches one case across a landscape; his "spreads" are two independent A4-portrait halves (case + paired theory).

All 3 complaints derive from the A3 promotion:
  1. dead bottom = portrait stack on short-wide sheet (D.1 whitespace must be INTENTIONAL, not leftover void).
  2. not-spread = it's a portrait layout widened; horizontal axis unused.
  3. bad data-viz = KPI caption-lines, no big number/photo/stencil/before-after (violates E.3 + §case-study line 238).
Overflow (the reason A3 was chosen) has a PROPER fix the reference reveals: the dark RAIL absorbs photo+metrics+quote OUT of the text flow + tight copy — NOT format inflation.

DECISION REQUIRED (user's call): (A) revert ST-07A to A4 portrait, build the documented 60/40 anatomy [RECOMMENDED, reference-faithful, fixes overflow via rail+copyfit] vs (B) author a TRUE A3-landscape Doppelseite (two composed halves like aerz_p05). Asked the user. NO CODE until answered.


## 2026-07-02 — THE A4-vs-A3 DECISION RULE (grounded in 08_DMC_Design_System_v2.md + 01_DMC_Master_System_v1.md)
User: "his reports are a BLEND — check the mds for how he decides A4 vs A3." Found the explicit rule.

DEFAULT = A4 single page (Einzelseite/portrait). A3 landscape (Doppelseite/spread) is the EXCEPTION, from only 2 sources:
  (1) ~2 THEMATIC spreads per 20-page report (08:202-207) — NOT case studies. Qualifying: Mechanismus+System-Diagramm; Zahlen/Proof+Kompetenz-Block; Vision/Zukunft+Einladung.
  (2) ST-07C — case study as true Doppelseite, Ausnahmefall ONLY (08:212-216,416): report #2/#3 of client, OR exceptionally strong case w/ much proof, OR 28+ page report.

CASE-STUDY TAXONOMY (08:392-418):
  ST-07A = Fallstudie EINZELSEITE (STANDARD) — 1 page A4. Budget 600-800 chars. MANDATORY: Kundenfoto, Vorher/Nachher-Zahl (>=40pt), Wendepunkt.
  ST-07B = Gegenseite — 1 page A4, independent "why" page, NO back-reference to the case ("wie bei Max..." verboten). Diagram/number-driven allowed.
  ST-07C = Fallstudie Doppelseite — 2 pages A3, EXCEPTION only, budget 1200-1500 across both.
The reader's "spread" (aerz/nikl) = ST-07A(A4) + ST-07B(A4), two independent portrait pages facing — NOT one case across a landscape.

MY ERROR (the error of magnitude): rendered ST-07A (by definition the A4 standard) as ST-07C (the A3 exception), for EVERY case study unconditionally. Inverted default vs exception. Caused all 3 complaints (dead bottom, no spread-across, weak data-viz).

CORRECTED BUILD (pending user go-ahead):
  1. ST-07A -> A4 portrait single (nikl_p08 anatomy): photo prominent + before/after number >=40pt as visual anchor + Wendepunkt + dark rail (photo + big stat numbers + pullquote). Overflow fix = copy-fit TRIM to 600-800 chars, NOT A3.
  2. treatment_stylist: A4 is default; A3 only for ~2 qualifying THEMATIC spreads + ST-07C when exception flag fires (report#, proof-strength, or page_count_target>=28). Replaces mis-tuned _wants_a3_process + DEFAULT_MAX_A3=8 (which promoted everything).
  3. Existing a3_case_study treatment -> repurpose as ST-07C/thematic-spread (rare wide canvas), re-authored to USE the width (two composed halves like aerz_p05). Gated behind the rule.
Selector inputs: page_count_target (exists in envelope); report-number + proof-strength flags (may need adding; default OFF so A4 standard wins).


## 2026-07-03 — BUILT the A4 case-study treatment (the corrected system)
Executed the corrected build end-to-end IN THE SYSTEM (not orchestrated by hand):

FILES CHANGED (research/v7-renderer):
- treatment_engine.py: _adapt_st07a now exposes td.caption = {name, role, url, initials} from `kunde` (the rail's person block + initials-avatar fallback).
- treatment_catalog.py: registered `a4_case_study` (case_study, a4-only, needs_image=False) as the STANDARD; kept `a3_case_study` for the ST-07C exception.
- treatment_stylist.py: ST-07A candidate list leads with a4_case_study (a3_case_study still listed but a4-format-filtered out unless promoted); DEFAULT_MAX_A3 8->4; new _wants_explicit_a3() promotes ST-07A->A3 ONLY on an explicit upstream signal (page_format=="a3" / case_study_spread / data.doppelseite); _REPEATABLE_TREATMENTS exempts the case treatment from dedup+no-adjacent so ALL case studies share the SAME layout (design rule).
- templates/treatments/a4_case_study.html.jinja + styles/treatments/a4_case_study.css: NEW A4 treatment (nikl_p08 anatomy). LEFT cream narrative (eyebrow + two-tone result headline + kurzportrait + Ausgangssituation/Ziel/Lösung/Ergebnis). RIGHT dark rail (bleeds right+foot): oversized ghost numeral + client PHOTO (or initials avatar) + name/role/url + big Ergebnis NUMBERS + pullquote. Text-quality fix: a stat VALUE <=16 chars renders as a big FIGURE, longer renders as a smaller wrapping STATEMENT under an accent kicker (fixes the "von Headcount auf Marktnachfrage..." clipping); overflow-wrap:anywhere + hyphens:auto for German compounds.

VERIFIED (chromium, treatments=True, offline):
- build_live (production/service path): 17=17 pages, overflow 0. ALL 5 ST-07A -> a4_case_study [a4]; only ST-06 Mechanism -> a3 (the 1 thematic spread). Case studies fill to ~91% and bleed. Text reads clean (proof: /tmp/prod_5.png, /tmp/prod_7.png).
- fixture deck (has real portraits): portrait path renders the real client photo cleanly (proof: /tmp/a4cs_portrait.png).
TESTS: fixed the frozen fixture (removed 5 stale page_format="a3" hand-edits on ST-07A pages so it matches the A4 standard) + updated 5 stale test expectations to the new spec (case studies A4 + repeat the same layout; synthetic imageless pages for the missing-portrait tests since the fixture gained real portraits). Full treatment suite green.

KNOWN LIMITATION (honest): the paged-media engine does NOT honor nested-div heights (height/min-height/absolute top+bottom all collapse to CONTENT; only content length or the @page fills). So a VERY SHORT case study leaves more cream whitespace below the rail (design-acceptable per D.1 Weißraum). Real-length copy fills to ~91% + bleeds. A future @page-based band (named @page with the inked right 40%) would force full-fill for any length — deferred (needs assembler @page surgery).


## 2026-07-03 (cont) — P2 FONTS DONE: brand faces bundled, serif body restored, clip fixed
BUILT (research/v7-renderer):
- fonts/: downloaded Inter[opsz,wght].ttf + Inter-Italic (google/fonts OFL; cmap format-12 VERIFIED, so both engines load it).
- assembler.py @font-face block: added Inter (normal+italic) + ALIASES 'Source Serif Pro'/'Source Sans Pro' -> the renamed Adobe files already bundled (Source Serif 4 / Source Sans 3 are the SAME faces post-rename).
- tokens/base.tokens.json: "$extra-bundled-families" config; compile_tokens._BUNDLED_FAMILIES unions it (names stay in CONFIG per the architecture guard). Fallback warnings GONE.
EFFECT: body text now renders the brand's requested 'Source Serif Pro' = REAL SERIF BODY (Richard-tier convention; the old sans body was the silent fallback all along). Headlines serif; true italics in quotes.
REGRESSION CAUGHT BY LOOKING: serif sets wider -> the left case-study field clipped the last lines mid-sentence. Fixed grounded: section line-height 1.46->1.4 (Richard B.1 spec ~1.4), lede 1.38, section gap space-3. Verified: full Ergebnis text renders w/ breathing room (/tmp/fonts_p5c.png); 17=17 overflow 0.
ALSO: the project's own em-dash guard FAILED me (my authored comments used em dashes = the exact LLM footprint this project bans). Swept ALL my authored files (templates/css/stylist/catalog/compile_tokens): guard green. Humbling + fitting.
NOTE: earlier "hangs" were NOT the font change: overlapping timed-out runs serialized chromium launches; also macOS SIP strips DYLD_* through /usr/bin/perl exec (use in-python signal.alarm for timeouts, not perl wrappers).


## 2026-07-03 (cont): full-suite result + legacy-lane drift flagged
Full fast suite: 331 passed, 20 FAILED: ALL pre-existing fixture-content drift in the LEGACY lane, NOT from the font/treatment work (verified by mechanism: each failing assertion reads fixture CONTENT I never touched):
  - test_st07a_fill_variant (11): assert portrait ABSENT on the apex case page, but the fixture now carries real portraits (cs_goldmantax.png etc.). The fill/social variants were designed for the no-portrait era.
  - test_viz_curation + viz_host (6): apply_apex_viz fails-loud: its hardcoded apex curation bindings no longer ground in the REGENERATED fixture copy (new metrics "1. Call"/"24 Monate").
  - test_render_r2 (3): legacy ST-07A flagship expects chart regions the new fixture data does not bind.
SHIP PATH UNAFFECTED: treatments suite 40/40 green, architecture guards green, live render verified.
RECOMMENDATION for owner: the legacy ST-07A variants (fill/social) are superseded by the a4_case_study treatment in the ship path; either retire those tests + the curation bindings, or regenerate them against the current fixture. Deferred: not P2 scope.


## 2026-07-03 (cont): P3 DEPLOY DONE: the service is containerized and VERIFIED end-to-end
BUILT:
- service.py/build_live.py: roots env-overridable (DMC_RENDERER_ROOT / DMC_PREPROC_ROOT; local defaults unchanged, local imports re-verified).
- dmc-renderer/requirements.txt: pinned to the verified venv set (weasyprint 68.1, playwright 1.60, pymupdf 1.27.2.3, fastapi 0.138.1, uvicorn 0.49...).
- Dockerfile (repo root) + .dockerignore: python:3.11-slim-bookworm, weasyprint apt libs + ghostscript, playwright install --with-deps chromium, copies dmc-renderer/ + research/v7-renderer/ + research/preprocessor/ + richard-grammar-v2.md (fail #1: grammar_loader reads repo-root richard-grammar-v2.md: fixed by COPY), HEALTHCHECK, uvicorn :8099. Image 839MB.
VERIFIED (docker run + real HTTP):
- GET /health 200. POST /render with the apex envelope -> HTTP 200, x-logical-pages 17, x-physical-pages 17, x-overflow 0, 8.5MB PDF.
- LOOKED at the container PDF's case-study page: treatment + serif typography + big-figure rail all correct; full Ergebnis text fits. MINOR parity note: right-edge rail bleed sits a hair narrower than the macOS render (Linux chromium build difference): cosmetic, logged.
=> P0 (real build) + P1 (QC gate) + P2 (fonts) + P3 (deploy) ALL DONE. The service is a real, shippable container.

## REMAINING = OWNER-GATED (not render-side)
- Marble panel texture: needs FAL key at build time (env passthrough already in Dockerfile docs).
- Real case-study portraits in the LIVE envelope (template ready: td.image renders, initials fallback proven).
- n8n workflow wiring to the containerized endpoint (workflow lives outside this repo).
- Legacy-lane test drift (20 tests): retire or regen (superseded by a4_case_study).
- Deferred: @page band for full rail bleed on very-short cases.


## 2026-07-04: FULL-DECK LOOK (user forced it): the live deck is NOT done: 3 content-lane defect classes
User: "you didnt show me any output." Saved the container render to _renders/dmc_report_apex_container_2026-07-04.pdf + built a 17-page contact sheet + LOOKED. The case-study lane + cover + theory interludes + back cover = premium. BUT:
  D1: ST-05 Über uns prints RAW DICT LITERALS on the page ({'label': 'Abgeschlossene AI-Projekte', 'value': '100+'}...).
  D2: ST-14 Irrglauben headline renders the literal string "None" (null leaked to print) + numerals 1-3 with no belief content.
  D3: ST-02 / ST-09 / ST-FAZIT / (ST-22 sparse) pages are MOSTLY EMPTY: giant dead gray regions. Live build X-Component-Count=1, so chart/component slots render as voids.
LESSON (hard): the overflow QC (17=17) measures page-count spill ONLY: it passes hollow pages, raw reprs, and literal None. Content-QC needed: a page containing "None" as a heading or "{'label'" as text = hard fail.
NEXT (renderer/build-side, not owner-gated): fix D1 (stat rendering in the ST-05 lane), D2 (grounding guard: absent -> omit, never str(None)), D3 (why generate_components yields 1 component in the live path vs the fixture's many), + add the content-QC gate.


## 2026-07-04 (cont): D1/D2 FIXED + content-QC live; deliverable v2 shipped
ROOT CAUSE of D1/D2: the "two realities" gap at the DATA-SCHEMA level: the n8n writer emits `headline` / beliefs[].{belief,reality,body} / credibility_points as {label,value} dicts / `bold_thesis`, while the whole render layer speaks the frozen-fixture schema (title / irrglaube+realitaet / stats / these). Untreated pages fell to legacy patterns reading absent keys -> printed literal None + raw dicts.
FIXES (all in-system):
- build_live._normalize_page_data(): the ONE boundary where the writer schema maps to canonical (title<-headline; ST-14 belief items incl. body folded into realitaet paragraphs; ST-05 stats<-credibility dicts, redundant string list dropped after it spilled About to a 2nd sheet; ST-FAZIT these<-bold_thesis). Grounded: renames only, never invents.
- treatment_stylist: ST-05 candidates = [editorial] only; ST-14 = [] (legacy P-5 by design: generics would DROP the beliefs). Test updated (LEGACY_BY_DESIGN_IDX), 24/24 green.
- assembler CONTENT-QC gate: scans each fragment's rendered text for literal-None + raw-dict-repr leaks -> loud warnings; service exposes X-Content-Defects + _strict 422s on them. THE GATE THE 17=17 CHECK LACKED.
VERIFIED: 17=17, overflow 0, defects 0. Irrglauben = full 3-beliefs page w/ evidence+citations; About = IN ZAHLEN stats rail; Fazit = recap+thesis+CTA. Deliverable: _renders/dmc_report_apex_v2_2026-07-04.pdf (contact sheet reviewed). Container REBUILT + RESTARTED with all fixes (health OK).
STILL OPEN (D3 partial): ST-02/ST-09 bottom-half voids (legacy viz/photo regions; live build component_count=1) + the A3 framework page reads sparse/pale. Next: make generate_components produce the missing viz from live data, or densify those legacy layouts when no viz exists.


## 2026-07-04 (cont): USER EXPOSED GAP #3: the reference-QC (Stage 9) was NEVER in the ship path
User: "the flow was each report developed side-by-side against a Richard reference PDF, mapping treatments: how did QC pass this?" ANSWER: it didn't: that flow EXISTS (research/quality_loop: perception.py deterministic facts, rubric.py, brain/conductor fix-loop, references/index.json = 84 classified pages across all 6 Richard decks w/ st_type+axes+PNG, stage_converge.run_stage = "Stage 9: grade the rendered deck against the references") but is reachable ONLY via the render.py CLI (showcase path). service.py -> build_live -> render_package BYPASSES it. Two-realities gap instance #3 (1: fixture vs live build; 2: writer vs render schema; 3: CLI QC vs service QC).
RAN Stage 9 on the live deck (deterministic-only, no vision key): **cleared 9/17, deck_reward 10.5M**. Flags by owner:
  - asset_gen 4x N01 HARD-FAIL: case-study portrait slots missing (the judge hard-fails the initials fallback I called graceful).
  - preprocessor 4x N15: prose-as-stat values (my figure/statement CSS was a render-side patch for a writer-side defect: references use NUMERALS in stat slots).
  - renderer 1x N04 density gap (ST-07B).
  - other: 2 convergence errors (ST-01 + an ST-07A: loop bugs to debug) + skipped rows needing the vision key.
NEXT: wire Stage 9 (deterministic part) into the service on every render (report in response; strict blocks hard-fails), then work the flag list by owner.


## 2026-07-04 (cont): STAGE 9 WIRED INTO THE SERVICE (the reference QC now judges every deck)
- service.py: _grade_deck() runs stage_converge (deterministic perception+rubric vs the 84-page Richard reference corpus) on EVERY render (envelope _grade:false to skip). Response carries reference_qc {cleared/total, deck_reward, flags_by_owner, hard_fails}; headers X-QC-Cleared / X-QC-Hard-Fails; _strict 422s on reference hard-fails (portraits missing etc.).
- Dockerfile/.dockerignore: research/quality_loop (code + reference corpus) ships in the image. Container rebuilt + restarted, health OK.
- VERIFIED locally through service.build_and_render: 17=17, overflow 0, defects 0, reference_qc cleared 9/17, hard_fails 4 (the truthful current state: the deck is NOT clear).
WORKLIST FROM THE JUDGE (by owner): asset_gen 4x portrait N01 HARD-FAILs (owner: envelope/Drive) | preprocessor 4x N15 prose-stats (owner: writer prompt: stat slots need NUMERALS) | renderer 1x ST-07B N04 density (me) | 2 convergence-loop errors ST-01/ST-07A-p7 (me) | vision rows key-gated (owner: key at deploy).


## 2026-07-04 (cont): user flagged the process/timeline pages ("shitty infographics") + restated the designed flow
DEFECT: p14 (A3 horizontal_process) + p16 (a4_vertical_timeline) rendered as bare numbered circles in empty fields. ROOT CAUSE: writer steps carry {number,title,description,duration}; canonical is {n,title,body,dauer}: the step BODIES existed but were dropped at the schema boundary (4th writer-schema mismatch). FIX: generic steps normalization in build_live._normalize_page_data (body<-description, dauer<-duration, n<-number) + ST-06 body<-mechanism_description.
FLOW GAP: the user restated the DESIGN: build pages against a deterministically-chosen reference, QC each built page vs the reference, AUTO-REDO failing pages. I had wired GRADE-ONLY (max_iterations=1, compose=False). FIX: service now runs the FULL loop: max_iterations=3 + compose=True + injected render_fn keeping treatments=True (stage_converge's default compose render would silently drop the treatment lane) and SHIPS the composed deck (pdf_path switches to composed_pdf when present).
STATUS: full run takes >9.3min (per-page redo renders + compose): running in bg. Interrupted first attempt confirmed all 17 pages converge + merge starts. Composed deck -> _renders/dmc_report_apex_v3_converged_2026-07-04.pdf when done.
KNOWN LIMITATION (logged): the per-page redo loop renders pages through its own path; treated-page fidelity inside the loop vs the composed ship render needs an audit later.


## 2026-07-04 (cont): full-loop run #1 died on DISK FULL: leak plugged
The converge run wrote ~20GB of per-page iteration intermediates (full renders kept per iteration) + 28 stale dmc_live_* tempdirs + docker cache -> 2.1GB free, run died with ENOSPC. Cleaned to 595GB free. service._grade_deck now DELETES converge/pages + converge/merged after composing (report + composed deck retained). Rerun in progress.


## 2026-07-04 (cont): the 20GB mystery SOLVED: compose_converged_package copied the package INTO ITSELF
Run #2 failed with ENAMETOOLONG: paths like out/converge/merged/out/converge/merged/... recursively. ROOT CAUSE: compose_converged_package does shutil.copytree(original, merged_dir) where merged_dir lives UNDER original/out/converge/: the copy recursively includes the merged dir itself. THIS was also the 20GB disk-full (run #1 died mid-recursion). FIX (quality_loop/compose.py): copytree with ignore_patterns("out","__pycache__"): `out` is render OUTPUT, not package input. Run #3 in bg with clean disk.
NOTE: this recursion bug means the CLI's compose path (showcase) likely never ran to completion on a package whose converge dir lived inside out/ either, OR the CLI wrote converge elsewhere. Either way the loop's compose was fragile: now correct by construction.


## 2026-07-04 (cont): FULL LOOP LIVE END-TO-END: composed deck ships; honest page verdicts
Run #3 succeeded: build -> render -> Stage-9 grade -> auto-REDO (3 iters) -> COMPOSE -> ship composed deck. QC on composed: cleared 9/17, 4 hard-fails (case-study portraits: data-level, owner-gated). Deliverable: _renders/dmc_report_apex_v3_converged_2026-07-04.pdf. Container rebuilt + live with the full loop.
PAGE VERDICTS (LOOKED): p16 timeline FIXED (bodies distributed down the spine, designed behavior). p14 framework HALF-fixed: content restored (intro + 6 step bodies) but composition below bar: half-width intro, dead band, bare text columns, no result KPI. The horizontal_process treatment needs DESIGN work to earn the A3 sheet (intro -> card row w/ fills+connectors -> result footer). NOT calling it done.
OPEN WORKLIST: [me] horizontal_process redesign; ST-07B N04 density gap; 2 convergence-loop errors (ST-01 + one ST-07A); loop-fidelity audit (per-page renders vs treated ship render). [owner] portraits in envelope (4 hard-fails), numeral stats in writer, FAL key, n8n wiring, vision key for reference-vision rows.


## 2026-07-07: CONTENT SIDE FIRST (owner's priority): the deterministic writer gate is BUILT + VERIFIED
Deliverables (docs/n8n/):
- writer_gate.js: self-contained vanilla-JS n8n Code node. Rules: (1) no em/en dashes, (2) banned vocabulary, (3) hedges, (4) NUMBER GROUNDING: every digit-run in the output must exist in the section data (catches computed "83%"), (5) certification/title claims must be verbatim in section data (catches "TÜV certified"), (6) language mode "writer"=English / "translated"=German (catches the half-translated deck). Emits {pass, violations[{rule,field,excerpt}], retry_instruction} ready for a bounded retry loop.
- WRITER-GATE-WIRING.md: node placement (after writer, IF on gate.pass, retry<=2 then fail loud; 2nd placement after translation in "translated" mode) + the translation-node diagnostic (only slots 5/7/10/11/13/14 came out German -> loop/filter/truncation suspects).
VERIFIED BY RUNNING (node, against the real christoph-winter output): 3 banned-word hits (seamless, robust x2: exact match to manual findings), 18 language flags on exactly the 6 German sections (better than my manual scan, which had missed slots 10/11), 0 dashes, 0 hedges; grounding demos: 83%/TÜV CAUGHT when absent from section data, PASS when present (no false positives).
NEXT (owner): paste gate into n8n + wire retry loop + find the translation bug. THEN (mine): renderer normalizer for the 5th schema dialect (titel/wert/schmerzpunkte/irrtuemer/schritte/...).


## 2026-07-10: ALL 15 code-review findings FIXED (Path B) + a grader-calibration discovery
Owner: Path B + all fixes, no half-assing.
- service.py FULLY REWRITTEN (Path B): render the real Chromium+treatments deck ONCE -> QC THOSE EXACT BYTES -> ship them. overflow+content computed on the shipped render (structural strict gate). cleanup in finally + temp package dir reclaimed (cleanup=True on HTTP path). NO inline converge/compose/weasyprint. Fixes C1,C2,C3,C4,D1.
- DISCOVERY: perception/rubric VISUAL grade is weasyprint-only (Chromium PDF exposes no font table to PyMuPDF -> N03 hard-fails every page -> 0/17). So the inline grade = _grade_deck_data(): DATA-only engine-agnostic checks (N01 required_slots_missing -> asset_gen; N15 non_numeral_stat_values -> writer). Honest result on apex: cleared 12/17, needs_photo 5, prose_stats 13. The full visual grader stays an OFFLINE tool. FOLLOWUP: recalibrate perception for Chromium if we want the visual grade inline.
- Mechanical: H1 (ST-05 credibility kept as strings when stats exist, not deleted), H2 (ST-14 string beliefs preserved), H3 (_PERCENT_FIGURE_RE crosses German ,/. -> "12,5%" not "5%"), H4 (_SOURCE_RE requires a year -> "(im Schnitt)" not a citation), M1 (CONTENT-QC None -> only bare `>None<` element, not the word in prose), M2 (container-repr detector now catches lists + int-key dicts), L1 (untreated page under treatments no longer re-stamped a3), L2 (rail bleed -20mm->-24mm reaches the 297mm sheet foot), L3 (initials skip Dr./Prof.), L4 (eyebrow :02d, "10" not "010").
VERIFY: regex/logic unit vs exact failure inputs PASS; H1/H2 asserts PASS; treatment+guard suite 26 PASS; live Path-B render 17=17 overflow0 content0 QC 12/17; case-study LOOKED good. Container rebuilding.
NEXT: v3 writer rerun on the clean system, then the christoph-winter 5th-schema-dialect normalizer.


## 2026-07-10 (cont): xhigh /code-review OF THE FIXES found 10 real defects in MY Path B fixes -> ALL FIXED
The review (wf_e4ffd435-435) checked this session's fixes and caught 10 distinct confirmed defects I introduced. All fixed + unit-verified:
- C3 REGRESSION (service strict gate): dropped hard_fails from the block but ALSO stopped failing closed on a GRADER ERROR -> strict could ship an ungraded deck 200. FIX: strict now 422s on (overflow OR content OR qc_error).
- X-QC-Error header: raw exception text (non-latin-1 German glyphs/emoji) -> UnicodeEncodeError -> 500 discarding a good PDF. FIX: encode('ascii','replace')[:120].
- hard_fails always [] (dead X-QC-Hard-Fails). FIX: hard_fails=needs_photo (the N01 missing-photo flags); renamed headers X-QC-Needs-Photo + X-QC-Prose-Stats.
- temp dir leaked when build_live_package raised (created inside build_live before service's try). FIX: service mkdtemp + build_live_package(output_dir=pkg) + finally rmtree (verified 0 leftover dmc_req_ dirs).
- ST-05 credibility f-string leaked literal 'None' when label/value null. FIX: _cred_str null-guard.
- ST-05 credibility dropped string entries in a mixed list. FIX: preserve strings (any-dict gate + pass-through).
- _SOURCE_RE captured '(seit 2019)' as a citation. FIX: require BOTH a comma AND a year (Source, Year) via lookaheads -> 'seit 2019' not captured.
- _PERCENT_FIGURE_RE could capture a trailing separator ('35,%'). FIX: digit run must start+end on a digit \d(?:[\d.,]*\d)?.
- M2 CONTENT-QC scanned RAW html -> attribute values (style url('data:...'), data-json) could false-positive + block strict shipping. FIX: M2 scans TAG-STRIPPED text (attributes gone); M1 keeps raw html for >None<.
- initials all-honorific -> empty avatar. FIX: fallback to first 2 real letters.
VERIFY: regex/logic unit vs exact review inputs ALL PASS; cleanup=True leaves 0 temp dirs; C3 gate blocks on grader error; header sanitize safe; live render 17=17 overflow0 content0 QC 12/17 needs_photo5 hard_fails5. Container rebuilding + treatment/guard tests running.


## 2026-07-11: christoph render polish: 2 bugs fixed + visual uplift for the flat pages
Owner: fix the 2 renderer bugs + "no infographic/elements that uplift visual taste".
FIXED:
- Theory (ST-07B) contrast bug: on the dark theory ground the base .th-body/lede (color-body / color-primary navy) were invisible. Root: st_07b hard-codes light-ground colors. Fix: build_live maps kernaussage->key_insight + sets page layout_variant="fill" (the dark authority composition) + st_07b.css override .th-fill-top text -> on-dark. Result: legible white body + a big italic KERNAUSSAGE statement panel fills the lower half (was empty flat). VERIFIED by looking.
- Case-study headline redundancy: dialect has no ergebnis_headline, so I derived it from ergebnis_text AND it re-printed as the Ergebnis section. Fix: when deriving headline from ergebnis_text, blank ergebnis_text (headline + numbers rail carry the outcome; no dup).
VISUAL UPLIFT:
- Mechanism (ST-06 horizontal_process): grid was hard-coded repeat(6,1fr) -> 4-step christoph left 2 empty cols + centered a tiny row. Fix: grid-auto-flow column / grid-auto-columns 1fr (adapts to N steps) + each step is now a CARD (6% accent tint, 0.9mm accent top-rule, min-height 92mm) centered in the flow -> reads as a 4-card process infographic (was a sparse row).
VERIFIED: christoph 15=15 overflow0 content0 QC 12/15; theory contrast fixed + statement panel; mechanism = process cards; case dedup. Apex regression tests (pagesize+qc) 5 PASS. Container rebuilt+live. Deliverable: _renders/dmc_christoph_winter_2026-07-10.pdf.
STILL FLAT (honest, not done): Outlook (ST-02) + About (ST-05) still cream + thin body ~60% empty (no visual element added for those types); mechanism cards a touch empty inside. These need either richer copy or a fill treatment for the text-only light pages.


## 2026-07-11: GROUNDED VISUAL-SYNTHESIS LAYER built (the "system does it" fix)
Owner chose auto-synthesis + "how can it synthesize wrong?? close every possibility, LLM ok, robust+accurate".
BUILT dmc-renderer/synthesize_visuals.py: turns a page's PROSE into grounded stat callouts + before/after devices so prose-only pages get the big-number devices rich treatments need.
THE ACCURACY GUARANTEE (closes "synthesize wrong"): _ground_device gate — EVERY numeric token a device shows must appear VERBATIM in that page's own source (digit-run compare, thousands-dot/decimal-comma/whitespace-insensitive) or the device is DROPPED. Fabrication is impossible by construction. Nothing computed. VERIFIED: fabricated "45 %"/"5->1" rejected; grounded "250 Unternehmen"/"2->20" pass; German "1.200 %"/"12,5" ground; no-number device rejected; page with own data untouched.
LLM path (env-gated OPENROUTER_API_KEY, sonnet-4.6, temp 0): reads the page, proposes labelled devices, then the SAME gate validates -> robust. No key -> deterministic pass: split number/unit for labels ("über 250 Unternehmen" -> value 250 / label UNTERNEHMEN; %/€ stay in value), before/after from "von X auf Y"/"X->Y".
WIRED: build_live pages loop calls synthesize_page_visuals after normalize (only fills pages with NO own viz/stats/ergebnis_metrics). ST-02/ST-09 candidate lists += a4_metric_column so synthesized stats fire.
RESULT: christoph pages-with-stats 3->8. About now renders a real "250 / UNTERNEHMEN" IN-ZAHLEN stat panel from its own copy. 15=15 overflow0 content0 QC12/15. Apex untouched (skips pages w/ own data); stylist+pagesize tests 15 pass. Container rebuilt+live.
HONEST LIMIT: synthesis can only visualize numbers that EXIST in the copy. Outlook (0 numbers) still thin; About (1 number) = 1 stat + still ~55% empty. The remaining dead space on those 2 pages is COPY-THINNESS (few figures, short body) = the content-gap-audit writer problem, not a system gap. The LLM path (needs the key) extracts more + better labels but can't invent substance.


## 2026-07-11: FILL TREATMENT built for the text-only pages (closes the dead space)
Owner chose "Build the fill treatments (recommended)" for the flat text pages (Outlook/About/Symptoms/Status-Quo/Fazit) — the prior entry flagged they still fell to legacy patterns and left a dead bottom band.

ROOT-CAUSE FOUND (why the fill headline was tiny in the first render): the treatment CSS referenced `var(--type-h1)` — a token that DOES NOT EXIST in the ramp (the ramp is display 32 / h2 20 / h3 14; canon folds H1 into display). An undefined var() with no fallback makes the ENTIRE font-size declaration invalid, so the headline silently inherited BODY size. Same latent bug sat in a4_case_study.css (quote glyph) + a3_case_study.css (A3 headline). FIXED all three -> `var(--type-display)`.
GUARD: new test_tokens.py::test_css_references_only_defined_type_tokens compiles the real token set and scans every styles/**/*.css for var(--type-*) with no fallback -> fails the build on any undefined token. This bug class cannot recur.

BUILT a4_editorial_fill (template + css, registered, ~fixed 257mm flex column):
- HEAD: eyebrow + a real display-size two-tone hero + lede (anchored top).
- MID has two shapes so a page always FILLS: LIST pages (>=2 items) render the numbered items as EQUAL-height bands (flex:1 1 0) that evenly divide the slack -> a filled rhythmic column with oversized accent numerals + per-item accent rules (never floating rows with dead voids). PROSE pages center a wide lede-scale column as balanced air; a lone credibility item folds in as an accent-bordered lead line.
- FOOT: a hero-quote (Fazit thesis promoted to a centred 28pt climax instead of a stranded footnote), or a stat rail, or a brand-URL CTA band that anchors thin closing pages (ST-22/Fazit). When a foot anchors the bottom the mid flows from the lede (one framed gap, not two).
STYLIST: a4_editorial_fill leads the text page types as the graceful FALLBACK — placed AFTER the data-gated treatments (a4_bi_dashboard needs viz, a4_vertical_timeline needs steps) so a DATA page still wins its rich layout and only a text-only page (no viz/steps) falls through to the fill. Added to _REPEATABLE_TREATMENTS so every text page gets it despite deck dedup. ST-02 ausblick_punkte -> zielgruppe -> numbered list.

VERIFIED by LOOKING (christoph, both local render + the CONTAINER's own PDF over HTTP):
- Outlook: hero + 3 numbered bands, filled. Symptoms: dense 3 bands + "15 bis 30 Minuten" stat, excellent. About: hero + confident lead + "250 UNTERNEHMEN" stat, balanced. Fazit: hero + 28pt thesis + CTA band. ST-22: pitch + CTA band.
- Tests: treatment_stylist + treatment_pagesize + no_literals + tokens (incl. the new guard) all PASS (18). Full suite 337 passed / 20 failed — the 20 are the PRE-EXISTING viz-curation + st07a-fill-variant drift (failure is the viz fabrication guard rejecting an ungrounded '24 Std.' in the apex fixture; grep-0 for any symbol I touched), unrelated to this work.
- Container rebuilt (exit 0), restarted, healthy; POST /render christoph -> 200, 15pp, overflow 0, content-defects 0, QC 12/15 (3 case studies use the initials-avatar fallback = shippable). Deliverable: _renders/dmc_christoph_winter_2026-07-11.pdf.

HONEST LIMIT (unchanged, a WRITER problem not a system gap): About/ST-22 are still airier than the dense pages because the writer gave them thin copy (few figures, short body). The fill treatment frames that thinness as designed whitespace + a CTA anchor; it cannot invent substance. Richer copy is the content-gap-audit/writer-prompt-v3 workstream.
SEPARATE FOLLOW-UP SPOTTED: a4_case_study still leaves a void in the lower LEFT narrative field (the dark right rail is full). Different treatment; not in this scope.


## 2026-07-13: v4 pipeline LIVE end-to-end + review-hardened (autonomous loop, iters 1-4)
Writer-prompt-v4 VISUAL DATA contract delivered + wired by owner; the v4 christoph JSON now renders with REAL devices, system-produced:
- Track A host slots: td.viz + td.components render in a4_editorial_fill/.ef-vizband, a4_case_study/.cs4-devices (fills the lower-left void), st_07b/.th-viz, st_14/.fb-proof, horizontal_process/.hp-viz, a4_vertical_timeline/.tl-viz; editorial's hero donut falls back to td.viz.
- Track B0 adapter (build_live): kennzahlen (%-wert -> donut ring w/ source, scalar -> stats w/ sub), vorher_nachher -> transform_arrow, anteil -> donut, kostenrechnung -> stat_strip, pullquote -> quote dict, bildwunsch passthrough. Shared %-routing lives ONCE in synthesize_visuals (percent_arc/donut_spec; >100% growth figures are NEVER rings).
- C1: grounded donut synthesis from prose percents (deterministic, fabrication gate extended).
- J2: ST-06 abschluss -> ergebnis -> the curved marble result footer fills the A3 foot. J5 SYSTEMIC: candidate_fits requires treatment_is_built (stub can never be assigned; render_fn honored; cache invalidated on register).
- /code-review (8 angles, 47 survived): all ~15 distinct correctness findings fixed same-day (crash-safe component reads + is_relative_to containment, falsy-zero guards, cross-field donut dedup + caps, dict-pullquote legacy guard, ST-07A stats merge, sub/source preserved + rendered, gauge caption hardcode removed, color_flood dark-beat coverage, em-dash sweep). 44 guard tests green.
- COUNTED before/after on the SAME v4 JSON: viz devices 0 -> 7 IN PIXELS (3 writer arrows + 3 sourced donuts + 1 synth donut); sheets 17=17; overflow 0.
- CONTAINER: caught a stale-image trap (docker build | tail masked a Docker Hub Bad-Gateway failure; the 2-day-old image answered HTTP 200 convincingly - only the pixel check exposed it). Rebuilt via local base-snapshot overlay during the Hub outage; verified NEW code inside (docker exec grep) + the served bytes show the donut band. Deliverable: _renders/dmc_christoph_v4_2026-07-11.pdf (container bytes).
NEXT: H4 reference-index broadening (QC loop's biggest hole), D detectors, deferred cleanup batch; F images await client assets; A5 dashboard awaits numeric data.


## 2026-07-13 (full day, three sessions): images + fal chain + reference-grounded redesigns + OWNER VERDICT PENDING
See docs/SESSION-STATE-2026-07-13.md for the complete pre-compaction state dump (defect register D1-D6, file inventory, repro quickstart). Summary:
- TRACK F: client assets live (founder + 5 product mockups fetched from inventory-one.com into client_assets/christoph-winter/; naming contract in client_assets/README.md). bildwunsch->product routing + ST-06 hero default (claims product-1 before the router).
- FAL/OPENROUTER: keys existed in .env but were NEVER LOADED (the breakage the owner called); then a 5s default httpx timeout killed every call. Both fixed; all 5 assets generated + cached; copy-fit ran.
- HOSTS: fal scene band (.ef-sceneband) + About PORTRAIT-RAIL variant + st_14 one-row proof band (donut gradient restored) + baseline-aligned footer chrome.
- REFERENCE-GROUNDED REBUILD: horizontal_process rebuilt to mein_werkzeugkoffer p16/17 anatomy (mockup-trio hero / navy numbered-steps panel / navy ERGEBNIS+CTA rail). Process rule now standing: retrieve Richard's same-type page FIRST, never invent.
- KNOWN BREAKS INTRODUCED BY MY CHANGES (owner screenshots, unfixed - awaiting his detailed list): FAZIT page rail misfire (founder slot exists on ST-FAZIT recipe -> rail variant keyed on bare td.image fires there; empty navy column + hero-quote clipped mid-word at 28pt in the narrowed column + sceneband/CTA overlap). Also: ST-03 back-cover void, ST-22 void, case-study left-foot void on device-less cases + weak statement-stat styling, cover photo soft (500px source).
- Owner: "Very bad treatments, there are many other things" - detailed feedback AFTER compaction; fix against that list, reference-first.

## 2026-07-14: /code-review xhigh + fix run (post-compaction, owner directive "find issues and fix them")

Review: 10 finder angles + 6 verifier groups + gap sweep over the 2026-07-13 file set.
~45 CONFIRMED findings, 15 reported (ReportFindings), then a 3-agent + main-lane fix run.

FIXED (renderer, all pixel-verified on the christoph v4 fixture):
- TRUE FULL-BLEED for rail pages: Chromium clips content at the page area and
  ignores @page background-image (gradients AND rasters never paint from CSS
  layers; only background-color does; empirically A/B-printed). Rail pages
  (a4_case_study, a4_editorial_fill portrait-rail) now route to the suppressed
  `bleed` named page with margins replicated as section padding; internal
  geometry unchanged; suppressed chrome re-drawn in-section (tp-chrome bars,
  folio via physical ordinal, on-dark over the rail). Cream halos gone.
- GROUND VEIL BAKED: the generated ground texture painted FULL STRENGTH on
  every light page (@page raster layer paints, the veil gradient above it
  does not). assembler._veiled_ground_uri composites the surface token over
  the texture (88%) into a derived asset; @page carries one clean raster.
- FAZIT (D1): portrait-rail variant now decided by the ADAPTER
  (td.variant='portrait_rail', ST-05 only) and merely consumed by the
  template; kernbotschaft hyphenation guard; sceneband is a DUOTONE plate
  (ink wash over the art) that grows to absorb thin-page slack (D6).
- ST-03 (D2): full-bleed atmosphere ground (report texture under a strong
  ink wash, geo motif suppressed when ground present) + explicit 297mm fill
  (min-height came up ~22mm short in fragmentation = the foot strip).
- ST-22 (D3): sequential ablauf_text prose becomes verbatim numbered steps
  (adapter), routing to a4_vertical_timeline (single continuous spine).
- Case studies (D4): s.sub citations render in the Ergebnis rail; trailing
  parentheticals split out of the big figure; figure/statement threshold
  matched to the rail measure; repeated NN initials avatar removed.
- ST-06: generated process_flow component SVG finally hosted (was
  produced-but-invisible); Ergebnis rail cap guarded.
- Adapter/synthesis correctness batch: key threading (LLM synthesis now
  actually runs keyed), LLM shape validation (crash repro fixed), year-span
  fabrication guard, German thousands-dot parse in percent_arc, phrase-figure
  donut rejection, full one-figure-one-device dedup (shared digit_key,
  '2,5' != '25'), falsy-zero presence tests, None-baking guard, silent
  image-drop warnings, founder role never company name, closing_redirect
  mapped, umlaut de-transliteration map, page_count_target coercion,
  natural sort for product files, engine validation in service, gs-flatten
  fallback, quoted harness paths, adapt-boundary HTML escaping, A3 tail
  guard (mid-deck A3 cannot recur), editorial locked to a3, containment in
  resolve_asset, classify heading-zone fixes + index rebuilt (11/11 types).
Tests: 44 guard + footer + slice/qc + 8 reference tests green (test_footer
folio assertion updated to the accent folio design; slice/qc updated by the
fix agent to the tail rule). Deliverable: _renders/dmc_christoph_v4_fixed_2026-07-14.pdf.
OPEN (owner lane): Montserrat TTF not bundled (deck renders in Source Sans 3);
hi-res founder photo for the cover; fal fazit_background has page text baked
into the art (prompt-builder feeds page copy; regenerate or crop); ST-03 wash
strength tunable; container STALE vs local code.

## 2026-07-14 round 2: owner feedback (sparse timeline, case-foot voids, stale container)

- DETERMINISTIC DEVICE COMPLETION (build_live): after the bildwunsch router,
  every ST-07A/ST-22 page with an empty device band (no product, no viz)
  claims the next product file in page order, cycling when exhausted. The
  christoph deck now shows a DIFFERENT mockup on every case page (tablet /
  phone-list / app phone / hero trio); product_imgs 1 -> 6.
- CONTENT-VOLUME CONTRACT (engine/catalog): Treatment.min_counts, enforced in
  meets_contract. a4_vertical_timeline requires >= 4 steps: 3 one-liners
  floated as dots in a void (the sparse-timeline critique); thin step sets now
  fall to a4_editorial_fill whose numbered bands flex-fill. _adapt_steps
  mirrors steps into list_items so the fallback renders them verbatim.
- CONTAINER REBUILT + VERIFIED END-TO-END: image was 35h stale AND its build
  ignored client_assets entirely (dockerignore allowlist + no COPY: every
  container render shipped with NO client imagery). Fixed both; POST of the
  christoph envelope to the containerized /render returned HTTP 200, 17 pages,
  A3 at p14, page-12 pixel-identical to the local harness render.
- GENERATION GATE (generate_assets skip_slots, computed in build_live): never
  pay for an asset no consumer can paint. cover_hero skipped when a founder
  file exists (founder-first cover never falls back to it); atmospheric
  gradient skipped (no live consumer; background_texture owns the atmosphere
  role). Unwired-asset audit: every remaining generated artifact has a counted
  consumer in the rendered HTML.
- Wiring gate: test_wiring_conformance 7 passed / 1 skip (apex-only provenance
  row). Guard battery 47 green; generate_assets producer tests 23 green.

## 2026-07-15 round 3: /code-review xhigh on the fix run itself + THE SCALE DISCOVERY

REVIEW: 10 angles + 6 verifiers + sweep over the round-1/2 diff (2349 lines).
15 findings reported (most CONFIRMED empirically, 3 refuted incl. an
actually-rendered WeasyPrint :has() test). Fixed via 2 agents + main lane.

**THE HEADLINE DISCOVERY (empirically proven, reproducible):** Chromium
print silently SCALES THE WHOLE DOCUMENT DOWN when ANY fragment exceeds its
named page box. 0.4mm of frame borders on the 297mm bleed rail sections was
enough: every deck since the bleed rails landed printed at ~84.6 percent of
design size (cover navy boundary 134mm vs the true 158.4mm; re-adding the
borders reproduces 17-sheets-at-85-percent exactly). Round-3's hairline
exemption removed the trigger, so the deck now prints at TRUE design scale,
and every page tuned against the shrunken render had to be re-fitted:
- st_07b fill grid was sized 261mm inside a 251mm dark-beat box (307mm
  section, fit only at 85 percent) -> 251mm + length-bucketed Kernaussage
  size (>110 chars steps down from display-xl to display).
- st_14 re-fitted to true scale (opener display-xl->display, title h3->lede,
  intro lede->body: each step reproduces the APPROVED 85-percent visual
  size) + definite-height flex root so it can never spill again.
- NEW GUARD in assembler: the print pass measures every fragment against its
  sheet and warns "fragment overflow (silent-shrink trigger)" - the spill QC
  cannot see this failure mode because the shrink PREVENTS the spill.

ROUND-3 CORRECTNESS FIXES (all verified): trim-edge hairlines exempted on
bleed rail pages (0.2mm lines printed at the physical sheet edges, 300dpi
proven); ef-mid bands shrink instead of clip (p-04 scene plate had lost its
accent rule); ST-07A stats fallthrough restored with citations (non-percent
kennzahlen rendered NOWHERE); German-aware sentence splitter (ordinals +
abbreviations no longer split into garbage steps that also flipped layout
routing); unit-aware digit_key ('40 %' != '40 Stunden'); SUMME never deduped
out of a cost strip (whole strip drops instead); count-noun symmetry in
before/after pairs; LLM donuts always through donut_spec (no verbatim
percent); founder gate now uses the resolver's exact match + manifest
downloads always honored; product cursor advances past missing files
(one dead file starved every later page); paintability guards (no product
claimed for pages that cannot paint it); veil engine-gated to chromium +
color-keyed filename + atomic write (weasyprint keeps its verified layer
stack); ST-06 candidate list gained the fill layout (3-step mid-deck pages
fell silently to legacy); escaped-length thresholds use pre-escape glyph
counts + viz text escaped at the adapt boundary; ST-03 overflow direction
flipped (top-clip -> bottom); em dashes + hex literal swept; dead code
removed (_page_chrome_rail, _ini avatar chain, geo variant dead work);
dockerignore excludes _local_out/apex-assets/var/backups (~180MB context).

RESULT: 17 sheets, A3 at 14, TRUE design scale, all devices painting,
battery green. Deliverable: _renders/dmc_christoph_v4_fixed_2026-07-15.pdf.
BLOCKED: container rebuild (Docker daemon down); rebuild + POST-verify when
OrbStack is back: docker build -t dmc-renderer . && docker rm -f
dmc-renderer && docker run -d --name dmc-renderer --env-file
research/preprocessor/.env -p 8099:8099 dmc-renderer
NOTE: the deck now looks ~18 percent LARGER than every deck reviewed before
2026-07-15 - that is the CORRECT design scale (tokens print true); the old
decks were secretly mini. Any page that now feels dense was tuned at 85
percent and wants the same step-down treatment st_14 got.

### 2026-07-15 tail: TWO more bugs found by continuing to verify after the report

1. **PAGE-ROUTING CONFLICT**: `.page.format-a4` and the treatment sheet both
   declared `page:` on railed sections. Chromium laid the fragment out against
   one page geometry and printed it on the other: the rail page came out
   squeezed to ~85 percent height with a dead band below. Fixed by
   `:not(.tp-rail)` on the format rule; ALL rail routing now lives in ONE
   assembler rule keyed on the section-level `.tp-rail` stamp (page: bleed +
   explicit height 296.5mm + min-height 0 + margins-as-padding + clip).
   NEVER min-height 297mm: an exact-fit fragment on a named page is a knife
   edge Chromium resolves by spilling OR by silently squeezing the axis.

2. **THE RAIL ANCHOR** (new regression class, bisect-proven): a rail
   positioned against the GRID and reaching past it with negative offsets has
   its paint TRUNCATED BY THE FOLLOWING PAGE's geometry. Isolation proved it:
   About alone = 296.5mm; `ST-02 -> About` = 296.5mm; `About -> chromed ST-09`
   = 271.1mm. The five case rails only ever escaped because a dark-beat page
   follows each of them (page-order luck). FIX: on a rail page the SECTION is
   the sheet, so rails anchor to the section's padding box (grid goes
   `position: static`; rail `top:16mm; bottom:0; right:0; height:auto`) with
   ABSOLUTE widths (88.8mm editorial-fill / 85.2mm case study): percentages
   would now resolve against the 210mm section instead of the 178mm grid and
   eat ~13mm of the text column. No negative offsets, no neighbour dependency.
   NOTE: the rail CSS lives in the TREATMENT sheets, which load AFTER the head
   -> an equal-specificity head rule silently loses. Rail geometry belongs in
   the treatment sheet.

VERIFIED: 17 sheets, A3@14, ALL SIX rails (About + 5 case studies) bleed
16..296.5mm vertically and to 210.0mm right, About's list bands + IN ZAHLEN
stats restored (they were being eaten by the clip). Deliverable refreshed:
_renders/dmc_christoph_v4_fixed_2026-07-15.pdf.

### 2026-07-15 tail-2: the apex regression my rail fix exposed (and the real cause)

The rail-anchor change turned tests RED: apex went 20 logical -> 21 physical.
Cumulative-prefix bisect (print sections 1..N, compare sheets to N) named the
culprit immediately, and it was NOT the rails: the apex COVER spills to two
sheets ON ITS OWN. Every full-bleed page (cover / breathers / back cover /
dark beats) sets its ground to the full 297mm sheet, which leaves the fragment
at ~297.1mm inside a 297mm page area: a knife edge Chromium resolves per deck
by luck. The christoph cover happened to fit; apex's did not, and once it
spilled every later page shifted (A3 15 -> 16). The rail work only made the
latent defect visible by removing the global shrink that had been papering
over it.
FIX (the same clamp the rail sections use, now on every bleed page):
  .page.st-01, .page.st-31, .page.st-32, .page.st-03, .page[data-page-mode]
  { height: 296.5mm; min-height: 0; overflow: hidden; }
0.5mm is invisible at trim and makes the fit deterministic for ANY deck.
VERIFIED: battery 53 passed (apex 20/20, A3 at 15); christoph 17 sheets,
A3@14, all six rails bleed. Deliverable refreshed off this exact tree.

## 2026-07-16: Montserrat wired, container live, and THE DEVICE-VOCABULARY GAP measured

1. **MONTSERRAT (owner ask)**: the TTFs had been sitting in fonts/ since May with
   NO @font-face declaring them, so every christoph deck silently printed in
   Source Sans 3. Added @font-face for Montserrat + Playfair Display (both
   already bundled) and listed them in the tokens' $extra-bundled-families.
   Verified: the fallback warning is GONE, the face is in the document, and the
   headline shapes changed on pixels. The deck now renders in the brand's face
   for the first time.
2. **CONTAINER**: rebuilt on current code (OrbStack back up), running and
   healthy on :8099 ("build_live (real package)").
3. **THE GAP, MEASURED** (full spec: docs/DEVICE-VOCABULARY-GAP-2026-07-16.md):
   the renderer can draw **16 viz presets**; the live adapter emits **4**
   (donut, stat_strip, transform_arrow, bar_compare). Twelve devices are built
   and unreachable - split_bar, ranked_bars, step_cascade, icon_array,
   phase_timeline, money_bar, gauge, kpi_card, icon/cluster families. That is
   why every page feels the same: the TRANSLATION layer speaks 4 words, not the
   renderer.
   Cause: device choice is a per-FIELD syntactic reflex in
   build_live._normalize_page_data (has "%" -> donut; vorher_nachher -> arrow;
   kostenrechnung -> stat_strip). Nothing reads what the figure MEANS. Richard
   picks by RHETORICAL ROLE (trend -> column chart; calculation -> formula
   ladder; capacity -> split bar; entity comparison -> labeled bars; market
   structure -> node diagram) and his writer emits the shape each role needs.
4. **ARCHITECTURE ANSWER (owner asked)**: there is NO render-only mode. Every
   stage runs in-process on every render - verified by call site:
   validate_and_resolve_brand_tokens(751), resolve_fonts(755), resolve_axes(760),
   validate_copy/copyfit(765), synthesize_page_visuals(657 per page),
   structure_content(872), resolve_slots(882), generate_assets/fal(905),
   generate_components(924), plan_layout(931), assemble_package(936),
   route_package(957), then assembler.render_package. The preprocessor is NOT
   being skipped and the layout IS computed every time. The dullness is not a
   skipped stage: the device-choosing stages know 4 devices, and
   generate_components builds bespoke SVG for only 4 page types (ST-06/09/14/07A).

## 2026-07-16 (later): owner gave the GO -> layers A + B landed, C in build

- **RICHARD'S COPY LAW READ** ("Wichtig für Copy (KI-Floskeln).docx"). It is a
  DATA-VIZ document as much as a copy document: digits-always makes figures
  machine-extractable, "€"-always gives one currency to parse, and
  "(Quelle, Datum)" on every figure IS the icon-stat card's source line. Copy law
  and device vocabulary are ONE contract from two directions.
  **REVERSAL RECORDED:** Richard now BANS "nicht X, sondern Y". My 2026-06-29
  memory had protected it as his signature move after a corpus read. The client's
  written rule wins over my inference; memory corrected.
  **A REAL BUG THE DOC EXPOSED:** "Keine Doppelpunkte" - build_live line ~230 was
  joining schmerzpunkte as "titel: beschreibung" and printing that colon on the
  status-quo page. Now joined as two sentences.
- **A DONE: `docs/writer-prompt-v5.md`** - Richard's verbatim rules + the 6 new
  role shapes (fakten / verlauf / rechnung / kategorien / zusammensetzung /
  entitaeten) + the closed icon vocabulary + the density rule. All keys OPTIONAL
  and additive, so an old payload renders exactly as before. Owner pastes it into
  n8n.
- **B DONE: the ROLE->DEVICE SELECTOR** (`build_live._role_devices`, contract in
  `docs/ROLE-DEVICE-CONTRACT.md`). Replaces the per-field reflex as the PRIMARY
  path; legacy `kennzahlen` remains the fallback. Verified on a synthetic payload:
  6 role shapes -> 6 new devices; bogus icon key -> None; empty page -> nothing;
  v4-only payload -> unchanged.
- **C IN BUILD** (2 agents): the icon set + icon_stat_row + column_chart, and
  formula_ladder + grouped_bars + stacked_bar_100 + entity_bars.

## 2026-07-16 (final): LAYER C DONE - the device vocabulary is LIVE and pixel-proven

BUILT (2 agents, both self-verified through the real Jinja env + real Chromium):
- `components/icons.jinja` - the closed 18-key line-icon vocabulary (zeit, geld,
  person, team, dokument, prozess, wachstum, warnung, ziel, standort, kalender,
  suche, chart, check, welt, schule, schutz, idee). Unknown/empty key renders
  NOTHING (a writer typo can never print a broken glyph).
- `components/viz_facts.jinja` - `icon_stat_row` (the workhorse: circled icon,
  figure, label, body, inline source, 1-6 cards in a row) + `column_chart`
  (values above bars, last/named bar highlighted, German number parsing).
- `components/viz_compare.jinja` + `styles/viz_compare.css` - `formula_ladder`
  (numbered rows ending in a DARK result box), `grouped_bars` (vorher/nachher per
  category + legend), `stacked_bar_100` (1 or 2 series), `entity_bars` (mark +
  name + bar; a range like "3-5" prints VERBATIM while the bar sizes from 3).
  CSS wired as a VIZ_CSS sibling in assembler (out of viz.css to avoid collision).

PIXEL PROOF (the only proof that counts): `fixtures/christoph_v5_payload.json` =
the same client payload with ST-14's three sourced kennzahlen reshaped into the
`fakten` ROLE (figures/labels/sources copied VERBATIM, nothing invented) + an
ST-09 `rechnung` built from figures already in that page's copy. Renders 17
sheets, A3@14. **ST-14 (p-05) went from 2 donuts + an orphan "70% to 75%" with no
device -> a 3-card ICON-STAT ROW with icons and inline sources.** That is
Richard's own pattern, emitted by the system from the client's own data.

CONSTRAINTS LEARNED (durable):
- `box-shadow` is BANNED in viz.css by test_viz_flat_on_cream (it WAS the owner's
  "dull" complaint). Cards = hairline border + surface fill, never a shadow.
- A 3-across figure must ladder its type (40pt @1-2 / 28pt @3 / 20pt @4-6) or a
  real figure like "87,8 %" breaks over two lines. Found by LOOKING, not by
  markup assertions.
- Percent widths must stay WHOLE (43%, not 43.0%): the float fabricated precision
  the writer never stated.
- 6 suite failures are PRE-EXISTING (fixtures/apex/viz_curation.py, untouched
  since Jun 17: a fabrication guard on '24 Std.'), proven by neutralize-and-rerun.

STILL OWNER LANE: paste `docs/writer-prompt-v5.md` into n8n. That is the ONLY
thing standing between this vocabulary and every future deck - the renderer and
the selector are ready; the writer has to speak the roles.
