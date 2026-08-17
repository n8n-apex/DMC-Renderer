"""Turn a client's Layer-B axes into the visual brief the prompts obey.

`build_image_prompts.py` asks for a brand guideline -- style, mood, lighting,
texture, shape language, palette usage, and an avoid-list -- and turns it
into one generation prompt per slot. Nothing ever built that guideline, so
generation would have produced competent, on-model, entirely off-brand
pictures for every client alike.

Every field it needs is already an axis in `richard-grammar-v2.md` §4. This
is the translation, so a client's visual DNA reaches the images rather than
stopping at the stylesheet.

The avoid-list is the part that matters most and is easiest to get wrong.
The grammar records exclusions per client as prose -- aerztepartner is
"cutout_figure, 3d_render, framed_rect (NO full-bleed)" -- and an image
generator will cheerfully produce a full-bleed photograph unless told not
to. An exclusion that lives only in a document is not an exclusion.
"""

from __future__ import annotations

from typing import Any


# What each texture axis means to a camera, rather than to a stylesheet.
_TEXTURE_LANGUAGE = {
    "marble_paper": (
        "fine marbled paper grain, subtle fibre, matte print surface"
    ),
    "crumpled_paper": (
        "softly crumpled paper, gentle creases catching light, tactile matte stock"
    ),
    "smooth": "clean smooth surface, no visible grain, flat even finish",
    "photo": "photographic surface, natural depth, no paper texture",
}

# A ground mode is a lighting decision as much as a colour one.
_GROUND_LANGUAGE = {
    "cream_textured": ("warm cream ground, soft diffused daylight, low contrast"),
    "cool_light": ("cool neutral light ground, clean even daylight, airy"),
    "role_split": (
        "dramatic split between a deep dark field and a light one, "
        "directional light, strong tonal separation"
    ),
    "tri": (
        "three-tone staging: near-black, one saturated field, one light field; "
        "controlled studio light"
    ),
    "saturated_dark_light": (
        "saturated dark bands against light ground, confident contrast"
    ),
}

_SHAPE_LANGUAGE = {
    "RRW": "right-hand rail geometry, strong vertical division, rectilinear",
    "LRP": "left rail with a portrait anchor, calm vertical rhythm",
    "NR": "no rail, full-width composition, generous margins",
    "BAND": "full-width horizontal banding, architectural stacking",
}

_MOTIF_LANGUAGE = {
    "ribbon": "a flowing ribbon form as a recurring accent",
    "corner_tab": "a rotated corner tab and side-label as a recurring accent",
    "swoosh": "a thin wing or swoosh arc as a recurring accent",
    "none": "",
}

# Never negotiable, whatever the client. A generated background carrying
# baked-in words wrecks a layout that puts real type on top of it.
_UNIVERSAL_AVOID = (
    "text, letters, words, numbers, captions, watermarks, signatures, "
    "logos, UI chrome, borders, frames, stock-photo cliche, "
    "distorted hands, extra limbs, plastic skin"
)


def derive_design_brief(profile: Any) -> dict[str, str]:
    """The visual guideline this client's axes describe."""
    accents = profile.accents
    palette = ", ".join(
        dict.fromkeys(
            [
                profile.primary_dark,
                accents.cover,
                accents.data_emphasis,
                accents.body_editorial,
            ]
        )
    )
    mechanic = (
        "one accent hue held against the dark primary, used sparingly for emphasis"
        if profile.accent_mechanic == "contrasting_hue"
        else "a single hue family in several tones, no competing accent"
    )
    motif = _MOTIF_LANGUAGE.get(profile.motif_kind(), "")

    return {
        # Style carries medium and surface only. Lighting is its OWN field
        # and embedding it here made every composed prompt repeat the same
        # sentence twice, which wastes the tokens an image model weights
        # most and pushes the subject out of the opening clause.
        # Medium only. Texture has its own field and lighting has its own
        # field; folding either in here makes a composed prompt say the same
        # sentence twice, which is how the first version of this wasted the
        # opening clause an image model weights hardest.
        "style": "editorial print photography for a German B2B consulting report",
        "mood": (
            "measured, credible, calm; a serious document a business owner "
            "reads at a desk, never advertising energy"
        ),
        "lighting": _GROUND_LANGUAGE.get(profile.ground_mode, "even daylight"),
        "texture_material": _TEXTURE_LANGUAGE.get(profile.texture, "smooth"),
        "shape_language": ", ".join(
            part
            for part in (_SHAPE_LANGUAGE.get(profile.case_geometry, ""), motif)
            if part
        ),
        "color_usage": f"palette {palette}; {mechanic}",
        "composition": (
            "generous negative space reserved for type set later; "
            "subject off-centre; nothing important near the edges"
        ),
        "imagery": ", ".join(profile.image_modes),
        "avoid": _avoid_list(profile),
    }


def _avoid_list(profile: Any) -> str:
    """What this client must never be shown, not just what everyone avoids.

    The grammar states exclusions per profile in prose. aerztepartner's row
    reads "cutout_figure, 3d_render, framed_rect (NO full-bleed)", and a
    generator will produce a full-bleed photograph unless the exclusion
    travels with the prompt.
    """
    parts = [_UNIVERSAL_AVOID]
    modes = set(profile.image_modes)
    if "full_bleed_photo" not in modes:
        parts.append("full-bleed edge-to-edge photography")
    if "3d_render" not in modes:
        parts.append("3d renders, CGI product visualisations")
    if "cutout_figure" not in modes and "cutout_bleed" not in modes:
        parts.append("cut-out figures on flat colour")
    if "device_mockup" not in modes:
        parts.append("device mockups, phone and laptop screens")
    if "product_shot" not in modes:
        parts.append("packshots, isolated product photography")
    if profile.accent_mechanic == "tonal_same_hue":
        parts.append("competing accent hues, multi-colour palettes")
    return "; ".join(parts)


def compose_slot_prompt(brief: dict[str, str], subject: str, aspect: str) -> str:
    """One slot's prompt, with the SUBJECT leading.

    An image model weights its opening clause hardest. Leading with a shared
    style block makes twelve slots read as twelve near-identical requests and
    buries the one clause that differs. Subject first, then how it should
    look, then what the composition must leave room for.
    """
    parts = [
        subject.strip().rstrip("."),
        brief["style"],
        brief["lighting"],
        brief["texture_material"],
        brief["color_usage"],
        brief["composition"],
        f"aspect ratio {aspect}",
    ]
    return ". ".join(part.strip().rstrip(".") for part in parts if part.strip()) + "."
