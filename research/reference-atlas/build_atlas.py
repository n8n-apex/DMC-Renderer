#!/usr/bin/env python3
"""Build the measured Richard reference atlas from the six source PDFs.

Run with the v7 renderer virtual environment because it contains PyMuPDF:

    research/v7-renderer/.venv/bin/python research/reference-atlas/build_atlas.py

The script treats each half of a landscape spread as one physical A4 face.
It writes normalized thumbnails, a measured JSON index, and contact sheets.
Editorial classification lives in atlas_annotations.tsv and is joined by face ID.
"""

from __future__ import annotations

import csv
import json
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import fitz
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
FACES_DIR = HERE / "faces"
CONTACTS_DIR = HERE / "contact-sheets"
ANNOTATIONS_PATH = HERE / "atlas_annotations.tsv"
OUTPUT_PATH = HERE / "reference-atlas.json"
PAGE_MAP_PATH = HERE / "PAGE-BY-PAGE.md"


@dataclass(frozen=True)
class Report:
    slug: str
    title: str
    pdf: str
    family: str
    expected_objects: int
    expected_faces: int = 20
    ocr: bool = False


REPORTS = [
    Report(
        "apex",
        "APEX KI DMC Report v1",
        "APEX - KI DMC Report v1 (1).pdf",
        "Apex modernist hybrid",
        20,
        ocr=True,
    ),
    Report(
        "buchagentur",
        "Buchagentur DMC Report",
        "Buchagentur DMC-Report (1).pdf",
        "Richard editorial",
        11,
    ),
    Report(
        "alexander",
        "Alexander Boss DMC Report",
        "DMC-Report Alexander Boss doppelt (1).pdf",
        "Richard editorial",
        11,
    ),
    Report(
        "werkzeug",
        "Mein Werkzeugkoffer DMC Report",
        "DMC-Report Mein_Werkzeugkoffer.pdf",
        "Richard editorial",
        11,
    ),
    Report(
        "niklas",
        "Niklas Niemeyer DMC Report",
        "Niklas Niemeyer DMC-Report Druckfertig (1).pdf",
        "Richard editorial",
        20,
    ),
    Report(
        "aerzte",
        "Aerztepartner DMC Report",
        "aerztepartner_v0.2 (1).pdf",
        "Richard editorial",
        11,
    ),
]


def words(text: str) -> list[str]:
    return re.findall(r"\b[\wÄÖÜäöüß€%.,'-]+\b", text, flags=re.UNICODE)


def density_band(word_count: int) -> str:
    if word_count < 120:
        return "light"
    if word_count < 260:
        return "moderate"
    if word_count < 400:
        return "dense"
    return "very_dense"


def face_clips(page: fitz.Page) -> list[tuple[str | None, fitz.Rect]]:
    rect = page.rect
    if rect.width > rect.height * 1.15:
        mid = rect.x0 + rect.width / 2
        return [
            ("L", fitz.Rect(rect.x0, rect.y0, mid, rect.y1)),
            ("R", fitz.Rect(mid, rect.y0, rect.x1, rect.y1)),
        ]
    return [(None, rect)]


def render_face(page: fitz.Page, clip: fitz.Rect, output: Path) -> Image.Image:
    target_width = 620
    zoom = target_width / clip.width
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=clip, alpha=False)
    image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, "JPEG", quality=84, optimize=True, progressive=True)
    return image


def ocr_face(page: fitz.Page, clip: fitz.Rect) -> str:
    """OCR a direct high-resolution render, not an enlarged thumbnail."""
    large_width = 1500
    zoom = large_width / clip.width
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=clip, alpha=False)
    large = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    with tempfile.NamedTemporaryFile(suffix=".png") as tmp:
        large.save(tmp.name, "PNG")
        result = subprocess.run(
            ["tesseract", tmp.name, "stdout", "-l", "eng"],
            check=True,
            capture_output=True,
            text=True,
        )
    return result.stdout


def read_annotations() -> dict[str, dict[str, str]]:
    if not ANNOTATIONS_PATH.exists():
        return {}
    with ANNOTATIONS_PATH.open(encoding="utf-8", newline="") as handle:
        rows = csv.DictReader(handle, delimiter="\t")
        return {row["id"]: row for row in rows}


def embedded_fonts(pdf_path: Path) -> list[str]:
    result = subprocess.run(
        ["pdffonts", str(pdf_path)], check=True, capture_output=True, text=True
    )
    fonts = set()
    for line in result.stdout.splitlines()[2:]:
        fields = line.split()
        if not fields:
            continue
        name = re.sub(r"^[A-Z]{6}\+", "", fields[0])
        fonts.add(name)
    return sorted(fonts)


def contact_sheet(report: Report, faces: list[dict]) -> None:
    cards = []
    for face in faces:
        image = Image.open(HERE / face["thumbnail"]).convert("RGB")
        thumb = image.copy()
        thumb.thumbnail((260, 370), Image.Resampling.LANCZOS)
        card = Image.new("RGB", (280, 420), "#e7e0d4")
        card.paste(thumb, ((280 - thumb.width) // 2, 10))
        draw = ImageDraw.Draw(card)
        label = f'{face["id"]}  {face.get("role", "unclassified")}'
        draw.text((10, 390), label, fill="#17243f")
        cards.append(card)

    columns = 5
    rows = (len(cards) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * 280, rows * 420), "#f7f2e9")
    for index, card in enumerate(cards):
        sheet.paste(card, ((index % columns) * 280, (index // columns) * 420))
    CONTACTS_DIR.mkdir(parents=True, exist_ok=True)
    sheet.save(CONTACTS_DIR / f"{report.slug}.jpg", "JPEG", quality=88, optimize=True)


def write_page_map(atlas: dict) -> None:
    lines = [
        "# Richard reference corpus: 120-face page map",
        "",
        "This is generated from `reference-atlas.json`. One row equals one physical A4 face. ",
        "Landscape PDF spreads are split into left and right faces before counting or classification.",
        "",
        "Word counts are capacity proxies, not copy-quality scores. Embedded text is preferred. ",
        "Direct high-resolution OCR is used when the source has no usable text layer.",
        "",
    ]
    for report in atlas["reports"]:
        lines.extend(
            [
                f'## {report["title"]}',
                "",
                f'- Source: `{report["source_pdf"]}`',
                f'- PDF objects: {report["pdf_objects"]}',
                f'- Physical faces: {report["physical_faces"]}',
                f'- Measured words: {report["total_words"]} total, {report["mean_words_per_face"]} mean per face',
                f'- Embedded fonts: {", ".join(report["embedded_fonts"]) if report["embedded_fonts"] else "not extractable"}',
                "",
                "| Face | PDF object | Side | Role | Title | Words | Density | Visual mechanism | Confidence |",
                "|---|---:|:---:|---|---|---:|---|---|:---:|",
            ]
        )
        for face in [f for f in atlas["faces"] if f["report"] == report["slug"]]:
            side = face["spread_side"] or "-"
            title = face.get("title", "Unclassified").replace("|", "/")
            mechanism = face.get("visual_mechanism", "Unclassified").replace("|", "/")
            lines.append(
                f'| [{face["id"]}]({face["thumbnail"]}) | {face["source_object"]} | {side} | '
                f'{face.get("role", "unclassified")} | {title} | {face["word_count"]} | '
                f'{face["density_band"]} | {mechanism} | {face.get("confidence", "unknown")} |'
            )
        lines.append("")
    PAGE_MAP_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    FACES_DIR.mkdir(parents=True, exist_ok=True)
    annotations = read_annotations()
    atlas = {
        "schema_version": "1.0",
        "unit": "physical_A4_face",
        "density_thresholds_words": {
            "light": "0-119",
            "moderate": "120-259",
            "dense": "260-399",
            "very_dense": "400+",
        },
        "reports": [],
        "faces": [],
    }

    for report in REPORTS:
        pdf_path = ROOT / report.pdf
        if not pdf_path.exists():
            raise FileNotFoundError(pdf_path)
        document = fitz.open(pdf_path)
        if len(document) != report.expected_objects:
            raise RuntimeError(
                f"{report.slug}: expected {report.expected_objects} PDF objects, found {len(document)}"
            )

        report_faces = []
        physical_index = 0
        for object_index, page in enumerate(document, start=1):
            clips = face_clips(page)
            for side, clip in clips:
                physical_index += 1
                face_id = f"{report.slug}-{physical_index:02d}"
                filename = f"{face_id}.jpg"
                image = render_face(page, clip, FACES_DIR / filename)
                embedded_text = page.get_text("text", clip=clip, sort=True)
                embedded_count = len(words(embedded_text))
                ocr_text = ""
                ocr_count = 0
                if report.ocr or embedded_count < 120:
                    ocr_text = ocr_face(page, clip)
                    ocr_count = len(words(ocr_text))
                if report.ocr or ocr_count > embedded_count:
                    text = ocr_text
                    word_count = ocr_count
                    text_source = "tesseract_ocr"
                else:
                    text = embedded_text
                    word_count = embedded_count
                    text_source = "embedded_text_layer"
                face = {
                    "id": face_id,
                    "report": report.slug,
                    "physical_face": physical_index,
                    "source_pdf": report.pdf,
                    "source_object": object_index,
                    "spread_side": side,
                    "thumbnail": f"faces/{filename}",
                    "width_pt": round(clip.width, 3),
                    "height_pt": round(clip.height, 3),
                    "word_count": word_count,
                    "word_count_source": text_source,
                    "embedded_word_count": embedded_count,
                    "ocr_word_count": ocr_count if ocr_text else None,
                    "density_band": density_band(word_count),
                }
                annotation = annotations.get(face_id)
                if annotation:
                    for key, value in annotation.items():
                        if key != "id" and value:
                            face[key] = value
                report_faces.append(face)
                atlas["faces"].append(face)

        if physical_index != report.expected_faces:
            raise RuntimeError(
                f"{report.slug}: expected {report.expected_faces} faces, found {physical_index}"
            )
        atlas["reports"].append(
            {
                "slug": report.slug,
                "title": report.title,
                "source_pdf": report.pdf,
                "family": report.family,
                "creator": document.metadata.get("creator") or None,
                "producer": document.metadata.get("producer") or None,
                "file_size_bytes": pdf_path.stat().st_size,
                "pdf_objects": len(document),
                "physical_faces": physical_index,
                "embedded_fonts": embedded_fonts(pdf_path),
                "total_words": sum(face["word_count"] for face in report_faces),
                "mean_words_per_face": round(
                    sum(face["word_count"] for face in report_faces) / physical_index, 1
                ),
            }
        )
        contact_sheet(report, report_faces)

    missing = sorted(set(annotations) - {face["id"] for face in atlas["faces"]})
    if missing:
        raise RuntimeError(f"Annotations reference unknown face IDs: {missing}")
    if len(atlas["faces"]) != 120:
        raise RuntimeError(f'Expected 120 faces, found {len(atlas["faces"])}')
    OUTPUT_PATH.write_text(json.dumps(atlas, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_page_map(atlas)
    print(f"Wrote {OUTPUT_PATH}")
    print(f"Wrote {PAGE_MAP_PATH}")
    print(f"Rendered {len(atlas['faces'])} physical faces")


if __name__ == "__main__":
    main()
