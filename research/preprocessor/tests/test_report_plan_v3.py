from __future__ import annotations

from pathlib import Path

import pytest

from contracts_v3.report_plan import (
    AssetRequirement,
    DensityBand,
    FacePlan,
    NarrativeRole,
    ProofRequirement,
    ProofType,
    ReportPlanV3,
    load_product_profile,
    validate_house_plan,
)
from contracts_v3.source_ledger import SourceLedger
from contracts_v3.units import DocumentUnits
from stages.plan_editorial_v3 import EditorialPlanningError, plan_editorial_v3


POLICY = Path(__file__).parent.parent / "policies" / "dmc_house_20_face.json"


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


def make_faces(count: int = 20, *, case_count: int | None = None) -> tuple[FacePlan, ...]:
    roles = list(ROLES[:count])
    if count > len(roles):
        roles.extend([NarrativeRole.THEORY] * (count - len(roles)))
    if case_count is not None:
        roles = [role for role in roles if role is not NarrativeRole.CASE_STUDY]
        insert_at = min(5, len(roles))
        for _ in range(case_count):
            roles.insert(insert_at, NarrativeRole.CASE_STUDY)
            insert_at += 2
        roles = roles[:count]
        while len(roles) < count:
            roles.insert(-1, NarrativeRole.THEORY)

    case_index = 0
    faces = []
    for index, role in enumerate(roles, start=1):
        if role is NarrativeRole.CASE_STUDY:
            case_index += 1
        proof_requirements = (
            (
                ProofRequirement(
                    requirement_id="trust.primary",
                    proof_type=ProofType.TRUST,
                    required_for_ship=True,
                ),
            )
            if role is NarrativeRole.TRUST_PROOF
            else ()
        )
        faces.append(
            FacePlan(
                face_id=f"face.{index:02d}",
                face_index=index,
                role=role,
                narrative_act=f"act {index}",
                argument=f"argument {index}",
                proof_requirements=proof_requirements,
                asset_requirements=(
                    AssetRequirement(
                        requirement_id=f"face.{index:02d}.context",
                        semantic_class="context",
                        required_for_ship=False,
                    ),
                ),
                dominant_mechanism="editorial",
                density_band=DensityBand.MODERATE,
                case_id=f"case.{case_index}" if role is NarrativeRole.CASE_STUDY else None,
            )
        )
    return tuple(faces)


def make_plan(
    *,
    face_count: int = 20,
    case_count: int | None = None,
    formats: list[str] | None = None,
) -> ReportPlanV3:
    faces = make_faces(face_count, case_count=case_count)
    if formats is None:
        formats = ["a4"] * face_count
    return ReportPlanV3(
        product_profile_id="dmc_house_20_face",
        units=DocumentUnits.from_formats(formats),
        faces=faces,
        spreads=(),
        audience="German B2B founder",
        central_thesis="A clear thesis",
        promise="A grounded promise",
        tone_profile="Richard house",
    )


def test_house_profile_requires_exactly_twenty_faces() -> None:
    profile = load_product_profile(POLICY)
    result = validate_house_plan(make_plan(face_count=18), profile)

    assert "face_count_mismatch" in result.codes


def test_house_profile_requires_exactly_three_cases() -> None:
    profile = load_product_profile(POLICY)
    result = validate_house_plan(make_plan(case_count=5), profile)

    assert "case_count_mismatch" in result.codes


def test_a3_spread_occupies_two_face_indices() -> None:
    formats = ["a4"] * 9 + ["a3"] + ["a4"] * 9
    plan = make_plan(formats=formats)

    assert plan.units.face_count == 20
    assert plan.units.fragment_count == 19
    assert plan.units.allocations[9].face_ids == ("face.10", "face.11")


def test_house_profile_accepts_complete_reference_grammar() -> None:
    profile = load_product_profile(POLICY)

    assert validate_house_plan(make_plan(), profile).failures == ()


def test_missing_trust_evidence_is_a_named_failure() -> None:
    profile = load_product_profile(POLICY)
    plan = make_plan().model_copy(
        update={
            "faces": tuple(
                face.model_copy(update={"proof_requirements": ()})
                for face in make_plan().faces
            )
        }
    )

    assert "trust_evidence_missing" in validate_house_plan(plan, profile).codes


def test_editorial_planner_rejects_unknown_claim_references() -> None:
    profile = load_product_profile(POLICY)
    faces = list(make_plan().faces)
    faces[3] = faces[3].model_copy(update={"claim_ids": ("claim.missing",)})

    with pytest.raises(EditorialPlanningError) as error:
        plan_editorial_v3(
            SourceLedger(sources=(), claims=()),
            {
                "faces": [face.model_dump(mode="json") for face in faces],
                "formats": ["a4"] * 20,
                "audience": "German B2B founder",
                "central_thesis": "A clear thesis",
                "promise": "A grounded promise",
                "tone_profile": "Richard house",
            },
            profile,
        )

    assert "unknown_claim_reference" in error.value.codes
