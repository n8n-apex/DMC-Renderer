# Quality Gate and Postprocessor Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Evaluate the exact artifact against evidence, geometry, reference quality, and export contracts, then produce separate searchable digital and validated print PDFs.

**Architecture:** Replace advisory warnings with typed release states and owner-addressed failures. Deterministic checks run first, calibrated visual review runs only on structurally valid candidates, and export happens only from a ship-ready raw PDF.

**Tech Stack:** Python 3.11, Pydantic v2, PyMuPDF, pikepdf, Pillow, Playwright, Ghostscript, pytest

---

This plan depends on both `2026-08-03-contract-and-editorial-planner.md` and `2026-08-03-composition-and-renderer.md`.

## Task 1: Define release states and typed failures

**Files:**

- Create: `research/preprocessor/contracts_v3/release.py`
- Create: `research/quality_loop/ship_gate_v3.py`
- Test: `research/quality_loop/tests/test_ship_gate_v3.py`

- [ ] Write failing tests for `rejected`, `draft`, `review_candidate`, and `ship_ready` transitions.

```python
def test_hard_failure_can_never_be_ship_ready() -> None:
    result = ShipGateV3.evaluate(bundle_with(
        failures=[failure("missing_required_asset", severity="hard")]
    ))
    assert result.state == ReleaseState.REJECTED

def test_known_placeholder_is_draft_not_success() -> None:
    result = ShipGateV3.evaluate(bundle_with(
        failures=[failure("approved_placeholder", severity="draft")]
    ))
    assert result.state == ReleaseState.DRAFT
```

- [ ] Implement `ReleaseState`, `FailureSeverity`, `FailureOwner`, `QualityFailure`, `GateResult`, and legal state transitions.
- [ ] Require every failure to name an owner stage, code, affected face IDs, affected element IDs when known, and remediation class.
- [ ] Reject unknown failure codes in ship mode.
- [ ] Run `research/preprocessor/.venv/bin/pytest -q research/quality_loop/tests/test_ship_gate_v3.py`.

## Task 2: Add exact structural and evidence gates

**Files:**

- Create: `research/quality_loop/gates/structure_v3.py`
- Create: `research/quality_loop/gates/evidence_v3.py`
- Create: `research/quality_loop/gates/assets_v3.py`
- Test: `research/quality_loop/tests/test_deterministic_gates_v3.py`

- [ ] Write tests for wrong face count, wrong fragment count, wrong PDF-object count, malformed A3 allocation, wrong case count, missing stable role, ungrounded claim, missing source appendix, missing required asset, and illegal asset substitution.
- [ ] Compare the frozen plan, materialization ledger, PDF page sizes, source ledger, and asset ledger. Never infer physical faces from PDF object count alone.
- [ ] Convert each A4 PDF object to one face and each A3 landscape object to two faces. Reject unsupported page sizes.
- [ ] Verify every shipped number and quote through claim IDs, not text search.
- [ ] Make five missing Christopher portraits blocking `assets` failures.
- [ ] Make the ungrounded Christopher `83%` a blocking `evidence` failure.
- [ ] Run `research/preprocessor/.venv/bin/pytest -q research/quality_loop/tests/test_deterministic_gates_v3.py`.

## Task 3: Add materialization and pixel gates

**Files:**

- Create: `research/quality_loop/gates/materialization_v3.py`
- Create: `research/quality_loop/gates/pixels_v3.py`
- Test: `research/quality_loop/tests/test_materialization_gates_v3.py`

- [ ] Write tests using purpose-built bad HTML fixtures for clipping, overlap, hidden text, text below minimum size, low contrast, missing element ID, and content outside safe bounds.
- [ ] Use the materialization ledger for element-level checks and raster analysis for final-image checks.
- [ ] Replace the accent-budget stub with measurable limits from the selected composition family. A family may opt out only through an explicit policy field.
- [ ] Treat any planned required element without a visible final box as a hard failure.
- [ ] Treat overlaps as hard only when both elements disallow overlap. Permit documented layers such as text over a veiled image.
- [ ] Run `research/preprocessor/.venv/bin/pytest -q research/quality_loop/tests/test_materialization_gates_v3.py`.

## Task 4: Rebuild reference-grounded visual scoring for Chromium v3

**Files:**

- Create: `research/quality_loop/reference_rubric_v3.py`
- Create: `research/quality_loop/calibration/build_dataset.py`
- Create: `research/quality_loop/calibration/ratings.schema.json`
- Create: `research/quality_loop/calibration/ratings.jsonl`
- Test: `research/quality_loop/tests/test_reference_rubric_v3.py`

- [ ] Define family-specific rubric dimensions: hierarchy, composition, typography, rhythm, density, proof visibility, mechanism clarity, and brand coherence.
- [ ] Link each rubric row to atlas face IDs and observable facts. Remove rubric rows whose inputs cannot be measured or reviewed.
- [ ] Build a calibration dataset containing all 120 reference faces, selected current-system failures, and later v3 candidates.
- [ ] Keep deterministic and visual scores separate. Visual scoring cannot override a hard failure.
- [ ] Support blind human ratings with rater ID, timestamp, family ID, dimension scores, acceptance, and comments.
- [ ] Do not set a ship threshold until at least two raters have scored the reference and candidate calibration set. Store the threshold in a versioned policy file after analysis.
- [ ] Run `research/preprocessor/.venv/bin/pytest -q research/quality_loop/tests/test_reference_rubric_v3.py`.

## Task 5: Preserve the digital PDF

**Files:**

- Create: `research/postprocessor/__init__.py`
- Create: `research/postprocessor/export_digital.py`
- Create: `research/postprocessor/models.py`
- Test: `research/postprocessor/tests/test_export_digital.py`

- [ ] Write tests that digital export preserves extractable text, links, page sizes, metadata, and embedded font references from the raw PDF.
- [ ] Implement `export_digital(raw_pdf, profile, output_path) -> ExportReport` using non-destructive metadata and optimization operations only.
- [ ] Reject any digital result whose extracted normalized text is less than 99 percent of the raw artifact's text.
- [ ] Reject lost links and unsupported page-size changes.
- [ ] Store checksums and the full export report beside the PDF.
- [ ] Run `research/preprocessor/.venv/bin/pytest -q research/postprocessor/tests/test_export_digital.py`.

## Task 6: Define explicit print profiles and preflight

**Files:**

- Create: `research/postprocessor/profiles/schema.py`
- Create: `research/postprocessor/profiles/dmc_print_test.json`
- Create: `research/postprocessor/profiles/README.md`
- Create: `research/postprocessor/tests/fixtures/srgb.icc`
- Create: `THIRD_PARTY_NOTICES.md`
- Test: `research/postprocessor/tests/test_print_profile.py`

- [ ] Add an approved, redistributable ICC test fixture and record its exact source, license, and SHA-256 in `THIRD_PARTY_NOTICES.md`. Do not copy a system profile without license review.
- [ ] Define strict fields: profile ID, PDF standard, ICC path and hash, color space, bleed, crop marks, image DPI limits, total area coverage, font policy, transparency policy, and flattening policy.
- [ ] Make printer profile absence a blocking error. `dmc_print_test` is for automated tests only and must have `production_allowed: false`.
- [ ] Write a test that production export rejects the test profile.
- [ ] Run `research/preprocessor/.venv/bin/pytest -q research/postprocessor/tests/test_print_profile.py`.

## Task 7: Implement print export and preflight

**Files:**

- Create: `research/postprocessor/export_print.py`
- Create: `research/postprocessor/preflight.py`
- Test: `research/postprocessor/tests/test_export_print.py`

- [ ] Write tests for ICC mismatch, page size, bleed, font status, image DPI, output intent, searchable-text preservation policy, and Ghostscript failure.
- [ ] Build the Ghostscript invocation only from the validated print profile. Do not hardcode `/printer` or PDF 1.3.
- [ ] Run Ghostscript into a temporary file, validate the temporary output, then atomically rename it into place.
- [ ] Never return the raw PDF under the print filename after a conversion failure.
- [ ] Emit `print-preflight.json` with every check, tool version, profile hash, input hash, and output hash.
- [ ] Keep flattening opt-in by profile. If enabled, label the loss of search and accessibility in the report.
- [ ] Run `research/preprocessor/.venv/bin/pytest -q research/postprocessor/tests/test_export_print.py`.

## Task 8: Wire the gate and exporters to the v3 service

**Files:**

- Modify: `dmc-renderer/service.py`
- Modify: `dmc-renderer/build_v3.py`
- Test: `dmc-renderer/tests/test_v3_release_flow.py`

- [ ] Back up both files under `dmc-renderer/.phase-zero-backups/2026-08-03/` before editing.
- [ ] Run deterministic gates on the source ledger, asset ledger, plan, contract, materialization ledger, raw PDF, and raster pages.
- [ ] Return structured JSON for rejected and draft states. Do not attach a delivery PDF to a rejected result.
- [ ] Export digital and print PDFs only from `ship_ready`.
- [ ] Allow `review_candidate` to return watermarked review PNGs and a raw review PDF with explicit headers.
- [ ] Add headers `X-DMC-Release-State`, `X-DMC-Gate-Report-SHA256`, and `X-DMC-Contract-Version`.
- [ ] Remove inline Ghostscript use from the v3 path. Leave v2 unchanged until migration completes.
- [ ] Run `research/preprocessor/.venv/bin/pytest -q dmc-renderer/tests/test_v3_release_flow.py`.

## Task 9: Add adversarial end-to-end fixtures

**Files:**

- Create: `dmc-renderer/fixtures/v3/valid-20-face.json`
- Create: `dmc-renderer/fixtures/v3/wrong-face-count.json`
- Create: `dmc-renderer/fixtures/v3/five-cases.json`
- Create: `dmc-renderer/fixtures/v3/ungrounded-number.json`
- Create: `dmc-renderer/fixtures/v3/missing-portrait.json`
- Create: `dmc-renderer/fixtures/v3/overcapacity.json`
- Create: `dmc-renderer/tests/test_v3_adversarial_e2e.py`

- [ ] Assert that only `valid-20-face.json` reaches `review_candidate` or higher.
- [ ] Assert that every invalid fixture fails at the earliest owning stage with a stable error code.
- [ ] Assert that no invalid fixture produces a delivery PDF.
- [ ] Run `research/preprocessor/.venv/bin/pytest -q dmc-renderer/tests/test_v3_adversarial_e2e.py`.

## Completion gate

Run:

```bash
research/preprocessor/.venv/bin/pytest -q \
  research/quality_loop/tests/test_ship_gate_v3.py \
  research/quality_loop/tests/test_deterministic_gates_v3.py \
  research/quality_loop/tests/test_materialization_gates_v3.py \
  research/quality_loop/tests/test_reference_rubric_v3.py \
  research/postprocessor/tests \
  dmc-renderer/tests/test_v3_release_flow.py \
  dmc-renderer/tests/test_v3_adversarial_e2e.py
```

The plan is complete only when:

- The current Christopher input cannot receive a delivery PDF.
- A valid fixture produces a searchable digital PDF with at least 99 percent text preservation.
- Print output requires an explicit production-approved profile and passes its preflight.
- Missing required assets, ungrounded claims, wrong face counts, clipping, and silent fallback are hard failures.
- Gate reports refer to the exact artifact hashes that are returned to the caller.
