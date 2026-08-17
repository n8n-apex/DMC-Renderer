from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from composition_registry.registry import (
    RegistryIntegrityError,
    load_registry,
)
from composition_registry.schema import CompositionRegistry


ROOT = Path(__file__).resolve().parents[3]
REGISTRY_PATH = ROOT / "research" / "composition_registry" / "families" / "dmc-v1.json"
MANIFEST_PATH = ROOT / "research" / "composition_registry" / "golden" / "manifest.json"
ATLAS_PATH = ROOT / "research" / "reference-atlas" / "reference-atlas.json"


def test_registry_contains_ten_complete_reference_grounded_families() -> None:
    registry = load_registry(
        REGISTRY_PATH,
        atlas_path=ATLAS_PATH,
        manifest_path=MANIFEST_PATH,
    )
    atlas_face_ids = {
        face["id"] for face in json.loads(ATLAS_PATH.read_text())["faces"]
    }

    assert len(registry.families) == 10
    for family in registry.families:
        assert family.semantic_promise
        assert family.supported_roles
        assert family.dominant_mechanisms
        assert family.regions
        assert family.supported_asset_classes
        assert family.typography_bounds
        assert family.known_failures
        assert family.atlas_face_ids
        assert set(family.atlas_face_ids) <= atlas_face_ids
        for region in family.regions:
            assert region.width_mm > 0
            assert region.height_mm > 0
            assert {capacity.language for capacity in region.capacities} == {"de", "en"}
            for capacity in region.capacities:
                assert capacity.min_words <= capacity.target_words <= capacity.max_words
                assert capacity.min_font_pt <= capacity.max_font_pt


def test_registry_rejects_duplicate_family_ids() -> None:
    raw = json.loads(REGISTRY_PATH.read_text())
    raw["families"].append(raw["families"][0])

    with pytest.raises(ValidationError, match="family ids must be unique"):
        CompositionRegistry.model_validate(raw)


def test_registry_rejects_unversioned_content_change(tmp_path: Path) -> None:
    raw = json.loads(REGISTRY_PATH.read_text())
    raw["families"][0]["semantic_promise"] = "Changed without a version bump"
    changed_registry = tmp_path / "dmc-v1.json"
    changed_registry.write_text(json.dumps(raw))
    unchanged_manifest = tmp_path / "manifest.json"
    unchanged_manifest.write_text(MANIFEST_PATH.read_text())

    with pytest.raises(RegistryIntegrityError, match="content hash"):
        load_registry(
            changed_registry,
            atlas_path=ATLAS_PATH,
            manifest_path=unchanged_manifest,
        )


def test_all_reference_ids_must_exist_in_atlas(tmp_path: Path) -> None:
    raw = json.loads(REGISTRY_PATH.read_text())
    raw["families"][0]["atlas_face_ids"] = ["missing-face"]
    changed_registry = tmp_path / "dmc-v1.json"
    changed_registry.write_text(json.dumps(raw))

    with pytest.raises(RegistryIntegrityError, match="unknown atlas face"):
        load_registry(changed_registry, atlas_path=ATLAS_PATH)
