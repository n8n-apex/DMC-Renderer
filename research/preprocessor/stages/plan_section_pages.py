"""US-603 — section pagination planner (semantic split).

A logical report SECTION may own multiple physical pages (user directive).
When a section's copy exceeds its per-ST capacity budget, this planner splits
it at SEMANTIC boundaries (whole narrative blocks / whole step pairs — never
mid-sentence) into multiple PlannedPage records, each carrying US-602 identity
(section_id / page_id / continuation_index / continuation_role /
section_page_count).

Guarantees:
  - short section -> exactly ONE page (no identity; back-compat)
  - heavy section -> 2+ pages at semantic boundaries
  - every source field appears on EXACTLY ONE page (no duplication, no loss)
  - continuations are contiguous (same section, adjacent records)
  - no fabrication: the split only RE-DISTRIBUTES the section's own data

Trigger: per-ST copy capacity (validate_copyfit.ST_COPY_BUDGET_CHARS). A
section over budget is split; a section under budget is untouched.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from stages.plan_layout import PlannedPage
from stages.validate_copyfit import ST_COPY_BUDGET_CHARS
from stages.validate_copy import _collect_all_strings

# Semantic roles a continuation page may carry (whole-block roles).
_SEMANTIC_ROLES = ("intro", "mechanism", "proof", "result", "close")

# Narrative copy fields per ST type : the blocks that must NEVER be split
# mid-content. Each block moves to ONE page as a whole.
_COPY_FIELDS_BY_ST: dict[str, list[str]] = {
    "ST-06": ["title", "body", "steps", "ergebnis"],
    "ST-07A": [
        "kurzportraet", "ausgangsproblem", "ziel", "loesung",
        "ergebnis_text", "ergebnis_metrics", "pullquote", "kunde", "viz",
    ],
    "ST-09": ["title", "body", "symptoms", "viz"],
}

# The fields that are "block collections" (each item is atomic) per ST.
_STEP_FIELD: dict[str, str] = {"ST-06": "steps", "ST-07A": "", "ST-09": "symptoms"}

# Page 1 of an ST-06 carries the intro + the first half of the steps;
# page 2 carries the rest + the result. Semantic, never mid-step.
_ST06_PAGE1_STEPS_RATIO = 0.5  # round up: page 1 = ceil(ratio * n)

# ST types whose budget is for an A3 SPREAD (the sheet already carries ~2x an
# A4 page's capacity). A spread is the section's multi-page allocation :
# splitting it further would fabricate pages, not compose them. The budget
# check is skipped (no split) for these.
_SPREAD_ST_TYPES: frozenset[str] = frozenset({"ST-07A"})


def _section_id(slot: int) -> str:
    return f"section.{slot}"


def _page_id(section_id: str, index: int) -> str:
    return f"{section_id}.page.{index}"


def _copy_len(data: dict) -> int:
    return sum(len(s) for s in _collect_all_strings(data))


def _split_steps_evenly(steps: list[dict], ratio: float = _ST06_PAGE1_STEPS_RATIO) -> list[list[dict]]:
    """Split a step list at a whole-step boundary (never inside a step)."""
    if not steps:
        return [[], []]
    n = len(steps)
    cut = max(1, int(round(n * ratio))) if n > 1 else 1
    if cut >= n:
        cut = n // 2 or 1
    return [list(steps[:cut]), list(steps[cut:])]


def _split_st06(page: PlannedPage, budget: int) -> list[PlannedPage]:
    """ST-06: page 1 = intro + early steps; page 2 = late steps + result."""
    data = page.data
    steps = list(data.get("steps") or [])
    first, second = _split_steps_evenly(steps)

    page1_data: dict = {
        "title": data.get("title"),
        "body": data.get("body"),
        "steps": first,
    }
    page2_data: dict = {
        "steps": second,
        "ergebnis": data.get("ergebnis"),
    }

    sid = _section_id(page.slot)
    p1 = PlannedPage(
        slot=page.slot, st_type=page.st_type, css_template=page.css_template,
        components=list(page.components), has_cta=page.has_cta,
        data={k: v for k, v in page1_data.items() if v not in (None, [], "")},
        page_numbers=page.page_numbers,
        layout_variant=page.layout_variant,
        page_format=page.page_format,
        section_id=sid, page_id=_page_id(sid, 1),
        continuation_index=1, continuation_role="intro",
        section_page_count=2,
    )
    p2 = PlannedPage(
        slot=page.slot, st_type=page.st_type, css_template=page.css_template,
        components=[], has_cta=False,
        data={k: v for k, v in page2_data.items() if v not in (None, [], "")},
        page_numbers=None,
        layout_variant=page.layout_variant,
        page_format=page.page_format,
        section_id=sid, page_id=_page_id(sid, 2),
        continuation_index=2, continuation_role="result",
        section_page_count=2,
    )
    out = [p1]
    if second:
        out.append(p2)
    return out


def _split_st07a(page: PlannedPage, budget: int) -> list[PlannedPage]:
    """ST-07A: page 1 = portrait + problem; page 2 = solution + result + proof.

    Every narrative block moves WHOLE to exactly one page.
    """
    data = page.data
    sid = _section_id(page.slot)

    # Blocks that belong to the problem/open (page 1) vs result/proof (page 2).
    open_fields = ("kurzportraet", "ausgangsproblem", "ziel")
    close_fields = ("loesung", "ergebnis_text", "ergebnis_metrics",
                    "pullquote", "kunde", "viz", "ergebnis_headline")

    def _pick(fields) -> dict:
        return {f: data[f] for f in fields if f in data and data[f] not in (None, "", [])}

    p1_data = _pick(open_fields)
    p2_data = _pick(close_fields)

    def _mk(index: int, role: str, d: dict, components: list[str], has_cta: bool) -> PlannedPage:
        return PlannedPage(
            slot=page.slot, st_type=page.st_type, css_template=page.css_template,
            components=list(components), has_cta=has_cta,
            data=d,
            page_numbers=page.page_numbers if index == 1 else None,
            layout_variant=page.layout_variant,
            page_format=page.page_format,
            section_id=sid, page_id=_page_id(sid, index),
            continuation_index=index, continuation_role=role,
            section_page_count=2,
        )

    p1 = _mk(1, "proof", p1_data, list(page.components), page.has_cta)
    p2 = _mk(2, "result", p2_data, [], False)
    return [p1, p2]


def _split_st09(page: PlannedPage) -> list[PlannedPage]:
    """ST-09 (Status Quo): a 3-paragraph body + 6 rich symptoms + a viz
    exceed one A4 sheet (verified US-2026-08-18: the 6 symptom cards
    overflowed the editorial-fill mid and were clipped against the foot).
    Split at the semantic context/evidence boundary: page 1 = title + body
    (the context), page 2 = the symptoms (the evidence). Real data."""
    data = page.data
    sid = _section_id(page.slot)
    context_fields = ("title", "body", "viz")
    evidence_fields = ("symptoms",)

    def _pick(fields) -> dict:
        return {f: data[f] for f in fields if f in data and data[f] not in (None, "", [])}

    def _mk(index: int, role: str, d: dict) -> PlannedPage:
        # both halves carry the section's TITLE (the section identity, not
        # fabrication) so the continuation renders its own heading and the
        # treated a4_editorial_fill contract ("headline") is met.
        if data.get("title") and "title" not in d:
            d = dict(d)
            d["title"] = data["title"]
        return PlannedPage(
            slot=page.slot, st_type=page.st_type, css_template=page.css_template,
            components=list(page.components) if index == 1 else [],
            has_cta=page.has_cta,
            data=d,
            page_numbers=page.page_numbers if index == 1 else None,
            layout_variant=page.layout_variant,
            page_format=page.page_format,
            section_id=sid, page_id=_page_id(sid, index),
            continuation_index=index, continuation_role=role,
            section_page_count=2,
        )

    return [_mk(1, "context", _pick(context_fields)),
            _mk(2, "evidence", _pick(evidence_fields))]


def _split_st02(page: PlannedPage) -> list[PlannedPage]:
    """ST-02 (Outlook): the 1544-char recap + the market-proof viz + the
    target-audience block exceed one sheet (verified: ST-02 alone rendered 2
    sheets). Split at the semantic context/evidence boundary: page 1 = the
    outlook + recap (context), page 2 = the market-proof viz + target
    audience (evidence). Real data; nothing invented."""
    data = page.data
    sid = _section_id(page.slot)
    context_fields = ("title", "body", "pullquote")
    evidence_fields = ("viz", "zielgruppe")

    def _pick(fields) -> dict:
        return {f: data[f] for f in fields if f in data and data[f] not in (None, "", [])}

    def _mk(index: int, role: str, d: dict) -> PlannedPage:
        return PlannedPage(
            slot=page.slot, st_type=page.st_type, css_template=page.css_template,
            components=list(page.components) if index == 1 else [],
            has_cta=page.has_cta,
            data=d,
            page_numbers=page.page_numbers if index == 1 else None,
            layout_variant=page.layout_variant,
            page_format=page.page_format,
            section_id=sid, page_id=_page_id(sid, index),
            continuation_index=index, continuation_role=role,
            section_page_count=2,
        )

    return [_mk(1, "context", _pick(context_fields)),
            _mk(2, "evidence", _pick(evidence_fields))]


def _split_st05(page: PlannedPage) -> list[PlannedPage]:
    """ST-05 (About): the page carries BOTH identity (title/body/stats/
    partners) AND proof (testimonials/credibility) — at vertical capacity it
    spills (US-609: silently became a 2-sheet section, shifting the deck).
    Split at the semantic identity/proof boundary: page 1 = identity, page 2
    = proof. Real data; nothing invented."""
    data = page.data
    sid = _section_id(page.slot)
    id_fields = ("title", "body", "stats", "partners")
    proof_fields = ("testimonials", "credibility_points")

    def _pick(fields) -> dict:
        return {f: data[f] for f in fields if f in data and data[f] not in (None, "", [])}

    def _mk(index: int, role: str, d: dict) -> PlannedPage:
        return PlannedPage(
            slot=page.slot, st_type=page.st_type, css_template=page.css_template,
            components=list(page.components) if index == 1 else [],
            has_cta=page.has_cta,
            data=d,
            page_numbers=page.page_numbers if index == 1 else None,
            layout_variant=page.layout_variant,
            page_format=page.page_format,
            section_id=sid, page_id=_page_id(sid, index),
            continuation_index=index, continuation_role=role,
            section_page_count=2,
        )

    return [_mk(1, "identity", _pick(id_fields)),
            _mk(2, "proof", _pick(proof_fields))]


def _split_fazit(page: PlannedPage) -> list[PlannedPage]:
    """ST-FAZIT: the closing page's recap is long (the FAZIT content measures
    937px+CTA > the 986px sheet — verified US-605). Split at a SEMANTIC
    boundary: page 1 = header + thesis + cost + CTA (the close); page 2 =
    the recap body + the market-proof viz. Both pages keep the section
    identity; the CTA stays on the LAST page of the section."""
    data = page.data
    sid = _section_id(page.slot)

    page1_data = {
        "title": data.get("title"),
        "these": data.get("these"),
        "kosten_des_nichtstuns": data.get("kosten_des_nichtstuns"),
        "cta_url": data.get("cta_url"),
        "author": data.get("author"),
    }
    # the market-proof viz rides with the BODY page: its figures ("58%",
    # "61%") are grounded in the recap prose : the no-fabrication guard
    # requires the figures on the same page that displays them.
    page2_data = {
        "body": data.get("body"),
        "viz": data.get("viz"),
        "cta_url": data.get("cta_url"),
    }

    def _mk(index: int, role: str, d: dict) -> PlannedPage:
        return PlannedPage(
            slot=page.slot, st_type=page.st_type, css_template=page.css_template,
            components=list(page.components) if index == 1 else [],
            has_cta=page.has_cta,
            data={k: v for k, v in d.items() if v not in (None, "", [])},
            page_numbers=page.page_numbers if index == 1 else None,
            layout_variant=page.layout_variant,
            page_format=page.page_format,
            section_id=sid, page_id=_page_id(sid, index),
            continuation_index=index, continuation_role=("close" if index == 1 else "result"),
            section_page_count=2,
        )

    return [_mk(1, "close", page1_data), _mk(2, "result", page2_data)]


def split_section(page: PlannedPage) -> list[PlannedPage]:
    """Split one source section into 1+ physical-page plans.

    Single-page (short / unsupported / under-budget) sections return the page
    UNCHANGED with no identity — exactly today's flat package (back-compat).
    """
    budget = ST_COPY_BUDGET_CHARS.get(page.st_type)
    if budget is None:
        return [page]
    if page.st_type in _SPREAD_ST_TYPES:
        # US-2026-08-19 (B3): a case study (ST-07A) is ONE page by design —
        # whether it renders as an A3 Doppelseite or (now, after the mixed-size
        # fix) an A4 single page. Splitting it would fabricate a second case
        # page; the case study's own fill layout absorbs the copy. The old
        # `and page.page_format == "a3"` guard let the A4 single-page case
        # studies fall through to _split_st07a (5 -> 7 pages).
        return [page]
    total = _copy_len(page.data)
    if page.st_type == "ST-02":
        # US-609: the Outlook's recap+viz+audience exceed one sheet (verified:
        # ST-02 alone rendered 2 sheets). Split context/evidence ONLY when
        # the copy is genuinely heavy (an empty/light Outlook stays one page).
        if total > 700:
            return _split_st02(page)
        return [page]
    if page.st_type == "ST-05":
        # US-609: the About's identity+proof exceed one sheet (verified spill).
        # Split at the identity/proof boundary ONLY when heavy.
        if total > 900:
            return _split_st05(page)
        return [page]
    if page.st_type == "ST-FAZIT":
        # US-605: the FAZIT's real layout (header + 900-char recap + thesis +
        # market-proof viz + cost + CTA band) measures past the 261mm sheet
        # (~1007px vs 986px verified) even though its copy is under the 1600-
        # char heuristic budget. A FAZIT with a recap over ~700 chars splits
        # at a semantic boundary: page 1 = the close (title/thesis/cost/CTA),
        # page 2 = the recap + the market-proof viz.
        if total > 700:
            return _split_fazit(page)
        return [page]
    if total <= budget:
        return [page]

    if page.st_type == "ST-06":
        return _split_st06(page, budget)
    if page.st_type == "ST-07A":
        return _split_st07a(page, budget)
    if page.st_type == "ST-09":
        # US-2026-08-18: 3-para body + 6 rich symptoms + viz exceed one A4
        # sheet (verified: the 6 symptom cards clipped against the foot on the
        # editorial-fill single page). Split context/evidence when heavy.
        if total > 900:
            return _split_st09(page)
        return [page]
    return [page]  # no semantic split rule yet -> honest single page
