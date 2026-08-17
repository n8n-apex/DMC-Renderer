"""Google Drive asset listing + md5-cached download (PRD §7.4).

DESIGNED here; the live google-api-python-client adapter (GoogleDriveLister)
is added when the user provides OAuth creds — it's a thin call to
files().list()/files().get_media(). The pure pieces below — parsing a
files.list response, feeding the slot resolver, and the md5 cache — are
testable now with fakes, and a provided local file list substitutes for
Drive via the same resolver. Brand-agnostic; no client literal.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Protocol


@dataclass(frozen=True)
class DriveFile:
    id: str
    name: str
    md5: Optional[str] = None


def parse_drive_listing(files_list_response: dict) -> list[DriveFile]:
    """Parse a Drive files.list() response -> DriveFile[], sorted by name
    (deterministic). Entries missing id or name are skipped defensively."""
    out: list[DriveFile] = []
    for f in (files_list_response or {}).get("files", []):
        fid, name = f.get("id"), f.get("name")
        if not fid or not name:
            continue
        out.append(DriveFile(id=fid, name=name, md5=f.get("md5Checksum")))
    return sorted(out, key=lambda d: d.name)


def drive_filenames(listing: list[DriveFile]) -> list[str]:
    """The filenames to hand to resolve_slots()."""
    return [f.name for f in listing]


def _ext(name: str) -> str:
    i = name.rfind(".")
    return name[i:] if i != -1 else ""


def md5_cache_dest(cache_dir: Path, file: DriveFile) -> Path:
    """The cache path a file is stored at, keyed by id + md5 + extension."""
    return Path(cache_dir) / f"{file.id}_{file.md5}{_ext(file.name)}"


def md5_cached_path(cache_dir: Optional[Path], file: DriveFile) -> Optional[Path]:
    """Return a cached copy's path when (id, md5) already exists -> skip the
    re-download. None when caching is off or the file carries no md5."""
    if cache_dir is None or not file.md5:
        return None
    p = md5_cache_dest(cache_dir, file)
    return p if p.exists() else None


class DriveLister(Protocol):
    """Interface the pipeline depends on. The live GoogleDriveLister
    implementation (OAuth2 + files().list) is added when creds arrive; tests
    use a fake. Keeps the pipeline decoupled from the google SDK."""

    def list_files(self, folder_id: str) -> list[DriveFile]: ...
