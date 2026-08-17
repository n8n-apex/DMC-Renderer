"""Compile the universal base tokens + a client's brand/axes into a CSS
`:root` block + a map of <html data-*> axis attributes.

Brand-agnostic: client colors/fonts arrive as DATA (BrandConfig); axes select
variants (e.g. serif vs sans display). Emits new semantic vars AND legacy
`--brand-*` aliases so existing patterns keep working during the migration.
"""
from __future__ import annotations

import json
import logging
import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from brand_tokens import BrandConfig  # noqa: E402

_BASE = json.loads((Path(__file__).resolve().parent / "base.tokens.json").read_text(encoding="utf-8"))

_LOG = logging.getLogger(__name__)

# Quoted family names inside a CSS font stack (e.g. a stack of the form
# "<Family>", sans-serif yields ["<Family>"]). Used to read the chassis-default
# faces out of CONFIG (base.tokens.json) rather than hardcoding the family
# strings in this LOGIC file: see the brand-agnostic guard
# (test_no_literals_in_architecture).
_QUOTED_FAMILY = re.compile(r"'([^']+)'")


def _quoted_families(stack: str) -> list[str]:
    """Every quoted family name in a CSS font-stack string, in order."""
    return _QUOTED_FAMILY.findall(stack)


def _primary_family(stack: str) -> str:
    """The first quoted family in a CSS font-stack (the bundled default face)."""
    families = _quoted_families(stack)
    return families[0] if families else ""


# Chassis-default bundled faces: read from base.tokens.json's font stacks (their
# TTFs ship in fonts/), plus the CONFIG's "$extra-bundled-families": faces with
# @font-face coverage beyond the default stacks (e.g. Inter's own TTFs; the
# pre-rename 'Source * Pro' aliases mapped onto the renamed Adobe files: see the
# assembler's @font-face block). The family NAMES live only in that CONFIG file,
# never as literals in this logic. A brand-supplied family outside this set has
# no bundled TTF yet, so we warn so the file can be bundled in a later phase.
_BUNDLED_FAMILIES: frozenset[str] = frozenset(
    fam
    for spec in _BASE["font"].values()
    for fam in _quoted_families(spec["$value"])
) | frozenset(_BASE.get("$extra-bundled-families", []))


def _font_stack(brand_family: str, bundled_default: str, generic: str) -> str:
    """Build a CSS font stack: brand family first, then bundled default, then generic.

    Phase A / spec 2026-06-03-self-correcting-quality-architecture §8: wire
    brand font end-to-end, warn on miss. The brand-supplied family (DATA) is
    placed at the FRONT (quoted) when it is present and differs from the
    bundled default; the bundled default and a generic keyword always backstop
    it. When the brand family is non-empty and NOT one of the bundled faces,
    emit a warning naming it (we have no TTF for it yet).
    """
    family = (brand_family or "").strip()
    if family and family not in _BUNDLED_FAMILIES:
        _LOG.warning(
            "brand font-family %r is not a bundled face %s; no TTF will load for "
            "it yet: falling back to %r. Bundle its file to render it.",
            family, sorted(_BUNDLED_FAMILIES), bundled_default,
        )
    parts: list[str] = []
    if family and family != bundled_default:
        parts.append(f"'{family}'")
    parts.append(f"'{bundled_default}'")
    parts.append(generic)
    return ", ".join(parts)


@dataclass(frozen=True)
class BrandAxes:
    """§4.0 perceptual axes (per-client). Defaults are grammar-neutral."""
    headline_type: str = "serif"     # serif | sans | sans_allcaps
    ground_mode: str = "light"       # light | dark | tonal …
    texture: str = "smooth"          # smooth | marble_paper | crumpled_paper | photo
    accent_mechanic: str = "tonal_same_hue"  # tonal_same_hue | contrasting_hue
    # v2.0 axes (carried but not yet wired to CSS/data-attrs: later 4b tasks)
    palette: str = "mono_tonal"      # mono_tonal | dual_contrasting | …
    qr_enabled: bool = False
    density: str = "balanced"        # balanced | compact | spacious


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Parse #RGB or #RRGGBB to (r, g, b) integers."""
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = h[0] * 2 + h[1] * 2 + h[2] * 2
    r = int(h[0:2], 16)
    g = int(h[2:4], 16)
    b = int(h[4:6], 16)
    return r, g, b


def _blend_hex(a_hex: str, b_hex: str, t: float) -> tuple[int, int, int]:
    """Blend two hex colors by factor t (0=a, 1=b), returning (r, g, b) integers."""
    ar, ag, ab = _hex_to_rgb(a_hex)
    br, bg, bb = _hex_to_rgb(b_hex)
    mix = lambda x, y: max(0, min(255, round(x + (y - x) * t)))  # noqa: E731
    return mix(ar, br), mix(ag, bg), mix(ab, bb)


def _relative_luminance(r: int, g: int, b: int) -> float:
    """Compute WCAG relative luminance from sRGB integers."""
    def _linearize(c: int) -> float:
        s = c / 255.0
        return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4

    return 0.2126 * _linearize(r) + 0.7152 * _linearize(g) + 0.0722 * _linearize(b)


def _flat(group: str) -> dict:
    return {k: v["$value"] for k, v in _BASE[group].items() if not k.startswith("$")}


def compile_tokens(brand: BrandConfig, axes: BrandAxes) -> tuple[str, dict]:
    space = _flat("space")
    type_ = _flat("type")
    color = _flat("color")
    font = _flat("font")

    display_family = "var(--font-serif)" if axes.headline_type == "serif" else "var(--font-sans-head)"

    lines: list[str] = [":root {"]
    # fonts: brand family (DATA) leads each sans stack, backed by the bundled
    # default + generic; serif stays the bundled editorial default from
    # base.tokens.json (Source Serif 4). The bundled-default NAME for each sans stack
    # is read from base.tokens.json (CONFIG), never hardcoded here. Warns when a
    # brand family is not one of the bundled faces (no TTF for it yet).
    head_default = _primary_family(font["sans-head"])
    body_default = _primary_family(font["sans-body"])
    lines.append(f"  --font-sans-head: {_font_stack(brand.font_heading, head_default, 'sans-serif')};")
    lines.append(f"  --font-sans-body: {_font_stack(brand.font_body, body_default, 'sans-serif')};")
    lines.append(f"  --font-serif: {font['serif']};")
    lines.append(f"  --font-display: {display_family};")
    # --font-head FOLLOWS the display family (axis-aware) so a serif-headline
    # brand (headline_type=serif) renders serif headings: the editorial signal: # and the display serif actually embeds (clearing the N03 font-fallback
    # hard-fail). A sans brand is unchanged: --font-display resolves to the
    # sans-head stack. Previously --font-head was pinned to --font-sans-head, so
    # serif brands silently got sans headings stuck on the unbundled brand face.
    lines.append("  --font-head: var(--font-display);")
    lines.append("  --font-body: var(--font-sans-body);")
    # semantic colors (per-client primitives bound here)
    lines.append(f"  --color-primary: {brand.brand_primary};")
    lines.append(f"  --color-accent: {brand.brand_accent};")
    lines.append(f"  --color-ink: {brand.brand_neutral_dark};")
    lines.append(f"  --color-muted: {brand.brand_neutral_mid};")
    lines.append(f"  --color-surface: {brand.brand_neutral_light};")
    lines.append(f"  --color-body: {color['body']};")
    lines.append(f"  --color-on-dark: {color['on-dark']};")
    # derived accent roles (hue-agnostic, computed from brand_accent)
    ar, ag, ab = _hex_to_rgb(brand.brand_accent)
    accent_tint = f"rgba({ar},{ag},{ab},0.12)"
    accent_wash = f"rgba({ar},{ag},{ab},0.05)"
    lum = _relative_luminance(ar, ag, ab)
    on_accent = brand.brand_neutral_dark if lum > 0.179 else color["on-dark"]
    lines.append(f"  --color-accent-tint: {accent_tint};")
    lines.append(f"  --color-on-accent: {on_accent};")
    lines.append(f"  --color-ground-wash: {accent_wash};")
    # derived primary role: same WCAG luminance rule applied to brand_primary
    pr, pg, pb = _hex_to_rgb(brand.brand_primary)
    primary_lum = _relative_luminance(pr, pg, pb)
    on_primary = brand.brand_neutral_dark if primary_lum > 0.179 else color["on-dark"]
    lines.append(f"  --color-on-primary: {on_primary};")
    # spacing + type scale (universal)
    for k, v in space.items():
        lines.append(f"  --space-{k}: {v};")
    for k, v in type_.items():
        lines.append(f"  --type-{k}: {v};")
    # legacy aliases so existing patterns (which use --brand-*) keep working
    lines.append(f"  --brand-primary: {brand.brand_primary};")
    lines.append(f"  --brand-accent: {brand.brand_accent};")
    lines.append(f"  --brand-neutral-dark: {brand.brand_neutral_dark};")
    lines.append(f"  --brand-neutral-mid: {brand.brand_neutral_mid};")
    lines.append(f"  --brand-neutral-light: {brand.brand_neutral_light};")
    # neutral role aliases (expose brand neutrals as named roles: no new derivation)
    lines.append(f"  --color-neutral-dark: {brand.brand_neutral_dark};")
    lines.append(f"  --color-neutral-mid: {brand.brand_neutral_mid};")
    lines.append(f"  --color-neutral-light: {brand.brand_neutral_light};")
    # --color-ground: brand_neutral_light blended ~5% toward brand_neutral_dark
    gr, gg, gb = _blend_hex(brand.brand_neutral_light, brand.brand_neutral_dark, 0.05)
    lines.append(f"  --color-ground: rgb({gr},{gg},{gb});")
    # --color-panel: primary when contrasting_hue, else ink
    if axes.accent_mechanic == "contrasting_hue":
        panel_css = "var(--color-primary)"
        panel_hex = brand.brand_primary
    else:
        panel_css = "var(--color-ink)"
        panel_hex = brand.brand_neutral_dark
    lines.append(f"  --color-panel: {panel_css};")
    # --color-on-panel: WCAG luminance on-color for the resolved panel hue
    plr, plg, plb = _hex_to_rgb(panel_hex)
    panel_lum = _relative_luminance(plr, plg, plb)
    on_panel = brand.brand_neutral_dark if panel_lum > 0.179 else color["on-dark"]
    lines.append(f"  --color-on-panel: {on_panel};")
    lines.append("}")
    css_root = "\n".join(lines)

    # Panel MATERIAL derived from the texture axis (value-driven, brand-agnostic):
    # the surface the stat/callout panels read as. A "paper" brand gets matte
    # cards; a clean/modern ("smooth") brand gets faux-glass cards (rounded + a
    # hairline light edge over the frosted ground: see [data-material="glass"] in
    # components.css); anything else stays flat. WeasyPrint can't do backdrop-filter,
    # so glass is an edge+ground treatment, never a render-time blur.
    _PAPER_TEXTURES = ("marble_paper", "crumpled_paper")
    if axes.texture in _PAPER_TEXTURES:
        _material = "paper"
    elif axes.texture == "smooth":
        _material = "glass"
    else:
        _material = "flat"

    data_attrs = {
        "data-headline-type": axes.headline_type,
        "data-ground-mode": axes.ground_mode,
        "data-texture": axes.texture,
        "data-density": axes.density,
        "data-material": _material,
    }
    return css_root, data_attrs
