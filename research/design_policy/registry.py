"""Load design policies and prove source, atlas, and family bindings."""

from __future__ import annotations

import json
from pathlib import Path

from schema import DesignPolicyRegistry


class DesignPolicyIntegrityError(ValueError):
    pass


def load_design_policy_registry(
    policy_path: Path,
    *,
    sources_path: Path,
    atlas_path: Path,
    production: bool = False,
) -> DesignPolicyRegistry:
    registry = DesignPolicyRegistry.model_validate(
        json.loads(policy_path.read_text(encoding="utf-8"))
    )
    sources = json.loads(sources_path.read_text(encoding="utf-8"))["sources"]
    paths_by_source = {
        source["source_id"]: {file["upstream_path"] for file in source["files"]}
        for source in sources
    }
    atlas_ids = {
        face["id"]
        for face in json.loads(atlas_path.read_text(encoding="utf-8"))["faces"]
    }
    for policy in registry.policies:
        if production and policy.promotion_state != "promoted":
            raise DesignPolicyIntegrityError(
                f"{policy.policy_id}@{policy.version} is not promoted"
            )
        unknown_faces = set(policy.atlas_face_ids) - atlas_ids
        if unknown_faces:
            raise DesignPolicyIntegrityError(
                f"{policy.policy_id} has unknown atlas faces: {sorted(unknown_faces)}"
            )
        for reference in policy.source_references:
            if reference.source_id not in paths_by_source:
                raise DesignPolicyIntegrityError(
                    f"{policy.policy_id} has unknown source {reference.source_id}"
                )
            if reference.upstream_path not in paths_by_source[reference.source_id]:
                raise DesignPolicyIntegrityError(
                    f"{policy.policy_id} has unsnapshotted path {reference.upstream_path}"
                )
    return registry


def assert_composition_policy_bindings(composition_registry, policy_registry) -> None:
    validated = set(policy_registry.validated_policy_ids)
    for family in composition_registry.families:
        unknown = set(family.design_policy_ids) - validated
        if unknown:
            raise DesignPolicyIntegrityError(
                f"{family.family_id} binds non-validated policies: {sorted(unknown)}"
            )
