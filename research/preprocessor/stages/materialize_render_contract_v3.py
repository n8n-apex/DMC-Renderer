"""Materialize a frozen v3 render contract from approved semantic decisions."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from typing import Literal

from composition_registry.schema import CompositionFamily, CompositionRegistry, RegionSpec
from contracts_v3.asset_ledger import AssetLedger, SemanticAssetClass
from contracts_v3.render_contract import (
    BodyElement,
    CompositionBreakdownElement,
    DistributionElement,
    EvidenceGalleryElement,
    ComparisonElement,
    CompositionAssignment,
    ExpectedMaterialization,
    FrozenRenderContractV3,
    GroupedComparisonElement,
    FormulaLadderElement,
    HeadingElement,
    ImageElement,
    ProcessElement,
    QrElement,
    RegionAssignment,
    LogoWallElement,
    ProofWallElement,
    QuoteElement,
    RenderFragmentV3,
    SourceElement,
    StatElement,
    ShareElement,
    TimeSeriesElement,
    element_claim_refs,
)
from contracts_v3.report_plan import FacePlan, ReportPlanV3
from contracts_v3.source_ledger import SourceLedger
from stages.plan_compositions_v3 import (
    CompositionPlanV3,
    FaceCompositionFacts,
    SelectedComposition,
)


_NUMBER_RE = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)?%?")


class ContractMaterializationFailure(ValueError):
    def __init__(
        self,
        *,
        code: str,
        detail: str,
        face_ids: tuple[str, ...],
        element_ids: tuple[str, ...] = (),
    ) -> None:
        self.owner_stage = "contract_materializer"
        self.code = code
        self.detail = detail
        self.face_ids = face_ids
        self.element_ids = element_ids
        super().__init__(f"{code}: {detail}")


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _family(
    registry: CompositionRegistry,
    selected: SelectedComposition,
) -> CompositionFamily:
    matches = tuple(
        family
        for family in registry.families
        if family.family_id == selected.family_id
        and family.version == selected.family_version
    )
    if len(matches) != 1:
        raise ContractMaterializationFailure(
            code="selected_family_not_registered",
            detail=f"{selected.family_id}@{selected.family_version} is not registered",
            face_ids=(),
        )
    family = matches[0]
    if selected.variant_id not in {variant.variant_id for variant in family.variants}:
        raise ContractMaterializationFailure(
            code="selected_variant_not_registered",
            detail=f"{selected.variant_id} is not registered for {family.family_id}",
            face_ids=(),
        )
    return family


def _minimum_font(region: RegionSpec, language: str) -> float:
    return next(
        capacity.min_font_pt
        for capacity in region.capacities
        if capacity.language == language
    )


_EXEMPTION_SHAPES = {
    "year": re.compile(r"^(1[89]|20)\d{2}$"),
    "ordered_list_label": re.compile(r"^\d{1,2}$"),
    "page_number": re.compile(r"^\d{1,3}$"),
}


def _validate_numeric_grounding(
    face: FacePlan,
    facts: FaceCompositionFacts,
    source_ledger: SourceLedger,
) -> None:
    for content_ref, semantic in facts.numeric_exemptions.items():
        text = facts.content_by_ref.get(content_ref, "")
        tokens = _NUMBER_RE.findall(text)
        shape = _EXEMPTION_SHAPES[semantic]
        if not tokens or not all(shape.fullmatch(token) for token in tokens):
            raise ContractMaterializationFailure(
                code="numeric_exemption_mismatch",
                detail=(
                    f"{content_ref} is exempted as {semantic} but its numeric "
                    "tokens do not match that shape"
                ),
                face_ids=(face.face_id,),
            )
    numeric_refs = tuple(
        content_ref
        for content_ref, text in facts.content_by_ref.items()
        if _NUMBER_RE.search(text)
        and content_ref not in facts.numeric_exemptions
    )
    if not numeric_refs:
        return
    known_claims = {claim.claim_id for claim in source_ledger.claims}
    if not face.claim_ids or not set(face.claim_ids) <= known_claims:
        raise ContractMaterializationFailure(
            code="numeric_content_without_claim",
            detail=f"numeric content has no declared claim: {', '.join(numeric_refs)}",
            face_ids=(face.face_id,),
        )


def _add_content_elements(
    *,
    face: FacePlan,
    region: RegionSpec,
    content_refs: tuple[str, ...],
) -> list[object]:
    allowed = set(region.allowed_element_kinds)
    elements: list[object] = []
    cursor = 0
    if "heading" in allowed and content_refs:
        elements.append(
            HeadingElement(
                element_id=f"{face.face_id}.{region.region_id}.heading.01",
                region_id=region.region_id,
                content_ref=content_refs[0],
                level=2,
                required_visibility=True,
            )
        )
        cursor = 1

    remaining = content_refs[cursor:]
    # A region's declared purpose beats the prose default. Without this the
    # family's own name ("false_belief_stack") and the client's card
    # treatment axis are both ignored and the page renders as paragraphs.
    preferred = getattr(region, "preferred_element_kind", None)
    if preferred == "process" and "process" in allowed and remaining:
        elements.append(
            ProcessElement(
                element_id=f"{face.face_id}.{region.region_id}.process.01",
                region_id=region.region_id,
                item_content_refs=remaining,
                claim_ids=face.claim_ids,
                required_visibility=True,
            )
        )
    elif "body" in allowed:
        for index, content_ref in enumerate(remaining, start=1):
            elements.append(
                BodyElement(
                    element_id=f"{face.face_id}.{region.region_id}.body.{index:02d}",
                    region_id=region.region_id,
                    content_ref=content_ref,
                    required_visibility=True,
                )
            )
    elif "process" in allowed and remaining:
        elements.append(
            ProcessElement(
                element_id=f"{face.face_id}.{region.region_id}.process.01",
                region_id=region.region_id,
                item_content_refs=remaining,
                claim_ids=face.claim_ids,
                required_visibility=True,
            )
        )
    elif "comparison" in allowed and len(remaining) >= 2:
        split_at = max(1, len(remaining) // 2)
        elements.append(
            ComparisonElement(
                element_id=f"{face.face_id}.{region.region_id}.comparison.01",
                region_id=region.region_id,
                left_content_refs=remaining[:split_at],
                right_content_refs=remaining[split_at:],
                claim_ids=face.claim_ids,
                required_visibility=True,
            )
        )
    elif not elements and "process" in allowed and content_refs:
        elements.append(
            ProcessElement(
                element_id=f"{face.face_id}.{region.region_id}.process.01",
                region_id=region.region_id,
                item_content_refs=content_refs,
                claim_ids=face.claim_ids,
                required_visibility=True,
            )
        )
    elif not elements and "comparison" in allowed and len(content_refs) >= 2:
        elements.append(
            ComparisonElement(
                element_id=f"{face.face_id}.{region.region_id}.comparison.01",
                region_id=region.region_id,
                left_content_refs=(content_refs[0],),
                right_content_refs=content_refs[1:],
                claim_ids=face.claim_ids,
                required_visibility=True,
            )
        )
    return elements


def _viz_region(
    family: CompositionFamily,
    facts: FaceCompositionFacts,
    kind: str,
):
    """Place a data device in the WIDEST region that allows it.

    A chart in a narrow rail overflows its column: its numerals are display
    scale and its marks need horizontal room. Region width is declared in the
    registry, so the placement rule is measurable rather than a CSS patch.
    """
    candidates = [
        region
        for region in family.regions
        if kind in region.allowed_element_kinds
        and facts.regions.get(region.region_id)
        and facts.regions[region.region_id].content_refs
    ]
    if not candidates:
        return None
    # A device belongs where devices live. A prose region (one that accepts
    # body copy) is already sized for its text, so dropping a chart into it
    # overflows the face; a dedicated device region (rail, band) is sized for
    # marks. Among equals, the widest wins - a chart needs horizontal room.
    dedicated = [
        region
        for region in candidates
        if "body" not in region.allowed_element_kinds
    ]
    pool = dedicated or candidates
    return max(pool, key=lambda region: (region.width_mm, region.region_id))


def _add_viz_elements(
    *,
    face: FacePlan,
    family: CompositionFamily,
    facts: FaceCompositionFacts,
    source_ledger: SourceLedger,
) -> tuple[list[object], set[str]]:
    """Select data visualization from claim relationships and evidence shape.

    A computed difference becomes a grouped before/after comparison; a wider
    computation becomes a formula ladder; claims sharing an entity scope
    across distinct time scopes become a time series. A claim with no
    recognized shape stays a plain stat. Decorative variety is never a
    selection input.
    """
    claim_by_id = {claim.claim_id: claim for claim in source_ledger.claims}
    elements: list[object] = []
    consumed: set[str] = set()

    series_groups: dict[str, list] = {}
    for claim_id in face.claim_ids:
        claim = claim_by_id.get(claim_id)
        if (
            claim is not None
            and claim.computation is None
            and claim.entity_scope
            and claim.time_scope
        ):
            series_groups.setdefault(claim.entity_scope, []).append(claim)

    # A transition: one subject stated at a before and an after. The prose
    # says "von X auf Y" without naming the delta, so no result claim is
    # bound and nothing is computed on the reader's behalf.
    transition_index = 0
    for scope, claims in sorted(series_groups.items()):
        if len(claims) != 2 or {claim.time_scope for claim in claims} != {
            "before",
            "after",
        }:
            continue
        target = _viz_region(family, facts, "grouped_comparison")
        if target is None:
            continue
        before = next(claim for claim in claims if claim.time_scope == "before")
        after = next(claim for claim in claims if claim.time_scope == "after")
        transition_index += 1
        elements.append(
            GroupedComparisonElement(
                element_id=(
                    f"{face.face_id}.{target.region_id}"
                    f".grouped_comparison.{transition_index:02d}"
                ),
                region_id=target.region_id,
                before_claim_id=before.claim_id,
                after_claim_id=after.claim_id,
                label_content_ref=facts.regions[target.region_id].content_refs[0],
                required_visibility=True,
            )
        )
        consumed.update({before.claim_id, after.claim_id})

    # A share: a percent claim naming what it is a share OF, with no time
    # scope. Its remainder is drawn as geometry, never as a second claim.
    share_index = 0
    for claim_id in face.claim_ids:
        if claim_id in consumed:
            continue
        claim = claim_by_id.get(claim_id)
        if (
            claim is None
            or claim.computation is not None
            or claim.unit != "percent"
            or not claim.entity_scope
            or claim.time_scope
        ):
            continue
        target = _viz_region(family, facts, "share")
        if target is None:
            continue
        share_index += 1
        elements.append(
            ShareElement(
                element_id=(
                    f"{face.face_id}.{target.region_id}.share.{share_index:02d}"
                ),
                region_id=target.region_id,
                claim_id=claim.claim_id,
                label_content_ref=facts.regions[target.region_id].content_refs[0],
                required_visibility=True,
            )
        )
        consumed.add(claim.claim_id)

    # Pull quote: a grounded quote claim whose exact words appear in a region
    # that accepts a quote becomes a quote card. The proof wall takes two or
    # more; a single testimonial had nowhere to go, so no page in the system
    # ever carried a pull quote even though the element was fully drawn.
    quote_index = 0
    for claim_id in face.claim_ids:
        if claim_id in consumed:
            continue
        claim = claim_by_id.get(claim_id)
        if claim is None or claim.claim_type.value != "quote":
            continue
        target = next(
            (
                region
                for region in family.regions
                if "quote" in region.allowed_element_kinds
                and facts.regions.get(region.region_id)
                and facts.regions[region.region_id].content_refs
            ),
            None,
        )
        if target is None:
            continue
        matching_ref = next(
            (
                ref
                for ref in facts.regions[target.region_id].content_refs
                if facts.content_by_ref.get(ref) == claim.normalized_value
            ),
            None,
        )
        if matching_ref is None:
            continue
        quote_index += 1
        elements.append(
            QuoteElement(
                element_id=f"{face.face_id}.{target.region_id}.quote.{quote_index:02d}",
                region_id=target.region_id,
                content_ref=matching_ref,
                claim_id=claim.claim_id,
                required_visibility=True,
            )
        )
        consumed.add(claim.claim_id)

    # Composition breakdown: percent claims that name the SAME whole and
    # together stay within it are parts of one thing, so they are drawn as one
    # breakdown rather than as separate figures the reader must add up.
    breakdown_groups: dict[str, list] = {}
    for claim_id in face.claim_ids:
        if claim_id in consumed:
            continue
        claim = claim_by_id.get(claim_id)
        if (
            claim is not None
            and claim.computation is None
            and claim.unit == "percent"
            and claim.entity_scope
            and not claim.time_scope
        ):
            breakdown_groups.setdefault(claim.entity_scope, []).append(claim)
    breakdown_index = 0
    for _, parts in sorted(breakdown_groups.items()):
        if len(parts) < 2 or not _within_one_whole(parts):
            continue
        target = _viz_region(family, facts, "composition_breakdown")
        if target is None:
            continue
        breakdown_index += 1
        part_ids = tuple(part.claim_id for part in parts)
        elements.append(
            CompositionBreakdownElement(
                element_id=(
                    f"{face.face_id}.{target.region_id}"
                    f".composition_breakdown.{breakdown_index:02d}"
                ),
                region_id=target.region_id,
                part_claim_ids=part_ids,
                label_content_ref=facts.regions[target.region_id].content_refs[0],
                required_visibility=True,
            )
        )
        consumed.update(part_ids)

    # Distribution: the same measure reported across DIFFERENT subjects at one
    # point in time is a spread, not a whole, so it is drawn as a comparison
    # across categories with no implied total.
    spread_groups: dict[str, list] = {}
    for claim_id in face.claim_ids:
        if claim_id in consumed:
            continue
        claim = claim_by_id.get(claim_id)
        if (
            claim is not None
            and claim.computation is None
            and claim.unit
            and claim.entity_scope
            and not claim.time_scope
        ):
            spread_groups.setdefault(claim.unit, []).append(claim)
    distribution_index = 0
    for _, segments in sorted(spread_groups.items()):
        scopes = {segment.entity_scope for segment in segments}
        if len(segments) < 2 or len(scopes) != len(segments):
            continue
        target = _viz_region(family, facts, "distribution")
        if target is None:
            continue
        distribution_index += 1
        segment_ids = tuple(segment.claim_id for segment in segments)
        elements.append(
            DistributionElement(
                element_id=(
                    f"{face.face_id}.{target.region_id}"
                    f".distribution.{distribution_index:02d}"
                ),
                region_id=target.region_id,
                segment_claim_ids=segment_ids,
                label_content_ref=facts.regions[target.region_id].content_refs[0],
                required_visibility=True,
            )
        )
        consumed.update(segment_ids)

    series_index = 0
    for _, claims in sorted(series_groups.items()):
        time_scopes = {claim.time_scope for claim in claims}
        if len(claims) < 3 or len(time_scopes) != len(claims):
            continue
        target = _viz_region(family, facts, "time_series")
        if target is None:
            continue
        series_index += 1
        ordered = tuple(
            claim.claim_id
            for claim in sorted(claims, key=lambda item: item.time_scope)
        )
        elements.append(
            TimeSeriesElement(
                element_id=(
                    f"{face.face_id}.{target.region_id}.time_series.{series_index:02d}"
                ),
                region_id=target.region_id,
                point_claim_ids=ordered,
                label_content_ref=facts.regions[target.region_id].content_refs[0],
                required_visibility=True,
            )
        )
        consumed.update(ordered)

    # Proof wall: two or more grounded quote claims whose exact text exists
    # among a wall-capable region's content refs become one review wall.
    wall_region = _viz_region(family, facts, "proof_wall")
    if wall_region is not None:
        region_refs = facts.regions[wall_region.region_id].content_refs
        pairs: list[tuple[str, str]] = []
        for claim_id in face.claim_ids:
            claim = claim_by_id.get(claim_id)
            if claim is None or claim.claim_type.value != "quote":
                continue
            matching_ref = next(
                (
                    ref
                    for ref in region_refs
                    if facts.content_by_ref.get(ref) == claim.normalized_value
                ),
                None,
            )
            if matching_ref is not None:
                pairs.append((claim_id, matching_ref))
        if len(pairs) >= 2:
            elements.append(
                ProofWallElement(
                    element_id=f"{face.face_id}.{wall_region.region_id}.proof_wall.01",
                    region_id=wall_region.region_id,
                    quote_content_refs=tuple(ref for _, ref in pairs),
                    claim_ids=tuple(claim_id for claim_id, _ in pairs),
                    required_visibility=True,
                )
            )
            consumed.update(claim_id for claim_id, _ in pairs)

    computed_index = 0
    for claim_id in face.claim_ids:
        if claim_id in consumed:
            continue
        claim = claim_by_id.get(claim_id)
        if claim is None or claim.computation is None:
            continue
        operands = claim.computation.operand_claim_ids
        if len(operands) < 2:
            continue
        if len(operands) == 2:
            target = _viz_region(family, facts, "grouped_comparison")
            if target is not None:
                computed_index += 1
                elements.append(
                    GroupedComparisonElement(
                        element_id=(
                            f"{face.face_id}.{target.region_id}"
                            f".grouped_comparison.{computed_index:02d}"
                        ),
                        region_id=target.region_id,
                        before_claim_id=operands[0],
                        after_claim_id=operands[1],
                        result_claim_id=claim.claim_id,
                        label_content_ref=facts.regions[
                            target.region_id
                        ].content_refs[0],
                        required_visibility=True,
                    )
                )
                consumed.add(claim.claim_id)
                consumed.update(operands)
                continue
        target = _viz_region(family, facts, "formula_ladder")
        if target is not None:
            computed_index += 1
            elements.append(
                FormulaLadderElement(
                    element_id=(
                        f"{face.face_id}.{target.region_id}"
                        f".formula_ladder.{computed_index:02d}"
                    ),
                    region_id=target.region_id,
                    operand_claim_ids=operands,
                    result_claim_id=claim.claim_id,
                    label_content_ref=facts.regions[target.region_id].content_refs[0],
                    required_visibility=True,
                )
            )
            consumed.add(claim.claim_id)
            consumed.update(operands)

    return elements, consumed


def _add_claim_elements(
    *,
    face: FacePlan,
    family: CompositionFamily,
    facts: FaceCompositionFacts,
    existing_claim_ids: set[str],
) -> list[object]:
    elements: list[object] = []
    # Each claim on a face needs its OWN label. Taking content_refs[0] every
    # time printed the region's heading under all four trust figures, so the
    # page read "Belege statt Behauptungen" four times instead of naming what
    # each number measures. Refs are consumed positionally from the second
    # one onward, because the first is the region heading.
    label_cursor = 0
    for index, claim_id in enumerate(face.claim_ids, start=1):
        if claim_id in existing_claim_ids:
            continue
        target = next(
            (
                region
                for region in family.regions
                if "stat" in region.allowed_element_kinds
                and facts.regions.get(region.region_id)
                and facts.regions[region.region_id].content_refs
            ),
            None,
        )
        kind = "stat"
        if target is None:
            target = next(
                (
                    region
                    for region in family.regions
                    if "source" in region.allowed_element_kinds
                    and facts.regions.get(region.region_id)
                    and facts.regions[region.region_id].content_refs
                ),
                None,
            )
            kind = "source"
        if target is None:
            raise ContractMaterializationFailure(
                code="claim_has_no_legal_region",
                detail=f"{claim_id} cannot be represented by {family.family_id}",
                face_ids=(face.face_id,),
            )
        region_refs = facts.regions[target.region_id].content_refs
        # The first ref is the region's own heading, so captions come from the
        # ones after it. A region with no spare ref gives its stats no caption
        # at all, rather than printing the page title under every figure.
        label_index = 1 + label_cursor
        label_ref = region_refs[label_index] if label_index < len(region_refs) else None
        label_cursor += 1
        element_id = f"{face.face_id}.{target.region_id}.{kind}.{index:02d}"
        if kind == "stat":
            elements.append(
                StatElement(
                    element_id=element_id,
                    region_id=target.region_id,
                    claim_id=claim_id,
                    label_content_ref=label_ref,
                    required_visibility=True,
                )
            )
        else:
            elements.append(
                SourceElement(
                    element_id=element_id,
                    region_id=target.region_id,
                    claim_id=claim_id,
                    # A citation must say something, so it falls back to the
                    # region's own text where a stat would print nothing.
                    content_ref=label_ref or region_refs[0],
                    required_visibility=True,
                )
            )
    return elements


def _add_asset_elements(
    *,
    face: FacePlan,
    family: CompositionFamily,
    facts: FaceCompositionFacts,
    asset_ledger: AssetLedger,
) -> list[object]:
    asset_by_id = {asset.asset_id: asset for asset in asset_ledger.assets}
    elements: list[object] = []
    grouped_logo_ids: set[str] = set()
    # Logo wall: three or more logo-class assets on one face become one wall
    # in a wall-capable region instead of scattered single images.
    logo_ids = tuple(
        asset_id
        for asset_id in facts.asset_ids
        if asset_by_id.get(asset_id) is not None
        and asset_by_id[asset_id].semantic_class.value == "logo"
    )
    if len(logo_ids) >= 3:
        wall_region = next(
            (
                region
                for region in family.regions
                if "logo_wall" in region.allowed_element_kinds
                and facts.regions.get(region.region_id)
                and facts.regions[region.region_id].content_refs
            ),
            None,
        )
        if wall_region is not None:
            elements.append(
                LogoWallElement(
                    element_id=f"{face.face_id}.{wall_region.region_id}.logo_wall.01",
                    region_id=wall_region.region_id,
                    asset_ids=logo_ids,
                    label_content_ref=facts.regions[
                        wall_region.region_id
                    ].content_refs[0],
                    required_visibility=True,
                )
            )
            grouped_logo_ids.update(logo_ids)

    # Evidence gallery: two or more proof-class assets on one face become one
    # captioned gallery. Richard's trust pages carry 11-15 marks; scattering
    # proof images as single stamps is what left ours at five. This element
    # was declared in the contract and drawn by the renderer, but nothing
    # ever built one, so the kind could never appear.
    proof_ids = tuple(
        asset_id
        for asset_id in facts.asset_ids
        if asset_id not in grouped_logo_ids
        and asset_by_id.get(asset_id) is not None
        and asset_by_id[asset_id].semantic_class.value in {"proof", "context"}
    )
    if len(proof_ids) >= 2:
        gallery_region = next(
            (
                region
                for region in family.regions
                if "evidence_gallery" in region.allowed_element_kinds
                and facts.regions.get(region.region_id)
                and facts.regions[region.region_id].content_refs
            ),
            None,
        )
        if gallery_region is not None:
            captions = facts.regions[gallery_region.region_id].content_refs
            elements.append(
                EvidenceGalleryElement(
                    element_id=(
                        f"{face.face_id}.{gallery_region.region_id}"
                        ".evidence_gallery.01"
                    ),
                    region_id=gallery_region.region_id,
                    asset_ids=proof_ids,
                    # One caption per image where the region supplies them,
                    # otherwise the gallery shares the region's own label.
                    caption_content_refs=(
                        captions[: len(proof_ids)]
                        if len(captions) >= len(proof_ids)
                        else captions[:1]
                    ),
                    required_visibility=True,
                )
            )
            grouped_logo_ids.update(proof_ids)

    for index, asset_id in enumerate(facts.asset_ids, start=1):
        if asset_id in grouped_logo_ids:
            continue
        asset = asset_by_id.get(asset_id)
        if asset is None:
            raise ContractMaterializationFailure(
                code="asset_id_not_registered",
                detail=f"{asset_id} is not present in the AssetLedger",
                face_ids=(face.face_id,),
            )
        is_qr = asset.semantic_class is SemanticAssetClass.QR
        allowed_kind = "qr" if is_qr else "image"
        target = next(
            (
                region
                for region in family.regions
                if allowed_kind in region.allowed_element_kinds
                and facts.regions.get(region.region_id)
                and facts.regions[region.region_id].content_refs
            ),
            None,
        )
        if target is None:
            raise ContractMaterializationFailure(
                code="asset_has_no_legal_region",
                detail=f"{asset_id} cannot be represented by {family.family_id}",
                face_ids=(face.face_id,),
            )
        content_ref = facts.regions[target.region_id].content_refs[0]
        element_id = f"{face.face_id}.{target.region_id}.{allowed_kind}.{index:02d}"
        if is_qr:
            elements.append(
                QrElement(
                    element_id=element_id,
                    region_id=target.region_id,
                    asset_id=asset_id,
                    destination_content_ref=content_ref,
                    required_visibility=True,
                )
            )
        else:
            elements.append(
                ImageElement(
                    element_id=element_id,
                    region_id=target.region_id,
                    asset_id=asset_id,
                    alt_content_ref=content_ref,
                    required_visibility=True,
                )
            )
    return elements


def _materialize_family(
    face: FacePlan,
    family: CompositionFamily,
    facts: FaceCompositionFacts,
    *,
    source_ledger: SourceLedger,
    asset_ledger: AssetLedger,
) -> tuple[object, ...]:
    _validate_numeric_grounding(face, facts, source_ledger)
    elements: list[object] = []
    for region in family.regions:
        region_facts = facts.regions.get(region.region_id)
        if region_facts is None:
            if region.required:
                raise ContractMaterializationFailure(
                    code="required_region_facts_missing",
                    detail=f"missing facts for {family.family_id}.{region.region_id}",
                    face_ids=(face.face_id,),
                )
            continue
        unknown_refs = set(region_facts.content_refs) - set(facts.content_by_ref)
        if unknown_refs:
            raise ContractMaterializationFailure(
                code="unknown_content_reference",
                detail=", ".join(sorted(unknown_refs)),
                face_ids=(face.face_id,),
            )
        elements.extend(
            _add_content_elements(
                face=face,
                region=region,
                content_refs=region_facts.content_refs,
            )
        )

    viz_elements, consumed_claim_ids = _add_viz_elements(
        face=face,
        family=family,
        facts=facts,
        source_ledger=source_ledger,
    )
    elements.extend(viz_elements)
    existing_claim_ids = {
        claim_id
        for element in elements
        for claim_id in getattr(element, "claim_ids", ())
    } | consumed_claim_ids
    elements.extend(
        _add_claim_elements(
            face=face,
            family=family,
            facts=facts,
            existing_claim_ids=existing_claim_ids,
        )
    )
    elements.extend(
        _add_asset_elements(
            face=face,
            family=family,
            facts=facts,
            asset_ledger=asset_ledger,
        )
    )

    for proof in face.proof_requirements:
        if proof.required_for_ship and not proof.claim_ids:
            raise ContractMaterializationFailure(
                code="proof_requirement_has_no_claim",
                detail=f"{proof.requirement_id} has no claim IDs",
                face_ids=(face.face_id,),
            )
        missing_claims = set(proof.claim_ids) - {
            claim_id
            for element in elements
            for claim_id in element_claim_refs(element)
        }
        if missing_claims:
            raise ContractMaterializationFailure(
                code="proof_requirement_not_materialized",
                detail=", ".join(sorted(missing_claims)),
                face_ids=(face.face_id,),
            )

    resolution_by_requirement = {
        (resolution.face_id, resolution.requirement_id): resolution
        for resolution in asset_ledger.resolutions
    }
    materialized_assets = {
        getattr(element, "asset_id", None) for element in elements
    }
    for requirement in face.asset_requirements:
        if not requirement.required_for_ship:
            continue
        resolution = resolution_by_requirement.get((face.face_id, requirement.requirement_id))
        if (
            resolution is None
            or resolution.code != "resolved"
            or resolution.asset_id not in materialized_assets
        ):
            raise ContractMaterializationFailure(
                code="asset_requirement_not_materialized",
                detail=requirement.requirement_id,
                face_ids=(face.face_id,),
            )

    for region in family.regions:
        region_elements = [
            element for element in elements if element.region_id == region.region_id
        ]
        if region.required and not region_elements:
            raise ContractMaterializationFailure(
                code="required_region_empty",
                detail=f"{family.family_id}.{region.region_id} has no legal element",
                face_ids=(face.face_id,),
            )
        illegal_kinds = {
            element.kind
            for element in region_elements
            if element.kind not in region.allowed_element_kinds
        }
        if illegal_kinds:
            raise ContractMaterializationFailure(
                code="illegal_element_for_region",
                detail=f"{region.region_id}: {', '.join(sorted(illegal_kinds))}",
                face_ids=(face.face_id,),
            )
    return tuple(elements)


def materialize_editorial_lead(*args, **kwargs):
    return _materialize_family(*args, **kwargs)


def materialize_false_belief_stack(*args, **kwargs):
    return _materialize_family(*args, **kwargs)


def materialize_case_narrative(*args, **kwargs):
    return _materialize_family(*args, **kwargs)


def materialize_theory_interpretation(*args, **kwargs):
    return _materialize_family(*args, **kwargs)


def materialize_mechanism_spread(*args, **kwargs):
    return _materialize_family(*args, **kwargs)


def materialize_summary_synthesis(*args, **kwargs):
    return _materialize_family(*args, **kwargs)


def materialize_objection_response(*args, **kwargs):
    return _materialize_family(*args, **kwargs)


def materialize_collaboration_pathway(*args, **kwargs):
    return _materialize_family(*args, **kwargs)


def materialize_evidence_wall(*args, **kwargs):
    return _materialize_family(*args, **kwargs)


def materialize_closing_cta(*args, **kwargs):
    return _materialize_family(*args, **kwargs)


FamilyMaterializer = Callable[..., tuple[object, ...]]
FAMILY_MATERIALIZERS: dict[str, FamilyMaterializer] = {
    "editorial_lead": materialize_editorial_lead,
    "false_belief_stack": materialize_false_belief_stack,
    "case_narrative": materialize_case_narrative,
    "theory_interpretation": materialize_theory_interpretation,
    "mechanism_spread": materialize_mechanism_spread,
    "summary_synthesis": materialize_summary_synthesis,
    "objection_response": materialize_objection_response,
    "collaboration_pathway": materialize_collaboration_pathway,
    "evidence_wall": materialize_evidence_wall,
    "closing_cta": materialize_closing_cta,
}


def materialize_render_contract_v3(
    plan: ReportPlanV3,
    composition_plan: CompositionPlanV3,
    facts_by_face: dict[str, FaceCompositionFacts],
    *,
    source_ledger: SourceLedger,
    asset_ledger: AssetLedger,
    registry: CompositionRegistry,
    mode: Literal["ship", "draft"],
    theme_id: str,
    artifact_hashes: dict[str, str],
) -> FrozenRenderContractV3:
    decision_by_face = {
        decision.face_id: decision for decision in composition_plan.decisions
    }
    face_by_id = {face.face_id: face for face in plan.faces}
    fragments: list[RenderFragmentV3] = []

    for allocation in plan.units.allocations:
        decisions = tuple(decision_by_face.get(face_id) for face_id in allocation.face_ids)
        if any(decision is None for decision in decisions):
            raise ContractMaterializationFailure(
                code="composition_decision_missing",
                detail=allocation.fragment_id,
                face_ids=allocation.face_ids,
            )
        # A spread carries one composition per face: 28 of the 36 reference
        # spreads pair two different roles on one sheet (case facing theory,
        # status quo facing false beliefs), so requiring one shared
        # composition contradicted the corpus.
        selected = decisions[0].selected
        families = []
        fragment_elements: list[object] = []
        for face_id, decision in zip(allocation.face_ids, decisions):
            face = face_by_id.get(face_id)
            facts = facts_by_face.get(face_id)
            if face is None or facts is None:
                raise ContractMaterializationFailure(
                    code="face_materialization_input_missing",
                    detail=face_id,
                    face_ids=(face_id,),
                )
            face_family = _family(registry, decision.selected)
            if allocation.format.value not in face_family.formats:
                raise ContractMaterializationFailure(
                    code="family_format_unsupported",
                    detail=(
                        f"{face_family.family_id} does not support "
                        f"{allocation.format.value}"
                    ),
                    face_ids=(face_id,),
                )
            materializer = FAMILY_MATERIALIZERS.get(face_family.family_id)
            if materializer is None:
                raise ContractMaterializationFailure(
                    code="family_materializer_missing",
                    detail=face_family.family_id,
                    face_ids=(face_id,),
                )
            families.append(face_family)
            fragment_elements.extend(
                materializer(
                    face,
                    face_family,
                    facts,
                    source_ledger=source_ledger,
                    asset_ledger=asset_ledger,
                )
            )
        family = families[0]

        region_ids: list[str] = []
        for face_family in families:
            for region in face_family.regions:
                if region.region_id not in region_ids:
                    region_ids.append(region.region_id)
        region_assignments = tuple(
            RegionAssignment(
                region_id=region_id,
                element_ids=tuple(
                    element.element_id
                    for element in fragment_elements
                    if element.region_id == region_id
                ),
            )
            for region_id in region_ids
        )
        minimum_font_pt: dict[str, float] = {}
        for element in fragment_elements:
            if element.kind in {"image", "qr", "divider", "group"}:
                continue
            owning_face_id = element.element_id.split(".", 2)[:2]
            face_id = ".".join(owning_face_id)
            language = facts_by_face[face_id].language
            # A mixed spread holds regions from both halves' families, so the
            # minimum-font lookup searches every family on the fragment.
            region = next(
                (
                    item
                    for face_family in families
                    for item in face_family.regions
                    if item.region_id == element.region_id
                ),
                None,
            )
            if region is None:
                raise ContractMaterializationFailure(
                    code="element_region_not_registered",
                    detail=f"{element.element_id} references {element.region_id}",
                    face_ids=allocation.face_ids,
                )
            minimum_font_pt[element.element_id] = _minimum_font(region, language)
        required_ids = tuple(
            element.element_id
            for element in fragment_elements
            if element.required_visibility
        )
        fragments.append(
            RenderFragmentV3(
                fragment_id=allocation.fragment_id,
                format=allocation.format.value,
                face_ids=allocation.face_ids,
                composition=CompositionAssignment(
                    family_id=family.family_id,
                    family_version=family.version,
                    variant_id=selected.variant_id,
                    theme_id=theme_id,
                ),
                face_compositions=tuple(
                    CompositionAssignment(
                        family_id=face_family.family_id,
                        family_version=face_family.version,
                        variant_id=decision.selected.variant_id,
                        theme_id=theme_id,
                    )
                    for face_family, decision in zip(families, decisions)
                ),
                elements=tuple(fragment_elements),
                region_assignments=region_assignments,
                expected_materialization=ExpectedMaterialization(
                    required_element_ids=required_ids,
                    minimum_font_pt=minimum_font_pt,
                ),
            )
        )

    content_refs = tuple(
        sorted(
            {
                content_ref
                for facts in facts_by_face.values()
                for content_ref in facts.content_by_ref
            }
        )
    )
    claim_refs = tuple(sorted(claim.claim_id for claim in source_ledger.claims))
    asset_refs = tuple(sorted(asset.asset_id for asset in asset_ledger.assets))
    payload_hash = _canonical_hash(
        {
            "fragments": [fragment.model_dump(mode="json") for fragment in fragments],
            "content_refs": content_refs,
            "claim_refs": claim_refs,
            "asset_refs": asset_refs,
        }
    )
    all_hashes = {**artifact_hashes, "contract_payload": payload_hash}
    return FrozenRenderContractV3(
        contract_id=f"contract.{payload_hash[:20]}",
        mode=mode,
        product_profile_id=plan.product_profile_id,
        fragments=tuple(fragments),
        content_refs=content_refs,
        claim_refs=claim_refs,
        asset_refs=asset_refs,
        artifact_hashes=all_hashes,
    )


def _within_one_whole(parts) -> bool:
    """True when these percent claims can be parts of a single whole.

    Values that already exceed 100 together are not parts of one thing, so
    drawing them as a breakdown would assert a relationship the evidence
    does not support.
    """
    total = 0.0
    for part in parts:
        try:
            total += float(part.normalized_value.replace(",", "."))
        except ValueError:
            return False
    return 0.0 < total <= 100.0
