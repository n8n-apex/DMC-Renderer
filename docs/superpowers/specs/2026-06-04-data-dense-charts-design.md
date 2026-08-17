# Data-Dense Charts — Design

**Date:** 2026-06-04
**Status:** Design for review (author approved direction; no implementation until sign-off).

## 1. Why this exists (the gap)

The honest audit found the single biggest visual-quality gap vs Richard's decks: they are **chart/data-dense**, ours render **0 charts**. The infra is half-built: `models_charts.py` defines 6 chart-spec types, `structure_content.py` extracts a `page["charts"]` list, and `assemble_package` packages it — but **nothing renders it**. Only ST-06 draws a token HTML bar from `page["data"]["bars"]`. So even the `BeforeAfterBars` we already extract sit unrendered. Charts are the highest-leverage remaining lever for "match Richard."

## 2. Decisions (author)
- **Preprocessor-generated SVG:** extend the existing `generate_components` stage to produce DATA-DRIVEN, brand-styled SVG from each page's chart specs; the renderer embeds them like any other component (renderer stays a dumb chassis; reuses the SVG-component pipeline).
- **All six** chart types: `BeforeAfterBars`, `ComparisonColumns`, `Donut`, `LineCompare`, `MoneyInfographic`, `CostMathStrip`.
- **Render + expand extraction together:** build the renderers AND expand `structure_content`'s prose→chart extraction so more pages actually get charts.

## 3. Cardinal rule — NEVER FABRICATE DATA (load-bearing)

Auto-charting prose numbers is exactly where a system invents data. Rules:
- A chart is generated ONLY when the source data UNAMBIGUOUSLY signals that chart (explicit field names / before-after / with-without tokens / parts-of-whole that actually sum). Two unrelated numbers ("50 Kunden / 10 Jahre") must NEVER become a chart.
- Numbers are PARSED from the real copy (German number parser), never computed/estimated/rounded into new values. A `CostMathStrip` shows the operands/result that EXIST in the data; it does not do arithmetic the author didn't write.
- A `Donut` is only produced when the parts are explicitly a breakdown of a stated whole; we do NOT infer percentages that aren't given.
- If extraction is ambiguous → emit NO chart (the prose stays as-is); the N15 flag can still note "this stat could be a chart" for a human. Brand-agnostic: chart styling takes theme colors as PARAMS; no client literals in logic.

## 4. Architecture — three pieces

### 4.1 Chart SVG generator (NEW: `stages/charts_svg.py`)
Pure, deterministic, brand-agnostic. One renderer per spec type + a dispatcher:
```
render_chart_svg(spec: ChartSpec, theme: ChartTheme) -> str   # dispatch on spec.kind
  render_before_after_bars / render_comparison_columns / render_donut /
  render_line_compare / render_money_infographic / render_cost_math_strip
```
- `ChartTheme` = the brand colors already in the package (brand_primary, brand_accent, neutral_light, ink) + a couple of derived tints. Passed in — no hardcoding.
- Output: a self-contained `<svg ...>...</svg>` string sized to a viewBox (the renderer scales it via CSS). Axis-aligned, flat, editorial (matches the deck DNA); no external fonts (use the page font via CSS `currentColor`/inherit where possible, else a generic family).
- Reuses/【supersedes】 the demo `bar_chart()`/`line_chart()` SVG helpers in `generate_components.py` (which currently use hardcoded data).

### 4.2 Extraction expansion (`stages/structure_content.py` + `stages/numbers.py`)
Add CONSERVATIVE, deterministic extractors (each gated on an explicit signal, per §3), beyond the current 2-item before/after bar:
- `ComparisonColumns` ← a `ohne`/`mit` (without/with) two-column structure.
- `Donut` ← an explicit parts-of-whole list (labels + values that sum to a stated/!00% whole).
- `MoneyInfographic` ← items carrying an explicit currency value.
- `CostMathStrip` ← an explicit operands+operator+result structure (no new arithmetic).
- `LineCompare` ← explicit multi-point series (x_labels + series).
Each extractor returns a validated ChartSpec or None; ambiguous → None (no chart).

### 4.3 Generation + package wiring (`stages/generate_components.py` + `assemble_package.py`)
- In Stage 6 (`generate_components_for_report`): for each page that has `charts`, call `render_chart_svg(spec, theme)` per spec → a chart SVG component keyed per page (e.g. `chart_{page_slot}_{i}`), with the brand theme.
- `assemble_package`: write the generated chart SVG components into the package alongside the existing components dict + keep `page["charts"]` (the specs) for provenance. The renderer reads the component(s) for the page.

### 4.4 Renderer integration (`v7-renderer/patterns/*`)
- The host pages: results / mechanism / case-study pages whose specs exist (ST-06 already has a bar; ST-07A case studies where N15 fires; any page with `charts`). Each such pattern embeds its chart SVG component into a designated chart region of the template (the renderer already embeds components).
- Replace ST-06's ad-hoc HTML bar with the real `BeforeAfterBars`/`ComparisonColumns` SVG when a spec is present (fallback to the old token bar if not).
- Brand colors flow from the package (axes/tokens) → already available in `RenderContext`.

## 5. End-to-end chain (target)
```
prose/data → structure_content (extract ChartSpec, conservatively) → page["charts"]
  → generate_components (render_chart_svg per spec, brand theme) → chart SVG component
  → assemble_package (component in package) → renderer pattern embeds SVG → PDF chart
```

## 6. Failure modes & risks (named)
- **Fabrication** (the big one) — mitigated by §3: explicit-signal-only extraction, parse-not-compute, ambiguous→none. Guard tests assert "two unrelated numbers → no chart."
- **German number formats** — reuse the existing `parse_german_number` (. = thousands, , = decimal).
- **SVG in WeasyPrint** — inline SVG is supported; avoid features WeasyPrint can't render (some filters/foreignObject). Verify via a real render (view the pixels).
- **Which pages host which chart** — driven by the spec present on the page + the ST recipe; documented per ST type; no guessing.
- **Visual quality** — first pass is clean/flat/on-brand; refinement (gridlines, value labels, legends) iterated against the rendered output.

## 7. Testing strategy
- `charts_svg.py`: deterministic per-type tests — given a spec + theme, the SVG string contains the expected values/labels/segment counts, uses the theme colors, and is well-formed (parses as XML). No network.
- Extraction: scripted page data → expected ChartSpec or None; explicit NO-FABRICATION tests (unrelated numbers → no chart; ambiguous → no chart).
- Generation/package: a page with charts yields a chart component in the package.
- Renderer: a golden/snapshot or a real render of a chart page; VIEW the rasterized PDF page to confirm the chart appears + is legible (never trust "rendered").
- Brand-agnostic guard extended to `charts_svg.py`.

## 8. Out of scope (deferred)
Interactive/animated charts; 3D; chart types beyond the 6 specs; auto-choosing a chart type the data doesn't signal; per-chart manual art-direction overrides.

## 9. Self-review
- **Scope:** one subsystem (chart specs → rendered SVG) across preprocessor + renderer; bounded by the 6 existing specs.
- **Honest / safe:** the no-fabrication rule is the spec's center; extraction is explicit-signal-only; parse-not-compute; ambiguous→none.
- **Reuses:** `models_charts` specs, `structure_content` + `numbers` parser, the `generate_components` SVG-component pipeline + package wiring, the renderer's component-embed path, brand tokens already in the package.
- **Author decisions captured:** preprocessor-SVG, all six, render+extract together.
