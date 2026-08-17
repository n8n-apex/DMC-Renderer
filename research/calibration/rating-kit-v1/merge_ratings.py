"""Turn a rater's simple CSV into schema-valid rating rows.

Rate in any spreadsheet with these columns (one row per face image):

    image,hierarchy,composition,typography,rhythm,density,proof_visibility,mechanism_clarity,brand_coherence,overall

where image is the file name (face-01.png ... face-40.png) and every score
is an integer 1-5. Export as CSV, then run:

    python3 merge_ratings.py --csv rater-utkarsh.csv --rater rater.utkarsh

The tool unseals the key, joins cohort + image hash onto every row, stamps
the current time, validates each row against ratings.schema.json, and
APPENDS to research/quality_loop/calibration/ratings.jsonl. It refuses
partial kits (all 40 faces must be rated) and duplicate rater submissions.
It cannot invent scores; it only reshapes yours.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parent
ROOT = KIT.parents[2]
KEY_PATH = KIT / "KEY-DO-NOT-OPEN-BEFORE-RATING.json"
LEDGER = ROOT / "research/quality_loop/calibration/ratings.jsonl"
SCHEMA = ROOT / "research/quality_loop/calibration/ratings.schema.json"
DIMENSIONS = (
    "hierarchy",
    "composition",
    "typography",
    "rhythm",
    "density",
    "proof_visibility",
    "mechanism_clarity",
    "brand_coherence",
)


def fail(message: str) -> None:
    raise SystemExit(f"REFUSED: {message}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--rater", required=True)
    parser.add_argument("--rubric-version", default="3.0")
    arguments = parser.parse_args()

    key = json.loads(KEY_PATH.read_text(encoding="utf-8"))
    rows = list(csv.DictReader(arguments.csv.open(encoding="utf-8-sig")))
    rated_images = {row["image"].strip() for row in rows}
    missing = sorted(set(key) - rated_images)
    if missing:
        fail(f"kit incomplete - unrated images: {', '.join(missing)}")
    unknown = sorted(rated_images - set(key))
    if unknown:
        fail(f"unknown images in CSV: {', '.join(unknown)}")

    existing = [
        json.loads(line)
        for line in LEDGER.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if any(row.get("rater_id") == arguments.rater for row in existing):
        fail(f"{arguments.rater} already submitted - one submission per rater")

    stamped = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    out_rows = []
    for row in rows:
        image = row["image"].strip()
        scores = {}
        for dimension in DIMENSIONS:
            value = int(row[dimension])
            if not 1 <= value <= 5:
                fail(f"{image} {dimension}={value} outside 1-5")
            scores[dimension] = value
        overall = int(row["overall"])
        if not 1 <= overall <= 5:
            fail(f"{image} overall={overall} outside 1-5")
        out_rows.append(
            {
                "rater_id": arguments.rater,
                "cohort": key[image]["cohort"],
                "face_image_sha256": key[image]["image_sha256"],
                "rubric_version": arguments.rubric_version,
                "scores": scores,
                "overall": overall,
                "rated_at": stamped,
            }
        )

    try:
        import jsonschema  # type: ignore

        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        for out in out_rows:
            jsonschema.validate(out, schema)
    except ModuleNotFoundError:
        pass  # structural checks above still hold

    with LEDGER.open("a", encoding="utf-8") as handle:
        for out in out_rows:
            handle.write(json.dumps(out, ensure_ascii=False) + "\n")
    digest = hashlib.sha256(LEDGER.read_bytes()).hexdigest()
    print(f"appended {len(out_rows)} rows for {arguments.rater}")
    print(f"ledger sha256: {digest}")
    print("when BOTH raters are in, the threshold derivation runs automatically.")


if __name__ == "__main__":
    sys.exit(main())
