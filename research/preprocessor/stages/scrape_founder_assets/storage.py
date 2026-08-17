"""Persist accepted founder assets + wipe the download scratch.

Data-handling rule driving this module: the scraper downloads candidates into
a SCRATCH dir (raw video, extracted frames, rejected images — potentially GBs).
We keep ONLY the assets that were ACCEPTED for a slot and DELETE the scratch.
No hoarding.

Two operations behind a swappable backend:

1. ``commit`` — persist each accepted asset under a per-founder namespace with
   a slot-keyed filename, and stamp ``final_path`` onto it.
2. ``cleanup_scratch`` — remove the scratch tree (raw downloads + rejected
   frames). Idempotent and never raises.

``LocalStorage`` writes to ``dest_root/client-assets/<founder_id>/`` on the
local filesystem (v1). A future ``SupabaseStorage`` implements the SAME
``StorageBackend`` Protocol: ``commit`` uploads each accepted asset to a
Supabase storage bucket under the same per-founder/slot namespace, and a
weekly-cleanup CRON clears the scratch area (a server-side counterpart of
``cleanup_scratch``). That backend is DELIBERATELY NOT implemented here —
v1 is local filesystem only, no network.

Brand-agnostic: ``founder_id`` is opaque and SANITIZED (no path traversal);
no client literals anywhere.
"""
from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass
from typing import List, Optional, Protocol

from .models import Candidate

# Where accepted assets live under ``dest_root``. One sub-namespace per founder.
CLIENT_ASSETS_DIRNAME: str = "client-assets"


@dataclass
class AcceptedAsset:
    """An asset chosen for a founder slot, ready to be persisted.

    ``final_path`` is ``None`` until a backend's ``commit`` persists it and
    stamps the resting location (local path now; bucket key later).
    """

    slot: str  # e.g. "cover_hero", "founder", "about_portrait", "team", "scene"
    candidate: Candidate
    final_path: Optional[str] = None


class StorageBackend(Protocol):
    """A swappable place to keep accepted assets + drop the scratch.

    Implementations persist accepted assets under a per-founder namespace with
    a slot-keyed filename, and wipe the download scratch when asked.

    ``LocalStorage`` (below) is the v1 filesystem backend. A future
    ``SupabaseStorage`` implements this same Protocol — ``commit`` uploads to a
    Supabase bucket and a weekly-cleanup cron clears scratch — and is NOT built
    here.
    """

    def commit(
        self, accepted: List[AcceptedAsset], founder_id: str
    ) -> List[AcceptedAsset]:
        """Persist each accepted asset under a per-founder, slot-keyed name.

        Returns the same assets with ``final_path`` set to their resting place.
        """
        ...

    def cleanup_scratch(self, scratch_dir: str) -> int:
        """Delete the scratch tree (raw downloads + rejected frames).

        Returns bytes/count freed. Safe to call when already gone; never raises.
        """
        ...


def _sanitize_founder_id(founder_id: str) -> str:
    """Reduce ``founder_id`` to a single safe path segment (no traversal).

    Strips directory separators and ``..`` so a value like ``"../evil"`` cannot
    escape ``dest_root``. Keeps only ``[A-Za-z0-9._-]``; falls back to
    ``"unknown"`` if nothing survives.
    """
    # Take the basename to drop any path components, then whitelist chars.
    base = os.path.basename(str(founder_id).strip().replace("\\", "/"))
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", base)
    cleaned = cleaned.strip(".")  # no leading/trailing dots -> kills "..", "."
    return cleaned or "unknown"


def _ext_for(candidate: Candidate) -> str:
    """File extension to use for the persisted copy (default ``.png``)."""
    _root, ext = os.path.splitext(candidate.local_path)
    return ext if ext else ".png"


class LocalStorage:
    """v1 backend: copy accepted assets to the local filesystem.

    Layout: ``dest_root/client-assets/<founder_id>/<slot>__<n><ext>``. The
    ``<n>`` index disambiguates multiple assets sharing one slot so none
    overwrite. ``founder_id`` is sanitized to one safe segment.
    """

    def __init__(self, dest_root: str) -> None:
        self.dest_root = dest_root

    def _founder_dir(self, founder_id: str) -> str:
        safe = _sanitize_founder_id(founder_id)
        return os.path.join(self.dest_root, CLIENT_ASSETS_DIRNAME, safe)

    def commit(
        self, accepted: List[AcceptedAsset], founder_id: str
    ) -> List[AcceptedAsset]:
        founder_dir = self._founder_dir(founder_id)
        os.makedirs(founder_dir, exist_ok=True)

        per_slot_index: dict[str, int] = {}
        for asset in accepted:
            idx = per_slot_index.get(asset.slot, 0)
            per_slot_index[asset.slot] = idx + 1
            ext = _ext_for(asset.candidate)
            filename = f"{asset.slot}__{idx}{ext}"
            dest = os.path.join(founder_dir, filename)
            shutil.copyfile(asset.candidate.local_path, dest)
            asset.final_path = dest
        return accepted

    def cleanup_scratch(self, scratch_dir: str) -> int:
        """Wipe the scratch tree; return bytes freed. Never raises.

        Sizes the tree first (best-effort) so callers can log how much raw
        download was reclaimed, then removes it with ``ignore_errors`` so a
        missing/already-gone dir is a no-op.
        """
        freed = 0
        for root, _dirs, files in os.walk(scratch_dir):
            for name in files:
                try:
                    freed += os.path.getsize(os.path.join(root, name))
                except OSError:
                    pass
        shutil.rmtree(scratch_dir, ignore_errors=True)
        return freed
