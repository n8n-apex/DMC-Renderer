"""Stage 5a — image prompt-builder via OpenRouter (default Sonnet 4.6).

The "prompt engineer": one BATCHED call that turns the brand design brief
(its reusable style, palette hexes, mood, lighting, texture/material, shape
language, do/don'ts) plus the report's list of specific image slots into a
per-slot fal.ai generation prompt + negative prompt.

Returns `{slot_id: {"prompt": str, "negative_prompt": str}}`. Returns `{}`
on ANY failure (no key, no brief, API error, parse error) so the caller in
`generate_assets` degrades gracefully to the `_compose_prompt` concatenation
fallback — the prompt-builder is additive, never load-bearing.
"""

from __future__ import annotations

import json
from typing import Any, Optional

import httpx

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
# A single text-only batched call over a handful of slots is fast, but the
# render path is async and best-effort, so allow generous headroom.
_TIMEOUT = 120.0

# Verbatim from the design spec §3.
_SYSTEM_PROMPT = (
    "You are an expert prompt engineer for a generative image model (fal.ai Nano Banana\n"
    "Pro / Flux). You are given a brand visual guideline (its reusable style, palette\n"
    "hexes, mood, lighting, texture/material, shape language, do/don'ts) and a list of\n"
    "specific image slots a report needs — each with a role (cover-hero background,\n"
    "status-quo scene, section background texture, atmospheric gradient), an aspect\n"
    "ratio, and the page's text context.\n"
    "\n"
    "For EACH slot, write the single best image-generation prompt and a negative prompt\n"
    "so the image is: (1) unmistakably on-brand per the guideline — apply the palette\n"
    "hexes, lighting, texture, and mood; (2) fit-for-purpose for its role and aspect;\n"
    "(3) production-safe.\n"
    "\n"
    "Hard rules:\n"
    "- Backgrounds and hero images MUST be uncluttered with clear negative space for\n"
    "  text overlaid later — no embedded words, letters, logos, UI chrome, or watermarks.\n"
    "- No real recognizable faces unless the role is explicitly a portrait.\n"
    "- Respect the guideline's avoid-list; match the aspect ratio's composition.\n"
    "- Each prompt is concrete and visual; no meta commentary.\n"
    "Output STRICT JSON: {\"prompts\": [{\"slot_id\",\"prompt\",\"negative_prompt\"}, ...]}\n"
    "covering every slot you were given."
)

_RESPONSE_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "image_prompts",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "prompts": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "slot_id": {"type": "string"},
                            "prompt": {"type": "string"},
                            "negative_prompt": {"type": "string"},
                        },
                        "required": ["slot_id", "prompt", "negative_prompt"],
                    },
                },
            },
            "required": ["prompts"],
        },
    },
}


def _brief_value(brief: Any, name: str) -> Any:
    """Read a field from a BrandDesignBrief (model or dict), tolerant of None."""
    if brief is None:
        return None
    if isinstance(brief, dict):
        return brief.get(name)
    return getattr(brief, name, None)


def _serialize_brief(brief: Any) -> str:
    """Serialize the brief fields the prompt-builder needs into a text block.

    Fields per spec §3: image_style_prompt, mood, color_usage,
    texture_material, imagery, shape_language, composition. Tolerant of a
    model OR a dict; skips fields that are empty/None.
    """
    lines: list[str] = ["BRAND VISUAL GUIDELINE:"]

    def add(label: str, value: Any) -> None:
        if value is None:
            return
        if isinstance(value, (list, tuple)):
            text = ", ".join(str(v) for v in value if v is not None)
        elif isinstance(value, dict):
            text = "; ".join(f"{k}: {v}" for k, v in value.items() if v is not None)
        else:
            text = str(value)
        if text and text.strip():
            lines.append(f"  {label}: {text.strip()}")

    add("image_style_prompt", _brief_value(brief, "image_style_prompt"))
    add("mood", _brief_value(brief, "mood"))
    add("color_usage", _brief_value(brief, "color_usage"))
    add("texture_material", _brief_value(brief, "texture_material"))

    # imagery is an ImageryGuidance (model or dict) — flatten its fields.
    imagery = _brief_value(brief, "imagery")
    if imagery is not None:
        for sub in ("style", "subjects", "treatment", "lighting", "avoid"):
            add(f"imagery.{sub}", _brief_value(imagery, sub))

    add("shape_language", _brief_value(brief, "shape_language"))
    add("composition", _brief_value(brief, "composition"))
    return "\n".join(lines)


def _serialize_specs(asset_specs: list[dict]) -> str:
    """Numbered list of the image slots the report needs."""
    lines = ["IMAGE SLOTS TO PRODUCE PROMPTS FOR:"]
    for i, spec in enumerate(asset_specs, 1):
        slot_id = spec.get("slot_id", f"slot_{i}")
        role = spec.get("role") or spec.get("image_type") or "image"
        aspect = spec.get("aspect_ratio", "auto")
        context = (spec.get("context") or "").strip()
        line = (
            f"  {i}. slot_id={slot_id!r}; role={role}; "
            f"aspect_ratio={aspect}"
        )
        if context:
            line += f"; context: {context}"
        lines.append(line)
    return "\n".join(lines)


def _build_user_prompt(design_brief: Any, asset_specs: list[dict]) -> str:
    return (
        _serialize_brief(design_brief)
        + "\n\n"
        + _serialize_specs(asset_specs)
        + "\n\nProduce the image_prompts JSON now, one entry per slot above."
    )


async def build_image_prompts(
    *,
    design_brief: Any,
    asset_specs: list[dict],
    api_key: Optional[str],
    model: str,
    http_client: Optional[httpx.AsyncClient] = None,
    timeout: float = _TIMEOUT,
) -> dict[str, dict]:
    """Batched Sonnet call. `asset_specs` items: `{slot_id, role,
    aspect_ratio, context}`.

    Returns `{slot_id: {"prompt": str, "negative_prompt": str}}`. Returns
    `{}` on any failure / no key / no brief / no specs (caller falls back
    to concatenation).
    """
    if not api_key or design_brief is None or not asset_specs:
        return {}

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",
             "content": _build_user_prompt(design_brief, asset_specs)},
        ],
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
            return {}
        # Tolerate OpenRouter's keep-alive whitespace padding via resp.json().
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        out: dict[str, dict] = {}
        for item in parsed.get("prompts") or []:
            if not isinstance(item, dict):
                continue
            slot_id = item.get("slot_id")
            prompt = item.get("prompt")
            if not slot_id or not isinstance(prompt, str) or not prompt.strip():
                continue
            negative = item.get("negative_prompt")
            out[str(slot_id)] = {
                "prompt": prompt,
                "negative_prompt": negative if isinstance(negative, str) else "",
            }
        return out
    except (httpx.HTTPError, KeyError, ValueError, TypeError):
        return {}
    finally:
        if owns:
            await client.aclose()
