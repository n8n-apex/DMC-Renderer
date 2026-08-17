"""Where the subject of an image actually is.

A slot is rarely the shape of the photograph that fills it, so something has
to decide what gets cut. `object-fit: cover` alone centres the crop, which
is a guess: it keeps the middle whether or not the subject is there. On a
landscape founder shot in a portrait rail, that is how a face ends up
half out of frame.

This measures instead. Edge density is a good cheap proxy for "where the
detail is": a face, a figure, a product carry high-frequency structure,
while sky, wall and studio backdrop do not. The busiest band of the image
is where the subject is, and the crop is anchored there.

It is deliberately NOT face detection. No model, no network, deterministic
across runs, and it degrades honestly: a photograph with no dominant
structure returns dead centre, which is exactly what centring is for.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

try:
    from PIL import Image, ImageFilter, ImageStat
except ImportError:  # pragma: no cover - Pillow ships with the renderer
    Image = None  # type: ignore[assignment]


# Twelve bands is fine enough to find a subject and coarse enough that noise
# does not move the anchor between runs.
_BANDS = 12
# Below this spread the image has no dominant subject and centring is right.
_MIN_CONTRAST = 1.6


@lru_cache(maxsize=256)
def focal_point(image_path: str) -> tuple[float, float]:
    """The subject's centre as (x, y) percentages, or (50, 50).

    Cached because a face's image is measured once per build and the same
    asset can appear on several faces.
    """
    if Image is None:
        return (50.0, 50.0)
    try:
        with Image.open(image_path) as handle:
            grey = handle.convert("L")
            # Work small: the anchor only needs percentages, and a full-size
            # edge pass on a 5000px source is wasted work.
            grey.thumbnail((480, 480))
            edges = grey.filter(ImageFilter.FIND_EDGES)
            # FIND_EDGES brightens the outermost pixel ring, so a perfectly
            # flat image reads as having structure at its borders and the
            # anchor drifts toward the frame. Trim the artifact before
            # measuring anything.
            inset = 2
            edges = edges.crop(
                (inset, inset, max(inset + 1, edges.width - inset),
                 max(inset + 1, edges.height - inset))
            )
            width, height = edges.size
    except Exception:
        return (50.0, 50.0)

    return (
        _axis_centre(edges, width, height, horizontal=True),
        _axis_centre(edges, width, height, horizontal=False),
    )


def _axis_centre(edges, width: int, height: int, *, horizontal: bool) -> float:
    """The detail-weighted centre along one axis, as a percentage."""
    scores: list[float] = []
    for index in range(_BANDS):
        if horizontal:
            box = (
                int(width * index / _BANDS), 0,
                max(1, int(width * (index + 1) / _BANDS)), height,
            )
        else:
            box = (
                0, int(height * index / _BANDS),
                width, max(1, int(height * (index + 1) / _BANDS)),
            )
        scores.append(ImageStat.Stat(edges.crop(box)).mean[0])

    span = max(scores) - min(scores)
    if span < _MIN_CONTRAST:
        # Flat detail across the axis: nothing is the subject, so centre.
        return 50.0

    # Weight by how far each band stands above the quietest one, so the
    # background does not drag the anchor toward the middle.
    floor = min(scores)
    weights = [score - floor for score in scores]
    total = sum(weights)
    if total <= 0:
        return 50.0
    centre = sum(
        weight * ((index + 0.5) / _BANDS) for index, weight in enumerate(weights)
    ) / total
    # Keep the anchor off the very edge; a crop pinned at 0% or 100% clips
    # the subject against the frame.
    return round(min(85.0, max(15.0, centre * 100.0)), 1)


def object_position(image_path: str | Path) -> str:
    """The CSS `object-position` value for this image."""
    x, y = focal_point(str(image_path))
    return f"{x}% {y}%"
