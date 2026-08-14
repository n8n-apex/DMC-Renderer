"""Tests for the Drive client's pure pieces (live google adapter is gated
on OAuth creds and added later). Uses a faked files.list response."""
from __future__ import annotations

from stages.drive_client import (
    DriveFile,
    drive_filenames,
    md5_cache_dest,
    md5_cached_path,
    parse_drive_listing,
)
from stages.resolve_slots import resolve_slots


def test_parse_listing_sorted_and_skips_invalid() -> None:
    resp = {"files": [
        {"id": "b", "name": "team.jpg", "md5Checksum": "m2"},
        {"id": "a", "name": "case-study-1.jpg", "md5Checksum": "m1"},
        {"id": "x"},
        {"name": "y.png"},
    ]}
    files = parse_drive_listing(resp)
    assert [f.name for f in files] == ["case-study-1.jpg", "team.jpg"]
    assert files[0].id == "a" and files[0].md5 == "m1"


def test_parse_empty_response() -> None:
    assert parse_drive_listing({}) == []
    assert parse_drive_listing({"files": []}) == []


def test_filenames_feed_the_slot_resolver() -> None:
    resp = {"files": [{"id": "a", "name": "case-study-1.jpg", "md5Checksum": "m"}]}
    names = drive_filenames(parse_drive_listing(resp))
    slots = resolve_slots("ST-07A", names, case_index=1)
    cp = [s for s in slots if s.slot_kind == "client_portrait"][0]
    assert cp.status == "resolved"
    assert cp.path == "case-study-1.jpg"


def test_md5_cache_hit_and_miss(tmp_path) -> None:
    f = DriveFile(id="a", name="x.png", md5="abc")
    cache = tmp_path / "drive_cache"
    assert md5_cached_path(cache, f) is None
    dest = md5_cache_dest(cache, f)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(b"img")
    hit = md5_cached_path(cache, f)
    assert hit is not None and hit.read_bytes() == b"img"
    assert hit == dest


def test_md5_cache_off_without_md5_or_dir(tmp_path) -> None:
    assert md5_cached_path(None, DriveFile(id="a", name="x.png", md5="abc")) is None
    assert md5_cached_path(tmp_path, DriveFile(id="a", name="x.png", md5=None)) is None
