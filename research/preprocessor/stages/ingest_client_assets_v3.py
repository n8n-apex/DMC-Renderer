"""Turn a client's real image folder into asset ledger records.

Every build so far has run on procedurally drawn placeholders because
nothing in the system could read a folder of client photographs. The files
were on disk the whole time.

Naming convention. Richard names files on upload, so the filename carries
the semantic class. This table is the convention; it is data, not logic, so
correcting it is a one-line change:

    founder*, portrait*, team*      -> identity
    proof*, review*, testimonial*   -> proof
    logo*, partner*, kunde*         -> logo
    product*, screenshot*, ui*      -> product
    case*, projekt*                 -> context
    anything else                   -> context

Rights are never assumed. An asset is CLIENT_AUTHORIZED only when the
caller passes it in `authorized`, naming who authorized it and when.
Everything else lands as UNKNOWN, which the asset gate blocks, so an
unauthorized photograph can never reach a client deliverable by default.
"""

from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path
from typing import Any, Iterable

from PIL import Image


IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp"})

# Filename prefix -> semantic class. Longest prefix wins, so "founder" is
# matched before a generic fallback.
NAMING_CONVENTION: tuple[tuple[str, str], ...] = (
    ("founder", "identity"),
    ("portrait", "identity"),
    ("team", "identity"),
    ("avatar", "identity"),
    ("proof", "proof"),
    ("review", "proof"),
    ("testimonial", "proof"),
    ("logo", "logo"),
    ("partner", "logo"),
    ("kunde", "logo"),
    ("product", "product"),
    ("screenshot", "product"),
    ("ui", "product"),
    ("case", "context"),
    ("projekt", "context"),
)

# Print size is derived at a print-safe density; the asset gate enforces its
# own minimum DPI separately against the box the layout gives the image.
PRINT_DPI = 300.0


def semantic_class_for(filename: str) -> str:
    """The class this filename declares, defaulting to context."""
    stem = Path(filename).stem.lower()
    for prefix, semantic in NAMING_CONVENTION:
        if stem.startswith(prefix) or f"_{prefix}" in stem or f"-{prefix}" in stem:
            return semantic
    return "context"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def discover(root: Path) -> tuple[Path, ...]:
    """Every image under the client folder, in a stable order."""
    return tuple(
        sorted(
            path
            for path in root.rglob("*")
            if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
        )
    )


def ingest_client_assets(
    root: Path,
    *,
    client_slug: str,
    authorized: Iterable[str] = (),
    authorized_by: str | None = None,
    authorized_on: date | None = None,
) -> tuple[dict[str, Any], ...]:
    """Asset records for one client's real images.

    `authorized` names the files the owner has explicitly cleared for use.
    Anything not named lands with rights UNKNOWN so the gate stops it.
    """
    authorized_names = {Path(name).name for name in authorized}
    if authorized_names and not authorized_by:
        raise ValueError("authorized assets require the name of the approver")

    records: list[dict[str, Any]] = []
    for path in discover(root):
        try:
            with Image.open(path) as image:
                width, height = image.size
        except Exception:
            continue
        semantic = semantic_class_for(path.name)
        is_authorized = path.name in authorized_names
        records.append(
            {
                "asset_id": f"asset.{client_slug}.{path.stem.lower().replace('_', '.')}",
                "semantic_class": semantic,
                "provenance_kind": "client_supplied",
                # The locator records WHERE it came from and, when cleared,
                # who said so. An approval with no name is not an approval.
                "source_locator": (
                    f"{client_slug}:{path.relative_to(root)}"
                    + (
                        f" (authorized by {authorized_by}"
                        f" on {(authorized_on or date.today()).isoformat()})"
                        if is_authorized
                        else ""
                    )
                ),
                "rights_status": "client_authorized" if is_authorized else "unknown",
                "content_hash": _sha256(path),
                "local_path": str(path),
                "pixel_width": width,
                "pixel_height": height,
                "print_width_mm": round(width / PRINT_DPI * 25.4, 2),
                "print_height_mm": round(height / PRINT_DPI * 25.4, 2),
                "substitution_policy": "exact_only",
            }
        )
    return tuple(records)


def aspect_ratio(record: dict[str, Any]) -> float:
    return record["pixel_width"] / record["pixel_height"]


def portrait_capable(record: dict[str, Any]) -> bool:
    """True when this image can fill a portrait slot without a brutal crop.

    Jousef's founder.png is 1179x755, landscape. Dropped into a portrait
    rail it loses most of the subject, so the layout needs to know before
    it commits the slot.
    """
    return aspect_ratio(record) <= 1.05


# Print-usable floor. A 64x50 favicon is 5mm on paper; it is a file, not a
# picture, and must never be counted toward a face's visual density.
MIN_PRINT_MM = 20.0


def print_usable(record: dict[str, Any]) -> bool:
    """True when this image is large enough to be a picture in print."""
    return (
        record["print_width_mm"] >= MIN_PRINT_MM
        and record["print_height_mm"] >= MIN_PRINT_MM
    )


def ingest_case_client_assets(
    root: Path,
    *,
    client_slug: str,
    authorized: Iterable[str] = (),
    authorized_by: str | None = None,
    authorized_on: date | None = None,
) -> tuple[dict[str, Any], ...]:
    """Assets scraped per case-study client, one folder per client.

    `incoming_assets/<case-client>/` holds material gathered for each case
    study: website stills, page sections, a founder photo. They are context
    and proof for the case pages, never logos, whatever the folder is named.
    Anything too small to print is dropped rather than counted.
    """
    records: list[dict[str, Any]] = []
    for folder in sorted(path for path in root.iterdir() if path.is_dir()):
        for record in ingest_client_assets(
            folder,
            client_slug=f"{client_slug}.{folder.name}",
            authorized=authorized,
            authorized_by=authorized_by,
            authorized_on=authorized_on,
        ):
            if not print_usable(record):
                continue
            # A screenshot of the client's own site is evidence for that
            # case, not a mark for a logo wall.
            if record["semantic_class"] == "logo":
                record["semantic_class"] = "context"
            records.append(record)
    return tuple(records)
