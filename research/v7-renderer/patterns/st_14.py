"""Pattern for ST-14 — FALSE BELIEFS (Plan B rebuild, grammar P-5).

DATA-PREP ONLY. This module reads the package `page` dict, shapes a context
dict, and renders `templates/st_14.html.jinja` (which composes the atomic macro
library on a token-themed layout, `styles/st_14.css`). The returned
PageFragment.html is that rendered string; the .css is the layout sheet.

WHY this shape (vs the old hand-built f-string CSS):
  - Brand-agnostic by construction: the template + layout CSS contain ZERO
    client literals (no hex, no font family, no client name). Colors + fonts
    arrive at render time via the token `:root` (compile_tokens) — the
    color-block heading sizes off `var(--font-display)`, which resolves to the
    SERIF face when the brand's axis is headline_type=serif (the apex deck IS
    serif).
  - The device LOOK (color_block_opener / numbered_block) lives in the `c-`
    classes (components.css, already in the shared <head>); this pattern only
    feeds the macros DATA and positions them.

DATA CONTRACT (preserved from the prior pattern — fields on page["data"]):
  title, body (intro prose), beliefs[] (list of {irrglaube, realitaet, quelle}
  dicts OR plain strings). Each belief becomes a numbered block: the `irrglaube`
  (myth) is the bold quote title, the `realitaet` (truth) is the accent-ruled
  reality sub-block under a "Realität" label, and `quelle` is the source line.

The myth strings in the data arrive wrapped in German typographic quote
artifacts (e.g. `„„… \"`); `_clean_quote` strips the leading/trailing quote
characters so the myth reads cleanly as one quoted line (the template + CSS
supply the quote LOOK). Plain-string beliefs degrade to a body-only block.

The German kicker (IRRGLAUBEN) and the reality label (Realität) are CONTENT
labels for this report TYPE (not client-specific) — module constants passed to
the template as data.

History (Plan B): replaced the prior monolithic f-string render (NUMBERED_BLOCK_CSS
from _components.py with hardcoded color + font-family literals) with this
data-prep → Jinja-template split. Earlier history documented in git.
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
_CSS_PATH = Path(__file__).resolve().parent.parent / "styles" / "st_14.css"
_CSS = _CSS_PATH.read_text(encoding="utf-8")

# Content labels for this report TYPE (not client-specific).
_KICKER = "Irrglauben"
_REALITY_LABEL = "Realität"

# Leading/trailing quote characters to peel off a myth string (ASCII + German
# typographic). The template + CSS render the myth AS a quote; the raw data
# double-wraps it, so we normalise to the bare sentence.
_QUOTE_CHARS = "\"'„“”‚‘’«»‹›"


def _clean_quote(text: str) -> str:
    """Strip wrapping quote characters + whitespace from a myth string."""
    return (text or "").strip().strip(_QUOTE_CHARS).strip()


def render(page: dict, ctx: RenderContext) -> PageFragment:
    """Render the ST-14 false-beliefs page as a PageFragment.

    Data-prep → render templates/st_14.html.jinja. Head-level CSS lives in the
    shared head (assembler); this returns only the page body markup + the
    ST-14-scoped layout CSS.
    """
    d: dict = page.get("data") or {}

    # ---- beliefs → numbered belief→reality blocks ----
    beliefs: list[dict] = []
    for i, it in enumerate(d.get("beliefs") or [], start=1):
        if isinstance(it, dict):
            myth = _clean_quote(it.get("irrglaube", ""))
            reality_html = preprocess_body(it.get("realitaet", ""))
            source = it.get("quelle", "")
        else:
            myth = ""
            reality_html = preprocess_body(str(it))
            source = ""
        beliefs.append({
            "n": i,
            "myth": myth,
            "reality_html": reality_html,
            "source": source,
        })

    # Optional conceptual diagram (convergence/Venn) — DATA only; the template
    # draws it brand-agnostically via the c-venn token classes. Absent → omitted.
    diagram = d.get("diagram") if isinstance(d.get("diagram"), dict) else None

    template = get_env().get_template("st_14.html.jinja")
    html = template.render(
        kicker=_KICKER,
        title=d.get("title", ""),
        intro_html=preprocess_body(d.get("body", "")),
        beliefs=beliefs,
        reality_label=_REALITY_LABEL,
        diagram=diagram,
        # the page's proof devices: data-viz presets (e.g. the writer's sourced
        # %-figures as donut rings) + any scalar stats. Rendered as a proof band
        # at the page foot — the sourced numbers behind the belief answers.
        # Graceful: absent -> no band.
        viz=d.get("viz") or [],
        stats=d.get("stats") or [],
    )
    return PageFragment(html=html, css=_CSS)
