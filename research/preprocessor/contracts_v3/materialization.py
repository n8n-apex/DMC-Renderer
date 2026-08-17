"""Observed renderer geometry and reconciliation contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field


class StrictFrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class BoundingBoxMm(StrictFrozenModel):
    x: float
    y: float
    width: float = Field(ge=0)
    height: float = Field(ge=0)


class ElementObservation(StrictFrozenModel):
    element_id: str = Field(min_length=1)
    face_id: str = Field(min_length=1)
    region_id: str = Field(min_length=1)
    content_ref: str | None = None
    claim_id: str | None = None
    asset_id: str | None = None
    bounding_box_mm: BoundingBoxMm
    font_size_pt: float | None = Field(default=None, ge=0)
    line_height_pt: float | None = Field(default=None, ge=0)
    visible: bool
    clipped: bool
    overflowed: bool
    foreground_color: str
    background_color: str
    intersecting_element_ids: tuple[str, ...] = ()


class MaterializationViolation(StrictFrozenModel):
    code: Literal[
        "required_element_missing",
        "element_hidden",
        "element_clipped",
        "element_overflow",
        "element_overlap",
        "font_below_contract_minimum",
        "unexpected_element",
    ]
    severity: Literal["hard"] = "hard"
    element_ids: tuple[str, ...]
    detail: str


class MaterializationLedger(StrictFrozenModel):
    schema_version: Literal["3.0"] = "3.0"
    contract_id: str = Field(min_length=1)
    observations: tuple[ElementObservation, ...]
    missing_required_element_ids: tuple[str, ...]
    violations: tuple[MaterializationViolation, ...]

    @computed_field
    @property
    def violation_codes(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(violation.code for violation in self.violations))
