# Phase A — Renderer Theme-Lock Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax. **NO GIT in this repo** — every "Checkpoint" step means *run the suite green*, never `git commit`.

**Goal:** Raise the shared renderer theme (type scale, color/ground, depth, furniture) to the documented DMC canon and wire the design axes, so pages gain hand-designed hierarchy + per-brand identity.

**Architecture:** All changes are in `research/v7-renderer/` (tokens → `compile_tokens` → CSS vars/`data-*` attrs → `components.css` + `assembler.py` head CSS). No package-contract or preprocessor change. Spec: `docs/superpowers/specs/2026-06-05-phase-A-renderer-theme-lock-design.md`.

**Tech Stack:** Python 3.11, WeasyPrint 68.1, DTCG JSON tokens, Jinja2, pytest, Pillow.

**Ground rules (every task):**
- Work in the **renderer venv** with the WeasyPrint lib path:
  `cd /Users/utkarsh/Projects/richard/research/v7-renderer && source .venv/bin/activate && export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib`
- Full suite: `python -m pytest tests/ -q` (≈185 tests must stay green, **except** the apex visual-regression baseline which is intentionally re-baked in Task 12).
- One render-doc-per-process for font assertions (fontconfig leaks state).
- Brand-agnostic: no client name/hex/font literal in logic; sizes are universal constants, colors derive from brand tokens.

---

### Task 1: Type scale tokens (scale B)

**Files:**
- Modify: `research/v7-renderer/tokens/base.tokens.json` (the `type` block)
- Modify: `research/v7-renderer/tokens/compile_tokens.py` (the `--type-*` emission)
- Test: `research/v7-renderer/tests/test_tokens.py`

- [ ] **Step 1: Write the failing test**
```python
def test_type_scale_B_values():
    from tokens.compile_tokens import compile_tokens
    from tokens.compile_tokens import BrandAxes  # adjust import to actual location
    css, _attrs = compile_tokens(_minimal_brand(), BrandAxes())
    assert "--type-h2: 20pt" in css
    assert "--type-display: 32pt" in css
    assert "--type-stat-xl: 60pt" in css
    assert "--type-stat: 40pt" in css
    assert "--type-h3: 14pt" in css
    assert "--type-pullquote: 18pt" in css
```
(`_minimal_brand()` = the existing test helper for a BrandTokens-like object; reuse whatever `test_tokens.py` already uses.)

- [ ] **Step 2: Run it — expect FAIL**
`python -m pytest tests/test_tokens.py::test_type_scale_B_values -v` → FAIL (vars absent / wrong pt).

- [ ] **Step 3: Edit `base.tokens.json` `type` block** to:
```json
"type": {
  "source": {"$value": "7.5pt"}, "caption": {"$value": "8.5pt"},
  "eyebrow": {"$value": "9.5pt"}, "label": {"$value": "9.5pt"},
  "body": {"$value": "10.5pt"}, "cta": {"$value": "11.5pt"},
  "h3": {"$value": "14pt"}, "pullquote": {"$value": "18pt"},
  "h2": {"$value": "20pt"}, "signature": {"$value": "28pt"},
  "display": {"$value": "32pt"}, "display-xl": {"$value": "40pt"},
  "stat": {"$value": "40pt"}, "stat-xl": {"$value": "60pt"},
  "hero": {"$value": "48pt"},
  "$comment": "Type ramp B. Canon: DMC_InDesign_Spec_v1 MODUL 4 (H1 28-40 def 32, H2 18-22, H3 13-15, big-stat 48-72); 08_DMC_Design_System_v2 E.3 (40-72)."
}
```

- [ ] **Step 4:** In `compile_tokens.py`, confirm the loop that emits `--type-<name>` iterates the whole `type` block (so the new keys emit automatically). If sizes are hardcoded rather than iterated, add explicit emissions for `stat`, `stat-xl`, `h3`, `pullquote`, `signature`, `cta`, `caption`, `source`.

- [ ] **Step 5: Run** `python -m pytest tests/test_tokens.py::test_type_scale_B_values -v` → PASS.

- [ ] **Step 6: Checkpoint** — `python -m pytest tests/ -q`. Some downstream tests that assert old sizes may fail; note them for the tasks that own those files (do NOT weaken this token task to satisfy them). Type-token-only tests green.

---

### Task 2: Re-point the "shout" components

**Files:**
- Modify: `research/v7-renderer/styles/components.css` (`.c-these`, `.c-key-insight__body`, `.c-authority__heading`, `.c-stat-strip`/`.c-stat-rail`/`.c-stat-callout` values, `.c-two-tone`)
- Test: `research/v7-renderer/tests/test_components.py`

- [ ] **Step 1: Write the failing test** (string-level assertions on the stylesheet):
```python
def test_shout_components_use_real_tiers():
    css = (Path(__file__).parent.parent / "styles/components.css").read_text()
    import re
    def fontsize_of(selector):
        block = re.search(re.escape(selector) + r"\s*\{[^}]*\}", css, re.S).group(0)
        return re.search(r"font-size:\s*var\((--type-[\w-]+)\)", block).group(1)
    assert fontsize_of(".c-these") == "--type-h2"
    assert fontsize_of(".c-key-insight__body") == "--type-h2"
    assert fontsize_of(".c-authority__heading") == "--type-h2"
    assert fontsize_of(".c-stat-rail .c-stat-value") == "--type-stat-xl"
    assert fontsize_of(".c-stat-strip .c-stat-value") == "--type-stat-xl"
```

- [ ] **Step 2: Run — expect FAIL** (`.c-these` etc. currently `--type-h2` is already 15→now 20, but stat values currently `--type-h2`; the test pins the *new* `--type-stat-xl`).
`python -m pytest tests/test_components.py::test_shout_components_use_real_tiers -v` → FAIL on the stat-value selectors.

- [ ] **Step 3: Edit `components.css`:** set `.c-stat-strip .c-stat-value`, `.c-stat-rail .c-stat-value`, `.c-stat-callout__value` → `font-size: var(--type-stat-xl);`. Leave `.c-these`/`.c-key-insight__body`/`.c-authority__heading` on `var(--type-h2)` (now 20pt). `.c-two-tone` stays `var(--type-display)` (now 32). If any pull-quote `calc()` referenced the old `--type-display` numerically, re-derive it off the var.

- [ ] **Step 4: Run** the test → PASS.

- [ ] **Step 5: Checkpoint** — `python -m pytest tests/test_components.py -q` green (re-baseline visual is Task 12).

---

### Task 3: Color roles — neutral aliases, `--color-panel`/`--color-on-panel`, `--color-ground`

**Files:**
- Modify: `research/v7-renderer/tokens/compile_tokens.py`
- Test: `research/v7-renderer/tests/test_tokens.py`

- [ ] **Step 1: Write the failing tests**
```python
def test_panel_role_follows_accent_mechanic():
    from tokens.compile_tokens import compile_tokens, BrandAxes
    ink_css, _ = compile_tokens(_minimal_brand(), BrandAxes(accent_mechanic="tonal_same_hue"))
    prim_css, _ = compile_tokens(_minimal_brand(), BrandAxes(accent_mechanic="contrasting_hue"))
    assert "--color-panel: var(--color-ink)" in ink_css
    assert "--color-panel: var(--color-primary)" in prim_css
    for css in (ink_css, prim_css):
        assert "--color-on-panel:" in css

def test_neutral_role_aliases_and_ground():
    from tokens.compile_tokens import compile_tokens, BrandAxes
    css, _ = compile_tokens(_minimal_brand(), BrandAxes())
    for v in ("--color-neutral-dark", "--color-neutral-mid", "--color-neutral-light", "--color-ground"):
        assert v in css
    # ground must differ from neutral-light (perceptible, not identical)
    import re
    light = re.search(r"--color-neutral-light:\s*([^;]+);", css).group(1).strip()
    ground = re.search(r"--color-ground:\s*([^;]+);", css).group(1).strip()
    assert ground != light
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement in `compile_tokens.py`** (append to the `lines`/`:root` emission, after the existing neutral/accent derivations):
```python
# Neutral role aliases (expose brand neutrals as named roles — no new derivation)
lines.append(f"  --color-neutral-dark: {brand.brand_neutral_dark};")
lines.append(f"  --color-neutral-mid: {brand.brand_neutral_mid};")
lines.append(f"  --color-neutral-light: {brand.brand_neutral_light};")

# Perceptible page ground: blend neutral-light toward neutral-dark ~5%, clamp light
gr, gg, gb = _blend_hex(brand.brand_neutral_light, brand.brand_neutral_dark, 0.05)
lines.append(f"  --color-ground: rgb({gr},{gg},{gb});")

# Authority panel role: primary when accent_mechanic contrasts, else ink
_panel_primary = axes.accent_mechanic == "contrasting_hue"
lines.append(f"  --color-panel: var(--color-{'primary' if _panel_primary else 'ink'});")
# on-panel: reuse the existing luminance on-color rule against the resolved panel hue
_panel_hex = brand.brand_primary if _panel_primary else brand.brand_ink  # adjust to actual ink token
lines.append(f"  --color-on-panel: {_on_color(_panel_hex)};")
```
Add a small helper if absent:
```python
def _blend_hex(a_hex, b_hex, t):
    ar, ag, ab = _hex_to_rgb(a_hex); br, bg, bb = _hex_to_rgb(b_hex)
    mix = lambda x, y: max(0, min(255, round(x + (y - x) * t)))
    return mix(ar, br), mix(ag, bg), mix(ab, bb)
```
Reuse the existing `_hex_to_rgb` and the existing on-color function (named `_on_color`/luminance helper at compile_tokens.py:150-159 — use the real name). If `brand.brand_ink` isn't a field, use whatever resolves to the dark ink in the current code.

- [ ] **Step 4: Run** both tests → PASS.

- [ ] **Step 5: Checkpoint** — `python -m pytest tests/test_tokens.py -q` green.

---

### Task 4: Authority/recap panels consume `--color-panel`

**Files:**
- Modify: `research/v7-renderer/styles/components.css` (`.c-authority`, `.c-dark-recap`; remove `.c-authority--primary`)
- Test: `research/v7-renderer/tests/test_components.py`

- [ ] **Step 1: Write the failing test**
```python
def test_authority_recap_use_panel_role():
    css = (Path(__file__).parent.parent / "styles/components.css").read_text()
    import re
    auth = re.search(r"\.c-authority\s*\{[^}]*\}", css, re.S).group(0)
    recap = re.search(r"\.c-dark-recap\s*\{[^}]*\}", css, re.S).group(0)
    assert "var(--color-panel)" in auth
    assert "var(--color-on-panel)" in auth
    assert "var(--color-panel)" in recap
    assert ".c-authority--primary" not in css  # modifier removed; recipe drives ink/primary
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Edit `components.css`:** in `.c-authority` and `.c-dark-recap`, change `background-color: var(--color-ink);` → `var(--color-panel);` and the text `color:` → `var(--color-on-panel);`. Delete the `.c-authority--primary { background-color: var(--color-primary); ... }` modifier block. **Do NOT touch** `.c-key-insight`, `.c-callout-panel`, `.c-cost-block`, `.c-stat-callout`, `.c-hflow__step`, `.c-bar-chart` track (they keep `--color-accent-tint` by design, per spec §5.3).

- [ ] **Step 4: Run** the test → PASS.

- [ ] **Step 5: Checkpoint** — `python -m pytest tests/test_components.py -q` green.

---

### Task 5: Serif display default + `sans_allcaps` + font preflight fix

**Files:**
- Modify: `research/v7-renderer/tokens/compile_tokens.py` (default `headline_type`, `sans_allcaps`)
- Modify: `research/v7-renderer/assembler.py` (the `[data-headline-type="sans_allcaps"]` head CSS rule)
- Modify: `research/v7-renderer/render.py` (`_REQUIRED_FONTS`)
- Test: `research/v7-renderer/tests/test_tokens.py`, `tests/test_render_r2.py` (or wherever head CSS is asserted)

- [ ] **Step 1: Write failing tests**
```python
def test_display_default_is_serif():
    from tokens.compile_tokens import compile_tokens, BrandAxes
    css, _ = compile_tokens(_minimal_brand(), BrandAxes())  # headline_type unset
    assert "--font-display: var(--font-serif)" in css

def test_sans_allcaps_emits_uppercase_rule():
    from assembler import shared_head_css  # adjust to real symbol
    head = shared_head_css(_minimal_brand_pkg(), _font_dir(), _axes())  # reuse existing helpers
    assert '[data-headline-type="sans_allcaps"]' in head
    assert "text-transform: uppercase" in head

def test_required_fonts_are_loaded_faces():
    import render
    req = " ".join(render._REQUIRED_FONTS)
    assert "SourceSans3" in req and "SourceSerif4" in req
    assert "Montserrat" not in req
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement.**
  - `compile_tokens.py`: where `display_family` is chosen (≈line 122), make the **default** branch serif: `display_family = "var(--font-serif)" if axes.headline_type in (None, "serif") else "var(--font-sans-head)"`. Ensure the resolver/axes default for `headline_type` resolves to `serif` here (if `BrandAxes()` defaults to `"sans"`, override at the renderer read: treat `"sans"` only when explicitly set — simplest: change the `BrandAxes` field default to `"serif"` in the renderer-side dataclass, since this is renderer-consumed).
  - `assembler.py` head CSS: add
    ```css
    [data-headline-type="sans_allcaps"] .c-two-tone,
    [data-headline-type="sans_allcaps"] h1, [data-headline-type="sans_allcaps"] .cs-headline {
      text-transform: uppercase; letter-spacing: 0.04em;
    }
    ```
    (Scope to the headline selectors actually used; keep body/thesis sentence-case.)
  - `render.py`: set `_REQUIRED_FONTS = ("SourceSans3[wght].ttf", "SourceSerif4[opsz,wght].ttf")` (match the real filenames in `research/v7-renderer/fonts/`).

- [ ] **Step 4: Run** all three → PASS.

- [ ] **Step 5: Checkpoint** — `python -m pytest tests/ -q` (font tests one-doc-per-process; expect green except visual baseline).

---

### Task 6: Perceptible page ground (keep folio wash intact)

**Files:**
- Modify: `research/v7-renderer/assembler.py` (the `[data-ground-mode]` `.page` rules ≈302-313; do NOT touch the @page folio gradient ≈168)
- Test: `tests/test_render_r2.py` (head CSS assertions)

- [ ] **Step 1: Write the failing test**
```python
def test_light_page_ground_is_color_ground_not_wash():
    head = shared_head_css(_minimal_brand_pkg(), _font_dir(), _axes())
    import re
    rule = re.search(r"\[data-ground-mode=\"light\"\][^{]*\{[^}]*\}", head, re.S).group(0)
    assert "var(--color-ground)" in rule
    assert "var(--color-ground-wash)" not in rule
    # folio band gradient still uses the wash (unchanged)
    assert "var(--color-ground-wash)" in head
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Edit `assembler.py`:** change `[data-ground-mode="light"] .page, [data-ground-mode="cool_light"] .page { background-color: var(--color-ground-wash); }` → `var(--color-ground);`. **Leave** the `@page` folio `linear-gradient(... var(--color-ground-wash))` (≈168) and `compile_tokens`' emission of `--color-ground-wash` untouched.

- [ ] **Step 4: Run** the test → PASS. Confirm `test_emits_tint_and_ground_roles` (tests/test_tokens.py) still green (wash var still emitted).

- [ ] **Step 5: Checkpoint** — `python -m pytest tests/test_render_r2.py tests/test_tokens.py -q` green.

---

### Task 7: Whisper grain tile + `[data-texture]` overlays

**Files:**
- Create: `research/v7-renderer/scripts/gen_grain_tile.py` (deterministic generator)
- Create: `research/v7-renderer/styles/_grain.py` (the committed base64 constant) OR embed the constant in `assembler.py`
- Modify: `research/v7-renderer/assembler.py` (always-on grain `background-image` on `.page` + `[data-texture]` overlays)
- Test: `research/v7-renderer/tests/test_texture_ground.py` (new)

- [ ] **Step 1: Write the generator** `scripts/gen_grain_tile.py`:
```python
"""Deterministic neutral grain tile -> base64 PNG. Run once; paste output into styles/_grain.py.
Brand-agnostic (neutral noise only). Run: python scripts/gen_grain_tile.py"""
import base64, io, random
from PIL import Image
def make_tile(size=128, seed=7, alpha=10):
    rnd = random.Random(seed)
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    px = img.load()
    for y in range(size):
        for x in range(size):
            v = rnd.randint(0, 255)               # neutral grey noise
            px[x, y] = (v, v, v, rnd.randint(0, alpha))  # very low alpha
    buf = io.BytesIO(); img.save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode()
if __name__ == "__main__":
    print(make_tile())
```

- [ ] **Step 2: Generate + commit the constant.** Run `python scripts/gen_grain_tile.py`, paste into `styles/_grain.py`:
```python
# Deterministic neutral grain tile (seed=7). Brand-agnostic. Regenerate via scripts/gen_grain_tile.py
GRAIN_TILE_B64 = "<paste output>"
GRAIN_DATA_URI = "data:image/png;base64," + GRAIN_TILE_B64
```

- [ ] **Step 3: Write the failing test** `tests/test_texture_ground.py`:
```python
def test_grain_paints_pixel_variance():
    # render a minimal .page and check the ground band has texture (variance > 0)
    from PIL import Image
    import numpy as np, io
    png_bytes = _render_blank_page_png(ground_mode="light")  # helper: render one .page to PNG
    arr = np.asarray(Image.open(io.BytesIO(png_bytes)).convert("L"))
    band = arr[20:80, 20:80]   # a clean, text-free corner inside the margin
    assert band.var() > 0.0, "grain ground collapsed to a flat solid (feTurbulence trap)"

def test_grain_constant_has_no_hex_or_client_literal():
    from styles._grain import GRAIN_DATA_URI
    assert "#" not in GRAIN_DATA_URI  # base64, no hex
```
(`_render_blank_page_png` = a tiny helper that renders one `<section class="page">` via the real `assembler` head CSS + WeasyPrint to a PNG; mirror the existing visual-regression render helper.)

- [ ] **Step 4: Run — expect FAIL** (no grain yet → variance 0).

- [ ] **Step 5: Implement in `assembler.py`:** import `GRAIN_DATA_URI` and add to the light/cool_light `.page` rule a second background layer:
```python
# .page light ground = color + always-on whisper grain (verified to paint; feTurbulence does NOT)
f'[data-ground-mode="light"] .page, [data-ground-mode="cool_light"] .page {{'
f'  background-color: var(--color-ground);'
f'  background-image: url("{GRAIN_DATA_URI}");'
f'  background-repeat: repeat; background-size: 128px 128px;'
f'}}'
# stronger texture character when the axis signals it
'[data-texture="marble_paper"] .page, [data-texture="crumpled_paper"] .page {'
'  background-blend-mode: multiply;'  # stronger read of the same tile
'}'
```
Keep z-order: `.page` content sits above (the background paints behind content by default). Brand-agnostic.

- [ ] **Step 6: Run** both tests → PASS.

- [ ] **Step 7: Checkpoint** — `python -m pytest tests/test_texture_ground.py -q` green.

---

### Task 8: Body leading FEST 14pt + density demotion + `balanced`

**Files:**
- Modify: `research/v7-renderer/assembler.py` (`body` line-height) and `research/v7-renderer/styles/density.css`
- Test: `tests/test_render_r2.py`, `tests/test_tokens.py`

- [ ] **Step 1: Write failing tests**
```python
def test_body_leading_is_absolute_14pt():
    head = shared_head_css(_minimal_brand_pkg(), _font_dir(), _axes())
    import re
    body = re.search(r"\bbody\s*\{[^}]*\}", head, re.S).group(0)
    assert re.search(r"line-height:\s*14pt", body)         # absolute pt (FEST), not unitless
    assert not re.search(r"line-height:\s*var\(--density-lead", body)

def test_balanced_density_rule_present():
    css = (Path(__file__).parent.parent / "styles/density.css").read_text()
    assert '[data-density="balanced"]' in css
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement.**
  - `assembler.py` `body { ... }`: set `line-height: 14pt;` (absolute) and `font-size: var(--type-body);` (10.5pt). Leave `html { font-size: 10pt; }`.
  - `density.css`: add `[data-density="balanced"] { --density-col-gap: 8mm; --density-para: var(--space-2); }` and make `compact`/`spacious` vary `--density-col-gap` + a new `--density-para` (paragraph spacing) — **remove `--density-lead` from the body `line-height` path** (body leading is FEST). If patterns still read `--density-lead`, keep the var defined but stop applying it to `body`.

- [ ] **Step 4: Run** both → PASS.

- [ ] **Step 5: Checkpoint** — `python -m pytest tests/test_render_r2.py tests/test_tokens.py -q` green.

---

### Task 9: Margins + header accent tick + footer hairline

**Files:**
- Modify: `research/v7-renderer/assembler.py` (`@page` margins; header band; footer/folio)
- Test: `tests/test_render_r2.py`

- [ ] **Step 1: Write the failing test**
```python
def test_margins_header_tick_footer_hairline():
    head = shared_head_css(_minimal_brand_pkg(), _font_dir(), _axes())
    assert "margin: 16mm 14mm 20mm 18mm" in head           # T R B L (canon I18/O14 -> on portrait L=18,R=14)
    assert "--color-accent" in head and "ph-tick" in head    # static header accent tick
    # footer folio stays muted, never accent
    import re
    folio = re.search(r"@bottom-left\s*\{[^}]*\}", head, re.S).group(0)
    assert "var(--color-muted)" in folio and "var(--color-accent)" not in folio
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement in `assembler.py`:**
  - `@page { margin: 16mm 14mm 20mm 18mm; ... }` (top/right/bottom/left).
  - In the running `.page-header` markup/CSS, add a static tick element `<span class="ph-tick"></span>` with CSS `.ph-tick { display:inline-block; width:6mm; height:0.6mm; background:var(--color-accent); margin-right:2mm; vertical-align:middle; }`. (No per-page text — deferred.)
  - Footer: keep `@bottom-left { content: string(pagefolio); color: var(--color-muted); }` and add a hairline, e.g. a `border-top: 0.2mm solid var(--color-muted);` on the folio margin box or a thin rule element. Folio color stays `--color-muted` (never accent).

- [ ] **Step 4: Run** the test → PASS.

- [ ] **Step 5: Checkpoint** — `python -m pytest tests/test_render_r2.py -q` green.

---

### Task 10: Shared hairline + ghost utilities (+ allowlist)

**Files:**
- Modify: `research/v7-renderer/styles/components.css` (add `.c-rule`, `.c-ghost-num`)
- Modify: `research/v7-renderer/tests/test_components.py` (extend allowed-prefix tuple)
- Test: `research/v7-renderer/tests/test_components.py`

- [ ] **Step 1: Add to the allowlist tuple** in `test_components.py::test_components_css_is_token_only_and_class_scoped` the prefixes `".c-rule"`, `".c-ghost-num"`. Then **write the failing test**:
```python
def test_shared_rule_and_ghost_utilities_exist():
    css = (Path(__file__).parent.parent / "styles/components.css").read_text()
    assert ".c-rule" in css
    assert ".c-ghost-num" in css
```

- [ ] **Step 2: Run — expect FAIL** (utilities absent; and the class-scope guard must still pass once they're added).

- [ ] **Step 3: Add to `components.css`:**
```css
/* Shared hairline rules (DNA §C6). Token-colored => brand-agnostic. */
.c-rule { border: 0; border-top: var(--rule-hairline, 0.2mm) solid var(--color-muted); }
.c-rule--accent { border-top-color: var(--color-accent); }
.c-rule--eyebrow { width: 26px; border-top-width: 0.4mm; border-top-color: var(--color-accent); }
/* Oversized faint ghost numeral utility (DNA §C1/§C6). */
.c-ghost-num { position: absolute; font-family: var(--font-display); font-weight: 700;
  font-size: var(--type-hero); line-height: 1; color: var(--color-ink); opacity: 0.06; z-index: 0; }
```
Define `--rule-hairline` in `compile_tokens`/base tokens if you want it themable (optional; default 0.2mm inline is fine).

- [ ] **Step 4: Run** `python -m pytest tests/test_components.py -q` → the class-scope guard + new test PASS.

- [ ] **Step 5: Checkpoint** — `python -m pytest tests/test_components.py -q` green.

---

### Task 11: Guard + behavior coverage sweep

**Files:**
- Modify: `research/v7-renderer/tests/` (ensure new modules covered by literal guard)
- Test: the guard tests + the full unit suite

- [ ] **Step 1:** Confirm `test_no_literals_in_architecture` / `test_no_client_name_in_logic` include `tokens/compile_tokens.py`, `assembler.py`, `styles/_grain.py`, `scripts/gen_grain_tile.py`. If their globs already rglob `*.py`/`*.css`, they're covered — add an assertion test if a new dir/file type isn't scanned.

- [ ] **Step 2: Write a guard regression test** (if not already present):
```python
def test_grain_and_ground_have_no_client_literal():
    from styles._grain import GRAIN_DATA_URI
    blob = GRAIN_DATA_URI
    for banned in ("apex","geva","conesso","nmr","coral","#"):  # base64 has no '#'
        assert banned.lower() not in blob.lower()
```

- [ ] **Step 3: Run** the guard tests → PASS.

- [ ] **Step 4: Checkpoint — full unit suite** (excluding visual baseline):
`python -m pytest tests/ -q --deselect tests/test_visual_regression.py::test_visual_regression_apex`
Expected: all green. Fix any token-name/size assertions in older tests that legitimately changed (update them to the new canon values — do NOT revert the canon).

---

### Task 12: Render the real apex deck, font-embed check, human review, re-baseline

**Files:**
- Uses: `research/v7-renderer/fixtures/apex/` + `render.py`
- Modify (LAST, after sign-off): `research/v7-renderer/tests/baselines/*.png`

- [ ] **Step 1: Rebuild the apex package + render** (the real fixture pipeline):
```bash
cd /Users/utkarsh/Projects/richard/research/preprocessor && .venv/bin/python ../v7-renderer/fixtures/apex/build_package.py
cd /Users/utkarsh/Projects/richard/research/v7-renderer && source .venv/bin/activate && export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib
python render.py fixtures/apex/resolved_package.json -o output/   # adjust to the real render CLI
```

- [ ] **Step 2: Verify structural invariants** (independently, never trust a "done"):
```bash
python -c "import fitz; d=fitz.open('output/report.pdf'); print('pages', d.page_count)"     # == 20
pdffonts output/report.pdf | grep -iE "SourceSerif4|SourceSans3"                              # both embedded
pdffonts output/report.pdf | grep -i montserrat && echo "FAIL: montserrat leaked" || echo OK
```

- [ ] **Step 3: VIEW the pixels** — rasterize cover + a case-study (ST-07A) + about (ST-05) to PNG and **look** (the verification bar): is the type hierarchy bold (32/60), the ground perceptibly grained (not flat), the authority panel dark, the header tick present? Compare whole pages to Richard's references. If a page regressed, fix the owning task — do **not** proceed to re-baseline.

- [ ] **Step 4: Re-baseline ONLY after sign-off:** once the rendered pages are confirmed *better* vs Richard, regenerate the visual-regression baselines:
```bash
UPDATE_BASELINES=1 python -m pytest tests/test_visual_regression.py::test_visual_regression_apex -q
```
Then run it again clean → PASS (now pinned to the approved new look). **Never** re-baseline a render you haven't eyeballed.

- [ ] **Step 5: Final checkpoint — full suite green:**
`python -m pytest tests/ -q` → all pass (including the freshly-baked visual baseline).

---

## Self-Review

**Spec coverage:** §5.1 type→T1/T2; §5.2 fonts→T5; §5.3 color roles→T3, panels→T4; §5.4 ground→T6, grain→T7; §5.5 utilities→T10; §5.6 axes→T3/T5/T7/T8; §5.7 furniture→T8/T9; §7 testing→every task + T11/T12; §4 verification bar→T12. All 14 gap-audit resolutions (§11) map to a task (feTurbulence→T7, recipe selection→T3, ground-wash keep→T6, panel correction→T4, FEST leading→T8, allowlist→T10, re-baseline→T12, etc.).

**Placeholder scan:** none — each code/test step shows concrete declarations/values. (Where a real symbol name is uncertain, the step says "adjust to the real name" with the line reference — the implementer reads the file.)

**Type consistency:** `--color-panel`/`--color-on-panel`/`--color-ground`/`--type-stat-xl`/`--type-stat`/`.c-rule`/`.c-ghost-num`/`GRAIN_DATA_URI` used identically across tasks.
