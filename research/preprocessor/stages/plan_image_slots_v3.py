"""Decide WHICH images a report needs, before any are made.

Generation without this is guesswork: a ceiling of nineteen spent on
nineteen unrelated pictures. Richard's own packages say otherwise. One
report of his (Buchagentur, 45 linked files) is:

    1 paper texture at 3584x4800, placed on NINE consecutive faces
    ~10 PSD composites named by PURPOSE, not by page number:
        "Geteiltes Gehirn Psychologie"      a concept illustration
        "Psychologie Gegenueberstellung"    a comparison graphic
        "Teammitglied 1 Ueber Uns Seite"    a team portrait for About
        "Kia Kahawa Ausgeschnitten mit Buch" a cutout figure with a prop
    4 photographs from one dated shoot
    4 logo variants

So the shape is: ONE ground reused everywhere, a handful of illustrations
each built for a specific argument, and a few real photographs. Six or
seven generations dress a whole report. Nineteen unique stock images would
cost more and look less like his work.

This plans that list from the report's own faces, so every requested image
exists because a specific page needs it and can say why.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


# Measured from the reference packages. A ground is a full A4 portrait at
# print resolution; a spread illustration is wide; a portrait is 3:4.
GROUND_PX = (3584, 4800)
ILLUSTRATION_PX = (4096, 4096)
SPREAD_PX = (5504, 3072)
PORTRAIT_PX = (2400, 3200)


@dataclass(frozen=True)
class ImageSlot:
    """One image the report needs, and the reason it needs it."""

    slot_id: str
    semantic_class: Literal["texture", "context", "identity", "proof", "product"]
    pixels: tuple[int, int]
    subject: str
    reason: str
    reused_on_faces: tuple[str, ...] = ()
    # Whether a photograph the client already owns can fill this slot.
    # A hero is atmosphere, so any good photograph serves. A CONCEPT
    # illustration is built for one argument and a stock shot cannot
    # stand in for it; a ground is a surface, not a picture. Counting
    # every supplied file as interchangeable is how "we have 28 images"
    # becomes "we need none".
    fillable_by_supplied: bool = True

    @property
    def aspect(self) -> str:
        w, h = self.pixels
        return "portrait" if w < h else "landscape" if w > h else "square"


# Roles whose page carries an argument a picture can actually illustrate.
# A cover needs atmosphere; a theory page needs a concept; a CTA needs
# neither and gets nothing rather than filler.
_ILLUSTRATED_ROLES = {"theory", "mechanism", "status_quo", "false_beliefs", "summary"}
_PORTRAIT_ROLES = {"case_study", "about"}
_HERO_ROLES = {"cover", "outlook"}


def plan_slots(faces: list[Any], *, client_slug: str) -> tuple[ImageSlot, ...]:
    """Every image this report needs, each with the face that asks for it."""
    slots: list[ImageSlot] = []
    interior = [
        getattr(face, "face_id", face.get("face_id"))
        for face in faces
        if _role(face) not in {"cover", "cta"}
    ]

    # One ground, reused across every interior face. This is the single
    # cheapest image in the report and the one Richard never skips.
    if interior:
        slots.append(
            ImageSlot(
                slot_id=f"{client_slug}.ground.paper",
                semantic_class="texture",
                pixels=GROUND_PX,
                subject="subtle paper surface, even tone, no focal point",
                reason=(
                    f"one ground dresses all {len(interior)} interior faces; "
                    "the reference places a single texture on nine"
                ),
                reused_on_faces=tuple(interior),
                fillable_by_supplied=False,
            )
        )

    for face in faces:
        role = _role(face)
        face_id = getattr(face, "face_id", None) or face.get("face_id", "")
        argument = getattr(face, "argument", None) or face.get("argument", "")
        if role in _HERO_ROLES:
            slots.append(
                ImageSlot(
                    slot_id=f"{face_id}.hero",
                    semantic_class="context",
                    pixels=SPREAD_PX,
                    subject=argument[:160],
                    reason=f"{role} face opens the report and carries its atmosphere",
                )
            )
        elif role in _ILLUSTRATED_ROLES and argument:
            # Named by the argument it explains, exactly as his PSDs are
            # ("Geteiltes Gehirn Psychologie" is a concept, not a page).
            slots.append(
                ImageSlot(
                    slot_id=f"{face_id}.concept",
                    semantic_class="context",
                    pixels=ILLUSTRATION_PX,
                    subject=argument[:160],
                    reason=f"{role} face argues one idea; the illustration carries it",
                    fillable_by_supplied=False,
                )
            )
        elif role in _PORTRAIT_ROLES:
            slots.append(
                ImageSlot(
                    slot_id=f"{face_id}.portrait",
                    semantic_class="identity",
                    pixels=PORTRAIT_PX,
                    subject=argument[:160] or "person, chest up, plain ground",
                    reason=f"{role} face names a person and must show one",
                )
            )
    return tuple(slots)


def _role(face: Any) -> str:
    role = getattr(face, "role", None)
    if role is None and isinstance(face, dict):
        role = face.get("role", "")
    return getattr(role, "value", role) or ""


def generation_budget(
    slots: tuple[ImageSlot, ...],
    supplied_by_class: dict[str, int] | None = None,
) -> dict:
    """What actually has to be generated, once real files are counted.

    Counted BY CLASS and only against slots a supplied photograph can
    honestly fill. An Instagram photo is a fine hero and a poor concept
    illustration; a paper ground is not a photograph at all. Treating the
    library as interchangeable is what turns "we own 28 images" into "we
    need none" while the pages stay empty.
    """
    supplied = dict(supplied_by_class or {})
    unique = len(slots)
    placements = sum(max(1, len(slot.reused_on_faces)) for slot in slots)

    must_generate: list[ImageSlot] = []
    for slot in slots:
        if not slot.fillable_by_supplied:
            must_generate.append(slot)
            continue
        available = supplied.get(slot.semantic_class, 0)
        if available > 0:
            supplied[slot.semantic_class] = available - 1
        else:
            must_generate.append(slot)

    return {
        "unique_images": unique,
        "total_placements": placements,
        "saved_by_reuse": placements - unique,
        "to_generate": len(must_generate),
        "generate": tuple(slot.slot_id for slot in must_generate),
        "covered_by_supplied": unique - len(must_generate),
    }
