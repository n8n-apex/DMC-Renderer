"""Generic skeleton pattern — the R1 fallback for every not-yet-built ST type.

Renders, brand-styled, from whatever `data` is present:
  - a headline (first of title/headline/these/mechanismus/eyebrow, else
    the first string field),
  - an optional subtitle,
  - body prose (intro/body/text/lede/summary + any leftover string
    fields), via preprocess_body,
  - any list fields (list[str] -> bullets; list[dict] -> labelled blocks),
  - an optional full-bleed page background image (first asset whose
    image_type == "background"),
  - any inline SVG components attached to the page.

Never assumes specific keys; empty `data` -> a near-empty but valid page.
Emits NO head-level CSS (no @page/@font-face/:root) — that is the shared
head's job. CSS is scoped under `.st-generic`.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# Allow flat imports from the chassis package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from preprocess import preprocess_body  # noqa: E402
from patterns.base import PageFragment, RenderContext  # noqa: E402


_HEADLINE_KEYS = ("title", "headline", "these", "mechanismus", "eyebrow")
_SUBTITLE_KEYS = ("subtitle", "kicker")
_BODY_KEYS = ("intro", "body", "text", "lede", "summary",
              "kosten_des_nichtstuns")


def _esc(s: str) -> str:
    return (
        str(s).replace("&", "&amp;").replace("<", "&lt;")
        .replace(">", "&gt;").replace('"', "&quot;")
    )


def _first_str(data: dict, keys: tuple[str, ...]) -> tuple[str, str]:
    """Return (key, value) for the first present non-empty string key, else ('','')."""
    for k in keys:
        v = data.get(k)
        if isinstance(v, str) and v.strip():
            return k, v.strip()
    return "", ""


def _render_list(key: str, items: list) -> str:
    """list[str] -> <ul>; list[dict] -> labelled blocks. Returns '' if empty."""
    if not items:
        return ""
    if all(isinstance(it, str) for it in items):
        lis = "".join(f"<li>{_esc(it)}</li>" for it in items if str(it).strip())
        return f'<ul class="gen-list">{lis}</ul>' if lis else ""
    blocks: list[str] = []
    for it in items:
        if isinstance(it, dict):
            label = it.get("label") or it.get("title") or it.get("name") or ""
            value = it.get("value") or it.get("text") or it.get("body") or ""
            parts = []
            if label:
                parts.append(f'<div class="gen-block-label">{_esc(label)}</div>')
            if value:
                parts.append(preprocess_body(str(value)))
            if parts:
                blocks.append(f'<div class="gen-block">{"".join(parts)}</div>')
        elif isinstance(it, str) and it.strip():
            blocks.append(f'<div class="gen-block">{preprocess_body(it)}</div>')
    return "".join(blocks)


def render(page: dict, ctx: RenderContext) -> PageFragment:
    data: dict[str, Any] = page.get("data") or {}

    used: set[str] = set()
    head_key, headline = _first_str(data, _HEADLINE_KEYS)
    if not headline:
        # fall back to the first string field of any name
        for k, v in data.items():
            if isinstance(v, str) and v.strip():
                head_key, headline = k, v.strip()
                break
    if head_key:
        used.add(head_key)

    sub_key, subtitle = _first_str(data, _SUBTITLE_KEYS)
    if sub_key:
        used.add(sub_key)

    body_html_parts: list[str] = []
    for k in _BODY_KEYS:
        v = data.get(k)
        if isinstance(v, str) and v.strip():
            body_html_parts.append(preprocess_body(v))
            used.add(k)

    list_html_parts: list[str] = []
    for k, v in data.items():
        if k in used:
            continue
        if isinstance(v, list):
            rendered = _render_list(k, v)
            if rendered:
                list_html_parts.append(rendered)
                used.add(k)

    # Any leftover scalar string fields -> render so nothing is lost.
    leftover_parts: list[str] = []
    for k, v in data.items():
        if k in used:
            continue
        if isinstance(v, str) and v.strip():
            leftover_parts.append(preprocess_body(v))
            used.add(k)

    # Optional full-bleed background image (first asset of type background).
    # Painted directly on the .st-generic block via an inline style so the
    # background actually renders (an abspos inset:0 child does not paint).
    bg_style = ""
    for a in (page.get("assets") or []):
        if a.get("image_type") == "background" and a.get("path"):
            p = ctx.resolve_asset(a["path"])
            if p is not None:
                bg_style = f' style="background-image:url(\'{p.as_uri()}\')"'
            break

    # Inline any SVG components attached to this page.
    comp_html_parts: list[str] = []
    for comp_rel in (page.get("components") or []):
        svg = ctx.resolve_component(comp_rel)
        if svg:
            comp_html_parts.append(f'<div class="gen-component">{svg}</div>')

    headline_html = (
        f'<h1 class="gen-headline">{_esc(headline)}</h1>' if headline else ""
    )
    subtitle_html = (
        f'<p class="gen-subtitle">{_esc(subtitle)}</p>' if subtitle else ""
    )

    html = (
        f'<div class="st-generic"{bg_style}>'
        f'<div class="gen-content">'
        f'{headline_html}{subtitle_html}'
        f'{"".join(body_html_parts)}'
        f'{"".join(list_html_parts)}'
        f'{"".join(leftover_parts)}'
        f'{"".join(comp_html_parts)}'
        f'</div></div>'
    )

    css = """
.st-generic {
  position: relative; min-height: 232mm;
  background-size: cover; background-position: center;
}
.st-generic .gen-content { position: relative; z-index: 1; }
.gen-headline {
  font-family: var(--font-head); font-weight: 800;
  font-size: 26pt; color: var(--brand-primary);
  line-height: 1.12; letter-spacing: -0.01em; margin: 0 0 5mm 0;
}
.gen-subtitle {
  font-family: var(--font-body);
  font-style: italic; font-weight: 400; font-size: 12pt;
  color: var(--brand-primary); line-height: 1.4; margin: 0 0 6mm 0;
}
.st-generic .gen-content p {
  font-family: var(--font-body);
  font-weight: 400; font-size: 10pt; line-height: var(--density-lead, 1.5); color: var(--color-body);
  margin: 0 0 3mm 0; hyphens: auto; text-align: justify;
}
.st-generic .gen-content p strong {
  font-family: var(--font-body);
  font-weight: 700; color: var(--color-body);
}
.gen-list { margin: 0 0 5mm 0; padding-left: 5mm; }
.gen-list li {
  font-family: var(--font-body);
  font-size: 10pt; line-height: var(--density-lead, 1.45); color: var(--color-body); margin: 0 0 1.5mm 0;
}
.gen-block { margin: 0 0 4mm 0; }
.gen-block-label {
  font-family: var(--font-head); font-weight: 700; font-size: 9.5pt;
  color: var(--brand-primary); letter-spacing: 0.02em; margin: 0 0 1.5mm 0;
}
.gen-component { margin: 4mm 0; }
"""
    return PageFragment(html=html, css=css)
