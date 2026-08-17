"""Stage Onboard-6 — brand design brief via OpenRouter (default Opus 4.6).

The "art director": looks at the screenshots + the MEASURED palette + the
resolved fonts (and the axes the token pass already classified) and writes
a precise, image-generation-ready brand visual guideline. Returns None on
any failure (missing key, API error, unparseable response) so the pipeline
degrades gracefully (the brief is additive, never load-bearing for the
BrandProfile contract chain).
"""

from __future__ import annotations

import json
from typing import Optional

import httpx

from models_onboard import (
    BrandDesignBrief,
    DomSignals,
    ImageryGuidance,
    PixelPalette,
    VisionReading,
)
from stages.onboard._imaging import encode_image_data_url

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
# Opus + 2 images + a long structured guideline runs ~60-90s; a 90s cap
# trips on slower runs and loses the whole brief. Onboard is an async
# background job (no HTTP-response deadline), so allow generous headroom.
_TIMEOUT = 240.0

_SYSTEM_PROMPT = (
    "You are a senior brand designer and art director with deep experience in visual\n"
    "identity and editorial design. You are shown screenshots of a company's website,\n"
    "plus its MEASURED color palette (exact hex values from pixel analysis) and the\n"
    "fonts actually rendered on the page.\n"
    "\n"
    "Produce a precise, image-generation-ready brand visual guideline — the kind a\n"
    "designer hands to an illustrator or a generative image model so everything they\n"
    "create looks unmistakably on-brand.\n"
    "\n"
    "Rules:\n"
    "- Analyze ONLY what is visible in the screenshots plus the provided palette/fonts.\n"
    "  Never invent facts about the company.\n"
    "- Be concrete and specific. Generic words alone (\"modern, clean, professional\")\n"
    "  are useless — name the actual visual devices: lighting quality, gradient\n"
    "  direction, corner radius, whitespace density, photographic vs illustrated\n"
    "  treatment, shape language, etc.\n"
    "- Reference the REAL hex values when describing color usage.\n"
    "- image_style_prompt MUST be a single reusable paragraph an image model\n"
    "  (fal.ai / Flux / Nano Banana) can prepend to ANY subject to render it in this\n"
    "  brand's style. Include the palette hexes, mood, lighting, texture/material, and\n"
    "  rendering style. Do NOT name a specific subject — it is a style preset.\n"
    "- negative_prompt lists what would make an image look OFF-brand.\n"
    "- Output STRICT JSON matching the schema. No prose outside the JSON."
)

_RESPONSE_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "brand_design_brief",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "visual_style_summary": {"type": "string"},
                "mood": {"type": "array", "items": {"type": "string"}},
                "imagery": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "style": {"type": "string"},
                        "subjects": {"type": "string"},
                        "treatment": {"type": "string"},
                        "lighting": {"type": "string"},
                        "avoid": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["style", "subjects", "treatment",
                                 "lighting", "avoid"],
                },
                "color_usage": {"type": "string"},
                "shape_language": {"type": "string"},
                "texture_material": {"type": "string"},
                "typography_character": {"type": "string"},
                "composition": {"type": "string"},
                "iconography": {"type": "string"},
                "image_style_prompt": {"type": "string"},
                "negative_prompt": {"type": "string"},
                "confidence": {"type": "number"},
            },
            "required": [
                "visual_style_summary", "mood", "imagery", "color_usage",
                "shape_language", "texture_material", "typography_character",
                "composition", "iconography", "image_style_prompt",
                "negative_prompt", "confidence",
            ],
        },
    },
}


def _build_user_prompt(
    palette: PixelPalette, dom: DomSignals, vision: Optional[VisionReading]
) -> str:
    lines = [
        "MEASURED PALETTE (exact hexes from pixel analysis — quote these verbatim in",
        "color_usage and image_style_prompt):",
    ]
    for i, c in enumerate(palette.colors):
        lines.append(f"  [{i}] {c.hex}  (~{c.coverage_pct:.0f}% coverage)")
    lines.append("RESOLVED FONTS (from the DOM):")
    lines.append(f"  heading: {dom.font_head or 'unknown'}")
    lines.append(f"  body:    {dom.font_body or 'unknown'}")
    if vision is not None:
        ax = vision.axes
        lines.append("DESIGNER AXES (already classified by the token pass):")
        lines.append(
            f"  accent_mechanic={ax.accent_mechanic}; ground_mode={ax.ground_mode}; "
            f"texture={ax.texture}; headline_type={ax.headline_type}"
        )
    lines.append("The website screenshots are attached. Produce the brand_design_brief JSON now.")
    return "\n".join(lines)


def _build_messages(
    hero_png: Optional[str],
    fullpage_png: Optional[str],
    palette: PixelPalette,
    dom: DomSignals,
    vision: Optional[VisionReading],
) -> list[dict]:
    content: list[dict] = [
        {"type": "text", "text": _build_user_prompt(palette, dom, vision)}
    ]
    for img in (hero_png, fullpage_png):
        data_url = encode_image_data_url(img)
        if data_url:
            content.append({"type": "image_url", "image_url": {"url": data_url}})
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": content},
    ]


async def generate_brand_brief(
    *,
    hero_png: Optional[str],
    fullpage_png: Optional[str],
    palette: PixelPalette,
    dom: DomSignals,
    vision: Optional[VisionReading],
    api_key: Optional[str],
    model: str,
    http_client: Optional[httpx.AsyncClient] = None,
    timeout: float = _TIMEOUT,
) -> Optional[BrandDesignBrief]:
    """Call the brief model. Returns a BrandDesignBrief, or None on any
    failure (caller marks the result needs_review but keeps the rest).
    """
    if not api_key or not hero_png:
        return None

    payload = {
        "model": model,
        "messages": _build_messages(hero_png, fullpage_png, palette, dom, vision),
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
        return BrandDesignBrief(
            **{**parsed, "imagery": ImageryGuidance(**parsed["imagery"])}
        )
    except (httpx.HTTPError, KeyError, ValueError, TypeError):
        return None
    finally:
        if owns:
            await client.aclose()
