"""Director — reference selection, visual job, generator brief.

The missing organism cycle, wired into the real pipeline:

    page report JSON
      -> selector (Supabase catalog, report-driven)     [reference + rationale]
      -> visual job (deterministic, from page data)     [what the visual must DO]
      -> generator brief (reference style + page subject) [the fal prompt contract]
      -> reviewer metadata (job + argument + density)   [judge against the job]

Everything is deterministic and no-fabrication: the subject comes VERBATIM from
the page's structured data (kunde, ergebnis_metrics, headline), the visual job
follows the shape of the argument, and the reference's mechanism/devices supply
the style language. Nothing is invented.

Local fallback: when Supabase env vars are absent, the selector degrades to the
legacy quality-loop index (st_type-only) so the pipeline never breaks.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

# ---------------------------------------------------------------------------
# Visual job classification (deterministic, from the page's own data shape)
# ---------------------------------------------------------------------------

# ST-07A result-metric shapes -> the argument's visual job.
_TRANSFORM_HINTS = ("→", "->", "auf ", "zu ", "sank", "stieg", "reduziert")
_COMPLETION_HINTS = ("von ", "/", "automatisiert", "abgeschlossen")
_SCALE_HINTS = ("verdoppelt", "verdoppeln", "skalier", "wachstum", "kapazität", "kapazitaet")


def _job_for_case_study(data: dict) -> str:
    """What the case-study visual must make the reader understand.

    Reads the LEAD result metric (the hero figure the visual supports) + the
    headline: a before/after transformation (24 Std. -> Minuten), a completion
    (6 von 6), or a scale shift (capacity doubled). Falls back to the headline
    when the lead metric is prose.
    """
    metrics = data.get("ergebnis_metrics") or []
    headline = str(data.get("ergebnis_headline") or "").lower()
    lead = ""
    if metrics:
        first = metrics[0]
        lead = str(first.get("value", "") if isinstance(first, dict) else first).lower()
    if any(h in lead for h in _TRANSFORM_HINTS):
        return "transformation"
    if any(h in lead for h in _COMPLETION_HINTS):
        return "completion"
    if any(h in headline for h in _SCALE_HINTS) or any(h in lead for h in _SCALE_HINTS):
        return "scale"
    return "system"


_JOB_DEVICE_LANGUAGE: dict[str, str] = {
    "transformation": "a before/after transformation: the old manual state on one side, "
                      "the automated state on the other, connected by a clear motion arc",
    "completion": "completion: distinct working parts converging into one unified, "
                  "complete system",
    "scale": "scale: an expanding system that grows without adding more of the old "
             "manual work — more output from the same core",
    "system": "a coherent system: interconnected parts working as one organized whole",
}


def _subject_for_case_study(data: dict) -> str:
    """The visual SUBJECT, verbatim from the page data — never invented."""
    kunde = data.get("kunde") or {}
    name = str(kunde.get("name") or "") if isinstance(kunde, dict) else ""
    headline = str(data.get("ergebnis_headline") or "")
    return f"for {name}" if name else headline


def _evidence_figures(data: dict, max_figures: int = 3) -> list[str]:
    """Real figures the visual may reference (verbatim, capped)."""
    figures: list[str] = []
    for m in data.get("ergebnis_metrics") or []:
        value = str(m.get("value", "") if isinstance(m, dict) else m)
        if value and value not in figures:
            figures.append(value)
        if len(figures) >= max_figures:
            break
    return figures


# ---------------------------------------------------------------------------
# Director: the full decision for one page
# ---------------------------------------------------------------------------

def compose_visual_job(st_type: str, data: dict) -> str:
    """What this page's visual element must explain (one short phrase)."""
    if st_type == "ST-07A":
        return _job_for_case_study(data)
    if st_type == "ST-31":
        return "atmosphere"
    if st_type == "ST-09":
        return "status quo problem"
    return "support"


def compose_generator_brief(st_type: str, data: dict, *, brand_primary: str = "",
                            brand_accent: str = "", reference: dict | None = None,
                            visual_job: str = "") -> dict:
    """The fal prompt contract: subject + concept + style + negatives.

    subject  — verbatim page data (kunde, headline, figures)
    concept  — the visual job translated into a concrete scene description
    style    — the reference's mechanism/devices (when selected) + brand palette
    negative — what the image must NOT contain
    """
    job = visual_job or compose_visual_job(st_type, data)
    concept = _JOB_DEVICE_LANGUAGE.get(job, _JOB_DEVICE_LANGUAGE["system"])

    if st_type == "ST-07A":
        subject = _subject_for_case_study(data)
        figures = _evidence_figures(data)
        concept = f"Abstract editorial visualization {subject}: {concept}"
        if figures:
            concept += f" The scene evokes the figures {', '.join(figures)} without writing them as text."
    elif st_type == "ST-31":
        subject = str(data.get("phrase") or "a moment of calm in a demanding working world")
        concept = f"An atmospheric editorial full-bleed visual {subject}"
    else:
        subject = str(data.get("title") or data.get("headline") or "the page's central idea")
        concept = f"An editorial supporting visual {subject}: {concept}"

    style_parts: list[str] = []
    if reference:
        mech = str(reference.get("mechanism") or "")
        devices = str(reference.get("devices") or "")
        if mech:
            style_parts.append(f"composition inspired by a {mech} reference spread")
        if devices:
            style_parts.append(f"device language: {devices}")
    if brand_primary and brand_accent:
        style_parts.append(
            f"colour palette: deep {brand_primary} ground with {brand_accent} accent light"
        )
    style_parts.append("premium editorial print quality, refined geometry, soft depth")
    style = "; ".join(style_parts)

    negative = (
        "photorealistic people, faces, hands, text, words, letters, numbers, "
        "charts, graphs, screenshots, logos, watermark, mockup, UI, bright "
        "colours, clutter, gradients without structure"
    )
    return {
        "subject": subject,
        "concept": concept,
        "style": style,
        "negative": negative,
        "visual_job": job,
    }


def compose_rationale(st_type: str, reference: dict | None, visual_job: str) -> str:
    """WHY this reference was selected — the recorded decision."""
    if reference is None:
        return f"{st_type} has no matching reference in the catalog; page scored alone"
    return (
        f"selected {reference.get('report')} p{reference.get('page_no')} "
        f"(face {reference.get('face_index')}) for {st_type}: matches "
        f"{reference.get('format', 'a4')} format"
        + (f", {reference.get('density')} density" if reference.get("density") else "")
        + (f", {reference.get('mechanism')} mechanism" if reference.get("mechanism") else "")
        + f"; visual job '{visual_job}'"
    )


# ---------------------------------------------------------------------------
# Selector with Supabase-first, local-index fallback
# ---------------------------------------------------------------------------

def _legacy_select(st_type: str, k: int) -> list[dict]:
    """Local fallback: the legacy quality-loop index (st_type-only)."""
    index_path = ROOT / "research" / "quality_loop" / "references" / "index.json"
    if not index_path.exists():
        return []
    rows = json.loads(index_path.read_text(encoding="utf-8"))
    matching = [r for r in rows if r.get("st_type") == st_type]
    return matching[:k]


async def select_references(dsn: str | None, st_type: str, *,
                            format_: str | None = None, density: str | None = None,
                            k: int = 3, client_slug: str = "",
                            report_id: str = "", face_key: str = "") -> list[dict]:
    """Choose reference faces for a page.

    Supabase catalog first (report-driven: format/density weighting, and the
    client's OWN deck excluded — the output being judged is not the reference
    bar); legacy index fallback when no DSN. Each returned row is a ref_faces
    record.
    """
    if dsn:
        try:
            from supabase.catalog import selector_query

            return await selector_query(
                dsn, st_type, format_=format_, density=density, k=k,
                exclude_report=client_slug or None,
            )
        except Exception:
            return _legacy_select(st_type, k)
    return _legacy_select(st_type, k)


def director_dsn() -> str | None:
    """The Supabase pooler URL from env, or None (local fallback mode)."""
    return os.environ.get("SUPABASE_POOLER_URL") or None


def allocate_references(candidates_by_key: dict[str, list[dict]]) -> dict[str, dict | None]:
    """Assign DISTINCT references across pages (reference diversification).

    Each page brings its candidate list (k=3, already format/density ranked);
    the allocator greedily assigns the first candidate whose (report, page_no)
    anchor is not yet used, so the deck anchors on DIFFERENT Richard pages.
    When the pool is too small, remaining pages take their best candidate
    (never None while candidates exist — honest degradation).

    Returns {page_key: chosen_reference_or_None}.
    """
    allocation: dict[str, dict | None] = {}
    used_anchors: set[tuple[str, int]] = set()

    # pages with FEWER candidates first: they are the constrained ones and must
    # get first pick of the distinct anchors.
    for page_key in sorted(candidates_by_key, key=lambda k: len(candidates_by_key[k])):
        candidates = candidates_by_key.get(page_key) or []
        if not candidates:
            allocation[page_key] = None
            continue
        chosen = None
        for candidate in candidates:
            anchor = (str(candidate.get("report") or ""), int(candidate.get("page_no") or 0))
            if anchor not in used_anchors:
                chosen = candidate
                used_anchors.add(anchor)
                break
        if chosen is None:
            chosen = candidates[0]  # pool exhausted: best available, honest
        allocation[page_key] = chosen
    return allocation


async def select_diversified_references(dsn: str | None, *, st_type: str,
                                        page_keys: list[str],
                                        format_: str | None = None,
                                        client_slug: str = "") -> dict[str, dict | None]:
    """Query k=5 candidates per page, then allocate DISTINCT anchors.

    The pool must be LARGER than the page count for real diversification
    (k=3 gave only niklas 8/10/12 — buchagentur 5/6 were 4th/5th rank and
    unreachable). The allocator then spreads the deck across different
    Richard pages so five case studies never anchor on one reference.
    Falls back per-page to the legacy index when no DSN.
    """
    candidates_by_key: dict[str, list[dict]] = {}
    for page_key in page_keys:
        refs = await select_references(
            dsn, st_type, format_=format_, k=5,
            client_slug=client_slug, face_key=page_key,
        )
        candidates_by_key[page_key] = refs
    return allocate_references(candidates_by_key)
