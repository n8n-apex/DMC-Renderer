# Director Organism — Auto-Fix Wiring + Deck Repair (US-201..US-210)

> 2026-08-14. Builds the organism the user described (taste, instincts, observation,
> implementation, thinking, judgment, determinism) by CONNECTING machinery that
> already exists but was never wired. Then repairs the deck's body (A3 case
> studies, spill, live entry, sparse pages). Final render is the LAST step.

## The organism (what "human" means here)

| Faculty | Subsystem | State |
|---|---|---|
| Eyes (deterministic) | DET gates (`perception.py`) | built, wired |
| Eyes (taste) | VIS review vs Richard's pages (`vis_client.py` + references/) | built, **refs NOT wired** (returns []) |
| Brain | `conductor_v3.propose` (defect codes → variant/type-scale fixes) | built, **orphaned** (`converge_v3` has zero callers) |
| Hands | `apply`/`apply_type` → `composition_plan_override` + `facts_override` | built, consumed by `build_and_render_v3`, **never produced in production** |
| Reflex arc | `run_visual_review_loop` | built, **scored the same render 3×; no conductor; no rebuild** |

**The one-line gap:** the loop's `build_fn` is a lambda returning precomputed
failures; `conductor` is never passed; references are empty. This program
connects them into: build → observe → judge → propose → rebuild → re-observe.

**Determinism:** same envelope → same fix sequence → same build. No randomness.
VIS rejection is the GATEKEEPER (taste); DET failures + a deterministic
rationale→defect keyword map are the DIAGNOSIS; conductor_v3 is the PRESCRIPTION.

## Part 1 — Nervous system (auto-fix wiring)

### US-201 — loop accepts conductor + scores FRESH renders
`review_page`/`run_visual_review_loop` in `research/quality_loop/visual_review_loop_v3.py`:
- `build_fn` contract changes to `build_fn(plan_override=None, facts_override=None) -> dict`
  with `page_pngs: {row_id: path}`, `failures: list[str]`, `composition_plan`,
  `registry`, `facts_by_face`, `contract_sha256`.
- Each attempt scores `build["page_pngs"][page_key]` (the FRESH render), not a
  static path.
- `review_page` gains the repair step: on fail, `conductor(build)` → if
  `{"changed": True, "plan_override", "facts_override"}` → `build_fn(overrides)`
  → re-score. Stalled (no change) breaks early.
- `run_visual_review_loop` accepts + forwards `conductor`.
- Fake builders in tests simulate real rebuilds (page PNG content changes when
  given overrides).

### US-202 — real build_fn + conductor adapter in build_v3
`dmc-renderer/build_v3.py` REVIEW_CANDIDATE branch:
- `build_fn(plan, facts)` calls `build_and_render_v3(envelope, ...,
  composition_plan_override=plan, facts_override=facts)` recursively with a
  `_skip_visual_review=True` recursion guard (inner builds never re-enter the loop).
- Maps inner result → loop contract (page_pngs by row_id, failures, plan,
  registry, facts).
- Conductor adapter: DET failures for the face + `_rationale_to_defects(rationale)`
  (deterministic keyword map: empty/hollow/leer/whitespace → `dead_space_region`;
  clip/overflow/cut/abgeschnitten → `element_clipped`; etc.) → `propose(...)`
  → `apply`/`apply_type` → overrides.
- Loop result records actual rebuilds; `visual_review_loop` key in the result
  carries rebuild evidence.

### US-203 — reference retrieval wired (taste)
`_reference_pngs_for` in build_v3: resolve each face's st_type from the report
plan → `quality_loop.references` retrieval (same-st_type pages, k=2) → PNG paths.
Best-effort: failure → `[]` (VIS then scores alone, honest).

## Part 2 — Body (deck repair)

### US-204 — case-study A3 routing made reproducible
- `plan_layout.py`: accept `casestudy_hero` in `_VALID_LAYOUT_VARIANTS` (explicit
  hint only); when resolved variant is `casestudy_hero`, emit
  `page_format="a3"` on the planned page.
- `assemble_package.py` writes `page_format` when set.
- `build_package.py` (apex): hint the 5 case-study pages to `casestudy_hero` so
  a re-bake reproduces the A3 spread (currently hand-edited into the JSON).
- **VERIFIED experimentally:** legacy path honors `page_format` → `format-a3`
  → A3 landscape; 20 pages, A4s full size, mixed-size printing works in current
  Chromium path.

### US-205 — A3 sheet fill (kill hollow bottom)
`styles/st_07a.css`: `.page.format-a3 .st-07a .csh { height: 261mm }` (definite
height — the WeasyPrint/Chromium lesson: percentage height collapses under
`min-height: 0`). Right dashboard + quote anchor to the sheet bottom
(`justify-content: space-between` already in `.csh-right`). Verify quadrant ink
BL/BR rises on the 5 A3 pages.

### US-206 — live-pipeline entry (client_slug/report_id)
`dmc-renderer/adapter_v3.py` `adapt_envelope_v3`: derive missing meta —
`client_slug` from `brand_tokens.company_name_short` (slugified), `report_id`
from `envelope.record_id` (precedence already established). Same derivation in
`build_live.py` v2 path (`envelope_to_render_request`). Tests: envelope with
bare meta now renders (stubbed pipeline), no literals.

### US-207 — ST-06 "30-50%" verification
Scoped override already exists (`st_06.css` 40pt + nowrap). Verify on pixels
(quadrant + edge-ink measurement). Fix only if measured clipped.

### US-208 — sparse ST-22 collaboration page (p19, 16.7/9.3/13.5/7.5)
Under-filled `fill` variant. Distribute: larger step titles, fuller timeline
cells, accent numerals — scoped to `st_22.css`. Verify quadrant ink.

## Part 3 — Ship

### US-209 — full verification
All suites (preprocessor, quality_loop targeted, dmc-renderer, harness exit 0);
G26 added to `closed_gaps_registry.json` (auto-fix loop live); ledger updated.

### US-210 — FINAL RENDER (last step, user judges taste)
Re-bake fixture via `build_package.py`, render via `render.py` (chromium),
verify 20 logical = 20 physical, page formats, quadrant metrics, dead-space
checks. Then hand the deck to the user.

## Hard rules
- Brand-agnostic: no client name/hex/font literal in logic (guard tests run).
- Never fabricate: no new data; fixes are layout/variant/scale only.
- Deterministic: no randomness; same envelope → same deck.
- Verify on pixels (quantitative — quadrant ink, page counts, dead-space) at
  every step; the user judges taste on the final render.
