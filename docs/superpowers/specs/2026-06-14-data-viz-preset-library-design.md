# Premium Data-Viz Preset Library — Design

**Date:** 2026-06-14
**Status:** Approved (preset set + curated-first data approach locked by user)
**Topic:** A brand-agnostic library of ~15 premium, Chromium-grade data-visualization "presets" for the report renderer, fed (initially) by hand-curated, verbatim client data, so the APEX deck visualizes its numbers instead of printing them as flat text.

---

## 1. Problem

The deck has *layout* devices (panels, callouts, one Venn) but almost no **true data-visualization** — graphics whose shape/size encodes a value. Forensics + a verified inventory established:

- **The deck renders exactly one diagram** today (the convergence Venn on p5).
- **The existing chart engine is 100% dormant + flat.** `research/preprocessor/stages/charts_svg.py` has 6 renderers (`before_after_bars`, `comparison_columns`, `donut`, `line_compare`, `money_infographic`, `cost_math_strip`) wired into `ST-06`/`ST-07A` via `RenderContext.chart_svgs()` — but **every APEX page's `charts` array is empty `[]`** (`structure_content` never extracted a spec), so it produces zero pixels. It also draws **flat** SVG (plain rects, no gradient/glow), well below Richard's bar even if fed.
- **68 visualizable data points** sit in the content as flat text/stat strings: 11 before/after, 23 proportions, 18 counts, 6 ranges, 4 money, 4 process timelines, 1 comparison (the Venn), 0 trend.

Richard's decks back **every** claim with a chart drawn at material quality: gradient fills that deepen at overlaps, soft wide ambient shadows, glowing display-serif numerals, dark-glass panels, ghost watermarks. The gap is the **data-viz device layer itself** + the chroma/depth to make it read.

## 2. Goal

Build a reusable library of named **premium viz presets** — Chromium-grade, brand-agnostic, token-only — and a single dispatch macro that mirrors the existing `diagram.jinja` proof-layer. Feed it on APEX with **hand-curated, verbatim** data (no fabrication). Wire it into the host patterns that carry real data. Result: a sendable APEX deck where the strongest proof points (case-study transformations, market stats, the engagement timeline) are visual.

The auto-extraction brain (a `plan_charts` preprocessor stage, sibling to `plan_diagrams`) is **explicitly deferred** — this design makes it a clean follow-on, not a prerequisite.

## 3. Non-Goals / Honest Boundaries

- **No fabrication, ever.** A preset renders only verbatim figures the curator supplies from real copy. Numeric values used for geometry (bar height, arc sweep) must agree with the displayed verbatim figure string. A preset with missing/empty data renders nothing (graceful omit).
- **No interactive-only or multi-dimensional visuals** that APEX has no honest data for: scatter/bubble, radar/spider, treemaps, decomposition trees, slicers, filled maps. Excluded by design.
- **Data-dependent presets ship dark on APEX:** `waterfall` (needs additive components), `funnel` (needs stage quantities), `line`/`area`/`combo` (need a time series — APEX has 0 trend points). Built into the library contract space but **not** built/curated in this phase; noted as future when real data exists.
- **The flat `charts_svg.py` engine is left untouched and dormant.** We do not force premium through its flat SVG path. It can be retired in a later cleanup; out of scope here.
- Brand font (`Gestura Headline`) remains unbundled; numerals use `var(--font-head)`/`var(--font-display)` which falls back to Source Serif. Bundling the OFL display face is a separate, already-tracked item.

## 4. Architecture

Mirrors the proven **diagram proof-layer** exactly (`components/diagram.jinja` → `concept_diagram.jinja` etc., decided by `plan_diagrams`, applied to `data['diagram']`, rendered by host patterns). The viz layer is the same shape, one level richer:

```
fixture (CLIENT DATA)                renderer (BRAND-AGNOSTIC)
─────────────────────                ─────────────────────────
build_package.py                     components/viz.jinja         ← dispatch (switch on preset)
  apply_apex_viz(pkg)        ───►    components/viz_*.jinja       ← one macro per preset family
  writes data['viz'] = [ {preset, …}, … ]   styles/viz.css       ← premium depth CSS (tokens only)
  (verbatim APEX numbers)            patterns/st_*.py + templates ← host reads data['viz'], renders dispatch
```

**Separation of concerns (matches existing discipline):**
- **Renderer = brand-agnostic.** `viz.jinja`, `viz_*.jinja`, `viz.css`, host wiring contain ZERO client literals — no hex, no font family, no client name, no APEX numbers. Colors via tokens + `color-mix`. Guard tests already ban client tokens in renderer logic; the new files must pass them.
- **Fixture = client data.** The actual APEX numbers live only in the curation step under `fixtures/apex/`. Verbatim from copy.

### 4.1 Data contract

`data['viz']` is a **list** of viz specs (a page may carry more than one). Each spec is a dict with a `preset` discriminator + preset-specific fields. The dispatch macro loops the list and renders each in document order within the host's viz zone. Single-viz pages carry a 1-element list. Empty/absent → nothing renders.

```jinja
{# components/viz.jinja — single dispatch entry point, mirrors diagram.jinja #}
{% from 'viz_transform.jinja' import ba_bars, transform_arrow, completion_ring %}
{% from 'viz_proportion.jinja' import donut, split_bar, gauge, radial_cluster, icon_array %}
{% from 'viz_magnitude.jinja' import stat_strip, money_bar, mega_numeral, kpi_card, ranked_bars %}
{% from 'viz_process.jinja' import phase_timeline, step_cascade %}

{% macro viz(specs) %}
{%- if specs -%}
  {%- for v in specs if v and v.preset -%}
    {%- if   v.preset == 'ba_bars'        -%}{{ ba_bars(v) }}
    {%- elif v.preset == 'transform_arrow'-%}{{ transform_arrow(v) }}
    {%- elif v.preset == 'completion_ring'-%}{{ completion_ring(v) }}
    {%- elif v.preset == 'donut'          -%}{{ donut(v) }}
    {%- elif v.preset == 'split_bar'      -%}{{ split_bar(v) }}
    {%- elif v.preset == 'gauge'          -%}{{ gauge(v) }}
    {%- elif v.preset == 'radial_cluster' -%}{{ radial_cluster(v) }}
    {%- elif v.preset == 'icon_array'     -%}{{ icon_array(v) }}
    {%- elif v.preset == 'stat_strip'     -%}{{ stat_strip(v) }}
    {%- elif v.preset == 'money_bar'      -%}{{ money_bar(v) }}
    {%- elif v.preset == 'mega_numeral'   -%}{{ mega_numeral(v) }}
    {%- elif v.preset == 'kpi_card'       -%}{{ kpi_card(v) }}
    {%- elif v.preset == 'ranked_bars'    -%}{{ ranked_bars(v) }}
    {%- elif v.preset == 'phase_timeline' -%}{{ phase_timeline(v) }}
    {%- elif v.preset == 'step_cascade'   -%}{{ step_cascade(v) }}
    {%- endif -%}
  {%- endfor -%}
{%- endif -%}
{% endmacro %}
```

Unknown preset → skipped (graceful). Adding a viz to a page can never break a render.

### 4.2 Preset contracts (the locked ~15)

Each macro is `{% if <required fields present> %}…{% endif %}` (graceful omit). `figure` fields are shown **verbatim**; numeric fields drive geometry only and must agree.

**Transformation**
- `ba_bars` — `{preset, title?, unit?, pairs:[{label, before:{value,magnitude}, after:{value,magnitude}, delta?}]}` — paired bars; height scales `magnitude` to the pair max; `value` shown verbatim as a display-serif numeral; optional `delta` pill (honest arithmetic on the two real figures, curator-supplied or omitted).
- `transform_arrow` — `{preset, title?, from:{value,label}, to:{value,label}}` — A → B dark-glass card; handles non-numeric afters ("Minuten").
- `completion_ring` — `{preset, percent:0-100, center:str (verbatim, e.g. "6/6" or "100%"), label, caption?}` — ring fill = percent; glowing center figure.

**Proportion**
- `donut` — `{preset, percent:0-100, figure:str (verbatim "90%"), label, source?}`.
- `split_bar` — `{preset, a:{percent, label}, b:{percent, label}, source?}` — two-segment bar (percents shown verbatim).
- `gauge` — `{preset, lo:0-100, hi:0-100, figure:str (verbatim "30–50%"), label, source?}` — semicircle; highlighted band `lo..hi` (single value → `lo==hi`).
- `radial_cluster` — `{preset, rings:[{percent, figure, label}] (2–3), source?}`.
- `icon_array` — `{preset, filled:int, total:int, figure:str (verbatim "rund 50 %"), label, glyph?}` — waffle; `filled` of `total` glyphs in accent.

**Magnitude**
- `stat_strip` — `{preset, items:[{value, label}] (2–4), on_dark?}` — premium display-serif numeral row on dark-glass with hairline dividers. (Distinct premium component; the existing flat `stat_strip`/`stat_rail` macros stay as-is for non-viz hosts.)
- `money_bar` — `{preset, value:str (verbatim "€200.000+"), label, fraction?:0-1 (bar fill; default 1.0)}`.
- `mega_numeral` — `{preset, value:str (verbatim "0"), label}` — oversized dark-glass numeral callout.
- `kpi_card` — `{preset, value:str, unit?, delta?:str, direction?:'up'|'down', context?}` — value + delta pill + context line.
- `ranked_bars` — `{preset, items:[{percent, figure, label}], source?, sorted?:bool (default true)}` — horizontal bars; width = percent; sorted desc unless `sorted:false`.

**Process**
- `phase_timeline` — `{preset, phases:[{label, duration:str (verbatim), weight:num}]}` — Gantt-style bars; bar size scales `weight`; `duration` shown verbatim.
- `step_cascade` — `{preset, steps:[{n?, title}]}` — ascending staircase of N step plates; `n` falls back to loop index.

**Structure** — `venn` already exists as `diagram` `kind=='convergence'`; the viz layer does not duplicate it. (It remains in the diagram proof-layer.)

### 4.3 Premium rendering recipe (token-only, from `.c-venn`/`.c-statcard`)

All presets use ONLY these token-derived treatments (Chromium honors; WeasyPrint drops losslessly):

- Dark-glass fill: `background-color: color-mix(in srgb, var(--color-ink) 88-90%, var(--color-primary))`.
- Accent keyline: `border: 0.3mm solid color-mix(in srgb, var(--color-accent) 45-60%, transparent)`.
- Ambient shadow: `box-shadow: 0 4mm 12mm color-mix(in srgb, var(--color-neutral-dark) 22-26%, transparent)`.
- Accent glow: `box-shadow: 0 0 6-7mm color-mix(in srgb, var(--color-accent) 28-30%, transparent)`.
- Numeral glow: `text-shadow: 0 0 5mm color-mix(in srgb, var(--color-accent) 55%, transparent)`.
- Gradient/overlap depth: `radial-gradient`/`linear-gradient` between `color-mix` token stops (e.g. accent→primary).
- Display numerals: `font-family: var(--font-head)`; weight 700-800; `font-size: var(--type-stat)` / `--type-stat-xl`; tight leading (~0.98).
- Labels: `var(--type-eyebrow)`/`--type-label`, letterspaced uppercase, `var(--color-muted)`.
- SVG arcs (donut/gauge/ring/radial): inline `<svg>` with stroke arcs; gradient via `<linearGradient>` using token-derived stops; glow via CSS `filter: drop-shadow(...)`. Arc geometry computed in the macro from `percent`/`lo`/`hi`. Units in `mm` for print fidelity.
- Dimensions in `mm`; `break-inside: avoid` on each figure.

Foreign/semantic colors (e.g. a green "down/saving" delta) are allowed only where they carry meaning, kept to their own element — consistent with the DNA "one accent = this matters."

### 4.4 Host wiring

Each target host pattern reads `viz = d.get("viz")` (a list; coerced to `None` if not a non-empty list) and passes it to its template, which renders `{% if viz %}<div class="host-viz">{{ render_viz(viz) }}</div>{% endif %}` in a designated zone. Exact zone per host is specified in the plan and verified on pixels. Targets (by available real data):

| Host | Page(s) | Presets | Placement note |
|---|---|---|---|
| ST-07A | p7,9,12,14,15 | `ba_bars`/`transform_arrow`/`completion_ring` | replaces/augments the existing `ergebnis_metrics` stat strip; graceful fallback to current strip if no `viz` |
| ST-22 | p19 | `phase_timeline` | the 5-step duration ladder zone |
| ST-06 | p16 | `step_cascade` + `gauge` | cascade upgrades the 6-step grid; gauge for 30-50% |
| ST-05 | p3 | `stat_strip` + `money_bar` | the "In Zahlen" zone |
| ST-09 | p4 | `icon_array` / `gauge` | status-quo zone |
| ST-FAZIT | p18 | `radial_cluster`/`ranked_bars`/`split_bar`/`icon_array` | stat-dense summary |
| ST-02 | p2 | `split_bar` / `gauge` | outlook body zone |
| ST-14 | p5 | (venn live) + optional `ranked_bars` | survey stats |

Hosts not in this table are untouched. All wiring is additive and graceful.

### 4.5 Curation (curated-first)

A new `fixtures/apex/viz_curation.py` exposes `apply_apex_viz(pkg)` (pure mutator, like `apply_diagram_plan`). It is called from `build_package.py` **after** the restructure + `plan_diagrams` steps (so it sees final, condensed pages) and **before** the final assertions. It writes `data['viz']` lists on the target pages using **verbatim** APEX figures sourced from the page's own copy. Every number is traceable to the data mine (`docs/superpowers/specs/2026-06-14-data-viz-preset-library-design.md` references the 68-point mine). No numbers are invented; geometry numerics agree with displayed strings.

This module is APEX-specific client data → it lives in the fixture, exempt from the brand-agnostic guard (same status as the rest of `build_package.py`).

## 5. Data Flow

1. `build_package.py` builds pages, runs restructure (LLM condense) + `plan_diagrams` (Venn) as today.
2. **NEW:** `apply_apex_viz(pkg)` writes `data['viz']` lists on target pages (verbatim figures).
3. Package assembled → `resolved_package.json`.
4. Renderer host pattern reads `data['viz']` → template renders `viz.jinja` dispatch → `viz_*.jinja` macros → `viz.css` premium styling → Chromium PDF → Ghostscript flatten.
5. Graceful at every hop: no `viz` → host renders exactly as today.

## 6. Error Handling / Robustness

- Every macro guards required fields; missing → renders nothing.
- Unknown `preset` → skipped by dispatch.
- Geometry math clamps (`percent` to 0-100; magnitudes default to a visible floor if unparseable, matching the existing `bar_chart` 8% floor).
- Host reads coerce non-list / empty `viz` to `None`.
- Overflow: each viz figure is `break-inside: avoid`; case-study viz replaces (not adds to) the existing strip so it doesn't grow the page. Per-page overflow verified on pixels (physical PNGs == logical pages, the established check).

## 7. Testing

TDD per family. Renderer tests (`research/v7-renderer/tests/`):
- `test_viz_dispatch.py` — dispatch routes each `preset` to its macro; unknown/empty → "" ; list iterates in order.
- `test_viz_transform.py`, `test_viz_proportion.py`, `test_viz_magnitude.py`, `test_viz_process.py` — each preset: renders expected class hooks + verbatim figure present; graceful omit on missing fields; geometry numerics produce expected arc/width (string assertions on computed values).
- **Brand-agnostic guard** must pass on all new renderer files (no client literals/hex/font family). Run the existing guard test.
- Fixture: `test_viz_curation.py` — `apply_apex_viz` writes lists only on target pages; every figure string is non-empty; idempotent; does not change page count (stays 20).
- Targeted runs only (`pytest -k`), never the full suite.
- **Verify on pixels** (the binding mandate): render the deck, view each touched page whole vs Richard's quality bar — not "did my element appear." Iterate per page.

## 8. Build Sequence (family by family, verify each on pixels)

Per the process mandate: spec → plan → **adversarial gap-audit before build** → build → verify on pixels → fix → reiterate.

1. **Scaffold:** `viz.jinja` dispatch + `viz.css` skeleton + `test_viz_dispatch.py` + host-read helper convention.
2. **Transformation family** (biggest unlock): `viz_transform.jinja` + CSS + tests → curate ST-07A case studies → wire ST-07A host → render → verify p7/9/12/14/15 on pixels.
3. **Proportion family:** `viz_proportion.jinja` + CSS + tests → curate ST-FAZIT/ST-09/ST-02/ST-14 → wire hosts → verify on pixels.
4. **Magnitude family:** `viz_magnitude.jinja` + CSS + tests → curate ST-05/ST-FAZIT → wire hosts → verify on pixels.
5. **Process family:** `viz_process.jinja` + CSS + tests → curate ST-22/ST-06 → wire hosts → verify on pixels.
6. **Whole-deck pass:** render 20/20, count check, full visual sweep vs Richard, fix rhythm/overflow.

Each family is independently shippable; if time runs short, the deck is sendable after any completed family.

## 9. Open Decisions (resolved)

- **Preset set:** locked at ~15 (user approved).
- **Data feed:** curated-first (user chose); auto `plan_charts` deferred.
- **`data['viz']` shape:** list of specs (supports multi-viz pages).
- **Existing flat chart engine:** left dormant, not extended.
