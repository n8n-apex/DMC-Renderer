"""Tests for storage.py — StorageBackend interface + LocalStorage + cleanup.

The author's data-handling rule: download to a SCRATCH dir, keep ONLY the
accepted assets, DELETE the raw downloads (no hoarding GBs of video/frames).
Accepted assets are persisted per-founder under a slot-keyed filename; scratch
is wiped afterwards. A SupabaseStorage backend (bucket upload + weekly cleanup
cron) implements the same Protocol later — not built here.

All filesystem only, tmp dirs, no network.
"""
from __future__ import annotations

import os

from stages.scrape_founder_assets.models import Candidate
from stages.scrape_founder_assets.storage import AcceptedAsset, LocalStorage


def _candidate(path, kind="post"):
    """A minimal Candidate pointing at a real tmp file."""
    return Candidate(
        source="youtube", kind=kind, local_path=str(path), width=10, height=10
    )


def _write(path, data=b"x"):
    """Write a dummy raw file and return its path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return str(path)


def test_commit_writes_slot_keyed_namespaced(tmp_path):
    """Accepted assets land under client-assets/<founder>/<slot>__<n><ext>."""
    src_dir = tmp_path / "scratch"
    a = _write(src_dir / "a.png", b"founder-bytes")
    b = _write(src_dir / "b.png", b"cover-bytes")
    accepted = [
        AcceptedAsset(slot="founder", candidate=_candidate(a)),
        AcceptedAsset(slot="cover_hero", candidate=_candidate(b)),
    ]
    dest_root = tmp_path / "dest"

    out = LocalStorage(str(dest_root)).commit(accepted, founder_id="acme123")

    base = dest_root / "client-assets" / "acme123"
    founder_path = base / "founder__0.png"
    cover_path = base / "cover_hero__0.png"
    assert founder_path.exists()
    assert cover_path.exists()
    # contents copied faithfully
    assert founder_path.read_bytes() == b"founder-bytes"
    assert cover_path.read_bytes() == b"cover-bytes"
    # final_path set on returned assets, pointing at the namespaced files
    paths = {a.slot: a.final_path for a in out}
    assert paths["founder"] == str(founder_path)
    assert paths["cover_hero"] == str(cover_path)
    # founder namespace isolates: a different founder writes elsewhere
    other = LocalStorage(str(dest_root)).commit(
        [AcceptedAsset(slot="founder", candidate=_candidate(a))],
        founder_id="other999",
    )
    assert "other999" in other[0].final_path
    assert "acme123" not in other[0].final_path


def test_commit_multiple_per_slot_indexed(tmp_path):
    """Two assets for the same slot get distinct indices (no overwrite)."""
    src_dir = tmp_path / "scratch"
    a = _write(src_dir / "a.png", b"one")
    b = _write(src_dir / "b.png", b"two")
    accepted = [
        AcceptedAsset(slot="team", candidate=_candidate(a)),
        AcceptedAsset(slot="team", candidate=_candidate(b)),
    ]
    dest_root = tmp_path / "dest"

    out = LocalStorage(str(dest_root)).commit(accepted, founder_id="acme")

    finals = [x.final_path for x in out]
    # two distinct files, neither overwriting the other
    assert len(set(finals)) == 2
    base = dest_root / "client-assets" / "acme"
    assert (base / "team__0.png").exists()
    assert (base / "team__1.png").exists()
    assert (base / "team__0.png").read_bytes() == b"one"
    assert (base / "team__1.png").read_bytes() == b"two"


def test_cleanup_deletes_scratch(tmp_path):
    """cleanup_scratch removes the tree and is idempotent (no raise if gone)."""
    scratch = tmp_path / "scratch"
    _write(scratch / "raw_video.mp4", b"rawrawraw")
    _write(scratch / "frames" / "f0.png", b"frame")
    assert scratch.exists()

    storage = LocalStorage(str(tmp_path / "dest"))
    freed = storage.cleanup_scratch(str(scratch))

    assert not scratch.exists()
    assert isinstance(freed, int)
    assert freed >= 0
    # calling again on an already-gone dir does NOT raise
    again = storage.cleanup_scratch(str(scratch))
    assert isinstance(again, int)


def test_founder_id_sanitized(tmp_path):
    """A traversal-y founder_id stays safely inside dest_root."""
    src_dir = tmp_path / "scratch"
    a = _write(src_dir / "a.png", b"safe")
    dest_root = tmp_path / "dest"

    out = LocalStorage(str(dest_root)).commit(
        [AcceptedAsset(slot="founder", candidate=_candidate(a))],
        founder_id="../evil",
    )

    final = out[0].final_path
    client_root = (dest_root / "client-assets").resolve()
    # the written file must live under dest_root/client-assets, not escape it
    assert os.path.commonpath([client_root, os.path.realpath(final)]) == str(
        client_root
    )
    assert os.path.exists(final)
    # nothing leaked to the parent of dest_root
    assert not (tmp_path / "evil").exists()
