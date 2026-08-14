from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from contracts_v3.report_plan import (
    DensityBand,
    FacePlan,
    NarrativeRole,
    ProductProfileException,
    ProofRequirement,
    ProofType,
    ReportPlanV3,
    load_product_profile,
    validate_house_plan,
)
from contracts_v3.units import DocumentUnits


ROOT = Path(__file__).resolve().parents[3]
ATLAS = ROOT / "research" / "reference-atlas" / "reference-atlas.json"
POLICY = ROOT / "research" / "preprocessor" / "policies" / "dmc_house_20_face.json"


def atlas() -> dict:
    return json.loads(ATLAS.read_text())


def test_all_six_reference_reports_have_twenty_physical_faces() -> None:
    reports = atlas()["reports"]

    assert len(reports) == 6
    assert {report["physical_faces"] for report in reports} == {20}


def test_all_six_reference_reports_have_exactly_three_case_faces() -> None:
    data = atlas()
    counts = {
        report["slug"]: sum(
            face["role"] == "case_study"
            for face in data["faces"]
            if face["report"] == report["slug"]
        )
        for report in data["reports"]
    }

    assert counts == {
        "apex": 3,
        "buchagentur": 3,
        "alexander": 3,
        "werkzeug": 3,
        "niklas": 3,
        "aerzte": 3,
    }


def _atlas_plan(
    *,
    product_profile_id: str,
    exception: ProductProfileException | None,
) -> ReportPlanV3:
    apex_faces = [face for face in atlas()["faces"] if face["report"] == "apex"]
    case_number = 0
    faces = []
    for index, source_face in enumerate(apex_faces, start=1):
        role = NarrativeRole(source_face["role"])
        if role is NarrativeRole.CASE_STUDY:
            case_number += 1
        faces.append(
            FacePlan(
                face_id=f"face.{index:02d}",
                face_index=index,
                role=role,
                narrative_act=source_face["cadence_function"],
                argument=source_face["title"],
                proof_requirements=(
                    (
                        ProofRequirement(
                            requirement_id="trust.primary",
                            proof_type=ProofType.TRUST,
                        ),
                    )
                    if role in {NarrativeRole.ABOUT, NarrativeRole.TRUST_PROOF}
                    else ()
                ),
                dominant_mechanism=source_face["visual_mechanism"],
                density_band=DensityBand(source_face["density_band"]),
                case_id=f"case.{case_number}" if role is NarrativeRole.CASE_STUDY else None,
            )
        )
    return ReportPlanV3(
        product_profile_id=product_profile_id,
        units=DocumentUnits.from_formats(["a4"] * 20),
        faces=tuple(faces),
        audience="German B2B founder",
        central_thesis="A grounded thesis",
        promise="A grounded promise",
        tone_profile="Richard house",
        exception=exception,
    )


def test_profile_exception_requires_approval_reason_and_non_house_id() -> None:
    profile = load_product_profile(POLICY)

    with pytest.raises(ValidationError):
        ProductProfileException.model_validate({"profile_id": "custom"})

    invalid = ProductProfileException(
        profile_id=profile.profile_id,
        approved_by="Richard",
        reason="Named product exception",
    )
    result = validate_house_plan(
        _atlas_plan(product_profile_id="custom", exception=invalid),
        profile,
    )
    assert "profile_exception_invalid" in result.codes

    approved = invalid.model_copy(update={"profile_id": "custom"})
    assert validate_house_plan(
        _atlas_plan(product_profile_id="custom", exception=approved),
        profile,
    ).failures == ()
