"""TDD for the MAGNITUDE viz family (components/viz_magnitude.jinja):
stat_strip, money_bar, mega_numeral, kpi_card, ranked_bars. Every figure is
shown VERBATIM; bar widths derive from the same string via the `num` filter.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from templating import get_env  # noqa: E402


def _r(macro, v):
    return get_env().from_string(
        "{%% from 'viz_magnitude.jinja' import %s %%}{{ %s(v) }}" % (macro, macro)
    ).render(v=v)


# ---- stat_strip ----
def test_stat_strip_values_verbatim_and_cells():
    out = _r("stat_strip", {"preset": "stat_strip", "items": [
        {"value": "30 %", "label": "Kosten"},
        {"value": "60 %", "label": "kein Wert"},
        {"value": "30 bis 50 %", "label": "eliminierbar"}]})
    assert "30 %" in out and "60 %" in out and "30 bis 50 %" in out
    assert "c-viz-strip" in out
    assert out.count("c-viz-strip__cell") == 3


def test_stat_strip_needs_items():
    assert _r("stat_strip", {"preset": "stat_strip", "items": []}).strip() == ""
    assert _r("stat_strip", {"preset": "stat_strip"}).strip() == ""


# ---- money_bar ----
def test_money_bar_value_verbatim():
    out = _r("money_bar", {"preset": "money_bar",
        "value": "€700 bis €800 Millionen", "label": "jährlich"})
    assert "€700 bis €800 Millionen" in out and "jährlich" in out
    assert "c-viz-money" in out


def test_money_bar_needs_value():
    assert _r("money_bar", {"preset": "money_bar", "label": "x"}).strip() == ""


# ---- mega_numeral ----
def test_mega_numeral_value_and_label():
    out = _r("mega_numeral", {"preset": "mega_numeral",
        "value": "50 %", "label": "Burnout"})
    assert "50 %" in out and "Burnout" in out and "c-viz-mega" in out


def test_mega_numeral_needs_value():
    assert _r("mega_numeral", {"preset": "mega_numeral", "label": "x"}).strip() == ""


# ---- kpi_card ----
def test_kpi_card_value_and_label():
    out = _r("kpi_card", {"preset": "kpi_card", "value": "61%", "label": "Agentic AI"})
    assert "61%" in out and "Agentic AI" in out and "c-viz-kpi" in out


def test_kpi_card_needs_value():
    assert _r("kpi_card", {"preset": "kpi_card"}).strip() == ""


# ---- ranked_bars ----
def test_ranked_bars_widths_derive_from_figures():
    out = _r("ranked_bars", {"preset": "ranked_bars", "items": [
        {"figure": "30 Min", "label": "Onboarding"},
        {"figure": "60 Min", "label": "Copy"}]})
    flat = out.replace(" ", "")
    # the larger figure (60) is the full-width bar; the smaller (30) scales to 50%
    assert "width:100%" in flat and "width:50%" in flat
    assert "30 Min" in out and "60 Min" in out and "c-viz-ranked" in out


def test_ranked_bars_needs_items():
    assert _r("ranked_bars", {"preset": "ranked_bars", "items": []}).strip() == ""
