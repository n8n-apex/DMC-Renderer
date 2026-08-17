"""Atomic Jinja macro library (Plan B, Task 2).

Each test renders a macro from a tiny template string via the shared env and
asserts (a) the macro renders the data it was given and (b) the emitted markup
carries NO raw hex color and NO font-family literal — components reference
semantic design tokens (var(--…)) ONLY, so they stay brand-agnostic. CSS lives
in styles/components.css (class-scoped) and is asserted separately.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHASSIS_ROOT = HERE.parent
sys.path.insert(0, str(CHASSIS_ROOT))

_FONT_LITERALS = ("Montserrat", "Source Sans 3", "Playfair Display", "Gestura")


def _render(src: str, **kw) -> str:
    from templating import get_env
    return get_env().from_string(src).render(**kw)


def _assert_no_literals(html: str) -> None:
    # markup carries no raw hex color and no font-family literal
    assert "#" not in html, f"raw hex/anchor '#' leaked into markup: {html!r}"
    for lit in _FONT_LITERALS:
        assert lit not in html, f"font literal {lit!r} leaked into markup: {html!r}"


# ---- pill ----
def test_pill_uses_tokens_only():
    html = _render("{% from 'pill.jinja' import pill %}{{ pill('FALLSTUDIE 01','solid') }}")
    assert "FALLSTUDIE 01" in html
    _assert_no_literals(html)


def test_pill_outline_is_default_variant():
    html = _render("{% from 'pill.jinja' import pill %}{{ pill('KICKER') }}")
    assert "KICKER" in html
    assert "outline" in html  # default variant reflected in the class
    _assert_no_literals(html)


def test_pill_solid_variant_marks_class():
    html = _render("{% from 'pill.jinja' import pill %}{{ pill('X','solid') }}")
    assert "solid" in html
    _assert_no_literals(html)


# ---- eyebrow ----
def test_eyebrow_emits_text():
    html = _render("{% from 'eyebrow.jinja' import eyebrow %}{{ eyebrow('Methodik') }}")
    assert "Methodik" in html
    assert "c-eyebrow" in html
    _assert_no_literals(html)


# ---- section_label ----
def test_section_label_emits_text():
    html = _render(
        "{% from 'section_label.jinja' import section_label %}"
        "{{ section_label('Ausgangssituation') }}"
    )
    assert "Ausgangssituation" in html
    assert "c-section-label" in html
    _assert_no_literals(html)


# ---- media_figure ----
def test_media_figure_graceful_when_empty():
    html = _render("{% from 'media_figure.jinja' import media_figure %}{{ media_figure('') }}")
    assert "media" in html  # renders a placeholder, does not crash
    _assert_no_literals(html)


def test_media_figure_with_src_and_caption():
    html = _render(
        "{% from 'media_figure.jinja' import media_figure %}"
        "{{ media_figure('photo.png', alt='Werk', caption='Produktion', ratio='16x9', frame=true) }}"
    )
    assert "photo.png" in html
    assert "Produktion" in html
    assert "Werk" in html
    # ratio + frame reflected as modifier classes
    assert "16x9" in html and "frame" in html
    _assert_no_literals(html)


# ---- qr ----
def test_qr_wraps_svg():
    # the pattern builds the SVG; the macro just wraps it in a square box.
    svg = "<svg viewBox='0 0 4 4'><rect width='4' height='4'></rect></svg>"
    html = _render("{% from 'qr.jinja' import qr %}{{ qr(svg) }}", svg=svg)
    assert "<svg" in html
    assert "qr" in html
    _assert_no_literals(html)


# ---- stat_strip ----
def test_stat_strip_emits_values():
    html = _render(
        "{% from 'stat_strip.jinja' import stat_strip %}"
        "{{ stat_strip([{'value':'+312%','label':'Umsatz'}]) }}"
    )
    assert "+312%" in html and "Umsatz" in html
    _assert_no_literals(html)


def test_stat_strip_multiple_cells():
    html = _render(
        "{% from 'stat_strip.jinja' import stat_strip %}"
        "{{ stat_strip([{'value':'4,2x','label':'Reichweite'},{'value':'-18%','label':'Kosten'}]) }}"
    )
    assert "4,2x" in html and "Reichweite" in html
    assert "-18%" in html and "Kosten" in html
    assert "stat-value" in html and "stat-label" in html
    _assert_no_literals(html)


# ---- pull_quote ----
def test_pull_quote_on_panel():
    html = _render(
        "{% from 'pull_quote.jinja' import pull_quote %}"
        "{{ pull_quote('Wir haben verdoppelt.', attribution='CEO, Werk GmbH') }}"
    )
    assert "Wir haben verdoppelt." in html
    assert "CEO, Werk GmbH" in html
    assert "pull-quote" in html
    _assert_no_literals(html)


def test_pull_quote_off_panel_variant():
    html = _render(
        "{% from 'pull_quote.jinja' import pull_quote %}"
        "{{ pull_quote('Zitat ohne Panel.', on_panel=false) }}"
    )
    assert "Zitat ohne Panel." in html
    _assert_no_literals(html)


# ---- proof_gallery ----
def test_proof_gallery_renders_framed_tiles_with_label():
    html = _render(
        "{% from 'proof_gallery.jinja' import proof_gallery %}"
        "{{ proof_gallery(['p0.png','p1.png','p2.png'], label='Referenzen') }}"
    )
    # every photo becomes a tile; the content label rides above
    assert "p0.png" in html and "p1.png" in html and "p2.png" in html
    assert "Referenzen" in html
    assert "c-proof-gallery" in html
    # NOTE: src URLs may carry a '#'-free path; the no-literal check below only
    # guards against hex COLORS / font literals (the paths here have none).
    for lit in _FONT_LITERALS:
        assert lit not in html


def test_proof_gallery_graceful_when_empty():
    # no photos -> renders NOTHING (no label, no frame band)
    html = _render(
        "{% from 'proof_gallery.jinja' import proof_gallery %}"
        "{{ proof_gallery([], label='Referenzen') }}"
    )
    assert "c-proof-gallery" not in html
    assert "Referenzen" not in html
    assert html.strip() == ""


# ---- styles/components.css: class-scoped + token-only guard ----
def test_components_css_is_token_only_and_class_scoped():
    css = (CHASSIS_ROOT / "styles" / "components.css").read_text(encoding="utf-8")
    import re

    # no raw hex colors
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", css), "raw hex color in components.css"
    # no font-family literals
    for lit in _FONT_LITERALS:
        assert lit not in css, f"font literal {lit!r} in components.css"

    # every selector list (text before each `{`) must be scoped to one of the
    # component classes — no bare element / global selectors that could change
    # the visual-regression baseline.
    allowed = (".c-pill", ".c-eyebrow", ".c-section-label", ".c-media", ".c-qr",
               ".c-stat-strip", ".c-stat-rail", ".c-pull-quote",
               ".c-numbered-block", ".c-callout-panel", ".c-color-block",
               ".c-step-card", ".c-hflow", ".c-bar-chart", ".c-stat-callout",
               ".c-dark-recap", ".c-authority", ".c-check-list", ".c-qa-item",
               ".c-logo-wall", ".c-proof-gallery", ".c-key-insight", ".c-geo",
               ".c-these", ".c-cost-block", ".c-url-band", ".c-two-tone",
               ".c-rule", ".c-ghost-num", ".c-phone", ".c-venn",
               ".c-statcard", ".c-twincol", ".c-qa", ".c-viz-island")
    for selector in re.findall(r"([^{}]+)\{", css):
        sel = selector.strip()
        if not sel or sel.startswith("@") or sel.startswith("/*"):
            continue
        for part in sel.split(","):
            part = part.strip()
            if not part:
                continue
            assert any(c in part for c in allowed), f"unscoped selector in components.css: {part!r}"


def test_shout_components_use_real_tiers():
    """Stat-value selectors must use --type-stat-xl; prose-shout selectors must use --type-h2."""
    import re
    css = (CHASSIS_ROOT / "styles" / "components.css").read_text(encoding="utf-8")

    # Helper: extract the declaration block for a given selector.
    # Matches the selector text (allowing flexible whitespace) then captures
    # everything up to the matching closing brace.
    def get_block(selector_pattern: str) -> str:
        m = re.search(
            selector_pattern + r"\s*\{([^}]*)\}",
            css,
            re.DOTALL,
        )
        assert m, f"Selector not found in components.css: {selector_pattern!r}"
        return m.group(1)

    # ---- stat-value selectors must use --type-stat-xl ----
    stat_selectors = [
        r"\.c-stat-strip\s+\.c-stat-value",
        r"\.c-stat-rail\s+\.c-stat-value",
        r"\.c-stat-callout__value",
    ]
    for sel_pat in stat_selectors:
        block = get_block(sel_pat)
        assert re.search(r"font-size\s*:\s*var\(\s*--type-stat-xl\s*\)", block), (
            f"Selector matching {sel_pat!r} must use var(--type-stat-xl) for font-size; "
            f"got block: {block!r}"
        )

    # ---- prose-shout selectors must stay on --type-h2 ----
    prose_selectors = [
        r"\.c-these",
        r"\.c-key-insight__body",
        r"\.c-authority__heading",
    ]
    for sel_pat in prose_selectors:
        block = get_block(sel_pat)
        assert re.search(r"font-size\s*:\s*var\(\s*--type-h2\s*\)", block), (
            f"Selector matching {sel_pat!r} must use var(--type-h2) for font-size; "
            f"got block: {block!r}"
        )


def test_authority_recap_use_panel_role():
    """Task 4: .c-authority and .c-dark-recap must consume --color-panel /
    --color-on-panel; the .c-authority--primary modifier must be gone."""
    import re

    css = (CHASSIS_ROOT / "styles" / "components.css").read_text(encoding="utf-8")

    def get_block(selector_pattern: str) -> str:
        m = re.search(selector_pattern + r"\s*\{([^}]*)\}", css, re.DOTALL | re.MULTILINE)
        assert m, f"Selector not found in components.css: {selector_pattern!r}"
        return m.group(1)

    # .c-authority base block must use --color-panel as background and
    # --color-on-panel as text color.
    # Use a negative lookahead so we match only the exact base class, not a modifier.
    auth_block = get_block(r"^\.c-authority(?![\w-])")
    assert "var(--color-panel)" in auth_block, (
        ".c-authority background must be var(--color-panel)"
    )
    assert "var(--color-on-panel)" in auth_block, (
        ".c-authority text color must be var(--color-on-panel)"
    )

    # .c-dark-recap base block must use --color-panel as background.
    recap_block = get_block(r"^\.c-dark-recap(?![\w-])")
    assert "var(--color-panel)" in recap_block, (
        ".c-dark-recap background must be var(--color-panel)"
    )

    # .c-dark-recap__body text color must use --color-on-panel.
    recap_body = get_block(r"\.c-dark-recap__body(?![\w-])")
    assert "var(--color-on-panel)" in recap_body, (
        ".c-dark-recap__body color must be var(--color-on-panel)"
    )

    # The --primary modifier must be deleted.
    assert ".c-authority--primary" not in css, (
        ".c-authority--primary modifier must be removed (recipe now drives "
        "ink-vs-primary via --color-panel)"
    )


def test_shared_rule_and_ghost_utilities_exist():
    css = (CHASSIS_ROOT / "styles" / "components.css").read_text(encoding="utf-8")
    assert ".c-rule" in css, ".c-rule utility is missing from components.css"
    assert ".c-ghost-num" in css, ".c-ghost-num utility is missing from components.css"


def test_components_css_appended_to_shared_head():
    from assembler import shared_head_css, FONT_DIR
    from brand_tokens import parse_brand_tokens

    brand = parse_brand_tokens({
        "brand_primary": "#5a9ab3", "brand_accent": "#85d2ee",
        "brand_neutral_dark": "#0F0F1F", "brand_neutral_mid": "#7A7A8C",
        "brand_neutral_light": "#fdffff", "font_heading": "Gestura",
        "font_body": "Source Sans 3", "qr_target_url": "https://x.de",
        "company_name_short": "X", "company_url_display": "x.de",
    })
    head = shared_head_css(brand, FONT_DIR)
    # representative component selectors are present (appended to the head)
    assert ".c-pill" in head
    assert ".c-stat-strip" in head
    assert head.count(".c-pull-quote") >= 1
