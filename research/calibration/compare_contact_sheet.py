"""Side-by-side contact sheets: Richard's reference faces vs candidate faces.

Usage:
    .venv/bin/python research/calibration/compare_contact_sheet.py \
        --reference-pdf "APEX - KI DMC Report v1 (1).pdf" \
        --candidate-dir <build>/face-rasters \
        --plan <build>/composition-plan-v3.json \
        --out research/calibration/contact-sheets/apex-vs-candidate.png

Pairs each candidate face with a reference page of the same family (via the
registry's apex atlas faces) and tiles them REFERENCE LEFT, CANDIDATE RIGHT
with a measurement caption. Purely diagnostic; never part of any gate.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import fitz
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
for entry in (ROOT / "research", ROOT / "research" / "preprocessor"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from quality_loop.gates.pixels_v3 import (  # noqa: E402
    PixelSample,
    load_pixel_policy,
    measure_face_pixels,
)

REGISTRY_PATH = ROOT / "research/composition_registry/families/dmc-v1.json"
POLICY_PATH = ROOT / "research/quality_loop/policies/pixel_policy_v1.json"
TILE_WIDTH = 420


ATLAS_PATH = ROOT / "research/reference-atlas/reference-atlas.json"
ROLE_BY_INDEX = {
    1: "cover", 2: "outlook", 3: "about", 4: "status_quo", 5: "false_beliefs",
    6: "case_study", 7: "theory", 8: "theory", 9: "theory", 10: "case_study",
    11: "theory", 12: "case_study", 13: "theory", 14: "mechanism",
    15: "trust_proof", 16: "summary", 17: "objections", 18: "collaboration",
    19: "status_quo", 20: "cta",
}


def reference_faces_by_role() -> dict[str, dict]:
    """One deterministic reference face per role, apex-first, via the atlas."""
    atlas = json.loads(ATLAS_PATH.read_text(encoding="utf-8"))
    records = sorted(
        (face for face in atlas["faces"] if face.get("role")),
        key=lambda face: (0 if face["id"].startswith("apex") else 1, face["id"]),
    )
    by_role: dict[str, dict] = {}
    for record in records:
        by_role.setdefault(record["role"], record)
    return by_role


def tile(image: Image.Image) -> Image.Image:
    ratio = TILE_WIDTH / image.width
    return image.resize((TILE_WIDTH, round(image.height * ratio)))


def caption(draw: ImageDraw.ImageDraw, x: int, y: int, text: str) -> None:
    draw.rectangle((x, y, x + TILE_WIDTH, y + 16), fill=(23, 23, 20))
    draw.text((x + 4, y + 3), text, fill=(245, 241, 232))


def build_sheet(
    reference_pdf: Path,
    candidate_dir: Path,
    plan_path: Path,
    out_path: Path,
    accent_rgb: tuple[int, int, int],
) -> Path:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    family_by_face = {
        decision["face_id"]: decision["selected"]["family_id"]
        for decision in plan["decisions"]
    }
    reference_map = reference_faces_by_role()
    policy = load_pixel_policy(POLICY_PATH)
    documents: dict[str, fitz.Document] = {}

    rows = []
    for face_png in sorted(candidate_dir.glob("face.*.png")):
        family_id = family_by_face.get(face_png.stem)
        face_index = int(face_png.stem.split(".")[1])
        role = ROLE_BY_INDEX.get(face_index)
        record = reference_map.get(role) if role else None
        if family_id is None or record is None:
            continue
        source_pdf = record["source_pdf"]
        if source_pdf not in documents:
            documents[source_pdf] = fitz.open(ROOT / source_pdf)
        reference_page = record["source_object"]
        pixmap = documents[source_pdf][reference_page - 1].get_pixmap(
            matrix=fitz.Matrix(0.7, 0.7), alpha=False
        )
        reference_image = Image.frombytes(
            "RGB", (pixmap.width, pixmap.height), pixmap.samples
        )
        side = record.get("spread_side")
        if side:
            half = reference_image.width // 2
            reference_image = (
                reference_image.crop((0, 0, half, reference_image.height))
                if side == "left"
                else reference_image.crop((half, 0, reference_image.width, reference_image.height))
            )
        candidate_image = Image.open(face_png).convert("RGB")
        features = measure_face_pixels(
            PixelSample(
                face_id=face_png.stem,
                family_id=family_id,
                image_path=str(face_png),
                accent_rgb=accent_rgb,
            ),
            policy.families[family_id],
            policy.measurement,
        )
        rows.append(
            (
                family_id,
                record["id"],
                tile(reference_image),
                tile(candidate_image),
                features,
            )
        )

    if not rows:
        raise SystemExit("no candidate faces matched a reference family")

    row_height = max(max(r[2].height, r[3].height) for r in rows) + 20
    sheet = Image.new(
        "RGB", (TILE_WIDTH * 2 + 30, row_height * len(rows) + 10), (245, 241, 232)
    )
    draw = ImageDraw.Draw(sheet)
    for index, (family_id, page, ref_img, cand_img, features) in enumerate(rows):
        y = 10 + index * row_height
        sheet.paste(ref_img, (10, y + 18))
        sheet.paste(cand_img, (TILE_WIDTH + 20, y + 18))
        caption(draw, 10, y, f"{page} | {family_id}")
        caption(
            draw,
            TILE_WIDTH + 20,
            y,
            (
                f"{features.face_id} ink={features.ink_occupancy:.2f} "
                f"ws={features.whitespace_fraction:.2f} "
                f"bands={features.type_rhythm_bands}"
            ),
        )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference-pdf", required=True, type=Path)
    parser.add_argument("--candidate-dir", required=True, type=Path)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--accent", default="64,128,160")
    arguments = parser.parse_args()
    accent = tuple(int(part) for part in arguments.accent.split(","))
    out = build_sheet(
        arguments.reference_pdf,
        arguments.candidate_dir,
        arguments.plan,
        arguments.out,
        accent,
    )
    print(out)


if __name__ == "__main__":
    main()
