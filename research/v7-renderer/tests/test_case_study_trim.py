"""Case-study rail pages must paint cream/navy to the sheet trim and keep
the footer wordmark fully on-sheet (not clipped by a white bottom strip).

Root cause this pins: a 303mm .tp-rail section on a 297mm A4 bleed page
leaves ~4mm of unpainted white at the sheet foot; the footer wordmark
sits in that zone and is cut. Cream (in-flow) and rail (absolute) also
do not share one 60% line through the foot, so the split reads as two
boxes. The contract: one 297mm sheet, cream left / navy right to the
trim, footer glyphs with real cap-height above the edge.
"""
from __future__ import annotations

from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
import sys

sys.path.insert(0, str(ROOT))

from assembler import FONT_DIR, shared_head_css  # noqa: E402
from package_loader import load_package  # noqa: E402
from templating import get_env  # noqa: E402

PT_PER_MM = 72.0 / 25.4


def _html() -> str:
    pkg = load_package(ROOT / "fixtures" / "apex")
    head = shared_head_css(pkg.brand, FONT_DIR, pkg.axes, engine="chromium")
    css = (ROOT / "styles" / "treatments" / "a4_case_study.css").read_text(
        encoding="utf-8"
    )
    body = """
<section class="page treatment-a4_case_study format-a4 tp-rail">
  <div class="cs4-grid">
    <div class="cs4-main">
      <p class="cs4-lede">Narrative field. The cream must reach the sheet foot.</p>
    </div>
    <div class="cs4-rail">
      <p class="cs4-ident-name">Client Name</p>
    </div>
  </div>
  <div class="tp-chrome-bottom" aria-hidden="true">
    <span class="tp-chrome-wm">WORDMARK TEXT</span>
    <span class="tp-chrome-url">example.test</span>
    <span class="tp-chrome-folio">10</span>
  </div>
</section>
"""
    return get_env().get_template("base.html.jinja").render(
        html_attrs="",
        head_css=head,
        fragment_css=css,
        body=body,
    )


def _render(tmp_path: Path):
    from playwright.sync_api import sync_playwright
    import fitz

    html_path = tmp_path / "report.html"
    html_path.write_text(_html(), encoding="utf-8")
    pdf_path = tmp_path / "report.pdf"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        pg = browser.new_page()
        pg.goto(html_path.resolve().as_uri())
        pg.pdf(path=str(pdf_path), print_background=True, prefer_css_page_size=True)
        browser.close()
    doc = fitz.open(pdf_path)
    assert len(doc) == 1, f"expected 1 page, got {len(doc)}"
    pix = doc[0].get_pixmap(dpi=150)
    png = tmp_path / "p.png"
    pix.save(str(png))
    doc.close()
    return png


def _px(img, xmm: float, ymm_from_bottom: float):
    w, h = img.size
    mm = h / 297.0
    x = min(w - 1, max(0, int(xmm * mm)))
    y = min(h - 1, max(0, h - 1 - int(ymm_from_bottom * mm)))
    return img.getpixel((x, y))


def test_case_study_fields_reach_sheet_foot(tmp_path):
    """Cream (left) and navy (right) paint to within 1mm of the sheet bottom.
    A white strip at the trim is the 'cream is a box' / footer-cut defect."""
    from PIL import Image

    png = _render(tmp_path)
    img = Image.open(png).convert("RGB")
    left = _px(img, 30, 0.6)
    right = _px(img, 180, 0.6)
    assert left[0] < 250 or left[1] < 250, (
        f"left field at sheet foot is white {left} — cream does not reach trim"
    )
    assert right[0] < 80 and right[2] < 130, (
        f"right field at sheet foot is not navy {right} — rail does not reach trim"
    )


def test_case_study_seam_is_one_line(tmp_path):
    """Cream/navy boundary x at mid-page and near the foot agree within 1mm."""
    from PIL import Image

    png = _render(tmp_path)
    img = Image.open(png).convert("RGB")
    w, h = img.size
    mm = h / 297.0

    def first_navy_x(ymm: float) -> float:
        y = min(h - 1, int(ymm * mm))
        for x in range(int(100 * mm), int(160 * mm)):
            r, g, b = img.getpixel((x, y))
            if r < 80 and b > r and (r + g + b) / 3 < 130:
                return x / mm
        raise AssertionError(f"no navy seam at y={ymm}mm")

    mid = first_navy_x(80)
    foot = first_navy_x(280)
    assert abs(mid - foot) < 1.0, (
        f"seam drifts: y=80mm -> {mid:.1f}mm, y=280mm -> {foot:.1f}mm"
    )


def test_footer_wordmark_not_clipped(tmp_path):
    """Footer wordmark ink in the left field has >=2mm cap-height and does
    not sit in the last 1.5mm of the sheet (clipped by the trim)."""
    from PIL import Image

    png = _render(tmp_path)
    img = Image.open(png).convert("RGB")
    w, h = img.size
    mm = h / 297.0
    ink_ys = []
    for y in range(h - int(25 * mm), h):
        for x in range(int(18 * mm), int(90 * mm)):
            r, g, b = img.getpixel((x, y))
            if r < 140 and g < 140 and b < 140:
                ink_ys.append(y)
                break
    assert ink_ys, "no footer wordmark ink in the left footer band"
    span_mm = (max(ink_ys) - min(ink_ys)) / mm
    assert span_mm >= 2.0, f"wordmark cap-height only {span_mm:.2f}mm (clipped)"
    from_bottom = (h - 1 - max(ink_ys)) / mm
    assert from_bottom >= 1.5, (
        f"wordmark ink reaches {from_bottom:.2f}mm from trim (clipped)"
    )
