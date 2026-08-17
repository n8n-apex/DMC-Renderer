"""TDD for the TRANSFORMATION viz family (components/viz_transform.jinja):
ba_bars, transform_arrow, completion_ring. Brand-agnostic, graceful-omit,
verbatim figures, render-derived geometry, page-unique SVG ids.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from templating import get_env  # noqa: E402


def _r(macro, v):
    t = get_env().from_string(
        "{%% from 'viz_transform.jinja' import %s %%}{{ %s(v) }}" % (macro, macro)
    )
    return t.render(v=v)


def _dispatch(specs):
    return get_env().from_string(
        "{% from 'viz.jinja' import viz %}{{ viz(specs) }}"
    ).render(specs=specs)


# ---- bar_compare (horizontal before/after EXHIBIT) ----
def test_bar_compare_renders_exhibit():
    out = _r("bar_compare", {"preset": "bar_compare", "title": "Bearbeitungszeit", "unit": "Min",
        "pairs": [
            {"label": "Onboarding", "before": {"value": "30"}, "after": {"value": "2"}, "delta": "−93 %"},
            {"label": "Copywriting", "before": {"value": "60"}, "after": {"value": "5"}, "delta": "−92 %"}],
        "source": "Conesso 2026"})
    flat = out.replace(" ", "")
    assert "c-viz-barc" in out
    assert "Onboarding" in out and "Copywriting" in out
    assert "30" in out and "60" in out and "2" in out and "5" in out      # values VERBATIM
    assert "−93 %" in out and "−92 %" in out                              # deltas
    assert "Vorher" in out and "Nachher" in out                          # legend
    assert "width:100" in flat and "width:50" in flat                    # geometry: max=60 -> 60=100%, 30=50%
    assert "Bearbeitungszeit" in out and "Conesso 2026" in out           # title + source


def test_bar_compare_geometry_scales_to_max():
    out = _r("bar_compare", {"preset": "bar_compare",
        "pairs": [{"label": "A", "before": {"value": "40"}, "after": {"value": "10"}}]})
    flat = out.replace(" ", "")
    assert "width:100" in flat and "width:25" in flat   # max=40 -> 40=100%, 10=25%


def test_bar_compare_needs_pairs():
    assert _r("bar_compare", {"preset": "bar_compare"}).strip() == ""


# ---- ba_bars ----
def test_ba_bars_shows_verbatim_values_and_delta():
    out = _r("ba_bars", {"preset": "ba_bars", "unit": "Min", "pairs": [
        {"label": "Onboarding", "before": {"value": "30"},
         "after": {"value": "2"}, "delta": "−93 %"}]})
    assert "30" in out and "2" in out and "Onboarding" in out
    assert "−93 %" in out
    assert "c-viz-ba" in out


def test_ba_bars_after_bar_shorter_than_before():
    out = _r("ba_bars", {"preset": "ba_bars", "pairs": [
        {"label": "x", "before": {"value": "30"}, "after": {"value": "2"}}]})
    flat = out.replace(" ", "")
    assert "height:100%" in flat   # before bar full (pair max)
    assert "height:6%" in flat     # after bar floor(2/30*100)=6


def test_ba_bars_empty_renders_nothing():
    assert _r("ba_bars", {"preset": "ba_bars", "pairs": []}).strip() == ""


def test_completion_ring_center_autofits_long_label():
    """Regression (the "6 von 6" bug): a long center label shrinks to fit the
    ring's inner hole and can never overflow the circle; a short label keeps the
    base size."""
    import re

    long_out = _r("completion_ring", {"preset": "completion_ring",
                                       "center": "6 von 6", "percent": 100})
    short_out = _r("completion_ring", {"preset": "completion_ring",
                                       "center": "6/6", "percent": 100})
    pat = r"c-viz-ring__center[^>]*font-size:([\d.]+)px"
    long_fs = float(re.search(pat, long_out).group(1))
    short_fs = float(re.search(pat, short_out).group(1))
    assert short_fs == 30.0          # short label keeps the base size
    assert long_fs < short_fs        # long label shrank to fit
    assert long_fs < 20.0            # sized down enough to sit inside the hole


# ---- transform_arrow ----
def test_transform_arrow_shows_both_verbatim():
    out = _r("transform_arrow", {"preset": "transform_arrow",
        "from": {"value": "24 Std.", "label": "Antwortzeit"},
        "to": {"value": "Minuten", "label": "automatisiert"}})
    assert "24 Std." in out and "Minuten" in out and "Antwortzeit" in out
    assert "c-viz-arrow" in out


def test_transform_arrow_needs_both_sides():
    assert _r("transform_arrow",
              {"preset": "transform_arrow", "from": {"value": "24"}}).strip() == ""


# ---- completion_ring ----
def test_completion_ring_full_and_center_verbatim():
    out = _r("completion_ring", {"preset": "completion_ring",
        "percent": 100, "center": "6/6", "label": "Prozesse"})
    assert "6/6" in out and "Prozesse" in out and "<svg" in out
    assert "c-viz-ring" in out


def test_completion_ring_needs_center():
    assert _r("completion_ring",
              {"preset": "completion_ring", "percent": 50}).strip() == ""


def test_completion_ring_ids_unique_on_one_page():
    # two equal-center rings through the dispatch must NOT share a gradient id
    out = _dispatch([
        {"preset": "completion_ring", "percent": 100, "center": "100%", "label": "a"},
        {"preset": "completion_ring", "percent": 100, "center": "100%", "label": "b"},
    ])
    import re
    ids = re.findall(r'id="(vizring[^"]*)"', out)
    assert len(ids) == 2 and ids[0] != ids[1], ids
