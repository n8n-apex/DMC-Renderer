from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PREPROCESSOR_ROOT = ROOT / "research" / "preprocessor"
QUALITY_ROOT = ROOT / "research" / "quality_loop"
for path in (PREPROCESSOR_ROOT, QUALITY_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from contracts_v3.release import (  # noqa: E402
    FailureOwner,
    FailureSeverity,
    QualityFailure,
    ReleaseState,
)
from ship_gate_v3 import GateBundleV3, ShipGateV3, can_transition  # noqa: E402


def failure(code: str, severity: str) -> QualityFailure:
    return QualityFailure(
        owner_stage=FailureOwner.ASSETS,
        code=code,
        severity=FailureSeverity(severity),
        face_ids=("face.06",),
        element_ids=("face.06.evidence.image.01",),
        remediation_class="supply_asset",
        detail="fixture failure",
    )


def test_hard_failure_can_never_be_ship_ready() -> None:
    result = ShipGateV3.evaluate(
        GateBundleV3(
            mode="ship",
            failures=(failure("missing_required_asset", "hard"),),
            deterministic_checks_complete=True,
            visual_review_complete=True,
            visual_accepted=True,
            visual_threshold_calibrated=True,
        )
    )

    assert result.state is ReleaseState.REJECTED


def test_known_placeholder_is_draft_not_success() -> None:
    result = ShipGateV3.evaluate(
        GateBundleV3(
            mode="draft",
            failures=(failure("approved_placeholder", "draft"),),
            deterministic_checks_complete=True,
        )
    )

    assert result.state is ReleaseState.DRAFT


def test_structurally_valid_unreviewed_artifact_is_review_candidate() -> None:
    result = ShipGateV3.evaluate(
        GateBundleV3(
            mode="ship",
            deterministic_checks_complete=True,
            visual_review_complete=False,
            visual_threshold_calibrated=False,
        )
    )

    assert result.state is ReleaseState.REVIEW_CANDIDATE


def test_ship_ready_requires_calibrated_accepted_visual_review() -> None:
    result = ShipGateV3.evaluate(
        GateBundleV3(
            mode="ship",
            deterministic_checks_complete=True,
            visual_review_complete=True,
            visual_accepted=True,
            visual_threshold_calibrated=True,
        )
    )

    assert result.state is ReleaseState.SHIP_READY


def test_unknown_failure_code_is_rejected_in_ship_mode() -> None:
    result = ShipGateV3.evaluate(
        GateBundleV3(
            mode="ship",
            failures=(failure("invented_failure", "review"),),
            deterministic_checks_complete=True,
        )
    )

    assert result.state is ReleaseState.REJECTED
    assert "unknown_failure_code" in result.failure_codes


def test_release_state_transitions_cannot_skip_review() -> None:
    assert can_transition(ReleaseState.DRAFT, ReleaseState.REVIEW_CANDIDATE)
    assert can_transition(ReleaseState.REVIEW_CANDIDATE, ReleaseState.SHIP_READY)
    assert not can_transition(ReleaseState.DRAFT, ReleaseState.SHIP_READY)
    assert not can_transition(ReleaseState.REJECTED, ReleaseState.SHIP_READY)


def test_review_required_is_a_dead_end_without_human_review() -> None:
    assert can_transition(ReleaseState.REVIEW_REQUIRED, ReleaseState.REVIEW_CANDIDATE)
    assert can_transition(ReleaseState.REVIEW_REQUIRED, ReleaseState.REJECTED)
    assert can_transition(ReleaseState.REVIEW_REQUIRED, ReleaseState.DRAFT)
    assert not can_transition(ReleaseState.REVIEW_REQUIRED, ReleaseState.SHIP_READY)
    # reachable from every state that was reviewable; hard-failed states stay put
    assert can_transition(ReleaseState.REVIEW_CANDIDATE, ReleaseState.REVIEW_REQUIRED)
    assert can_transition(ReleaseState.SHIP_READY, ReleaseState.REVIEW_REQUIRED)
    assert not can_transition(ReleaseState.REJECTED, ReleaseState.REVIEW_REQUIRED)
    assert not can_transition(ReleaseState.DRAFT, ReleaseState.REVIEW_REQUIRED)
