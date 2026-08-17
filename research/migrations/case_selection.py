from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CaseCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str = Field(min_length=1)
    source_slot: int = Field(gt=0)
    source_content_path: str = Field(min_length=1)
    source_label: str = Field(min_length=1)


class CaseDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class ThreeCaseSelectionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["3.0"] = "3.0"
    required_case_count: Literal[3] = 3
    candidates: tuple[CaseCandidate, ...]
    chosen_cases: tuple[CaseDecision, ...] = ()
    excluded_cases: tuple[CaseDecision, ...] = ()
    pending_cases: tuple[CaseDecision, ...] = ()
    human_review_status: Literal["pending", "approved", "rejected"]
    approved_by: str | None = None
    approved_at: str | None = None

    @model_validator(mode="after")
    def validate_partition(self) -> "ThreeCaseSelectionRecord":
        candidate_ids = {candidate.case_id for candidate in self.candidates}
        decided = [
            *(item.case_id for item in self.chosen_cases),
            *(item.case_id for item in self.excluded_cases),
            *(item.case_id for item in self.pending_cases),
        ]
        if len(decided) != len(set(decided)) or set(decided) != candidate_ids:
            raise ValueError("case decisions must partition every candidate exactly once")
        if self.human_review_status == "approved":
            if len(self.chosen_cases) != self.required_case_count:
                raise ValueError("approved selection requires exactly three chosen cases")
            if self.pending_cases:
                raise ValueError("approved selection cannot contain pending cases")
            if not self.approved_by or not self.approved_at:
                raise ValueError("approved selection requires reviewer identity and timestamp")
        elif self.approved_by or self.approved_at:
            raise ValueError("unapproved selection cannot claim approval metadata")
        return self

