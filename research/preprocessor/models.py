"""Pydantic v2 models — Phase A.

INPUT shape — what n8n POSTs (RenderRequest):

  {
    "record_id": "recXXXX",
    "client": {
      "name": "...", "company": "...", "website_url": "...",
      "brand_hex_dark": "#1A2540", "brand_hex_light": "#F5F0E8",
      "brand_hex_accent": "#E97E47",
      "visual_style": "...", "logo_url": "...", "headshot_urls": [...],
      "drive_folder": "...", "brand_profile": { ... optional ... }
    },
    "report_json": {
      "meta": { "client_slug", "report_id", "lang", "page_format",
                "page_count_target" },
      "pages": [ { "slot": N, "type": "ST-XX", "data": {...} }, ... ]
    },
    "image_manifest": { "images": [...] }
  }

OUTPUT shape — what /render returns (RenderResponse):

  {
    "status": "success" | "warn" | "error",
    "validated_brand_tokens": { ... 10 flat fields matching chassis
                                  BrandConfig ... },
    "font_config": { ... font_heading + font_body name + paths
                      + source ... },
    "errors": [ ... critical issues that prevented validation ... ],
    "warnings": [ ... non-blocking issues for Richard's QA ... ]
  }

Input-driven principle: every field on the way in is per-client DATA.
Logic refers to fields by name (`client.brand_hex_accent`), never to
hexes by literal name. The pre-processor transforms data into the
chassis's BrandConfig shape and is brand-agnostic throughout.
"""

from __future__ import annotations

from typing import Any, Optional
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


# ─────────────────────────────────────────────────────────────────────────────
# INPUT MODELS (the n8n-POSTed shape)
# ─────────────────────────────────────────────────────────────────────────────


class BrandProfile(BaseModel):
    """Optional Layer-B brand profile produced by Mode 1 (`/onboard`).

    All fields optional in Phase A — Mode 1 isn't built yet. When
    present, fields here are PREFERRED over the flat hexes on
    `ClientInput` (richer source of truth per spec).

    Field names mirror grammar §4.0 Layer-B axes and the chassis's
    `BrandConfig` field names so the merge logic stays straightforward.
    """

    model_config = ConfigDict(extra="allow")  # Mode 1 may add fields later

    # Hex overrides (richer than the 3-hex flat input).
    brand_primary: Optional[str] = None
    brand_accent: Optional[str] = None
    brand_neutral_dark: Optional[str] = None
    brand_neutral_mid: Optional[str] = None
    brand_neutral_light: Optional[str] = None

    # Font identification — pre-processor resolves these in Stage 2.
    font_head: Optional[str] = None
    font_body: Optional[str] = None

    # Brand-identity perceptual axes (grammar §4.0 M/G/X/H). Captured by
    # Mode 1 (/onboard); not yet consumed by the renderer but stored so
    # the data is present when the renderer grows to read them.
    accent_mechanic: Optional[str] = None   # §4.0 M: contrasting_hue | tonal_same_hue
    ground_mode: Optional[str] = None       # §4.0 G
    texture: Optional[str] = None           # §4.0 X: marble_paper | crumpled_paper | smooth | photo
    headline_type: Optional[str] = None     # §4.0 H: serif | sans | sans_allcaps

    # §B axes added post-DNA (palette/accent derivation + QR + density).
    palette: Optional[str] = None        # mono_tonal | dual_contrasting
    qr_enabled: Optional[bool] = None     # whether the brand uses QR codes
    density: Optional[str] = None         # airy | balanced | packed


class ImageryGuidance(BaseModel):
    style: str
    subjects: str
    treatment: str
    lighting: str
    avoid: list[str] = Field(default_factory=list)


class BrandDesignBrief(BaseModel):
    visual_style_summary: str
    mood: list[str] = Field(default_factory=list)
    imagery: ImageryGuidance
    color_usage: str
    shape_language: str
    texture_material: str
    typography_character: str
    composition: str
    iconography: str
    image_style_prompt: str
    negative_prompt: str
    confidence: float = 0.0


class ClientInput(BaseModel):
    """The client block of the render request.

    Three hex fields are REQUIRED at the input level (n8n cannot fetch
    a brand without them). Pydantic raises 422 at the route if any is
    missing — this is the "reject loud" the spec requires.
    """

    model_config = ConfigDict(extra="allow")

    name: str
    company: str
    website_url: str
    brand_hex_dark: str = Field(min_length=4)
    brand_hex_light: str = Field(min_length=4)
    brand_hex_accent: str = Field(min_length=4)

    # Optional today; required for full render pipeline later.
    visual_style: Optional[str] = None
    logo_url: Optional[str] = None
    headshot_urls: list[str] = Field(default_factory=list)
    drive_folder: Optional[str] = None
    brand_profile: Optional[BrandProfile] = None
    design_brief: Optional[BrandDesignBrief] = None

    # Founder channel URLs (ingested from Airtable) — consumed by the
    # founder-asset scraper. Optional; no hard URL-format validation.
    # `founder_linkedin_url` is reserved per spec (not yet consumed).
    founder_youtube_url: Optional[str] = None
    founder_instagram_url: Optional[str] = None
    founder_linkedin_url: Optional[str] = None


class ReportMeta(BaseModel):
    model_config = ConfigDict(extra="allow")

    client_slug: str
    report_id: str
    lang: str = "de"
    page_format: str = "A4"
    page_count_target: int  # validated in Stage 1 against {16,20,24,28}
    export_mode: Optional[str] = None
    # Awareness level 1-5 per Richard's 11_Cover_Headlines §8 matrix.
    # 1 = no problem awareness, 2 = problem-aware/wrong-diagnosis,
    # 3 = right-diagnosis/seeking-solution, 4 = knows-solution-direction,
    # 5 = ready-to-buy/knows-you. Defaults to 2 (most common for
    # unknown brands; Mode 1 onboarding can override).
    awareness_level: int = 2


class ReportPage(BaseModel):
    """One page in the report. `data` is free-form per ST type."""

    model_config = ConfigDict(extra="allow")

    slot: int
    type: str  # e.g. "ST-07A"
    data: dict[str, Any]
    chapter_type_original: Optional[str] = None
    page_numbers: Optional[str] = None


class ReportJson(BaseModel):
    model_config = ConfigDict(extra="allow")

    meta: ReportMeta
    pages: list[ReportPage]


class ImageManifestItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    page_slot: int
    page_st_type: str
    image_type: str
    url: Optional[str] = None
    status: Optional[str] = None


class ImageManifest(BaseModel):
    model_config = ConfigDict(extra="allow")

    images: list[ImageManifestItem] = Field(default_factory=list)


class RenderRequest(BaseModel):
    """The full /render POST payload from n8n."""

    model_config = ConfigDict(extra="allow")

    record_id: str
    client: ClientInput
    report_json: ReportJson
    image_manifest: ImageManifest = Field(default_factory=ImageManifest)
    # Opt-in (non-breaking): when true, after building the package the service
    # also renders + grades + ships it (the autonomy spine), delivering the
    # ship-or-escalate outcome to ``ship_webhook`` (or the configured webhook).
    ship: bool = False
    ship_webhook: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# OUTPUT MODELS (what /render returns)
# ─────────────────────────────────────────────────────────────────────────────


class BrandTokensResolved(BaseModel):
    """The 10 flat fields the chassis's BrandConfig expects.

    Matches `research/v7-renderer/brand_tokens.py` `BrandConfig` shape
    exactly — same field names, same types. The chassis can consume
    this dict directly via `parse_brand_tokens(dict)`.
    """

    brand_primary: str
    brand_accent: str
    brand_neutral_dark: str
    brand_neutral_mid: str
    brand_neutral_light: str
    font_heading: str
    font_body: str
    qr_target_url: str
    company_name_short: str
    company_url_display: str


class FontConfig(BaseModel):
    """Resolved font configuration.

    `font_*_path` is a string path to the on-disk font file when the
    font is resolvable (chassis default OR a previously-fetched
    Google Font), or None when the font needs a customer upload.

    `source` describes how the fonts were resolved:
      - "chassis_default"           — both fonts are the default
                                       Priorität-2 system pair
      - "customer_upload_needed"    — at least one font name was
                                       supplied that the chassis
                                       doesn't ship; Mode-1 fetch or
                                       customer upload pending
    """

    font_heading_name: str
    font_body_name: str
    font_heading_path: Optional[str] = None
    font_body_path: Optional[str] = None
    source: str


class ValidationIssue(BaseModel):
    code: str
    message: str
    location: Optional[str] = None  # e.g. "report_json.pages[0]"


# ─────────────────────────────────────────────────────────────────────────────
# Stage 3 — copy validation (grammar §3.9)
# ─────────────────────────────────────────────────────────────────────────────


class CopyWarning(BaseModel):
    """One QA warning raised by Stage 3. NEVER blocks render — Richard
    reviews these and decides whether to fix the source copy.

    `severity` is always "warning" in Stage 3. The field is present for
    forward compatibility (future copy-discipline rules may distinguish
    soft warnings from hard rejections, but today they are all soft).
    """

    page_slot: int
    page_type: str          # e.g. "ST-01"
    field_name: str         # e.g. "title", "subtitle", "intro_body"
    rule: str               # e.g. "buzzword_denylist", "konjunktiv"
    detail: str             # human-readable, references the offending substring
    severity: str = "warning"


# ─────────────────────────────────────────────────────────────────────────────
# Stage 4 — cover stack validation (Richard's 11_Cover_Headlines doc)
# ─────────────────────────────────────────────────────────────────────────────


class ScoreDetail(BaseModel):
    """Per-criterion score row for the H/S/B matrices."""

    criterion: str   # e.g. "H1", "S3", "B5"
    score: int       # 0, 1, or 2 (H/S/B all use 0-2 scale)
    reason: str      # one-line explanation of how the score was reached


class CoverValidation(BaseModel):
    """Stage 4 output — cover stack scoring + sizing.

    The renderer uses `headline_size_class` to pick a display font
    size: "short" → 36-44pt (Etikett, 4-8 words), "long" → 24-30pt
    wrapping 2-3 lines (Diagnose, 12-30 words).

    `overall` summarises the three matrix scores + the disqualification
    list into one of three buckets:
      - "pass"                  — all scores at threshold, zero disqs
      - "pass_with_warnings"    — scores acceptable, some weaknesses
      - "needs_review"          — at least one score below threshold OR
                                  any disqualification
    """

    headline_type: str          # "Typ A — Etikett" | "Typ B — Diagnose" | "ambiguous"
    headline_size_class: str    # "short" | "long"
    awareness_level: int        # 1-5

    h_score: int                # 0-16
    h_scores_detail: list[ScoreDetail]

    s_score: int                # 0-10
    s_scores_detail: list[ScoreDetail]

    b_score: int                # 0-10
    b_scores_detail: list[ScoreDetail]

    disqualifications: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    overall: str                # "pass" | "pass_with_warnings" | "needs_review"


# ─────────────────────────────────────────────────────────────────────────────
# Stage 7 — layout planning (grammar §1.2, §1.4)
# ─────────────────────────────────────────────────────────────────────────────


class PlannedPageSummary(BaseModel):
    """One page in the layout plan as serialised on the /render response.

    The full `LayoutPlan.pages` also carries the original `data` block
    and the SVG component strings; those are useful for the assembler
    (Stage 8) but heavy to serialise into the JSON response. The
    response-layer view (`PlannedPageSummary`) keeps just the routing
    metadata plus a `component_count`.
    """

    slot: int
    st_type: str
    css_template: str          # e.g. "case_study"
    has_cta: bool
    component_count: int


class LayoutPlanSummary(BaseModel):
    """Layout plan view embedded in /render JSON responses.

    Excludes the heavy SVG strings and original page `data` blobs to
    keep responses small. Stage 8 consumes the full LayoutPlan
    in-memory; this summary is what n8n receives.
    """

    page_count: int
    page_count_target: int
    cta_positions: list[int] = Field(default_factory=list)
    breathing_positions: list[int] = Field(default_factory=list)
    pages: list[PlannedPageSummary] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# Stage 5 — AI assets (image inventory + download + stubbed generation)
# ─────────────────────────────────────────────────────────────────────────────


class AssetResultModel(BaseModel):
    """One asset (downloaded, stubbed, or pending-upload). This is the
    JSON-serialisable view of the in-memory `AssetResult` dataclass —
    the dataclass lives in `stages.generate_assets` for internal use,
    this model is what the /render response and `resolved_package.json`
    carry.

    `status` values:
      - "downloaded"           — file present on disk at `path`
      - "generated"            — fal.ai generated + downloaded; `path` set
      - "stub_not_generated"   — generator stubbed; `path` is None
      - "client_upload_needed" — customer must supply; `path` is None
      - "failed"               — download/generation tried and failed
      - "skipped_no_url"       — manifest had no URL for this slot
    """

    slot_id: str
    status: str
    path: Optional[str] = None
    message: str = ""
    page_slot: Optional[int] = None
    image_type: str = ""
    prompt: Optional[str] = None
    negative_prompt: Optional[str] = None


class AssetSummary(BaseModel):
    """Aggregate counts surfaced on the /render response (and on
    resolved_package.json under `asset_summary`).
    """

    total_required: int = 0
    total_downloaded: int = 0
    total_stubbed: int = 0
    total_client_upload_needed: int = 0
    total_failed: int = 0
    total_generated: int = 0


# ─────────────────────────────────────────────────────────────────────────────
# Stage 8 — resolved package
# ─────────────────────────────────────────────────────────────────────────────


class ResolvedPackageSummary(BaseModel):
    """View of the assembled package surfaced on the /render response."""

    package_path: str          # absolute path to resolved_package.json
    output_dir: str            # absolute path to the package root
    page_count: int
    total_warnings: int
    asset_summary: AssetSummary


class RenderResponse(BaseModel):
    """Response shape.

    `status` is "success" when validation passed and all stages
    completed cleanly, "warn" when there are non-blocking warnings,
    "error" when Stage 1 raised a critical issue that prevents the
    chassis from rendering.

    Phase B added `cover_validation` (Stage 4) and `copy_warnings`
    (Stage 3). Phase C added `layout_plan` (Stage 7) and
    `component_count` (Stage 6). Phase D adds `package_path` /
    `output_dir` (Stage 8 — local-disk artifact location) and
    `asset_summary` (Stage 5 counts).
    """

    status: str
    validated_brand_tokens: Optional[BrandTokensResolved] = None
    font_config: Optional[FontConfig] = None
    cover_validation: Optional[CoverValidation] = None
    copy_warnings: list[CopyWarning] = Field(default_factory=list)
    layout_plan: Optional[LayoutPlanSummary] = None
    component_count: int = 0
    asset_summary: Optional[AssetSummary] = None
    package_path: Optional[str] = None
    output_dir: Optional[str] = None
    page_count: Optional[int] = None
    total_warnings: int = 0
    errors: list[ValidationIssue] = Field(default_factory=list)
    warnings: list[ValidationIssue] = Field(default_factory=list)
