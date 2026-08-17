"""Typed print design policy registry."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictFrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PolicySourceReference(StrictFrozenModel):
    source_id: str = Field(min_length=1)
    upstream_path: str = Field(min_length=1)
    rationale: str = Field(min_length=1)


class DesignPolicy(StrictFrozenModel):
    policy_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]+$")
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    kind: Literal[
        "invariant",
        "planner_feature",
        "family_guidance",
        "deterministic_validator",
        "human_rubric",
    ]
    print_translation: str = Field(min_length=1)
    source_references: tuple[PolicySourceReference, ...] = Field(min_length=1)
    atlas_face_ids: tuple[str, ...] = Field(min_length=1)
    enforcement_owner: Literal[
        "composition_planner",
        "composition_registry",
        "contract_materializer",
        "renderer",
        "materialization",
        "quality_gate",
        "visual_review",
    ]
    confidence: Literal["low", "medium", "high"]
    status: Literal["experimental", "validated", "deprecated"]
    promotion_state: Literal[
        "experimental",
        "curated_candidate",
        "corpus_tested",
        "client_tested",
        "promoted",
    ]
    known_exceptions: tuple[str, ...] = Field(min_length=1)


class DesignPolicyRegistry(StrictFrozenModel):
    schema_version: Literal["1.0"] = "1.0"
    registry_id: str = Field(min_length=1)
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    policies: tuple[DesignPolicy, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_policy_ids(self) -> "DesignPolicyRegistry":
        policy_ids = [policy.policy_id for policy in self.policies]
        if len(policy_ids) != len(set(policy_ids)):
            raise ValueError("design policy IDs must be unique")
        return self

    @property
    def validated_policy_ids(self) -> tuple[str, ...]:
        return tuple(
            policy.policy_id for policy in self.policies if policy.status == "validated"
        )
