"""Phase 5: page texture, a subtle procedural BRAND MARBLE ground.

The light-page GROUND (the package's `background_texture` report-asset, which the
renderer layers as report_ground_uri on every [data-ground-mode="light"] .page)
is overwritten with a SUBTLE brand marble: the procedural marble (code, not fal)
blended over a solid cream (brand_neutral_light) at GROUND_MARBLE_ALPHA. The
user-approved swatch "C" == ~16% marble over cream, atmosphere behind the copy,
never a pattern that competes with it.

Brand-agnostic: every colour is a brand token; the ONLY literal is the alpha.
Import-light on purpose (PIL + stages.procedural_texture only) so the build and
the test suite can both reach it without build_package's heavy pydantic imports.
"""
from __future__ import annotations

# The page ground is mostly cream with a WHISPER of marble. 0.16 == swatch "C":
# subtle enough that the warm-cream mean (legibility / design conformance) holds.
GROUND_MARBLE_ALPHA = 0.16


def _hex_to_rgb_tuple(h: str) -> tuple[int, int, int]:
    """'#rrggbb' -> (r, g, b). Brand-agnostic (input is a brand token)."""
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def blend_marble_over_cream(
    *,
    width: int,
    height: int,
    brand_neutral_light: str,
    brand_accent: str,
    brand_primary: str,
    alpha: float = GROUND_MARBLE_ALPHA,
    seed: int = 7,
):
    """Blend a procedural brand marble over a solid cream (brand_neutral_light)
    ground at `alpha`, returning the blended PIL RGB image.

    The result is a SUBTLE brand marble that preserves the warm-cream legibility
    of the page. Brand-agnostic: the cream is brand_neutral_light, the veins come
    from generate_brand_texture(brand_accent/brand_primary), no colour literals.
    Image.blend(a, b, alpha) == a*(1-alpha) + b*alpha, so at alpha 0.16 the ground
    stays mostly cream and its MEAN colour remains in the warm-cream band.
    """
    from PIL import Image  # noqa: PLC0415
    from stages.procedural_texture import generate_brand_texture  # noqa: PLC0415

    cream = Image.new(
        "RGB", (int(width), int(height)), _hex_to_rgb_tuple(brand_neutral_light)
    )
    marble = generate_brand_texture(
        "marble",
        int(width),
        int(height),
        brand_neutral_light=brand_neutral_light,
        brand_accent=brand_accent,
        brand_primary=brand_primary,
        seed=seed,
    ).convert("RGB")
    return Image.blend(cream, marble, float(alpha))
