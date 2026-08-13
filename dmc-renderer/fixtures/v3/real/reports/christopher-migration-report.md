# Migration report: christopher

Review-only migration of a legacy report payload into v3 editorial inputs. This record is NOT renderable and must not be treated as approved content. Every open gate below requires a human decision.

## Original artifact (preserved, verified separately)

- Repository path: `dmc-renderer/fixtures/christoph_v5_payload.json`
- SHA-256: `329bfa7681eb7ee490ff36ab9a63ba174f50c9f0c4647cc4f96936e3f3af95a4`
- Byte count: 20547
- Report pointer: `$`
- The original bytes are never edited. `verify_original` recomputes the hash and byte count on demand.

## Source references (all rights unresolved)

- Total references preserved verbatim: 4
- explicit_source_field: 3
- url_field: 1
- Every reference carries rights_status `unknown`. No rights were invented; resolving them is a human task.

## Case selection (pending human decision)

- Candidates found in the legacy report: 5
  - slot 6: Geschäftsführer mittelständischer Software-Hersteller (`$.pages[5].data`)
  - slot 8: CTO Softwarehaus Schienen- und Trassenbau (`$.pages[7].data`)
  - slot 10: Geschäftsführer Dienstleistungsunternehmen 45 MA (`$.pages[9].data`)
  - slot 12: Geschäftsführer Bauunternehmen 6 Poliere (`$.pages[11].data`)
  - slot 13: Geschäftsführer Eventgastronomie Hamburg (`$.pages[12].data`)
- Required case count: 3. Chosen: 0. Excluded: 0. Pending: 5.
- Human review status: `pending`. No automated selection was made.

## Editorial map (explicit, never page-range derived)

- 20 faces defined explicitly from source content paths. Legacy `page_numbers` strings were never read; mutating them does not change this map.

| Face | Role | Source |
| --- | --- | --- |
| face.01 | cover | `$.pages[0].data` |
| face.02 | outlook | `$.pages[1].data` |
| face.03 | about | `$.pages[2].data` |
| face.04 | status_quo | `$.pages[3].data` |
| face.05 | false_beliefs | `$.pages[4].data` |
| face.06 | case_study | case selection pending human review |
| face.07 | theory | `$.pages[6].data` |
| face.08 | theory | `$.pages[8].data` |
| face.09 | theory | `$.pages[10].data` |
| face.10 | case_study | case selection pending human review |
| face.11 | mechanism | `$.pages[13].data` |
| face.12 | case_study | case selection pending human review |
| face.13 | summary | `$.pages[14].data` |
| face.14 | objections | house structure face without legacy source content |
| face.15 | trust_proof | `$.pages[2].data.vertrauenspunkte` |
| face.16 | collaboration | `$.pages[15].data` |
| face.17 | collaboration | `$.pages[15].data` |
| face.18 | cta | `$.pages[16].data` |
| face.19 | brand_breather | house structure face without legacy source content |
| face.20 | cta | `$.pages[16].data` |

## Typed blockers

- Total blockers: 61
- `case_portrait_unresolved`: 5
- `cta_url_missing`: 1
- `founder_portrait_rights_unresolved`: 1
- `human_case_selection_pending`: 1
- `objections_evidence_missing`: 1
- `source_rights_unresolved`: 4
- `source_spans_missing`: 1
- `trust_proof_unverified`: 1
- `unsupported_claim`: 46

- Migrated `sources`, `claims`, and `assets` are all empty: nothing in the legacy payload is grounded, rights-cleared, or span-verified, so nothing was promoted.
- `renderable`: False

## Precomposition outcome

Correctly blocked. Feeding this record through `build_precomposition_bundle_v3` raises `PrecompositionBlocked`; the pipeline refuses to produce a bundle from this migration.

Distinct failure codes raised by the pipeline:

- `case_portrait_unresolved`
- `cta_url_missing`
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
