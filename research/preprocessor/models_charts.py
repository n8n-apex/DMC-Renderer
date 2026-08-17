"""Rhetorical chart-DATA models (DNA §C5). Persuasion data only — NO axis
chrome; the renderer draws. Each variant carries a `kind` discriminator.
parse_chart() validates a dict into the right variant by `kind`; never
raises. Brand-agnostic: chart shapes only, no client value.
"""
from __future__ import annotations

from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

_P = ConfigDict(extra="forbid")


class BeforeAfterBars(BaseModel):
    model_config = _P
    kind: Literal["before_after_bars"] = "before_after_bars"
    title: Optional[str] = None
    unit: Optional[str] = None
    before_label: Optional[str] = None
    before_value: Optional[float] = None
    before_text: Optional[str] = None
    after_label: Optional[str] = None
    after_value: Optional[float] = None
    after_text: Optional[str] = None


class LineSeries(BaseModel):
    model_config = _P
    name: Optional[str] = None
    points: list[float] = Field(default_factory=list)


class LineCompare(BaseModel):
    model_config = _P
    kind: Literal["line_compare"] = "line_compare"
    title: Optional[str] = None
    x_labels: list[str] = Field(default_factory=list)
    series: list[LineSeries] = Field(default_factory=list)


class DonutSegment(BaseModel):
    model_config = _P
    label: Optional[str] = None
    value: Optional[float] = None
    text: Optional[str] = None


class Donut(BaseModel):
    model_config = _P
    kind: Literal["donut"] = "donut"
    title: Optional[str] = None
    segments: list[DonutSegment] = Field(default_factory=list)


class MoneyItem(BaseModel):
    model_config = _P
    label: Optional[str] = None
    value: Optional[float] = None
    text: Optional[str] = None


class MoneyInfographic(BaseModel):
    model_config = _P
    kind: Literal["money_infographic"] = "money_infographic"
    title: Optional[str] = None
    currency: Optional[str] = "€"
    items: list[MoneyItem] = Field(default_factory=list)


class CostMathStrip(BaseModel):
    model_config = _P
    kind: Literal["cost_math_strip"] = "cost_math_strip"
    title: Optional[str] = None
    operands: list[float] = Field(default_factory=list)
    operand_texts: list[str] = Field(default_factory=list)
    operators: list[str] = Field(default_factory=list)
    result: Optional[float] = None
    result_text: Optional[str] = None
    unit: Optional[str] = None


class ComparisonColumns(BaseModel):
    model_config = _P
    kind: Literal["comparison_columns"] = "comparison_columns"
    title: Optional[str] = None
    ohne: list[str] = Field(default_factory=list)
    mit: list[str] = Field(default_factory=list)


ChartSpec = Annotated[
    Union[
        BeforeAfterBars, LineCompare, Donut,
        MoneyInfographic, CostMathStrip, ComparisonColumns,
    ],
    Field(discriminator="kind"),
]
_CHART_ADAPTER = TypeAdapter(ChartSpec)


def parse_chart(data) -> tuple[Optional[BaseModel], Optional[str]]:
    """Validate a dict (carrying a `kind`) into its ChartSpec variant.
    Returns (chart, None) on success, (None, warning) otherwise. Never raises.
    """
    if not isinstance(data, dict):
        return None, "chart: not a dict"
    if "kind" not in data:
        return None, "chart: missing 'kind'"
    try:
        return _CHART_ADAPTER.validate_python(data), None
    except ValidationError as exc:
        return None, f"chart[{data.get('kind')!r}]: invalid ({exc.error_count()} error(s))"
