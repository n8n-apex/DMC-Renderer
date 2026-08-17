"""Authority-panel contrast regression — the "invisible stats" bug.

ROOT CAUSE (found 2026-06-16): for a brand where brand_primary == brand_accent
(APEX sets BOTH to #4A7C7E), every authority panel grounded on
``var(--color-primary)`` and any accent-colored text on it
(ST-05 stat numerals were ``var(--color-accent)``) collapsed to ~1:1 contrast and
vanished. The labels survived only because they used ``var(--color-on-primary)``.

THE FIX re-grounds every authority panel on ``var(--color-ink)`` (the true dark
neutral, #2E3E50 for apex) — matching the ST-07A stat rail which ALREADY did this
("APEX's mid-cyan primary would read pale here, so ink is chosen") — and lifts the
ST-05 stat numerals to ``var(--color-on-dark)``.

These assertions bind the fix so it cannot silently regress.

Run: pytest tests/test_panel_contrast.py -v
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
STYLES = ROOT / "styles"
BRAND = ROOT / "fixtures" / "apex" / "brand_input.json"

# Every panel/ground that must read as a TRUE dark surface, not the brand's
# (possibly mid-value) primary. (file, exact-selector).
AUTHORITY_PANELS = [
    ("components.css", ".c-viz-island"),      # shared data-viz dark island (p2/p4/p18 depth)
    # NB: .st-02 .ol-quote is now a FLAT CREAM quote by design (its page's dark
    #     island is the rings viz above), so it is no longer an authority panel.
    ("st_05.css", ".st-05 .ab-lead"),         # about positioning panel
    ("st_05.css", ".st-05 .ab-stats"),        # about "in Zahlen" stat panel
    ("st_fazit.css", ".st-fazit .fz-header"), # conclusion anchor band
    ("st_07a.css", ".st-07a .cs-panel"),      # case-study sidebar panel
    ("st_01.css", ".st-01 .cv-hero"),         # cover hero fallback ground
    ("st_31.css", ".st-31 .br-bleed"),        # breather fallback ground
]


def _block(css: str, selector: str) -> str:
    """Return the declaration block (between the first {...}) for an exact selector."""
    i = css.find(selector)
    assert i != -1, f"selector {selector!r} not found"
    brace = css.find("{", i)
    end = css.find("}", brace)
    return css[brace + 1:end]


def test_authority_panels_ground_on_ink_not_primary():
    for fname, sel in AUTHORITY_PANELS:
        block = _block((STYLES / fname).read_text(), sel)
        assert "background-color: var(--color-ink)" in block, (
            f"{fname} {sel}: authority panel must ground on --color-ink (true dark), got:\n{block}"
        )
        assert "background-color: var(--color-primary)" not in block, (
            f"{fname} {sel}: must NOT ground on --color-primary (collapses for primary==accent brands)"
        )


def test_no_authority_ground_paints_on_primary_anywhere():
    """Belt-and-braces: no stylesheet grounds a surface on --color-primary.
    (Accent CHIPS/bars use var(--color-accent) and are unaffected.)"""
    offenders = []
    for css in STYLES.glob("*.css"):
        for n, line in enumerate(css.read_text().splitlines(), 1):
            if "background-color: var(--color-primary)" in line:
                offenders.append(f"{css.name}:{n}")
    assert not offenders, f"primary used as a panel ground at: {offenders}"


def test_about_stat_numerals_use_on_dark():
    block = _block((STYLES / "st_05.css").read_text(), ".st-05 .ab-stats .c-stat-value")
    assert "color: var(--color-on-dark)" in block, (
        "ST-05 stat numerals must be on-dark on the dark panel (matches ST-07A stat rail)"
    )
    assert "color: var(--color-accent)" not in block, (
        "ST-05 stat numerals must NOT be accent (teal-on-teal == invisible when primary==accent)"
    )


# --- WCAG contrast: prove the fix is legible and document the bug it replaces ---

def _lin(c: float) -> float:
    c /= 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def _luminance(hx: str) -> float:
    hx = hx.lstrip("#")
    r, g, b = int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16)
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def _contrast(a: str, b: str) -> float:
    la, lb = _luminance(a), _luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def test_apex_numeral_contrast_fixed_and_old_pairing_was_the_bug():
    brand = json.loads(BRAND.read_text())["brand_tokens"]
    primary = brand["brand_primary"]
    accent = brand["brand_accent"]
    ink = brand["brand_neutral_dark"]
    on_dark = "#FFFFFF"
    # The OLD pairing (accent numerals on a primary panel) was the bug for apex:
    assert _contrast(primary, accent) < 1.5, (
        "regression guard: this brand has primary != accent, so the original bug "
        "could not have occurred — revisit the fix rationale"
    )
    # The NEW pairing (on-dark numerals on an ink panel) clears the large-text bar:
    assert _contrast(ink, on_dark) >= 3.0, (
        f"on-dark numerals on the ink panel must be legible (got {_contrast(ink, on_dark):.2f}:1)"
    )
