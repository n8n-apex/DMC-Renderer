"""Bridge: v3 contract elements into the SVG chart renderers.

`research/preprocessor/stages/charts_svg.py` holds six real chart renderers
(before/after bars, comparison columns, donut, line compare, money
infographic, cost-math strip). v3 never called any of them, so its devices
were limited to the handful of CSS presets the v2 bridge reaches. Two of the
six have no CSS equivalent at all: the money infographic and the cost-math
strip are exactly the devices Richard's cost pages carry.

Grounding rule, enforced here and in the spec models: the float drives the
geometry, the claim's own verbatim string drives the printed glyphs. A
German "13.160 €" parses to 13160.0 for the bar height and still prints
"13.160 €", never "13160". A claim whose magnitude cannot be read yields no
chart rather than a chart with an invented number.

Colour comes from CSS custom properties rather than hex, because the SVG is
inlined into a document whose `:root` already carries the compiled brand
tokens. The charts therefore follow the client's brand with no threading.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, Mapping

PREPROCESSOR_ROOT = Path(__file__).resolve().parents[3] / "preprocessor"
if str(PREPROCESSOR_ROOT) not in sys.path:
    sys.path.insert(0, str(PREPROCESSOR_ROOT))

from models_charts import (  # noqa: E402
    BeforeAfterBars,
    CostMathStrip,
    Donut,
    DonutSegment,
    LineCompare,
    LineSeries,
    MoneyInfographic,
    MoneyItem,
)
from stages.charts_svg import ChartTheme, render_chart_svg  # noqa: E402


# The document's own tokens, so a chart is never off-brand and follows a
# theme switch without being re-rendered.
BRAND_THEME = ChartTheme(
    ink="var(--ink)",
    paper="var(--paper)",
    primary="var(--accent)",
    accent="var(--accent-2, var(--accent))",
    muted="var(--muted)",
    font_family="inherit",
)

_MAGNITUDE = re.compile(r"-?\d[\d.\s]*(?:,\d+)?|-?\d+(?:\.\d+)?")


def magnitude(verbatim: str) -> float | None:
    """The number inside a German figure string, or None if there isn't one.

    "13.160 €" -> 13160.0, "4,9 von 5" -> 4.9, "30 Minuten" -> 30.0.
    A dot is a thousands separator and a comma is the decimal point, which
    is the opposite of the machine convention, so both are normalised here
    rather than by float() guessing.
    """
    match = _MAGNITUDE.search(verbatim or "")
    if match is None:
        return None
    token = match.group(0).strip().replace(" ", "").replace(" ", "")
    if "," in token:
        token = token.replace(".", "").replace(",", ".")
    elif token.count(".") == 1 and len(token.split(".")[1]) == 3:
        # A single dot with exactly three trailing digits is a thousands mark.
        token = token.replace(".", "")
    elif token.count(".") > 1:
        token = token.replace(".", "")
    try:
        return float(token)
    except ValueError:
        return None


def _value(claim_values: Mapping[str, str], claim_id: str) -> str:
    if claim_id not in claim_values:
        raise KeyError(f"missing claim value {claim_id}")
    return claim_values[claim_id]


def _label(content_by_ref: Mapping[str, str], content_ref: str | None) -> str | None:
    if not content_ref:
        return None
    return content_by_ref.get(content_ref)


def _is_money(text: str) -> bool:
    lowered = text.lower()
    return "€" in text or "eur" in lowered


def spec_for(
    element: Any,
    *,
    content_by_ref: Mapping[str, str],
    claim_values: Mapping[str, str],
) -> Any | None:
    """The chart spec this element earns, or None when SVG adds nothing."""
    kind = element.kind
    title = _label(content_by_ref, getattr(element, "label_content_ref", None))

    if kind == "grouped_comparison":
        before = _value(claim_values, element.before_claim_id)
        after = _value(claim_values, element.after_claim_id)
        before_n, after_n = magnitude(before), magnitude(after)
        if before_n is None or after_n is None:
            return None
        return BeforeAfterBars(
            title=title,
            before_label="vorher",
            before_value=before_n,
            before_text=before,
            after_label="nachher",
            after_value=after_n,
            after_text=after,
        )

    if kind == "formula_ladder":
        operand_texts = [
            _value(claim_values, claim_id) for claim_id in element.operand_claim_ids
        ]
        operands = [magnitude(text) for text in operand_texts]
        result_text = _value(claim_values, element.result_claim_id)
        result = magnitude(result_text)
        if result is None or any(value is None for value in operands):
            return None
        return CostMathStrip(
            title=title,
            operands=[value for value in operands if value is not None],
            operand_texts=operand_texts,
            operators=["+"] * max(0, len(operands) - 1),
            result=result,
            result_text=result_text,
        )

    if kind == "time_series":
        texts = [_value(claim_values, cid) for cid in element.point_claim_ids]
        points = [magnitude(text) for text in texts]
        if any(value is None for value in points):
            return None
        return LineCompare(
            title=title,
            x_labels=texts,
            series=[LineSeries(name=title, points=[v for v in points if v is not None])],
        )

    if kind in {"share", "distribution", "composition_breakdown"}:
        claim_ids = (
            (element.claim_id,)
            if kind == "share"
            else getattr(element, "segment_claim_ids", None)
            or getattr(element, "part_claim_ids", ())
        )
        texts = [_value(claim_values, claim_id) for claim_id in claim_ids]
        values = [magnitude(text) for text in texts]
        if not texts or any(value is None for value in values):
            return None
        # A breakdown denominated in money reads as a money infographic; a
        # breakdown of proportions reads as a ring.
        if all(_is_money(text) for text in texts):
            return MoneyInfographic(
                title=title,
                items=[
                    MoneyItem(label=title, value=value, text=text)
                    for value, text in zip(values, texts)
                ],
            )
        return Donut(
            title=title,
            segments=[
                DonutSegment(label=title, value=value, text=text)
                for value, text in zip(values, texts)
            ],
        )

    return None


def render(
    element: Any,
    *,
    content_by_ref: Mapping[str, str],
    claim_values: Mapping[str, str],
) -> str:
    """One inlined SVG chart, or empty when this element earns no chart."""
    spec = spec_for(
        element, content_by_ref=content_by_ref, claim_values=claim_values
    )
    if spec is None:
        return ""
    return render_chart_svg(spec, BRAND_THEME)
