"""Tests for Stage Onboard-2 — pixel_palette (Pillow quantization)."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from stages.onboard.pixel_palette import extract_palette, _rgb_to_hex, _luminance


def _make_two_color_png(tmp_path: Path) -> str:
    """70% navy (#1a2540), 30% coral (#e97e47), 100x100."""
    img = Image.new("RGB", (100, 100), (26, 37, 64))   # navy
    coral = Image.new("RGB", (30, 100), (233, 126, 71))
    img.paste(coral, (70, 0))
    p = tmp_path / "hero.png"
    img.save(p)
    return str(p)


def test_rgb_to_hex() -> None:
    assert _rgb_to_hex((26, 37, 64)) == "#1a2540"
    assert _rgb_to_hex((255, 255, 255)) == "#ffffff"


def test_luminance_orders_dark_light() -> None:
    assert _luminance((0, 0, 0)) < _luminance((255, 255, 255))


def test_extract_palette_two_colors(tmp_path: Path) -> None:
    palette = extract_palette(_make_two_color_png(tmp_path), region="hero")
    hexes = {c.hex for c in palette.colors}
    assert "#1a2540" in hexes
    assert "#e97e47" in hexes
    assert palette.colors[0].hex == "#1a2540"
    assert palette.colors[0].coverage_pct > palette.colors[1].coverage_pct
    assert palette.colors[0].region == "hero"


def test_extract_palette_light_dark_indices(tmp_path: Path) -> None:
    palette = extract_palette(_make_two_color_png(tmp_path), region="hero")
    assert palette.colors[palette.lightest_idx].hex == "#e97e47"
    assert palette.colors[palette.darkest_idx].hex == "#1a2540"


def test_extract_palette_none_path_is_empty() -> None:
    palette = extract_palette(None, region="hero")
    assert palette.colors == []
    assert palette.lightest_idx is None


def test_extract_palette_missing_file_is_empty(tmp_path: Path) -> None:
    palette = extract_palette(str(tmp_path / "nope.png"), region="hero")
    assert palette.colors == []
