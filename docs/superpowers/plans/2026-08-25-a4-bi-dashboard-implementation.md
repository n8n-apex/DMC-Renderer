# a4_bi_dashboard Implementation Plan — the "Power-BI" 50/50 data spread

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `a4_bi_dashboard` treatment (currently a metadata-only stub) so apex's ST-09 context page renders as Richard's two-column "Light/Navy 50-50" data spread — interior dark stat panel + editorial narrative — using the existing `viz` device library.

**Architecture:** A Jinja treatment template + scoped CSS registered by name in `treatment_catalog.py` (already there). The engine's existing `treatment_is_built`/`candidate_fits`/`render` path activates it. To host on apex, one candidate-list change (`_CANDIDATES["ST-09"]`), one optional fixture curation (`viz_rich`), and a catalog `formats` pin (`a4`) so metadata stays honest. Everything token-only, no fabrication, pixel-verified every step.

**Tech stack:** Jinja2 macros + CSS paged media (Chromium engine, WeasyPrint lossless fallback), existing `viz.jinja` dispatch, pytest.

**Spec:** `docs/superpowers/specs/2026-08-25-a4-bi-dashboard-design.md` (contains the reference-anatomy audit + host decision).

---

## Non-negotiable rules

- **No client literals / raw hex / font-family literal / em dashes (U+2014)** in `templates/`, `styles/`, `patterns/`, `components/`. Guard: `test_no_literals_in_architecture.py` (recursive over templates+styles) + `test_no_em_dashes_in_treatment_files`. Commits: no em dashes in the new files.
- **Dark panels ground on `var(--color-ink)`** — NOT `--color-primary` (apex sets primary==accent, would make rail stats invisible; `test_panel_contrast.py` binds best practice). Mirror the `a4_case_study` rail recipe exactly.
- **Never fabricate a figure.** The second device ("25–30 %") is added ONLY via the grounded `viz_curation` enrichment (`_figure_grounded` must pass) and only if the dashboard sheet still fits (26 logical == 26 physical, `overflow=[]`).
- **The dark panel is INTERIOR (inset 25% width, middle-to-bottom), NOT full-bleed** — the reference p3 audit proved it. DO NOT touch `assembler.py` edge/`tp-rail` carve-outs; a full-bleed rail is a future, separate change.
- **Verify on pixels every step** — render, READ `output/report-pN.png` (the ST-09 context page index), judge the WHOLE page vs the tuff reference. Never "did my device appear."
- **No full pytest suite** (user-banned); run targeted `-k`/file tests only.

---

## File map

| File | Action |
|---|---|
| `research/v7-renderer/treatment_catalog.py` (`:96`) | pin `formats` → `frozenset({"a4"})` |
| `research/v7-renderer/treatment_stylist.py` (`:97`) | `_CANDIDATES["ST-09"]` → `["a4_bi_dashboard","a4_editorial_fill","a4_two_stack","a4_dark_divider"]` |
| `research/v7-renderer/templates/treatments/a4_bi_dashboard.html.jinja` | NEW — the treatment fragment |
| `research/v7-renderer/styles/treatments/a4_bi_dashboard.css` | NEW — the scoped model for the interior panel + narrative rail |
| `research/v7-renderer/tests/test_treatment_dashboard.py` | NEW — unit tests (dispatch contract, viz-fitted selection, interior-geometry classes) |
| `research/v7-renderer/fixtures/apex/viz_curation.py` (`_st09_specs`) | add the grounded "25–30 %" device ONLY if fit-safe |
| `research/v7-renderer/tests/test_viz_curation.py` | add a test asserting the ST-09 enrichment stays grounded |
| `research/v7-renderer/fixtures/apex/resolved_package.json` | re-baked only (build_package.py), never hand-edited |
| `research/v7-renderer/tests/test_treatment_slice.py` (`~189-208`) | update the stale `treatment-a4_editorial_fill` assertion for ST-09 context → dashboard; note the two pre-existing 25/26 stale pins (do not widen) |

---

## Tasks (TDD; run the guard battery after every task)

### Task 1 — Pin the catalog formats to a4 (honest metadata)

**Files:** `research/v7-renderer/treatment_catalog.py:96`, test `test_treatment_dispatch.py`.

- [ ] **Step 1:** Change the stub line:
```python
_treatment("a4_bi_dashboard", "dashboard", frozenset({"a4"}), ("viz",)),
```
- [ ] **Step 2:** Run `pytest tests/test_treatment_dispatch.py -q` → still green (a4-only means no existing a3 promotion references it, which the audit confirmed).

### Task 2 — Add the dashboard to ST-09's candidate list (context fits, evidence stays fill)

**Files:** `research/v7-renderer/treatment_stylist.py:97`, update `test_treatment_stylist.py`.

- [ ] **Step 1:** Change `_CANDIDATES["ST-09"]`:
```python
"ST-09": ["a4_bi_dashboard", "a4_editorial_fill", "a4_two_stack", "a4_dark_divider"],
```
The context page (`data.viz` present) now fits → assigned; the evidence page (viz=None) fails the contract → fill. Verify with the fake fixture in `test_treatment_stylist.py` (add an assertion that a ST-09 page WITH viz assigns the dashboard).
- [ ] **Step 2:** Run `pytest tests/test_treatment_stylist.py -q` → green; guard `<test_no_literals_in_architecture.py> -q` → green.

### Task 3 — Renderer: the dashboard fragment template (the bank item)

**Files:** create `templates/treatments/a4_bi_dashboard.html.jinja`
**Test:** new `tests/test_treatment_dashboard.py` (probe-leaf pattern, mirroring `test_treatment_dispatch.py:189-261`)

- [ ] **Step 1:** Write the failing test fixture:
```python
# test_treatment_dashboard.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import json, copy
from package_loader import load_package
from brand_tokens import parse_brand_tokens
from grammar_loader import load_grammar
from templating import get_env
from treatment_engine import adapt, treatment_is_built, render, get_treatment, meets_contract
from treatment_catalog import register_all

def _ctx():
    register_all()
    pkg = json.loads((Path(__file__).resolve().parent.parent / "fixtures/apex/resolved_package.json").read_text())
    b = parse_brand_tokens(pkg.brand)
    return _RenderContext(brand=b, grammar=load_grammar(), ..., package_dir=..., report_assets=...)

def test_dashboard_is_built_and_fits_viz():
    assert treatment_is_built("a4_bi_dashboard") is True
    page = copy.deepcopy(next(p for p in _pkg()["pages"] if p["st_type"] == "ST-09" and p.get("continuation_role") == "context"))
    td = adapt(page, ctx)
    assert meets_contract(td, get_treatment("a4_bi_dashboard")) is True

def test_no_viz_never_fits():
    page = copy.deepcopy(...); page["data"].pop("viz", None)
    assert meets_contract(adapt(page, ctx), get_treatment("a4_bi_dashboard")) is False
```
(make it import `load_package`, `from grammar_loader import load_grammar`, `from package_loader import ...` — copy the widget from `test_treatment_engine.py:74-86` and the probe-template teardown from `test_treatment_dispatch.py:189-261`.)
- [ ] **Step 2:** Run → FAIL (template missing).
- [ ] **Step 3:** Author the template — a fragment with the reference anatomy:
  - optional hero strip `{% if td.image %}<div class="db-hero">…</div>{% endif %}`
  - head row (`eyebrow`, `two_tone_headline(td.headline, td.headline_accent, tag='h1')`, `td.subhead`)
  - the body grid: `<div class="db-grid"><div class="db-narrative">{{ td.body|join }}<div/or sections_list></div><aside class="db-rail"><div class="db-rail-cap">In Zahlen</div>{% for s in td.stats %}…{% endfor %}{# viz devices ARE the rail content #}{% if td.viz %}<div class="db-devices">{{ render_viz(td.viz) }}</div>{% endif %}</aside></div>`
  - optional foot: cta-url band from `ctx.brand.company_url_display` (fallback; never fabricate), or `td.credentials`.
  - NO em dashes; token-only; all `db-*` classes scoped.
- [ ] **Step 4:** Run TDD tests → PASS; `test_no_literals_in_architecture.py -q` → PASS.
- [ ] **Step 5 (checkpoint):** unit green + guard green.

### Task 4 — Model CSS (dark interior rail, matched to the ref)

**Files:** create `styles/treatments/a4_bi_dashboard.css`, guard.

> **DRY-or-fork (explicit decision, audit finding #8):** the dashboard's interior
> dark rail is visually a sibling of `a4_case_study`'s full-bleed rail. There is
> NO CSS-sharing/`@import` mechanism between treatments (each PageFragment
> carries its own css string, deduped only by exact text — `assembler.py:1170-1175`).
> For v1 we choose a **scoped fork** (this treatment's own css) — the honest,
> low-risk choice: the dashboard rail is INTERIOR (inset, no bleed), carries viz
> devices + stats (NOT case stats/caption/quote), so a shared rail abstraction
> would be premature. Extract a shared rail only if a THIRD railed treatment
> appears. Decision recorded, not avoided.

- [ ] **Step 1:** Implement the scoped sheet `.page.treatment-a4_bi_dashboard`:
  - `.db-grid { display:flex; }` — narrative `flex: 1 1 65%`; rail `flex: 0 0 32%`, `background: var(--color-ink)`, `--color-on-dark` text, inset margins — the reference audit says the rail is interior with ~5% white margin right/bottom (mask it with rail border-radius:0 + inner padding; NO bleed).
  - rail caps, stat numerals (figure/statement like the case-study), `.db-devices .c-viz` sized to the rail (dark-on adapts: `--color-on-dark`).
  - foot: `border-top: 0.4mm solid var(--color-accent)` + URL in accent (mirror the `ef-foot`/`ef-cta` recipe).
- [ ] **Step 2:** Guard `<to ensure> no raw hex/font/em dash`. Ensure `test_panel_contrast.py` remains green (the dark rail uses `--color-ink`).
- [ ] **Step 3 (checkpoint):** render p<context> and READ the page on pixels — the ST-09 context now shows the dashboard fill.

### Task 5 — Wire the fixture host + verify the deck on pixels (no overflow)

**Files:** `fixtures/apex/viz_curation.py` ONLY if the two-device rail is content-safe; `resolved_package.json` re-baked via `build_package.py`.
- [ ] **Step 1:** Decide (from the Task 4 render): does the ST-09 context (1 device) already read as the intended spread? If yes → STOP enrichment (do not pad). If the rail looks thin with one device → add the grounded enrichment:
```python
# _st09_specs -> append a second, grounded device (figures verbatim in body);
# e.g. the "25–30 %" phrase -> {"preset":"split_bar", "a":{...verbatim...}} or
# a stat_strip; must pass _figure_grounded; keep total 2 devices max.
```
- [ ] **Step 2:** If enriched: `cd research/preprocessor && source .venv/bin/activate && python ../v7-renderer/fixtures/apex/build_package.py --no-fal` (produces the re-baked package; asserts 26 pages; writes `.fal_active` only when actually quality is needed).
- [ ] **Step 3:** Render: `cd research/v7-renderer && source .venv/bin/activate && export DYLD_FALLBACK_LIBRARY_PATH=… && python render.py --fast --no-visual-gate`.
- [ ] **Step 4:** Verify **physical == logical** (`fitz` page count == 26) and `overflow=[]` in the render log. Open `output/report-p05.png` (the dashboard) + p03/p06 (unchanged neighbors) — no clip, rail has margin, narrative reads to the foot.
- [ ] **Step 5:** Fix any visual gap the pixels reveal; iterate.

### Task 6 — Rebase the tests (same commit as the candidate change) + targeted verification

**Files:** `tests/test_treatment_slice.py`, `tests/test_render_r1.py` (stale 25 pins), `tests/test_viz_curation.py`
- [ ] **Step 1:** Update `test_treatment_slice.py:189-208` — the ST-09 slice now stamps `treatment-a4_bi_dashboard`; keep a second assertion that the evidence page stays `fill`.
- [ ] **Step 2:** `pytest tests/test_treatment_dashboard.py tests/test_treatment_slice.py tests/test_treatment_stylist.py tests/test_viz_curation.py -q` → green. Note (do NOT "fix" as part of scope) the pre-existing `25/26` stale pins (`test_treatment_slice.py:217`, `test_render_r1.py:362`) — flag as follow-up, not silently changed.
- [ ] **Step 3:** Full render once at the end (with `--export-idml`) → the deck must still be 26 logical == 26 physical, `overflow=[]`; visualize the full deck (`.output`) and sanity-check no contiguous-pair repeat.

---

## Verification protocol (every task)

Render: `cd research/v7-renderer && source .venv/bin/activate && export DYLIAB… && python render.py --fast --no-visual-gate` (fast = no convergence). Read `<output>/report-p<N>.png` for the required page. Guards: `pytest tests/test_no_literals_in_architecture.py tests/test_design_conformance.py -q` (plus the targeted file). Physical==logical: `python -c "import fitz; print(len(fitz.open('output/report_print.pdf')))"`.

---

## Self-review

- **Spec coverage:** all Layer-A tasks (template/css/selection) → Tasks 1–4,6; Layer-B (switch, curation) → Task 5 with the "only if fit-safe" gate; the no-overflow/in-bleed discipline → Tasks 3–4 + verification; the `formats` pin → Task 1.
- **Placeholder scan:** every macro is fully written; every command explicit; the "enrich with 25–30 %" step is content, not a TBD (it's shown in full with the grounding + overflow gates).
- **Type/naming:** `a4_bi_dashboard` consistent; classes `db-*` names consistent; `_REPO_ROOT`/`fragment`/`base.html.jinja` names referenced match the code the audit verified.