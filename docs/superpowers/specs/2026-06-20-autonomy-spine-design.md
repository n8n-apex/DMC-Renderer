# Autonomy Spine — Design Spec

**Status:** Authoritative design, approved in brainstorming dialogue 2026-06-20 (sections 1 to 3 approved; this document folds in the verification + infection audit of 2026-06-20). Build resumes against THIS doc; next step is writing-plans.
**Date:** 2026-06-20
**Goal (verbatim user framing to preserve):** "The system actually proceeding through its entire processes to generate the report" with "Claude Code not acting as the mediator." The live service self-produces a Richard-quality PDF end to end, with a human pulled in only by exception.
**Cardinal rule (inherited, non-negotiable):** brand-agnostic everywhere. No client name, hex, font, or literal in logic. Per-client is DATA (brand tokens, axes, content, assets). This is "the rule that nearly killed the project." No em dashes in any authored text or copy.

---

## 0. What this is, and what it is NOT

This spine is **the wiring and gap-closing of an architecture that already exists on paper**, not a new invention. The parent design is `docs/superpowers/specs/2026-06-03-self-correcting-quality-architecture-design.md` (the Brain / Conductor / Interceptor closed loop), which already states that "the Brain wraps the existing pipeline, and it may adopt the async `/render` to 202 plus webhook variant." This spec makes that real and removes the defects that stop it from running today.

The 2026-06-20 verification + infection audit (run `wf_4513bd57-e13`) confirmed two things that shape this spec:
1. **Most of the machinery already exists.** The whole-deck loop (`research/quality_loop/run_deck.py`, `brain.converge_deck`), the vision reference-comparison grader (`vis_client.score_page`, `references/`), and the 7-field design-axes contract (`package_loader.py:54-60`) are all built. The spine is mostly **wiring, composition, and cache re-keying** on top of working code.
2. **The "two realities" disconnect is real and confirmed against live code.** The live `/render` endpoint never renders or grades anything; the only graded PDF ever produced comes from running the renderer by hand against a frozen fixture. Every recurring regression and the autonomy gap trace to this one fault.

**Foundations to build ON, never reinvent (cited so a future session does not rebuild them):**
- `research/quality_loop/brain.py` (`converge_page`, `converge_deck`, `best_artifacts`, the three guards), `run_deck.py`, `stage_converge.py`.
- `research/quality_loop/vis_client.py` (`score_page`), `references/decks.py`, `references/classify.py`, the `vis_results` branch in `analysis.score`.
- `research/v7-renderer/package_loader.py:54-60` (the 7-field `axes` loader).
- The rubric in `2026-06-03-self-correcting-quality-architecture-design.md` §6 (positive P01 to P16, negative N01 to N14), derived from `2026-05-30-richard-design-dna.md` §C/§E.

---

## 1. Locked constraints (from brainstorming, do not relitigate)

1. **Entry point: the live FastAPI `/render` web service**, triggered by n8n/Airtable, produces the final graded PDF with no human in the normal path. (User choice.)
2. **Quality target: match then exceed.** The live `/render` output must reproduce, then beat, today's hand-tuned frozen apex deck. Every hand edit in the frozen fixture moves into brand-agnostic stage and renderer logic. The frozen fixture is demoted to a regression benchmark. (User choice.)
3. **Ship policy: quality gate, escalate by exception.** Ship automatically only when the deck clears the bar against Richard's references. Otherwise hold and notify a human (you or Richard) with the by-owner punch-list. Autonomous by default, human by exception. (User choice; matches Richard's own QA-below-threshold-to-human-review rule.)
4. **Runner model: async orchestrator that shells out to the renderer environment.** The web service returns 202 immediately, a background job runs the stages, then invokes the renderer plus loop as a subprocess in its own environment, reads the graded result, and posts the outcome to n8n. The orchestrator core is written runner-agnostic so a job queue can replace the subprocess later with no rewrite. (User choice.)

---

## 2. Target architecture

```
n8n / Airtable  --POST /render-->  Live service (returns 202, starts job)
                                        |
                                   Orchestrator (new core, runner-agnostic)
                                        |
                            Preprocessor stages 1..8.5  -->  live package dir (NOT the frozen fixture)
                                        |
                            RenderRunner (subprocess, renderer environment):
                              renderer (treatments on, engine pinned chromium)
                              + quality loop (vision on) composes winning per-page states
                              -->  final report.pdf  +  convergence_report.json
                                        |
                                   Quality gate vs Richard references
                                   /                          \
                          cleared                          below bar
                          ship: upload PDF,                escalate: callback n8n
                          callback n8n done                with by-owner punch-list
                                |                                  |
                          Final PDF to client             You or Richard adds input
```

The orchestrator is the Brain from the parent architecture, scoped to production: it owns the run, the per-page loop, the keep-best memory, the gate, and the ship/escalate decision. The Conductor and Interceptors (perception, analysis, rubric, reference-grounding) already exist in `research/quality_loop` and are invoked, not rebuilt.

---

## 3. Components and interfaces

Each unit has one job and a clean, testable interface.

### 3.1 Orchestrator (new, in the preprocessor service)
The runner-agnostic core. One entry, `run_report_job(request) -> JobOutcome`. It runs the preprocessor stages to a live per-job package directory, hands that directory to the runner, reads back the graded result, applies the gate, and returns a `JobOutcome` (`shipped` with a PDF location, or `escalated` with a punch-list). The async `/render` background task calls this and posts the outcome to n8n.
- Interface in: the `RenderRequest`. Interface out: `JobOutcome`.
- **Fixes infection #1** (`main.py:285,398,460-489`: `/render` never calls the renderer or the grader, confirmed by grep). After `assemble_package` / `route_package`, the orchestrator invokes the runner instead of returning a bare package path.

### 3.2 Render runner (new, the subprocess seam)
A thin adapter behind a `RenderRunner` protocol. The subprocess implementation invokes the renderer in its own environment: package directory in, final `report.pdf` plus `convergence_report.json` out, in a known output directory. A job-queue implementation drops in later without touching the orchestrator. This seam gets the heaviest tests (a fake runner for unit tests plus a real end-to-end smoke test).
- The subprocess invocation **must pin the engine explicitly to chromium** (see addition A) and turn treatments on and vision on.

### 3.3 Live-package wiring (renderer + service)
- The renderer already consumes any package via `--package-dir`; the orchestrated path passes the live directory and never the frozen fixture.
- **Fixes infection #7** (`main.py:460-461` calls `route_package(manifest=None)` while `route_package.py:44` gates all social routing behind `if manifest is not None`, so the live deck has no IG breathers, no testimonial binding, and different diagram placement than the graded fixture). Decision required (see open decision OD-4): either build and plumb a real `AssetManifest`, or explicitly scope social routing out and delete the dead `social_proof` key (`assemble_package.py:297`).
- **Fixes infection #10** (`apply_apex_viz`, AI-scene suppression, and the marble ground exist only in `build_package.py`, not in `/render`). These enrichments move into the shared stages so the live path produces them (see component 3.6).

### 3.4 Compose-fixes into the shipped PDF (quality loop + renderer)
- **Fixes infection #2** (`brain.py:362,462` produces better per-page renders into `PageResult.best_artifacts`, but `build_report` at `stage_converge.py:34-79` never reads them; the shipped PDF is the pre-correction render). Thread `best_artifacts` through `build_report` to a merge step: the assembler re-renders the whole deck once from each page's winning state, or composes each page's best `iter_n/report.pdf`, and that becomes the shipped PDF. Delete the "deferred" note at `stage_converge.py:13-14`.
- Expand the conductor's auto-fix knobs past the single dead-space one where it is safe; route everything the loop cannot fix into the punch-list (see component 3.5).

### 3.5 Grader for A3 and treatment pages, and the quality gate (quality loop)
- **Fixes infection #3** (`render.py:131-132`: `--treatments` skips Stage 9 because the grader compares against A4 references). Make treatment pages gradeable against their own A3 reference layout, or grade them structurally, instead of skipping. Treatments and the grader stop being mutually exclusive.
- **Fixes infection #17** (`rubric.py:165-172`, `analysis.py:361-368`: `positive_max()` sums all positive weights globally, so "cleared" is mathematically unreachable). Compute `positive_max` over only the positives a given `st_type` can earn (per-type maximum) so "cleared" is meaningful.
- **The gate, defined precisely.** A page clears when it has no hard failure and its per-type reward clears the bar. The deck ships when no page has a hard failure, there are no asset or content blockers outstanding, and the deck clears its bar (and the document-coherence pass from the parent architecture §5.4 passes). Otherwise it escalates. Both bars are config values.
- **Escalation payload** is the by-owner punch-list (`flags_by_owner`, grouped renderer / preprocessor / asset_gen): asset and content gaps go to the human to supply; renderer-capability gaps the loop could not fix are flagged separately so we learn what capability to build next.
- **Fixes infection #13** (N15, non-numeral stat content, fires and routes to the preprocessor but has no executor). N15 is the proven anchor for escalate-plus-fix; the spine either adds the executor or escalates by exception.

### 3.6 Parity port (preprocessor stages, all brand-agnostic)
Move every hand edit out of the frozen fixture into stage logic, so the live build of the apex inputs grades at least as high as the frozen fixture (the acceptance test).
- Lift `_SUPPRESS_SLOTS`, the viz curation, and the marble ground from `build_package.py:229-235,277-278,295-325` into the shared `generate_assets` / `route_package` stages, brand-agnostic. The curated apex numbers stay in the fixture (`viz_curation.py` is the documented exemption to the brand-agnostic guard); the LOGIC that applies them is brand-agnostic. (**Fixes infection #10.**)
- Founder image selection, panel and material assets via the AI img2img pipeline, and treatments-on by default also move into the live path.
- **Resolve the chart/viz fork (infection delta #8):** the preprocessor `charts_svg.py` SVG engine is built but fed empty `charts==[]`; the live `viz.jinja` preset layer is fed only by the frozen `apply_apex_viz`; `plan_charts` auto-extraction is deferred. For a non-apex client there is no prose-to-viz path today. The parity port must either wire `plan_charts` so the live path produces viz, or explicitly scope premium viz as apex-only and say so in the gate (a viz-less page is not a hard fail for a non-apex client).

### 3.7 Regression hardening
- **Stale-doc banners (infection #11):** add a banner atop `research/v7-renderer/README.md` and `CHASSIS-NOTES.md` (and the preprocessor README) pointing to the authoritative sources and correcting engine to chromium, fonts to the bundled Source faces, and entrypoint to the multi-page package via `render`. They currently teach WeasyPrint, Montserrat, and a dead entrypoint.
- **Content-hash cache invalidation (infections #4, #5, #6, #12):** see the cache mandate in section 6. This is the single most important fix for your stated "decayed data cached into the code" pain.
- **Demote the frozen fixture (infection #9):** require an explicit `--package-dir` on the live path; the bare `render.py` default to `fixtures/apex` is removed. The fixture becomes a benchmark guarded by the parity test. Delete `.prefal.bak` (restoring it silently reintroduces the ripped-out AI-scene slop).
- **Regenerate the drifted reference index (infection #8):** `references/index.json` axes for apex have ZERO overlap with the live package axes (`mono_blue_cyan_navy / tonal / frosted_glass_geometric / airy` versus `mono_tonal / tonal_same_hue / smooth / compact`), so the grader grounds against pages chosen by a broken metric. Regenerate the index from `decks.py` whenever the axis vocabulary changes, and unify the axis vocabulary (map the DNA densities to the `[compact, balanced, spacious]` ladder). Remove the `REPO_ROOT` absolute-path hardcode at `decks.py:10`.
- **Namespace the output (infection #12):** write `report.pdf` under a per-run or content-hash subdirectory, or clear it at start, so a crash mid-render cannot let the grader read the previous run's PDF.
- **Fix or delete dead scaffolding (infections #14, #15, #18, #19):** tag chart components with a type marker instead of the positional `components[-n:]` slice; warn or error when `brand.font_heading` is a non-bundled family that will be silently dropped; clean up the three leaking `tempfile.mkdtemp` dirs (request-scoped, consumed then deleted); delete or wire the test-only `pipeline.py` graphlib runner, the test-only `drive_client.py` md5 cache, and the producer/consumer-mismatched `process` diagram kind.

**Interfaces that keep these units independent:** orchestrator to runner is one call (`run(package_dir) -> (pdf, report)`); orchestrator to n8n is one callback payload; renderer to loop is "the loop returns each page's winning state, the assembler composes the final"; preprocessor to renderer stays the existing package contract, only now the live one is consumed.

---

## 4. Additions from the verification (beyond the seven parts)

A. **Pin the engine to chromium in the orchestrator.** `render.py:74` defaults the CLI to chromium, but `assembler.render_package`'s function-signature default is still `weasyprint`. The orchestrator must call `render_package(..., engine="chromium")` explicitly; a bare call silently uses the legacy WeasyPrint path, whose folio/header chrome is inert under chromium and whose overflow validator differs. WeasyPrint is legacy fallback only. Grade the chromium output.

B. **Fail loud, never default-mask, on contract gaps.** Remove the `axes` versus `brand_axes` fork that silently defaults `palette / qr_enabled / density` when only the 4-field block is present (`package_loader.py:55`); thread all 7 axes and error on a missing one. Warn on a dropped `font_heading`. Make `layout_variant` a real declared field (it survives only via `extra="allow"` today). Error on a density value outside the ladder instead of restarting from index 0.

C. **Make "cleared" reachable and gate the premium path.** Per-`st_type` `positive_max` (addition to 3.5), and A3/treatment-specific references so the treatments path is graded. An unreachable gate or an ungraded premium path makes escalate-by-exception meaningless.

D. **Resolve the chart/viz fork and the curated-only reality** (folded into 3.6): state which viz engine ships, and that premium viz is fixture-curated-only today, so the parity port either wires `plan_charts` or scopes premium viz as apex-only.

E. **Add copy-fit-budget contract fields** to the preprocessor-to-renderer package (per the PBR-I design): a per-region schematic plus min/target/max character budgets so the renderer can fill regions honestly. This is a package-schema change requiring a fixture re-bake. Without it, "fill the region" regresses.

F. **Define one canonical ST vocabulary and one grading geometry.** Old1 defines 37 page types; the renderer uses about 12 to 16. `_inventory.md` requires both single-A4-portrait and 2-up-landscape-spread export. The gate must grade ONE geometry, or preprocessor and renderer silently disagree. Encode the rule that empty byline fields (`founder_full_name`, `founder_role`, empty for apex by design per `BRAND_TOKENS.md:39`) are valid, not a defect to escalate on.

G. **Make the cache mandate concrete and total** for all four caches (section 6).

H. **Build on existing machinery, not from scratch:** the implementation plan must reference `converge_deck` / `run_deck.py`, `brain.best_artifacts`, `vis_client.score_page`, the 7-field axes loader, and the rubric in the parent design as the foundations the spine wires together.

---

## 5. The grading bar (what "Richard-quality" means to the gate)

Two layers, both already specced, neither to be re-derived here.

1. **The HARD/SOFT design rules (the contract).** `2026-05-16-grammar-contract-reconciliation-matrix.md:850-1463` is the live bar (the RICHARD-PRIMARY re-ratification of 2026-05-18 explicitly STRUCK the earlier apex-contract decisions at L765-836; do not cite those). The HARD rules the gate must enforce, each with a verbatim citation in that block: 3mm bleed; body color `#333333` (not black, not display navy); 2-column Blocksatz with auto-hyphenation; page count in {16, 20, 24, 28}; CTA cadence S2/S9/S18/S20; Atemseite every 5 to 7 pages, never adjacent; at least 20 percent whitespace per page; at most 3 design colors plus neutral; accent at most 10 percent of page AREA plus location-allow-listed; same-family bold; PDF/X CMYK export (Layer 3, deferred). SOFT ranges: headline 28 to 40pt (default 32), pullquote 17 to 20pt, asymmetric margins about 16/20/18/14, about 2 thematic doublespreads per 20-page report (case studies stay single-page).
2. **The operational rubric (the scorer).** The positive P01 to P16 and negative N01 to N14 tables in `2026-06-03-self-correcting-quality-architecture-design.md` §6, derived from the DNA. DET rows gate the loop; VIS rows are reference-grounded composition judgments; DET gates VIS on the fakeable rows; hard-fails latch.

**Flagged contradiction the spine must resolve (open decision OD-1):** the InDesign spec names Montserrat headlines and Source Sans Pro body, but the team extracted serif headlines (Source Serif 4) from the actual reference decks and CURRENT-STATE calls serif "the Richard signal." The reference DECKS are the visual ground truth; the spec font names are the fallback hierarchy. Recommendation: grade against the decks' actual appearance (serif where the decks are serif), treat the InDesign-spec font names as the fallback chain, and confirm with the user. Either way, this is a theme-lock decision made ONCE up front (parent architecture §5.3), not a per-page knob.

---

## 6. Cache-invalidation mandate (the core of your stated pain)

Every cache below is currently keyed in a way that lets decayed data reach the output. The fix is the same pattern everywhere: **the key must contain a content hash of every input that can change the output, including the code/prompt that produces it.**

| Cache | file:line | Today's key (broken) | Required key |
|---|---|---|---|
| fal image cache (#4) | `assets_cache.py:18-22` | `sha256(model, prompt, negative, aspect, resolution)` | add `brand_primary/accent`, the `brand_profile` axes, `client_slug`, a `design_brief` content-hash, and a prompt-builder version. Evict on generator/prompt-template version bump. Purge the 5 stale apex PNGs. |
| restructure (LLM copy) cache (#5) | `restructure_page.py:389-395`, `_PROMPT_VERSION` at `:32` | `sha256(model, st_type, manual _PROMPT_VERSION, 12 raw fields)`; and two physical dirs diverge by CWD | replace `_PROMPT_VERSION` with a hash of `_SYSTEM_PROMPT` plus the schema; add `copy_budget` and the full page `data`. Unify the two cache dirs to one absolute path. |
| VIS-score cache (#6) | `vis_client.py:131-148`, model at `:247` | `sha256(manual PROMPT_VERSION, page_png, ref_pngs, row_ids)`; the model is sent but NEVER hashed | fold `self.model` and a hash of the actual built prompt (plus `_SYSTEM_PROMPT`) into the key; drop reliance on the manual version string. **Highest-value single fix.** |
| output PDF (#12) | `assembler.py:793,804,843`, read by grader at `render.py:56` | reused dir, overwritten by name, no run-id | per-run or content-hash subdir, or clear at start. |

**Principle to encode as a guard:** a cache key that omits the model, the prompt text, or the brand/client inputs is a bug. Add a small test that asserts each cache key includes them (so this class of decay cannot silently return).

---

## 7. Data flow

1. n8n posts `/render` with report data, brand, image manifest, and founder URLs. The brand profile and design brief were produced earlier, out of band, by the async `/onboard` endpoint (open decision OD-3: define which founder-asset path is canonical, the pre-staged `client_assets/<slug>/` or the in-render scrape gated at `main.py:320`).
2. The service validates the request, creates a `job_id`, returns 202, and schedules the background job.
3. The orchestrator runs the preprocessor stages into a per-job working directory, producing the live package.
4. The runner renders and grades in the renderer environment (engine pinned chromium, treatments on, vision on), composes the winning per-page states into the final `report.pdf`, and writes `convergence_report.json`.
5. The orchestrator reads the report and applies the gate. Ship: upload the PDF (storage decision OD-2), call n8n back with the URL. Escalate: call n8n back with the by-owner punch-list.
6. n8n delivers the PDF or notifies the human, and updates Airtable.

---

## 8. Error handling (no human in the normal path)

Every stage already fails closed and never crashes; the orchestrator's job is to tell "degraded but shippable" apart from "real blocker." The render subprocess gets a hard timeout and one retry with captured output, so a renderer crash escalates cleanly instead of hanging (the guardrail memory notes long renders can drop their connection). Jobs are idempotent on report id; the content-hash caches mean a re-trigger never double-charges image generation and a changed package always forces a fresh grade. The n8n callback retries (the `/onboard` pattern), and on final failure the outcome is persisted to disk so nothing is lost. The three leaking temp dirs are cleaned (infection #18).

---

## 9. Testing

- Unit: the orchestrator with a fake runner across the ship and escalate paths; the gate logic against synthetic convergence reports; the per-type `positive_max` fix; each cache key asserted to include model/prompt/brand inputs (the anti-decay guard).
- Seam: a tiny real package through the subprocess (directory in, PDF and report out).
- Parity: the live build of the apex inputs grades at least as high as the frozen benchmark (guards the parity port).
- Grader: an A3 treatment page grades against A3 references without a false flag; an empty-byline page does not escalate.
- Regression: the existing brand-agnostic guard (`test_no_client_name_in_logic`, `test_no_literals_in_architecture`) automatically covers every new module.
- End to end: one real `/render` run (apex inputs) yields 202 then a callback that is shipped or escalated, asserted against the expected outcome.

---

## 10. Open decisions (must be settled during writing-plans or by the user)

- **OD-1 (serif vs Montserrat headlines):** grade against the decks' actual serif appearance, treat the InDesign-spec Montserrat/Source-Sans as the fallback chain. Recommend confirm with user. (Section 5.)
- **OD-2 (storage):** the parent architecture decided Supabase as the data layer (references, runs, page_scores, client-assets, generated-assets, outputs). Use Supabase `outputs/` for the shipped PDF and `runs`/`page_scores` for the audit trail, or a simpler disk-plus-URL for the first cut. Recommend Supabase since it is already decided.
- **OD-3 (founder-asset path):** define the canonical path (pre-staged `client_assets/<slug>/` versus in-render scrape) so the live run is deterministic.
- **OD-4 (social routing):** build and plumb a real `AssetManifest` into `route_package`, or explicitly scope social out for the first cut and delete the dead `social_proof` key. Recommend scope-out for the first working spine, then add the manifest in a follow-on, since social is additive and the gate can pass without it.
- **OD-5 (canonical ST vocabulary and grading geometry):** pick one ST vocabulary and one geometry (single-A4 vs 2-up spread) for the gate. (Addition F.)

---

## 11. Out of scope (named so it is not silently assumed in)

- Layer 3 post-processor: RGB to CMYK, PDF/X-4, true physical-sheet bleed. Deferred (the parent architecture's Layer 3).
- Human-supplied assets that cannot be synthesized: the licensed brand font file (else a bundled top-tier OSS editorial face wired end to end with a loud warning on miss), and the missing real client case-study photos. These are the residual 15 to 20 percent the loop cannot close; the gate flags them, it does not fake them.
- A from-scratch grader, loop, or contract. All three exist; the spine wires and fixes them.
- The Plaud-to-Close automation (`plaud-close-automation/`), confirmed a separate project.

---

## 12. Self-review

- **Placeholders:** none. Every component names a concrete module seam and the infections it fixes carry file:line.
- **Consistency:** the architecture (section 2), components (3), additions (4), grading bar (5), and caches (6) all reference the same units and the same parent design.
- **Brand-agnostic:** section 0 reaffirms it; every gate rule scores a device or relationship or print rule, never a client value; the curated apex numbers stay in `viz_curation.py` (the one documented data exemption), the logic stays brand-agnostic.
- **Honesty:** section 11 states the renderer ceiling and the human-supplied residual plainly; the spine raises consistency to the bar the renderer can express, it does not manufacture a brand font or a real client photo.
- **Scope:** one coherent spine; the open decisions are named, not buried; the build order is left to writing-plans, which will sequence the seven parts plus the eight additions into verifiable phases.
- **No em dashes:** confirmed throughout.
