from __future__ import annotations

import json
import sys
from pathlib import Path

import fitz
import pytest
from pydantic import ValidationError


RENDERER_ROOT = Path(__file__).resolve().parent.parent
RESEARCH_ROOT = RENDERER_ROOT.parent
PREPROCESSOR_ROOT = RESEARCH_ROOT / "preprocessor"
for path in (RENDERER_ROOT, RESEARCH_ROOT, PREPROCESSOR_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from composition_registry.registry import load_registry  # noqa: E402
from contracts_v3.render_contract import FrozenRenderContractV3  # noqa: E402
from contract_loader_v3 import ContractLoadFailure, load_render_contract  # noqa: E402
from families.registry import FamilyRendererRegistry, default_registry  # noqa: E402
from render_v3 import (  # noqa: E402
    RenderBundleV3,
    RenderFailureV3,
    render_contract_html,
    render_v3,
)


ROOT = Path(__file__).resolve().parents[3]
REGISTRY_PATH = (
    ROOT / "research" / "composition_registry" / "families" / "dmc-v1.json"
)
ATLAS_PATH = ROOT / "research" / "reference-atlas" / "reference-atlas.json"


def contract_payload(
    *,
    mode: str = "ship",
    family_id: str = "editorial_lead",
    family_version: str = "1.4.0",
    variant_id: str = "proof_rail",
    fallback_family_id: str | None = None,
) -> dict:
    fragment = {
        "fragment_id": "fragment.01",
        "format": "a4",
        "face_ids": ["face.01"],
        "composition": {
            "family_id": family_id,
            "family_version": family_version,
            "variant_id": variant_id,
            "theme_id": "light",
        },
        "elements": [
            {
                "kind": "heading",
                "element_id": "face.01.headline.heading.01",
                "region_id": "headline",
                "content_ref": "content.face.01.title",
                "level": 1,
                "required_visibility": True,
            }
        ],
        "region_assignments": [
            {
                "region_id": "headline",
                "element_ids": ["face.01.headline.heading.01"],
            }
        ],
        "expected_materialization": {
            "required_element_ids": ["face.01.headline.heading.01"],
            "minimum_font_pt": {"face.01.headline.heading.01": 28},
        },
    }
    if fallback_family_id is not None:
        fragment["fallback_family_id"] = fallback_family_id
    return {
        "schema_version": "3.0",
        "contract_id": "contract.fixture",
        "mode": mode,
        "product_profile_id": "dmc_house_20_face",
        "fragments": [fragment],
        "content_refs": ["content.face.01.title"],
        "claim_refs": [],
        "asset_refs": [],
        "artifact_hashes": {"contract_payload": "a" * 64},
    }


def bundle() -> RenderBundleV3:
    return RenderBundleV3(
        content_by_ref={"content.face.01.title": "Eine klare Leitidee"},
        claim_values={},
        asset_paths={},
    )


def registry_model():
    return load_registry(REGISTRY_PATH, atlas_path=ATLAS_PATH)


def test_ship_loader_rejects_unknown_family() -> None:
    contract = FrozenRenderContractV3.model_validate(
        contract_payload(family_id="unregistered_family")
    )

    with pytest.raises(ContractLoadFailure, match="unknown_family"):
        load_render_contract(contract, registry_model())


def test_contract_rejects_missing_family_version() -> None:
    payload = contract_payload()
    del payload["fragments"][0]["composition"]["family_version"]

    with pytest.raises(ValidationError, match="family_version"):
        FrozenRenderContractV3.model_validate(payload)


def test_loader_rejects_unsupported_variant() -> None:
    contract = FrozenRenderContractV3.model_validate(
        contract_payload(variant_id="invented_variant")
    )

    with pytest.raises(ContractLoadFailure, match="unsupported_variant"):
        load_render_contract(contract, registry_model())


def test_html_uses_exact_family_dispatch_and_semantic_attributes() -> None:
    contract = FrozenRenderContractV3.model_validate(contract_payload())

    result = render_contract_html(
        contract,
        bundle(),
        registry_model(),
        renderer_registry=default_registry(),
    )

    assert 'data-family-id="editorial_lead"' in result.html
    assert 'data-element-id="face.01.headline.heading.01"' in result.html
    assert 'data-content-ref="content.face.01.title"' in result.html
    assert "Eine klare Leitidee" in result.html
    assert "ST-01" not in result.html


def test_ship_mode_propagates_family_render_exception() -> None:
    contract = FrozenRenderContractV3.model_validate(contract_payload())
    renderers = default_registry()

    def fail(*args, **kwargs):
        raise RuntimeError("synthetic family failure")

    renderers.register(("editorial_lead", "1.4.0"), fail, replace=True)

    with pytest.raises(RenderFailureV3) as caught:
        render_contract_html(
            contract,
            bundle(),
            registry_model(),
            renderer_registry=renderers,
        )

    assert caught.value.code == "family_render_failed"
    assert caught.value.owner_stage == "renderer"


def test_draft_mode_uses_only_named_fallback_and_records_degradation() -> None:
    contract = FrozenRenderContractV3.model_validate(
        contract_payload(mode="draft", fallback_family_id="theory_interpretation")
    )
    renderers = default_registry()

    def fail(*args, **kwargs):
        raise RuntimeError("synthetic family failure")

    renderers.register(("editorial_lead", "1.4.0"), fail, replace=True)
    result = render_contract_html(
        contract,
        bundle(),
        registry_model(),
        renderer_registry=renderers,
    )

    assert result.degradations[0].from_family_id == "editorial_lead"
    assert result.degradations[0].to_family_id == "theory_interpretation"
    assert 'data-family-id="theory_interpretation"' in result.html


def test_renderer_writes_raw_pdf_png_html_and_metadata(tmp_path: Path) -> None:
    contract = FrozenRenderContractV3.model_validate(contract_payload())

    result = render_v3(
        contract,
        bundle(),
        registry_model(),
        output_dir=tmp_path,
    )

    assert result.raw_pdf_path.name == "report.raw.pdf"
    assert result.raw_pdf_path.is_file()
    assert result.html_path.is_file()
    assert result.metadata_path.is_file()
    assert len(result.png_paths) == 1
    assert fitz.open(result.raw_pdf_path).page_count == 1
    metadata = json.loads(result.metadata_path.read_text(encoding="utf-8"))
    assert metadata["ghostscript_invoked"] is False


def test_brand_accent_flows_from_bundle_into_rendered_css() -> None:
    contract = FrozenRenderContractV3.model_validate(contract_payload())
    blue = RenderBundleV3(
        content_by_ref={"content.face.01.title": "Eine klare Leitidee"},
        claim_values={},
        asset_paths={},
        brand_accent="#4080a0",
    )

    result = render_contract_html(contract, blue, registry_model())

    assert "--accent: #4080a0" in result.html
    assert "--accent: #c94e2c" not in result.html

    default = render_contract_html(contract, bundle(), registry_model())
    assert "--accent: #c94e2c" in default.html


def test_invalid_brand_accent_is_rejected_not_defaulted() -> None:
    import pytest as pytest_module
    from pydantic import ValidationError

    with pytest_module.raises(ValidationError):
        RenderBundleV3(
            content_by_ref={},
            claim_values={},
            asset_paths={},
            brand_accent="javascript:alert(1)",
        )
