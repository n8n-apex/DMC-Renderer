from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


RoleName = Literal[
    "cover",
    "outlook",
    "about",
    "status_quo",
    "false_beliefs",
    "case_study",
    "theory",
    "mechanism",
    "trust_proof",
    "summary",
    "objections",
    "collaboration",
    "cta",
    "brand_breather",
]


class RegionCapacity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    language: Literal["de", "en"]
    min_words: int = Field(ge=0)
    target_words: int = Field(ge=0)
    max_words: int = Field(gt=0)
    max_wrapped_lines: int = Field(gt=0)
    min_font_pt: float = Field(gt=0)
    max_font_pt: float = Field(gt=0)

    @model_validator(mode="after")
    def validate_ranges(self) -> "RegionCapacity":
        if not self.min_words <= self.target_words <= self.max_words:
            raise ValueError("word capacity must be ordered")
        if self.min_font_pt > self.max_font_pt:
            raise ValueError("font bounds must be ordered")
        return self


class RegionSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    region_id: str = Field(min_length=1)
    semantic_purpose: str = Field(min_length=1)
    required: bool
    width_mm: float = Field(gt=0)
    height_mm: float = Field(gt=0)
    allowed_element_kinds: tuple[str, ...] = Field(min_length=1)
    # What this region is FOR, as opposed to what it merely permits.
    # `_add_content_elements` used to take `body` whenever prose was allowed,
    # so a belief STACK rendered as seven paragraphs and every card treatment
    # in the grammar had nothing to attach to. A region that exists to carry
    # numbered cards says so here, and the materializer honours it.
    preferred_element_kind: str | None = None
    capacities: tuple[RegionCapacity, ...] = Field(min_length=2)
    max_items: int | None = Field(default=None, gt=0)
    image_aspect_ratio_min: float | None = Field(default=None, gt=0)
    image_aspect_ratio_max: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_language_and_aspect_ranges(self) -> "RegionSpec":
        languages = [capacity.language for capacity in self.capacities]
        if len(languages) != len(set(languages)):
            raise ValueError("region capacity languages must be unique")
        if self.image_aspect_ratio_min and self.image_aspect_ratio_max:
            if self.image_aspect_ratio_min > self.image_aspect_ratio_max:
                raise ValueError("image aspect-ratio bounds must be ordered")
        return self


class TypographyBound(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    role: Literal["display", "heading", "body", "label", "numeric", "caption"]
    min_pt: float = Field(gt=0)
    max_pt: float = Field(gt=0)
    min_line_height: float = Field(gt=0)
    max_line_height: float = Field(gt=0)

    @model_validator(mode="after")
    def validate_ranges(self) -> "TypographyBound":
        if self.min_pt > self.max_pt or self.min_line_height > self.max_line_height:
            raise ValueError("typography bounds must be ordered")
        return self


class EvidenceBounds(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    min_claims: int = Field(ge=0)
    max_claims: int = Field(ge=0)
    min_assets: int = Field(ge=0)
    max_assets: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_ranges(self) -> "EvidenceBounds":
        if self.min_claims > self.max_claims or self.min_assets > self.max_assets:
            raise ValueError("evidence bounds must be ordered")
        return self


class FamilyVariant(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    variant_id: str = Field(min_length=1)
    semantic_delta: str = Field(min_length=1)
    geometry_delta: str = Field(min_length=1)
    # Share of the family's declared text envelope this variant leaves for
    # prose. A variant that spends vertical room on a photo field or a device
    # band leaves less; the planner checks capacity against this before
    # selecting the variant, so copy can never be approved for a geometry
    # that cannot hold it. Tighten only: 1.0 is the family's own envelope.
    envelope_scale: float = Field(default=1.0, gt=0.0, le=1.0)


class CompositionFamily(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    family_id: str = Field(pattern=r"^[a-z][a-z0-9_]+$")
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    semantic_promise: str = Field(min_length=1)
    supported_roles: tuple[RoleName, ...] = Field(min_length=1)
    dominant_mechanisms: tuple[str, ...] = Field(min_length=1)
    formats: tuple[Literal["a4", "a3"], ...] = Field(min_length=1)
    regions: tuple[RegionSpec, ...] = Field(min_length=1)
    supported_asset_classes: tuple[str, ...] = Field(min_length=1)
    evidence_bounds: EvidenceBounds
    typography_bounds: tuple[TypographyBound, ...] = Field(min_length=1)
    grid_rules: tuple[str, ...] = Field(min_length=1)
    theme_affordances: tuple[str, ...] = Field(min_length=1)
    cadence_tags: tuple[str, ...] = Field(min_length=1)
    accessibility_constraints: tuple[str, ...] = Field(min_length=1)
    known_failures: tuple[str, ...] = Field(min_length=1)
    atlas_face_ids: tuple[str, ...] = Field(min_length=1)
    design_policy_ids: tuple[str, ...] = Field(min_length=1)
    variants: tuple[FamilyVariant, ...] = Field(min_length=1)
    calibration_status: Literal[
        "experimental",
        "curated_candidate",
        "corpus_tested",
        "client_tested",
        "promoted",
    ]


class CompositionRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    registry_id: str = Field(min_length=1)
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    families: tuple[CompositionFamily, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_family_ids(self) -> "CompositionRegistry":
        family_ids = [family.family_id for family in self.families]
        if len(family_ids) != len(set(family_ids)):
            raise ValueError("family ids must be unique")
        return self

    def for_role(self, role: str) -> tuple[CompositionFamily, ...]:
        return tuple(family for family in self.families if role in family.supported_roles)
