# DMC v3 migration readiness, revision 2

Date: 2026-08-06
Supersedes: `V3-MIGRATION-READINESS.md` (2026-08-03)

Decision: **DO NOT MIGRATE THE DEFAULT ROUTE YET.**

The blocking reasons have changed. Revision 1 blocked on an unwired visual
product: identical PDFs across different clients, a generic renderer, no
evidence-to-pixel binding, no artifact retention, and a fail-open release
default. Every one of those code-side failures is now closed and pinned by
tests. What remains are the decisions and inputs that belong to humans:
blind ratings and an approved visual threshold, printer-supplied production
values, rights confirmations, recovery of three source authorities,
credential rotation, live n8n import proof, and the owner's route decision.

## 1. What changed since revision 1

| Revision 1 blocker | State now |
|---|---|
| B1: no deployed workflow parity | Review-safe v3 workflow export exists (`docs/n8n/workflows/DMC-Ingestion-Pipeline-v3-review.json`, 47 nodes, inactive, 36 structural tests); the original deployed export is preserved byte-identically. Live import and read-back proof remain owner actions. |
| B2: no real client through the v3 path | Jousef and Christopher have deterministic migration records: preserved original hashes, every source reference extracted with `rights_status="unknown"`, case selection PENDING, 180 and 61 typed blockers. They are correctly blocked, not rendered; a test pins `renderable=False`. |
| B3: client variation unwired (identical PDFs) | **Closed.** Client character (tone, brand energy, imagery, chart opportunity, evidence density, asset availability) flows through typed `DesignFeaturesV3` into scored family and variant selection. Five rendered profiles now produce five distinct PDFs; the materially different trio produces fully distinct composition plans. Pinned: `test_materially_different_clients_produce_distinct_plans_and_pdfs`. |
| B4: creative treatment layer skeletal | **Closed at the structural level.** All ten families have atlas-grounded anatomy with per-variant grid layouts; raster-difference tests prove families and variants render visibly different pages; eight semantic viz element kinds render claim-bound devices selected by evidence shape. CSS is token-only with enforced palette and type-bound budgets. Whether the result meets Richard's bar is exactly what the human rating gate exists to decide. |
| B5: human calibration absent | Mechanics complete: seven deterministic pixel features per face, strict blind-rating schema, deterministic threshold derivation with dataset and code hashes. `ratings.jsonl` is empty and guarded against fabrication; the threshold policy is `unapproved_draft` with null values and cannot be treated as calibrated. **Ratings and approval remain the open human gate.** |
| B6: no production print profile | Mechanics complete: real Ghostscript ink-coverage measurement, crop marks and trim/bleed boxes, immutable preflight reports. `dmc_print_production_v1.json` exists as an explicitly blocked template with twelve printer-gated nulls. **Printer values remain the open external gate.** |
| B7: families and policies not promoted | Promotion now additionally requires accepted atlas-comparison records, and `client_tested` promotion rejects all-synthetic test matrices. All families remain `corpus_tested` — promotion legitimately waits on the human gates above. |
| B8: three missing source authorities | Unchanged. Recovery is an owner action (`research/missing-sources/manifest.json`). |
| B9: historical v2 suite failures | Unchanged at exactly the recorded 15-failure baseline through every v3 change (latest run 20260805T214134Z: 381 passed, 15 failed — count identical to the recorded baseline). |

Additional hardening landed beyond the revision-1 blockers:

- The fail-open release default is gone; a missing or unknown release state
  is a 500, never a shipped PDF. `ship_ready` requires typed
  `VisualReviewEvidenceV3` (two distinct raters, rubric version, exact
  candidate hash, threshold-policy hash); boolean flags alone raise.
- Every retained build persists an immutable `BuildRecordV3` (input, ledger,
  plan, contract, PDF, gate, and export-report hashes) in an atomic,
  immutable artifact store with retention classes; review PDFs are visibly
  stamped and delivery files are separate.
- Evidence and assets are verified from bytes at ship time: source content
  hashes recomputed, claims re-checked for spans or computation chains,
  asset bytes re-hashed, dimensions and effective DPI measured, traversal
  and face-allowlist and expiry violations rejected. A validated source
  appendix must cover every rendered source and is retained with the build.
- A3 spreads are split into exact face-level rasters before pixel gating.
- The six-field workflow version handshake (3.2.1) covers all five paste
  targets with byte-hash verification, and the n8n code runs dependency-free
  inside Code nodes.

## 2. Program gate results (2026-08-06)

| Gate | Result |
|---|---|
| Source-to-pixel traceability | Pass — including viz elements, byte-recomputed hashes, appendix coverage |
| Exactly 20 physical faces / 3 cases | Pass |
| Capacity-feasible composition | Pass — now including physical height budgets and variant envelopes |
| Zero silent ship fallback | Pass |
| Zero missing required visible elements | Pass |
| Blocking evidence and asset failures | Pass — extended to byte truth |
| Client-differentiated output | **Pass** — 5 profiles, 5 distinct PDFs, distinct plans where inputs are materially different |
| Family visual distinctness | Pass — raster-difference tests across families and variants |
| Searchable digital output | Pass — profile-validated with immutable export report |
| Profile-validated production print | **Fail** — blocked template only; printer values required |
| Reproducible manifests and artifacts | Pass — immutable store, idempotent persist |
| Deployed n8n parity | **Not proven** — review export ready; owner must import and hash-verify |
| Promoted families and policies | Fail by design — awaiting human gates |
| Human-calibrated visual threshold | **Fail** — zero ratings; policy `unapproved_draft` |
| Owner migration approval | Not requested |

Known open finding: the print-path PDF/A conversion currently measures
0.7522 searchable-text preservation against the 0.99 requirement on the
mechanical fixture. The gate correctly fails it. This must be resolved
(conversion settings or requirement review with the printer) before any
production print approval.

## 3. Remaining approvals ledger (nothing below can be coded around)

1. **Two independent blind raters** score reference and candidate faces;
   then derive the threshold (`derive_visual_threshold_policy`) and obtain
   named owner approval of `visual-threshold-v1.json`.
2. **Printer-supplied values** for the twelve nulls in
   `dmc_print_production_v1.json`, then production print preflight.
3. **Rights confirmations** for client and global assets; Jousef and
   Christopher case selection and editorial approval.
4. **Recovery of the three missing source authorities** and reconciliation.
5. **Credential rotation** for credentials retained by the old stopped
   container.
6. **Import of the v3 review workflow** into n8n, fill the labeled
   placeholders, and prove the deployed bytes match the repository export.
7. **Owner route decision.** `POST /render` is unchanged and stays v2 until
   every gate above passes and the owner explicitly approves migration in a
   separate decision. This document records readiness, not approval.

## 4. Evidence

- Verification: `research/calibration/runs/20260805T214134Z-verification/`
- Plan: `docs/superpowers/plans/2026-08-05-v3-integration-hardening.md`
- Progress log: `docs/phase-zero/HARDENING-PROGRESS-2026-08-05.md`
- Audit of the Codex handoff: `docs/phase-zero/CODEX-AUDIT-2026-08-05.md`
- Client distinctness pin: `dmc-renderer/tests/test_calibration_fixtures.py::test_materially_different_clients_produce_distinct_plans_and_pdfs`
- Release safety: `dmc-renderer/tests/test_v3_release_flow.py`, `test_v3_artifact_persistence.py`
- Review workflow: `docs/n8n/workflows/DMC-Ingestion-Pipeline-v3-review.json` + manifest
