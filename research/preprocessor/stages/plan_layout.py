"""Stage 7 — layout planning.

Verifies the validated page array against grammar §1.2 (FIXED slots,
CTA cadence, Atemseite rhythm) and §1.4 (case-study count), assigns a
CSS template name per page, and attaches the SVG components produced
by Stage 6.

Output: a `LayoutPlan` object containing:
  - `pages`               — list of `PlannedPage` (slot, st_type,
                            css_template, components, has_cta, data)
  - `page_count`          — len(pages)
  - `page_count_target`   — from ReportMeta
  - `warnings`            — strings, never raises
  - `cta_positions`       — slot numbers that carry a CTA element
  - `breathing_positions` — slot numbers that are Atemseite (ST-31/ST-32)

The render endpoint serialises a thin view (LayoutPlanSummary) into
JSON; the full plan (with SVG strings and page data) is held in memory
for Stage 8 to consume.

Why warnings, not errors: Stage 1 already runs hard semantic checks
(page count, case study count, FIXED slots) and rejects with errors
when something is critically wrong. Stage 7's job is layout discipline
— surfaces gaps Richard's QA can fix in content rather than blocking
the render.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

# ST type → CSS template name (renderer pattern file). Generic for
# unknown types so we never fail the render — Stage 8 + the renderer
# can decide whether to fall back to a default pattern.
ST_TO_TEMPLATE: dict[str, str] = {
    "ST-01": "cover",
    "ST-02": "outlook",
    "ST-03": "cta_hard",
    "ST-05": "about",
    "ST-06": "mechanism",
    "ST-07A": "case_study",
    "ST-07B": "theory",
    "ST-08": "faq",
    "ST-09": "status_quo",
    "ST-14": "false_beliefs",
    "ST-22": "collaboration",
    "ST-31": "atemseite",
    "ST-32": "breathing",
    "ST-FAZIT": "summary",
}

# Page types that count as "breathing" / Atemseite — light content,
# the rest of the report needs them as relief from dense pages.
BREATHING_TYPES: frozenset[str] = frozenset({"ST-31", "ST-32"})

# Page types that typically host a CTA element. ST-03 is always a hard
# CTA; ST-22 (Collaboration) and ST-08 (FAQ) frequently pair with one.
CTA_TYPES: frozenset[str] = frozenset({"ST-03", "ST-22", "ST-08"})

# Threshold for the "stretch of dense pages without breathing" warning.
DENSE_RUN_LIMIT = 8

# ST types whose renderer supports a "fill" layout variant and which should
# DEFAULT to it (the sparse "standard" under-fills the sheet). Each of these
# implements a full-height authority/timeline composition (the renderer clamps
# unknown variants), so defaulting them to "fill" kills the dead bottom band the
# "standard" layout leaves. Other ST types only get a layout_variant if the input
# page explicitly asks for one — we never force a variant on them.
FILL_DEFAULT_TYPES: frozenset[str] = frozenset(
    {"ST-07A", "ST-07B", "ST-22", "ST-FAZIT"}
)

# Accepted layout-variant values (an unrecognised explicit hint is ignored
# rather than written through, so a typo can't silently break the renderer).
_VALID_LAYOUT_VARIANTS: frozenset[str] = frozenset(
    {"standard", "fill", "casestudy_hero"}
)

# Layout variants whose design assumes a WIDE (A3-landscape) sheet. When a
# page carries one of these, the planner stamps page_format="a3" so the
# assembler routes the page to the a3-landscape named @page (the legacy path
# already honours package page_format; casestudy_hero is the A3 "Doppelseite"
# spread model Richard uses for case studies).
_SPREAD_LAYOUT_VARIANTS: frozenset[str] = frozenset({"casestudy_hero"})


# ─────────────────────────────────────────────────────────────────────────────
# In-memory dataclasses (NOT serialised to JSON — Stage 8 consumes these)
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class PlannedPage:
    """One page, enriched with rendering metadata + SVG components.

    A logical report SECTION may own multiple physical pages (user directive:
    "use as many pages as it requires"). When a section expands, each planned
    page carries identity fields (section_id / page_id / continuation_index /
    continuation_role / section_page_count). All default to None: a
    single-page section stays exactly today's flat one-slot-one-page record
    (back-compat — no identity is written to the package).
    """

    slot: int
    st_type: str
    css_template: str
    components: list[str]    # SVG strings from Stage 6
    has_cta: bool
    data: dict               # original page data, passed through
    page_numbers: Optional[str] = None   # folio text for the renderer (R1)
    # Per-page layout-variant hint for the renderer. None → not written into the
    # package (renderer falls back to its own default, back-compat). For ST-07A
    # this is set to an explicit hint if the page provides one, else "fill".
    layout_variant: Optional[str] = None
    # Per-page sheet format ("a3" for spread variants, else None → renderer
    # keeps its default A4). Written into the package when not None.
    page_format: Optional[str] = None
    # ---- US-602 section/physical-page identity (all None = single page) ----
    section_id: Optional[str] = None        # e.g. "section.16"
    page_id: Optional[str] = None           # e.g. "section.16.page.2"
    continuation_index: Optional[int] = None  # 1-based position in the section
    continuation_role: Optional[str] = None   # intro|mechanism|proof|result|close
    section_page_count: Optional[int] = None  # total physical pages the section owns


@dataclass
class LayoutPlan:
    """Stage 7 output. Heavy fields (`pages[].components`, `pages[].data`)
    are kept in memory for Stage 8 — the JSON response only sees the
    `LayoutPlanSummary` view via `to_summary()`.
    """

    pages: list[PlannedPage]
    page_count: int
    page_count_target: int
    warnings: list[str] = field(default_factory=list)
    cta_positions: list[int] = field(default_factory=list)
    breathing_positions: list[int] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _unpack(page: Any) -> tuple[int, str, dict]:
    """Normalise a page (dict or Pydantic ReportPage) → (slot, type, data)."""
    if isinstance(page, dict):
        slot = int(page["slot"])
        st_type = str(page["type"])
        data = page.get("data") or {}
        return slot, st_type, data if isinstance(data, dict) else {}
    # Pydantic model
    data = getattr(page, "data", {}) or {}
    return int(page.slot), str(page.type), data if isinstance(data, dict) else {}


def _page_numbers(page: Any) -> Optional[str]:
    """Extract page_numbers from a dict or Pydantic ReportPage (None if absent)."""
    if isinstance(page, dict):
        val = page.get("page_numbers")
    else:
        val = getattr(page, "page_numbers", None)
    return str(val) if val is not None else None


def _explicit_layout_variant(page: Any, data: dict) -> Optional[str]:
    """Read an explicit per-page layout-variant hint, if the input page carries
    one. Accepts it on the page top-level (`page.layout_variant` /
    `page["layout_variant"]`) OR inside the page `data` block
    (`data["layout_variant"]`). Returns the hint only if it is a recognised
    value; an unknown/typo'd value returns None (ignored, never written through).
    """
    if isinstance(page, dict):
        hint = page.get("layout_variant")
    else:
        hint = getattr(page, "layout_variant", None)
    if hint is None and isinstance(data, dict):
        hint = data.get("layout_variant")
    if isinstance(hint, str) and hint in _VALID_LAYOUT_VARIANTS:
        return hint
    return None


def _resolve_layout_variant(
    st_type: str, explicit: Optional[str],
) -> Optional[str]:
    """Layout-variant policy for one page.

    - explicit hint present  → honour it (any ST type).
    - no hint, ST is a fill-default type (ST-07A) → "fill".
    - otherwise              → None (don't force a variant; renderer defaults).
    """
    if explicit is not None:
        return explicit
    if st_type in FILL_DEFAULT_TYPES:
        return "fill"
    return None


def _has_cta_element(st_type: str, data: dict) -> bool:
    """Heuristic: page carries a CTA if it's a CTA-host ST type OR its
    data block contains a `cta` / `cta_block` / `cta_url` key.
    """
    if st_type in CTA_TYPES:
        return True
    if any(k in data for k in ("cta", "cta_block", "cta_url", "cta_text")):
        return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────


def plan_layout(
    pages: list[Any],
    components: dict[int, list[str]],
    page_count_target: int,
) -> LayoutPlan:
    """Verify structural rules, enrich pages with rendering metadata.

    `pages` may be a list of dicts or Pydantic ReportPage instances.
    `components` is Stage 6's output ({slot: [svg, ...]}).

    Returns a LayoutPlan with warnings (never raises).
    """
    planned: list[PlannedPage] = []
    warnings: list[str] = []
    cta_positions: list[int] = []
    breathing_positions: list[int] = []

    # Pre-walk: enrich each page
    normalised: list[tuple[int, str, dict]] = [_unpack(p) for p in pages]
    page_numbers_list: list[Optional[str]] = [_page_numbers(p) for p in pages]

    # F: CSS template assignment + G: component attachment
    for raw_page, (slot, st_type, data), page_numbers in zip(
        pages, normalised, page_numbers_list
    ):
        css_template = ST_TO_TEMPLATE.get(st_type, "generic")
        if css_template == "generic":
            warnings.append(
                f"slot {slot}: unknown ST type {st_type!r} — falling back to "
                f"'generic' template"
            )

        has_cta = _has_cta_element(st_type, data)
        if has_cta:
            cta_positions.append(slot)
        if st_type in BREATHING_TYPES:
            breathing_positions.append(slot)

        # Layout-variant policy (per-page hint → renderer). ST-07A defaults to
        # "fill"; any ST type honours an explicit page hint; other types get
        # None (not written into the package → renderer keeps its own default).
        layout_variant = _resolve_layout_variant(
            st_type, _explicit_layout_variant(raw_page, data)
        )

        # Sheet format: spread variants are A3-designed (Richard's
        # "Doppelseite" model) → stamp a3 so the assembler routes them to the
        # wide sheet; everything else stays A4 (renderer default).
        page_format = (
            "a3" if layout_variant in _SPREAD_LAYOUT_VARIANTS else None
        )

        planned.append(PlannedPage(
            slot=slot,
            st_type=st_type,
            css_template=css_template,
            components=list(components.get(slot, ())),
            has_cta=has_cta,
            data=data,
            page_numbers=page_numbers,
            layout_variant=layout_variant,
            page_format=page_format,
        ))

    # US-603: section pagination — a section whose copy exceeds its per-ST
    # capacity expands into multiple physical-page plans at semantic
    # boundaries (split_section). Each expanded page carries US-602 identity
    # (section_id / continuation_index / continuation_role). Single-page
    # sections are returned UNCHANGED (back-compat: the flat one-slot-one-
    # sheet package). Imported lazily: plan_section_pages imports PlannedPage
    # from THIS module, so a top-level import would be circular.
    from stages.plan_section_pages import split_section

    expanded: list[PlannedPage] = []
    for pp in planned:
        expanded.extend(split_section(pp))
    planned = expanded

    page_count = len(planned)

    # E: page-count alignment (physical pages vs the soft target). The target
    # is a LOGICAL-section count; expanded sections (US-603) legitimately push
    # the physical count above it — that is the user's multi-page directive,
    # so the warning is informational, never a block.
    if page_count != page_count_target:
        warnings.append(
            f"page count mismatch: {page_count} physical pages planned, "
            f"target is {page_count_target} (a section may have expanded — "
            f"allowed by the multi-page directive)"
        )

    # A: FIXED slots
    if planned:
        first = planned[0]
        if first.st_type != "ST-01":
            warnings.append(
                f"slot 1 should be ST-01 (Cover); got {first.st_type!r}"
            )
        last = planned[-1]
        if last.st_type != "ST-03":
            warnings.append(
                f"final slot should be ST-03 (Hard CTA with QR); "
                f"got {last.st_type!r}"
            )

    # B: case-study count
    case_studies = [p for p in planned if p.st_type == "ST-07A"]
    if len(case_studies) < 3:
        warnings.append(
            f"only {len(case_studies)} ST-07A case studies — grammar §1.4 "
            f"requires at least 3"
        )

    # B (continued): ST-07A without adjacent ST-07B
    type_by_slot = {p.slot: p.st_type for p in planned}
    for cs in case_studies:
        next_st = type_by_slot.get(cs.slot + 1)
        if next_st != "ST-07B":
            warnings.append(
                f"slot {cs.slot} (ST-07A) is not followed by an adjacent "
                f"ST-07B (next slot is {next_st!r})"
            )

    # C: CTA cadence — needs at least one CTA between S3 and the final
    # slot (not counting S1, S2, or the final slot itself)
    mid_cta_present = any(
        2 < slot < page_count
        for slot in cta_positions
    )
    if not mid_cta_present and page_count > 4:
        warnings.append(
            f"no CTA element found between slot 3 and slot {page_count - 1} "
            f"— grammar §1.2 wants a mid-report CTA around S9 and/or S18"
        )

    # D: Atemseite rhythm — adjacency check
    for i in range(len(breathing_positions) - 1):
        if breathing_positions[i + 1] == breathing_positions[i] + 1:
            warnings.append(
                f"breathing pages at slots {breathing_positions[i]} and "
                f"{breathing_positions[i + 1]} are adjacent — Atemseite "
                f"should be spaced out, not paired"
            )

    # D (continued): stretch of dense pages
    dense_run = 0
    dense_run_start = None
    for p in planned:
        if p.st_type in BREATHING_TYPES:
            dense_run = 0
            dense_run_start = None
        else:
            if dense_run == 0:
                dense_run_start = p.slot
            dense_run += 1
            if dense_run > DENSE_RUN_LIMIT:
                warnings.append(
                    f"stretch of {dense_run}+ consecutive dense pages starting "
                    f"at slot {dense_run_start} — insert an Atemseite "
                    f"(ST-31/ST-32) for relief"
                )
                # Reset to avoid duplicate-warn for the same run
                dense_run = 0
                dense_run_start = None

    return LayoutPlan(
        pages=planned,
        page_count=page_count,
        page_count_target=page_count_target,
        warnings=warnings,
        cta_positions=cta_positions,
        breathing_positions=breathing_positions,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Serialisation helper for the /render response
# ─────────────────────────────────────────────────────────────────────────────


def layout_plan_to_summary(plan: LayoutPlan) -> dict:
    """Build the LayoutPlanSummary-shaped dict for /render JSON.

    Excludes the heavy SVG strings and original page `data`. The
    response advertises `component_count` per page; the actual SVG
    strings live in `plan.pages[i].components` in memory.
    """
    return {
        "page_count": plan.page_count,
        "page_count_target": plan.page_count_target,
        "cta_positions": plan.cta_positions,
        "breathing_positions": plan.breathing_positions,
        "pages": [
            {
                "slot": p.slot,
                "st_type": p.st_type,
                "css_template": p.css_template,
                "has_cta": p.has_cta,
                "component_count": len(p.components),
            }
            for p in plan.pages
        ],
        "warnings": list(plan.warnings),
    }
