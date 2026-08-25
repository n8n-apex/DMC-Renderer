"""Resolve a client's envelope images into v3 AssetRecords (input-driven).

In production the client's asset folder is a Google Drive folder Richard drops
into Airtable; the envelope's ``images`` carries each file either as a Drive
public URL (``https://drive.google.com/uc?id=...``) or as a path to an
already-fetched local copy. Nothing is stored in this repo.

This stage turns those images into the ``AssetRecord``s the v3 asset ledger
resolves per face, tagging each by a deterministic slot-name rule so the case
faces get their ``identity`` asset and proof/product slots get theirs. It is
the mechanism by which "the client folder" becomes groundable, hashed assets
— never a fabricated figure.

FAIL CLOSED: a slot that resolves to no readable file produces no record.
The case face then carries an honest ``asset_gen`` gap (the loop flags, never
fakes). Brand-agnostic: class rules come from the slot name, not a client.
"""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Any

from PIL import Image

from contracts_v3.asset_ledger import (
    AssetRecord,
    ProvenanceKind,
    RightsStatus,
    SemanticAssetClass,
    SubstitutionPolicy,
)

Slot = str
SemanticClass = SemanticAssetClass

# slot-name -> semantic class. ``case``/``portrait``/``founder``/``author``
# names a person = identity; ``proof``/``testimonial`` = proof; the rest drop
# to a near-empty content class so they never wrongly satisfy identity/proof.
def _slot_semantic(slot: str) -> tuple[SemanticClass, str]:
    s = slot.lower()
    if re.search(r"case|portrait|founder|author|person|kunde|client|team", s):
        return SemanticAssetClass.IDENTITY, "identity"
    if re.search(r"proof|testimonial|logo|credential|review", s):
        return SemanticAssetClass.PROOF, "proof"
    if re.search(r"logo", s):
        return SemanticAssetClass.LOGO, "logo"
    if re.search(r"texture|background|atmos|ground|marble", s):
        return SemanticAssetClass.TEXTURE, "texture"
    if re.search(r"scene|photo|image|visual", s):
        return SemanticAssetClass.CONTEXT, "context"
    return SemanticAssetClass.DECORATION, "decoration"


def _fetch_bytes(ref: str, client_assets_root: Path) -> bytes | None:
    """Resolve an envelope image ref (Drive URL or local path) to bytes.

    FAIL CLOSED: None on any unreadable ref. The caller records an asset_gen
    gap rather than a fabricated record.
    """
    if ref.startswith("http://") or ref.startswith("https://"):
        m = re.search(r"[?&]id=([^&]+)", ref)
        fid = m.group(1) if m else None
        if fid:
            cache = client_assets_root / "drive_cache"
            local = cache / f"{fid}.bin"
            if local.exists():
                return local.read_bytes()
        # No download adapter here (network/creds live on the Drive stage).
        # Without a cached copy we cannot read the file -> fail closed.
        return None
    p = Path(ref)
    if not p.is_absolute():
        p = client_assets_root / p
    try:
        return p.read_bytes()
    except OSError:
        return None


def resolve_client_assets_v3(
    envelope: dict[str, Any],
    *,
    client_assets_root: Path,
    allowed_face_ids_by_slot: dict[Slot, tuple[str, ...]] | None = None,
    print_dpi: float = 150.0,
    rights_status: RightsStatus = RightsStatus.CLIENT_AUTHORIZED,
) -> tuple[AssetRecord, ...]:
    """Pure, deterministic. ``images`` -> AssetRecord tuple.

    ``allowed_face_ids_by_slot`` lets a caller bind one slot (e.g. a specific
    case portrait) to the face it belongs to (never cross-client binding).
    When absent, identity assets stay package-wide (any face may take them),
    which is the safe default for the founder portrait.
    """
    images = envelope.get("images") or {}
    records: list[AssetRecord] = []
    for slot, ref in sorted(images.items()):
        if not isinstance(ref, str) or not ref:
            continue
        semantic, _ = _slot_semantic(slot)
        if semantic in {SemanticAssetClass.DECORATION, SemanticAssetClass.TEXTURE} and not (
            ref.startswith("http") or (client_assets_root / ref).exists()
        ):
            # background/texture never needs a person; skip quietly upstream
            pass
        data = _fetch_bytes(ref, client_assets_root)
        if data is None:
            continue  # fail closed -> honest asset_gen gap downstream
        try:
            im = Image.open(__import__("io").BytesIO(data))
            width, height = im.size
        except Exception:
            continue
        record = AssetRecord(
            asset_id=f"asset.{slot}.{hashlib.sha256(data).hexdigest()[:16]}",
            semantic_class=semantic,
            provenance_kind=ProvenanceKind.CLIENT_PUBLIC
            if ref.startswith("http")
            else ProvenanceKind.CLIENT_SUPPLIED,
            source_locator=ref,
            rights_status=rights_status,
            content_hash=hashlib.sha256(data).hexdigest(),
            local_path=str(client_assets_root / "drive_cache" / f"{slot}.bin")
            if ref.startswith("http")
            else str(Path(ref) if Path(ref).is_absolute() else client_assets_root / ref),
            pixel_width=width,
            pixel_height=height,
            # Fit to a standard A4 half-column at the print DPI.
            print_width_mm=round(width / print_dpi * 25.4, 1),
            print_height_mm=round(height / print_dpi * 25.4, 1),
            allowed_face_ids=tuple(
                dict.fromkeys((allowed_face_ids_by_slot or {}).get(slot, ()))
            ),
            substitution_policy=(
                SubstitutionPolicy.APPROVED_CLASSES
                if semantic is SemanticAssetClass.PROOF
                else SubstitutionPolicy.EXACT_ONLY
            ),
        )
        records.append(record)
    return tuple(records)