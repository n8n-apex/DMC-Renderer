# Premium Data-Viz Preset Library — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a brand-agnostic library of ~15 premium, Chromium-grade data-viz "presets" (dispatch + family macros + CSS), feed them with hand-curated verbatim APEX data, and wire them into the host patterns so the deck visualizes its numbers instead of printing them as flat text.

**Architecture:** Mirrors the existing diagram proof-layer exactly — `components/viz.jinja` dispatch switches on a `preset` discriminator → `components/viz_*.jinja` family macros → `styles/viz.css` (token-only premium depth) → host patterns read `data['viz']` (a list of specs) and render the dispatch. Client numbers live only in `fixtures/apex/viz_curation.py` (`apply_apex_viz`, a pure mutator with a grounding guard). Graceful omit at every hop.

**Tech Stack:** Jinja2 macros, CSS with `color-mix`/`mm` units, inline SVG arcs for rings/gauges, Python (pytest), Chromium print-to-PDF + Ghostscript flatten.

**Spec:** `docs/superpowers/specs/2026-06-14-data-viz-preset-library-design.md`

---

## Conventions (read once, apply to EVERY task)

**NO GIT in this repo.** The skill's "commit" steps are replaced by a **checkpoint**: run the task's tests + confirm green. Never `git` anything.

**NO full pytest suite** (user-banned, ~3 min). Run targeted `-k`/path only.

**Renderer environment** (every render/test command):
```bash
cd /Users/utkarsh/Projects/richard/research/v7-renderer
source .venv/bin/activate
export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib
```

**Render the deck** (Chromium default): `python render.py` → writes `output/report.pdf` + `output/report-pNN.png` (1 PNG per logical page).

**Rebuild the package** (needs OpenRouter key for the restructure stage):
```bash
cd /Users/utkarsh/Projects/richard/research/preprocessor
set -a; . ./.env; set +a
cd /Users/utkarsh/Projects/richard/research/v7-renderer
python fixtures/apex/build_package.py    # writes fixtures/apex/resolved_package.json (asserts 20 pages)
```

**VERIFY ON PIXELS (binding mandate):** after each family, render and READ the touched `output/report-pNN.png` files and judge the WHOLE page against Richard's quality bar — not "did my element appear." Iterate curation/CSS on what the pixels show.

**Brand-agnostic guard:** every new file under `components/` and `styles/` must contain ZERO client literals (no hex, no font-family literal, no client name, no APEX numbers). Colors via tokens + `color-mix`. Verify with:
```bash
pytest tests/test_no_literals_in_architecture.py -q
```

**Tokens available** (use only these): colors `--color-primary --color-accent --color-ink --color-on-dark --color-on-primary --color-body --color-muted --color-neutral-dark --color-surface --color-ground --color-ground-wash`; fonts `--font-display --font-head --font-body`; type `--type-stat-xl --type-stat --type-display-xl --type-display --type-hero --type-h2 --type-h3 --type-lede --type-label --type-eyebrow --type-caption`; space `--space-1..6`.

**Premium recipe** (token-only, from the live `.c-venn`/`.c-statcard`):
- dark-glass: `background-color: color-mix(in srgb, var(--color-ink) 88%, var(--color-primary));`
- accent keyline: `border: 0.3mm solid color-mix(in srgb, var(--color-accent) 50%, transparent);`
- ambient shadow: `box-shadow: 0 4mm 12mm color-mix(in srgb, var(--color-neutral-dark) 24%, transparent);`
- accent glow (add to box-shadow list): `0 0 7mm color-mix(in srgb, var(--color-accent) 28%, transparent)`
- numeral glow: `text-shadow: 0 0 5mm color-mix(in srgb, var(--color-accent) 55%, transparent);`
- gradient fill: `background-image: linear-gradient(180deg, color-mix(in srgb, var(--color-accent) 80%, transparent), color-mix(in srgb, var(--color-primary) 90%, transparent));`
- display numeral: `font-family: var(--font-head); font-weight: 800; font-size: var(--type-stat); line-height: 0.98;`

---

## Gap-audit fixes (LOCKED — apply everywhere; these override any looser wording below)

The pre-build adversarial audit (`tasks/wpszs6r9z`) verified these against the real repo. They are binding:

1. **icon_array uses inline SVG, NOT Tabler.** The print `<head>` (`assembler.py` `shared_head_css`) loads only Source Sans 3 + Source Serif 4 — there is NO Tabler/`ti-*` webfont. `icon_array` MUST render each cell as an inline `<svg>` filled glyph (default: a `<circle>` dot; the macro draws `total` circles, first `filled` in `color-mix(var(--color-accent)…)`, rest in `color-mix(var(--color-muted)…)`). No `ti ti-*` classes anywhere in print components. Spec §4.2 `icon_array` contract is hereby locked to SVG circles (`glyph` arg dropped).

2. **ba_bars magnitude is derived at render, not curated.** The `ba_bars` macro extracts the leading integer/decimal from each `value` string with a regex (e.g. `'30'→30`, `'2'→2`); curation does NOT supply `magnitude`. This makes height and the verbatim numeral impossible to diverge. Contract simplifies to `before:{value}`, `after:{value}`.

3. **All SVG gradient/filter IDs must be page-unique via a loop-safe token** (the macro's `loop.index` plus a per-macro prefix, e.g. `id="vizring{{ loop.index }}"`). NEVER key an id on a data value (`v.center`) — two equal values would collide and the renderer would apply one gradient to both. Add a test asserting two equal-value rings on one page produce distinct ids.

4. **Positive/delta pills use `var(--color-accent)`** (token-only). There is NO `--color-positive`/semantic-green token and a hardcoded green literal would fail the brand-agnostic guard on `styles/`/`components/`. The `ba_bars` `__delta` pill and any "good news" emphasis = accent tint. (True semantic green is a future token addition, out of scope.)

5. **`_figure_grounded` rule (LOCKED):** normalize both sides with NFKC + whitespace-collapse, then: (a) if the figure contains any non-digit char (e.g. `'> 200.000 €'`, `'100 %'`, `'6/6'`), accept iff the full normalized figure string is a substring of the normalized page-data JSON; (b) if the figure is digits-only (e.g. `'0'`, `'30'`, `'2'`), accept iff `re.search(r'(?<!\d)' + re.escape(fig) + r'(?!\d)', page_json)` matches (digit-boundary, so `'2'` does NOT match inside `'2025'`/`'20'`). Test both modes incl. the `'2'`-vs-`'2025'` false-positive case.

6. **`.c-statcard` accent glow (pre-fix, Task 0.0):** the live reference component is missing the spec'd glow layer; add it so the recipe is real before mirroring it.

7. **`viz_curation.py` is guard-exempt** — `test_no_literals_in_architecture.py` scans `templates/ styles/ patterns/ components/` but NOT `fixtures/`, so the curated APEX numbers there are fine. Confirmed `apply_apex_viz` insertion (build_package.py between line 298 `apply_diagram_plan` and line 300 `write_text`) is INSIDE the `if manifest_path.exists():` regen gate — correct.

8. **Case-study viz presets are VISUAL-ONLY** (`ba_bars`/`transform_arrow`/`completion_ring`/`mega_numeral`/`money_bar`) — never the plain `stat_strip` preset — so the viz band (bottom, in `cs-charts`/`cs-main--fill`) complements the existing numeric strip/statstack rather than duplicating it. On pixels, if a figure still reads as duplicated, drop it from curation. The `stat_strip` viz preset is for ST-05 only.

9. **ST-07A curation is keyed on `fallstudie_number` (populated 1..5).** Corrected descriptors (verified ground truth):
   - **fallstudie 1 (Martina Ammon, page idx 6)** = Support: `transform_arrow` (`24 Std.`→`Minuten`) + `money_bar` (`> 200.000 €`). Extract `24 Std.` / `> 200.000 €` verbatim from this page's metrics.
   - **fallstudie 3 (Frese, idx 11)** = metric string is `von bis zu 24 Stunden auf Minuten`; build `transform_arrow` from extracted `24 Stunden`→`Minuten` (grounding sees `24 Stunden` in the string) + the page's other metrics.
   - **fallstudie 4 (Conesso, idx 13)** = Onboarding/Copywriting: `ba_bars` pairs `30`→`2` and `60`→`5` (from `von 30 auf 2 Minuten` / `von 60 auf 5 Minuten`), `unit:"Min"`, accent delta optional.
   - The remaining two case studies (`6 von 6`/`0`; `100 % automatisiert`): `completion_ring` + `mega_numeral` as in Task 1.5, matched by their real metrics.
   - **Always read `fixtures/apex/resolved_package.json` for each page's real `ergebnis_metrics` and copy figures verbatim — the plan's labels are guidance, the file is ground truth.**

10. **ST-07A standard-variant viz band uses class `cs-viz`** (Task 1.4 adds a `.st-07a .cs-viz` rule: `margin-top: var(--space-4); width:100%`). Do NOT use `cs-charts--below` (no such rule exists). The fill variant places `cs-viz` inside `cs-main--fill`.

---

## Phase 0 — Scaffold (dispatch + CSS register + dispatch test)

### Task 0.0: Add the missing accent glow to `.c-statcard` (reference-component pre-fix)

**Files:** Modify `research/v7-renderer/styles/components.css` (the `.c-statcard` `box-shadow` line).

- [ ] **Step 1:** In `styles/components.css`, find `.c-statcard { … box-shadow: 0 4mm 12mm color-mix(in srgb, var(--color-neutral-dark) 26%, transparent); }` and append the accent glow as a second shadow layer:
```css
  box-shadow: 0 4mm 12mm color-mix(in srgb, var(--color-neutral-dark) 26%, transparent),
              0 0 6mm color-mix(in srgb, var(--color-accent) 28%, transparent);
```
- [ ] **Step 2 (checkpoint):** `pytest tests/test_no_literals_in_architecture.py -q` → PASS; `python render.py` → 20 PNGs; READ `output/report-p5.png`-adjacent statcard page (the stat_callout host) to confirm the card now reads as lit, not flat.

### Task 0.1: `viz.css` registered in the shared head

**Files:**
- Create: `research/v7-renderer/styles/viz.css`
- Modify: `research/v7-renderer/assembler.py` (the `shared_head_css` concat that already inlines `components.css` — add `viz.css` after it)

- [ ] **Step 1:** Find where `components.css` is read+inlined in `assembler.py`:
  `grep -n "components.css" assembler.py`
- [ ] **Step 2:** Create `styles/viz.css` with a header comment + a single sentinel rule so the file is non-empty and auditable:
```css
/* viz.css — premium data-viz PRESET library (Chromium engine).
   Token-only / brand-agnostic: every colour via var(--token) + color-mix; no
   hex, no font-family literal, no client data. Chromium honours the gradients/
   glow/dark-glass; WeasyPrint drops them losslessly (flat fallback). Families:
   viz_transform / viz_proportion / viz_magnitude / viz_process. */
.c-viz { break-inside: avoid; margin: var(--space-3) 0 0 0; }
```
- [ ] **Step 3:** In `assembler.py`, inline `viz.css` immediately after `components.css` in the same read-and-concat style the existing code uses (mirror the exact `(STYLES_DIR / "components.css").read_text(...)` call you found).
- [ ] **Step 4 (checkpoint):** `python render.py` succeeds and still emits 20 PNGs:
  `ls output/report-p*.png | wc -l` → `20`. (No visual change yet.)

### Task 0.2: `viz.jinja` dispatch macro

**Files:**
- Create: `research/v7-renderer/components/viz.jinja`
- Test: `research/v7-renderer/tests/test_viz_dispatch.py`

- [ ] **Step 1: Write the failing test** `tests/test_viz_dispatch.py`:
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from templating import get_env

def _render(specs):
    tmpl = get_env().from_string(
        "{% from 'viz.jinja' import viz %}{{ viz(specs) }}"
    )
    return tmpl.render(specs=specs)

def test_empty_renders_nothing():
    assert _render(None).strip() == ""
    assert _render([]).strip() == ""

def test_unknown_preset_skipped():
    assert _render([{"preset": "nope"}]).strip() == ""

def test_list_iterates_in_order():
    out = _render([
        {"preset": "mega_numeral", "value": "0", "label": "A"},
        {"preset": "mega_numeral", "value": "100+", "label": "B"},
    ])
    assert out.index("0") < out.index("100+")
```
- [ ] **Step 2: Run → FAIL** (`viz.jinja` not found / macros missing):
  `pytest tests/test_viz_dispatch.py -q`
- [ ] **Step 3: Implement** `components/viz.jinja` — the dispatch from spec §4.1, BUT every macro call threads the loop counter as a page-unique id seed (LOCKED #3). The switch lives inside `{% for v in specs if v and v.preset %}` and calls e.g. `{{ ba_bars(v, loop.index) }}`, `{{ completion_ring(v, loop.index) }}`, … — passing `loop.index` as the second arg to ALL family macros (SVG-bearing ones use it for unique gradient ids; others ignore it). For Phase 0, the four `viz_*.jinja` family files don't exist yet → create **stub** family files so imports resolve, each macro signed `(v, uid=0)`:
  - `components/viz_transform.jinja`: stub macros `ba_bars(v, uid=0)`, `transform_arrow(v, uid=0)`, `completion_ring(v, uid=0)`.
  - `components/viz_proportion.jinja`: stub `donut`, `split_bar`, `gauge`, `radial_cluster`, `icon_array` (all `(v, uid=0)`).
  - `components/viz_magnitude.jinja`: stub `stat_strip`, `money_bar`, `mega_numeral`, `kpi_card`, `ranked_bars` (all `(v, uid=0)`).
  - `components/viz_process.jinja`: stub `phase_timeline`, `step_cascade` (all `(v, uid=0)`).
  Each stub macro: `{% macro NAME(v, uid=0) %}{%- if v -%}<span class="c-viz c-viz--NAME">{{ v.value or v.figure or v.center or '' }}{% for x in (v.items or v.pairs or v.rings or v.phases or v.steps or []) %}{{ x.value or x.figure or x.label or '' }}{% endfor %}</span>{%- endif -%}{% endmacro %}`. (Real macros in later tasks keep the `(v, uid=0)` signature; SVG ones build ids like `id="vizring{{ uid }}"`.)
  (Real bodies replace the stubs family-by-family in later phases. Stubs let dispatch + tests pass now.)
- [ ] **Step 4: Run → PASS:** `pytest tests/test_viz_dispatch.py -q`
- [ ] **Step 5: Guard:** `pytest tests/test_no_literals_in_architecture.py -q` → PASS.
- [ ] **Step 6 (checkpoint):** dispatch test green + guard green.

---

## Phase 1 — Transformation family (biggest unlock) + ST-07A

### Task 1.1: `ba_bars` macro + CSS (TDD)

**Files:**
- Modify: `research/v7-renderer/components/viz_transform.jinja` (replace the `ba_bars` stub)
- Modify: `research/v7-renderer/styles/viz.css`
- Test: `research/v7-renderer/tests/test_viz_transform.py`

Contract (spec §4.2, per LOCKED #2): `{preset:'ba_bars', title?, unit?, pairs:[{label, before:{value}, after:{value}, delta?}]}`. Bar height is **derived at render** from the leading number of each `value` (LOCKED #2) via a `num` Jinja filter; `value` shown verbatim (display serif); optional `delta` accent pill (LOCKED #4).

- [ ] **Step 0: Add the `num` Jinja filter** in `research/v7-renderer/templating.py` — register a filter that extracts the leading number from a string so the macro can derive bar heights from the verbatim `value` (no curated magnitude). Find where `get_env()` builds the Environment and where filters/globals are registered, then add:
```python
import re as _re
def _leadnum(s):
    m = _re.search(r"-?\d+(?:[.,]\d+)?", str(s or ""))
    return float(m.group(0).replace(",", ".")) if m else 0.0
# after env = Environment(...):
env.filters["num"] = _leadnum
```
- [ ] **Step 1: Write failing tests** in `tests/test_viz_transform.py`:
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from templating import get_env

def _r(macro, v):
    t = get_env().from_string(
        "{%% from 'viz_transform.jinja' import %s %%}{{ %s(v) }}" % (macro, macro)
    )
    return t.render(v=v)

def test_ba_bars_shows_verbatim_values_and_delta():
    out = _r("ba_bars", {"preset": "ba_bars", "unit": "Min", "pairs": [
        {"label": "Onboarding", "before": {"value": "30"},
         "after": {"value": "2"}, "delta": "−93 %"}]})
    assert "30" in out and "2" in out and "Onboarding" in out
    assert "−93 %" in out
    assert "c-viz-ba" in out

def test_ba_bars_after_bar_shorter_than_before():
    # height % derived from the verbatim values; pair max=30 → before 100%, after floor(2/30*100)=6%
    out = _r("ba_bars", {"preset": "ba_bars", "pairs": [
        {"label": "x", "before": {"value": "30"}, "after": {"value": "2"}}]})
    assert "height:100%" in out.replace(" ", "")   # before bar full
    assert "height:6%" in out.replace(" ", "")     # after bar floored to 6

def test_ba_bars_empty_renders_nothing():
    assert _r("ba_bars", {"preset": "ba_bars", "pairs": []}).strip() == ""
```
- [ ] **Step 2: Run → FAIL** (stub doesn't produce `c-viz-ba`/heights): `pytest tests/test_viz_transform.py -q`
- [ ] **Step 3: Implement** `ba_bars` in `viz_transform.jinja`. Height % derives from `value` via the `num` filter, scaled to the pair max, floored to a visible 6% min. Markup: a `.c-viz-ba` figure → per pair a `.c-viz-ba__pair` with two `.c-viz-ba__col` columns (before muted gradient, after accent gradient), each with a `.c-viz-ba__num` (verbatim value, display serif) above and `.c-viz-ba__cap` (unit·label) below, plus optional `.c-viz-ba__delta` accent pill:
```jinja
{% macro ba_bars(v) %}
{%- if v and v.pairs and (v.pairs | selectattr('before') | list) -%}
<figure class="c-viz c-viz-ba" role="img" aria-label="{% for p in v.pairs %}{{ p.label }}: {{ p.before.value }} auf {{ p.after.value }}{% if v.unit %} {{ v.unit }}{% endif %}; {% endfor %}">
  {%- if v.title %}<figcaption class="c-viz-ba__title">{{ v.title }}</figcaption>{% endif -%}
  <div class="c-viz-ba__row">
  {%- for p in v.pairs -%}
    {%- set bn = p.before.value | num -%}
    {%- set an = p.after.value | num -%}
    {%- set m = [bn, an] | max -%}
    {%- set bh = (((bn / m * 100) if m else 0) | round(0,'floor') | int, 6) | max -%}
    {%- set ah = (((an / m * 100) if m else 0) | round(0,'floor') | int, 6) | max -%}
    <div class="c-viz-ba__pair">
      <div class="c-viz-ba__plabel">{{ p.label }}</div>
      <div class="c-viz-ba__bars">
        <div class="c-viz-ba__col">
          <span class="c-viz-ba__num">{{ p.before.value }}</span>
          <span class="c-viz-ba__bar c-viz-ba__bar--before" style="height:{{ bh }}%"></span>
          <span class="c-viz-ba__cap">{% if v.unit %}{{ v.unit }} · {% endif %}vorher</span>
        </div>
        <div class="c-viz-ba__col">
          <span class="c-viz-ba__num c-viz-ba__num--after">{{ p.after.value }}</span>
          <span class="c-viz-ba__bar c-viz-ba__bar--after" style="height:{{ ah }}%"></span>
          <span class="c-viz-ba__cap">{% if v.unit %}{{ v.unit }} · {% endif %}nachher</span>
        </div>
      </div>
      {%- if p.delta %}<span class="c-viz-ba__delta">{{ p.delta }}</span>{% endif -%}
    </div>
  {%- endfor -%}
  </div>
</figure>
{%- endif -%}
{% endmacro %}
```
- [ ] **Step 4: Add CSS** to `viz.css` for `.c-viz-ba*` using the premium recipe (before bar: muted gradient via `color-mix(var(--color-muted)...)`; after bar: accent→primary gradient + glow; `__num` display serif, `__num--after` accent + glow; `__delta` an **accent** tint pill — LOCKED #4, no green; bars in a fixed-height flex track ~34mm with `align-items:flex-end`).
- [ ] **Step 5: Run → PASS** + guard:
  `pytest tests/test_viz_transform.py -k ba_bars -q && pytest tests/test_no_literals_in_architecture.py -q`
- [ ] **Step 6 (checkpoint):** ba_bars tests green + guard green.

### Task 1.2: `transform_arrow` macro + CSS (TDD)

**Files:** Modify `viz_transform.jinja` (replace `transform_arrow` stub), `viz.css`; add tests to `tests/test_viz_transform.py`.

Contract: `{preset:'transform_arrow', title?, from:{value,label}, to:{value,label}}` — dark-glass card, big serif `from.value` → accent-glow `to.value`.

- [ ] **Step 1: Failing tests:**
```python
def test_transform_arrow_shows_both_verbatim():
    out = _r("transform_arrow", {"preset": "transform_arrow",
        "from": {"value": "24 Std.", "label": "Antwortzeit"},
        "to": {"value": "Minuten", "label": "automatisiert"}})
    assert "24 Std." in out and "Minuten" in out and "Antwortzeit" in out
    assert "c-viz-arrow" in out

def test_transform_arrow_needs_both_sides():
    assert _r("transform_arrow", {"preset": "transform_arrow", "from": {"value": "24"}}).strip() == ""
```
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** `transform_arrow` (guard: both `v.from.value` and `v.to.value`). Markup: `.c-viz-arrow` dark-glass flex card → `.c-viz-arrow__side` (value serif + label) · `.c-viz-arrow__glyph` (→) · `.c-viz-arrow__side--to` (accent value + glow + label).
- [ ] **Step 4: CSS** `.c-viz-arrow*` — dark-glass card recipe, `__side` value `var(--type-stat)` serif `var(--color-on-dark)`, `--to` value accent + numeral glow, `__glyph` accent.
- [ ] **Step 5: Run → PASS** + guard.
- [ ] **Step 6 (checkpoint).**

### Task 1.3: `completion_ring` macro + CSS (TDD)

**Files:** Modify `viz_transform.jinja` (replace `completion_ring` stub), `viz.css`; add tests.

Contract: `{preset:'completion_ring', percent:0-100, center:str(verbatim), label, caption?}`. Inline SVG ring; arc dash = `percent/100 * circumference`.

- [ ] **Step 1: Failing tests:**
```python
def test_completion_ring_full_and_center_verbatim():
    out = _r("completion_ring", {"preset": "completion_ring",
        "percent": 100, "center": "6/6", "label": "Prozesse"})
    assert "6/6" in out and "Prozesse" in out and "<svg" in out
    assert "c-viz-ring" in out

def test_completion_ring_needs_center():
    assert _r("completion_ring", {"preset": "completion_ring", "percent": 50}).strip() == ""
```
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** `completion_ring` (guard `v.center`). Compute `circ = 3.1416 * 2 * R` (pick `R=50` viewBox units), `dash = (v.percent|default(100)|float / 100 * circ) | round(1)`. SVG: track circle + value circle with `stroke-dasharray="{{dash}} {{circ}}"`, `transform="rotate(-90 ...)"`, `stroke="url(#vizring{{ uid }})"` token-gradient def + CSS `filter: drop-shadow` glow; `<text>` center (serif accent) + label. **Gradient id MUST be page-unique (LOCKED #3):** accept a `uid` macro arg (the host/dispatch passes `loop.index`); if called standalone, default `uid` to a fixed token. The dispatch loop in `viz.jinja` already iterates `specs` — pass `loop.index` as `uid` to every SVG-bearing macro so ids never collide across multiple viz on one page. NEVER key the id on `v.center`.
- [ ] **Step 3b: Add a collision test** in `tests/test_viz_transform.py`: render two `completion_ring` specs with the SAME center ("100%") through the `viz` dispatch and assert the two `id=` substrings differ.
- [ ] **Step 4: CSS** `.c-viz-ring*` (dark-glass wrapper optional; the SVG carries the arc; glow via `filter`).
- [ ] **Step 5: Run → PASS** + guard.
- [ ] **Step 6 (checkpoint).**

### Task 1.4: ST-07A host wiring (read `data['viz']`, render dispatch in the chart band)

**Files:**
- Modify: `research/v7-renderer/patterns/st_07a.py` (read `viz`, pass to template)
- Modify: `research/v7-renderer/templates/st_07a.html.jinja` (import dispatch; render viz band in BOTH variants)
- Test: `research/v7-renderer/tests/test_viz_host_st07a.py`

- [ ] **Step 1: Failing test** `tests/test_viz_host_st07a.py` — render the ST-07A pattern on a real apex page (so `RenderContext` is built correctly) toggling `data['viz']`, and assert the viz markup appears, and that a page WITHOUT `viz` renders no `c-viz`. **There is NO `tests/conftest.py`/`make_ctx`** (audit-verified) — define `_apex_ctx()` inline, mirroring `tests/test_st07a_fill_variant.py:187-194`. First open that file and copy its exact ctx-construction (`load_package(APEX_DIR)` → `RenderContext(brand=..., grammar=load_grammar(), package_dir=..., report_assets=...)`); then:
```python
import copy, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import patterns.st_07a as st07a
# --- reuse the EXACT helpers test_st07a_fill_variant.py uses (load_package,
# --- load_grammar, RenderContext, APEX dir constant). Define _apex_ctx() and
# --- grab a real ST-07A page from the loaded package: ---
from tests.test_st07a_fill_variant import _apex_ctx  # if that file exposes it
# If it does NOT expose a reusable helper, copy its 187-194 body into a local
# _apex_ctx() here verbatim (do not invent make_ctx).

def _st07a_page(pkg):
    return copy.deepcopy(next(p for p in pkg["pages"] if p["st_type"] == "ST-07A"))

def test_viz_renders_when_present():
    ctx, pkg = _apex_ctx()             # adapt to the helper's real return shape
    page = _st07a_page(pkg)
    page["data"]["viz"] = [{"preset": "mega_numeral", "value": "0", "label": "neue MA"}]
    frag = st07a.render(page, ctx)
    assert "c-viz" in frag.html and "neue MA" in frag.html

def test_no_viz_unchanged():
    ctx, pkg = _apex_ctx()
    page = _st07a_page(pkg)
    page["data"].pop("viz", None)
    frag = st07a.render(page, ctx)
    assert "c-viz" not in frag.html
```
  **The implementer MUST read `tests/test_st07a_fill_variant.py` first** and match its real ctx/package helpers (names + return shapes) — the snippet above is the shape, not a guaranteed import.
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement pattern** in `patterns/st_07a.py`: after the `chart_svgs = ctx.chart_svgs(page)[:CS_MAX_CHARTS]` line, add:
```python
    # data-viz PRESET layer: data['viz'] is a list of {preset, …} specs the
    # curation step wrote. Coerce to None unless a non-empty list so the template
    # renders exactly as before when absent (graceful).
    viz = d.get("viz")
    viz = viz if isinstance(viz, list) and viz else None
```
  and add `viz=viz,` to the `template.render(...)` kwargs.
- [ ] **Step 4: Implement template** `templates/st_07a.html.jinja`: add `{% from 'viz.jinja' import viz as render_viz %}` at top. In BOTH variants — the **fill** variant's `cs-main--fill` block (after its `chart_svgs` loop) and the **standard** variant's below-grid area (after the `cs-charts cs-charts--below` block) — add:
```jinja
    {% if viz %}
    <div class="cs-viz">{{ render_viz(viz) }}</div>
    {% endif %}
```
- [ ] **Step 4b: Add the `.cs-viz` rule** (LOCKED #10 — `cs-charts--below` styling does not apply to it) to `styles/st_07a.css`:
```css
.st-07a .cs-viz { width: 100%; margin-top: var(--space-4); }
```
- [ ] **Step 5: Run → PASS** the host test; guard `pytest tests/test_no_literals_in_architecture.py -q`.
- [ ] **Step 6 (checkpoint):** host renders viz when present, unchanged when absent.

### Task 1.5: `viz_curation.py` scaffold + grounding guard + ST-07A specs

**Files:**
- Create: `research/v7-renderer/fixtures/apex/viz_curation.py`
- Modify: `research/v7-renderer/fixtures/apex/build_package.py` (call `apply_apex_viz` after `apply_diagram_plan`, before the `write_text`)
- Test: `research/v7-renderer/tests/test_viz_curation.py`

The grounding guard is the structural no-fabrication enforcer: every displayed figure string must already appear in the page's own data.

- [ ] **Step 1: Failing test** `tests/test_viz_curation.py`:
```python
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fixtures.apex.viz_curation import apply_apex_viz, _figure_grounded

def test_grounding_rejects_ungrounded_figure():
    page = {"st_type": "ST-07A", "data": {"ergebnis_metrics": [{"value": "30"}]}}
    assert _figure_grounded("30", page) is True
    assert _figure_grounded("999", page) is False

def test_grounding_digit_boundary_no_false_positive():
    # '2' must NOT ground against a page that only contains '2025'
    page = {"st_type": "X", "data": {"quelle": "PwC 2025"}}
    assert _figure_grounded("2", page) is False
    page2 = {"st_type": "X", "data": {"m": [{"value": "von 30 auf 2 Minuten"}]}}
    assert _figure_grounded("2", page2) is True

def test_grounding_nondigit_substring_mode():
    page = {"st_type": "X", "data": {"m": [{"value": "> 200.000 €"}]}}
    assert _figure_grounded("> 200.000 €", page) is True
    assert _figure_grounded("100 %", page) is False

def test_apply_sets_viz_only_on_targets_and_keeps_count():
    pkg = {"pages": [
        {"st_type": "ST-07A", "fallstudie_number": 5, "data": {
            "ergebnis_metrics": [{"label": "Onboarding", "value": "von 30 auf 2 Minuten"}]}},
        {"st_type": "ST-01", "data": {}},
    ]}
    apply_apex_viz(pkg)
    assert isinstance(pkg["pages"][0]["data"].get("viz"), list)
    assert "viz" not in pkg["pages"][1]["data"]
    assert len(pkg["pages"]) == 2
```
- [ ] **Step 2: Run → FAIL** (module missing).
- [ ] **Step 3: Implement** `viz_curation.py`:
  - `_norm(s)`: NFKC + collapse whitespace (the `restructure_page._norm` approach is gone from the codebase — write it fresh: `unicodedata.normalize("NFKC", s)` then `re.sub(r"\s+", " ", s).strip()`).
  - `_figure_grounded(figure, page) -> bool` (LOCKED #5): let `pj = _norm(json.dumps(page['data'], ensure_ascii=False))` and `f = _norm(figure)`. If `f` contains any non-digit char (`'> 200.000 €'`, `'100 %'`, `'6/6'`, `'24 Std.'`) → `return f in pj`. If `f` is digits-only (`'0'`,`'30'`,`'2'`) → `return re.search(r'(?<!\d)' + re.escape(f) + r'(?!\d)', pj) is not None` (digit-boundary, so `'2'` does NOT match inside `'2025'`). Test BOTH modes including the `'2'`-vs-`'2025'` case (see Step 1).
  - `apply_apex_viz(pkg)`: a per-target dispatch keyed by `(st_type, fallstudie_number)` (case studies) / `st_type` (others). For each target, build the `viz` list from the **verbatim** figures in the curation tables below; assert every spec's displayed figure is `_figure_grounded` on that page (fail loud otherwise); set `page['data']['viz']`. Pure mutator, returns None.
  - **ST-07A curation** (the 5 case studies, matched by `fallstudie_number` 1..5): use the **corrected, audit-verified descriptor→preset mapping in LOCKED #9** above (fallstudie 1 Ammon = Support arrow+money; 3 Frese = arrow from extracted `24 Stunden`; 4 Conesso = ba_bars 30→2 & 60→5; plus the `6 von 6`/`0` page → completion_ring + mega_numeral; the `100 % automatisiert` page → completion_ring). `value` for ba_bars = the bare verbatim numeral ("30","2","60","5") — `num` derives the height. `transform_arrow` value strings must be a verbatim substring of the page (extract `24 Stunden`/`24 Std.` from the real metric so grounding passes). `delta` is honest arithmetic on the two real figures (accent pill); omit if both before/after aren't present.
    - **GROUND TRUTH = `fixtures/apex/resolved_package.json`.** READ each ST-07A page's real `ergebnis_metrics` and copy figures verbatim; the descriptors are guidance, the file decides. Every spec figure is re-checked by `_figure_grounded` (fail-loud).
- [ ] **Step 4:** Wire into `build_package.py` — after line ~298 `apply_diagram_plan(pkg, diagram_plan)`, add:
```python
        from fixtures.apex.viz_curation import apply_apex_viz
        apply_apex_viz(pkg)
        print("[viz] presets applied")
```
  (Inside the same regen block, before `(HERE / "resolved_package.json").write_text(...)`.)
- [ ] **Step 5: Run → PASS:** `pytest tests/test_viz_curation.py -q` + guard (curation is fixture code, exempt, but run dispatch/transform tests to ensure no break).
- [ ] **Step 6 (checkpoint).**

### Task 1.6: Rebuild + render + VERIFY ON PIXELS (Transformation)

- [ ] **Step 1:** Rebuild the package (sourcing `.env`): the `build_package.py` command from Conventions. Confirm it prints `[viz] presets applied` and asserts 20 pages.
- [ ] **Step 2:** Render: `python render.py`. Confirm 20 PNGs.
- [ ] **Step 3: READ the pixels** — `output/report-p7.png`, `p9`, `p12`, `p14`, `p15` (the 5 case studies). Judge each WHOLE page vs Richard: does the transformation viz read premium, sit in the dead bottom band without overflow, not duplicate the stat strip awkwardly, numbers verbatim & correct? Also re-read one untouched page (e.g. p2) to confirm no regression.
- [ ] **Step 4: Fix on what the pixels show** — adjust `viz.css` sizing/placement and/or curation (e.g. if the stat strip + viz duplicate, drop the redundant metric from the strip or pick a complementary preset). Re-render. Iterate until each case-study page reads premium.
- [ ] **Step 5 (checkpoint):** all 5 case studies verified premium on pixels; deck still 20/20.

---

## Phase 2 — Proportion family (donut · split_bar · gauge · radial_cluster · icon_array)

Each macro follows the **same TDD shape as Phase 1** (failing test asserting verbatim figure + class hook + graceful-omit → implement guarded macro → CSS via the premium recipe → PASS + guard). The Phase-1 files are the concrete reference. SVG-arc macros (`donut`, `gauge`, `radial_cluster`) compute arc geometry in Jinja exactly like `completion_ring`.

### Task 2.1: `donut` — `{percent, figure(verbatim), label, source?}` — ring + center verbatim figure + side label. Tests: verbatim figure present, `<svg>` present, arc dash scales with percent, omit when no `figure`. CSS `.c-viz-donut*`.

### Task 2.2: `split_bar` — `{a:{percent,label}, b:{percent,label}, source?}` — two-segment bar, widths = percents, each percent shown verbatim. Tests: both percents + labels present, widths reflect percents, omit when `a`/`b` missing. CSS `.c-viz-split*`.

### Task 2.3: `gauge` — `{lo, hi, figure(verbatim), label, source?}` — semicircle SVG; track + highlighted band arc from `lo` to `hi` (compute endpoints from the `f→angle` map in spec; single value → `lo==hi`). Tests: figure present, `<path` band present, omit when no `figure`. CSS `.c-viz-gauge*`.

### Task 2.4: `radial_cluster` — `{rings:[{percent,figure,label}] (2–3), source?}` — N rings side by side (reuse the `completion_ring` arc logic per ring; unique SVG ids per ring via loop index). Tests: each figure present, N `<svg>` blocks, omit when `rings` empty. CSS `.c-viz-cluster*`.

### Task 2.5: `icon_array` — `{filled, total, figure(verbatim), label}` — `total` **inline-SVG circle** cells (LOCKED #1 — NO Tabler webfont in the print head), first `filled` in `color-mix(var(--color-accent)…)`, rest in `color-mix(var(--color-muted)…)`. Each cell is a small `<svg viewBox="0 0 10 10"><circle cx=5 cy=5 r=4 .../></svg>` in a flex/grid wrap. Tests: figure present, exactly `filled` accent-filled circles + `total-filled` muted, omit when `total<=0`. CSS `.c-viz-iconarray*`. (Do NOT use `ti ti-*` classes — they render blank in print.)

### Task 2.6: Host wiring + curation + VERIFY
- **Hosts:** ST-FAZIT, ST-09, ST-02, ST-14 — each reads `viz = d.get('viz')` (list-or-None) and renders `{% if viz %}<div class="..-viz">{{ render_viz(viz) }}</div>{% endif %}` in its body zone (mirror the ST-07A wiring; import `viz as render_viz`). Add a host test per pattern asserting viz appears when present, absent otherwise (mirror `test_viz_host_st07a.py`).
- **Curation** in `viz_curation.py` (verbatim, grounded — assert each via `_figure_grounded`):
  - ST-FAZIT (p18): `radial_cluster {rings:[{58, "58 %", "autonome Systeme"},{61,"61 %","agentic AI"}], source:"KPMG 2026"}` + `split_bar {a:{40,"messbarer Return"}, b:{60,"kein messbarer Return"}, source:"BCG 2026"}` + `icon_array {filled:1,total:2,figure:"rund 50 %",label:"Wissensarbeiter nahe Burnout"}`. (Pick the 2–3 that fit on pixels; drop overflow.)
  - ST-09 (p4): `icon_array {filled:1,total:2,figure:"rund 50 %",label:"Wissensarbeiter nahe Burnout"}` OR `gauge` for `25–30 %` — verify which reads better.
  - ST-02 (p2): `split_bar {a:{60,"kein messbarer Wert"}, b:{40,"Wert aus KI"}}` (only if grounded in p2 copy — else `gauge` for `bis zu 30 %`).
  - ST-14 (p5): keep the Venn; optionally `ranked_bars` (built in Phase 3) — defer to Phase 3.
- **VERIFY ON PIXELS:** rebuild, render, READ p18/p4/p2 (and p5), iterate. Checkpoint: proportion pages premium, 20/20, no regression.

---

## Phase 3 — Magnitude family (stat_strip · money_bar · mega_numeral · kpi_card · ranked_bars)

Same TDD shape; Phase-1/2 files are the reference.

### Task 3.1: `mega_numeral` — `{value(verbatim), label}` — oversized dark-glass numeral callout. (Already exercised by the Phase-0 dispatch test's ordering check — now give it the real premium body.) Tests: value+label present, omit when no `value`. CSS `.c-viz-mega*`.

### Task 3.2: `money_bar` — `{value(verbatim), label, fraction?:0-1 default 1.0}` — horizontal gradient money bar + verbatim figure at the end. Tests: value+label present, bar width reflects `fraction`, omit when no `value`. CSS `.c-viz-money*`.

### Task 3.3: `stat_strip` — `{items:[{value,label}] (2–4), on_dark?}` — premium display-serif numeral row on dark-glass, hairline dividers. Tests: each value present, omit when `items` empty. CSS `.c-viz-statstrip*`. (Distinct from the existing flat `stat_strip.jinja` — different file/classes; do not modify the old one.)

### Task 3.4: `kpi_card` — `{value(verbatim), unit?, delta?, direction?, context?}` — value + delta pill (semantic colour by `direction`) + context line. Tests: value+delta+context present, omit when no `value`. CSS `.c-viz-kpi*`.

### Task 3.5: `ranked_bars` — `{items:[{percent,figure,label}], source?, sorted? default true}` — horizontal bars, width=percent, sorted desc unless `sorted:false`, each figure verbatim. Tests: figures present, descending order when `sorted`, omit when empty. CSS `.c-viz-ranked*`.

### Task 3.6: Host wiring + curation + VERIFY
- **Hosts:** ST-05 (p3), ST-14 (p5 ranked_bars beside the Venn), plus reuse ST-FAZIT/ST-07A already wired (append specs to their existing `viz` lists in curation).
- **Curation** (verbatim, grounded):
  - ST-05 (p3): `stat_strip {items:[{"100+","AI-Projekte"},{"€200k+","Einsparung / Jahr"},{"30-50%","Betriebskosten"}]}` — label is VERBATIM `Betriebskosten`, **NO `↓`** (LOCKED #6: do not edit the source string; if a down-arrow accent is wanted, add it via CSS `::after`, not the data). Plus optional `money_bar {value:"€200.000+", label:"Einsparung / Jahr"}` (only if grounded). The page's "In Zahlen" already shows these — verify it complements, not duplicates; may instead REPLACE the existing flat stat panel — decide on pixels.
  - ST-14 (p5): `ranked_bars {items:[{percent:90, figure:"90 %", label:"CEOs nutzen KI"},{percent:58, figure:"58 %", label:"B2B autonome Systeme"}], source:"PwC · KPMG"}` — **ONLY 90 % and 58 %** (audit-verified: those are the only survey %s grounded on ST-14; `77 %`/`61 %` live on ST-FAZIT/ST-06, NOT here). The grounding guard will reject any other figure on this page. Do NOT add a fuller set here, and do NOT move all four to ST-FAZIT (it lacks `90 %`). If a 4-bar ranking is wanted, build it from figures that genuinely co-occur on one page.
- **VERIFY ON PIXELS:** rebuild, render, READ p3/p5/p18, iterate. Checkpoint.

---

## Phase 4 — Process family (phase_timeline · step_cascade)

### Task 4.1: `phase_timeline` — `{phases:[{label, duration(verbatim), weight}]}` — Gantt-style bars; bar size scales `weight` to the max; `duration` shown verbatim. Tests: each duration+label present, bar sizes reflect weights, omit when empty. CSS `.c-viz-timeline*`.

### Task 4.2: `step_cascade` — `{steps:[{n?, title}]}` — ascending staircase of N plates; `n` falls back to loop index; last plate = accent gradient + glow. Tests: each title present, N plates, omit when empty. CSS `.c-viz-cascade*`.

### Task 4.3: Host wiring + curation + VERIFY
- **Hosts:** ST-22 (p19), ST-06 (p16) — wire `viz` (mirror ST-07A); host tests per pattern.
- **Curation** (verbatim, grounded):
  - ST-22 (p19): `phase_timeline {phases:[{"Erstgespräch","1 Tag",1},{"Audit","3-5 Tage",1.6},{"Setup","2-3 Tage",1.3},{"Implementierung","1-3 Wochen",2.4},{"Go-Live","2-3 Tage",1.3}]}`. Durations verbatim from the page's `dauer` fields (ground truth = `resolved_package.json`); `weight` is a presentation scalar (not a figure → exempt from grounding, but keep proportional to the stated durations).
  - ST-06 (p16): `step_cascade {steps:[{1,"Workflow-Audit und Engpass-Diagnose"},{2,"CRM-Bereinigung und Datenstruktur"},{3,"AI-Agenten-Implementierung"},{4,"Onboarding- und Fulfillment-Automatisierung"},{5,"Kommunikations- und Support-Automatisierung"},{6,"Kontinuierliche Optimierung und Reporting"}]}` + optional `gauge {lo:30,hi:50,figure:"30-50%",label:"operative Effizienz", source:"PwC 2026"}`. Titles verbatim from the page's step data. (The cascade may REPLACE the existing 6-step grid — decide on pixels; if it overflows, keep grid + add only the gauge.)
- **VERIFY ON PIXELS:** rebuild, render, READ p19/p16, iterate. Checkpoint.

---

## Phase 5 — Whole-deck pass

### Task 5.1: Full-deck render + sweep
- [ ] **Step 1:** Rebuild + render. Assert exactly 20 PNGs (`ls output/report-p*.png | wc -l` → 20) and no overflow (physical PNG count == logical page count).
- [ ] **Step 2: READ all 20 pages** in sequence. Check: rhythm (viz not on every page back-to-back), no duplication between a viz and its page's stat text, every figure verbatim & correct, dark-glass/glow renders (Chromium), no overflow/clipping.
- [ ] **Step 3:** Fix any rhythm/overflow/duplication by adjusting curation (which page carries which preset) and `viz.css`. Re-render.
- [ ] **Step 4: Targeted test sweep:** `pytest tests/test_viz_dispatch.py tests/test_viz_transform.py tests/test_viz_proportion.py tests/test_viz_magnitude.py tests/test_viz_process.py tests/test_viz_curation.py tests/test_viz_host_st07a.py tests/test_no_literals_in_architecture.py -q` → all green.
- [ ] **Step 5 (checkpoint):** deck 20/20, all viz pages verified premium on pixels vs Richard, guard + viz tests green. Sendable.

---

## Self-Review (run after writing; fixed inline)

- **Spec coverage:** dispatch (4.1) → Task 0.2; all 15 preset contracts (4.2) → Tasks 1.1–1.3, 2.1–2.5, 3.1–3.5, 4.1–4.2; premium recipe (4.3) → Conventions + every CSS step; host wiring (4.4) → Tasks 1.4, 2.6, 3.6, 4.3; curation + grounding (4.5) → Task 1.5 + each phase's curation; data flow (5) → Task 1.5 Step 4 placement; robustness (6) → graceful-omit guards in every macro + list coercion in hosts; testing (7) → per-task TDD + guard + pixel verify + Task 5.1. No spec section unmapped.
- **No placeholders:** every macro/CSS step states the contract, class hooks, and recipe; curation lists verbatim figures + names ground truth. Phases 2–4 reference the concrete Phase-1 files rather than restating identical macro boilerplate (the recipe + one full worked SVG/bar macro exist in Phase 1) — this is deliberate DRY, not a "similar to Task N" dodge: each later task gives its own contract, class hooks, and tests.
- **Type/name consistency:** `data['viz']` is a list everywhere; dispatch macro `viz` imported `as render_viz` in every host; preset names match spec §4.2 exactly; `_figure_grounded`/`apply_apex_viz` names consistent between curation module + tests.
- **No-git / no-full-suite / venv+DYLD / pixel-verify** constraints stated in Conventions and repeated in every checkpoint.
