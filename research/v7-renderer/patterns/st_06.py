"""Pattern for ST-06 — MECHANISM / how-it-works (Plan B rebuild, grammar P-8).

DATA-PREP ONLY. This module reads the package `page` dict, shapes a context
dict, and renders `templates/st_06.html.jinja` (which composes the atomic macro
library on a token-themed layout, `styles/st_06.css`). The returned
PageFragment.html is that rendered string; the .css is the layout sheet.

WHY this shape (vs the old hand-built f-string CSS):
  - Brand-agnostic by construction: the template + layout CSS contain ZERO
    client literals (no hex, no font family, no client name). Colors + fonts
    arrive at render time via the token `:root` (compile_tokens) — the heading
    sizes off `var(--font-display)`, which resolves to the SERIF face when the
    brand's axis is headline_type=serif (the apex deck IS serif).
  - The device LOOK (step_card / horizontal_flow / bar_chart / stat_callout_card
    / dark_recap_panel) lives in the `c-` classes (components.css, already in the
    shared <head>); this pattern only feeds the macros DATA and positions them.

DATA CONTRACT (preserved from the prior pattern — fields on page["data"]):
  title, body (intro prose), steps[] (list of {title, body} dicts OR plain
  strings — the mechanism stages), ergebnis (the result/recap prose for the dark
  "Das Ergebnis" panel). OPTIONAL: metrics[] / bars[] (list of {label, value}
  dicts) for the token-drawn bar chart — absent in the apex fixture, so the chart
  gracefully does not render and the page leads with the core devices.

This page is the RICHEST interior. It composes the CORE devices always present:
  - numbered STEP CARDS (the mechanism stages in detail), 2-up,
  - a HORIZONTAL FLOW diagram (Schritt 1 → N — a title-only at-a-glance overview
    derived from the same steps), and
  - a solid dark "Das Ergebnis" RECAP panel (dark_recap_panel, --color-ink fill).
Plus, when the data supplies them (graceful otherwise):
  - a floated STAT-CALLOUT card pulled from the result metric (a percentage in
    the ergebnis text, e.g. "30-50%"), and
  - a token-drawn BAR CHART from metrics[]/bars[].

The German kicker (Methodik), the flow label (Der Ablauf) and the recap label
(Das Ergebnis) are CONTENT labels for this report TYPE (not client-specific) —
module constants passed to the template as data.

History (Plan B): replaced the prior monolithic f-string render (NUMBERED_STEP_CARD_CSS
from _components.py with hardcoded color + font-family literals baked into the
pattern) with this data-prep → Jinja-template split. Earlier history in git.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Allow flat imports from the chassis package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from preprocess import preprocess_body  # noqa: E402
from templating import get_env  # noqa: E402
from patterns.base import PageFragment, RenderContext  # noqa: E402

# Layout CSS lives in a sibling sheet so it's auditable by the brand-agnostic
# guard (tokens only). Read once at import; returned verbatim as fragment.css.
_CSS_PATH = Path(__file__).resolve().parent.parent / "styles" / "st_06.css"
_CSS = _CSS_PATH.read_text(encoding="utf-8")

# Content labels for this report TYPE (not client-specific).
_KICKER = "Methodik"
_FLOW_LABEL = "Der Ablauf"
_RECAP_LABEL = "Das Ergebnis"

# A percentage range / figure in the result prose (e.g. "30-50%", "61%") that we
# surface as the floated stat-callout — a real number from the data, not invented.
_PCT_RE = re.compile(r"\d+(?:[.,]\d+)?(?:\s*[-–]\s*\d+(?:[.,]\d+)?)?\s*%")

# Strip a long flow-box title down to its FIRST clause (before "und"/"-"/",") so
# the 1→N overview strip stays scannable; the full title lives on the step card.
def _step_fields(it) -> tuple[str, str]:
    """A step is a {title, body} dict or a plain string (body-only)."""
    if isinstance(it, dict):
        return it.get("title", ""), it.get("body", "")
    return "", str(it)


def _flow_title(title: str) -> str:
    """Shorten a step title to its leading clause for the compact flow strip.

    The detailed step card keeps the full title; the flow box only needs a short
    label (e.g. "Workflow-Audit und Engpass-Diagnose" → "Workflow-Audit"). Splits
    on the first " und "/"&"/dash/comma; falls back to the whole (short) title.
    """
    if not title:
        return ""
    parts = re.split(r"\s+und\s+|\s+&\s+|\s*[–—-]\s*|,", title, maxsplit=1)
    head = (parts[0] if parts else title).strip()
    return head or title.strip()


def _stat_callout(ergebnis: str) -> dict | None:
    """Pull a percentage figure out of the result prose for a floated stat card.

    Returns {value, label} (a real number from the data) or None when there is no
    parseable figure — the card is then omitted (graceful, no invented metric).
    """
    m = _PCT_RE.search(ergebnis or "")
    if not m:
        return None
    value = re.sub(r"\s+", "", m.group())  # tidy "30 - 50 %" → "30-50%"
    return {"value": value, "label": "Effizienzgewinn"}


def _bars(d: dict) -> list[dict]:
    """Optional bar-chart rows from metrics[]/bars[] ({label, value} dicts OR
    'label: value' strings). Absent in the apex fixture → [] → chart not rendered.
    """
    bars: list[dict] = []
    for b in (d.get("bars") or d.get("metrics") or []):
        if isinstance(b, dict):
            label, value = b.get("label", ""), b.get("value", "")
        elif isinstance(b, str) and ":" in b:
            label, value = (s.strip() for s in b.split(":", 1))
        else:
            label, value = "", str(b)
        if label or value:
            bars.append({"label": label, "value": value})
    return bars


def render(page: dict, ctx: RenderContext) -> PageFragment:
    """Render the ST-06 mechanism page as a PageFragment.

    Data-prep → render templates/st_06.html.jinja. Head-level CSS lives in the
    shared head (assembler); this returns only the page body markup + the
    ST-06-scoped layout CSS.
    """
    d: dict = page.get("data") or {}

    # ---- mechanism stages → numbered step cards + a compact flow overview ----
    steps: list[dict] = []
    flow_steps: list[dict] = []
    for i, it in enumerate(d.get("steps") or [], start=1):
        title, body = _step_fields(it)
        steps.append({
            "n": i,
            "title": title,
            "body_html": preprocess_body(body),
        })
        flow_steps.append({"n": i, "title": _flow_title(title)})

    ergebnis = d.get("ergebnis", "")

    # ---- data-driven chart SVG(s): the pre-processor extracts chart specs onto
    # page["charts"] and appends a brand-styled SVG per spec to page["components"]
    # (the tail). When present they render in the chart region INSTEAD of the
    # ad-hoc token bar; absent → fall back to the old metrics[]/bars[] bar. ----
    chart_svgs = ctx.chart_svgs(page)

    # US-704 (2026-08-22): NON-chart generated component SVGs (e.g. the
    # preprocessor's data-driven "PROZESS · MECHANIK" step-flow diagram on
    # slot 16) are stored in page["components"] but were never hosted — the
    # template had a host for dmc:chart-marked chart SVGs only, so this
    # diagram sat produced-but-invisible in the fixture. chart_svgs already
    # selects every component whose file carries the dmc:chart sentinel; we
    # now ALSO resolve the remaining components (no sentinel = a data diagram,
    # not a chart) and give them a host below. Dedup is by the SAME sentinel
    # chart_svgs uses: a component that is already a chart is skipped.
    _components: list[str] = []
    for rel in (page.get("components") or []):
        if not isinstance(rel, str) or not rel:
            continue
        svg = ctx.resolve_component(rel)
        if svg and svg.strip() and "dmc:chart" not in svg:
            _components.append(svg)

    # data-viz PRESET layer: data['viz'] is a list of {preset, …} specs the
    # curation step wrote (verbatim figures / step titles). Coerce to None unless
    # a non-empty list so the template renders exactly as before when absent
    # (graceful). The template renders the dispatch via the shared viz macro
    # (ST-07A pattern). On ST-06 a PROCESS preset (step_cascade) visualizes the
    # same mechanism stages the step cards already carry.
    viz = d.get("viz")
    viz = viz if isinstance(viz, list) and viz else None

    # US-604: continuation-role awareness. The ST-06 section may span two
    # physical pages (US-603 planner): page 1 = intro + early steps, page 2 =
    # late steps + result. Each page renders as a FULL composition (the intro
    # page carries an explicit continuation cue; the result page carries the
    # recap). A single-page ST-06 has no role -> legacy markup unchanged.
    continuation_role = str(page.get("continuation_role") or "").strip()
    continuation_role = (
        continuation_role if continuation_role in ("intro", "result") else ""
    )

    # US-608: on the INTRO continuation the slice carries the mechanism body
    # (no ergebnis) — bind the body's OWN real figure as the page's stat so
    # the page displays a bound data point (the reviewer requires one). The
    # figure is VERBATIM in the slice's copy; the stat is suppressed when no
    # figure exists (graceful, no fabrication).
    _intro_stat = None
    if not ergebnis and continuation_role == "intro":
        _intro_stat = _stat_callout(str(d.get("body") or ""))

    template = get_env().get_template("st_06.html.jinja")
    html = template.render(
        kicker=_KICKER,
        title=d.get("title", ""),
        intro_html=preprocess_body(d.get("body", "")),
        stat_callout=_stat_callout(ergebnis) or _intro_stat,
        flow_label=_FLOW_LABEL if flow_steps else "",
        flow_steps=flow_steps,
        steps=steps,
        chart_label="Vorher / Nachher",
        chart_svgs=chart_svgs,
        components=_components,
        bars=_bars(d),
        recap_label=_RECAP_LABEL if ergebnis else "",
        recap_html=preprocess_body(ergebnis),
        viz=viz,
        continuation_role=continuation_role,
        # US-607: the physical-page plan (page N of M) for continuation
        # furniture — the template renders a 'Seite N / M' marker when the
        # section spans multiple pages.
        page_plan={
            "page_id": page.get("page_id"),
            "section_id": page.get("section_id"),
            "continuation_index": page.get("continuation_index") or 1,
            "section_page_count": page.get("section_page_count") or 1,
        },
        # the page's diagram proof (plan_diagrams output — real data, e.g. the
        # stat_callout figure). Rendered on the RESULT continuation so the page
        # carries its full data payload (the vision audit flagged the dead band
        # above the recap).
        diagram=d.get("diagram") if isinstance(d.get("diagram"), dict) else None,
    )
    return PageFragment(html=html, css=_CSS)
