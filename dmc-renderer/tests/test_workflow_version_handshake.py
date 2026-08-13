from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException


DMC_ROOT = Path(__file__).resolve().parent.parent
if str(DMC_ROOT) not in sys.path:
    sys.path.insert(0, str(DMC_ROOT))

import service  # noqa: E402
import build_live  # noqa: E402
from contracts_v3.build_manifest import (  # noqa: E402
    BuildManifestV3,
    BuildVersions,
)
from pydantic import BaseModel, ConfigDict, ValidationError  # noqa: E402


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


def result() -> dict:
    return {
        "pdf_bytes": b"%PDF",
        "delivery_pdf_bytes": b"%PDF",
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


def test_exact_deployed_artifact_bundle_is_hashed_into_build_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = {}

    def fake_build(body, **_kwargs):
        captured.update(body)
        return result()

    monkeypatch.setattr(service, "build_and_render_v3", fake_build)
    body = envelope()

    response = service.render_v3_endpoint(body)

    expected_hash = body["workflow_verification_v3"]["verification_bundle_sha256"]
    assert captured["workflow_verification_bundle_sha256"] == expected_hash
    assert response.headers["x-dmc-workflow-verification-sha256"] == expected_hash


def test_verification_bundle_covers_all_five_evidence_artifacts() -> None:
    bundle = service.expected_workflow_verification_bundle_v3()

    assert bundle["workflow_contract_version"] == "3.2.1"
    assert [artifact["artifact_id"] for artifact in bundle["artifacts"]] == [
        "writer_prompt",
        "schema_resolver",
        "writer_gate",
        "source_ledger",
        "claim_gate",
    ]


def test_hash_or_node_mismatch_rejects_before_build(monkeypatch: pytest.MonkeyPatch) -> None:
    called = False

    def fake_build(body, **_kwargs):
        nonlocal called
        called = True
        return result()

    monkeypatch.setattr(service, "build_and_render_v3", fake_build)
    body = envelope()
    body["workflow_verification_v3"]["artifacts"][0]["sha256"] = "0" * 64
    unsigned = copy.deepcopy(body["workflow_verification_v3"])
    unsigned.pop("verification_bundle_sha256")
    body["workflow_verification_v3"]["verification_bundle_sha256"] = hashlib.sha256(
        json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()

    with pytest.raises(HTTPException) as caught:
        service.render_v3_endpoint(body)

    assert called is False
    assert caught.value.status_code == 409
    assert caught.value.detail["code"] == "workflow_artifact_mismatch"


def test_bundle_rejects_extra_fields_including_credentials() -> None:
    body = envelope()
    body["workflow_verification_v3"]["credential"] = "must-not-be-stored"

    with pytest.raises(HTTPException) as caught:
        service.render_v3_endpoint(body)

    assert caught.value.status_code == 409
    assert caught.value.detail["code"] == "workflow_verification_bundle_invalid"


@pytest.mark.parametrize("version_field", tuple(WORKFLOW_VERSIONS))
def test_every_submitted_workflow_version_is_required_before_build(
    monkeypatch: pytest.MonkeyPatch,
    version_field: str,
) -> None:
    called = False

    def fake_build(body, **_kwargs):
        nonlocal called
        called = True
        return result()

    monkeypatch.setattr(service, "build_and_render_v3", fake_build)
    body = envelope()
    body.pop(version_field)

    with pytest.raises(HTTPException) as caught:
        service.render_v3_endpoint(body)

    assert called is False
    assert caught.value.detail["code"] == "workflow_versions_missing"
    assert caught.value.detail["fields"] == [version_field]


@pytest.mark.parametrize("version_field", tuple(WORKFLOW_VERSIONS))
def test_every_mismatched_workflow_version_is_rejected_before_build(
    monkeypatch: pytest.MonkeyPatch,
    version_field: str,
) -> None:
    called = False

    def fake_build(body, **_kwargs):
        nonlocal called
        called = True
        return result()

    monkeypatch.setattr(service, "build_and_render_v3", fake_build)
    body = envelope()
    body[version_field] = "999.0.0"

    with pytest.raises(HTTPException) as caught:
        service.render_v3_endpoint(body)

    assert called is False
    assert caught.value.detail["code"] == "workflow_version_unsupported"
    assert caught.value.detail["field"] == version_field


class ManifestBundle(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    manifest: BuildManifestV3


def test_precomposition_build_versions_retain_only_supported_workflow_fields() -> None:
    bundle = ManifestBundle(
        manifest=BuildManifestV3(
            versions=BuildVersions(
                product_profile="test-profile",
                workflow_authority="non_workflow",
            ),
            artifact_hashes={"source_ledger": "a" * 64},
        )
    )
    body = {
        **WORKFLOW_VERSIONS,
        "workflow_verification_bundle_sha256": "b" * 64,
        "credential_version": "must-not-be-retained",
    }

    retained = build_live._with_workflow_provenance_v3(bundle, body)

    assert retained.manifest.versions.model_dump(exclude_none=True) == {
        "contract_schema": "3.0",
        "product_profile": "test-profile",
        "preprocessor": "3.0",
        "workflow_authority": "verified",
        "workflow_contract": "3.2.1",
        "writer_prompt": "5.1.1",
        "schema_resolver": "5.2.1",
        "writer_gate": "3.1.1",
        "source_ledger": "3.2.1",
        "claim_gate": "3.2.1",
    }
    assert retained.manifest.artifact_hashes["workflow_verification_bundle"] == "b" * 64


@pytest.mark.parametrize(
    ("version_field", "malformed_value"),
    (
        ("writer_prompt_version", {}),
        ("claim_gate_version", []),
    ),
)
def test_precomposition_rejects_malformed_supported_workflow_versions(
    version_field: str,
    malformed_value: object,
) -> None:
    bundle = ManifestBundle(
        manifest=BuildManifestV3(
            versions=BuildVersions(
                product_profile="test-profile",
                workflow_authority="non_workflow",
            ),
            artifact_hashes={"source_ledger": "a" * 64},
        )
    )
    body = {**WORKFLOW_VERSIONS, version_field: malformed_value}

    with pytest.raises(ValidationError):
        build_live._with_workflow_provenance_v3(bundle, body)


def test_build_versions_reject_arbitrary_version_keys() -> None:
    with pytest.raises(ValidationError):
        BuildVersions(
            product_profile="test-profile",
            workflow_authority="non_workflow",
            credential_version="must-not-be-retained",
        )


def test_direct_precomposition_without_workflow_ingress_stays_explicitly_non_workflow() -> None:
    bundle = ManifestBundle(
        manifest=BuildManifestV3(
            versions=BuildVersions(
                product_profile="test-profile",
                workflow_authority="non_workflow",
            ),
            artifact_hashes={"source_ledger": "a" * 64},
        )
    )

    retained = build_live._with_workflow_provenance_v3(bundle, {})

    assert retained.manifest.versions.workflow_authority == "non_workflow"
