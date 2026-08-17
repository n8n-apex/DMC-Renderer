# Contract and Editorial Planner Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Introduce canonical evidence, page-unit, editorial, and asset contracts that reject the current Christopher contradictions before rendering.

**Architecture:** Build immutable Pydantic v3 contracts beside package v2, add pure stages that produce them, and select v2 or v3 behind an explicit feature flag until the new renderer is ready. No current fallback is removed in this plan.

**Tech Stack:** Python 3.11, Pydantic v2, pytest, JSON fixtures

---

Repository note: this workspace is not under git. Before changing an existing file, copy it to a dated directory under `dmc-renderer/.phase-zero-backups/2026-08-03/`. Do not back up generated output or virtual environments.

## Task 1: Define canonical page units

**Files:**

- Create: `research/preprocessor/contracts_v3/__init__.py`
- Create: `research/preprocessor/contracts_v3/units.py`
- Test: `research/preprocessor/tests/test_contracts_v3_units.py`

- [x] Write failing tests for A4 faces, A3 spreads, render fragments, and PDF objects.

```python
def test_a3_spread_counts_as_two_faces_and_one_fragment() -> None:
    plan = DocumentUnits.from_formats(["a4", "a3", "a4"])
    assert plan.face_count == 4
    assert plan.fragment_count == 3
    assert plan.expected_pdf_objects == 3

def test_unit_names_are_never_implicit() -> None:
    with pytest.raises(ValidationError):
        DocumentUnits.model_validate({"count": 20})
```

- [x] Run `research/preprocessor/.venv/bin/pytest -q research/preprocessor/tests/test_contracts_v3_units.py` and confirm failure because the models do not exist.
- [x] Implement `FragmentFormat`, `FaceAllocation`, and `DocumentUnits` in `contracts_v3/units.py`.

```python
class FragmentFormat(str, Enum):
    A4 = "a4"
    A3 = "a3"

class FaceAllocation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    fragment_id: str
    format: FragmentFormat
    face_ids: tuple[str, ...]

    @model_validator(mode="after")
    def validate_face_count(self) -> "FaceAllocation":
        expected = 1 if self.format == FragmentFormat.A4 else 2
        if len(self.face_ids) != expected:
            raise ValueError(f"{self.format.value} requires {expected} face ids")
        return self
```

- [x] Export the types from `contracts_v3/__init__.py`.
- [x] Re-run the focused test and confirm it passes.

## Task 2: Build the immutable source and claim ledger

**Files:**

- Create: `research/preprocessor/contracts_v3/source_ledger.py`
- Create: `research/preprocessor/stages/build_source_ledger.py`
- Test: `research/preprocessor/tests/test_source_ledger_v3.py`
- Fixture: `research/preprocessor/tests/fixtures/source_bundle_christoph_minimal.json`

- [x] Write tests that reject an unlocated number, an unlocated quote, a computed claim without operands, and a source without a content hash.
- [x] Write a passing test for a sourced number.

```python
def test_number_requires_source_span() -> None:
    with pytest.raises(ValidationError, match="source_spans"):
        Claim(
            claim_id="claim.revenue",
            claim_type="number",
            normalized_value="83",
            unit="percent",
            source_ids=("source.interview",),
            source_spans=(),
        )
```

- [x] Run `research/preprocessor/.venv/bin/pytest -q research/preprocessor/tests/test_source_ledger_v3.py` and confirm the expected import failure.
- [x] Implement strict frozen models: `SourceItem`, `SourceSpan`, `Claim`, `Computation`, and `SourceLedger`.
- [x] Implement `build_source_ledger(source_bundle: dict) -> SourceLedger` as a pure function. It must hash local source bytes, normalize units, and preserve verbatim text.
- [x] Add `SourceLedger.assert_ship_grounded()` that returns typed failures for every number, quote, credential, named result, or certification without valid source spans.
- [x] Add fixture provenance for the current Christopher `83%` claim. If the fixture has no source span, record it as ungrounded and make the test expect a blocking failure. Do not invent a source.
- [x] Re-run the focused test.

## Task 3: Define the house editorial profile and ReportPlanV3

**Files:**

- Create: `research/preprocessor/contracts_v3/report_plan.py`
- Create: `research/preprocessor/policies/dmc_house_20_face.json`
- Create: `research/preprocessor/stages/plan_editorial_v3.py`
- Test: `research/preprocessor/tests/test_report_plan_v3.py`

- [x] Add failing tests for the reference-grounded invariants.

```python
def test_house_profile_requires_exactly_twenty_faces() -> None:
    result = validate_house_plan(plan_with(face_count=18))
    assert "face_count_mismatch" in result.codes

def test_house_profile_requires_exactly_three_cases() -> None:
    result = validate_house_plan(plan_with(case_count=5))
    assert "case_count_mismatch" in result.codes

def test_a3_spread_occupies_two_face_indices() -> None:
    plan = plan_with_spread(left=10, right=11)
    assert plan.units.face_count == 20
    assert plan.units.fragment_count == 19
```

- [x] Run `research/preprocessor/.venv/bin/pytest -q research/preprocessor/tests/test_report_plan_v3.py` and confirm failure.
- [x] Encode the stable roles and constraints in `dmc_house_20_face.json`. Include exactly three cases, two or more theory faces, stable opening and closing roles, trust evidence, and named exception policy.
- [x] Implement strict models `ProductProfile`, `NarrativeRole`, `ProofRequirement`, `AssetRequirement`, `FacePlan`, `SpreadPlan`, and `ReportPlanV3`.
- [x] Implement `plan_editorial_v3(ledger, brief, profile) -> ReportPlanV3`. The first version may use deterministic role allocation and must return a typed planning failure when evidence cannot support a required role.
- [x] Keep legacy ST codes as optional compatibility metadata only.
- [x] Add a regression proving the Christopher fixture is rejected for five cases and 23 source-declared faces rather than silently snapped to 20 or inheriting the renderer's 18-page collapse.
- [x] Re-run the focused test.

## Task 4: Define the provenance-aware AssetLedger

**Files:**

- Create: `research/preprocessor/contracts_v3/asset_ledger.py`
- Create: `research/preprocessor/stages/build_asset_ledger_v3.py`
- Test: `research/preprocessor/tests/test_asset_ledger_v3.py`

- [x] Write failing tests for identity substitution, proof substitution, missing rights, missing local bytes, and insufficient print resolution.

```python
def test_product_image_cannot_fill_case_identity_requirement() -> None:
    requirement = AssetRequirement(
        requirement_id="case.1.identity",
        semantic_class="identity",
        required_for_ship=True,
    )
    asset = asset_record(semantic_class="product")
    assert resolve_asset(requirement, [asset]).code == "illegal_semantic_substitution"
```

- [x] Run `research/preprocessor/.venv/bin/pytest -q research/preprocessor/tests/test_asset_ledger_v3.py` and confirm failure.
- [x] Implement `SemanticAssetClass`, `ProvenanceKind`, `RightsStatus`, `SubstitutionPolicy`, `AssetRecord`, and `AssetLedger`.
- [x] Implement exact-class resolution for identity and proof assets. Permit configured judgmental selection only for context and decoration.
- [x] Record content hashes, pixel dimensions, print size, effective DPI, generation recipe, model version, seed, and allowed face IDs.
- [x] Make five missing Christopher portraits typed ship blockers.
- [x] Re-run the focused test.

## Task 5: Remove alias inflation from the v3 path

**Files:**

- Modify: `dmc-renderer/build_live.py`
- Create: `dmc-renderer/adapter_v3.py`
- Test: `dmc-renderer/tests/test_adapter_v3.py`

- [x] Back up `dmc-renderer/build_live.py` to `dmc-renderer/.phase-zero-backups/2026-08-03/build_live.py`.
- [x] Write a regression that recursively counts normalized strings and proves v3 creates no duplicate `title`/`titel`, `body`/`einleitung`, or `steps`/`schritte` copies.
- [x] Run `research/preprocessor/.venv/bin/pytest -q dmc-renderer/tests/test_adapter_v3.py` and confirm failure.
- [x] Implement `adapt_envelope_v3()` as a translation-only boundary. It may rename fields once but may not inject authors, assign case numbers, snap counts, fill theory copy, route assets, or create claims.
- [x] Add a dual-build feature flag `DMC_CONTRACT_VERSION=v2|v3`. Default remains v2 until Plan 2 completes.
- [x] Log an explicit adapter failure for unsupported target counts. Do not snap.
- [x] Re-run the focused test and the existing adapter harness: `research/preprocessor/.venv/bin/python dmc-renderer/verify_contract_fixes.py`.

## Task 6: Add a canonical v3 orchestration seam

**Files:**

- Create: `research/preprocessor/pipeline_v3.py`
- Create: `research/preprocessor/contracts_v3/build_manifest.py`
- Test: `research/preprocessor/tests/test_pipeline_v3_contracts.py`

- [x] Write a test that the pipeline stops before composition planning when source, editorial, or asset blockers exist.
- [x] Write a test that all output artifacts include their schema and policy versions.
- [x] Implement this stage order:

```python
ledger = build_source_ledger(source_bundle)
report_plan = plan_editorial_v3(ledger, brief, profile)
asset_ledger = build_asset_ledger_v3(source_bundle, report_plan)
raise_if_blocked(ledger, report_plan, asset_ledger)
return PrecompositionBundleV3(
    source_ledger=ledger,
    report_plan=report_plan,
    asset_ledger=asset_ledger,
    versions=BuildVersions.current(),
)
```

- [x] Add JSON serialization with stable key ordering and content hashes.
- [x] Run `research/preprocessor/.venv/bin/pytest -q research/preprocessor/tests/test_pipeline_v3_contracts.py`.

## Task 7: Reconcile stale product tests

**Files:**

- Modify: `research/preprocessor/tests/test_validate_input.py`
- Create: `research/preprocessor/tests/test_house_profile_reference_contract.py`
- Reference: `research/reference-atlas/reference-atlas.json`

- [x] Do not delete the legacy at-least-three test. Rename it to make its v2 scope explicit.
- [x] Add v3 tests that derive six report summaries from the atlas and assert 20 faces and exactly three cases for every source.
- [x] Add a test that a product-profile exception must contain `approved_by`, `reason`, and a different profile ID.
- [x] Run:

```bash
research/preprocessor/.venv/bin/pytest -q \
  research/preprocessor/tests/test_validate_input.py \
  research/preprocessor/tests/test_house_profile_reference_contract.py
```

## Completion gate

Run:

```bash
research/preprocessor/.venv/bin/pytest -q \
  research/preprocessor/tests/test_contracts_v3_units.py \
  research/preprocessor/tests/test_source_ledger_v3.py \
  research/preprocessor/tests/test_report_plan_v3.py \
  research/preprocessor/tests/test_asset_ledger_v3.py \
  research/preprocessor/tests/test_pipeline_v3_contracts.py \
  research/preprocessor/tests/test_house_profile_reference_contract.py \
  dmc-renderer/tests/test_adapter_v3.py
```

The plan is complete only when:

- The current Christopher fixture is rejected before rendering for its ungrounded `83%`, five cases, wrong face count, and five missing identity assets.
- A synthetic valid 20-face, three-case fixture produces a deterministic `PrecompositionBundleV3`.
- No v3 copy budget counts compatibility aliases.
- Every serialized artifact includes version and content-hash metadata.
