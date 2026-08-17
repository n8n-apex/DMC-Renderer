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


@pytest.mark.xfail(
    reason=(
        "Phase A theme-lock (2026-06-05): canon type changed every page AND "
        "overflows the deck to 25 physical pages (5 pages spill) until Phase B "
        "per-pattern reflow restores 20. Re-baseline (UPDATE_BASELINES=1) ONLY "
        "after Phase B reflow + human sign-off vs Richard — never freeze the "
        "overflow. Plan: docs/superpowers/plans/2026-06-05-phase-A-renderer-theme-lock.md"
    ),
    strict=False,
)
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
