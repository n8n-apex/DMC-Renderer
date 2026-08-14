from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
RESEARCH_ROOT = ROOT / "research"
PREPROCESSOR_ROOT = RESEARCH_ROOT / "preprocessor"
QUALITY_ROOT = RESEARCH_ROOT / "quality_loop"
for path in (RESEARCH_ROOT, PREPROCESSOR_ROOT, QUALITY_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

# Imported via the quality_loop package name so the top-level module name
# "calibration" stays free for research/calibration (they collide when both
# suites run in one pytest invocation).
from quality_loop.calibration.build_dataset import build_calibration_dataset  # noqa: E402
from composition_registry.registry import load_registry  # noqa: E402
from contracts_v3.release import (  # noqa: E402
    FailureOwner,
    FailureSeverity,
    QualityFailure,
    ReleaseState,
)
from reference_rubric_v3 import (  # noqa: E402
    BlindRatingRow,
    ThresholdDerivationError,
    VisualReviewResult,
    build_reference_rubric,
    derive_visual_threshold_policy,
    resolve_visual_release_state,
)


ATLAS_PATH = RESEARCH_ROOT / "reference-atlas" / "reference-atlas.json"
REGISTRY_PATH = RESEARCH_ROOT / "composition_registry" / "families" / "dmc-v1.json"


def test_family_rubric_has_all_observable_dimensions_and_atlas_links() -> None:
    atlas = json.loads(ATLAS_PATH.read_text(encoding="utf-8"))
    atlas_ids = {face["id"] for face in atlas["faces"]}
    registry = load_registry(REGISTRY_PATH, atlas_path=ATLAS_PATH)

    rubric = build_reference_rubric(registry)

    assert set(rubric.dimensions) == {
        "hierarchy",
        "composition",
        "typography",
        "rhythm",
        "density",
        "proof_visibility",
        "mechanism_clarity",
        "brand_coherence",
    }
    assert {row.family_id for row in rubric.rows} == {
        family.family_id for family in registry.families
    }
    assert all(set(row.atlas_face_ids) <= atlas_ids for row in rubric.rows)
    assert all(row.observable_facts and row.review_method in {"measured", "blind_human"} for row in rubric.rows)
    assert "hierarchy.one-dominant-mechanism" in rubric.design_policy_ids
    assert "review.observation-problem-fix" in rubric.design_policy_ids


def test_calibration_dataset_contains_all_120_references_and_other_cohorts(tmp_path: Path) -> None:
    output_path = tmp_path / "dataset.json"

    dataset = build_calibration_dataset(
        ATLAS_PATH,
        output_path,
        current_failures=(
            {"sample_id": "failure.current.01", "image_path": "/tmp/failure.png", "family_id": "editorial_lead"},
        ),
        candidates=(
            {"sample_id": "candidate.v3.01", "image_path": "/tmp/candidate.png", "family_id": "editorial_lead"},
        ),
    )

    assert sum(item.cohort == "reference" for item in dataset.samples) == 120
    assert {item.cohort for item in dataset.samples} == {"reference", "current_failure", "v3_candidate"}
    assert output_path.is_file()


def rating(rater_id: str, cohort: str) -> BlindRatingRow:
    """SYNTHETIC in-memory test fixture; never written to ratings.jsonl."""
    import hashlib

    return BlindRatingRow(
        rater_id=rater_id,
        cohort=cohort,
        face_image_sha256=hashlib.sha256(
            f"synthetic-test-fixture:{cohort}:{rater_id}".encode("utf-8")
        ).hexdigest(),
        rubric_version="3.0",
        scores={
            "hierarchy": 4,
            "composition": 4,
            "typography": 4,
            "rhythm": 4,
            "density": 4,
            "proof_visibility": 4,
            "mechanism_clarity": 4,
            "brand_coherence": 4,
        },
        overall=4,
        rated_at=datetime(2026, 8, 3, tzinfo=timezone.utc).isoformat(),
    )


def test_threshold_is_withheld_until_two_raters_cover_reference_and_candidate() -> None:
    import pytest

    with pytest.raises(ThresholdDerivationError):
        derive_visual_threshold_policy(
            (rating("rater-a", "reference"), rating("rater-a", "candidate"))
        )

    derived = derive_visual_threshold_policy(
        (
            rating("rater-a", "reference"),
            rating("rater-a", "candidate"),
            rating("rater-b", "reference"),
            rating("rater-b", "candidate"),
        )
    )
    assert derived["threshold"] is not None
    assert derived["status"] == "derived_unapproved"


def test_visual_score_cannot_override_a_hard_failure() -> None:
    hard_failure = QualityFailure(
        owner_stage=FailureOwner.ASSETS,
        code="missing_required_asset",
        severity=FailureSeverity.HARD,
        face_ids=("face.06",),
        remediation_class="supply_asset",
        detail="portrait missing",
    )
    visual = VisualReviewResult(
        calibrated=True,
        accepted=True,
        mean_score=5,
        rater_ids=("rater-a", "rater-b"),
    )

    assert resolve_visual_release_state((hard_failure,), visual) is ReleaseState.REJECTED
