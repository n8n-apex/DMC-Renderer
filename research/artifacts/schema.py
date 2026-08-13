"""Typed build records, retention classes, and visual review evidence.

Every retained v3 build persists one immutable :class:`BuildRecordV3` whose
hashes bind the exact inputs, decisions, and outputs of that build. Release
decisions consume :class:`VisualReviewEvidenceV3`; booleans alone can never
authorize `ship_ready`.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


_LOWERCASE_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_WORKFLOW_VERSION_KEYS = (
    "workflow_contract",
    "writer_prompt",
    "schema_resolver",
    "writer_gate",
    "source_ledger",
    "claim_gate",
)

RetentionClassName = Literal[
    "rejected",
    "draft",
    "review",
    "review_required",
    "approved_digital",
    "approved_print",
]


def _require_sha256(value: str, label: str) -> str:
    if not isinstance(value, str) or not _LOWERCASE_SHA256.fullmatch(value):
        raise ValueError(f"{label} must be a lowercase SHA-256 hex digest")
    return value


class VisualReviewEvidenceV3(BaseModel):
    """Human visual-review evidence required before any ship_ready release."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rater_ids: tuple[str, ...]
    rubric_version: str
    candidate_sha256: str
    decided_at: str
    threshold_policy_sha256: str
    accepted: bool

    @field_validator("rater_ids")
    @classmethod
    def _require_two_distinct_raters(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        cleaned = tuple(rater.strip() for rater in value)
        if any(not rater for rater in cleaned):
            raise ValueError("rater IDs must be non-empty")
        if len(set(cleaned)) < 2:
            raise ValueError("visual review requires at least two distinct raters")
        return cleaned

    @field_validator("candidate_sha256", "threshold_policy_sha256")
    @classmethod
    def _require_hash(cls, value: str) -> str:
        return _require_sha256(value, "evidence hash")

    @field_validator("rubric_version", "decided_at")
    @classmethod
    def _require_nonempty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("evidence fields must be non-empty")
        return value


class RetentionClass(BaseModel):
    """What one release outcome is allowed and required to retain."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: RetentionClassName
    retained_kinds: tuple[str, ...]


_DIAGNOSIS_KINDS = (
    "build_record",
    "gate_report",
    "render_contract",
    "composition_plan",
)
_REVIEW_KINDS = _DIAGNOSIS_KINDS + (
    "materialization_ledger",
    "rendered_html",
    "raw_pdf",
    "review_pdf",
    "source_appendix",
    "attempt_records",
)

RETENTION_CLASSES: dict[str, RetentionClass] = {
    "rejected": RetentionClass(name="rejected", retained_kinds=_DIAGNOSIS_KINDS),
    "draft": RetentionClass(name="draft", retained_kinds=_DIAGNOSIS_KINDS),
    "review": RetentionClass(name="review", retained_kinds=_REVIEW_KINDS),
    "review_required": RetentionClass(
        name="review_required",
        retained_kinds=_REVIEW_KINDS,
    ),
    "approved_digital": RetentionClass(
        name="approved_digital",
        retained_kinds=_REVIEW_KINDS + ("digital_pdf", "digital_export_report"),
    ),
    "approved_print": RetentionClass(
        name="approved_print",
        retained_kinds=_REVIEW_KINDS
        + ("digital_pdf", "digital_export_report", "print_pdf", "print_preflight_report"),
    ),
}


def retention_class_for_state(
    release_state: str,
    *,
    export_targets: tuple[str, ...] = (),
) -> RetentionClassName:
    if release_state == "rejected":
        return "rejected"
    if release_state == "draft":
        return "draft"
    if release_state == "review_candidate":
        return "review"
    if release_state == "review_required":
        return "review_required"
    if release_state == "ship_ready":
        return "approved_print" if "print" in export_targets else "approved_digital"
    raise ValueError(f"unknown release state: {release_state}")


class BuildRecordV3(BaseModel):
    """One immutable provenance record for a retained v3 build."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    build_id: str
    release_state: Literal[
        "rejected", "draft", "review_candidate", "review_required", "ship_ready"
    ]
    retention_class: RetentionClassName
    input_sha256: str
    workflow_versions: dict[str, str]
    source_ledger_sha256: str
    asset_ledger_sha256: str
    editorial_plan_sha256: str
    composition_plan_sha256: str
    render_contract_sha256: str
    pdf_hashes: dict[str, str]
    gate_report_sha256: str
    export_report_hashes: dict[str, str]
    visual_review_evidence: VisualReviewEvidenceV3 | None = None

    @field_validator(
        "input_sha256",
        "source_ledger_sha256",
        "asset_ledger_sha256",
        "editorial_plan_sha256",
        "composition_plan_sha256",
        "render_contract_sha256",
        "gate_report_sha256",
    )
    @classmethod
    def _require_hash(cls, value: str) -> str:
        return _require_sha256(value, "build record hash")

    @field_validator("pdf_hashes", "export_report_hashes")
    @classmethod
    def _require_hash_map(cls, value: dict[str, str]) -> dict[str, str]:
        for key, digest in value.items():
            _require_sha256(digest, f"hash for {key}")
        return value

    @field_validator("build_id")
    @classmethod
    def _require_build_id(cls, value: str) -> str:
        if not re.fullmatch(r"build\.[0-9a-f]{16}", value):
            raise ValueError("build_id must be 'build.' plus 16 hex characters")
        return value

    @model_validator(mode="after")
    def _require_complete_workflow_versions(self) -> "BuildRecordV3":
        missing = sorted(set(_WORKFLOW_VERSION_KEYS) - set(self.workflow_versions))
        if missing:
            raise ValueError(
                f"workflow versions must cover all six fields; missing: {', '.join(missing)}"
            )
        return self
