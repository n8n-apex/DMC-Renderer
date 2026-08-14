"""A ground is the sheet's surface, declared per face."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from contracts_v3.render_contract import (
    BodyElement,
    CompositionAssignment,
    ExpectedMaterialization,
    FrozenRenderContractV3,
    RegionAssignment,
    RenderFragmentV3,
)


def _fragment(**overrides) -> RenderFragmentV3:
    body = BodyElement(
        element_id="face.01.narrative.body.01",
        region_id="narrative",
        content_ref="content.face.01.narrative.01",
        required_visibility=True,
    )
    base = dict(
        fragment_id="fragment.01",
        format="a4",
        face_ids=("face.01",),
        composition=CompositionAssignment(
            family_id="editorial_lead", family_version="1.1.0",
            variant_id="photo_bleed", theme_id="light",
        ),
        elements=(body,),
        region_assignments=(
            RegionAssignment(region_id="narrative", element_ids=(body.element_id,)),
        ),
        expected_materialization=ExpectedMaterialization(
            required_element_ids=(body.element_id,), minimum_font_pt={},
        ),
    )
    base.update(overrides)
    return RenderFragmentV3(**base)


def test_a_fragment_needs_no_ground() -> None:
    """Most faces sit on the paper itself."""
    assert _fragment().face_grounds == ()


def test_a_ground_must_cover_every_face_or_none() -> None:
    """An A3 spread with one ground named would silently dress half a sheet."""
    with pytest.raises(ValidationError):
        _fragment(
            format="a3",
            face_ids=("face.01", "face.02"),
            face_grounds=("asset.ground",),
        )


def test_a_ground_must_be_a_declared_asset() -> None:
    """A background pointing at nothing renders a blank face, silently."""
    with pytest.raises(ValidationError):
        FrozenRenderContractV3(
            contract_id="c1", mode="ship", product_profile_id="p",
            fragments=(_fragment(face_grounds=("asset.ground.paper",)),),
            content_refs=("content.face.01.narrative.01",),
            claim_refs=(), asset_refs=(),   # ground not declared
            artifact_hashes={},
        )


def test_a_declared_ground_is_accepted() -> None:
    contract = FrozenRenderContractV3(
        contract_id="c1", mode="ship", product_profile_id="p",
        fragments=(_fragment(face_grounds=("asset.ground.paper",)),),
        content_refs=("content.face.01.narrative.01",),
        claim_refs=(), asset_refs=("asset.ground.paper",),
        artifact_hashes={},
    )

    assert contract.fragments[0].face_grounds == ("asset.ground.paper",)


def test_the_same_ground_may_dress_every_face_of_a_spread() -> None:
    """Buchagentur places ONE texture on nine consecutive faces."""
    fragment = _fragment(
        format="a3",
        face_ids=("face.01", "face.02"),
        face_grounds=("asset.ground.paper", "asset.ground.paper"),
    )

    assert len(set(fragment.face_grounds)) == 1
