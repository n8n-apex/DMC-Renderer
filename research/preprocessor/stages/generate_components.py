"""Stage 6 — SVG component generation.

Walks the report pages and produces brand-coloured SVG components per
page slot. Returns `{slot: [svg_string, ...]}` keyed by page slot.

Provenance: the eight existing component functions (process_flow,
matrix_2x2, causality_chain, metaphor_split, bar_chart, line_chart,
stat_block, compare_table) were ported from
`research/decoration-samples/_build/build_v6.py`. The original used
module-level `PRIMARY` / `ACCENT` constants from `v5_palette.py`, so
every diagram came out in a single hardcoded palette regardless of
client. We chose **Option A** (per the Phase C spec): copy the
function bodies and parameterise the colours. We did NOT modify
`build_v6.py` itself; that file remains as the historical reference
build.

Why Option A vs Option B (monkey-patching the colour module at import
time):
  - build_v6.py imports `weasyprint` and runs PDF/PNG generation as a
    side-effect on import. We can't import it as a library without
    triggering those side effects, and we can't add an `if __name__ ==
    "__main__"` guard without modifying the file (which scope forbids).
  - Monkey-patching module globals is fragile, not thread-safe, and
    would break test isolation.
  - Copying keeps the pre-processor self-contained — no cross-tree
    imports into research/decoration-samples/.

The original used Pillow + on-disk font files for pixel-perfect text
measurement. The pre-processor has neither Pillow nor those fonts (and
we are not adding a brittle cross-tree dep), so this module ships a
self-contained character-width estimator (`_text_width_estimate`) that
gets us close enough for autofit/wrap decisions. The SVG output
structure is identical; the layout-fit checks land in approximately the
same place. Pixel-perfect alignment is the renderer's job, not Stage
6's.

Additional new components added per Phase C:
  - curved_arrow_flow  — numbered process steps with curved connectors
  - paired_comparison  — before/after two-column panel with markers
  - venn_diagram       — 2-3 overlapping circles with labels

All components output SELF-CONTAINED SVG strings that:
  - declare xmlns="http://www.w3.org/2000/svg"
  - carry explicit width=… height=… attributes (plus viewBox)
  - use ONLY the colours passed in as parameters (no hardcoded brand
    hex anywhere in the SVG output)
  - work when embedded inline into an HTML document (WeasyPrint
    composites them by serialising the surrounding HTML to a single PDF)
"""

from __future__ import annotations

from typing import Any, Optional

from stages.charts_svg import ChartTheme, render_chart_svg

# ─────────────────────────────────────────────────────────────────────────────
# Default style constants — NOT brand-specific, kept fixed across clients.
# ─────────────────────────────────────────────────────────────────────────────

# Neutral greys used for rule lines, captions, dividers. These are
# brand-neutral and stay constant across all clients (Richard's design
# language defines them this way).
DEFAULT_DARK_GRAY = "#3d3d4a"
DEFAULT_DEEP = "#dcdcdf"
DEFAULT_CREAM = "#F8F5F0"
DEFAULT_COMPARE_RED = "#c0392b"
DEFAULT_COMPARE_GREEN = "#27ae60"


# ─────────────────────────────────────────────────────────────────────────────
# Self-contained text-width estimator (replaces text_fit.py's PIL dep)
# ─────────────────────────────────────────────────────────────────────────────


# Rough character-width factors per font flavour. These are SVG-unit
# multipliers applied to `font-size`. Calibrated by eye against the
# build_v6 PIL-measured baselines; close enough that the same lines
# fit/wrap at the same sizes in the vast majority of cases.
_CHAR_WIDTH_BY_FONT: dict[str, float] = {
    "Inter-400": 0.50,
    "Inter-700": 0.52,
    "Inter-800": 0.55,
    "Inter-900": 0.58,
    "Serif-400": 0.48,
    "Serif-400i": 0.48,
}


def _text_width_estimate(text: str, font_key: str, size_pt: float) -> float:
    """Approximate text width in viewBox units.

    Caps at upper-case caveat: ALL-CAPS strings render ~10% wider in
    practice; we apply that bump because several callers pass uppercase
    section labels.
    """
    if not text:
        return 0.0
    factor = _CHAR_WIDTH_BY_FONT.get(font_key, 0.52)
    base = len(text) * size_pt * factor
    if text == text.upper() and any(c.isalpha() for c in text):
        base *= 1.10
    return base


def _autofit_size(
    text: str,
    max_width: float,
    font_key: str,
    *,
    min_size: int,
    max_size: int,
) -> int:
    """Largest integer point size ≤ max_size such that the text fits
    in `max_width`. Falls back to `min_size`."""
    for size in range(int(max_size), int(min_size) - 1, -1):
        if _text_width_estimate(text, font_key, size) <= max_width:
            return size
    return int(min_size)


def _truncate_to_width(
    text: str, max_width: float, font_key: str, size_pt: float
) -> str:
    """If `text` is wider than max_width at size_pt, trim with an
    ellipsis. Otherwise return as-is."""
    if _text_width_estimate(text, font_key, size_pt) <= max_width:
        return text
    # Trim until it fits (with the ellipsis suffix accounted for)
    ell = "…"
    ell_w = _text_width_estimate(ell, font_key, size_pt)
    s = text
    while s and _text_width_estimate(s, font_key, size_pt) + ell_w > max_width:
        s = s[:-1]
    return (s.rstrip() + ell) if s else ell


def _wrap_lines(
    text: str,
    max_width: float,
    font_key: str,
    size_pt: float,
    *,
    max_lines: int,
) -> list[str]:
    """Greedy word-wrap. If the final line still overflows after
    `max_lines`, truncates that line."""
    words = text.split()
    if not words:
        return []
    lines: list[str] = []
    cur = words[0]
    for w in words[1:]:
        candidate = f"{cur} {w}"
        if _text_width_estimate(candidate, font_key, size_pt) <= max_width:
            cur = candidate
        else:
            lines.append(cur)
            cur = w
            if len(lines) == max_lines:
                break
    if len(lines) < max_lines:
        lines.append(cur)
    if len(lines) == max_lines:
        # Truncate the final line if needed
        lines[-1] = _truncate_to_width(lines[-1], max_width, font_key, size_pt)
    return lines


def _pill_width(text: str, font_key: str, size_pt: float, *, padding_x: float) -> float:
    return _text_width_estimate(text, font_key, size_pt) + padding_x * 2


# ─────────────────────────────────────────────────────────────────────────────
# Shared geometry helpers
# ─────────────────────────────────────────────────────────────────────────────


def _arrow_path(
    x1: float, y1: float, x2: float, y2: float,
    *, color: str, w: float = 1.4, head: float = 7, opacity: float = 0.85,
) -> str:
    """Direction arrow: solid line + filled triangle head at (x2,y2)."""
    dx, dy = x2 - x1, y2 - y1
    length = (dx * dx + dy * dy) ** 0.5 or 1
    ux, uy = dx / length, dy / length
    x2_line = x2 - ux * (head * 0.6)
    y2_line = y2 - uy * (head * 0.6)
    return (
        f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2_line:.1f}" y2="{y2_line:.1f}" '
        f'stroke="{color}" stroke-width="{w}" stroke-linecap="round" opacity="{opacity}"/>'
        f'<path d="M {x2:.1f} {y2:.1f} '
        f'L {x2 - ux * head - uy * head * 0.45:.1f} {y2 - uy * head + ux * head * 0.45:.1f} '
        f'L {x2 - ux * head + uy * head * 0.45:.1f} {y2 - uy * head - ux * head * 0.45:.1f} Z" '
        f'fill="{color}" opacity="{opacity}"/>'
    )


def _svg_header(
    *, w: int, kicker: str, title: str, pad_x: int,
    primary: str, deep: str, dark_gray: str,
) -> str:
    """Standard kicker + title + rule line at the top of each component."""
    parts: list[str] = []
    if kicker:
        parts.append(
            f'<text x="{pad_x}" y="22" font-family="Inter, sans-serif" '
            f'font-weight="700" font-size="8" letter-spacing="0.22em" '
            f'fill="{dark_gray}">{kicker}</text>'
        )
    if title:
        parts.append(
            f'<text x="{pad_x}" y="44" font-family="Inter, sans-serif" '
            f'font-weight="800" font-size="14" fill="{primary}" '
            f'letter-spacing="-0.015em">{title}</text>'
        )
    parts.append(
        f'<line x1="{pad_x}" y1="60" x2="{w - pad_x}" y2="60" '
        f'stroke="{deep}" stroke-width="0.8"/>'
    )
    return "".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# 1. process_flow — ST-06 mechanism (port of build_v6 with color params)
# ─────────────────────────────────────────────────────────────────────────────


def process_flow(
    steps: list[dict],
    *,
    primary: str,
    accent: str,
    w: Optional[int] = None, h: Optional[int] = None,
    kicker: str = "PROZESS · MECHANIK",
    title: str = "Vorgehen",
    dark_gray: str = DEFAULT_DARK_GRAY,
    deep: str = DEFAULT_DEEP,
) -> str:
    """Linear sequence with solid direction arrows. All circles on one
    horizontal line. Final node accent-coloured; the rest are outlined
    in `primary`.

    US-2026-08-22 (the user's p20 report): the old fixed 340px canvas
    TRUNCATED every step label to "Workflow-A…" (data loss at generation)
    and the render side then shrank that into a 55mm band (unreadable).
    The canvas width now scales with the node count (each step gets a
    fixed share), and labels WRAP to at most 2 full lines instead of being
    cut with an ellipsis — the SVG is a real diagram with real labels.
    """
    n = len(steps)
    # one row per label (WRAP, never truncate). Each step gets >= 130px so
    # labels like "Kontinuierliche Optimierung" fit 2 lines at 10px.
    w = w or max(340, n * 180 + 60)
    h = h or 260
    pad_x = 30
    avail = w - 2 * pad_x
    step_gap = avail / (n - 1) if n > 1 else avail
    inner_max_w = step_gap * 0.96
    end_max_w = step_gap * 1.0

    cy_const = 118
    cx_list, cy_list = [], []
    nodes_svg = []
    for i, s in enumerate(steps):
        cx = pad_x + (avail * i / (n - 1) if n > 1 else avail / 2)
        cy = cy_const
        cx_list.append(cx)
        cy_list.append(cy)
        is_last = (i == n - 1)
        fill = accent if is_last else "white"
        stroke = accent if is_last else primary
        text_color = "white" if is_last else primary
        nodes_svg.append(
            f'<circle cx="{cx:.1f}" cy="{cy}" r="14" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="1.8"/>'
            f'<text x="{cx:.1f}" y="{cy + 4}" text-anchor="middle" '
            f'font-family="Inter, sans-serif" font-weight="800" '
            f'font-size="13" fill="{text_color}">{s["n"]}</text>'
        )

    conns_svg = []
    for i in range(n - 1):
        x1, y1 = cx_list[i] + 14, cy_list[i]
        x2, y2 = cx_list[i + 1] - 14, cy_list[i + 1]
        conns_svg.append(_arrow_path(x1, y1, x2, y2, color=dark_gray, w=1.1,
                                     head=6, opacity=0.7))

    labels_svg = []
    for i, s in enumerate(steps):
        label = s["short"]
        is_end = (i == 0 or i == n - 1)
        max_w = end_max_w if is_end else inner_max_w
        size = _autofit_size(label, max_w, "Inter-700",
                             min_size=12, max_size=14)
        # WRAP (2 lines) — hard truncation with "…" is data loss; a 2-line
        # full label on the mechanism page is real copy shown properly.
        lines = _wrap_lines(label, max_w, "Inter-700", size, max_lines=2)
        if len(lines) == 1:
            lines_svg = (f'<text x="{cx_list[i]:.1f}" y="{cy_const + 37}" '
                         f'text-anchor="middle" font-family="Inter, sans-serif" '
                         f'font-weight="700" font-size="{size}" fill="{primary}" '
                         f'letter-spacing="-0.01em">{lines[0]}</text>')
        else:
            line_h = size * 1.15 + 2
            start_y = cy_const + 37 - (len(lines) - 1) * line_h / 2 - 0
            parts = []
            for li, ln in enumerate(lines):
                parts.append(
                    f'<text x="{cx_list[i]:.1f}" y="{start_y + li * line_h:.1f}" '
                    f'text-anchor="middle" font-family="Inter, sans-serif" '
                    f'font-weight="700" font-size="{size}" fill="{primary}" '
                    f'letter-spacing="-0.01em">{ln}</text>'
                )
            lines_svg = "".join(parts)
        labels_svg.append(lines_svg)

    return (
        f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
        f'xmlns="http://www.w3.org/2000/svg">'
        + _svg_header(w=w, kicker=kicker, title=title, pad_x=pad_x,
                      primary=primary, deep=deep, dark_gray=dark_gray)
        + "".join(conns_svg) + "".join(nodes_svg) + "".join(labels_svg)
        + '</svg>'
    )


# ─────────────────────────────────────────────────────────────────────────────
# 2. matrix_2x2 — ST-09 status-quo matrix
# ─────────────────────────────────────────────────────────────────────────────


def matrix_2x2(
    payload: dict,
    *,
    primary: str,
    accent: str,  # noqa: ARG001  (reserved for future accent dot)
    w: int = 340, h: int = 240,
    kicker: str = "STATUS QUO · MATRIX",
    title: str = "Konsequenzen × Sichtbarkeit",
    dark_gray: str = DEFAULT_DARK_GRAY,
    deep: str = DEFAULT_DEEP,
) -> str:
    """2×2 conceptual matrix with quadrant tags, meanings, and plotted
    items. Per-quadrant flip on label overflow.
    """
    pad_left, pad_top = 60, 56
    plot_w = w - pad_left - 18
    plot_h = 150
    cx = pad_left + plot_w / 2
    cy = pad_top + plot_h / 2
    half_w, half_h = plot_w / 2, plot_h / 2

    quadrants = payload["quadrants"]
    quad_rects = {
        "tl": (pad_left, pad_top, half_w, half_h),
        "tr": (cx, pad_top, half_w, half_h),
        "bl": (pad_left, cy, half_w, half_h),
        "br": (cx, cy, half_w, half_h),
    }
    outer_corner = {
        "tl": ("left", "top"),
        "tr": ("right", "top"),
        "bl": ("left", "bottom"),
        "br": ("right", "bottom"),
    }

    quad_svg = []
    inner_pad = 4
    meaning_w = half_w - inner_pad * 2 - 2
    max_lines = 3
    meaning_lh = 10

    for code, (qx, qy, qw, qh) in quad_rects.items():
        q = quadrants[code]
        tag = q["tag"]
        meaning = q["meaning"]
        h_side, v_side = outer_corner[code]

        tag_size = _autofit_size(tag, meaning_w, "Inter-800",
                                 min_size=7, max_size=8)
        if _text_width_estimate(tag, "Inter-800", tag_size) > meaning_w:
            tag = _truncate_to_width(tag, meaning_w, "Inter-800", tag_size)

        meaning_size = 9
        lines = _wrap_lines(meaning, meaning_w, "Serif-400i",
                            meaning_size, max_lines=max_lines)
        if lines and lines[-1].endswith("…"):
            meaning_size = 8
            lines = _wrap_lines(meaning, meaning_w, "Serif-400i",
                                meaning_size, max_lines=max_lines)

        if h_side == "left":
            anchor_x = qx + inner_pad
            text_anchor = "start"
        else:
            anchor_x = qx + qw - inner_pad
            text_anchor = "end"

        n_lines = len(lines)
        if v_side == "top":
            tag_y = qy + inner_pad + 8
        else:
            tag_y = qy + qh - inner_pad - (n_lines * meaning_lh) - 3

        quad_svg.append(
            f'<text x="{anchor_x:.1f}" y="{tag_y:.1f}" text-anchor="{text_anchor}" '
            f'font-family="Inter, sans-serif" font-weight="800" '
            f'font-size="{tag_size}" letter-spacing="0.22em" '
            f'fill="{primary}">{tag}</text>'
        )
        for li, line in enumerate(lines):
            line_y = tag_y + 4 + (li + 1) * meaning_lh - 2
            quad_svg.append(
                f'<text x="{anchor_x:.1f}" y="{line_y:.1f}" text-anchor="{text_anchor}" '
                f'font-family="Source Serif 4, serif" font-style="italic" '
                f'font-size="{meaning_size}" fill="{dark_gray}">{line}</text>'
            )

    # Item plot with per-quadrant flip-on-overflow
    items_svg = []
    label_size = 8.5
    label_gap = 8
    matrix_right = pad_left + plot_w
    r = 4

    by_quad: dict[str, list] = {"tl": [], "tr": [], "bl": [], "br": []}
    for it in payload["items"]:
        by_quad[it["qtag"]].append(it)

    quad_flip_left: dict[str, bool] = {}
    for qtag, items in by_quad.items():
        any_overflow = False
        for it in items:
            ix = pad_left + it["x"] * plot_w
            lw = _text_width_estimate(it["label"], "Inter-700", label_size)
            if (ix + r + label_gap + lw) > (matrix_right - 2):
                any_overflow = True
                break
        quad_flip_left[qtag] = any_overflow

    for it in payload["items"]:
        ix = pad_left + it["x"] * plot_w
        iy = pad_top + (1 - it["y"]) * plot_h
        label = it["label"]
        flip = quad_flip_left[it["qtag"]]
        if flip:
            text_x = ix - r - label_gap
            text_anchor = "end"
        else:
            text_x = ix + r + label_gap
            text_anchor = "start"
        items_svg.append(
            f'<circle cx="{ix:.1f}" cy="{iy:.1f}" r="{r}" '
            f'fill="{primary}" opacity="0.85"/>'
            f'<text x="{text_x:.1f}" y="{iy + 3:.1f}" text-anchor="{text_anchor}" '
            f'font-family="Inter, sans-serif" font-weight="700" '
            f'font-size="{label_size}" fill="{primary}">{label}</text>'
        )

    y_axis_label = payload["y_axis"]["label"].upper()
    x_axis_label = payload["x_axis"]["label"].upper()

    return (
        f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
        f'xmlns="http://www.w3.org/2000/svg">'
        + _svg_header(w=w, kicker=kicker, title=title, pad_x=22,
                      primary=primary, deep=deep, dark_gray=dark_gray)
        + f'<g transform="translate(22 {pad_top + plot_h / 2}) rotate(-90)">'
        f'<text text-anchor="middle" font-family="Inter, sans-serif" '
        f'font-weight="700" font-size="9" letter-spacing="0.18em" '
        f'fill="{dark_gray}">{y_axis_label}</text></g>'
        f'<text x="{pad_left - 4}" y="{pad_top + 6}" text-anchor="end" '
        f'font-family="Source Serif 4, serif" font-style="italic" '
        f'font-size="9" fill="{dark_gray}">{payload["y_axis"]["high"]}</text>'
        f'<text x="{pad_left - 4}" y="{pad_top + plot_h + 2}" text-anchor="end" '
        f'font-family="Source Serif 4, serif" font-style="italic" '
        f'font-size="9" fill="{dark_gray}">{payload["y_axis"]["low"]}</text>'
        f'<text x="{cx}" y="{pad_top + plot_h + 26}" text-anchor="middle" '
        f'font-family="Inter, sans-serif" font-weight="700" font-size="9" '
        f'letter-spacing="0.18em" fill="{dark_gray}">{x_axis_label}</text>'
        f'<text x="{pad_left}" y="{pad_top + plot_h + 16}" '
        f'font-family="Source Serif 4, serif" font-style="italic" '
        f'font-size="9" fill="{dark_gray}">{payload["x_axis"]["low"]}</text>'
        f'<text x="{pad_left + plot_w}" y="{pad_top + plot_h + 16}" '
        f'text-anchor="end" font-family="Source Serif 4, serif" '
        f'font-style="italic" font-size="9" '
        f'fill="{dark_gray}">{payload["x_axis"]["high"]}</text>'
        f'<rect x="{pad_left}" y="{pad_top}" width="{plot_w}" height="{plot_h}" '
        f'fill="none" stroke="{deep}" stroke-width="1"/>'
        f'<line x1="{cx}" y1="{pad_top}" x2="{cx}" y2="{pad_top + plot_h}" '
        f'stroke="{deep}" stroke-width="0.8"/>'
        f'<line x1="{pad_left}" y1="{cy}" x2="{pad_left + plot_w}" y2="{cy}" '
        f'stroke="{deep}" stroke-width="0.8"/>'
        + "".join(quad_svg) + "".join(items_svg) + '</svg>'
    )


# ─────────────────────────────────────────────────────────────────────────────
# 3. causality_chain — ST-14 belief→consequence
# ─────────────────────────────────────────────────────────────────────────────


def causality_chain(
    pills: list[str],
    *,
    primary: str,
    accent: str,
    w: int = 340, h: int = 240,
    kicker: str = "URSACHE → KONSEQUENZ",
    title: str = "Die Kausalkette",
    dark_gray: str = DEFAULT_DARK_GRAY,
    deep: str = DEFAULT_DEEP,
) -> str:
    """N-pill cause→effect chain. Terminal pill is accent-coloured."""
    pad_x = 12
    avail = w - 2 * pad_x

    def measure(size_pt: int, arrow_gap: float, pad_inner: float):
        widths = [_pill_width(t, "Inter-700", size_pt, padding_x=pad_inner)
                  for t in pills]
        n_arrows = len(pills) - 1
        total = sum(widths) + n_arrows * arrow_gap
        return widths, total

    candidates = [
        (12, 10, 22), (12, 10, 14), (12, 8, 14),
        (11, 10, 22), (11, 10, 14), (11, 8, 14), (11, 8, 10),
        (10, 10, 14), (10, 8, 14), (10, 8, 10), (10, 7, 10),
        (9, 10, 14), (9, 8, 14), (9, 8, 10), (9, 7, 10), (9, 6, 10),
    ]
    chosen_size = chosen_pad_in = chosen_gap = None
    widths = None
    for s, pin, gap in candidates:
        widths_s, total_s = measure(s, gap, pin)
        if total_s <= avail:
            chosen_size, chosen_pad_in, chosen_gap = s, pin, gap
            widths = widths_s
            break
    if chosen_size is None:
        chosen_size, chosen_pad_in, chosen_gap = 9, 6, 8
        widths, _ = measure(9, 8, 6)

    size_pt = chosen_size
    min_arrow_gap = chosen_gap
    pill_h = 34
    y_pill = 110
    cy = y_pill + pill_h / 2

    extra = max(0, avail - (sum(widths) + (len(pills) - 1) * min_arrow_gap))
    extra_each = extra / max(1, len(pills) - 1)
    actual_arrow = min_arrow_gap + extra_each

    pills_svg = []
    arrows_svg = []
    cur_x = pad_x
    centers = []
    for i, txt in enumerate(pills):
        pw = widths[i]
        is_last = (i == len(pills) - 1)
        fill = accent if is_last else "white"
        stroke = accent if is_last else primary
        text_color = "white" if is_last else primary
        pills_svg.append(
            f'<rect x="{cur_x:.1f}" y="{y_pill}" width="{pw:.1f}" height="{pill_h}" '
            f'rx="{pill_h/2:.1f}" ry="{pill_h/2:.1f}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="1.6"/>'
            f'<text x="{cur_x + pw/2:.1f}" y="{cy + 4:.1f}" text-anchor="middle" '
            f'font-family="Inter, sans-serif" font-weight="700" '
            f'font-size="{size_pt}" fill="{text_color}">{txt}</text>'
        )
        centers.append((cur_x, cur_x + pw))
        cur_x += pw + actual_arrow

    for i in range(len(pills) - 1):
        x1 = centers[i][1]
        x2 = centers[i + 1][0]
        arrows_svg.append(
            _arrow_path(x1 + 3, cy, x2 - 3, cy,
                        color=primary, w=1.4, head=7, opacity=0.85)
        )

    return (
        f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
        f'xmlns="http://www.w3.org/2000/svg">'
        + _svg_header(w=w, kicker=kicker, title=title, pad_x=pad_x,
                      primary=primary, deep=deep, dark_gray=dark_gray)
        + "".join(arrows_svg) + "".join(pills_svg) + '</svg>'
    )


# ─────────────────────────────────────────────────────────────────────────────
# 4. metaphor_split — iceberg
# ─────────────────────────────────────────────────────────────────────────────


def metaphor_split(
    payload: dict,
    *,
    primary: str,
    accent: str,  # noqa: ARG001
    neutral_light: str = DEFAULT_CREAM,
    w: int = 340, h: int = 240,
    kicker: str = "SYSTEM · SICHTBAR vs. VERBORGEN",
    title: str = "Was sichtbar ist — was Sie kostet",
    above_label: str = "20% SICHTBAR",
    below_label: str = "80% VERBORGEN",
    dark_gray: str = DEFAULT_DARK_GRAY,
    deep: str = DEFAULT_DEEP,
) -> str:
    """Iceberg silhouette with above-/below-waterline label blocks."""
    pad_x = 22
    header_h = 60
    ice_top = header_h + 14
    ice_bot = h - 14
    ice_h = ice_bot - ice_top

    ice_full_w = w * 0.42
    ice_left = pad_x
    ice_right = ice_left + ice_full_w
    ice_cx = ice_left + ice_full_w / 2

    above_h = ice_h * 0.25
    waterline_y = ice_top + above_h

    pl, pr, cw = ice_left, ice_right, ice_cx
    wt, bt = waterline_y, ice_bot

    peak_apex_x = cw - 6
    peak_apex_y = ice_top + 1
    peak_l_wing_x = pl + 22
    peak_r_wing_x = pr - 18
    above_path = (
        f"M {peak_l_wing_x:.1f} {wt:.1f} "
        f"L {peak_l_wing_x + 6:.1f} {wt - above_h * 0.55:.1f} "
        f"L {peak_apex_x:.1f} {peak_apex_y:.1f} "
        f"L {peak_apex_x + 11:.1f} {peak_apex_y + above_h * 0.35:.1f} "
        f"L {peak_apex_x + 19:.1f} {peak_apex_y + above_h * 0.22:.1f} "
        f"L {peak_r_wing_x:.1f} {wt:.1f} Z"
    )
    below_path = (
        f"M {peak_l_wing_x:.1f} {wt:.1f} "
        f"L {pl + 8:.1f} {wt + ice_h * 0.08:.1f} "
        f"L {pl - 2:.1f} {wt + ice_h * 0.20:.1f} "
        f"C {pl - 8:.1f} {wt + ice_h * 0.30:.1f}, "
        f"{pl - 5:.1f} {wt + ice_h * 0.42:.1f}, "
        f"{pl + 4:.1f} {wt + ice_h * 0.48:.1f} "
        f"L {pl + 14:.1f} {wt + ice_h * 0.55:.1f} "
        f"L {pl + 6:.1f} {wt + ice_h * 0.65:.1f} "
        f"C {pl + 2:.1f} {wt + ice_h * 0.74:.1f}, "
        f"{pl + 14:.1f} {bt - 6:.1f}, "
        f"{pl + 22:.1f} {bt:.1f} "
        f"L {pl + 38:.1f} {bt - 4:.1f} "
        f"L {pl + 52:.1f} {bt:.1f} "
        f"L {ice_right - 38:.1f} {bt - 2:.1f} "
        f"L {ice_right - 18:.1f} {bt:.1f} "
        f"C {ice_right + 6:.1f} {wt + ice_h * 0.70:.1f}, "
        f"{ice_right + 14:.1f} {wt + ice_h * 0.55:.1f}, "
        f"{ice_right + 4:.1f} {wt + ice_h * 0.42:.1f} "
        f"L {ice_right + 10:.1f} {wt + ice_h * 0.32:.1f} "
        f"L {ice_right - 2:.1f} {wt + ice_h * 0.22:.1f} "
        f"L {ice_right + 6:.1f} {wt + ice_h * 0.13:.1f} "
        f"L {peak_r_wing_x:.1f} {wt:.1f} Z"
    )
    waterline = (
        f'<line x1="{pad_x}" y1="{waterline_y:.1f}" x2="{w - pad_x}" '
        f'y2="{waterline_y:.1f}" stroke="{dark_gray}" stroke-width="0.8" '
        f'stroke-dasharray="3 3" opacity="0.5"/>'
    )

    label_x = ice_right + 16
    label_w_avail = (w - pad_x) - label_x - 2

    above_tag_y = ice_top + 14
    above_block = [
        f'<text x="{label_x:.1f}" y="{above_tag_y:.1f}" '
        f'font-family="Inter, sans-serif" font-weight="800" font-size="9" '
        f'letter-spacing="0.22em" fill="{primary}">{above_label}</text>'
    ]
    cur_y = above_tag_y + 14
    for itm in payload["visible"]["items"]:
        size = _autofit_size(itm, label_w_avail - 10, "Inter-700",
                             min_size=9, max_size=10)
        if _text_width_estimate(itm, "Inter-700", size) > (label_w_avail - 10):
            lines = _wrap_lines(itm, label_w_avail - 10, "Inter-700", 9,
                                max_lines=2)
        else:
            lines = [itm]
        for li, line in enumerate(lines):
            if li == 0:
                above_block.append(
                    f'<circle cx="{label_x + 3:.1f}" cy="{cur_y - 3:.1f}" '
                    f'r="1.6" fill="{primary}"/>'
                )
            above_block.append(
                f'<text x="{label_x + 10:.1f}" y="{cur_y:.1f}" '
                f'font-family="Inter, sans-serif" font-weight="600" '
                f'font-size="{size}" fill="{primary}">{line}</text>'
            )
            cur_y += 12

    below_block = []
    below_tag_y = max(cur_y + 6, waterline_y + 16)
    below_block.append(
        f'<text x="{label_x:.1f}" y="{below_tag_y:.1f}" '
        f'font-family="Inter, sans-serif" font-weight="800" font-size="9" '
        f'letter-spacing="0.22em" fill="{primary}">{below_label}</text>'
    )
    cur_y = below_tag_y + 14
    for itm in payload["hidden"]["items"]:
        size = _autofit_size(itm, label_w_avail - 10, "Inter-700",
                             min_size=9, max_size=10)
        if _text_width_estimate(itm, "Inter-700", size) > (label_w_avail - 10):
            lines = _wrap_lines(itm, label_w_avail - 10, "Inter-700", 9,
                                max_lines=2)
        else:
            lines = [itm]
        for li, line in enumerate(lines):
            if li == 0:
                below_block.append(
                    f'<circle cx="{label_x + 3:.1f}" cy="{cur_y - 3:.1f}" '
                    f'r="1.6" fill="{primary}"/>'
                )
            below_block.append(
                f'<text x="{label_x + 10:.1f}" y="{cur_y:.1f}" '
                f'font-family="Inter, sans-serif" font-weight="600" '
                f'font-size="{size}" fill="{primary}">{line}</text>'
            )
            cur_y += 12
        cur_y += 1

    return (
        f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
        f'xmlns="http://www.w3.org/2000/svg">'
        + _svg_header(w=w, kicker=kicker, title=title, pad_x=pad_x,
                      primary=primary, deep=deep, dark_gray=dark_gray)
        + waterline
        + f'<path d="{above_path}" fill="{neutral_light}" stroke="{primary}" '
        f'stroke-width="1.2" stroke-linejoin="round"/>'
        + f'<path d="{below_path}" fill="{primary}" fill-opacity="0.92" '
        f'stroke="{primary}" stroke-width="1.2" stroke-linejoin="round"/>'
        + "".join(above_block) + "".join(below_block)
        + '</svg>'
    )


# ─────────────────────────────────────────────────────────────────────────────
# 5. bar_chart
# ─────────────────────────────────────────────────────────────────────────────


def bar_chart(
    data: list[dict],
    *,
    primary: str,
    accent: str,
    w: int = 340, h: int = 240,
    accent_label: Optional[str] = None,
    kicker: str = "KENNZAHL · STUNDEN/MONAT",
    title: str = "Aufwand pro Prozess",
    dark_gray: str = DEFAULT_DARK_GRAY,
    deep: str = DEFAULT_DEEP,
) -> str:
    """N-bar chart. One bar accent-coloured (by `accent_label` or last)."""
    pad_left, pad_right, pad_top, pad_bot = 40, 22, 64, 56
    plot_w = w - pad_left - pad_right
    plot_h = h - pad_top - pad_bot
    n = len(data)
    max_v = max(d["value"] for d in data)
    bw = plot_w / (n * 1.5)
    gap = (plot_w - bw * n) / (n - 1) if n > 1 else 0

    label_slot_w = bw + gap * 0.8
    label_plan = []
    for d in data:
        label = d["label"]
        size = _autofit_size(label, label_slot_w, "Inter-700",
                             min_size=9, max_size=11)
        if _text_width_estimate(label, "Inter-700", size) <= label_slot_w:
            label_plan.append({"text": label, "size": size, "lines": [label]})
        else:
            lines = _wrap_lines(label, label_slot_w, "Inter-700", 9, max_lines=2)
            label_plan.append({"text": label, "size": 9, "lines": lines})

    baseline_y = pad_top + plot_h
    bars_svg = []
    for i, d in enumerate(data):
        bh = (d["value"] / max_v) * plot_h
        x = pad_left + i * (bw + gap)
        y = baseline_y - bh
        is_accent = (d["label"] == accent_label) if accent_label \
            else (i == n - 1)
        fill = accent if is_accent else primary
        opacity = 1.0 if is_accent else 0.85
        bars_svg.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{bh:.1f}" '
            f'fill="{fill}" opacity="{opacity}"/>'
            f'<text x="{x + bw/2:.1f}" y="{y - 6:.1f}" text-anchor="middle" '
            f'font-family="Inter, sans-serif" font-weight="800" '
            f'font-size="10" fill="{primary}">{d["display"]}</text>'
        )
        plan = label_plan[i]
        for li, line in enumerate(plan["lines"]):
            line_y = baseline_y + 16 + li * 11
            bars_svg.append(
                f'<text x="{x + bw/2:.1f}" y="{line_y:.1f}" text-anchor="middle" '
                f'font-family="Inter, sans-serif" font-weight="600" '
                f'font-size="{plan["size"]}" fill="{dark_gray}">{line}</text>'
            )

    return (
        f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
        f'xmlns="http://www.w3.org/2000/svg">'
        + _svg_header(w=w, kicker=kicker, title=title, pad_x=22,
                      primary=primary, deep=deep, dark_gray=dark_gray)
        + f'<line x1="{pad_left}" y1="{baseline_y:.1f}" x2="{w - pad_right}" '
        f'y2="{baseline_y:.1f}" stroke="{primary}" stroke-width="1"/>'
        + "".join(bars_svg) + '</svg>'
    )


# ─────────────────────────────────────────────────────────────────────────────
# 6. line_chart
# ─────────────────────────────────────────────────────────────────────────────


def line_chart(
    series: list[dict], x_labels: list[str], y_ticks: list[int],
    *,
    primary: str,
    accent: str,
    w: int = 340, h: int = 240,
    kicker: str = "TRAJEKTORIE",
    title: str = "Verlauf",
    dark_gray: str = DEFAULT_DARK_GRAY,
    deep: str = DEFAULT_DEEP,
) -> str:
    """Multi-series line chart. Each series can mark itself accent."""
    pad_left, pad_right, pad_top, pad_bot = 44, 76, 64, 36
    plot_w = w - pad_left - pad_right
    plot_h = h - pad_top - pad_bot
    y_max = max(y_ticks)
    y_min = 0
    n = len(x_labels)
    label_avail_w = pad_right - 12

    lines_svg = []
    for s in series:
        is_accent = s.get("accent", False)
        color = accent if is_accent else dark_gray
        opacity = 1.0 if is_accent else 0.75
        pts = []
        for i, v in enumerate(s["values"]):
            x = pad_left + (plot_w * i / (n - 1))
            y = pad_top + plot_h - ((v - y_min) / (y_max - y_min)) * plot_h
            pts.append((x, y))
        path_d = " ".join(f"{'M' if i == 0 else 'L'} {x:.1f} {y:.1f}"
                          for i, (x, y) in enumerate(pts))
        lines_svg.append(
            f'<path d="{path_d}" stroke="{color}" '
            f'stroke-width="{2.4 if is_accent else 1.8}" fill="none" '
            f'opacity="{opacity}" stroke-linecap="round" stroke-linejoin="round"/>'
        )
        last_x, last_y = pts[-1]
        lbl = s["label"]
        lbl_size = _autofit_size(lbl, label_avail_w, "Inter-700",
                                 min_size=9, max_size=11)
        if _text_width_estimate(lbl, "Inter-700", lbl_size) > label_avail_w:
            lbl = _truncate_to_width(lbl, label_avail_w, "Inter-700", lbl_size)
        val_text = f"{s['values'][-1]}"
        lines_svg.append(
            f'<circle cx="{last_x:.1f}" cy="{last_y:.1f}" r="3.5" fill="{color}"/>'
            f'<text x="{last_x + 8:.1f}" y="{last_y + 4:.1f}" '
            f'font-family="Inter, sans-serif" font-weight="700" '
            f'font-size="{lbl_size}" fill="{color}">{lbl}</text>'
            f'<text x="{last_x + 8:.1f}" y="{last_y + 16:.1f}" '
            f'font-family="Source Serif 4, serif" font-style="italic" '
            f'font-size="8.5" fill="{dark_gray}">{val_text}</text>'
        )

    y_ticks_svg = []
    for tick in y_ticks:
        y = pad_top + plot_h - (tick / y_max) * plot_h
        y_ticks_svg.append(
            f'<line x1="{pad_left - 4:.1f}" y1="{y:.1f}" '
            f'x2="{pad_left:.1f}" y2="{y:.1f}" stroke="{dark_gray}" stroke-width="0.8"/>'
            f'<text x="{pad_left - 8:.1f}" y="{y + 3:.1f}" text-anchor="end" '
            f'font-family="Inter, sans-serif" font-weight="600" '
            f'font-size="8.5" fill="{dark_gray}">{tick}</text>'
            f'<line x1="{pad_left:.1f}" y1="{y:.1f}" '
            f'x2="{w - pad_right:.1f}" y2="{y:.1f}" '
            f'stroke="{deep}" stroke-width="0.6" stroke-dasharray="2 3" opacity="0.5"/>'
        )

    ticks_svg = []
    x_slot_w = plot_w / max(1, n - 1)
    for i, lbl in enumerate(x_labels):
        x = pad_left + (plot_w * i / (n - 1))
        s = _autofit_size(lbl, x_slot_w * 0.9, "Inter-700",
                          min_size=9, max_size=10)
        ticks_svg.append(
            f'<text x="{x:.1f}" y="{pad_top + plot_h + 16}" text-anchor="middle" '
            f'font-family="Inter, sans-serif" font-weight="600" '
            f'font-size="{s}" fill="{dark_gray}">{lbl}</text>'
        )

    return (
        f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
        f'xmlns="http://www.w3.org/2000/svg">'
        + _svg_header(w=w, kicker=kicker, title=title, pad_x=22,
                      primary=primary, deep=deep, dark_gray=dark_gray)
        + "".join(y_ticks_svg)
        + f'<line x1="{pad_left}" y1="{pad_top + plot_h}" '
        f'x2="{w - pad_right}" y2="{pad_top + plot_h}" '
        f'stroke="{primary}" stroke-width="1"/>'
        + "".join(lines_svg) + "".join(ticks_svg)
        + '</svg>'
    )


# ─────────────────────────────────────────────────────────────────────────────
# 7. stat_block — ST-07A case study result row
# ─────────────────────────────────────────────────────────────────────────────


def stat_block(
    stats: list[dict],
    *,
    primary: str,
    accent: str,
    w: int = 340, h: int = 240,
    accent_idx: int = 0,
    kicker: str = "ERGEBNIS",
    title: str = "Kennzahlen",
    dark_gray: str = DEFAULT_DARK_GRAY,
    deep: str = DEFAULT_DEEP,
) -> str:
    """3-up big-number row."""
    n = len(stats)
    pad_x = 18
    avail = w - 2 * pad_x
    col_w = avail / n
    cols = []
    for i, st in enumerate(stats):
        cx = pad_x + col_w * i + col_w / 2
        is_accent = (i == accent_idx)
        num_color = accent if is_accent else primary

        label_upper = st["label"].upper()
        lbl_avail = col_w * 0.92
        lbl_size = _autofit_size(label_upper, lbl_avail, "Inter-700",
                                 min_size=9, max_size=11)
        if _text_width_estimate(label_upper, "Inter-700", lbl_size) > lbl_avail:
            label_upper = _truncate_to_width(label_upper, lbl_avail,
                                             "Inter-700", lbl_size)

        sub = st["sub"]
        sub_avail = col_w * 0.92
        sub_size = _autofit_size(sub, sub_avail, "Serif-400i",
                                 min_size=9, max_size=10)
        if _text_width_estimate(sub, "Serif-400i", sub_size) > sub_avail:
            sub = _truncate_to_width(sub, sub_avail, "Serif-400i", sub_size)

        cols.append(
            f'<text x="{cx:.1f}" y="120" text-anchor="middle" '
            f'font-family="Inter, sans-serif" font-weight="900" '
            f'font-size="34" fill="{num_color}" '
            f'letter-spacing="-0.04em">{st["value"]}</text>'
            f'<text x="{cx:.1f}" y="148" text-anchor="middle" '
            f'font-family="Inter, sans-serif" font-weight="700" '
            f'font-size="{lbl_size}" letter-spacing="0.18em" '
            f'fill="{dark_gray}">{label_upper}</text>'
            f'<text x="{cx:.1f}" y="166" text-anchor="middle" '
            f'font-family="Source Serif 4, serif" font-style="italic" '
            f'font-size="{sub_size}" fill="{primary}">{sub}</text>'
        )
        if i < n - 1:
            cols.append(
                f'<line x1="{pad_x + col_w * (i + 1):.1f}" y1="88" '
                f'x2="{pad_x + col_w * (i + 1):.1f}" y2="128" '
                f'stroke="{deep}" stroke-width="0.8"/>'
            )

    return (
        f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
        f'xmlns="http://www.w3.org/2000/svg">'
        + _svg_header(w=w, kicker=kicker, title=title, pad_x=pad_x,
                      primary=primary, deep=deep, dark_gray=dark_gray)
        + "".join(cols) + '</svg>'
    )


# ─────────────────────────────────────────────────────────────────────────────
# 8. compare_table — Before/After 2-column
# ─────────────────────────────────────────────────────────────────────────────


def compare_table(
    rows: list[dict],
    headers: tuple[str, str],
    *,
    primary: str,
    accent: str,  # noqa: ARG001  (reserved; current design uses red/green for x/√)
    w: int = 340, h: int = 320,
    kicker: str = "VOR · NACH",
    title: str = "Vorher / Nachher",
    dark_gray: str = DEFAULT_DARK_GRAY,
    deep: str = DEFAULT_DEEP,
    bad_color: str = DEFAULT_COMPARE_RED,
    good_color: str = DEFAULT_COMPARE_GREEN,
) -> str:
    """2-column before/after with red ✕ on left, green ✓ on right."""
    pad_x = 18
    head_y = 78
    col_w = (w - 2 * pad_x) / 2
    icon_gutter = 18
    text_left_x = pad_x + icon_gutter
    text_right_x = pad_x + col_w + 8 + icon_gutter
    cell_text_w_left = col_w - icon_gutter - 4
    cell_text_w_right = col_w - icon_gutter - 4

    line_size = 9
    line_h = 12
    row_top_pad = 6

    plans = []
    for r in rows:
        left_lines = _wrap_lines(r["left"], cell_text_w_left, "Inter-700",
                                 line_size, max_lines=2)
        right_lines = _wrap_lines(r["right"], cell_text_w_right, "Inter-700",
                                  line_size, max_lines=2)
        n_lines = max(len(left_lines), len(right_lines))
        row_h = max(28, row_top_pad + n_lines * line_h + 8)
        plans.append({"left": left_lines, "right": right_lines,
                      "n_lines": n_lines, "row_h": row_h})

    rows_svg = []
    y = head_y + 22
    for i, plan in enumerate(plans):
        n_lines = plan["n_lines"]
        row_center_y = y + plan["row_h"] / 2
        icon_y = row_center_y - 6
        text_block_h = n_lines * line_h
        text_start_y = row_center_y - text_block_h / 2 + (line_size - 1)

        rows_svg.append(
            f'<g transform="translate({pad_x} {icon_y:.1f})">'
            f'<circle cx="6" cy="6" r="6" fill="{bad_color}" opacity="0.16"/>'
            f'<path d="M 3 3 L 9 9 M 9 3 L 3 9" stroke="{bad_color}" '
            f'stroke-width="1.5" stroke-linecap="round"/>'
            f'</g>'
        )
        for li, line in enumerate(plan["left"]):
            line_y = text_start_y + li * line_h
            rows_svg.append(
                f'<text x="{text_left_x:.1f}" y="{line_y:.1f}" '
                f'font-family="Inter, sans-serif" font-weight="500" '
                f'font-size="{line_size}" fill="{primary}" '
                f'opacity="0.7">{line}</text>'
            )
        rows_svg.append(
            f'<g transform="translate({pad_x + col_w + 8:.1f} {icon_y:.1f})">'
            f'<circle cx="6" cy="6" r="6" fill="{good_color}" opacity="0.18"/>'
            f'<path d="M 2.5 6 L 5 8.5 L 9.5 4" stroke="{good_color}" '
            f'stroke-width="1.7" stroke-linecap="round" '
            f'stroke-linejoin="round" fill="none"/>'
            f'</g>'
        )
        for li, line in enumerate(plan["right"]):
            line_y = text_start_y + li * line_h
            rows_svg.append(
                f'<text x="{text_right_x:.1f}" y="{line_y:.1f}" '
                f'font-family="Inter, sans-serif" font-weight="700" '
                f'font-size="{line_size}" fill="{primary}">{line}</text>'
            )
        if i < len(plans) - 1:
            div_y = y + plan["row_h"]
            rows_svg.append(
                f'<line x1="{pad_x}" y1="{div_y:.1f}" x2="{w - pad_x}" '
                f'y2="{div_y:.1f}" stroke="{deep}" stroke-width="0.6"/>'
            )
        y += plan["row_h"]

    last_row_bottom = y
    required_h = int(last_row_bottom + 16)
    svg_h = max(h, required_h)

    return (
        f'<svg viewBox="0 0 {w} {svg_h}" width="{w}" height="{svg_h}" '
        f'xmlns="http://www.w3.org/2000/svg">'
        + _svg_header(w=w, kicker=kicker, title=title, pad_x=pad_x,
                      primary=primary, deep=deep, dark_gray=dark_gray)
        + f'<text x="{pad_x}" y="{head_y + 8}" '
        f'font-family="Inter, sans-serif" font-weight="800" '
        f'font-size="8.5" letter-spacing="0.18em" '
        f'fill="{dark_gray}">{headers[0]}</text>'
        + f'<text x="{pad_x + col_w + 8}" y="{head_y + 8}" '
        f'font-family="Inter, sans-serif" font-weight="800" font-size="8.5" '
        f'letter-spacing="0.18em" fill="{primary}">{headers[1]}</text>'
        + f'<line x1="{pad_x + col_w - 4}" y1="{head_y - 2}" '
        f'x2="{pad_x + col_w - 4}" y2="{last_row_bottom:.1f}" '
        f'stroke="{deep}" stroke-width="0.8"/>'
        + "".join(rows_svg) + '</svg>'
    )


# ─────────────────────────────────────────────────────────────────────────────
# 9 (NEW). curved_arrow_flow — numbered process flow with curved connectors
# ─────────────────────────────────────────────────────────────────────────────


def curved_arrow_flow(
    steps: list[dict],
    *,
    primary: str,
    accent: str,
    w: int = 800, h: int = 400,
    kicker: str = "ABLAUF · MEHRSCHRITTIG",
    title: str = "Vorgehen Schritt für Schritt",
    dark_gray: str = DEFAULT_DARK_GRAY,
    deep: str = DEFAULT_DEEP,
) -> str:
    """Numbered process steps in panels connected by curved arrows.

    Each step dict carries `number`, `title`, `description`. Panels are
    filled in `primary`; step numbers are large and prominent in
    `accent`. Connectors are quadratic Bézier curves arcing alternately
    above/below the baseline.
    """
    n = len(steps)
    pad_x = 30
    pad_top = 70
    panel_gap = 36
    avail = w - 2 * pad_x
    panel_w = (avail - panel_gap * (n - 1)) / max(1, n)
    panel_h = 180
    panel_y = pad_top
    panel_radius = 6

    panels_svg = []
    arrows_svg = []
    centers = []

    for i, step in enumerate(steps):
        px = pad_x + i * (panel_w + panel_gap)
        cx = px + panel_w / 2

        # Filled panel
        panels_svg.append(
            f'<rect x="{px:.1f}" y="{panel_y}" width="{panel_w:.1f}" '
            f'height="{panel_h}" rx="{panel_radius}" ry="{panel_radius}" '
            f'fill="{primary}"/>'
        )
        # Step number prominent
        number = step.get("number", f"{i + 1:02d}")
        panels_svg.append(
            f'<text x="{cx:.1f}" y="{panel_y + 50}" text-anchor="middle" '
            f'font-family="Inter, sans-serif" font-weight="900" '
            f'font-size="32" fill="{accent}" '
            f'letter-spacing="-0.04em">{number}</text>'
        )
        # Step title (white on primary panel)
        title_text = step.get("title", "")
        title_avail = panel_w - 16
        title_size = _autofit_size(title_text, title_avail, "Inter-800",
                                   min_size=10, max_size=14)
        if _text_width_estimate(title_text, "Inter-800", title_size) > title_avail:
            title_text = _truncate_to_width(title_text, title_avail,
                                            "Inter-800", title_size)
        panels_svg.append(
            f'<text x="{cx:.1f}" y="{panel_y + 90}" text-anchor="middle" '
            f'font-family="Inter, sans-serif" font-weight="800" '
            f'font-size="{title_size}" fill="white">{title_text}</text>'
        )
        # Step description (wrap, white at lower weight)
        desc_text = step.get("description", "")
        desc_lines = _wrap_lines(desc_text, panel_w - 16, "Inter-400",
                                 9, max_lines=4)
        for li, line in enumerate(desc_lines):
            panels_svg.append(
                f'<text x="{cx:.1f}" y="{panel_y + 112 + li * 12}" '
                f'text-anchor="middle" font-family="Inter, sans-serif" '
                f'font-weight="500" font-size="9" '
                f'fill="white" fill-opacity="0.86">{line}</text>'
            )
        centers.append((px, cx, px + panel_w))

    # Curved connectors — quadratic Bézier arcing above (even idx) or
    # below (odd idx). End in an arrow head.
    for i in range(n - 1):
        x_from = centers[i][2] + 4
        x_to = centers[i + 1][0] - 4
        y_mid = panel_y + panel_h / 2
        # Arc up for even, down for odd
        arc_height = 28
        sign = -1 if (i % 2 == 0) else 1
        ctrl_x = (x_from + x_to) / 2
        ctrl_y = y_mid + sign * arc_height
        # Bézier curve path
        arrows_svg.append(
            f'<path d="M {x_from:.1f} {y_mid:.1f} '
            f'Q {ctrl_x:.1f} {ctrl_y:.1f} {x_to:.1f} {y_mid:.1f}" '
            f'stroke="{accent}" stroke-width="2" fill="none" '
            f'stroke-linecap="round"/>'
        )
        # Arrow head at x_to
        head = 8
        arrows_svg.append(
            f'<path d="M {x_to:.1f} {y_mid:.1f} '
            f'L {x_to - head:.1f} {y_mid - head * 0.5:.1f} '
            f'L {x_to - head:.1f} {y_mid + head * 0.5:.1f} Z" '
            f'fill="{accent}"/>'
        )

    return (
        f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
        f'xmlns="http://www.w3.org/2000/svg">'
        + _svg_header(w=w, kicker=kicker, title=title, pad_x=pad_x,
                      primary=primary, deep=deep, dark_gray=dark_gray)
        + "".join(panels_svg) + "".join(arrows_svg) + '</svg>'
    )


# ─────────────────────────────────────────────────────────────────────────────
# 10 (NEW). paired_comparison — Before/After two-column with markers
# ─────────────────────────────────────────────────────────────────────────────


def paired_comparison(
    pairs: list[dict],
    *,
    primary: str,
    accent: str,
    w: int = 800, h: int = 300,
    kicker: str = "VORHER · NACHHER",
    title: str = "Was sich ändert",
    dark_gray: str = DEFAULT_DARK_GRAY,
    deep: str = DEFAULT_DEEP,
) -> str:
    """Side-by-side before/after rows. Left column muted (grey); right
    column highlighted in accent. Each row carries an arrow marker
    between the two columns.
    """
    pad_x = 30
    pad_top = 80
    col_gap = 60
    row_h = max(40, (h - pad_top - 30) // max(1, len(pairs)))
    col_w = (w - 2 * pad_x - col_gap) / 2

    parts: list[str] = []

    # Column header bar
    parts.append(
        f'<rect x="{pad_x}" y="{pad_top - 24}" width="{col_w:.1f}" '
        f'height="18" fill="{dark_gray}" opacity="0.10"/>'
    )
    parts.append(
        f'<text x="{pad_x + 8}" y="{pad_top - 11}" '
        f'font-family="Inter, sans-serif" font-weight="800" font-size="9" '
        f'letter-spacing="0.20em" fill="{dark_gray}">VORHER</text>'
    )
    parts.append(
        f'<rect x="{pad_x + col_w + col_gap:.1f}" y="{pad_top - 24}" '
        f'width="{col_w:.1f}" height="18" fill="{accent}" opacity="0.15"/>'
    )
    parts.append(
        f'<text x="{pad_x + col_w + col_gap + 8:.1f}" y="{pad_top - 11}" '
        f'font-family="Inter, sans-serif" font-weight="800" font-size="9" '
        f'letter-spacing="0.20em" fill="{accent}">NACHHER</text>'
    )

    for i, pair in enumerate(pairs):
        y_row = pad_top + i * row_h
        y_center = y_row + row_h / 2

        # Left (before) cell — muted card
        parts.append(
            f'<rect x="{pad_x}" y="{y_row + 4:.1f}" width="{col_w:.1f}" '
            f'height="{row_h - 8:.1f}" fill="white" '
            f'stroke="{deep}" stroke-width="1" rx="3" ry="3"/>'
        )
        before_text = pair.get("before", "")
        lines = _wrap_lines(before_text, col_w - 20, "Inter-700",
                            11, max_lines=2)
        for li, line in enumerate(lines):
            parts.append(
                f'<text x="{pad_x + 12}" y="{y_center - 2 + li * 13:.1f}" '
                f'font-family="Inter, sans-serif" font-weight="500" '
                f'font-size="11" fill="{primary}" '
                f'opacity="0.65">{line}</text>'
            )

        # Right (after) cell — accent-highlighted card
        rx = pad_x + col_w + col_gap
        parts.append(
            f'<rect x="{rx:.1f}" y="{y_row + 4:.1f}" width="{col_w:.1f}" '
            f'height="{row_h - 8:.1f}" fill="{accent}" fill-opacity="0.08" '
            f'stroke="{accent}" stroke-width="1.6" rx="3" ry="3"/>'
        )
        after_text = pair.get("after", "")
        lines = _wrap_lines(after_text, col_w - 20, "Inter-800",
                            11, max_lines=2)
        for li, line in enumerate(lines):
            parts.append(
                f'<text x="{rx + 12:.1f}" y="{y_center - 2 + li * 13:.1f}" '
                f'font-family="Inter, sans-serif" font-weight="800" '
                f'font-size="11" fill="{primary}">{line}</text>'
            )

        # Centre arrow marker
        ax = pad_x + col_w + col_gap / 2
        parts.append(
            f'<circle cx="{ax:.1f}" cy="{y_center:.1f}" r="10" '
            f'fill="{accent}"/>'
        )
        parts.append(
            f'<path d="M {ax - 4:.1f} {y_center - 4:.1f} '
            f'L {ax + 4:.1f} {y_center:.1f} '
            f'L {ax - 4:.1f} {y_center + 4:.1f}" '
            f'stroke="white" stroke-width="1.8" fill="none" '
            f'stroke-linecap="round" stroke-linejoin="round"/>'
        )

    return (
        f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
        f'xmlns="http://www.w3.org/2000/svg">'
        + _svg_header(w=w, kicker=kicker, title=title, pad_x=pad_x,
                      primary=primary, deep=deep, dark_gray=dark_gray)
        + "".join(parts) + '</svg>'
    )


# ─────────────────────────────────────────────────────────────────────────────
# 11 (NEW). venn_diagram — 2 or 3 overlapping circles
# ─────────────────────────────────────────────────────────────────────────────


def venn_diagram(
    labels: list[str],
    intersection_label: str,
    *,
    primary: str,
    accent: str,
    w: int = 600, h: int = 400,
    kicker: str = "ÜBERSCHNEIDUNG",
    title: str = "Wo sich die Felder treffen",
    dark_gray: str = DEFAULT_DARK_GRAY,
    deep: str = DEFAULT_DEEP,
    extra_color: str = "#5C8FA8",  # third-circle color — brand-neutral teal
) -> str:
    """Two- or three-circle Venn. Circles use brand colors at low opacity
    so overlaps appear darker (additive). Labels centred on each
    circle's lobe; intersection label centred at the overlap.
    """
    if len(labels) not in (2, 3):
        raise ValueError("venn_diagram requires exactly 2 or 3 labels")

    pad_x = 30
    diagram_top = 80
    diagram_h = h - diagram_top - 30
    cx_canvas = w / 2

    # Common circle radius
    r = min(diagram_h * 0.42, w * 0.20)
    parts: list[str] = []

    if len(labels) == 2:
        # Two circles side-by-side, overlapping by ~30% radius
        offset = r * 0.55
        c1_x = cx_canvas - offset
        c2_x = cx_canvas + offset
        cy = diagram_top + diagram_h / 2

        parts.append(
            f'<circle cx="{c1_x:.1f}" cy="{cy:.1f}" r="{r:.1f}" '
            f'fill="{primary}" fill-opacity="0.20" '
            f'stroke="{primary}" stroke-width="1.6"/>'
        )
        parts.append(
            f'<circle cx="{c2_x:.1f}" cy="{cy:.1f}" r="{r:.1f}" '
            f'fill="{accent}" fill-opacity="0.20" '
            f'stroke="{accent}" stroke-width="1.6"/>'
        )
        # Labels on lobe centres (away from overlap)
        parts.append(
            f'<text x="{c1_x - r * 0.55:.1f}" y="{cy + 5:.1f}" '
            f'text-anchor="middle" font-family="Inter, sans-serif" '
            f'font-weight="800" font-size="13" '
            f'fill="{primary}">{labels[0]}</text>'
        )
        parts.append(
            f'<text x="{c2_x + r * 0.55:.1f}" y="{cy + 5:.1f}" '
            f'text-anchor="middle" font-family="Inter, sans-serif" '
            f'font-weight="800" font-size="13" '
            f'fill="{accent}">{labels[1]}</text>'
        )
        # Intersection label in the centre
        int_size = _autofit_size(intersection_label, r * 0.9, "Inter-800",
                                 min_size=9, max_size=12)
        parts.append(
            f'<text x="{cx_canvas:.1f}" y="{cy + 5:.1f}" '
            f'text-anchor="middle" font-family="Inter, sans-serif" '
            f'font-weight="800" font-size="{int_size}" '
            f'fill="{primary}">{intersection_label}</text>'
        )

    else:  # 3 circles
        # Three circles arranged in a triangle, mutually overlapping
        offset_x = r * 0.55
        offset_y = r * 0.55
        cy_top = diagram_top + r * 0.85
        cy_bot = cy_top + offset_y * 1.6
        c1 = (cx_canvas, cy_top)
        c2 = (cx_canvas - offset_x, cy_bot)
        c3 = (cx_canvas + offset_x, cy_bot)
        colors = [primary, accent, extra_color]
        for (cx, cy), col in zip([c1, c2, c3], colors):
            parts.append(
                f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" '
                f'fill="{col}" fill-opacity="0.18" '
                f'stroke="{col}" stroke-width="1.6"/>'
            )
        # Lobe labels
        parts.append(
            f'<text x="{c1[0]:.1f}" y="{c1[1] - r * 0.7:.1f}" '
            f'text-anchor="middle" font-family="Inter, sans-serif" '
            f'font-weight="800" font-size="13" '
            f'fill="{colors[0]}">{labels[0]}</text>'
        )
        parts.append(
            f'<text x="{c2[0] - r * 0.6:.1f}" y="{c2[1] + r * 0.85:.1f}" '
            f'text-anchor="middle" font-family="Inter, sans-serif" '
            f'font-weight="800" font-size="13" '
            f'fill="{colors[1]}">{labels[1]}</text>'
        )
        parts.append(
            f'<text x="{c3[0] + r * 0.6:.1f}" y="{c3[1] + r * 0.85:.1f}" '
            f'text-anchor="middle" font-family="Inter, sans-serif" '
            f'font-weight="800" font-size="13" '
            f'fill="{colors[2]}">{labels[2]}</text>'
        )
        # Centroid for intersection
        cx_int = (c1[0] + c2[0] + c3[0]) / 3
        cy_int = (c1[1] + c2[1] + c3[1]) / 3
        int_size = _autofit_size(intersection_label, r * 0.7, "Inter-800",
                                 min_size=9, max_size=11)
        parts.append(
            f'<text x="{cx_int:.1f}" y="{cy_int + 4:.1f}" '
            f'text-anchor="middle" font-family="Inter, sans-serif" '
            f'font-weight="800" font-size="{int_size}" '
            f'fill="{primary}">{intersection_label}</text>'
        )

    return (
        f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
        f'xmlns="http://www.w3.org/2000/svg">'
        + _svg_header(w=w, kicker=kicker, title=title, pad_x=pad_x,
                      primary=primary, deep=deep, dark_gray=dark_gray)
        + "".join(parts) + '</svg>'
    )


# ─────────────────────────────────────────────────────────────────────────────
# Dispatcher — generate_components_for_report
# ─────────────────────────────────────────────────────────────────────────────


# Page-type → list-of-component-builders mapping. Each entry's builder
# is called with (page_data, primary, accent, neutral_light); it returns
# either a single SVG string or None to skip.
def _build_for_st06(
    data: dict, primary: str, accent: str, neutral_light: str,
) -> Optional[str]:
    steps = data.get("steps") or data.get("framework_steps") or []
    if not steps:
        return None
    norm = []
    for i, s in enumerate(steps):
        if isinstance(s, str):
            norm.append({"n": i + 1, "short": s})
        elif isinstance(s, dict):
            norm.append({
                "n": s.get("n", i + 1),
                "short": s.get("short", s.get("title", "")),
            })
    return process_flow(norm, primary=primary, accent=accent)


def _build_for_st09(
    data: dict, primary: str, accent: str, neutral_light: str,
) -> Optional[str]:
    # ST-09 may carry either a matrix payload or chart data
    if "quadrants" in data and "items" in data:
        return matrix_2x2(data, primary=primary, accent=accent)
    if "iceberg" in data:
        return metaphor_split(data["iceberg"], primary=primary, accent=accent,
                              neutral_light=neutral_light)
    if "bar_data" in data:
        return bar_chart(data["bar_data"], primary=primary, accent=accent)
    return None


def _build_for_st14(
    data: dict, primary: str, accent: str, neutral_light: str,
) -> Optional[str]:
    pills = data.get("pills") or data.get("causality_chain")
    if not pills:
        return None
    return causality_chain(list(pills), primary=primary, accent=accent)


def _build_for_st07a(
    data: dict, primary: str, accent: str, neutral_light: str,
) -> Optional[str]:
    stats = data.get("stats") or data.get("ergebnis_stats") or []
    if not stats:
        return None
    norm = []
    for s in stats:
        norm.append({
            "value": str(s.get("value", "")),
            "label": str(s.get("label", "")),
            "sub": str(s.get("sub", "")),
        })
    return stat_block(norm, primary=primary, accent=accent)


_GENERIC_CHART_BUILDERS = {
    "bar": lambda d, p, a, nl: bar_chart(d["bar_data"], primary=p, accent=a),
    "line": lambda d, p, a, nl: line_chart(
        d["line_data"]["series"], d["line_data"]["x_labels"],
        d["line_data"]["y_ticks"], primary=p, accent=a,
    ),
    "compare": lambda d, p, a, nl: compare_table(
        d["compare_data"]["rows"], tuple(d["compare_data"]["headers"]),
        primary=p, accent=a,
    ),
}


def _build_extras_for_any(
    data: dict, primary: str, accent: str, neutral_light: str,
) -> list[str]:
    """Pages of any type can carry chart payloads under explicit keys
    (`bar_data`, `line_data`, `compare_data`). Each present payload
    produces an extra component.
    """
    extras: list[str] = []
    if "bar_data" in data and isinstance(data["bar_data"], list):
        extras.append(_GENERIC_CHART_BUILDERS["bar"](data, primary, accent, neutral_light))
    if "line_data" in data and isinstance(data["line_data"], dict) \
            and "series" in data["line_data"]:
        extras.append(_GENERIC_CHART_BUILDERS["line"](data, primary, accent, neutral_light))
    if "compare_data" in data and isinstance(data["compare_data"], dict) \
            and "rows" in data["compare_data"]:
        extras.append(_GENERIC_CHART_BUILDERS["compare"](data, primary, accent, neutral_light))
    return extras


_ST_BUILDERS: dict[str, Any] = {
    "ST-06": _build_for_st06,
    "ST-09": _build_for_st09,
    "ST-14": _build_for_st14,
    "ST-07A": _build_for_st07a,
}


def _chart_theme(
    brand_primary: str, brand_accent: str, brand_neutral_light: str,
) -> ChartTheme:
    """Map the brand tokens already passed to Stage 6 onto a ChartTheme.

    primary/accent/paper come straight from the brand. `ink` reuses the
    brand primary (the deck's text colour is the primary in light-ground
    decks); `muted` is a fixed brand-neutral mid-grey for rules/labels
    (same provenance as the module's other DEFAULT_* greys — not a client
    literal). Brand-agnostic: colours flow from the params.
    """
    return ChartTheme(
        ink=brand_primary,
        paper=brand_neutral_light,
        primary=brand_primary,
        accent=brand_accent,
        muted=DEFAULT_DARK_GRAY,
        font_family="inherit",
    )


def _charts_for_slot(structured, slot: int) -> list:
    """The chart specs the structure_content stage extracted for `slot`
    (empty when no structured view is supplied or the page has none)."""
    if structured is None:
        return []
    for sp in getattr(structured, "pages", []):
        if getattr(sp, "slot", None) == slot:
            return list(getattr(sp, "charts", []) or [])
    return []


def generate_components_for_report(
    pages: list[Any],
    *,
    brand_primary: str,
    brand_accent: str,
    brand_neutral_light: str,
    structured: Any = None,
) -> dict[int, list[str]]:
    """Walk the page plan and emit SVG components per slot.

    Pages can be dicts or Pydantic ReportPage instances. Pages with no
    relevant payload are simply absent from the returned dict (no empty
    entries) — keeps the JSON response minimal.

    When `structured` (a StructuredContent from the structure_content stage)
    is supplied, each page's extracted chart specs are rendered to brand-
    themed SVGs (via `render_chart_svg`) and appended to that slot's
    components — deterministically, after the ST/extra components. Pages
    with no charts are unchanged, and omitting `structured` keeps the
    legacy behaviour (backward compatible).
    """
    theme = _chart_theme(brand_primary, brand_accent, brand_neutral_light)
    out: dict[int, list[str]] = {}
    for page in pages:
        slot, st_type, data = _unpack(page)
        components: list[str] = []
        if isinstance(data, dict):
            builder = _ST_BUILDERS.get(st_type)
            if builder is not None:
                svg = builder(data, brand_primary, brand_accent, brand_neutral_light)
                if svg:
                    components.append(svg)
            # Generic chart payloads can appear on any page type
            components.extend(_build_extras_for_any(
                data, brand_primary, brand_accent, brand_neutral_light,
            ))
        # Data-driven chart specs extracted by structure_content (Task 5).
        for spec in _charts_for_slot(structured, slot):
            components.append(render_chart_svg(spec, theme))
        if components:
            out[slot] = components
    return out


def _unpack(page: Any) -> tuple[int, str, Any]:
    """Normalise a page (dict or Pydantic ReportPage) to a tuple."""
    if isinstance(page, dict):
        return int(page["slot"]), str(page["type"]), page.get("data", {})
    # Pydantic-style attribute access
    return int(page.slot), str(page.type), page.data
