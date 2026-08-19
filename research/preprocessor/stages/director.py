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
    # IMAGE-TO-IMAGE instructions (binding, US-407): what grammar to PRESERVE
    # from the selected reference and what concrete subject to PLACE. Never
    # "evokes figures" abstractions — the edit model transforms the reference
    # raster, it does not imagine a scene from prose.
    "transformation": "preserve the reference spread's proof-panel grammar and "
                      "stat rhythm; place a calm abstract visualization of the "
                      "workflow transformation: distinct lanes on one side "
                      "converging into one organized operating system on the other",
    "completion": "preserve the reference's proof grammar; place distinct working "
                  "parts converging into one unified complete system",
    "scale": "preserve the reference's authority grammar; place an expanding "
             "system that grows without adding more manual work",
    "system": "preserve the reference's editorial grammar; place interconnected "
              "parts working as one organized whole",
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
        # IMAGE-TO-IMAGE instruction (binding, US-407): the reference raster's
        # TONE and PALETTE are preserved; its DATA PANELS are deliberately NOT
        # mirrored (panels invite chart-like cells — the experiment leaked
        # bar-chart shapes twice). The art is ONE flowing abstract band.
        concept = (
            f"Using the input reference image ONLY for its dark-navy tone, "
            f"amber accent light, and editorial refinement, create ONE purely "
            f"ABSTRACT flowing contextual band {subject}: {concept}. "
            f"Do NOT copy the reference's panel grid or columns. STRICTLY "
            f"ABSTRACT: no text, no words, no numbers, no labels, no icons, "
            f"no charts, no bars, no axes, no graphs, no UI, no panels, "
            f"no faces."
        )
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
    """Local fallback: the legacy quality-loop index (st_type-only).

    US-2026-08-19 (input-dependent-reference fix): (a) ROOT resolves to
    `research/`, so the old path `ROOT/"research"/"quality_loop"/...` became
    `research/research/...` and returned ZERO references; and (b) the index
    rows are `{deck, page_no, st_type, axes, png_path}` but the Director
    brief's `selected_reference` contract expects `{face_id, report,
    page_no, raster_uri, ...}`. Rows are now mapped to the brief's shape so
    every page's "which reference PDF it needs" actually lands. The index
    lives at `research/quality_loop/references/index.json`. """
    index_path = ROOT / "quality_loop" / "references" / "index.json"
    if not index_path.exists():
        return []
    rows = json.loads(index_path.read_text(encoding="utf-8"))
    matching = [r for r in rows if r.get("st_type") == st_type]
    out = []
    for r in matching[:k]:
        out.append({
            "face_id": f"{r.get('deck')}-{r.get('page_no')}",
            "report": r.get("deck"),
            "page_no": r.get("page_no"),
            "raster_uri": r.get("png_path"),
            "sha256": None,
            "devices": None,
            "mechanism": None,
            "density": (r.get("axes") or {}).get("density"),
            "st_type": r.get("st_type"),
        })
    return out


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


# ---------------------------------------------------------------------------
# US-606 — the REAL page brief (the Director contract object)
# ---------------------------------------------------------------------------

# Deterministic page-arc roles per st_type (the section's composition sequence).
_PAGE_ARC_BY_ST: dict[str, list[str]] = {
    "ST-07A": ["intro", "mechanism", "result"],
    "ST-06": ["intro", "mechanism", "result"],
    "ST-22": ["intro", "process", "result"],
    "ST-FAZIT": ["close", "result"],
    "ST-02": ["context", "evidence"],
    "ST-09": ["problem", "reassurance"],
    "ST-14": ["beliefs", "synthesis"],
    "ST-05": ["identity", "proof"],
    "ST-07B": ["essay", "insight"],
}

# Deterministic region roles per st_type (layout regions the renderer can
# consume; bounds are fractions of the sheet — normalized, brand-agnostic).
_REGION_PLAN_BY_ST: dict[str, list[dict]] = {
    "ST-07A": [
        {"region": "left_story", "role": "narrative", "bounds": [0.0, 0.0, 0.56, 1.0]},
        {"region": "right_proof", "role": "full_height_data_panel", "bounds": [0.58, 0.0, 1.0, 1.0]},
    ],
    "ST-06": [
        {"region": "header", "role": "intro", "bounds": [0.0, 0.0, 1.0, 0.22]},
        {"region": "mechanism", "role": "mechanism", "bounds": [0.0, 0.24, 1.0, 0.55]},
        {"region": "result", "role": "result", "bounds": [0.0, 0.77, 1.0, 1.0]},
    ],
    "ST-22": [
        {"region": "banner", "role": "intro", "bounds": [0.0, 0.0, 1.0, 0.18]},
        {"region": "process", "role": "process", "bounds": [0.0, 0.20, 1.0, 0.70]},
        {"region": "cta", "role": "result", "bounds": [0.0, 0.72, 1.0, 1.0]},
    ],
    "ST-FAZIT": [
        {"region": "close", "role": "close", "bounds": [0.0, 0.0, 1.0, 0.70]},
        {"region": "cta", "role": "cta", "bounds": [0.0, 0.72, 1.0, 1.0]},
    ],
}

# Renderer-native devices the page may host (the renderer owns ALL data
# relationships; fal never draws numbers).
_RENDERER_DEVICES_BY_ST: dict[str, list[str]] = {
    "ST-07A": ["transform_arrow", "grouped_bars", "stat_stack", "completion_ring"],
    "ST-06": ["step_cascade", "stat_strip", "stat_callout", "bar_chart"],
    "ST-22": ["horizontal_flow", "timeline", "stat_strip"],
    "ST-FAZIT": ["radial_cluster", "mega_numeral", "url_band", "signoff"],
    "ST-02": ["radial_cluster", "stat_strip"],
    "ST-09": ["mega_numeral", "stat_strip", "numbered_block"],
    "ST-14": ["concept_diagram", "stat_strip", "numbered_block"],
    "ST-05": ["stat_strip", "testimonial_cards", "logo_wall"],
    "ST-07B": ["key_insight", "mega_numeral"],
}


def must_show_figures(st_type: str, data: dict, max_figures: int = 3) -> list[str]:
    """The VERBATIM figures the page's visual must show (never invented).

    Reads the page's own structured data (metrics values, diagram figures,
    stats). Every returned figure appears verbatim in the page data.
    """
    figs: list[str] = []
    for m in data.get("ergebnis_metrics") or []:
        v = str(m.get("value", "") if isinstance(m, dict) else m)
        if v and v not in figs:
            figs.append(v)
        if len(figs) >= max_figures:
            return figs
    stats = data.get("stats") or data.get("ergebnis_stats") or []
    for s in stats:
        v = str(s.get("value", "") if isinstance(s, dict) else s)
        if v and v not in figs:
            figs.append(v)
        if len(figs) >= max_figures:
            return figs
    return figs


def _must_not_imply(st_type: str) -> list[str]:
    """What the page's visual must NOT imply (deterministic, brand-agnostic)."""
    return ["new metric", "fake interface", "real customer photograph", "price"]


def compose_page_brief(
    *,
    st_type: str,
    data: dict,
    client_slug: str,
    report_id: str,
    page_key: str,
    section_id: str,
    reference: dict | None = None,
    continuation_role: str = "",
) -> dict:
    """The ONE Director page brief per physical page (US-606, contract §3).

    Deterministic + no-fabrication: must_show is VERBATIM page data;
    page_arc/region_plan/renderer_devices come from the st_type tables; the
    selected reference (when provided) is recorded with its identity.
    """
    job = compose_visual_job(st_type, data)
    arc_roles = _PAGE_ARC_BY_ST.get(st_type, ["intro", "result"])
    regions = _REGION_PLAN_BY_ST.get(st_type, [
        {"region": "main", "role": "main", "bounds": [0.0, 0.0, 1.0, 1.0]},
    ])
    if continuation_role:
        # a continuation page's arc/regions narrow to its own role
        arc_roles = [r for r in arc_roles if r == continuation_role] or [continuation_role]
        regions = [r for r in regions if r["role"] == continuation_role] or regions

    brief = {
        "client_slug": client_slug,
        "report_id": report_id,
        "page_key": page_key,
        "section_id": section_id,
        "st_type": st_type,
        "selected_reference": (
            {
                "face_id": reference.get("face_id"),
                "report": reference.get("report"),
                "page_no": reference.get("page_no"),
                "raster_uri": reference.get("raster_uri"),
                "sha256": reference.get("sha256"),
                "anatomy": {
                    "regions": [],
                    "devices": str(reference.get("devices") or "").split(","),
                    "mechanism": reference.get("mechanism"),
                    "density": reference.get("density"),
                },
            }
            if reference else None
        ),
        "rationale": compose_rationale(st_type, reference, job),
        "visual_job": job,
        "must_show": must_show_figures(st_type, data),
        "must_not_imply": _must_not_imply(st_type),
        "page_arc": [{"page": i + 1, "role": r} for i, r in enumerate(arc_roles)],
        "region_plan": regions,
        "renderer_devices": _RENDERER_DEVICES_BY_ST.get(st_type, []),
    }
    return brief
