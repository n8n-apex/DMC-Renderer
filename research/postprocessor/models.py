"""Shared typed export profiles and reports."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictFrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DigitalExportProfile(StrictFrozenModel):
    schema_version: Literal["1.0"] = "1.0"
    profile_id: str = Field(min_length=1)
    minimum_text_preservation_ratio: float = Field(default=0.99, ge=0.99, le=1)
    preserve_links: bool = True
    preserve_page_sizes: bool = True
    preserve_metadata: bool = True
    preserve_font_references: bool = True


class ExportReport(StrictFrozenModel):
    schema_version: Literal["3.0"] = "3.0"
    export_kind: Literal["digital", "print"]
    profile_id: str
    accepted: bool
    input_sha256: str
    output_sha256: str
    input_path: str
    output_path: str
    text_preservation_ratio: float = Field(ge=0, le=1)
    input_links: tuple[str, ...]
    output_links: tuple[str, ...]
    input_page_sizes_mm: tuple[tuple[float, float], ...]
    output_page_sizes_mm: tuple[tuple[float, float], ...]
    input_font_references: tuple[str, ...]
    output_font_references: tuple[str, ...]
    metadata_preserved: bool
    notes: tuple[str, ...] = ()
