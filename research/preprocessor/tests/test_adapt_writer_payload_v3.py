"""A live writer payload must become a v3 envelope, or be refused clearly."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from composition_registry.registry import load_registry
from stages.adapt_writer_payload_v3 import (
    WriterPayloadUnsupported,
    adapt_writer_payload,
    family_for_chapter,
    is_spread,
    printed_pages,
    role_for_chapter,
)


ROOT = Path(__file__).resolve().parents[3]
REGISTRY_PATH = ROOT / "research" / "composition_registry" / "families" / "dmc-v1.json"
ATLAS_PATH = ROOT / "research" / "reference-atlas" / "reference-atlas.json"
REAL_PAYLOAD = ROOT / "dmc-renderer" / "fixtures" / "apex_consulting_payload.json"
CAPTURED_AT = datetime(2026, 8, 7, tzinfo=timezone.utc)


def registry():
    return load_registry(REGISTRY_PATH, atlas_path=ATLAS_PATH)


def real_payload() -> dict:
    return json.loads(REAL_PAYLOAD.read_text(encoding="utf-8"))["payload"]


def test_every_chapter_type_in_the_real_payload_maps_to_a_family() -> None:
    families = {family.family_id for family in registry().families}

    for page in real_payload()["pages"]:
        chapter = page["chapter_type_original"]
        assert family_for_chapter(chapter) in families, chapter
        assert role_for_chapter(chapter)


def test_an_unknown_chapter_type_is_refused_by_name() -> None:
    with pytest.raises(WriterPayloadUnsupported) as caught:
        family_for_chapter("Horoscope")

    assert caught.value.code == "unmapped_chapter_type"
    assert "Horoscope" in caught.value.detail


def test_a_page_range_is_read_as_a_spread() -> None:
    assert printed_pages({"page_numbers": "4-5"}) == (4, 5)
    assert printed_pages({"page_numbers": "7"}) == (7,)
    assert is_spread({"page_numbers": "4-5"})
    assert not is_spread({"page_numbers": "7"})


def test_two_chapters_on_one_printed_page_are_refused_with_both_names() -> None:
    """The real payload overlaps its own numbering; that must not pass."""
    with pytest.raises(WriterPayloadUnsupported) as caught:
        adapt_writer_payload(
            real_payload(), registry=registry(), captured_at=CAPTURED_AT
        )

    assert caught.value.code == "page_number_collision"
    assert "Mechanism" in caught.value.detail


def test_reflow_lays_chapters_out_in_order_without_collisions() -> None:
    envelope = adapt_writer_payload(
        real_payload(), registry=registry(), captured_at=CAPTURED_AT, renumber=True
    )

    assert envelope["pagination_renumbered"] is True
    brief = envelope["editorial_brief_v3"]
    assert len(brief["faces"]) == sum(
        2 if fmt == "a3" else 1 for fmt in brief["formats"]
    )
    indices = [face["face_index"] for face in brief["faces"]]
    assert indices == list(range(1, len(indices) + 1))


def test_the_envelope_carries_evidence_read_from_its_own_copy() -> None:
    envelope = adapt_writer_payload(
        real_payload(), registry=registry(), captured_at=CAPTURED_AT, renumber=True
    )

    assert envelope["claims"]
    assert envelope["derived_devices"]
    appendix = {entry["source_id"] for entry in envelope["source_appendix_v3"]["entries"]}
    assert {source["source_id"] for source in envelope["sources"]} == appendix


def test_a_face_only_declares_claims_its_own_copy_prints() -> None:
    envelope = adapt_writer_payload(
        real_payload(), registry=registry(), captured_at=CAPTURED_AT, renumber=True
    )
    claim_by_id = {claim["claim_id"]: claim for claim in envelope["claims"]}
    text_by_source = {
        source["source_id"]: source["verbatim_text"] for source in envelope["sources"]
    }
    facts_by_face = {item["face_id"]: item for item in envelope["composition_facts_v3"]}

    for face in envelope["editorial_brief_v3"]["faces"]:
        copy = set(facts_by_face[face["face_id"]]["content_by_ref"].values())
        for claim_id in face["claim_ids"]:
            spans = claim_by_id[claim_id]["source_spans"]
            assert any(text_by_source[span["source_id"]] in copy for span in spans)
