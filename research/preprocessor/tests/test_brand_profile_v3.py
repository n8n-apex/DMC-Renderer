"""Every client must look like itself. The grammar forbids defaulting axes."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
RENDERER = ROOT / "research" / "v7-renderer"
if str(RENDERER) not in sys.path:
    sys.path.insert(0, str(RENDERER))

from tokens.brand_profile import (  # noqa: E402
    BrandProfile,
    ProfileMissing,
    load_profiles,
    profile_for,
)


EXPECTED = {"geva", "aerz", "nikl", "alex", "buch"}


def test_all_five_observed_profiles_are_encoded() -> None:
    assert set(load_profiles()) == EXPECTED


def test_each_profile_matches_the_grammar_row() -> None:
    """Spot-check cells that are cited in richard-grammar-v2.md §4.1."""
    geva = profile_for("geva")
    assert geva.primary_dark == "#1E1D41"
    assert geva.texture == "marble_paper"
    assert geva.belief_treatment == "ghost_numeral"
    assert geva.case_geometry == "LRP"

    buch = profile_for("buch")
    assert buch.accent_mechanic == "tonal_same_hue"   # the structural outlier
    assert buch.headline_construction == "tonal_accent_word"
    assert buch.case_geometry == "NR"

    alex = profile_for("alex")
    assert alex.headline_type == "sans_allcaps"
    assert alex.case_geometry == "BAND"

    nikl = profile_for("nikl")
    assert nikl.page_unit == "single_page"            # the only single-page client
    assert nikl.belief_treatment == "connector_spine"


def test_no_two_clients_share_a_treatment_fingerprint() -> None:
    """If two profiles render identically, the overfit is back."""
    fingerprints = {
        profile_id: tuple(sorted(profile.data_attributes().items()))
        for profile_id, profile in load_profiles().items()
    }

    assert len(set(fingerprints.values())) == len(fingerprints)


def test_a_profile_missing_an_axis_cannot_be_constructed() -> None:
    """The grammar's HARD rule, expressed as a type."""
    complete = profile_for("geva").model_dump()
    for axis in ("ground_mode", "texture", "belief_treatment", "case_geometry"):
        partial = {k: v for k, v in complete.items() if k != axis}
        with pytest.raises(Exception):
            BrandProfile.model_validate(partial)


def test_an_unknown_client_is_refused_not_defaulted() -> None:
    with pytest.raises(ProfileMissing) as caught:
        profile_for("does-not-exist")

    assert "forbids" in str(caught.value)


def test_every_axis_reaches_the_dom() -> None:
    """An axis with no attribute cannot change how anything looks."""
    attributes = profile_for("geva").data_attributes()

    for axis in (
        "data-ground-mode",
        "data-texture",
        "data-headline-type",
        "data-headline-construction",
        "data-belief-treatment",
        "data-case-geometry",
        "data-accent-mechanic",
        "data-page-unit",
        "data-image-modes",
    ):
        assert axis in attributes


def test_the_stylesheet_acts_on_every_axis_attribute() -> None:
    """A DOM attribute nothing styles is still a report that looks the same."""
    css = (RENDERER / "styles_v3" / "axes.css").read_text(encoding="utf-8")

    for axis in (
        "data-ground-mode",
        "data-texture",
        "data-headline-type",
        "data-headline-construction",
        "data-belief-treatment",
        "data-accent-mechanic",
    ):
        assert axis in css, f"axes.css never uses {axis}"

    # every value of the belief axis must be drawn, not just one
    for treatment in ("dark_box", "ghost_numeral", "connector_spine", "plain_numbered"):
        assert treatment in css


def test_every_named_motif_maps_to_a_drawn_device() -> None:
    """A motif described in prose must resolve to something CSS can draw."""
    from tokens.brand_profile import load_profiles

    drawn = {"ribbon", "corner_tab", "swoosh", "none"}
    for profile_id, profile in load_profiles().items():
        kind = profile.motif_kind()
        assert kind in drawn, f"{profile_id} motif {profile.motif!r} -> {kind}"
        if profile.motif:
            assert kind != "none", f"{profile_id} has a motif that draws nothing"


def test_the_stylesheet_draws_every_case_geometry_and_motif() -> None:
    css = (RENDERER / "styles_v3" / "axes.css").read_text(encoding="utf-8")

    for geometry in ("RRW", "LRP", "NR", "BAND"):
        assert f'data-case-geometry="{geometry}"' in css
    for motif in ("ribbon", "corner_tab", "swoosh"):
        assert f'data-motif="{motif}"' in css
    for mode in ("framed_rect", "full_bleed_photo", "duotone", "round_portrait"):
        assert f'data-image-modes~="{mode}"' in css


def test_a_profile_without_full_bleed_never_gets_one() -> None:
    """aerz states 'NO full-bleed' explicitly; the axis must honour it."""
    aerz = profile_for("aerz")

    assert "full_bleed_photo" not in aerz.image_modes
    assert "cutout_bleed" not in aerz.image_modes
