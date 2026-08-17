"""Dispatch tests for the data-viz PRESET layer (components/viz.jinja).

Mirrors the diagram proof-layer's dispatch shape: a single `viz(specs)` macro
switches on each spec's `preset` and delegates to a family macro. Graceful at
every hop — empty/None specs and unknown presets render nothing.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from templating import get_env  # noqa: E402


def _render(specs):
    tmpl = get_env().from_string("{% from 'viz.jinja' import viz %}{{ viz(specs) }}")
    return tmpl.render(specs=specs)


def test_empty_renders_nothing():
    assert _render(None).strip() == ""
    assert _render([]).strip() == ""


def test_unknown_preset_skipped():
    assert _render([{"preset": "nope"}]).strip() == ""


def test_list_iterates_in_order():
    out = _render([
        {"preset": "mega_numeral", "value": "0", "label": "A"},
        {"preset": "mega_numeral", "value": "100+", "label": "B"},
    ])
    assert out.index("0") < out.index("100+")
