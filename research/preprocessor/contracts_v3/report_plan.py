from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .units import DocumentUnits


class NarrativeRole(str, Enum):
    COVER = "cover"
    OUTLOOK = "outlook"
    ABOUT = "about"
    STATUS_QUO = "status_quo"
    FALSE_BELIEFS = "false_beliefs"
    CASE_STUDY = "case_study"
    THEORY = "theory"
    MECHANISM = "mechanism"
    TRUST_PROOF = "trust_proof"
    SUMMARY = "summary"
    OBJECTIONS = "objections"
    COLLABORATION = "collaboration"
    CTA = "cta"
    BRAND_BREATHER = "brand_breather"


class DensityBand(str, Enum):
    LIGHT = "light"
    MODERATE = "moderate"
    DENSE = "dense"
    VERY_DENSE = "very_dense"


class ProofType(str, Enum):
    CLAIM = "claim"
    TRUST = "trust"
    CASE_RESULT = "case_result"
    SOURCE = "source"


class ProofRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    requirement_id: str = Field(min_length=1)
    proof_type: ProofType
    claim_ids: tuple[str, ...] = ()
    required_for_ship: bool = True


class AssetRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    requirement_id: str = Field(min_length=1)
    semantic_class: Literal[
        "identity",
        "proof",
        "product",
        "process",
        "context",
        "decoration",
        "texture",
        "logo",
        "qr",
        "source",
    ]
    required_for_ship: bool = True
    allowed_substitutions: tuple[
        Literal[
            "identity",
            "proof",
            "product",
            "process",
            "context",
            "decoration",
            "texture",
            "logo",
            "qr",
            "source",
        ],
        ...,
    ] = ()
    min_print_dpi: float = Field(default=240.0, gt=0)


class FacePlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    face_id: str = Field(min_length=1)
    face_index: int = Field(gt=0)
    role: NarrativeRole
    narrative_act: str = Field(min_length=1)
    argument: str = Field(min_length=1)
    claim_ids: tuple[str, ...] = ()
    proof_requirements: tuple[ProofRequirement, ...] = ()
    asset_requirements: tuple[AssetRequirement, ...] = ()
    dominant_mechanism: str = Field(min_length=1)
    density_band: DensityBand
    transition_in: str | None = None
    transition_out: str | None = None
    case_id: str | None = None
    theory_for_case_id: str | None = None
    legacy_st_type: str | None = None

    @model_validator(mode="after")
    def validate_case_identity(self) -> "FacePlan":
        if self.role is NarrativeRole.CASE_STUDY and not self.case_id:
            raise ValueError("case study face requires case_id")
        if self.role is not NarrativeRole.CASE_STUDY and self.case_id:
            raise ValueError("case_id is only valid for case study faces")
        return self


class SpreadPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    spread_id: str = Field(min_length=1)
    fragment_id: str = Field(min_length=1)
    left_face_id: str = Field(min_length=1)
    right_face_id: str = Field(min_length=1)


class ProductProfileException(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    profile_id: str = Field(min_length=1)
    approved_by: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class ProductProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    profile_id: str = Field(min_length=1)
    schema_version: Literal["3.0"] = "3.0"
    face_count: int = Field(gt=0)
    case_count: int = Field(gt=0)
    min_theory_faces: int = Field(ge=0)
    required_roles: tuple[NarrativeRole, ...]
    require_trust_evidence: bool
    cover_must_be_first: bool
    cta_must_be_last: bool
    exception_policy: str = Field(min_length=1)


class DesignFeaturesV3(BaseModel):
    """Client-specific editorial and visual-brand features.

    These are selection inputs, not decoration: composition planning scores
    every candidate family and variant against them so materially different
    clients stop collapsing into identical plans.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    tone_tokens: tuple[str, ...] = Field(min_length=1)
    brand_energy: Literal["restrained", "balanced", "expressive"]
    imagery_density: Literal["sparse", "moderate", "rich"]
    chart_opportunity: Literal["none", "low", "moderate", "high"]


class ReportPlanV3(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["3.0"] = "3.0"
    product_profile_id: str = Field(min_length=1)
    units: DocumentUnits
    faces: tuple[FacePlan, ...] = Field(min_length=1)
    spreads: tuple[SpreadPlan, ...] = ()
    audience: str = Field(min_length=1)
    central_thesis: str = Field(min_length=1)
    promise: str = Field(min_length=1)
    tone_profile: str = Field(min_length=1)
    source_coverage: tuple[str, ...] = ()
    design_features: DesignFeaturesV3 | None = None
    exception: ProductProfileException | None = None

    @model_validator(mode="after")
    def validate_units_and_faces(self) -> "ReportPlanV3":
        planned_face_ids = [face.face_id for face in self.faces]
        allocated_face_ids = [
            face_id for allocation in self.units.allocations for face_id in allocation.face_ids
        ]
        if planned_face_ids != allocated_face_ids:
            raise ValueError("face plan ids must match allocated face ids in order")
        expected_indices = list(range(1, len(self.faces) + 1))
        if [face.face_index for face in self.faces] != expected_indices:
            raise ValueError("face indices must be consecutive from one")
        return self


class PlanFailure(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(min_length=1)
    detail: str = Field(min_length=1)


class PlanValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    failures: tuple[PlanFailure, ...] = ()

    @property
    def codes(self) -> tuple[str, ...]:
        return tuple(failure.code for failure in self.failures)


def load_product_profile(path: Path) -> ProductProfile:
    return ProductProfile.model_validate(json.loads(path.read_text()))


def validate_house_plan(plan: ReportPlanV3, profile: ProductProfile) -> PlanValidationResult:
    failures: list[PlanFailure] = []

    if plan.units.face_count != profile.face_count:
        failures.append(
            PlanFailure(
                code="face_count_mismatch",
                detail=f"profile requires {profile.face_count} faces, got {plan.units.face_count}",
            )
        )

    case_count = sum(face.role is NarrativeRole.CASE_STUDY for face in plan.faces)
    if case_count != profile.case_count:
        failures.append(
            PlanFailure(
                code="case_count_mismatch",
                detail=f"profile requires {profile.case_count} cases, got {case_count}",
            )
        )

    theory_count = sum(face.role is NarrativeRole.THEORY for face in plan.faces)
    if theory_count < profile.min_theory_faces:
        failures.append(
            PlanFailure(
                code="theory_count_too_low",
                detail=f"profile requires at least {profile.min_theory_faces} theory faces",
            )
        )

    present_roles = {face.role for face in plan.faces}
    for role in profile.required_roles:
        if role not in present_roles:
            failures.append(
                PlanFailure(code="required_role_missing", detail=f"missing required role {role.value}")
            )

    if profile.cover_must_be_first and plan.faces[0].role is not NarrativeRole.COVER:
        failures.append(PlanFailure(code="cover_not_first", detail="cover must be face one"))
    if profile.cta_must_be_last and plan.faces[-1].role is not NarrativeRole.CTA:
        failures.append(PlanFailure(code="cta_not_last", detail="CTA must be the final face"))

    has_trust = any(
        requirement.proof_type is ProofType.TRUST
        for face in plan.faces
        for requirement in face.proof_requirements
    )
    if profile.require_trust_evidence and not has_trust:
        failures.append(
            PlanFailure(code="trust_evidence_missing", detail="profile requires trust evidence")
        )

    if plan.product_profile_id != profile.profile_id:
        if plan.exception is None:
            failures.append(
                PlanFailure(
                    code="profile_exception_missing",
                    detail="a non-house profile requires an approved exception",
                )
            )
        elif plan.exception.profile_id == profile.profile_id:
            failures.append(
                PlanFailure(
                    code="profile_exception_invalid",
                    detail="exception profile_id must differ from the house profile",
                )
            )

    return PlanValidationResult(failures=tuple(failures))
