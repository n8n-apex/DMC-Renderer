"""Permanent visual-QC gate for treatment pages (dead-space / empty-panel).

Renders the real 3-page mixed-format treatment slice through the production
Chromium path (the same render_package call the dev helper + test_treatment_slice
use) and asserts that tools/qc_dead_space.find_dead_regions returns NOTHING for
the TREATED A3 page:
  - the horizontal_process framework page (no dead band).

A3 rule (2026-07-14): mid-deck A3 breaks Chromium's mixed-size A4 print, so the
About hero A3 is suspended and non-hero A3 promotions are tail-gated to the
final quarter of the deck (index >= 3*len(pages)//4). The About page renders A4
via a4_editorial_fill and is out of this gate's A3 scope; the framework flow at
the deck tail is the one A3 page.

The cover + cover-spill pages are OUT OF SCOPE (the short Chromium slice emits a
trailing artifact for the full-bleed cover; the full deck is clean). We identify
the treated A3 page by its A3-landscape dimensions, which is robust against
that harness-only cover-spill page.

This is the gate that would have caught the empty-navy-box regression before it
reached a reviewer: with the buggy flex-grow credential wall (which collapsed to
zero height under Chromium's paged-media engine) the editorial page's navy column
held a ~10% empty navy block, which find_dead_regions flags as an EMPTY PANEL.

Run ONLY this file:
  python -m pytest tests/test_treatment_qc.py -v
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from assembler import render_package  # noqa: E402
from tools.qc_dead_space import find_dead_regions  # noqa: E402

# Slice page indices in the real apex package (pinned), mirroring
# test_treatment_slice + tools/_ts15_slice_render:
#   0  -> ST-01 cover (bypass)  : A4 portrait, untreated (out of scope)
#   2  -> ST-05 About           : a4_editorial_fill, A4 portrait (A3 suspended,
#         out of this gate's A3 scope)
#   15 -> ST-06 framework       : horizontal_process, A3 landscape (TREATED, in scope)
SLICE_INDICES = [0, 2, 15]

# An A3-landscape page is wider than tall; A4-portrait is taller than wide. The
# treated pages are the A3-landscape ones; the cover + cover-spill are A4-portrait.
def _is_a3_landscape(png_path: Path) -> bool:
    with Image.open(png_path) as im:
        w, h = im.size
    return (w / h) > 1.2  # ~1.41 for A3 landscape, ~0.71 for A4 portrait


@pytest.fixture(scope="module")
def slice_pngs(tmp_path_factory):
    """Render the slice FRESH through the production Chromium path and return the
    written PNG paths (report-p*.png)."""
    tmp = tmp_path_factory.mktemp("ts15_qc")
    pkg_dir = tmp / "pkg"
    out_dir = tmp / "out"
    shutil.copytree(ROOT / "fixtures" / "apex", pkg_dir)

    manifest_path = pkg_dir / "resolved_package.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["pages"] = [manifest["pages"][i] for i in SLICE_INDICES]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    render_package(pkg_dir, out_dir, engine="chromium", treatments=True)
    pngs = sorted(out_dir.glob("report-p*.png"))
    assert pngs, "slice render produced no PNGs"
    return pngs


def test_slice_pages_no_dead_space(slice_pngs):
    """The TREATED A3 page (the tail framework flow) carries NO dead-space /
    empty-panel regions. The cover + cover-spill + About A4 pages are out of
    scope (A3 rule 2026-07-14: the About hero A3 is suspended and non-hero A3
    promotions are tail-gated to the final quarter of the deck)."""
    treated = [p for p in slice_pngs if not _is_a3_landscape(p)]
    assert len(treated) >= 3, (
        f"expected the About + ST-06 continuation pages; found {len(treated)}"
    )

    failures: list[str] = []
    for png in treated:
        regions = find_dead_regions(png)
        if regions:
            detail = "; ".join(r.describe() for r in regions)
            failures.append(f"{png.name}: {detail}")

    assert not failures, (
        "dead-space / empty-panel region(s) flagged on treated page(s):\n  "
        + "\n  ".join(failures)
    )
