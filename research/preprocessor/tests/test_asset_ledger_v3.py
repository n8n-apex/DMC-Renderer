from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from pydantic import ValidationError

from contracts_v3.asset_ledger import (
    AssetRecord,
    ProvenanceKind,
    RightsStatus,
    SemanticAssetClass,
    SubstitutionPolicy,
    resolve_asset,
)
from contracts_v3.report_plan import (
    AssetRequirement,
    DensityBand,
    FacePlan,
    NarrativeRole,
    ReportPlanV3,
)
from contracts_v3.units import DocumentUnits
from stages.build_asset_ledger_v3 import build_asset_ledger_v3


def asset_record(
    tmp_path: Path,
    *,
    semantic_class: SemanticAssetClass,
    rights_status: RightsStatus = RightsStatus.CLIENT_AUTHORIZED,
    pixel_width: int = 1200,
    pixel_height: int = 1200,
    local_bytes: bool = True,
    substitution_policy: SubstitutionPolicy = SubstitutionPolicy.EXACT_ONLY,
) -> AssetRecord:
    local_path = tmp_path / f"{semantic_class.value}.bin"
    if local_bytes:
        local_path.write_bytes(b"asset bytes")
    return AssetRecord(
        asset_id=f"asset.{semantic_class.value}",
        semantic_class=semantic_class,
        provenance_kind=ProvenanceKind.CLIENT_SUPPLIED,
        source_locator="client upload",
        rights_status=rights_status,
        content_hash=hashlib.sha256(b"asset bytes").hexdigest(),
        local_path=str(local_path),
        pixel_width=pixel_width,
        pixel_height=pixel_height,
        print_width_mm=100,
        print_height_mm=100,
        allowed_face_ids=("face.01",),
        substitution_policy=substitution_policy,
    )


def requirement(
    semantic_class: str,
    *,
    allowed_substitutions: tuple[str, ...] = (),
) -> AssetRequirement:
    return AssetRequirement(
        requirement_id=f"requirement.{semantic_class}",
        semantic_class=semantic_class,
        required_for_ship=True,
        allowed_substitutions=allowed_substitutions,
        min_print_dpi=240,
    )


def test_product_image_cannot_fill_case_identity_requirement(tmp_path: Path) -> None:
    result = resolve_asset(
        requirement("identity"),
        [asset_record(tmp_path, semantic_class=SemanticAssetClass.PRODUCT)],
        face_id="face.01",
    )

    assert result.code == "illegal_semantic_substitution"


def test_identity_cannot_opt_into_semantic_substitution(tmp_path: Path) -> None:
    result = resolve_asset(
        requirement("identity", allowed_substitutions=("product",)),
        [asset_record(tmp_path, semantic_class=SemanticAssetClass.PRODUCT)],
        face_id="face.01",
    )

    assert result.code == "illegal_semantic_substitution"


def test_context_can_use_explicitly_allowed_decoration(tmp_path: Path) -> None:
    result = resolve_asset(
        requirement("context", allowed_substitutions=("decoration",)),
        [
            asset_record(
                tmp_path,
                semantic_class=SemanticAssetClass.DECORATION,
                substitution_policy=SubstitutionPolicy.APPROVED_CLASSES,
            )
        ],
        face_id="face.01",
    )

    assert result.code == "resolved"
    assert result.asset_id == "asset.decoration"


def test_exact_only_context_asset_cannot_substitute(tmp_path: Path) -> None:
    result = resolve_asset(
        requirement("context", allowed_substitutions=("decoration",)),
        [asset_record(tmp_path, semantic_class=SemanticAssetClass.DECORATION)],
        face_id="face.01",
    )

    assert result.code == "illegal_semantic_substitution"


def test_unknown_rights_block_resolution(tmp_path: Path) -> None:
    result = resolve_asset(
        requirement("proof"),
        [
            asset_record(
                tmp_path,
                semantic_class=SemanticAssetClass.PROOF,
                rights_status=RightsStatus.UNKNOWN,
            )
        ],
        face_id="face.01",
    )

    assert result.code == "rights_not_cleared"


def test_missing_local_bytes_block_resolution(tmp_path: Path) -> None:
    result = resolve_asset(
        requirement("identity"),
        [
            asset_record(
                tmp_path,
                semantic_class=SemanticAssetClass.IDENTITY,
                local_bytes=False,
            )
        ],
        face_id="face.01",
    )

    assert result.code == "local_bytes_missing"


def test_insufficient_print_resolution_blocks_asset(tmp_path: Path) -> None:
    result = resolve_asset(
        requirement("identity"),
        [
            asset_record(
                tmp_path,
                semantic_class=SemanticAssetClass.IDENTITY,
                pixel_width=100,
                pixel_height=100,
            )
        ],
        face_id="face.01",
    )

    assert result.code == "insufficient_print_resolution"


def test_generated_asset_requires_reproducibility_metadata(tmp_path: Path) -> None:
    local_path = tmp_path / "generated.bin"
    local_path.write_bytes(b"generated")

    with pytest.raises(ValidationError, match="generation_recipe"):
        AssetRecord(
            asset_id="asset.generated",
            semantic_class="context",
            provenance_kind="generated",
            source_locator="image model",
            rights_status="cleared",
            content_hash=hashlib.sha256(b"generated").hexdigest(),
            local_path=str(local_path),
            pixel_width=1200,
            pixel_height=1200,
            print_width_mm=100,
            print_height_mm=100,
        )


def five_case_plan() -> ReportPlanV3:
    faces = tuple(
        FacePlan(
            face_id=f"face.{index:02d}",
            face_index=index,
            role=NarrativeRole.CASE_STUDY,
            narrative_act=f"case {index}",
            argument=f"case argument {index}",
            asset_requirements=(
                AssetRequirement(
                    requirement_id=f"case.{index}.identity",
                    semantic_class="identity",
                    required_for_ship=True,
                ),
            ),
            dominant_mechanism="case narrative",
            density_band=DensityBand.MODERATE,
            case_id=f"case.{index}",
        )
        for index in range(1, 6)
    )
    return ReportPlanV3(
        product_profile_id="legacy_christopher",
        units=DocumentUnits.from_formats(["a4"] * 5),
        faces=faces,
        audience="German B2B founder",
        central_thesis="Migration needs user understanding",
        promise="A grounded migration plan",
        tone_profile="Richard house",
    )


def test_five_missing_case_portraits_are_ship_blockers() -> None:
    ledger = build_asset_ledger_v3({"assets": []}, five_case_plan())

    assert len(ledger.ship_blockers()) == 5
    assert {failure.code for failure in ledger.ship_blockers()} == {"missing_required"}
