"""The trust page must carry walls, not a stat strip and one photo.

Richard's trust pages stack logo walls and review-quote cards. A v3 build
once rendered that face as stats plus a single image, and the wall element
kinds existed in the contract and the renderer with nothing producing them.
These tests hold that closed.
"""

from __future__ import annotations

import inspect

from stages import materialize_render_contract_v3 as materializer


WALL_KINDS = ("LogoWallElement", "ProofWallElement", "EvidenceGalleryElement")


def test_every_wall_kind_has_a_producer() -> None:
    """A wall the materializer never builds can never reach a page."""
    source = inspect.getsource(materializer)
    missing = [kind for kind in WALL_KINDS if f"{kind}(" not in source]

    assert not missing, f"wall kinds with no producer: {missing}"


def test_a_lone_testimonial_still_becomes_a_quote_card() -> None:
    """The proof wall needs two quotes; one must not fall on the floor.

    QuoteElement was declared and styled and never constructed, so a single
    review had nowhere to go and simply vanished from the page.
    """
    source = inspect.getsource(materializer)

    assert "QuoteElement(" in source


def test_wall_thresholds_stay_at_the_reference_minimums() -> None:
    """Loosening a threshold to make a wall appear would be fabrication.

    A logo wall needs three marks and a proof wall needs two quotes because
    that is what the element contracts require; a wall drawn from one asset
    asserts a breadth of evidence the client does not have.
    """
    from contracts_v3.render_contract import (
        EvidenceGalleryElement,
        LogoWallElement,
        ProofWallElement,
    )

    assert LogoWallElement.model_fields["asset_ids"].metadata[0].min_length == 3
    assert ProofWallElement.model_fields["claim_ids"].metadata[0].min_length == 2
    assert EvidenceGalleryElement.model_fields["asset_ids"].metadata[0].min_length == 2
