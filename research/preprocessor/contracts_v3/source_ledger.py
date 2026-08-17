from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SourceKind(str, Enum):
    INTERVIEW = "interview"
    WEBSITE = "website"
    DOCUMENT = "document"
    SOCIAL = "social"
    CLIENT_UPLOAD = "client_upload"
    EXTERNAL_REFERENCE = "external_reference"


class ClaimType(str, Enum):
    FACT = "fact"
    NUMBER = "number"
    QUOTE = "quote"
    CREDENTIAL = "credential"
    INTERPRETATION = "interpretation"
    PROMISE = "promise"
    CERTIFICATION = "certification"
    NAMED_RESULT = "named_result"


class SourceSpan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str = Field(min_length=1)
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    verbatim: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_range(self) -> "SourceSpan":
        if self.end <= self.start:
            raise ValueError("source span end must be greater than start")
        return self


class Computation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    formula: str = Field(min_length=1)
    operand_claim_ids: tuple[str, ...] = Field(min_length=1)


class SourceItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str = Field(min_length=1)
    source_kind: SourceKind
    locator: str = Field(min_length=1)
    captured_at: datetime
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    rights_status: str = Field(min_length=1)
    verbatim_text: str
    language: str = Field(min_length=2)
    allowed_uses: tuple[str, ...] = ()


class Claim(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    claim_id: str = Field(min_length=1)
    claim_type: ClaimType
    normalized_value: str = Field(min_length=1)
    unit: str | None = None
    time_scope: str | None = None
    entity_scope: str | None = None
    source_ids: tuple[str, ...] = ()
    source_spans: tuple[SourceSpan, ...] = ()
    computation: Computation | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    allowed_uses: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_grounding_shape(self) -> "Claim":
        grounded_types = {
            ClaimType.FACT,
            ClaimType.NUMBER,
            ClaimType.QUOTE,
            ClaimType.CREDENTIAL,
            ClaimType.CERTIFICATION,
            ClaimType.NAMED_RESULT,
        }
        if self.claim_type in grounded_types and not (self.source_spans or self.computation):
            raise ValueError("grounded claim requires source_spans or computation")
        span_source_ids = {span.source_id for span in self.source_spans}
        if span_source_ids and span_source_ids != set(self.source_ids):
            raise ValueError("source_ids must exactly match source_spans")
        return self


class SourceAppendixEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str = Field(min_length=1)
    citation_text: str = Field(min_length=1)


class SourceAppendixV3(BaseModel):
    """The rendered source appendix delivered alongside the report.

    Every source referenced by a rendered claim must appear here; the evidence
    gate enforces that coverage against the exact contract.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    entries: tuple[SourceAppendixEntry, ...] = ()

    @model_validator(mode="after")
    def validate_unique_sources(self) -> "SourceAppendixV3":
        source_ids = [entry.source_id for entry in self.entries]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("appendix source ids must be unique")
        return self

    def covered_source_ids(self) -> frozenset[str]:
        return frozenset(entry.source_id for entry in self.entries)


class GroundingFailure(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(min_length=1)
    severity: Literal["hard"] = "hard"
    claim_id: str | None = None
    token: str | None = None
    content_path: str | None = None
    detail: str = Field(min_length=1)


class SourceLedger(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["3.0"] = "3.0"
    sources: tuple[SourceItem, ...]
    claims: tuple[Claim, ...]
    grounding_failures: tuple[GroundingFailure, ...] = ()

    @model_validator(mode="after")
    def validate_references(self) -> "SourceLedger":
        source_by_id = {source.source_id: source for source in self.sources}
        if len(source_by_id) != len(self.sources):
            raise ValueError("source ids must be unique")
        claim_ids = {claim.claim_id for claim in self.claims}
        if len(claim_ids) != len(self.claims):
            raise ValueError("claim ids must be unique")
        for claim in self.claims:
            for source_id in claim.source_ids:
                if source_id not in source_by_id:
                    raise ValueError(f"claim {claim.claim_id} references unknown source {source_id}")
            for span in claim.source_spans:
                source = source_by_id.get(span.source_id)
                if source is None:
                    raise ValueError(f"claim {claim.claim_id} references unknown source {span.source_id}")
                if source.verbatim_text[span.start:span.end] != span.verbatim:
                    raise ValueError(f"claim {claim.claim_id} source span does not match verbatim text")
            if claim.computation:
                unknown_operands = set(claim.computation.operand_claim_ids) - claim_ids
                if unknown_operands:
                    unknown = ", ".join(sorted(unknown_operands))
                    raise ValueError(f"claim {claim.claim_id} has unknown operand claims: {unknown}")
        return self

    def assert_ship_grounded(self) -> tuple[GroundingFailure, ...]:
        return self.grounding_failures
