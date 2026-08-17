from __future__ import annotations

import hashlib
import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from .asset_ledger import AssetLedger
from .report_plan import ReportPlanV3
from .source_ledger import SourceLedger


_STRICT_SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
_LOWERCASE_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_WORKFLOW_VERSION_FIELDS = (
    "workflow_contract",
    "writer_prompt",
    "schema_resolver",
    "writer_gate",
    "source_ledger",
    "claim_gate",
)


def stable_json(value: object) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def stable_hash(value: object) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


class BuildVersions(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_schema: Literal["3.0"] = "3.0"
    product_profile: str
    preprocessor: Literal["3.0"] = "3.0"
    workflow_authority: Literal["non_workflow", "verified"]
    workflow_contract: str | None = None
    writer_prompt: str | None = None
    schema_resolver: str | None = None
    writer_gate: str | None = None
    source_ledger: str | None = None
    claim_gate: str | None = None

    @model_validator(mode="after")
    def _enforce_workflow_authority(self) -> "BuildVersions":
        values = {field: getattr(self, field) for field in _WORKFLOW_VERSION_FIELDS}
        if self.workflow_authority == "verified":
            missing = sorted(field for field, value in values.items() if value is None)
            if missing:
                raise ValueError(
                    "verified builds require the complete workflow authority set; "
                    f"missing: {', '.join(missing)}"
                )
            invalid = sorted(
                field
                for field, value in values.items()
                if not _STRICT_SEMVER.fullmatch(value)
            )
            if invalid:
                raise ValueError(
                    "workflow authority versions must be strict semantic versions; "
                    f"invalid: {', '.join(invalid)}"
                )
        else:
            present = sorted(field for field, value in values.items() if value is not None)
            if present:
                raise ValueError(
                    "non_workflow builds must not carry workflow authority versions; "
                    f"present: {', '.join(present)}"
                )
        return self


class BuildManifestV3(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["3.0"] = "3.0"
    versions: BuildVersions
    artifact_hashes: dict[str, str]

    @field_validator("artifact_hashes")
    @classmethod
    def _enforce_artifact_hashes(cls, value: dict[str, str]) -> dict[str, str]:
        if not value:
            raise ValueError("artifact hashes must not be empty")
        invalid = sorted(
            key
            for key, digest in value.items()
            if not isinstance(digest, str) or not _LOWERCASE_SHA256.fullmatch(digest)
        )
        if invalid:
            raise ValueError(
                f"artifact hashes must be lowercase SHA-256: {', '.join(invalid)}"
            )
        return value


class PrecompositionBundleV3(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["3.0"] = "3.0"
    source_ledger: SourceLedger
    report_plan: ReportPlanV3
    asset_ledger: AssetLedger
    manifest: BuildManifestV3

    @property
    def content_hash(self) -> str:
        return stable_hash(self)

    def to_stable_json(self) -> str:
        return stable_json(self)
