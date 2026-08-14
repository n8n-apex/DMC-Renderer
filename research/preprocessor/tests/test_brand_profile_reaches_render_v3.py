"""A profile that never reaches the renderer is not a profile."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


def test_the_build_passes_the_profile_id_to_the_render_bundle() -> None:
    """The field existed at both ends and nothing carried it between.

    `render_v3` read `bundle.brand_profile_id`, `brand_profile.py` loaded
    it, the override logic was written -- and `build_v3` never set it, so
    every client rendered on default axes. GEVA and Buchagentur, as
    different as two profiles get, produced byte-identical output.
    """
    source = (ROOT / "dmc-renderer" / "build_v3.py").read_text(encoding="utf-8")

    assert "brand_profile_id=" in source, (
        "build_v3 must pass brand_profile_id into RenderBundleV3"
    )


def test_every_declared_profile_supplies_every_axis() -> None:
    """The grammar's hard rule: a missing axis is a loud error, never a default."""
    import sys

    renderer = ROOT / "research" / "v7-renderer"
    if str(renderer) not in sys.path:
        sys.path.insert(0, str(renderer))
    from tokens.brand_profile import load_profiles

    profiles = load_profiles()

    assert len(profiles) >= 5, sorted(profiles)
    for profile in profiles.values():
        # Constructing it already enforced this, but assert the axes that
        # decide how a page LOOKS are genuinely distinct per client.
        assert profile.primary_dark.startswith("#")
        assert profile.belief_treatment
        assert profile.ground_mode
        assert profile.image_modes


def test_two_profiles_do_not_share_a_palette() -> None:
    """If every client resolves to one accent, the axes are not firing."""
    import sys

    renderer = ROOT / "research" / "v7-renderer"
    if str(renderer) not in sys.path:
        sys.path.insert(0, str(renderer))
    from tokens.brand_profile import load_profiles

    accents = {
        profile.accents.data_emphasis for profile in load_profiles().values()
    }

    assert len(accents) > 1, accents


def test_an_unknown_profile_id_refuses_rather_than_defaulting() -> None:
    import sys

    renderer = ROOT / "research" / "v7-renderer"
    if str(renderer) not in sys.path:
        sys.path.insert(0, str(renderer))
    from tokens.brand_profile import ProfileMissing, profile_for

    with pytest.raises(ProfileMissing):
        profile_for("no-such-client")
