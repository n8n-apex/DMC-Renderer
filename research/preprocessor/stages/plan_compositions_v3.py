"""Deterministic composition feasibility and selection for v3 reports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

import re

from composition_registry.capacity import CapacityInput, estimate_region_capacity
from composition_registry.schema import CompositionFamily, CompositionRegistry
from contracts_v3.asset_ledger import AssetLedger
from contracts_v3.report_plan import DesignFeaturesV3, FacePlan, ReportPlanV3
from contracts_v3.source_ledger import SourceLedger


_TOKEN_RE = re.compile(r"[a-zäöüß0-9]+", re.IGNORECASE)


def _tokens(*values: str) -> frozenset[str]:
    found: set[str] = set()
    for value in values:
        found.update(match.lower() for match in _TOKEN_RE.findall(value))
    return frozenset(found)


class StrictFrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CompositionScoringPolicy(StrictFrozenModel):
    schema_version: Literal["1.0"] = "1.0"
    policy_id: str = Field(min_length=1)
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    weights: dict[str, float]
    tie_breakers: tuple[
        Literal["family_id", "family_version", "variant_id"], ...
    ]
    density_band_target_words: dict[str, int] = Field(default_factory=dict)
    feature_affinities: dict[str, dict[str, tuple[str, ...]]] = Field(
        default_factory=dict
    )

    def affinity_tokens(self, feature: str, level: str) -> frozenset[str]:
        return frozenset(self.feature_affinities.get(feature, {}).get(level, ()))


class RegionCompositionFacts(StrictFrozenModel):
    content_refs: tuple[str, ...]
    font_size_pt: float = Field(gt=0)
    image_aspect_ratio: float | None = Field(default=None, gt=0)
    stat_count: int = Field(default=0, ge=0)
    list_item_count: int = Field(default=0, ge=0)


class FaceCompositionFacts(StrictFrozenModel):
    face_id: str = Field(min_length=1)
    language: Literal["de", "en"]
    content_by_ref: dict[str, str]
    regions: dict[str, RegionCompositionFacts]
    asset_ids: tuple[str, ...] = ()
    # Typed semantic exclusions from numeric-grounding: a content ref may be
    # exempted only by declaring WHAT its number is. Never a regex hole.
    numeric_exemptions: dict[
        str, Literal["year", "ordered_list_label", "page_number"]
    ] = Field(default_factory=dict)


class ConsideredFamily(StrictFrozenModel):
    family_id: str
    family_version: str
    feasible: bool
    elimination_reasons: tuple[str, ...]
    capacity_statuses: dict[str, Literal["fits", "near_limit", "does_not_fit"]]
    capacity_violations: dict[str, tuple[str, ...]]
    score_components: dict[str, float]
    total_score: float


class SelectedComposition(StrictFrozenModel):
    family_id: str
    family_version: str
    variant_id: str
    policy_id: str
    policy_version: str


class VariantTieBreak(StrictFrozenModel):
    policy_tie_breakers: tuple[
        Literal["family_id", "family_version", "variant_id"], ...
    ]
    applied: bool
    winner_variant_id: str


class FaceCompositionDecision(StrictFrozenModel):
    face_id: str
    considered: tuple[ConsideredFamily, ...]
    selected: SelectedComposition
    variant_scores: dict[str, float] = Field(default_factory=dict)
    tie_break: VariantTieBreak | None = None
    backtracking_signals: tuple[
        Literal["try_variant", "try_family", "return_to_editorial", "return_to_assets"],
        ...,
    ] = ("try_variant", "try_family")


class CompositionPlanV3(StrictFrozenModel):
    schema_version: Literal["3.0"] = "3.0"
    registry_version: str
    policy_id: str
    policy_version: str
    decisions: tuple[FaceCompositionDecision, ...]


class CompositionPlanningFailure(ValueError):
    def __init__(
        self,
        *,
        face_id: str,
        considered: tuple[ConsideredFamily, ...],
        backtracking_signal: Literal[
            "try_variant", "try_family", "return_to_editorial", "return_to_assets"
        ],
    ) -> None:
        self.face_id = face_id
        self.owner_stage = "composition_planner"
        self.considered = considered
        self.backtracking_signal = backtracking_signal
        common_reasons = (
            set.intersection(
                *(set(candidate.elimination_reasons) for candidate in considered)
            )
            if considered
            else set()
        )
        all_reasons = tuple(
            dict.fromkeys(
                reason
                for candidate in considered
                for reason in candidate.elimination_reasons
            )
        )
        self.elimination_codes = tuple(
            reason for reason in all_reasons if reason in common_reasons
        ) or all_reasons
        detail = ", ".join(self.elimination_codes) or "no candidate family"
        super().__init__(f"{face_id} has no feasible composition: {detail}")


def load_composition_policy(path: Path) -> CompositionScoringPolicy:
    return CompositionScoringPolicy.model_validate(
        json.loads(path.read_text(encoding="utf-8"))
    )


_CHART_ELEMENT_KINDS = frozenset({"stat", "comparison", "process"})
_LEVEL_VALUES = {
    "sparse": 0.0,
    "moderate": 0.5,
    "rich": 1.0,
    "none": 0.0,
    "low": 0.33,
    "high": 1.0,
}


def _feature_token_pool(
    features: DesignFeaturesV3,
    policy: CompositionScoringPolicy,
) -> frozenset[str]:
    pool = set(_tokens(*features.tone_tokens))
    pool |= policy.affinity_tokens("imagery_density", features.imagery_density)
    pool |= policy.affinity_tokens("brand_energy", features.brand_energy)
    pool |= policy.affinity_tokens("chart_opportunity", features.chart_opportunity)
    return frozenset(pool)


def _family_feature_scores(
    family: CompositionFamily,
    face: FacePlan,
    features: DesignFeaturesV3 | None,
    policy: CompositionScoringPolicy,
    *,
    language: str,
    evidence_count: int,
    available_asset_count: int,
) -> dict[str, float]:
    if features is None:
        return {
            "tone_alignment": 0.0,
            "density_fit": 0.0,
            "evidence_density_fit": 0.0,
            "chart_opportunity_fit": 0.0,
            "asset_availability_fit": 0.0,
        }

    family_tokens = _tokens(
        *family.cadence_tags,
        *family.theme_affordances,
        family.semantic_promise,
    )
    tone_overlap = len(_feature_token_pool(features, policy) & family_tokens)

    band_target = policy.density_band_target_words.get(face.density_band.value, 0)
    family_target = sum(
        capacity.target_words
        for region in family.regions
        if region.required
        for capacity in region.capacities
        if capacity.language == language
    )
    if band_target > 0 and family_target > 0:
        density_fit = 1.0 - (
            abs(band_target - family_target) / max(band_target, family_target)
        )
    else:
        density_fit = 0.0

    bounds = family.evidence_bounds
    midpoint = (bounds.min_claims + bounds.max_claims) / 2
    if bounds.min_claims <= evidence_count <= bounds.max_claims:
        evidence_fit = 1.0 - (
            abs(evidence_count - midpoint) / max(midpoint, 1.0)
        )
    else:
        evidence_fit = 0.0

    chart_regions = sum(
        1
        for region in family.regions
        if _CHART_ELEMENT_KINDS & set(region.allowed_element_kinds)
    )
    chart_fraction = chart_regions / max(1, len(family.regions))
    chart_fit = 1.0 - abs(
        _LEVEL_VALUES[features.chart_opportunity] - chart_fraction
    )

    asset_intensity = min(
        1.0,
        family.evidence_bounds.max_assets / 8
        + (0.25 if family.evidence_bounds.min_assets > 0 else 0.0),
    )
    availability = min(1.0, available_asset_count / 4)
    imagery_level = _LEVEL_VALUES[features.imagery_density]
    demanded = min(imagery_level, availability)
    asset_fit = 1.0 - abs(demanded - asset_intensity)

    return {
        "tone_alignment": policy.weights.get("tone_alignment", 0.0) * tone_overlap,
        "density_fit": policy.weights.get("density_fit", 0.0) * density_fit,
        "evidence_density_fit": policy.weights.get("evidence_density_fit", 0.0)
        * evidence_fit,
        "chart_opportunity_fit": policy.weights.get("chart_opportunity_fit", 0.0)
        * chart_fit,
        "asset_availability_fit": policy.weights.get("asset_availability_fit", 0.0)
        * asset_fit,
    }


def _score_variants(
    family: CompositionFamily,
    features: DesignFeaturesV3 | None,
    policy: CompositionScoringPolicy,
    face: FacePlan | None = None,
) -> tuple[dict[str, float], "VariantTieBreak", str]:
    weight = policy.weights.get("variant_alignment", 0.0)
    pool = (
        _feature_token_pool(features, policy) if features is not None else frozenset()
    )
    if features is not None and face is not None:
        # The face's own density band steers text-led vs photo-led variants:
        # Richard's corpus carries both editorial modes and the band is the
        # honest selector between them.
        pool = pool | policy.affinity_tokens("density_band", face.density_band.value)
    scores = {
        variant.variant_id: weight
        * len(
            pool
            & _tokens(
                variant.variant_id,
                variant.semantic_delta,
                variant.geometry_delta,
            )
        )
        for variant in family.variants
    }
    best_score = max(scores.values())
    leaders = sorted(
        variant_id for variant_id, score in scores.items() if score == best_score
    )
    tie_break = VariantTieBreak(
        policy_tie_breakers=policy.tie_breakers,
        applied=len(leaders) > 1,
        winner_variant_id=leaders[0],
    )
    return scores, tie_break, leaders[0]


def _score_family(
    family: CompositionFamily,
    family_history: tuple[str, ...],
    registry: CompositionRegistry,
    policy: CompositionScoringPolicy,
) -> dict[str, float]:
    previous_id = family_history[-1] if family_history else None
    previous = next(
        (candidate for candidate in registry.families if candidate.family_id == previous_id),
        None,
    )
    previous_tags = set(previous.cadence_tags) if previous else set()
    novel_tags = len(set(family.cadence_tags) - previous_tags)
    repeated = previous_id == family.family_id
    return {
        "cadence_novelty": policy.weights.get("cadence_novelty", 0.0)
        * novel_tags,
        "family_switch_bonus": (
            policy.weights.get("family_switch_bonus", 0.0)
            if previous_id is not None and not repeated
            else 0.0
        ),
        "repeat_penalty": (
            policy.weights.get("repeat_penalty", 0.0) if repeated else 0.0
        ),
    }


def _candidate_record(
    family: CompositionFamily,
    face: FacePlan,
    facts: FaceCompositionFacts,
    *,
    source_ledger: SourceLedger,
    asset_ledger: AssetLedger,
    policy: CompositionScoringPolicy,
    registry: CompositionRegistry,
    family_history: tuple[str, ...],
    font_path: Path,
    design_features: DesignFeaturesV3 | None = None,
) -> ConsideredFamily:
    reasons: list[str] = []
    capacity_statuses: dict[str, Literal["fits", "near_limit", "does_not_fit"]] = {}
    capacity_violations: dict[str, tuple[str, ...]] = {}

    if face.dominant_mechanism not in family.dominant_mechanisms:
        reasons.append("unsupported_dominant_mechanism")

    known_claims = {claim.claim_id for claim in source_ledger.claims}
    required_claims = set(face.claim_ids)
    for requirement in face.proof_requirements:
        required_claims.update(requirement.claim_ids)
        if requirement.required_for_ship and requirement.claim_ids:
            if not set(requirement.claim_ids) <= known_claims:
                reasons.append("required_proof_missing")
        elif requirement.required_for_ship and not known_claims:
            reasons.append("required_proof_missing")
    evidence_count = len(required_claims & known_claims)
    if evidence_count < family.evidence_bounds.min_claims:
        reasons.append("minimum_claim_evidence_missing")
    if evidence_count > family.evidence_bounds.max_claims:
        reasons.append("claim_evidence_exceeds_family")

    asset_by_id = {asset.asset_id: asset for asset in asset_ledger.assets}
    selected_assets = [asset_by_id.get(asset_id) for asset_id in facts.asset_ids]
    if any(asset is None for asset in selected_assets):
        reasons.append("selected_asset_missing")
    selected_classes = {
        asset.semantic_class.value for asset in selected_assets if asset is not None
    }
    if selected_classes - set(family.supported_asset_classes):
        reasons.append("illegal_asset_class")
    if len(selected_assets) < family.evidence_bounds.min_assets:
        reasons.append("minimum_asset_evidence_missing")
    if len(selected_assets) > family.evidence_bounds.max_assets:
        reasons.append("asset_count_exceeds_family")

    resolution_by_requirement = {
        (resolution.face_id, resolution.requirement_id): resolution
        for resolution in asset_ledger.resolutions
    }
    for requirement in face.asset_requirements:
        if not requirement.required_for_ship:
            continue
        resolution = resolution_by_requirement.get((face.face_id, requirement.requirement_id))
        if resolution is None or resolution.code != "resolved":
            reasons.append("required_asset_unresolved")

    for region in family.regions:
        if not region.required:
            continue
        region_facts = facts.regions.get(region.region_id)
        if region_facts is None:
            reasons.append("region_capacity_missing")
            capacity_statuses[region.region_id] = "does_not_fit"
            capacity_violations[region.region_id] = ("region_capacity_missing",)
            continue
        assessment = estimate_region_capacity(
            region,
            CapacityInput(
                language=facts.language,
                content_by_ref=facts.content_by_ref,
                selected_content_refs=region_facts.content_refs,
                font_path=str(font_path),
                font_size_pt=region_facts.font_size_pt,
                image_aspect_ratio=region_facts.image_aspect_ratio,
                stat_count=region_facts.stat_count,
                list_item_count=region_facts.list_item_count,
            ),
        )
        capacity_statuses[region.region_id] = assessment.status
        capacity_violations[region.region_id] = assessment.violation_codes
        if assessment.status == "does_not_fit":
            reasons.append("region_does_not_fit")

    score_components = {
        **_score_family(family, family_history, registry, policy),
        **_family_feature_scores(
            family,
            face,
            design_features,
            policy,
            language=facts.language,
            evidence_count=evidence_count,
            available_asset_count=sum(
                1 for asset in selected_assets if asset is not None
            ),
        ),
    }
    unique_reasons = tuple(dict.fromkeys(reasons))
    return ConsideredFamily(
        family_id=family.family_id,
        family_version=family.version,
        feasible=not unique_reasons,
        elimination_reasons=unique_reasons,
        capacity_statuses=capacity_statuses,
        capacity_violations=capacity_violations,
        score_components=score_components,
        total_score=sum(score_components.values()),
    )


def _variant_capacity_fits(
    family: CompositionFamily,
    facts: FaceCompositionFacts,
    envelope_scale: float,
    font_path: Path,
) -> bool:
    """Does this face's copy fit the family's regions at this variant's scale?"""
    for region in family.regions:
        if not region.required:
            continue
        region_facts = facts.regions.get(region.region_id)
        if region_facts is None:
            return False
        assessment = estimate_region_capacity(
            region,
            CapacityInput(
                language=facts.language,
                content_by_ref=facts.content_by_ref,
                selected_content_refs=region_facts.content_refs,
                font_path=str(font_path),
                font_size_pt=region_facts.font_size_pt,
                image_aspect_ratio=region_facts.image_aspect_ratio,
                stat_count=region_facts.stat_count,
                list_item_count=region_facts.list_item_count,
                envelope_scale=envelope_scale,
            ),
        )
        if assessment.status == "does_not_fit":
            return False
    return True


def _failure_signal(
    considered: tuple[ConsideredFamily, ...],
) -> Literal["try_variant", "try_family", "return_to_editorial", "return_to_assets"]:
    if not considered:
        return "try_family"
    minimum_reason_count = min(len(candidate.elimination_reasons) for candidate in considered)
    closest_candidates = tuple(
        candidate
        for candidate in considered
        if len(candidate.elimination_reasons) == minimum_reason_count
    )
    codes = {
        reason
        for candidate in closest_candidates
        for reason in candidate.elimination_reasons
    }
    if codes & {
        "illegal_asset_class",
        "selected_asset_missing",
        "minimum_asset_evidence_missing",
        "required_asset_unresolved",
    }:
        return "return_to_assets"
    if codes & {"region_does_not_fit", "region_capacity_missing"}:
        return "return_to_editorial"
    return "try_family"


def select_composition_for_face(
    face: FacePlan,
    facts: FaceCompositionFacts,
    *,
    source_ledger: SourceLedger,
    asset_ledger: AssetLedger,
    registry: CompositionRegistry,
    policy: CompositionScoringPolicy,
    family_history: tuple[str, ...],
    font_path: Path,
    design_features: DesignFeaturesV3 | None = None,
) -> FaceCompositionDecision:
    if facts.face_id != face.face_id:
        raise ValueError("composition facts must match the planned face")

    candidates = registry.for_role(face.role.value)
    considered = tuple(
        _candidate_record(
            family,
            face,
            facts,
            source_ledger=source_ledger,
            asset_ledger=asset_ledger,
            policy=policy,
            registry=registry,
            family_history=family_history,
            font_path=font_path,
            design_features=design_features,
        )
        for family in sorted(candidates, key=lambda item: (item.family_id, item.version))
    )
    feasible = tuple(candidate for candidate in considered if candidate.feasible)
    if not feasible:
        raise CompositionPlanningFailure(
            face_id=face.face_id,
            considered=considered,
            backtracking_signal=_failure_signal(considered),
        )

    selected_record = sorted(
        feasible,
        key=lambda item: (-item.total_score, item.family_id, item.family_version),
    )[0]
    selected_family = next(
        family
        for family in candidates
        if family.family_id == selected_record.family_id
        and family.version == selected_record.family_version
    )
    variant_scores, tie_break, variant_id = _score_variants(
        selected_family, design_features, policy, face
    )
    # A variant that spends vertical room on a photo field or a device band
    # leaves less for prose. Verify the copy actually fits the chosen
    # geometry, and fall to the next-best variant when it does not, so the
    # renderer is never handed copy its layout cannot hold.
    variant_by_id = {
        variant.variant_id: variant for variant in selected_family.variants
    }
    ordered_variants = sorted(
        variant_scores,
        key=lambda item: (-variant_scores[item], item),
    )
    feasible_variant = None
    for candidate_id in ordered_variants:
        variant = variant_by_id[candidate_id]
        if _variant_capacity_fits(
            selected_family, facts, variant.envelope_scale, font_path
        ):
            feasible_variant = candidate_id
            break
    if feasible_variant is not None:
        variant_id = feasible_variant
    return FaceCompositionDecision(
        face_id=face.face_id,
        considered=considered,
        selected=SelectedComposition(
            family_id=selected_family.family_id,
            family_version=selected_family.version,
            variant_id=variant_id,
            policy_id=policy.policy_id,
            policy_version=policy.version,
        ),
        variant_scores=variant_scores,
        tie_break=tie_break,
    )


def plan_compositions_v3(
    plan: ReportPlanV3,
    facts_by_face: dict[str, FaceCompositionFacts],
    *,
    source_ledger: SourceLedger,
    asset_ledger: AssetLedger,
    registry: CompositionRegistry,
    policy: CompositionScoringPolicy,
    font_path: Path,
) -> CompositionPlanV3:
    decisions: list[FaceCompositionDecision] = []
    history: list[str] = []
    for face in plan.faces:
        facts = facts_by_face.get(face.face_id)
        if facts is None:
            raise ValueError(f"missing composition facts for {face.face_id}")
        decision = select_composition_for_face(
            face,
            facts,
            source_ledger=source_ledger,
            asset_ledger=asset_ledger,
            registry=registry,
            policy=policy,
            family_history=tuple(history),
            font_path=font_path,
            design_features=plan.design_features,
        )
        decisions.append(decision)
        history.append(decision.selected.family_id)
    return CompositionPlanV3(
        registry_version=registry.version,
        policy_id=policy.policy_id,
        policy_version=policy.version,
        decisions=tuple(decisions),
    )
