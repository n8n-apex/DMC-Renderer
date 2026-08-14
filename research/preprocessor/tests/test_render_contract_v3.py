from __future__ import annotations

import pytest
from pydantic import ValidationError

from contracts_v3.render_contract import (
    BodyElement,
    CompositionAssignment,
    ExpectedMaterialization,
    FrozenRenderContractV3,
    HeadingElement,
    ImageElement,
    RegionAssignment,
    RenderFragmentV3,
    StatElement,
)


def fragment_payload(*, format: str = "a4", face_ids: list[str] | None = None) -> dict:
    return {
        "fragment_id": "fragment.01",
        "format": format,
        "face_ids": face_ids or ["face.01"],
        "composition": {
            "family_id": "editorial_lead",
            "family_version": "1.0.0",
            "variant_id": "proof_rail",
            "theme_id": "light",
        },
        "elements": [
            {
                "kind": "heading",
                "element_id": "face.01.heading",
                "region_id": "headline",
                "content_ref": "content.face.01.title",
                "level": 1,
                "required_visibility": True,
            }
        ],
        "region_assignments": [
            {"region_id": "headline", "element_ids": ["face.01.heading"]}
        ],
        "expected_materialization": {
            "required_element_ids": ["face.01.heading"],
            "minimum_font_pt": {"face.01.heading": 28.0},
        },
    }


def test_stat_requires_claim_reference() -> None:
    with pytest.raises(ValidationError, match="claim_id"):
        StatElement(
            element_id="case.result",
            region_id="proof",
            value="83%",
            label="Zeitersparnis",
            required_visibility=True,
        )


def test_unknown_elements_are_forbidden() -> None:
    payload = fragment_payload()
    payload["elements"] = [
        {
            "kind": "magic_widget",
            "element_id": "magic",
            "region_id": "headline",
            "text": "x",
            "required_visibility": True,
        }
    ]

    with pytest.raises(ValidationError):
        RenderFragmentV3.model_validate(payload)


def test_image_rejects_inline_asset_path() -> None:
    with pytest.raises(ValidationError, match="asset_id"):
        ImageElement(
            element_id="case.image",
            region_id="proof",
            asset_path="/tmp/client.png",
            alt_content_ref="content.case.alt",
            required_visibility=True,
        )


def test_free_text_number_is_not_a_content_reference() -> None:
    with pytest.raises(ValidationError):
        StatElement(
            element_id="case.result",
            region_id="proof",
            claim_id="claim.result",
            label_content_ref="content.case.result_label",
            value="83%",
            required_visibility=True,
        )


def test_required_visibility_must_be_explicit() -> None:
    with pytest.raises(ValidationError, match="required_visibility"):
        HeadingElement(
            element_id="face.01.heading",
            region_id="headline",
            content_ref="content.face.01.title",
            level=1,
        )


def test_a3_fragment_requires_two_face_ids() -> None:
    with pytest.raises(ValidationError, match="a3 requires 2 face ids"):
        RenderFragmentV3.model_validate(
            fragment_payload(format="a3", face_ids=["face.01"])
        )


def test_strict_valid_contract_preserves_only_references() -> None:
    fragment = RenderFragmentV3.model_validate(fragment_payload())
    contract = FrozenRenderContractV3(
        contract_id="contract.synthetic",
        mode="ship",
        product_profile_id="dmc_house_20_face",
        fragments=(fragment,),
        content_refs=("content.face.01.title",),
        claim_refs=(),
        asset_refs=(),
        artifact_hashes={
            "source_ledger": "a" * 64,
            "report_plan": "b" * 64,
            "asset_ledger": "c" * 64,
            "family_registry": "d" * 64,
            "composition_policy": "e" * 64,
        },
    )

    assert contract.fragments[0].elements[0].content_ref == "content.face.01.title"
    with pytest.raises(ValidationError):
        BodyElement(
            element_id="body",
            region_id="narrative",
            content_ref="content.body",
            text="duplicated copy",
            required_visibility=True,
        )


def test_all_element_kinds_are_discriminated_and_strict() -> None:
    payload = fragment_payload()
    payload["elements"] = [
        {"kind":"heading","element_id":"e.heading","region_id":"r","content_ref":"content.heading","level":2,"required_visibility":True},
        {"kind":"body","element_id":"e.body","region_id":"r","content_ref":"content.body","required_visibility":True},
        {"kind":"quote","element_id":"e.quote","region_id":"r","content_ref":"content.quote","claim_id":"claim.quote","required_visibility":True},
        {"kind":"stat","element_id":"e.stat","region_id":"r","claim_id":"claim.stat","label_content_ref":"content.stat.label","required_visibility":True},
        {"kind":"comparison","element_id":"e.comparison","region_id":"r","left_content_refs":["content.left"],"right_content_refs":["content.right"],"claim_ids":[],"required_visibility":True},
        {"kind":"process","element_id":"e.process","region_id":"r","item_content_refs":["content.step.1"],"required_visibility":True},
        {"kind":"image","element_id":"e.image","region_id":"r","asset_id":"asset.image","alt_content_ref":"content.image.alt","required_visibility":True},
        {"kind":"source","element_id":"e.source","region_id":"r","claim_id":"claim.source","content_ref":"content.source","required_visibility":True},
        {"kind":"qr","element_id":"e.qr","region_id":"r","asset_id":"asset.qr","destination_content_ref":"content.url","required_visibility":True},
        {"kind":"divider","element_id":"e.divider","region_id":"r","required_visibility":False},
        {"kind":"group","element_id":"e.group","region_id":"r","child_element_ids":["e.heading","e.body"],"required_visibility":True}
    ]
    payload["region_assignments"] = [
        {"region_id": "r", "element_ids": [item["element_id"] for item in payload["elements"]]}
    ]
    payload["expected_materialization"] = {
        "required_element_ids": [
            item["element_id"]
            for item in payload["elements"]
            if item["required_visibility"]
        ],
        "minimum_font_pt": {},
    }

    fragment = RenderFragmentV3.model_validate(payload)

    assert [element.kind for element in fragment.elements] == [
        "heading", "body", "quote", "stat", "comparison", "process",
        "image", "source", "qr", "divider", "group",
    ]


def test_assignment_models_forbid_unknown_fields() -> None:
    CompositionAssignment(
        family_id="editorial_lead",
        family_version="1.0.0",
        variant_id="proof_rail",
        theme_id="light",
    )
    RegionAssignment(region_id="headline", element_ids=("heading",))
    ExpectedMaterialization(required_element_ids=("heading",), minimum_font_pt={})

    with pytest.raises(ValidationError):
        RegionAssignment.model_validate(
            {"region_id": "headline", "element_ids": ["heading"], "magic": True}
        )
