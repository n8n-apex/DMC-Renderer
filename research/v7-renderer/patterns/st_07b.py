"""Pattern for ST-07B — THEORY / "Gegenseite" (Plan B rebuild, grammar P-7).

DATA-PREP ONLY. This module reads the package `page` dict, shapes a context
dict, and renders `templates/st_07b.html.jinja` (which composes the atomic macro
library on a token-themed layout, `styles/st_07b.css`). The returned
PageFragment.html is that rendered string; the .css is the layout sheet.

WHY this shape (vs the old hand-built f-string CSS):
  - Brand-agnostic by construction: the template + layout CSS contain ZERO
    client literals (no hex, no font family, no client name). Colors + fonts
    arrive at render time via the token `:root` (compile_tokens) — the headline
    sizes off `var(--font-display)`, which resolves to the SERIF face when the
    brand's axis is headline_type=serif (the apex deck IS serif). Set against the
    sans `var(--font-body)` two-column prose, that serif/sans pairing is the §18
    contrast.
  - The device LOOK (key_insight = accent-ruled tint panel + larger italic body;
    eyebrow) lives in the `c-` classes (components.css, already in the shared
    <head>); this pattern only feeds the macros DATA and positions them.

DATA CONTRACT (preserved from the prior pattern — fields on page["data"]):
  title (the serif headline), body (the argument prose, markdown), key_insight
  (the payoff insight line, markdown) for the key-insight callout, and an OPTIONAL
  compare = {ohne: [str], mit: [str]} before/after grid. Plain-string or absent
  fields degrade gracefully (no headline / no body / no callout / no compare grid).

The German eyebrow kicker (Theorie) and the key-insight label (Kernaussage) and
the compare-column labels (OHNE / MIT) are CONTENT labels for this report TYPE
(not client-specific) — module constants passed to the template as data.

History (Plan B): replaced the prior monolithic f-string render (hand-written
.th-* CSS with hardcoded color + font-family literals baked into the pattern)
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
_CSS_PATH = Path(__file__).resolve().parent.parent / "styles" / "st_07b.css"
_CSS = _CSS_PATH.read_text(encoding="utf-8")

# Content labels for this report TYPE (not client-specific).
_KICKER = "Theorie"
_INSIGHT_LABEL = "Kernaussage"
_COMPARE_SPEC: tuple[tuple[str, str, str], ...] = (
    ("ohne", "Ohne System", "ohne"),   # (data-key, label, tone-modifier)
    ("mit", "Mit System", "mit"),
)


def render(page: dict, ctx: RenderContext) -> PageFragment:
    """Render the ST-07B theory page as a PageFragment.

    Data-prep → render templates/st_07b.html.jinja. Head-level CSS lives in the
    shared head (assembler); this returns only the page body markup + the
    ST-07B-scoped layout CSS.
    """
    d: dict = page.get("data") or {}

    # ---- optional before/after compare grid (graceful: absent → no grid) ----
    compare_src = d.get("compare") or {}
    compare: list[dict] = []
    for key, label, tone in _COMPARE_SPEC:
        items = [str(x) for x in (compare_src.get(key) or []) if str(x).strip()]
        if items:
            compare.append({"label": label, "tone": tone, "items": items})
    # only render the grid when BOTH sides carry content (a one-sided compare is
    # not a contrast — drop it rather than render a lopsided box)
    if len(compare) < 2:
        compare = []

    insight_html = preprocess_body(d.get("key_insight", ""))

    # ---- layout variant (per-page hint) ----------------------------------
    # "standard" (DEFAULT, unchanged): kicker + serif headline → two-up body →
    #   optional compare grid → the key-insight as an accent-ruled TINT callout
    #   spanning full width. On the apex theory page (pages[7]) `compare` is null
    #   and the body is short, so the bottom ~60% of the sheet is empty white
    #   (N08 dead-space band).
    # "fill": the expert DARK authority-panel composition (DNA §C3 — niklas p8 /
    #   boss p5). The kicker + headline + body (+ compare grid when present) sit
    #   in the UPPER portion; the key_insight becomes a LARGE full-width DARK
    #   panel pinned to fill the LOWER portion of the content box (oversized
    #   italic statement, white/accent on the dark ground). The full-width dark
    #   panel filling the empty band is what kills the dead space. Brand-agnostic:
    #   tokens only (the dark ground + on-dark/accent text resolve from the token
    #   layer at render time).
    layout_variant = page.get("layout_variant", "standard")
    if layout_variant not in ("standard", "fill"):
        layout_variant = "standard"

    template = get_env().get_template("st_07b.html.jinja")
    html = template.render(
        layout_variant=layout_variant,
        kicker=_KICKER,
        title=d.get("title", ""),
        body_html=preprocess_body(d.get("body", "")),
        compare=compare,
        insight_html=insight_html,
        insight_label=_INSIGHT_LABEL if insight_html.strip() else "",
        # the page's data-viz preset specs (e.g. the writer's vorher_nachher as
        # a transform_arrow) — rendered as a device band between the body and
        # the insight panel. Graceful: absent -> no band.
        viz=d.get("viz") or [],
    )
    return PageFragment(html=html, css=_CSS)
