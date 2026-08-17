"""Bridge: v3 typed contract elements into the v2 designed preset library.

The v3 rebuild recreated contracts and gates but rendered its own ad-hoc
HTML, orphaning the component library (42 components, ~50 viz preset macros,
token-driven, grounding-safe) that the v2 renderer already draws with. This
module is the missing connection: a v3 element carries claim IDs and content
refs, this builds the preset spec the v2 macro expects, and the macro draws
the device.

Grounding is preserved end to end: every printed figure is the claim's exact
`normalized_value`, and every bar geometry is derived by the macros from that
same string via the `num` filter, so a numeral and its mark can never
diverge. A spec the library cannot draw renders nothing rather than a
fabricated device.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Mapping

RENDERER_ROOT = Path(__file__).resolve().parent.parent
if str(RENDERER_ROOT) not in sys.path:
    sys.path.insert(0, str(RENDERER_ROOT))

from templating import get_env  # noqa: E402  (v2 env: components + num/fitfs)


_DISPATCH_TEMPLATE = "{% from 'viz.jinja' import viz %}{{ viz(specs) }}"


def render_preset(spec: dict, uid: int = 0) -> str:
    """Render one preset spec through the v2 dispatch. Empty when undrawable."""
    if not spec or not spec.get("preset"):
        return ""
    environment = get_env()
    return environment.from_string(_DISPATCH_TEMPLATE).render(specs=[spec]).strip()


def _value(claim_values: Mapping[str, str], claim_id: str) -> str:
    if claim_id not in claim_values:
        raise KeyError(f"missing claim value {claim_id}")
    return claim_values[claim_id]


def _label(content_by_ref: Mapping[str, str], content_ref: str) -> str:
    if content_ref not in content_by_ref:
        raise KeyError(f"missing content reference {content_ref}")
    return content_by_ref[content_ref]


def grouped_comparison_spec(
    element: Any,
    *,
    content_by_ref: Mapping[str, str],
    claim_values: Mapping[str, str],
) -> dict:
    """A computed before/after difference becomes the ba_bars transform device."""
    pair: dict[str, Any] = {
        "label": _label(content_by_ref, element.label_content_ref),
        "before": {"value": _value(claim_values, element.before_claim_id)},
        "after": {"value": _value(claim_values, element.after_claim_id)},
    }
    if element.result_claim_id is not None:
        pair["delta"] = _value(claim_values, element.result_claim_id)
    return {"preset": "ba_bars", "pairs": [pair]}


def formula_ladder_spec(
    element: Any,
    *,
    content_by_ref: Mapping[str, str],
    claim_values: Mapping[str, str],
) -> dict:
    """A computation chain becomes the calculation ladder landing on its result."""
    return {
        "preset": "formula_ladder",
        "titel": _label(content_by_ref, element.label_content_ref),
        "schritte": [
            {"wert": _value(claim_values, claim_id)}
            for claim_id in element.operand_claim_ids
        ],
        "ergebnis": {"wert": _value(claim_values, element.result_claim_id)},
    }


def series_spec(
    element: Any,
    claim_ids: tuple[str, ...],
    *,
    content_by_ref: Mapping[str, str],
    claim_values: Mapping[str, str],
) -> dict:
    """Entity-over-time and part rows become the column chart."""
    return {
        "preset": "column_chart",
        "titel": _label(content_by_ref, element.label_content_ref),
        "punkte": [
            {"wert": _value(claim_values, claim_id)} for claim_id in claim_ids
        ],
    }


def proportion_spec(
    element: Any,
    claim_ids: tuple[str, ...],
    *,
    content_by_ref: Mapping[str, str],
    claim_values: Mapping[str, str],
) -> dict:
    """Part-to-whole segments become the 100 percent stacked bar."""
    label = _label(content_by_ref, element.label_content_ref)
    return {
        "preset": "stacked_bar_100",
        "titel": label,
        "segmente": [
            {"wert": _value(claim_values, claim_id), "label": label}
            for claim_id in claim_ids
        ],
    }


def stat_strip_spec(values_and_labels: tuple[tuple[str, str], ...]) -> dict:
    """Several claim figures on one face become one at-a-glance proof strip."""
    return {
        "preset": "stat_strip",
        "items": [
            {"value": value, "label": label} for value, label in values_and_labels
        ],
    }


def share_spec(
    element: Any,
    *,
    content_by_ref: Mapping[str, str],
    claim_values: Mapping[str, str],
) -> dict:
    """One stated share becomes the donut: figure verbatim, arc from it.

    The remainder of the ring is the unstated rest. It carries no number
    and no label, because the prose never stated one.
    """
    figure = _value(claim_values, element.claim_id)
    percent = _percent(figure)
    if percent is None:
        return {}
    return {
        "preset": "donut",
        "figure": figure,
        "percent": percent,
        "label": _label(content_by_ref, element.label_content_ref),
    }


def _percent(figure: str) -> float | None:
    """The share's magnitude, or None when the figure will not read as one."""
    cleaned = figure.replace("%", "").replace(" ", "").replace(" ", "")
    cleaned = cleaned.replace(".", "").replace(",", ".") if "," in cleaned else cleaned
    try:
        value = float(cleaned)
    except ValueError:
        return None
    return value if 0.0 <= value <= 100.0 else None


def step_cascade_spec(
    element: Any,
    *,
    content_by_ref: Mapping[str, str],
    title: str | None = None,
) -> dict:
    """An ordered mechanism becomes the designed cascade, not a bullet list.

    The theory families were built around "one explanatory device" in the
    mechanism column. A plain <ol> left that column dead, so an ordered
    process placed in a dedicated device region is drawn as the cascade the
    preset library already designs.
    """
    steps = [
        {"n": index, "title": _label(content_by_ref, ref)}
        for index, ref in enumerate(element.item_content_refs, start=1)
    ]
    if not steps:
        return {}
    spec: dict[str, Any] = {"preset": "step_cascade", "steps": steps}
    if title:
        spec["title"] = title
    return spec
