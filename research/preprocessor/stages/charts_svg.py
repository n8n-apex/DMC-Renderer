"""Pure, deterministic, brand-agnostic SVG renderers for the six chart-spec
types (models_charts.py) + a dispatcher.

Design (see docs/superpowers/specs/2026-06-04-data-dense-charts-design.md §4.1):
- `render_chart_svg(spec, theme) -> str` dispatches on `spec.kind`.
- Each renderer returns a self-contained, well-formed
  `<svg viewBox="0 0 W H" xmlns="...">...</svg>` string on a fixed coordinate
  system; the renderer scales it via CSS (width/height 100%).
- ONLY the passed `ChartTheme` colors are used — no hardcoded brand/client hexes.
- Robustness: None / empty / all-zero / div-by-zero inputs never crash; they
  return a graceful minimal themed frame (with the title if present).
- VERBATIM: CostMathStrip renders the given operands/result; it never does
  arithmetic.

This module is pure: no network, no file I/O, no client/brand literals.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional
from xml.sax.saxutils import escape

# Sentinel embedded (as an inert XML comment) in every chart SVG this module
# emits, so the renderer can select chart components by marker rather than by
# their tail position in page["components"] (infection #14). Inert: it renders
# nothing and does not affect chart geometry. Keep in sync with
# v7-renderer/patterns/base.py CHART_SVG_MARKER.
CHART_SVG_MARKER = "dmc:chart"


@dataclass
class ChartTheme:
    """Brand color tokens (caller passes them — no defaults for colors).

    Hex color strings + an optional CSS font-family. `font_family="inherit"`
    lets the chart pick up the page font.
    """

    ink: str
    paper: str
    primary: str
    accent: str
    muted: str
    font_family: str = "inherit"


# --------------------------------------------------------------------------
# Small helpers (all pure)
# --------------------------------------------------------------------------
def _esc(value) -> str:
    """XML-escape a value as text, mapping None to empty string."""
    if value is None:
        return ""
    return escape(str(value))


def _printed(text: Optional[str], value: Optional[float]) -> str:
    """The glyphs to draw: the claim's own string, else the formatted float.

    Geometry always comes from the float; only the printed characters come
    from here. This is what keeps a drawn figure identical to the approved
    copy, including German thousands dots and decimal commas.
    """
    if text:
        return text
    return _num(value)


def _num(value: Optional[float]) -> str:
    """Render a number without a trailing `.0` (so 20.0 -> "20", 4.5 -> "4.5")."""
    if value is None:
        return ""
    f = float(value)
    if f == int(f):
        return str(int(f))
    # Trim trailing zeros from the decimal rendering, keep it deterministic.
    return ("%g" % f)


def _frame(width: int, height: int, theme: ChartTheme, title: Optional[str], *, body: str = "") -> str:
    """A minimal themed `<svg>` frame: paper background + optional title.

    Used both as the graceful empty fallback and as the shell that every
    renderer wraps its body in.
    """
    title_el = ""
    if title:
        title_el = (
            f'<text x="{width / 2:.1f}" y="28" text-anchor="middle" '
            f'font-family="{_esc(theme.font_family)}" font-size="20" '
            f'font-weight="700" fill="{_esc(theme.ink)}">{_esc(title)}</text>'
        )
    return (
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="100%" '
        f'xmlns="http://www.w3.org/2000/svg" '
        f'preserveAspectRatio="xMidYMid meet" role="img">'
        f"<!-- {CHART_SVG_MARKER} -->"
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="{_esc(theme.paper)}"/>'
        f"{title_el}{body}"
        f"</svg>"
    )


def _empty(width: int, height: int, theme: ChartTheme, title: Optional[str]) -> str:
    """Graceful minimal frame when there is nothing to plot."""
    return _frame(width, height, theme, title)


# --------------------------------------------------------------------------
# 1. BeforeAfterBars
# --------------------------------------------------------------------------
def _before_after_bars(spec, theme: ChartTheme) -> str:
    W, H = 480, 320
    before_v = spec.before_value
    after_v = spec.after_value
    # Graceful frame when there's nothing real to draw.
    values = [v for v in (before_v, after_v) if v is not None]
    if not values:
        return _empty(W, H, theme, spec.title)
    vmax = max(abs(float(v)) for v in values)

    baseline_y = 280
    top = 70  # below the title
    max_bar_h = baseline_y - top
    bar_w = 90
    gap = 110
    # Two slots centered.
    x_before = W / 2 - gap / 2 - bar_w / 2
    x_after = W / 2 + gap / 2 - bar_w / 2

    parts: list[str] = []
    # Baseline axis.
    parts.append(
        f'<line x1="60" y1="{baseline_y}" x2="{W - 60}" y2="{baseline_y}" '
        f'stroke="{_esc(theme.muted)}" stroke-width="1.5"/>'
    )

    def _bar(x: float, value: Optional[float], label: Optional[str], fill: str,
             text: Optional[str] = None) -> None:
        if value is None:
            return
        h = 0.0 if vmax == 0 else max_bar_h * (abs(float(value)) / vmax)
        y = baseline_y - h
        parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w}" height="{h:.1f}" '
            f'fill="{_esc(fill)}" rx="3"/>'
        )
        # Value (+ unit) above the bar.
        val_txt = _printed(text, value)
        if spec.unit and not text:
            val_txt = f"{val_txt} {spec.unit}"
        parts.append(
            f'<text x="{x + bar_w / 2:.1f}" y="{y - 10:.1f}" text-anchor="middle" '
            f'font-family="{_esc(theme.font_family)}" font-size="18" font-weight="700" '
            f'fill="{_esc(theme.ink)}">{_esc(val_txt)}</text>'
        )
        # Category label below the baseline.
        parts.append(
            f'<text x="{x + bar_w / 2:.1f}" y="{baseline_y + 24:.1f}" text-anchor="middle" '
            f'font-family="{_esc(theme.font_family)}" font-size="15" '
            f'fill="{_esc(theme.muted)}">{_esc(label)}</text>'
        )

    _bar(x_before, before_v, spec.before_label, theme.primary, spec.before_text)
    _bar(x_after, after_v, spec.after_label, theme.accent, spec.after_text)

    return _frame(W, H, theme, spec.title, body="".join(parts))


# --------------------------------------------------------------------------
# 2. ComparisonColumns (qualitative two-column TEXT)
# --------------------------------------------------------------------------
def _comparison_columns(spec, theme: ChartTheme) -> str:
    W, H = 480, 360
    ohne = list(spec.ohne or [])
    mit = list(spec.mit or [])
    if not ohne and not mit:
        return _empty(W, H, theme, spec.title)

    top = 64
    col_w = 200
    gap = 40
    x_left = (W - (2 * col_w + gap)) / 2
    x_right = x_left + col_w + gap
    panel_h = H - top - 24
    row_h = 34

    parts: list[str] = []

    def _column(x: float, items: list[str], header: str, header_fill: str, bullet_fill: str) -> None:
        # Panel background.
        parts.append(
            f'<rect x="{x:.1f}" y="{top}" width="{col_w}" height="{panel_h}" '
            f'rx="8" fill="{_esc(theme.paper)}" stroke="{_esc(theme.muted)}" '
            f'stroke-width="1"/>'
        )
        # Header band.
        parts.append(
            f'<rect x="{x:.1f}" y="{top}" width="{col_w}" height="36" rx="8" '
            f'fill="{_esc(header_fill)}"/>'
        )
        parts.append(
            f'<text x="{x + col_w / 2:.1f}" y="{top + 24:.1f}" text-anchor="middle" '
            f'font-family="{_esc(theme.font_family)}" font-size="15" font-weight="700" '
            f'fill="{_esc(theme.paper)}">{_esc(header)}</text>'
        )
        # Bullet rows.
        for i, item in enumerate(items):
            cy = top + 36 + 16 + i * row_h
            parts.append(
                f'<circle cx="{x + 18:.1f}" cy="{cy + 12:.1f}" r="4" '
                f'fill="{_esc(bullet_fill)}"/>'
            )
            parts.append(
                f'<text x="{x + 34:.1f}" y="{cy + 16:.1f}" '
                f'font-family="{_esc(theme.font_family)}" font-size="14" '
                f'fill="{_esc(theme.ink)}">{_esc(item)}</text>'
            )

    # "ohne" (without) = the negative/muted column; "mit" (with) = accent.
    _column(x_left, ohne, "Ohne", theme.muted, theme.muted)
    _column(x_right, mit, "Mit", theme.accent, theme.accent)

    return _frame(W, H, theme, spec.title, body="".join(parts))


# --------------------------------------------------------------------------
# 3. Donut
# --------------------------------------------------------------------------
def _arc_path(cx: float, cy: float, r_outer: float, r_inner: float,
              a0: float, a1: float) -> str:
    """SVG path `d` for a donut wedge between angles a0..a1 (radians, clockwise
    from 12 o'clock). Pure trig, deterministic."""
    def pt(r: float, a: float) -> tuple[float, float]:
        return (cx + r * math.sin(a), cy - r * math.cos(a))

    large = 1 if (a1 - a0) > math.pi else 0
    ox0, oy0 = pt(r_outer, a0)
    ox1, oy1 = pt(r_outer, a1)
    ix1, iy1 = pt(r_inner, a1)
    ix0, iy0 = pt(r_inner, a0)
    return (
        f"M {ox0:.2f} {oy0:.2f} "
        f"A {r_outer:.2f} {r_outer:.2f} 0 {large} 1 {ox1:.2f} {oy1:.2f} "
        f"L {ix1:.2f} {iy1:.2f} "
        f"A {r_inner:.2f} {r_inner:.2f} 0 {large} 0 {ix0:.2f} {iy0:.2f} "
        f"Z"
    )


def _donut(spec, theme: ChartTheme) -> str:
    W, H = 480, 360
    segs = [s for s in (spec.segments or []) if s.value is not None]
    total = sum(abs(float(s.value)) for s in segs)
    if not segs or total <= 0:
        return _empty(W, H, theme, spec.title)

    cx, cy = 160, 200
    r_outer, r_inner = 110, 64
    # Deterministic color cycle from the theme (no extra brand hexes).
    palette = [theme.primary, theme.accent, theme.ink, theme.muted]

    parts: list[str] = []
    legend_x = 300
    legend_y = 120

    if len(segs) == 1:
        # Single 100% segment = a full ring (two concentric circles).
        seg = segs[0]
        parts.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r_outer}" fill="{_esc(palette[0])}"/>'
        )
        parts.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r_inner}" fill="{_esc(theme.paper)}"/>'
        )
        parts.append(
            f'<circle cx="{legend_x + 8}" cy="{legend_y + 8}" r="7" '
            f'fill="{_esc(palette[0])}"/>'
        )
        parts.append(
            f'<text x="{legend_x + 24}" y="{legend_y + 13}" '
            f'font-family="{_esc(theme.font_family)}" font-size="14" '
            f'fill="{_esc(theme.ink)}">{_esc(seg.label)} '
            f'({_printed(seg.text, seg.value)})</text>'
        )
        return _frame(W, H, theme, spec.title, body="".join(parts))

    angle = 0.0
    for i, seg in enumerate(segs):
        frac = abs(float(seg.value)) / total
        a0 = angle
        a1 = angle + frac * 2 * math.pi
        angle = a1
        fill = palette[i % len(palette)]
        parts.append(f'<path d="{_arc_path(cx, cy, r_outer, r_inner, a0, a1)}" fill="{_esc(fill)}"/>')
        # Legend row.
        ly = legend_y + i * 28
        parts.append(
            f'<circle cx="{legend_x + 8}" cy="{ly + 8}" r="7" fill="{_esc(fill)}"/>'
        )
        parts.append(
            f'<text x="{legend_x + 24}" y="{ly + 13}" '
            f'font-family="{_esc(theme.font_family)}" font-size="14" '
            f'fill="{_esc(theme.ink)}">{_esc(seg.label)} ({_printed(seg.text, seg.value)})</text>'
        )

    return _frame(W, H, theme, spec.title, body="".join(parts))


# --------------------------------------------------------------------------
# 4. LineCompare
# --------------------------------------------------------------------------
def _line_compare(spec, theme: ChartTheme) -> str:
    W, H = 520, 360
    x_labels = list(spec.x_labels or [])
    series = [s for s in (spec.series or []) if s.points]
    if not series:
        return _empty(W, H, theme, spec.title)

    plot_l, plot_r = 56, W - 24
    plot_t, plot_b = 70, 280
    plot_w = plot_r - plot_l
    plot_h = plot_b - plot_t

    all_points = [p for s in series for p in s.points if p is not None]
    if not all_points:
        return _empty(W, H, theme, spec.title)
    vmin = min(float(p) for p in all_points)
    vmax = max(float(p) for p in all_points)
    vrange = vmax - vmin

    palette = [theme.primary, theme.accent, theme.ink, theme.muted]
    parts: list[str] = []

    # Axis baseline + left rule.
    parts.append(
        f'<line x1="{plot_l}" y1="{plot_b}" x2="{plot_r}" y2="{plot_b}" '
        f'stroke="{_esc(theme.muted)}" stroke-width="1.5"/>'
    )

    def _x(i: int, n: int) -> float:
        if n <= 1:
            return plot_l + plot_w / 2
        return plot_l + plot_w * (i / (n - 1))

    def _y(v: float) -> float:
        if vrange == 0:
            return plot_t + plot_h / 2  # flat series → centered line
        return plot_b - plot_h * ((float(v) - vmin) / vrange)

    for si, s in enumerate(series):
        color = palette[si % len(palette)]
        n = len(s.points)
        pts = " ".join(
            f"{_x(i, n):.2f},{_y(p):.2f}"
            for i, p in enumerate(s.points)
            if p is not None
        )
        parts.append(
            f'<polyline points="{pts}" fill="none" stroke="{_esc(color)}" '
            f'stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>'
        )
        # Point markers.
        for i, p in enumerate(s.points):
            if p is None:
                continue
            parts.append(
                f'<circle cx="{_x(i, n):.2f}" cy="{_y(p):.2f}" r="3.5" '
                f'fill="{_esc(color)}"/>'
            )

    # X labels.
    n_labels = len(x_labels)
    for i, lbl in enumerate(x_labels):
        x = _x(i, n_labels)
        parts.append(
            f'<text x="{x:.1f}" y="{plot_b + 22:.1f}" text-anchor="middle" '
            f'font-family="{_esc(theme.font_family)}" font-size="13" '
            f'fill="{_esc(theme.muted)}">{_esc(lbl)}</text>'
        )

    # Legend (series names) along the bottom.
    legend_y = H - 18
    lx = plot_l
    for si, s in enumerate(series):
        color = palette[si % len(palette)]
        parts.append(
            f'<rect x="{lx:.1f}" y="{legend_y - 10:.1f}" width="14" height="6" '
            f'rx="2" fill="{_esc(color)}"/>'
        )
        name = s.name or ""
        parts.append(
            f'<text x="{lx + 20:.1f}" y="{legend_y:.1f}" '
            f'font-family="{_esc(theme.font_family)}" font-size="13" '
            f'fill="{_esc(theme.ink)}">{_esc(name)}</text>'
        )
        lx += 24 + 8 * max(1, len(name))

    return _frame(W, H, theme, spec.title, body="".join(parts))


# --------------------------------------------------------------------------
# 5. MoneyInfographic
# --------------------------------------------------------------------------
def _money_infographic(spec, theme: ChartTheme) -> str:
    W, H = 520, 360
    items = [it for it in (spec.items or []) if it.value is not None]
    if not items:
        return _empty(W, H, theme, spec.title)
    vmax = max(abs(float(it.value)) for it in items)
    currency = spec.currency or ""

    top = 70
    row_h = min(56, (H - top - 24) / max(1, len(items)))
    label_x = 24
    bar_x = 150
    bar_max_w = W - bar_x - 100
    bar_h = min(28, row_h * 0.5)

    parts: list[str] = []
    palette = [theme.primary, theme.accent]
    for i, it in enumerate(items):
        cy = top + i * row_h
        # Label.
        parts.append(
            f'<text x="{label_x}" y="{cy + row_h / 2 + 5:.1f}" '
            f'font-family="{_esc(theme.font_family)}" font-size="15" font-weight="600" '
            f'fill="{_esc(theme.ink)}">{_esc(it.label)}</text>'
        )
        # Bar (proportional).
        w = 0.0 if vmax == 0 else bar_max_w * (abs(float(it.value)) / vmax)
        by = cy + (row_h - bar_h) / 2
        fill = palette[i % len(palette)]
        parts.append(
            f'<rect x="{bar_x}" y="{by:.1f}" width="{w:.1f}" height="{bar_h:.1f}" '
            f'rx="4" fill="{_esc(fill)}"/>'
        )
        # Currency-prefixed value at the bar end.
        val_txt = it.text or f"{currency}{_num(it.value)}"
        parts.append(
            f'<text x="{bar_x + w + 8:.1f}" y="{by + bar_h / 2 + 5:.1f}" '
            f'font-family="{_esc(theme.font_family)}" font-size="15" font-weight="700" '
            f'fill="{_esc(theme.ink)}">{_esc(val_txt)}</text>'
        )

    return _frame(W, H, theme, spec.title, body="".join(parts))


# --------------------------------------------------------------------------
# 6. CostMathStrip (render VERBATIM — never compute arithmetic)
# --------------------------------------------------------------------------
def _cost_math_strip(spec, theme: ChartTheme) -> str:
    W, H = 560, 200
    operands = list(spec.operands or [])
    operators = list(spec.operators or [])
    has_result = spec.result is not None
    if not operands and not has_result:
        return _empty(W, H, theme, spec.title)

    # Interleave: operand, operator, operand, operator, ... then "=" result.
    # We render exactly what is given; NO value is computed.
    # Each token: (text, kind) where kind is "tile", "op", or "result".
    tokens: list[tuple[str, str]] = []
    for i, op in enumerate(operands):
        tokens.append((_printed(
            spec.operand_texts[i] if i < len(spec.operand_texts) else None,
            op,
        ), "tile"))
        if i < len(operators):
            tokens.append((_esc(operators[i]), "op"))
    if has_result:
        tokens.append(("=", "op"))
        result_txt = _printed(spec.result_text, spec.result)
        if spec.unit:
            result_txt = f"{result_txt} {spec.unit}"
        tokens.append((result_txt, "result"))

    if not tokens:
        return _empty(W, H, theme, spec.title)

    tile_h = 66
    op_w = 34
    gap = 10
    cy = 110
    font_size = 22
    _char_w = 13.0  # approx px per char at font_size 22 (700 weight)
    _pad = 26       # horizontal padding inside a tile

    def _tile_width(text: str) -> float:
        # width-adaptive so a long result like "1040 h/Jahr" never overflows
        return max(72.0, len(text) * _char_w + _pad)

    # Per-token widths (tiles adapt to their text; operators are fixed).
    widths = [op_w if kind == "op" else _tile_width(text) for text, kind in tokens]
    total_w = sum(widths) + gap * (len(tokens) - 1)

    # Grow the canvas so the whole equation fits with margins (the SVG scales
    # via CSS, so a wider viewBox just makes the strip wider — never clipped).
    margin = 28
    W = max(560.0, total_w + 2 * margin)
    x = (W - total_w) / 2

    parts: list[str] = []
    tile_index = 0
    for (text, kind), w in zip(tokens, widths):
        if kind == "op":
            parts.append(
                f'<text x="{x + w / 2:.1f}" y="{cy + 9:.1f}" text-anchor="middle" '
                f'font-family="{_esc(theme.font_family)}" font-size="26" font-weight="700" '
                f'fill="{_esc(theme.ink)}">{_esc(text)}</text>'
            )
            x += w + gap
            continue
        # tile or result: a filled rounded tile with the value on top.
        if kind == "result":
            fill = theme.accent
        elif tile_index == 0:
            fill = theme.primary
        else:
            fill = theme.ink
        parts.append(
            f'<rect x="{x:.1f}" y="{cy - tile_h / 2:.1f}" width="{w:.1f}" '
            f'height="{tile_h}" rx="10" fill="{_esc(fill)}"/>'
        )
        parts.append(
            f'<text x="{x + w / 2:.1f}" y="{cy + 8:.1f}" text-anchor="middle" '
            f'font-family="{_esc(theme.font_family)}" font-size="{font_size}" font-weight="700" '
            f'fill="{_esc(theme.paper)}">{_esc(text)}</text>'
        )
        x += w + gap
        tile_index += 1

    return _frame(W, H, theme, spec.title, body="".join(parts))


# --------------------------------------------------------------------------
# Dispatcher
# --------------------------------------------------------------------------
_DEFAULT_SIZE = (480, 320)


def render_chart_svg(spec, theme: ChartTheme) -> str:
    """Dispatch on `spec.kind` to the matching per-type renderer.

    Returns a self-contained `<svg>` string. Unknown / None specs return a
    graceful empty themed frame rather than raising.
    """
    if spec is None:
        return _empty(*_DEFAULT_SIZE, theme, None)
    kind = getattr(spec, "kind", None)
    renderer = _RENDERERS.get(kind)
    if renderer is None:
        return _empty(*_DEFAULT_SIZE, theme, getattr(spec, "title", None))
    return renderer(spec, theme)


# Filled in across Tasks 1-3.
_RENDERERS = {
    "before_after_bars": _before_after_bars,
    "comparison_columns": _comparison_columns,
    "donut": _donut,
    "line_compare": _line_compare,
    "money_infographic": _money_infographic,
    "cost_math_strip": _cost_math_strip,
}
