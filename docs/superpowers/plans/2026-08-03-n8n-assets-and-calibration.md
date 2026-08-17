# Workflow, Asset Bank, Design Policy, and Calibration Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make upstream workflow versions reproducible, turn assets into a provenance-aware bank, translate selected design-skill knowledge into print policies, and calibrate the new system across references and diverse clients.

**Architecture:** The repository becomes the source of truth for versioned workflow artifacts and design policies. External systems declare the exact versions they execute. Skills inform authoring and critique through a reviewed policy registry, never through unpinned runtime prompt injection.

**Tech Stack:** JavaScript for n8n nodes, Python 3.11, JSON Schema, pytest, Node.js tests, SHA-256 manifests

---

This plan begins after the v3 contracts exist. Calibration continues through the other implementation plans and controls final promotion.

## Task 1: Version all n8n paste targets as one workflow contract

**Files:**

- Create: `docs/n8n/workflow-contract-v3.json`
- Create: `docs/n8n/verify_workflow_contract.py`
- Modify: `docs/writer-prompt-v5.md`
- Modify: `docs/resolve-schema-node-v5.js`
- Modify: `docs/n8n/writer_gate.js`
- Modify: `docs/n8n/WRITER-GATE-WIRING.md`
- Test: `docs/n8n/tests/test_workflow_contract.py`

- [ ] Back up each modified file under `docs/n8n/.phase-zero-backups/2026-08-03/`. Place the writer prompt backup there even though its source file is one directory higher.
- [ ] Define a manifest that records artifact ID, semantic version, repository path, SHA-256, expected node name, input schema version, and output schema version.
- [ ] Add a failing test that edits one byte in a copied artifact and detects the hash mismatch.
- [ ] Add `workflow_contract_version`, `writer_prompt_version`, `schema_resolver_version`, and `writer_gate_version` to the outgoing envelope.
- [ ] Update the service to reject missing or unsupported versions on `/render-v3`.
- [ ] Keep `/render` behavior unchanged during migration.
- [ ] Run `research/preprocessor/.venv/bin/pytest -q docs/n8n/tests/test_workflow_contract.py`.

## Task 2: Move evidence rules ahead of prose generation

**Files:**

- Create: `docs/n8n/source-ledger-node-v3.js`
- Create: `docs/n8n/claim-gate-v3.js`
- Create: `docs/n8n/SOURCE-LEDGER-WIRING.md`
- Test: `docs/n8n/tests/source-ledger-node-v3.test.js`
- Test: `docs/n8n/tests/claim-gate-v3.test.js`

- [ ] Write Node tests for direct facts, computed claims, quotes, credentials, and ungrounded numbers.
- [ ] Make the source-ledger node emit stable source IDs and spans before the writer runs.
- [ ] Make the writer consume claim IDs and source excerpts. It must not create unsourced numeric claims.
- [ ] Make the claim gate reject a page when any number, quote, credential, certification, or named outcome lacks a valid claim ID.
- [ ] Remove text-based numeric approval from the v3 workflow. Keep it only in v2 compatibility code.
- [ ] Run `node --test docs/n8n/tests/source-ledger-node-v3.test.js docs/n8n/tests/claim-gate-v3.test.js`.

## Task 3: Create the governed asset bank

**Files:**

- Create: `asset_bank/README.md`
- Create: `asset_bank/manifest.schema.json`
- Create: `asset_bank/manifest.json`
- Create: `asset_bank/index.py`
- Create: `asset_bank/validate.py`
- Create: `asset_bank/assets/.gitkeep`
- Test: `asset_bank/tests/test_asset_bank.py`

- [ ] Inventory existing `client_assets/`, `incoming_assets/`, `refs/`, and generated decorative sources without moving or deleting files.
- [ ] Write a report at `asset_bank/inventory-2026-08-03.json` with path, hash, dimensions, media type, inferred client, and duplicate group. Mark inferred fields for human review.
- [ ] Define required manifest fields matching `AssetLedger`: semantic class, provenance, source locator, rights, allowed uses, client scope, dimensions, print DPI constraints, and content hash.
- [ ] Make identity and proof records require explicit human confirmation. Do not infer rights.
- [ ] Add deterministic selection APIs for identity and proof. Add seeded scoring for approved context and decorative choices.
- [ ] Never copy client-scoped assets into a global decorative pool.
- [ ] Run `research/preprocessor/.venv/bin/pytest -q asset_bank/tests/test_asset_bank.py`.

## Task 4: Snapshot selected external design sources

**Files:**

- Create: `research/design_policy/README.md`
- Create: `research/design_policy/sources.json`
- Create: `research/design_policy/sync_sources.py`
- Create: `research/design_policy/vendor/.gitkeep`
- Create: `THIRD_PARTY_NOTICES.md`
- Test: `research/design_policy/tests/test_sources.py`

- [ ] Use only the public MIT-licensed material from [TypeUI](https://github.com/bergside/typeui) and [Designer Skills](https://github.com/Owl-Listener/designer-skills). Do not pull paid TypeUI content.
- [ ] Pin each source to an exact commit SHA and record repository URL, path, license path, retrieval date, local snapshot path, and SHA-256.
- [ ] Select TypeUI fundamentals plus editorial and publication design material. Exclude interactive patterns that have no print translation.
- [ ] Select Designer Skills material from `visual-critique`, `design-systems`, `ui-design`, and `design-ops`. Focus on hierarchy, composition, typography, information density, tokens, data visualization integrity, governance, critique, and handoff.
- [ ] Implement `sync_sources.py --verify` so normal tests verify pinned local bytes and never fetch the network.
- [ ] Record source license text and attribution in `THIRD_PARTY_NOTICES.md`.
- [ ] Run `research/preprocessor/.venv/bin/pytest -q research/design_policy/tests/test_sources.py`.

## Task 5: Translate source knowledge into a print DesignPolicyRegistry

**Files:**

- Create: `research/design_policy/schema.py`
- Create: `research/design_policy/registry.py`
- Create: `research/design_policy/policies/dmc-print-v1.json`
- Create: `research/design_policy/translation-log.md`
- Test: `research/design_policy/tests/test_registry.py`

- [ ] Define policy kinds: invariant, planner feature, family guidance, deterministic validator, and human rubric.
- [ ] Require every policy to carry source references, atlas evidence, print translation, enforcement owner, confidence, status, and known exceptions.
- [ ] Translate, do not copy blindly. Example:

```json
{
  "policy_id": "hierarchy.one-dominant-mechanism",
  "kind": "planner_feature",
  "print_translation": "Each face declares one dominant reading mechanism; minor devices may support it but may not compete for first attention.",
  "atlas_face_ids": ["apex.face.06", "buchagentur.face.08"],
  "status": "validated",
  "enforcement_owner": "composition_planner"
}
```

- [ ] Reject policies that have no print translation or no enforcement owner.
- [ ] Keep aesthetic suggestions experimental until corpus and client calibration passes.
- [ ] Wire validated policies into the composition registry, family tests, ship-gate rubrics, and design-review templates. Do not inject the vendor skill text into the writer prompt.
- [ ] Run `research/preprocessor/.venv/bin/pytest -q research/design_policy/tests/test_registry.py`.

## Task 6: Build a diverse calibration fixture set

**Files:**

- Create: `dmc-renderer/fixtures/calibration/manifest.json`
- Create: `dmc-renderer/fixtures/calibration/christoph.json`
- Create: `dmc-renderer/fixtures/calibration/apex.json`
- Create: `dmc-renderer/fixtures/calibration/service-business.json`
- Create: `dmc-renderer/fixtures/calibration/product-business.json`
- Create: `dmc-renderer/fixtures/calibration/sparse-evidence.json`
- Test: `dmc-renderer/tests/test_calibration_fixtures.py`

- [ ] Reuse real client content only when rights and provenance are known. Redact confidential details in committed fixtures.
- [ ] Require at least five fixture profiles that vary industry, tone, asset availability, evidence density, and visual brand.
- [ ] Include expected blockers rather than making every fixture artificially complete.
- [ ] Add a manifest with source hashes, consent status, redaction status, expected product profile, and expected gate state.
- [ ] Run `research/preprocessor/.venv/bin/pytest -q dmc-renderer/tests/test_calibration_fixtures.py`.

## Task 7: Add family and policy promotion tooling

**Files:**

- Create: `research/composition_registry/promotion.py`
- Create: `research/design_policy/promotion.py`
- Create: `research/calibration/run_matrix.py`
- Create: `research/calibration/report.py`
- Test: `research/calibration/tests/test_promotion.py`

- [ ] Implement states `experimental`, `curated_candidate`, `corpus_tested`, `client_tested`, and `promoted`.
- [ ] Require a promotion record with old and new versions, rationale, golden hashes, test matrix, deterministic gate results, human rating summary, and approver.
- [ ] Render every candidate family against its atlas examples and every compatible calibration fixture.
- [ ] Prevent production registry loading of anything below `promoted`.
- [ ] Never mutate an existing promoted version. Create a new semantic version.
- [ ] Run `research/preprocessor/.venv/bin/pytest -q research/calibration/tests/test_promotion.py`.

## Task 8: Recover and reconcile missing authorities

**Files:**

- Create: `research/missing-sources/README.md`
- Create: `research/missing-sources/manifest.json`
- Create: `research/missing-sources/reconcile.py`
- Test: `research/missing-sources/tests/test_manifest.py`

- [ ] Record the lost copy-law document and missing Luka Martic and Frese reference PDFs as unresolved authorities with expected source, last-known filename, and why each matters.
- [ ] When re-downloaded, hash files before reading and store them outside `Downloads` in `refs/source-authorities/`.
- [ ] Compare recovered copy law against `docs/writer-prompt-v5.md` and memory transcription. Produce a line-level reconciliation report without silently changing policy.
- [ ] Add recovered reference PDFs to the atlas through a new version. Do not overwrite the 120-face v1 dataset.
- [ ] Run `research/preprocessor/.venv/bin/pytest -q research/missing-sources/tests/test_manifest.py`.

## Task 9: Prove deployed workflow parity

**Files:**

- Create: `docs/n8n/deployment-checklist-v3.md`
- Create: `dmc-renderer/tests/test_workflow_version_handshake.py`
- Modify: `dmc-renderer/service.py`

- [ ] Add a read-only n8n verification step to the checklist that copies deployed node source and version fields back into a verification bundle.
- [ ] Implement a service handshake that records the workflow contract version in every build manifest.
- [ ] Reject v3 jobs whose deployed artifact hashes do not match `workflow-contract-v3.json`.
- [ ] Store the verification bundle hash, not workflow credentials.
- [ ] Run `research/preprocessor/.venv/bin/pytest -q dmc-renderer/tests/test_workflow_version_handshake.py`.

## Completion gate

Run:

```bash
research/preprocessor/.venv/bin/pytest -q \
  docs/n8n/tests \
  asset_bank/tests \
  research/design_policy/tests \
  research/calibration/tests \
  research/missing-sources/tests \
  dmc-renderer/tests/test_calibration_fixtures.py \
  dmc-renderer/tests/test_workflow_version_handshake.py

node --test docs/n8n/tests/*.test.js
```

The plan is complete only when:

- A v3 job proves which writer, schema resolver, and gate versions produced it.
- Every selected asset has class, provenance, rights, and content-hash evidence.
- External design guidance is pinned, licensed, print-translated, and connected to an enforcement owner.
- No unpromoted family or policy can load in production.
- At least five diverse fixtures participate in the calibration matrix.
- Recovered authorities are reconciled without overwriting the original Phase Zero evidence.
