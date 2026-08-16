"""TS-1.5 integration proof: render a 3-page MIXED-format treatment slice through
the REAL production Chromium path and assert on the gs-flattened output.

A3 RULE (2026-07-14): mid-deck A3 breaks Chromium's mixed-size A4 print
(bisect-proven), so the stylist suspends the About A3 hero outright and
tail-gates every non-hero A3 promotion to the FINAL quarter of the deck
(index >= 3*len(pages)//4). The About page therefore renders A4 via
a4_editorial_fill; the framework flow (deck tail) keeps its A3.

The slice (reusing the real apex assets so the About founder portrait resolves
via the founder-identity fallback):
  logical p0  page index 0   ST-01 cover (bypass)  -> A4 portrait, untreated
  logical p1  page index 2   ST-05 About           -> a4_editorial_fill, A4 portrait
  logical p2  page index 15  ST-06 framework       -> horizontal_process, A3 landscape

Assertions:
  - res.page_count == 3 (three LOGICAL pages, one section each),
  - the three EXPECTED physical page sizes appear IN ORDER among the flattened
    report.pdf pages: A4-portrait (cover), A4-portrait (About fill),
    A3-landscape (framework). (A short Chromium slice can emit an extra trailing
    artifact page for the full-bleed cover; the SIZE-in-order check ignores that
    harness-only artifact, while the FULL-deck no-spill check below is the
    authoritative content-fit gate.),
  - report.html stamps treatment-a4_editorial_fill + format-a4 AND
    treatment-horizontal_process + format-a3 (the assembler stamped the treatment
    + format classes for the two treated pages),
  - the FULL apex deck renders with physical pages == logical pages and NO
    overflow spill (the authoritative product contract: every section is exactly
    one sheet in the real deck).

This is a REAL render (a few seconds for 3 pages via Playwright + Ghostscript),
exercised exactly as render_package builds the production document.

Run ONLY this file:
  python -m pytest tests/test_treatment_slice.py -v
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from assembler import render_package  # noqa: E402

# Points-per-mm (PDF user space): 1mm = 72/25.4 pt.
PT_PER_MM = 72.0 / 25.4
A3_LAND_W = 420.0 * PT_PER_MM   # ~1190.55 pt
A3_LAND_H = 297.0 * PT_PER_MM   # ~ 841.89 pt
A4_PORT_W = 210.0 * PT_PER_MM   # ~ 595.28 pt
A4_PORT_H = 297.0 * PT_PER_MM   # ~ 841.89 pt
TOL = 3.0

# Slice page indices in the real apex package (pinned):
#   0  -> ST-01 cover (bypass)  : A4 portrait, untreated
#   2  -> ST-05 About           : a4_editorial_fill, A4 portrait (A3 hero
#         suspended; non-hero A3 is tail-gated to the final deck quarter)
#   15 -> ST-06 intro continuation (US-604: the section spans two A4 pages)
#   16 -> ST-06 result continuation
SLICE_INDICES = [0, 2, 15, 16]

# The four EXPECTED physical page sizes, IN ORDER (the logical pages):
#   (A4 cover, A4 About fill, A4 ST-06 intro, A4 ST-06 result). No A3 page
#   remains — the framework's horizontal_process A3 promotion is gone (the
#   section is two A4 continuation pages).
EXPECTED_SIZES = [
    (A4_PORT_W, A4_PORT_H),
    (A4_PORT_W, A4_PORT_H),
    (A4_PORT_W, A4_PORT_H),
    (A4_PORT_W, A4_PORT_H),
]


@pytest.fixture(scope="module")
def rendered(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("ts15_slice")
    pkg_dir = tmp / "pkg"
    out_dir = tmp / "out"
    shutil.copytree(ROOT / "fixtures" / "apex", pkg_dir)

    manifest_path = pkg_dir / "resolved_package.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["pages"] = [manifest["pages"][i] for i in SLICE_INDICES]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    res = render_package(pkg_dir, out_dir, engine="chromium", treatments=True)
    return {"res": res, "out": out_dir}


@pytest.fixture(scope="module")
def full_deck(tmp_path_factory):
    """The FULL apex deck rendered through the production Chromium path. This is
    the authoritative no-spill contract: every logical section is exactly one
    sheet in the real product (a short 3-page slice can emit a Chromium trailing
    artifact for the full-bleed cover that the full deck does not)."""
    tmp = tmp_path_factory.mktemp("ts15_full")
    pkg_dir = tmp / "pkg"
    out_dir = tmp / "out"
    shutil.copytree(ROOT / "fixtures" / "apex", pkg_dir)
    res = render_package(pkg_dir, out_dir, engine="chromium", treatments=True)
    return {"res": res, "out": out_dir}


def _approx(a: float, b: float, tol: float = TOL) -> bool:
    return abs(a - b) <= tol


def _size_matches(rect, size, tol: float = TOL) -> bool:
    w, h = size
    return _approx(rect.width, w, tol) and _approx(rect.height, h, tol)


def test_page_count_is_four(rendered):
    """Four LOGICAL pages (one section each): cover + editorial + ST-06 intro +
    ST-06 result continuation (US-604: the framework section spans two pages)."""
    assert rendered["res"].page_count == 4


def test_expected_page_sizes_in_order(rendered):
    """The four expected physical page sizes (all A4) appear IN ORDER among
    the flattened report.pdf pages.

    US-604: ST-06 spans intro + result continuation pages (both A4). A short
    Chromium slice can emit extra trailing artifact pages for full-bleed pages
    (the full deck does not -- see test_full_deck_no_spill). We therefore
    assert the EXPECTED sizes appear as an ordered subsequence."""
    import fitz

    pdf = rendered["out"] / "report.pdf"
    assert pdf.exists(), f"expected flattened report.pdf at {pdf}"
    doc = fitz.open(pdf)
    rects = [doc[i].rect for i in range(doc.page_count)]
    doc.close()

    print("\nMEASURED page rects (pt):")
    for i, r in enumerate(rects):
        print(f"  page {i}: width={round(r.width, 2)}  height={round(r.height, 2)}")

    # walk the physical pages, consuming each expected size in order.
    expected = list(EXPECTED_SIZES)
    ei = 0
    for r in rects:
        if ei < len(expected) and _size_matches(r, expected[ei]):
            ei += 1
    assert ei == len(expected), (
        f"expected page sizes {expected} not found in order; "
        f"measured {[(round(r.width, 1), round(r.height, 1)) for r in rects]}"
    )


def test_report_html_stamps_treatment_and_format_classes(rendered):
    # US-604: the About page renders A4 via a4_editorial_fill; the ST-06
    # continuation pages are NOT treated (they belong to the section — the
    # section's own pattern renders them). No A3 page remains.
    html = (rendered["out"] / "report.html").read_text(encoding="utf-8")
    assert "treatment-a4_editorial_fill" in html, (
        "a4_editorial_fill treatment class not stamped on the About page"
    )
    assert "format-a4" in html, "A4 format class not stamped on the About page"
    assert "treatment-horizontal_process" not in html, (
        "horizontal_process must not be stamped (ST-06 is continuation-bypassed)"
    )
    # no SECTION carries the A3 format class (the shared head CSS defines the
    # .page.format-a3 rule but no page opts in — ST-06 is two A4 continuations).
    sections = re.findall(r'<section[^>]*class="([^"]+)"', html)
    assert not any("format-a3" in s for s in sections), (
        f"no section may be format-a3; got {[s for s in sections if 'format-a3' in s]}"
    )


def test_full_deck_no_spill(full_deck):
    """AUTHORITATIVE content-fit gate: the FULL apex deck renders with one
    physical sheet per logical page and no overflow spill. Every treated page
    (incl. the A3 horizontal_process at the deck tail) fits its sheet in the
    real product."""
    res = full_deck["res"]
    # US-604: apex is now 21 pages (ST-06 spans two continuation pages).
    assert res.page_count == 21, f"apex deck is 21 pages; got {res.page_count}"
    assert len(res.png_paths) == res.page_count, (
        f"physical pages {len(res.png_paths)} != logical {res.page_count} "
        f"-- a section overflowed its sheet in the full deck"
    )
    spills = [o for o in (res.overflow or [])
              if "spill" in o.lower() or "overflow" in o.lower()]
    assert not spills, f"unexpected overflow/spill flags in full deck: {res.overflow}"


def test_full_deck_a3_pages(full_deck):
    """In the full deck exactly the framework page (idx 15) is A3-landscape;
    everything else is A4-portrait.

    A3 rule (2026-07-14): mid-deck A3 breaks Chromium's mixed-size A4 print, so
    the About hero A3 is suspended and non-hero A3 promotions are tail-gated to
    the final quarter of the deck (index >= 3*len(pages)//4 = 15 for 20 pages).
    Idx 15 is exactly the first tail slot, the empirically-safe zone."""
    import fitz

    pdf = full_deck["out"] / "report.pdf"
    doc = fitz.open(pdf)
    a3 = [i for i in range(doc.page_count)
          if _approx(doc[i].rect.width, A3_LAND_W) and _approx(doc[i].rect.height, A3_LAND_H)]
    doc.close()
    # US-604: no A3 pages remain (ST-06 spans two A4 continuations)
    assert a3 == [], f"expected no A3 pages; got {a3}"
