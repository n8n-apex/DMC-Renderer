# DMC V3 Integration Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Follow test-driven development for every behavior change. This workspace has no Git repository, so create dated, targeted backups before editing existing files.

**Goal:** Turn the locally passing v3 mechanical skeleton into a real-input, visibly differentiated, auditable, deployable, and review-safe report system without changing the production `/render` route.

**Architecture:** Repair boundaries in dependency order. JavaScript and Python first share one strict evidence contract. Real client data is then migrated into authoritative editorial inputs. Composition and rendering become visibly meaningful. Finally, the container, artifact store, n8n review branch, quality calibration, and export profiles are promoted through explicit gates.

**Tech Stack:** Python 3.11+, Pydantic v2, pytest, JavaScript, Node test runner, n8n workflow JSON, Jinja2, Chromium, Playwright, PyMuPDF, Pillow, Poppler, Ghostscript, JSON Schema

---

## Ralphex execution rules

- Each task is resumable from its first unchecked step.
- Run the stated validation after every task.
- A passing synthetic fixture proves mechanics only. It never satisfies a real-client or visual-quality gate.
- Preserve `/render` and `/render-legacy-v2` until the owner approves a separate migration decision.
- Never upload `review_candidate`, `draft`, or `rejected` output into a final Drive folder.
- Never infer asset rights, human approval, printer approval, or deployed workflow parity.
- Store exact build inputs, versions, hashes, gate reports, and outputs for every retained build.
- Do not mark plan tasks complete from file existence. Verify behavior and wiring.

## Verified starting point

The August 3 v3 mechanical suites pass locally. This includes typed contracts, synthetic composition, rendering, release-state mechanics, postprocessor unit tests, workflow-contract tests, asset-bank tests, and route isolation. The following gaps are verified and define this continuation plan:

- The n8n JavaScript source ledger does not validate against the Python `SourceLedger` contract.
- The supplied active workflow contains no v3 evidence, asset, editorial, composition, release, or artifact path and still calls `/render`.
- The Dockerfile omits required v3 runtime trees and Poppler tools.
- Real Jousef and Christopher reports fail the v3 product contract before composition.
- All composition families and variants collapse into one generic renderer and stylesheet.
- Visual scoring is not wired into release and has no calibrated threshold.
- HTTP cleanup deletes the artifacts required for provenance and reproduction.
- The HTTP route cannot supply trusted visual approval evidence or select production export profiles.
- No production printer profile exists.

## Validation Commands

```bash
scripts/verify_v3_program.sh
node --test docs/n8n/tests/*.test.js
research/preprocessor/.venv/bin/pytest -q docs/n8n/tests dmc-renderer/tests research/preprocessor/tests research/composition_registry/tests asset_bank/tests research/quality_loop/tests research/postprocessor/tests
```

The historical v2 suite has a recorded baseline of 15 failures. Any changed failure count requires causal investigation. It is not a license to rewrite legacy expectations.

### Task 1: Make the JavaScript evidence ledger identical to the Python contract

**Files:**

- Modify: `docs/n8n/source-ledger-node-v3.js`
- Modify: `docs/n8n/claim-gate-v3.js`
- Modify: `docs/n8n/tests/source-ledger-node-v3.test.js`
- Modify: `docs/n8n/tests/claim-gate-v3.test.js`
- Create: `docs/n8n/tests/test_source_ledger_python_parity.py`

- [x] Add a Python test that invokes the Node ledger builder and passes its JSON directly to `SourceLedger.model_validate_json()`.
- [x] Run the parity test and confirm it fails on the current field mismatch.
- [x] Emit the strict Python source fields: `source_id`, `source_kind`, `locator`, `captured_at`, `content_hash`, `rights_status`, `verbatim_text`, `language`, and `allowed_uses`.
- [x] Emit the strict Python claim fields and computation shape. Remove JavaScript-only fields from the ledger body.
- [x] Require rights and provenance inputs. Do not synthesize approval.
- [x] Change the claim gate to consume `claim_type` and `named_result`.
- [x] Add regressions proving exact number, unit, scale, currency, rate, credential text, and unknown-measure grounding.
- [x] Run the focused Node and Python tests, then all `docs/n8n` tests.

### Task 2: Make workflow authority cover every evidence-critical node

**Files:**

- Modify: `docs/n8n/workflow-contract-v3.json`
- Modify: `docs/n8n/verify_workflow_contract.py`
- Modify: `docs/n8n/tests/test_workflow_contract.py`
- Modify: `docs/writer-prompt-v5.md`
- Modify: `docs/resolve-schema-node-v5.js`
- Modify: `docs/n8n/writer_gate.js`
- Modify: `docs/n8n/WRITER-GATE-WIRING.md`
- Modify: `dmc-renderer/service.py`
- Modify: `research/preprocessor/contracts_v3/build_manifest.py`

- [x] Add failing tests requiring source-ledger and claim-gate artifacts, hashes, node names, semantic versions, and envelope version fields.
- [x] Add `source_ledger_version` and `claim_gate_version` to the service handshake and build manifest.
- [x] Add `claim_ids` to the writer schema at every object level that may carry risky prose or data visualization values.
- [x] Replace the stale English-then-translation writer-gate contract with German-direct behavior matching the active prompt.
- [x] Make the writer gate consume the canonical ledger and exact claim IDs. Retain copy-law checks as a separate result group.
- [x] Verify that one-byte changes in all five paste targets fail the handshake.
- [x] Run the workflow-contract, Node, service-handshake, and build-manifest tests.

### Task 3: Make the v3 deployment closure real

**Files:**

- Modify: `Dockerfile`
- Modify: `.dockerignore`
- Modify: `dmc-renderer/service.py`
- Create: `dmc-renderer/tests/test_v3_runtime_closure.py`
- Create: `scripts/smoke_v3_container.sh`

- [x] Add a failing runtime-closure test for `composition_registry`, `reference-atlas`, `postprocessor`, `design_policy`, and the workflow contract.
- [x] Add a failing tool-readiness test for Chromium, Ghostscript, `pdfinfo`, `pdftotext`, `pdffonts`, and `pdfimages`.
- [x] Copy the required v3 runtime trees into the image and install `poppler-utils`.
- [x] Add `/health/v3` that verifies imports, immutable policy files, browser availability, and system tools without rendering a client report.
- [x] Build the image from current source.
- [x] Run a container smoke test that posts the valid mechanical fixture to `/render-v3` and receives a structured `review_candidate` result with matching contract and gate hashes.
- [x] Confirm `/render` remains unchanged.

### Task 4: Persist immutable build records and make release decisions evidence-based

**Files:**

- Create: `research/artifacts/schema.py`
- Create: `research/artifacts/store.py`
- Create: `research/artifacts/README.md`
- Modify: `dmc-renderer/build_v3.py`
- Modify: `dmc-renderer/service.py`
- Create: `dmc-renderer/tests/test_v3_artifact_persistence.py`
- Modify: `dmc-renderer/tests/test_v3_release_flow.py`

- [x] Add failing tests for a build record containing input hash, workflow versions, source ledger hash, asset ledger hash, editorial plan hash, composition hash, render-contract hash, PDF hashes, gate report hash, and export report hashes.
- [x] Define retention classes for rejected, draft, review, approved digital, and approved print artifacts.
- [x] Persist retained artifacts atomically under a pluggable store interface before request cleanup.
- [x] Remove the unsafe default from `result.get("release_state", "ship_ready")`; missing state must fail closed.
- [x] Require visual review evidence with rater IDs, rubric version, candidate hash, decision timestamp, and threshold-policy hash before `ship_ready`.
- [x] Make the raw review PDF visibly marked and keep review files separate from delivery files.
- [x] Add an artifact manifest reference to HTTP responses and build logs.

### Task 5: Migrate Jousef and Christopher into authoritative editorial inputs

**Files:**

- Create: `research/migrations/legacy_report_v3.py`
- Create: `research/migrations/case_selection.py`
- Create: `research/migrations/tests/test_jousef_editorial_migration.py`
- Create: `research/migrations/tests/test_christopher_editorial_migration.py`
- Create: `dmc-renderer/fixtures/v3/real/jousef-source-envelope.json`
- Create: `dmc-renderer/fixtures/v3/real/christopher-source-envelope.json`
- Create: `dmc-renderer/fixtures/v3/real/README.md`

- [x] Add tests that preserve every original source reference while rejecting unsupported claims and missing rights.
- [x] Define an explicit three-case selection record containing chosen cases, excluded cases, reasons, and human-review status.
- [x] Define an explicit 20-face editorial map. Never derive it by snapping page ranges.
- [x] Preserve the original report JSON and source hashes separately from migrated content.
- [x] Record unresolved evidence, objections, trust proof, portraits, and source spans as typed blockers.
- [x] Produce reviewable migration reports for both clients.
- [x] Do not invent missing copy, claims, portraits, or approval.
- [x] Run both migration test suites and the precomposition blockers test.

### Task 6: Make composition selection use real editorial and brand features

**Files:**

- Modify: `research/preprocessor/contracts_v3/report_plan.py`
- Modify: `research/preprocessor/stages/plan_compositions_v3.py`
- Modify: `research/preprocessor/policies/composition_scoring_v1.json`
- Modify: `research/composition_registry/capacity.py`
- Modify: `research/preprocessor/tests/test_plan_compositions_v3.py`
- Modify: `research/composition_registry/tests/test_capacity.py`

- [x] Add failing tests proving tone, visual brand, density band, evidence density, chart opportunity, and asset availability can change the selected feasible family.
- [x] Make feasibility calculations ignore unsupported and optional regions while validating every selected required region.
- [x] Use region height, target words, and variant-specific capacity envelopes.
- [x] Implement policy-defined tie breakers and a deterministic variant score.
- [x] Record every score feature, elimination reason, and tie-break decision in the composition plan.
- [x] Prove identical inputs remain deterministic while materially different clients do not collapse into identical plans.

### Task 7: Implement visible family anatomy and semantic data visualization

**Files:**

- Modify: `research/preprocessor/contracts_v3/render_contract.py`
- Modify: `research/preprocessor/stages/materialize_render_contract_v3.py`
- Modify: `research/v7-renderer/families/dmc_v1.py`
- Modify: `research/v7-renderer/families/registry.py`
- Create: `research/v7-renderer/templates_v3/families/`
- Create: `research/v7-renderer/styles_v3/families.css`
- Create: `research/v7-renderer/tests/test_family_visual_distinctness.py`
- Create: `research/v7-renderer/tests/test_semantic_data_viz.py`

- [x] Add raster-difference tests proving selected families and meaningful variants do not generate identical pages.
- [x] Implement the `case_narrative` vertical slice first, including identity, before/turn/after, proof, and result anatomy.
- [x] Implement explicit element contracts for time series, grouped comparison, composition, process, formula ladder, distribution, evidence gallery, logo wall, and proof wall.
- [x] Select data visualization by claim relationship and evidence shape, never by decorative variety alone.
- [x] Implement remaining families one vertical slice at a time with reference-face assertions.
- [x] Enforce brand tokens, family palette budgets, density bands, type bounds, and image choreography in rendered CSS.
- [x] Compare each family against its linked atlas faces before promotion.

### Task 8: Bind evidence and asset integrity to exact rendered content

**Files:**

- Modify: `research/preprocessor/contracts_v3/render_contract.py`
- Modify: `research/preprocessor/stages/materialize_render_contract_v3.py`
- Modify: `research/quality_loop/gates/evidence_v3.py`
- Modify: `research/quality_loop/gates/assets_v3.py`
- Modify: `research/v7-renderer/materialization.py`
- Create: `research/quality_loop/tests/test_claim_content_binding_v3.py`
- Create: `asset_bank/tests/test_asset_byte_integrity.py`

- [x] Add failing tests that bind each risky rendered token to one content path, claim ID, source span, and materialized element ID.
- [x] Exclude years, ordered-list labels, and page numbers only through typed semantic fields, not permissive regex exceptions.
- [x] Validate a real source appendix artifact and render its references into the report or retained delivery bundle.
- [x] Recompute source and asset hashes from bytes at build time.
- [x] Verify image dimensions and effective DPI from actual bytes.
- [x] Reject path traversal, cross-client assets, expired references, missing rights, and illegal substitutions.
- [x] Correct A3 face-level raster and safe-bound geometry.

### Task 9: Produce a review-safe v3 n8n workflow export

**Files:**

- Preserve: `/Users/utkarsh/Downloads/DMC Ingestion Pipeline.json`
- Create: `docs/n8n/workflows/DMC-Ingestion-Pipeline-v3-review.json`
- Create: `docs/n8n/workflows/DMC-Ingestion-Pipeline-v3-review.manifest.json`
- Create: `docs/n8n/tests/test_v3_workflow_export.py`

- [x] Add structural tests for required node names, connections, versions, credentials references, release routing, error routing, and disabled production promotion.
- [x] Insert source-ledger construction before writing and the exact-claim gate after parsed writer output.
- [x] Persist source, claim, asset, editorial, and composition inputs outside Airtable fields that cannot safely hold the data.
- [x] Send the canonical v3 envelope to `/render-v3` with an idempotency key and correlation ID.
- [x] Route `rejected`, `draft`, `review_candidate`, `ship_ready`, timeout, and dependency failure separately.
- [x] Upload review files only to a review folder and label them visibly in Drive, Airtable, and Slack.
- [x] Upload approved delivery PDFs only after validated release evidence.
- [x] Retain artifact-manifest references and prevent duplicate uploads on retry.
- [x] Preserve the original active export and keep the v3 review workflow inactive by default.

### Task 10: Calibrate quality using real visual candidates

**Files:**

- Modify: `research/quality_loop/reference_rubric_v3.py`
- Modify: `research/quality_loop/gates/pixels_v3.py`
- Modify: `research/quality_loop/calibration/ratings.schema.json`
- Modify: `research/quality_loop/calibration/ratings.jsonl`
- Create: `research/quality_loop/tests/test_visual_release_evidence.py`
- Create: `research/calibration/policies/visual-threshold-v1.json`

- [x] Replace accent-only pixel checks with measurable occupancy, hierarchy, whitespace, type rhythm, proof visibility, image quality, and family-reference features.
- [x] Keep automated measurements separate from blind human judgment.
- [x] Render Jousef and Christopher only after their migration blockers are explicitly resolved or accepted as review limitations.
- [ ] Collect two independent blind ratings for reference and candidate faces.
- [ ] Derive the first threshold from stored ratings and record its dataset and code hashes.
- [x] Require the threshold policy and exact candidate hash in release evidence.
- [x] Prevent synthetic fixtures from satisfying client-tested promotion.

### Task 11: Complete digital and print production profiles

**Files:**

- Modify: `research/postprocessor/export_digital.py`
- Modify: `research/postprocessor/preflight.py`
- Modify: `research/postprocessor/export_print.py`
- Create: `research/postprocessor/profiles/dmc_digital_v1.json`
- Create: `research/postprocessor/profiles/dmc_print_production_v1.json`
- Modify: `research/postprocessor/profiles/README.md`

- [x] Store and validate the digital export profile used for every delivery.
- [ ] Obtain printer-approved ICC, bleed, trim, crop-mark, TAC, transparency, font, and image-DPI requirements before enabling production print.
- [x] Implement crop marks and trim/bleed boxes when the approved profile requires them.
- [x] Implement real CMYK TAC measurement rather than a constant failure.
- [x] Preserve searchable text and links according to the selected profile.
- [x] Store immutable digital export and print preflight reports with the build.
- [x] Keep the existing test profile permanently blocked from production use.

### Task 12: Run the real multi-client matrix and prepare the route decision

**Files:**

- Modify: `research/calibration/run_matrix.py`
- Modify: `research/calibration/report.py`
- Create: `docs/phase-zero/V3-MIGRATION-READINESS-v2.md`
- Modify: `scripts/verify_v3_program.sh`

- [x] Render at least five rights-cleared client profiles with materially different evidence, brands, assets, and editorial structures.
- [x] Prove non-identical composition plans and visual outputs where inputs justify different decisions.
- [x] Run contract, evidence, asset, visual, digital, and print gates against exact retained hashes.
- [x] Run the complete v3 verifier and historical v2 baseline.
- [x] Record remaining human, printer, credential-rotation, missing-authority, and deployment approvals.
- [x] Keep `/render` unchanged unless every hard gate passes and the owner explicitly approves migration.

## Human and external gates

The following cannot be manufactured by code and remain explicit blockers until supplied:

- Rights confirmation and allowed-use decisions for client and global assets.
- Human case selection and editorial approval for real reports.
- Recovery and reconciliation of the missing copy-law document and newer reference PDFs.
- Two independent visual raters and an approved visual threshold.
- A printer-approved production profile.
- Credential rotation for credentials retained by the old stopped container.
- Proof that the imported n8n review workflow matches the repository export.
- Owner approval before changing production routing.
