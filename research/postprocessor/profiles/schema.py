"""Strict print and digital profile loading, licensing boundary, and production policy."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PrintProfileFailure(RuntimeError):
    def __init__(self, code: str, detail: str) -> None:
        self.owner_stage = "print_export"
        self.code = code
        self.detail = detail
        self.face_ids = ()
        self.element_ids = ()
        super().__init__(f"{code}: {detail}")


class DigitalProfileFailure(RuntimeError):
    def __init__(self, code: str, detail: str) -> None:
        self.owner_stage = "digital_export"
        self.code = code
        self.detail = detail
        self.face_ids = ()
        self.element_ids = ()
        super().__init__(f"{code}: {detail}")


class MetadataNormalizationFlags(BaseModel):
    """Explicit, individually named metadata normalization switches."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    strip_creation_date: bool = False
    strip_modification_date: bool = False
    normalize_producer: bool = False

    @property
    def any_active(self) -> bool:
        return (
            self.strip_creation_date
            or self.strip_modification_date
            or self.normalize_producer
        )


class DigitalProfile(BaseModel):
    """Stored, validated digital export profile recorded with every delivery."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    profile_id: str = Field(min_length=1)
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    pdf_standard_target: Literal["preserve_source", "PDF/A-2b"]
    minimum_text_preservation_ratio: float = Field(ge=0.99, le=1)
    preserve_links: bool
    preserve_page_sizes: bool
    preserve_metadata: bool
    preserve_font_references: bool
    metadata_normalization: MetadataNormalizationFlags
    production_allowed: bool

    @model_validator(mode="after")
    def validate_metadata_policy(self) -> "DigitalProfile":
        if self.preserve_metadata and self.metadata_normalization.any_active:
            raise ValueError(
                "metadata normalization changes metadata and cannot be combined "
                "with preserve_metadata"
            )
        return self


def digital_profile_sha256(profile: BaseModel) -> str:
    """Deterministic content hash binding a delivery to its exact profile."""

    canonical = json.dumps(
        profile.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_digital_profile(path: Path) -> DigitalProfile:
    if not path.is_file():
        raise DigitalProfileFailure("digital_profile_missing", str(path))
    payload = json.loads(path.read_text(encoding="utf-8"))
    profile = DigitalProfile.model_validate(payload)
    if not profile.production_allowed:
        raise DigitalProfileFailure(
            "digital_profile_not_production_approved",
            f"profile {profile.profile_id} is not approved for deliveries",
        )
    return profile


class PrintProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    profile_id: str = Field(min_length=1)
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    pdf_standard: Literal["PDF/X-4", "PDF/X-1a:2001", "PDF/A-2b"]
    icc_path: str = Field(min_length=1)
    icc_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    color_space: Literal["RGB", "CMYK"]
    bleed_mm: float = Field(ge=0)
    crop_marks: bool
    minimum_image_dpi: float = Field(gt=0)
    maximum_total_area_coverage_percent: float = Field(gt=0, le=400)
    font_policy: Literal["embed_all", "outline_all"]
    transparency_policy: Literal["preserve", "flatten"]
    flattening_policy: Literal["none", "ghostscript"]
    preserve_searchable_text: bool
    production_allowed: bool

    @model_validator(mode="after")
    def validate_policy_compatibility(self) -> "PrintProfile":
        if self.transparency_policy == "flatten" and self.flattening_policy == "none":
            raise ValueError("flatten transparency requires a flattening policy")
        if self.transparency_policy == "preserve" and self.flattening_policy != "none":
            raise ValueError("preserved transparency cannot request flattening")
        if self.font_policy == "outline_all" and self.preserve_searchable_text:
            raise ValueError("outlined fonts cannot promise searchable text")
        return self


def _reject_blocked_print_template(payload: dict, path: Path) -> None:
    status = payload.get("status")
    if status is not None:
        raise PrintProfileFailure(
            "print_profile_blocked_template",
            f"profile {payload.get('profile_id', path.name)} carries status "
            f"{status!r}: it is a printer-gated template and can never be exported",
        )
    placeholders = sorted(
        key
        for key, value in payload.items()
        if value is None or (isinstance(value, dict) and "required_from" in value)
    )
    if placeholders:
        raise PrintProfileFailure(
            "print_profile_incomplete",
            "printer-supplied values are missing: " + ", ".join(placeholders),
        )


def load_print_profile(path: Path) -> PrintProfile:
    if not path.is_file():
        raise PrintProfileFailure("print_profile_missing", str(path))
    payload = json.loads(path.read_text(encoding="utf-8"))
    _reject_blocked_print_template(payload, path)
    icc_path = Path(payload["icc_path"])
    if not icc_path.is_absolute():
        icc_path = (path.parent / icc_path).resolve()
    payload["icc_path"] = str(icc_path)
    profile = PrintProfile.model_validate(payload)
    if not icc_path.is_file():
        raise PrintProfileFailure(
            "print_profile_missing",
            f"ICC profile does not exist: {icc_path}",
        )
    actual_hash = hashlib.sha256(icc_path.read_bytes()).hexdigest()
    if actual_hash != profile.icc_sha256:
        raise PrintProfileFailure(
            "print_profile_missing",
            f"ICC hash mismatch: expected {profile.icc_sha256}, got {actual_hash}",
        )
    return profile


def assert_profile_for_export(profile: PrintProfile, *, production: bool) -> None:
    if production and not profile.production_allowed:
        raise PrintProfileFailure(
            "print_profile_not_production_approved",
            f"profile {profile.profile_id} is test-only",
        )
