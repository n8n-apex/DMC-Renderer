# DMC v3 migration readiness

Date: 2026-08-03

Decision: **DO NOT MIGRATE THE DEFAULT ROUTE**

The v3 architecture is no longer an unwired code sketch. It now has authoritative contracts, deterministic composition selection, exact artifact gates, governed assets, versioned workflow handshakes, print and digital export boundaries, and reproducible calibration runs.

The v3 visual product is still a skeleton. The current review candidate is safe and reproducible, but it is far below Richard's quality bar. It has placeholder content and assets, does not respond to client visual brand or tone, does not demonstrate the required data visualization system, has no live n8n parity proof, has no production print profile, and has no human-calibrated acceptance threshold.

`POST /render` therefore remains v2. `POST /render-legacy-v2` is the named compatibility route. `POST /render-v3` remains explicit and review-only unless every ship gate is satisfied.

## 1. Migration decision

The correct Phase 5 outcome is a blocked migration, not a forced green result.

The v3 system may be used for deterministic development and review candidates. It must not become the default or produce a delivery claim until all blockers in section 8 are closed and the owner explicitly approves the route change.

## 2. What is genuinely implemented

### Preprocessor

- Source, claim, editorial, asset, unit, and build-manifest contracts are strict and versioned.
- Page, face, spread, fragment, and PDF-object units are explicit.
- Evidence extraction happens before prose generation in the repository workflow design.
- Numeric, quoted, credential, certification, and named-outcome claims require valid claim IDs.
- The 20-face house profile requires exactly three complete cases.
- Capacity is checked against family regions before composition is accepted.
- Christopher's redacted known-failure recipe is rejected before composition with the expected evidence, count, case, and asset failures.

### Renderer

- Ten composition families are registered at version `1.1.0`.
- Selection is feasibility-first and deterministic.
- V3 composition selection does not use ST codes or compatibility aliases.
- A frozen render contract owns all visible element references.
- Required visibility is recorded in a materialization ledger.
- Ship mode has no silent family fallback.
- The same frozen input and asset paths produce identical contract, HTML, ledger, and PDF bytes.

### Postprocessor and quality gate

- Structure, evidence, assets, materialization, pixels, digital export, print profile, and exact artifact hashes have blocking gates.
- A valid deterministic candidate can become `review_candidate`, but not `ship_ready`, without calibrated human visual acceptance.
- Searchable digital export is tested for at least 99 percent normalized text preservation.
- Print export requires an explicit validated profile and preflight.
- The only repository print profile is deliberately test-only and cannot be used for production.

### Workflow, policy, and assets

- The n8n writer prompt, schema resolver, writer gate, and workflow contract have pinned versions and hashes.
- A source-ledger node and claim gate exist for evidence-before-prose operation.
- Deployed workflow parity has a strict verification bundle and service handshake.
- The asset bank inventories 103 files without moving client assets or inferring rights.
- Identity and proof selection requires explicit human confirmation.
- Public design-source material is pinned by commit and file hash, licensed, and translated into print policies.
- Design-source text is not injected into the runtime writer prompt.
- Composition families and design policies have immutable promotion tooling.
- Production loaders reject any family or policy below `promoted`.

## 3. Program gate results

| Gate | Result | Evidence and interpretation |
|---|---|---|
| Source-to-pixel traceability | Pass for synthetic v3 fixture | Claims, assets, elements, contract, materialization ledger, raster pages, and PDF carry stable references and hashes. |
| Exactly 20 physical faces | Pass for valid house fixture | The valid fixture allocates 20 faces across 19 PDF objects because one A3 fragment contains two faces. |
| Exactly three complete cases | Pass for valid fixture | The invalid Christopher recipe is rejected with five cases. |
| Capacity-feasible composition | Pass for tested fixture | Selection rejects incompatible families before rendering. |
| Zero silent ship fallback | Pass | Renderer degradation is a hard failure in ship mode. |
| Zero missing required visible elements | Pass for valid fixture | Materialization and asset gates inspect required IDs. |
| Blocking evidence and asset failures | Pass | Ungrounded numeric content and missing required identity or proof assets reject the job. |
| Searchable digital output | Pass in tests | Digital preservation tests exceed the 99 percent requirement. |
| Profile-validated production print output | Fail | Only `dmc_print_test` exists and it has `production_allowed: false`. |
| Reproducible manifests and artifacts | Pass | Same-input contract, HTML, ledger, and raw PDF hashes are identical across two runs. |
| Deployed n8n parity | Not proven | The handshake and checklist exist, but no read-only bundle from the live n8n workflow has been supplied. |
| Promoted family and policy versions | Fail by design | All validated policies and all ten families remain `corpus_tested`, not `promoted`. |
| Broad client visual calibration | Fail | Three nominally different valid profiles emit the same PDF bytes. |
| Human-calibrated visual threshold | Fail | There are zero completed blind ratings and no approved threshold. |
| Owner migration approval | Not requested | Approval must come only after all hard gates pass. |

## 4. Calibration run

All five frozen profiles ran with `FAL_KEY` and `OPENROUTER_API_KEY` replaced by sentinel values. No external generation was enabled.

| Fixture | Expected | Actual | Result |
|---|---:|---:|---|
| Christopher redacted | Rejected | Rejected | Matched |
| Apex synthetic | Review candidate | Review candidate | Matched |
| Service business | Review candidate | Review candidate | Matched |
| Product business | Review candidate | Review candidate | Matched |
| Sparse evidence | Rejected | Rejected | Matched |

Christopher's actual failure codes were:

- `ungrounded_numeric_candidate`
- `face_count_mismatch`
- `case_count_mismatch`
- `required_role_missing`
- `cta_not_last`
- `missing_required`

The expected four known blocker classes are present. The additional role and CTA failures are consequences of the deliberately truncated 17-face recipe.

The valid profiles have different gate-report hashes because their client identifiers and ledgers differ. Their raw PDF SHA-256 is identical:

`3dcf5bf6bce76032e22481b417068e945caa5f4a61d8ef7694e984d5f19b82b3`

This proves that the calibration metadata currently does not change rendered visual decisions.

## 5. Determinism result

The Apex synthetic fixture was built twice with the same envelope and immutable asset paths.

| Artifact | SHA-256 | Same across both runs |
|---|---|---:|
| Frozen contract | `311e756a18ea79ed90ceb36560257eb3aa7887a5cbaaf047b81b2f00cb964502` | Yes |
| Rendered HTML | `5014f4a4980aed2f38e2547e44420150af6a9899ea4a5895d290650d1eaeee8d` | Yes |
| Materialization ledger | `0922e0acdfa9c7a73a8f1eac202f197e002dbff4f31c6fda5c46e99adec5823a` | Yes |
| Raw PDF | `3dcf5bf6bce76032e22481b417068e945caa5f4a61d8ef7694e984d5f19b82b3` | Yes |

The earlier exploratory comparison that used different asset directories was not a same-input test. Asset locator paths are part of the asset-ledger input. The authoritative result above reuses one frozen envelope.

## 6. Visual and density audit

The v3 candidate is mechanically valid but not a credible DMC report.

Measured candidate density:

- 219 extracted words across the raw PDF
- 19 PDF objects
- 20 physical faces
- 10.9 words per face

Richard's six-reference corpus ranges from 248.8 to 345.0 words per face:

| Reference | Mean words per face |
|---|---:|
| Apex | 337.7 |
| Buchagentur | 345.0 |
| Alexander | 318.1 |
| Werkzeugkoffer | 248.8 |
| Niklas | 256.7 |
| Aerztepartner | 271.1 |

The synthetic v3 candidate therefore carries only about 3.2 to 4.4 percent of the reference corpus's mean face density.

This does not mean the production report should copy Richard's density blindly. It means the current calibration candidate does not exercise realistic copy capacity at all. It cannot prove that the system solves the original overlong-copy problem because it tests the opposite extreme.

Visual inspection of candidate pages 1, 6, 8, and 14 found:

- repeated generic headings and repeated body lines
- large neutral placeholder image blocks
- no meaningful client brand response
- an A3 theory spread that duplicates the same mechanism on both faces
- very large unused fields
- no Richard-level editorial pacing
- no rich chart or data-visualization grammar
- no meaningful distinction among Apex, service, and product profiles

The PDF itself is valid, searchable, tagged, unencrypted, and contains embedded Unicode fonts. Those are export properties, not proof of design quality.

No blind human review was recorded. The rating schema requires at least two raters who cover both reference and candidate cohorts before a threshold can be recommended. A model inspection is not substituted for that human gate.

## 7. Verification results

Authoritative verification run: `20260803T151949Z`

Focused v3 results:

| Group | Result |
|---|---:|
| Phase 1 contracts | 56 passed |
| Phase 2 composition | 33 passed |
| Phase 2 renderer | 16 passed |
| Phase 3 quality and exports | 42 passed |
| Phase 4 workflow, assets, policy | 26 passed |
| Phase 4 renderer handshake and fixtures | 8 passed |
| Phase 4 Node workflow contracts | 6 passed |
| Phase 5 route isolation | 3 passed |
| Verifier contract | 2 passed |

Focused total: 186 Python tests passed and 6 Node tests passed.

Complete renderer-directory result:

`15 failed, 352 passed, 1 skipped, 5 xfailed`

The same 15 historical v2 failures remain. The pass count increased from the earlier 342 baseline because ten v3 renderer tests now live inside the same directory. The failure count did not increase after the v3 work.

The 15 failures cluster around:

- stale or contradictory Apex founder and case-study fixture expectations
- ST-07A standard versus fill branch drift
- missing chart and social-post rendering in the selected branch
- ST-07A one-page overflow
- the light-page ground token behavior

The verification summary is intentionally `failed` because the historical suite is not green. Requirements were not weakened or rewritten to hide that state.

## 8. Hard migration blockers

### Blocker 1: Real upstream workflow parity is absent

The repository can verify a live n8n bundle, but no bundle from the deployed workflow exists. Until the actual node sources, names, versions, schemas, and hashes match, repository correctness does not prove production correctness.

### Blocker 2: Real client content has not passed the complete v3 path

Christopher is correctly rejected. The three successful profiles use intentionally minimal synthetic copy. No genuinely different complete client input has yet produced a review-worthy v3 report.

### Blocker 3: Visual brand, tone, and client variation are unwired

The fixture profiles contain different industry, tone, evidence density, asset availability, and visual-brand metadata. The three successful PDF hashes are identical. Those fields do not yet influence content planning, family variants, type roles, palette, image treatment, chart selection, or density.

### Blocker 4: The creative treatment layer is skeletal

The family registry is semantically meaningful, but the rendered implementations are generic. The system currently demonstrates boxes, headings, basic lists, processes, comparisons, stats, and images. It does not demonstrate Richard's actual component richness, layered hierarchy, branded proof, photo choreography, chart grammar, controlled asymmetry, or page-to-page rhythm.

### Blocker 5: Human calibration is absent

No two-rater blind comparison against matching atlas families exists. No approved visual threshold exists. All review candidates must remain review-only.

### Blocker 6: No production print profile exists

The RGB PDF/A-2b test profile proves machinery only. A printer-approved production profile, ICC bytes, output standard, bleed, crop marks, image DPI, ink coverage, font policy, and transparency policy are still required.

### Blocker 7: Families and policies are not promoted

All validated policies and all ten composition families remain `corpus_tested`. Production loading correctly rejects them. Promotion requires matrix results, golden hashes, deterministic gates, human ratings, rationale, version change, and approver.

### Blocker 8: Three source authorities remain missing

- `Wichtig für Copy (KI-Floskeln).docx`
- `DMC Report Luka Martic.pdf`
- `InDesign Frese Recruiting Report v2.pdf`

Recovered bytes must be hashed and reconciled. The 120-face atlas must be versioned forward rather than overwritten.

### Blocker 9: The legacy baseline still has 15 failures

Defaulting to v2 remains operationally conservative, but it is not a claim that v2 is high quality. Its known fixture drift, branch drift, overflow, and visual-token failures remain visible.

## 9. System completeness verdict

| Layer | Verdict |
|---|---|
| Contract model | Substantially built and fail-closed |
| Evidence model | Built locally, not proven in deployed n8n |
| Editorial planner | Structurally built, not calibrated on realistic copy |
| Composition planner | Deterministic and capacity-aware for registered families |
| Family library | Semantically structured, visually skeletal |
| Asset system | Governed inventory and selection exist, real human confirmations incomplete |
| Renderer | Deterministic, traceable, and exact; creative output underbuilt |
| Quality gate | Strong for deterministic invalidity; human quality threshold absent |
| Digital export | Test-proven |
| Print export | Mechanically test-proven, production authority absent |
| Workflow parity | Contract exists, deployed parity unproven |
| Calibration | Five outcomes executed, broad quality calibration failed |
| Migration | Blocked |

The system is not "just a skeleton" in architecture anymore. The skeleton is concentrated in the part users actually see: copy calibration, visual-brand interpretation, composition variants, data visualization, asset treatment, and calibrated art direction.

## 10. Required next work order

1. Export the deployed n8n v3 node sources and complete the hash handshake.
2. Recover the three missing source authorities and reconcile them without overwriting Phase Zero evidence.
3. Build one rights-cleared, redacted, realistic client fixture with complete source spans, claims, proof, identity assets, and production-length copy.
4. Wire tone, visual brand, evidence density, and asset availability into explicit planner features and family selection inputs.
5. Implement Richard-derived visual treatments for each family, including real image choreography, proof devices, density bands, and chart grammar.
6. Add deterministic data-visualization selection based on claim type, comparison structure, time series, distribution, process, and confidence.
7. Render five genuinely different clients and require non-identical visual decisions that remain within the house grammar.
8. Run two-rater blind review against matching atlas faces and set the first approved threshold.
9. Add a printer-approved production profile and pass the print preflight.
10. Promote new family and policy versions with immutable promotion records.
11. Re-run `scripts/verify_v3_program.sh`.
12. Request explicit owner approval before changing `POST /render`.

## 11. Route state

- `POST /render`: v2 default, labeled `legacy-v2` and `legacy-draft` in response headers
- `POST /render-legacy-v2`: named v2 compatibility route
- `POST /render-v3`: explicit v3 route with workflow version handshake and review-state enforcement

No default-route migration was made.

## 12. Evidence paths

- Verification script: `scripts/verify_v3_program.sh`
- Verification summary: `research/calibration/runs/20260803T151949Z-verification/verification-summary-20260803T151949Z.json`
- Verification logs: `research/calibration/runs/20260803T151949Z-verification/logs/`
- Calibration report: `research/calibration/runs/2026-08-03-phase5/calibration-fixture-report.json`
- Determinism report: `research/calibration/runs/2026-08-03-phase5/determinism/determinism-report.json`
- Visual inspection: `research/calibration/runs/2026-08-03-phase5/visual-inspection.json`
- Review candidate PDF: `research/calibration/runs/2026-08-03-phase5/calibration.apex-synthetic/build/report.raw.pdf`
- Review candidate rasters: `research/calibration/runs/2026-08-03-phase5/calibration.apex-synthetic/build/review-p01.png` through `review-p19.png`
- Workflow contract: `docs/n8n/workflow-contract-v3.json`
- Deployment checklist: `docs/n8n/deployment-checklist-v3.md`
- Asset inventory: `asset_bank/inventory-2026-08-03.json`
- Design-source manifest: `research/design_policy/sources.json`
- Design policies: `research/design_policy/policies/dmc-print-v1.json`
- Composition registry: `research/composition_registry/families/dmc-v1.json`
- Missing-authority manifest: `research/missing-sources/manifest.json`
- Print profile boundary: `research/postprocessor/profiles/README.md`

## 13. Approval boundary

This document records a migration rejection. It is not an owner approval request.

The default route may change only after every hard blocker is closed, the verification script no longer has unexplained failures, the human threshold is calibrated and met, and the owner explicitly approves the migration in a separate decision.
