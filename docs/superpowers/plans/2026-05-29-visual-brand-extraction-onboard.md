# Visual Brand Extraction (`/onboard` Mode 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `/onboard` pipeline that screenshots a client's website, measures its real colors + fonts, lets a vision model assign semantic roles (never invent hex), and POSTs a `BrandProfile` to the n8n webhook.

**Architecture:** Five pure-ish layers chained by typed Pydantic contracts (capture → dom_extract → pixel_palette → vision_reading → reconcile), orchestrated async and delivered to a webhook. The vision model emits *indices into the measured palette*, so colors are always real, never hallucinated. Output plugs into the existing `ClientInput.brand_profile` seam.

**Tech Stack:** FastAPI, Pydantic v2, Playwright (headless Chromium), Pillow (color quantization), httpx (OpenRouter + webhook), pytest.

**Spec:** `docs/superpowers/specs/2026-05-28-visual-brand-extraction-onboard-design.md`

**Working directory for all commands:** `/Users/utkarsh/Projects/richard/research/preprocessor` with `source .venv/bin/activate` already run. All `pytest` commands assume this.

---

## File Structure

| File | Responsibility |
|---|---|
| `models.py` (modify) | Extend `BrandProfile` with 4 optional perceptual axes |
| `models_onboard.py` (create) | All onboard contracts: request/response + per-layer |
| `stages/onboard/__init__.py` (create) | Package marker |
| `stages/onboard/dom_extract.py` (create) | Pure `parse(raw_dom_eval) -> DomSignals` + color/font normalizers |
| `stages/onboard/pixel_palette.py` (create) | Pillow quantize → `PixelPalette` |
| `stages/onboard/vision_reading.py` (create) | OpenRouter Sonnet call → `VisionReading` (index-validated) |
| `stages/onboard/reconcile.py` (create) | Pure resolution + fallback + provenance + needs_review → `OnboardResult` |
| `stages/onboard/capture.py` (create) | Playwright session: screenshots + DOM eval → `CaptureResult` |
| `stages/onboard/pipeline.py` (create) | `async run_onboard_pipeline()` orchestrator |
| `main.py` (modify) | Replace `/onboard` stub with async 202 + BackgroundTask + webhook delivery |
| `requirements.txt` (modify) | Add `playwright`, `Pillow` |
| `tests/test_onboard_*.py` (create) | One test module per layer + endpoint |

**Dependency order (TDD-friendly, pure layers first):** Task 1 deps → Task 2 models → Task 3 dom_extract → Task 4 pixel_palette → Task 5 reconcile → Task 6 vision_reading → Task 7 capture → Task 8 pipeline → Task 9 endpoint → Task 10 guard + full verify.

---

## Task 1: Dependencies

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add the two new dependencies**

Edit `requirements.txt` to read exactly:

```
fastapi>=0.115
uvicorn[standard]>=0.32
pydantic>=2.9
httpx>=0.27
pytest>=9.0
playwright>=1.49
Pillow>=11.0
```

- [ ] **Step 2: Install**

Run:
```bash
pip install -r requirements.txt && playwright install chromium
```
Expected: pip reports playwright + Pillow installed; `playwright install chromium` downloads the browser (or reports already installed).

- [ ] **Step 3: Verify imports**

Run:
```bash
python -c "import playwright, PIL; from playwright.async_api import async_playwright; print('ok', PIL.__version__)"
```
Expected: prints `ok` and a Pillow version ≥ 11.

- [ ] **Step 4: Commit**

```bash
git add research/preprocessor/requirements.txt
git commit -m "build: add playwright + Pillow for /onboard visual pipeline"
```

---

## Task 2: Extend `BrandProfile` + create onboard contracts

**Files:**
- Modify: `models.py` (the `BrandProfile` class)
- Create: `models_onboard.py`
- Test: `tests/test_onboard_models.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_onboard_models.py`:

```python
"""Tests for onboard contract models + the extended BrandProfile."""

from __future__ import annotations

from models import BrandProfile
from models_onboard import (
    CaptureResult,
    DomSignals,
    FlatHexFallback,
    OnboardAccepted,
    OnboardDiagnostics,
    OnboardRequest,
    OnboardResult,
    PaletteColor,
    PixelPalette,
    VisionAxes,
    VisionReading,
    VisionRoleRefs,
)


def test_brand_profile_has_new_perceptual_axes() -> None:
    bp = BrandProfile(
        brand_primary="#1A2540",
        accent_mechanic="contrasting_hue",
        ground_mode="cool_light",
        texture="smooth",
        headline_type="sans",
    )
    assert bp.accent_mechanic == "contrasting_hue"
    assert bp.ground_mode == "cool_light"
    assert bp.texture == "smooth"
    assert bp.headline_type == "sans"


def test_brand_profile_axes_default_none() -> None:
    bp = BrandProfile()
    assert bp.accent_mechanic is None
    assert bp.texture is None


def test_onboard_request_flat_hex_optional() -> None:
    req = OnboardRequest(record_id="rec1", website_url="https://x.de")
    assert req.flat_hex_fallback is None
    assert req.callback_url is None


def test_onboard_request_with_fallback() -> None:
    req = OnboardRequest(
        record_id="rec1",
        website_url="https://x.de",
        flat_hex_fallback=FlatHexFallback(dark="#111", light="#EEE", accent="#F50"),
    )
    assert req.flat_hex_fallback.accent == "#F50"


def test_onboard_result_round_trip() -> None:
    result = OnboardResult(
        record_id="rec1",
        job_id="job1",
        status="success",
        brand_profile=BrandProfile(brand_primary="#1A2540"),
        field_confidence={"brand_primary": 0.9},
        provenance={"brand_primary": "vision_role+pixel"},
        needs_review=False,
        review_reasons=[],
        diagnostics=OnboardDiagnostics(render_mode="ok", palette_size=6),
    )
    dumped = result.model_dump()
    assert dumped["brand_profile"]["brand_primary"] == "#1A2540"
    assert dumped["diagnostics"]["render_mode"] == "ok"


def test_internal_contracts_construct() -> None:
    cap = CaptureResult(hero_png="a.png", fullpage_png="b.png",
                         raw_dom_eval={}, status="ok", notes=[])
    dom = DomSignals(css_color_vars={}, font_head=None, font_body=None,
                     sampled_colors=[], logo_url=None)
    pal = PixelPalette(
        colors=[PaletteColor(hex="#1A2540", coverage_pct=70.0, region="hero")],
        lightest_idx=0, darkest_idx=0,
    )
    vr = VisionReading(
        role_refs=VisionRoleRefs(primary=0, accent=None, neutral_dark=None,
                                 neutral_mid=None, neutral_light=None),
        axes=VisionAxes(accent_mechanic="contrasting_hue", ground_mode=None,
                        texture=None, headline_type="sans"),
        confidence={"primary": 0.9}, notes=None,
    )
    assert cap.status == "ok"
    assert dom.font_head is None
    assert pal.colors[0].hex == "#1A2540"
    assert vr.role_refs.primary == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_onboard_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'models_onboard'`.

- [ ] **Step 3: Extend `BrandProfile` in `models.py`**

In `models.py`, the `BrandProfile` class currently ends with `font_body: Optional[str] = None`. Add the four axes immediately after `font_body`:

```python
    # Font identification — pre-processor resolves these in Stage 2.
    font_head: Optional[str] = None
    font_body: Optional[str] = None

    # Brand-identity perceptual axes (grammar §4.0 M/G/X/H). Captured by
    # Mode 1 (/onboard); not yet consumed by the renderer but stored so
    # the data is present when the renderer grows to read them.
    accent_mechanic: Optional[str] = None   # §4.0 M: contrasting_hue | tonal_same_hue
    ground_mode: Optional[str] = None       # §4.0 G
    texture: Optional[str] = None           # §4.0 X: marble_paper | crumpled_paper | smooth | photo
    headline_type: Optional[str] = None     # §4.0 H: serif | sans | sans_allcaps
```

- [ ] **Step 4: Create `models_onboard.py`**

```python
"""Contracts for Mode 1 (/onboard) — the visual brand-extraction pipeline.

Each pipeline layer consumes the previous layer's typed output. These
models ARE the contract chain (spec §3.3, §4). `BrandProfile` (the clean
Stage-1-ready shape) lives in models.py and is imported here.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from models import BrandProfile


# ── Endpoint request/response ────────────────────────────────────────────────

class FlatHexFallback(BaseModel):
    dark: str
    light: str
    accent: str


class OnboardRequest(BaseModel):
    record_id: str
    website_url: str
    # OPTIONAL: /onboard REPLACES the text scraper that used to produce
    # these, so they may not exist at onboard-time. Fallback chain degrades
    # past them to chassis defaults + needs_review.
    flat_hex_fallback: Optional[FlatHexFallback] = None
    callback_url: Optional[str] = None  # default: env REPORT_GENERATOR_WEBHOOK


class OnboardAccepted(BaseModel):
    status: str = "accepted"
    job_id: str
    record_id: str


class OnboardDiagnostics(BaseModel):
    render_mode: str = "unknown"      # ok | spa_blank | timeout | nav_error
    screenshots: list[str] = Field(default_factory=list)
    timings_ms: dict[str, int] = Field(default_factory=dict)
    vision_model: Optional[str] = None
    palette_size: int = 0


class OnboardResult(BaseModel):
    record_id: str
    job_id: str
    status: str                        # success | partial | failed
    brand_profile: BrandProfile
    field_confidence: dict[str, float] = Field(default_factory=dict)
    provenance: dict[str, str] = Field(default_factory=dict)
    needs_review: bool = False
    review_reasons: list[str] = Field(default_factory=list)
    diagnostics: OnboardDiagnostics = Field(default_factory=OnboardDiagnostics)


# ── Internal per-layer contracts ─────────────────────────────────────────────

class CaptureResult(BaseModel):
    hero_png: Optional[str]            # path; None if capture produced nothing
    fullpage_png: Optional[str]
    raw_dom_eval: dict = Field(default_factory=dict)
    status: str                        # ok | spa_blank | timeout | nav_error
    notes: list[str] = Field(default_factory=list)


class DomSignals(BaseModel):
    css_color_vars: dict[str, str] = Field(default_factory=dict)
    font_head: Optional[str] = None
    font_body: Optional[str] = None
    sampled_colors: list[str] = Field(default_factory=list)
    logo_url: Optional[str] = None


class PaletteColor(BaseModel):
    hex: str
    coverage_pct: float
    region: str                        # hero | fullpage


class PixelPalette(BaseModel):
    colors: list[PaletteColor] = Field(default_factory=list)
    lightest_idx: Optional[int] = None
    darkest_idx: Optional[int] = None


class VisionRoleRefs(BaseModel):
    primary: Optional[int] = None      # index into PixelPalette.colors
    accent: Optional[int] = None
    neutral_dark: Optional[int] = None
    neutral_mid: Optional[int] = None
    neutral_light: Optional[int] = None


class VisionAxes(BaseModel):
    accent_mechanic: Optional[str] = None
    ground_mode: Optional[str] = None
    texture: Optional[str] = None
    headline_type: Optional[str] = None


class VisionReading(BaseModel):
    role_refs: VisionRoleRefs
    axes: VisionAxes
    confidence: dict[str, float] = Field(default_factory=dict)
    notes: Optional[str] = None
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_onboard_models.py -v`
Expected: PASS (6 tests).

- [ ] **Step 6: Commit**

```bash
git add research/preprocessor/models.py research/preprocessor/models_onboard.py research/preprocessor/tests/test_onboard_models.py
git commit -m "feat(onboard): extend BrandProfile + add pipeline contract models"
```

---

## Task 3: `dom_extract.py` — pure DOM-signal parser

**Files:**
- Create: `stages/onboard/__init__.py` (empty)
- Create: `stages/onboard/dom_extract.py`
- Test: `tests/test_onboard_dom_extract.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_onboard_dom_extract.py`:

```python
"""Tests for Stage Onboard-1 — dom_extract (pure parser)."""

from __future__ import annotations

from stages.onboard.dom_extract import parse, _to_hex, _first_family


def test_to_hex_rgb() -> None:
    assert _to_hex("rgb(26, 37, 64)") == "#1a2540"


def test_to_hex_rgba() -> None:
    assert _to_hex("rgba(233, 126, 71, 0.8)") == "#e97e47"


def test_to_hex_already_hex() -> None:
    assert _to_hex("#1A2540") == "#1a2540"
    assert _to_hex("#abc") == "#aabbcc"


def test_to_hex_unparseable_returns_none() -> None:
    assert _to_hex("transparent") is None
    assert _to_hex("inherit") is None
    assert _to_hex("") is None


def test_first_family_strips_quotes_and_generics() -> None:
    assert _first_family('"Montserrat", Arial, sans-serif') == "Montserrat"
    assert _first_family("'Source Sans Pro', sans-serif") == "Source Sans Pro"
    assert _first_family("sans-serif") is None       # generic-only → None
    assert _first_family("") is None


def test_parse_full_signal() -> None:
    raw = {
        "cssVars": {"--brand": "rgb(26,37,64)", "--gap": "16px", "--accent": "#E97E47"},
        "fontHead": '"Montserrat", sans-serif',
        "fontBody": "'Source Sans Pro', Arial, sans-serif",
        "sampledColors": ["rgb(26,37,64)", "#E97E47", "not-a-color"],
        "logoUrl": "https://x.de/logo.svg",
    }
    dom = parse(raw)
    assert dom.css_color_vars == {"--brand": "#1a2540", "--accent": "#e97e47"}
    assert dom.font_head == "Montserrat"
    assert dom.font_body == "Source Sans Pro"
    assert dom.sampled_colors == ["#1a2540", "#e97e47"]
    assert dom.logo_url == "https://x.de/logo.svg"


def test_parse_empty_dict_is_safe() -> None:
    dom = parse({})
    assert dom.font_head is None
    assert dom.css_color_vars == {}
    assert dom.sampled_colors == []
    assert dom.logo_url is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_onboard_dom_extract.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'stages.onboard'`.

- [ ] **Step 3: Create the package marker + implementation**

Create `stages/onboard/__init__.py` (empty file).

Create `stages/onboard/dom_extract.py`:

```python
"""Stage Onboard-1 — parse the raw page.evaluate() blob into DomSignals.

Pure: no browser, no I/O. Fed the dict that capture.py's injected JS
returns. Normalizes CSS colors to lowercase #rrggbb and resolves font
stacks to their first concrete family.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from models_onboard import DomSignals

# Generic CSS font families that are NOT a real typeface name.
_GENERIC_FAMILIES = frozenset({
    "serif", "sans-serif", "monospace", "cursive", "fantasy",
    "system-ui", "ui-serif", "ui-sans-serif", "ui-monospace",
    "inherit", "initial", "unset", "-apple-system", "blinkmacsystemfont",
})

_RGB_RE = re.compile(
    r"rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})", re.IGNORECASE
)
_HEX_RE = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def _to_hex(color: Any) -> Optional[str]:
    """Normalize a CSS color string to lowercase #rrggbb, or None."""
    if not isinstance(color, str):
        return None
    c = color.strip()
    if not c:
        return None
    m = _HEX_RE.match(c)
    if m:
        body = m.group(1).lower()
        if len(body) == 3:
            body = "".join(ch * 2 for ch in body)
        return f"#{body}"
    m = _RGB_RE.match(c)
    if m:
        r, g, b = (max(0, min(255, int(m.group(i)))) for i in (1, 2, 3))
        return f"#{r:02x}{g:02x}{b:02x}"
    return None


def _first_family(stack: Any) -> Optional[str]:
    """First concrete family from a font-family stack, or None if only
    generic families are present.
    """
    if not isinstance(stack, str) or not stack.strip():
        return None
    for raw in stack.split(","):
        fam = raw.strip().strip('"').strip("'").strip()
        if fam and fam.lower() not in _GENERIC_FAMILIES:
            return fam
    return None


def parse(raw_dom_eval: dict) -> DomSignals:
    """Parse the page.evaluate() blob into DomSignals. Tolerant of any
    missing/extra keys.
    """
    raw = raw_dom_eval or {}

    css_vars: dict[str, str] = {}
    for name, value in (raw.get("cssVars") or {}).items():
        hexv = _to_hex(value)
        if hexv is not None:
            css_vars[name] = hexv

    sampled: list[str] = []
    for value in (raw.get("sampledColors") or []):
        hexv = _to_hex(value)
        if hexv is not None:
            sampled.append(hexv)

    logo = raw.get("logoUrl")
    return DomSignals(
        css_color_vars=css_vars,
        font_head=_first_family(raw.get("fontHead")),
        font_body=_first_family(raw.get("fontBody")),
        sampled_colors=sampled,
        logo_url=logo if isinstance(logo, str) and logo.strip() else None,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_onboard_dom_extract.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add research/preprocessor/stages/onboard/__init__.py research/preprocessor/stages/onboard/dom_extract.py research/preprocessor/tests/test_onboard_dom_extract.py
git commit -m "feat(onboard): dom_extract pure parser (colors + fonts)"
```

---

## Task 4: `pixel_palette.py` — Pillow color quantization

**Files:**
- Create: `stages/onboard/pixel_palette.py`
- Test: `tests/test_onboard_pixel_palette.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_onboard_pixel_palette.py`:

```python
"""Tests for Stage Onboard-2 — pixel_palette (Pillow quantization)."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from stages.onboard.pixel_palette import extract_palette, _rgb_to_hex, _luminance


def _make_two_color_png(tmp_path: Path) -> str:
    """70% navy (#1a2540), 30% coral (#e97e47), 100x100."""
    img = Image.new("RGB", (100, 100), (26, 37, 64))   # navy
    coral = Image.new("RGB", (30, 100), (233, 126, 71))
    img.paste(coral, (70, 0))
    p = tmp_path / "hero.png"
    img.save(p)
    return str(p)


def test_rgb_to_hex() -> None:
    assert _rgb_to_hex((26, 37, 64)) == "#1a2540"
    assert _rgb_to_hex((255, 255, 255)) == "#ffffff"


def test_luminance_orders_dark_light() -> None:
    assert _luminance((0, 0, 0)) < _luminance((255, 255, 255))


def test_extract_palette_two_colors(tmp_path: Path) -> None:
    palette = extract_palette(_make_two_color_png(tmp_path), region="hero")
    hexes = {c.hex for c in palette.colors}
    assert "#1a2540" in hexes
    assert "#e97e47" in hexes
    # navy dominates (70% vs 30%) → ranked first
    assert palette.colors[0].hex == "#1a2540"
    assert palette.colors[0].coverage_pct > palette.colors[1].coverage_pct
    # region tag propagated
    assert palette.colors[0].region == "hero"


def test_extract_palette_light_dark_indices(tmp_path: Path) -> None:
    palette = extract_palette(_make_two_color_png(tmp_path), region="hero")
    # coral is lighter than navy
    assert palette.colors[palette.lightest_idx].hex == "#e97e47"
    assert palette.colors[palette.darkest_idx].hex == "#1a2540"


def test_extract_palette_none_path_is_empty() -> None:
    palette = extract_palette(None, region="hero")
    assert palette.colors == []
    assert palette.lightest_idx is None


def test_extract_palette_missing_file_is_empty(tmp_path: Path) -> None:
    palette = extract_palette(str(tmp_path / "nope.png"), region="hero")
    assert palette.colors == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_onboard_pixel_palette.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'stages.onboard.pixel_palette'`.

- [ ] **Step 3: Create the implementation**

Create `stages/onboard/pixel_palette.py`:

```python
"""Stage Onboard-2 — quantize a screenshot into a ranked color palette.

Pure over the image bytes (deterministic median-cut). The "eyedropper":
it produces REAL measured hex values + coverage %, which Layer 3 (vision)
then assigns roles to by index. Never invents a color.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PIL import Image

from models_onboard import PaletteColor, PixelPalette

_MAX_COLORS = 8
_DOWNSCALE = 200  # px longest edge — quantize on a thumbnail for speed/stability


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    r, g, b = rgb
    return f"#{r:02x}{g:02x}{b:02x}"


def _luminance(rgb: tuple[int, int, int]) -> float:
    r, g, b = rgb
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def extract_palette(
    image_path: Optional[str], region: str = "hero", max_colors: int = _MAX_COLORS
) -> PixelPalette:
    """Median-cut quantize `image_path` into ≤ max_colors ranked by
    coverage. Returns an empty palette if the path is None/missing/unreadable.
    """
    if not image_path:
        return PixelPalette()
    p = Path(image_path)
    if not p.exists():
        return PixelPalette()
    try:
        img = Image.open(p).convert("RGB")
    except Exception:
        return PixelPalette()

    img.thumbnail((_DOWNSCALE, _DOWNSCALE))
    quantized = img.quantize(colors=max_colors)
    palette_flat = quantized.getpalette() or []
    counts = quantized.getcolors() or []  # list of (count, palette_index)
    total = sum(c for c, _ in counts) or 1

    rows: list[tuple[float, tuple[int, int, int]]] = []
    for count, idx in counts:
        base = idx * 3
        rgb = (
            palette_flat[base], palette_flat[base + 1], palette_flat[base + 2],
        )
        rows.append((count / total * 100.0, rgb))

    # Rank by coverage descending.
    rows.sort(key=lambda r: r[0], reverse=True)

    colors = [
        PaletteColor(hex=_rgb_to_hex(rgb), coverage_pct=round(pct, 2), region=region)
        for pct, rgb in rows
    ]
    if not colors:
        return PixelPalette()

    lum = [_luminance(rgb) for _, rgb in rows]
    lightest_idx = max(range(len(lum)), key=lambda i: lum[i])
    darkest_idx = min(range(len(lum)), key=lambda i: lum[i])

    return PixelPalette(
        colors=colors, lightest_idx=lightest_idx, darkest_idx=darkest_idx
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_onboard_pixel_palette.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add research/preprocessor/stages/onboard/pixel_palette.py research/preprocessor/tests/test_onboard_pixel_palette.py
git commit -m "feat(onboard): pixel_palette median-cut color extraction"
```

---

## Task 5: `reconcile.py` — pure value resolution

**Files:**
- Create: `stages/onboard/reconcile.py`
- Test: `tests/test_onboard_reconcile.py`

This is the only place values get bound. It applies the §5.1 fallback chains and computes provenance/confidence/needs_review/status.

- [ ] **Step 1: Write the failing test**

Create `tests/test_onboard_reconcile.py`:

```python
"""Tests for Stage Onboard-4 — reconcile (pure resolution)."""

from __future__ import annotations

from models_onboard import (
    DomSignals,
    FlatHexFallback,
    OnboardRequest,
    PaletteColor,
    PixelPalette,
    VisionAxes,
    VisionReading,
    VisionRoleRefs,
)
from stages.onboard.reconcile import reconcile


def _palette() -> PixelPalette:
    return PixelPalette(
        colors=[
            PaletteColor(hex="#1a2540", coverage_pct=60.0, region="hero"),  # 0 navy
            PaletteColor(hex="#f5efe3", coverage_pct=25.0, region="hero"),  # 1 cream
            PaletteColor(hex="#e97e47", coverage_pct=15.0, region="hero"),  # 2 coral
        ],
        lightest_idx=1, darkest_idx=0,
    )


def _vision() -> VisionReading:
    return VisionReading(
        role_refs=VisionRoleRefs(primary=0, accent=2, neutral_dark=0,
                                 neutral_mid=None, neutral_light=1),
        axes=VisionAxes(accent_mechanic="contrasting_hue", ground_mode="cool_light",
                        texture="smooth", headline_type="sans"),
        confidence={"primary": 0.95, "accent": 0.9, "neutral_light": 0.8},
    )


def _dom() -> DomSignals:
    return DomSignals(font_head="Montserrat", font_body="Source Sans Pro")


def _req() -> OnboardRequest:
    return OnboardRequest(
        record_id="rec1", website_url="https://x.de",
        flat_hex_fallback=FlatHexFallback(dark="#000", light="#fff", accent="#f00"),
    )


def test_happy_path_uses_vision_plus_pixel() -> None:
    res = reconcile(dom=_dom(), palette=_palette(), vision=_vision(),
                    request=_req(), capture_status="ok")
    bp = res.brand_profile
    assert bp.brand_primary == "#1a2540"
    assert bp.brand_accent == "#e97e47"
    assert bp.brand_neutral_light == "#f5efe3"
    assert bp.font_head == "Montserrat"
    assert bp.font_body == "Source Sans Pro"
    # axes captured
    assert bp.accent_mechanic == "contrasting_hue"
    assert bp.headline_type == "sans"
    # provenance + status
    assert res.provenance["brand_primary"] == "vision_role+pixel"
    assert res.provenance["font_head"] == "dom_token"
    assert res.status == "success"
    assert res.needs_review is False


def test_vision_none_falls_back_to_pixel_heuristics() -> None:
    res = reconcile(dom=_dom(), palette=_palette(), vision=None,
                    request=_req(), capture_status="ok")
    bp = res.brand_profile
    # darkest pixel → primary; most-saturated non-neutral high-coverage → accent
    assert bp.brand_primary == "#1a2540"
    assert bp.brand_accent == "#e97e47"
    assert res.provenance["brand_primary"] == "pixel_sample"
    assert res.needs_review is True  # vision miss lowers confidence
    assert res.brand_profile.accent_mechanic is None  # no vision → no axes


def test_no_palette_no_vision_uses_flat_hex() -> None:
    res = reconcile(dom=DomSignals(), palette=PixelPalette(), vision=None,
                    request=_req(), capture_status="spa_blank")
    bp = res.brand_profile
    assert bp.brand_primary == "#000"      # flat_hex.dark
    assert bp.brand_accent == "#f00"       # flat_hex.accent
    assert bp.brand_neutral_light == "#fff"
    assert res.provenance["brand_primary"] == "flat_hex_fallback"
    assert res.needs_review is True


def test_no_palette_no_flat_hex_uses_default_and_fails() -> None:
    req = OnboardRequest(record_id="r", website_url="https://x.de")  # no flat hex
    res = reconcile(dom=DomSignals(), palette=PixelPalette(), vision=None,
                    request=req, capture_status="nav_error")
    assert res.provenance["brand_primary"] == "default"
    assert res.status == "failed"
    assert res.needs_review is True


def test_out_of_range_vision_index_ignored() -> None:
    bad_vision = VisionReading(
        role_refs=VisionRoleRefs(primary=99, accent=2),  # 99 out of range
        axes=VisionAxes(), confidence={"primary": 0.9, "accent": 0.9},
    )
    res = reconcile(dom=_dom(), palette=_palette(), vision=bad_vision,
                    request=_req(), capture_status="ok")
    # primary falls back to pixel heuristic (darkest), not crash
    assert res.brand_profile.brand_primary == "#1a2540"
    assert res.provenance["brand_primary"] == "pixel_sample"


def test_missing_body_font_flags_review() -> None:
    res = reconcile(dom=DomSignals(font_head="Montserrat", font_body=None),
                    palette=_palette(), vision=_vision(),
                    request=_req(), capture_status="ok")
    assert res.brand_profile.font_body is None
    assert res.needs_review is True
    assert any("font_body" in r for r in res.review_reasons)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_onboard_reconcile.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'stages.onboard.reconcile'`.

- [ ] **Step 3: Create the implementation**

Create `stages/onboard/reconcile.py`:

```python
"""Stage Onboard-4 — reconcile signals into a BrandProfile + OnboardResult.

Pure function. The ONLY place values are bound. Applies the spec §5.1
fallback chains, records provenance + per-field confidence, and decides
needs_review + status. Vision references are dereferenced into measured
palette hex here (vision never carries a hex itself).
"""

from __future__ import annotations

from typing import Optional

from models import BrandProfile
from models_onboard import (
    DomSignals,
    OnboardDiagnostics,
    OnboardRequest,
    OnboardResult,
    PixelPalette,
    VisionReading,
)

CONFIDENCE_THRESHOLD = 0.6
CRITICAL_FIELDS = ("brand_primary", "brand_accent", "font_body")

# Worst-case defaults (only used when neither vision/pixel nor flat-hex
# supply a value). Brand-agnostic. Mirror validate_input neutrals.
_DEFAULT_PRIMARY = "#222222"
_DEFAULT_ACCENT = "#888888"
_DEFAULT_NEUTRAL_DARK = "#0F0F1F"
_DEFAULT_NEUTRAL_MID = "#7A7A8C"
_DEFAULT_NEUTRAL_LIGHT = "#FFFFFF"


def _palette_hex(palette: PixelPalette, idx: Optional[int]) -> Optional[str]:
    """Dereference a vision role index into a measured hex, or None if the
    index is missing/out-of-range.
    """
    if idx is None:
        return None
    if 0 <= idx < len(palette.colors):
        return palette.colors[idx].hex
    return None


def _saturation(hexv: str) -> float:
    r = int(hexv[1:3], 16); g = int(hexv[3:5], 16); b = int(hexv[5:7], 16)
    mx, mn = max(r, g, b), min(r, g, b)
    return 0.0 if mx == 0 else (mx - mn) / mx


def _most_saturated(palette: PixelPalette) -> Optional[str]:
    if not palette.colors:
        return None
    return max(palette.colors, key=lambda c: _saturation(c.hex)).hex


def reconcile(
    *,
    dom: DomSignals,
    palette: PixelPalette,
    vision: Optional[VisionReading],
    request: OnboardRequest,
    capture_status: str,
) -> OnboardResult:
    flat = request.flat_hex_fallback
    confidence: dict[str, float] = {}
    provenance: dict[str, str] = {}

    def set_field(name: str, value: str, prov: str, conf: float) -> str:
        provenance[name] = prov
        confidence[name] = conf
        return value

    # ── brand_primary ────────────────────────────────────────────────
    v_primary = _palette_hex(palette, vision.role_refs.primary) if vision else None
    if v_primary is not None:
        brand_primary = set_field(
            "brand_primary", v_primary, "vision_role+pixel",
            (vision.confidence or {}).get("primary", 0.7),
        )
    elif palette.darkest_idx is not None:
        brand_primary = set_field(
            "brand_primary", palette.colors[palette.darkest_idx].hex,
            "pixel_sample", 0.5,
        )
    elif flat is not None:
        brand_primary = set_field("brand_primary", flat.dark, "flat_hex_fallback", 0.3)
    else:
        brand_primary = set_field("brand_primary", _DEFAULT_PRIMARY, "default", 0.0)

    # ── brand_accent ─────────────────────────────────────────────────
    v_accent = _palette_hex(palette, vision.role_refs.accent) if vision else None
    if v_accent is not None:
        brand_accent = set_field(
            "brand_accent", v_accent, "vision_role+pixel",
            (vision.confidence or {}).get("accent", 0.7),
        )
    elif _most_saturated(palette) is not None:
        brand_accent = set_field(
            "brand_accent", _most_saturated(palette), "pixel_sample", 0.5,
        )
    elif flat is not None:
        brand_accent = set_field("brand_accent", flat.accent, "flat_hex_fallback", 0.3)
    else:
        brand_accent = set_field("brand_accent", _DEFAULT_ACCENT, "default", 0.0)

    # ── brand_neutral_light ──────────────────────────────────────────
    v_light = _palette_hex(palette, vision.role_refs.neutral_light) if vision else None
    if v_light is not None:
        brand_neutral_light = set_field(
            "brand_neutral_light", v_light, "vision_role+pixel",
            (vision.confidence or {}).get("neutral_light", 0.7),
        )
    elif palette.lightest_idx is not None:
        brand_neutral_light = set_field(
            "brand_neutral_light", palette.colors[palette.lightest_idx].hex,
            "pixel_sample", 0.5,
        )
    elif flat is not None:
        brand_neutral_light = set_field(
            "brand_neutral_light", flat.light, "flat_hex_fallback", 0.3,
        )
    else:
        brand_neutral_light = set_field(
            "brand_neutral_light", _DEFAULT_NEUTRAL_LIGHT, "default", 0.0,
        )

    # ── brand_neutral_dark ───────────────────────────────────────────
    v_dark = _palette_hex(palette, vision.role_refs.neutral_dark) if vision else None
    if v_dark is not None:
        brand_neutral_dark = set_field(
            "brand_neutral_dark", v_dark, "vision_role+pixel",
            (vision.confidence or {}).get("neutral_dark", 0.7),
        )
    elif palette.darkest_idx is not None:
        brand_neutral_dark = set_field(
            "brand_neutral_dark", palette.colors[palette.darkest_idx].hex,
            "pixel_sample", 0.5,
        )
    else:
        brand_neutral_dark = set_field(
            "brand_neutral_dark", _DEFAULT_NEUTRAL_DARK, "default", 0.2,
        )

    # ── brand_neutral_mid ────────────────────────────────────────────
    v_mid = _palette_hex(palette, vision.role_refs.neutral_mid) if vision else None
    if v_mid is not None:
        brand_neutral_mid = set_field(
            "brand_neutral_mid", v_mid, "vision_role+pixel",
            (vision.confidence or {}).get("neutral_mid", 0.7),
        )
    else:
        brand_neutral_mid = set_field(
            "brand_neutral_mid", _DEFAULT_NEUTRAL_MID, "default", 0.2,
        )

    # ── fonts ────────────────────────────────────────────────────────
    if dom.font_head:
        font_head = set_field("font_head", dom.font_head, "dom_token", 0.9)
    else:
        provenance["font_head"] = "default"; confidence["font_head"] = 0.0
        font_head = None
    if dom.font_body:
        font_body = set_field("font_body", dom.font_body, "dom_token", 0.9)
    else:
        provenance["font_body"] = "default"; confidence["font_body"] = 0.0
        font_body = None

    # ── perceptual axes (vision-only; null if no vision) ─────────────
    axes = vision.axes if vision else None
    brand_profile = BrandProfile(
        brand_primary=brand_primary,
        brand_accent=brand_accent,
        brand_neutral_dark=brand_neutral_dark,
        brand_neutral_mid=brand_neutral_mid,
        brand_neutral_light=brand_neutral_light,
        font_head=font_head,
        font_body=font_body,
        accent_mechanic=axes.accent_mechanic if axes else None,
        ground_mode=axes.ground_mode if axes else None,
        texture=axes.texture if axes else None,
        headline_type=axes.headline_type if axes else None,
    )

    # ── review + status ──────────────────────────────────────────────
    review_reasons: list[str] = []
    for field in CRITICAL_FIELDS:
        conf = confidence.get(field, 0.0)
        prov = provenance.get(field, "default")
        if conf < CONFIDENCE_THRESHOLD:
            review_reasons.append(
                f"{field}: low confidence ({conf:.2f}, source={prov})"
            )
    if vision is None:
        review_reasons.append("vision layer unavailable — colors from pixel/fallback only")

    needs_review = len(review_reasons) > 0

    primary_defaulted = provenance.get("brand_primary") == "default"
    accent_defaulted = provenance.get("brand_accent") == "default"
    if primary_defaulted and accent_defaulted:
        status = "failed"
    elif needs_review:
        status = "partial"
    else:
        status = "success"

    return OnboardResult(
        record_id=request.record_id,
        job_id="",  # filled by the orchestrator
        status=status,
        brand_profile=brand_profile,
        field_confidence=confidence,
        provenance=provenance,
        needs_review=needs_review,
        review_reasons=review_reasons,
        diagnostics=OnboardDiagnostics(
            render_mode=capture_status,
            palette_size=len(palette.colors),
        ),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_onboard_reconcile.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add research/preprocessor/stages/onboard/reconcile.py research/preprocessor/tests/test_onboard_reconcile.py
git commit -m "feat(onboard): reconcile — value binding, provenance, fallbacks, status"
```

---

## Task 6: `vision_reading.py` — OpenRouter Sonnet call

**Files:**
- Create: `stages/onboard/vision_reading.py`
- Test: `tests/test_onboard_vision_reading.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_onboard_vision_reading.py`:

```python
"""Tests for Stage Onboard-3 — vision_reading (OpenRouter call)."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from PIL import Image

from models_onboard import DomSignals, PaletteColor, PixelPalette
from stages.onboard.vision_reading import (
    read_vision,
    _build_palette_prompt,
    _validate_indices,
)
from models_onboard import VisionReading, VisionRoleRefs, VisionAxes


def _png(tmp_path: Path) -> str:
    p = tmp_path / "hero.png"
    Image.new("RGB", (10, 10), (26, 37, 64)).save(p)
    return str(p)


def _palette() -> PixelPalette:
    return PixelPalette(colors=[
        PaletteColor(hex="#1a2540", coverage_pct=60, region="hero"),
        PaletteColor(hex="#e97e47", coverage_pct=20, region="hero"),
    ], lightest_idx=1, darkest_idx=0)


def _ok_response_json() -> dict:
    content = {
        "role_refs": {"primary": 0, "accent": 1, "neutral_dark": 0,
                      "neutral_mid": None, "neutral_light": 1},
        "axes": {"accent_mechanic": "contrasting_hue", "ground_mode": "cool_light",
                 "texture": "smooth", "headline_type": "sans"},
        "confidence": {"primary": 0.95, "accent": 0.9},
        "notes": "navy primary, coral accent",
    }
    return {"choices": [{"message": {"content": json.dumps(content)}}]}


def test_build_palette_prompt_lists_indices() -> None:
    text = _build_palette_prompt(_palette(), DomSignals(font_head="Montserrat"))
    assert "[0]" in text and "#1a2540" in text
    assert "[1]" in text and "#e97e47" in text
    assert "Montserrat" in text


def test_validate_indices_drops_out_of_range() -> None:
    vr = VisionReading(
        role_refs=VisionRoleRefs(primary=0, accent=99),
        axes=VisionAxes(), confidence={},
    )
    cleaned = _validate_indices(vr, palette_len=2)
    assert cleaned.role_refs.primary == 0
    assert cleaned.role_refs.accent is None  # 99 dropped


@pytest.mark.anyio
async def test_read_vision_parses_ok(tmp_path: Path) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_ok_response_json())
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        vr = await read_vision(
            hero_png=_png(tmp_path), fullpage_png=None,
            palette=_palette(), dom=DomSignals(),
            api_key="k", model="anthropic/claude-sonnet-4.6", http_client=client,
        )
    assert vr is not None
    assert vr.role_refs.primary == 0
    assert vr.axes.headline_type == "sans"


@pytest.mark.anyio
async def test_read_vision_api_error_returns_none(tmp_path: Path) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        vr = await read_vision(
            hero_png=_png(tmp_path), fullpage_png=None,
            palette=_palette(), dom=DomSignals(),
            api_key="k", model="m", http_client=client,
        )
    assert vr is None


@pytest.mark.anyio
async def test_read_vision_no_api_key_returns_none(tmp_path: Path) -> None:
    vr = await read_vision(
        hero_png=_png(tmp_path), fullpage_png=None,
        palette=_palette(), dom=DomSignals(), api_key=None, model="m",
    )
    assert vr is None


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_onboard_vision_reading.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'stages.onboard.vision_reading'`.

- [ ] **Step 3: Create the implementation**

Create `stages/onboard/vision_reading.py`:

```python
"""Stage Onboard-3 — vision reading via OpenRouter (default Sonnet 4.6).

The "eye": looks at the screenshots + the MEASURED palette and assigns
semantic roles by INDEX (never a hex) plus the perceptual axes. Returns
None on any failure (missing key, API error, unparseable response) so the
reconcile layer degrades gracefully.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Optional

import httpx

from models_onboard import (
    DomSignals,
    PixelPalette,
    VisionAxes,
    VisionReading,
    VisionRoleRefs,
)

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_TIMEOUT = 60.0

_SYSTEM_PROMPT = (
    "You are an expert brand and visual designer. You are shown screenshots "
    "of a company's website plus a list of colors that have ALREADY been "
    "measured from the page (each with an index). Your job is judgment, not "
    "measurement: decide which MEASURED color (by index) plays each brand "
    "role, and classify the brand's visual axes. NEVER output a hex code — "
    "only indices into the provided palette. If unsure, use null."
)

# Strict JSON schema for the structured response.
_RESPONSE_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "brand_vision_reading",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "role_refs": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "primary": {"type": ["integer", "null"]},
                        "accent": {"type": ["integer", "null"]},
                        "neutral_dark": {"type": ["integer", "null"]},
                        "neutral_mid": {"type": ["integer", "null"]},
                        "neutral_light": {"type": ["integer", "null"]},
                    },
                    "required": ["primary", "accent", "neutral_dark",
                                 "neutral_mid", "neutral_light"],
                },
                "axes": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "accent_mechanic": {"type": ["string", "null"]},
                        "ground_mode": {"type": ["string", "null"]},
                        "texture": {"type": ["string", "null"]},
                        "headline_type": {"type": ["string", "null"]},
                    },
                    "required": ["accent_mechanic", "ground_mode",
                                 "texture", "headline_type"],
                },
                "confidence": {"type": "object", "additionalProperties": {"type": "number"}},
                "notes": {"type": ["string", "null"]},
            },
            "required": ["role_refs", "axes", "confidence", "notes"],
        },
    },
}


def _build_palette_prompt(palette: PixelPalette, dom: DomSignals) -> str:
    lines = ["MEASURED PALETTE (assign roles by index; do not invent colors):"]
    for i, c in enumerate(palette.colors):
        lines.append(f"  [{i}] {c.hex}  (~{c.coverage_pct:.0f}% coverage, {c.region})")
    lines.append("")
    lines.append("RESOLVED FONTS (from the DOM):")
    lines.append(f"  heading: {dom.font_head or 'unknown'}")
    lines.append(f"  body:    {dom.font_body or 'unknown'}")
    lines.append("")
    lines.append(
        "AXES — accent_mechanic ∈ {contrasting_hue, tonal_same_hue}; "
        "ground_mode ∈ {cream_textured, cool_light, role_split, tri, "
        "saturated_dark+light}; texture ∈ {marble_paper, crumpled_paper, "
        "smooth, photo}; headline_type ∈ {serif, sans, sans_allcaps}."
    )
    return "\n".join(lines)


def _encode_image(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    p = Path(path)
    if not p.exists():
        return None
    b64 = base64.b64encode(p.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _build_messages(hero_png, fullpage_png, palette, dom) -> list[dict]:
    content: list[dict] = [{"type": "text", "text": _build_palette_prompt(palette, dom)}]
    for img in (hero_png, fullpage_png):
        data_url = _encode_image(img)
        if data_url:
            content.append({"type": "image_url", "image_url": {"url": data_url}})
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": content},
    ]


def _validate_indices(reading: VisionReading, palette_len: int) -> VisionReading:
    """Null out any role index that is out of range for the palette."""
    rr = reading.role_refs
    def ok(i: Optional[int]) -> Optional[int]:
        return i if (i is not None and 0 <= i < palette_len) else None
    reading.role_refs = VisionRoleRefs(
        primary=ok(rr.primary), accent=ok(rr.accent),
        neutral_dark=ok(rr.neutral_dark), neutral_mid=ok(rr.neutral_mid),
        neutral_light=ok(rr.neutral_light),
    )
    return reading


async def read_vision(
    *,
    hero_png: Optional[str],
    fullpage_png: Optional[str],
    palette: PixelPalette,
    dom: DomSignals,
    api_key: Optional[str],
    model: str,
    http_client: Optional[httpx.AsyncClient] = None,
    timeout: float = _TIMEOUT,
) -> Optional[VisionReading]:
    """Call the vision model. Returns a VisionReading, or None on any
    failure (caller degrades to pixel/flat-hex fallback).
    """
    if not api_key or not hero_png:
        return None

    payload = {
        "model": model,
        "messages": _build_messages(hero_png, fullpage_png, palette, dom),
        "temperature": 0,
        "response_format": _RESPONSE_SCHEMA,
    }
    headers = {"Authorization": f"Bearer {api_key}",
               "Content-Type": "application/json"}

    owns = http_client is None
    client = http_client or httpx.AsyncClient(timeout=timeout)
    try:
        resp = await client.post(_OPENROUTER_URL, json=payload, headers=headers)
        if resp.status_code != 200:
            return None
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        reading = VisionReading(
            role_refs=VisionRoleRefs(**(parsed.get("role_refs") or {})),
            axes=VisionAxes(**(parsed.get("axes") or {})),
            confidence=parsed.get("confidence") or {},
            notes=parsed.get("notes"),
        )
        return _validate_indices(reading, len(palette.colors))
    except (httpx.HTTPError, KeyError, ValueError, TypeError):
        return None
    finally:
        if owns:
            await client.aclose()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_onboard_vision_reading.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add research/preprocessor/stages/onboard/vision_reading.py research/preprocessor/tests/test_onboard_vision_reading.py
git commit -m "feat(onboard): vision_reading — OpenRouter Sonnet, index-only roles"
```

---

## Task 7: `capture.py` — Playwright session

**Files:**
- Create: `stages/onboard/capture.py`
- Test: `tests/test_onboard_capture.py`

The real browser work is integration-tested via a fake `async_playwright`; the pure helpers (`_looks_blank`, the DOM JS constant, consent selectors) are unit-tested.

- [ ] **Step 1: Write the failing test**

Create `tests/test_onboard_capture.py`:

```python
"""Tests for Stage Onboard-0 — capture (Playwright session)."""

from __future__ import annotations

import pytest

from stages.onboard import capture as cap
from models_onboard import OnboardRequest


def test_dom_eval_js_is_nonempty_and_has_key_tokens() -> None:
    js = cap.DOM_EVAL_JS
    assert isinstance(js, str) and len(js) > 50
    assert "getComputedStyle" in js
    assert "fontFamily" in js
    assert "cssVars" in js          # returns the documented shape


def test_looks_blank_true_for_empty_signal() -> None:
    assert cap._looks_blank({"sampledColors": [], "bodyText": ""}) is True


def test_looks_blank_false_with_content() -> None:
    assert cap._looks_blank(
        {"sampledColors": ["rgb(1,2,3)"], "bodyText": "Hello world"}
    ) is False


def test_consent_selectors_nonempty() -> None:
    assert len(cap.CONSENT_TEXTS) > 0
    assert any("akzeptier" in t.lower() for t in cap.CONSENT_TEXTS)


@pytest.mark.anyio
async def test_capture_maps_fake_session(tmp_path, monkeypatch) -> None:
    """A fake async_playwright proves CaptureResult mapping without a browser."""
    from tests._onboard_fakes import fake_async_playwright
    monkeypatch.setattr(cap, "async_playwright", fake_async_playwright(
        raw_dom_eval={"cssVars": {}, "fontHead": "Montserrat, sans-serif",
                      "fontBody": "Arial", "sampledColors": ["rgb(1,2,3)"],
                      "bodyText": "Hi", "logoUrl": None},
    ))
    result = await cap.capture(
        OnboardRequest(record_id="r", website_url="https://x.de"),
        output_dir=tmp_path,
    )
    assert result.status == "ok"
    assert result.hero_png is not None
    assert result.raw_dom_eval["fontHead"].startswith("Montserrat")


@pytest.mark.anyio
async def test_capture_navigation_error_returns_status(tmp_path, monkeypatch) -> None:
    from tests._onboard_fakes import fake_async_playwright
    monkeypatch.setattr(cap, "async_playwright", fake_async_playwright(raise_on_goto=True))
    result = await cap.capture(
        OnboardRequest(record_id="r", website_url="https://x.de"),
        output_dir=tmp_path,
    )
    assert result.status in ("nav_error", "timeout")
    assert result.hero_png is None


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
```

- [ ] **Step 2: Create the test fake helper**

Create `tests/_onboard_fakes.py`:

```python
"""Fake async_playwright for capture tests — no real browser."""

from __future__ import annotations

from pathlib import Path


class _FakePage:
    def __init__(self, raw_dom_eval, raise_on_goto):
        self._raw = raw_dom_eval
        self._raise = raise_on_goto

    async def goto(self, url, wait_until=None, timeout=None):
        if self._raise:
            raise RuntimeError("nav failed")

    async def evaluate(self, js):
        # Scroll calls pass JS that isn't our DOM blob; return None for those.
        if isinstance(js, str) and "cssVars" in js:
            return self._raw
        return None

    async def screenshot(self, path=None, full_page=False, **kw):
        Path(path).write_bytes(b"\x89PNG\r\n\x1a\nFAKE")

    async def query_selector_all(self, selector):
        return []

    async def set_viewport_size(self, *a, **k):
        return None


class _FakeBrowser:
    def __init__(self, page): self._page = page
    async def new_page(self, **kw): return self._page
    async def close(self): return None


class _FakeChromium:
    def __init__(self, page): self._page = page
    async def launch(self, **kw): return _FakeBrowser(self._page)


class _FakePW:
    def __init__(self, page): self.chromium = _FakeChromium(page)


class _FakeCtx:
    def __init__(self, page): self._page = page
    async def __aenter__(self): return _FakePW(self._page)
    async def __aexit__(self, *a): return False


def fake_async_playwright(raw_dom_eval=None, raise_on_goto=False):
    page = _FakePage(raw_dom_eval or {}, raise_on_goto)
    def factory():
        return _FakeCtx(page)
    return factory
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_onboard_capture.py -v`
Expected: FAIL — `AttributeError`/`ImportError` on `stages.onboard.capture`.

- [ ] **Step 4: Create the implementation**

Create `stages/onboard/capture.py`:

```python
"""Stage Onboard-0 — capture screenshots + DOM signals via Playwright.

Owns the single browser session. Best-effort cookie dismissal, lazy-load
scroll, hero + full-page screenshots, and one page.evaluate() that returns
the raw DOM blob (parsed later by dom_extract). NEVER raises — failures map
to a status code and empty outputs.
"""

from __future__ import annotations

from pathlib import Path

from playwright.async_api import async_playwright  # re-exported for monkeypatch

from models_onboard import CaptureResult, OnboardRequest

_VIEWPORT = {"width": 1440, "height": 900}
_NAV_TIMEOUT_MS = 30000

# Cookie/consent button label substrings (German + English), case-insensitive.
CONSENT_TEXTS = (
    "akzeptieren", "alle akzeptieren", "zustimmen", "einverstanden",
    "accept", "accept all", "agree", "i agree", "allow all", "got it",
)

# Returns the documented raw shape: {cssVars, fontHead, fontBody,
# sampledColors, bodyText, logoUrl}.
DOM_EVAL_JS = r"""
() => {
  const out = { cssVars: {}, fontHead: null, fontBody: null,
                sampledColors: [], bodyText: "", logoUrl: null };
  try {
    const rootStyle = getComputedStyle(document.documentElement);
    for (let i = 0; i < rootStyle.length; i++) {
      const prop = rootStyle[i];
      if (prop.startsWith("--")) {
        const val = rootStyle.getPropertyValue(prop).trim();
        if (val) out.cssVars[prop] = val;
      }
    }
    const h = document.querySelector("h1, h2");
    const b = document.querySelector("p, body");
    if (h) out.fontHead = getComputedStyle(h).fontFamily;
    if (b) out.fontBody = getComputedStyle(b).fontFamily;

    const sel = "header, nav, h1, h2, button, a.btn, .hero, [class*=hero]";
    const seen = [];
    document.querySelectorAll(sel).forEach((el) => {
      const cs = getComputedStyle(el);
      [cs.color, cs.backgroundColor, cs.borderColor].forEach((c) => {
        if (c && c !== "rgba(0, 0, 0, 0)" && !seen.includes(c)) seen.push(c);
      });
    });
    out.sampledColors = seen.slice(0, 30);
    out.bodyText = (document.body ? document.body.innerText : "").slice(0, 500);

    const logo = document.querySelector(
      "header img, img[alt*=logo i], img[class*=logo i], a[href='/'] img");
    if (logo && logo.src) out.logoUrl = logo.src;
  } catch (e) {}
  return out;
}
"""


def _looks_blank(raw: dict) -> bool:
    """True if the page produced no usable content (likely an unrendered SPA)."""
    if not raw:
        return True
    colors = raw.get("sampledColors") or []
    text = (raw.get("bodyText") or "").strip()
    return len(colors) == 0 and len(text) == 0


async def _dismiss_consent(page) -> None:
    """Best-effort cookie/consent dismissal. Never raises."""
    try:
        buttons = await page.query_selector_all("button, a, [role=button]")
        for btn in buttons:
            try:
                label = (await btn.inner_text()).strip().lower()
            except Exception:
                continue
            if any(t in label for t in CONSENT_TEXTS):
                try:
                    await btn.click(timeout=2000)
                    return
                except Exception:
                    continue
    except Exception:
        return


async def _scroll_to_trigger_lazy(page) -> None:
    try:
        await page.evaluate(
            "async () => { for (let y=0; y<document.body.scrollHeight; y+=600)"
            " { window.scrollTo(0, y); await new Promise(r=>setTimeout(r,80)); }"
            " window.scrollTo(0,0); }"
        )
    except Exception:
        return


async def capture(
    request: OnboardRequest, *, output_dir: Path, timeout_ms: int = _NAV_TIMEOUT_MS
) -> CaptureResult:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    hero_path = output_dir / "hero.png"
    fullpage_path = output_dir / "fullpage.png"
    notes: list[str] = []

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                page = await browser.new_page(viewport=_VIEWPORT)
                try:
                    await page.goto(request.website_url,
                                    wait_until="networkidle", timeout=timeout_ms)
                except Exception as exc:  # navigation/timeout
                    notes.append(f"navigation failed: {exc!s}")
                    status = "timeout" if "timeout" in str(exc).lower() else "nav_error"
                    return CaptureResult(hero_png=None, fullpage_png=None,
                                         raw_dom_eval={}, status=status, notes=notes)

                await _dismiss_consent(page)
                await _scroll_to_trigger_lazy(page)

                await page.screenshot(path=str(hero_path), full_page=False)
                await page.screenshot(path=str(fullpage_path), full_page=True)
                raw = await page.evaluate(DOM_EVAL_JS)

                status = "spa_blank" if _looks_blank(raw) else "ok"
                return CaptureResult(
                    hero_png=str(hero_path), fullpage_png=str(fullpage_path),
                    raw_dom_eval=raw or {}, status=status, notes=notes,
                )
            finally:
                await browser.close()
    except Exception as exc:  # playwright launch / unexpected
        notes.append(f"capture failed: {exc!s}")
        return CaptureResult(hero_png=None, fullpage_png=None, raw_dom_eval={},
                             status="nav_error", notes=notes)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_onboard_capture.py -v`
Expected: PASS (6 tests).

- [ ] **Step 6: Commit**

```bash
git add research/preprocessor/stages/onboard/capture.py research/preprocessor/tests/test_onboard_capture.py research/preprocessor/tests/_onboard_fakes.py
git commit -m "feat(onboard): capture — Playwright screenshots + DOM eval"
```

---

## Task 8: `pipeline.py` — orchestrator

**Files:**
- Create: `stages/onboard/pipeline.py`
- Test: `tests/test_onboard_pipeline.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_onboard_pipeline.py`:

```python
"""Tests for the onboard pipeline orchestrator."""

from __future__ import annotations

import pytest

from stages.onboard import pipeline as pl
from models_onboard import (
    CaptureResult, DomSignals, OnboardRequest, PaletteColor, PixelPalette,
    VisionAxes, VisionReading, VisionRoleRefs,
)


def _req() -> OnboardRequest:
    return OnboardRequest(record_id="rec1", website_url="https://x.de")


@pytest.mark.anyio
async def test_pipeline_happy_path(tmp_path, monkeypatch) -> None:
    async def fake_capture(request, *, output_dir, timeout_ms=30000):
        return CaptureResult(hero_png="h.png", fullpage_png="f.png",
                             raw_dom_eval={"fontHead": "Montserrat"}, status="ok")
    def fake_parse(raw):
        return DomSignals(font_head="Montserrat", font_body="Arial")
    def fake_extract(path, region="hero", max_colors=8):
        return PixelPalette(colors=[PaletteColor(hex="#1a2540", coverage_pct=70, region="hero")],
                            lightest_idx=0, darkest_idx=0)
    async def fake_vision(**kw):
        return VisionReading(role_refs=VisionRoleRefs(primary=0, accent=0),
                             axes=VisionAxes(headline_type="sans"),
                             confidence={"primary": 0.9, "accent": 0.9})

    monkeypatch.setattr(pl, "capture", fake_capture)
    monkeypatch.setattr(pl.dom_extract, "parse", fake_parse)
    monkeypatch.setattr(pl.pixel_palette, "extract_palette", fake_extract)
    monkeypatch.setattr(pl, "read_vision", fake_vision)

    result = await pl.run_onboard_pipeline(
        _req(), output_dir=tmp_path, api_key="k", model="m")
    assert result.brand_profile.brand_primary == "#1a2540"
    assert result.brand_profile.headline_type == "sans"
    assert result.diagnostics.render_mode == "ok"
    assert result.diagnostics.vision_model == "m"
    assert "capture" in result.diagnostics.timings_ms


@pytest.mark.anyio
async def test_pipeline_capture_failure_degrades(tmp_path, monkeypatch) -> None:
    async def fake_capture(request, *, output_dir, timeout_ms=30000):
        return CaptureResult(hero_png=None, fullpage_png=None,
                             raw_dom_eval={}, status="nav_error")
    monkeypatch.setattr(pl, "capture", fake_capture)
    # vision must NOT be called when hero is None — guard with a raiser
    async def boom(**kw): raise AssertionError("vision should be skipped")
    monkeypatch.setattr(pl, "read_vision", boom)

    result = await pl.run_onboard_pipeline(
        _req(), output_dir=tmp_path, api_key="k", model="m")
    assert result.status in ("failed", "partial")
    assert result.needs_review is True


@pytest.mark.anyio
async def test_pipeline_unexpected_exception_is_caught(tmp_path, monkeypatch) -> None:
    async def fake_capture(request, *, output_dir, timeout_ms=30000):
        raise RuntimeError("kaboom")
    monkeypatch.setattr(pl, "capture", fake_capture)
    result = await pl.run_onboard_pipeline(
        _req(), output_dir=tmp_path, api_key="k", model="m")
    assert result.status == "failed"
    assert result.needs_review is True


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_onboard_pipeline.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'stages.onboard.pipeline'`.

- [ ] **Step 3: Create the implementation**

Create `stages/onboard/pipeline.py`:

```python
"""Onboard orchestrator — runs the 5-layer chain and assembles OnboardResult.

Each layer consumes only the previous layer's typed output. Wrapped so any
unexpected error degrades to a failed-but-valid result (webhook still fires).
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

import httpx

from models_onboard import OnboardRequest, OnboardResult, PixelPalette
from stages.onboard import dom_extract, pixel_palette
from stages.onboard.capture import capture
from stages.onboard.reconcile import reconcile
from stages.onboard.vision_reading import read_vision


async def run_onboard_pipeline(
    request: OnboardRequest,
    *,
    output_dir: Path,
    api_key: Optional[str],
    model: str,
    http_client: Optional[httpx.AsyncClient] = None,
) -> OnboardResult:
    timings: dict[str, int] = {}

    def _mark(name: str, start: float) -> None:
        timings[name] = int((time.perf_counter() - start) * 1000)

    try:
        t = time.perf_counter()
        cap = await capture(request, output_dir=Path(output_dir))
        _mark("capture", t)

        t = time.perf_counter()
        dom = dom_extract.parse(cap.raw_dom_eval)
        _mark("dom_extract", t)

        t = time.perf_counter()
        palette = (pixel_palette.extract_palette(cap.hero_png, region="hero")
                   if cap.hero_png else PixelPalette())
        _mark("pixel_palette", t)

        t = time.perf_counter()
        vision = None
        if cap.hero_png and api_key:
            vision = await read_vision(
                hero_png=cap.hero_png, fullpage_png=cap.fullpage_png,
                palette=palette, dom=dom, api_key=api_key, model=model,
                http_client=http_client,
            )
        _mark("vision", t)

        result = reconcile(
            dom=dom, palette=palette, vision=vision,
            request=request, capture_status=cap.status,
        )
        result.diagnostics.screenshots = [
            p for p in (cap.hero_png, cap.fullpage_png) if p
        ]
        result.diagnostics.timings_ms = timings
        result.diagnostics.vision_model = model if vision is not None else None
        return result

    except Exception as exc:  # last-resort guard — never crash the request
        result = reconcile(
            dom=dom_extract.parse({}), palette=PixelPalette(), vision=None,
            request=request, capture_status="nav_error",
        )
        result.status = "failed"
        result.needs_review = True
        result.review_reasons.append(f"pipeline exception: {exc!s}")
        result.diagnostics.timings_ms = timings
        return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_onboard_pipeline.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add research/preprocessor/stages/onboard/pipeline.py research/preprocessor/tests/test_onboard_pipeline.py
git commit -m "feat(onboard): pipeline orchestrator with degrade-on-error"
```

---

## Task 9: `/onboard` endpoint — 202 + BackgroundTask + webhook delivery

**Files:**
- Modify: `main.py` (replace the `/onboard` stub)
- Test: `tests/test_onboard_endpoint.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_onboard_endpoint.py`:

```python
"""End-to-end test of the /onboard endpoint (pipeline + delivery mocked)."""

from __future__ import annotations

import main
from fastapi.testclient import TestClient
from models import BrandProfile
from models_onboard import OnboardDiagnostics, OnboardResult


def _fake_result(record_id: str) -> OnboardResult:
    return OnboardResult(
        record_id=record_id, job_id="", status="success",
        brand_profile=BrandProfile(brand_primary="#1a2540"),
        diagnostics=OnboardDiagnostics(render_mode="ok", palette_size=4),
    )


def test_onboard_returns_202_with_job_id(monkeypatch) -> None:
    delivered = {}

    async def fake_pipeline(request, **kw):
        return _fake_result(request.record_id)

    async def fake_deliver(result, webhook, output_dir):
        delivered["record_id"] = result.record_id
        delivered["job_id"] = result.job_id
        delivered["webhook"] = webhook

    monkeypatch.setattr(main, "run_onboard_pipeline", fake_pipeline)
    monkeypatch.setattr(main, "_deliver_result", fake_deliver)

    client = TestClient(main.app)
    resp = client.post("/onboard", json={
        "record_id": "recABC", "website_url": "https://x.de",
    })
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["status"] == "accepted"
    assert body["record_id"] == "recABC"
    assert body["job_id"]
    # BackgroundTask ran during TestClient request handling
    assert delivered["record_id"] == "recABC"
    assert delivered["job_id"] == body["job_id"]


def test_onboard_missing_website_url_returns_422() -> None:
    client = TestClient(main.app)
    resp = client.post("/onboard", json={"record_id": "recABC"})
    assert resp.status_code == 422


def test_deliver_result_posts_then_persists_on_failure(monkeypatch, tmp_path) -> None:
    import asyncio
    import httpx

    # First: webhook returns 500 twice → persists to disk.
    calls = {"n": 0}

    async def fake_post(self, url, json=None, **kw):
        calls["n"] += 1
        return httpx.Response(500, text="no")

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    result = _fake_result("recX")
    asyncio.run(main._deliver_result(result, "https://hook.test", tmp_path))
    assert calls["n"] >= 2  # retried
    persisted = tmp_path / "onboard_result.json"
    assert persisted.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_onboard_endpoint.py -v`
Expected: FAIL — `AttributeError: module 'main' has no attribute 'run_onboard_pipeline'` (and the stub returns 501, not 202).

- [ ] **Step 3: Modify `main.py`**

In `main.py`, update imports — add to the existing import block (after the `from stages.assemble_package import assemble_package` line):

```python
from stages.onboard.pipeline import run_onboard_pipeline  # noqa: E402
from models_onboard import OnboardAccepted, OnboardRequest, OnboardResult  # noqa: E402
```

Add to the top-of-file imports (with the other stdlib imports near `import tempfile`):

```python
import json  # noqa: E402
import os  # noqa: E402
from uuid import uuid4  # noqa: E402

import httpx  # noqa: E402
from fastapi import BackgroundTasks  # noqa: E402
```

Replace the entire existing `/onboard` stub function (the `@app.post("/onboard", status_code=status.HTTP_501_NOT_IMPLEMENTED)` block and its `def onboard()` body) with:

```python
_DEFAULT_VISION_MODEL = "anthropic/claude-sonnet-4.6"
_WEBHOOK_RETRIES = 2


@app.post("/onboard", status_code=202, response_model=OnboardAccepted)
async def onboard(
    request: OnboardRequest, background_tasks: BackgroundTasks
) -> OnboardAccepted:
    """Mode 1 — visual brand extraction.

    Returns 202 immediately and runs the 5-layer pipeline in the
    background; on completion POSTs the OnboardResult to the
    report-generator webhook (n8n persists it to Airtable).
    """
    job_id = uuid4().hex
    background_tasks.add_task(_run_and_deliver, request, job_id)
    return OnboardAccepted(job_id=job_id, record_id=request.record_id)


async def _run_and_deliver(request: OnboardRequest, job_id: str) -> None:
    output_dir = Path(
        os.getenv("ONBOARD_OUTPUT_DIR") or tempfile.mkdtemp(prefix="dmc_onboard_")
    )
    result = await run_onboard_pipeline(
        request,
        output_dir=output_dir,
        api_key=os.getenv("OPENROUTER_API_KEY"),
        model=os.getenv("OPENROUTER_VISION_MODEL", _DEFAULT_VISION_MODEL),
    )
    result.job_id = job_id
    webhook = request.callback_url or os.getenv("REPORT_GENERATOR_WEBHOOK")
    await _deliver_result(result, webhook, output_dir)


async def _deliver_result(
    result: OnboardResult, webhook: Optional[str], output_dir: Path
) -> None:
    """POST the result to the webhook (2 retries); on final failure persist
    it to disk so it is never lost.
    """
    payload = result.model_dump()
    if webhook:
        async with httpx.AsyncClient(timeout=30.0) as client:
            for attempt in range(1, _WEBHOOK_RETRIES + 1):
                try:
                    resp = await client.post(webhook, json=payload)
                    if resp.status_code < 400:
                        return
                except httpx.HTTPError:
                    pass
    # Fallback: persist to disk.
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    (Path(output_dir) / "onboard_result.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
```

Note: `Optional` and `Path` and `tempfile` and `status` are already imported in `main.py` (verify the existing import block; `Optional` may need adding — if `from typing import Optional` is absent, add it).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_onboard_endpoint.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add research/preprocessor/main.py research/preprocessor/tests/test_onboard_endpoint.py
git commit -m "feat(onboard): /onboard async endpoint + webhook delivery"
```

---

## Task 10: Regression guard + full verification

**Files:**
- Verify: `tests/test_no_client_name_in_logic.py` (already rglobs `stages/**`; no change expected)

- [ ] **Step 1: Confirm the client-name guard covers the new files**

Run: `pytest tests/test_no_client_name_in_logic.py -v`
Expected: PASS — the guard's `rglob("*.py")` already scans `stages/onboard/*.py` and `models_onboard.py`. If it FAILS, a forbidden literal leaked into the new code; remove it.

- [ ] **Step 2: Run the full pre-processor suite**

Run: `pytest tests/ -v`
Expected: PASS — the prior 135 tests plus the new onboard tests (models 6 + dom 7 + pixel 6 + reconcile 6 + vision 6 + capture 6 + pipeline 3 + endpoint 3 = 43), all green.

- [ ] **Step 3: Confirm the chassis baseline is undisturbed**

Run:
```bash
cd /Users/utkarsh/Projects/richard/research/v7-renderer && source .venv/bin/activate && python -m pytest tests/ -v
```
Expected: 11/11 PASS. Then `cd` back to `research/preprocessor` and re-activate its venv.

- [ ] **Step 4: Manual smoke (optional, requires network + key)**

Only if a real `OPENROUTER_API_KEY` is exported and network is available:
```bash
export OPENROUTER_API_KEY=...        # never commit this
python -c "import asyncio, tempfile; from pathlib import Path; \
from models_onboard import OnboardRequest; \
from stages.onboard.pipeline import run_onboard_pipeline; \
r=asyncio.run(run_onboard_pipeline(OnboardRequest(record_id='t', website_url='https://www.baulig-consulting.de'), \
output_dir=Path(tempfile.mkdtemp()), api_key=__import__('os').getenv('OPENROUTER_API_KEY'), model='anthropic/claude-sonnet-4.6')); \
print(r.status, r.brand_profile.brand_primary, r.brand_profile.brand_accent, r.provenance)"
```
Expected: prints a status + measured primary/accent hexes + provenance map.

- [ ] **Step 5: Final commit**

```bash
git add -A research/preprocessor
git commit -m "test(onboard): full suite green + guard covers stages/onboard"
```

---

## Self-Review

**Spec coverage:**
- §3.3 contract chain → Tasks 3–8 (one stage each, typed contracts in Task 2). ✓
- §3.4 vision-emits-indices-not-hex → `vision_reading` schema + `_validate_indices` (Task 6) + `reconcile._palette_hex` dereference (Task 5). ✓
- §4.1 async 202 + webhook → Task 9. ✓
- §4.2/4.3 all models → Task 2. ✓
- §5 BrandProfile extension + field map + fallbacks → Task 2 (model) + Task 5 (every fallback branch tested). ✓
- §6 error table → capture status mapping (Task 7), vision None (Task 6), reconcile fallbacks + status (Task 5), webhook retry/persist (Task 9), pipeline catch-all (Task 8). ✓
- §7 test plan → one test module per layer + guard (Tasks 3–10). ✓
- §9 deps/env → Task 1 (deps) + Task 9 (env reads). ✓

**Placeholder scan:** No "TBD"/"handle edge cases"/"similar to" — every code step is complete and runnable. ✓

**Type consistency:** `reconcile(dom=, palette=, vision=, request=, capture_status=)` keyword-only signature matches its callers (pipeline + tests). `read_vision(**keyword)` matches pipeline + tests. `extract_palette(path, region=, max_colors=)` matches pipeline + tests. `OnboardResult.job_id` set by orchestrator (`reconcile` returns `""`, pipeline leaves it, endpoint sets it) — consistent. `DOM_EVAL_JS` returns `{cssVars, fontHead, fontBody, sampledColors, bodyText, logoUrl}`; `dom_extract.parse` reads exactly those keys. ✓

---

## Execution notes

- TDD throughout: every task writes the failing test first, then the minimal implementation.
- Pure layers (dom_extract, pixel_palette, reconcile) carry the bulk of coverage and need no mocks.
- Browser + network are never hit in tests (fake `async_playwright`, `httpx.MockTransport`/monkeypatch).
- Frequent commits: one per task.
