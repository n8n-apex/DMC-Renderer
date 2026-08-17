"""Social-proof DATA models (DNA §C4) — ratings, reviews, logo lists.

VALIDATED from agency-supplied content; NEVER LLM-synthesized (fabricating
social proof is forbidden). parse_social_proof validates a provided dict;
absent → None; never invents. Brand-agnostic: shapes only, no client value.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError

_P = ConfigDict(extra="allow")


class RatingCard(BaseModel):
    model_config = _P
    platform: Optional[str] = None
    score: Optional[float] = None
    max_score: float = 5.0
    count: Optional[int] = None
    verified: bool = False


class ReviewCard(BaseModel):
    model_config = _P
    name: Optional[str] = None
    role: Optional[str] = None
    stars: Optional[float] = None
    text: Optional[str] = None
    date: Optional[str] = None


class LogoItem(BaseModel):
    model_config = _P
    name: Optional[str] = None
    asset_key: Optional[str] = None
    grayscale: bool = True


class SocialProofBlock(BaseModel):
    model_config = _P
    ratings: list[RatingCard] = Field(default_factory=list)
    reviews: list[ReviewCard] = Field(default_factory=list)
    press_logos: list[LogoItem] = Field(default_factory=list)
    client_logos: list[LogoItem] = Field(default_factory=list)


def parse_social_proof(data) -> tuple[Optional[SocialProofBlock], Optional[str]]:
    """Validate provided social-proof content. None → (None, None) (no proof
    is fine). Invalid shape → (None, warning). NEVER fabricates."""
    if data is None:
        return None, None
    if not isinstance(data, dict):
        return None, "social_proof: not a dict"
    try:
        return SocialProofBlock.model_validate(data), None
    except ValidationError as exc:
        return None, f"social_proof: invalid ({exc.error_count()} error(s))"


# ---------------------------------------------------------------------------
# Intelligent asset-routing (Phase 1 — Social Layout Planner)
#
# These are the schema CONTRACT between the (Phase-2) VIS interceptor that
# perceives scraped social assets and the (Phase-1) rules-place planner that
# decides where each asset lands in the report. Phase 1 hand-authors the
# AssetManifest; Phase 2 emits the same shape from live perception.
#
# Brand-agnostic by construction: these models carry only SHAPES. Every client
# value (handle, brand_text, paths) lives in the manifest DATA, never here.
# ---------------------------------------------------------------------------


class AssetClassification(BaseModel):
    """One classified social asset (the interceptor's per-image verdict).

    role examples (free-form, set by the classifier): founder_portrait,
    client_photo, content_card, interview, speaking, working, scene. The
    planner reads role + the flags below; it never hard-codes a role string
    that identifies a specific client.
    """
    model_config = _P
    path: str
    role: str
    is_testimonial_card: bool = False
    brand_text: str = ""
    visual_appeal: int = 0
    has_overlaid_text: bool = False


class AssetManifest(BaseModel):
    """The full classified pool for one report (interceptor output)."""
    model_config = _P
    handle: str = ""
    assets: list[AssetClassification] = Field(default_factory=list)


class SocialBinding(BaseModel):
    """One placement decision: a set of assets bound to a report home.

    target_kind = the home's ST type (e.g. "ST-31", "ST-05", "ST-07A",
    "ST-FAZIT"); element = the renderer vocabulary slot the applier writes
    ("profile_grid", "scene_breather", "testimonials", "case_study_post",
    "fazit_author"). page_slot pins the exact page (None only for author).
    """
    model_config = _P
    target_kind: str
    page_slot: Optional[int] = None
    element: str
    assets: list[str] = Field(default_factory=list)
    handle: str = ""
    caption: str = ""


class SocialPlan(BaseModel):
    """The planner's full decision: what to bind + what was dropped (with a
    human-readable reason for each drop, for QA/auditing)."""
    model_config = _P
    bindings: list[SocialBinding] = Field(default_factory=list)
    dropped: list[str] = Field(default_factory=list)
