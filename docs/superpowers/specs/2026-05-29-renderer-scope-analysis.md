# Renderer (Layer 2) — Scope & Gap Analysis (pre-build)

**Status:** Analysis (feeds the renderer brainstorm → spec → plan → build)
**Date:** 2026-05-29
**Component:** `research/v7-renderer/` (the chassis / WeasyPrint compositor)
**Purpose:** Map the renderer's real state + the pre-processor↔renderer↔post-processor contract, enumerate every open loop, and flag every upstream/downstream impact BEFORE building. No code yet.

---

## A. Three-layer architecture (from the chassis's own CHASSIS-NOTES)

```
Layer 1 — PRE-PROCESSOR (DONE)        Layer 2 — RENDERER (this)        Layer 3 — POST-PROCESSOR (absent)
ingest payload, validate copy,        take a PRE-RESOLVED PACKAGE,     RGB→CMYK (ISO Coated v2 300%),
resolve fonts, plan layout,           apply CSS page templates         PDF/X-4 intent, TrimBox/BleedBox,
SVG components, AI images (fal)        (Layer-A patterns) → RGB PDF     veraPDF compliance
```

The chassis is **designed to consume a pre-resolved package** — i.e. our `resolved_package.json`. The seam is intended; it is simply **not wired** (see §C-1). The chassis explicitly does NOT do Layer-1 work (image gen, SVG geometry, copy validation) or Layer-3 work (CMYK). Those boundaries are firm.

## B. Current renderer state (verified by reading)

| Piece | State |
|---|---|
| `render.py` | **Single-page proof harness.** Hardcoded to read `v7-test/fixture_mw_geva.json`, asserts exactly **1 page** of type **ST-07A**, dispatches to `render_lrp`, WeasyPrint→PDF, accent-budget validate, PyMuPDF rasterize. Has produced a real `output/geva.pdf`. |
| `brand_tokens.py` | **Done + aligned.** `BrandConfig` = the exact 10 fields the pre-processor's `BrandTokensResolved` emits. `resolved_package.json["brand"]` feeds `parse_brand_tokens` with zero changes. |
| `grammar_loader.py` | **Done.** Source-of-truth gate (ratified `richard-grammar-v2.md`); `get_section()` fail-loud. 11 contract tests green. |
| `chassis_config.py` | **Done.** Per-element anti-pattern toggles (rounded corners / shadows). |
| `preprocess.py` | **Done.** Body markdown→HTML + WeasyPrint hyphenation. |
| `patterns/st_07a.py` | **The only real pattern** (592 LOC). Returns a **complete single-page HTML document** (own `@page`, `@font-face`, brand CSS-vars, table-layout columns, background-image photo, inline QR SVG). |
| `patterns/st_{01,02,03,05,06,07b,09,14,22,fazit}.py` | **10 one-line stubs.** |
| `patterns/st_{08,31,32}.py` | **MISSING entirely** (no file) — yet the pre-processor's `ST_TO_TEMPLATE` maps these. |
| `validators/accent_budget.py` | Real-ish (144 LOC) but **rasterization is a stub** (`passed=True`). |
| `validators/{overflow,contrast}.py` | **Stubs** (8–10 LOC). |
| `shared/components`, `shared/css` | **Empty dirs.** |
| `fonts/` | 4 variable fonts present (Montserrat + Source Sans 3) — matches chassis-default. |
| `fixtures/apex/` | The package we just generated (real images + `resolved_package.json`). The intended new render input. |

## C. Open loops (contract mismatches) — the must-fix list

1. **INPUT CONTRACT MISMATCH (the central loop).** `render.py` reads the GEVA fixture shape (`payload.pages` + `images` + `brand_tokens`). The pre-processor emits `resolved_package.json` (`brand` + `fonts` + `pages[].{data,assets,components,cover_validation}` + `report_assets` + `validation`). → The renderer needs a **package loader** that consumes `resolved_package.json` and resolves its relative asset/component/font paths against the package dir.

2. **SINGLE-PAGE → MULTI-PAGE.** `render.py` hardcodes 1 ST-07A page. The target is a 16/20/24/28-page report. → Walk all `pages`, dispatch each to its pattern, assemble one multi-page document.

3. **PATTERN INTERFACE.** `render_lrp` returns a *full* HTML doc (its own `<html><head><@page>`). Multi-page can't concatenate full docs. → Define ONE uniform pattern interface: each pattern returns a **page fragment** (the page's body markup + scoped CSS); a **shared head** (`@page` A4+bleed+folio, `@font-face`, brand CSS-vars, body rules, `break-after:page`) is assembled ONCE. `st_07a` must be refactored from full-doc to fragment to match.

4. **PATTERN COVERAGE GAP.** Patterns exist for 11 of the 14 ST types the pre-processor produces. **`ST-08`, `ST-31`, `ST-32` have no pattern file at all.** → Reconcile the build set against the grammar slot plan; create the missing files.

5. **PER-PATTERN DATA CONTRACT.** Each pattern needs specific `data` keys (e.g. ST-07A wants fallstudie fields). The pre-processor passes `page.data` **verbatim/free-form**. There is no schema tying a pattern's expected keys to what the report JSON provides. → Each pattern must (a) document its expected `data` keys and (b) **degrade gracefully** when keys are missing (render skeleton, not crash). This is the renderer-side robustness rule.

6. **MISSING PACKAGE FIELDS the patterns need (UPSTREAM impact).** `assemble_package`'s page manifest carries `slot, st_type, css_template, has_cta, data, assets, components, cover_validation` — but **not `page_numbers`** (which `render_lrp` uses) nor chapter labels. → **Controlled additive change to the pre-processor** (`assemble_package` + the `PlannedPage`/manifest) to include `page_numbers`. Additive → won't break the pre-processor's 210 tests.

7. **`cover_validation.headline_size_class` not consumed.** It's in the package (per cover page) precisely so the cover pattern sizes the headline (short→36-44pt / long→24-30pt). → The ST-01 pattern must read it.

8. **`report_assets` (texture / gradient) application undefined.** The package carries report-level background texture + atmospheric gradient, but nothing says how a page applies them. → Define the rule (e.g. page background per grammar ground-mode axis `G`), driven by data not hardcoded.

## D. Upstream impact (pre-processor) — addressed, not ignored

- **Add `page_numbers` (and optional chapter label) to the package page manifest** (§C-6). Additive; covered by a new assemble_package test. No behavior change to existing fields.
- Everything else aligns: `brand` → `parse_brand_tokens` (exact), `fonts` (chassis-default present on disk), `assets`/`components` relative paths (portable by design), `cover_validation` per page. **No breaking change to Layer 1.**
- The pre-processor and renderer are separate venvs/services — building the renderer touches pre-processor code ONLY for the additive field above.

## E. Downstream impact (post-processor) — none today

- Layer 3 does not exist. The renderer's **RGB PDF is the terminal artifact** for now. Building the renderer breaks no downstream (there is none). Layer-3 (RGB→CMYK, PDF/X-4) remains a future, separate build. The renderer must emit a clean RGB PDF that a future Layer 3 can consume (standard WeasyPrint output — already the case).

## F. Validators — scope decision needed

- `accent_budget` (stub rasterization), `overflow`, `contrast` are stubs; whitespace ≥20%, ≤3-colours, atemseite-rhythm, CTA-Kadenz are unimplemented. → For a first real multi-page render, **`overflow` matters most** (does content fit each page?). Recommend: keep accent/contrast/whitespace as stubs for v1; decide whether to implement real `overflow` now or defer. (Pre-processor Stage 7 already checks structural rhythm/CTA cadence, so those needn't be re-done in the renderer.)

## G. Content dependency (for meaningful TDD output)

- The apex `resolved_package.json` has a **rich ST-01 cover** but mostly **empty `data: {}`** on interior pages (it reused the sample report structure). → A full render shows a real cover + skeleton interiors. To exercise all patterns with real content, we need a **content-rich report fixture** (real per-page `data`). Options: (a) build patterns to render skeletons from empty data now + enrich later, or (b) author a richer apex content fixture. The images + brand are already real (the hard part); page text is the remaining input.

## H. No-open-loops closure (every package field → consumer)

| Package field | Renderer consumer |
|---|---|
| `brand` (10 fields) | `parse_brand_tokens` → CSS vars (all patterns) |
| `fonts.{heading,body}.path` | shared `@font-face` (resolve relative → package fonts/) |
| `pages[].st_type` | dispatch → pattern module |
| `pages[].css_template` | (informational; pattern is keyed by st_type) |
| `pages[].data` | the pattern's content fields (per-pattern contract, §C-5) |
| `pages[].assets[].path` | `<img>` / `background-image` (resolve relative) |
| `pages[].components[]` | inline SVG embed |
| `pages[].cover_validation.headline_size_class` | ST-01 headline sizing (§C-7) |
| `pages[].has_cta` | CTA element rendering on the page |
| `report_assets[]` (texture/gradient) | page background per ground-mode (§C-8) |
| `page_numbers` (**to add**, §C-6) | `@bottom-left` folio |
| `validation`, `asset_summary`, `design_brief` | **NOT renderer inputs** (QA/Layer-1 metadata) — explicitly out of scope, no loop |

## I. Proposed build schema (same as the pre-processor)

1. **Brainstorm** (decisions: pattern interface = fragment+shared-CSS; the exact pattern build set incl. ST-08/31/32; content-fixture vs skeleton; overflow-validator scope; the package loader).
2. **Spec** (the package-loader contract, the pattern interface signature, per-pattern data contracts, the shared CSS module, the multi-page assembler, the `page_numbers` upstream add).
3. **Plan** (TDD, task-per-pattern + loader + assembler + the st_07a refactor).
4. **Build** (opus subagents, fresh per task) → verify: renderer pytest GREEN (keep the 11 contract tests + no-coral guard), a **real multi-page render of the apex package → PDF**, plus the pre-processor's 210 + additive test still green.
5. **Review** (independent) + visual inspection of the rendered PDF.

## J. Risks / guarantees

- **Non-disruption:** Layer 1 changes limited to one additive field (`page_numbers`); its 210 tests stay green. Renderer keeps its 11 contract tests + the `test_no_coral` guard green. No Layer-3 to disturb.
- **Brand-agnostic:** the renderer is already hue/client-agnostic (verified); the build must keep it so (the `test_no_coral` guard enforces it).
- **Biggest unknowns:** (1) WeasyPrint multi-page fidelity across 10 new patterns; (2) content-fixture richness; (3) how faithfully CSS can hit Richard's Layer-A geometry for each pattern (only ST-07A is proven).
