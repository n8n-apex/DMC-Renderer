"""Tests for the axis-driven texture-template registry."""
from __future__ import annotations

from stages.texture_templates import texture_prompt


def test_known_combo_uses_material_vocabulary() -> None:
    prompt, neg = texture_prompt(role="texture", texture_axis="marble_paper", ground_mode="light")
    assert "marbled" in prompt.lower()
    assert "light" in prompt.lower()
    assert "logo" in neg.lower()


def test_ground_mode_dark_tints_prompt() -> None:
    prompt, _ = texture_prompt(role="texture", texture_axis="photo", ground_mode="dark")
    assert "dark" in prompt.lower()


def test_brief_fields_incorporated() -> None:
    prompt, neg = texture_prompt(
        role="gradient", texture_axis="smooth", ground_mode="mixed",
        style_prompt="STYLE-DNA-XYZ", material="brushed parchment",
        negative_prompt="warm tones, grunge",
    )
    assert "STYLE-DNA-XYZ" in prompt
    assert "brushed parchment" in prompt
    assert neg == "warm tones, grunge"


def test_unknown_axis_falls_back() -> None:
    prompt, _ = texture_prompt(role="texture", texture_axis="nonexistent")
    assert isinstance(prompt, str) and prompt


def test_deterministic() -> None:
    a = texture_prompt(role="scene", texture_axis="photo", ground_mode="dark")
    b = texture_prompt(role="scene", texture_axis="photo", ground_mode="dark")
    assert a == b
