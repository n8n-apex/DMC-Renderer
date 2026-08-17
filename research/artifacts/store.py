"""Pluggable, atomic, immutable artifact store for retained v3 builds.

The filesystem implementation stages every build into a hidden temp directory
inside the store root and promotes it with one atomic rename. A failed persist
can never leave a partial build visible, and a promoted build can never be
overwritten with different bytes.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from typing import Protocol

from .schema import BuildRecordV3


FileSource = bytes | Path
FileSpec = tuple[str, FileSource]


class ArtifactStore(Protocol):
    def persist(self, record: BuildRecordV3, *, files: dict[str, FileSpec]) -> dict:
        """Persist one immutable build; return its manifest reference."""


def _read_source(source: FileSource) -> bytes:
    if isinstance(source, (bytes, bytearray)):
        return bytes(source)
    return Path(source).read_bytes()


class FilesystemArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def persist(self, record: BuildRecordV3, *, files: dict[str, FileSpec]) -> dict:
        self.root.mkdir(parents=True, exist_ok=True)
        build_dir = self.root / record.build_id

        staged: dict[str, dict[str, str]] = {}
        payloads: dict[str, bytes] = {}
        for kind, (name, source) in files.items():
            data = _read_source(source)
            payloads[name] = data
            staged[kind] = {
                "name": name,
                "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": str(len(data)),
            }

        manifest_body = {
            "schema_version": "1.0",
            "record": record.model_dump(mode="json"),
            "files": staged,
        }
        manifest_text = (
            json.dumps(manifest_body, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        )
        manifest_sha256 = hashlib.sha256(manifest_text.encode("utf-8")).hexdigest()

        if build_dir.exists():
            existing_path = build_dir / "manifest.json"
            existing = existing_path.read_bytes() if existing_path.is_file() else b""
            if hashlib.sha256(existing).hexdigest() == manifest_sha256:
                return {
                    "path": str(existing_path),
                    "manifest_sha256": manifest_sha256,
                    "build_id": record.build_id,
                }
            raise FileExistsError(
                f"artifact build {record.build_id} is immutable and already exists "
                "with different content"
            )

        staging_dir = Path(
            tempfile.mkdtemp(prefix=".tmp-", dir=self.root)
        )
        try:
            for name, data in payloads.items():
                (staging_dir / name).write_bytes(data)
            (staging_dir / "manifest.json").write_text(manifest_text, encoding="utf-8")
            staging_dir.rename(build_dir)
        except Exception:
            shutil.rmtree(staging_dir, ignore_errors=True)
            raise

        return {
            "path": str(build_dir / "manifest.json"),
            "manifest_sha256": manifest_sha256,
            "build_id": record.build_id,
        }
