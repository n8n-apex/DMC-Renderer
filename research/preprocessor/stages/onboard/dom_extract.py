"""Stage Onboard-1 — parse the raw page.evaluate() blob into DomSignals.

Pure: no browser, no I/O. Fed the dict that capture.py's injected JS
returns. Normalizes CSS colors to lowercase #rrggbb and resolves font
stacks to their first concrete family.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from models_onboard import DomSignals

# Generic CSS font families that are NOT a real typeface name.
_GENERIC_FAMILIES = frozenset({
    "serif", "sans-serif", "monospace", "cursive", "fantasy",
    "system-ui", "ui-serif", "ui-sans-serif", "ui-monospace",
    "inherit", "initial", "unset", "-apple-system", "blinkmacsystemfont",
})

_RGB_RE = re.compile(
    r"rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})", re.IGNORECASE
)
_HEX_RE = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def _to_hex(color: Any) -> Optional[str]:
    """Normalize a CSS color string to lowercase #rrggbb, or None."""
    if not isinstance(color, str):
        return None
    c = color.strip()
    if not c:
        return None
    m = _HEX_RE.match(c)
    if m:
        body = m.group(1).lower()
        if len(body) == 3:
            body = "".join(ch * 2 for ch in body)
        return f"#{body}"
    m = _RGB_RE.match(c)
    if m:
        r, g, b = (max(0, min(255, int(m.group(i)))) for i in (1, 2, 3))
        return f"#{r:02x}{g:02x}{b:02x}"
    return None


def _first_family(stack: Any) -> Optional[str]:
    """First concrete family from a font-family stack, or None if only
    generic families are present.
    """
    if not isinstance(stack, str) or not stack.strip():
        return None
    for raw in stack.split(","):
        fam = raw.strip().strip('"').strip("'").strip()
        if fam and fam.lower() not in _GENERIC_FAMILIES:
            return fam
    return None


def parse(raw_dom_eval: dict) -> DomSignals:
    """Parse the page.evaluate() blob into DomSignals. Tolerant of any
    missing/extra keys.
    """
    raw = raw_dom_eval or {}

    css_vars: dict[str, str] = {}
    for name, value in (raw.get("cssVars") or {}).items():
        hexv = _to_hex(value)
        if hexv is not None:
            css_vars[name] = hexv

    sampled: list[str] = []
    for value in (raw.get("sampledColors") or []):
        hexv = _to_hex(value)
        if hexv is not None:
            sampled.append(hexv)

    logo = raw.get("logoUrl")
    return DomSignals(
        css_color_vars=css_vars,
        font_head=_first_family(raw.get("fontHead")),
        font_body=_first_family(raw.get("fontBody")),
        sampled_colors=sampled,
        logo_url=logo if isinstance(logo, str) and logo.strip() else None,
    )
