"""Required asset resolution and semantic substitution gates."""

from __future__ import annotations

import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
PREPROCESSOR_ROOT = HERE.parents[1] / "preprocessor"
if str(PREPROCESSOR_ROOT) not in sys.path:
    sys.path.insert(0, str(PREPROCESSOR_ROOT))

from contracts_v3.asset_ledger import AssetLedger  # noqa: E402
from contracts_v3.release import (  # noqa: E402
    FailureOwner,
    FailureSeverity,
    QualityFailure,
)
from contracts_v3.report_plan import ReportPlanV3  # noqa: E402
from contracts_v3.render_contract import FrozenRenderContractV3  # noqa: E402


_CODE_MAP = {
    "missing_required": "missing_required_asset",
    "absent": "missing_required_asset",
    "illegal_semantic_substitution": "illegal_asset_substitution",
    "rights_not_cleared": "asset_rights_not_cleared",
    "local_bytes_missing": "missing_required_asset",
    "insufficient_print_resolution": "missing_required_asset",
}


# Classes whose whole purpose is to recur across the report. These are the
# real members of SemanticAssetClass; "ground" and "motif" were in an earlier
# version of this set and are not classes at all, so those exemptions could
# never have fired. A texture IS the ground (Buchagentur places one on nine
# faces) and a logo IS the running mark (Niklas repeats one eight times).
_REPEATABLE_CLASSES = frozenset({"texture", "logo", "decoration"})


def _byte_failure(code: str, detail: str, *, face_ids: tuple[str, ...] = ()) -> QualityFailure:
    return QualityFailure(
        owner_stage=FailureOwner.ASSETS,
        code=code,
        severity=FailureSeverity.HARD,
        face_ids=face_ids,
        remediation_class="supply_asset",
        detail=detail,
    )


def check_asset_bytes_v3(
    asset_ledger: AssetLedger,
    *,
    used_face_ids: dict[str, tuple[str, ...]],
    minimum_dpi: float | None = None,
    reference_date: str | None = None,
    allow_synthetic_assets: bool = False,
) -> tuple[QualityFailure, ...]:
    """Re-verify every ledger asset from its actual bytes at build time.

    The ledger's declared hash, dimensions, and print size are treated as
    claims to be checked, never as truth.

    ``allow_synthetic_assets`` is for CALIBRATION builds only: the frozen
    synthetic asset bank exists so the pipeline can be exercised deterministically
    without real client photos. A calibration build still stops at
    review_candidate (it can never become ship_ready without human review
    evidence and a real asset audit), so exempting it from the placeholder rule
    does NOT weaken the production guarantee. Production builds keep the
    default False and a procedural placeholder can never ship.
    """
    import hashlib

    from PIL import Image

    failures: list[QualityFailure] = []
    for asset in asset_ledger.assets:
        raw_path = Path(asset.local_path)
        if ".." in raw_path.parts:
            failures.append(
                _byte_failure(
                    "asset_path_traversal",
                    f"{asset.asset_id} path contains traversal segments",
                )
            )
            continue
        if not raw_path.is_file():
            failures.append(
                _byte_failure(
                    "missing_required_asset",
                    f"{asset.asset_id} bytes are absent at {raw_path}",
                )
            )
            continue
        data = raw_path.read_bytes()
        actual_hash = hashlib.sha256(data).hexdigest()
        if actual_hash != asset.content_hash:
            failures.append(
                _byte_failure(
                    "asset_bytes_mismatch",
                    f"{asset.asset_id} bytes do not match the ledger hash",
                )
            )
        try:
            with Image.open(raw_path) as image:
                actual_width, actual_height = image.size
        except Exception:
            failures.append(
                _byte_failure(
                    "asset_bytes_unreadable",
                    f"{asset.asset_id} bytes are not a readable image",
                )
            )
            continue
        if (actual_width, actual_height) != (asset.pixel_width, asset.pixel_height):
            failures.append(
                _byte_failure(
                    "asset_dimensions_mismatch",
                    f"{asset.asset_id} declares {asset.pixel_width}x{asset.pixel_height} "
                    f"but bytes are {actual_width}x{actual_height}",
                )
            )
        if minimum_dpi is not None:
            effective_dpi = min(
                actual_width / (asset.print_width_mm / 25.4),
                actual_height / (asset.print_height_mm / 25.4),
            )
            if effective_dpi < minimum_dpi:
                failures.append(
                    _byte_failure(
                        "asset_print_resolution_insufficient",
                        f"{asset.asset_id} measures {effective_dpi:.0f} dpi at print "
                        f"size; {minimum_dpi:.0f} dpi is required",
                    )
                )
        used_on = used_face_ids.get(asset.asset_id, ())
        if asset.allowed_face_ids:
            illegal = tuple(
                face_id for face_id in used_on if face_id not in asset.allowed_face_ids
            )
            if illegal:
                failures.append(
                    _byte_failure(
                        "asset_face_not_allowed",
                        f"{asset.asset_id} is used on faces outside its allowlist",
                        face_ids=illegal,
                    )
                )
        if asset.valid_until is not None:
            if reference_date is None:
                failures.append(
                    _byte_failure(
                        "asset_expiry_unverifiable",
                        f"{asset.asset_id} has valid_until but no build reference date",
                    )
                )
            elif asset.valid_until < reference_date:
                failures.append(
                    _byte_failure(
                        "asset_reference_expired",
                        f"{asset.asset_id} reference lapsed on {asset.valid_until}",
                    )
                )

    # A placeholder is not a photograph. Procedurally drawn stand-ins were
    # printing at up to 84mm on client-facing pages and reading as real
    # portraits, so a build carrying them can never be a shippable report.
    # Calibration builds declare allow_synthetic_assets=True and never reach
    # ship_ready, so the production guarantee stays intact.
    if not allow_synthetic_assets:
        for asset in asset_ledger.assets:
            locator = (asset.source_locator or "").lower()
            if "synthetic" in locator or "placeholder" in locator:
                failures.append(
                    _byte_failure(
                        "synthetic_placeholder_asset",
                        f"{asset.asset_id} is a generated placeholder ({asset.source_locator})",
                        face_ids=tuple(asset.allowed_face_ids),
                    )
                )

    # One image standing in for several different people or companies is the
    # same lie told repeatedly. Distinct faces must not share image bytes.
    by_hash: dict[str, list] = {}
    for asset in asset_ledger.assets:
        by_hash.setdefault(asset.content_hash, []).append(asset)
    for content_hash, shared in by_hash.items():
        face_sets = {tuple(sorted(asset.allowed_face_ids)) for asset in shared}
        # Measured against the reference: reuse is Richard's TECHNIQUE for
        # some classes, not a defect. Buchagentur places one full-face ground
        # on nine consecutive faces; Niklas and Werkzeugkoffer each repeat the
        # client logo 8-9 times. This rule was written to catch duplicated
        # PLACEHOLDER photographs and would have condemned his own practice.
        # A portrait or a proof shot may not repeat; a ground, texture, logo
        # or motif is meant to.
        if all(
            asset.semantic_class.value in _REPEATABLE_CLASSES for asset in shared
        ):
            continue
        if len(shared) > 1 and len(face_sets) > 1:
            names = ", ".join(sorted(asset.asset_id for asset in shared))
            failures.append(
                _byte_failure(
                    "asset_reused_across_faces",
                    f"identical bytes ({content_hash[:12]}) serve unrelated faces: {names}",
                    face_ids=tuple(
                        sorted({fid for asset in shared for fid in asset.allowed_face_ids})
                    ),
                )
            )
    return tuple(failures)


def check_assets_v3(
    plan: ReportPlanV3,
    asset_ledger: AssetLedger,
    contract: FrozenRenderContractV3 | None,
) -> tuple[QualityFailure, ...]:
    failures: list[QualityFailure] = []
    for resolution in asset_ledger.ship_blockers():
        failures.append(
            QualityFailure(
                owner_stage=FailureOwner.ASSETS,
                code=_CODE_MAP.get(resolution.code, "missing_required_asset"),
                severity=FailureSeverity.HARD,
                face_ids=(resolution.face_id,) if resolution.face_id else (),
                remediation_class="supply_asset",
                detail=resolution.detail,
            )
        )
    if contract is not None:
        known_assets = {asset.asset_id for asset in asset_ledger.assets}
        for asset_id in sorted(set(contract.asset_refs) - known_assets):
            element_ids = tuple(
                element.element_id
                for fragment in contract.fragments
                for element in fragment.elements
                if getattr(element, "asset_id", None) == asset_id
            )
            failures.append(
                QualityFailure(
                    owner_stage=FailureOwner.ASSETS,
                    code="missing_required_asset",
                    severity=FailureSeverity.HARD,
                    element_ids=element_ids,
                    remediation_class="supply_asset",
                    detail=f"contract asset {asset_id} is absent from the ledger",
                )
            )
    return tuple(failures)
