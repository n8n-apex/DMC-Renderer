"""ST-07A via the reference-derived LayoutTemplate (Phase 4, Task 5).

Binds the niklas case-study template's regions to the apex case-study page data
through the existing macros, then places them with the template-driven engine.
``_calibrate_template`` makes the v1 extracted template robust to variable
content: it collapses the repeated kicker+body frames into ONE flowing narrative
column (so apex's copy never clips) and adds the dark authority RAIL panel the
extraction missed. Behind the ``TEMPLATE_DRIVEN_ST07A`` flag (A/B on pixels
before any swap). Brand-agnostic: pulls only from page data + tokens.
"""
from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from layout_template import LayoutTemplate, Region  # noqa: E402
from patterns._template_driven import render_from_template, render_macro  # noqa: E402
from patterns.base import PageFragment, RenderContext  # noqa: E402
from patterns.st_07a import _KICKER_BASE, _SECTION_SPEC  # noqa: E402
from preprocess import preprocess_body  # noqa: E402

_TEMPLATE_PATH = (
    Path(__file__).resolve().parent.parent
    / "layout_templates" / "ST-07A" / "case-study-split-stat-rail.json"
)

# Region-content styling (scoped; tokens only — no client literals). The rail
# content sits on the dark panel so it is on-dark (white) with sparing accent.
_EXTRA_CSS = """
.tpl-region--panel { background: var(--color-ink); }
.tpl-region--body { overflow: visible; }
.tpl-sec { margin: 0 0 5mm 0; }
.tpl-sec .cs-body { font-family: var(--font-body); font-size: var(--type-body);
  line-height: 1.5; color: var(--color-body); margin-top: 2mm; }
.tpl-region--lede, .tpl-region--stat, .tpl-region--portrait { padding: 0 5mm; }
.tpl-kunde-name { font-family: var(--font-head); font-weight: 700; color: var(--color-on-dark); }
.tpl-kunde-role { font-size: var(--type-label); color: var(--color-on-dark); opacity: 0.72; }
.tpl-kunde-url  { font-size: var(--type-label);
  color: color-mix(in srgb, var(--color-accent) 55%, var(--color-on-dark)); }
.tpl-stat { border-top: 0.3mm solid color-mix(in srgb, var(--color-accent) 70%, transparent);
  padding-top: 2mm; }
.tpl-stat-v { font-family: var(--font-head); font-weight: 800; font-size: var(--type-display);
  letter-spacing: -0.01em; color: var(--color-on-dark); line-height: 1.0; }
.tpl-stat-l { font-family: var(--font-head); font-size: var(--type-label);
  text-transform: uppercase; letter-spacing: 0.04em; color: var(--color-on-dark);
  opacity: 0.78; margin-top: 1mm; }
""".strip()

_RAIL_ROLES = ("portrait", "lede", "stat")
_NARR_ROLES = ("kicker", "body")


def _calibrate_template(tpl: LayoutTemplate) -> LayoutTemplate:
    """Make the v1 extracted template robust to variable content + add the rail.

    (1) Collapse the repeated kicker+body frames into ONE flowing 'body' region
        (their bounding box) so longer/shorter copy flows instead of clipping.
    (2) Add a dark 'panel' region (full height, spanning the right column) BEHIND
        the portrait/lede/stat content — the authority rail the extraction missed.
    """
    regions = list(tpl.regions)
    narr = [r for r in regions if r.role in _NARR_ROLES]
    rail = [r for r in regions if r.role in _RAIL_ROLES]
    keep = [r for r in regions if r.role not in _NARR_ROLES]

    new: list[Region] = []
    if rail:
        rx = max(0.0, min(r.x for r in rail) - 0.02)
        new.append(Region(role="panel", x=rx, y=0.0, w=round(1.0 - rx, 4), h=1.0, z=0))
    for r in keep:  # lift rail content above the panel
        z = max(r.z, 1) if r.role in _RAIL_ROLES else r.z
        new.append(replace(r, z=z))
    if narr:
        x0, y0 = min(r.x for r in narr), min(r.y for r in narr)
        x1 = max(r.x + r.w for r in narr)
        y1 = max(r.y + r.h for r in narr)
        new.append(Region(role="body", x=x0, y=y0,
                          w=round(x1 - x0, 4), h=round(y1 - y0, 4), z=2))

    return replace(tpl, regions=tuple(new))


def _sections(d: dict) -> list[dict]:
    out: list[dict] = []
    for heading, key in _SECTION_SPEC:
        body = (d.get(key) or "").strip()
        if body:
            out.append({"heading": heading, "body_html": preprocess_body(body)})
    return out


def st07a_region_renderer(page: dict, ctx: RenderContext):
    """Return ``render_region(region, index)`` binding roles to apex data."""
    d = page.get("data", page)
    num = d.get("fallstudie_number", "")
    kicker_label = f"{_KICKER_BASE} 0{num}" if num else _KICKER_BASE
    headline = d.get("ergebnis_headline", "")
    sections = _sections(d)
    metrics = [m for m in (d.get("ergebnis_metrics") or []) if isinstance(m, dict)]
    kunde = d.get("kunde") or {}
    kunde_url = kunde.get("company_url", "") or getattr(ctx.brand, "company_url_display", "")
    pull = d.get("pullquote") or {}
    portrait_uri = ctx.slot_uri(page, "case_study_portrait")
    counters: dict[str, int] = {}

    def _nth(role: str, seq: list):
        i = counters.get(role, 0)
        counters[role] = i + 1
        return seq[i] if i < len(seq) else None

    def render_region(r: Region, index: int) -> Optional[str]:
        role = r.role
        if role == "panel":
            return "<div></div>"  # background fill only (CSS paints it)
        if role == "eyebrow":
            return render_macro("pill.jinja", "pill", label=kicker_label, variant="solid")
        if role == "ghost_numeral":
            return render_macro("ghost_numeral.jinja", "ghost_numeral", n=num) if num else None
        if role == "headline":
            return (render_macro("two_tone_headline.jinja", "two_tone_headline",
                                 lead=headline) if headline else None)
        if role == "body":  # the merged narrative column: ALL section pairs, flowing
            if not sections:
                return None
            blocks = []
            for s in sections:
                lbl = render_macro("section_label.jinja", "section_label", text=s["heading"])
                blocks.append(
                    f'<div class="tpl-sec">{lbl}'
                    f'<div class="cs-body">{s["body_html"]}</div></div>'
                )
            return "".join(blocks)
        if role == "kicker":  # fallback (calibrated template has none)
            s = _nth("kicker", sections)
            return render_macro("section_label.jinja", "section_label", text=s["heading"]) if s else None
        if role == "portrait":
            return (render_macro("media_figure.jinja", "media_figure",
                                 src=portrait_uri, ratio="4x5", frame=True)
                    if portrait_uri else None)
        if role == "lede":
            name, fn = kunde.get("name", ""), kunde.get("funktion", "")
            if not (name or kunde_url):
                return None
            html = ""
            if name:
                html += f'<div class="tpl-kunde-name">{name}</div>'
            if fn:
                html += f'<div class="tpl-kunde-role">{fn}</div>'
            if kunde_url:
                html += f'<div class="tpl-kunde-url">{kunde_url}</div>'
            return html
        if role == "stat":
            m = _nth("stat", metrics)
            if not m:
                return None
            return (f'<div class="tpl-stat"><div class="tpl-stat-v">{m.get("value", "")}</div>'
                    f'<div class="tpl-stat-l">{m.get("label", "")}</div></div>')
        if role == "quote":
            return (render_macro("pull_quote.jinja", "pull_quote",
                                 text=pull.get("text", ""),
                                 attribution=pull.get("attribution", ""),
                                 on_panel=True) if pull.get("text") else None)
        if role == "footer":
            return kunde_url or getattr(ctx.brand, "company_name_short", "") or None
        return None

    return render_region


def render(page: dict, ctx: RenderContext) -> PageFragment:
    raw = LayoutTemplate.from_dict(json.loads(_TEMPLATE_PATH.read_text(encoding="utf-8")))
    tpl = _calibrate_template(raw)
    frag = render_from_template(tpl, render_region=st07a_region_renderer(page, ctx))
    return PageFragment(html=frag.html, css=frag.css + "\n" + _EXTRA_CSS)
