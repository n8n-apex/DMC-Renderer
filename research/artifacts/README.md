# v3 artifact store

Every retained v3 build persists one immutable record before request cleanup.
This is what makes release decisions auditable and builds reproducible.

## What is stored

`schema.BuildRecordV3` binds one build to its exact evidence:

- `input_sha256` — canonical hash of the source envelope
- `workflow_versions` — the six-field n8n handshake (contract, writer prompt,
  schema resolver, writer gate, source ledger, claim gate)
- `source_ledger_sha256`, `asset_ledger_sha256`, `editorial_plan_sha256`
- `composition_plan_sha256`, `render_contract_sha256`
- `pdf_hashes` (raw, review, digital, print as produced)
- `gate_report_sha256`, `export_report_hashes`
- `visual_review_evidence` — the human decision that authorized `ship_ready`,
  or `null` for anything below it

## Retention classes

| Class | Applies to | Retained |
|---|---|---|
| `rejected` | rejected builds | record, gate report, contract, composition plan (diagnosis only, no PDFs) |
| `draft` | draft builds | same as rejected |
| `review` | review candidates | diagnosis + materialization ledger, HTML, raw PDF, visibly marked review PDF |
| `approved_digital` | ship-ready digital | review set + digital PDF + digital export report |
| `approved_print` | ship-ready print | approved_digital set + print PDF + preflight report |

## Store semantics

`store.FilesystemArtifactStore.persist` stages into a hidden temp directory
and promotes with one atomic rename:

- A failed persist never leaves a partial build visible.
- Re-persisting identical content is idempotent.
- Re-persisting different content under the same `build_id` raises — retained
  builds are immutable.

The store root comes from the `DMC_V3_ARTIFACT_ROOT` environment variable or
the `artifact_store_root` build parameter; tests always pass explicit temp
roots.

## Release safety invariants

- A missing or unknown `release_state` in a build result is a 500, never a
  shipped PDF (`dmc-renderer/service.py`).
- `review_candidate` responses serve only the visibly marked review PDF.
- `ship_ready` requires validated `VisualReviewEvidenceV3`: at least two
  distinct raters, a rubric version, the exact candidate PDF hash, a decision
  timestamp, and the hash of the threshold policy in force. Boolean flags
  without evidence raise `visual_review_evidence_missing`.
