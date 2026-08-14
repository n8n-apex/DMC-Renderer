"""Reference-grounded rubric and blind human calibration models for v3.

Automated pixel measurements (``gates/pixels_v3.py``) and blind human
judgment are kept strictly separate: this module carries the rubric that
humans rate against, the strict shape of one blind rating row, the pure
threshold-derivation function, and the loader that refuses to treat an
unapproved or null-threshold policy as calibrated. No code in this module
can create rating data; only real raters can.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


HERE = Path(__file__).resolve().parent
RESEARCH_ROOT = HERE.parent
PREPROCESSOR_ROOT = RESEARCH_ROOT / "preprocessor"
for dependency_root in (RESEARCH_ROOT, PREPROCESSOR_ROOT):
    if str(dependency_root) not in sys.path:
        sys.path.insert(0, str(dependency_root))

from composition_registry.schema import CompositionRegistry  # noqa: E402
from contracts_v3.release import (  # noqa: E402
    FailureSeverity,
    QualityFailure,
    ReleaseState,
)


DIMENSIONS = (
    "hierarchy",
    "composition",
    "typography",
    "rhythm",
    "density",
    "proof_visibility",
    "mechanism_clarity",
    "brand_coherence",
)

Dimension = Literal[
    "hierarchy",
    "composition",
    "typography",
    "rhythm",
    "density",
    "proof_visibility",
    "mechanism_clarity",
    "brand_coherence",
]


class StrictFrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RubricRow(StrictFrozenModel):
    family_id: str
    dimension: Dimension
    atlas_face_ids: tuple[str, ...] = Field(min_length=1)
    observable_facts: tuple[str, ...] = Field(min_length=1)
    review_method: Literal["measured", "blind_human"]
    weight: float = Field(gt=0)


class ReferenceRubricV3(StrictFrozenModel):
    schema_version: Literal["3.0"] = "3.0"
    rubric_id: str
    version: str
    dimensions: tuple[Dimension, ...]
    design_policy_ids: tuple[str, ...]
    rows: tuple[RubricRow, ...]


_OBSERVABLES: dict[str, tuple[str, Literal["measured", "blind_human"]]] = {
    "hierarchy": ("headline prominence and reading order are visible", "blind_human"),
    "composition": ("region occupancy and dominant geometry are visible", "blind_human"),
    "typography": ("font sizes, line lengths, and role contrast are measurable", "measured"),
    "rhythm": ("spacing intervals and density changes are visible", "blind_human"),
    "density": ("word count and occupied area are measurable", "measured"),
    "proof_visibility": ("proof element boxes and labels are visible", "measured"),
    "mechanism_clarity": ("one dominant explanatory mechanism is identifiable", "blind_human"),
    "brand_coherence": ("palette, type roles, and image treatment are consistent", "blind_human"),
}


def build_reference_rubric(registry: CompositionRegistry) -> ReferenceRubricV3:
    policy_payload = json.loads(
        (RESEARCH_ROOT / "design_policy" / "policies" / "dmc-print-v1.json").read_text(
            encoding="utf-8"
        )
    )
    validated_policy_ids = tuple(
        policy["policy_id"]
        for policy in policy_payload["policies"]
        if policy["status"] == "validated"
    )
    rows = tuple(
        RubricRow(
            family_id=family.family_id,
            dimension=dimension,
            atlas_face_ids=family.atlas_face_ids,
            observable_facts=(_OBSERVABLES[dimension][0],),
            review_method=_OBSERVABLES[dimension][1],
            weight=1.0,
        )
        for family in registry.families
        for dimension in DIMENSIONS
    )
    return ReferenceRubricV3(
        rubric_id="dmc-reference-rubric",
        version="1.0.0",
        dimensions=DIMENSIONS,
        design_policy_ids=validated_policy_ids,
        rows=rows,
    )


RatingCohort = Literal["reference", "candidate"]

_SHA256_LENGTH = 64


class BlindRatingRow(StrictFrozenModel):
    """One blind human rating of one face image against the rubric.

    Matches ``calibration/ratings.schema.json`` exactly. Rows exist only when
    a real human produced them; tests construct rows in memory and label them
    synthetic, and nothing here ever writes to ``ratings.jsonl``.
    """

    rater_id: str = Field(min_length=1)
    cohort: RatingCohort
    face_image_sha256: str
    rubric_version: str = Field(min_length=1)
    scores: dict[Dimension, int]
    overall: int = Field(ge=1, le=5)
    rated_at: str

    @field_validator("face_image_sha256")
    @classmethod
    def validate_face_hash(cls, value: str) -> str:
        if len(value) != _SHA256_LENGTH or any(
            char not in "0123456789abcdef" for char in value
        ):
            raise ValueError(
                "face_image_sha256 must be a lowercase SHA-256 hex digest"
            )
        return value

    @field_validator("rated_at")
    @classmethod
    def validate_rated_at(cls, value: str) -> str:
        datetime.fromisoformat(value)
        return value

    @model_validator(mode="after")
    def validate_scores(self) -> "BlindRatingRow":
        if set(self.scores) != set(DIMENSIONS):
            raise ValueError("rating must score every rubric dimension")
        if any(score < 1 or score > 5 for score in self.scores.values()):
            raise ValueError("dimension scores must be from 1 to 5")
        return self


class ThresholdDerivationError(ValueError):
    """The rating rows cannot honestly support a threshold."""


class ThresholdPolicyNotCalibratedError(RuntimeError):
    """The threshold policy in force is not an approved, derived policy."""


ThresholdPolicyStatus = Literal[
    "unapproved_draft",
    "derived_unapproved",
    "approved",
]


class ThresholdDerivationRecord(StrictFrozenModel):
    ratings_dataset_sha256: str | None
    derivation_code_sha256: str | None
    formula: str = Field(min_length=1)


class VisualThresholdPolicyV1(StrictFrozenModel):
    """The visual quality threshold policy, honest about its own status.

    ``unapproved_draft``   no ratings exist; every derived value is null.
    ``derived_unapproved`` mechanically derived from stored ratings, with
                           dataset and code hashes filled, but no human
                           approval yet.
    ``approved``           derived and approved by a named human; only this
                           status is calibrated. Task 4's
                           ``VisualReviewEvidenceV3`` binds the SHA-256 of
                           this file as ``threshold_policy_sha256``.
    """

    schema_version: Literal["1.0"] = "1.0"
    policy_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    status: ThresholdPolicyStatus
    rubric_version: str | None
    threshold: float | None
    derivation: ThresholdDerivationRecord
    approved_by: str | None = None
    approved_at: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def validate_status_consistency(self) -> "VisualThresholdPolicyV1":
        derived_fields = (
            self.threshold,
            self.derivation.ratings_dataset_sha256,
            self.derivation.derivation_code_sha256,
            self.rubric_version,
        )
        if self.status == "unapproved_draft":
            if any(value is not None for value in derived_fields):
                raise ValueError(
                    "an unapproved draft must not carry derived values"
                )
        else:
            if any(value is None for value in derived_fields):
                raise ValueError(
                    "a derived policy must carry threshold, rubric version, "
                    "dataset hash, and code hash"
                )
        if self.status == "approved":
            if not self.approved_by or not self.approved_at:
                raise ValueError(
                    "an approved policy must name its approver and approval time"
                )
        elif self.approved_by is not None or self.approved_at is not None:
            raise ValueError("only an approved policy may carry approval fields")
        return self

    @property
    def calibrated(self) -> bool:
        return self.status == "approved" and self.threshold is not None


_DERIVATION_FORMULA = (
    "threshold = mean(reference overall) - pooled_std(reference overall, "
    "candidate overall); pooled_std = sqrt(((n_ref - 1) * var_ref + "
    "(n_cand - 1) * var_cand) / (n_ref + n_cand - 2)) with sample variances; "
    "result clamped to [1, 5] and rounded to 3 decimals"
)


def _sample_variance(values: tuple[float, ...]) -> float:
    mean = sum(values) / len(values)
    return sum((value - mean) ** 2 for value in values) / (len(values) - 1)


def _canonical_ratings_bytes(rows: tuple[BlindRatingRow, ...]) -> bytes:
    ordered = sorted(
        rows,
        key=lambda row: (
            row.cohort,
            row.rater_id,
            row.face_image_sha256,
            row.rated_at,
        ),
    )
    lines = [
        json.dumps(
            row.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        for row in ordered
    ]
    return ("\n".join(lines) + "\n").encode("utf-8")


def derive_visual_threshold_policy(
    rows: tuple[BlindRatingRow, ...],
    *,
    policy_id: str = "dmc-visual-threshold",
    version: str = "1.0.0",
) -> dict:
    """Derive the threshold policy dict from parsed blind rating rows.

    Pure and deterministic: identical rows (in any order) produce an
    identical policy dict. Refuses to derive from fewer than two distinct
    raters per cohort, a missing cohort, or mixed rubric versions. The
    result is ``derived_unapproved``: human approval is a separate, real
    decision that code cannot make.
    """
    reference = tuple(row for row in rows if row.cohort == "reference")
    candidate = tuple(row for row in rows if row.cohort == "candidate")
    for cohort_name, cohort_rows in (
        ("reference", reference),
        ("candidate", candidate),
    ):
        raters = {row.rater_id for row in cohort_rows}
        if len(raters) < 2:
            raise ThresholdDerivationError(
                f"threshold derivation requires at least two distinct raters "
                f"in the {cohort_name} cohort; found {len(raters)}"
            )
    rubric_versions = {row.rubric_version for row in rows}
    if len(rubric_versions) != 1:
        raise ThresholdDerivationError(
            "threshold derivation requires a single rubric version across "
            f"all rows; found {sorted(rubric_versions)}"
        )

    reference_overall = tuple(float(row.overall) for row in reference)
    candidate_overall = tuple(float(row.overall) for row in candidate)
    reference_mean = sum(reference_overall) / len(reference_overall)
    pooled_variance = (
        (len(reference_overall) - 1) * _sample_variance(reference_overall)
        + (len(candidate_overall) - 1) * _sample_variance(candidate_overall)
    ) / (len(reference_overall) + len(candidate_overall) - 2)
    threshold = reference_mean - math.sqrt(pooled_variance)
    threshold = round(min(5.0, max(1.0, threshold)), 3)

    return {
        "schema_version": "1.0",
        "policy_id": policy_id,
        "version": version,
        "status": "derived_unapproved",
        "rubric_version": rubric_versions.pop(),
        "threshold": threshold,
        "derivation": {
            "ratings_dataset_sha256": hashlib.sha256(
                _canonical_ratings_bytes(rows)
            ).hexdigest(),
            "derivation_code_sha256": hashlib.sha256(
                Path(__file__).read_bytes()
            ).hexdigest(),
            "formula": _DERIVATION_FORMULA,
        },
        "approved_by": None,
        "approved_at": None,
        "notes": (
            "Mechanically derived; not approved. Approval is a human "
            "decision recorded by setting status=approved with approved_by "
            "and approved_at."
        ),
    }


def load_visual_threshold_policy(path: Path) -> VisualThresholdPolicyV1:
    return VisualThresholdPolicyV1.model_validate(
        json.loads(Path(path).read_text(encoding="utf-8"))
    )


def require_calibrated_threshold_policy(
    path: Path,
) -> tuple[VisualThresholdPolicyV1, str]:
    """Load a threshold policy that may authorize calibrated visual review.

    Returns the policy plus the SHA-256 of the exact policy file bytes (the
    value ``VisualReviewEvidenceV3.threshold_policy_sha256`` must match).
    Raises :class:`ThresholdPolicyNotCalibratedError` for any policy that is
    not approved with a derived threshold.
    """
    policy = load_visual_threshold_policy(path)
    if not policy.calibrated:
        raise ThresholdPolicyNotCalibratedError(
            f"threshold policy {policy.policy_id} {policy.version} has "
            f"status {policy.status!r} and threshold {policy.threshold!r}: "
            "it cannot be used as a calibrated visual threshold"
        )
    return policy, hashlib.sha256(Path(path).read_bytes()).hexdigest()


class VisualReviewResult(StrictFrozenModel):
    calibrated: bool
    accepted: bool
    mean_score: float = Field(ge=1, le=5)
    rater_ids: tuple[str, ...]


def resolve_visual_release_state(
    deterministic_failures: tuple[QualityFailure, ...],
    visual_review: VisualReviewResult,
) -> ReleaseState:
    if any(
        failure.severity is FailureSeverity.HARD
        for failure in deterministic_failures
    ):
        return ReleaseState.REJECTED
    if not visual_review.calibrated:
        return ReleaseState.REVIEW_CANDIDATE
    return (
        ReleaseState.SHIP_READY
        if visual_review.accepted
        else ReleaseState.REJECTED
    )
