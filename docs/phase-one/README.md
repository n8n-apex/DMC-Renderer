# Phase One: Design Grammar and Canonical Schema

Date: 2026-08-03

Status: complete

## Outcome

Phase One creates the authoritative precomposition boundary for contract v3.
It does not replace the renderer and it does not make the current Christopher
fixture shippable. It makes the reasons that input is not shippable explicit,
typed, deterministic, and early.

The v3 flow is:

```text
n8n envelope
  -> translation-only adapter
  -> source and claim ledger
  -> editorial report plan
  -> semantic asset ledger
  -> precomposition gate
  -> deterministic PrecompositionBundleV3
```

Any adapter, grounding, editorial, or asset blocker stops the flow before
composition and rendering.

## Authoritative house product

The evidence-backed default is `dmc_house_20_face`:

- Exactly 20 physical A4-equivalent faces.
- Exactly 3 case-study faces.
- At least 2 theory faces.
- Cover first and CTA last.
- Required narrative roles for outlook, about, status quo, false beliefs,
  summary, objections, collaboration, and CTA.
- Trust evidence must be planned, but it does not require one fixed page type.
- Density uses the atlas vocabulary: `light`, `moderate`, `dense`, and
  `very_dense`.
- A different product profile requires a named exception with `approved_by`,
  `reason`, and a profile ID different from the house profile.

This is derived from
`research/reference-atlas/reference-atlas.json`. All six Richard reports have
20 physical faces and exactly 3 case-study faces.

## Canonical units

Contract v3 separates physical faces from rendered fragments:

- A4 fragment: one physical face.
- A3 fragment: two physical faces.
- PDF object expectation: fragment count, not face count.
- Editorial contract: physical face count, not PDF object count.

For example, nine A4 fragments, one A3 fragment, and nine more A4 fragments
produce 20 faces, 19 fragments, and 19 expected PDF objects.

## Canonical contracts

The v3 contract package is in `research/preprocessor/contracts_v3/`:

- `units.py`: physical faces, fragments, and A4 or A3 allocation.
- `source_ledger.py`: immutable sources, spans, claims, computations, and typed
  grounding failures.
- `report_plan.py`: narrative roles, proof needs, asset needs, density, spreads,
  exceptions, and the house-profile validator.
- `asset_ledger.py`: semantic asset identity, provenance, rights, local bytes,
  print DPI, generated-asset recipe, and resolution result.
- `build_manifest.py`: stable serialization, artifact hashes, build versions,
  and `PrecompositionBundleV3`.

All models are strict and frozen. Unknown fields are rejected and successful
objects cannot be mutated after validation.

## Stage ownership

`dmc-renderer/adapter_v3.py` is a translation-only boundary. It may rename a
known alias once. It may not write copy, inject an author, assign case numbers,
snap page counts, route assets, or create claims. It recognizes the established
ST grammar, including ST-08 objections and ST-31 or ST-32 breathers. An unknown
ST type becomes an explicit adapter blocker.

`research/preprocessor/stages/build_source_ledger.py` owns evidence ingestion,
source hashing, claim validation, and ungrounded numeric-candidate detection.

`research/preprocessor/stages/plan_editorial_v3.py` owns physical-face
materialization, narrative roles, proof requirements, case identity, and
product-profile validation.

`research/preprocessor/stages/build_asset_ledger_v3.py` owns deterministic
asset resolution against the semantic requirements in the report plan.

`research/preprocessor/pipeline_v3.py` aggregates failures from all four
precomposition owners and either raises `PrecompositionBlocked` or returns one
deterministic bundle.

## Asset rules

- Identity and proof assets always require an exact semantic-class match.
- Explicit substitutions are available only to non-identity and non-proof
  requirements, such as context and decoration. The requirement must name the
  allowed class and the asset must use `APPROVED_CLASSES` substitution policy.
- A present but semantically wrong asset is an illegal substitution, not a
  successful fallback.
- Required assets must have cleared rights, local bytes, and adequate effective
  print DPI.
- Generated assets must record the generation recipe, model version, and seed.
- Decorative assets cannot silently stand in for client identity or proof.

## Grounding rules

- Sources carry capture time, locator, content hash, rights status, language,
  verbatim text, and allowed uses.
- Factual, numeric, quote, credential, certification, and named-result claims
  require exact source spans or a declared computation.
- An unlocated grounded claim from an input bundle becomes a typed
  `ungrounded_claim` ship blocker instead of aborting failure aggregation.
- Computed claims require operand claim IDs.
- Source spans must match the stored verbatim text exactly.
- Unknown source references and mismatched verbatim spans become typed blockers
  during source-bundle ingestion.
- Numeric tokens in report page data without a grounded claim become hard
  `ungrounded_numeric_candidate` failures.

## Current Christopher result

The current fixture is
`dmc-renderer/fixtures/christoph_v5_payload.json`.

The legacy source declares 23 physical faces across 17 page objects. Contract
v3 preserves those 23 faces instead of inheriting the renderer's accidental
18-page collapse. The source also declares 5 case studies.

With no source, claim, or asset evidence supplied, the precomposition gate
returns:

- 46 `ungrounded_numeric_candidate` failures, including the reported `83%`.
- 1 `face_count_mismatch`, because the house product requires 20 and the input
  declares 23.
- 1 `case_count_mismatch`, because the house product requires 3 and the input
  declares 5.
- 1 `required_role_missing` for objections.
- 5 `missing_required` identity-asset failures, one for each case study.

This rejection happens before composition. Contract v3 does not generate a PDF
from this fixture until those upstream facts are corrected or an approved
product-profile exception is supplied.

## Runtime selection

`DMC_CONTRACT_VERSION` controls the seam:

- Unset or `v2`: preserve the existing live build path.
- `v3`: adapt once, build the canonical ledgers and plan, then stop on any
  precomposition blocker.
- Any other value: reject explicitly.

The default remains v2 until later phases implement composition, quality-loop,
and postprocessor contracts on top of `PrecompositionBundleV3`.

## Test evidence

Fresh results from 2026-08-03:

- Phase One completion gate: 56 passed.
- Full preprocessor suite: 525 passed.
- v3 adapter suite: 10 passed.
- Legacy adapter contract harness: 10 of 10 passed.
- Renderer architecture guard battery: 45 passed.
- Full historical renderer suite: 342 passed, 15 failed, 1 skipped, 5 xfailed.

The 15 historical failures are confined to legacy Apex fixture and renderer
expectations in `research/v7-renderer/tests/test_render_r2.py` and
`research/v7-renderer/tests/test_st07a_fill_variant.py`. The count is identical
to the handoff baseline. No Phase One contract or adapter test fails.

## Known boundary after Phase One

Phase One establishes what may be composed. It does not yet establish how a
valid plan selects a page family, fits content into regions, produces a PDF,
scores the materialized result, or exports print and digital variants. Those
belong to the next implementation phases and must consume this contract rather
than recreate their own hidden schema.

The current v2 renderer remains operational but is not evidence that contract
v3 is complete end to end. A valid synthetic 20-face input produces a stable
precomposition bundle. A valid real client input, v3 composition engine, and v3
postprocessor are still future work.
