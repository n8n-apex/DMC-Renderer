"""G18 (downloaded scenes paint), G20 (page-count snap surfaced), G23 (single
layout-variant source)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / ".." / "research" / "v7-renderer"))
sys.path.insert(0, str(ROOT / ".." / "research" / "preprocessor"))


class _FakeCtx:
    def __init__(self):
        self.paths = {}

    def resolve_asset(self, rel):
        from pathlib import Path

        if rel in self.paths:
            return Path(self.paths[rel])
        return None


def _uri(path: str) -> str:
    from pathlib import Path

    return Path(path).as_uri()


def test_downloaded_scene_paints_on_treated_page() -> None:
    """G18: a client-supplied (downloaded) scene must resolve, not only the
    generated fal art."""
    from treatment_engine import _scene_uri

    ctx = _FakeCtx()
    ctx.paths["assets/scene.png"] = "/tmp/scene.png"
    page = {"assets": [
        {"status": "downloaded", "image_type": "scene", "path": "assets/scene.png"},
    ]}
    uri = _scene_uri(page, ctx)
    assert uri == _uri("/tmp/scene.png")


def test_generated_scene_still_paints() -> None:
    from treatment_engine import _scene_uri

    ctx = _FakeCtx()
    ctx.paths["assets/scene.png"] = "/tmp/scene.png"
    page = {"assets": [
        {"status": "generated", "image_type": "scene", "path": "assets/scene.png"},
    ]}
    assert _scene_uri(page, ctx) == _uri("/tmp/scene.png")


def test_non_scene_asset_ignored() -> None:
    from treatment_engine import _scene_uri

    ctx = _FakeCtx()
    page = {"assets": [
        {"status": "downloaded", "image_type": "portrait", "path": "assets/p.png"},
    ]}
    assert _scene_uri(page, ctx) is None


def test_st07b_fill_default_lives_in_plan_layout() -> None:
    """G23: plan_layout is the single source of the ST-07B fill default; an
    explicit non-fill variant must win over it."""
    from stages.plan_layout import _resolve_layout_variant

    assert _resolve_layout_variant("ST-07B", None) == "fill"
    assert _resolve_layout_variant("ST-07B", "standard") == "standard"
    assert _resolve_layout_variant("ST-01", None) is None
