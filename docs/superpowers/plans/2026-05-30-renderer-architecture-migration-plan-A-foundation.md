# Renderer Architecture Migration — Plan A (Foundation) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax. Per the user's standing instruction, use the supporting skills throughout: **test-driven-development** for each task, **systematic-debugging** on any failure, **verification-before-completion** before claiming done, **requesting-code-review** after the foundation lands.

**Goal:** Re-found the renderer on a real architecture — a design-token layer, axis-driven theming, and a Jinja2 document shell — proven output-preserving by a visual-regression harness, so the later pattern rebuild (Plan B) is clean and brand-agnostic.

**Architecture:** `report.json + brand tokens + §4.0 axes` → `compile_tokens()` (CSS `:root` vars + `data-*` axis attrs) → Jinja2 `base.html.jinja` doc shell → existing patterns' `PageFragment`s injected → WeasyPrint → PNGs → visual-regression pixel-diff. Patterns are NOT rewritten here (that's Plan B); they keep working unchanged on the new foundation.

**Tech Stack:** Python 3.11, WeasyPrint, Jinja2 (new dep), Pillow (already present via PyMuPDF env), PyMuPDF.

---

## CRITICAL EXECUTION NOTES

1. **No git.** Never commit. Each task's gate is pytest + (where relevant) the visual-regression suite.
2. **Renderer venv MUST be activated** (WeasyPrint needs `DYLD_FALLBACK_LIBRARY_PATH`): `cd /Users/utkarsh/Projects/richard/research/v7-renderer && source .venv/bin/activate && python …`. Pre-processor uses its own venv (no activation): `cd /Users/utkarsh/Projects/richard/research/preprocessor && .venv/bin/python …`.
3. **Baselines now:** renderer `pytest tests/ -q` = 41 passed; pre-processor = 220 passed. Keep both green at every task.
4. **Python 3.11 (R-6):** never put a backslash inside an f-string `{…}` expression — precompute. (Jinja templates avoid this entirely; in `.py` keep precomputing.)
5. **Output-preserving discipline:** **ALL** Plan A tasks must NOT change the rendered pixels — the visual-regression suite enforces it at every step. The serif font + `--font-display` var are *plumbed* (Task 5) but only *consumed* when patterns adopt `var(--font-display)` in Plan B, so even Task 5 is pixel-identical. **No re-baseline happens in Plan A** — if any task changes a pixel, that's a bug to fix, not a baseline to update.
6. **New dependency:** add `Jinja2` to the renderer venv (`pip install jinja2`) in Task 6; record it in `research/v7-renderer/requirements.txt` if present.

---

## File Structure (Plan A)

```
research/v7-renderer/
  tokens/
    base.tokens.json        # NEW — universal design constants (DTCG-style), cited to grammar/spec
    compile_tokens.py       # NEW — compile_tokens(brand, axes) -> (css_root, data_attrs); BrandAxes dataclass
  templating.py             # NEW — Jinja2 Environment factory (loader, autoescape off for our trusted HTML)
  templates/
    base.html.jinja         # NEW — document shell + <head> (tokens :root + @page chrome + @font-face)
  fonts/PlayfairDisplay[wght].ttf (+ Italic)   # NEW — bundled default serif (Task 5)
  package_loader.py         # MODIFIED — read brand_axes -> BrandAxes on LoadedPackage
  assembler.py              # MODIFIED — shared head via compile_tokens; doc via base.html.jinja; set <html data-*>
  tests/
    test_visual_regression.py  # NEW — render apex -> pixel-diff vs baselines/
    baselines/                 # NEW — committed baseline PNGs (bootstrapped on first run)
    test_tokens.py             # NEW — compile_tokens unit tests
    test_axes.py               # NEW — brand_axes flow + data-* + serif resolution
research/preprocessor/
  stages/assemble_package.py # MODIFIED (additive) — accept + emit brand_axes block
  main.py                    # MODIFIED — pass brand_axes (from brand_profile) into assemble_package
  tests/test_assemble_package.py  # MODIFIED — assert brand_axes in manifest
research/v7-renderer/fixtures/apex/build_package.py  # MODIFIED — pass brand_axes from brand_input.json
```

---

## Task 1: Visual-regression harness (the safety net — build FIRST)

**Why first:** every later step must be proven output-preserving (or intentionally re-baselined). This harness is that proof.

**Files:** Create `research/v7-renderer/tests/test_visual_regression.py`; baselines live in `research/v7-renderer/tests/baselines/`.

- [ ] **Step 1: Write the harness + test**

```python
"""Visual-regression: render the apex fixture and pixel-diff each page vs a
committed baseline. Bootstraps baselines on first run (writes + passes).
Re-baseline intentionally by deleting tests/baselines/ (or setting
UPDATE_BASELINES=1) and re-running.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHASSIS_ROOT = HERE.parent
sys.path.insert(0, str(CHASSIS_ROOT))

import pytest  # noqa: E402
from PIL import Image, ImageChops  # noqa: E402

from assembler import render_package  # noqa: E402

FIXTURE = CHASSIS_ROOT / "fixtures" / "apex"
BASELINES = HERE / "baselines"
# Fraction of pixels allowed to differ beyond per-channel delta (anti-aliasing tolerance).
PER_PIXEL_DELTA = 24
MAX_DIFF_FRACTION = 0.005  # 0.5%


def _diff_fraction(a: Image.Image, b: Image.Image) -> float:
    if a.size != b.size:
        return 1.0
    diff = ImageChops.difference(a.convert("RGB"), b.convert("RGB"))
    # count pixels whose max channel delta exceeds PER_PIXEL_DELTA
    bbox_pixels = a.size[0] * a.size[1]
    hist = diff.convert("L").point(lambda p: 255 if p > PER_PIXEL_DELTA else 0).histogram()
    differing = hist[255] if len(hist) > 255 else 0
    return differing / float(bbox_pixels or 1)


def test_visual_regression_apex(tmp_path):
    result = render_package(FIXTURE, tmp_path)
    assert result.png_paths, "no PNGs rendered"
    BASELINES.mkdir(parents=True, exist_ok=True)
    update = os.environ.get("UPDATE_BASELINES") == "1"
    regressions = []
    for png in result.png_paths:
        base = BASELINES / png.name
        if update or not base.exists():
            Image.open(png).save(base)        # bootstrap / re-baseline
            continue
        frac = _diff_fraction(Image.open(png), Image.open(base))
        if frac > MAX_DIFF_FRACTION:
            regressions.append(f"{png.name}: {frac:.3%} pixels changed")
    assert not regressions, (
        "visual regression(s) vs baseline (re-baseline intentionally with "
        "UPDATE_BASELINES=1 if the change is wanted):\n" + "\n".join(regressions)
    )
```

- [ ] **Step 2: Run it — bootstraps baselines, passes**

Run: `cd /Users/utkarsh/Projects/richard/research/v7-renderer && source .venv/bin/activate && python -m pytest tests/test_visual_regression.py -q`
Expected: PASS (first run writes `tests/baselines/report-p1.png … p20.png`). Confirm 20 baseline files exist: `ls tests/baselines | wc -l` → 20.

- [ ] **Step 3: Run again — now diffs, still passes (proves stability)**

Run: same command. Expected: PASS (current render == baseline → deterministic confirmed).

- [ ] **Step 4: Verification checkpoint**

Run: `cd /Users/utkarsh/Projects/richard/research/v7-renderer && source .venv/bin/activate && python -m pytest tests/ -q`
Expected: all green (41 + 1 new).

---

## Task 2: Token layer — `base.tokens.json` + `compile_tokens.py` + `BrandAxes`

**Why:** the single brand-agnostic theming surface. Universal constants live in the base file (cited to grammar/spec); per-client colors/fonts/axes bind at compile time → CSS `:root` vars. Emits BOTH new semantic `--color-*`/`--font-*`/`--space-*`/`--type-*` vars AND legacy `--brand-*` aliases so existing patterns keep working unchanged.

**Files:** Create `research/v7-renderer/tokens/base.tokens.json`, `research/v7-renderer/tokens/compile_tokens.py`; Test `research/v7-renderer/tests/test_tokens.py`.

- [ ] **Step 1: Write the failing test** — `tests/test_tokens.py`:

```python
from __future__ import annotations
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
CHASSIS_ROOT = HERE.parent
sys.path.insert(0, str(CHASSIS_ROOT))

from brand_tokens import parse_brand_tokens  # noqa: E402
from tokens.compile_tokens import compile_tokens, BrandAxes  # noqa: E402

SAMPLE = {
    "brand_primary": "#5a9ab3", "brand_accent": "#85d2ee",
    "brand_neutral_dark": "#0F0F1F", "brand_neutral_mid": "#7A7A8C",
    "brand_neutral_light": "#fdffff", "font_heading": "Gestura Headline",
    "font_body": "Source Sans 3", "qr_target_url": "https://x.de",
    "company_name_short": "X", "company_url_display": "x.de",
}

def test_compile_tokens_emits_semantic_and_legacy_vars():
    brand = parse_brand_tokens(SAMPLE)
    css, attrs = compile_tokens(brand, BrandAxes(headline_type="serif"))
    # new semantic vars
    assert "--color-accent: #85d2ee" in css
    assert "--color-primary: #5a9ab3" in css
    assert "--font-display:" in css and "--font-serif:" in css
    assert "--space-4:" in css and "--type-display:" in css
    # legacy aliases (so existing patterns keep working)
    assert "--brand-primary: #5a9ab3" in css
    assert "--brand-accent: #85d2ee" in css
    assert "--brand-neutral-light: #fdffff" in css
    # serif axis -> display family is the serif var
    assert "--font-display: var(--font-serif)" in css
    # data attrs
    assert attrs["data-headline-type"] == "serif"

def test_sans_axis_uses_sans_display():
    brand = parse_brand_tokens(SAMPLE)
    css, attrs = compile_tokens(brand, BrandAxes(headline_type="sans"))
    assert "--font-display: var(--font-sans-head)" in css
    assert attrs["data-headline-type"] == "sans"

def test_brandaxes_defaults():
    ax = BrandAxes()
    assert ax.headline_type in ("serif", "sans", "sans_allcaps")
    assert ax.ground_mode and ax.texture and ax.accent_mechanic
```

- [ ] **Step 2: Run — expect FAIL** (`ModuleNotFoundError: No module named 'tokens'`)

Run: `cd /Users/utkarsh/Projects/richard/research/v7-renderer && source .venv/bin/activate && python -m pytest tests/test_tokens.py -q`

- [ ] **Step 3: Create `tokens/base.tokens.json`** (universal constants only — no client values; values cited to the grammar/InDesign spec):

```json
{
  "$comment": "Universal DMC design constants. NO client values. Cited: type ← DMC_InDesign_Spec_v1.md L183/L243; spacing ← 08_DMC_Design_System_v2 margins; fonts ← L484-489.",
  "space": {
    "1": {"$value": "2mm"}, "2": {"$value": "3mm"}, "3": {"$value": "4mm"},
    "4": {"$value": "6mm"}, "5": {"$value": "8mm"}, "6": {"$value": "12mm"}
  },
  "type": {
    "eyebrow": {"$value": "8pt"}, "label": {"$value": "9pt"}, "body": {"$value": "10pt"},
    "h3": {"$value": "11pt"}, "h2": {"$value": "15pt"}, "display": {"$value": "24pt"},
    "display-xl": {"$value": "34pt"}
  },
  "color": {
    "body": {"$value": "#333333"}, "on-dark": {"$value": "#FFFFFF"}
  },
  "font": {
    "sans-head": {"$value": "'Montserrat', sans-serif"},
    "sans-body": {"$value": "'Source Sans 3', 'Source Sans Pro', sans-serif"},
    "serif": {"$value": "'Playfair Display', Georgia, serif"}
  }
}
```

- [ ] **Step 4: Create `tokens/compile_tokens.py`**

```python
"""Compile the universal base tokens + a client's brand/axes into a CSS
`:root` block + a map of <html data-*> axis attributes.

Brand-agnostic: client colors/fonts arrive as DATA (BrandConfig); axes select
variants (e.g. serif vs sans display). Emits new semantic vars AND legacy
`--brand-*` aliases so existing patterns keep working during the migration.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from brand_tokens import BrandConfig  # noqa: E402

_BASE = json.loads((Path(__file__).resolve().parent / "base.tokens.json").read_text(encoding="utf-8"))


@dataclass(frozen=True)
class BrandAxes:
    """§4.0 perceptual axes (per-client). Defaults are grammar-neutral."""
    headline_type: str = "sans"      # serif | sans | sans_allcaps
    ground_mode: str = "light"       # light | dark | tonal …
    texture: str = "smooth"          # smooth | marble_paper | crumpled_paper | photo
    accent_mechanic: str = "tonal_same_hue"  # tonal_same_hue | contrasting_hue


def _flat(group: str) -> dict:
    return {k: v["$value"] for k, v in _BASE[group].items()}


def compile_tokens(brand: BrandConfig, axes: BrandAxes) -> tuple[str, dict]:
    space = _flat("space")
    type_ = _flat("type")
    color = _flat("color")
    font = _flat("font")

    display_family = "var(--font-serif)" if axes.headline_type == "serif" else "var(--font-sans-head)"

    lines: list[str] = [":root {"]
    # fonts
    lines.append(f"  --font-sans-head: {font['sans-head']};")
    lines.append(f"  --font-sans-body: {font['sans-body']};")
    lines.append(f"  --font-serif: {font['serif']};")
    lines.append(f"  --font-display: {display_family};")
    lines.append("  --font-head: var(--font-sans-head);")
    lines.append("  --font-body: var(--font-sans-body);")
    # semantic colors (per-client primitives bound here)
    lines.append(f"  --color-primary: {brand.brand_primary};")
    lines.append(f"  --color-accent: {brand.brand_accent};")
    lines.append(f"  --color-ink: {brand.brand_neutral_dark};")
    lines.append(f"  --color-muted: {brand.brand_neutral_mid};")
    lines.append(f"  --color-surface: {brand.brand_neutral_light};")
    lines.append(f"  --color-body: {color['body']};")
    lines.append(f"  --color-on-dark: {color['on-dark']};")
    # spacing + type scale (universal)
    for k, v in space.items():
        lines.append(f"  --space-{k}: {v};")
    for k, v in type_.items():
        lines.append(f"  --type-{k}: {v};")
    # legacy aliases so existing patterns (which use --brand-*) keep working
    lines.append(f"  --brand-primary: {brand.brand_primary};")
    lines.append(f"  --brand-accent: {brand.brand_accent};")
    lines.append(f"  --brand-neutral-dark: {brand.brand_neutral_dark};")
    lines.append(f"  --brand-neutral-mid: {brand.brand_neutral_mid};")
    lines.append(f"  --brand-neutral-light: {brand.brand_neutral_light};")
    lines.append("}")
    css_root = "\n".join(lines)

    data_attrs = {
        "data-headline-type": axes.headline_type,
        "data-ground-mode": axes.ground_mode,
        "data-texture": axes.texture,
    }
    return css_root, data_attrs
```

- [ ] **Step 5: Run — expect PASS**

Run: `cd /Users/utkarsh/Projects/richard/research/v7-renderer && source .venv/bin/activate && python -m pytest tests/test_tokens.py -q`

- [ ] **Step 6: Verification checkpoint** — `… && python -m pytest tests/ -q` all green (visual-regression still passes — nothing wired in yet).

---

## Task 3: Wire the token layer into the assembler shared head (output-preserving)

**Why:** replace the hand-written `:root` in `assembler.shared_head_css` with `compile_tokens` output. Because compile_tokens emits the same `--brand-*` aliases the patterns use, the rendered pixels are unchanged — visual-regression proves it.

**Files:** Modify `research/v7-renderer/assembler.py`.

- [ ] **Step 1: Edit `shared_head_css`** to source `:root` from `compile_tokens`. It currently takes `(brand, font_dir)`; add an `axes` param (default `BrandAxes()` so callers without axes still work). Replace the hand-written `:root {{ … }}` block with the compiled root. Keep the `@font-face`, `@page`, `body`, `.page` rules exactly as they are.

At the top of `assembler.py` add:
```python
from tokens.compile_tokens import compile_tokens, BrandAxes  # noqa: E402
```
Change the signature + the `:root` section:
```python
def shared_head_css(brand, font_dir: Path, axes: "BrandAxes | None" = None) -> str:
    font_uri = Path(font_dir).resolve().as_uri()
    css_root, _ = compile_tokens(brand, axes or BrandAxes())
    return f"""
@font-face {{ font-family:'Montserrat'; src:url('{font_uri}/Montserrat%5Bwght%5D.ttf') format('truetype'); font-weight:100 900; font-style:normal; }}
@font-face {{ font-family:'Montserrat'; src:url('{font_uri}/Montserrat-Italic%5Bwght%5D.ttf') format('truetype'); font-weight:100 900; font-style:italic; }}
@font-face {{ font-family:'Source Sans 3'; src:url('{font_uri}/SourceSans3%5Bwght%5D.ttf') format('truetype'); font-weight:200 900; font-style:normal; }}
@font-face {{ font-family:'Source Sans 3'; src:url('{font_uri}/SourceSans3-Italic%5Bwght%5D.ttf') format('truetype'); font-weight:200 900; font-style:italic; }}
{css_root}
@page {{
  size: A4 portrait;
  margin: 16mm 14mm 20mm 18mm;
  background-color: var(--brand-neutral-light);
  @top-left {{
    content: "{_esc(brand.company_name_short)}";
    font-family: 'Montserrat', sans-serif; font-weight: 400; font-size: 8pt;
    color: var(--brand-primary); letter-spacing: 0.005em; padding: 6mm 0 0 0;
  }}
  @bottom-left {{
    content: string(pagefolio);
    font-family: 'Montserrat', sans-serif; font-weight: 400; font-size: 7.5pt;
    color: var(--brand-neutral-mid); padding: 0 0 4mm 0;
  }}
}}
* {{ box-sizing: border-box; }}
html {{ font-size: 10pt; }}
body {{
  font-family: 'Source Sans 3', 'Source Sans Pro', sans-serif;
  color: #333333; margin: 0; line-height: 1.42;
}}
.page {{ position: relative; break-after: page; }}
.page:last-child {{ break-after: auto; }}
"""
```
(`render_package` keeps calling `shared_head_css(pkg.brand, FONT_DIR)` for now; axes wire in Task 5.)

- [ ] **Step 2: Run the full renderer suite + visual-regression**

Run: `cd /Users/utkarsh/Projects/richard/research/v7-renderer && source .venv/bin/activate && python -m pytest tests/ -q`
Expected: all green — **including `test_visual_regression_apex` (0 pixels changed)**, proving the token layer is output-identical.

- [ ] **Step 3: If visual-regression fails** (any pixel drift): the compiled `:root` must be missing/renaming a `--brand-*` alias a pattern relies on. Use systematic-debugging — diff the compiled `:root` vs the old hand-written one; ensure every `--brand-*` var is present with the same value. Fix, re-run. Do NOT re-baseline (this step must be output-identical).

---

## Task 4: Pre-processor emits `brand_axes` (additive, upstream)

**Why:** the §4.0 axes live on `client.brand_profile` but never reach the package. Emit a `brand_axes` block so the renderer can theme by axis. Additive — pre-processor tests stay green + one assertion.

**Files:** Modify `research/preprocessor/stages/assemble_package.py`, `research/preprocessor/main.py`, `research/v7-renderer/fixtures/apex/build_package.py`, `research/preprocessor/tests/test_assemble_package.py`.

- [ ] **Step 1: Add the failing assertion** — in `research/preprocessor/tests/test_assemble_package.py`, add:

```python
def test_manifest_carries_brand_axes(tmp_path) -> None:
    import asyncio, json
    from stages.plan_layout import LayoutPlan, PlannedPage
    from stages.generate_assets import AssetPlan
    from models import FontConfig
    planned = [PlannedPage(slot=1, st_type="ST-01", css_template="cover",
                           components=[], has_cta=False, data={}, page_numbers="1")]
    resolved = asyncio.run(assemble_package(
        brand_tokens={"brand_primary": "#111", "brand_accent": "#222",
            "brand_neutral_dark": "#333", "brand_neutral_mid": "#444",
            "brand_neutral_light": "#555", "font_heading": "M", "font_body": "S",
            "qr_target_url": "https://x.de", "company_name_short": "X",
            "company_url_display": "x.de"},
        font_config=FontConfig(font_heading_name="M", font_body_name="S",
            font_heading_path=None, font_body_path=None, source="chassis_default"),
        copy_warnings=[], cover_validation=None, asset_plan=AssetPlan(assets=[]),
        components={}, layout_plan=LayoutPlan(pages=planned, page_count=1, page_count_target=20),
        report_json={"meta": {"report_id": "T"}, "pages": []}, output_dir=tmp_path,
        brand_axes={"headline_type": "serif", "ground_mode": "dark",
                    "texture": "smooth", "accent_mechanic": "contrasting_hue"},
    ))
    manifest = json.loads((resolved.output_dir / "resolved_package.json").read_text())
    assert manifest["brand_axes"]["headline_type"] == "serif"
    assert manifest["brand_axes"]["ground_mode"] == "dark"
```

- [ ] **Step 2: Run — expect FAIL** (`assemble_package() got an unexpected keyword argument 'brand_axes'`)

Run: `cd /Users/utkarsh/Projects/richard/research/preprocessor && .venv/bin/python -m pytest tests/test_assemble_package.py::test_manifest_carries_brand_axes -q`

- [ ] **Step 3: Thread `brand_axes` through `assemble_package`** — in `research/preprocessor/stages/assemble_package.py`:
  - Add `brand_axes: Optional[dict] = None,` to the `assemble_package(...)` keyword params.
  - Pass it into `_build_manifest(...)` (add `brand_axes=brand_axes,` to the call) and add `brand_axes: Optional[dict] = None,` to `_build_manifest`'s signature.
  - In the manifest dict returned by `_build_manifest`, add a top-level key (next to `"brand": dict(brand_tokens),`):
    ```python
        "brand_axes": dict(brand_axes) if brand_axes else {},
    ```

- [ ] **Step 4: Wire `main.py /render`** — in `research/preprocessor/main.py`, just before the `assemble_package(...)` call, build the axes from the profile:
```python
    bp = request.client.brand_profile
    brand_axes = {
        "headline_type": (bp.headline_type if bp and bp.headline_type else "sans"),
        "ground_mode": (bp.ground_mode if bp and bp.ground_mode else "light"),
        "texture": (bp.texture if bp and bp.texture else "smooth"),
        "accent_mechanic": (bp.accent_mechanic if bp and bp.accent_mechanic else "tonal_same_hue"),
    }
```
and add `brand_axes=brand_axes,` to the `await assemble_package(...)` call.

- [ ] **Step 5: Wire the apex generator** — in `research/v7-renderer/fixtures/apex/build_package.py`, after `brand_profile = BrandProfile(**brand_input["brand_profile"])`, build the same axes dict (using `brand_profile` as `bp`) and add `brand_axes=brand_axes,` to its `assemble_package(...)` call.

- [ ] **Step 6: Run new test + full pre-processor suite**

Run: `cd /Users/utkarsh/Projects/richard/research/preprocessor && .venv/bin/python -m pytest tests/ -q`
Expected: all green (220 + 1). Then regenerate the apex package so it carries `brand_axes`:
`cd /Users/utkarsh/Projects/richard/research/preprocessor && .venv/bin/python ../v7-renderer/fixtures/apex/build_package.py` → `pages=20 …` no AssertionError. Confirm: `python3 -c "import json; print(json.load(open('/Users/utkarsh/Projects/richard/research/v7-renderer/fixtures/apex/resolved_package.json'))['brand_axes'])"` → shows `headline_type: serif` (apex's profile).

- [ ] **Step 7: Renderer visual-regression must still pass** (the new `brand_axes` block in the package is ignored by the renderer until Task 5; output unchanged):
`cd /Users/utkarsh/Projects/richard/research/v7-renderer && source .venv/bin/activate && python -m pytest tests/ -q` → all green, 0 pixel diff.

---

## Task 5: Renderer reads `brand_axes` + bundles the serif font (plumbing, output-preserving)

**Why:** make the axes available to the token layer (`compile_tokens` already resolves `--font-display` by `headline_type`) and bundle the serif so Plan B can consume it. **No pixel change** — the existing patterns still hardcode Montserrat; nothing uses `--font-display` yet.

**Files:** Modify `research/v7-renderer/package_loader.py`, `research/v7-renderer/assembler.py`; add `fonts/PlayfairDisplay[wght].ttf` (+ Italic); Test `research/v7-renderer/tests/test_axes.py`.

- [ ] **Step 1: Bundle the serif font**
```
cd /Users/utkarsh/Projects/richard/research/v7-renderer/fonts
curl -sSL -o "PlayfairDisplay[wght].ttf" "https://github.com/google/fonts/raw/main/ofl/playfairdisplay/PlayfairDisplay%5Bwght%5D.ttf"
curl -sSL -o "PlayfairDisplay-Italic[wght].ttf" "https://github.com/google/fonts/raw/main/ofl/playfairdisplay/PlayfairDisplay-Italic%5Bwght%5D.ttf"
file "PlayfairDisplay[wght].ttf"   # must say TrueType; size > 100KB
```
If blocked/fails, report BLOCKED (don't fake the file).

- [ ] **Step 2: Write the failing test** — `tests/test_axes.py`:
```python
from __future__ import annotations
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
CHASSIS_ROOT = HERE.parent
sys.path.insert(0, str(CHASSIS_ROOT))
from package_loader import load_package, LoadedPackage  # noqa: E402
from tokens.compile_tokens import BrandAxes  # noqa: E402

FIXTURE = CHASSIS_ROOT / "fixtures" / "apex"

def test_loaded_package_exposes_axes():
    pkg = load_package(FIXTURE)
    assert isinstance(pkg.axes, BrandAxes)
    assert pkg.axes.headline_type == "serif"   # apex's profile (after Task 4 regen)

def test_missing_axes_defaults(tmp_path):
    import json
    (tmp_path / "resolved_package.json").write_text(json.dumps({
        "brand": {"brand_primary":"#111","brand_accent":"#222","brand_neutral_dark":"#333",
                  "brand_neutral_mid":"#444","brand_neutral_light":"#555","font_heading":"M",
                  "font_body":"S","qr_target_url":"https://x.de","company_name_short":"X",
                  "company_url_display":"x.de"}, "pages": []}), encoding="utf-8")
    pkg = load_package(tmp_path)
    assert isinstance(pkg.axes, BrandAxes)   # defaults, no crash
```

- [ ] **Step 3: Run — expect FAIL** (`LoadedPackage` has no `axes`)

Run: `cd /Users/utkarsh/Projects/richard/research/v7-renderer && source .venv/bin/activate && python -m pytest tests/test_axes.py -q`

- [ ] **Step 4: `package_loader.py` — read axes**
  - Change import: `from dataclasses import dataclass, field`.
  - Add import: `from tokens.compile_tokens import BrandAxes  # noqa: E402` (after the brand_tokens import).
  - Add field to `LoadedPackage`: `axes: BrandAxes = field(default_factory=BrandAxes)`.
  - In `load_package`, before the return, build axes:
    ```python
    _ax = pkg.get("brand_axes", {}) or {}
    axes = BrandAxes(**{k: v for k, v in _ax.items()
                        if k in ("headline_type", "ground_mode", "texture", "accent_mechanic")})
    ```
    and add `axes=axes,` to the `LoadedPackage(...)` construction.

- [ ] **Step 5: `assembler.py` — add the serif @font-face, pass axes, set `<html data-*>`**
  - In `shared_head_css`, add two `@font-face` rules for `'Playfair Display'` (normal + italic), mirroring the Montserrat ones (URL-encode brackets `%5B %5D`, `font-weight:400 900`). (Declared-but-unused → no pixel change.)
  - In `render_package`: change `head = shared_head_css(pkg.brand, FONT_DIR)` → `head = shared_head_css(pkg.brand, FONT_DIR, pkg.axes)`.
  - Compute axis attrs once and put them on `<html>`:
    ```python
    from tokens.compile_tokens import compile_tokens   # add to imports
    _, data_attrs = compile_tokens(pkg.brand, pkg.axes)
    attr_str = "".join(f' {k}="{v}"' for k, v in data_attrs.items())
    ```
    and change the doc's opening tag from `'<html lang="de">'` to `f'<html lang="de"{attr_str}>'` (in `html_doc`).

- [ ] **Step 6: Run tests + visual-regression — all green, 0 pixel diff**

Run: `cd /Users/utkarsh/Projects/richard/research/v7-renderer && source .venv/bin/activate && python -m pytest tests/ -q`
Expected: all green, **`test_visual_regression_apex` 0 diff** (serif var defined + font declared, but no element consumes `var(--font-display)` yet → identical pixels). If a pixel changed, something is consuming the serif unexpectedly — investigate (systematic-debugging); do not re-baseline.

---

## Task 6: Jinja2 document shell (infrastructure, output-preserving)

**Why:** move the document assembly out of an f-string into a Jinja2 template — the templating foundation Plan B's patterns build on. The rendered pixels stay identical (only the HTML-string *construction* changes).

**Files:** add `Jinja2` to the renderer venv; Create `research/v7-renderer/templating.py`, `research/v7-renderer/templates/base.html.jinja`; Modify `research/v7-renderer/assembler.py`.

- [ ] **Step 1: Install Jinja2**
`cd /Users/utkarsh/Projects/richard/research/v7-renderer && source .venv/bin/activate && pip install jinja2` and add `jinja2` to `requirements.txt` if that file exists.

- [ ] **Step 2: Create `templating.py`**
```python
"""Jinja2 environment for the renderer. autoescape is OFF: the templates
assemble already-escaped, trusted HTML fragments produced by the patterns
(patterns escape their own data). Markup lives in templates/, not Python.
"""
from __future__ import annotations
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape  # noqa: F401

_TEMPLATES = Path(__file__).resolve().parent / "templates"
_ENV: Environment | None = None

def get_env() -> Environment:
    global _ENV
    if _ENV is None:
        _ENV = Environment(
            loader=FileSystemLoader(str(_TEMPLATES)),
            autoescape=False,          # fragments are pre-escaped, trusted
            trim_blocks=True, lstrip_blocks=True,
        )
    return _ENV
```

- [ ] **Step 3: Create `templates/base.html.jinja`**
```jinja
<!DOCTYPE html><html lang="de"{{ html_attrs }}><head><meta charset="utf-8"><style>{{ head_css }}{{ fragment_css }}</style></head><body>{{ body }}</body></html>
```

- [ ] **Step 4: `assembler.py` — render the doc via the template**
Replace the `html_doc = ( … f-string … )` construction in `render_package` with:
```python
    from templating import get_env
    html_doc = get_env().get_template("base.html.jinja").render(
        html_attrs=attr_str,
        head_css=head,
        fragment_css="".join(css_blocks),
        body=body,
    )
```
(Keep everything else — the per-page overflow doc can stay the existing string; it's internal/advisory.)

- [ ] **Step 5: Run tests + visual-regression — all green, 0 pixel diff**

Run: `cd /Users/utkarsh/Projects/richard/research/v7-renderer && source .venv/bin/activate && python -m pytest tests/ -q`
Expected: all green, 0 pixel diff (the doc is byte-equivalent in structure; WeasyPrint ignores inter-tag whitespace). If diff: compare the rendered `html_doc` to the prior string output; reconcile whitespace/order; do not re-baseline.

---

## Task 7: Establish the anti-pollution guard (extensible; teeth grow in Plan B)

**Why:** lock the structural rule early — raw hex colors + font-family literals + client-name branching are banned in the *new* architecture files (tokens compiler, templating, templates). `base.tokens.json` is the ONLY place hex primitives are allowed. Plan B extends the scanned set to `components/`, `styles/`, and each migrated pattern.

**Files:** Create `research/v7-renderer/tests/test_no_literals_in_architecture.py`.

- [ ] **Step 1: Write the guard test**
```python
"""Anti-pollution guard: no raw hex colors / font-family literals / client
branching in the NEW architecture files. Per-client values live in DATA;
universal primitives live ONLY in tokens/base.tokens.json. Plan B adds
components/ + styles/ + patterns to SCANNED as they migrate.
"""
from __future__ import annotations
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCANNED = [ROOT / "tokens" / "compile_tokens.py", ROOT / "templating.py"]
SCANNED += list((ROOT / "templates").glob("*.jinja"))

_HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
_FONT_LIT = re.compile(r"""['"](Montserrat|Source Sans 3|Playfair Display|Gestura)[^'"]*['"]""")

def test_no_raw_literals_in_architecture_files():
    violations = []
    for f in SCANNED:
        if not f.exists():
            continue
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if _HEX.search(line) or _FONT_LIT.search(line):
                violations.append(f"{f.name}:{i}: {line.strip()}")
    assert not violations, (
        "raw hex/font literal in an architecture file (put primitives in "
        "tokens/base.tokens.json; per-client values come from data):\n"
        + "\n".join(violations)
    )
```
> Note: `compile_tokens.py` reads font/color *names from `base.tokens.json`* and binds *client colors from the BrandConfig object* (no literals), so it passes. If you find yourself wanting a literal there, put it in `base.tokens.json` instead.

- [ ] **Step 2: Run — expect PASS** (the architecture files carry no literals by construction)

Run: `cd /Users/utkarsh/Projects/richard/research/v7-renderer && source .venv/bin/activate && python -m pytest tests/test_no_literals_in_architecture.py -q`
If it FAILS, you have a literal in a new architecture file — move it to `base.tokens.json` or source it from data. (This is the lock working.)

- [ ] **Step 3: Full verification (both suites + visual-regression)**

Run: `cd /Users/utkarsh/Projects/richard/research/v7-renderer && source .venv/bin/activate && python -m pytest tests/ -q` → all green (41 baseline + visual-regression + tokens + axes + literal-guard).
Run: `cd /Users/utkarsh/Projects/richard/research/preprocessor && .venv/bin/python -m pytest tests/ -q` → all green (220 + brand_axes).

---

## Self-Review (planner checklist — completed)

**Spec coverage (migration spec §11 phases 1–5):** phase 1 tokenize → Task 3 (+ token layer in Task 2); phase 2 token compiler → Task 2; phase 3 thread axes → Tasks 4 (upstream) + 5 (renderer) + serif; phase 4 Jinja2 → Task 6 (the doc shell; per-pattern Jinja conversion is Plan B, intentionally — avoids touching patterns twice); phase 5 component library → **Plan B** (built with its first consumers); visual-regression → Task 1; guards → Task 7. Phase 6 (reference-quality pattern rebuild) = **Plan B**.

**Placeholder scan:** none — every new file has complete code; modifications give exact edits + the surrounding context.

**Type consistency:** `compile_tokens(brand, axes) -> (css_root, data_attrs)` and `BrandAxes(headline_type, ground_mode, texture, accent_mechanic)` are defined once (Task 2) and used identically in Tasks 3/5; `LoadedPackage.axes: BrandAxes` (Task 5) matches; `assemble_package(..., brand_axes=dict)` (Task 4) matches main.py + generator + the loader's read key (`brand_axes`).

**Output-preserving invariant:** Tasks 1,3,4,5,6,7 are all proven pixel-identical by `test_visual_regression_apex`; the serif is plumbed-not-consumed. Nothing in Plan A changes the look — by design.

**Brand-agnostic:** colors/fonts/axes flow from data; `base.tokens.json` holds only universal constants; the literal-guard locks it. Legacy `--brand-*` aliases keep existing patterns working until Plan B migrates them to `--color-*`/`var(--font-display)`.

---

## Execution Handoff

Plan A saved to `docs/superpowers/plans/2026-05-30-renderer-architecture-migration-plan-A-foundation.md`. Execute with **superpowers:subagent-driven-development** (fresh opus subagent per task; I review between tasks; TDD + the visual-regression gate at each step; systematic-debugging on any pixel drift; verification-before-completion before each DONE). No git — pytest + visual-regression are the gates. **Plan B (the reference-quality pattern rebuild)** is written after Plan A lands and its foundation is proven (visual-regression green, both suites green, a code review of the foundation).

