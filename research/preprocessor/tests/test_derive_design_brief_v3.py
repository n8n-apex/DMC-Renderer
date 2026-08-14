"""A client's axes must reach the images, not stop at the stylesheet."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

RENDERER = Path(__file__).resolve().parents[3] / "research" / "v7-renderer"
if str(RENDERER) not in sys.path:
    sys.path.insert(0, str(RENDERER))

from stages.derive_design_brief_v3 import derive_design_brief  # noqa: E402
from tokens.brand_profile import AccentRoles, BrandProfile  # noqa: E402


def _profile(**overrides) -> BrandProfile:
    base = dict(
        profile_id="p", client_name="C",
        primary_dark="#222B53",
        accents=AccentRoles(
            cover="#C9A227", cta="#C9A227", body_editorial="#222B53",
            data_emphasis="#3E6FD6", icons="#C9A227", url="#3E6FD6",
            kicker="#C9A227",
        ),
        accent_mechanic="contrasting_hue", ground_mode="cool_light",
        texture="crumpled_paper", headline_type="serif",
        headline_construction="accent_word",
        image_modes=("cutout_figure", "framed_rect"),
        page_unit="spread", case_geometry="RRW", belief_treatment="dark_box",
        rating_widget="trustpilot",
        font_head="Montserrat", font_body="Source Sans Pro",
    )
    base.update(overrides)
    return BrandProfile(**base)


def test_a_mode_the_client_never_uses_becomes_an_exclusion() -> None:
    """The grammar's aerztepartner row says NO full-bleed, in prose.

    A generator will produce full-bleed photography unless the exclusion
    travels with the prompt, so it must be derived, not remembered.
    """
    brief = derive_design_brief(_profile())

    assert "full-bleed" in brief["avoid"]


def test_a_mode_the_client_does_use_is_not_excluded() -> None:
    brief = derive_design_brief(_profile(image_modes=("full_bleed_photo",)))

    assert "full-bleed" not in brief["avoid"]


def test_a_tonal_client_forbids_competing_accents() -> None:
    """Buchagentur is the structural outlier: one hue, several tones."""
    brief = derive_design_brief(_profile(accent_mechanic="tonal_same_hue"))

    assert "competing accent hues" in brief["avoid"]


def test_baked_in_text_is_always_forbidden() -> None:
    """A background with words in it wrecks type set on top of it."""
    brief = derive_design_brief(_profile())

    for banned in ("text", "letters", "watermarks", "logos"):
        assert banned in brief["avoid"]


def test_the_palette_carries_the_client_hexes() -> None:
    brief = derive_design_brief(_profile())

    assert "#222B53" in brief["color_usage"]
    assert "#C9A227" in brief["color_usage"]


def test_the_texture_axis_becomes_camera_language() -> None:
    """`crumpled_paper` means nothing to an image model on its own."""
    brief = derive_design_brief(_profile(texture="crumpled_paper"))

    assert "creases" in brief["texture_material"]


def test_the_motif_reaches_the_shape_language() -> None:
    brief = derive_design_brief(
        _profile(motif="flowing gold ribbon footer every interior")
    )

    assert "ribbon" in brief["shape_language"]


def test_composition_always_reserves_room_for_type() -> None:
    """Every one of these images has real type set over it later."""
    brief = derive_design_brief(_profile())

    assert "negative space" in brief["composition"]


@pytest.mark.parametrize("ground", ["cream_textured", "cool_light", "role_split", "tri"])
def test_every_ground_mode_has_lighting_language(ground) -> None:
    brief = derive_design_brief(_profile(ground_mode=ground))

    assert brief["lighting"].strip()


def test_no_phrase_is_repeated_in_a_composed_prompt() -> None:
    """Saying the same thing twice wastes the clause a model weights most.

    The first version embedded the ground language in `style` AND emitted it
    as `lighting`, so every prompt opened with the same sentence twice and
    pushed the subject past where it counts.
    """
    from stages.derive_design_brief_v3 import compose_slot_prompt

    brief = derive_design_brief(_profile())
    prompt = compose_slot_prompt(brief, "a quiet desk at dusk", "3:4")

    clauses = [c.strip().lower() for c in prompt.split(".") if c.strip()]
    assert len(clauses) == len(set(clauses)), [
        c for c in clauses if clauses.count(c) > 1
    ]


def test_the_subject_leads_the_prompt() -> None:
    """Twelve slots differ only by subject; it cannot be buried."""
    from stages.derive_design_brief_v3 import compose_slot_prompt

    brief = derive_design_brief(_profile())
    prompt = compose_slot_prompt(brief, "a quiet desk at dusk", "3:4")

    assert prompt.lower().startswith("a quiet desk at dusk")


def test_two_slots_differ_early_not_late() -> None:
    """If the first 80 characters match, the model sees one request twice."""
    from stages.derive_design_brief_v3 import compose_slot_prompt

    brief = derive_design_brief(_profile())
    a = compose_slot_prompt(brief, "a quiet desk at dusk", "3:4")
    b = compose_slot_prompt(brief, "a busy workshop floor", "3:4")

    assert a[:80] != b[:80]
