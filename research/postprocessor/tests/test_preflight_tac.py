"""Real CMYK total-area-coverage measurement replaces the constant failure."""

from __future__ import annotations

import sys
from pathlib import Path

import fitz
import pytest


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT / "research") not in sys.path:
    sys.path.insert(0, str(ROOT / "research"))

from postprocessor.preflight import (  # noqa: E402
    measure_max_total_area_coverage_percent,
    preflight_print,
)
from postprocessor.profiles.schema import load_print_profile  # noqa: E402


PROFILE_PATH = ROOT / "research" / "postprocessor" / "profiles" / "dmc_print_test.json"


def make_cmyk_pdf(path: Path, fill: tuple[float, float, float, float]) -> None:
    document = fitz.open()
    page = document.new_page(width=200, height=200)
    page.draw_rect(fitz.Rect(20, 20, 180, 180), color=None, fill=fill)
    document.save(str(path))
    document.close()


def check_by_id(report, check_id: str):
    return next(check for check in report.checks if check.check_id == check_id)


def test_black_only_page_measures_one_hundred_percent(tmp_path: Path) -> None:
    pdf = tmp_path / "black-only.pdf"
    make_cmyk_pdf(pdf, (0, 0, 0, 1))

    measured = measure_max_total_area_coverage_percent(pdf)

    assert measured == pytest.approx(100.0, abs=1.0)


def test_rich_four_color_page_measures_full_coverage_sum(tmp_path: Path) -> None:
    pdf = tmp_path / "rich.pdf"
    make_cmyk_pdf(pdf, (0.8, 0.7, 0.6, 1.0))

    measured = measure_max_total_area_coverage_percent(pdf)

    assert measured == pytest.approx(310.0, abs=1.0)


def test_measurement_is_deterministic(tmp_path: Path) -> None:
    pdf = tmp_path / "rich.pdf"
    make_cmyk_pdf(pdf, (0.8, 0.7, 0.6, 1.0))

    assert measure_max_total_area_coverage_percent(
        pdf
    ) == measure_max_total_area_coverage_percent(pdf)


def test_cmyk_profile_fails_when_measured_tac_exceeds_limit(tmp_path: Path) -> None:
    pdf = tmp_path / "rich.pdf"
    make_cmyk_pdf(pdf, (0.8, 0.7, 0.6, 1.0))
    profile = load_print_profile(PROFILE_PATH).model_copy(
        update={"color_space": "CMYK", "maximum_total_area_coverage_percent": 300.0}
    )

    report = preflight_print(pdf, pdf, profile)

    tac_check = check_by_id(report, "total_area_coverage")
    assert tac_check.passed is False
    assert "310" in tac_check.detail
    assert "total_area_coverage" in report.failed_check_ids


def test_cmyk_profile_passes_when_measured_tac_is_within_limit(tmp_path: Path) -> None:
    pdf = tmp_path / "black-only.pdf"
    make_cmyk_pdf(pdf, (0, 0, 0, 1))
    profile = load_print_profile(PROFILE_PATH).model_copy(
        update={"color_space": "CMYK", "maximum_total_area_coverage_percent": 300.0}
    )

    report = preflight_print(pdf, pdf, profile)

    tac_check = check_by_id(report, "total_area_coverage")
    assert tac_check.passed is True
    assert "100" in tac_check.detail


def test_rgb_profile_records_informational_measurement(tmp_path: Path) -> None:
    pdf = tmp_path / "black-only.pdf"
    make_cmyk_pdf(pdf, (0, 0, 0, 1))
    profile = load_print_profile(PROFILE_PATH)

    report = preflight_print(pdf, pdf, profile)

    tac_check = check_by_id(report, "total_area_coverage")
    assert tac_check.passed is True
    assert "informational" in tac_check.detail
    assert "%" in tac_check.detail
