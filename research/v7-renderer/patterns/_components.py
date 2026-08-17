"""Shared pattern helper: the inline-SVG QR generator.

The old R2 HTML-string builders (numbered_step_card / numbered_block /
dark_cta_panel / stat_strip / bar_mini / horizontal_flow + their *_CSS
constants) lived here but are SUPERSEDED by the token-only Jinja macros in
components/ (styled via styles/components.css) and have been removed. The only
survivor is qr_svg, which is brand-agnostic by construction: it takes fg/bg as
ARGS (the pattern passes resolved token colors in), so it carries no literals of
its own.
"""
from __future__ import annotations

import qrcode


def _esc(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def qr_svg(url: str, fg: str, bg: str, cell: int = 4) -> str:
    """Inline SVG QR (fg modules on bg). Shared by st_03 + st_07a (DRY).

    fg/bg are caller-supplied colors (resolved tokens), so this helper stays
    brand-agnostic.
    """
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M,
                       box_size=cell, border=0)
    qr.add_data(url)
    qr.make(fit=True)
    n = qr.modules_count
    size = n * cell
    rects = []
    for r, row in enumerate(qr.get_matrix()):
        for c, on in enumerate(row):
            if on:
                rects.append(f'<rect x="{c*cell}" y="{r*cell}" width="{cell}" height="{cell}" fill="{fg}"/>')
    return (f'<svg viewBox="0 0 {size} {size}" width="100%" height="100%" '
            f'xmlns="http://www.w3.org/2000/svg"><rect width="{size}" height="{size}" fill="{bg}"/>'
            + "".join(rects) + "</svg>")
