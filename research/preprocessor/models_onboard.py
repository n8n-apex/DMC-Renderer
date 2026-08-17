"""Contracts for Mode 1 (/onboard) — the visual brand-extraction pipeline.

Each pipeline layer consumes the previous layer's typed output. These
models ARE the contract chain. `BrandProfile` (the clean Stage-1-ready
shape) lives in models.py and is imported here.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from models import BrandDesignBrief, BrandProfile, ImageryGuidance


# ── Endpoint request/response ────────────────────────────────────────────────

class FlatHexFallback(BaseModel):
    dark: str
    light: str
    accent: str


class OnboardRequest(BaseModel):
    record_id: str
    website_url: str
    flat_hex_fallback: Optional[FlatHexFallback] = None
    callback_url: Optional[str] = None


class OnboardAccepted(BaseModel):
    status: str = "accepted"
    job_id: str
    record_id: str


class OnboardDiagnostics(BaseModel):
    render_mode: str = "unknown"
    screenshots: list[str] = Field(default_factory=list)
    timings_ms: dict[str, int] = Field(default_factory=dict)
    vision_model: Optional[str] = None
    palette_size: int = 0


class OnboardResult(BaseModel):
    record_id: str
    job_id: str
    status: str
    brand_profile: BrandProfile
    field_confidence: dict[str, float] = Field(default_factory=dict)
    provenance: dict[str, str] = Field(default_factory=dict)
    needs_review: bool = False
    review_reasons: list[str] = Field(default_factory=list)
    diagnostics: OnboardDiagnostics = Field(default_factory=OnboardDiagnostics)
    design_brief: Optional[BrandDesignBrief] = None


# ── Internal per-layer contracts ─────────────────────────────────────────────

class CaptureResult(BaseModel):
    hero_png: Optional[str]
    fullpage_png: Optional[str]
    raw_dom_eval: dict = Field(default_factory=dict)
    status: str
    notes: list[str] = Field(default_factory=list)


class DomSignals(BaseModel):
    css_color_vars: dict[str, str] = Field(default_factory=dict)
    font_head: Optional[str] = None
    font_body: Optional[str] = None
    sampled_colors: list[str] = Field(default_factory=list)
    logo_url: Optional[str] = None


class PaletteColor(BaseModel):
    hex: str
    coverage_pct: float
    region: str


class PixelPalette(BaseModel):
    colors: list[PaletteColor] = Field(default_factory=list)
    lightest_idx: Optional[int] = None
    darkest_idx: Optional[int] = None


class VisionRoleRefs(BaseModel):
    primary: Optional[int] = None
    accent: Optional[int] = None
    neutral_dark: Optional[int] = None
    neutral_mid: Optional[int] = None
    neutral_light: Optional[int] = None


class VisionAxes(BaseModel):
    accent_mechanic: Optional[str] = None
    ground_mode: Optional[str] = None
    texture: Optional[str] = None
    headline_type: Optional[str] = None
    palette: Optional[str] = None
    qr_enabled: Optional[bool] = None
    density: Optional[str] = None


class VisionReading(BaseModel):
    role_refs: VisionRoleRefs
    axes: VisionAxes
    confidence: dict[str, float] = Field(default_factory=dict)
    notes: Optional[str] = None
