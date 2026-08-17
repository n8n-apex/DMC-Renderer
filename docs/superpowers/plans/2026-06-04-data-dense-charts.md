# Data-Dense Charts — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use `- [ ]`. **NO GIT** (checkpoint = full preprocessor suite green; renderer suite green where touched). Activate venvs: preprocessor `cd research/preprocessor && source .venv/bin/activate`; renderer `cd research/v7-renderer && source .venv/bin/activate` (+ `export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` for rendering). **No network** in unit tests. Brand-agnostic: chart styling takes theme colors as PARAMS — NO client/brand literals in logic (guard test enforced). **NEVER FABRICATE DATA** — see the cardinal rule in the spec §3.

**Goal:** Render all 6 chart-spec types as brand-styled SVG generated in the preprocessor, embedded by the renderer, AND expand prose→chart extraction — so the deck becomes data-dense like the reference.

**Architecture:** new `stages/charts_svg.py` (pure SVG renderers, dispatch on `spec.kind`) → `generate_components` bakes per-page chart SVG from `page["charts"]` specs using the brand theme → `assemble_package` carries the component → renderer patterns embed it. Plus conservative new extractors in `structure_content`. Per `docs/superpowers/specs/2026-06-04-data-dense-charts-design.md`.

**Chart specs (exact fields, from `models_charts.py`):**
- `BeforeAfterBars`: title, unit, before_label, before_value:float, after_label, after_value:float
- `ComparisonColumns`: title, ohne:list[str], mit:list[str]  (qualitative 2-column, NOT numeric)
- `Donut`: title, segments:list[{label, value:float}]
- `LineCompare`: title, x_labels:list[str], series:list[{name, points:list[float]}]
- `MoneyInfographic`: title, currency, items:list[{label, value:float}]
- `CostMathStrip`: title, operands:list[float], operators:list[str], result:float, unit

---

### Task 1 — `charts_svg.py`: ChartTheme + dispatcher + BeforeAfterBars
**Files:** Create `stages/charts_svg.py`; Test `tests/test_charts_svg.py`.

- [ ] **Step 1: failing test**
```python
import xml.etree.ElementTree as ET
from models_charts import BeforeAfterBars
from stages.charts_svg import ChartTheme, render_chart_svg

THEME = ChartTheme(ink="#1A2540", paper="#F5EFE3", primary="#1A2540", accent="#E97E47", muted="#9aa0ad")

def test_before_after_bars_svg_wellformed_and_themed():
    spec = BeforeAfterBars(title="Aufwand", unit="h", before_label="Vorher", before_value=20, after_label="Nachher", after_value=4)
    svg = render_chart_svg(spec, THEME)
    root = ET.fromstring(svg)                      # well-formed XML
    assert root.tag.endswith("svg") and root.get("viewBox")
    assert "Vorher" in svg and "Nachher" in svg     # labels present
    assert "20" in svg and "4" in svg               # values present
    assert THEME.accent in svg                      # uses the theme accent
    # the after bar (4) must be shorter than the before bar (20): compare rect heights/widths
    # (assert two <rect> bars exist with proportional sizes)
    rects = [e for e in root.iter() if e.tag.endswith("rect")]
    assert len(rects) >= 2
```
- [ ] **Step 2: run → FAIL** (`python -m pytest tests/test_charts_svg.py -q`).
- [ ] **Step 3: implement** `ChartTheme` (dataclass: ink, paper, primary, accent, muted, + optional font_family default "inherit") and `render_chart_svg(spec, theme) -> str` dispatching on `spec.kind`. Implement `_before_after_bars(spec, theme)`: a clean two-bar SVG on a fixed `viewBox="0 0 480 320"`, bars proportional to before/after values (guard div-by-zero / None → omit bar), value labels + unit + axis-baseline, accent on the "after" bar, ink on "before", title at top. No external fonts. Return the `<svg>` string. Stub the other 5 kinds to raise `NotImplementedError` for now (filled in T2/T3) OR return an empty themed frame — your choice, but `render_chart_svg` must not crash on a known kind.
- [ ] **Step 4: run → PASS.** Checkpoint: `python -m pytest -q`.

### Task 2 — ComparisonColumns + Donut renderers
**Files:** `stages/charts_svg.py`; `tests/test_charts_svg.py`.
- [ ] Failing tests: `ComparisonColumns(ohne=["A","B"], mit=["X","Y","Z"])` → SVG with two labeled columns, all bullet strings present, ohne column tinted muted/ink, mit column accent; well-formed XML. `Donut(segments=[{label:"A",value:60},{label:"B",value:40}])` → an SVG donut/pie with 2 arcs proportional to 60/40 (assert two `<path>` arc elements + labels + the values; a single 100% segment is a full ring). Div-by-zero (all zero / empty) → a graceful empty themed frame, no crash.
- [ ] Implement `_comparison_columns` + `_donut` (SVG arcs via path `d` with computed angles; pure trig, deterministic). Wire into the dispatcher.
- [ ] Run → PASS. Checkpoint.

### Task 3 — LineCompare + MoneyInfographic + CostMathStrip renderers
**Files:** `stages/charts_svg.py`; `tests/test_charts_svg.py`.
- [ ] Failing tests: `LineCompare(x_labels=["Q1","Q2","Q3"], series=[{name:"A",points:[1,2,3]},{name:"B",points:[3,2,1]}])` → SVG with 2 `<polyline>`/`<path>` lines, x labels, a legend with series names, themed colors (primary + accent), well-formed. `MoneyInfographic(currency="€", items=[{label:"Setup",value:5000},{label:"Monat",value:900}])` → SVG with each item's label + `€`-prefixed value, bars/figures proportional. `CostMathStrip(operands=[3,4], operators=["×"], result=12, unit="h")` → SVG strip showing `3 × 4 = 12 h` as styled tiles (NO arithmetic done in code — render the given operands/result verbatim). Empty/None → graceful frame.
- [ ] Implement the three renderers; wire into the dispatcher. Now every `spec.kind` renders.
- [ ] Run → PASS. Checkpoint.

### Task 4 — Extraction expansion (conservative, NO-FABRICATION)
**Files:** `stages/structure_content.py`, `stages/numbers.py` (helpers), `models_pagedata.py` if needed; Test `tests/test_structure_content_charts.py` (extend existing).
- [ ] Failing tests FIRST, including the NO-FABRICATION guards:
  - `ComparisonColumns`: page data with an explicit `ohne`/`mit` (without/with) structure → a ComparisonColumns spec. Without those keys/tokens → None.
  - `Donut`: an explicit parts-of-whole list (e.g. `data["breakdown"]` or a list whose values are labeled shares) → a Donut spec. A plain list of unrelated numbers → None.
  - `MoneyInfographic`: items each carrying an explicit currency value → a MoneyInfographic. No currency signal → None.
  - `CostMathStrip`: an explicit operands+operator+result structure → a CostMathStrip (verbatim; no computed result). Absent → None.
  - **Guard:** two unrelated numbers ("50 Kunden", "10 Jahre") → NO chart of any kind. Ambiguous → None. (Assert `structured.charts == []`.)
- [ ] Implement the extractors in `structure_content` (each gated on an explicit field/token signal; parse via `parse_german_number`; never compute new values; ambiguous → None). Keep the existing BeforeAfterBars extractor working.
- [ ] Run → PASS. Checkpoint.

### Task 5 — Generation + package wiring
**Files:** `stages/generate_components.py`, `stages/assemble_package.py`; Tests extend `tests/test_generate_components.py` + `tests/test_assemble_package.py`.
- [ ] Failing tests: `generate_components_for_report` (or a new helper) — given pages where a page has `charts` (StructuredPage.charts), produce a chart SVG component per spec, keyed deterministically per page (e.g. `chart_{page_slot}_{i}`), built via `render_chart_svg(spec, ChartTheme(<brand tokens>))`. The brand tokens (brand_primary/brand_accent/brand_neutral_light/ink) come from the existing args. `assemble_package`: the chart component(s) appear in the package's components for that page; `page["charts"]` (specs) still present for provenance.
- [ ] Implement: build `ChartTheme` from the brand tokens already passed to `generate_components_for_report`; for each page's charts, render + register the SVG component. Ensure `assemble_package` writes them. Replace the demo `bar_chart()`/`line_chart()` hardcoded-data helpers' USE with the data-driven path (keep or delete the demo helpers as appropriate).
- [ ] Run → PASS. Checkpoint: full preprocessor suite.

### Task 6 — Renderer integration (embed on host pages)
**Files:** `research/v7-renderer/patterns/*.py` (the chart-host ST patterns, e.g. `st_06.py`, `st_07a.py`, and any results page), their templates, `patterns/_components.py`/base if needed; renderer tests.
- [ ] Read how a generated SVG component is embedded today (the components dict on the page / `RenderContext`); find the existing ST-06 HTML `bar_chart.jinja` usage. Failing test: a page carrying a chart component renders an `<svg>` (or the component) into the page fragment (assert the fragment HTML contains the chart svg / component marker). 
- [ ] Implement: in each chart-host pattern, embed the page's chart SVG component into a chart region of the template. For ST-06, prefer the real `BeforeAfterBars`/`ComparisonColumns` SVG component when present, falling back to the existing token bar otherwise. Keep non-chart pages unchanged.
- [ ] Run → PASS. Checkpoint: renderer test suite green; preprocessor suite green.

### Task 7 — Real render verification (VIEW the pixels)
- [ ] Add/curate a fixture page (or reuse the apex fixture) that carries at least one chart spec of 2–3 types; rebuild the apex package (`build_package.py`) and render (`render.py`). 
- [ ] **VIEW the rasterized chart page PNG(s)** — confirm the chart(s) actually appear, are legible, on-brand, and not clipped (never trust "rendered"). Iterate on `charts_svg.py` geometry/labels against what you see.
- [ ] Checkpoint: full preprocessor suite + renderer suite green; clean up any one-off scripts; restore any mutated fixture.

---

## Self-review
- **Spec coverage:** SVG renderers for all 6 specs (T1–T3), conservative extraction + no-fabrication guards (T4), generation+package wiring (T5), renderer embed (T6), pixel verification (T7). All cite the spec.
- **No fabrication:** T4 has explicit guard tests (unrelated numbers → no chart; ambiguous → None; parse-not-compute; verbatim CostMathStrip).
- **Brand-agnostic:** ChartTheme colors are params; guard extended to `charts_svg.py`.
- **Type consistency:** `ChartTheme` + `render_chart_svg(spec, theme)` defined T1, used unchanged T2/T3/T5; exact `models_charts` field names used throughout.
- **Reuse:** `models_charts` specs, `structure_content`+`numbers`, `generate_components` pipeline + package wiring, renderer component-embed path, brand tokens.
- **Verify-the-pixels:** T7 requires viewing the rendered chart, not trusting test green.
