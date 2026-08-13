# Baseline Ledger — 2026-08-13

> **THIS FILE IS THE AUTHORITATIVE TEST-STATE RECORD.** Every prior count claim
> in this repo is stale: CODEX-HANDOFF.md's "15 failed / 342 passed",
> phase-zero's "15 failed / 352 passed", and V3-MIGRATION-READINESS-v2's
> "all green" were each true on their run date and are now superseded by the
> numbers below. Do not inherit a count from any older file; re-run these
> commands.

## Verified counts (2026-08-13, after US-001..US-003)

| Suite | Command | Result |
|---|---|---|
| Renderer | `cd research/v7-renderer && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python -m pytest tests/ -q` | **398 passed / 0 failed** / 1 skipped / 5 xfailed |
| Preprocessor | `cd research/preprocessor && .venv/bin/python -m pytest tests -q` | **731 passed / 0 failed** |
| dmc-renderer | `cd dmc-renderer && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib ../research/v7-renderer/.venv/bin/python -m pytest tests/ -q` | **103 passed / 0 failed / 4 xfailed** |
| Guard battery | `cd research/v7-renderer && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python -m pytest tests/test_components.py tests/test_tokens.py tests/test_design_conformance.py tests/test_no_literals_in_architecture.py -q` | **45 passed / 0 failed** |
| Offline contract-fix harness | `cd dmc-renderer && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib ../research/v7-renderer/.venv/bin/python verify_contract_fixes.py` | **10/10 passed** |

## What changed to reach this state (2026-08-13)

1. **US-001 — registry version drift (28 NEW renderer failures).** The
   composition registry is 1.7.0 with family versions 1.3.0-1.6.0; four v3
   renderer test files hardcoded 1.1.0 → `ContractLoadFailure`. Fixed by
   updating to real versions + dynamic per-family lookup in the parameterized
   tests. **Also fixed a REAL loader bug** this exposed: the fallback-family
   lookup used the primary fragment's version (theory_interpretation@1.4.0 but
   it is 1.5.0) in both `contract_loader_v3.py` and `render_v3.py`; both now
   resolve the fallback by family id across registered versions. Formula-ladder
   test reasserted to the real SVG contract (it is an `_SVG_PREFERRED_KIND`).
2. **US-002 — fixture drift (the documented 15 renderer failures).** apex
   case studies became GoldmanTax + `cs_*.png` portraits; tests asserted the
   old Martina Ammon / `1_founder.png` / `cs-chart-svg` / pre-2026-07-13 ground
   contract. Realigned to current reality; the two overflow tests now stamp
   `page_format='a3'` (the hero's real sheet) because the standalone WeasyPrint
   harness mis-measures A3 on an A4 box.
3. **US-003 — the 9 dmc-renderer failures.** (a) REAL fix: the
   `synthetic_placeholder_asset` gate over-applied to calibration builds —
   added `ReleaseContextV3.allow_synthetic_assets` (production default False).
   (b) REAL fix: christoph-known-failures is INTENTIONALLY a 17-face
   misallocation (manifest: rejected + face_count_mismatch); the face-allocation
   test now skips manifest-declared misallocated fixtures. (c) DETERMINED: the
   remaining 7 failures are the documented 2026-08-08 pixel-policy recalibration
   to Richard's corpus — synthetic fixtures carry no real photos (gap G24), so
   they are correctly rejected on the density blockers. Gates are correct;
   manifest + tests updated to expect `rejected`; 4 ship-machinery tests xfailed
   with a dated reason (they need a photo-bearing candidate).

## Standing rules

- **Never weaken a gate to make a test pass.** When a gate is correct
  (corpus-derived, validated against Richard's 84 faces) and a fixture
  genuinely fails it, the fixture/manifest expectation is the stale side —
  record the honest state, don't relax the gate.
- **`allow_synthetic_assets=True` is calibration-only.** It is how the frozen
  synthetic asset bank exercises the pipeline deterministically. A calibration
  build still stops at `rejected`/`review_candidate` and can never reach
  `ship_ready` without real review evidence. Production keeps the default False.
- The collaboration face (face.18) is a known below-band outlier: its A3
  pathway process renders via the SVG component bridge, whose text PyMuPDF's
  `get_text("words")` does not count. Pinned below band with an exemption;
  remove it if real photos / a countable layout ever put it in band.
- The Aug-11 family-CSS typography rework (stat numerals 40pt/34pt → 26pt)
  measurably lowered ink while staying inside the corpus bands. Per-family
  anti-regression ink floors were re-pinned 2026-08-13 to the current levels
  with the dated reason. The corpus band (min 0.1029) is the authority.

## How to use this file

Every future session STARTS by re-running the five commands above (or the
standing assessment harness from Phase 6 / US-020 once built) and recording the
new tails. A count that differs from this ledger is either progress (record it)
or a regression (investigate before any other work).
