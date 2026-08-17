# Codex work audit and verified status map (2026-08-05)

## 1. Executive summary: built vs skeleton

**What Codex actually built (real, on disk, substantive):**
- The **v3 contract layer** (`research/preprocessor/contracts_v3/`, 9 files, ~1,220 lines) and the Aug-3 contract-and-editorial-planner plan (42/42 checked) — the only sub-plan whose checkboxes match reality.
- The **JS/Python evidence-ledger parity work (Task 1)**: `docs/n8n/source-ledger-node-v3.js` (211), `claim-gate-v3.js` (428), their Node test suites (350 + 495 lines), and the Python parity test (present under the variant name `test_source_ledger_node_v3_parity.py`, not the planned filename).
- **Deployment scaffolding (Task 3)**: `Dockerfile`, `.dockerignore`, `scripts/smoke_v3_container.sh`, `dmc-renderer/tests/test_v3_runtime_closure.py`, and a wired `/health/v3` route (`dmc-renderer/service.py:452`). Route isolation (`/render` v2, `/render-legacy-v2`, `/render-v3`) exists as documented.
- A **large red-test wave for Task 2**: Codex wrote failing tests for the six-field version handshake, paste-target execution semantics, dimension-checked computations, German banned-vocab inflections, and resolver claim_ids paths — **without any implementation**. Consequence: **14 Node tests and 10 Python workflow-contract tests currently FAIL**, even though the plan shows Task 1 checked `[x]` including "run Node+Python tests." The repo's test suites are red right now, by design of an unfinished TDD cycle.

**What is skeleton or absent:**
- The **v3 renderer's visual layer is a shell**: 10 family IDs but one generic renderer emitting identical `<section class="region">` wrappers (`families/dmc_v1.py`, 71 lines), a 12-line base template, a 41-line token sheet. No per-family anatomy, no data viz in v3 — despite 22 rich viz presets, a full treatment system, and a scoring loop sitting unwired one directory over.
- **Tasks 4, 7–12 are not started**: no artifact store (`research/artifacts/` missing), the **fail-open release default is still live** (`service.py:566` — `result.get("release_state", "ship_ready")`), no family templates, no evidence-binding tests, no review-safe workflow export, zero human ratings, no production print/digital profiles, no v2 readiness doc.
- **Task 5 migration modules are thin stubs** (25 + 57 lines of code vs 303 lines of tests) and the real Jousef/Christopher source-envelope fixtures do not exist.
- The **migration decision stands**: DO NOT MIGRATE; `POST /render` remains v2. The gates that failed (print profile, promotion, calibration, human threshold, deployed parity) all fail for reasons Codex cannot fix alone (Section 3).

## 2. Task status table — v3-integration-hardening (2026-08-05 plan)

| # | Task | Verdict | Evidence (one line) |
|---|------|---------|---------------------|
| 1 | JS/Py evidence-ledger parity | **DONE** (checked, but suite now red) | All 4 deliverable files + parity test exist (variant name); the 8 `[x]` are real, but the shared suites now show 14 Node + 10 Python failures from Task 2's red tests — the "tests pass" checkbox is no longer true as stated. |
| 2 | Workflow authority over evidence-critical nodes | **IN-PROGRESS-RED** | `test_workflow_version_handshake.py` + expanded Node/Python contract tests exist and FAIL: six-field handshake at 3.2.1/5.1.1/5.2.1/3.1.1, no-CommonJS-globals paste-target execution, dimension-checked computations, German banned-vocab inflections, resolver claim_ids paths — zero implementation. |
| 3 | Deployment closure (Docker/health/smoke) | **DONE** (unverified in container) | `Dockerfile` (68), `.dockerignore` (47), `smoke_v3_container.sh` (241), `test_v3_runtime_closure.py` (196), `/health/v3` at service.py:452 — all exist; plan checkboxes unchecked and no container-run evidence recorded. |
| 4 | Immutable artifacts, evidence-based release | **NOT-STARTED** | `research/artifacts/` directory missing entirely; unsafe fail-open default `result.get("release_state", "ship_ready")` still present at `dmc-renderer/service.py:566`. |
| 5 | Jousef/Christopher editorial migration | **SKELETON** | `legacy_report_v3.py` (25 lines) + `case_selection.py` (57) vs 303 lines of tests; all three `dmc-renderer/fixtures/v3/real/` fixture files missing — nothing real can flow through. |
| 6 | Composition selection on real features | **NOT-STARTED** | All listed files pre-date this plan (Aug-3 work); no new artifacts, no checked boxes, no evidence of feature-based selection work. |
| 7 | Visible family anatomy + semantic viz | **NOT-STARTED** | All 4 Create targets missing (`templates_v3/families/`, `styles_v3/families.css`, both tests); `families/dmc_v1.py` still renders every family as identical generic regions. |
| 8 | Bind evidence/asset integrity to content | **NOT-STARTED** | Both Create targets missing (`test_claim_content_binding_v3.py`, `test_asset_byte_integrity.py`); only pre-existing gate files present. |
| 9 | Review-safe n8n workflow export | **NOT-STARTED** | `docs/n8n/workflows/` does not exist; only the raw owner export in `~/Downloads/DMC Ingestion Pipeline.json`. |
| 10 | Visual quality calibration | **NOT-STARTED** | `calibration/ratings.jsonl` is empty (1 line); no `visual-threshold-v1.json`, no `test_visual_release_evidence.py`; zero blind ratings exist. |
| 11 | Digital + print production profiles | **NOT-STARTED** | Only `dmc_print_test.json` (`production_allowed: false`); both production profiles missing. |
| 12 | Multi-client matrix + route decision | **NOT-STARTED** | `V3-MIGRATION-READINESS-v2.md` missing; `run_matrix.py`/`report.py` are pre-existing thin files (71 + 19 lines). |

No task is MISWIRED in the strict sense; the closest hazard is the **fail-open release default at service.py:566** (Task 4's target), which makes `/render-v3` treat a missing release_state as ship-ready today.

## 3. Hard blockers requiring humans

1. **Rights confirmation** — no rights/provenance approval may be inferred; real client assets need owner sign-off before entering the ledger.
2. **Two independent visual raters + approved threshold** — `ratings.jsonl` is empty; the ship threshold cannot exist until ≥2 raters score reference and candidate sets and the owner approves a threshold (plan rule; migration gate "human-calibrated visual threshold: Fail").
3. **Printer-approved production profile** — only `dmc_print_test` exists, deliberately `production_allowed: false`; a real profile requires printer specs from a human.
4. **Three missing source authorities** — `Wichtig für Copy (KI-Floskeln).docx`, `DMC Report Luka Martic.pdf`, `InDesign Frese Recruiting Report v2.pdf` are gone from disk (transcribed remnants survive only in `docs/writer-prompt-v5.md` and memory); recovery is a human/owner action (`research/missing-sources/manifest.json`).
5. **Credential rotation** — keys associated with the old stopped container must be rotated by the owner before deployment closure is trustworthy.
6. **Deployed n8n workflow export** — the live workflow is not in this repo; parity is unprovable until the owner supplies a read-only export of the deployed instance (migration gate "Deployed n8n parity: Not proven"). Same for the paste-targets going live: `writer-prompt-v5.md`, `resolve-schema-node-v5.js`, `writer_gate.js` are all owner-side actions and the single biggest lever.
7. Also human-gated: **case selection/editorial approval** for Jousef/Christopher migration content, and **owner approval** before any change to production routing.

## 4. Reusable design knowledge index for Task 7 (family anatomy)

All paths verified on disk 2026-08-05.

**Rich machinery to pull into the flat v3 families:**
- **Viz preset library (22 presets)**: dispatch `research/v7-renderer/components/viz.jinja` (uid = loop index for page-unique SVG ids) → family macro files `viz_transform/proportion/magnitude/process/facts/compare.jinja` + `styles/viz.css` (the "premium recipe" is token-only and reusable verbatim).
- **Grounding guard pattern**: `research/v7-renderer/fixtures/apex/viz_curation.py::_figure_grounded` — verbatim-figure enforcement, digit-boundary matching, magnitudes derived at render so numeral and bar can't diverge. Never weaken.
- **Preprocessor SVG charts**: `research/preprocessor/stages/charts_svg.py` — `ChartTheme` parameterized (fits v3's flat token vars directly), 6 spec kinds, conservative extraction, never computes results.
- **Treatment system**: `treatment_engine.py` (`TreatmentData` — the proven "map real page data → named layout with required_fields gate" pattern), `treatment_catalog.py` (16 named layouts), `treatment_stylist.py` (deterministic assignment, no-two-adjacent-alike, A3 promotion only on hero), 6 authored template/CSS pairs in `templates/treatments/`.
- **Layout-template geometry model**: `research/v7-renderer/layout_template.py` — grid + regions (role, fractional geometry, fit modes) + type_roles + color_roles, hex forbidden; one extracted exemplar `layout_templates/ST-07A/case-study-split-stat-rail.json`. Direct precedent for per-family anatomy specs.
- **Component macros**: `research/v7-renderer/components/` — 40+ macros (two_tone_headline, stat_rail, ghost_numeral, pull_quote, authority_panel, …).
- **Theme-lock tokens**: `tokens/base.tokens.json` + `compile_tokens.py` — full type ramp (stat-xl 60pt → caption) and color roles, vs v3's 5-var `styles_v3/tokens.css`.
- **Scoring loop to gate the enrichment**: `quality_loop/reference_rubric_v3.py` (8 dimensions), `ship_gate_v3.py`, `vis_client.py` (cached, temp-0, brand-agnostic prompt), `references/` (84 classified reference pages, apex flagged machine_generated).
- **The seam**: `families/registry.py` `FamilyRendererRegistry` keyed `(family_id, version)` — where per-family renderers plug in; v3 pipeline stages already feed it (`plan_compositions_v3.py`, `materialize_render_contract_v3.py`, `render_v3.py`).

**Durable rules that bind any Task 7 work**: brand-agnostic guard (no client hex/name/font in components/styles/templates — `test_no_literals_in_architecture.py`); no fabricated figures; no box-shadow on viz; page-unique SVG ids; verify on pixels against Richard's reference PDFs, never test-green alone; graceful omit (missing data renders nothing, never a placeholder); stat sizes scoped down in page sheets, never up in components.

## 5. Stale or contradictory documentation worth correcting

1. **Hardening plan Task 1 `[x]` vs red suites**: the plan claims Node+Python tests were run and pass; 14 Node + 10 Python workflow-contract tests currently fail (Task 2 red tests). Annotate Task 1 or the plan header so the red state is expected, not hidden.
2. **Aug-3 sub-plan checkboxes never updated**: three of four sub-plans (composition-and-renderer, quality-and-postprocessor, n8n-assets-and-calibration) show 0 boxes checked, yet the master program marks "run every v3 test group from the four plans" `[x]` and the hardening plan asserts those suites "pass locally." One side is wrong on paper; the verification log (186 Python + 6 Node passed, run 20260803T151949Z) suggests the checkboxes are the stale side.
3. **`docs/phase-zero/README.md` checklist**: all 9 verification boxes unchecked while `VERIFICATION.md` records Status: Passed.
4. **CODEX-HANDOFF "NOT a git repository"**: the working directory is now a git repo (branch `claude/gracious-yalow-9408b9`, commits present). The no-history/no-blame gotcha is obsolete and should be rewritten.
5. **Test-count drift**: handoff says full suite "15 failed, **342** passed"; phase-zero records "15 failed, **352** passed" — reconcile or date-stamp both.
6. **`PRODUCTION_CODE_UNCHANGED_SINCE_2026-08-03=PASS`** — only valid on its run date; content-engine commits have landed since.
7. **STATE-OF-THE-BUILD stage line numbers** are pre-edit (751/755/…); CODEX-HANDOFF's (910/914/…) are the verified post-edit set. Mark the older table superseded.
8. **Plan filename vs disk**: the Task 1 parity test was planned as `test_source_ledger_python_parity.py` but exists as `test_source_ledger_node_v3_parity.py` — update the plan's Files section so file-existence audits don't misreport it missing.
9. **Point-in-time claims to re-verify before reuse**: capability-matrix counts (46: 9/17/3/2/15), asset-bank inventory (103 files, pinned to `inventory-2026-08-03.json`), "no deployed-workflow bundle exists," "zero blind ratings," "all families corpus_tested" — all dated 2026-08-03.
10. **`context.md`** is already flagged historical/contradictory in phase-zero docs; keep it out of authority chains.

Key paths: plan `/Users/utkarsh/Projects/richard/docs/superpowers/plans/2026-08-05-v3-integration-hardening.md`; fail-open default `/Users/utkarsh/Projects/richard/dmc-renderer/service.py:566`; readiness record `/Users/utkarsh/Projects/richard/docs/phase-zero/V3-MIGRATION-READINESS.md`; missing-sources manifest `/Users/utkarsh/Projects/richard/research/missing-sources/manifest.json`.

---

## Addendum: state after the 2026-08-05 Task 2 session (this session)

The red state described above was resolved in the same session that produced this audit:

- All 51 Node tests in `docs/n8n/tests/` pass (previously 14 failing).
- All 27 Python tests in `docs/n8n/tests/` pass (previously 10 failing).
- All 21 tests in `dmc-renderer/tests/test_workflow_version_handshake.py` pass (previously 4 failing).
- All 31 tests in `research/preprocessor/tests/test_build_manifest_v3.py` pass (previously 28 failing).

Implementation summary (backups in `tmp/backups/2026-08-05-task2/`):

1. `docs/n8n/source-ledger-node-v3.js` — replaced `node:crypto` with a portable FIPS 180-4 SHA-256 (n8n Code nodes have no `require`), exported `sha256`, added unit-dimension checks (`incompatible computation units`) and arity rules (difference/ratio exactly two operands) for computed claims, guarded `module.exports`, added the `$input` execution tail, bumped versions to the 3.2.1 handshake.
2. `docs/n8n/claim-gate-v3.js` — JSON *number* primitives are now grounded at every depth (root, arrays, objects) with nearest-inherited `claim_ids`; strings inside arrays are checked; key-hint semantics added (`ergebnis_text` → named outcome, `vertrauenspunkte` → credential); guarded exports + `$input` tail; 3.2.1 versions.
3. `docs/n8n/writer_gate.js` — German banned-vocabulary now rejects adjective inflections (`robuster`, `revolutionäre`, …); English detection catches short English titles and mixed English prose via an English-marker dominance rule while German loanwords (`Team`) stay safe; `$input` tail; 3.2.1 versions.
4. `docs/resolve-schema-node-v5.js` — 3.2.1 handshake versions (bildwunsch was already art-only).
5. `docs/writer-prompt-v5.md` — 3.2.1 handshake block; `bildwunsch.zweck` removed (renderer reads `art` only); ST-03/CTA metric devices removed to match the resolver (contract audit 2026-07-16).
6. `docs/n8n/workflow-contract-v3.json` — contract 3.2.1, artifact versions 5.1.1/5.2.1/3.1.1/3.2.1/3.2.1, hashes recomputed from current bytes.
7. `docs/n8n/verify_workflow_contract.py` — five-artifact rule now applies to all 3.2.x contracts.
8. `research/preprocessor/contracts_v3/build_manifest.py` — `BuildVersions.workflow_authority` is required and typed (`non_workflow` | `verified`); verified builds require the complete strict-semver six-field set; non_workflow builds must carry none; `BuildManifestV3.artifact_hashes` must be non-empty lowercase SHA-256.
9. `dmc-renderer/build_live.py` — `_with_workflow_provenance_v3` stamps `workflow_authority="verified"` only on complete ingress (all six fields + verification-bundle hash).
10. `research/preprocessor/pipeline_v3.py` — constructs `BuildVersions` explicitly as `non_workflow`.
11. `docs/n8n/deployment-checklist-v3.md` — names all five authoritative nodes.

The fail-open release default at `dmc-renderer/service.py` (`result.get("release_state", "ship_ready")`) remains the top open hazard and is Task 4's first target.
