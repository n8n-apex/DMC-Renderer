"""Generate the NAVY MARBLE panel texture used by the curved treatment footer
and the dark content panels (editorial right column, framework result band).

CODE-generated (numpy + Pillow) via the preprocessor's procedural_texture.marble,
so it is deterministic, resolution-independent, and reads as real mottled stone
(fine lighter veins over a deep navy ground), never "generic AI slop".

BRAND-AGNOSTIC by construction: make_navy_marble takes the ink + accent hex as
arguments (tints derive from those brand tokens). Only the apex run-script at the
bottom passes the literal apex values, which is fine because this fixture is the
demo package (exempt from the token-only rule that governs the treatment CSS).

The locked parameters below are tuned + approved by the controller. Run this file
directly to (re)write fixtures/apex/assets/panel_marble.png.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

# the marble generator lives in the sibling preprocessor package.
sys.path.insert(0, "/Users/utkarsh/Projects/richard/research/preprocessor")
from stages.procedural_texture import marble  # noqa: E402


def _hx(h: str) -> np.ndarray:
    h = h.lstrip("#")
    return np.array([int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)], float)


def _hexs(a: np.ndarray) -> str:
    a = np.clip(a, 0, 255).astype(int)
    return "#%02x%02x%02x" % (a[0], a[1], a[2])


def _mix(a: np.ndarray, b: np.ndarray, t: float) -> np.ndarray:
    return a * (1 - t) + b * t


def make_navy_marble(width, height, *, ink_hex, accent_hex, seed=4):
    """Deep navy stone: an ink ground with fine lighter veins that pick up a
    whisper of the brand accent at the brightest vein centres. Tints are all
    derived from the passed ink + accent tokens (brand-agnostic)."""
    DARK = _hx(ink_hex)
    ACC = _hx(accent_hex)
    W = np.array([255, 255, 255.0])
    stops = [
        (0.0, ink_hex),
        (0.6, _hexs(_mix(DARK, W, 0.06))),
        (0.86, _hexs(_mix(DARK, W, 0.14))),
        (1.0, _hexs(_mix(_mix(DARK, ACC, 0.4), W, 0.16))),
    ]
    return marble(
        int(width), int(height), stops, seed=seed,
        x_period=0.85, y_period=1.5, turb_power=2.6, vein_sharpness=1.5,
    )


def _apex_tokens() -> tuple[str, str]:
    """Read ink + accent from the apex package brand block (NOT hardcoded in the
    generator). Only this apex run-script binds the literal apex values."""
    import json
    pkg = json.loads(
        (Path(__file__).parent / "resolved_package.json").read_text(encoding="utf-8")
    )
    brand = pkg["brand"]
    return brand["brand_neutral_dark"], brand["brand_accent"]


def main() -> int:
    ink_hex, accent_hex = _apex_tokens()
    # A3 @ 4 px/mm: 420mm x 297mm -> 1680 x 1188. High-res so background-size:cover
    # stays crisp on the tall navy column AND the wide footer band.
    img = make_navy_marble(1680, 1188, ink_hex=ink_hex, accent_hex=accent_hex)
    out = Path(__file__).parent / "assets" / "panel_marble.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    print(f"wrote {out} ({img.size[0]}x{img.size[1]}) ink={ink_hex} accent={accent_hex}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
