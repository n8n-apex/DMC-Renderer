"""G3: social routing must run on the live path, not only the fixture."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT / "research" / "preprocessor", ROOT / "dmc-renderer"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from models_social import AssetManifest  # noqa: E402


def test_persisted_manifest_is_loaded_from_client_ig_dir(tmp_path: Path) -> None:
    """A classified asset_manifest.json persisted in the client's ig/ dir must
    load into an AssetManifest with its handle and assets intact."""
    manifest_data = {
        "handle": "jousefmrd",
        "assets": [
            {
                "path": "jousefmrd_avatar.jpg",
                "role": "founder_portrait",
                "visual_appeal": 3,
            },
            {
                "path": "jousefmrd_DQXmnfZjKnp_2.jpg",
                "role": "content_card",
                "is_testimonial_card": True,
                "brand_text": "Bildungsfabrik",
                "has_overlaid_text": True,
                "visual_appeal": 3,
            },
        ],
    }
    ig = tmp_path / "ig"
    ig.mkdir()
    (ig / "asset_manifest.json").write_text(
        json.dumps(manifest_data), encoding="utf-8"
    )

    from build_live import _build_social_manifest

    manifest = _build_social_manifest(ig)
    assert manifest is not None
    assert isinstance(manifest, AssetManifest)
    assert manifest.handle == "jousefmrd"
    assert len(manifest.assets) == 2
    assert manifest.assets[1].is_testimonial_card is True


def test_no_manifest_and_no_ig_dir_does_not_raise(tmp_path: Path) -> None:
    """A client with no IG pool must degrade gracefully (manifest=None), never
    crash or silently pass a fake manifest."""
    from build_live import _build_social_manifest

    assert _build_social_manifest(tmp_path / "does-not-exist") is None
    empty = tmp_path / "ig"
    empty.mkdir()
    assert _build_social_manifest(empty) is None
