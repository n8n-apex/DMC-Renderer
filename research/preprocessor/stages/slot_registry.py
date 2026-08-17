"""Declarative slot taxonomy + per-ST recipes (DNA §D / §7.1).

Names slot KINDS + drive_key CONVENTIONS only — never a client (brand-
agnostic). `source="drive"` on founder/client/team structurally forbids a
fal "fake person". The pure resolver (resolve_slots) consumes these + a
file listing. Not wired into generate_assets yet (Phase 3/4).
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

SlotKind = Literal[
    "founder_hero", "client_portrait", "team", "press_logo", "client_logo",
    "scene", "device_mockup", "texture", "gradient", "logo", "proof",
]
Cardinality = Literal["one", "indexed", "many"]
SlotSource = Literal["drive", "manifest", "generate", "composite"]


class SlotSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slot_kind: SlotKind
    cardinality: Cardinality = "one"
    source: SlotSource = "drive"
    required: bool = False
    aspect_ratio: str = "1x1"
    drive_key: Optional[str] = None
    slot_id: str = ""
    image_type: str = ""


PAGE_TYPE_RECIPES: dict[str, list[SlotSpec]] = {
    "ST-01": [
        SlotSpec(slot_kind="founder_hero", source="drive", required=False, aspect_ratio="3x4", drive_key="founder", slot_id="founder", image_type="portrait"),
        SlotSpec(slot_kind="scene", source="generate", aspect_ratio="3x4", slot_id="scene", image_type="scene"),
    ],
    "ST-05": [
        SlotSpec(slot_kind="team", source="drive", required=False, aspect_ratio="4x3", drive_key="team", slot_id="about_portrait", image_type="portrait"),
        SlotSpec(slot_kind="press_logo", cardinality="many", source="drive", aspect_ratio="3x2", drive_key="press-logo-*", slot_id="press_logo", image_type="logo"),
        SlotSpec(slot_kind="client_logo", cardinality="many", source="drive", aspect_ratio="3x2", drive_key="client-logo-*", slot_id="client_logo", image_type="logo"),
        # Credibility/proof photos (deal/award/press shots) — a "use-it-if-you-have-it"
        # gallery on the About page (DNA §C4). Optional, many, sourced from Drive.
        SlotSpec(slot_kind="proof", cardinality="many", source="drive", required=False, aspect_ratio="4x5", drive_key="proof-*", slot_id="proof", image_type="photo"),
        SlotSpec(slot_kind="logo", source="drive", required=False, aspect_ratio="1x1", drive_key="logo", slot_id="about_logo", image_type="logo"),
    ],
    "ST-07A": [
        SlotSpec(slot_kind="client_portrait", cardinality="indexed", source="drive", required=True, aspect_ratio="1x1", drive_key="case-study-{n}", slot_id="case_study_portrait", image_type="portrait"),
        SlotSpec(slot_kind="device_mockup", source="composite", required=False, aspect_ratio="9x16", slot_id="device_mockup", image_type="device"),
    ],
    "ST-09": [SlotSpec(slot_kind="scene", source="generate", aspect_ratio="16x9", slot_id="scene", image_type="scene")],
    "ST-FAZIT": [
        SlotSpec(slot_kind="scene", source="generate", aspect_ratio="3x4", slot_id="scene", image_type="scene"),
        SlotSpec(slot_kind="founder_hero", source="drive", required=False, aspect_ratio="1x1", drive_key="founder", slot_id="founder", image_type="portrait"),
    ],
    "ST-31": [SlotSpec(slot_kind="texture", source="generate", aspect_ratio="3x4", slot_id="texture", image_type="texture")],
    "ST-32": [SlotSpec(slot_kind="texture", source="generate", aspect_ratio="3x4", slot_id="texture", image_type="texture")],
}


def recipe_for(st_type: str) -> list[SlotSpec]:
    """The list of SlotSpecs for a page's ST type (empty if it needs no imagery)."""
    return PAGE_TYPE_RECIPES.get(st_type, [])
