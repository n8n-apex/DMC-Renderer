"""The production print profile is a printer-gated template and must stay blocked."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT / "research") not in sys.path:
    sys.path.insert(0, str(ROOT / "research"))

from postprocessor.profiles.schema import (  # noqa: E402
    PrintProfileFailure,
    assert_profile_for_export,
    load_print_profile,
)


TEMPLATE_PATH = (
    ROOT / "research" / "postprocessor" / "profiles" / "dmc_print_production_v1.json"
)
ICC_FIXTURE = ROOT / "research" / "postprocessor" / "tests" / "fixtures" / "srgb.icc"

PRINTER_GATED_FIELDS = (
    "pdf_standard",
    "icc_path",
    "icc_sha256",
    "color_space",
    "bleed_mm",
    "crop_marks",
    "minimum_image_dpi",
    "maximum_total_area_coverage_percent",
    "font_policy",
    "transparency_policy",
    "flattening_policy",
    "preserve_searchable_text",
)


def test_template_declares_every_printer_supplied_value_as_null() -> None:
    payload = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))

    assert payload["profile_id"] == "dmc_print_production_v1"
    assert payload["production_allowed"] is False
    assert payload["status"] == "awaiting_printer_approval"
    for field in PRINTER_GATED_FIELDS:
        entry = payload[field]
        assert entry["value"] is None, field
        assert entry["required_from"] == "printer", field


def test_loader_rejects_template_for_any_export() -> None:
    with pytest.raises(PrintProfileFailure) as caught:
        load_print_profile(TEMPLATE_PATH)

    assert caught.value.code == "print_profile_blocked_template"


def test_doctored_template_without_status_is_still_incomplete(tmp_path: Path) -> None:
    payload = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))
    payload.pop("status")
    doctored = tmp_path / "doctored.json"
    doctored.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(PrintProfileFailure) as caught:
        load_print_profile(doctored)

    assert caught.value.code == "print_profile_incomplete"


def test_filled_template_without_printer_approval_stays_blocked(tmp_path: Path) -> None:
    import hashlib

    filled = {
        "schema_version": "1.0",
        "profile_id": "dmc_print_production_v1",
        "version": "1.0.0",
        "pdf_standard": "PDF/X-4",
        "icc_path": str(ICC_FIXTURE),
        "icc_sha256": hashlib.sha256(ICC_FIXTURE.read_bytes()).hexdigest(),
        "color_space": "CMYK",
        "bleed_mm": 3,
        "crop_marks": True,
        "minimum_image_dpi": 300,
        "maximum_total_area_coverage_percent": 300,
        "font_policy": "embed_all",
        "transparency_policy": "preserve",
        "flattening_policy": "none",
        "preserve_searchable_text": True,
        "production_allowed": False,
    }
    path = tmp_path / "filled.json"
    path.write_text(json.dumps(filled), encoding="utf-8")

    profile = load_print_profile(path)

    with pytest.raises(PrintProfileFailure) as caught:
        assert_profile_for_export(profile, production=True)

    assert caught.value.code == "print_profile_not_production_approved"
