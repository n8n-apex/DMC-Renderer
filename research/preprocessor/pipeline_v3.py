from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from contracts_v3.build_manifest import (
    BuildManifestV3,
    BuildVersions,
    PrecompositionBundleV3,
    stable_hash,
)
from contracts_v3.report_plan import ProductProfile
from stages.build_asset_ledger_v3 import build_asset_ledger_v3
from stages.build_source_ledger import build_source_ledger
from stages.plan_editorial_v3 import (
    collect_editorial_failures,
    materialize_editorial_plan_v3,
)


class PipelineFailure(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    owner_stage: Literal[
        "adapter",
        "source_ledger",
        "editorial_planning",
        "asset_resolution",
    ]
    code: str
    detail: str
    content_path: str | None = None
    face_id: str | None = None
    requirement_id: str | None = None


class PrecompositionBlocked(ValueError):
    def __init__(self, failures: tuple[PipelineFailure, ...]):
        self.failures = failures
        super().__init__("; ".join(f"{item.code}: {item.detail}" for item in failures))

    @property
    def codes(self) -> tuple[str, ...]:
        return tuple(failure.code for failure in self.failures)


def build_precomposition_bundle_v3(
    source_bundle: dict[str, Any],
    brief: dict[str, Any],
    profile: ProductProfile,
) -> PrecompositionBundleV3:
    source_ledger = build_source_ledger(source_bundle)
    report_plan = materialize_editorial_plan_v3(source_ledger, brief, profile)
    asset_ledger = build_asset_ledger_v3(source_bundle, report_plan)

    failures = [
        PipelineFailure(
            owner_stage="adapter",
            code=failure["code"],
            detail=failure["detail"],
            content_path=failure.get("content_path"),
        )
        for failure in source_bundle.get("adapter_failures", ())
    ]
    failures.extend(
        PipelineFailure(
            owner_stage="source_ledger",
            code=failure.code,
            detail=failure.detail,
            content_path=failure.content_path,
        )
        for failure in source_ledger.assert_ship_grounded()
    )
    failures.extend(
        PipelineFailure(
            owner_stage="editorial_planning",
            code=failure.code,
            detail=failure.detail,
        )
        for failure in collect_editorial_failures(report_plan, source_ledger, profile)
    )
    failures.extend(
        PipelineFailure(
            owner_stage="asset_resolution",
            code=failure.code,
            detail=failure.detail,
            face_id=failure.face_id,
            requirement_id=failure.requirement_id,
        )
        for failure in asset_ledger.ship_blockers()
    )
    if failures:
        raise PrecompositionBlocked(tuple(failures))

    artifact_hashes = {
        "source_ledger": stable_hash(source_ledger),
        "report_plan": stable_hash(report_plan),
        "asset_ledger": stable_hash(asset_ledger),
    }
    return PrecompositionBundleV3(
        source_ledger=source_ledger,
        report_plan=report_plan,
        asset_ledger=asset_ledger,
        manifest=BuildManifestV3(
            versions=BuildVersions(
                product_profile=profile.profile_id,
                workflow_authority="non_workflow",
            ),
            artifact_hashes=artifact_hashes,
        ),
    )
