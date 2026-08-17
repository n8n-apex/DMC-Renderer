from __future__ import annotations

import hashlib
import json
from pathlib import Path

from composition_registry.calibrate_capacity import write_calibration_report
from composition_registry.capacity import (
    CapacityInput,
    estimate_region_capacity,
    measure_wrapped_lines,
    word_count,
)
from composition_registry.schema import RegionSpec


ROOT = Path(__file__).resolve().parents[3]
FONT = ROOT / "research" / "v7-renderer" / "fonts" / "SourceSans3[wght].ttf"
REGISTRY = ROOT / "research" / "composition_registry" / "families" / "dmc-v1.json"


def region(*, max_words: int = 40, max_lines: int = 12) -> RegionSpec:
    return RegionSpec.model_validate(
        {
            "region_id": "narrative",
            "semantic_purpose": "test narrative",
            "required": True,
            "width_mm": 80,
            "height_mm": 80,
            "allowed_element_kinds": ["body"],
            "capacities": [
                {
                    "language": "de",
                    "min_words": 0,
                    "target_words": 20,
                    "max_words": max_words,
                    "max_wrapped_lines": max_lines,
                    "min_font_pt": 9.5,
                    "max_font_pt": 12,
                },
                {
                    "language": "en",
                    "min_words": 0,
                    "target_words": 22,
                    "max_words": max_words + 4,
                    "max_wrapped_lines": max_lines,
                    "min_font_pt": 9.5,
                    "max_font_pt": 12,
                },
            ],
            "max_items": 3,
            "image_aspect_ratio_min": 0.75,
            "image_aspect_ratio_max": 1.5,
        }
    )


def sample(
    text: str,
    *,
    font_size_pt: float = 10.5,
    image_aspect_ratio: float | None = None,
    stat_count: int = 0,
    list_item_count: int = 0,
) -> CapacityInput:
    return CapacityInput(
        language="de",
        content_by_ref={"content.body": text},
        selected_content_refs=("content.body",),
        font_path=str(FONT),
        font_size_pt=font_size_pt,
        image_aspect_ratio=image_aspect_ratio,
        stat_count=stat_count,
        list_item_count=list_item_count,
    )


def test_word_count_handles_german_compounds_and_numbers() -> None:
    assert word_count("UX-First Modernisierung spart 83 Prozent.") == 5


def test_wrapped_line_measurement_uses_actual_bundled_font() -> None:
    text = "Eine belastbare Zeile mit mehreren deutschen Wörtern. " * 4

    narrow = measure_wrapped_lines(text, FONT, font_size_pt=10, width_mm=45)
    wide = measure_wrapped_lines(text, FONT, font_size_pt=10, width_mm=120)

    assert narrow > wide >= 1


def test_minimum_font_size_is_a_hard_capacity_failure() -> None:
    result = estimate_region_capacity(region(), sample("Kurzer Text", font_size_pt=8))

    assert result.status == "does_not_fit"
    assert "below_minimum_font_size" in result.violation_codes


def test_image_aspect_ratio_is_checked() -> None:
    result = estimate_region_capacity(
        region(), sample("Kurzer Text", image_aspect_ratio=2.0)
    )

    assert result.status == "does_not_fit"
    assert "image_aspect_ratio_out_of_range" in result.violation_codes


def test_stat_count_is_checked_independently() -> None:
    result = estimate_region_capacity(region(), sample("Text", stat_count=4))

    assert "stat_count_exceeded" in result.violation_codes


def test_list_item_count_is_checked_independently() -> None:
    result = estimate_region_capacity(region(), sample("Text", list_item_count=4))

    assert "list_item_count_exceeded" in result.violation_codes


def test_near_limit_is_distinct_from_fit_and_failure() -> None:
    text = "wort " * 37

    result = estimate_region_capacity(region(max_words=40, max_lines=30), sample(text))

    assert result.status == "near_limit"


def test_region_height_bounds_wrapped_lines_even_below_declared_max() -> None:
    tall_text = "Eine belastbare Zeile mit mehreren deutschen Wörtern. " * 6

    spec = region(max_words=400, max_lines=30)
    short_region = spec.model_copy(update={"height_mm": 15.0})
    result = estimate_region_capacity(short_region, sample(tall_text))

    assert result.status == "does_not_fit"
    assert "height_line_budget_exceeded" in result.violation_codes

    generous = estimate_region_capacity(spec, sample(tall_text))
    assert "height_line_budget_exceeded" not in generous.violation_codes


def test_exceeding_target_words_is_at_least_near_limit() -> None:
    text = "wort " * 25

    result = estimate_region_capacity(region(max_words=200, max_lines=30), sample(text))

    assert result.status == "near_limit"
    below_target = estimate_region_capacity(
        region(max_words=200, max_lines=30), sample("wort " * 12)
    )
    assert below_target.status == "fits"


def test_variant_envelope_scale_tightens_every_budget() -> None:
    text = "wort " * 18

    full = estimate_region_capacity(
        region(max_words=40, max_lines=30),
        sample(text).model_copy(update={"envelope_scale": 1.0}),
    )
    tightened = estimate_region_capacity(
        region(max_words=40, max_lines=30),
        sample(text).model_copy(update={"envelope_scale": 0.4}),
    )

    assert full.status in {"fits", "near_limit"}
    assert tightened.status == "does_not_fit"
    assert "word_count_exceeded" in tightened.violation_codes


def test_alias_inflation_is_excluded_by_selected_content_refs() -> None:
    capacity_input = CapacityInput(
        language="de",
        content_by_ref={
            "content.page4.body": "Nur kanonischer Inhalt",
            "legacy.page4.einleitung": "Nur kanonischer Inhalt",
            "legacy.page4.body": "Nur kanonischer Inhalt",
        },
        selected_content_refs=("content.page4.body",),
        font_path=str(FONT),
        font_size_pt=10.5,
    )

    result = estimate_region_capacity(region(), capacity_input)

    assert result.word_count == 3
    assert result.evaluated_content_refs == ("content.page4.body",)


def test_calibration_report_is_separate_and_does_not_mutate_registry(
    tmp_path: Path,
) -> None:
    before_hash = hashlib.sha256(REGISTRY.read_bytes()).hexdigest()
    report_path = tmp_path / "capacity-calibration.json"

    write_calibration_report(
        [
            {
                "sample_id": "boundary.de",
                "html": "<p>Grenzprobe</p>",
                "selector": "p",
            }
        ],
        report_path,
        measurer=lambda item: {
            "wrapped_lines": 1,
            "bounding_box": {"x": 0, "y": 0, "width": 80, "height": 12},
        },
    )

    report = json.loads(report_path.read_text())
    assert report["schema_version"] == "1.0"
    assert report["measurements"][0]["sample_id"] == "boundary.de"
    assert hashlib.sha256(REGISTRY.read_bytes()).hexdigest() == before_hash
