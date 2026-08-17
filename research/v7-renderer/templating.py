"""Jinja2 environment for the renderer. autoescape is OFF: the templates
assemble already-escaped, trusted HTML fragments produced by the patterns
(patterns escape their own data). Markup lives in templates/, not Python.
"""
from __future__ import annotations
import re as _re
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape  # noqa: F401

_ROOT = Path(__file__).resolve().parent
_TEMPLATES = _ROOT / "templates"
_COMPONENTS = _ROOT / "components"
_ENV: Environment | None = None

_NUM_RE = _re.compile(r"-?\d+(?:[.,]\d+)?")


def _leadnum(value) -> float:
    """Extract the leading number from a string for viz bar/arc geometry.

    The data-viz macros DISPLAY a figure verbatim (e.g. "30", "> 200.000 €",
    "2,5x") but need a numeric magnitude to size a bar/arc. This filter derives
    that magnitude from the same string so the geometry can never diverge from
    the shown numeral. "30 Min"→30, "2,5x"→2.5, "> 200.000 €"→200000 (German
    thousands dot is treated as a grouping separator, comma as decimal); no
    number → 0.0 (the macro then floors to a visible minimum).
    """
    m = _NUM_RE.search(str(value or ""))
    if not m:
        return 0.0
    tok = m.group(0)
    # German convention: '.' groups thousands, ',' is the decimal point.
    tok = tok.replace(".", "").replace(",", ".") if "," in tok else tok.replace(".", "")
    try:
        return float(tok)
    except ValueError:
        return 0.0


def _fit_fontsize(text, inner: float, base: float, glyph: float = 0.6) -> float:
    """Shrink a CENTER label's font-size to fit an inner width (SVG user units).

    A ring/donut/cluster center label wider than the circle's inner hole spills
    over (the "6 von 6" bug). This scales the size DOWN by character count so a
    multi-char label fits, while a short label keeps the base size:
    ``min(base, inner / (len(text) * glyph))``. ``glyph`` is the average glyph
    advance as a fraction of the font size for the bold head face. FORMAT logic
    (geometry only), never client text.
    """
    n = max(1, len(str(text or "")))
    return round(min(float(base), inner / (n * glyph)), 1)


def get_env() -> Environment:
    global _ENV
    if _ENV is None:
        _ENV = Environment(
            # both templates/ and components/ are searched, so a page template
            # can `{% from 'pill.jinja' import pill %}` from the macro library.
            loader=FileSystemLoader([str(_TEMPLATES), str(_COMPONENTS)]),
            autoescape=False,          # fragments are pre-escaped, trusted
            trim_blocks=True, lstrip_blocks=True,
        )
        # `num` — leading-number extractor used by the viz macros to size bars/
        # arcs from a verbatim figure string (geometry can't diverge from text).
        _ENV.filters["num"] = _leadnum
        # `fitfs` — shrink a viz center label's font-size to fit the circle's
        # inner hole so it can never overflow (e.g. ring center "6 von 6").
        _ENV.filters["fitfs"] = _fit_fontsize
    return _ENV
