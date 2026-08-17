from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[3]
POSTPROCESSOR_ROOT = ROOT / "research" / "postprocessor"
if str(ROOT / "research") not in sys.path:
    sys.path.insert(0, str(ROOT / "research"))

from postprocessor.export_digital import (  # noqa: E402
    DigitalExportFailure,
    export_digital,
    validate_digital_export,
)
from postprocessor.models import DigitalExportProfile  # noqa: E402
from postprocessor.profiles.schema import (  # noqa: E402
    digital_profile_sha256,
    load_digital_profile,
)


FONT = ROOT / "research" / "v7-renderer" / "fonts" / "SourceSans3[wght].ttf"
DIGITAL_PROFILE_PATH = (
    ROOT / "research" / "postprocessor" / "profiles" / "dmc_digital_v1.json"
)


def make_pdf(path: Path, *, text: str, with_link: bool = True) -> None:
    link = (
        '<a href="https://example.com/calibrate">Kalibrieren</a>'
        if with_link
        else "Kalibrieren"
    )
    html = f"""<!doctype html><style>
    @font-face {{ font-family: DMC; src: url('{FONT.resolve().as_uri()}'); }}
    @page {{ size: A4; margin: 20mm; }}
    body {{ font-family: DMC, sans-serif; }}
    </style><h1>{text}</h1><p>Searchable body copy.</p>{link}"""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(html, wait_until="networkidle")
        page.pdf(path=str(path), prefer_css_page_size=True, tagged=True)
        browser.close()


def profile() -> DigitalExportProfile:
    return DigitalExportProfile(
        profile_id="digital-preserve-v1",
        minimum_text_preservation_ratio=0.99,
        preserve_links=True,
        preserve_page_sizes=True,
        preserve_metadata=True,
        preserve_font_references=True,
    )


def test_digital_export_preserves_text_links_sizes_metadata_and_fonts(tmp_path: Path) -> None:
    raw = tmp_path / "raw.pdf"
    output = tmp_path / "report.digital.pdf"
    make_pdf(raw, text="Digitale Ausgabe")

    report = export_digital(raw, profile(), output)

    assert output.read_bytes() == raw.read_bytes()
    assert report.accepted is True
    assert report.text_preservation_ratio == pytest.approx(1.0)
    assert report.input_links == report.output_links == ("https://example.com/calibrate",)
    assert report.input_page_sizes_mm == report.output_page_sizes_mm
    assert report.input_font_references == report.output_font_references
    assert report.metadata_preserved is True
    sidecar = output.with_suffix(".export-report.json")
    assert json.loads(sidecar.read_text(encoding="utf-8"))["output_sha256"] == report.output_sha256
    export_report = json.loads(
        (output.parent / "report.digital-export-report.json").read_text(encoding="utf-8")
    )
    assert export_report["text_preservation_ratio"] == report.text_preservation_ratio
    assert (
        export_report["text_preservation_ratio"]
        >= export_report["minimum_text_preservation_ratio"]
    )


def test_digital_export_from_stored_profile_records_profile_identity(tmp_path: Path) -> None:
    raw = tmp_path / "raw.pdf"
    output = tmp_path / "report.digital.pdf"
    make_pdf(raw, text="Profilgebundene Ausgabe")
    stored_profile = load_digital_profile(DIGITAL_PROFILE_PATH)

    report = export_digital(raw, DIGITAL_PROFILE_PATH, output)

    assert report.accepted is True
    assert report.profile_id == "dmc_digital_v1"
    report_path = output.parent / "report.digital-export-report.json"
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["report_kind"] == "digital_export_report"
    assert payload["profile_id"] == "dmc_digital_v1"
    assert payload["profile_sha256"] == digital_profile_sha256(stored_profile)
    assert payload["input_sha256"] == report.input_sha256
    assert payload["output_sha256"] == report.output_sha256
    assert payload["text_preservation_ratio"] == pytest.approx(1.0)
    assert payload["text_preservation_ratio"] >= stored_profile.minimum_text_preservation_ratio
    assert payload["minimum_text_preservation_ratio"] == stored_profile.minimum_text_preservation_ratio
    assert payload["input_link_count"] == 1
    assert payload["output_link_count"] == 1
    assert payload["links_preserved"] is True


def test_digital_export_accepts_profile_id_string(tmp_path: Path) -> None:
    raw = tmp_path / "raw.pdf"
    output = tmp_path / "report.digital.pdf"
    make_pdf(raw, text="Profil per Kennung")

    report = export_digital(raw, "dmc_digital_v1", output)

    assert report.accepted is True
    assert report.profile_id == "dmc_digital_v1"


def test_pdfa_target_fails_on_non_pdfa_source(tmp_path: Path) -> None:
    raw = tmp_path / "raw.pdf"
    output = tmp_path / "report.digital.pdf"
    make_pdf(raw, text="Kein PDF/A")
    payload = json.loads(DIGITAL_PROFILE_PATH.read_text(encoding="utf-8"))
    payload["pdf_standard_target"] = "PDF/A-2b"
    strict_profile = tmp_path / "strict-digital.json"
    strict_profile.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(DigitalExportFailure) as caught:
        export_digital(raw, strict_profile, output)

    assert caught.value.code == "digital_pdfa_target_unmet"
    assert not output.exists()


def test_digital_validation_rejects_more_than_one_percent_text_loss(tmp_path: Path) -> None:
    raw = tmp_path / "raw.pdf"
    damaged = tmp_path / "damaged.pdf"
    make_pdf(raw, text="Viele wichtige Wörter bleiben erhalten")
    make_pdf(damaged, text="")

    with pytest.raises(DigitalExportFailure) as caught:
        validate_digital_export(raw, damaged, profile())

    assert caught.value.code == "digital_text_loss"


def test_digital_validation_rejects_lost_links_and_page_size_change(tmp_path: Path) -> None:
    raw = tmp_path / "raw.pdf"
    damaged = tmp_path / "damaged.pdf"
    make_pdf(raw, text="Original", with_link=True)
    make_pdf(damaged, text="Original", with_link=False)

    with pytest.raises(DigitalExportFailure) as caught:
        validate_digital_export(raw, damaged, profile())

    assert caught.value.code == "digital_link_loss"
