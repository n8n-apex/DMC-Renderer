"""Tests for the slot taxonomy + per-ST recipe registry."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from stages.slot_registry import SlotSpec, recipe_for


def test_case_study_has_required_indexed_client_portrait() -> None:
    specs = recipe_for("ST-07A")
    kinds = {s.slot_kind for s in specs}
    assert "client_portrait" in kinds
    cp = next(s for s in specs if s.slot_kind == "client_portrait")
    assert cp.cardinality == "indexed"
    assert cp.required is True
    assert cp.source == "drive"
    assert cp.drive_key == "case-study-{n}"


def test_about_has_team_and_logo_walls() -> None:
    specs = recipe_for("ST-05")
    by_kind = {s.slot_kind: s for s in specs}
    assert by_kind["team"].source == "drive"
    assert by_kind["press_logo"].cardinality == "many"
    assert by_kind["client_logo"].cardinality == "many"


def test_about_has_proof_gallery() -> None:
    specs = recipe_for("ST-05")
    proof = [s for s in specs if s.slot_kind == "proof"]
    assert proof, "About page should carry an optional proof gallery"
    assert proof[0].cardinality == "many"
    assert proof[0].source == "drive"
    assert proof[0].required is False
    assert proof[0].drive_key == "proof-*"


def test_cover_has_founder_hero_drive_and_generated_scene() -> None:
    specs = recipe_for("ST-01")
    by_kind = {s.slot_kind: s for s in specs}
    assert by_kind["founder_hero"].source == "drive"
    assert by_kind["scene"].source == "generate"


def test_human_kinds_are_never_generated() -> None:
    for st in ("ST-01", "ST-05", "ST-07A", "ST-FAZIT"):
        for s in recipe_for(st):
            if s.slot_kind in ("founder_hero", "client_portrait", "team"):
                assert s.source == "drive"


def test_unknown_type_has_empty_recipe() -> None:
    assert recipe_for("ST-99") == []


def test_slotspec_rejects_unknown_kind() -> None:
    with pytest.raises(ValidationError):
        SlotSpec(slot_kind="unicorn")  # type: ignore[arg-type]


def test_every_slotspec_has_slot_id_and_image_type() -> None:
    """Every SlotSpec in every recipe must carry a non-empty slot_id and image_type."""
    from stages.slot_registry import PAGE_TYPE_RECIPES
    for st_type, specs in PAGE_TYPE_RECIPES.items():
        for spec in specs:
            assert spec.slot_id, f"{st_type}/{spec.slot_kind} missing slot_id"
            assert spec.image_type, f"{st_type}/{spec.slot_kind} missing image_type"


def test_st05_has_logo_slotspec() -> None:
    """ST-05 recipe must contain a SlotSpec with slot_kind=='logo', slot_id=='about_logo',
    source=='drive', required is False, drive_key=='logo'."""
    specs = recipe_for("ST-05")
    logo_specs = [s for s in specs if s.slot_kind == "logo"]
    assert logo_specs, "ST-05 should have a 'logo' SlotSpec"
    logo = logo_specs[0]
    assert logo.slot_id == "about_logo"
    assert logo.source == "drive"
    assert logo.required is False
    assert logo.drive_key == "logo"
