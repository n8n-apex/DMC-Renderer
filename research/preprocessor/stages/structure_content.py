"""structure_content — turn raw report pages into a typed, structured view:
per-page typed PageData (by st_type), rhetorical ChartSpec data (explicit
chart/charts keys + a deterministic before/after transform from a 2-item
numeric stat list), and a validated SocialProofBlock (never invented).
Pure (no I/O); degrades to warnings, never blocks. Heavy carriers are
dataclasses (ADR split). Not wired into the package until a later phase.
Brand-agnostic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from pydantic import BaseModel

from models_charts import (
    BeforeAfterBars,
    ComparisonColumns,
    CostMathStrip,
    Donut,
    DonutSegment,
    LineCompare,
    LineSeries,
    MoneyInfographic,
    MoneyItem,
    parse_chart,
)
from models_pagedata import parse_page_data
from models_social import SocialProofBlock, parse_social_proof
from stages.numbers import parse_german_number

_STAT_FIELDS = ("ergebnis_metrics", "metrics", "bars", "stats")

# A 2-item numeric stat list is only a genuine before/after comparison when its
# labels signal one — item0 reads as a "before" state and item1 as an "after"
# state. Without this signal, two unrelated numbers (e.g. "50 Kunden / 10 Jahre")
# would be fabricated into a misleading "50 -> 10" chart, violating the
# zero-hallucination deterministic-transform contract (PRD §8.3 lane ①) and the
# rule that a before/after must be an actual comparison (DNA §C5).
_BEFORE_TOKENS = ("vorher", "ohne", "alt", "before", "status quo", "bisher", "heute")
_AFTER_TOKENS = ("nachher", "mit", "neu", "after", "ziel", "danach", "künftig")


def _label_has_token(label, tokens) -> bool:
    if not isinstance(label, str):
        return False
    low = label.lower()
    return any(tok in low for tok in tokens)


@dataclass
class StructuredPage:
    slot: Optional[int]
    st_type: str
    data: BaseModel
    charts: list = field(default_factory=list)
    social_proof: Optional[SocialProofBlock] = None
    warnings: list = field(default_factory=list)


@dataclass
class StructuredContent:
    pages: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


def _get(page, key, default=None):
    if isinstance(page, dict):
        return page.get(key, default)
    return getattr(page, key, default)


def _stat_value_label(item):
    if isinstance(item, str):
        return parse_german_number(item), item
    return parse_german_number(getattr(item, "value", None)), getattr(item, "label", None)


def _before_after_from_stats(data_model) -> Optional[BeforeAfterBars]:
    """A 2-item stat list -> a before/after ONLY when both values parse to
    numbers AND the labels signal a genuine before/after (item0 a "before"
    token, item1 an "after" token). No signal -> None (no fabricated chart)."""
    for fname in _STAT_FIELDS:
        items = getattr(data_model, fname, None)
        if isinstance(items, list) and len(items) == 2:
            v0, l0 = _stat_value_label(items[0])
            v1, l1 = _stat_value_label(items[1])
            if v0 is None or v1 is None:
                continue
            if _label_has_token(l0, _BEFORE_TOKENS) and _label_has_token(l1, _AFTER_TOKENS):
                return BeforeAfterBars(
                    before_label=l0, before_value=v0,
                    after_label=l1, after_value=v1,
                )
    return None


# --------------------------------------------------------------------------
# Conservative prose→chart extractors (Task 4). Each is gated on an EXPLICIT
# field-name signal in the raw page dict — never on a bare number or an
# ambiguous shape. Ambiguous / absent → None (no chart). Numbers are PARSED
# via parse_german_number; no value is ever computed or estimated. This
# enforces the cardinal NO-FABRICATION rule (design spec §3).
# --------------------------------------------------------------------------

# Explicit field-name signals (German + English) per chart kind.
_OHNE_KEYS = ("ohne", "without")
_MIT_KEYS = ("mit", "with")
_DONUT_KEYS = ("breakdown", "segments", "anteile")
_MONEY_KEYS = ("kosten", "investment", "money")
_MATH_KEYS = ("rechnung", "math", "calc")
_SERIES_KEYS = ("series", "verlauf")
# Symbols that mark a value as an explicit currency amount.
_CURRENCY_SIGNALS = ("€", "$", "£")


def _first_present(raw: dict, keys) -> Optional[object]:
    for k in keys:
        if k in raw:
            return raw[k]
    return None


def _str_list(value) -> Optional[list]:
    """A list of non-empty strings, or None if `value` isn't one."""
    if not isinstance(value, list) or not value:
        return None
    out = [str(v) for v in value if isinstance(v, str) and v.strip()]
    return out if out else None


def _label_value_items(value):
    """Yield (label, raw_value) pairs from a list of {label,value} dicts.
    Returns None when `value` isn't a non-empty list of such dicts."""
    if not isinstance(value, list) or not value:
        return None
    pairs = []
    for it in value:
        if not isinstance(it, dict) or "value" not in it:
            return None
        pairs.append((it.get("label"), it.get("value")))
    return pairs


def _comparison_columns_from(raw: dict) -> Optional[ComparisonColumns]:
    """Explicit ohne/mit (without/with) STRING lists → a qualitative
    two-column comparison. Either side may be nested under a `compare` dict.
    No such keys → None."""
    source = raw
    if isinstance(raw.get("compare"), dict):
        source = raw["compare"]
    ohne = _str_list(_first_present(source, _OHNE_KEYS))
    mit = _str_list(_first_present(source, _MIT_KEYS))
    if ohne is None and mit is None:
        return None
    return ComparisonColumns(
        ohne=ohne or [], mit=mit or [], title=raw.get("title"),
    )


def _donut_from(raw: dict) -> Optional[Donut]:
    """An EXPLICIT parts-of-whole field (breakdown/segments/anteile) that is
    a list of {label,value}. A plain number list is NOT a breakdown → None."""
    pairs = _label_value_items(_first_present(raw, _DONUT_KEYS))
    if pairs is None:
        return None
    segs = []
    for label, val in pairs:
        v = parse_german_number(val)
        if v is None:
            return None  # an unparseable share → ambiguous → no chart
        segs.append(DonutSegment(label=str(label) if label is not None else None, value=v))
    if not segs:
        return None
    return Donut(segments=segs, title=raw.get("title"))


def _money_infographic_from(raw: dict) -> Optional[MoneyInfographic]:
    """Items under an explicit currency field (kosten/investment/money), each
    {label,value}, where the values carry a currency signal (€/$/£). No
    currency signal → None (a bare number is not money)."""
    raw_items = _first_present(raw, _MONEY_KEYS)
    pairs = _label_value_items(raw_items)
    if pairs is None:
        return None
    currency = None
    items = []
    for label, val in pairs:
        text = str(val)
        sig = next((c for c in _CURRENCY_SIGNALS if c in text), None)
        if sig is None:
            return None  # no explicit currency signal → not money → no chart
        currency = currency or sig
        v = parse_german_number(val)
        if v is None:
            return None
        items.append(MoneyItem(label=str(label) if label is not None else None, value=v))
    if not items:
        return None
    return MoneyInfographic(currency=currency, items=items, title=raw.get("title"))


def _cost_math_strip_from(raw: dict) -> Optional[CostMathStrip]:
    """An EXPLICIT operands+operators(+result) struct (rechnung/math/calc).
    The result is rendered VERBATIM — never computed. No operands → None."""
    struct = _first_present(raw, _MATH_KEYS)
    if not isinstance(struct, dict):
        return None
    raw_operands = struct.get("operands")
    if not isinstance(raw_operands, list) or not raw_operands:
        return None
    operands = [parse_german_number(o) for o in raw_operands]
    if any(o is None for o in operands):
        return None
    operators = [str(op) for op in struct.get("operators", []) if op is not None]
    result = parse_german_number(struct.get("result"))  # VERBATIM; None ok
    return CostMathStrip(
        operands=operands, operators=operators, result=result,
        unit=struct.get("unit"), title=raw.get("title"),
    )


def _line_compare_from(raw: dict) -> Optional[LineCompare]:
    """An EXPLICIT multi-point series struct (series/verlauf) carrying
    x_labels + a list of named point lists. Absent / wrong shape → None."""
    struct = _first_present(raw, _SERIES_KEYS)
    if not isinstance(struct, dict):
        return None
    raw_series = struct.get("series")
    x_labels = _str_list(struct.get("x_labels")) or []
    if not isinstance(raw_series, list) or not raw_series:
        return None
    series = []
    for s in raw_series:
        if not isinstance(s, dict):
            return None
        raw_points = s.get("points")
        if not isinstance(raw_points, list) or not raw_points:
            return None
        points = [parse_german_number(p) for p in raw_points]
        if any(p is None for p in points):
            return None
        series.append(LineSeries(name=s.get("name"), points=points))
    if not series:
        return None
    return LineCompare(x_labels=x_labels, series=series, title=raw.get("title"))


# Order matters only for determinism; the signals are mutually exclusive in
# practice (distinct field names), so at most one fires per page.
_EXTRACTORS = (
    _comparison_columns_from,
    _donut_from,
    _money_infographic_from,
    _cost_math_strip_from,
    _line_compare_from,
)


def _auto_charts_from_raw(raw: dict) -> list:
    """Run every explicit-signal extractor over the raw page dict; collect
    each chart it yields (each gated on its own explicit field signal)."""
    charts: list = []
    for extractor in _EXTRACTORS:
        spec = extractor(raw)
        if spec is not None:
            charts.append(spec)
    return charts


def structure_content(pages) -> StructuredContent:
    out_pages: list = []
    all_warnings: list = []
    for page in pages:
        slot = _get(page, "slot")
        st_type = _get(page, "type") or _get(page, "st_type") or ""
        raw = _get(page, "data") or {}

        data_model, warn = parse_page_data(st_type, raw)
        warnings: list = []
        if warn:
            warnings.append(warn)

        charts: list = []
        if isinstance(raw, dict):
            explicit = []
            if isinstance(raw.get("chart"), dict):
                explicit.append(raw["chart"])
            if isinstance(raw.get("charts"), list):
                explicit.extend(c for c in raw["charts"] if isinstance(c, dict))
            for cd in explicit:
                chart, cw = parse_chart(cd)
                if chart is not None:
                    charts.append(chart)
                elif cw:
                    warnings.append(cw)
        # Conservative prose→chart extraction, only when the page carries no
        # explicit chart already. Each extractor is gated on an explicit
        # field-name signal (NO fabrication — spec §3).
        if not charts and isinstance(raw, dict):
            charts.extend(_auto_charts_from_raw(raw))
        if not charts:
            auto = _before_after_from_stats(data_model)
            if auto is not None:
                charts.append(auto)

        social_proof = None
        if isinstance(raw, dict) and "social_proof" in raw:
            social_proof, spw = parse_social_proof(raw.get("social_proof"))
            if spw:
                warnings.append(spw)

        out_pages.append(StructuredPage(
            slot=slot, st_type=st_type, data=data_model,
            charts=charts, social_proof=social_proof, warnings=warnings,
        ))
        all_warnings.extend(warnings)

    return StructuredContent(pages=out_pages, warnings=all_warnings)
