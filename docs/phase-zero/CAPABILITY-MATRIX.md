# Phase Zero Capability Matrix

Date: 2026-08-03

## Status definitions

| Status | Meaning |
|---|---|
| Wired | Executes in the current Christopher HTTP build path and substantially does what its name promises. |
| Partial | Executes, but its contract, coverage, or failure behavior is insufficient for production. |
| Stale | Exists and may be tested, but encodes an obsolete path or requirement. |
| Unwired | Implemented in the repository but unreachable from the live build path. |
| Absent | No implementation satisfies the capability. |

## Matrix

| Layer | Capability | Status | Evidence | Production consequence |
|---|---|---|---|---|
| Input | n8n writer prompt v5 | Partial | Paste target exists in `docs/writer-prompt-v5.md`; deployed state is inaccessible. | Source quality cannot be reproduced from the repository alone. |
| Input | n8n schema resolver v5 | Partial | Paste target exists in `docs/resolve-schema-node-v5.js`; deployed state is inaccessible. | Repository and live workflow can drift silently. |
| Input | Deterministic writer gate | Unwired | `docs/n8n/writer_gate.js` exists, but deployment cannot be proven. | Banned words, invented credentials, and computed claims may reach the renderer. |
| Input | Multi-dialect compatibility | Wired | `_normalize_page_data()` in `dmc-renderer/build_live.py` adapts several payload dialects. | Historical fixtures still render. |
| Input | Canonical input schema | Absent | Page payloads remain free-form dictionaries with aliases. | Every downstream stage interprets meaning independently. |
| Evidence | Claim provenance ledger | Absent | No claim-to-source-span model survives into the package. | Numbers and assertions cannot be audited at ship time. |
| Evidence | Semantic number grounding | Partial | Visual synthesis checks digit occurrence, not claim context. | Correct numbers can receive incorrect labels or units. |
| Editorial | Reference-grounded page grammar | Partial | ST ordering and warnings exist, but target agreement and exactly-three cases are not enforced. | A 17-object, five-case deck passes a 24-target job. |
| Editorial | Narrative argument planner | Absent | No page-level thesis, evidence role, or transition contract. | ST labels stand in for editorial reasoning. |
| Editorial | Capacity-aware copy budget | Partial | Character thresholds exist, but aliases inflate counts by up to about 2.1 times. | Warnings are duplicated and fit decisions are noisy. |
| Editorial | Case-theory pairing | Partial | `plan_layout.py` warns on missing adjacency. | Two unpaired cases still ship. |
| Schema | Typed ST page data | Partial | `models_pagedata.py` parses permissively and falls back. | Malformed or incomplete pages are normalized instead of rejected. |
| Schema | Strict resolved package | Partial | Top-level extras are forbidden, but resolved pages and nested visuals are permissive. | Hollow pages can be valid packages. |
| Assets | Slot registry | Partial | Twelve slots resolve in the current fixture, but only a narrow set of page roles is modeled. | Theory, proof, screenshot, source, and QR needs are not explicit. |
| Assets | Required-asset blocking | Partial | Five case portraits are `missing_required`; assembly and service still succeed. | Missing identity proof ships as a polished draft. |
| Assets | Provenance and rights ledger | Absent | No rights, source class, allowed use, or semantic substitution policy. | Generated or product images can mask missing proof assets. |
| Assets | Generative image production | Wired | Fresh build generated three assets through the configured image path. | Surface finish improves, but builds are externally dependent and not fully reproducible. |
| Assets | Social asset planner | Unwired | Live route calls `route_package(..., manifest=None, ...)`. | Tested deterministic social routing never runs. |
| Visuals | Deterministic SVG component generation | Partial | Eleven builders exist; three are test-only and production dispatch is narrow. | The visible report uses only one generated SVG. |
| Visuals | Diagram intent detection | Partial | Active detector list covers convergence and generic stat callout. | Most text cannot become a reasoned diagram. |
| Layout | Legacy ST pattern routing | Wired | `plan_layout.py` maps every known ST to a legacy CSS family. | The deck always has a fallback page. |
| Layout | Capacity solver | Absent | No region-level word, line, or asset feasibility model. | Planner cannot choose a family because it fits. |
| Layout | Cadence planner | Partial | Dense-run and divider heuristics exist. | Recommendations overgeneralize from one reference style. |
| Layout | Backtracking alternatives | Absent | A chosen family is not replaced through measured retry. | Overflow and hollowness are handled late or visually ignored. |
| Treatments | Treatment catalog | Partial | Six dedicated template/CSS pairs sit behind sixteen descriptors. | Catalog breadth overstates implemented composition breadth. |
| Treatments | Runtime treatment selection | Wired | `treatment_stylist.py` assigns treatments by ST, fields, format, reuse, and adjacency. | The system produces limited syntactic variation. |
| Treatments | Semantic composition choice | Absent | Selector has no evidence, argument, asset-class, or capacity inputs. | Art direction is disconnected from what the page must prove. |
| Renderer | Chromium paged rendering | Wired | Fresh PDF and PNGs render successfully. | The main output engine is operational. |
| Renderer | Deterministic exact-contract execution | Partial | Renderer receives permissive pages and can reinterpret or fall back. | The preprocessor is not the sole authority. |
| Renderer | Premium-family failure blocking | Absent | Treatment and pattern exceptions fall back silently. | A failed premium page can ship as generic legacy output. |
| Renderer | Element-level materialization ledger | Absent | No planned element ID is matched to a final bounding box and visibility result. | Required copy or proof can disappear without a precise failure. |
| QA | PDF object overflow guard | Wired | PDF object count is compared with fragment count. | Extra objects are detected. |
| QA | Canonical face-count guard | Absent | A3 objects are not converted to two A4-equivalent faces. | Page-count success is semantically false. |
| QA | Raw content leak guard | Wired | Python singleton and container leaks are checked. | A narrow class of rendering bugs is blocked. |
| QA | Clipping and overlap detection | Partial | Some DOM height checks exist; treated pages skip the older A4-box check. | Element-level clipping and collisions can pass. |
| QA | Accent budget | Stale | Validator seam exists but implementation is a stub. | Claimed validation has no visual meaning. |
| QA | Reference-grounded quality loop | Stale | `research/quality_loop/` targets the older render path and is not called by HTTP service. | Premium output is not graded by the strongest available rubric. |
| QA | Blocking required-asset gate | Absent | Service reports data hard failures without rejecting the response. | Five missing portraits ship. |
| QA | Ship-state machine | Absent | Success is effectively binary: response or exception. | Draft degradation is indistinguishable from ship readiness. |
| Export | Ghostscript flattening | Wired | Inline PDF 1.3 printer-preset flattening runs. | Visual appearance is raster-stabilized. |
| Export | Searchable digital PDF | Absent | Fresh delivery PDF has zero extracted words and zero font references. | Search, selection, accessibility, and future tagging are lost. |
| Export | Formal print preflight | Absent | No PDF/X, ICC, TAC, bleed, crop, or printer-profile contract. | The file is flattened but not demonstrably press ready. |
| Operations | Reproducible build manifest | Partial | Package records some provenance and assets, but external model versions and source claims are incomplete. | Identical input does not guarantee identical evidence or assets. |
| Operations | Deployed workflow parity check | Absent | n8n is external and no handshake records prompt/schema versions. | The repo cannot prove what produced a job. |
| Tests | Unit and contract coverage | Wired | Fresh targeted runs produced 219 passes, 1 skip, plus a 10-of-10 harness. | Many code paths are protected from mechanical regression. |
| Tests | Reference-spec conformance | Stale | Tests intentionally accept five cases, contrary to all six references. | Green tests can preserve the wrong product behavior. |

## Overall score

Across 46 capabilities:

- Wired: 9
- Partial: 17
- Stale: 3
- Unwired: 2
- Absent: 15

The count is less important than the distribution. Rendering and local mechanics are the strongest area. Evidence, editorial planning, capacity planning, materialization, ship gating, and export contracts are the weakest. Those weak areas sit at subsystem boundaries, which explains why adding more isolated components has not produced a consistently good report.

## Dependency interpretation

The correct rebuild order is not visual polish first.

1. Canonical page and evidence semantics
2. Strict editorial and asset contracts
3. Capacity-aware composition planning
4. Deterministic renderer execution
5. Final-artifact quality gates
6. Separate digital and print exports
7. Wider creative family promotion

Any new template, skill, generated asset, or grader added before steps 1 through 3 will inherit the same ambiguity.
