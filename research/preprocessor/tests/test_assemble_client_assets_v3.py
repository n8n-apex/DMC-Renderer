"""The join from a client's real files to a buildable asset list."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from contracts_v3.asset_ledger import AssetRecord
from stages.assemble_client_assets_v3 import assemble


ROOT = Path(__file__).resolve().parents[3]
OWN = ROOT / "research" / "preprocessor" / "client_assets" / "apex"
CASES = ROOT / "incoming_assets"


def test_it_gathers_both_the_client_and_the_case_client_images() -> None:
    result = assemble(client_slug="jousef", own_assets_dir=OWN, case_assets_dir=CASES)

    assert len(result.assets) >= 28
    for record in result.assets:
        AssetRecord.model_validate(record)


def test_unauthorized_files_are_carried_but_blocked() -> None:
    """27 real images stayed out of the last build. That must hold."""
    result = assemble(client_slug="jousef", own_assets_dir=OWN, case_assets_dir=CASES)

    assert result.authorized == 0
    assert result.blocked_on_rights == len(result.assets)


def test_authorizing_one_file_moves_exactly_one() -> None:
    result = assemble(
        client_slug="jousef",
        own_assets_dir=OWN,
        case_assets_dir=CASES,
        authorized=("founder.png",),
        authorized_by="owner",
        authorized_on=date(2026, 8, 8),
    )

    assert result.authorized == 1
    assert result.blocked_on_rights == len(result.assets) - 1


def test_it_warns_that_the_founder_shot_is_landscape() -> None:
    """Cheaper to say here than to discover in a rendered PDF."""
    result = assemble(client_slug="jousef", own_assets_dir=OWN, case_assets_dir=CASES)

    assert any("founder.png is landscape" in w for w in result.warnings)


def test_a_square_avatar_does_not_count_as_a_portrait() -> None:
    """Portrait ASPECT is not enough; 320x320 is 27mm, a thumbnail.

    jousefmrd_avatar.jpg is square so it passes the aspect check, but an
    identity rail wants roughly 55mm. Counting it would report a usable
    founder portrait that does not exist.
    """
    result = assemble(client_slug="jousef", own_assets_dir=OWN, case_assets_dir=CASES)

    assert any("no portrait founder shot" in w for w in result.warnings)
    assert any("usable print size" in w for w in result.warnings)


def test_it_warns_that_no_logo_exists() -> None:
    result = assemble(client_slug="jousef", own_assets_dir=OWN, case_assets_dir=CASES)

    assert any("logo wall cannot be built" in w for w in result.warnings)


def test_the_shortfall_is_measured_against_authorized_images_only() -> None:
    """An unauthorized file is not available, so it cannot close a gap."""
    unauthorized = assemble(
        client_slug="jousef", own_assets_dir=OWN, case_assets_dir=CASES,
        required_count=47,
    )
    with_one = assemble(
        client_slug="jousef", own_assets_dir=OWN, case_assets_dir=CASES,
        required_count=47,
        authorized=("founder.png",), authorized_by="owner",
    )

    assert unauthorized.shortfall == 47
    assert with_one.shortfall == 46


def test_files_too_small_to_print_never_reach_the_build() -> None:
    """conesso's 64x50 favicons are 5mm; they must not be assets."""
    result = assemble(client_slug="jousef", own_assets_dir=OWN, case_assets_dir=CASES)

    for record in result.assets:
        assert record["print_width_mm"] >= 20.0
        assert record["print_height_mm"] >= 20.0
