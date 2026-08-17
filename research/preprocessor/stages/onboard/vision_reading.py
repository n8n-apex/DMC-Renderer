"""Stage Onboard-3 — vision reading via OpenRouter (default Sonnet 4.6).

The "eye": looks at the screenshots + the MEASURED palette and assigns
semantic roles by INDEX (never a hex) plus the perceptual axes. Returns
None on any failure (missing key, API error, unparseable response) so the
reconcile layer degrades gracefully.
"""

from __future__ import annotations

import json
from typing import Optional

import httpx

from models_onboard import (
    DomSignals,
    PixelPalette,
    VisionAxes,
    VisionReading,
    VisionRoleRefs,
)
from stages.onboard._imaging import encode_image_data_url

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_TIMEOUT = 60.0

_SYSTEM_PROMPT = (
    "You are an expert brand and visual designer. You are shown screenshots "
    "of a company's website plus a list of colors that have ALREADY been "
    "measured from the page (each with an index). Your job is judgment, not "
    "measurement: decide which MEASURED color (by index) plays each brand "
    "role, and classify the brand's visual axes. NEVER output a hex code — "
    "only indices into the provided palette. If unsure, use null."
)

_RESPONSE_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "brand_vision_reading",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "role_refs": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "primary": {"type": ["integer", "null"]},
                        "accent": {"type": ["integer", "null"]},
                        "neutral_dark": {"type": ["integer", "null"]},
                        "neutral_mid": {"type": ["integer", "null"]},
                        "neutral_light": {"type": ["integer", "null"]},
                    },
                    "required": ["primary", "accent", "neutral_dark",
                                 "neutral_mid", "neutral_light"],
                },
                "axes": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "accent_mechanic": {"type": ["string", "null"]},
                        "ground_mode": {"type": ["string", "null"]},
                        "texture": {"type": ["string", "null"]},
                        "headline_type": {"type": ["string", "null"]},
                    },
                    "required": ["accent_mechanic", "ground_mode",
                                 "texture", "headline_type"],
                },
                "confidence": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "primary": {"type": ["number", "null"]},
                        "accent": {"type": ["number", "null"]},
                        "neutral_dark": {"type": ["number", "null"]},
                        "neutral_mid": {"type": ["number", "null"]},
                        "neutral_light": {"type": ["number", "null"]},
                    },
                    "required": ["primary", "accent", "neutral_dark",
                                 "neutral_mid", "neutral_light"],
                },
                "notes": {"type": ["string", "null"]},
            },
            "required": ["role_refs", "axes", "confidence", "notes"],
        },
    },
}


# Allowed §4.0 vocabularies per axis. The strict JSON schema only
# constrains axes to "string"; this whitelist is the real guard so a
# model that returns an off-vocabulary label can't pollute BrandProfile.
_ALLOWED_AXES: dict[str, frozenset[str]] = {
    "accent_mechanic": frozenset({"contrasting_hue", "tonal_same_hue"}),
    "ground_mode": frozenset({
        "cream_textured", "cool_light", "role_split", "tri",
        "saturated_dark+light",
    }),
    "texture": frozenset({"marble_paper", "crumpled_paper", "smooth", "photo"}),
    "headline_type": frozenset({"serif", "sans", "sans_allcaps"}),
}


def _validate_axes(axes: VisionAxes) -> VisionAxes:
    """Null out any axis value that isn't in the §4.0 allowed vocabulary."""
    def ok(field: str, value: Optional[str]) -> Optional[str]:
        return value if value in _ALLOWED_AXES[field] else None
    return VisionAxes(
        accent_mechanic=ok("accent_mechanic", axes.accent_mechanic),
        ground_mode=ok("ground_mode", axes.ground_mode),
        texture=ok("texture", axes.texture),
        headline_type=ok("headline_type", axes.headline_type),
    )


def _build_palette_prompt(palette: PixelPalette, dom: DomSignals) -> str:
    lines = ["MEASURED PALETTE (assign roles by index; do not invent colors):"]
    for i, c in enumerate(palette.colors):
        lines.append(f"  [{i}] {c.hex}  (~{c.coverage_pct:.0f}% coverage, {c.region})")
    lines.append("")
    lines.append("RESOLVED FONTS (from the DOM):")
    lines.append(f"  heading: {dom.font_head or 'unknown'}")
    lines.append(f"  body:    {dom.font_body or 'unknown'}")
    lines.append("")
    lines.append(
        "AXES — accent_mechanic in {contrasting_hue, tonal_same_hue}; "
        "ground_mode in {cream_textured, cool_light, role_split, tri, "
        "saturated_dark+light}; texture in {marble_paper, crumpled_paper, "
        "smooth, photo}; headline_type in {serif, sans, sans_allcaps}."
    )
    return "\n".join(lines)


# Thin alias preserving the historical name/signature used by this module
# and its tests. The real downscale + JPEG-recompress logic now lives in
# stages.onboard._imaging (shared with the brand-brief layer). This is SAFE
# for accuracy: the vision model only picks INDICES into the palette that
# pixel_palette measured from the original PNG, so compression here cannot
# change any stored hex value.
def _encode_image(path: Optional[str], *, max_edge: int = 1568) -> Optional[str]:
    return encode_image_data_url(path, max_edge=max_edge)


def _build_messages(hero_png, fullpage_png, palette, dom) -> list[dict]:
    content: list[dict] = [{"type": "text", "text": _build_palette_prompt(palette, dom)}]
    for img in (hero_png, fullpage_png):
        data_url = _encode_image(img)
        if data_url:
            content.append({"type": "image_url", "image_url": {"url": data_url}})
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": content},
    ]


def _validate_indices(reading: VisionReading, palette_len: int) -> VisionReading:
    """Null out any role index that is out of range for the palette."""
    rr = reading.role_refs
    def ok(i: Optional[int]) -> Optional[int]:
        return i if (i is not None and 0 <= i < palette_len) else None
    reading.role_refs = VisionRoleRefs(
        primary=ok(rr.primary), accent=ok(rr.accent),
        neutral_dark=ok(rr.neutral_dark), neutral_mid=ok(rr.neutral_mid),
        neutral_light=ok(rr.neutral_light),
    )
    return reading


async def read_vision(
    *,
    hero_png: Optional[str],
    fullpage_png: Optional[str],
    palette: PixelPalette,
    dom: DomSignals,
    api_key: Optional[str],
    model: str,
    http_client: Optional[httpx.AsyncClient] = None,
    timeout: float = _TIMEOUT,
) -> Optional[VisionReading]:
    """Call the vision model. Returns a VisionReading, or None on any
    failure (caller degrades to pixel/flat-hex fallback).
    """
    if not api_key or not hero_png:
        return None

    payload = {
        "model": model,
        "messages": _build_messages(hero_png, fullpage_png, palette, dom),
        "temperature": 0,
        "response_format": _RESPONSE_SCHEMA,
    }
    headers = {"Authorization": f"Bearer {api_key}",
               "Content-Type": "application/json"}

    owns = http_client is None
    client = http_client or httpx.AsyncClient(timeout=timeout)
    try:
        resp = await client.post(_OPENROUTER_URL, json=payload, headers=headers)
        if resp.status_code != 200:
            return None
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        # The model returns null confidence for roles it's unsure about, but
        # VisionReading.confidence is dict[str, float] — a null would raise
        # ValidationError and lose the ENTIRE reading. Drop non-numeric
        # entries (bool excluded: it's an int subclass).
        raw_conf = parsed.get("confidence") or {}
        confidence = {
            k: float(v) for k, v in raw_conf.items()
            if isinstance(v, (int, float)) and not isinstance(v, bool)
        }
        reading = VisionReading(
            role_refs=VisionRoleRefs(**(parsed.get("role_refs") or {})),
            axes=VisionAxes(**(parsed.get("axes") or {})),
            confidence=confidence,
            notes=parsed.get("notes"),
        )
        reading = _validate_indices(reading, len(palette.colors))
        reading.axes = _validate_axes(reading.axes)
        return reading
    except (httpx.HTTPError, KeyError, ValueError, TypeError):
        return None
    finally:
        if owns:
            await client.aclose()
