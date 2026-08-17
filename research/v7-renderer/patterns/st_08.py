"""Pattern for ST-08 — FAQ / häufige Fragen (Plan B rebuild, Master S19).

DATA-PREP ONLY. This module reads the package `page` dict, shapes a context
dict, and renders `templates/st_08.html.jinja` (which composes the atomic macro
library on a token-themed layout, `styles/st_08.css`). The returned
PageFragment.html is that rendered string; the .css is the layout sheet.

WHY this shape (vs the old hand-built f-string CSS):
  - Brand-agnostic by construction: the template + layout CSS contain ZERO
    client literals (no hex, no font family, no client name). Colors + fonts
    arrive at render time via the token `:root` (compile_tokens) — the heading
    sizes off `var(--font-display)`, which resolves to the SERIF face when the
    brand's axis is headline_type=serif (the apex deck IS serif). Set against the
    sans `var(--font-body)` answers, that serif/sans pairing is the §18 contrast.
  - The Q&A unit LOOK (accent question + body answer) lives in the `c-qa-item`
    class (components.css, already in the shared <head>); this pattern only feeds
    the macro DATA and the layout positions the items two-up.

DATA CONTRACT (preserved from the prior pattern — fields on page["data"]):
  title (the heading), faqs[] (a list of {frage, antwort} dicts OR plain
  strings). A dict's `frage` is the accent question, `antwort` the markdown
  answer; a plain string degrades to an answer-only item. OPTIONAL: body / intro
  (a short lede above the stack). Absent fields degrade gracefully (no heading /
  no intro / no list). NOTE: ST-08 is not in the apex fixture (synthetic-verified
  in the test suite), so this pattern is exercised by realistic FAQ data there.

The German eyebrow kicker (Häufige Fragen) is a CONTENT label for this report
TYPE (not client-specific) — a module constant passed to the template as data.

History (Plan B): replaced the prior monolithic f-string render (hand-written
.faq-* CSS with hardcoded color + font-family literals baked into the pattern)
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
_CSS_PATH = Path(__file__).resolve().parent.parent / "styles" / "st_08.css"
_CSS = _CSS_PATH.read_text(encoding="utf-8")

# Content label for this report TYPE (not client-specific).
_KICKER = "Häufige Fragen"


def _qa_fields(it) -> tuple[str, str]:
    """A FAQ entry is a {frage, antwort} dict or a plain string (answer-only)."""
    if isinstance(it, dict):
        return it.get("frage", ""), it.get("antwort", "")
    return "", str(it)


def render(page: dict, ctx: RenderContext) -> PageFragment:
    """Render the ST-08 FAQ page as a PageFragment.

    Data-prep → render templates/st_08.html.jinja. Head-level CSS lives in the
    shared head (assembler); this returns only the page body markup + the
    ST-08-scoped layout CSS.
    """
    d: dict = page.get("data") or {}

    # ---- FAQ entries → accent-question / body-answer items ----
    faqs: list[dict] = []
    for it in d.get("faqs") or []:
        question, answer = _qa_fields(it)
        if question or answer:
            faqs.append({
                "question": question,
                "answer_html": preprocess_body(answer),
            })

    template = get_env().get_template("st_08.html.jinja")
    html = template.render(
        kicker=_KICKER,
        title=d.get("title", ""),
        intro_html=preprocess_body(d.get("body", "") or d.get("intro", "")),
        faqs=faqs,
    )
    return PageFragment(html=html, css=_CSS)
