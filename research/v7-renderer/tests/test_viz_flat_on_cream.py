"""Phase 1 guard: the data-viz preset CSS must be FLAT-ON-CREAM (Richard /
Power-BI editorial style), NOT dark-glass.

The reference decks (refs/aerztepartner, refs/niklas_niemeyer) visualize data as
flat, rationed-colour marks on the cream ground: solid accent bars/arcs, muted-gray
context, hairline dividers, navy-ink numerals. The earlier viz.css rendered every
device with drop-shadow glow, box-shadow cards, and gradient fills that fight the
cream editorial DNA (the owner's 'dull / looks bad' complaint). This guard forbids
those recipes from re-entering the preset CSS. Brand-agnostic: scans CSS tokens only,
no client data.
"""
import sys
from pathlib import Path

_VIZ_CSS = Path(__file__).resolve().parent.parent / "styles" / "viz.css"

# The dark-glass / glow recipe that must stay OUT of the flat-on-cream preset CSS.
_FORBIDDEN = (
    "text-shadow",
    "box-shadow",
    "drop-shadow(",
    "linear-gradient(",
    "radial-gradient(",
)


def test_viz_css_is_flat_no_glow_or_gradient():
    css = _VIZ_CSS.read_text(encoding="utf-8")
    hits = sorted({tok for tok in _FORBIDDEN if tok in css})
    assert not hits, (
        "viz.css must be flat-on-cream (no glow/shadow/gradient); "
        f"found forbidden recipe tokens: {hits}"
    )
