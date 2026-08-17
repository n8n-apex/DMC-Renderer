from __future__ import annotations

from typing import Any

from contracts_v3.asset_ledger import AssetLedger, AssetRecord, resolve_asset
from contracts_v3.report_plan import ReportPlanV3


def build_asset_ledger_v3(
    source_bundle: dict[str, Any], report_plan: ReportPlanV3
) -> AssetLedger:
    assets = tuple(AssetRecord.model_validate(raw) for raw in source_bundle.get("assets", ()))
    resolutions = tuple(
        resolve_asset(requirement, assets, face_id=face.face_id)
        for face in report_plan.faces
        for requirement in face.asset_requirements
    )
    return AssetLedger(assets=assets, resolutions=resolutions)
