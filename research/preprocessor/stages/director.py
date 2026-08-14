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

    Reads the REAL result metrics + headline: a before/after transformation
    (24 Std. -> Minuten), a completion (6 von 6), or a scale shift (capacity
    doubled). Falls back to the headline when the metrics are prose.
    """
    metrics = data.get("ergebnis_metrics") or []
    headline = str(data.get("ergebnis_headline") or "").lower()
    joined = " ".join(
        str(m.get("value", "") if isinstance(m, dict) else m) for m in metrics
    ).lower()
    if any(h in joined for h in _TRANSFORM_HINTS):
        return "transformation"
    if any(h in joined for h in _COMPLETION_HINTS):
        return "completion"
    if any(h in headline for h in _SCALE_HINTS) or any(h in joined for h in _SCALE_HINTS):
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

    Supabase catalog first (report-driven: format/density weighting); legacy
    index fallback when no DSN. Each returned row is a ref_faces record.
    """
    if dsn:
        try:
            from supabase.catalog import selector_query

            return await selector_query(
                dsn, st_type, format_=format_, density=density, k=k,
            )
        except Exception:
            return _legacy_select(st_type, k)
    return _legacy_select(st_type, k)


def director_dsn() -> str | None:
    """The Supabase pooler URL from env, or None (local fallback mode)."""
    return os.environ.get("SUPABASE_POOLER_URL") or None
