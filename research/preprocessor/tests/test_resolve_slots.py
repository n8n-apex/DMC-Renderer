"""Tests for the pure, deterministic slot resolver."""
from __future__ import annotations

from stages.resolve_slots import normalize_name, resolve_slots


def test_normalize_name_cases() -> None:
    assert normalize_name("Founder_Photo.JPG") == "founder-photo"
    assert normalize_name("case study 1.png") == "case-study-1"
    assert normalize_name("press logo acme.png") == "press-logo-acme"
    assert normalize_name("founder-image-12.jpg") == "founder"
    assert normalize_name("image-7-team.png") == "team"


def _by_kind(slots):
    out = {}
    for s in slots:
        out.setdefault(s.slot_kind, []).append(s)
    return out


def test_case_study_portrait_resolves_by_index() -> None:
    slots = resolve_slots("ST-07A", ["case-study-1.jpg", "other.png"], case_index=1)
    cp = _by_kind(slots)["client_portrait"][0]
    assert cp.status == "resolved"
    assert cp.path == "case-study-1.jpg"


def test_missing_required_client_portrait_is_named_error() -> None:
    slots = resolve_slots("ST-07A", ["case-study-1.jpg"], case_index=2)
    cp = _by_kind(slots)["client_portrait"][0]
    assert cp.status == "missing_required"
    assert cp.expected == "case-study-2"


def test_indexed_without_index_is_missing_required() -> None:
    slots = resolve_slots("ST-07A", ["case-study-1.jpg"], case_index=None)
    assert _by_kind(slots)["client_portrait"][0].status == "missing_required"


def test_composite_slot_is_absent_for_downstream() -> None:
    slots = resolve_slots("ST-07A", [], case_index=1)
    dm = _by_kind(slots)["device_mockup"][0]
    assert dm.status == "absent"
    assert dm.source == "composite"


def test_many_logos_resolve_sorted_and_optional_miss_absent() -> None:
    listing = ["press-logo-wsj.png", "press-logo-forbes.png", "team.jpg"]
    slots = resolve_slots("ST-05", listing)
    by = _by_kind(slots)
    assert by["team"][0].status == "resolved"
    press = [s for s in by["press_logo"] if s.status == "resolved"]
    assert [s.path for s in press] == ["press-logo-forbes.png", "press-logo-wsj.png"]
    assert by["client_logo"][0].status == "absent"


def test_determinism_shuffled_listing_same_result() -> None:
    a = resolve_slots("ST-05", ["press-logo-b.png", "press-logo-a.png", "team.jpg"])
    b = resolve_slots("ST-05", ["team.jpg", "press-logo-a.png", "press-logo-b.png"])
    assert [(s.slot_kind, s.status, s.path) for s in a] == [(s.slot_kind, s.status, s.path) for s in b]


def test_cover_founder_optional_absent_when_missing() -> None:
    slots = resolve_slots("ST-01", [])
    by = _by_kind(slots)
    assert by["founder_hero"][0].status == "absent"
    assert by["scene"][0].status == "absent"


def test_resolved_slot_carries_slot_id_image_type_aspect_ratio() -> None:
    """ST-07A case_index=2 with listing ['case-study-2.png'] yields a ResolvedSlot
    with slot_kind=='client_portrait', slot_id=='case_study_portrait',
    image_type=='portrait', aspect_ratio=='1x1', status=='resolved',
    index==2, path=='case-study-2.png'."""
    slots = resolve_slots("ST-07A", ["case-study-2.png"], case_index=2)
    cp = _by_kind(slots)["client_portrait"][0]
    assert cp.slot_kind == "client_portrait"
    assert cp.slot_id == "case_study_portrait"
    assert cp.image_type == "portrait"
    assert cp.aspect_ratio == "1x1"
    assert cp.status == "resolved"
    assert cp.index == 2
    assert cp.path == "case-study-2.png"
