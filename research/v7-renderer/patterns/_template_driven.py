"""Template-driven renderer (Phase 4, Task 3) — the PLACEMENT engine.

Places page content into a reference-derived ``LayoutTemplate``: a page-sized
relative box with one ABSOLUTELY-positioned frame per region at the template's
normalized x/y/w/h (page fractions, top-left origin). The per-region CONTENT is
produced by an injectable ``render_region`` callback (the role -> macro -> page
data binding), so THIS module owns PLACEMENT only and stays st_type-agnostic.
Regions whose content is empty/None are OMITTED (no empty boxes — graceful).

The role -> page-data binder (which is case-study-shaped for ST-07A, cover-shaped
for ST-01, etc.) is built per st_type at migration time (Task 5); this engine +
``render_macro`` are the generic, reusable substrate it stands on.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from layout_template import LayoutTemplate, Region  # noqa: E402
from patterns.base import PageFragment  # noqa: E402
from templating import get_env  # noqa: E402

# Scoped CSS (no :root/@page/@font-face — those live in the shared head). The
# page box is the A4 content box the assembler gives each `.page` (261mm tall);
# region frames position against it as percentages.
_PAGE_CSS = """
.tpl-page { position: relative; width: 100%; height: 261mm; }
.tpl-region { position: absolute; box-sizing: border-box; overflow: hidden; }
.tpl-region--footer {
  writing-mode: vertical-rl; transform: rotate(180deg);
  font-family: var(--font-head); font-size: var(--type-caption);
  letter-spacing: 0.18em; text-transform: uppercase; color: var(--color-muted);
}
""".strip()


def _region_style(r: Region) -> str:
    """Absolute-frame inline style from a region's normalized geometry."""
    return (
        f"left:{r.x * 100:.3f}%;top:{r.y * 100:.3f}%;"
        f"width:{r.w * 100:.3f}%;height:{r.h * 100:.3f}%;z-index:{r.z}"
    )


def render_macro(macro_file: str, macro_name: str, **kwargs) -> str:
    """Render ONE component macro to an HTML string via the shared Jinja env.

    Lets the role binder reuse the existing macro library
    (``two_tone_headline``, ``section_label``, ``media_figure``, ``pull_quote``,
    ``ghost_numeral``, ``pill``, ``viz`` …) without hand-writing markup.
    """
    env = get_env()
    tmpl = env.from_string(
        "{%% from '%s' import %s %%}{{ %s(**kw) }}" % (macro_file, macro_name, macro_name)
    )
    return tmpl.render(kw=kwargs).strip()


def render_from_template(
    template: LayoutTemplate,
    *,
    render_region: Callable[[Region, int], Optional[str]],
) -> PageFragment:
    """Place each region's content (from ``render_region``) per template geometry.

    ``render_region(region, index) -> html | None``: a falsy return OMITS the
    region (graceful, no empty frame). Returns a ``PageFragment`` (html body +
    scoped css) the assembler wraps in the page ``<section>``.
    """
    parts: list[str] = ['<div class="tpl-page">']
    for i, r in enumerate(template.regions):
        html = render_region(r, i)
        if not html:
            continue
        parts.append(
            f'<div class="tpl-region tpl-region--{r.role}" '
            f'style="{_region_style(r)}">{html}</div>'
        )
    parts.append("</div>")
    return PageFragment(html="\n".join(parts), css=_PAGE_CSS)
