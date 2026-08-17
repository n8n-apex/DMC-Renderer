"""Tests for slot_bridge — map scraper slots to resolver drive-key filenames.

The slot resolver matches single slots by EXACT normalized stem and many slots
by ``<stem>-`` prefix. These tests verify the bridge writes filenames the real
resolver (stages.resolve_slots) actually picks up.
"""
from __future__ import annotations

from stages.scrape_founder_assets.orchestrator import FounderAssetResult, SlotOutcome
from stages.scrape_founder_assets.slot_bridge import (
    ELEMENT_TO_DRIVE_KEY,
    place_for_resolver,
    place_routed,
)
from stages.scrape_founder_assets.models import RoutedElement
from stages.resolve_slots import resolve_slots
from stages.local_assets import list_client_assets


def _img(path):
    # a 1x1 png is enough; the bridge only copies bytes.
    from PIL import Image
    Image.new("RGB", (4, 4), (10, 10, 10)).save(path)
    return str(path)


def test_places_founder_team_proof_with_resolver_matching_names(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    f = _img(src / "founder__0.jpg")
    t = _img(src / "team__0.jpg")
    s = _img(src / "scene__0.jpg")

    result = FounderAssetResult(
        slots={
            "founder": SlotOutcome(slot="founder", status="filled", path=f),
            "team": SlotOutcome(slot="team", status="filled", path=t),
            "scene": SlotOutcome(slot="scene", status="filled", path=s),
        }
    )

    dest = tmp_path / "client_assets" / "acme"
    placed = place_for_resolver(result, dest)

    names = list_client_assets(dest)
    # single drive_keys -> exact stem; many drive_key proof -> indexed
    assert "founder.jpg" in names
    assert "team.jpg" in names
    assert "proof-1.jpg" in names
    assert set(placed) == {"founder", "team", "scene"}

    # the REAL resolver now matches these into the right slots
    cover = resolve_slots("ST-01", names)
    founder_slot = next(s for s in cover if s.slot_kind == "founder_hero")
    assert founder_slot.status == "resolved" and founder_slot.path == "founder.jpg"

    about = resolve_slots("ST-05", names)
    team_slot = next(s for s in about if s.slot_kind == "team")
    assert team_slot.status == "resolved" and team_slot.path == "team.jpg"
    proof_slots = [s for s in about if s.slot_kind == "proof" and s.status == "resolved"]
    assert proof_slots and proof_slots[0].path == "proof-1.jpg"


def test_flagged_slots_are_skipped(tmp_path):
    src = tmp_path / "src"; src.mkdir()
    f = _img(src / "founder__0.jpg")
    result = FounderAssetResult(
        slots={
            "founder": SlotOutcome(slot="founder", status="filled", path=f),
            "team": SlotOutcome(slot="team", status="flagged", reason="no asset"),
        }
    )
    dest = tmp_path / "ca" / "acme"
    placed = place_for_resolver(result, dest)
    assert set(placed) == {"founder"}
    assert list_client_assets(dest) == ["founder.jpg"]


def test_multiple_scene_become_indexed_proof(tmp_path):
    src = tmp_path / "src"; src.mkdir()
    result = FounderAssetResult(
        slots={
            "scene": SlotOutcome(slot="scene", status="filled", path=_img(src / "a.jpg")),
            "about_portrait": SlotOutcome(slot="about_portrait", status="filled", path=_img(src / "b.jpg")),
        }
    )
    # about_portrait -> team (single); scene -> proof-1 (many)
    dest = tmp_path / "ca" / "acme"
    place_for_resolver(result, dest)
    names = list_client_assets(dest)
    assert "team.jpg" in names      # about_portrait mapped to team
    assert "proof-1.jpg" in names   # scene mapped to proof gallery


# --- place_routed: route a list[RoutedElement] -> resolver drive-key files ---

def test_element_to_drive_key_map():
    # cover_hero -> founder; team -> team; scene/proof/content_card -> proof;
    # logo -> logo; device_mockup has NO drive file (None). There is NO
    # about_portrait report element (the renderer has only founder + team slots).
    assert ELEMENT_TO_DRIVE_KEY["cover_hero"] == "founder"
    assert ELEMENT_TO_DRIVE_KEY["team"] == "team"
    assert ELEMENT_TO_DRIVE_KEY["scene"] == "proof"
    assert ELEMENT_TO_DRIVE_KEY["proof"] == "proof"
    assert ELEMENT_TO_DRIVE_KEY["content_card"] == "proof"
    assert ELEMENT_TO_DRIVE_KEY["logo"] == "logo"
    assert ELEMENT_TO_DRIVE_KEY["device_mockup"] is None
    assert "about_portrait" not in ELEMENT_TO_DRIVE_KEY


def test_place_routed_resolver_matching_names(tmp_path):
    src = tmp_path / "src"; src.mkdir()
    cover = _img(src / "cover.jpg")
    portrait = _img(src / "portrait.jpg")
    proof_a = _img(src / "pa.jpg")
    proof_b = _img(src / "pb.jpg")
    working = _img(src / "work.jpg")

    routed = [
        RoutedElement(element="cover_hero", status="filled", path=cover,
                      role="founder_portrait", appeal=3),
        RoutedElement(element="team", status="filled", path=portrait,
                      role="group_team", appeal=2),
        RoutedElement(element="proof", status="filled", path=proof_a,
                      role="content_card", appeal=2),
        RoutedElement(element="scene", status="filled", path=proof_b,
                      role="lifestyle", appeal=2),
        # device_mockup is NOT a drive file — must be skipped here.
        RoutedElement(element="device_mockup", status="filled", path=working,
                      role="founder_working", appeal=3),
        # flagged element is skipped (never fabricated).
        RoutedElement(element="logo", status="flagged", reason="no asset"),
    ]

    dest = tmp_path / "client_assets" / "acme"
    placed = place_routed(routed, dest)

    names = list_client_assets(dest)
    assert "founder.jpg" in names       # cover_hero -> founder (single)
    assert "team.jpg" in names          # team -> team (single)
    # proof + scene both -> proof gallery, indexed (two distinct files)
    assert "proof-1.jpg" in names
    assert "proof-2.jpg" in names
    # device_mockup never written as a drive file
    assert "cover_hero" in placed and "device_mockup" not in placed
    assert "logo" not in placed  # flagged logo skipped

    # the REAL resolver picks these up into the right slots
    cover_slots = resolve_slots("ST-01", names)
    founder_slot = next(s for s in cover_slots if s.slot_kind == "founder_hero")
    assert founder_slot.status == "resolved" and founder_slot.path == "founder.jpg"

    about = resolve_slots("ST-05", names)
    team_slot = next(s for s in about if s.slot_kind == "team")
    assert team_slot.status == "resolved" and team_slot.path == "team.jpg"
    proof_slots = [s for s in about if s.slot_kind == "proof" and s.status == "resolved"]
    assert proof_slots


def test_place_routed_dedup_single_drive_key_first_filled_wins(tmp_path):
    """A single drive_key ('team') is written ONCE: if two FILLED elements map to
    the same single drive_key, only the FIRST writes the file; the second never
    overwrites. (The router emits at most one 'team', but place_routed must still
    enforce the single-slot-written-once contract.)"""
    src = tmp_path / "src"; src.mkdir()
    a = _img(src / "a.jpg")
    b = _img(src / "b.jpg")
    routed = [
        RoutedElement(element="team", status="filled", path=a,
                      role="group_team", appeal=3),
        # a 2nd element mapping to the same single drive_key must NOT overwrite
        RoutedElement(element="team", status="filled", path=b,
                      role="founder_portrait", appeal=2),
    ]
    dest = tmp_path / "ca" / "acme"
    place_routed(routed, dest)

    names = list_client_assets(dest)
    assert names == ["team.jpg"]  # exactly one team file, not overwritten


def test_place_routed_cover_and_team_are_distinct_drive_files(tmp_path):
    """cover_hero -> founder.jpg and team -> team.jpg are distinct single slots;
    a founder portrait in the hero and a group photo in team coexist."""
    src = tmp_path / "src"; src.mkdir()
    hero = _img(src / "hero.jpg")
    group = _img(src / "group.jpg")
    routed = [
        RoutedElement(element="cover_hero", status="filled", path=hero,
                      role="founder_portrait", appeal=3),
        RoutedElement(element="team", status="filled", path=group,
                      role="group_team", appeal=3),
    ]
    dest = tmp_path / "ca" / "acme"
    placed = place_routed(routed, dest)

    names = list_client_assets(dest)
    assert "founder.jpg" in names and "team.jpg" in names
    assert placed["cover_hero"].endswith("founder.jpg")
    assert placed["team"].endswith("team.jpg")


def test_place_routed_skips_flagged_and_device(tmp_path):
    src = tmp_path / "src"; src.mkdir()
    w = _img(src / "w.jpg")
    routed = [
        RoutedElement(element="device_mockup", status="filled", path=w,
                      role="founder_working", appeal=3),
        RoutedElement(element="cover_hero", status="flagged", reason="no face"),
    ]
    dest = tmp_path / "ca" / "acme"
    placed = place_routed(routed, dest)
    assert placed == {}
    assert list_client_assets(dest) == []
