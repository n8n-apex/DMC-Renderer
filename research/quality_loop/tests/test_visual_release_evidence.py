"""Release-evidence mechanics for visual calibration (hardening Task 10).

Every rating row in this file is a SYNTHETIC TEST FIXTURE constructed in
memory purely to prove the mechanics of threshold derivation and policy
loading. No fabricated human data is ever written to
``research/quality_loop/calibration/ratings.jsonl``: that file stays empty
until two real blind raters have produced real rows, and the committed
threshold policy stays ``unapproved_draft`` with null values until then.
Those are human gates and cannot be coded around.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import pytest
from PIL import Image


ROOT = Path(__file__).resolve().parents[3]
RESEARCH_ROOT = ROOT / "research"
PREPROCESSOR_ROOT = RESEARCH_ROOT / "preprocessor"
QUALITY_ROOT = RESEARCH_ROOT / "quality_loop"
MIGRATIONS_ROOT = RESEARCH_ROOT / "migrations"
for path in (RESEARCH_ROOT, PREPROCESSOR_ROOT, QUALITY_ROOT, MIGRATIONS_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from composition_registry.promotion import PromotionRecord, promote  # noqa: E402
from gates.pixels_v3 import (  # noqa: E402
    PixelSample,
    load_pixel_policy,
    run_pixel_gate_v3,
)
from legacy_report_v3 import MigrationRecord  # noqa: E402
from reference_rubric_v3 import (  # noqa: E402
    BlindRatingRow,
    ThresholdDerivationError,
    ThresholdPolicyNotCalibratedError,
    derive_visual_threshold_policy,
    load_visual_threshold_policy,
    require_calibrated_threshold_policy,
)


THRESHOLD_POLICY_PATH = (
    RESEARCH_ROOT / "calibration" / "policies" / "visual-threshold-v1.json"
)
PIXEL_POLICY_PATH = QUALITY_ROOT / "policies" / "pixel_policy_v1.json"
RATINGS_JSONL_PATH = QUALITY_ROOT / "calibration" / "ratings.jsonl"
REAL_FIXTURES = ROOT / "dmc-renderer" / "fixtures" / "v3" / "real"

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


def synthetic_row(
    rater_id: str,
    cohort: str,
    overall: int,
    *,
    seed: int = 0,
) -> BlindRatingRow:
    """A clearly synthetic in-memory rating row. Never persisted."""
    return BlindRatingRow(
        rater_id=rater_id,
        cohort=cohort,
        face_image_sha256=hashlib.sha256(
            f"synthetic-test-fixture:{cohort}:{rater_id}:{seed}".encode("utf-8")
        ).hexdigest(),
        rubric_version="3.0",
        scores={dimension: overall for dimension in DIMENSIONS},
        overall=overall,
        rated_at="2026-08-06T10:00:00+00:00",
    )


def four_rater_rows() -> tuple[BlindRatingRow, ...]:
    return (
        synthetic_row("rater-a", "reference", 5),
        synthetic_row("rater-b", "reference", 4),
        synthetic_row("rater-a", "candidate", 3),
        synthetic_row("rater-b", "candidate", 4),
    )


# ---------------------------------------------------------------------------
# Honesty guards on committed calibration data
# ---------------------------------------------------------------------------


def test_committed_ratings_file_contains_no_fabricated_rows() -> None:
    lines = RATINGS_JSONL_PATH.read_text(encoding="utf-8").splitlines()
    data_lines = [
        line for line in lines if line.strip() and not line.lstrip().startswith("#")
    ]
    assert data_lines == [], (
        "ratings.jsonl must stay empty of rating rows until real blind "
        "human ratings exist; fabricating them is forbidden"
    )


def test_committed_threshold_policy_is_an_unapproved_null_draft() -> None:
    payload = json.loads(THRESHOLD_POLICY_PATH.read_text(encoding="utf-8"))
    assert payload["status"] == "unapproved_draft"
    assert payload["threshold"] is None
    assert payload["derivation"]["ratings_dataset_sha256"] is None
    assert payload["derivation"]["derivation_code_sha256"] is None


# ---------------------------------------------------------------------------
# (a) An unapproved policy can never be used as calibrated
# ---------------------------------------------------------------------------


def test_unapproved_policy_file_is_refused_as_calibrated() -> None:
    policy = load_visual_threshold_policy(THRESHOLD_POLICY_PATH)
    assert policy.status == "unapproved_draft"
    assert policy.threshold is None

    with pytest.raises(ThresholdPolicyNotCalibratedError):
        require_calibrated_threshold_policy(THRESHOLD_POLICY_PATH)


def test_derived_but_unapproved_policy_is_still_refused(tmp_path: Path) -> None:
    derived = derive_visual_threshold_policy(four_rater_rows())
    assert derived["status"] == "derived_unapproved"
    path = tmp_path / "derived-policy.json"
    path.write_text(json.dumps(derived, sort_keys=True), encoding="utf-8")

    with pytest.raises(ThresholdPolicyNotCalibratedError):
        require_calibrated_threshold_policy(path)


def test_approved_policy_with_real_values_is_calibrated(tmp_path: Path) -> None:
    # Synthetic approval fixture, written only under tmp_path: proves the
    # mechanics that Task 4's VisualReviewEvidenceV3 flow will hash once a
    # real approved policy lands.
    derived = derive_visual_threshold_policy(four_rater_rows())
    approved = {
        **derived,
        "status": "approved",
        "approved_by": "synthetic-fixture-owner",
        "approved_at": "2026-08-06T12:00:00+00:00",
    }
    path = tmp_path / "approved-policy.json"
    path.write_text(json.dumps(approved, sort_keys=True), encoding="utf-8")

    policy, policy_sha256 = require_calibrated_threshold_policy(path)

    assert policy.status == "approved"
    assert policy.threshold is not None
    assert policy_sha256 == hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# (b) Derivation refuses <2 raters or a missing cohort
# ---------------------------------------------------------------------------


def test_derivation_refuses_single_rater() -> None:
    rows = (
        synthetic_row("rater-a", "reference", 5),
        synthetic_row("rater-a", "candidate", 4),
    )
    with pytest.raises(ThresholdDerivationError):
        derive_visual_threshold_policy(rows)


def test_derivation_refuses_missing_cohort() -> None:
    rows = (
        synthetic_row("rater-a", "reference", 5),
        synthetic_row("rater-b", "reference", 4),
    )
    with pytest.raises(ThresholdDerivationError):
        derive_visual_threshold_policy(rows)


def test_derivation_refuses_mixed_rubric_versions() -> None:
    rows = four_rater_rows()
    mixed = rows[:3] + (
        rows[3].model_copy(update={"rubric_version": "2.0"}),
    )
    with pytest.raises(ThresholdDerivationError):
        derive_visual_threshold_policy(mixed)


# ---------------------------------------------------------------------------
# (c) A derived policy from >=2-rater synthetic rows is complete
# ---------------------------------------------------------------------------


def test_derived_policy_contains_threshold_and_both_hashes() -> None:
    rows = four_rater_rows()
    derived = derive_visual_threshold_policy(rows)

    # reference overall = (5, 4), candidate overall = (3, 4)
    reference_mean = 4.5
    pooled_std = math.sqrt(((5 - 4.5) ** 2 + (4 - 4.5) ** 2 + (3 - 3.5) ** 2 + (4 - 3.5) ** 2) / 2)
    expected = round(reference_mean - pooled_std, 3)

    assert derived["threshold"] == expected
    assert derived["rubric_version"] == "3.0"
    for key in ("ratings_dataset_sha256", "derivation_code_sha256"):
        value = derived["derivation"][key]
        assert isinstance(value, str) and len(value) == 64
        int(value, 16)


def test_derivation_is_deterministic_and_order_independent() -> None:
    rows = four_rater_rows()
    first = derive_visual_threshold_policy(rows)
    second = derive_visual_threshold_policy(tuple(reversed(rows)))
    assert first == second


# ---------------------------------------------------------------------------
# Pixel gate: measurable features recorded per face
# ---------------------------------------------------------------------------


def _paper_face(tmp_path: Path, name: str) -> Path:
    """A synthetic face: paper ground, headline band, body rows, accent proof."""
    width, height = 400, 566
    image = Image.new("RGB", (width, height), (245, 241, 232))
    # headline band near the top
    for y in range(40, 90):
        for x in range(30, 340):
            image.putpixel((x, y), (23, 23, 20))
    # three body text bands
    for band_top in (180, 260, 340):
        for y in range(band_top, band_top + 30):
            for x in range(30, 370):
                image.putpixel((x, y), (60, 58, 54))
    # accent proof marker in the lower proof band
    for y in range(480, 520):
        for x in range(30, 150):
            image.putpixel((x, y), (201, 78, 44))
    path = tmp_path / f"{name}.png"
    image.save(path)
    return path


def test_pixel_gate_records_every_feature_per_face(tmp_path: Path) -> None:
    policy = load_pixel_policy(PIXEL_POLICY_PATH)
    face_path = _paper_face(tmp_path, "face-01")
    sample = PixelSample(
        face_id="face.01",
        family_id="editorial_lead",
        image_path=str(face_path),
        accent_rgb=(201, 78, 44),
    )

    report = run_pixel_gate_v3((sample,), policy)

    assert len(report.faces) == 1
    face = report.faces[0]
    assert face.face_id == "face.01"
    assert face.family_id == "editorial_lead"
    for feature in (
        "accent_fraction",
        "ink_occupancy",
        "vertical_hierarchy",
        "whitespace_fraction",
        "proof_visibility",
        "image_coverage",
    ):
        value = getattr(face, feature)
        assert isinstance(value, float)
    assert 0.0 <= face.accent_fraction <= 1.0
    assert 0.0 <= face.ink_occupancy <= 1.0
    assert 0.0 <= face.whitespace_fraction <= 1.0
    assert 0.0 <= face.proof_visibility <= 1.0
    assert 0.0 <= face.image_coverage <= 1.0
    assert face.vertical_hierarchy > 0.0
    assert isinstance(face.type_rhythm_bands, int)
    assert face.type_rhythm_bands >= 4  # headline + three body bands + proof


def test_pixel_feature_violations_fail_with_named_codes(tmp_path: Path) -> None:
    policy = load_pixel_policy(PIXEL_POLICY_PATH)

    black_path = tmp_path / "all-black.png"
    Image.new("RGB", (400, 566), (0, 0, 0)).save(black_path)
    black_codes = {
        failure.code
        for failure in run_pixel_gate_v3(
            (
                PixelSample(
                    face_id="face.01",
                    family_id="editorial_lead",
                    image_path=str(black_path),
                    accent_rgb=(201, 78, 44),
                ),
            ),
            policy,
        ).failures
    }
    assert "ink_occupancy_out_of_bounds" in black_codes
    assert "whitespace_fraction_out_of_bounds" in black_codes

    accent_path = tmp_path / "accent-flood.png"
    accent_image = Image.new("RGB", (400, 566), (245, 241, 232))
    for y in range(566):
        for x in range(240):
            accent_image.putpixel((x, y), (201, 78, 44))
    accent_image.save(accent_path)
    accent_codes = {
        failure.code
        for failure in run_pixel_gate_v3(
            (
                PixelSample(
                    face_id="face.02",
                    family_id="editorial_lead",
                    image_path=str(accent_path),
                    accent_rgb=(201, 78, 44),
                ),
            ),
            policy,
        ).failures
    }
    assert "accent_budget_exceeded" in accent_codes


# ---------------------------------------------------------------------------
# (d) Synthetic fixtures can never satisfy client_tested promotion
# ---------------------------------------------------------------------------


def _client_tested_record(test_matrix: tuple[dict, ...]) -> PromotionRecord:
    return PromotionRecord.model_validate(
        {
            "artifact_kind": "composition_family",
            "artifact_id": "editorial_lead",
            "old_version": "1.0.0",
            "new_version": "1.1.0",
            "from_state": "corpus_tested",
            "to_state": "client_tested",
            "rationale": "Synthetic-fixture promotion attempt (test).",
            "golden_hashes": {"contract": "a" * 64},
            "test_matrix": test_matrix,
            "deterministic_gate_results": {"hard_failure_count": 0},
            "human_rating_summary": {
                "rater_count": 2,
                "mean_score": 4.5,
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
    )


def test_all_synthetic_matrix_cannot_reach_client_tested() -> None:
    record = _client_tested_record(
        (
            {"sample_id": "calibration.apex-synthetic", "passed": True, "failure_codes": ()},
            {"sample_id": "calibration.service-business", "passed": True, "failure_codes": ()},
        )
    )
    with pytest.raises(ValueError, match="synthetic"):
        promote(record)


def test_client_tested_requires_and_accepts_a_real_client_sample() -> None:
    record = _client_tested_record(
        (
            {"sample_id": "calibration.apex-synthetic", "passed": True, "failure_codes": ()},
            {"sample_id": "client.rights-cleared-01", "passed": True, "failure_codes": ()},
        )
    )
    assert promote(record) == "client_tested"


# ---------------------------------------------------------------------------
# Standing human gate: Jousef and Christopher stay unrenderable
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("fixture_name", "expected_blockers"),
    (("jousef", 180), ("christopher", 61)),
)
def test_migration_fixtures_remain_unrenderable(
    fixture_name: str, expected_blockers: int
) -> None:
    payload = json.loads(
        (REAL_FIXTURES / f"{fixture_name}-source-envelope.json").read_text(
            encoding="utf-8"
        )
    )
    record = MigrationRecord.model_validate(payload)

    assert record.renderable is False
    assert len(record.blockers) == expected_blockers
    assert record.sources == ()
    assert record.claims == ()
    assert record.assets == ()
