"""TDD for the PROPORTION viz family (components/viz_proportion.jinja):
donut, split_bar, gauge, radial_cluster, icon_array.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from templating import get_env  # noqa: E402


def _r(macro, v):
    return get_env().from_string(
        "{%% from 'viz_proportion.jinja' import %s %%}{{ %s(v) }}" % (macro, macro)
    ).render(v=v)


def _dispatch(specs):
    return get_env().from_string(
        "{% from 'viz.jinja' import viz %}{{ viz(specs) }}"
    ).render(specs=specs)


# ---- donut ----
def test_donut_center_verbatim_and_svg():
    out = _r("donut", {"preset": "donut", "percent": 90, "figure": "90 %", "label": "CEOs"})
    assert "90 %" in out and "CEOs" in out and "<svg" in out and "c-viz-donut" in out


def test_donut_needs_figure():
    assert _r("donut", {"preset": "donut", "percent": 90}).strip() == ""


# ---- split_bar ----
def test_split_bar_widths_and_percents():
    out = _r("split_bar", {"preset": "split_bar",
        "a": {"percent": 40, "label": "Return"}, "b": {"percent": 60, "label": "kein Return"}})
    flat = out.replace(" ", "")
    assert "width:40%" in flat and "width:60%" in flat
    assert "40%" in out and "60%" in out and "c-viz-split" in out


def test_split_bar_needs_both():
    assert _r("split_bar", {"preset": "split_bar", "a": {"percent": 40}}).strip() == ""


# ---- gauge ----
def test_gauge_band_and_center():
    out = _r("gauge", {"preset": "gauge", "lo": 30, "hi": 50, "figure": "30–50 %", "label": "Effizienz"})
    assert "30–50 %" in out and "<path" in out and "c-viz-gauge" in out


def test_gauge_long_figure_autoshrinks_to_fit():
    # Regression: a long center figure ("30 bis 50 %") used to overflow the arc
    # because the gauge center had a FIXED font-size while donut/cluster center
    # labels auto-shrink (fitfs). The gauge center must now carry a fitfs inline
    # font-size BELOW the 26px base so the figure stays inside the semicircle.
    out = _r("gauge", {"preset": "gauge", "lo": 30, "hi": 50,
                       "figure": "30 bis 50 %", "label": "Reduktion"})
    m = re.search(r"c-viz-gauge__center[^>]*font-size:([0-9.]+)px", out)
    assert m, "gauge center must carry an inline fitfs font-size"
    assert float(m.group(1)) < 26.0


def test_gauge_short_figure_keeps_base_size():
    out = _r("gauge", {"preset": "gauge", "lo": 40, "hi": 40, "figure": "47 %", "label": "x"})
    m = re.search(r"c-viz-gauge__center[^>]*font-size:([0-9.]+)px", out)
    assert m and float(m.group(1)) == 26.0
    assert 'pathLength="100"' in out


def test_gauge_needs_figure():
    assert _r("gauge", {"preset": "gauge", "lo": 30, "hi": 50}).strip() == ""


# ---- radial_cluster ----
def test_radial_cluster_rings_and_unique_ids():
    out = _r("radial_cluster", {"preset": "radial_cluster", "rings": [
        {"percent": 58, "figure": "58 %", "label": "a"},
        {"percent": 61, "figure": "61 %", "label": "b"}]})
    assert "58 %" in out and "61 %" in out and out.count("<svg") == 2
    ids = re.findall(r'id="(vizcluster[^"]*)"', out)
    assert len(ids) == 2 and ids[0] != ids[1], ids


def test_radial_cluster_ids_unique_across_specs_on_page():
    out = _dispatch([
        {"preset": "radial_cluster", "rings": [{"percent": 50, "figure": "50 %", "label": "x"}]},
        {"preset": "radial_cluster", "rings": [{"percent": 50, "figure": "50 %", "label": "y"}]},
    ])
    ids = re.findall(r'id="(vizcluster[^"]*)"', out)
    assert len(ids) == 2 and ids[0] != ids[1], ids


# ---- icon_array ----
def test_icon_array_filled_and_empty_counts():
    out = _r("icon_array", {"preset": "icon_array", "filled": 1, "total": 2,
        "figure": "rund 50 %", "label": "Burnout"})
    assert out.count("is-filled") == 1 and out.count("is-empty") == 1
    assert "rund 50 %" in out and "c-viz-iconarray" in out
    assert "ti-" not in out   # NO Tabler webfont — inline SVG only


def test_icon_array_needs_total():
    assert _r("icon_array", {"preset": "icon_array", "figure": "x", "total": 0}).strip() == ""


def test_ring_center_text_is_vertically_centered() -> None:
    """SVG center figures must be vertically centered on the circle's centre,
    not baseline-anchored (baseline-anchored text sits visibly above the
    middle — the "58%/61% inside the ring" bug). dominant-baseline=central
    puts the glyph CENTER on the y it is given."""
    html = (
        _r("donut", {"figure": "50 %", "percent": 50})
        + _r("gauge", {"figure": "30 %"})
        + _r("radial_cluster", {"rings": [{"percent": 58, "figure": "58%", "label": "x"}]})
    )
    centers = re.findall(
        r'<text class="[^"]*__center" x="\d+" y="\d+" dominant-baseline="central"',
        html,
    )
    assert centers, "every center <text> must carry dominant-baseline=central"
    assert len(centers) >= 3, f"expected donut+gauge+cluster centers, got {len(centers)}"


def test_ring_center_text_vertical_center_in_transform() -> None:
    """completion_ring center (the "6 von 6" figure) must also be
    dominant-baseline=central on the circle's cy."""
    from templating import get_env

    html = get_env().from_string(
        "{% from 'viz_transform.jinja' import completion_ring %}{{ completion_ring(v) }}"
    ).render(v={"center": "6 von 6", "percent": 100})
    assert 'dominant-baseline="central"' in html
    m = re.search(r'<text class="c-viz-ring__center" x="60" y="(\d+)"', html)
    assert m and m.group(1) == "60", "ring center y must be the circle's cy=60"
