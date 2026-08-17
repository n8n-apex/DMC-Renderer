"""Post-conversion print preflight against one validated profile."""

from __future__ import annotations

import difflib
import hashlib
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Literal

import numpy
from PIL import Image
from pydantic import BaseModel, ConfigDict

from postprocessor.export_digital import _font_references, _page_sizes, _text
from postprocessor.profiles.schema import PrintProfile


class PreflightCheck(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    check_id: str
    passed: bool
    detail: str


class PrintPreflightReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["3.0"] = "3.0"
    profile_id: str
    profile_hash: str
    input_hash: str
    output_hash: str
    ghostscript_version: str
    accepted: bool
    checks: tuple[PreflightCheck, ...]
    searchable_text_required: bool
    searchable_text_preserved: bool
    notes: tuple[str, ...] = ()

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(check.check_id for check in self.checks if not check.passed)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _profile_hash(profile: PrintProfile) -> str:
    return hashlib.sha256(profile.model_dump_json().encode("utf-8")).hexdigest()


def _box(path: Path, name: str) -> tuple[float, float, float, float] | None:
    output = subprocess.run(
        ("pdfinfo", "-box", str(path)),
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    match = re.search(
        rf"^{name}:\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)",
        output,
        re.MULTILINE,
    )
    return tuple(float(match.group(index)) for index in range(1, 5)) if match else None


def _bleed_matches(path: Path, bleed_mm: float) -> bool:
    bleed = _box(path, "BleedBox")
    trim = _box(path, "TrimBox")
    if bleed is None or trim is None:
        return False
    expected_points = bleed_mm * 72 / 25.4
    differences = (
        trim[0] - bleed[0],
        trim[1] - bleed[1],
        bleed[2] - trim[2],
        bleed[3] - trim[3],
    )
    return all(abs(value - expected_points) <= 0.75 for value in differences)


def _fonts_embedded(path: Path, *, text_present: bool) -> bool:
    lines = _font_references(path)
    if text_present and not lines:
        return False
    for line in lines:
        columns = re.split(r"\s{2,}", line)
        status_columns = columns[3].lower().split() if len(columns) >= 4 else []
        if not status_columns or status_columns[0] != "yes":
            return False
    return True


def _minimum_image_dpi(path: Path) -> float | None:
    output = subprocess.run(
        ("pdfimages", "-list", str(path)),
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    values: list[float] = []
    for line in output.splitlines()[2:]:
        columns = line.split()
        if len(columns) < 14 or not columns[0].isdigit():
            continue
        try:
            values.extend((float(columns[12]), float(columns[13])))
        except ValueError:
            continue
    return min(values) if values else None


def _has_output_intent(path: Path) -> bool:
    data = path.read_bytes()
    return b"/OutputIntent" in data or b"/OutputIntents" in data


def measure_max_total_area_coverage_percent(
    pdf_path: Path,
    *,
    resolution: int = 72,
) -> float:
    """Measure the maximum per-pixel CMYK total area coverage of a PDF.

    Every page is separated into CMYK ink values with Ghostscript's
    ``tiff32nc`` device at a fixed resolution; the result is the largest
    per-pixel sum of the four ink channels, as a percentage (0-400).
    """

    with tempfile.TemporaryDirectory() as scratch:
        pattern = Path(scratch) / "page-%04d.tif"
        try:
            subprocess.run(
                (
                    "gs",
                    "-dBATCH",
                    "-dNOPAUSE",
                    "-dQUIET",
                    "-dSAFER",
                    "-sDEVICE=tiff32nc",
                    f"-r{resolution}",
                    "-o",
                    str(pattern),
                    str(pdf_path),
                ),
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as error:
            raise RuntimeError(
                f"Ghostscript CMYK separation failed: {error.stderr}"
            ) from error
        pages = sorted(Path(scratch).glob("page-*.tif"))
        if not pages:
            raise RuntimeError("Ghostscript produced no CMYK separation pages")
        maximum_fraction = 0.0
        for page in pages:
            with Image.open(page) as image:
                ink = numpy.asarray(image, dtype=numpy.uint16)
                maximum_fraction = max(
                    maximum_fraction,
                    float(ink.sum(axis=2).max()) / 255.0,
                )
    return round(maximum_fraction * 100.0, 2)


def _trim_page_sizes_mm(path: Path) -> tuple[tuple[float, float], ...]:
    import fitz

    with fitz.open(str(path)) as document:
        return tuple(
            (
                round(page.trimbox.width * 25.4 / 72, 3),
                round(page.trimbox.height * 25.4 / 72, 3),
            )
            for page in document
        )


def _sizes_match(
    expected: tuple[tuple[float, float], ...],
    actual: tuple[tuple[float, float], ...],
    *,
    tolerance_mm: float = 0.05,
) -> bool:
    if len(expected) != len(actual):
        return False
    return all(
        abs(expected_dim - actual_dim) <= tolerance_mm
        for expected_size, actual_size in zip(expected, actual)
        for expected_dim, actual_dim in zip(expected_size, actual_size)
    )


def _ghostscript_version() -> str:
    try:
        return subprocess.run(
            ("gs", "--version"),
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except Exception:
        return "unavailable"


def preflight_print(
    input_pdf: Path,
    output_pdf: Path,
    profile: PrintProfile,
) -> PrintPreflightReport:
    checks: list[PreflightCheck] = []
    actual_icc_hash = _sha256(Path(profile.icc_path)) if Path(profile.icc_path).is_file() else "missing"
    checks.append(
        PreflightCheck(
            check_id="icc_hash",
            passed=actual_icc_hash == profile.icc_sha256,
            detail=f"expected {profile.icc_sha256}, got {actual_icc_hash}",
        )
    )
    input_sizes = _page_sizes(input_pdf)
    output_sizes = _page_sizes(output_pdf)
    requires_print_geometry = profile.bleed_mm > 0 or profile.crop_marks
    if requires_print_geometry:
        output_trim_sizes = _trim_page_sizes_mm(output_pdf)
        checks.append(
            PreflightCheck(
                check_id="page_sizes",
                passed=_sizes_match(input_sizes, output_trim_sizes),
                detail=(
                    f"input media={input_sizes}, output trim={output_trim_sizes} "
                    f"(media carries {profile.bleed_mm:.2f} mm bleed and marks)"
                ),
            )
        )
    else:
        checks.append(
            PreflightCheck(
                check_id="page_sizes",
                passed=input_sizes == output_sizes,
                detail=f"input={input_sizes}, output={output_sizes}",
            )
        )
    checks.append(
        PreflightCheck(
            check_id="bleed",
            passed=_bleed_matches(output_pdf, profile.bleed_mm),
            detail=f"required bleed is {profile.bleed_mm:.2f} mm",
        )
    )
    output_text = _text(output_pdf)
    font_passed = (
        _fonts_embedded(output_pdf, text_present=bool(output_text))
        if profile.font_policy == "embed_all"
        else True
    )
    checks.append(
        PreflightCheck(
            check_id="fonts",
            passed=font_passed,
            detail=f"font policy is {profile.font_policy}",
        )
    )
    minimum_dpi = _minimum_image_dpi(output_pdf)
    dpi_passed = minimum_dpi is None or minimum_dpi >= profile.minimum_image_dpi
    checks.append(
        PreflightCheck(
            check_id="image_dpi",
            passed=dpi_passed,
            detail=(
                "no raster images"
                if minimum_dpi is None
                else f"minimum observed DPI {minimum_dpi:.1f}"
            ),
        )
    )
    checks.append(
        PreflightCheck(
            check_id="output_intent",
            passed=_has_output_intent(output_pdf),
            detail=f"required by {profile.pdf_standard}",
        )
    )
    input_text = _text(input_pdf)
    text_ratio = (
        1.0
        if not input_text and not output_text
        else difflib.SequenceMatcher(None, input_text, output_text).ratio()
    )
    searchable_preserved = text_ratio >= 0.99
    checks.append(
        PreflightCheck(
            check_id="searchable_text",
            passed=searchable_preserved or not profile.preserve_searchable_text,
            detail=f"text preservation ratio {text_ratio:.4f}",
        )
    )
    measured_tac = measure_max_total_area_coverage_percent(output_pdf)
    if profile.color_space == "CMYK":
        checks.append(
            PreflightCheck(
                check_id="total_area_coverage",
                passed=measured_tac <= profile.maximum_total_area_coverage_percent,
                detail=(
                    f"measured maximum TAC {measured_tac:.2f}% against limit "
                    f"{profile.maximum_total_area_coverage_percent:.2f}%"
                ),
            )
        )
    else:
        checks.append(
            PreflightCheck(
                check_id="total_area_coverage",
                passed=True,
                detail=(
                    "informational: RGB output has no CMYK separations to gate; "
                    f"Ghostscript default conversion measures {measured_tac:.2f}%"
                ),
            )
        )
    notes = (
        ("search and accessibility may be lost by profile",)
        if not profile.preserve_searchable_text
        else ()
    )
    return PrintPreflightReport(
        profile_id=profile.profile_id,
        profile_hash=_profile_hash(profile),
        input_hash=_sha256(input_pdf),
        output_hash=_sha256(output_pdf),
        ghostscript_version=_ghostscript_version(),
        accepted=all(check.passed for check in checks),
        checks=tuple(checks),
        searchable_text_required=profile.preserve_searchable_text,
        searchable_text_preserved=searchable_preserved,
        notes=notes,
    )
