"""REVIEW_REQUIRED is a distinct, non-shippable release state."""
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contracts_v3.release import ReleaseState, ReviewAttemptRecord, ReviewVerdict  # noqa: E402


def test_review_required_is_a_distinct_state() -> None:
    assert ReleaseState.REVIEW_REQUIRED == "review_required"
    assert ReleaseState.REVIEW_REQUIRED != ReleaseState.REVIEW_CANDIDATE
    assert ReleaseState.REVIEW_REQUIRED != ReleaseState.SHIP_READY


def test_review_attempt_record_holds_the_full_trail() -> None:
    record = ReviewAttemptRecord(
        attempt_index=1,
        contract_sha256="a" * 64,
        render_sha256="b" * 64,
        page_scores={"face.01": {"score": 3, "rationale": "ok"}},
        conductor_summary="1 applied, 0 flagged",
        verdict=ReviewVerdict.PASSED,
    )
    assert record.verdict.value == "passed"
    assert record.contract_sha256 == "a" * 64
    assert record.attempt_index == 1
