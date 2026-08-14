# Baseline Ledger — 2026-08-14 (visual-review retry loop)

> Supersedes the 2026-08-13 ledger for the NEW work in this session. The
> 2026-08-13 counts remain the record for the consolidated gap-closure program;
> this file records the visual-review retry loop (G25) that landed 2026-08-14.

## Verified counts (2026-08-14, after US-101..US-109)

| Suite | Command | Result |
|---|---|---|
| Preprocessor | `cd research/preprocessor && .venv/bin/python -m pytest tests -q` | **736 passed / 0 failed** |
| Quality_loop (new) | `cd research/quality_loop && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib ../v7-renderer/.venv/bin/python -m pytest tests/test_visual_review_loop_v3.py tests/test_ship_gate_v3.py tests/test_assess_closed_gaps.py -q` | **19 passed / 0 failed** |
| dmc-renderer | `cd dmc-renderer && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib ../research/v7-renderer/.venv/bin/python -m pytest tests/ -q` | **131 passed / 0 failed / 4 xfailed** |
| Assessment harness | `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib research/v7-renderer/.venv/bin/python research/quality_loop/assess_closed_gaps.py --fast` | **36/38 closed, exit 0** (G19+G24 human-gated) |

## What changed (US-101..US-109, 2026-08-14)

1. **`ReleaseState.REVIEW_REQUIRED`** — a distinct, non-shippable state. A deck
   whose visual review cannot pass after all retries lands here; NO delivery
   PDF is ever emitted.
2. **`ReviewAttemptRecord`** — immutable per-attempt record (contract/render
   hashes, page scores, conductor summary, verdict).
3. **`ShipGateV3` transitions** — REVIEW_REQUIRED is human-gated: it can move
   to REVIEW_CANDIDATE/REJECTED/DRAFT but never directly to SHIP_READY.
4. **`visual_review_loop_v3`** — `retry_transient` (3× exponential backoff for
   transient reviewer failures), `review_page` (build→score→conductor repair→
   rebuild, 3 attempts), `run_visual_review_loop` (per-page attempts + one
   whole-deck re-review of failed pages → review_candidate | review_required).
5. **`build_and_render_v3`** — runs the loop at the REVIEW_CANDIDATE branch;
   review_required downgrades the gate state and suppresses delivery.
6. **`/render-v3`** — returns HTTP 202 application/json for review_required
   (release_state, failures, attempt_records, hashes, artifact_manifest), no
   PDF body.
7. **Artifact retention** — `review_required` class retains the ledger, HTML,
   raw PDF, and attempt records; never a delivery PDF.
8. **Harness fix** — `_run_pytest`/`_run_suite_zero` now cd to the nearest
   conftest.py ancestor so suites' sys.path assumptions match manual runs.

## Standing rules

- **Never ship an ungraded deck.** A visual review that cannot run (after 3
  transient retries) or cannot pass (after 3 page attempts + 1 whole-deck pass)
  returns REVIEW_REQUIRED with no PDF.
- **Never block without a retry path.** Blocking alone is a defect; the retry
  ladder is the recovery path, and exhaustion is honest (`unreviewable` /
  `rejected`), never a silent pass.
- The harness (`assess_closed_gaps.py --fast`) is the standing entry point;
  run it before any future work.

## Open (human-gated, unchanged)

- G19: design_brief live wiring (fal prompts default style).
- G24: real client photographs.

## Director Organism program (US-201..US-210, 2026-08-14)

**Nervous system (auto-fix wiring) — the reflex arc is now LIVE:**
- US-201: the visual loop accepts a conductor, scores the FRESH render each
  attempt (`build["page_pngs"][row]`), rebuilds with conductor overrides, and
  records rebuild evidence. 11 tests.
- US-202: `build_and_render_v3` REVIEW_CANDIDATE branch now rebuilds via a
  recursive call (recursion guard `_skip_visual_review`), with a conductor
  adapter: DET failures + VIS rationale → `_rationale_to_defects` (deterministic
  keyword map: empty/hollow/leer → dead_space_region; clip/overflow →
  element_clipped) → conductor_v3.propose → apply/apply_type → plan+facts
  overrides. Seam test proves a VIS rejection triggers a rebuild WITH the
  override and the fresh render passes. 135 dmc tests.
- US-203: taste wiring — per-face reference retrieval (`legacy_st_type` →
  `retrieve_references` → Richard's same-type pages), keyed by row id, graceful
  miss. The VIS reviewer now compares against real anchors.
- G26 added: "visual review auto-fix (reflex arc)" — assessed by the seam test.

**Body (deck repair) — 20 logical = 20 physical, verified:**
- US-204: `casestudy_hero` (A3 spread) made reproducible: plan_layout accepts
  the variant + stamps `page_format="a3"`, assemble_package writes it,
  build_package hints the 5 apex case studies. Re-bake reproduces the spread.
  Mixed A3/A4 printing verified working (A4s full-size, no compression).
- US-205: A3 sheets fill: definite `.csh` height + narrative flex-distribution
  (BL ink 0.2% → 7-17% on the 5 spreads); definite portrait height makes the
  box engine-independent (a 1:1 crop no longer overflows WeasyPrint's measure).
- US-206: live entry fixed — bare meta derives `client_slug` (slugified
  company_name_short) + `report_id` (record_id) in adapter_v3 AND build_live v2.
- US-207: "30-50%" verified clean on pixels (right column 7.6% ink, uniform
  profile, no clip).
- US-208: ST-22 collaboration page typography step-up (pullquote-size step
  titles + lede-size bodies; quadrant ink 7.5-16.7% → 10.5-20.1%).

**Verified counts (2026-08-14, post-201..208):** preprocessor 738/0,
renderer 398/0, dmc 138/0 (+4 xfail), guards 13/0, harness 37/39 exit 0.
