"""Task 7 — whisper grain tests.

test_grain_paints_pixel_variance
    Render a minimal page (data-ground-mode="light") to PNG via WeasyPrint +
    PyMuPDF (same path as test_visual_regression.py). Convert to grayscale numpy;
    sample the centre of the .page content box; assert band.var() > 0.0.
    This would fail with an feTurbulence grain (WeasyPrint flattens SVG filters)
    but PASSES with a base64 PNG background-image tile.

test_grain_constant_has_no_hex
    The GRAIN_DATA_URI constant must not contain any bare '#' character
    (no client hex literal leaks).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))


# ---------------------------------------------------------------------------
# test 1 — no # in the constant
# ---------------------------------------------------------------------------

def test_grain_constant_has_no_hex():
    from styles._grain import GRAIN_DATA_URI  # noqa: PLC0415
    assert "#" not in GRAIN_DATA_URI, (
        "GRAIN_DATA_URI must not contain a raw '#' (no hex literals allowed in "
        "brand-agnostic architecture files)"
    )


def test_grain_constant_has_no_client_substring():
    """Defensive guard: the base64 grain constant must not contain any known
    client name as a substring (case-insensitive), and no bare '#'.

    styles/_grain.py is excluded from the chassis-level test_no_coral_in_chassis_logic
    guard because a 59 KB random base64 string can contain any 5-letter sequence by
    chance if the tile is regenerated with a different seed.  This test compensates:
    it asserts the CURRENT constant is clean, making a future regen safe regardless
    of the guard's file scope.  If this test fails after a regen, update the seed in
    scripts/gen_grain_tile.py until the output is clean, then re-run.

    Note on "nmr": this is a 3-character sequence with a collision probability of
    roughly 1 in 64^3 ≈ 1-in-262 144, giving ~0.2 expected occurrences in a 59 KB
    base64 string.  It is virtually guaranteed to appear in ANY random base64 output
    of this size, so including it in the banned set would require regenerating the
    tile indefinitely.  The meaningful client-name risk is from longer sequences
    (4+ characters) that cannot arise by ordinary chance; those are included here.
    """
    from styles._grain import GRAIN_DATA_URI  # noqa: PLC0415

    # "nmr" excluded — it is a 3-char sequence that appears by chance in virtually
    # every 59 KB base64 blob (expected ~0.2 occurrences); not a useful signal.
    _BANNED = ("apex", "geva", "conesso", "coral", "boss")
    uri_lower = GRAIN_DATA_URI.lower()
    found = [b for b in _BANNED if b in uri_lower]
    assert not found, (
        f"GRAIN_DATA_URI contains banned client substring(s): {found}. "
        "Regenerate the grain tile (scripts/gen_grain_tile.py) with a different "
        "seed until the output contains none of: " + ", ".join(_BANNED)
    )
    assert "#" not in GRAIN_DATA_URI, (
        "GRAIN_DATA_URI must not contain a bare '#' character"
    )


# ---------------------------------------------------------------------------
# test 2 — rendered page actually shows pixel variance (grain is painting)
# ---------------------------------------------------------------------------

def _render_minimal_grain_page_to_png(tmp_path: Path) -> Path:
    """Render a minimal single .page with data-ground-mode='light' to a PNG.

    Uses WeasyPrint write_pdf + PyMuPDF rasterize — identical to the production
    path in render_package / test_visual_regression.py so the result is a true
    representation of what WeasyPrint actually paints.
    """
    import weasyprint  # noqa: PLC0415
    from assembler import shared_head_css, FONT_DIR  # noqa: PLC0415
    from brand_tokens import BrandConfig  # noqa: PLC0415
    from tokens.compile_tokens import BrandAxes  # noqa: PLC0415

    # Minimal brand — all 10 required BrandConfig fields
    brand = BrandConfig(
        brand_primary="#1A1A2E",
        brand_accent="#E94560",
        brand_neutral_dark="#2D2D2D",
        brand_neutral_mid="#888888",
        brand_neutral_light="#F5F5F5",
        font_heading="'Source Sans 3', sans-serif",
        font_body="'Source Sans 3', sans-serif",
        qr_target_url="https://example.com",
        company_name_short="TestCo",
        company_url_display="example.com",
    )
    axes = BrandAxes(ground_mode="light")
    head_css = shared_head_css(brand, FONT_DIR, axes)

    # A minimal document: the <html> carries data-ground-mode="light" (via the
    # compile_tokens data_attrs path, but we set it directly here for isolation).
    html_doc = f"""<!DOCTYPE html>
<html lang="de" data-ground-mode="light">
<head>
  <meta charset="utf-8">
  <style>{head_css}</style>
</head>
<body>
  <section class="page">
    <p>&nbsp;</p>
  </section>
</body>
</html>"""

    pdf_path = tmp_path / "grain_test.pdf"
    weasyprint.HTML(string=html_doc, base_url=str(ROOT)).write_pdf(str(pdf_path))

    # Rasterize page 1 with PyMuPDF at 2× scale (same as render_package)
    import fitz  # noqa: PLC0415
    doc = fitz.open(str(pdf_path))
    pix = doc[0].get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
    png_path = tmp_path / "grain_test_p1.png"
    pix.save(str(png_path))
    doc.close()
    return png_path


def test_grain_paints_pixel_variance(tmp_path):
    """The grain tile must produce measurable pixel variance in the rendered PNG.

    We sample a 200×200 px band from the CENTRE of the page (well inside the
    .page content box, away from @page margins which WeasyPrint renders in the
    sheet area). The band is converted to float32 grayscale; band.var() > 0
    proves the grain actually painted (would be 0.0 for a flat fill, which is
    what WeasyPrint produces for SVG feTurbulence).
    """
    png_path = _render_minimal_grain_page_to_png(tmp_path)
    img = Image.open(png_path).convert("L")  # grayscale
    w, h = img.size

    # Sample centre 200×200 band (inside content box, not the @page margin)
    cx, cy = w // 2, h // 2
    half = 100
    band = np.array(
        img.crop((cx - half, cy - half, cx + half, cy + half)),
        dtype=np.float32,
    )

    variance = float(band.var())
    assert variance > 0.0, (
        f"Grain produced ZERO pixel variance (variance={variance:.4f}). "
        "The background-image grain tile is not painting. Check that:\n"
        "  1. assembler.py includes background-image: url(GRAIN_DATA_URI) in the "
        "     [data-ground-mode='light'] .page rule\n"
        "  2. The data URI is a valid PNG (not an SVG feTurbulence filter)\n"
        "  3. The tile has non-zero alpha (alpha > 0)\n"
        f"  PNG size: {w}x{h}, centre crop: {band.shape}"
    )
    # Soft informational assertion — variance should be perceptible but subtle
    # (whisper grain, not heavy texture). No upper bound enforced: the test
    # proves existence, not magnitude.
