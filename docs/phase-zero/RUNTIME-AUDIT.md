# Phase Zero Runtime Audit

Date: 2026-08-03

Status: Evidence complete. This document describes the executable system, not the intended architecture in older specifications.

## Executive verdict

The project is not an empty skeleton. It has a substantial preprocessor, asset pipeline, component library, Chromium renderer, treatment layer, test suite, and PDF flattening pass. The failure is architectural: many capable parts do not share one strict contract or one definition of ready.

The current chain can produce a polished-looking PDF while all of these facts remain true:

- The requested page count is not satisfied.
- Five required client portraits are missing.
- Two case studies have no adjacent theory page.
- A source value has no surviving claim provenance.
- Copy-fit measurements are inflated by adapter aliases.
- The flattened delivery PDF has no searchable text layer.
- Twenty-two warnings and five data-QC hard failures do not block shipment.

The system is therefore a capable prototype with permissive failure behavior, not a robust production report compiler.

## Evidence base

This audit uses four kinds of evidence:

1. The 120-face reference atlas at `research/reference-atlas/`.
2. Direct call-path inspection from `dmc-renderer/build_live.py` through the preprocessor and renderer.
3. A fresh Christopher v5 build stored at `research/phase-zero-evidence/christoph-v5-current/`.
4. Fresh targeted tests covering the adapter, preprocessor, treatment wiring, renderer guards, and contract fixes.

Older root documents were treated as historical hypotheses when they contradicted current executable behavior. In particular, `context.md` mixes the retired WeasyPrint path with the current Chromium path and describes the postprocessor differently from the implementation.

## Reference contract discovered from Richard's six reports

The six source PDFs contain 84 PDF objects but 120 physical A4 faces. Four reports use A3 spreads, so PDF object count is not physical face count.

All six reports have exactly 20 physical faces and exactly three case studies. Stable editorial roles are:

- Cover
- Outlook or expectation setting
- About or authority
- Status quo or problem frame
- False beliefs
- Exactly three case studies
- At least two theory or interpretation pages
- Summary
- Objections
- Collaboration
- Final CTA

An explicit mechanism page appears in five of the five Richard-editorial reports and is absent from Apex. A dedicated trust page is not universal, but trust evidence is universal.

The corpus contains 35,550 extracted words. The mean is 296.2 words per physical face and the median is 304. Regular content faces average 319.5 words. The fresh Christopher artifact contains 2,508 words across 18 A4-equivalent faces, or about 139.3 words per face. Richard's references therefore contain about 2.1 times more words per face.

This disproves the initial diagnosis that the system's main problem is simply too much text. The stronger diagnosis is poor allocation: low-density copy is repeated across weak composition families, while missing proof assets and underused visual mechanisms make the pages feel text-heavy.

## Actual runtime chain

```text
n8n envelope
  -> adapter and dialect normalization
  -> input and brand validation
  -> copy validation and copy-fit estimates
  -> content structuring and visual synthesis
  -> slot resolution, asset generation, component generation
  -> advisory layout plan
  -> permissive package assembly
  -> partial routing
  -> treatment selection plus legacy pattern fallback
  -> Chromium PDF
  -> inline Ghostscript flattening
  -> advisory overflow and data-QC results
  -> HTTP response
```

The live entry point is `dmc-renderer/service.py`. It calls `dmc-renderer/build_live.py`, which performs both input adaptation and orchestration. The package is rendered by `research/v7-renderer/assembler.py`.

## Fresh Christopher execution

Artifacts:

- Input fixture: `dmc-renderer/fixtures/christoph_v5_payload.json`
- Resolved package: `research/phase-zero-evidence/christoph-v5-current/pkg/resolved_package.json`
- Raw Chromium PDF: `research/phase-zero-evidence/christoph-v5-current/render/report_print.pdf`
- Flattened delivery PDF: `research/phase-zero-evidence/christoph-v5-current/render/report.pdf`
- Contact sheet: `research/phase-zero-evidence/christoph-v5-current/contact-sheet.png`

Observed facts:

| Fact | Result |
|---|---:|
| Source target | 23 |
| Adapter target | 24 |
| Logical page objects | 17 |
| PDF objects | 17 |
| A4-equivalent faces | 18 |
| Case studies | 5 |
| Preprocessor warnings | 22 |
| Missing required portraits | 5 |
| Data-QC hard failures | 5 |
| Generated SVG components | 1 |
| Assembler warnings | 0 |
| Overflow flags | 0 |
| Raw PDF extracted words | 2,508 |
| Flattened PDF extracted words | 0 |

The adapter silently snaps 23 to 24 because only 16, 20, 24, and 28 are accepted. Validation then accepts 17 page objects because it validates the target value but does not require the array length to equal the target. It also accepts five case studies because the current rule is at least three, while every reference contains exactly three.

The ship gate compares 17 rendered PDF objects with 17 render fragments. That proves no fragment spilled into an extra PDF object, but it does not prove that the planned face count was achieved. The A3 spread also means that the output contains 18 A4-equivalent faces, not 17 physical faces.

## Preprocessor findings

### 1. The adapter is a second schema and a second author

`dmc-renderer/build_live.py` normalizes multiple field dialects, restores aliases, injects authors, reassigns case numbers, fills theory pages, maps images, snaps page targets, and hardcodes product routing. This is not a thin compatibility layer. It owns editorial and semantic decisions that should belong to an explicit planning stage.

The normalization creates duplicate aliases such as `titel` and `title`, `einleitung` and `body`, and `schritte` and `steps`. Recursive character counts in the normalized Christopher data are inflated by about 1.3 to 2.1 times. Copy validation and copy-fit then inspect both aliases, creating duplicate warnings and distorted capacity estimates.

### 2. The models validate shape more than meaning

`research/preprocessor/models.py` permits extra fields and represents page data as a free-form dictionary. `research/preprocessor/models_pagedata.py` makes almost every ST field optional, permits extras, and falls back instead of rejecting malformed page data. `research/preprocessor/models_package.py` forbids unknown top-level package fields but permits unknown page fields and untyped charts, assets, and components.

The package can therefore be structurally valid while lacking:

- Editorial argument
- Narrative role
- Source claim linkage
- Proof completeness
- Asset provenance and rights
- Density target
- Composition family
- Region capacity
- Required visible elements
- Cadence transition
- Confidence and fallback policy

### 3. Visual synthesis is numerically shallow

`research/preprocessor/stages/synthesize_visuals.py` verifies that numeric tokens used in generated structures occur somewhere in the page text. It does not prove that the selected label, unit, denominator, time period, or claim context belongs to that number. A number can therefore be grounded syntactically but attached to the wrong meaning.

The writer prompt also encourages two to four kinds of visual material on a strong page. The atlas shows a different pattern: most successful pages use one dominant reading mechanism supported by minor secondary devices.

### 4. The asset system confuses absence with permission to substitute

The slot registry covers cover, about, case, status, conclusion, and breather assets. It does not express the full reference vocabulary, including theory diagrams, mechanism artifacts, evidence screenshots, review walls, source blocks, and QR proof.

Five case portraits are marked `missing_required` in the fresh package. The pipeline still generates or routes contextual and product visuals. This improves surface finish but does not satisfy identity or proof requirements. Asset class substitution is not prohibited.

### 5. Built capability is not the same as live capability

The social planner has substantial deterministic routing logic and tests, but the live caller passes `manifest=None`, so it never executes. Three component builders, `curved_arrow_flow`, `paired_comparison`, and `venn_diagram`, are exercised only by tests and are unreachable from production dispatch.

`plan_diagrams.py` describes a broader detector system, but the active detector list only supports convergence over an existing visual and a generic stat callout. It cannot create the process, comparison, or question-and-answer range implied by its design.

## Composition and renderer findings

### 1. Layout planning does not solve layout

`research/preprocessor/stages/plan_layout.py` maps ST types to legacy CSS patterns and emits advisory warnings. Its density model mostly distinguishes breather pages from everything else. It does not measure the capacity of individual regions, select the dominant mechanism from evidence, or backtrack when a family cannot fit.

The planner also recommends breathers and dark dividers more aggressively than the reference corpus supports. Most Richard reports contain 18 to 20 light faces. Niklas is the outlier with frequent dark resets.

### 2. Treatment breadth is advertised but not implemented

The treatment catalog exposes 16 descriptors, but only six have dedicated template and CSS pairs. The fresh output uses three treatment types plus legacy patterns. Ten catalog entries are metadata-only or resolve through generic presentation.

Treatment selection relies primarily on ST type, required field presence, page format, repetition, and adjacency. It does not receive editorial argument, evidence completeness, asset class, measured capacity, or cadence goals. This produces syntactic variety rather than reasoned art direction.

### 3. Silent fallback hides incomplete work

The assembler catches pattern and treatment errors and falls back to generic or legacy output. Package routing is also best-effort. This keeps builds alive during development, but the same behavior exists in the shipping path. A production export can therefore conceal a failed premium composition.

### 4. Final-pixel validation is incomplete

The current checks detect extra PDF objects, bare Python singleton leaks, container representations, and some raw DOM height overflow. They do not prove that every required element is visible, unclipped, non-overlapping, legible, or semantically correct.

The accent-budget validator is a stub. The older closed quality loop is calibrated to the WeasyPrint path and is not invoked by the current HTTP service. There is no single path that renders the premium deck and grades that exact artifact against the Richard reference system.

## Ship gate findings

`dmc-renderer/service.py` labels missing portraits as `hard_fails`, but strict HTTP rejection only blocks overflow, content leaks, or grader errors. Missing required assets are returned as headers and metadata while the PDF still ships.

There is no explicit state machine for:

- Rejected
- Draft with known degradation
- Review candidate
- Ship ready

As a result, warnings, stubs, fallbacks, and missing proof all share one successful response path.

## Postprocessor findings

Ghostscript flattening is embedded inside the renderer. It writes PDF 1.3 using the printer preset and returns the raw Chromium PDF if Ghostscript fails.

The fresh artifact proves a material information loss:

- The raw PDF contains 2,508 extractable words and 337 font references.
- The flattened delivery PDF contains zero extractable words and zero font references.

Flattening removes search, selection, copy, accessibility, and future tagging potential. It is not a neutral print preflight.

The current postprocessor does not provide:

- A preserved digital PDF
- PDF/X conformance
- Output intent or ICC profile
- Printer-specific color conversion
- Total area coverage checks
- Bleed and crop-mark policy
- Tagged accessibility
- Link preservation
- Metadata validation

## Tests and specification drift

Fresh targeted verification produced:

- Contract harness: 10 of 10 passed.
- Renderer guard battery: 45 passed.
- Treatment and wiring tests: 40 passed, 1 skipped.
- Preprocessor architecture tests: 134 passed.

This is 219 passing targeted tests, 1 skipped test, and a separate 10-of-10 contract harness. The full suite was not rerun during Phase Zero, so the July count must not be presented as current.

Green tests do not prove reference fidelity. `research/preprocessor/tests/test_validate_input.py` explicitly requires five case studies to pass and rejects an exactly-three rule. The six references show exactly three cases in every report. The test suite therefore protects at least one stale product assumption.

## Root causes

The failures collapse into seven root causes:

1. No canonical unit for a page, face, spread, fragment, or PDF object.
2. No immutable evidence ledger connecting source material to claims and visuals.
3. No strict frozen render contract between planning and rendering.
4. No capacity-aware composition planner with bounded alternatives.
5. No provenance-aware asset ledger or semantic substitution policy.
6. No blocking ship-state gate over the exact delivered artifact.
7. No separate digital and print export contracts.

These are system-design failures. More templates, prompts, or generated decoration will not fix them until the authority boundaries and contracts are corrected.
