"""Typed release states and owner-addressed quality failures."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ReleaseState(str, Enum):
    REJECTED = "rejected"
    DRAFT = "draft"
    REVIEW_CANDIDATE = "review_candidate"
    REVIEW_REQUIRED = "review_required"
    SHIP_READY = "ship_ready"


class ReviewVerdict(str, Enum):
    PASSED = "passed"
    REJECTED = "rejected"
    UNREVIEWABLE = "unreviewable"


class ReviewAttemptRecord(BaseModel):
    """One immutable build+review attempt in the retry trail.

    A human reading the review_required result must be able to reconstruct
    exactly what was built, what each page scored, what the conductor
    proposed, and how the attempt ended - without re-running anything.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    attempt_index: int = Field(ge=1)
    contract_sha256: str = Field(min_length=64, max_length=64)
    render_sha256: str = Field(min_length=64, max_length=64)
    page_scores: dict[str, dict] = Field(default_factory=dict)
    conductor_summary: str = ""
    verdict: ReviewVerdict


class FailureSeverity(str, Enum):
    HARD = "hard"
    DRAFT = "draft"
    REVIEW = "review"


class FailureOwner(str, Enum):
    ADAPTER = "adapter"
    SOURCE_LEDGER = "source_ledger"
    EDITORIAL = "editorial_planning"
    ASSETS = "assets"
    COMPOSITION = "composition_planner"
    CONTRACT = "contract_materializer"
    RENDERER = "renderer"
    MATERIALIZATION = "materialization"
    PIXELS = "pixels"
    VISUAL_REVIEW = "visual_review"
    DIGITAL_EXPORT = "digital_export"
    PRINT_EXPORT = "print_export"
    WORKFLOW = "workflow"
    QUALITY_GATE = "quality_gate"


class QualityFailure(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    owner_stage: FailureOwner
    code: str = Field(min_length=1)
    severity: FailureSeverity
    face_ids: tuple[str, ...] = ()
    element_ids: tuple[str, ...] = ()
    remediation_class: str = Field(min_length=1)
    detail: str = Field(min_length=1)


class GateResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "3.0"
    state: ReleaseState
    failures: tuple[QualityFailure, ...]
    deterministic_checks_complete: bool
    visual_review_complete: bool
    visual_threshold_calibrated: bool

    @property
    def failure_codes(self) -> tuple[str, ...]:
        return tuple(failure.code for failure in self.failures)
