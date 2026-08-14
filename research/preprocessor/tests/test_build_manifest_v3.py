from __future__ import annotations

import pytest
from pydantic import ValidationError

from contracts_v3.build_manifest import BuildManifestV3, BuildVersions


WORKFLOW_VERSIONS = {
    "workflow_contract": "3.2.1",
    "writer_prompt": "5.1.1",
    "schema_resolver": "5.2.1",
    "writer_gate": "3.1.1",
    "source_ledger": "3.2.1",
    "claim_gate": "3.2.1",
}


def non_workflow_versions() -> BuildVersions:
    return BuildVersions(
        product_profile="test-profile",
        workflow_authority="non_workflow",
    )


def test_workflow_authority_mode_is_required_and_typed() -> None:
    with pytest.raises(ValidationError):
        BuildVersions(product_profile="test-profile")
    with pytest.raises(ValidationError):
        BuildVersions(product_profile="test-profile", workflow_authority="implicit")


def test_verified_workflow_requires_the_complete_semver_authority_set() -> None:
    verified = BuildVersions(
        product_profile="test-profile",
        workflow_authority="verified",
        **WORKFLOW_VERSIONS,
    )
    assert verified.workflow_authority == "verified"

    for missing in WORKFLOW_VERSIONS:
        incomplete = {key: value for key, value in WORKFLOW_VERSIONS.items() if key != missing}
        with pytest.raises(ValidationError, match="complete workflow authority"):
            BuildVersions(
                product_profile="test-profile",
                workflow_authority="verified",
                **incomplete,
            )


def test_non_workflow_mode_rejects_workflow_authority_values() -> None:
    with pytest.raises(ValidationError, match="non_workflow"):
        BuildVersions(
            product_profile="test-profile",
            workflow_authority="non_workflow",
            workflow_contract="3.2.1",
        )


@pytest.mark.parametrize("field", tuple(WORKFLOW_VERSIONS))
@pytest.mark.parametrize("value", ("", "3.2", "v3.2.1", "3.2.1-dev"))
def test_workflow_versions_require_strict_nonempty_semver(field: str, value: str) -> None:
    values = {**WORKFLOW_VERSIONS, field: value}
    with pytest.raises(ValidationError):
        BuildVersions(
            product_profile="test-profile",
            workflow_authority="verified",
            **values,
        )


def test_manifest_requires_nonempty_lowercase_sha256_artifact_hashes() -> None:
    invalid_hash_sets = (
        {},
        {"source_ledger": ""},
        {"source_ledger": "A" * 64},
        {"source_ledger": "a" * 63},
    )
    for hashes in invalid_hash_sets:
        with pytest.raises(ValidationError):
            BuildManifestV3(versions=non_workflow_versions(), artifact_hashes=hashes)

    manifest = BuildManifestV3(
        versions=non_workflow_versions(),
        artifact_hashes={"source_ledger": "a" * 64},
    )
    assert manifest.artifact_hashes["source_ledger"] == "a" * 64

