"""Atomic Ghostscript print export derived only from a validated profile."""

from __future__ import annotations

import json
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

from postprocessor.preflight import PrintPreflightReport, preflight_print
from postprocessor.profiles.schema import PrintProfile, assert_profile_for_export


MARK_LENGTH_PT = 10.0
MARK_GAP_PT = 2.0
MARK_STROKE_PT = 0.5
PRINT_PREFLIGHT_REPORT_NAME = "report.print-preflight-report.json"


class PrintExportFailure(RuntimeError):
    def __init__(self, code: str, detail: str) -> None:
        self.owner_stage = "print_export"
        self.code = code
        self.detail = detail
        self.face_ids = ()
        self.element_ids = ()
        super().__init__(f"{code}: {detail}")


def build_ghostscript_command(
    profile: PrintProfile,
    input_pdf: Path,
    output_pdf: Path,
    *,
    output_intent_definition: Path | None = None,
) -> list[str]:
    standard_flags = {
        "PDF/X-4": ("-dPDFX=4", "-dCompatibilityLevel=1.6"),
        "PDF/X-1a:2001": ("-dPDFX", "-dCompatibilityLevel=1.3"),
        "PDF/A-2b": ("-dPDFA=2", "-dCompatibilityLevel=1.7"),
    }
    definition_path = output_intent_definition or output_pdf.with_suffix(
        ".output-intent.ps"
    )
    command = [
        "gs",
        f"--permit-file-read={profile.icc_path}",
        "-dBATCH",
        "-dNOPAUSE",
        "-dSAFER",
        "-sDEVICE=pdfwrite",
        *standard_flags[profile.pdf_standard],
        f"-sColorConversionStrategy={profile.color_space}",
        f"-sOutputICCProfile={profile.icc_path}",
        "-dEmbedAllFonts=true",
        "-dSubsetFonts=true",
        "-dDetectDuplicateImages=true",
        f"-sOutputFile={output_pdf}",
        str(definition_path),
        str(input_pdf),
    ]
    return command


def _postscript_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _write_output_intent_definition(
    profile: PrintProfile,
    definition_path: Path,
) -> None:
    component_count = 3 if profile.color_space == "RGB" else 4
    intent_standard = (
        "GTS_PDFA1" if profile.pdf_standard == "PDF/A-2b" else "GTS_PDFX"
    )
    icc_path = _postscript_string(profile.icc_path)
    profile_id = _postscript_string(profile.profile_id)
    definition = f"""%!
[/_objdef {{dmc_icc}} /type /stream /OBJ pdfmark
[{{dmc_icc}} << /N {component_count} >> /PUT pdfmark
[{{dmc_icc}} ({icc_path}) /PUTFILE pdfmark
[/_objdef {{dmc_output_intent}} /type /dict /OBJ pdfmark
[{{dmc_output_intent}} << /Type /OutputIntent /S /{intent_standard} /DestOutputProfile {{dmc_icc}} /OutputConditionIdentifier ({profile_id}) /Info ({profile_id}) >> /PUT pdfmark
[{{Catalog}} << /OutputIntents [{{dmc_output_intent}}] >> /PUT pdfmark
"""
    definition_path.write_text(definition, encoding="ascii")


def _box_string(rect) -> str:
    return f"[{rect.x0:.4f} {rect.y0:.4f} {rect.x1:.4f} {rect.y1:.4f}]"


def _draw_corner_marks(page, trim, *, bleed_pts: float, color) -> None:
    import fitz

    offset = bleed_pts + MARK_GAP_PT
    length = MARK_LENGTH_PT
    corners = (
        (trim.x0, trim.y0, -1, -1),
        (trim.x1, trim.y0, 1, -1),
        (trim.x0, trim.y1, -1, 1),
        (trim.x1, trim.y1, 1, 1),
    )
    for corner_x, corner_y, direction_x, direction_y in corners:
        page.draw_line(
            fitz.Point(corner_x, corner_y + direction_y * offset),
            fitz.Point(corner_x, corner_y + direction_y * (offset + length)),
            color=color,
            width=MARK_STROKE_PT,
        )
        page.draw_line(
            fitz.Point(corner_x + direction_x * offset, corner_y),
            fitz.Point(corner_x + direction_x * (offset + length), corner_y),
            color=color,
            width=MARK_STROKE_PT,
        )


def apply_print_geometry(pdf_path: Path, profile: PrintProfile) -> bool:
    """Add TrimBox/BleedBox and corner crop marks when the profile requires them.

    The incoming page geometry is treated as the trim size: the MediaBox is
    expanded outward by the bleed (plus mark room), the TrimBox pins the
    original geometry, and the BleedBox extends the trim by the profile bleed.
    Returns True when the file was modified.
    """

    import fitz

    bleed_pts = profile.bleed_mm * 72 / 25.4
    if bleed_pts <= 0 and not profile.crop_marks:
        return False
    mark_room = (MARK_GAP_PT + MARK_LENGTH_PT) if profile.crop_marks else 0.0
    margin = bleed_pts + mark_room
    mark_color = (1, 1, 1, 1) if profile.color_space == "CMYK" else (0, 0, 0)
    with fitz.open(str(pdf_path)) as document:
        for page in document:
            trim = fitz.Rect(page.mediabox)
            media = fitz.Rect(
                trim.x0 - margin, trim.y0 - margin, trim.x1 + margin, trim.y1 + margin
            )
            bleed_box = fitz.Rect(
                trim.x0 - bleed_pts,
                trim.y0 - bleed_pts,
                trim.x1 + bleed_pts,
                trim.y1 + bleed_pts,
            )
            document.xref_set_key(page.xref, "MediaBox", _box_string(media))
            document.xref_set_key(page.xref, "CropBox", _box_string(media))
            document.xref_set_key(page.xref, "BleedBox", _box_string(bleed_box))
            document.xref_set_key(page.xref, "TrimBox", _box_string(trim))
        document.save(
            str(pdf_path), incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP
        )
    if profile.crop_marks:
        with fitz.open(str(pdf_path)) as document:
            for page in document:
                trim_in_page = fitz.Rect(
                    margin,
                    margin,
                    page.rect.width - margin,
                    page.rect.height - margin,
                )
                _draw_corner_marks(
                    page, trim_in_page, bleed_pts=bleed_pts, color=mark_color
                )
            document.save(
                str(pdf_path), incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP
            )
    return True


def export_print(
    raw_pdf: Path,
    profile: PrintProfile,
    output_path: Path,
    *,
    production: bool,
    runner: Callable = subprocess.run,
) -> PrintPreflightReport:
    assert_profile_for_export(profile, production=production)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        prefix=f".{output_path.stem}.",
        suffix=".tmp.pdf",
        dir=output_path.parent,
        delete=False,
    ) as handle:
        temporary_path = Path(handle.name)
    definition_path = temporary_path.with_suffix(".output-intent.ps")
    try:
        temporary_path.unlink()
        _write_output_intent_definition(profile, definition_path)
        command = build_ghostscript_command(
            profile,
            raw_pdf,
            temporary_path,
            output_intent_definition=definition_path,
        )
        try:
            runner(command, check=True, capture_output=True, text=True)
        except Exception as error:
            stderr = getattr(error, "stderr", None) or str(error)
            raise PrintExportFailure("ghostscript_failed", str(stderr)) from error
        if not temporary_path.is_file() or temporary_path.stat().st_size == 0:
            raise PrintExportFailure(
                "ghostscript_failed",
                "Ghostscript did not produce output bytes",
            )
        apply_print_geometry(temporary_path, profile)
        report = preflight_print(raw_pdf, temporary_path, profile)
        if not report.accepted:
            raise PrintExportFailure(
                "print_preflight_failed",
                f"failed checks: {', '.join(report.failed_check_ids)}",
            )
        temporary_path.replace(output_path)
        final_report = report.model_copy(
            update={"output_hash": report.output_hash}
        )
        report_text = (
            json.dumps(
                final_report.model_dump(mode="json"),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        (output_path.parent / "print-preflight.json").write_text(
            report_text, encoding="utf-8"
        )
        (output_path.parent / PRINT_PREFLIGHT_REPORT_NAME).write_text(
            report_text, encoding="utf-8"
        )
        return final_report
    finally:
        temporary_path.unlink(missing_ok=True)
        definition_path.unlink(missing_ok=True)
