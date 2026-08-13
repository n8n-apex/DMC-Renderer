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
