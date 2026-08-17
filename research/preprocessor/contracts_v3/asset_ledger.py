from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .report_plan import AssetRequirement


class SemanticAssetClass(str, Enum):
    IDENTITY = "identity"
    PROOF = "proof"
    PRODUCT = "product"
    PROCESS = "process"
    CONTEXT = "context"
    DECORATION = "decoration"
    TEXTURE = "texture"
    LOGO = "logo"
    QR = "qr"
    SOURCE = "source"


class ProvenanceKind(str, Enum):
    CLIENT_SUPPLIED = "client_supplied"
    CLIENT_PUBLIC = "client_public"
    LICENSED = "licensed"
    GENERATED = "generated"
    DERIVED = "derived"


class RightsStatus(str, Enum):
    CLEARED = "cleared"
    CLIENT_AUTHORIZED = "client_authorized"
    LICENSED = "licensed"
    PUBLIC_USE = "public_use"
    UNKNOWN = "unknown"
    RESTRICTED = "restricted"


class SubstitutionPolicy(str, Enum):
    EXACT_ONLY = "exact_only"
    APPROVED_CLASSES = "approved_classes"
    FORBIDDEN = "forbidden"


class AssetRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    asset_id: str = Field(min_length=1)
    semantic_class: SemanticAssetClass
    provenance_kind: ProvenanceKind
    source_locator: str = Field(min_length=1)
    rights_status: RightsStatus
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    local_path: str
    pixel_width: int = Field(gt=0)
    pixel_height: int = Field(gt=0)
    print_width_mm: float = Field(gt=0)
    print_height_mm: float = Field(gt=0)
    allowed_face_ids: tuple[str, ...] = ()
    substitution_policy: SubstitutionPolicy = SubstitutionPolicy.EXACT_ONLY
    # ISO date after which the reference (license, approval, upload) lapses.
    valid_until: str | None = None
    generation_recipe: str | None = None
    model_version: str | None = None
    seed: int | None = None

    @model_validator(mode="after")
    def validate_generated_metadata(self) -> "AssetRecord":
        if self.provenance_kind is ProvenanceKind.GENERATED:
            missing = [
                name
                for name, value in (
                    ("generation_recipe", self.generation_recipe),
                    ("model_version", self.model_version),
                    ("seed", self.seed),
                )
                if value is None or value == ""
            ]
            if missing:
                raise ValueError(f"generated asset requires {', '.join(missing)}")
        return self

    @property
    def effective_dpi(self) -> float:
        horizontal = self.pixel_width / (self.print_width_mm / 25.4)
        vertical = self.pixel_height / (self.print_height_mm / 25.4)
        return min(horizontal, vertical)


class AssetResolution(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    requirement_id: str
    face_id: str | None = None
    required_for_ship: bool
    code: Literal[
        "resolved",
        "missing_required",
        "absent",
        "illegal_semantic_substitution",
        "rights_not_cleared",
        "local_bytes_missing",
        "insufficient_print_resolution",
    ]
    asset_id: str | None = None
    detail: str


class AssetLedger(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["3.0"] = "3.0"
    assets: tuple[AssetRecord, ...]
    resolutions: tuple[AssetResolution, ...]

    @model_validator(mode="after")
    def validate_unique_assets(self) -> "AssetLedger":
        asset_ids = [asset.asset_id for asset in self.assets]
        if len(asset_ids) != len(set(asset_ids)):
            raise ValueError("asset ids must be unique")
        return self

    def ship_blockers(self) -> tuple[AssetResolution, ...]:
        return tuple(
            resolution
            for resolution in self.resolutions
            if resolution.required_for_ship and resolution.code != "resolved"
        )


_CLEARED_RIGHTS = {
    RightsStatus.CLEARED,
    RightsStatus.CLIENT_AUTHORIZED,
    RightsStatus.LICENSED,
    RightsStatus.PUBLIC_USE,
}


def resolve_asset(
    requirement: AssetRequirement,
    assets: list[AssetRecord] | tuple[AssetRecord, ...],
    *,
    face_id: str | None = None,
) -> AssetResolution:
    required_class = SemanticAssetClass(requirement.semantic_class)
    permitted_classes = {required_class}
    if required_class not in {SemanticAssetClass.IDENTITY, SemanticAssetClass.PROOF}:
        permitted_classes |= {
            SemanticAssetClass(value) for value in requirement.allowed_substitutions
        }
    face_candidates = [
        asset
        for asset in assets
        if not asset.allowed_face_ids or face_id is None or face_id in asset.allowed_face_ids
    ]
    candidates = sorted(
        (
            asset
            for asset in face_candidates
            if asset.semantic_class is required_class
            or (
                asset.semantic_class in permitted_classes
                and asset.substitution_policy is SubstitutionPolicy.APPROVED_CLASSES
            )
        ),
        key=lambda asset: asset.asset_id,
    )
    if not candidates:
        code = (
            "illegal_semantic_substitution"
            if face_candidates
            else "missing_required" if requirement.required_for_ship else "absent"
        )
        return AssetResolution(
            requirement_id=requirement.requirement_id,
            face_id=face_id,
            required_for_ship=requirement.required_for_ship,
            code=code,
            detail=f"no permitted {required_class.value} asset is available",
        )

    asset = candidates[0]
    if asset.rights_status not in _CLEARED_RIGHTS:
        return AssetResolution(
            requirement_id=requirement.requirement_id,
            face_id=face_id,
            required_for_ship=requirement.required_for_ship,
            code="rights_not_cleared",
            asset_id=asset.asset_id,
            detail=f"asset rights are {asset.rights_status.value}",
        )
    asset_path = Path(asset.local_path)
    if not asset_path.is_file():
        return AssetResolution(
            requirement_id=requirement.requirement_id,
            face_id=face_id,
            required_for_ship=requirement.required_for_ship,
            code="local_bytes_missing",
            asset_id=asset.asset_id,
            detail="asset has no local bytes",
        )
    if asset.effective_dpi < requirement.min_print_dpi:
        return AssetResolution(
            requirement_id=requirement.requirement_id,
            face_id=face_id,
            required_for_ship=requirement.required_for_ship,
            code="insufficient_print_resolution",
            asset_id=asset.asset_id,
            detail=(
                f"effective DPI {asset.effective_dpi:.1f} is below "
                f"required {requirement.min_print_dpi:.1f}"
            ),
        )
    return AssetResolution(
        requirement_id=requirement.requirement_id,
        face_id=face_id,
        required_for_ship=requirement.required_for_ship,
        code="resolved",
        asset_id=asset.asset_id,
        detail="asset resolved",
    )
