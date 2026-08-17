"""Device-mockup compositing (DNA §C2 / PRD §9.1).

Paste a client's real creative (ad / dashboard / book cover, sourced from
Drive) INTO a transparent device-frame PNG's screen hole, so it reads as
"displayed on the device". Pure Pillow, deterministic, offline. The frame
PNGs are a small reusable, brand-agnostic asset library (authored
separately). Axis-aligned screen placement; perspective warp + drop shadow
are deferred refinements. Standalone — wired onto the case-study slot in a
later phase. Brand-agnostic.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

from PIL import Image

_PathLike = Union[str, Path]


def composite_device_mockup(
    *,
    creative_path: _PathLike,
    frame_path: _PathLike,
    screen_box: tuple[int, int, int, int],
    output_path: Optional[_PathLike] = None,
) -> Image.Image:
    """Resize the creative to `screen_box` and place it behind the frame's
    transparent screen hole; layer the frame on top. `screen_box` is
    (left, top, right, bottom) in frame pixel coordinates.

    Returns the composited RGBA image (saved to output_path if given).
    Raises FileNotFoundError if an input is missing, ValueError on a
    degenerate box — the caller decides how to degrade.
    """
    # Open via context managers so the source file handles are closed (the
    # converted copies own their own pixel data).
    with Image.open(frame_path) as _frame_img:
        frame = _frame_img.convert("RGBA")
    with Image.open(creative_path) as _creative_img:
        creative = _creative_img.convert("RGBA")

    left, top, right, bottom = screen_box
    width, height = right - left, bottom - top
    if width <= 0 or height <= 0:
        raise ValueError(f"invalid screen_box {screen_box}: non-positive area")

    # Explicit BICUBIC (PRD §9.1) so output is deterministic across Pillow
    # versions, not subject to the resize() default changing.
    creative_resized = creative.resize((width, height), resample=Image.BICUBIC)
    canvas = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    canvas.paste(creative_resized, (left, top))
    result = Image.alpha_composite(canvas, frame)

    if output_path is not None:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        result.save(out)
    return result
