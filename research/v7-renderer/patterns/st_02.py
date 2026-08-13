"""Pattern for ST-02 — OUTLOOK / "what this report is about" (Plan B rebuild,
grammar P-2).

DATA-PREP ONLY. This module reads the package `page` dict, shapes a context
dict, and renders `templates/st_02.html.jinja` (which composes the atomic macro
library on a token-themed layout, `styles/st_02.css`). The returned
PageFragment.html is that rendered string; the .css is the layout sheet.

WHY this shape (vs the old hand-built f-string CSS):
  - Brand-agnostic by construction: the template + layout CSS contain ZERO
    client literals (no hex, no font family, no client name). Colors + fonts
    arrive at render time via the token `:root` (compile_tokens) — the
    question-headline sizes off `var(--font-display)`, which resolves to the
    SERIF face when the brand's axis is headline_type=serif (the apex deck IS
    serif). Set against the sans `var(--font-body)` two-column prose, that
    serif/sans pairing is the §18 contrast.
  - The device LOOK (callout_panel tint fill + check_list accent check glyphs)
    lives in the `c-` classes (components.css, already in the shared <head>);
    this pattern only feeds the macros DATA and positions them.

DATA CONTRACT (preserved from the prior pattern — fields on page["data"]):
  title (the question-headline), body (intro prose, markdown), zielgruppe[] (a
  list of audience-qualifier strings for the check-list panel). Plain-string or
  absent fields degrade gracefully (no headline / no body / no panel).

The German eyebrow kicker (Ausblick) and the audience-panel label (Zielgruppe
des Reports) are CONTENT labels for this report TYPE (not client-specific) —
module constants passed to the template as data.

History (Plan B): replaced the prior monolithic f-string render (hand-written
.ol-* CSS with hardcoded color + font-family literals baked into the pattern)
with this data-prep → Jinja-template split. Earlier history documented in git.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow flat imports from the chassis package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from preprocess import preprocess_body  # noqa: E402
from templating import get_env  # noqa: E402
from patterns.base import PageFragment, RenderContext  # noqa: E402

# Layout CSS lives in a sibling sheet so it's auditable by the brand-agnostic
# guard (tokens only). Read once at import; returned verbatim as fragment.css.
_CSS_PATH = Path(__file__).resolve().parent.parent / "styles" / "st_02.css"
_CSS = _CSS_PATH.read_text(encoding="utf-8")

# Content labels for this report TYPE (not client-specific).
_KICKER = "Ausblick"
_ZG_LABEL = "Zielgruppe des Reports"
_TK_LABEL = "Was Sie mitnehmen"


def render(page: dict, ctx: RenderContext) -> PageFragment:
    """Render the ST-02 outlook page as a PageFragment.

    Data-prep → render templates/st_02.html.jinja. Head-level CSS lives in the
    shared head (assembler); this returns only the page body markup + the
    ST-02-scoped layout CSS.
    """
    d: dict = page.get("data") or {}

    # ---- audience qualifiers → check-list items (graceful: [] → no panel) ----
    # G13: the reader's TAKEAWAYS are `takeaways` (labelled "Was Sie
    # mitnehmen"); a genuine target-audience list stays `zielgruppe`. The old
    # rename put takeaways under "Zielgruppe des Reports" (wrong).
    zielgruppe = [str(z) for z in (d.get("zielgruppe") or []) if str(z).strip()]
    takeaways = [str(z) for z in (d.get("takeaways") or []) if str(z).strip()]

    # OPTIONAL accent pull-quote (the report's thesis) on a dark callout panel —
    # the visual break between the prose and the audience panel (graceful: "" → none).
    # Accepts BOTH shapes: a plain string, or the {text, attribution} dict the
    # writer-v4 normalizer emits (str() on the dict printed a Python repr on the page).
    _pq = d.get("pullquote", "")
    if isinstance(_pq, dict):
        _pq = _pq.get("text", "")
    pullquote = str(_pq or "").strip()

    diagram = d.get("diagram") if isinstance(d.get("diagram"), dict) else None

    # data-viz PRESET layer: data['viz'] is a list of {preset, …} specs the
    # curation step wrote (verbatim figures). Coerce to None unless a non-empty
    # list so the template renders exactly as before when absent (graceful). The
    # template renders the dispatch via the shared viz macro (ST-07A pattern).
    viz = d.get("viz")
    viz = viz if isinstance(viz, list) and viz else None

    # navy-stone material for the viz-island depth treatment (graceful -> token navy)
    panel_texture_uri = ctx.resolve_report_asset(("panel_texture",), ("panel_texture",)) or ""

    template = get_env().get_template("st_02.html.jinja")
    html = template.render(
        kicker=_KICKER,
        title=d.get("title", ""),
        body_html=preprocess_body(d.get("body", "")),
        pullquote=pullquote,
        zielgruppe=zielgruppe,
        zielgruppe_label=_ZG_LABEL if zielgruppe else "",
        takeaways=takeaways,
        takeaways_label=_TK_LABEL if takeaways else "",
        diagram=diagram,
        viz=viz,
        panel_texture_uri=panel_texture_uri,
    )
    return PageFragment(html=html, css=_CSS)
