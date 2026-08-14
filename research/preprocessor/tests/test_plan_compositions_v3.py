from __future__ import annotations

import json
from pathlib import Path

import pytest

from composition_registry.registry import load_registry
from contracts_v3.asset_ledger import (
    AssetLedger,
    AssetRecord,
    AssetResolution,
)
from contracts_v3.report_plan import FacePlan
from contracts_v3.source_ledger import Claim, SourceLedger
from stages.plan_compositions_v3 import (
    CompositionPlanningFailure,
    FaceCompositionFacts,
    RegionCompositionFacts,
    load_composition_policy,
    select_composition_for_face,
)


ROOT = Path(__file__).resolve().parents[3]
FONT = ROOT / "research" / "v7-renderer" / "fonts" / "SourceSans3[wght].ttf"
REGISTRY_PATH = (
    ROOT / "research" / "composition_registry" / "families" / "dmc-v1.json"
)
ATLAS_PATH = ROOT / "research" / "reference-atlas" / "reference-atlas.json"
POLICY_PATH = (
    ROOT / "research" / "preprocessor" / "policies" / "composition_scoring_v1.json"
)


def face(*, mechanism: str = "editorial", claim_ids: tuple[str, ...] = ()) -> FacePlan:
    return FacePlan(
        face_id="face.05",
        face_index=5,
        role="about",
        narrative_act="authority",
        argument="Eine belastbare Positionierung",
        claim_ids=claim_ids,
        dominant_mechanism=mechanism,
        density_band="moderate",
    )


def source_ledger(*, with_claim: bool = False) -> SourceLedger:
    claims = (
        Claim(
            claim_id="claim.proof",
            claim_type="interpretation",
            normalized_value="Belegter Vertrauensanker",
        ),
    ) if with_claim else ()
    return SourceLedger(sources=(), claims=claims)


def asset_ledger(
    tmp_path: Path,
    *,
    semantic_class: str | None = None,
) -> AssetLedger:
    if semantic_class is None:
        return AssetLedger(assets=(), resolutions=())
    asset_path = tmp_path / f"{semantic_class}.png"
    asset_path.write_bytes(b"fixture")
    asset = AssetRecord(
        asset_id=f"asset.{semantic_class}",
        semantic_class=semantic_class,
        provenance_kind="client_supplied",
        source_locator="fixture",
        rights_status="cleared",
        content_hash="0" * 64,
        local_path=str(asset_path),
        pixel_width=1200,
        pixel_height=1200,
        print_width_mm=80,
        print_height_mm=80,
        allowed_face_ids=("face.05",),
    )
    return AssetLedger(
        assets=(asset,),
        resolutions=(
            AssetResolution(
                requirement_id="optional.proof",
                face_id="face.05",
                required_for_ship=False,
                code="resolved",
                asset_id=asset.asset_id,
                detail="fixture",
            ),
        ),
    )


def facts(
    *,
    overflow_region: str | None = None,
    asset_ids: tuple[str, ...] = (),
) -> FaceCompositionFacts:
    region_ids = (
        "headline",
        "narrative",
        "anchor",
        "trust_header",
        "proof_wall",
    )
    content_by_ref: dict[str, str] = {}
    regions: dict[str, RegionCompositionFacts] = {}
    for region_id in region_ids:
        ref = f"content.face.05.{region_id}"
        content_by_ref[ref] = (
            "wort " * 800 if region_id == overflow_region else "Klarer Inhalt"
        )
        regions[region_id] = RegionCompositionFacts(
            content_refs=(ref,),
            font_size_pt=32 if region_id == "headline" else 10,
            image_aspect_ratio=1.0 if region_id in {"anchor", "proof_wall"} else None,
        )
    return FaceCompositionFacts(
        face_id="face.05",
        language="de",
        content_by_ref=content_by_ref,
        regions=regions,
        asset_ids=asset_ids,
    )


def select(
    tmp_path: Path,
    *,
    current_face: FacePlan | None = None,
    current_facts: FaceCompositionFacts | None = None,
    sources: SourceLedger | None = None,
    assets: AssetLedger | None = None,
    history: tuple[str, ...] = (),
    features=None,
):
    return select_composition_for_face(
        current_face or face(),
        current_facts or facts(),
        source_ledger=sources or source_ledger(),
        asset_ledger=assets or asset_ledger(tmp_path),
        registry=load_registry(REGISTRY_PATH, atlas_path=ATLAS_PATH),
        policy=load_composition_policy(POLICY_PATH),
        family_history=history,
        font_path=FONT,
        design_features=features,
    )


def test_required_proof_absence_eliminates_evidence_family(tmp_path: Path) -> None:
    result = select(tmp_path)

    evidence = next(item for item in result.considered if item.family_id == "evidence_wall")
    assert "minimum_claim_evidence_missing" in evidence.elimination_reasons
    assert result.selected.family_id == "editorial_lead"


def test_illegal_asset_class_eliminates_a_family(tmp_path: Path) -> None:
    assets = asset_ledger(tmp_path, semantic_class="decoration")

    with pytest.raises(CompositionPlanningFailure) as caught:
        select(
            tmp_path,
            current_facts=facts(asset_ids=("asset.decoration",)),
            assets=assets,
        )

    assert "illegal_asset_class" in caught.value.elimination_codes
    assert caught.value.backtracking_signal == "return_to_assets"


def test_required_region_capacity_failure_is_not_selectable(tmp_path: Path) -> None:
    with pytest.raises(CompositionPlanningFailure) as caught:
        select(tmp_path, current_facts=facts(overflow_region="narrative"))

    assert "region_does_not_fit" in caught.value.elimination_codes
    assert caught.value.backtracking_signal == "return_to_editorial"


def test_unsupported_dominant_mechanism_is_a_hard_elimination(tmp_path: Path) -> None:
    with pytest.raises(CompositionPlanningFailure) as caught:
        select(tmp_path, current_face=face(mechanism="unsupported_magic"))

    assert caught.value.elimination_codes == ("unsupported_dominant_mechanism",)
    assert caught.value.backtracking_signal == "try_family"


def test_cadence_changes_ranking_but_never_feasibility(tmp_path: Path) -> None:
    assets = asset_ledger(tmp_path, semantic_class="proof")
    sources = source_ledger(with_claim=True)
    current_face = face(claim_ids=("claim.proof",))
    current_facts = facts(asset_ids=("asset.proof",))

    result = select(
        tmp_path,
        current_face=current_face,
        current_facts=current_facts,
        sources=sources,
        assets=assets,
        history=("editorial_lead",),
    )

    assert result.selected.family_id == "evidence_wall"
    assert all(item.feasible for item in result.considered)
    repeated = next(item for item in result.considered if item.family_id == "editorial_lead")
    assert repeated.score_components["repeat_penalty"] < 0


def test_selection_and_decision_record_are_deterministic(tmp_path: Path) -> None:
    first = select(tmp_path)
    second = select(tmp_path)

    assert first == second
    # The decision must record the version that is actually live, not a
    # version the test happened to be written against.
    registry = load_registry(REGISTRY_PATH, atlas_path=ATLAS_PATH)
    assert first.selected.family_version == next(
        family.version
        for family in registry.families
        if family.family_id == first.selected.family_id
    )
    assert first.selected.variant_id
    assert json.dumps(first.model_dump(mode="json"), sort_keys=True) == json.dumps(
        second.model_dump(mode="json"), sort_keys=True
    )


def design_features(
    *,
    energy: str,
    imagery: str,
    charts: str,
    tones: tuple[str, ...],
):
    from contracts_v3.report_plan import DesignFeaturesV3

    return DesignFeaturesV3(
        tone_tokens=tones,
        brand_energy=energy,
        imagery_density=imagery,
        chart_opportunity=charts,
    )


def proofed_selection_inputs(tmp_path: Path):
    assets = asset_ledger(tmp_path, semantic_class="proof")
    sources = source_ledger(with_claim=True)
    current_face = face(claim_ids=("claim.proof",))
    current_facts = facts(asset_ids=("asset.proof",))
    return current_face, current_facts, sources, assets


def test_design_features_change_the_selected_feasible_family(tmp_path: Path) -> None:
    current_face, current_facts, sources, assets = proofed_selection_inputs(tmp_path)

    restrained = select(
        tmp_path,
        current_face=current_face,
        current_facts=current_facts,
        sources=sources,
        assets=assets,
        features=design_features(
            energy="restrained",
            imagery="sparse",
            charts="none",
            tones=("framing", "editorial"),
        ),
    )
    expressive = select(
        tmp_path,
        current_face=current_face,
        current_facts=current_facts,
        sources=sources,
        assets=assets,
        features=design_features(
            energy="expressive",
            imagery="rich",
            charts="high",
            tones=("trust", "proof_density"),
        ),
    )

    assert all(item.feasible for item in restrained.considered)
    assert {item.family_id for item in restrained.considered} == {
        item.family_id for item in expressive.considered
    }
    assert restrained.selected.family_id == "editorial_lead"
    assert expressive.selected.family_id == "evidence_wall"


def test_every_feature_score_component_is_recorded_per_candidate(tmp_path: Path) -> None:
    result = select(
        tmp_path,
        features=design_features(
            energy="balanced",
            imagery="moderate",
            charts="low",
            tones=("framing",),
        ),
    )

    for candidate in result.considered:
        for component in (
            "tone_alignment",
            "density_fit",
            "evidence_density_fit",
            "chart_opportunity_fit",
            "asset_availability_fit",
        ):
            assert component in candidate.score_components, (
                candidate.family_id,
                component,
            )


def test_variant_selection_is_scored_not_alphabetical(tmp_path: Path) -> None:
    sparse = select(
        tmp_path,
        features=design_features(
            energy="restrained",
            imagery="sparse",
            charts="none",
            tones=("framing",),
        ),
    )
    rich = select(
        tmp_path,
        features=design_features(
            energy="expressive",
            imagery="rich",
            charts="none",
            tones=("framing",),
        ),
    )

    assert sparse.selected.family_id == "editorial_lead"
    assert rich.selected.family_id == "editorial_lead"
    assert sparse.selected.variant_id == "proof_rail"
    assert rich.selected.variant_id == "photo_bleed"
    assert sparse.variant_scores
    assert sparse.selected.variant_id in sparse.variant_scores
    assert sparse.tie_break.policy_tie_breakers == (
        "family_id",
        "family_version",
        "variant_id",
    )


def test_variant_tie_breaks_follow_the_policy_order_and_are_recorded(
    tmp_path: Path,
) -> None:
    # No design features: every variant scores zero, so the policy tie-breaker
    # (variant_id ascending) must decide and the decision must say so.
    result = select(tmp_path)

    scores = set(result.variant_scores.values())
    assert scores == {0.0}
    assert result.tie_break.applied is True
    assert result.selected.variant_id == sorted(result.variant_scores)[0]


def many_claim_inputs(tmp_path: Path, *, claim_count: int, band: str):
    sources = SourceLedger(
        sources=(),
        claims=tuple(
            Claim(
                claim_id=f"claim.{index}",
                claim_type="interpretation",
                normalized_value=f"Beleg {index}",
            )
            for index in range(claim_count)
        ),
    )
    current_face = FacePlan(
        face_id="face.05",
        face_index=5,
        role="about",
        narrative_act="authority",
        argument="Eine belastbare Positionierung",
        claim_ids=tuple(f"claim.{index}" for index in range(claim_count)),
        dominant_mechanism="editorial",
        density_band=band,
    )
    neutral = design_features(
        energy="balanced",
        imagery="moderate",
        charts="moderate",
        tones=("neutral",),
    )
    return current_face, sources, neutral


def test_density_band_alone_changes_the_selected_feasible_family(
    tmp_path: Path,
) -> None:
    assets = asset_ledger(tmp_path, semantic_class="proof")
    outcomes = {}
    for band in ("moderate", "dense"):
        current_face, sources, neutral = many_claim_inputs(
            tmp_path, claim_count=2, band=band
        )
        result = select(
            tmp_path,
            current_face=current_face,
            current_facts=facts(asset_ids=("asset.proof",)),
            sources=sources,
            assets=assets,
            features=neutral,
        )
        assert all(item.feasible for item in result.considered), band
        outcomes[band] = result.selected.family_id

    assert outcomes["moderate"] == "evidence_wall"
    assert outcomes["dense"] == "editorial_lead"


def test_evidence_density_alone_changes_the_selected_feasible_family(
    tmp_path: Path,
) -> None:
    assets = asset_ledger(tmp_path, semantic_class="proof")
    outcomes = {}
    for claim_count in (2, 6):
        current_face, sources, neutral = many_claim_inputs(
            tmp_path, claim_count=claim_count, band="dense"
        )
        result = select(
            tmp_path,
            current_face=current_face,
            current_facts=facts(asset_ids=("asset.proof",)),
            sources=sources,
            assets=assets,
            features=neutral,
        )
        assert all(item.feasible for item in result.considered), claim_count
        outcomes[claim_count] = result.selected.family_id

    assert outcomes[2] == "editorial_lead"
    assert outcomes[6] == "evidence_wall"


def test_asset_availability_alone_changes_the_selected_family(tmp_path: Path) -> None:
    proof_features = design_features(
        energy="expressive",
        imagery="rich",
        charts="high",
        tones=("trust", "proof_density"),
    )
    sources = source_ledger(with_claim=True)
    current_face = face(claim_ids=("claim.proof",))

    with_assets = select(
        tmp_path,
        current_face=current_face,
        current_facts=facts(asset_ids=("asset.proof",)),
        sources=sources,
        assets=asset_ledger(tmp_path, semantic_class="proof"),
        features=proof_features,
    )
    without_assets = select(
        tmp_path,
        current_face=current_face,
        current_facts=facts(),
        sources=sources,
        assets=asset_ledger(tmp_path),
        features=proof_features,
    )

    assert with_assets.selected.family_id == "evidence_wall"
    assert without_assets.selected.family_id == "editorial_lead"
    starved = next(
        item
        for item in without_assets.considered
        if item.family_id == "evidence_wall"
    )
    assert "minimum_asset_evidence_missing" in starved.elimination_reasons


def test_unsupported_fact_regions_never_change_the_decision(tmp_path: Path) -> None:
    baseline = select(tmp_path)
    padded_facts = facts()
    padded = padded_facts.model_copy(
        update={
            "content_by_ref": {
                **padded_facts.content_by_ref,
                "content.face.05.off_grid": "Nicht deklarierte Region",
            },
            "regions": {
                **padded_facts.regions,
                "off_grid": RegionCompositionFacts(
                    content_refs=("content.face.05.off_grid",),
                    font_size_pt=10,
                ),
            },
        }
    )

    padded_result = select(tmp_path, current_facts=padded)

    assert padded_result.selected == baseline.selected
    assert padded_result.considered == baseline.considered


def test_identical_features_are_deterministic_and_different_features_diverge(
    tmp_path: Path,
) -> None:
    quiet = design_features(
        energy="restrained", imagery="sparse", charts="none", tones=("framing",)
    )
    loud = design_features(
        energy="expressive", imagery="rich", charts="high", tones=("trust",)
    )

    first = select(tmp_path, features=quiet)
    second = select(tmp_path, features=quiet)
    other = select(tmp_path, features=loud)

    assert first == second
    assert (
        first.selected != other.selected
        or first.variant_scores != other.variant_scores
    )


def test_face_density_band_steers_the_editorial_variant(tmp_path: Path) -> None:
    """Dense faces choose the text-led variant; light faces the photo-led one.

    Richard's corpus shows both editorial modes: photo-led pages around 300
    words and text-led pages up to 529. The band is the honest selector.
    """
    rich = design_features(
        energy="expressive", imagery="rich", charts="none", tones=("framing",)
    )

    def run(band: str):
        current_face = FacePlan(
            face_id="face.05",
            face_index=5,
            role="about",
            narrative_act="authority",
            argument="Eine belastbare Positionierung",
            dominant_mechanism="editorial",
            density_band=band,
        )
        return select(
            tmp_path,
            current_face=current_face,
            features=rich,
        )

    light = run("light")
    dense = run("dense")

    assert light.selected.family_id == "editorial_lead"
    assert dense.selected.family_id == "editorial_lead"
    assert light.selected.variant_id == "photo_bleed"
    assert dense.selected.variant_id == "proof_rail"
