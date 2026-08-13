"""G13 (takeaways label), G14 (cost-of-inaction on treated summary),
G22 (umlaut must not rewrite identity fields)."""
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / ".." / "research" / "v7-renderer"))

from build_live import _fix_umlauts_deep  # noqa: E402


def test_takeaways_are_not_labelled_zielgruppe() -> None:
    """G13: ST-02 takeaway items must render under 'Was Sie mitnehmen', never
    'Zielgruppe des Reports'."""
    from patterns.st_02 import _TK_LABEL, _ZG_LABEL, render
    from patterns.base import RenderContext
    from grammar_loader import load_grammar
    from brand_tokens import parse_brand_tokens

    data = {
        "title": "Ausblick",
        "takeaways": ["Sie verstehen den Hebel.", "Sie kennen die Reihenfolge."],
    }
    brand = parse_brand_tokens({
        "brand_primary": "#171714", "brand_accent": "#c94e2c",
        "brand_neutral_dark": "#171714", "brand_neutral_mid": "#656158",
        "brand_neutral_light": "#f5f1e8", "font_heading": "Montserrat",
        "font_body": "Source Sans 3", "qr_target_url": "https://example.de",
        "company_name_short": "Example", "company_url_display": "example.de",
    })
    ctx = RenderContext(brand=brand, grammar=load_grammar(), package_dir="fixtures/apex")
    html = render({"st_type": "ST-02", "data": data}, ctx).html
    assert _TK_LABEL in html, "takeaways must render under the takeaways label"
    assert "Was Sie mitnehmen" in html
    # a zielgruppe block must not be emitted for takeaways
    assert "Zielgruppe des Reports" not in html


def test_umlaut_rewrite_preserves_identity_names() -> None:
    """G22: a curated identity name must survive the umlaut pass."""
    page = {
        "author": {"name": "Christoph Waehrend", "role": "Gruender"},
        "kunde": {"name": "Waehrend & Söhne", "company_url": "https://waehrend.example"},
        "body": "Die ueberlastung sinkt.",
    }
    fixed = _fix_umlauts_deep(page)
    assert fixed["author"]["name"] == "Christoph Waehrend", "author.name must be exempt"
    assert fixed["kunde"]["name"] == "Waehrend & Söhne", "kunde.name must be exempt"
    assert "ueberlastung" not in fixed["body"], "prose copy must still be fixed"


def test_umlaut_still_fixes_prose() -> None:
    assert _fix_umlauts_deep("Der Ablauf wird ueberarbeitet.") == "Der Ablauf wird überarbeitet."


def test_treated_fazit_carries_cost_of_inaction() -> None:
    """G14: the cost-of-inaction must reach the treated summary path (it was
    read only by the legacy pattern, so it never rendered live)."""
    from treatment_engine import _adapt_fazit, TreatmentData

    data = {
        "these": "Die zweite Schicht kostet 68 Stunden pro Woche.",
        "kosten_des_nichtstuns": "Jedes Jahr ohne Umbau bindet 310.000 €.",
    }
    td = _adapt_fazit(TreatmentData(), {}, data, None)
    labels = [s.get("label") for s in td.stats]
    assert "Kosten des Nichtstuns" in labels, "the cost block must be mapped onto the treated summary"
    assert any("310.000 €" in s.get("value", "") for s in td.stats)
