"""Authoritative v3 release-state evaluator."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict


HERE = Path(__file__).resolve().parent
PREPROCESSOR_ROOT = HERE.parent / "preprocessor"
if str(PREPROCESSOR_ROOT) not in sys.path:
    sys.path.insert(0, str(PREPROCESSOR_ROOT))

from contracts_v3.release import (  # noqa: E402
    FailureOwner,
    FailureSeverity,
    GateResult,
    QualityFailure,
    ReleaseState,
)


KNOWN_FAILURE_CODES = frozenset(
    {
        "approved_placeholder",
        "wrong_face_count",
        "wrong_fragment_count",
        "wrong_pdf_object_count",
        "malformed_a3_allocation",
        "unsupported_pdf_page_size",
        "wrong_case_count",
        "required_role_missing",
        "ungrounded_claim",
        "ungrounded_numeric_candidate",
        "source_appendix_missing",
        "missing_required_asset",
        "illegal_asset_substitution",
        "asset_rights_not_cleared",
        "synthetic_placeholder_asset",
        "asset_reused_across_faces",
        "dead_space_region",
        "visual_density_below_reference",
        "element_clipped",
        "element_hidden",
        "element_overlap",
        "element_overflow",
        "font_below_contract_minimum",
        "required_element_missing",
        "unexpected_element",
        "content_outside_safe_bounds",
        "low_contrast",
        "accent_budget_exceeded",
        "visual_review_rejected",
        "digital_text_loss",
        "digital_link_loss",
        "digital_page_size_changed",
        "print_profile_missing",
        "print_profile_not_production_approved",
        "print_preflight_failed",
        "render_degradation",
        # Task 8 evidence and asset byte-truth codes.
        "claim_missing_source_span",
        "source_appendix_invalid",
        "source_appendix_incomplete",
        "source_bytes_mismatch",
        "asset_bytes_mismatch",
        "asset_bytes_unreadable",
        "asset_dimensions_mismatch",
        "asset_print_resolution_insufficient",
        "asset_path_traversal",
        "asset_face_not_allowed",
        "asset_reference_expired",
        "asset_expiry_unverifiable",
        # Task 10 per-feature pixel codes.
        "ink_occupancy_out_of_bounds",
        "vertical_hierarchy_out_of_bounds",
        "whitespace_fraction_out_of_bounds",
        "type_rhythm_out_of_bounds",
        "proof_visibility_out_of_bounds",
        "image_coverage_out_of_bounds",
        "unknown_failure_code",
    }
)


class GateBundleV3(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: Literal["ship", "draft"]
    failures: tuple[QualityFailure, ...] = ()
    deterministic_checks_complete: bool
    visual_review_complete: bool = False
    visual_accepted: bool = False
    visual_threshold_calibrated: bool = False


_LEGAL_TRANSITIONS = {
    ReleaseState.REJECTED: {ReleaseState.REJECTED, ReleaseState.DRAFT},
    ReleaseState.DRAFT: {
        ReleaseState.REJECTED,
        ReleaseState.DRAFT,
        ReleaseState.REVIEW_CANDIDATE,
    },
    ReleaseState.REVIEW_CANDIDATE: {
        ReleaseState.REJECTED,
        ReleaseState.DRAFT,
        ReleaseState.REVIEW_CANDIDATE,
        ReleaseState.REVIEW_REQUIRED,
        ReleaseState.SHIP_READY,
    },
    ReleaseState.REVIEW_REQUIRED: {
        ReleaseState.REJECTED,
        ReleaseState.DRAFT,
        ReleaseState.REVIEW_CANDIDATE,
    },
    ReleaseState.SHIP_READY: {
        ReleaseState.REJECTED,
        ReleaseState.DRAFT,
        ReleaseState.REVIEW_CANDIDATE,
        ReleaseState.REVIEW_REQUIRED,
        ReleaseState.SHIP_READY,
    },
}


def can_transition(current: ReleaseState, target: ReleaseState) -> bool:
    return target in _LEGAL_TRANSITIONS[current]


class ShipGateV3:
    @classmethod
    def evaluate(cls, bundle: GateBundleV3) -> GateResult:
        failures = list(bundle.failures)
        if bundle.mode == "ship":
            unknown = tuple(
                sorted({failure.code for failure in failures} - KNOWN_FAILURE_CODES)
            )
            if unknown:
                failures.append(
                    QualityFailure(
                        owner_stage=FailureOwner.QUALITY_GATE,
                        code="unknown_failure_code",
                        severity=FailureSeverity.HARD,
                        remediation_class="register_or_remove_failure_code",
                        detail=f"unknown ship-mode codes: {', '.join(unknown)}",
                    )
                )

        severities = {failure.severity for failure in failures}
        if FailureSeverity.HARD in severities:
            state = ReleaseState.REJECTED
        elif FailureSeverity.DRAFT in severities or bundle.mode == "draft":
            state = ReleaseState.DRAFT
        elif not bundle.deterministic_checks_complete:
            state = ReleaseState.REJECTED
            failures.append(
                QualityFailure(
                    owner_stage=FailureOwner.QUALITY_GATE,
                    code="unknown_failure_code",
                    severity=FailureSeverity.HARD,
                    remediation_class="complete_deterministic_checks",
                    detail="deterministic checks are incomplete",
                )
            )
        elif (
            bundle.visual_review_complete
            and bundle.visual_accepted
            and bundle.visual_threshold_calibrated
        ):
            state = ReleaseState.SHIP_READY
        else:
            state = ReleaseState.REVIEW_CANDIDATE

        return GateResult(
            state=state,
            failures=tuple(failures),
            deterministic_checks_complete=bundle.deterministic_checks_complete,
            visual_review_complete=bundle.visual_review_complete,
            visual_threshold_calibrated=bundle.visual_threshold_calibrated,
        )
