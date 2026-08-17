"""Turn a live writer payload into a v3 build envelope.

v3 was only ever fed hand-authored fixtures, so nothing in the system knew
how to read what the writer actually emits. A real payload is a list of
pages, each carrying a chapter type and a handful of prose fields. Those
chapter types are not decoration: they name the same editorial roles the
composition families were derived from, so the mapping is a rename, not an
invention.

    Cover, Outlook      -> editorial_lead
    About               -> evidence_wall
    Status Quo, Theory  -> theory_interpretation
    False Beliefs       -> false_belief_stack
    Case Study          -> case_narrative
    Mechanism           -> mechanism_spread
    Summary             -> summary_synthesis
    Collaboration       -> collaboration_pathway
    CTA                 -> closing_cta

A page whose page_numbers span a range was written as a spread, so it is
allocated an A3 sheet and its fields are split across the two faces: the
setup on the left, the payoff on the right. A single page stays A4.

Evidence comes from `derive_claims_v3`, which reads the figures out of the
same prose, so a real report arrives with grounded claims and the device
intents its sentences earned.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from composition_registry.schema import CompositionFamily, CompositionRegistry
from stages.derive_claims_v3 import DerivedEvidence, derive_evidence


class WriterPayloadUnsupported(ValueError):
    """The payload names an editorial role the family set does not cover."""

    def __init__(self, *, code: str, detail: str) -> None:
        self.owner_stage = "writer_payload_adapter"
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


# Chapter types as the writer emits them, matched case-insensitively on the
# leading words so "Case Study 3" and "Theory 1" resolve with their number.
# The plan's own role vocabulary is this same vocabulary, so the chapter
# names the role directly and the family follows from the role.
_CHAPTER_TABLE = (
    ("cover", "cover", "editorial_lead"),
    ("outlook", "outlook", "editorial_lead"),
    ("about", "about", "evidence_wall"),
    ("status quo", "status_quo", "theory_interpretation"),
    ("false beliefs", "false_beliefs", "false_belief_stack"),
    ("case study", "case_study", "case_narrative"),
    ("theory", "theory", "theory_interpretation"),
    ("mechanism", "mechanism", "mechanism_spread"),
    ("summary", "summary", "summary_synthesis"),
    ("fazit", "summary", "summary_synthesis"),
    ("objection", "objections", "objection_response"),
    ("collaboration", "collaboration", "collaboration_pathway"),
    ("cta", "cta", "closing_cta"),
    ("trust", "trust_proof", "evidence_wall"),
)


def _chapter_entry(chapter_type: str) -> tuple[str, str, str]:
    lowered = (chapter_type or "").strip().lower()
    for entry in _CHAPTER_TABLE:
        if lowered.startswith(entry[0]):
            return entry
    raise WriterPayloadUnsupported(
        code="unmapped_chapter_type",
        detail=f"no composition family covers chapter type {chapter_type!r}",
    )


_PAGE_RANGE = re.compile(r"^\s*(\d+)\s*[-–]\s*(\d+)\s*$")
_PAGE_SINGLE = re.compile(r"^\s*(\d+)\s*$")


def printed_pages(page: dict[str, Any]) -> tuple[int, ...]:
    """The printed pages this written page claims, from its own numbering."""
    raw = str(page.get("page_numbers", ""))
    span = _PAGE_RANGE.match(raw)
    if span:
        first, last = int(span.group(1)), int(span.group(2))
        return tuple(range(first, last + 1)) if last >= first else (first,)
    single = _PAGE_SINGLE.match(raw)
    return (int(single.group(1)),) if single else ()


def _assert_pagination_is_consistent(pages: list[dict[str, Any]]) -> None:
    """No printed page may be claimed by two written pages.

    The writer numbers each chapter itself, so a collision means two
    chapters were written onto the same sheet. Laying them out anyway would
    silently drop one, so the payload is refused with both names.
    """
    claimed_by: dict[int, str] = {}
    collisions: list[str] = []
    for page in pages:
        name = str(page.get("chapter_type_original", "?"))
        for number in printed_pages(page):
            if number in claimed_by:
                collisions.append(f"page {number}: {claimed_by[number]} and {name}")
            else:
                claimed_by[number] = name
    if collisions:
        raise WriterPayloadUnsupported(
            code="page_number_collision",
            detail="; ".join(collisions),
        )


def family_for_chapter(chapter_type: str) -> str:
    return _chapter_entry(chapter_type)[2]


def role_for_chapter(chapter_type: str) -> str:
    return _chapter_entry(chapter_type)[1]


def is_spread(page: dict[str, Any]) -> bool:
    """A page written across a numbered range was written as a spread."""
    return len(printed_pages(page)) == 2


def _flatten(value: Any) -> list[str]:
    """Every readable string in one page field, in document order."""
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, (int, float)):
        return [str(value)]
    if isinstance(value, list):
        return [item for child in value for item in _flatten(child)]
    if isinstance(value, dict):
        return [item for child in value.values() for item in _flatten(child)]
    return []


def _page_blocks(page: dict[str, Any]) -> list[str]:
    return [block for value in (page.get("data") or {}).values() for block in _flatten(value)]


def _region_font_pt(family: CompositionFamily, region_id: str, language: str) -> float:
    region = next(item for item in family.regions if item.region_id == region_id)
    capacity = next(item for item in region.capacities if item.language == language)
    kinds = set(region.allowed_element_kinds)
    # A heading-only region carries display type; anything holding prose is
    # set at reading size. Both stay inside the region's declared envelope.
    wanted = 26.0 if kinds <= {"heading"} else 9.5
    return round(min(max(wanted, capacity.min_font_pt), capacity.max_font_pt), 2)


def _distribute(blocks: list[str], region_ids: tuple[str, ...]) -> dict[str, list[str]]:
    """First block leads the first region; the rest fill the remaining ones."""
    if not blocks:
        return {}
    if len(region_ids) == 1:
        return {region_ids[0]: blocks}
    lead, *rest = blocks
    assigned: dict[str, list[str]] = {region_ids[0]: [lead]}
    if not rest:
        return assigned
    # The second region takes the body of the argument; any further region
    # takes the tail, so no region is left empty while another overflows.
    if len(region_ids) == 2:
        assigned[region_ids[1]] = rest
        return assigned
    split = max(1, len(rest) * 2 // 3)
    assigned[region_ids[1]] = rest[:split]
    assigned[region_ids[2]] = rest[split:] or rest[-1:]
    return assigned


def _renumbered(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Lay the chapters out in document order, keeping each one's shape."""
    laid_out: list[dict[str, Any]] = []
    cursor = 1
    for page in pages:
        width = max(1, len(printed_pages(page)))
        numbers = (
            str(cursor) if width == 1 else f"{cursor}-{cursor + width - 1}"
        )
        laid_out.append({**page, "page_numbers": numbers})
        cursor += width
    return laid_out


def adapt_writer_payload(
    payload: dict[str, Any],
    *,
    registry: CompositionRegistry,
    captured_at: datetime,
    renumber: bool = False,
) -> dict[str, Any]:
    """Build the v3 envelope a live writer payload describes."""

    pages = list(payload.get("pages") or ())
    if not pages:
        raise WriterPayloadUnsupported(
            code="empty_payload", detail="payload carries no pages"
        )
    if renumber:
        # The caller has accepted that the writer's own numbering is unusable
        # and asked for chapters to be laid out in document order instead.
        # Each chapter keeps the shape it was written in; only the numbering
        # is replaced, and the envelope records that it happened.
        pages = _renumbered(pages)
    else:
        _assert_pagination_is_consistent(pages)
    meta = payload.get("meta") or {}
    language = str(meta.get("lang") or "de")
    family_by_id = {family.family_id: family for family in registry.families}

    faces: list[dict[str, Any]] = []
    facts: list[dict[str, Any]] = []
    formats: list[str] = []
    face_index = 0

    for page in pages:
        chapter = str(page.get("chapter_type_original", ""))
        _, role, family_id = _chapter_entry(chapter)
        family = family_by_id.get(family_id)
        if family is None:
            raise WriterPayloadUnsupported(
                code="family_not_registered",
                detail=f"{family_id} is not in the loaded registry",
            )
        region_ids = tuple(region.region_id for region in family.regions)
        blocks = _page_blocks(page)
        if not blocks:
            continue
        if is_spread(page):
            half = max(1, len(blocks) // 2)
            face_blocks = [blocks[:half], blocks[half:] or blocks[-1:]]
            formats.append("a3")
        else:
            face_blocks = [blocks]
            formats.append("a4")

        for blocks_for_face in face_blocks:
            face_index += 1
            face_id = f"face.{face_index:02d}"
            distributed = _distribute(blocks_for_face, region_ids)
            content_by_ref: dict[str, str] = {}
            regions: dict[str, dict[str, Any]] = {}
            for region_id, texts in distributed.items():
                refs = []
                for order, text in enumerate(texts, start=1):
                    ref = f"content.{face_id}.{region_id}.{order:02d}"
                    content_by_ref[ref] = text
                    refs.append(ref)
                regions[region_id] = {
                    "content_refs": tuple(refs),
                    "font_size_pt": _region_font_pt(family, region_id, language),
                }
            faces.append(
                {
                    "face_id": face_id,
                    "face_index": face_index,
                    "role": role,
                    "narrative_act": chapter,
                    "argument": blocks_for_face[0][:200],
                    "claim_ids": [],
                    "proof_requirements": (
                        [
                            {
                                "requirement_id": f"{face_id}.trust",
                                "proof_type": "trust",
                            }
                        ]
                        if role in {"about", "trust_proof"}
                        else []
                    ),
                    "asset_requirements": [],
                    "dominant_mechanism": role,
                    "density_band": "dense" if len(blocks_for_face) >= 6 else "moderate",
                    # A case face names the case it tells, so its evidence
                    # can be traced back to one client, not to the report.
                    "case_id": f"case.{face_id}" if role == "case_study" else None,
                }
            )
            facts.append(
                {
                    "face_id": face_id,
                    "language": language,
                    "content_by_ref": content_by_ref,
                    "regions": regions,
                    "asset_ids": [],
                }
            )

    evidence = derive_evidence(
        {"report_json": payload}, captured_at=captured_at, language=language
    )
    _bind_claims_to_faces(faces, facts, evidence)

    return {
        "payload": payload,
        "sources": list(evidence.sources),
        "claims": list(evidence.claims),
        "source_appendix_v3": {
            "entries": [
                {
                    "source_id": source["source_id"],
                    "citation_text": (
                        "Angabe aus der freigegebenen Berichtskopie, "
                        f"{source['locator']}"
                    ),
                }
                for source in evidence.sources
            ]
        },
        "editorial_brief_v3": {
            "product_profile_id": str(meta.get("report_id") or "writer_payload"),
            "formats": formats,
            "faces": faces,
            "audience": str(meta.get("audience") or "German B2B founder"),
            "central_thesis": faces[0]["argument"] if faces else "",
            "promise": faces[0]["argument"] if faces else "",
            "tone_profile": "Richard house",
        },
        "composition_facts_v3": facts,
        "assets": [],
        "images": [],
        "brand_tokens": {},
        "pagination_renumbered": renumber,
        "derived_devices": [device.model_dump() for device in evidence.devices],
    }


def _bind_claims_to_faces(
    faces: list[dict[str, Any]],
    facts: list[dict[str, Any]],
    evidence: DerivedEvidence,
) -> None:
    """Give each face the claims whose verbatim text it actually prints.

    A claim is bound by its own span text appearing in the copy the face
    carries, so a face never declares evidence it does not show.
    """
    text_by_source = {source["source_id"]: source["verbatim_text"] for source in evidence.sources}
    claims_by_text: dict[str, list[str]] = {}
    for claim in evidence.claims:
        for span in claim["source_spans"]:
            source_text = text_by_source.get(span["source_id"])
            if source_text is not None:
                claims_by_text.setdefault(source_text, []).append(claim["claim_id"])
    facts_by_face = {item["face_id"]: item for item in facts}
    for face in faces:
        face_facts = facts_by_face[face["face_id"]]
        bound: list[str] = []
        for text in face_facts["content_by_ref"].values():
            bound.extend(claims_by_text.get(text, ()))
        face["claim_ids"] = list(dict.fromkeys(bound))
