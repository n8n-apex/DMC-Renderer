"""Pure, deterministic slot resolver: match a page's SlotSpecs against a
file/Drive listing by naming convention. Emits ResolvedSlot with status
resolved | missing_required | absent (DNA §7.3 — a required miss is a NAMED
error, never a blank box). No I/O; listing normalized once + many-slots
sorted, so a shuffled listing yields identical output. The guarded
rapidfuzz last-resort is deferred to the Drive unit. Brand-agnostic.
"""
from __future__ import annotations

import re
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from stages.slot_registry import SlotSpec, recipe_for

SlotStatus = Literal["resolved", "missing_required", "absent"]


class ResolvedSlot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slot_kind: str
    source: str
    status: SlotStatus
    path: Optional[str] = None
    drive_key: Optional[str] = None
    index: Optional[int] = None
    expected: Optional[str] = None
    warnings: list[str] = Field(default_factory=list)
    slot_id: Optional[str] = None
    image_type: Optional[str] = None
    aspect_ratio: Optional[str] = None


def normalize_name(name: str) -> str:
    """lowercase, drop extension, [_/space]->-, collapse, drop n8n image-<n> affix."""
    s = name.strip().lower()
    s = re.sub(r"\.[a-z0-9]+$", "", s)
    s = re.sub(r"[_\s]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    s = re.sub(r"-image-\d+$", "", s)
    s = re.sub(r"^image-\d+-", "", s)
    return s


def _miss(spec: SlotSpec, *, expected: Optional[str] = None, index: Optional[int] = None) -> ResolvedSlot:
    return ResolvedSlot(
        slot_kind=spec.slot_kind, source=spec.source,
        status="missing_required" if spec.required else "absent",
        drive_key=spec.drive_key, expected=expected or spec.drive_key, index=index,
        slot_id=spec.slot_id or None, image_type=spec.image_type or None,
        aspect_ratio=spec.aspect_ratio or None,
    )


def resolve_slots(st_type: str, drive_listing, *, case_index: Optional[int] = None) -> list[ResolvedSlot]:
    """Resolve every SlotSpec for st_type against drive_listing (filenames).
    `case_index` binds an `indexed` slot to its Fallstudie ordinal."""
    pairs = sorted((normalize_name(n), n) for n in drive_listing)
    out: list[ResolvedSlot] = []

    for spec in recipe_for(st_type):
        if spec.source in ("generate", "composite"):
            out.append(ResolvedSlot(
                slot_kind=spec.slot_kind, source=spec.source, status="absent",
                drive_key=spec.drive_key, expected=spec.drive_key,
                slot_id=spec.slot_id or None, image_type=spec.image_type or None,
                aspect_ratio=spec.aspect_ratio or None,
            ))
            continue

        if spec.cardinality == "many":
            stem = normalize_name((spec.drive_key or spec.slot_kind).replace("*", ""))
            matches = [orig for nk, orig in pairs if stem and (nk == stem or nk.startswith(stem + "-"))]
            if matches:
                for i, orig in enumerate(matches):
                    out.append(ResolvedSlot(
                        slot_kind=spec.slot_kind, source=spec.source, status="resolved",
                        path=orig, index=i, drive_key=spec.drive_key,
                        slot_id=spec.slot_id or None, image_type=spec.image_type or None,
                        aspect_ratio=spec.aspect_ratio or None,
                    ))
            else:
                out.append(_miss(spec))
            continue

        if spec.cardinality == "indexed":
            if case_index is None:
                out.append(_miss(spec, index=None))
                continue
            key = (spec.drive_key or spec.slot_kind).replace("{n}", str(case_index))
            idx = case_index
        else:
            key = spec.drive_key or spec.slot_kind
            idx = None

        target = normalize_name(key)
        hit = next((orig for nk, orig in pairs if nk == target), None)
        if hit is not None:
            out.append(ResolvedSlot(
                slot_kind=spec.slot_kind, source=spec.source, status="resolved",
                path=hit, drive_key=spec.drive_key, index=idx, expected=key,
                slot_id=spec.slot_id or None, image_type=spec.image_type or None,
                aspect_ratio=spec.aspect_ratio or None,
            ))
        else:
            out.append(_miss(spec, expected=key, index=idx))

    return out
