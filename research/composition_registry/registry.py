from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from .schema import CompositionRegistry


class RegistryIntegrityError(ValueError):
    pass


def stable_json(value: Any) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def stable_hash(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def load_registry(
    registry_path: Path,
    *,
    atlas_path: Path,
    manifest_path: Path | None = None,
    production: bool = False,
) -> CompositionRegistry:
    raw = json.loads(registry_path.read_text())
    registry = CompositionRegistry.model_validate(raw)

    atlas = json.loads(atlas_path.read_text())
    known_face_ids = {face["id"] for face in atlas["faces"]}
    for family in registry.families:
        unknown = set(family.atlas_face_ids) - known_face_ids
        if unknown:
            raise RegistryIntegrityError(
                f"{family.family_id} has unknown atlas face: {', '.join(sorted(unknown))}"
            )
        if production and family.calibration_status != "promoted":
            raise RegistryIntegrityError(
                f"{family.family_id}@{family.version} is not promoted"
            )

    if manifest_path is not None:
        manifest = json.loads(manifest_path.read_text())
        if manifest.get("registry_id") != registry.registry_id:
            raise RegistryIntegrityError("manifest registry id does not match")
        if manifest.get("registry_version") != registry.version:
            raise RegistryIntegrityError("manifest registry version does not match")
        if manifest.get("registry_content_hash") != stable_hash(raw):
            raise RegistryIntegrityError("registry content hash does not match golden manifest")
        family_hashes = manifest.get("family_hashes") or {}
        for family_raw in raw["families"]:
            key = f"{family_raw['family_id']}@{family_raw['version']}"
            if family_hashes.get(key) != stable_hash(family_raw):
                raise RegistryIntegrityError(f"family content hash mismatch for {key}")
    return registry
