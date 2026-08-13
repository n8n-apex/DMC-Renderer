from __future__ import annotations

import json
import hashlib
import sys
from pathlib import Path

import pytest


RENDERER_ROOT = Path(__file__).resolve().parent.parent
if str(RENDERER_ROOT) not in sys.path:
    sys.path.insert(0, str(RENDERER_ROOT))

import service  # noqa: E402


def result(state: str) -> dict:
    return {
        "release_state": state,
        "raw_pdf_bytes": b"%PDF-raw",
        "review_pdf_bytes": b"%PDF-review-marked" if state == "review_candidate" else None,
        "artifact_manifest": {
            "path": "/artifact-store/build.deadbeef/manifest.json",
            "manifest_sha256": "f" * 64,
        },
        "delivery_pdf_bytes": b"%PDF-delivery" if state == "ship_ready" else None,
        "face_count": 20,
        "fragment_count": 19,
        "physical_pages": 19,
        "review_png_paths": ["review-p1.png"] if state == "review_candidate" else [],
        "failures": (
            [
                {
                    "owner_stage": "assets",
                    "code": "missing_required_asset",
                    "severity": "hard",
                    "face_ids": ["face.06"],
                    "element_ids": [],
                    "remediation_class": "supply_asset",
                    "detail": "portrait missing",
                }
            ]
            if state == "rejected"
            else []
        ),
        "gate_report_sha256": "e" * 64,
        "hashes": {
            "contract": "a" * 64,
            "composition_policy": "b" * 64,
            "family_registry": "c" * 64,
            "build": "d" * 64,
        },
    }


def envelope() -> dict:
    bundle = service.expected_workflow_verification_bundle_v3()
    bundle["verification_bundle_sha256"] = hashlib.sha256(
        json.dumps(bundle, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "payload": {"meta": {}},
        "images": {},
        "brand_tokens": {},
        "workflow_contract_version": "3.2.1",
        "writer_prompt_version": "5.1.1",
        "schema_resolver_version": "5.2.1",
        "writer_gate_version": "3.1.1",
        "source_ledger_version": "3.2.1",
        "claim_gate_version": "3.2.1",
        "workflow_verification_v3": bundle,
    }


def test_rejected_release_returns_structured_json_without_pdf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(service, "build_and_render_v3", lambda body, **_kwargs: result("rejected"))

    response = service.render_v3_endpoint(envelope())
    payload = json.loads(response.body)

    assert response.status_code == 422
    assert response.media_type == "application/json"
    assert payload["release_state"] == "rejected"
    assert payload["delivery_pdf_available"] is False
    assert payload["artifact_manifest"]["manifest_sha256"] == "f" * 64
    assert b"%PDF" not in response.body


def test_review_candidate_returns_only_the_marked_review_pdf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        service,
        "build_and_render_v3",
        lambda body, **_kwargs: result("review_candidate"),
    )

    response = service.render_v3_endpoint(envelope())

    assert response.body == b"%PDF-review-marked"
    assert response.headers["x-dmc-release-state"] == "review_candidate"
    assert response.headers["x-dmc-review-only"] == "true"
    assert response.headers["x-dmc-review-pngs"] == "1"
    assert response.headers["x-dmc-artifact-manifest-sha256"] == "f" * 64


def test_review_candidate_without_marked_pdf_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    broken = result("review_candidate")
    broken["review_pdf_bytes"] = None
    monkeypatch.setattr(service, "build_and_render_v3", lambda body, **_kwargs: broken)

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as caught:
        service.render_v3_endpoint(envelope())

    assert caught.value.status_code == 500
    assert caught.value.detail["code"] == "review_artifact_missing"


def test_missing_release_state_fails_closed_without_pdf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    broken = result("ship_ready")
    broken.pop("release_state")
    monkeypatch.setattr(service, "build_and_render_v3", lambda body, **_kwargs: broken)

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as caught:
        service.render_v3_endpoint(envelope())

    assert caught.value.status_code == 500
    assert caught.value.detail["code"] == "release_state_missing"


def test_unknown_release_state_fails_closed_without_pdf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    broken = result("ship_ready")
    broken["release_state"] = "shipped"
    monkeypatch.setattr(service, "build_and_render_v3", lambda body, **_kwargs: broken)

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as caught:
        service.render_v3_endpoint(envelope())

    assert caught.value.status_code == 500
    assert caught.value.detail["code"] == "release_state_unknown"


def test_ship_ready_returns_delivery_pdf_and_exact_gate_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        service,
        "build_and_render_v3",
        lambda body, **_kwargs: result("ship_ready"),
    )

    response = service.render_v3_endpoint(envelope())

    assert response.body == b"%PDF-delivery"
    assert response.headers["x-dmc-release-state"] == "ship_ready"
    assert response.headers["x-dmc-gate-report-sha256"] == "e" * 64
    assert response.headers["x-dmc-contract-version"] == "3.0"
    assert response.headers["x-dmc-review-only"] == "false"


def test_draft_release_returns_json_and_no_delivery_pdf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(service, "build_and_render_v3", lambda body, **_kwargs: result("draft"))

    response = service.render_v3_endpoint(envelope())
    payload = json.loads(response.body)

    assert response.status_code == 202
    assert payload["release_state"] == "draft"
    assert payload["delivery_pdf_available"] is False


def test_visual_review_exhausted_returns_review_required_without_pdf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A deck whose visual review can never pass must NOT ship a PDF; the
    build returns review_required.

    The synthetic envelope is rejected by deterministic pixel gates before it
    ever reaches the review branch, so this seam test forces the gate to
    REVIEW_CANDIDATE (deterministic gates pass) and verifies the visual loop's
    review_required verdict propagates and suppresses any delivery."""
    from build_v3 import ReleaseContextV3, build_and_render_v3
    from contracts_v3.release import ReleaseState
    from test_build_v3 import valid_envelope
    import tempfile

    import quality_loop.visual_review_loop_v3 as loop_module

    real_evaluate = __import__("build_v3")._evaluate_release

    def review_candidate_gate(failures, context):
        return real_evaluate(failures, context).model_copy(
            update={"state": ReleaseState.REVIEW_CANDIDATE}
        )

    monkeypatch.setattr(__import__("build_v3"), "_evaluate_release", review_candidate_gate)
    monkeypatch.setattr(
        loop_module, "run_visual_review_loop",
        lambda *args, **kwargs: {
            "release_state": "review_required",
            "delivery_pdf_bytes": None,
            "attempt_records": [{"page": 0, "verdict": "rejected"}],
            "whole_deck_passes": 1,
            "page_outcomes": {0: {"passed": False, "verdict": "rejected"}},
        },
    )

    envelope = valid_envelope(Path(tempfile.mkdtemp()) / "assets")
    result = build_and_render_v3(
        envelope,
        output_dir=Path(tempfile.mkdtemp()) / "build",
        cleanup=False,
        release_context=ReleaseContextV3(allow_synthetic_assets=True),
    )
    assert result["release_state"] == "review_required"
    assert result["delivery_pdf_bytes"] is None
