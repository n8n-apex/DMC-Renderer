"""Regression: chart_svgs() must select chart components by an EXPLICIT marker,
not by tail position.

Background (infection-map #14): the producer appends chart SVGs last to a page's
`components`, and the old `chart_svgs()` tail-sliced `components[-n:]`. That breaks
silently the moment any non-chart component is appended after a chart (reorder).
The fix: every chart SVG carries a `dmc:chart` sentinel (added in `_frame`, the
single wrapper all chart renderers return through), and selection prefers marked
components -- falling back to the legacy tail-slice only for pre-marker packages.

These tests pin the PURE selection helper so the contract is fast + dependency-free.
"""
from __future__ import annotations

from patterns.base import _select_chart_svgs

_MARK = "<!-- dmc:chart -->"


def test_marker_selection_is_robust_to_reordering():
    # A marked chart sits in the MIDDLE; a non-chart was appended after it.
    # Tail-slicing would wrongly return the appended non-chart.
    resolved = [
        "<svg>nonchart-a</svg>",
        f"<svg>{_MARK}donut</svg>",
        "<svg>nonchart-appended-after</svg>",
    ]
    got = _select_chart_svgs(resolved, 1)
    assert got == [f"<svg>{_MARK}donut</svg>"]


def test_multiple_marked_charts_selected_in_order():
    resolved = [
        f"<svg>{_MARK}a</svg>",
        "<svg>nonchart</svg>",
        f"<svg>{_MARK}b</svg>",
    ]
    assert _select_chart_svgs(resolved, 2) == [
        f"<svg>{_MARK}a</svg>",
        f"<svg>{_MARK}b</svg>",
    ]


def test_legacy_tail_fallback_when_no_markers():
    # Pre-marker package: no sentinel anywhere -> preserve the old tail-slice.
    resolved = ["<svg>nonchart</svg>", "<svg>legacy-chart</svg>"]
    assert _select_chart_svgs(resolved, 1) == ["<svg>legacy-chart</svg>"]


def test_marker_count_caps_at_spec_count():
    # Defensive: never return more charts than the page declares specs for.
    resolved = [f"<svg>{_MARK}a</svg>", f"<svg>{_MARK}b</svg>"]
    assert _select_chart_svgs(resolved, 1) == [f"<svg>{_MARK}a</svg>"]


def test_none_entries_dropped_and_zero_specs_empty():
    assert _select_chart_svgs([None, "<svg>x</svg>"], 0) == []
    assert _select_chart_svgs([None, None], 1) == []
    assert _select_chart_svgs([None, f"<svg>{_MARK}c</svg>"], 1) == [f"<svg>{_MARK}c</svg>"]
