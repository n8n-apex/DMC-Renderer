from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException


RENDERER_ROOT = Path(__file__).resolve().parent.parent
if str(RENDERER_ROOT) not in sys.path:
    sys.path.insert(0, str(RENDERER_ROOT))

import service  # noqa: E402


WORKFLOW_VERSIONS = {
    "workflow_contract_version": "3.2.1",
    "writer_prompt_version": "5.1.1",
    "schema_resolver_version": "5.2.1",
    "writer_gate_version": "3.1.1",
    "source_ledger_version": "3.2.1",
    "claim_gate_version": "3.2.1",
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
        **WORKFLOW_VERSIONS,
        "workflow_verification_v3": bundle,
    }


def successful_result() -> dict:
    return {
        "pdf_bytes": b"%PDF-v3-fixture",
        "release_state": "ship_ready",
        "face_count": 20,
        "fragment_count": 19,
        "physical_pages": 19,
        "hashes": {
            "contract": "a" * 64,
            "composition_policy": "b" * 64,
            "family_registry": "c" * 64,
            "build": "d" * 64,
        },
    }


def test_render_v3_route_is_added_without_replacing_legacy_route() -> None:
    paths = {route.path for route in service.app.routes}

    assert "/render" in paths
    assert "/render-v3" in paths


def test_render_v3_returns_pdf_and_all_provenance_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(service, "build_and_render_v3", lambda body, **_kwargs: successful_result())

    response = service.render_v3_endpoint(envelope())

    assert response.body == b"%PDF-v3-fixture"
    assert response.headers["x-dmc-contract-hash"] == "a" * 64
    assert response.headers["x-dmc-composition-policy-hash"] == "b" * 64
    assert response.headers["x-dmc-family-registry-hash"] == "c" * 64
    assert response.headers["x-dmc-build-hash"] == "d" * 64
    assert response.headers["x-logical-faces"] == "20"
    assert response.headers["x-rendered-fragments"] == "19"


def test_render_v3_returns_structured_stage_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class SyntheticFailure(RuntimeError):
        owner_stage = "composition_planner"
        code = "region_does_not_fit"
        face_ids = ("face.04",)
        element_ids = ("face.04.body.01",)

    def fail(body, **_kwargs):
        raise SyntheticFailure("copy exceeds the selected region")

    monkeypatch.setattr(service, "build_and_render_v3", fail)

    with pytest.raises(HTTPException) as caught:
        service.render_v3_endpoint(envelope())

    assert caught.value.status_code == 422
    assert caught.value.detail == {
        "owner_stage": "composition_planner",
        "code": "region_does_not_fit",
        "face_ids": ["face.04"],
        "element_ids": ["face.04.body.01"],
        "detail": "copy exceeds the selected region",
    }


def test_render_v3_rejects_missing_envelope_fields_before_build() -> None:
    with pytest.raises(HTTPException) as caught:
        service.render_v3_endpoint({"payload": {}, "images": {}})

    assert caught.value.status_code == 400
    assert "brand_tokens" in str(caught.value.detail)
