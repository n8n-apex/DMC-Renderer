# Renderer Phase A — Theme-Lock + Capability Widening — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> **NO GIT in this repo** (see `context.md`). Every "Checkpoint" below = run the full renderer suite + guards + (for visual tasks) re-baseline visual-regression deliberately. There is NO `git commit` step — never run git.

**Goal:** Close most of the visible APEX→reference quality gap by locking a distinctive, dark, dense, brand-driven *theme* and widening renderer *capabilities*, so the closed loop (Phase B) has a high ceiling to converge to.

**Architecture:** Layer 2 (`research/v7-renderer/`, WeasyPrint HTML/CSS→PDF). This is **Phase A** of the Self-Correcting Quality Architecture (`docs/superpowers/specs/2026-06-03-self-correcting-quality-architecture-design.md` §10) and **subsumes** the 4b renderer spec (`docs/superpowers/specs/2026-06-02-renderer-phase-4b-v2-consumption-design.md`). It is the *theme-lock* (spec §5.3) + *capability-widening* (spec §5.5) pass: no closed loop yet. Two stages: **Stage 1 (theme-lock, T1–T7)** = the APEX-visible transformation; **Stage 2 (GEN widening, T8–T10)** = components APEX doesn't exercise but the Phase-B rubric needs active.

**Tech Stack:** Python 3.11, WeasyPrint, Jinja2 macros (`components/*.jinja`), DTCG tokens (`tokens/base.tokens.json` + `tokens/compile_tokens.py`), pytest + a pixel visual-regression net (`tests/test_visual_regression.py` + `tests/baselines/`). uv-managed venv; **must `source .venv/bin/activate`** (sets `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib`).

**Grounding (read, do not work from memory):**
- `docs/superpowers/specs/2026-06-03-self-correcting-quality-architecture-design.md` — master architecture; §8 (the renderer ceiling + font reality), §10 (Phase A scope), §12 (the photo-distribution principle + asset request).
- `docs/superpowers/specs/2026-05-30-richard-design-dna.md` — **§B axes, §C design devices, §D per-page recipes, §E the ranked gap list (★★★ levers), §F who-builds-what**. THE schema. The Apex PDF is the quality bar, NEVER a schema source.
- `docs/superpowers/specs/2026-06-02-renderer-phase-4b-v2-consumption-design.md` — §3 component table (the capability flags), §4 decomposition.

**Cardinal rule (non-negotiable):** no client name / hex / font literal in logic. Guards `test_no_coral_in_chassis_logic`, `test_no_literals_in_architecture` must stay green and cover every new module. Serif comes from the `headline_type` axis; the per-client font/colour are DATA. References ground composition, never brand values.

**Baseline state (verified 2026-06-03):** 144 tests pass; 20 visual-regression baselines frozen; 4b-1 already done (founder hero on ST-01, proof gallery + dark `.ab-lead` panel on ST-05, `--color-on-primary` token at `compile_tokens.py:95`, `dark_recap_panel` on ST-06, graceful photo-less ST-07A, running-header band). 27 macros exist.

---

## File Structure (what each task touches)

**Stage 1 — theme-lock (shared tokens + APEX-visible composition):**
- `fonts/Fraunces[*].ttf` (+ Italic, + `OFL-Fraunces.txt`) — NEW bundled default editorial serif (replaces Playfair as the chassis default).
- `tokens/base.tokens.json` — serif family → Fraunces; ADD a `hero` type tier.
- `tokens/compile_tokens.py` — read `brand.font_heading`/`font_body` into the font stacks (brand-preferred, bundled-fallback); loud warning on un-bundled brand font; emit `data-density`.
- `assembler.py` — @font-face Fraunces (replace Playfair); keep Montserrat + Source Sans 3.
- `styles/density.css` — NEW: `[data-density=compact|balanced|spacious]` rules. Bundled by `assembler.py`.
- `components/authority_panel.jinja` — NEW reusable dark panel macro.
- `components/ghost_numeral.jinja` — NEW oversized ghost/outline numeral.
- `components/pull_quote.jinja`, `components/url_band.jinja`, `components/two_tone_headline.jinja` — upsize quote glyph / make URL the biggest element / apply to section headers.
- `patterns/st_01.py … st_fazit.py` — adopt hero tier, dark panels, two-tone headers, ghost numerals, density, photo redistribution.
- `tests/test_tokens.py`, `tests/test_axes.py`, `tests/test_render_r2.py`, `tests/test_visual_regression.py` — extend.
- `fixtures/apex/` — regenerate the v2 package + render at the Stage-1 checkpoint.

**Stage 2 — GEN capability widening (synthetic-fixture tested):**
- `components/rating_card.jinja`, `review_card.jinja`, `review_grid.jinja`, `press_logo_wall.jinja`, `client_logo_wall.jinja` — NEW social-proof library.
- `components/charts/` — NEW inline-SVG chart macros (`before_after_bars`, `line_compare`, `donut`, `cost_math_strip`, `comparison_columns`, `money_infographic`) + `result_box.jinja` + `--color-positive` token.
- `patterns/st_testimonials.py`, `patterns/st_logowall.py` + registry — NEW page types (paired pre-processor models, flagged).
- `tests/fixtures/social_proof_sample.json`, `tests/fixtures/charts_sample.json` — NEW synthetic fixtures to render GEN components (APEX carries no such data).

---

## STAGE 1 — THEME-LOCK (T1–T7) → APEX visual checkpoint

### Task 1: Wire the brand/OSS heading font end-to-end (fixes the #1 "generic" tell)

**Why:** `compile_tokens.py:64-71` emits `--font-serif` from `base.tokens.json` (hardcoded Playfair) and **never reads `brand.font_heading`/`font_body`** (DNA §E gap; spec §8 "the #1 tell"). Two fixes: (a) replace the Playfair *default* with a distinctive OFL editorial serif (**Fraunces** — variable, optical-sizing, OFL, a Didone-adjacent face matching Richard's serif decks, and NOT the Playfair "AI default"); (b) feed `brand.font_heading`/`font_body` into the font stacks so a supplied brand font wins, with a **loud warning** when a named brand font is not bundled. (Copying a real licensed font *file* into the package is Phase C / the asset request — spec §12; here we wire the data path + the default + the warning.)

**Files:**
- Create: `fonts/Fraunces[opsz,wght].ttf`, `fonts/Fraunces-Italic[opsz,wght].ttf`, `fonts/OFL-Fraunces.txt`
- Modify: `tokens/base.tokens.json:15-19` (font group), `tokens/compile_tokens.py:58-95`, `assembler.py:145-150`
- Test: `tests/test_tokens.py`

- [ ] **Step 1: Download Fraunces (OFL variable TTF) into `fonts/`.**
Run (from `research/v7-renderer/`):
```bash
curl -fsSL -o "fonts/Fraunces[opsz,wght].ttf" \
  "https://github.com/google/fonts/raw/main/ofl/fraunces/Fraunces%5Bopsz,wght%5D.ttf"
curl -fsSL -o "fonts/Fraunces-Italic[opsz,wght].ttf" \
  "https://github.com/google/fonts/raw/main/ofl/fraunces/Fraunces-Italic%5Bopsz,wght%5D.ttf"
curl -fsSL -o "fonts/OFL-Fraunces.txt" \
  "https://github.com/google/fonts/raw/main/ofl/fraunces/OFL.txt"
ls -la fonts/Fraunces*
```
Expected: two TTFs (each >100KB) + the licence. If the axis-suffix in the filename differs (Fraunces ships `[SOFT,WONK,opsz,wght]`), use whatever the repo serves and keep the on-disk name consistent in Steps 3–4. Verify with `python -c "from fontTools.ttLib import TTFont; f=TTFont('fonts/Fraunces[opsz,wght].ttf'); print(f['name'].getDebugName(1))"` → prints `Fraunces`.

- [ ] **Step 2: Write the failing test** in `tests/test_tokens.py`:
```python
def test_brand_heading_font_is_wired_into_font_stack():
    from brand_tokens import parse_brand_tokens
    from tokens.compile_tokens import compile_tokens, BrandAxes
    brand = parse_brand_tokens(_sample_tokens(font_heading="Acme Grotesk", font_body="Acme Text"))
    css, _ = compile_tokens(brand, BrandAxes(headline_type="sans"))
    # brand-supplied family must appear, ahead of the bundled fallback
    assert "Acme Grotesk" in css
    assert "Acme Text" in css

def test_default_serif_is_fraunces_not_playfair():
    from brand_tokens import parse_brand_tokens
    from tokens.compile_tokens import compile_tokens, BrandAxes
    brand = parse_brand_tokens(_sample_tokens())
    css, _ = compile_tokens(brand, BrandAxes(headline_type="serif"))
    assert "Fraunces" in css
    assert "Playfair" not in css

def test_unbundled_brand_font_emits_warning(caplog):
    import logging
    from brand_tokens import parse_brand_tokens
    from tokens.compile_tokens import compile_tokens, BrandAxes
    brand = parse_brand_tokens(_sample_tokens(font_heading="Nonexistent Licensed Face"))
    with caplog.at_level(logging.WARNING):
        compile_tokens(brand, BrandAxes())
    assert any("Nonexistent Licensed Face" in r.message for r in caplog.records)
```
Add a `_sample_tokens(**overrides)` helper if not present (a dict with all 10 required keys; defaults `font_heading="Montserrat"`, `font_body="Source Sans 3"`).

- [ ] **Step 3: Run → confirm FAIL.** `source .venv/bin/activate && python -m pytest tests/test_tokens.py -k "font" -v` → FAIL (brand font absent / Playfair present / no warning).

- [ ] **Step 4: Implement in `tokens/compile_tokens.py`.** Replace the font block (lines 64-73) with brand-aware stacks + a bundled-family registry + warning:
```python
import logging
_LOG = logging.getLogger(__name__)
# Families whose font files this renderer bundles (assembler.py @font-face).
_BUNDLED_FAMILIES = {"Montserrat", "Source Sans 3", "Source Sans Pro", "Fraunces"}

def _font_stack(brand_family: str, bundled_default: str, generic: str) -> str:
    """brand family first (if it differs), then the bundled default, then generic.
    Warns when the brand family is not bundled (it will fall back at render)."""
    parts = []
    bf = (brand_family or "").strip()
    if bf and bf not in (bundled_default,):
        parts.append(f"'{bf}'")
        if bf not in _BUNDLED_FAMILIES:
            _LOG.warning(
                "brand font %r is not bundled with the renderer; falling back to %r. "
                "Supply the font file to fonts/ (+ assembler @font-face) to use it.",
                bf, bundled_default,
            )
    parts.append(f"'{bundled_default}'")
    parts.append(generic)
    return ", ".join(parts)
```
Then in `compile_tokens`, emit:
```python
    display_family = "var(--font-serif)" if axes.headline_type == "serif" else "var(--font-sans-head)"
    lines.append(f"  --font-sans-head: {_font_stack(brand.font_heading, 'Montserrat', 'sans-serif')};")
    lines.append(f"  --font-sans-body: {_font_stack(brand.font_body, 'Source Sans 3', 'sans-serif')};")
    lines.append(f"  --font-serif: {font['serif']};")  # base.tokens.json now → Fraunces
    lines.append(f"  --font-display: {display_family};")
    lines.append("  --font-head: var(--font-sans-head);")
    lines.append("  --font-body: var(--font-sans-body);")
```
Update `tokens/base.tokens.json` font.serif → `"'Fraunces', Georgia, serif"`.
Update `assembler.py:149-150`: replace the two Playfair `@font-face` lines with Fraunces (match the on-disk filename from Step 1, URL-encode the brackets `%5B…%5D`), `font-weight:100 900`.

- [ ] **Step 5: Run → confirm PASS.** `python -m pytest tests/test_tokens.py -v` → PASS.

- [ ] **Step 6: Checkpoint (NO git).** `python -m pytest tests/ -q` → expect 147 pass (144 + 3). Guards green. **Visual-regression will diff** (Playfair→Fraunces is intended) — do NOT re-baseline yet; the Stage-1 checkpoint (after T7) re-baselines once, against the reference. Note the expected visual-regression failures.

---

### Task 2: Hero type tier + bigger display headlines

**Why:** type tops out at 34pt (`base.tokens.json:10`); DNA §C1 wants *giant* two-tone display titles on covers/openers. Add a hero tier and apply it.

**Files:** Modify `tokens/base.tokens.json:7-11`, `patterns/st_01.py` (cover title), `tests/test_tokens.py`. Touch section-opener CSS in `patterns/st_06.py`/`st_09.py`/`st_14.py` only where the headline is the focal element.

- [ ] **Step 1: Failing test** — `tokens/base.tokens.json` exposes a `hero` tier larger than `display-xl`:
```python
def test_hero_type_tier_exists_and_is_largest():
    import json, pathlib
    t = json.loads(pathlib.Path("tokens/base.tokens.json").read_text())["type"]
    def pt(v): return float(v["$value"].replace("pt",""))
    assert "hero" in t
    assert pt(t["hero"]) >= 48
    assert pt(t["hero"]) > pt(t["display-xl"])
```
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement.** Add to `base.tokens.json` type group: `"hero": {"$value": "52pt"}` and bump `"display-xl": {"$value": "40pt"}`. (`compile_tokens` already loops the whole `type` group at lines 99-100 → `--type-hero` emits automatically.)
- [ ] **Step 4: Apply** `var(--type-hero)` to the ST-01 cover title (the two-tone display); use `--type-display-xl` for section openers. Keep `line-height` tight (~0.95) and `letter-spacing` slightly negative on hero per editorial display convention.
- [ ] **Step 5: Run → PASS.** `python -m pytest tests/test_tokens.py -v`.
- [ ] **Step 6: Checkpoint.** Full suite green (visual-regression diffs expected on cover — defer re-baseline to T7).

---

### Task 3: Wire the `density` axis (fix the dead-whitespace / not-magazine-dense gap)

**Why:** `density` is declared (`compile_tokens.py:31`) but never emitted to `data_attrs` (lines 110-114) or consumed (DNA §E gap #9 "too airy"; spec §10 "wire the density axis"). Emit `data-density` and add CSS that tightens column gaps / line-height / paragraph spacing for `compact`, loosens for `spacious`.

**Files:** Create `styles/density.css`; Modify `tokens/compile_tokens.py:110-114`, `assembler.py` (bundle the new stylesheet), `tests/test_axes.py`.

- [ ] **Step 1: Failing test** in `tests/test_axes.py`:
```python
def test_density_axis_emitted_as_data_attr():
    from tokens.compile_tokens import compile_tokens, BrandAxes
    from brand_tokens import parse_brand_tokens
    brand = parse_brand_tokens(_sample_tokens())
    _, attrs = compile_tokens(brand, BrandAxes(density="compact"))
    assert attrs.get("data-density") == "compact"
```
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement.** In `compile_tokens.py` add `"data-density": axes.density` to the `data_attrs` dict. Create `styles/density.css`:
```css
/* Density axis — value-driven content tightness. Brand-agnostic. */
:root { --density-col-gap: var(--space-5); --density-lead: 1.5; --density-para: var(--space-3); }
[data-density="compact"]  { --density-col-gap: var(--space-3); --density-lead: 1.36; --density-para: var(--space-2); }
[data-density="spacious"] { --density-col-gap: var(--space-6); --density-lead: 1.62; --density-para: var(--space-4); }
.l-cols { column-gap: var(--density-col-gap); }
p, .body { line-height: var(--density-lead); margin-bottom: var(--density-para); }
```
Bundle it in `assembler.py`'s shared head (alongside `components.css`). Ensure multi-column body blocks reference `--density-col-gap` and body text references `--density-lead`/`--density-para` (update the relevant base/body CSS so the variables take effect).
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Checkpoint.** Full suite green. (Apex axis is currently `balanced`; the Stage-1 checkpoint may set apex→`compact` in the fixture to tighten — decide at T7 against the reference.)

---

### Task 4: Reusable dark `authority_panel` macro + pale-panel audit

**Why:** DNA §C3 / §E gap #4 (★★★): authority panels must be **dark** (navy/ink/primary) with `--color-on-primary` text, never pale accent-tint. 4b-1 added the token + `dark_recap_panel` (ST-06) + `.ab-lead` (ST-05) but only there. Generalize a reusable panel and **audit every pattern** for pale-tint "authority" fills (positioning blocks, stat rails, CTA).

**Files:** Create `components/authority_panel.jinja`; Modify `styles/components.css`, `patterns/st_05.py`, `patterns/st_07a.py`, `patterns/st_03.py`; audit all `patterns/*.py` + `styles/*.css`; Test `tests/test_render_r2.py`.

- [ ] **Step 1: Failing test** — the macro renders a dark panel with on-dark text and no pale-tint fill:
```python
def test_authority_panel_is_dark_with_on_color():
    from tests._render_helpers import render_macro  # existing helper pattern
    html = render_macro("authority_panel", {"body": "X", "eyebrow": "POSITIONIERUNG"})
    assert "c-authority" in html
    # CSS class is bound to --color-ink / --color-primary + --color-on-primary, never accent-tint
```
(Mirror the existing macro-render test approach in `tests/test_render_r2.py`; if no `render_macro` helper exists, inline a Jinja `Environment` render of the macro file as other macro tests do.)
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** `components/authority_panel.jinja` — a flexible dark panel (eyebrow + heading + body + optional stat row slot), CSS class `.c-authority { background: var(--color-ink); color: var(--color-on-dark); }` (or `--color-primary` + `--color-on-primary` variant via a `tone="primary"` param). Reuse `--color-on-primary` (compile_tokens.py:95).
- [ ] **Step 4: Audit + apply.** Grep `patterns/*.py` and `styles/*.css` for panel fills using `--color-accent`, `--color-accent-tint`, `--color-ground-wash`, or rgba-accent on a *panel/box* role; convert authority panels to the dark macro. Apply to: ST-05 positioning, ST-07A case-study stat rail, ST-03 back-cover/CTA ground. Leave genuine *light tint callouts* ("Tipp"/insight, green result box) as light — those are correct per DNA §C3 (only the **authority** panels must be dark).
- [ ] **Step 5: Run → PASS.** Brand-agnostic guard green (semantic tokens only).
- [ ] **Step 6: Checkpoint.** Full suite green.

---

### Task 5: Decorative glyphs — `ghost_numeral` macro + upsized quote glyph

**Why:** DNA §C1/§C6: oversized ghost/outline numerals + giant typographic quote marks are a recurring richness device (gap #13). `pull_quote.jinja` already has a quote glyph — verify/upsize. Ghost numerals are MISSING.

**Files:** Create `components/ghost_numeral.jinja`; Modify `components/pull_quote.jinja`, `patterns/st_07a.py` (Fallstudie number), `patterns/st_06.py` (step/section numbers); Test `tests/test_render_r2.py`.

- [ ] **Step 1: Failing test** — `ghost_numeral` renders a large outline numeral element:
```python
def test_ghost_numeral_renders_large_outline_digit():
    html = render_macro("ghost_numeral", {"n": 3})
    assert "c-ghost-num" in html and ">3<" in html
```
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** `ghost_numeral.jinja`: a `<span class="c-ghost-num">{{ n }}</span>` with CSS `.c-ghost-num { font-family: var(--font-display); font-size: calc(var(--type-hero) * 1.6); line-height: 1; color: transparent; -webkit-text-stroke: 1.5px var(--color-accent); opacity: .18; }` (outline; if WeasyPrint ignores `-webkit-text-stroke`, fall back to a low-opacity solid `--color-accent` fill — verify in the render and pick the one that paints). Position it behind/beside the section number. Upsize the `pull_quote` glyph to `≥3×` body per DNA §C1 if not already.
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Checkpoint.** Full suite green.

---

### Task 6: Two-tone section headers + CTA URL band (URL = biggest element)

**Why:** DNA §C1 two-tone headlines recur beyond the cover (section openers); §C3 CTA band makes the **URL the single biggest element**, QR subordinate. `two_tone_headline` + `url_band` macros exist — extend their application.

**Files:** Modify `components/url_band.jinja`, `patterns/st_03.py` (back-cover CTA), `patterns/st_22.py` (FAQ CTA), and section openers `patterns/st_06.py`/`st_09.py`/`st_14.py` to use `two_tone_headline`; Test `tests/test_render_r2.py`.

- [ ] **Step 1: Failing test** — `url_band` makes the URL the dominant type and gates the QR on `qr_enabled`:
```python
def test_url_band_url_is_dominant_and_qr_gated():
    html = render_macro("url_band", {"url": "www.x.de", "qr_enabled": False})
    assert "c-url-band__url" in html
    assert "c-qr" not in html  # QR suppressed when axis off
```
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement.** `url_band`: URL at `var(--type-display-xl)`+, full-width saturated `--color-primary`/`--color-ink` ground, optional `qr` only when `qr_enabled`. Apply `two_tone_headline` (neutral serif + bold-caps accent word) to the named section openers.
- [ ] **Step 4: Run → PASS.** (Apex `qr_enabled=false` per DNA §B → APEX uses URL pills, no QR; verify the gate.)
- [ ] **Step 5: Checkpoint.** Full suite green.

---

### Task 7: Roll the theme across remaining patterns + photo redistribution → APEX checkpoint

**Why:** 4b-1 touched 4/14 patterns; bring the locked theme (Fraunces, hero tier, dark panels, two-tone, ghost numerals, density) into the rest (`st_02, st_07b, st_08, st_09, st_14, st_22, st_31, st_32, st_fazit`). Apply the **photo-distribution principle** (spec §12): founder recurs *small* beside pull-quotes; the 3 proof photos are **distributed** as individual credibility moments, NOT crammed into one ST-05 row (4b-1's mistake); each case-study photo runs large on its own Fallstudie.

**Files:** Modify the remaining `patterns/*.py`; `fixtures/apex/build_package.py` + `report_content.json` (only if redistribution needs a content/slot tweak — keep regen-safe); `tests/test_visual_regression.py` baselines.

- [ ] **Step 1:** For each remaining pattern, adopt `var(--font-display)`/hero tier on its headline, convert any authority panel to `authority_panel`, apply `[data-density]` spacing, add ghost numerals where DNA §D recipe calls for big numbers. Keep each change brand-agnostic (semantic tokens only).
- [ ] **Step 2: Photo redistribution.** In ST-05, stop cramming proof-1/2/3 into one row; place ONE proof photo as a framed credibility moment and move the others to where they earn their keep (e.g. beside the founder pull-quote / on an adjacent content page) per spec §12. Founder recurs small beside a pull-quote. Confirm each of the 5 APEX images still appears (context.md asset rule).
- [ ] **Step 3: Regenerate + render.** `cd ../preprocessor && .venv/bin/python ../v7-renderer/fixtures/apex/build_package.py` (expect `pages=20 st07a=5 …`), then `cd ../v7-renderer && source .venv/bin/activate && python render.py` → `output/report.pdf` + `report-p1..20.png`.
- [ ] **Step 4: Judge each page** against `APEX - KI DMC Report v1 (1).pdf` + the DNA §E ★★★ levers (founder hero, large client photos, dark panels, social-proof presence) — read the PNGs. Decide apex `density` (`balanced`→`compact`?) here.
- [ ] **Step 5: Re-baseline visual-regression** deliberately, page-by-page, ONLY for pages judged improved against the reference: `UPDATE_BASELINES=1 python -m pytest tests/test_visual_regression.py`.
- [ ] **Step 6: Checkpoint + USER VISUAL CHECKPOINT.** Full suite green; guards green. **Surface the transformed APEX deck (cover/About/case-study) to the user vs the reference** before Stage 2 — this is the "are we at the bar?" moment, and the natural place to confirm the theme-lock landed.

---

## STAGE 2 — GEN CAPABILITY WIDENING (T8–T10) → synthetic-fixture checkpoint

> These components are NOT exercised by APEX content (no ratings/reviews/chart data). They exist to **activate Phase-B rubric rows** (spec §5.5) and to make the renderer generally complete (DNA §C4/§C5/§F). Tested via synthetic fixtures + unit renders, not the APEX baseline.

### Task 8: Social-proof component library

**Why:** DNA §C4 / §E gap #2 (★★★ for clients that supply it): press-logo wall, rating cards (Trustpilot/Google/ProvenExpert), screenshot review-card grid, grayscale client-logo wall. Reads `page["social_proof"]` (already typed in the package: `RatingCard`/`ReviewCard`/logos).

**Files:** Create `components/rating_card.jinja`, `review_card.jinja`, `review_grid.jinja`, `press_logo_wall.jinja`, `client_logo_wall.jinja`; `tests/fixtures/social_proof_sample.json`; Test `tests/test_social_proof_components.py`.

- [ ] **Step 1: Synthetic fixture + failing tests.** `social_proof_sample.json` with 2 ratings (platform/score/count/verified) + 4 reviews (name/date/stars/text) + press/client logos. Tests assert each macro renders the structured fields (stars row, score, "verifiziert", avatar/initial, grayscale logo grid). Example:
```python
def test_rating_card_shows_score_count_and_verified():
    rc = {"platform": "Trustpilot", "score": "4,8", "count": 212, "verified": True}
    html = render_macro("rating_card", {"rating": rc})
    assert "4,8" in html and "212" in html and "verifiziert" in html.lower()
```
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** the five macros (star row = repeated SVG/glyph; review card = avatar/initial + name + date + star row + lead + body; logo walls = grid, client logos `filter: grayscale(1)`; rating card = platform + stars + score + count + verified badge). Brand-agnostic; on-brand via tokens.
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Checkpoint.** Full suite green; brand-agnostic guard covers the new macros.

---

### Task 9: Inline-SVG charts + `result_box` + green token

**Why:** DNA §C5 / §E gap #6: rhetorical charts drawn from `page["charts"]` data. WeasyPrint renders inline `<svg>` robustly (`conic-gradient` is unreliable — 4b spec §5). Build the named chart kinds + the green "Ergebnis" result box.

**Files:** Create `components/charts/before_after_bars.jinja`, `line_compare.jinja`, `donut.jinja`, `cost_math_strip.jinja`, `comparison_columns.jinja`, `money_infographic.jinja`, `components/result_box.jinja`; add `--color-positive` to `compile_tokens.py` + `base.tokens.json`; `tests/fixtures/charts_sample.json`; Test `tests/test_charts.py`.

- [ ] **Step 1: `--color-positive` token (failing test).** A green token derived/configured for result boxes:
```python
def test_color_positive_token_present():
    css, _ = compile_tokens(parse_brand_tokens(_sample_tokens()), BrandAxes())
    assert "--color-positive" in css
```
- [ ] **Step 2: Run → FAIL → implement** `--color-positive` (a fixed accessible green in `base.tokens.json` color group, emitted in `compile_tokens`; brand-agnostic, not a client value).
- [ ] **Step 3: Chart macros (failing tests → implement).** Each macro takes a typed chart dict (matching `models_charts.py` kinds) and emits inline `<svg>` with brand-token fills, no axis chrome (DNA §C5). Example for `before_after_bars`:
```python
def test_before_after_bars_emits_two_svg_bars_with_values():
    chart = {"kind": "before_after", "before": {"label":"Ohne","value":14,"unit":"%"},
             "after": {"label":"Mit","value":50,"unit":"%"}}
    html = render_macro("charts/before_after_bars", {"chart": chart})
    assert "<svg" in html and "14" in html and "50" in html
```
Build the six chart kinds + `result_box` (green tint + check bullets, DNA §C3) the same TDD way.
- [ ] **Step 4: Run → PASS** for all chart tests.
- [ ] **Step 5: Wire** the chart dispatch so a pattern reading `page["charts"][]` renders the right macro by `kind` (a small `charts/__init__.py`-style selector or a Jinja include map).
- [ ] **Step 6: Checkpoint.** Full suite green; guards green.

---

### Task 10: TESTIMONIALS + LOGO-WALL page types (paired pre-processor models)

**Why:** DNA §D / §F name two NEW page types. They need pre-processor `TestimonialsData`/`LogoWallData` models + slot recipes + ST codes (4b spec §6). APEX uses neither; this completes generality.

**Files:** Create `patterns/st_testimonials.py`, `patterns/st_logowall.py` + register in `patterns/__init__.py`; pre-processor `research/preprocessor/models_pagedata.py` (add `TestimonialsData`, `LogoWallData` + register in `parse_page_data`) + the renderer's German-key page-data parsing; `tests/test_render_r2.py` + a preprocessor model test.

- [ ] **Step 1:** Add the two typed page-data models in the pre-processor (mirror existing per-ST models; `extra="allow"`), register in `parse_page_data`, add a unit test. Run the **preprocessor** suite (`cd ../preprocessor && .venv/bin/python -m pytest tests/ -q`) → expect golden frozen + count +1.
- [ ] **Step 2:** Build the two renderer patterns composing T8's social-proof macros (TESTIMONIALS = rating header + `review_grid`; LOGO-WALL = "Über N+ zufriedene Kunden" + `client_logo_wall` + CTA band). Register ST codes.
- [ ] **Step 3:** Render a synthetic page of each type from a fixture (not APEX) and verify structure.
- [ ] **Step 4: Checkpoint.** Both suites green (renderer + preprocessor golden + guards).

---

## Final verification (whole Phase A)

- [ ] Renderer suite green: `cd research/v7-renderer && source .venv/bin/activate && python -m pytest tests/ -q`.
- [ ] Pre-processor golden + guard green (Task 10 touched it): `cd research/preprocessor && .venv/bin/python -m pytest tests/ -q`.
- [ ] Brand-agnostic guards green across ALL new modules: `test_no_coral_in_chassis_logic`, `test_no_literals_in_architecture`, `test_no_client_name_in_logic`.
- [ ] APEX deck rendered + visual-regression re-baselined per approved page; the four ★★★ DNA levers visibly present on APEX (founder hero, large client photo, dark authority panels, density).
- [ ] Final code review (subagent) of the whole Phase A diff vs this plan + the spec §10.
- [ ] Update `context.md` (Phase A done; the locked theme; which rubric rows are now active for Phase B) + the spec's §10 Phase-A line.

## Self-review (against the spec)
- **Spec §10 Phase A coverage:** font end-to-end + warning (T1) ✓; darken authority panels (T4) ✓; bump type scale + hero tier (T2) ✓; missing devices — ghost numerals (T5), rating/review cards (T8), more chart kinds via inline SVG (T9) ✓; per-page layout variants (T7) ✓; wire density (T3) ✓. **Theme-lock §5.3** = T1–T6 (shared tokens) ✓. **Capability-clamp §5.5** = T8–T10 activate more rubric rows ✓.
- **DNA ★★★ levers (§E):** founder-hero + client photos (4b-1 + T7 redistribution), dark panels (T4), social-proof (T8/T10) ✓.
- **No placeholders:** every task names files + real code/CSS or a precise interface + acceptance; design-judgment tasks (T4–T7) are gated by visual-regression + the reference + per-task review (the proven 4b method).
- **Brand-agnostic:** every token/macro is semantic; `--color-positive` is a fixed accessible green (not a client value); guards extended. References (Phase B) ground composition only.
- **NO git:** all checkpoints are test+guard+visual-regression; no commit steps.
- **Honesty:** Stage 1 is the APEX-visible win; Stage 2 is generality for Phase B and is explicitly NOT exercised by APEX content (tested via synthetic fixtures). The loop (Phase B) raises consistency to this widened ceiling; it does not raise the ceiling.
