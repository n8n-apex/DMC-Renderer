"""Tests for social-proof models — validated, never invented."""
from __future__ import annotations

from models_social import RatingCard, ReviewCard, SocialProofBlock, parse_social_proof


def test_full_block() -> None:
    block, warn = parse_social_proof({
        "ratings": [{"platform": "Trustpilot", "score": 4.8, "count": 212, "verified": True}],
        "reviews": [{"name": "M.", "role": "CEO", "stars": 5, "text": "top", "date": "2025-01"}],
        "press_logos": [{"name": "Forbes"}],
        "client_logos": [{"name": "ACME", "asset_key": "client-logo-1"}],
    })
    assert warn is None
    assert isinstance(block, SocialProofBlock)
    assert block.ratings[0].platform == "Trustpilot"
    assert block.ratings[0].verified is True
    assert block.reviews[0].stars == 5.0
    assert block.client_logos[0].asset_key == "client-logo-1"
    assert block.client_logos[0].grayscale is True


def test_absent_is_none_no_warning() -> None:
    block, warn = parse_social_proof(None)
    assert block is None
    assert warn is None


def test_empty_dict_is_empty_block_never_fabricated() -> None:
    block, warn = parse_social_proof({})
    assert warn is None
    assert block.ratings == [] and block.reviews == []
    assert block.press_logos == [] and block.client_logos == []


def test_partial_only_ratings() -> None:
    block, warn = parse_social_proof({"ratings": [{"platform": "Google", "score": 4.9}]})
    assert warn is None
    assert block.ratings[0].score == 4.9
    assert block.reviews == []


def test_bad_shape_returns_warning() -> None:
    block, warn = parse_social_proof({"ratings": "not-a-list"})
    assert block is None
    assert warn is not None


def test_models_construct_directly() -> None:
    assert RatingCard(platform="Capterra", score=4.7).max_score == 5.0
    assert ReviewCard(name="A").stars is None
