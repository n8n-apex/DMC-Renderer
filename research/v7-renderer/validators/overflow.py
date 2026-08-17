"""Text-overflow validator — real (R1).

Post-layout truth: render a single page's content as a standalone
1-page document; if WeasyPrint produces >1 physical page, the content
overflowed its box. Advisory only — the assembler records the flag in
RenderResult.overflow and never blocks the render (mirrors accent_budget).

The per-page standalone render is acceptable at QA/build time; it can be
optimized later if it dominates render time.
"""

from __future__ import annotations

from typing import Optional

import weasyprint
from weasyprint.text.fonts import FontConfiguration


def count_pages(html_doc: str, base_url: Optional[str] = None) -> int:
    """Return the number of physical pages WeasyPrint lays out for `html_doc`.

    Uses a FontConfiguration so layout is measured with the SAME bundled faces
    the real render embeds (Source Serif 4 / Source Sans 3). Without it the
    overflow check would measure system-fallback metrics and disagree with the
    actual PDF (see plan 2026-06-03-renderer-phase-A — the font-loading fix).
    """
    document = weasyprint.HTML(string=html_doc, base_url=base_url).render(
        font_config=FontConfiguration()
    )
    return len(document.pages)


def check_overflow(html_doc: str, base_url: Optional[str] = None) -> bool:
    """True iff `html_doc` lays out to more than one physical page."""
    return count_pages(html_doc, base_url) > 1
