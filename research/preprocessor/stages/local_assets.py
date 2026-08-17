"""Local Client Assets folder lister — the local stand-in for the Drive
listing (PRD §7.4). Returns image filenames under client_assets/<client>/,
sorted + deterministic, junk/non-image filtered. Feeds resolve_slots()
exactly like a Drive listing would. Brand-agnostic.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Union

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}

_DIGIT_RUN = re.compile(r"\d+")


def _natural_key(name: str) -> tuple:
    """Natural sort key on the first digit run so product-2 precedes
    product-10; names without digits fall back to plain name order."""
    m = _DIGIT_RUN.search(name)
    if not m:
        return (name, -1, "")
    return (name[:m.start()], int(m.group(0)), name[m.end():])


def client_assets_dir(client_slug: str, *, base: Union[str, Path]) -> Path:
    return Path(base) / client_slug


def list_client_assets(folder: Union[str, Path]) -> list[str]:
    """Image filenames directly under `folder`, sorted; [] if absent."""
    p = Path(folder)
    if not p.is_dir():
        return []
    return sorted(
        (f.name for f in p.iterdir()
         if f.is_file() and f.suffix.lower() in _IMAGE_EXTS),
        key=_natural_key,
    )
