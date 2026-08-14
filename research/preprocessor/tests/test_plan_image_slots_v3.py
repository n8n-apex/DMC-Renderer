"""What to generate is decided before anything is generated."""

from __future__ import annotations

from stages.plan_image_slots_v3 import (
    GROUND_PX,
    generation_budget,
    plan_slots,
)


def _faces(*roles: str) -> list[dict]:
    return [
        {"face_id": f"face.{i:02d}", "role": role, "argument": f"Argument {i}"}
        for i, role in enumerate(roles, start=1)
    ]


def test_one_ground_serves_every_interior_face() -> None:
    """The reference places a single texture on nine faces."""
    slots = plan_slots(_faces("cover", "theory", "theory", "summary", "cta"),
                       client_slug="c")
    ground = next(s for s in slots if s.semantic_class == "texture")

    assert ground.pixels == GROUND_PX
    # Interior only: the cover and the CTA are not dressed with it.
    assert set(ground.reused_on_faces) == {"face.02", "face.03", "face.04"}


def test_a_cta_gets_no_image_rather_than_filler() -> None:
    slots = plan_slots(_faces("cta"), client_slug="c")

    assert not [s for s in slots if s.slot_id.startswith("face.01")]


def test_a_concept_slot_cannot_be_filled_by_a_stock_photograph() -> None:
    """An illustration built for one argument has no substitute."""
    slots = plan_slots(_faces("theory"), client_slug="c")
    concept = next(s for s in slots if s.slot_id.endswith(".concept"))

    assert concept.fillable_by_supplied is False


def test_a_hero_can_be_filled_by_a_photograph_the_client_owns() -> None:
    slots = plan_slots(_faces("cover"), client_slug="c")
    hero = next(s for s in slots if s.slot_id.endswith(".hero"))

    assert hero.fillable_by_supplied is True


def test_a_library_of_photographs_does_not_cover_concepts_or_grounds() -> None:
    """28 owned images must not read as "we need none"."""
    slots = plan_slots(_faces("cover", "theory", "theory"), client_slug="c")

    budget = generation_budget(slots, supplied_by_class={"context": 23})

    # The hero is covered; the ground and both concepts are not.
    assert budget["covered_by_supplied"] == 1
    assert budget["to_generate"] == 3
    assert any(s.endswith("ground.paper") for s in budget["generate"])


def test_reuse_is_counted_as_a_saving_not_as_extra_work() -> None:
    slots = plan_slots(_faces("cover", "theory", "theory", "summary"), client_slug="c")

    budget = generation_budget(slots)

    assert budget["total_placements"] > budget["unique_images"]
    assert budget["saved_by_reuse"] == (
        budget["total_placements"] - budget["unique_images"]
    )


def test_every_slot_can_say_why_it_exists() -> None:
    """A requested image with no reason is a guess."""
    slots = plan_slots(_faces("cover", "about", "theory", "mechanism"), client_slug="c")

    assert slots
    for slot in slots:
        assert slot.reason.strip()
        assert slot.subject.strip()
