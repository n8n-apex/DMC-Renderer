"""Non-destructive searchable digital PDF preservation export."""

from __future__ import annotations

import difflib
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

from postprocessor.models import DigitalExportProfile, ExportReport
from postprocessor.profiles.schema import (
    DigitalProfile,
    MetadataNormalizationFlags,
    digital_profile_sha256,
    load_digital_profile,
)


PROFILES_DIR = Path(__file__).resolve().parent / "profiles"
DIGITAL_EXPORT_REPORT_NAME = "report.digital-export-report.json"

DigitalProfileLike = DigitalExportProfile | DigitalProfile


class DigitalExportFailure(RuntimeError):
    def __init__(self, code: str, detail: str) -> None:
        self.owner_stage = "digital_export"
        self.code = code
        self.detail = detail
        self.face_ids = ()
        self.element_ids = ()
        super().__init__(f"{code}: {detail}")


def resolve_digital_profile(
    profile: DigitalProfileLike | str | Path,
) -> DigitalProfileLike:
    """Accept a typed profile, a stored profile path, or a stored profile id."""

    if isinstance(profile, (DigitalExportProfile, DigitalProfile)):
        return profile
    if isinstance(profile, Path):
        return load_digital_profile(profile)
    if isinstance(profile, str):
        candidate = Path(profile)
        if candidate.suffix == ".json":
            return load_digital_profile(candidate)
        return load_digital_profile(PROFILES_DIR / f"{profile}.json")
    raise DigitalExportFailure(
        "digital_profile_invalid",
        f"unsupported profile reference of type {type(profile).__name__}",
    )


def _run(*args: str) -> str:
    result = subprocess.run(
        args,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _text(path: Path) -> str:
    extracted = _run("pdftotext", "-enc", "UTF-8", str(path), "-")
    return " ".join(extracted.split())


def _links(path: Path) -> tuple[str, ...]:
    output = _run("pdfinfo", "-url", str(path))
    urls = re.findall(r"https?://[^\s]+", output)
    return tuple(sorted(dict.fromkeys(urls)))


def _page_sizes(path: Path) -> tuple[tuple[float, float], ...]:
    summary = _run("pdfinfo", str(path))
    pages_match = re.search(r"^Pages:\s+(\d+)", summary, re.MULTILINE)
    if pages_match is None:
        raise DigitalExportFailure("digital_page_size_changed", "PDF page count is unavailable")
    sizes = []
    for page_number in range(1, int(pages_match.group(1)) + 1):
        output = _run(
            "pdfinfo",
            "-f",
            str(page_number),
            "-l",
            str(page_number),
            str(path),
        )
        match = re.search(
            r"Page(?:\s+\d+)?\s+size:\s+([\d.]+) x ([\d.]+) pts",
            output,
        )
        if match is None:
            raise DigitalExportFailure(
                "digital_page_size_changed",
                f"page {page_number} has no readable MediaBox",
            )
        width_mm = float(match.group(1)) * 25.4 / 72
        height_mm = float(match.group(2)) * 25.4 / 72
        sizes.append((round(width_mm, 3), round(height_mm, 3)))
    return tuple(sizes)


def _font_references(path: Path) -> tuple[str, ...]:
    output = _run("pdffonts", str(path))
    lines = [line.strip() for line in output.splitlines()[2:] if line.strip()]
    return tuple(sorted(lines))


def _metadata(path: Path) -> dict[str, str]:
    output = _run("pdfinfo", "-isodates", str(path))
    metadata: dict[str, str] = {}
    for line in output.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        if key in {"Pages", "Page size", "File size", "Optimized", "PDF version"}:
            continue
        metadata[key.strip()] = value.strip()
    return metadata


def _pdfa_markers_present(path: Path) -> bool:
    data = path.read_bytes()
    has_output_intent = b"/OutputIntent" in data or b"/OutputIntents" in data
    has_pdfa_id = b"pdfaid:part" in data or b"pdfaid" in data
    return has_output_intent and has_pdfa_id


def _apply_metadata_normalization(
    path: Path,
    flags: MetadataNormalizationFlags,
) -> None:
    if not flags.any_active:
        return
    import fitz

    with fitz.open(str(path)) as document:
        metadata = dict(document.metadata or {})
        if flags.strip_creation_date:
            metadata["creationDate"] = ""
        if flags.strip_modification_date:
            metadata["modDate"] = ""
        if flags.normalize_producer:
            metadata["producer"] = "DMC v3 digital export"
        document.set_metadata(metadata)
        document.save(str(path), incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP)


def validate_digital_export(
    raw_pdf: Path,
    output_pdf: Path,
    profile: DigitalProfileLike,
) -> ExportReport:
    if getattr(profile, "pdf_standard_target", "preserve_source") == "PDF/A-2b":
        if not _pdfa_markers_present(output_pdf):
            raise DigitalExportFailure(
                "digital_pdfa_target_unmet",
                "profile targets PDF/A-2b but the output carries no PDF/A "
                "output intent and identification markers",
            )
    raw_text = _text(raw_pdf)
    output_text = _text(output_pdf)
    text_ratio = (
        1.0
        if not raw_text and not output_text
        else difflib.SequenceMatcher(None, raw_text, output_text).ratio()
    )
    input_links = _links(raw_pdf)
    output_links = _links(output_pdf)
    input_sizes = _page_sizes(raw_pdf)
    output_sizes = _page_sizes(output_pdf)
    input_fonts = _font_references(raw_pdf)
    output_fonts = _font_references(output_pdf)
    metadata_preserved = _metadata(raw_pdf) == _metadata(output_pdf)

    if text_ratio < profile.minimum_text_preservation_ratio:
        raise DigitalExportFailure(
            "digital_text_loss",
            f"text preservation {text_ratio:.4f} is below {profile.minimum_text_preservation_ratio:.4f}",
        )
    if profile.preserve_links and input_links != output_links:
        raise DigitalExportFailure("digital_link_loss", "PDF annotations or URLs changed")
    if profile.preserve_page_sizes and input_sizes != output_sizes:
        raise DigitalExportFailure("digital_page_size_changed", "page geometry changed")
    if profile.preserve_font_references and input_fonts != output_fonts:
        raise DigitalExportFailure("digital_text_loss", "embedded font references changed")
    if profile.preserve_metadata and not metadata_preserved:
        raise DigitalExportFailure("digital_text_loss", "document metadata changed")

    return ExportReport(
        export_kind="digital",
        profile_id=profile.profile_id,
        accepted=True,
        input_sha256=_sha256(raw_pdf),
        output_sha256=_sha256(output_pdf),
        input_path=str(raw_pdf),
        output_path=str(output_pdf),
        text_preservation_ratio=text_ratio,
        input_links=input_links,
        output_links=output_links,
        input_page_sizes_mm=input_sizes,
        output_page_sizes_mm=output_sizes,
        input_font_references=input_fonts,
        output_font_references=output_fonts,
        metadata_preserved=metadata_preserved,
    )


def _write_digital_export_report(
    report: ExportReport,
    profile: DigitalProfileLike,
    output_path: Path,
) -> Path:
    payload = {
        "schema_version": "1.0",
        "report_kind": "digital_export_report",
        "profile_id": report.profile_id,
        "profile_sha256": digital_profile_sha256(profile),
        "profile_version": getattr(profile, "version", None),
        "pdf_standard_target": getattr(profile, "pdf_standard_target", "preserve_source"),
        "accepted": report.accepted,
        "input_sha256": report.input_sha256,
        "output_sha256": report.output_sha256,
        "input_path": report.input_path,
        "output_path": report.output_path,
        "text_preservation_ratio": report.text_preservation_ratio,
        "minimum_text_preservation_ratio": profile.minimum_text_preservation_ratio,
        "input_link_count": len(report.input_links),
        "output_link_count": len(report.output_links),
        "links_preserved": report.input_links == report.output_links,
        "input_links": list(report.input_links),
        "output_links": list(report.output_links),
        "metadata_preserved": report.metadata_preserved,
        "input_page_sizes_mm": [list(size) for size in report.input_page_sizes_mm],
        "output_page_sizes_mm": [list(size) for size in report.output_page_sizes_mm],
    }
    report_path = output_path.parent / DIGITAL_EXPORT_REPORT_NAME
    report_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report_path


def export_digital(
    raw_pdf: Path,
    profile: DigitalProfileLike | str | Path,
    output_path: Path,
) -> ExportReport:
    resolved_profile = resolve_digital_profile(profile)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(".digital.tmp.pdf")
    shutil.copyfile(raw_pdf, temporary_path)
    try:
        normalization = getattr(resolved_profile, "metadata_normalization", None)
        if normalization is not None:
            _apply_metadata_normalization(temporary_path, normalization)
        report = validate_digital_export(raw_pdf, temporary_path, resolved_profile)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
    temporary_path.replace(output_path)
    final_report = report.model_copy(
        update={
            "output_path": str(output_path),
            "output_sha256": _sha256(output_path),
        }
    )
    sidecar = output_path.with_suffix(".export-report.json")
    sidecar.write_text(
        json.dumps(
            final_report.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    _write_digital_export_report(final_report, resolved_profile, output_path)
    return final_report
