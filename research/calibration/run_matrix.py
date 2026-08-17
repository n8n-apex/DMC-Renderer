"""Build and execute the complete family-by-evidence calibration matrix."""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel, ConfigDict


class StrictFrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class MatrixJob(StrictFrozenModel):
    family_id: str
    family_version: str
    sample_id: str
    cohort: Literal["atlas", "calibration_fixture"]


class MatrixExecutionResult(StrictFrozenModel):
    family_id: str
    family_version: str
    sample_id: str
    cohort: Literal["atlas", "calibration_fixture"]
    passed: bool
    failure_codes: tuple[str, ...] = ()


def build_matrix(composition_registry, calibration_manifest: dict) -> tuple[MatrixJob, ...]:
    compatible_fixtures = tuple(
        fixture
        for fixture in calibration_manifest["fixtures"]
        if fixture["expected_gate_state"] != "rejected"
    )
    jobs: list[MatrixJob] = []
    for family in composition_registry.families:
        jobs.extend(
            MatrixJob(
                family_id=family.family_id,
                family_version=family.version,
                sample_id=face_id,
                cohort="atlas",
            )
            for face_id in family.atlas_face_ids
        )
        jobs.extend(
            MatrixJob(
                family_id=family.family_id,
                family_version=family.version,
                sample_id=fixture["fixture_id"],
                cohort="calibration_fixture",
            )
            for fixture in compatible_fixtures
        )
    return tuple(jobs)


def run_matrix(
    jobs: tuple[MatrixJob, ...],
    *,
    runner: Callable[[MatrixJob], dict],
) -> tuple[MatrixExecutionResult, ...]:
    return tuple(
        MatrixExecutionResult(
            **job.model_dump(mode="json"),
            **runner(job),
        )
        for job in jobs
    )
