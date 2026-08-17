"""Offline verification for the versioned n8n workflow artifact contract."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


_SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
_REQUIRED_ARTIFACT_FIELDS = {
    "artifact_id",
    "semantic_version",
    "repository_path",
    "sha256",
    "expected_node_name",
    "input_schema_version",
    "output_schema_version",
    "envelope_version_field",
}
_V3_2_ARTIFACT_IDS = {
    "writer_prompt",
    "schema_resolver",
    "writer_gate",
    "source_ledger",
    "claim_gate",
}


def load_workflow_contract(path: Path) -> dict:
    contract = json.loads(path.read_text(encoding="utf-8"))
    if contract.get("schema_version") != "1.0":
        raise ValueError("unsupported workflow contract schema")
    if not _SEMVER.fullmatch(str(contract.get("contract_version", ""))):
        raise ValueError("workflow contract version must use semantic versioning")
    artifacts = contract.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise ValueError("workflow contract requires artifacts")
    artifact_ids: list[str] = []
    paths: list[str] = []
    envelope_version_fields: list[str] = []
    for artifact in artifacts:
        if set(artifact) != _REQUIRED_ARTIFACT_FIELDS:
            raise ValueError("workflow artifact fields do not match the schema")
        if not _SEMVER.fullmatch(artifact["semantic_version"]):
            raise ValueError("artifact version must use semantic versioning")
        if not re.fullmatch(r"[0-9a-f]{64}", artifact["sha256"]):
            raise ValueError("artifact hash must be SHA-256")
        artifact_ids.append(artifact["artifact_id"])
        paths.append(artifact["repository_path"])
        envelope_version_fields.append(artifact["envelope_version_field"])
    if len(artifact_ids) != len(set(artifact_ids)):
        raise ValueError("workflow artifact IDs must be unique")
    if len(paths) != len(set(paths)):
        raise ValueError("workflow artifact paths must be unique")
    if len(envelope_version_fields) != len(set(envelope_version_fields)):
        raise ValueError("workflow envelope version fields must be unique")
    if (
        str(contract["contract_version"]).startswith("3.2.")
        and set(artifact_ids) != _V3_2_ARTIFACT_IDS
    ):
        raise ValueError("workflow contract v3.2 requires exactly the five evidence artifacts")
    return contract


def verify_workflow_contract(
    contract: dict,
    repository_root: Path,
    *,
    artifact_ids: tuple[str, ...] | None = None,
) -> dict:
    """Verify declared bytes; explicit selections raise if empty or unknown."""
    selected = None
    if artifact_ids is not None:
        selected = set(artifact_ids)
        if not selected:
            raise ValueError("workflow artifact selection must not be empty")
        declared = {artifact["artifact_id"] for artifact in contract["artifacts"]}
        unknown = sorted(selected - declared)
        if unknown:
            raise ValueError(f"unknown workflow artifact IDs: {', '.join(unknown)}")
    mismatches: list[dict[str, str]] = []
    verified: list[dict[str, str]] = []
    for artifact in contract["artifacts"]:
        if selected is not None and artifact["artifact_id"] not in selected:
            continue
        path = repository_root / artifact["repository_path"]
        if not path.is_file():
            mismatches.append(
                {
                    "artifact_id": artifact["artifact_id"],
                    "code": "artifact_missing",
                    "path": str(path),
                }
            )
            continue
        actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual_hash != artifact["sha256"]:
            mismatches.append(
                {
                    "artifact_id": artifact["artifact_id"],
                    "code": "artifact_hash_mismatch",
                    "expected_sha256": artifact["sha256"],
                    "actual_sha256": actual_hash,
                }
            )
        else:
            verified.append(
                {
                    "artifact_id": artifact["artifact_id"],
                    "sha256": actual_hash,
                }
            )
    return {
        "accepted": not mismatches,
        "contract_version": contract["contract_version"],
        "verified": verified,
        "mismatches": mismatches,
    }
