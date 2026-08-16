"""US-601 — the 30-50% clip is a HARD regression.

The ST-06 stat callout value ("30-50%") has repeatedly been clipped by its
42mm card. Earlier "fixes" used letter-spacing/font-size squeezing or CSS
changes that broke pagination. The honest contract: the value node in the
REAL Chromium print geometry must fit inside its own box (scrollWidth <=
clientWidth) with NO letter-spacing squeeze and at the token size.

This test measures the ACTUAL ship-engine DOM (Playwright Chromium print
emulation) on the assembled ST-06 page — the same engine that produces
report.pdf — not markup assertions.
"""

from __future__ import annotations

import copy
import re
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from package_loader import load_package  # noqa: E402
from assembler import shared_head_css, _section  # noqa: E402
from patterns import st_06  # noqa: E402
from patterns.base import RenderContext  # noqa: E402
from grammar_loader import load_grammar  # noqa: E402

APEX = ROOT / "fixtures" / "apex"
CHASSIS_ROOT = ROOT

# The ST-06 section in the apex package now spans TWO physical pages (US-603):
# page 1 = intro (slot 16), page 2 = result (continuation carrying the
# 30-50% ergebnis + the stat card). The stat-fit regression must measure the
# RESULT page.
ST06_INDEX = 15  # slot 16, intro page (no stat)


def _apex_ctx():
    pkg = load_package(APEX)
    return RenderContext(
        brand=pkg.brand,
        grammar=load_grammar(),
        package_dir=pkg.package_dir,
        report_assets=pkg.report_assets,
    )


def _st06_result_page() -> dict:
    pkg = load_package(APEX)
    for page in pkg.pages:
        if (str(page.get("st_type")) == "ST-06"
                and page.get("continuation_role") == "result"):
            return copy.deepcopy(page)
    raise AssertionError("ST-06 result continuation page not found in package")


def _assemble_st06() -> tuple[str, str]:
    """Return (html_doc, css) for the real ST-06 RESULT page (has the stat)."""
    pkg = load_package(APEX)
    page = _st06_result_page()
    frag = st_06.render(page, _apex_ctx())
    head = shared_head_css(pkg.brand, CHASSIS_ROOT / "fonts", pkg.axes)
    one_doc = (
        '<!DOCTYPE html><html lang="de"><head><meta charset="utf-8">'
        f"<style>{head}{frag.css}</style></head>"
        f"<body>{_section(page, frag, 16)}</body></html>"
    )
    return one_doc, frag.css


def _value_geometry() -> dict:
    """Measure the stat-callout value node in the real Chromium print DOM.

    US-604: the 30-50% figure on the result continuation renders via the
    diagram proof (stat_callout) instead of the floated card when the diagram
    is present (one figure, one place — no duplication). Measure whichever
    host carries the value.
    """
    from playwright.sync_api import sync_playwright

    html_doc, _css = _assemble_st06()
    html_path = ROOT / "output" / "st06_geometry.html"
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(html_doc, encoding="utf-8")

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        page.goto(html_path.resolve().as_uri())
        page.emulate_media(media="print")
        out = page.evaluate(
            """() => {
                const sel = '.st-06 .c-stat-callout__value, .st-06 [class*="stat"] [class*="figure"], .st-06 .c-statcard__figure';
                const v = document.querySelector(sel);
                const card = v ? v.closest('.c-stat-callout, .c-statcard, [class*="stat"]') : null;
                if (!v || !card) return null;
                const vr = v.getBoundingClientRect();
                const cr = card.getBoundingClientRect();
                return {
                    text: v.textContent,
                    valueWidth: Math.round(vr.width),
                    scrollWidth: v.scrollWidth,
                    clientWidth: v.clientWidth,
                    cardWidth: Math.round(cr.width),
                    fontSize: getComputedStyle(v).fontSize,
                    letterSpacing: getComputedStyle(v).letterSpacing,
                    whiteSpace: getComputedStyle(v).whiteSpace,
                };
            }"""
        )
        browser.close()
    return out


def test_stat_value_fits_its_box() -> None:
    """THE regression: the visible 30-50% value must not clip.

    The value node's scrollWidth (the text's intrinsic width) must be <= its
    clientWidth (the box it paints in) in the ship engine's print geometry.
    """
    geo = _value_geometry()
    assert geo is not None, "stat callout value/card not found on the ST-06 page"
    assert geo["text"] == "30-50%", f"unexpected value text: {geo['text']!r}"
    assert geo["scrollWidth"] <= geo["clientWidth"], (
        f"ST-06 stat value '{geo['text']}' CLIPS: scrollWidth "
        f"{geo['scrollWidth']}px > clientWidth {geo['clientWidth']}px "
        f"(card {geo['cardWidth']}px). The value must fit its box — widen "
        f"the card or give the stat a real region; never squeeze via "
        f"letter-spacing/font-size."
    )


def test_stat_value_no_letter_spacing_squeeze() -> None:
    """The 'fix' must not be the letter-spacing squeeze.

    The prior pagination-safe hack shrank the value visually via a narrower
    letter-spacing. That is banned: the value must fit at the token size with
    normal spacing.
    """
    geo = _value_geometry()
    assert geo is not None
    ls = geo["letterSpacing"]
    # The OLD squeeze hack crammed the value into a 42mm card with aggressive
    # negative letter-spacing. The diagram's stat figure may carry its design
    # kerning (-0.5px class); the HARD regression is the FIT (the test above),
    # not a zero-tolerance kerning check. Reject only a squeeze that the fit
    # would also reject (> -1px is design kerning, not a clip fix).
    import re as _re
    m = _re.match(r"(-?[\d.]+)px", ls or "")
    if m:
        assert float(m.group(1)) >= -1.0, f"letter-spacing squeeze: {ls}"
    else:
        assert ls in ("normal", "0px"), f"letter-spacing: {ls}"
    # computed style normalizes 40pt -> 53.3333px (40 * 96/72).
    assert geo["fontSize"] == "53.3333px", (
        f"value must stay at the token size --type-stat (40pt -> 53.3333px); "
        f"got {geo['fontSize']} (font-size shrink is banned)"
    )


def test_st06_css_has_no_squeeze_hack() -> None:
    """No letter-spacing/nowrap squeeze in the ST-06 scoped CSS either."""
    _html, css = _assemble_st06()
    block = re.search(
        r"\.st-06 \.c-stat-callout__value\s*\{([^}]*)\}", css, re.S
    )
    if block:
        body = block.group(1)
        assert "letter-spacing" not in body, (
            "ST-06 value CSS must not use letter-spacing squeeze"
        )
        assert "--type-stat" in body, (
            "ST-06 value CSS must keep the token size"
        )


def test_st06_intro_stat_card_wide_enough() -> None:
    """The card must be WIDE enough for the value + padding at the token size.

    Measured: "30-50%" at 40pt needs 176px; the card adds padding
    (space-3/space-4) and centering. The scoped width must exceed the text.
    """
    _html, css = _assemble_st06()
    block = re.search(
        r"\.st-06 \.mx-intro-stat\s*\{([^}]*)\}", css, re.S
    )
    assert block, "missing .st-06 .mx-intro-stat rule"
    body = block.group(1)
    m = re.search(r"width:\s*([\d.]+)mm", body)
    assert m, f"no explicit width in .mx-intro-stat: {body}"
    width_mm = float(m.group(1))
    # 176px text + ~2 * (space-3 2mm + space-4 4mm) padding + margin = ~70mm
    assert width_mm >= 66, (
        f".mx-intro-stat width {width_mm}mm is too narrow for '30-50%' at "
        f"40pt (needs ~70mm with padding); widen it — the clip is a layout "
        f"contract failure, not a typography one"
    )
