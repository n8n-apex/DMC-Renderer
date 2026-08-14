"""Tests for the local Client Assets folder lister (Drive substitute)."""
from __future__ import annotations
from stages.local_assets import client_assets_dir, list_client_assets


def test_lists_image_files_only(tmp_path) -> None:
    (tmp_path / "founder.png").write_bytes(b"x")
    (tmp_path / "case-study-1.jpg").write_bytes(b"x")
    (tmp_path / "notes.txt").write_text("ignore me")
    (tmp_path / ".DS_Store").write_bytes(b"x")
    names = list_client_assets(tmp_path)
    assert set(names) == {"founder.png", "case-study-1.jpg"}


def test_missing_dir_returns_empty(tmp_path) -> None:
    assert list_client_assets(tmp_path / "nope") == []


def test_client_assets_dir_builds_path(tmp_path) -> None:
    p = client_assets_dir("apex", base=tmp_path)
    assert p == tmp_path / "apex"
