"""Task 0.2 frozen spike: PROVE mixed A3-landscape / A4-portrait page sizes
survive the REAL production Chromium output path (page.pdf with
prefer_css_page_size=True) FOLLOWED BY the Ghostscript flatten pass.

An earlier standalone spike proved Chromium ALONE preserves mixed page sizes,
but it did NOT include the gs flatten, and gs is known to sometimes normalize
page geometry. This test exercises the EXACT production sequence
(render_package's chromium branch: Playwright page.pdf -> gs pdfwrite flatten
-> fitz rasterize) on a hand-built 3-section document and asserts, on the
GS-FLATTENED output:

  (a) page sizes: A3-landscape, A4-portrait, A3-landscape (within +-3pt).
  (b) page COUNT == 3: no logical page silently spilled onto a blank sheet.
      This is the critical anti-regression assertion the audit demanded.
  (c) raster dims: the A3 PNGs open wider than tall, the A4 PNG taller than
      wide, and A3 width > A4 width.
  (d) chrome present: the persistent header band (top margin strip) and the
      counter(page) folio (bottom-right) actually render on the page.

The section markup is hand-built (the section-class STAMPING is a later task),
but the head CSS is the REAL production `shared_head_css(..., engine="chromium")`
and the document is assembled via the REAL `base.html.jinja`, exactly mirroring
how `render_package` builds `html_doc`. So this exercises the production @page
rules + chrome that Task 0.2 added.

Chrome-present check is PIXEL-BASED (option per the task brief): the gs-flattened
PDF carries NO extractable text layer (fitz get_text() returns ''), so we
rasterize and count non-background (darker-than-the-cream-ground) pixels in the
top margin band and the bottom-right folio corner. The cream ground is ~#F6F3ED
(luminance ~240); all chrome ink (--color-primary #4A7C7E ~110, --color-ink
#2E3E50 ~60, --color-muted #5E5E58 ~94) sits far below the threshold, so the
check has wide margin.

Self-contained and rerunnable: everything renders into a fresh tempdir.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
import sys

sys.path.insert(0, str(ROOT))

from package_loader import load_package  # noqa: E402
from assembler import shared_head_css, FONT_DIR  # noqa: E402
from templating import get_env  # noqa: E402

# Points-per-mm (PDF user space): 1mm = 72/25.4 pt = 2.8346pt.
PT_PER_MM = 72.0 / 25.4
A3_LAND_W = 420.0 * PT_PER_MM   # ~1190.55 pt
A3_LAND_H = 297.0 * PT_PER_MM   # ~ 841.89 pt
A4_PORT_W = 210.0 * PT_PER_MM   # ~ 595.28 pt
A4_PORT_H = 297.0 * PT_PER_MM   # ~ 841.89 pt
TOL = 3.0                        # +-3pt tolerance


def _lorem(n: int) -> str:
    """A few sentences of filler. Short on purpose: enough to clearly render,
    not enough to overflow the (tall) content box."""
    s = (
        "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do "
        "eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim "
        "ad minim veniam, quis nostrud exercitation ullamco laboris."
    )
    return " ".join([s] * n)


def _section(format_class: str, idx: int) -> str:
    """One hand-built logical page. Heading + a few short paragraphs.
    `format_class` is 'format-a3' or 'format-a4'."""
    paras = "".join(f"<p>{_lorem(2)}</p>" for _ in range(3))
    return (
        f'<section class="page {format_class}">'
        f"<h1>Treatment page-size probe {idx}</h1>"
        f"{paras}"
        "</section>"
    )


def _build_html() -> str:
    """Assemble the 3-section document with the REAL production head CSS and the
    REAL base.html.jinja template, mirroring render_package's chromium path."""
    pkg = load_package(ROOT / "fixtures" / "apex")
    head = shared_head_css(pkg.brand, FONT_DIR, pkg.axes, engine="chromium")
    body = (
        _section("format-a3", 1)
        + _section("format-a4", 2)
        + _section("format-a3", 3)
    )
    return get_env().get_template("base.html.jinja").render(
        html_attrs="",        # bare html; the format classes drive page sizing
        head_css=head,
        fragment_css="",
        body=body,
    )


def _render_pipeline(tmp_path: Path):
    """Run the exact production chromium pipeline: write html -> Playwright
    page.pdf(prefer_css_page_size=True) -> gs pdfwrite flatten -> fitz raster.

    Returns (flat_pdf_path, raw_pdf_path, [png_path,...])."""
    html_doc = _build_html()
    html_path = tmp_path / "report.html"
    html_path.write_text(html_doc, encoding="utf-8")

    raw_pdf = tmp_path / "report_print.pdf"
    flat_pdf = tmp_path / "report.pdf"

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        pg = browser.new_page()
        pg.goto(html_path.resolve().as_uri())
        pg.pdf(path=str(raw_pdf), print_background=True,
               prefer_css_page_size=True)
        browser.close()

    gs = shutil.which("gs")
    assert gs, "ghostscript (gs) not found: required to exercise the flatten pass"
    subprocess.run(
        [gs, "-dBATCH", "-dNOPAUSE", "-sDEVICE=pdfwrite",
         "-dCompatibilityLevel=1.3", "-r300", "-dPDFSETTINGS=/printer",
         "-dColorConversionStrategy=/LeaveColorUnchanged",
         "-o", str(flat_pdf), str(raw_pdf)],
        check=True, capture_output=True,
    )

    import fitz  # PyMuPDF
    png_paths: list[Path] = []
    doc = fitz.open(flat_pdf)
    for i, page in enumerate(doc):
        pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
        png = tmp_path / f"report-p{i + 1}.png"
        pix.save(str(png))
        png_paths.append(png)
    doc.close()
    return flat_pdf, raw_pdf, png_paths


def _approx(a: float, b: float, tol: float = TOL) -> bool:
    return abs(a - b) <= tol


@pytest.fixture(scope="module")
def rendered(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("ts02_pagesize")
    flat_pdf, raw_pdf, pngs = _render_pipeline(tmp)
    return {"flat": flat_pdf, "raw": raw_pdf, "pngs": pngs, "dir": tmp}


# ---------------------------------------------------------------------------
# (b) page COUNT == 3, the critical anti-regression assertion.
# ---------------------------------------------------------------------------
def test_page_count_is_three_no_spill(rendered):
    import fitz
    doc = fitz.open(rendered["flat"])
    n = doc.page_count
    doc.close()
    assert n == 3, (
        f"expected exactly 3 physical pages (no logical page spilled onto a "
        f"blank second sheet); got {n}"
    )


# ---------------------------------------------------------------------------
# (a) page SIZES survive the gs flatten: A3-land, A4-port, A3-land.
# ---------------------------------------------------------------------------
def test_mixed_page_sizes_survive_flatten(rendered):
    import fitz
    doc = fitz.open(rendered["flat"])
    rects = [doc[i].rect for i in range(doc.page_count)]
    doc.close()

    measured = [(round(r.width, 2), round(r.height, 2)) for r in rects]
    print("\nMEASURED flattened page rects (pt):")
    for i, (w, h) in enumerate(measured):
        print(f"  page {i}: width={w}  height={h}")
    print(f"EXPECTED A3-landscape: {A3_LAND_W:.2f} x {A3_LAND_H:.2f}")
    print(f"EXPECTED A4-portrait:  {A4_PORT_W:.2f} x {A4_PORT_H:.2f}")

    assert len(rects) == 3, f"need 3 pages to check sizes; got {len(rects)}"

    # page 0: A3 landscape
    assert _approx(rects[0].width, A3_LAND_W) and _approx(rects[0].height, A3_LAND_H), (
        f"page 0 expected A3-landscape ~{A3_LAND_W:.1f}x{A3_LAND_H:.1f}pt; "
        f"got {rects[0].width:.1f}x{rects[0].height:.1f}pt"
    )
    # page 1: A4 portrait
    assert _approx(rects[1].width, A4_PORT_W) and _approx(rects[1].height, A4_PORT_H), (
        f"page 1 expected A4-portrait ~{A4_PORT_W:.1f}x{A4_PORT_H:.1f}pt; "
        f"got {rects[1].width:.1f}x{rects[1].height:.1f}pt"
    )
    # page 2: A3 landscape
    assert _approx(rects[2].width, A3_LAND_W) and _approx(rects[2].height, A3_LAND_H), (
        f"page 2 expected A3-landscape ~{A3_LAND_W:.1f}x{A3_LAND_H:.1f}pt; "
        f"got {rects[2].width:.1f}x{rects[2].height:.1f}pt"
    )


# ---------------------------------------------------------------------------
# (c) raster dims differ correctly (A3 wide, A4 tall, A3 width > A4 width).
# ---------------------------------------------------------------------------
def test_raster_dimensions(rendered):
    from PIL import Image
    pngs = rendered["pngs"]
    assert len(pngs) == 3, f"need 3 PNGs; got {len(pngs)}"
    sizes = []
    for p in pngs:
        with Image.open(p) as im:
            sizes.append(im.size)  # (w, h)
    print("\nRASTER PNG sizes (px):", sizes)
    (a3a_w, a3a_h), (a4_w, a4_h), (a3b_w, a3b_h) = sizes

    assert a3a_w > a3a_h, f"A3 page 0 should be wider than tall; got {a3a_w}x{a3a_h}"
    assert a3b_w > a3b_h, f"A3 page 2 should be wider than tall; got {a3b_w}x{a3b_h}"
    assert a4_h > a4_w, f"A4 page 1 should be taller than wide; got {a4_w}x{a4_h}"
    assert a3a_w > a4_w, f"A3 width should exceed A4 width; {a3a_w} vs {a4_w}"
    assert a3b_w > a4_w, f"A3 width should exceed A4 width; {a3b_w} vs {a4_w}"


# ---------------------------------------------------------------------------
# (d) chrome present (PIXEL-BASED): header band in the top margin strip and
#     the counter(page) folio in the bottom-right corner.
# ---------------------------------------------------------------------------
def _luma(px) -> float:
    """Rec.601 luma of an (R,G,B[,A]) tuple."""
    r, g, b = px[0], px[1], px[2]
    return 0.299 * r + 0.587 * g + 0.114 * b


def _count_dark(im, box, thresh: float) -> int:
    """Count pixels in `box` (left, top, right, bottom) darker than `thresh`."""
    crop = im.crop(box).convert("RGB")
    return sum(1 for px in crop.getdata() if _luma(px) < thresh)


def _chrome_present(png_path: Path) -> tuple[int, int, float, float]:
    """Returns (top_band_dark_count, folio_corner_dark_count, bg_luma, thresh).

    The raster is 2x: 1mm = 2 * 2.8346 = 5.669 px. The top margin is 16mm; the
    header band sits near its lower part (~6-14mm). The folio (counter(page))
    sits in the bottom-right within the 20mm bottom margin / 14mm right margin.
    """
    from PIL import Image
    with Image.open(png_path) as im:
        im = im.convert("RGB")
        w, h = im.size
        px_per_mm = 2.0 * PT_PER_MM  # 2x raster, pt-per-mm

        # Sample the page background luma from a quiet zone (center of the page,
        # which is content area but between paragraphs there is plenty of cream;
        # use a small patch at ~50% width, ~50% height. Body copy is dark but
        # sparse, so the MODAL value there is the cream ground. To be robust we
        # take the brightest-cluster proxy: the max luma in a center strip, which
        # is the cream ground itself.
        cx0, cy0 = int(w * 0.45), int(h * 0.46)
        cx1, cy1 = int(w * 0.55), int(h * 0.50)
        center = im.crop((cx0, cy0, cx1, cy1)).convert("RGB")
        lumas = [_luma(p) for p in center.getdata()]
        bg_luma = max(lumas) if lumas else 255.0
        # threshold: clearly-darker-than-ground. Chrome ink is <=110; ground
        # ~240. A threshold 60pt below ground (and never above 200) is generous
        # for chrome ink yet excludes the cream ground + its grain whisper.
        thresh = min(bg_luma - 60.0, 200.0)

        # Top margin band: a horizontal strip from ~5mm to ~15mm down, spanning
        # the inner content width (skip the L/R margins so the band ink, not
        # stray edge artifacts, is what we count).
        tb = (
            int(18.0 * px_per_mm),                 # left ~ left margin
            int(5.0 * px_per_mm),                  # top ~5mm
            int(w - 14.0 * px_per_mm),             # right ~ right margin
            int(15.0 * px_per_mm),                 # bottom ~15mm
        )
        top_dark = _count_dark(im, tb, thresh)

        # Bottom-right folio corner: the counter(page) sits ~4mm up from the
        # bottom inside the right margin. Sample a box in the bottom-right.
        fb = (
            int(w - 30.0 * px_per_mm),             # 30mm wide
            int(h - 18.0 * px_per_mm),             # 18mm tall
            w,
            h,
        )
        folio_dark = _count_dark(im, fb, thresh)
    return top_dark, folio_dark, bg_luma, thresh


def test_chrome_present_on_a3_and_a4(rendered):
    pngs = rendered["pngs"]
    # Check one A3 page (page 0) and the A4 page (page 1).
    for label, idx in (("A3 page 0", 0), ("A4 page 1", 1)):
        top_dark, folio_dark, bg_luma, thresh = _chrome_present(pngs[idx])
        print(
            f"\n{label}: bg_luma={bg_luma:.1f} thresh={thresh:.1f} "
            f"top_band_dark={top_dark} folio_corner_dark={folio_dark}"
        )
        # Require a small-but-real count of chrome ink in each region. The
        # wordmark/booking text spans many glyphs (hundreds of dark px at 2x);
        # the folio is a single small numeral (tens of px). Use conservative
        # floors so the check is robust but still proves the chrome painted.
        assert top_dark >= 50, (
            f"{label}: expected the header band to paint chrome ink in the top "
            f"margin strip; found only {top_dark} dark px (thresh {thresh:.0f})"
        )
        assert folio_dark >= 8, (
            f"{label}: expected the counter(page) folio to paint in the "
            f"bottom-right; found only {folio_dark} dark px (thresh {thresh:.0f})"
        )
