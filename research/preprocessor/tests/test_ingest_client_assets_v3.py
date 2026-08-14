"""Real client images must enter the ledger, and unapproved ones must not."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from contracts_v3.asset_ledger import AssetRecord
from stages.ingest_client_assets_v3 import (
    ingest_client_assets,
    portrait_capable,
    semantic_class_for,
)


ROOT = Path(__file__).resolve().parents[3]
JOUSEF = ROOT / "research" / "preprocessor" / "client_assets" / "apex"


@pytest.mark.parametrize(
    "filename,expected",
    [
        ("founder.png", "identity"),
        ("proof-1.png", "proof"),
        ("case-study-3.png", "context"),
        ("jousefmrd_avatar.jpg", "identity"),
        ("logo-partner.webp", "logo"),
        ("product-2.webp", "product"),
        ("something-else.jpg", "context"),
    ],
)
def test_the_filename_declares_the_semantic_class(filename, expected) -> None:
    assert semantic_class_for(filename) == expected


def test_every_jousef_image_becomes_a_valid_asset_record() -> None:
    records = ingest_client_assets(JOUSEF, client_slug="jousef")

    assert len(records) >= 18
    for record in records:
        AssetRecord.model_validate(record)


def test_nothing_is_rights_cleared_unless_it_was_named() -> None:
    """An unapproved photograph must never default to usable."""
    records = ingest_client_assets(JOUSEF, client_slug="jousef")

    assert all(record["rights_status"] == "unknown" for record in records)


def test_a_named_file_is_authorized_and_records_who_said_so() -> None:
    records = ingest_client_assets(
        JOUSEF,
        client_slug="jousef",
        authorized=["founder.png"],
        authorized_by="owner",
        authorized_on=date(2026, 8, 8),
    )
    founder = next(r for r in records if r["local_path"].endswith("founder.png"))
    others = [r for r in records if not r["local_path"].endswith("founder.png")]

    assert founder["rights_status"] == "client_authorized"
    assert "authorized by owner on 2026-08-08" in founder["source_locator"]
    assert all(r["rights_status"] == "unknown" for r in others)


def test_an_approval_with_no_approver_is_refused() -> None:
    with pytest.raises(ValueError, match="approver"):
        ingest_client_assets(JOUSEF, client_slug="jousef", authorized=["founder.png"])


def test_the_founder_photo_is_flagged_as_landscape() -> None:
    """1179x755 cannot fill a portrait rail; the layout must know."""
    records = ingest_client_assets(JOUSEF, client_slug="jousef")
    founder = next(r for r in records if r["local_path"].endswith("founder.png"))

    assert founder["pixel_width"] == 1179 and founder["pixel_height"] == 755
    assert not portrait_capable(founder)


def test_a_favicon_is_a_file_not_a_picture() -> None:
    """64x50 is 5mm in print; it must not count toward visual density."""
    from stages.ingest_client_assets_v3 import print_usable

    assert not print_usable({"print_width_mm": 5.4, "print_height_mm": 4.2})
    assert print_usable({"print_width_mm": 180.5, "print_height_mm": 86.8})


def test_case_client_screenshots_are_context_never_logos() -> None:
    """A folder named for a client does not make its screenshots marks."""
    from stages.ingest_client_assets_v3 import ingest_case_client_assets

    records = ingest_case_client_assets(
        ROOT / "incoming_assets", client_slug="jousef.case"
    )

    assert records
    assert all(r["semantic_class"] == "context" for r in records)
    assert all(r["rights_status"] == "unknown" for r in records)
    for record in records:
        AssetRecord.model_validate(record)
