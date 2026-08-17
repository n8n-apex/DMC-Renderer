# Composition Planner and Renderer Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Turn a valid editorial and asset bundle into a strict, capacity-feasible render contract, then render it without semantic inference or silent fallback.

**Architecture:** Extract versioned composition families from the 120-face atlas, select only from feasible families, freeze the result into discriminated element contracts, and add a separate v3 renderer that emits geometry evidence for every required element.

**Tech Stack:** Python 3.11, Pydantic v2, Jinja2, Chromium, Playwright, PyMuPDF, pytest

---

This plan depends on `2026-08-03-contract-and-editorial-planner.md`. Keep v2 operational until the v3 completion gate passes.

## Task 1: Build the versioned composition-family registry

**Files:**

- Create: `research/composition_registry/README.md`
- Create: `research/composition_registry/schema.py`
- Create: `research/composition_registry/registry.py`
- Create: `research/composition_registry/families/dmc-v1.json`
- Create: `research/composition_registry/golden/manifest.json`
- Test: `research/composition_registry/tests/test_registry.py`

- [ ] Write failing tests that every family has a semantic promise, supported roles, dominant mechanisms, region capacities, asset classes, typography bounds, known failures, and at least one atlas face reference.
- [ ] Write a test that rejects duplicate IDs and unversioned changes.
- [ ] Seed ten family records from the approved architecture: editorial lead, false-belief stack, case narrative, theory interpretation, mechanism spread, summary synthesis, objections, collaboration, evidence wall, and closing CTA.
- [ ] Use exact atlas face IDs from `research/reference-atlas/reference-atlas.json`. Do not describe a family as reference-grounded without a face reference.
- [ ] Store copy capacity as measured ranges by region and language, not a single page-wide character number.
- [ ] Run `research/preprocessor/.venv/bin/pytest -q research/composition_registry/tests/test_registry.py`.

## Task 2: Define the frozen render-contract element union

**Files:**

- Create: `research/preprocessor/contracts_v3/render_contract.py`
- Test: `research/preprocessor/tests/test_render_contract_v3.py`

- [ ] Write tests that reject unknown element types, inline asset paths, free-text numbers without claim IDs, missing required visibility, and a spread with one face ID.

```python
def test_stat_requires_claim_reference() -> None:
    with pytest.raises(ValidationError, match="claim_id"):
        StatElement(
            element_id="case.result",
            value="83%",
            label="Zeitersparnis",
            required_visibility=True,
        )

def test_unknown_elements_are_forbidden() -> None:
    with pytest.raises(ValidationError):
        RenderFragmentV3.model_validate({
            "fragment_id": "f1",
            "format": "a4",
            "face_ids": ["face.01"],
            "elements": [{"kind": "magic_widget", "text": "x"}],
        })
```

- [ ] Implement discriminated frozen models for heading, body, quote, stat, comparison, process, image, source, QR, divider, and group elements.
- [ ] Implement `CompositionAssignment`, `RegionAssignment`, `ExpectedMaterialization`, `RenderFragmentV3`, and `FrozenRenderContractV3` with `extra="forbid"` at every level.
- [ ] Require content, claim, and asset references instead of duplicating source values into arbitrary dictionaries.
- [ ] Run `research/preprocessor/.venv/bin/pytest -q research/preprocessor/tests/test_render_contract_v3.py`.

## Task 3: Implement region-level capacity estimation

**Files:**

- Create: `research/composition_registry/capacity.py`
- Create: `research/composition_registry/calibrate_capacity.py`
- Create: `research/composition_registry/fixtures/german_copy_samples.json`
- Test: `research/composition_registry/tests/test_capacity.py`

- [ ] Add failing tests for word count, wrapped line count, minimum font size, image aspect ratio, stat count, and list-item count.
- [ ] Implement a deterministic first-pass estimator using font metrics from the actual bundled fonts and family region geometry.
- [ ] Add a Playwright calibration command that renders boundary samples and writes measured line and bounding-box results back to a separate calibration report. It must not mutate production family JSON automatically.
- [ ] Add explicit statuses `fits`, `near_limit`, and `does_not_fit`.
- [ ] Prove the current alias-inflated Christopher page 4 is evaluated from canonical content refs only.
- [ ] Run `research/preprocessor/.venv/bin/pytest -q research/composition_registry/tests/test_capacity.py`.

## Task 4: Implement semantic family feasibility and selection

**Files:**

- Create: `research/preprocessor/stages/plan_compositions_v3.py`
- Create: `research/preprocessor/policies/composition_scoring_v1.json`
- Test: `research/preprocessor/tests/test_plan_compositions_v3.py`

- [ ] Write tests that eliminate a family when required proof is absent, an asset class is illegal, any required region does not fit, or the dominant mechanism is unsupported.
- [ ] Write tests that cadence changes ranking but never makes an infeasible family selectable.
- [ ] Implement feasibility before scoring.

```python
feasible = [
    family for family in registry.for_role(face.role)
    if supports_mechanism(family, face.dominant_mechanism)
    and evidence_fits(family, face, source_ledger)
    and assets_fit(family, face, asset_ledger)
    and capacity_fits(family, face, content)
]
if not feasible:
    raise CompositionPlanningFailure.from_face(face)
selected = max(feasible, key=lambda f: cadence_score(f, history, policy))
```

- [ ] Make the selection deterministic for identical inputs and policy versions.
- [ ] Record all considered families, elimination reasons, score components, and the selected version.
- [ ] Enforce one dominant mechanism per face. Secondary ornament does not count as a mechanism.
- [ ] Implement backtracking signals: `try_variant`, `try_family`, `return_to_editorial`, and `return_to_assets`.
- [ ] Run `research/preprocessor/.venv/bin/pytest -q research/preprocessor/tests/test_plan_compositions_v3.py`.

## Task 5: Materialize the frozen contract

**Files:**

- Create: `research/preprocessor/stages/materialize_render_contract_v3.py`
- Test: `research/preprocessor/tests/test_materialize_render_contract_v3.py`

- [ ] Write a test for all twenty faces, explicit spread accounting, stable element IDs, and no unreferenced string values.
- [ ] Implement one materializer per family ID. Each materializer converts semantic content references into the family's named regions and element union.
- [ ] Require every proof requirement and asset requirement to map to at least one required-visible element.
- [ ] Refuse to materialize if a number has no claim ID or an image has no asset ID.
- [ ] Serialize a full `FrozenRenderContractV3` and include source, plan, asset, family, policy, and contract hashes.
- [ ] Run `research/preprocessor/.venv/bin/pytest -q research/preprocessor/tests/test_materialize_render_contract_v3.py`.

## Task 6: Create the deterministic v3 renderer

**Files:**

- Create: `research/v7-renderer/render_v3.py`
- Create: `research/v7-renderer/contract_loader_v3.py`
- Create: `research/v7-renderer/families/base.py`
- Create: `research/v7-renderer/families/registry.py`
- Create: `research/v7-renderer/families/dmc_v1.py`
- Create: `research/v7-renderer/templates_v3/base.html.jinja`
- Create: `research/v7-renderer/styles_v3/tokens.css`
- Test: `research/v7-renderer/tests/test_render_v3_contract.py`

- [ ] Write tests that ship mode rejects an unknown family, missing family version, unsupported variant, or rendering exception.
- [ ] Write a draft-mode test that permits only the contract's named fallback and records the degradation.
- [ ] Implement strict contract loading before any HTML work.
- [ ] Implement family dispatch by exact `(family_id, version)` tuple. Do not use ST type to select a template.
- [ ] Reuse existing Jinja components only through typed element adapters. Do not pass the raw page dictionary to templates.
- [ ] Emit `data-element-id`, `data-content-ref`, `data-claim-id`, and `data-asset-id` attributes.
- [ ] Keep typography fitting inside contract bounds. If fit is impossible, return a structured render failure instead of shrinking further.
- [ ] Produce `report.raw.pdf`, page PNGs, rendered HTML, and render metadata. Do not invoke Ghostscript in this renderer.
- [ ] Run `research/v7-renderer/.venv/bin/pytest -q research/v7-renderer/tests/test_render_v3_contract.py`.

## Task 7: Emit the MaterializationLedger

**Files:**

- Create: `research/v7-renderer/materialization.py`
- Create: `research/preprocessor/contracts_v3/materialization.py`
- Test: `research/v7-renderer/tests/test_materialization_ledger.py`

- [ ] Add a Playwright probe that records bounding boxes, computed font size, line height, visibility, overflow, contrast inputs, and intersecting element IDs.
- [ ] Write tests for a clipped element, fully hidden element, overlap, below-minimum font size, and missing required element.
- [ ] Reconcile planned and observed element IDs. Any missing required ID is a hard render failure.
- [ ] Store coordinates in millimeters relative to the owning face, including correct left and right coordinates inside A3 spreads.
- [ ] Write `materialization-ledger.json` beside the raw PDF.
- [ ] Run `research/v7-renderer/.venv/bin/pytest -q research/v7-renderer/tests/test_materialization_ledger.py`.

## Task 8: Wire an isolated v3 service route

**Files:**

- Modify: `dmc-renderer/service.py`
- Modify: `dmc-renderer/build_live.py`
- Create: `dmc-renderer/build_v3.py`
- Test: `dmc-renderer/tests/test_service_v3.py`

- [ ] Back up both modified files under `dmc-renderer/.phase-zero-backups/2026-08-03/`.
- [ ] Add `POST /render-v3` without changing `POST /render`.
- [ ] Wire the exact order: v3 adapter, source ledger, editorial plan, asset ledger, composition plan, frozen contract, v3 renderer, materialization ledger.
- [ ] Disable external image generation in contract tests through an explicit deterministic fixture asset bank. Never rely on ambient API keys.
- [ ] Return structured failures with `owner_stage`, `code`, `face_ids`, and `element_ids`.
- [ ] Add response headers for contract, policy, family-registry, and build hashes.
- [ ] Run `research/preprocessor/.venv/bin/pytest -q dmc-renderer/tests/test_service_v3.py`.

## Completion gate

Run:

```bash
research/preprocessor/.venv/bin/pytest -q \
  research/composition_registry/tests \
  research/preprocessor/tests/test_render_contract_v3.py \
  research/preprocessor/tests/test_plan_compositions_v3.py \
  research/preprocessor/tests/test_materialize_render_contract_v3.py \
  research/v7-renderer/tests/test_render_v3_contract.py \
  research/v7-renderer/tests/test_materialization_ledger.py \
  dmc-renderer/tests/test_service_v3.py
```

Then run a deterministic synthetic valid fixture twice and compare SHA-256 hashes of the frozen contract, HTML, materialization ledger, and raw PDF.

The plan is complete only when:

- One valid 20-face plan renders with correct face, fragment, spread, and PDF-object counts.
- Every required element is present in the materialization ledger.
- No ST code, adapter alias, or raw page dictionary selects a v3 composition.
- Ship mode has zero silent template or treatment fallbacks.
- The same frozen input and asset bytes produce the same contract and materialization output.
