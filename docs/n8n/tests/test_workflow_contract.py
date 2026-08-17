from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException


ROOT = Path(__file__).resolve().parents[3]
N8N_ROOT = ROOT / "docs" / "n8n"
DMC_ROOT = ROOT / "dmc-renderer"
for path in (N8N_ROOT, DMC_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import service  # noqa: E402
from verify_workflow_contract import (  # noqa: E402
    load_workflow_contract,
    verify_workflow_contract,
)


MANIFEST_PATH = N8N_ROOT / "workflow-contract-v3.json"
EXPECTED_ARTIFACTS = {
    "writer_prompt": ("Section Writer v5", "writer_prompt_version", "5.1.1"),
    "schema_resolver": (
        "Resolve Schema and Build Prompts v5",
        "schema_resolver_version",
        "5.2.1",
    ),
    "writer_gate": ("Writer Gate v3", "writer_gate_version", "3.1.1"),
    "source_ledger": ("Source Ledger v3", "source_ledger_version", "3.2.1"),
    "claim_gate": ("Claim Gate v3", "claim_gate_version", "3.2.1"),
}
EXPECTED_WORKFLOW_VERSIONS = {
    "workflow_contract_version": "3.2.1",
    **{
        envelope_field: semantic_version
        for _, envelope_field, semantic_version in EXPECTED_ARTIFACTS.values()
    },
}


def versioned_envelope() -> dict:
    return {
        "payload": {"meta": {}},
        "images": {},
        "brand_tokens": {},
        **EXPECTED_WORKFLOW_VERSIONS,
    }


def test_repository_artifacts_match_the_versioned_workflow_contract() -> None:
    contract = load_workflow_contract(MANIFEST_PATH)
    report = verify_workflow_contract(contract, ROOT)

    assert contract["contract_version"] == "3.2.1"
    assert {
        artifact["artifact_id"]: (
            artifact["expected_node_name"],
            artifact["envelope_version_field"],
            artifact["semantic_version"],
        )
        for artifact in contract["artifacts"]
    } == EXPECTED_ARTIFACTS
    assert len(contract["artifacts"]) == 5
    assert report["accepted"] is True
    assert report["mismatches"] == []


@pytest.mark.parametrize("artifact_id", tuple(EXPECTED_ARTIFACTS))
def test_one_byte_change_is_detected_without_network_access(
    tmp_path: Path,
    artifact_id: str,
) -> None:
    contract = load_workflow_contract(MANIFEST_PATH)
    artifact = next(
        item for item in contract["artifacts"] if item["artifact_id"] == artifact_id
    )
    copied_root = tmp_path / "repository"
    copied_path = copied_root / artifact["repository_path"]
    copied_path.parent.mkdir(parents=True)
    shutil.copyfile(ROOT / artifact["repository_path"], copied_path)
    copied_path.write_bytes(copied_path.read_bytes() + b"X")

    report = verify_workflow_contract(
        contract,
        copied_root,
        artifact_ids=(artifact["artifact_id"],),
    )

    assert report["accepted"] is False
    assert report["mismatches"][0]["code"] == "artifact_hash_mismatch"


def test_verification_rejects_an_empty_artifact_selection() -> None:
    contract = load_workflow_contract(MANIFEST_PATH)

    with pytest.raises(ValueError, match="artifact selection must not be empty"):
        verify_workflow_contract(contract, ROOT, artifact_ids=())


def test_verification_rejects_unknown_artifact_ids() -> None:
    contract = load_workflow_contract(MANIFEST_PATH)

    with pytest.raises(ValueError, match="unknown workflow artifact IDs: unknown_gate"):
        verify_workflow_contract(contract, ROOT, artifact_ids=("unknown_gate",))


def test_v3_2_1_contract_rejects_duplicate_envelope_version_fields(
    tmp_path: Path,
) -> None:
    contract = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    contract["artifacts"][1]["envelope_version_field"] = contract["artifacts"][0][
        "envelope_version_field"
    ]
    path = tmp_path / "duplicate-envelope-field.json"
    path.write_text(json.dumps(contract), encoding="utf-8")

    with pytest.raises(ValueError, match="envelope version fields must be unique"):
        load_workflow_contract(path)


def test_v3_2_1_contract_requires_exact_five_artifact_ids(tmp_path: Path) -> None:
    contract = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    contract["artifacts"] = contract["artifacts"][:-1]
    path = tmp_path / "missing-artifact.json"
    path.write_text(json.dumps(contract), encoding="utf-8")

    with pytest.raises(ValueError, match="requires exactly the five evidence artifacts"):
        load_workflow_contract(path)


def test_evidence_modules_export_their_contract_semantic_versions() -> None:
    script = """
const sourceLedger = require('./docs/n8n/source-ledger-node-v3.js');
const claimGate = require('./docs/n8n/claim-gate-v3.js');
process.stdout.write(JSON.stringify({
  source_ledger: sourceLedger.SOURCE_LEDGER_VERSION,
  claim_gate: claimGate.CLAIM_GATE_VERSION,
}));
"""
    completed = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(completed.stdout) == {
        "source_ledger": "3.2.1",
        "claim_gate": "3.2.1",
    }


@pytest.mark.parametrize("missing_field", tuple(EXPECTED_WORKFLOW_VERSIONS))
def test_render_v3_rejects_each_missing_workflow_version_before_build(
    monkeypatch: pytest.MonkeyPatch,
    missing_field: str,
) -> None:
    called = False

    def fake_build(body, **_kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(service, "build_and_render_v3", fake_build)
    envelope = versioned_envelope()
    envelope.pop(missing_field)

    with pytest.raises(HTTPException) as caught:
        service.render_v3_endpoint(envelope)

    assert called is False
    assert caught.value.status_code == 409
    assert caught.value.detail["code"] == "workflow_versions_missing"
    assert caught.value.detail["fields"] == [missing_field]


@pytest.mark.parametrize("version_field", tuple(EXPECTED_WORKFLOW_VERSIONS))
def test_render_v3_rejects_each_unsupported_workflow_version_before_build(
    monkeypatch: pytest.MonkeyPatch,
    version_field: str,
) -> None:
    called = False

    def fake_build(body, **_kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(service, "build_and_render_v3", fake_build)
    envelope = versioned_envelope()
    envelope[version_field] = "999.0.0"

    with pytest.raises(HTTPException) as caught:
        service.render_v3_endpoint(envelope)

    assert called is False
    assert caught.value.status_code == 409
    assert caught.value.detail["code"] == "workflow_version_unsupported"
    assert caught.value.detail["field"] == version_field


def test_each_executable_paste_target_declares_the_exact_six_field_handshake() -> None:
    script = """
const artifacts = {
  schema_resolver: require('./docs/resolve-schema-node-v5.js'),
  writer_gate: require('./docs/n8n/writer_gate.js'),
  source_ledger: require('./docs/n8n/source-ledger-node-v3.js'),
  claim_gate: require('./docs/n8n/claim-gate-v3.js'),
};
process.stdout.write(JSON.stringify(Object.fromEntries(
  Object.entries(artifacts).map(([key, artifact]) => [key, {
    frozen: Object.isFrozen(artifact.WORKFLOW_VERSIONS_V3),
    versions: artifact.WORKFLOW_VERSIONS_V3,
  }]),
)));
"""
    completed = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    declarations = json.loads(completed.stdout)
    assert set(declarations) == {
        "schema_resolver",
        "writer_gate",
        "source_ledger",
        "claim_gate",
    }
    for artifact, declaration in declarations.items():
        assert declaration["frozen"] is True, artifact
        assert declaration["versions"] == EXPECTED_WORKFLOW_VERSIONS, artifact


def test_writer_prompt_declares_the_exact_six_field_handshake() -> None:
    text = (ROOT / "docs/writer-prompt-v5.md").read_text(encoding="utf-8")

    for field, version in EXPECTED_WORKFLOW_VERSIONS.items():
        assert text.count(f"{field} = {version}") == 1


def test_deployment_checklist_names_all_five_authoritative_nodes() -> None:
    text = (N8N_ROOT / "deployment-checklist-v3.md").read_text(encoding="utf-8")

    for node_name in (
        "Section Writer v5",
        "Resolve Schema and Build Prompts v5",
        "Writer Gate v3",
        "Source Ledger v3",
        "Claim Gate v3",
    ):
        assert node_name in text
