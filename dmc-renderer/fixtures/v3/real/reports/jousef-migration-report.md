# Migration report: jousef

Review-only migration of a legacy report payload into v3 editorial inputs. This record is NOT renderable and must not be treated as approved content. Every open gate below requires a human decision.

## Original artifact (preserved, verified separately)

- Repository path: `dmc-renderer/fixtures/apex_consulting_payload.json`
- SHA-256: `242c70ce4ffd002ef819b651cb8f2563d3dfb2c5f339a2579da0331a39950e0f`
- Byte count: 42379
- Report pointer: `$.payload`
- The original bytes are never edited. `verify_original` recomputes the hash and byte count on demand.

## Source references (all rights unresolved)

- Total references preserved verbatim: 37
- citation: 23
- url_field: 9
- inline_url: 5
- Every reference carries rights_status `unknown`. No rights were invented; resolving them is a human task.

## Case selection (pending human decision)

- Candidates found in the legacy report: 5
  - slot 6: Martina Ammon (`$.payload.pages[5].data`)
  - slot 8: Cordes Consulting (`$.payload.pages[7].data`)
  - slot 10: Frese Recruiting (`$.payload.pages[9].data`)
  - slot 12: Conesso GmbH (`$.payload.pages[11].data`)
  - slot 13: Hanisch & Klein (`$.payload.pages[12].data`)
- Required case count: 3. Chosen: 0. Excluded: 0. Pending: 5.
- Human review status: `pending`. No automated selection was made.

## Editorial map (explicit, never page-range derived)

- 20 faces defined explicitly from source content paths. Legacy `page_numbers` strings were never read; mutating them does not change this map.

| Face | Role | Source |
| --- | --- | --- |
| face.01 | cover | `$.payload.pages[0].data` |
| face.02 | outlook | `$.payload.pages[1].data` |
| face.03 | about | `$.payload.pages[2].data` |
| face.04 | status_quo | `$.payload.pages[3].data` |
| face.05 | false_beliefs | `$.payload.pages[4].data` |
| face.06 | case_study | case selection pending human review |
| face.07 | theory | `$.payload.pages[6].data` |
| face.08 | theory | `$.payload.pages[8].data` |
| face.09 | theory | `$.payload.pages[10].data` |
| face.10 | case_study | case selection pending human review |
| face.11 | mechanism | `$.payload.pages[13].data` |
| face.12 | case_study | case selection pending human review |
| face.13 | summary | `$.payload.pages[14].data` |
| face.14 | objections | house structure face without legacy source content |
| face.15 | trust_proof | `$.payload.pages[2].data.credibility_points` |
| face.16 | collaboration | `$.payload.pages[15].data` |
| face.17 | collaboration | `$.payload.pages[15].data` |
| face.18 | cta | `$.payload.pages[16].data` |
| face.19 | brand_breather | house structure face without legacy source content |
| face.20 | cta | `$.payload.pages[16].data` |

## Typed blockers

- Total blockers: 180
- `case_portrait_unresolved`: 5
- `founder_portrait_rights_unresolved`: 1
- `human_case_selection_pending`: 1
- `objections_evidence_missing`: 1
- `source_rights_unresolved`: 37
- `source_spans_missing`: 1
- `trust_proof_unverified`: 1
- `unsupported_claim`: 133

- Migrated `sources`, `claims`, and `assets` are all empty: nothing in the legacy payload is grounded, rights-cleared, or span-verified, so nothing was promoted.
- `renderable`: False

## Precomposition outcome

Correctly blocked. Feeding this record through `build_precomposition_bundle_v3` raises `PrecompositionBlocked`; the pipeline refuses to produce a bundle from this migration.

Distinct failure codes raised by the pipeline:

- `case_portrait_unresolved`
- `founder_portrait_rights_unresolved`
- `human_case_selection_pending`
- `missing_required`
- `objections_evidence_missing`
- `source_rights_unresolved`
- `source_spans_missing`
- `trust_proof_unverified`
- `ungrounded_numeric_candidate`
- `unsupported_claim`

This document is for human review only. Nothing here is release material, and no gate may be closed by editing this report.
