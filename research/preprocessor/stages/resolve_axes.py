"""resolve_axes — derive the 7 per-client design axes (DNA §B) as validated
Literals, deterministically. Precedence per axis: explicit brand_profile →
derived-from-tokens (palette/accent_mechanic, by hue distance) → grammar
default. Pure (no I/O, stdlib colorsys only). Records per-axis provenance.

Brand-agnostic: axes are DATA — this module names only axis kinds + value
sets, never a client. Not wired into the package until a later phase.
"""
from __future__ import annotations

import colorsys
from typing import Literal, Optional

from pydantic import BaseModel

HeadlineType = Literal["serif", "sans", "sans_allcaps"]
Palette = Literal["mono_tonal", "dual_contrasting"]
AccentMechanic = Literal["tonal_same_hue", "contrasting_hue"]
Texture = Literal["smooth", "marble_paper", "crumpled_paper", "paper_grain", "photo"]
# density value set: the original DNA vocabulary (airy/balanced/packed) PLUS the
# renderer chassis's synonyms (compact/spacious) so an explicit brand_profile may
# speak either vocabulary and pass straight through to the package the chassis
# consumes (chassis maps balanced|compact|spacious to --density-* vars). Additive
# — no existing value's meaning changes.
Density = Literal["airy", "balanced", "packed", "compact", "spacious"]
GroundMode = Literal["light", "dark", "mixed"]

_HEADLINE = {"serif", "sans", "sans_allcaps"}
_PALETTE = {"mono_tonal", "dual_contrasting"}
_ACCENT = {"tonal_same_hue", "contrasting_hue"}
_TEXTURE = {"smooth", "marble_paper", "crumpled_paper", "paper_grain", "photo"}
_DENSITY = {"airy", "balanced", "packed", "compact", "spacious"}
_GROUND = {"light", "dark", "mixed"}

_HUE_SAME_FAMILY_DEG = 35.0
_MIN_ACCENT_SATURATION = 0.15


class ResolvedAxes(BaseModel):
    """The 7 validated design axes. Serialized into the package in a later phase."""

    headline_type: HeadlineType
    palette: Palette
    accent_mechanic: AccentMechanic
    texture: Texture
    qr_enabled: bool
    density: Density
    ground_mode: GroundMode


def _hex_to_hls(hex_str: str) -> Optional[tuple[float, float, float]]:
    """(#rgb|#rrggbb) → (hue_deg, lightness, saturation); None if unparseable."""
    s = hex_str.strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) != 6:
        return None
    try:
        r, g, b = (int(s[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    except ValueError:
        return None
    h, light, sat = colorsys.rgb_to_hls(r, g, b)
    return h * 360.0, light, sat


def _hue_distance(a: float, b: float) -> float:
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)


def _derive_palette_accent(primary_hex: str, accent_hex: str) -> tuple[Palette, AccentMechanic]:
    p = _hex_to_hls(primary_hex)
    a = _hex_to_hls(accent_hex)
    if p is None or a is None:
        return "mono_tonal", "tonal_same_hue"
    if a[2] < _MIN_ACCENT_SATURATION:
        return "mono_tonal", "tonal_same_hue"
    if _hue_distance(p[0], a[0]) <= _HUE_SAME_FAMILY_DEG:
        return "mono_tonal", "tonal_same_hue"
    return "dual_contrasting", "contrasting_hue"


def resolve_axes(
    *,
    brand_profile,
    brand_primary: str,
    brand_accent: str,
) -> tuple[ResolvedAxes, dict[str, str]]:
    """Resolve the 7 axes + a {axis: source} provenance map. Sources:
    "brand_profile" | "derived" | "default"."""
    prov: dict[str, str] = {}

    def explicit(axis: str, allowed: set[str]) -> Optional[str]:
        val = getattr(brand_profile, axis, None) if brand_profile is not None else None
        if isinstance(val, str) and val in allowed:
            prov[axis] = "brand_profile"
            return val
        return None

    def with_default(axis: str, chosen: Optional[str], default: str) -> str:
        if chosen is not None:
            return chosen
        prov[axis] = "default"
        return default

    headline_type = with_default("headline_type", explicit("headline_type", _HEADLINE), "serif")
    texture = with_default("texture", explicit("texture", _TEXTURE), "smooth")
    density = with_default("density", explicit("density", _DENSITY), "balanced")
    # ground_mode is intentionally explicit-or-default-"light", NOT derived from
    # brand tokens: per DNA §C3 the page ground is light by default for every
    # client (dark is applied to PANELS, a renderer concern), so deriving "dark"
    # from a dark primary would be wrong.
    ground_mode = with_default("ground_mode", explicit("ground_mode", _GROUND), "light")

    palette = explicit("palette", _PALETTE)
    accent = explicit("accent_mechanic", _ACCENT)
    if palette is None or accent is None:
        d_palette, d_accent = _derive_palette_accent(brand_primary, brand_accent)
        if palette is None:
            palette, prov["palette"] = d_palette, "derived"
        if accent is None:
            accent, prov["accent_mechanic"] = d_accent, "derived"

    qr_val = getattr(brand_profile, "qr_enabled", None) if brand_profile is not None else None
    if isinstance(qr_val, bool):
        qr_enabled, prov["qr_enabled"] = qr_val, "brand_profile"
    else:
        qr_enabled, prov["qr_enabled"] = False, "default"

    return (
        ResolvedAxes(
            headline_type=headline_type,
            palette=palette,
            accent_mechanic=accent,
            texture=texture,
            qr_enabled=qr_enabled,
            density=density,
            ground_mode=ground_mode,
        ),
        prov,
    )
