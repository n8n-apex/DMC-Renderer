from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest


DMC_ROOT = Path(__file__).resolve().parent.parent
if str(DMC_ROOT) not in sys.path:
    sys.path.insert(0, str(DMC_ROOT))

import service  # noqa: E402


def v2_result() -> dict:
    return {
        "pdf_bytes": b"%PDF-v2",
        "page_count": 17,
        "physical_pages": 17,
        "component_count": 20,
        "overflow": [],
        "content_defects": [],
        "reference_qc": {"cleared": 17, "total": 17, "hard_fails": []},
    }


def v3_result() -> dict:
    return {
        "release_state": "review_candidate",
        "raw_pdf_bytes": b"%PDF-v3-raw",
        "review_pdf_bytes": b"%PDF-v3-review",
        "delivery_pdf_bytes": None,
        "face_count": 20,
        "fragment_count": 19,
        "physical_pages": 19,
        "review_png_count": 19,
        "failures": [],
        "gate_report_sha256": "e" * 64,
        "hashes": {
            "contract": "a" * 64,
            "composition_policy": "b" * 64,
            "family_registry": "c" * 64,
            "build": "d" * 64,
        },
    }


def v3_envelope() -> dict:
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


def test_default_and_named_legacy_routes_use_only_v2_builder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"v2": 0, "v3": 0}

    def build_v2(body, engine="chromium", grade=True, cleanup=True):
        calls["v2"] += 1
        return v2_result()

    def build_v3(body, **_kwargs):
        calls["v3"] += 1
        return v3_result()

    monkeypatch.setattr(service, "build_and_render", build_v2)
    monkeypatch.setattr(service, "build_and_render_v3", build_v3)
    body = {"payload": {}, "images": {}, "brand_tokens": {}}

    default_response = service.render_endpoint(body)
    legacy_response = service.render_legacy_v2_endpoint(body)

    assert default_response.body == b"%PDF-v2"
    assert legacy_response.body == b"%PDF-v2"
    for response in (default_response, legacy_response):
        assert response.headers["x-dmc-pipeline-version"] == "legacy-v2"
        assert response.headers["x-dmc-release-state"] == "legacy-draft"
    assert calls == {"v2": 2, "v3": 0}


def test_explicit_v3_route_never_calls_v2_builder(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"v2": 0, "v3": 0}

    def build_v2(*args, **kwargs):
        calls["v2"] += 1
        return v2_result()

    def build_v3(body, **_kwargs):
        calls["v3"] += 1
        return v3_result()

    monkeypatch.setattr(service, "build_and_render", build_v2)
    monkeypatch.setattr(service, "build_and_render_v3", build_v3)

    response = service.render_v3_endpoint(v3_envelope())

    assert response.body == b"%PDF-v3-review"
    assert calls == {"v2": 0, "v3": 1}


def test_route_table_exposes_all_three_explicit_paths() -> None:
    paths = {route.path for route in service.app.routes}

    assert {"/render", "/render-legacy-v2", "/render-v3"} <= paths
