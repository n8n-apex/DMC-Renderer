"""Stage Onboard-4 — reconcile signals into a BrandProfile + OnboardResult.

Pure function. The ONLY place values are bound. Applies the fallback
chains, records provenance + per-field confidence, and decides
needs_review + status. Vision references are dereferenced into measured
palette hex here (vision never carries a hex itself).
"""

from __future__ import annotations

from typing import Optional

from models import BrandProfile
from models_onboard import (
    DomSignals,
    OnboardDiagnostics,
    OnboardRequest,
    OnboardResult,
    PixelPalette,
    VisionReading,
)

CONFIDENCE_THRESHOLD = 0.6
CRITICAL_FIELDS = ("brand_primary", "brand_accent", "font_body")

_DEFAULT_PRIMARY = "#222222"
_DEFAULT_ACCENT = "#888888"
_DEFAULT_NEUTRAL_DARK = "#0F0F1F"
_DEFAULT_NEUTRAL_MID = "#7A7A8C"
_DEFAULT_NEUTRAL_LIGHT = "#FFFFFF"


def _palette_hex(palette: PixelPalette, idx: Optional[int]) -> Optional[str]:
    """Dereference a vision role index into a measured hex, or None if the
    index is missing/out-of-range.
    """
    if idx is None:
        return None
    if 0 <= idx < len(palette.colors):
        return palette.colors[idx].hex
    return None


def _saturation(hexv: str) -> float:
    r = int(hexv[1:3], 16); g = int(hexv[3:5], 16); b = int(hexv[5:7], 16)
    mx, mn = max(r, g, b), min(r, g, b)
    return 0.0 if mx == 0 else (mx - mn) / mx


def _most_saturated(
    palette: PixelPalette, *, exclude: Optional[str] = None
) -> Optional[str]:
    """Highest-saturation palette color, skipping `exclude` (e.g. the
    already-chosen primary) so primary and accent don't collide. Prefers
    clearly chromatic colors; if everything left is near-neutral, returns
    the most-saturated remaining color anyway (better than nothing).
    """
    candidates = [c for c in palette.colors if c.hex != exclude]
    if not candidates:
        return None
    chromatic = [c for c in candidates if _saturation(c.hex) >= 0.15]
    pool = chromatic or candidates
    return max(pool, key=lambda c: _saturation(c.hex)).hex


def reconcile(
    *,
    dom: DomSignals,
    palette: PixelPalette,
    vision: Optional[VisionReading],
    request: OnboardRequest,
    capture_status: str,
) -> OnboardResult:
    flat = request.flat_hex_fallback
    confidence: dict[str, float] = {}
    provenance: dict[str, str] = {}

    def set_field(name: str, value: str, prov: str, conf: float) -> str:
        provenance[name] = prov
        confidence[name] = conf
        return value

    # brand_primary
    v_primary = _palette_hex(palette, vision.role_refs.primary) if vision else None
    if v_primary is not None:
        brand_primary = set_field(
            "brand_primary", v_primary, "vision_role+pixel",
            (vision.confidence or {}).get("primary", 0.7),
        )
    elif palette.darkest_idx is not None:
        brand_primary = set_field(
            "brand_primary", palette.colors[palette.darkest_idx].hex,
            "pixel_sample", 0.5,
        )
    elif flat is not None:
        brand_primary = set_field("brand_primary", flat.dark, "flat_hex_fallback", 0.3)
    else:
        brand_primary = set_field("brand_primary", _DEFAULT_PRIMARY, "default", 0.0)

    # brand_accent — must differ from primary; exclude it from the
    # pixel heuristic so a brand whose darkest color is also its most
    # saturated doesn't get the same hex for both roles.
    v_accent = _palette_hex(palette, vision.role_refs.accent) if vision else None
    accent_pixel = _most_saturated(palette, exclude=brand_primary)
    if v_accent is not None:
        brand_accent = set_field(
            "brand_accent", v_accent, "vision_role+pixel",
            (vision.confidence or {}).get("accent", 0.7),
        )
    elif accent_pixel is not None:
        brand_accent = set_field(
            "brand_accent", accent_pixel, "pixel_sample", 0.5,
        )
    elif flat is not None:
        brand_accent = set_field("brand_accent", flat.accent, "flat_hex_fallback", 0.3)
    else:
        brand_accent = set_field("brand_accent", _DEFAULT_ACCENT, "default", 0.0)

    # brand_neutral_light
    v_light = _palette_hex(palette, vision.role_refs.neutral_light) if vision else None
    if v_light is not None:
        brand_neutral_light = set_field(
            "brand_neutral_light", v_light, "vision_role+pixel",
            (vision.confidence or {}).get("neutral_light", 0.7),
        )
    elif palette.lightest_idx is not None:
        brand_neutral_light = set_field(
            "brand_neutral_light", palette.colors[palette.lightest_idx].hex,
            "pixel_sample", 0.5,
        )
    elif flat is not None:
        brand_neutral_light = set_field(
            "brand_neutral_light", flat.light, "flat_hex_fallback", 0.3,
        )
    else:
        brand_neutral_light = set_field(
            "brand_neutral_light", _DEFAULT_NEUTRAL_LIGHT, "default", 0.0,
        )

    # brand_neutral_dark
    v_dark = _palette_hex(palette, vision.role_refs.neutral_dark) if vision else None
    if v_dark is not None:
        brand_neutral_dark = set_field(
            "brand_neutral_dark", v_dark, "vision_role+pixel",
            (vision.confidence or {}).get("neutral_dark", 0.7),
        )
    elif palette.darkest_idx is not None:
        brand_neutral_dark = set_field(
            "brand_neutral_dark", palette.colors[palette.darkest_idx].hex,
            "pixel_sample", 0.5,
        )
    else:
        brand_neutral_dark = set_field(
            "brand_neutral_dark", _DEFAULT_NEUTRAL_DARK, "default", 0.2,
        )

    # brand_neutral_mid
    v_mid = _palette_hex(palette, vision.role_refs.neutral_mid) if vision else None
    if v_mid is not None:
        brand_neutral_mid = set_field(
            "brand_neutral_mid", v_mid, "vision_role+pixel",
            (vision.confidence or {}).get("neutral_mid", 0.7),
        )
    else:
        brand_neutral_mid = set_field(
            "brand_neutral_mid", _DEFAULT_NEUTRAL_MID, "default", 0.2,
        )

    # fonts
    if dom.font_head:
        font_head = set_field("font_head", dom.font_head, "dom_token", 0.9)
    else:
        provenance["font_head"] = "default"; confidence["font_head"] = 0.0
        font_head = None
    if dom.font_body:
        font_body = set_field("font_body", dom.font_body, "dom_token", 0.9)
    else:
        provenance["font_body"] = "default"; confidence["font_body"] = 0.0
        font_body = None

    # perceptual axes (vision-only; null if no vision)
    axes = vision.axes if vision else None
    brand_profile = BrandProfile(
        brand_primary=brand_primary,
        brand_accent=brand_accent,
        brand_neutral_dark=brand_neutral_dark,
        brand_neutral_mid=brand_neutral_mid,
        brand_neutral_light=brand_neutral_light,
        font_head=font_head,
        font_body=font_body,
        accent_mechanic=axes.accent_mechanic if axes else None,
        ground_mode=axes.ground_mode if axes else None,
        texture=axes.texture if axes else None,
        headline_type=axes.headline_type if axes else None,
        palette=axes.palette if axes else None,
        qr_enabled=axes.qr_enabled if axes else None,
        density=axes.density if axes else None,
    )

    # review + status
    review_reasons: list[str] = []
    for field in CRITICAL_FIELDS:
        conf = confidence.get(field, 0.0)
        prov = provenance.get(field, "default")
        if conf < CONFIDENCE_THRESHOLD:
            review_reasons.append(
                f"{field}: low confidence ({conf:.2f}, source={prov})"
            )
    if vision is None:
        review_reasons.append("vision layer unavailable — colors from pixel/fallback only")

    needs_review = len(review_reasons) > 0

    primary_defaulted = provenance.get("brand_primary") == "default"
    accent_defaulted = provenance.get("brand_accent") == "default"
    if primary_defaulted and accent_defaulted:
        status = "failed"
    elif needs_review:
        status = "partial"
    else:
        status = "success"

    return OnboardResult(
        record_id=request.record_id,
        job_id="",  # filled by the orchestrator
        status=status,
        brand_profile=brand_profile,
        field_confidence=confidence,
        provenance=provenance,
        needs_review=needs_review,
        review_reasons=review_reasons,
        diagnostics=OnboardDiagnostics(
            render_mode=capture_status,
            palette_size=len(palette.colors),
        ),
    )
