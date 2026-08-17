from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
RESEARCH = ROOT / "research"
for path in (
    RESEARCH,
    RESEARCH / "design_policy",
    RESEARCH / "calibration",
):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from calibration.run_matrix import build_matrix, run_matrix  # noqa: E402
from composition_registry.promotion import PromotionRecord, promote  # noqa: E402
from composition_registry.registry import (  # noqa: E402
    RegistryIntegrityError,
    load_registry,
)
from registry import (  # noqa: E402
    DesignPolicyIntegrityError,
    load_design_policy_registry,
)


ATLAS = RESEARCH / "reference-atlas" / "reference-atlas.json"
COMPOSITIONS = RESEARCH / "composition_registry" / "families" / "dmc-v1.json"
POLICIES = RESEARCH / "design_policy" / "policies" / "dmc-print-v1.json"
SOURCES = RESEARCH / "design_policy" / "sources.json"
CALIBRATION = ROOT / "dmc-renderer" / "fixtures" / "calibration" / "manifest.json"


def promotion_record(**updates) -> PromotionRecord:
    payload = {
        "artifact_kind": "composition_family",
        "artifact_id": "editorial_lead",
        "old_version": "1.0.0",
        "new_version": "1.1.0",
        "from_state": "client_tested",
        "to_state": "promoted",
        "rationale": "Passed reference and client calibration.",
        "golden_hashes": {"contract": "a" * 64, "pdf": "b" * 64},
        "test_matrix": (
            {"sample_id": "apex-02", "passed": True, "failure_codes": ()},
            {"sample_id": "calibration.apex-synthetic", "passed": True, "failure_codes": ()},
        ),
        "deterministic_gate_results": {"hard_failure_count": 0},
        "human_rating_summary": {
            "rater_count": 2,
            "mean_score": 4.2,
            "threshold": 4.0,
            "accepted": True,
        },
        "atlas_comparisons": (
            {
                "atlas_face_id": "apex-02",
                "candidate_raster_sha256": "c" * 64,
                "accepted": True,
                "notes": "hierarchy and proof placement match the reference face",
            },
        ),
        "approver": "owner",
    }
    payload.update(updates)
    return PromotionRecord.model_validate(payload)


def test_promotion_requires_new_version_matrix_gates_humans_and_approver() -> None:
    assert promote(promotion_record()) == "promoted"
    with pytest.raises(ValueError, match="new semantic version"):
        promote(promotion_record(new_version="1.0.0"))
    with pytest.raises(ValueError, match="matrix"):
        promote(
            promotion_record(
                test_matrix=(
                    {"sample_id": "bad", "passed": False, "failure_codes": ("overflow",)},
                )
            )
        )
    with pytest.raises(ValueError, match="human"):
        promote(
            promotion_record(
                human_rating_summary={
                    "rater_count": 1,
                    "mean_score": 5,
                    "threshold": 4,
                    "accepted": True,
                }
            )
        )


def test_family_promotion_requires_accepted_atlas_comparisons() -> None:
    with pytest.raises(ValueError, match="atlas comparison"):
        promote(promotion_record(atlas_comparisons=()))
    with pytest.raises(ValueError, match="atlas comparison"):
        promote(
            promotion_record(
                atlas_comparisons=(
                    {
                        "atlas_face_id": "apex-02",
                        "candidate_raster_sha256": "c" * 64,
                        "accepted": False,
                        "notes": "candidate diverges from the reference face",
                    },
                )
            )
        )


def test_promoted_version_cannot_be_mutated_in_place() -> None:
    with pytest.raises(ValueError, match="immutable"):
        promote(
            promotion_record(
                old_version="1.1.0",
                new_version="1.1.0",
                from_state="promoted",
                to_state="promoted",
            )
        )


def test_production_loaders_reject_everything_below_promoted() -> None:
    with pytest.raises(RegistryIntegrityError, match="not promoted"):
        load_registry(COMPOSITIONS, atlas_path=ATLAS, production=True)
    with pytest.raises(DesignPolicyIntegrityError, match="not promoted"):
        load_design_policy_registry(
            POLICIES,
            sources_path=SOURCES,
            atlas_path=ATLAS,
            production=True,
        )


def test_matrix_covers_each_family_atlas_faces_and_compatible_clients() -> None:
    compositions = load_registry(COMPOSITIONS, atlas_path=ATLAS)
    manifest = json.loads(CALIBRATION.read_text())
    jobs = build_matrix(compositions, manifest)

    for family in compositions.families:
        family_jobs = [job for job in jobs if job.family_id == family.family_id]
        assert set(family.atlas_face_ids) <= {job.sample_id for job in family_jobs}
        assert {
            item["fixture_id"]
            for item in manifest["fixtures"]
            if item["expected_gate_state"] != "rejected"
        } <= {job.sample_id for job in family_jobs}

    results = run_matrix(jobs, runner=lambda job: {"passed": True, "failure_codes": []})
    assert len(results) == len(jobs)
    assert all(result.passed for result in results)
