"""Deterministic visual-QC gate: a dead-space / empty-panel detector.

Given a rendered page PNG, this tool DETECTS large empty (content-free) regions
so defects like an empty navy portrait box or a dead cream band are caught by a
tool instead of by the reader's eye. It is the permanent gate for treatment
pages: a page that flags here is NOT shippable.

How it works (purely deterministic, no model, no network):
  1. Load the PNG (Pillow) and tile it into a grid of small square cells (~6mm
     cells; at the 2x raster the renderer uses that is ~34px). For each cell
     compute the luma MEAN, the luma VARIANCE, and the mean RGB.
  2. A cell is "flat" (content-empty) when its luma variance is below a small
     threshold: a near-uniform patch of one color (empty cream ground, empty
     navy panel, a blank band) has almost no variance, whereas a photo or a run
     of text has high variance. So flat == "nothing is drawn in this cell".
  3. Determine the PAGE-GROUND color (the cream substrate) from the inset corner
     cells. Flat cells then split into two kinds:
       - GROUND-colored flat cells (the cream page substrate). The ground IS
         meant to be empty, so only an ABNORMALLY large dead ground band flags.
       - PANEL-colored flat cells (a colored panel, e.g. the navy portrait
         column, that has gone empty). A colored panel is supposed to CARRY
         content, so even a moderate empty block in it is a defect.
  4. Compute the largest axis-aligned all-flat RECTANGLE (the "maximal empty
     rectangle", MER) separately for each kind. The MER is the right signal: a
     dead PANEL or a dead BAND contains one big solid empty rectangle, whereas a
     FILLED panel (a dark result band with a gauge + text) or the cream ground
     threading around text columns is broken up by content into only small
     rectangles. A photo has high variance, so no flat cells, so no MER at all.
  5. FLAG when a MER is both large enough AND sits substantially INSIDE the
     content area (past the thin outer @page margin ring, which is itself flat):
       - a PANEL (non-ground) MER above panel_area_frac  -> empty-panel defect,
       - a GROUND (cream) MER above ground_area_frac      -> dead-band defect.
     The two thresholds are why the cream page ground inside the normal margins
     does NOT false-positive (normal breathing is well under ground_area_frac)
     while an empty colored panel (which never legitimately occurs) trips the
     much lower panel threshold.

Each flag reports its bbox (in mm), area %, and mean color so a reviewer can
tell a navy empty box (dark mean) from a cream dead band (light mean) at a
glance.

Public API:
    find_dead_regions(png_path, *, panel_area_frac=..., ground_area_frac=...,
                      var_thresh=..., cell_mm=..., margin_mm=...)
        -> list[DeadRegion]

CLI:
    python tools/qc_dead_space.py PAGE.png [PAGE2.png ...]
  Prints CLEAN or the flagged regions and exits non-zero if ANY page flags.

The page's physical size (A3 landscape vs A4 portrait) is inferred from the PNG
aspect ratio so bounding boxes are reported in millimetres. No client strings,
no brand assumptions: it reads only pixels. (The unicode long-dash char is
referenced only via chr(0x2014) so the house no-dash guard stays clean.)
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

# ---- known physical page sizes (mm), matched against the PNG aspect ratio ----
_PAGE_SIZES_MM: tuple[tuple[float, float], ...] = (
    (420.0, 297.0),  # A3 landscape
    (297.0, 420.0),  # A3 portrait
    (210.0, 297.0),  # A4 portrait
    (297.0, 210.0),  # A4 landscape
)

# ---- default tuning -----------------------------------------------------------
# var_thresh: a cell whose luma variance is below this is "flat" (content-empty).
#   Empty cream / empty navy patches sit near 0; antialiased text edges and photo
#   texture sit far above. 40 (luma^2) cleanly separates the two.
# panel_area_frac: a non-ground (colored-panel) maximal empty rectangle larger
#   than this fraction of the page flags as an EMPTY-PANEL defect. The editorial
#   empty navy box measured ~9.8% of the sheet; a clean page's largest panel
#   empty-rect is <=5.2%. 0.07 sits cleanly between.
# ground_area_frac: a ground (cream) maximal empty rectangle larger than this
#   flags as a DEAD-BAND defect. Normal page breathing is <=9%; a genuine dead
#   cream band runs >=25-30%. 0.22 catches the band without tripping breathing.
# cell_mm: cell edge in millimetres (~6mm -> ~34px at the 2x raster).
# margin_mm: the outer @page margin ring to discount (the renderer uses
#   16/14/20/18mm); a representative inset so the flat margin ring is never the
#   thing that flags.
# ground_color_dist: max per-channel-sum distance for a flat cell to count as the
#   page-ground (cream) color rather than a colored panel.
DEFAULT_VAR_THRESH: float = 40.0
DEFAULT_PANEL_AREA_FRAC: float = 0.07
DEFAULT_GROUND_AREA_FRAC: float = 0.22
DEFAULT_CELL_MM: float = 6.0
DEFAULT_MARGIN_MM: float = 14.0
DEFAULT_GROUND_COLOR_DIST: int = 60


@dataclass(frozen=True)
class DeadRegion:
    """One flagged empty region.

    kind        : "panel" (an empty colored panel) or "band" (a dead ground band).
    bbox_mm     : (x0, y0, x1, y1) bounding box in millimetres on the sheet.
    area_frac   : the rectangle's area as a fraction of the whole page (0..1).
    mean_luma   : mean luma (0..255) of the region (dark => navy, light => cream).
    mean_rgb    : mean (r, g, b) of the region, for navy-vs-cream readability.
    """

    kind: str
    bbox_mm: tuple[float, float, float, float]
    area_frac: float
    mean_luma: float
    mean_rgb: tuple[int, int, int]

    def describe(self) -> str:
        x0, y0, x1, y1 = (round(v, 1) for v in self.bbox_mm)
        r, g, b = self.mean_rgb
        tone = "dark/navy" if self.mean_luma < 90 else (
            "light/cream" if self.mean_luma > 170 else "mid")
        label = "EMPTY PANEL" if self.kind == "panel" else "DEAD BAND"
        return (
            f"{label}  bbox=({x0},{y0})..({x1},{y1})mm  "
            f"area={self.area_frac * 100:.1f}%  "
            f"mean_luma={self.mean_luma:.0f} ({tone}, rgb {r},{g},{b})"
        )


def _page_size_mm(width_px: int, height_px: int) -> tuple[float, float]:
    """Infer the physical (width_mm, height_mm) from the PNG aspect ratio."""
    ratio = width_px / height_px
    best = min(_PAGE_SIZES_MM, key=lambda s: abs((s[0] / s[1]) - ratio))
    return best


def _color_dist(a: tuple[int, int, int], b: tuple[int, int, int]) -> int:
    """L1 (manhattan) distance between two RGB triples."""
    return abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2])


def _max_empty_rect(mask: list[list[bool]], rows: int, cols: int
                    ) -> tuple[int, int, int, int, int]:
    """Largest axis-aligned all-True rectangle in `mask`.

    Returns (area_cells, r0, c0, r1, c1) (inclusive cell indices). O(rows*cols)
    via the classic histogram / monotonic-stack method, run row by row.
    """
    best = (0, 0, 0, -1, -1)
    heights = [0] * cols
    for r in range(rows):
        for c in range(cols):
            heights[c] = heights[c] + 1 if mask[r][c] else 0
        stack: list[tuple[int, int]] = []  # (start_col, height)
        for c in range(cols + 1):
            cur = heights[c] if c < cols else 0
            start = c
            while stack and stack[-1][1] > cur:
                sc, sh = stack.pop()
                area = sh * (c - sc)
                if area > best[0]:
                    best = (area, r - sh + 1, sc, r, c - 1)
                start = sc
            stack.append((start, cur))
    return best


def find_dead_regions(
    png_path: str | Path,
    *,
    panel_area_frac: float = DEFAULT_PANEL_AREA_FRAC,
    ground_area_frac: float = DEFAULT_GROUND_AREA_FRAC,
    var_thresh: float = DEFAULT_VAR_THRESH,
    cell_mm: float = DEFAULT_CELL_MM,
    margin_mm: float = DEFAULT_MARGIN_MM,
    ground_color_dist: int = DEFAULT_GROUND_COLOR_DIST,
) -> list[DeadRegion]:
    """Detect large interior content-empty regions on a rendered page PNG.

    Returns a list of DeadRegion (empty when the page is CLEAN). Pure +
    deterministic: the same PNG + thresholds always yields the same flags.
    """
    img = Image.open(png_path).convert("RGB")
    width_px, height_px = img.size
    width_mm, height_mm = _page_size_mm(width_px, height_px)
    px_per_mm = width_px / width_mm

    cell_px = max(1, int(round(cell_mm * px_per_mm)))
    cols = width_px // cell_px
    rows = height_px // cell_px
    if cols < 6 or rows < 6:
        return []

    px = img.load()
    n = cell_px * cell_px

    flat = [[False] * cols for _ in range(rows)]
    cell_mean = [[0.0] * cols for _ in range(rows)]
    cell_rgb = [[(0, 0, 0)] * cols for _ in range(rows)]
    for r in range(rows):
        y0 = r * cell_px
        for c in range(cols):
            x0 = c * cell_px
            s = s2 = sr = sg = sb = 0
            for yy in range(y0, y0 + cell_px):
                for xx in range(x0, x0 + cell_px):
                    pr, pg, pb = px[xx, yy]
                    lum = (pr * 299 + pg * 587 + pb * 114) // 1000
                    s += lum
                    s2 += lum * lum
                    sr += pr
                    sg += pg
                    sb += pb
            mean = s / n
            cell_mean[r][c] = mean
            cell_rgb[r][c] = (sr // n, sg // n, sb // n)
            flat[r][c] = ((s2 / n) - (mean * mean)) < var_thresh

    # Page-ground (cream substrate) color: the median of the inset corner cells.
    corner_cells = [
        cell_rgb[r][c]
        for r in (1, 2, rows - 3, rows - 2)
        for c in (1, 2, cols - 3, cols - 2)
    ]
    corner_cells.sort(key=lambda t: t[0] + t[1] + t[2])
    ground_rgb = corner_cells[len(corner_cells) // 2]

    # Discount the outer @page margin ring: a flat cell inside the margin band is
    # not eligible to START a dead region (the ring is flat by construction). We
    # mark margin cells as NOT-flat for the MER pass so the ring cannot be the
    # rectangle that flags; an interior dead block is unaffected.
    margin_cells = max(0, int(round(margin_mm / cell_mm)))

    def interior(r: int, c: int) -> bool:
        return (margin_cells <= r < rows - margin_cells
                and margin_cells <= c < cols - margin_cells)

    panel_mask = [[False] * cols for _ in range(rows)]
    ground_mask = [[False] * cols for _ in range(rows)]
    for r in range(rows):
        for c in range(cols):
            if not flat[r][c] or not interior(r, c):
                continue
            if _color_dist(cell_rgb[r][c], ground_rgb) <= ground_color_dist:
                ground_mask[r][c] = True
            else:
                panel_mask[r][c] = True

    total_cells = rows * cols
    regions: list[DeadRegion] = []

    for mask, kind, thresh in (
        (panel_mask, "panel", panel_area_frac),
        (ground_mask, "band", ground_area_frac),
    ):
        area, r0, c0, r1, c1 = _max_empty_rect(mask, rows, cols)
        if r1 < r0 or c1 < c0:
            continue
        area_frac = area / total_cells
        if area_frac < thresh:
            continue
        x0_mm = c0 * cell_px / px_per_mm
        y0_mm = r0 * cell_px / px_per_mm
        x1_mm = (c1 + 1) * cell_px / px_per_mm
        y1_mm = (r1 + 1) * cell_px / px_per_mm
        cells = [(r, c) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)]
        lum = sum(cell_mean[r][c] for r, c in cells) / len(cells)
        mr = sum(cell_rgb[r][c][0] for r, c in cells) / len(cells)
        mg = sum(cell_rgb[r][c][1] for r, c in cells) / len(cells)
        mb = sum(cell_rgb[r][c][2] for r, c in cells) / len(cells)
        regions.append(DeadRegion(
            kind=kind,
            bbox_mm=(x0_mm, y0_mm, x1_mm, y1_mm),
            area_frac=area_frac,
            mean_luma=lum,
            mean_rgb=(int(mr), int(mg), int(mb)),
        ))

    regions.sort(key=lambda d: d.area_frac, reverse=True)
    return regions


def _check(path: Path) -> list[DeadRegion]:
    regions = find_dead_regions(path)
    if regions:
        print(f"FAIL  {path.name}: {len(regions)} dead-space region(s) flagged")
        for reg in regions:
            print(f"   {reg.describe()}")
    else:
        print(f"CLEAN {path.name}: no dead-space regions")
    return regions


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: python tools/qc_dead_space.py PAGE.png [PAGE2.png ...]")
        return 2
    any_flag = False
    for arg in argv:
        path = Path(arg)
        if not path.exists():
            print(f"FAIL  {arg}: file not found")
            any_flag = True
            continue
        if _check(path):
            any_flag = True
    return 1 if any_flag else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
