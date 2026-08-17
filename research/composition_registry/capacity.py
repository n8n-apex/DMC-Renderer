"""Deterministic capacity estimates for composition regions.

The estimator is intentionally conservative. It is used before rendering to
reject assignments that are known to exceed a calibrated family envelope.
Browser measurements live in ``calibrate_capacity.py`` and are kept separate
from this deterministic decision path.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from PIL import ImageFont
from pydantic import BaseModel, ConfigDict, Field

from composition_registry.schema import RegionSpec


_WORD_RE = re.compile(
    r"[0-9A-Za-zÄÖÜäöüß]+(?:-[0-9A-Za-zÄÖÜäöüß]+)*"
)


class CapacityInput(BaseModel):
    """Content and presentation facts used for one region decision."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    language: Literal["de", "en"]
    content_by_ref: dict[str, str]
    selected_content_refs: tuple[str, ...]
    font_path: str
    font_size_pt: float = Field(gt=0)
    image_aspect_ratio: float | None = Field(default=None, gt=0)
    stat_count: int = Field(default=0, ge=0)
    list_item_count: int = Field(default=0, ge=0)
    # Variant envelopes may only tighten the family envelope, never widen it.
    envelope_scale: float = Field(default=1.0, gt=0, le=1.0)
    # Vertical room spent on things that are not wrapped lines: the space
    # between blocks and any heading above them. Counting lines alone
    # over-estimates how much copy a region holds, which is how copy gets
    # approved for a region the renderer then overflows.
    block_spacing_mm: float = Field(default=3.0, ge=0)
    heading_block_mm: float = Field(default=14.0, ge=0)


class CapacityAssessment(BaseModel):
    """Stable result consumed by composition selection and diagnostics."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["fits", "near_limit", "does_not_fit"]
    word_count: int = Field(ge=0)
    wrapped_line_count: int = Field(ge=0)
    evaluated_content_refs: tuple[str, ...]
    violation_codes: tuple[str, ...] = ()


def word_count(text: str) -> int:
    """Count words while treating a hyphenated compound as one word."""

    return len(_WORD_RE.findall(text))


def measure_wrapped_lines(
    text: str,
    font_path: Path,
    *,
    font_size_pt: float,
    width_mm: float,
) -> int:
    """Measure greedy wrapping with the bundled production font."""

    if not text.strip():
        return 0

    font_size_px = max(1, round(font_size_pt * 96 / 72))
    width_px = max(1.0, width_mm * 96 / 25.4)
    font = ImageFont.truetype(str(font_path), font_size_px)
    space_width = float(font.getlength(" "))

    lines = 1
    current_width = 0.0
    for token in text.split():
        token_width = float(font.getlength(token))
        proposed = token_width if current_width == 0 else current_width + space_width + token_width
        if current_width > 0 and proposed > width_px:
            lines += 1
            current_width = token_width
        else:
            current_width = proposed
    return lines


def estimate_region_capacity(
    region: RegionSpec,
    capacity_input: CapacityInput,
) -> CapacityAssessment:
    """Evaluate only canonical selected references against a region envelope."""

    violations: list[str] = []
    selected_text: list[str] = []
    for content_ref in capacity_input.selected_content_refs:
        if content_ref not in capacity_input.content_by_ref:
            violations.append("unknown_content_ref")
            continue
        selected_text.append(capacity_input.content_by_ref[content_ref])

    text = " ".join(selected_text)
    measured_words = word_count(text)
    measured_lines = measure_wrapped_lines(
        text,
        font_path=Path(capacity_input.font_path),
        font_size_pt=capacity_input.font_size_pt,
        width_mm=region.width_mm,
    )
    language_capacity = next(
        capacity
        for capacity in region.capacities
        if capacity.language == capacity_input.language
    )
    scale = capacity_input.envelope_scale
    max_words_budget = max(1, int(language_capacity.max_words * scale))
    max_lines_budget = max(1, int(language_capacity.max_wrapped_lines * scale))
    target_words_budget = (
        max(1, int(language_capacity.target_words * scale))
        if language_capacity.target_words > 0
        else 0
    )
    # Physical line budget from the region height at the tightest plausible
    # leading (1.2). A declared max_wrapped_lines can never exceed what the
    # region is physically tall enough to hold.
    line_height_mm = capacity_input.font_size_pt * 1.2 * 25.4 / 72
    block_count = max(1, len(capacity_input.selected_content_refs))
    non_text_mm = (
        block_count * capacity_input.block_spacing_mm
        + (
            # Only a MIXED region pays for a heading above its prose. In a
            # heading-only region the heading is the measured text itself, so
            # charging it again would double-count.
            capacity_input.heading_block_mm
            if {"heading", "body"} <= set(region.allowed_element_kinds)
            else 0.0
        )
    )
    usable_height_mm = max(line_height_mm, region.height_mm - non_text_mm)
    height_line_budget = max(1, int(usable_height_mm / line_height_mm))

    if capacity_input.font_size_pt < language_capacity.min_font_pt:
        violations.append("below_minimum_font_size")
    if capacity_input.font_size_pt > language_capacity.max_font_pt:
        violations.append("above_maximum_font_size")
    if measured_words > max_words_budget:
        violations.append("word_count_exceeded")
    if measured_lines > max_lines_budget:
        violations.append("wrapped_line_count_exceeded")
    if measured_lines > height_line_budget:
        violations.append("height_line_budget_exceeded")
    if capacity_input.image_aspect_ratio is not None:
        minimum_aspect = region.image_aspect_ratio_min
        maximum_aspect = region.image_aspect_ratio_max
        if (
            minimum_aspect is not None
            and capacity_input.image_aspect_ratio < minimum_aspect
        ) or (
            maximum_aspect is not None
            and capacity_input.image_aspect_ratio > maximum_aspect
        ):
            violations.append("image_aspect_ratio_out_of_range")
    if region.max_items is not None and capacity_input.stat_count > region.max_items:
        violations.append("stat_count_exceeded")
    if (
        region.max_items is not None
        and capacity_input.list_item_count > region.max_items
    ):
        violations.append("list_item_count_exceeded")

    if violations:
        status: Literal["fits", "near_limit", "does_not_fit"] = "does_not_fit"
    else:
        word_ratio = measured_words / max_words_budget
        line_ratio = measured_lines / max_lines_budget
        near_minimum_font = (
            capacity_input.font_size_pt - language_capacity.min_font_pt <= 0.25
        )
        above_target = (
            target_words_budget > 0 and measured_words > target_words_budget
        )
        status = (
            "near_limit"
            if word_ratio >= 0.9
            or line_ratio >= 0.9
            or near_minimum_font
            or above_target
            else "fits"
        )

    return CapacityAssessment(
        status=status,
        word_count=measured_words,
        wrapped_line_count=measured_lines,
        evaluated_content_refs=capacity_input.selected_content_refs,
        violation_codes=tuple(dict.fromkeys(violations)),
    )
