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
    """Median-cut quantize `image_path` into <= max_colors ranked by
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
