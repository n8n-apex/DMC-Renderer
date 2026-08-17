"""DMC composition-family components for compatible registry versions."""

from __future__ import annotations

from typing import Any

from families.anatomy import anatomy_role, element_anatomy_class
from families.base import render_element


FAMILY_IDS = (
    "editorial_lead",
    "false_belief_stack",
    "case_narrative",
    "theory_interpretation",
    "mechanism_spread",
    "summary_synthesis",
    "objection_response",
    "collaboration_pathway",
    "evidence_wall",
    "closing_cta",
)


def _render_regions(
    fragment: Any,
    bundle: Any,
    face_id: str,
    family_id: str,
) -> list[str]:
    prefix = f"{face_id}."
    face_elements = tuple(
        element
        for element in fragment.elements
        if element.element_id.startswith(prefix)
    )
    regions: list[str] = []
    region_order = tuple(
        assignment.region_id for assignment in fragment.region_assignments
    )
    for region_id in region_order:
        elements = tuple(
            element for element in face_elements if element.region_id == region_id
        )
        if not elements:
            continue
        rendered_parts: list[str] = []
        for element in elements:
            markup = render_element(
                element,
                content_by_ref=bundle.content_by_ref,
                claim_values=bundle.claim_values,
                asset_paths=bundle.asset_paths,
                # The SVG component generators compute tints arithmetically,
                # so they need real hex, not a CSS custom property.
                brand_primary=bundle.brand_tokens.get("brand_primary"),
                brand_accent=bundle.brand_accent
                or bundle.brand_tokens.get("brand_accent"),
            )
            extra_class = element_anatomy_class(family_id, element)
            if extra_class:
                markup = markup.replace('class="el ', f'class="el {extra_class} ', 1)
            rendered_parts.append(markup)
        role = anatomy_role(family_id, region_id)
        regions.append(
            f'<section class="region region-{region_id} anatomy-{role}" '
            f'data-region-id="{region_id}" data-anatomy-role="{role}">'
            f'{"".join(rendered_parts)}</section>'
        )
    return regions


def render_dmc_family(
    fragment: Any,
    bundle: Any,
    *,
    rendered_family_id: str | None = None,
) -> str:
    family_id = rendered_family_id or fragment.composition.family_id
    # A spread's halves may carry different compositions; each face is drawn
    # with its own family so a case can face its theory on one sheet.
    face_compositions = getattr(fragment, "face_compositions", ()) or ()
    face_markup: list[str] = []
    for index, face_id in enumerate(fragment.face_ids):
        face_family_id = family_id
        variant_id = fragment.composition.variant_id
        if rendered_family_id is None and index < len(face_compositions):
            face_family_id = face_compositions[index].family_id
            variant_id = face_compositions[index].variant_id
        regions = _render_regions(fragment, bundle, face_id, face_family_id)
        # The ground is a layer under the regions, not a region element, so
        # it is painted as the face's own background rather than placed.
        grounds = getattr(fragment, "face_grounds", ()) or ()
        ground_id = grounds[index] if index < len(grounds) else ""
        ground_style = ""
        if ground_id and ground_id in bundle.asset_paths:
            from pathlib import Path as _Path

            uri = _Path(bundle.asset_paths[ground_id]).resolve().as_uri()
            ground_style = (
                f' style="background-image:url({uri});background-size:cover;'
                f'background-position:center"'
            )
        face_markup.append(
            f'<article class="face anatomy-face"{ground_style} data-face-id="{face_id}" '
            f'data-family-id="{face_family_id}" data-variant-id="{variant_id}" '
            f'data-anatomy="{face_family_id}">'
            f'{"".join(regions)}</article>'
        )
    return (
        f'<section class="fragment {fragment.format}" '
        f'data-fragment-id="{fragment.fragment_id}" '
        f'data-family-id="{family_id}" '
        f'data-family-version="{fragment.composition.family_version}" '
        f'data-variant-id="{fragment.composition.variant_id}" '
        f'data-anatomy="{family_id}">'
        f'{"".join(face_markup)}</section>'
    )


def render_case_narrative(
    fragment: Any,
    bundle: Any,
    *,
    rendered_family_id: str | None = None,
) -> str:
    """Case narrative vertical slice: identity, before/turn/after, proof, result.

    The story column carries the client identity and the narrative turn; the
    evidence rail carries the proof devices and the result figure. Region and
    element anatomy classes let the family stylesheet draw the case as a
    labelled transformation instead of a generic text column.
    """
    return render_dmc_family(
        fragment,
        bundle,
        rendered_family_id=rendered_family_id or "case_narrative",
    )
