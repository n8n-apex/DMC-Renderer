"""Axis-driven texture/atmosphere prompt fragments (DNA §C6 / PRD §9.2).

A registry keyed by (role, texture_axis) -> a base atmosphere fragment;
ground_mode tints it; the brand brief's style/material/negative fill it.
NO client literal — only material/atmosphere vocabulary. Standalone; wired
into the generate path in a later phase. Deterministic + brand-agnostic.
"""
from __future__ import annotations

from typing import Optional

_FRAGMENTS: dict[tuple[str, str], str] = {
    ("texture", "smooth"): "a smooth, clean abstract background surface",
    ("texture", "marble_paper"): "an elegant marbled-paper surface with subtle veining",
    ("texture", "crumpled_paper"): "a softly crumpled paper texture with gentle shadows",
    ("texture", "paper_grain"): "a fine paper-grain texture, editorial and tactile",
    ("texture", "photo"): "a darkened cinematic photographic backdrop, softly out of focus",
    ("gradient", "smooth"): "a smooth tonal gradient wash",
    ("gradient", "marble_paper"): "a marbled tonal gradient with faint veining",
    ("gradient", "crumpled_paper"): "a paper-textured tonal gradient",
    ("gradient", "paper_grain"): "a grainy tonal gradient",
    ("gradient", "photo"): "a cinematic vignette gradient over a darkened photo",
    ("scene", "smooth"): "a clean, minimal on-brand scene backdrop",
    ("scene", "photo"): "a darkened, scrimmed photographic scene so text stays legible",
}
_DEFAULT_FRAGMENT = "an abstract, on-brand background surface"

_GROUND_TINT = {
    "light": "on a light, airy ground",
    "dark": "on a deep, dark ground",
    "mixed": "with balanced light-and-dark contrast",
}

_DEFAULT_NEGATIVE = "text, words, letters, logos, watermark, people, faces"


def texture_prompt(
    *,
    role: str,
    texture_axis: str,
    ground_mode: str = "mixed",
    style_prompt: Optional[str] = None,
    material: Optional[str] = None,
    negative_prompt: Optional[str] = None,
) -> tuple[str, str]:
    """Compose a (prompt, negative_prompt) for a texture/atmosphere asset.
    Deterministic; brand values arrive via style_prompt/material/negative."""
    base = (
        _FRAGMENTS.get((role, texture_axis))
        or _FRAGMENTS.get(("texture", texture_axis))
        or _DEFAULT_FRAGMENT
    )
    tint = _GROUND_TINT.get(ground_mode, _GROUND_TINT["mixed"])
    parts = [base, tint]
    if material:
        parts.append(f"material: {material}")
    if style_prompt:
        parts.append(style_prompt)
    prompt = ", ".join(p for p in parts if p)
    negative = negative_prompt or _DEFAULT_NEGATIVE
    return prompt, negative
