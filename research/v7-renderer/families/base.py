"""Typed element adapters shared by v3 composition families."""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any, Mapping


def _attrs(element: Any) -> str:
    attributes = {
        "data-element-id": element.element_id,
        "data-region-id": element.region_id,
        "data-required-visibility": str(element.required_visibility).lower(),
    }
    content_ref = getattr(element, "content_ref", None)
    if content_ref:
        attributes["data-content-ref"] = content_ref
    claim_id = getattr(element, "claim_id", None)
    if claim_id:
        attributes["data-claim-id"] = claim_id
    asset_id = getattr(element, "asset_id", None)
    if asset_id:
        attributes["data-asset-id"] = asset_id
    return " ".join(
        f'{name}="{escape(str(value), quote=True)}"'
        for name, value in attributes.items()
    )


def _text(content_by_ref: Mapping[str, str], content_ref: str) -> str:
    if content_ref not in content_by_ref:
        raise KeyError(f"missing content reference {content_ref}")
    return escape(content_by_ref[content_ref])


def render_element(
    element: Any,
    *,
    content_by_ref: Mapping[str, str],
    claim_values: Mapping[str, str],
    asset_paths: Mapping[str, str],
    brand_primary: str | None = None,
    brand_accent: str | None = None,
) -> str:
    attrs = _attrs(element)
    kind = element.kind
    if kind == "heading":
        tag = f"h{element.level}"
        headline = _accented_headline(_text(content_by_ref, element.content_ref))
        return f'<{tag} class="el heading" {attrs}>{headline}</{tag}>'
    if kind == "body":
        return f'<p class="el body" {attrs}>{_text(content_by_ref, element.content_ref)}</p>'
    if kind == "quote":
        value = _text(content_by_ref, element.content_ref)
        return f'<blockquote class="el quote" {attrs}>{value}</blockquote>'
    if kind == "stat":
        if element.claim_id not in claim_values:
            raise KeyError(f"missing claim value {element.claim_id}")
        value = escape(claim_values[element.claim_id])
        caption = ""
        if element.label_content_ref:
            caption = (
                f"<figcaption>{_text(content_by_ref, element.label_content_ref)}"
                "</figcaption>"
            )
        return f'<figure class="el stat" {attrs}><strong>{value}</strong>{caption}</figure>'
    if kind == "comparison":
        left = "".join(
            f"<li>{_text(content_by_ref, ref)}</li>" for ref in element.left_content_refs
        )
        right = "".join(
            f"<li>{_text(content_by_ref, ref)}</li>" for ref in element.right_content_refs
        )
        claim_attr = escape(" ".join(element.claim_ids), quote=True)
        return f'<div class="el comparison" {attrs} data-claim-ids="{claim_attr}"><ul>{left}</ul><ul>{right}</ul></div>'
    if kind == "process":
        claim_attr = escape(" ".join(element.claim_ids), quote=True)
        # A region that carries an ordered process but no prose exists to
        # hold ONE drawn structure. The component library builds those and
        # v3 has never called it, which is why they rendered as bullets.
        if element.region_id in _device_only_regions():
            from families import component_bridge

            drawn = component_bridge.render(
                element,
                content_by_ref=content_by_ref,
                claim_values=claim_values,
                primary=brand_primary or component_bridge.DEFAULT_PRIMARY,
                accent=brand_accent or component_bridge.DEFAULT_ACCENT,
            )
            if drawn:
                return (
                    f'<div class="el device device-process device-svg" {attrs} '
                    f'data-claim-ids="{claim_attr}">{drawn}</div>'
                )
        items = "".join(
            f"<li>{_text(content_by_ref, ref)}</li>" for ref in element.item_content_refs
        )
        return f'<ol class="el process" {attrs} data-claim-ids="{claim_attr}">{items}</ol>'
    if kind in {"image", "qr"}:
        if element.asset_id not in asset_paths:
            raise KeyError(f"missing asset path {element.asset_id}")
        source = Path(asset_paths[element.asset_id]).resolve().as_uri()
        ref = (
            element.alt_content_ref
            if kind == "image"
            else element.destination_content_ref
        )
        alt = _text(content_by_ref, ref)
        css_class = "image" if kind == "image" else "qr"
        if kind == "qr":
            # A QR code must never be cropped off-centre; it is a machine
            # target, not a picture with a subject.
            return (
                f'<img class="el {css_class}" {attrs} '
                f'src="{escape(source, quote=True)}" alt="{alt}">'
            )
        # A slot is rarely the shape of the photograph filling it. Anchoring
        # the crop on the measured subject is what stops a face being cut
        # off; `object-fit: cover` alone just keeps the middle and hopes.
        from families.focal_point import object_position

        position = object_position(asset_paths[element.asset_id])
        return (
            f'<img class="el {css_class}" {attrs} '
            f'src="{escape(source, quote=True)}" alt="{alt}" '
            f'style="object-position:{position}" data-focal="{position}">'
        )
    if kind == "source":
        label = _text(content_by_ref, element.content_ref)
        return f'<cite class="el source" {attrs}>{label}</cite>'
    if kind == "divider":
        return f'<hr class="el divider" {attrs}>'
    if kind == "group":
        children = escape(" ".join(element.child_element_ids), quote=True)
        return f'<div class="el group" {attrs} data-child-element-ids="{children}"></div>'
    if kind in {
        "grouped_comparison",
        "formula_ladder",
        "time_series",
        "share",
        "distribution",
        "composition_breakdown",
    }:
        return _render_library_device(
            element,
            attrs,
            content_by_ref=content_by_ref,
            claim_values=claim_values,
        )
    if kind == "evidence_gallery":
        cells = []
        for index, asset_id in enumerate(element.asset_ids):
            if asset_id not in asset_paths:
                raise KeyError(f"missing asset path {asset_id}")
            source = Path(asset_paths[asset_id]).resolve().as_uri()
            caption_ref = element.caption_content_refs[
                min(index, len(element.caption_content_refs) - 1)
            ]
            caption = _text(content_by_ref, caption_ref)
            cells.append(
                f'<figure class="gallery-cell" data-asset-id="{escape(asset_id, quote=True)}">'
                f'<img src="{escape(source, quote=True)}" alt="{caption}">'
                f"<figcaption>{caption}</figcaption></figure>"
            )
        return f'<div class="el evidence-gallery" {attrs}>{"".join(cells)}</div>'
    if kind == "logo_wall":
        label = _text(content_by_ref, element.label_content_ref)
        cells = []
        for asset_id in element.asset_ids:
            if asset_id not in asset_paths:
                raise KeyError(f"missing asset path {asset_id}")
            source = Path(asset_paths[asset_id]).resolve().as_uri()
            cells.append(
                f'<img class="logo-cell" data-asset-id="{escape(asset_id, quote=True)}" '
                f'src="{escape(source, quote=True)}" alt="{label}">'
            )
        return (
            f'<div class="el logo-wall" {attrs}>'
            f'<span class="wall-label">{label}</span>{"".join(cells)}</div>'
        )
    if kind == "proof_wall":
        claim_attr = escape(" ".join(element.claim_ids), quote=True)
        cells = "".join(
            f'<blockquote class="proof-cell">{_text(content_by_ref, ref)}</blockquote>'
            for ref in element.quote_content_refs
        )
        return (
            f'<div class="el proof-wall" {attrs} data-claim-ids="{claim_attr}">'
            f"{cells}</div>"
        )
    raise ValueError(f"unsupported typed element {kind}")


def _claim_value(claim_values: Mapping[str, str], claim_id: str) -> str:
    if claim_id not in claim_values:
        raise KeyError(f"missing claim value {claim_id}")
    return claim_values[claim_id]


def _magnitude(value: str) -> float | None:
    """Parse a leading numeral (German or dot decimals) for bar scaling only.

    The printed value is always the exact claim text; the parsed magnitude
    only sizes the bar, so a failed parse degrades to equal bars rather than
    inventing a number.
    """
    import re

    match = re.match(r"^[+-]?\d[\d.,]*", str(value).strip())
    if not match:
        return None
    lexeme = match.group(0)
    if lexeme.count(",") == 1 and lexeme.count(".") == 0:
        lexeme = lexeme.replace(",", ".")
    elif lexeme.count(".") > 1 or (lexeme.count(".") == 1 and lexeme.count(",") == 1):
        lexeme = lexeme.replace(".", "").replace(",", ".")
    try:
        return abs(float(lexeme))
    except ValueError:
        return None


def _bar_rows(
    claim_ids: tuple[str, ...],
    claim_values: Mapping[str, str],
    *,
    emphasize_last: bool = False,
) -> str:
    values = [_claim_value(claim_values, claim_id) for claim_id in claim_ids]
    magnitudes = [_magnitude(value) for value in values]
    known = [magnitude for magnitude in magnitudes if magnitude is not None]
    peak = max(known) if known else 1.0
    rows = []
    for index, (claim_id, value, magnitude) in enumerate(
        zip(claim_ids, values, magnitudes)
    ):
        share = (magnitude / peak * 100) if magnitude is not None and peak > 0 else 100
        emphasis = " bar-result" if emphasize_last and index == len(claim_ids) - 1 else ""
        rows.append(
            f'<div class="bar-row{emphasis}" data-claim-id="{escape(claim_id, quote=True)}">'
            f'<span class="bar" style="width: {share:.1f}%"></span>'
            f'<span class="bar-value">{escape(value)}</span></div>'
        )
    return "".join(rows)


def _render_library_device(
    element: Any,
    attrs: str,
    *,
    content_by_ref: Mapping[str, str],
    claim_values: Mapping[str, str],
) -> str:
    """Draw an evidence device with the designed preset library.

    v3 owns WHICH device a claim shape earns; the v2 preset library owns HOW
    that device looks. The wrapper keeps the element's contract attributes on
    the outside so materialization and evidence gates still see one element.
    """
    from families import chart_bridge, viz_bridge

    kind = element.kind
    # The SVG chart renderers draw a framed, labelled chart with axes; the CSS
    # presets draw a compact block. For the kinds where SVG is genuinely
    # richer, it wins; anything it cannot ground falls back rather than
    # dropping the device.
    if kind in _SVG_PREFERRED_KINDS:
        drawn = chart_bridge.render(
            element, content_by_ref=content_by_ref, claim_values=claim_values
        )
        if drawn:
            from contracts_v3.render_contract import element_claim_refs

            claim_ids = " ".join(element_claim_refs(element))
            css_kind = kind.replace("_", "-")
            return (
                f'<div class="el device device-{css_kind} device-svg" {attrs} '
                f'data-claim-ids="{escape(claim_ids, quote=True)}">{drawn}</div>'
            )

    if kind == "grouped_comparison":
        spec = viz_bridge.grouped_comparison_spec(
            element, content_by_ref=content_by_ref, claim_values=claim_values
        )
    elif kind == "formula_ladder":
        spec = viz_bridge.formula_ladder_spec(
            element, content_by_ref=content_by_ref, claim_values=claim_values
        )
    elif kind == "time_series":
        spec = viz_bridge.series_spec(
            element,
            element.point_claim_ids,
            content_by_ref=content_by_ref,
            claim_values=claim_values,
        )
    elif kind == "share":
        spec = viz_bridge.share_spec(
            element, content_by_ref=content_by_ref, claim_values=claim_values
        )
    elif kind == "distribution":
        spec = viz_bridge.proportion_spec(
            element,
            element.segment_claim_ids,
            content_by_ref=content_by_ref,
            claim_values=claim_values,
        )
    else:
        spec = viz_bridge.proportion_spec(
            element,
            element.part_claim_ids,
            content_by_ref=content_by_ref,
            claim_values=claim_values,
        )

    drawn = viz_bridge.render_preset(spec)
    if not drawn:
        raise ValueError(
            f"preset library could not draw {kind} for {element.element_id}"
        )
    css_kind = kind.replace("_", "-")
    # Evidence traceability survives the handoff: the library draws the device,
    # the wrapper keeps every claim the device prints addressable in the DOM.
    from contracts_v3.render_contract import element_claim_refs

    claim_ids = " ".join(element_claim_refs(element))
    return (
        f'<div class="el device device-{css_kind}" {attrs} '
        f'data-claim-ids="{escape(claim_ids, quote=True)}">{drawn}</div>'
    )


_DEVICE_ONLY_REGIONS: frozenset[str] | None = None


def _device_only_regions() -> frozenset[str]:
    """Region ids that accept an ordered process but carry no prose.

    Read from the composition registry rather than hard coded, so a region
    that gains or loses `body` changes how its process is drawn without an
    edit here.
    """
    global _DEVICE_ONLY_REGIONS
    if _DEVICE_ONLY_REGIONS is not None:
        return _DEVICE_ONLY_REGIONS
    import json

    path = (
        Path(__file__).resolve().parents[2]
        / "composition_registry"
        / "families"
        / "dmc-v1.json"
    )
    found: set[str] = set()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        _DEVICE_ONLY_REGIONS = frozenset()
        return _DEVICE_ONLY_REGIONS
    for family in raw.get("families", ()):
        for region in family.get("regions", ()):
            kinds = set(region.get("allowed_element_kinds", ()))
            if "process" in kinds and "body" not in kinds:
                found.add(region["region_id"])
    _DEVICE_ONLY_REGIONS = frozenset(found)
    return _DEVICE_ONLY_REGIONS


# Kinds the SVG renderers draw better than the CSS presets. `formula_ladder`
# and money breakdowns have NO CSS equivalent at all, which is why the cost
# pages had nothing to draw with.
# Measured, not assumed: the CSS ba_bars draws a heavier, better before/after
# than the SVG (it carries the delta chip and fills the rail), and the CSS
# donut and column chart likewise. SVG wins ONLY where CSS has no equivalent
# at all: a calculation ladder, and a breakdown denominated in money, which a
# 100-percent stacked bar cannot express.
_SVG_PREFERRED_KINDS = frozenset(
    {
        "formula_ladder",
        "distribution",
        "composition_breakdown",
    }
)


def _accented_headline(text: str) -> str:
    """Mark the headline's final phrase so a profile can colour it.

    `richard-grammar-v2.md` axis HC names four headline constructions and
    three of them (accent_word, two_tone_two_weight, tonal_accent_word)
    colour or weight ONE part of the line. CSS cannot select "the last
    word", so the markup always carries the span and the axis attribute on
    the body decides whether it is styled. Under single_colour the span is
    inert, so this is safe for every profile.

    The final phrase, not the final word: German headlines end on a
    separable verb or a short noun that reads as one unit ("...dann teuer",
    "...unklar ist"), and colouring a single stranded word looks like a
    mistake rather than a decision.
    """
    stripped = text.rstrip()
    trailing = text[len(stripped):]
    if not stripped:
        return escape(text)
    words = stripped.split(" ")
    if len(words) < 4:
        # A short line is accented whole; splitting three words looks broken.
        return escape(text)
    tail_length = 2 if len(words) >= 7 else 1
    head = " ".join(words[:-tail_length])
    tail = " ".join(words[-tail_length:])
    return (
        f"{escape(head)} "
        f'<span class="hl-accent">{escape(tail)}</span>{escape(trailing)}'
    )
