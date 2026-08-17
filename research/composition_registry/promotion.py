"""Auditable promotion records for composition families."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


PromotionState = Literal[
    "experimental",
    "curated_candidate",
    "corpus_tested",
    "client_tested",
    "promoted",
]
_STATE_ORDER = (
    "experimental",
    "curated_candidate",
    "corpus_tested",
    "client_tested",
    "promoted",
)


class StrictFrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class MatrixResult(StrictFrozenModel):
    sample_id: str = Field(min_length=1)
    passed: bool
    failure_codes: tuple[str, ...] = ()


class HumanRatingSummary(StrictFrozenModel):
    rater_count: int = Field(ge=0)
    mean_score: float = Field(ge=1, le=5)
    threshold: float = Field(ge=1, le=5)
    accepted: bool


class AtlasComparison(StrictFrozenModel):
    """A recorded comparison of a candidate face against one atlas face."""

    atlas_face_id: str = Field(min_length=1)
    candidate_raster_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    accepted: bool
    notes: str = Field(min_length=1)


class PromotionRecord(StrictFrozenModel):
    schema_version: Literal["1.0"] = "1.0"
    artifact_kind: Literal["composition_family", "design_policy"]
    artifact_id: str = Field(min_length=1)
    old_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    new_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    from_state: PromotionState
    to_state: PromotionState
    rationale: str = Field(min_length=1)
    golden_hashes: dict[str, str]
    test_matrix: tuple[MatrixResult, ...] = Field(min_length=1)
    deterministic_gate_results: dict[str, int]
    human_rating_summary: HumanRatingSummary
    atlas_comparisons: tuple[AtlasComparison, ...] = ()
    approver: str = Field(min_length=1)


def _version_tuple(version: str) -> tuple[int, int, int]:
    return tuple(int(part) for part in version.split("."))  # type: ignore[return-value]


def promote(record: PromotionRecord) -> PromotionState:
    if record.from_state == "promoted" and record.old_version == record.new_version:
        raise ValueError("promoted versions are immutable")
    if _version_tuple(record.new_version) <= _version_tuple(record.old_version):
        raise ValueError("promotion requires a new semantic version")
    if _STATE_ORDER.index(record.to_state) != _STATE_ORDER.index(record.from_state) + 1:
        raise ValueError("promotion must advance exactly one state")
    if not record.test_matrix or any(not item.passed for item in record.test_matrix):
        raise ValueError("promotion matrix contains failures")
    if record.to_state == "client_tested" and all(
        item.sample_id.startswith("calibration.") for item in record.test_matrix
    ):
        raise ValueError(
            "client_tested promotion requires at least one real client sample: "
            "a matrix of only synthetic calibration.* fixtures cannot prove "
            "client testing"
        )
    if record.deterministic_gate_results.get("hard_failure_count", 0) != 0:
        raise ValueError("deterministic hard failures block promotion")
    human = record.human_rating_summary
    if (
        human.rater_count < 2
        or not human.accepted
        or human.mean_score < human.threshold
    ):
        raise ValueError("human calibration does not support promotion")
    if record.artifact_kind == "composition_family":
        if not record.atlas_comparisons or any(
            not comparison.accepted for comparison in record.atlas_comparisons
        ):
            raise ValueError(
                "family promotion requires accepted atlas comparisons for its "
                "linked reference faces"
            )
    return record.to_state
