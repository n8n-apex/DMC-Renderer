"""Footer A chrome regression.

The deck already runs a HEADER (wordmark top-left + booking URL top-right), so the
footer must COMPLEMENT it, not duplicate it: a full-width teal hairline rule at the
content-box bottom + the page number moved to @bottom-right in navy (--color-ink),
suppressed on the full-bleed page types (cover/breather/back-cover/dark beats).

Binds the footer so it cannot silently regress. Run: pytest tests/test_footer.py -v
"""
from assembler import shared_head_css, FONT_DIR
from brand_tokens import parse_brand_tokens


def _brand():
    return parse_brand_tokens({
        "brand_primary": "#4A7C7E", "brand_accent": "#4A7C7E",
        "brand_neutral_dark": "#2E3E50", "brand_neutral_mid": "#7A7A8C",
        "brand_neutral_light": "#F6F3ED", "font_heading": "Source Serif 4",
        "font_body": "Source Sans 3", "qr_target_url": "https://apex-consulting.ai",
        "company_name_short": "APEX CONSULTING", "company_url_display": "apex-consulting.ai",
    })


def test_chromium_footer_folio_right_with_teal_rule():
    head = shared_head_css(_brand(), FONT_DIR, engine="chromium")
    # page number now lives bottom-RIGHT in ink (navy), not muted bottom-left
    assert "@bottom-right" in head
    assert "counter(page)" in head
    # full-width teal hairline rule on the content-box bottom (mirrors the header top border)
    assert "border-bottom: 0.2mm solid var(--color-accent)" in head
    # the folio alone carries the ACCENT (the 2026-07-13 footer redesign: one
    # level typographic band, wordmark + url muted, folio accent).
    assert "color: var(--color-accent)" in head.split("@bottom-right", 1)[1][:200]


def test_full_bleed_pages_suppress_the_footer_rule():
    head = shared_head_css(_brand(), FONT_DIR, engine="chromium")
    # the cover/breather/back-cover/dark beats drop both header and footer rules
    assert "border-bottom: none" in head


def test_weasyprint_footer_folio_right():
    head = shared_head_css(_brand(), FONT_DIR, engine="weasyprint")
    assert "@bottom-right" in head
    assert "string(pagefolio)" in head
