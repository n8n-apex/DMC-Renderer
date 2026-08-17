from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT / "research") not in sys.path:
    sys.path.insert(0, str(ROOT / "research"))

from postprocessor.export_print import (  # noqa: E402
    MARK_GAP_PT,
    MARK_LENGTH_PT,
    PrintExportFailure,
    build_ghostscript_command,
    export_print,
)
from postprocessor.preflight import preflight_print  # noqa: E402
from postprocessor.profiles.schema import load_print_profile  # noqa: E402


PROFILE_PATH = ROOT / "research" / "postprocessor" / "profiles" / "dmc_print_test.json"
FONT = ROOT / "research" / "v7-renderer" / "fonts" / "SourceSans3[wght].ttf"


def make_pdf(path: Path, *, page_size: str = "A4") -> None:
    html = f"""<!doctype html><style>
    @font-face {{ font-family: DMC; src: url('{FONT.resolve().as_uri()}'); }}
    @page {{ size: {page_size}; margin: 20mm; }}
    body {{ font-family: DMC, sans-serif; }}
    </style><h1>Searchable print proof</h1><p>Embedded font and stable geometry.</p>"""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(html, wait_until="networkidle")
        page.pdf(path=str(path), prefer_css_page_size=True, tagged=True)
        browser.close()


def test_ghostscript_command_is_derived_from_validated_profile(tmp_path: Path) -> None:
    profile = load_print_profile(PROFILE_PATH)
    command = build_ghostscript_command(
        profile,
        tmp_path / "raw.pdf",
        tmp_path / "output.pdf",
    )

    assert f"-sOutputICCProfile={Path(profile.icc_path)}" in command
    assert "-dPDFA=2" in command
    assert "-sColorConversionStrategy=RGB" in command
    assert not any("/printer" in item for item in command)
    assert "-dCompatibilityLevel=1.3" not in command


def test_print_export_is_atomic_and_passes_preflight(tmp_path: Path) -> None:
    raw = tmp_path / "raw.pdf"
    output = tmp_path / "report.print.pdf"
    make_pdf(raw)

    report = export_print(
        raw,
        load_print_profile(PROFILE_PATH),
        output,
        production=False,
    )

    assert output.is_file()
    assert report.accepted is True
    assert all(check.passed for check in report.checks)
    assert report.searchable_text_preserved is True
    assert output.with_name("print-preflight.json").is_file()


def test_preflight_rejects_icc_mismatch_page_size_and_bleed(tmp_path: Path) -> None:
    raw = tmp_path / "raw-a4.pdf"
    wrong_size = tmp_path / "wrong-letter.pdf"
    make_pdf(raw, page_size="A4")
    make_pdf(wrong_size, page_size="Letter")
    profile = load_print_profile(PROFILE_PATH)

    mismatched = preflight_print(
        raw,
        raw,
        profile.model_copy(update={"icc_sha256": "0" * 64}),
    )
    wrong_geometry = preflight_print(raw, wrong_size, profile)
    wrong_bleed = preflight_print(
        raw,
        raw,
        profile.model_copy(update={"bleed_mm": 3}),
    )

    assert "icc_hash" in mismatched.failed_check_ids
    assert "page_sizes" in wrong_geometry.failed_check_ids
    assert "bleed" in wrong_bleed.failed_check_ids


def test_ghostscript_failure_leaves_no_print_filename(tmp_path: Path) -> None:
    raw = tmp_path / "raw.pdf"
    output = tmp_path / "report.print.pdf"
    make_pdf(raw)

    def fail_runner(*args, **kwargs):
        raise subprocess.CalledProcessError(1, args[0], stderr="synthetic failure")

    with pytest.raises(PrintExportFailure) as caught:
        export_print(
            raw,
            load_print_profile(PROFILE_PATH),
            output,
            production=False,
            runner=fail_runner,
        )

    assert caught.value.code == "ghostscript_failed"
    assert not output.exists()


def test_print_export_applies_trim_bleed_boxes_and_crop_marks(tmp_path: Path) -> None:
    import fitz

    raw = tmp_path / "raw.pdf"
    output = tmp_path / "report.print.pdf"
    make_pdf(raw)
    profile = load_print_profile(PROFILE_PATH).model_copy(
        update={"bleed_mm": 3.0, "crop_marks": True}
    )

    report = export_print(raw, profile, output, production=False)

    assert report.accepted is True
    assert "bleed" not in report.failed_check_ids
    assert "page_sizes" not in report.failed_check_ids
    bleed_pts = 3.0 * 72 / 25.4
    margin_pts = bleed_pts + MARK_GAP_PT + MARK_LENGTH_PT
    with fitz.open(raw) as source:
        input_width = source[0].mediabox.width
        input_height = source[0].mediabox.height
    with fitz.open(output) as document:
        page = document[0]
        assert page.trimbox != page.mediabox
        assert page.mediabox.width == pytest.approx(input_width + 2 * margin_pts, abs=0.1)
        assert page.mediabox.height == pytest.approx(input_height + 2 * margin_pts, abs=0.1)
        assert page.trimbox.width == pytest.approx(input_width, abs=0.1)
        assert page.trimbox.height == pytest.approx(input_height, abs=0.1)
        assert page.bleedbox.width == pytest.approx(input_width + 2 * bleed_pts, abs=0.1)
        assert page.bleedbox.height == pytest.approx(input_height + 2 * bleed_pts, abs=0.1)
        corner = page.get_pixmap(clip=fitz.Rect(0, 0, 24, 24))
        assert any(byte < 250 for byte in corner.samples)


def test_print_export_without_marks_keeps_boxes_untouched(tmp_path: Path) -> None:
    import fitz

    raw = tmp_path / "raw.pdf"
    output = tmp_path / "report.print.pdf"
    make_pdf(raw)
    profile = load_print_profile(PROFILE_PATH)
    assert profile.bleed_mm == 0
    assert profile.crop_marks is False

    export_print(raw, profile, output, production=False)

    with fitz.open(output) as document:
        page = document[0]
        assert document.xref_get_key(page.xref, "TrimBox")[0] == "null"
        assert document.xref_get_key(page.xref, "BleedBox")[0] == "null"
        assert page.trimbox == page.mediabox
        assert page.bleedbox == page.mediabox


def test_print_export_writes_immutable_preflight_report(tmp_path: Path) -> None:
    import json as json_module

    raw = tmp_path / "raw.pdf"
    output = tmp_path / "report.print.pdf"
    make_pdf(raw)

    report = export_print(raw, load_print_profile(PROFILE_PATH), output, production=False)

    report_path = output.parent / "report.print-preflight-report.json"
    assert report_path.is_file()
    payload = json_module.loads(report_path.read_text(encoding="utf-8"))
    assert payload["profile_id"] == report.profile_id
    assert payload["profile_hash"] == report.profile_hash
    assert payload["input_hash"] == report.input_hash
    assert payload["output_hash"] == report.output_hash
    assert payload["accepted"] is True


def test_flattening_loss_is_explicit_in_preflight_report(tmp_path: Path) -> None:
    raw = tmp_path / "raw.pdf"
    make_pdf(raw)
    profile = load_print_profile(PROFILE_PATH).model_copy(
        update={
            "transparency_policy": "flatten",
            "flattening_policy": "ghostscript",
            "preserve_searchable_text": False,
        }
    )

    report = preflight_print(raw, raw, profile)

    assert report.searchable_text_required is False
    assert "search and accessibility may be lost by profile" in report.notes
