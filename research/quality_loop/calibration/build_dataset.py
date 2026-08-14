"""Build the v3 visual calibration dataset from reference and candidate cohorts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict


class CalibrationSample(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    sample_id: str
    cohort: Literal["reference", "current_failure", "v3_candidate"]
    image_path: str
    family_id: str
    atlas_face_id: str | None = None
    source_report: str | None = None


class CalibrationDataset(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["3.0"] = "3.0"
    samples: tuple[CalibrationSample, ...]


def build_calibration_dataset(
    atlas_path: Path,
    output_path: Path,
    *,
    current_failures: tuple[dict, ...] = (),
    candidates: tuple[dict, ...] = (),
) -> CalibrationDataset:
    atlas = json.loads(atlas_path.read_text(encoding="utf-8"))
    atlas_root = atlas_path.parent
    samples = [
        CalibrationSample(
            sample_id=f"reference.{face['id']}",
            cohort="reference",
            image_path=str((atlas_root / face["thumbnail"]).resolve()),
            family_id=str(face.get("pattern_family") or face.get("role") or "unclassified"),
            atlas_face_id=face["id"],
            source_report=face["report"],
        )
        for face in atlas["faces"]
    ]
    samples.extend(
        CalibrationSample(cohort="current_failure", **item)
        for item in current_failures
    )
    samples.extend(
        CalibrationSample(cohort="v3_candidate", **item)
        for item in candidates
    )
    dataset = CalibrationDataset(samples=tuple(samples))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            dataset.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return dataset
