# Renderer Plan B — Reference-Quality Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task (fresh subagent per task + two-stage spec-then-quality review). Implementers use superpowers:test-driven-development. Steps use checkbox (`- [ ]`).

**Goal:** Rebuild the 14 renderer patterns to **reference quality** on the Plan-A foundation (tokens + Jinja2 + axis theming + visual-regression), composing an **atomic Jinja macro library**, integrating the package's **photos + charts**, and hitting the **22-item richness checklist** — while staying **provably brand-agnostic** (no client hex/font/name/label in code; serif headings come from the `headline_type` axis, never hardcoded).

**Architecture:** `page.data + assets + axes` → pattern `render(page, ctx)` does **data-prep only** → renders a `templates/st_XX.html.jinja` that composes **`components/*.jinja` macros** → CSS lives in **`styles/*.css`** (class-based, **semantic tokens only**) → assembler bundles head (token `:root` + enriched chrome) + deduped pattern CSS → WeasyPrint → **visual-regression** (intentionally re-baselined as each page is approved).

**Tech Stack:** Python 3.11, WeasyPrint, Jinja2, the Plan-A token layer, PyMuPDF (raster), Pillow (pixel-diff). Renderer at `research/v7-renderer/`.

**Predecessor:** spec `2026-05-30-renderer-architecture-migration-design.md` §6. **Build target (the bar):** `2026-05-30-reference-design-system.md` (§A global system, §B per-ST layouts, §C 22-item checklist).

---

## Conventions & Guardrails (read before any task)

- **NO GIT.** Verified by tests, not commits. Each task ENDS in a verification checkpoint (suite + visual review), not a `git commit`.
- **Renderer venv MUST be activated** for WeasyPrint: `cd research/v7-renderer && source .venv/bin/activate` (sets `DYLD_FALLBACK_LIBRARY_PATH`). It's **uv-managed** — install with `uv pip install …` (no bare pip).
- **Test command:** `cd research/v7-renderer && source .venv/bin/activate && python -m pytest tests/ -q` → baseline **48 passed**.
- **Render the apex deck:** `cd research/v7-renderer && source .venv/bin/activate && python render.py` → `output/report.pdf` + `output/report-p1..20.png`.
- **The reference (quality bar, NOT a schema source):** `APEX - KI DMC Report v1 (1).pdf` (repo root). Compare page-by-page; NEVER copy a client literal from it.
- **Visual-regression is EXPECTED to fail during this rebuild** — it detects the intended redesign. After visual-review-vs-reference approves a page, **re-baseline deliberately**: `UPDATE_BASELINES=1 python -m pytest tests/test_visual_regression.py -q`. Re-baselining is a reviewed step, never automatic.
- **Brand-agnostic (cardinal rule):** macros/styles/templates use SEMANTIC tokens only (`var(--color-*)`, `var(--font-display)`, `var(--space-*)`, `var(--type-*)`). NO raw hex, NO `'Montserrat'`/`'Playfair'` literals, NO client name/German-label-in-logic. The Phase-3 guard locks this.
- **Serif headings come from the axis:** apex is `headline_type=serif`, so `--font-display` already resolves to Playfair. Headlines use `var(--font-display)` → serif for apex, sans for a sans-brand. Never hardcode serif.
- **Python 3.11 trap:** no backslash inside f-string `{…}` expressions (precompute). Jinja avoids most of this — prefer templates over f-strings.
- **Assemble/never-crash preserved:** the assembler's per-page try→`_generic`→placeholder isolation, per-page folio (`string-set`), overflow + accent-budget validators stay intact.

## Semantic tokens available (from `tokens/compile_tokens.py`)
Fonts: `--font-display` (serif if `headline_type=serif`, else sans-head), `--font-head` (sans), `--font-body` (sans), `--font-serif`, `--font-sans-head`, `--font-sans-body`.
Colors: `--color-primary`, `--color-accent`, `--color-ink` (dark), `--color-muted`, `--color-surface` (page bg), `--color-body` (#333), `--color-on-dark` (#fff). **(Task 1 adds `--color-accent-tint`, `--color-on-accent`, `--color-ground-wash`.)**
Spacing: `--space-1..6` (2/3/4/6/8/12mm). Type: `--type-eyebrow|label|body|h3|h2|display|display-xl`.
Axis attrs on `<html>`: `data-headline-type`, `data-ground-mode`, `data-texture`.

## File Structure
**Created:** `components/` (Jinja macros), `styles/` (static CSS), `templates/st_*.html.jinja` (14 page templates), `tokens/` token additions, `tests/test_components.py`, `tests/test_no_literals_in_patterns.py`.
**Modified:** `tokens/base.tokens.json` + `compile_tokens.py` (new color roles), `templating.py` (load `components/`), `assembler.py` (enriched head + bundle `styles/components.css`), all 14 `patterns/st_*.py` (data-prep → Jinja), `tests/test_visual_regression.py` baselines (re-baselined).
**Deleted:** `patterns/_components.py` (replaced by macros), `shared/css/` + `shared/components/` (empty scaffold; final location is `styles/` + `components/`).

---

# PHASE 1 — Foundation + Flagship → USER GATE

### Task 1: Token roles + directory reconciliation

**Files:** Modify `tokens/base.tokens.json`, `tokens/compile_tokens.py`; create `components/.gitkeep`, `styles/.gitkeep`; delete `shared/`; Test `tests/test_tokens.py`

- [ ] **Step 1: Write failing test** (`tests/test_tokens.py` append): `compile_tokens` emits `--color-accent-tint`, `--color-on-accent`, `--color-ground-wash`.

```python
def test_emits_tint_and_ground_roles():
    from tokens.compile_tokens import compile_tokens, BrandAxes
    from brand_tokens import BrandConfig
    css, _ = compile_tokens(BrandConfig(brand_primary="#123", brand_accent="#456",
        brand_neutral_dark="#111", brand_neutral_mid="#888", brand_neutral_light="#eee",
        font_heading="X", font_body="Y", qr_target_url="u", company_name_short="c", company_url_display="d"),
        BrandAxes(accent_mechanic="tonal_same_hue"))
    assert "--color-accent-tint:" in css
    assert "--color-on-accent:" in css
    assert "--color-ground-wash:" in css
```

- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** in `compile_tokens.py`: derive a tint from the accent as an `rgba()` at low alpha (compute via a small hex→rgb helper; keep it hue-agnostic — works for any brand). `--color-accent-tint` ≈ accent @ ~12% alpha; `--color-on-accent` = `--color-on-dark` (#fff) for contrasting fills / `--color-ink` for tonal_same_hue light fills (branch on `axes.accent_mechanic`); `--color-ground-wash` ≈ accent @ ~5% (the subtle page wash). Add these `lines.append(...)` after the existing color block. NO client literal — all derived from `brand.brand_accent`.
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Reconcile dirs** — create `components/` + `styles/` (with `.gitkeep`), remove the empty `shared/css/` + `shared/components/`.
- [ ] **Step 6: Verify** — full suite → **48 passed** (+1 new = 49); visual-regression unchanged (new vars unused yet). `ls shared 2>/dev/null` → gone.

### Task 2: Atomic macro library (flagship subset) + `styles/components.css`

**Files:** Create `components/{pill,eyebrow,section_label,media_figure,qr,stat_strip,pull_quote}.jinja`, `styles/components.css`; Modify `templating.py` (loader incl. `components/`), `assembler.py` (bundle `styles/components.css` into head); Test `tests/test_components.py`

- [ ] **Step 1:** In `templating.py`, change the loader to `FileSystemLoader([str(_TEMPLATES), str(_COMPONENTS)])` so `{% from 'pill.jinja' import pill %}` resolves.
- [ ] **Step 2: Write failing tests** (`tests/test_components.py`): render each macro standalone, assert the device is present AND contains NO raw hex / font literal (only `var(--…)`).

```python
def _render(src, **kw):
    from templating import get_env
    return get_env().from_string(src).render(**kw)

def test_pill_uses_tokens_only():
    html = _render("{% from 'pill.jinja' import pill %}{{ pill('FALLSTUDIE 01') }}")
    assert "FALLSTUDIE 01" in html
    assert "#" not in html and "Montserrat" not in html  # no literals in markup

def test_stat_strip_emits_accent_values():
    html = _render("{% from 'stat_strip.jinja' import stat_strip %}{{ stat_strip([{'value':'+312%','label':'Umsatz'}]) }}")
    assert "+312%" in html and "Umsatz" in html
```

- [ ] **Step 3: Run → FAIL.**
- [ ] **Step 4: Implement the macros** (markup only; classes map to `styles/components.css`). Example `components/pill.jinja`:

```jinja
{% macro pill(label, variant='outline') -%}
<span class="kpill kpill--{{ variant }}">{{ label }}</span>
{%- endmacro %}
```
Similarly: `eyebrow(text)` → `<span class="eyebrow">`; `section_label(text)` → `<div class="section-label">` (uppercase, letter-spaced); `media_figure(src, alt='', caption='', ratio='4x3', frame=false)` → `<figure class="media media--{{ratio}}">` with a `background-image` div (graceful empty when `src` falsy); `qr(svg)` → `<div class="qr">{{ svg }}</div>`; `stat_strip(stats)` → `.stat-strip` with `.stat-value`(accent) + `.stat-label`; `pull_quote(text, attribution='', on_panel=true)` → `.pull-quote`.

- [ ] **Step 5: Implement `styles/components.css`** — one class block per macro, **semantic tokens only**. Example:

```css
.kpill { display:inline-block; font-family:var(--font-head); font-weight:700; font-size:var(--type-eyebrow);
  letter-spacing:0.14em; text-transform:uppercase; padding:1.6mm 5mm; border-radius:99mm; line-height:1; }
.kpill--outline { color:var(--color-accent); border:0.4mm solid var(--color-accent); }
.kpill--solid { color:var(--color-on-accent); background:var(--color-accent); }
.section-label { font-family:var(--font-head); font-weight:700; font-size:var(--type-eyebrow);
  letter-spacing:0.12em; text-transform:uppercase; color:var(--color-accent); margin:0 0 var(--space-2) 0; }
.stat-strip { display:flex; gap:var(--space-4); }
.stat-strip .stat-value { font-family:var(--font-head); font-weight:800; font-size:var(--type-h2); color:var(--color-accent); line-height:1; }
.stat-strip .stat-label { font-family:var(--font-body); font-weight:600; font-size:var(--type-eyebrow);
  letter-spacing:0.04em; text-transform:uppercase; color:var(--color-body); margin-top:var(--space-1); }
/* media, qr, pull-quote, eyebrow … */
```

- [ ] **Step 6:** In `assembler.py` `shared_head_css`, append the contents of `styles/components.css` once (read the file) so component classes are globally available; patterns then return only their own `styles/st_XX.css`.
- [ ] **Step 7: Run → PASS**; full suite green. (Components unused by patterns yet ⇒ visual-regression still matches; if the appended CSS changes nothing visually, baselines hold.)

### Task 3: Enrich the shared head — header band, folio wash, axis page-ground

**Files:** Modify `assembler.py` (`shared_head_css`); Test `tests/test_assembler.py` (or new)

- [ ] **Step 1: Write failing test**: the head CSS contains a header-band rule + a bottom folio wash + an axis-driven ground hook.

```python
def test_head_has_band_and_wash():
    from assembler import shared_head_css, FONT_DIR
    from brand_tokens import parse_brand_tokens
    brand = parse_brand_tokens({...minimal valid 10-field...})
    css = shared_head_css(brand, FONT_DIR)
    assert "@top-left" in css and "@bottom-left" in css
    assert "linear-gradient" in css  # the pale folio wash
```

- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** (per reference §A "persistent chrome"):
  - **Header band:** keep `@top-left` wordmark; add a thin vertical divider + a small uppercase eyebrow via `@top-right` (or a running element). Token-colored.
  - **Folio wash:** `@bottom-left` folio sits over a pale gradient — add a `@page` bottom wash using `--color-ground-wash` (a faint `linear-gradient` anchored to the page bottom).
  - **Axis page-ground:** add a body/page background hook driven by `[data-ground-mode]`/`[data-texture]` (e.g. `[data-ground-mode="dark"]{ --color-surface: var(--color-ink); }` already possible; add a subtle `--color-ground-wash` behind content). Keep it subtle behind CONTENT pages (fixes the "texture stuck on one page" complaint); full-bleed atmospheric stays for ST-31/32.
- [ ] **Step 4: Run → PASS**; render the deck; this changes ALL pages' chrome → visual-regression will flag every page. **Visual-review the chrome vs the reference; if right, re-baseline** (`UPDATE_BASELINES=1`). Full suite green.

### Task 4: Rebuild the FLAGSHIP — ST-07A case study

**Files:** Create `templates/st_07a.html.jinja`, `styles/st_07a.css`; Modify `patterns/st_07a.py` (data-prep → render template); Test `tests/test_render_r2.py` (ST-07A assertions)

- [ ] **Step 1: Write failing test**: the rebuilt ST-07A fragment contains the kicker pill, a serif-display headline (uses `var(--font-display)`), the sidebar (portrait figure + pull-quote + QR + accent link), the stat strip, and uppercase section labels — and NO raw hex / font literal.

```python
def test_st07a_reference_devices_and_no_literals():
    page = _apex_page("ST-07A")            # load from fixture
    frag = st_07a.render(page, _ctx())
    h = frag.html + frag.css
    assert "kpill" in h and "stat-strip" in h and "pull-quote" in h and "qr" in h
    assert "var(--font-display)" in (frag.css)        # serif via axis
    assert "Montserrat" not in frag.css and "#" not in frag.css.replace("var(--", "")  # tokens only
```

- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** per reference §B ST-07A. `patterns/st_07a.py` keeps its data contract (preserve every field it reads today: `kurzportraet, ausgangsproblem, ziel, loesung, ergebnis_text, pullquote.{text,attribution}, fallstudie_number, ergebnis_headline, kunde.{name,company_url}, ergebnis_metrics[]`; portrait asset `slot_id=="case_study_portrait"`), does data-prep + builds the QR svg, then renders `templates/st_07a.html.jinja` which `{% from %}`-imports `pill, media_figure, qr, stat_strip, pull_quote, section_label` and composes: **left sidebar** = `media_figure(portrait)` + name/role + accent link + `qr` + `pull_quote`; **right column** = `pill('FALLSTUDIE 0N','solid')` + serif `<h1 class="case-headline">` + lede + `section_label`+body ×(Ausgangssituation/Ziel/Lösung/Ergebnis, non-empty only) + `stat_strip(ergebnis_metrics)`. `styles/st_07a.css` = layout only, semantic tokens (headline `font-family:var(--font-display); font-size:var(--type-display)`). Keep the non-empty-section logic (overflow guard) + table/grid two-column.
- [ ] **Step 4: Run → PASS.**

### Task 5: 🚦 FLAGSHIP USER GATE (mandatory stop)

- [ ] **Step 1:** Render the full deck (`python render.py`); locate the ST-07A page PNG (`output/report-pNN.png`).
- [ ] **Step 2:** Present to the user **side-by-side: the rebuilt ST-07A page vs the reference's case-study page** (`APEX - KI DMC Report v1 (1).pdf`). State which of the 22 checklist items it hits (pills, accent stat numbers, two-column+sidebar, serif/sans, uppercase section labels, pull-quote, QR-in-sidebar).
- [ ] **Step 3: STOP. Get explicit approval that this is the quality bar.** If the user wants changes, iterate ST-07A + the macros/styles until approved. **Only after approval:** re-baseline the changed pages and proceed to Phase 2. *(This is the spec's "lock the bar" gate — do not roll out 13 patterns against an unapproved bar.)*

---

# PHASE 2 — Rollout (after the bar is locked)

> Each task: build `templates/st_XX.html.jinja` + `styles/st_XX.css` + rewrite `patterns/st_XX.py` (data-prep → template), composing macros (extend the library as needed), integrating the page's assets, matching reference §B + the §C checklist items listed. TDD: a unit test asserting the named devices are present + no literals; then render + **visual-review vs the reference** + re-baseline. Preserve each pattern's CURRENT data-field contract (read the existing `patterns/st_XX.py` + the fixture). New macros built here: `numbered_marker, numbered_block, callout_panel (tint), dark_cta_panel, bar_chart, step_card, horizontal_flow, logo_wall, color_block_opener, cost_block, url_band, stat_callout_card, banner_figure` — all semantic-token-only in `styles/components.css`.

### Task 6: ST-01 Cover (showcase #2)
**Reference §B ST-01; checklist #8,#4,#18,#20.** Full-bleed hero photo (asset `slot_id` cover hero, e.g. `1_cover_hero`) + dark scrim; top nav/eyebrow row; lower-left serif name+role; huge `var(--font-display)` title (`--type-display-xl`); vertical **stat rail** of callouts; subtitle bar. Macros: `media_figure(full-bleed)`, `stat_strip`(vertical variant), `eyebrow`. Verify the proven WeasyPrint rule (background on the block w/ min-height; non-empty flex). Test + visual-review + re-baseline.

### Task 7: ST-09 Status-quo + ST-14 False-beliefs (numbered-block family)
**§B ST-09/ST-14; checklist #10,#6,#11,#14.** Build `numbered_marker` + `numbered_block` + `callout_panel`(tint) + `color_block_opener` + an ohne/mit two-panel. **ST-09:** numbered symptom blocks (big accent numeral + bold title + body) + tint insight panel; integrate the status-quo scene asset (`4_/5_status_quo_scene`). **ST-14:** solid accent color-block behind the opener + numbered belief→reality blocks (myth + distinct "Realität" sub-block + source) + optional ohne/mit. Tests + visual-review + re-baseline.

### Task 8: ST-06 Mechanism (richest interior)
**§B ST-06; checklist #12,#13,#5.** Build `step_card`, `horizontal_flow` (connectors), `bar_chart` (token bars from `data`, NOT a Stage-6 SVG), `stat_callout_card` (floated), `dark_cta_panel` ("Das Ergebnis" recap). Compose: numbered step cards → horizontal flow diagram → dark recap panel → bar chart + floated stat-callout cards. Tests + visual-review + re-baseline.

### Task 9: ST-02 Outlook + ST-08 FAQ
**§B ST-02/ST-08; checklist #6,#7,#18,#19.** **ST-02:** large serif question-headline + two-column body + tint **check-list panel** (`callout_panel` + check items). **ST-08:** serif heading + two-column **Q&A stack** (accent question + body answer). Tests + visual-review + re-baseline.

### Task 10: ST-05 About + ST-07B Theory
**§B ST-05/ST-07B; checklist #16,#4,#6,#17.** **ST-05:** serif heading + **stat trio** ("in Zahlen", `stat_strip`) + grayscale **logo wall** (`logo_wall` macro; grayscale filter); integrate `founder.png` if the about layout calls for a portrait. **ST-07B:** serif headline + prose + distinct **key-insight callout** (`callout_panel` w/ accent rule + larger italic) + optional before/after. Tests + visual-review + re-baseline.

### Task 11: ST-22 Collaboration + ST-31/ST-32 Breathing
**§B ST-22/ST-31/32; checklist #9,#12,#22,#20.** **ST-22:** full-width **banner photo** header (`banner_figure`, a client photo) + horizontal **numbered step flow** (Schritt 1→N) with connectors + optional durations (`horizontal_flow`). **ST-31/32:** full-page atmospheric ground (the `report_atmospheric_gradient`/`background_texture` asset + translucent geometric shapes), little/no text — a deliberate pacing page. Tests + visual-review + re-baseline.

### Task 12: ST-FAZIT Summary + ST-03 Hard-CTA back cover
**§B ST-FAZIT/ST-03; checklist #15,#20,#21.** Build `url_band` (giant full-width accent URL button) + `cost_block` + geometric-shapes layer. **ST-FAZIT:** serif "Zusammenfassung" header band + recap + large **These pull-statement** + cost block + full-width accent URL band. **ST-03:** saturated brand-ground + low-opacity geometric shapes + short headline + **oversized accent URL** (biggest type on page) as full-width button + `qr` + logo. Tests + visual-review + re-baseline.

---

# PHASE 3 — Lock & sign-off

### Task 13: Extend the pollution guard to components/styles/patterns
**Files:** Create `tests/test_no_literals_in_patterns.py`

- [ ] **Step 1:** After ALL 14 patterns are converted, add a guard that scans `components/**.jinja`, `styles/**.css`, `templates/st_*.html.jinja`, and `patterns/st_*.py` for raw hex (`#[0-9a-fA-F]{3,6}`) and font-family literals (`'Montserrat'`/`'Playfair'`/`'Source Sans'`) and `if client`/brand-name branching → MUST find NONE (allowed only in `tokens/base.tokens.json` primitives + per-client data). 
- [ ] **Step 2: Run → PASS** (proves the rebuild left zero literals). If it fails, fix the offending pattern to use a token. Keep `test_no_coral_in_chassis_logic` + `test_no_literals_in_architecture` green.

### Task 14: Final full-deck review + re-baseline + suite
- [ ] **Step 1:** Render the full deck; **page-by-page visual review vs the reference**, ticking every one of the **22 §C checklist items** (record which page satisfies each). Fix any gap in the owning pattern.
- [ ] **Step 2:** Confirm assets integrated (cover hero, status-quo scene, case-study portraits, collaboration banner, atmospheric ground, founder, logo wall) — no dropped assets (the original complaint).
- [ ] **Step 3:** Re-baseline all 20 visual-regression PNGs (reviewed), run full suite → all green; overflow validator clean (20 logical = 20 physical pages).
- [ ] **Step 4: 🚦 Final user review** of the complete deck vs the reference.

---

## Self-Review

- **Spec coverage:** §6 atomic components → Task 2 + Phase-2 macros; Jinja templating → all patterns; asset integration (the dropped-asset fix) → Tasks 4,6,7,10,11; axis serif → tokens + every headline via `--font-display`; ground/texture wash → Task 3; visual-regression re-baseline → every Phase-2 task + Task 14; extended guards → Task 13. Reference §B all 14 STs → Tasks 4,6-12. §C all 22 items → mapped across tasks, signed off in Task 14. ✔
- **Flagship-first:** Phase 1 builds foundation + ST-07A and STOPS at the user gate (Task 5) before any rollout — the spec's "lock the bar" requirement. ✔
- **Placeholder scan:** Phase 1 has real macro/CSS/test code; Phase 2 tasks are concrete (named macros + §B layout + §C items + assets + data contract preserved from the existing pattern), with the CSS conventions established by the flagship + `components.css` (not vague). ✔
- **Type/name consistency:** macro names (`pill, eyebrow, section_label, media_figure, qr, stat_strip, pull_quote`, + Phase-2 set) and token names (`--color-accent-tint`, `--font-display`, …) used consistently; `render(page, ctx)->PageFragment` + assembler dispatch preserved throughout. ✔
- **Brand-agnostic:** semantic-tokens-only enforced by the Task-13 guard; serif via axis; no client literal anywhere in logic. The direct fix for the pollution failure mode. ✔
- **No-git:** every task ends in suite + visual-review + deliberate re-baseline. ✔
