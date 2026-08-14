from __future__ import annotations

import json
from pathlib import Path

import pytest

from contracts_v3.report_plan import (
    DensityBand,
    FacePlan,
    NarrativeRole,
    ProofRequirement,
    ProofType,
    load_product_profile,
)
from pipeline_v3 import PrecompositionBlocked, build_precomposition_bundle_v3
from stages.plan_editorial_v3 import legacy_report_to_editorial_brief


ROOT = Path(__file__).resolve().parents[3]
POLICY = ROOT / "research" / "preprocessor" / "policies" / "dmc_house_20_face.json"
CHRISTOPH = ROOT / "dmc-renderer" / "fixtures" / "christoph_v5_payload.json"


ROLES = (
    NarrativeRole.COVER,
    NarrativeRole.OUTLOOK,
    NarrativeRole.ABOUT,
    NarrativeRole.STATUS_QUO,
    NarrativeRole.FALSE_BELIEFS,
    NarrativeRole.CASE_STUDY,
    NarrativeRole.THEORY,
    NarrativeRole.CASE_STUDY,
    NarrativeRole.THEORY,
    NarrativeRole.CASE_STUDY,
    NarrativeRole.THEORY,
    NarrativeRole.MECHANISM,
    NarrativeRole.TRUST_PROOF,
    NarrativeRole.THEORY,
    NarrativeRole.SUMMARY,
    NarrativeRole.OBJECTIONS,
    NarrativeRole.COLLABORATION,
    NarrativeRole.STATUS_QUO,
    NarrativeRole.OUTLOOK,
    NarrativeRole.CTA,
)


def valid_brief() -> dict:
    case_number = 0
    faces = []
    for index, role in enumerate(ROLES, start=1):
        if role is NarrativeRole.CASE_STUDY:
            case_number += 1
        faces.append(
            FacePlan(
                face_id=f"face.{index:02d}",
                face_index=index,
                role=role,
                narrative_act=f"act {index}",
                argument=f"argument {index}",
                proof_requirements=(
                    (
                        ProofRequirement(
                            requirement_id="trust.primary",
                            proof_type=ProofType.TRUST,
                        ),
                    )
                    if role is NarrativeRole.TRUST_PROOF
                    else ()
                ),
                dominant_mechanism="editorial",
                density_band=DensityBand.MODERATE,
                case_id=f"case.{case_number}" if role is NarrativeRole.CASE_STUDY else None,
            ).model_dump(mode="json")
        )
    return {
        "product_profile_id": "dmc_house_20_face",
        "faces": faces,
        "formats": ["a4"] * 20,
        "audience": "German B2B founder",
        "central_thesis": "A clear thesis",
        "promise": "A grounded promise",
        "tone_profile": "Richard house",
    }


def test_valid_bundle_is_deterministic_and_versioned() -> None:
    profile = load_product_profile(POLICY)
    source_bundle = {"sources": [], "claims": [], "assets": []}

    first = build_precomposition_bundle_v3(source_bundle, valid_brief(), profile)
    second = build_precomposition_bundle_v3(source_bundle, valid_brief(), profile)

    assert first.to_stable_json() == second.to_stable_json()
    assert first.content_hash == second.content_hash
    assert first.manifest.versions.contract_schema == "3.0"
    assert first.manifest.versions.product_profile == "dmc_house_20_face"
    assert first.manifest.versions.workflow_authority == "non_workflow"
    assert set(first.manifest.artifact_hashes) == {
        "source_ledger",
        "report_plan",
        "asset_ledger",
    }


def test_christoph_is_blocked_before_composition_with_all_primary_failures() -> None:
    profile = load_product_profile(POLICY)
    report_json = json.loads(CHRISTOPH.read_text())
    brief = legacy_report_to_editorial_brief(report_json)

    with pytest.raises(PrecompositionBlocked) as error:
        build_precomposition_bundle_v3(
            {
                "sources": [],
                "claims": [],
                "assets": [],
                "report_json": report_json,
            },
            brief,
            profile,
        )

    codes = error.value.codes
    assert "ungrounded_numeric_candidate" in codes
    assert "face_count_mismatch" in codes
    assert "case_count_mismatch" in codes
    assert codes.count("missing_required") == 5
    assert all(failure.owner_stage != "composition" for failure in error.value.failures)


def test_legacy_christoph_brief_preserves_declared_faces_and_cases() -> None:
    report_json = json.loads(CHRISTOPH.read_text())

    brief = legacy_report_to_editorial_brief(report_json)

    assert len(brief["faces"]) == 23
    assert brief["formats"] == ["a4"] * 23
    assert sum(face["role"] == "case_study" for face in brief["faces"]) == 5
    assert sum(
        requirement["semantic_class"] == "identity"
        for face in brief["faces"]
        for requirement in face["asset_requirements"]
    ) == 5


@pytest.mark.parametrize(
    ("legacy_type", "expected_role"),
    (
        ("ST-08", "objections"),
        ("ST-31", "brand_breather"),
        ("ST-32", "brand_breather"),
    ),
)
def test_legacy_bridge_maps_complete_established_grammar(
    legacy_type: str,
    expected_role: str,
) -> None:
    brief = legacy_report_to_editorial_brief(
        {
            "meta": {},
            "pages": [
                {
                    "slot": 1,
                    "type": legacy_type,
                    "page_numbers": "1",
                    "data": {"titel": "Known grammar face"},
                }
            ],
        }
    )

    assert brief["faces"][0]["role"] == expected_role
