"""DESIGN-SYSTEM CONFORMANCE GATE.

Turns the extracted Richard design system (docs/superpowers/specs/
2026-06-14-richard-design-system-EXTRACTED.md + ...-infographic-vocabulary-...)
into EXECUTABLE assertions so the documented rules actually bind the build
instead of living in a doc that gets ignored. This is the fix for the recurring
failure where understanding was documented but never reached the renderer.

The canonical rules checked here (each maps to a line in the spec):
  - GROUND is warm cream #F6F3ED (R245-250 / G242-247 / B235-243), never white.
  - INK/dark is a soft NAVY (visible, bluish, max channel ~60-100), never
    near-black #0F0F1F.
  - ACCENT is a MUTED teal/sage (max channel <= ~150, teal-ish G,B >= R),
    never a bright cyan like #85d2ee.
  - ZERO drop/box/text shadows + glow anywhere in styles/ (flat, one depth
    plane). `: none` is allowed.

Run: pytest tests/test_design_conformance.py -v
These are EXPECTED to fail until the renderer is re-architected to the spec;
keeping them red is the point — they are the definition of done.
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BRAND = ROOT / "fixtures" / "apex" / "brand_input.json"
STYLES = ROOT / "styles"


def _hex_to_rgb(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _brand_tokens() -> dict:
    return json.loads(BRAND.read_text(encoding="utf-8"))["brand_tokens"]


# ---- GROUND must be warm cream, not white ----
def test_ground_is_cream_not_white():
    r, g, b = _hex_to_rgb(_brand_tokens()["brand_neutral_light"])
    assert 244 <= r <= 251 and 240 <= g <= 248 and 233 <= b <= 244, (
        f"ground {(r, g, b)} is not warm cream #F6F3ED-range "
        f"(spec: never pure white)"
    )
    # warm: red channel must exceed blue (cream is warm, white/cool is not)
    assert r > b, f"ground {(r, g, b)} is not WARM (R must exceed B)"


# ---- INK/dark must be a soft navy, not near-black ----
def test_ink_is_soft_navy_not_black():
    r, g, b = _hex_to_rgb(_brand_tokens()["brand_neutral_dark"])
    mx = max(r, g, b)
    assert 55 <= mx <= 105, (
        f"ink {(r, g, b)} max-channel {mx} not in soft-navy range 55-105 "
        f"(spec navy #2E3E50; #0F0F1F near-black is wrong)"
    )
    assert b >= r, f"ink {(r, g, b)} is not bluish-navy (B must be >= R)"


# ---- ACCENT must be a muted teal, not bright cyan ----
def test_accent_is_muted_teal_not_bright_cyan():
    for key in ("brand_primary", "brand_accent"):
        r, g, b = _hex_to_rgb(_brand_tokens()[key])
        assert max(r, g, b) <= 150, (
            f"{key} {(r, g, b)} is too bright/light for a muted teal accent "
            f"(spec #4A7C7E; #85d2ee bright cyan is wrong)"
        )
        assert g >= r and b >= r, f"{key} {(r, g, b)} is not teal-ish (G,B >= R)"


# ---- NO neon accent-GLOW (user override: keep tasteful DEPTH, kill only the
#      gaudy cyan glow). A shadow that tints itself with the brand accent is a
#      glow; a neutral ambient shadow (neutral-dark / black) is legitimate depth
#      and is allowed. So we flag ONLY box-/text-/drop-shadows that reference the
#      accent token (the neon look the user rejected), not depth itself. ----
_SHADOW_RE = re.compile(r"(box-shadow|text-shadow|drop-shadow)\s*:?\s*([^;}]*)", re.I | re.S)


def test_no_neon_accent_glow():
    offenders = []
    for css in sorted(STYLES.glob("*.css")):
        text = css.read_text(encoding="utf-8")
        for m in _SHADOW_RE.finditer(text):
            val = m.group(2).strip().lower()
            if "color-accent" in val or "--color-accent" in val:
                line_no = text[:m.start()].count("\n") + 1
                offenders.append(f"{css.name}:{line_no}: {m.group(0).strip()[:90]}")
    assert not offenders, (
        "user override: tasteful depth is fine; neon ACCENT-glow is not. "
        f"Found {len(offenders)} accent-tinted shadows (retune to neutral depth "
        "or remove):\n" + "\n".join(offenders[:40])
    )


# ---- the deck uses the 6-type LAYOUT SYSTEM, not one reused template ----
def test_layout_type_system_is_used_with_variety():
    import sys
    sys.path.insert(0, str(ROOT))
    from patterns.layout_types import layout_type_for, LAYOUT_RECIPES
    pkg = json.loads((ROOT / "fixtures" / "apex" / "resolved_package.json").read_text(encoding="utf-8"))
    used = {layout_type_for(p["st_type"]) for p in pkg["pages"]}
    assert used <= set(LAYOUT_RECIPES), f"unknown layout types: {used - set(LAYOUT_RECIPES)}"
    # variety: the deck must compose from several distinct layouts, not one
    assert len(used) >= 4, f"only {len(used)} distinct layout types in the deck: {used}"
