from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictFrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ElementBase(StrictFrozenModel):
    element_id: str = Field(min_length=1)
    region_id: str = Field(min_length=1)
    required_visibility: bool


class HeadingElement(ElementBase):
    kind: Literal["heading"] = "heading"
    content_ref: str = Field(min_length=1)
    level: int = Field(ge=1, le=6)


class BodyElement(ElementBase):
    kind: Literal["body"] = "body"
    content_ref: str = Field(min_length=1)


class QuoteElement(ElementBase):
    kind: Literal["quote"] = "quote"
    content_ref: str = Field(min_length=1)
    claim_id: str = Field(min_length=1)


class StatElement(ElementBase):
    kind: Literal["stat"] = "stat"
    claim_id: str = Field(min_length=1)
    # Optional: a region may have no label distinct from its own heading, and
    # a figure captioned with the page title tells the reader nothing.
    label_content_ref: str | None = Field(default=None, min_length=1)


class ComparisonElement(ElementBase):
    kind: Literal["comparison"] = "comparison"
    left_content_refs: tuple[str, ...] = Field(min_length=1)
    right_content_refs: tuple[str, ...] = Field(min_length=1)
    claim_ids: tuple[str, ...] = ()


class ProcessElement(ElementBase):
    kind: Literal["process"] = "process"
    item_content_refs: tuple[str, ...] = Field(min_length=1)
    claim_ids: tuple[str, ...] = ()


class ImageElement(ElementBase):
    kind: Literal["image"] = "image"
    asset_id: str = Field(min_length=1)
    alt_content_ref: str = Field(min_length=1)


class SourceElement(ElementBase):
    kind: Literal["source"] = "source"
    claim_id: str = Field(min_length=1)
    content_ref: str = Field(min_length=1)


class QrElement(ElementBase):
    kind: Literal["qr"] = "qr"
    asset_id: str = Field(min_length=1)
    destination_content_ref: str = Field(min_length=1)


class DividerElement(ElementBase):
    kind: Literal["divider"] = "divider"


class GroupElement(ElementBase):
    kind: Literal["group"] = "group"
    child_element_ids: tuple[str, ...] = Field(min_length=1)


# --- Semantic data-visualization elements -----------------------------------
# Every device binds to exact claim IDs. Selection is driven by the claims'
# evidence shape (computation, time scope, entity scope), never by decorative
# variety; the materialization stage owns that mapping.


class GroupedComparisonElement(ElementBase):
    """Before/after pair drawn as labeled magnitude bars with the delta."""

    kind: Literal["grouped_comparison"] = "grouped_comparison"
    before_claim_id: str = Field(min_length=1)
    after_claim_id: str = Field(min_length=1)
    result_claim_id: str | None = None
    label_content_ref: str = Field(min_length=1)


class FormulaLadderElement(ElementBase):
    """A computed claim shown as its operand rows and emphasized result."""

    kind: Literal["formula_ladder"] = "formula_ladder"
    operand_claim_ids: tuple[str, ...] = Field(min_length=2)
    result_claim_id: str = Field(min_length=1)
    label_content_ref: str = Field(min_length=1)


class TimeSeriesElement(ElementBase):
    """Claims sharing an entity scope across distinct time scopes."""

    kind: Literal["time_series"] = "time_series"
    point_claim_ids: tuple[str, ...] = Field(min_length=3)
    label_content_ref: str = Field(min_length=1)


class ShareElement(ElementBase):
    """One stated share of a whole, drawn against its own remainder.

    The remainder is geometry, not a claim: the prose states "70 % of X",
    so only that figure is grounded and only that figure is labelled.
    """

    kind: Literal["share"] = "share"
    claim_id: str = Field(min_length=1)
    label_content_ref: str = Field(min_length=1)


class DistributionElement(ElementBase):
    kind: Literal["distribution"] = "distribution"
    segment_claim_ids: tuple[str, ...] = Field(min_length=2)
    label_content_ref: str = Field(min_length=1)


class CompositionBreakdownElement(ElementBase):
    kind: Literal["composition_breakdown"] = "composition_breakdown"
    part_claim_ids: tuple[str, ...] = Field(min_length=2)
    label_content_ref: str = Field(min_length=1)


class EvidenceGalleryElement(ElementBase):
    kind: Literal["evidence_gallery"] = "evidence_gallery"
    asset_ids: tuple[str, ...] = Field(min_length=2)
    caption_content_refs: tuple[str, ...] = Field(min_length=1)


class LogoWallElement(ElementBase):
    kind: Literal["logo_wall"] = "logo_wall"
    asset_ids: tuple[str, ...] = Field(min_length=3)
    label_content_ref: str = Field(min_length=1)


class ProofWallElement(ElementBase):
    kind: Literal["proof_wall"] = "proof_wall"
    quote_content_refs: tuple[str, ...] = Field(min_length=2)
    claim_ids: tuple[str, ...] = Field(min_length=2)


Element = Annotated[
    Union[
        HeadingElement,
        BodyElement,
        QuoteElement,
        StatElement,
        ComparisonElement,
        ProcessElement,
        ImageElement,
        SourceElement,
        QrElement,
        DividerElement,
        GroupElement,
        GroupedComparisonElement,
        FormulaLadderElement,
        TimeSeriesElement,
        ShareElement,
        DistributionElement,
        CompositionBreakdownElement,
        EvidenceGalleryElement,
        LogoWallElement,
        ProofWallElement,
    ],
    Field(discriminator="kind"),
]


class CompositionAssignment(StrictFrozenModel):
    family_id: str = Field(min_length=1)
    family_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    variant_id: str = Field(min_length=1)
    theme_id: str = Field(min_length=1)


class RegionAssignment(StrictFrozenModel):
    region_id: str = Field(min_length=1)
    element_ids: tuple[str, ...] = Field(min_length=1)


class ExpectedMaterialization(StrictFrozenModel):
    required_element_ids: tuple[str, ...]
    minimum_font_pt: dict[str, float]


def element_content_refs(element: Element) -> tuple[str, ...]:
    if isinstance(element, (HeadingElement, BodyElement, QuoteElement, SourceElement)):
        return (element.content_ref,)
    if isinstance(element, StatElement):
        return (element.label_content_ref,) if element.label_content_ref else ()
    if isinstance(element, ComparisonElement):
        return element.left_content_refs + element.right_content_refs
    if isinstance(element, ProcessElement):
        return element.item_content_refs
    if isinstance(element, ImageElement):
        return (element.alt_content_ref,)
    if isinstance(element, QrElement):
        return (element.destination_content_ref,)
    if isinstance(
        element,
        (
            GroupedComparisonElement,
            FormulaLadderElement,
            TimeSeriesElement,
            DistributionElement,
            CompositionBreakdownElement,
            LogoWallElement,
            ShareElement,
        ),
    ):
        return (element.label_content_ref,)
    if isinstance(element, EvidenceGalleryElement):
        return element.caption_content_refs
    if isinstance(element, ProofWallElement):
        return element.quote_content_refs
    return ()


def element_claim_refs(element: Element) -> tuple[str, ...]:
    if isinstance(element, (QuoteElement, StatElement, SourceElement, ShareElement)):
        return (element.claim_id,)
    if isinstance(element, (ComparisonElement, ProcessElement, ProofWallElement)):
        return element.claim_ids
    if isinstance(element, GroupedComparisonElement):
        refs = (element.before_claim_id, element.after_claim_id)
        if element.result_claim_id is not None:
            refs = refs + (element.result_claim_id,)
        return refs
    if isinstance(element, FormulaLadderElement):
        return element.operand_claim_ids + (element.result_claim_id,)
    if isinstance(element, TimeSeriesElement):
        return element.point_claim_ids
    if isinstance(element, DistributionElement):
        return element.segment_claim_ids
    if isinstance(element, CompositionBreakdownElement):
        return element.part_claim_ids
    return ()


def element_asset_refs(element: Element) -> tuple[str, ...]:
    if isinstance(element, (ImageElement, QrElement)):
        return (element.asset_id,)
    if isinstance(element, (EvidenceGalleryElement, LogoWallElement)):
        return element.asset_ids
    return ()


class RenderFragmentV3(StrictFrozenModel):
    fragment_id: str = Field(min_length=1)
    format: Literal["a4", "a3"]
    face_ids: tuple[str, ...]
    composition: CompositionAssignment
    # A spread is one sheet carrying two DIFFERENT compositions in 28 of the
    # 36 reference spreads (case study facing its theory, status quo facing
    # false beliefs). When present, one assignment per face in face_ids
    # order; `composition` stays the fragment's leading assignment.
    face_compositions: tuple[CompositionAssignment, ...] = ()
    # A ground is the sheet's own surface, not something inside a region, so
    # it is declared per face rather than as an element. Measured from the
    # reference: Buchagentur places ONE texture at 213.7x303.0mm on nine
    # consecutive faces. It is the single cheapest source of visual density
    # in the whole system, because one asset dresses every interior page.
    face_grounds: tuple[str, ...] = ()
    elements: tuple[Element, ...] = Field(min_length=1)
    region_assignments: tuple[RegionAssignment, ...] = Field(min_length=1)
    expected_materialization: ExpectedMaterialization
    fit_policy: Literal["strict", "bounded"] = "strict"
    fallback_family_id: str | None = None

    @model_validator(mode="after")
    def validate_fragment_contract(self) -> "RenderFragmentV3":
        expected_faces = 1 if self.format == "a4" else 2
        if len(self.face_ids) != expected_faces:
            raise ValueError(f"{self.format} requires {expected_faces} face ids")
        if self.face_grounds and len(self.face_grounds) != len(self.face_ids):
            raise ValueError("face grounds must cover every face once")
        if self.face_compositions:
            if len(self.face_compositions) != len(self.face_ids):
                raise ValueError("face compositions must cover every face once")
            if self.face_compositions[0] != self.composition:
                raise ValueError("leading face composition must match the fragment")
        element_ids = [element.element_id for element in self.elements]
        if len(element_ids) != len(set(element_ids)):
            raise ValueError("element ids must be unique within a fragment")
        assigned_ids = [
            element_id
            for assignment in self.region_assignments
            for element_id in assignment.element_ids
        ]
        if set(assigned_ids) != set(element_ids):
            raise ValueError("region assignments must cover every element exactly")
        if len(assigned_ids) != len(set(assigned_ids)):
            raise ValueError("an element may belong to only one region")
        for assignment in self.region_assignments:
            for element_id in assignment.element_ids:
                element = self.elements[element_ids.index(element_id)]
                if element.region_id != assignment.region_id:
                    raise ValueError("element region does not match region assignment")
        required_ids = {
            element.element_id for element in self.elements if element.required_visibility
        }
        if set(self.expected_materialization.required_element_ids) != required_ids:
            raise ValueError("expected materialization must list every required element")
        unknown_font_ids = set(self.expected_materialization.minimum_font_pt) - set(element_ids)
        if unknown_font_ids:
            raise ValueError("minimum font map references unknown elements")
        group_children = {
            child_id
            for element in self.elements
            if isinstance(element, GroupElement)
            for child_id in element.child_element_ids
        }
        if group_children - set(element_ids):
            raise ValueError("group references unknown child elements")
        return self


Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class FrozenRenderContractV3(StrictFrozenModel):
    schema_version: Literal["3.0"] = "3.0"
    contract_id: str = Field(min_length=1)
    mode: Literal["ship", "draft"]
    product_profile_id: str = Field(min_length=1)
    fragments: tuple[RenderFragmentV3, ...] = Field(min_length=1)
    content_refs: tuple[str, ...]
    claim_refs: tuple[str, ...]
    asset_refs: tuple[str, ...]
    artifact_hashes: dict[str, Sha256]

    @model_validator(mode="after")
    def validate_declared_references(self) -> "FrozenRenderContractV3":
        fragment_ids = [fragment.fragment_id for fragment in self.fragments]
        if len(fragment_ids) != len(set(fragment_ids)):
            raise ValueError("fragment ids must be unique")
        face_ids = [face_id for fragment in self.fragments for face_id in fragment.face_ids]
        if len(face_ids) != len(set(face_ids)):
            raise ValueError("face ids must be unique across fragments")
        used_content = {
            ref
            for fragment in self.fragments
            for element in fragment.elements
            for ref in element_content_refs(element)
        }
        used_claims = {
            ref
            for fragment in self.fragments
            for element in fragment.elements
            for ref in element_claim_refs(element)
        }
        used_assets = {
            ref
            for fragment in self.fragments
            for element in fragment.elements
            for ref in element_asset_refs(element)
        } | {
            ground
            for fragment in self.fragments
            for ground in fragment.face_grounds
            if ground
        }
        if not used_content <= set(self.content_refs):
            raise ValueError("element references undeclared content")
        if not used_claims <= set(self.claim_refs):
            raise ValueError("element references undeclared claims")
        if not used_assets <= set(self.asset_refs):
            raise ValueError("element references undeclared assets")
        return self
