"""ResolvedPackageManifest v2.0 — the validated Layer-1 -> Layer-2 contract.

Promotes the hand-built manifest dict to a Pydantic model so the assembler
validates-then-dumps (a renderer-relevant typo in a top-level key fails
loudly at assembly time). extra="forbid" at the manifest level; extra="allow"
on the page so renderer-relevant extras survive. Brand-agnostic.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from stages.resolve_axes import ResolvedAxes


class ResolvedPageV2(BaseModel):
    model_config = ConfigDict(extra="allow")
    slot: int
    st_type: str
    css_template: Optional[str] = None
    has_cta: Optional[bool] = None
    page_numbers: Optional[str] = None
    cover_validation: Optional[dict] = None
    data: dict = Field(default_factory=dict)
    charts: list = Field(default_factory=list)
    social_proof: Optional[dict] = None
    slots: list = Field(default_factory=list)
    assets: list = Field(default_factory=list)
    components: list = Field(default_factory=list)
    # ---- US-602 section/physical-page identity (optional; a single-page
    # section omits them — back-compat with the flat one-slot-one-sheet
    # package). A section that expands across physical pages carries these so
    # the renderer can place continuations correctly (and so QA can verify
    # section boundaries). ----
    section_id: Optional[str] = None
    page_id: Optional[str] = None
    continuation_index: Optional[int] = None
    continuation_role: Optional[str] = None
    section_page_count: Optional[int] = None


class ResolvedPackageManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal["2.0"]
    generated_at: str
    record_id: str
    brand: dict
    axes: ResolvedAxes
    brand_axes: dict = Field(default_factory=dict)
    provenance: dict[str, str] = Field(default_factory=dict)
    fonts: dict
    report_assets: list = Field(default_factory=list)
    pages: list[ResolvedPageV2]
    slot_summary: dict = Field(default_factory=dict)
    validation: dict = Field(default_factory=dict)
    asset_summary: dict = Field(default_factory=dict)
    asset_warnings: list = Field(default_factory=list)
