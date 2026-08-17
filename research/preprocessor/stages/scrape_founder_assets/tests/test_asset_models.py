"""Tests for the asset-understanding models (Task 1).

`AssetJudgement` is the structured VIS verdict for a single scraped asset
(its role + whether it carries overlaid text + a 0-3 visual-appeal rank).
`RoutedElement` is the router's per-element outcome (filled with a real asset,
or flagged when no suitable real asset exists — never fabricated).

Shapes only; brand-agnostic.
"""
from __future__ import annotations

from stages.scrape_founder_assets.models import (
    ASSET_ROLES,
    AssetJudgement,
    RoutedElement,
)


def test_asset_judgement_defaults_and_roles():
    j = AssetJudgement(role="founder_working", has_overlaid_text=False, visual_appeal=3)
    assert j.role == "founder_working" and j.visual_appeal == 3 and j.notes == ""
    assert "founder_portrait" in ASSET_ROLES and "content_card" in ASSET_ROLES


def test_routed_element_shape():
    r = RoutedElement(
        element="cover_hero",
        status="filled",
        path="/x.jpg",
        role="founder_portrait",
        appeal=3,
    )
    assert r.status == "filled" and r.role == "founder_portrait"
    r2 = RoutedElement(element="team", status="flagged", reason="no suitable asset")
    assert r2.status == "flagged" and r2.path is None
