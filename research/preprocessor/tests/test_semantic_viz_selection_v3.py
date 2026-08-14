"""Data visualization is selected by claim relationship, never decoration."""

from __future__ import annotations

from pathlib import Path

import hashlib

from composition_registry.registry import load_registry
from contracts_v3.asset_ledger import AssetLedger
from contracts_v3.report_plan import FacePlan, ReportPlanV3
from contracts_v3.source_ledger import (
    Claim,
    Computation,
    SourceItem,
    SourceLedger,
    SourceSpan,
)
from contracts_v3.units import DocumentUnits
from stages.materialize_render_contract_v3 import materialize_render_contract_v3
from stages.plan_compositions_v3 import (
    CompositionPlanV3,
    FaceCompositionDecision,
    FaceCompositionFacts,
    RegionCompositionFacts,
    SelectedComposition,
)


ROOT = Path(__file__).resolve().parents[3]
REGISTRY_PATH = (
    ROOT / "research" / "composition_registry" / "families" / "dmc-v1.json"
)
ATLAS_PATH = ROOT / "research" / "reference-atlas" / "reference-atlas.json"


SOURCE_TEXT = (
    "Die Bearbeitung dauerte 120 Minuten und liegt nun bei 20 Minuten. "
    "Anfragen je Quartal: 12 Anfragen, 19 Anfragen, 27 Anfragen. "
    "Der Betrieb umfasst 7 Standorte."
)


def span(verbatim: str) -> SourceSpan:
    start = SOURCE_TEXT.index(verbatim)
    return SourceSpan(
        source_id="source.fixture",
        start=start,
        end=start + len(verbatim),
        verbatim=verbatim,
    )


def grounded(claim_id: str, value: str, **kwargs) -> Claim:
    return Claim(
        claim_id=claim_id,
        claim_type="number",
        normalized_value=value,
        source_ids=("source.fixture",),
        source_spans=(span(value),),
        **kwargs,
    )


def ledger() -> SourceLedger:
    source = SourceItem(
        source_id="source.fixture",
        source_kind="document",
        locator="fixture.txt",
        captured_at="2026-08-05T09:30:00+00:00",
        content_hash=hashlib.sha256(SOURCE_TEXT.encode("utf-8")).hexdigest(),
        rights_status="client_authorized",
        verbatim_text=SOURCE_TEXT,
        language="de",
        allowed_uses=("report",),
    )
    return SourceLedger(
        sources=(source,),
        claims=(
            grounded("claim.before", "120 Minuten", unit="minute"),
            grounded("claim.after", "20 Minuten", unit="minute"),
            Claim(
                claim_id="claim.saved",
                claim_type="number",
                normalized_value="100 Minuten",
                unit="minute",
                computation=Computation(
                    formula="before - after",
                    operand_claim_ids=("claim.before", "claim.after"),
                ),
            ),
            grounded(
                "claim.q1", "12 Anfragen", entity_scope="anfragen", time_scope="2025-Q1"
            ),
            grounded(
                "claim.q2", "19 Anfragen", entity_scope="anfragen", time_scope="2025-Q2"
            ),
            grounded(
                "claim.q3", "27 Anfragen", entity_scope="anfragen", time_scope="2025-Q3"
            ),
            grounded("claim.lonely", "7 Standorte"),
        ),
    )


def single_case_fixture(claim_ids: tuple[str, ...]):
    units = DocumentUnits.from_formats(["a4"])
    face = FacePlan(
        face_id="face.01",
        face_index=1,
        role="case_study",
        narrative_act="proof",
        argument="Die dokumentierte Transformation",
        claim_ids=claim_ids,
        dominant_mechanism="proof",
        density_band="moderate",
        case_id="case.01",
    )
    plan = ReportPlanV3(
        product_profile_id="dmc_house_20_face",
        units=units,
        faces=(face,),
        audience="German B2B founder",
        central_thesis="A clear thesis",
        promise="A grounded promise",
        tone_profile="Richard house",
    )
    composition_plan = CompositionPlanV3(
        registry_version=registry_version(),
        policy_id="dmc-composition-scoring",
        policy_version="1.0.0",
        decisions=(
            FaceCompositionDecision(
                face_id="face.01",
                considered=(),
                selected=SelectedComposition(
                    family_id="case_narrative",
                    family_version=family_version("case_narrative"),
                    variant_id="right_rail",
                    policy_id="dmc-composition-scoring",
                    policy_version="1.0.0",
                ),
            ),
        ),
    )
    story_heading = "content.face.01.story.heading"
    story_body = "content.face.01.story.body"
    rail_label = "content.face.01.rail.label"
    facts = {
        "face.01": FaceCompositionFacts(
            face_id="face.01",
            language="de",
            content_by_ref={
                story_heading: "Vom Rückstand zur Routine",
                story_body: "Die Bearbeitung ist dokumentiert und reproduzierbar.",
                rail_label: "Dokumentierte Bearbeitungszeit",
            },
            regions={
                "case_story": RegionCompositionFacts(
                    content_refs=(story_heading, story_body),
                    font_size_pt=10,
                ),
                "evidence_rail": RegionCompositionFacts(
                    content_refs=(rail_label,),
                    font_size_pt=10,
                ),
            },
        )
    }
    return plan, composition_plan, facts


def materialize(claim_ids: tuple[str, ...]):
    plan, composition_plan, facts = single_case_fixture(claim_ids)
    return materialize_render_contract_v3(
        plan,
        composition_plan,
        facts,
        source_ledger=ledger(),
        asset_ledger=AssetLedger(assets=(), resolutions=()),
        registry=load_registry(REGISTRY_PATH, atlas_path=ATLAS_PATH),
        mode="ship",
        theme_id="light",
        artifact_hashes={"contract_payload": "a" * 64},
    )


def elements_by_kind(contract):
    kinds: dict[str, list] = {}
    for fragment in contract.fragments:
        for element in fragment.elements:
            kinds.setdefault(element.kind, []).append(element)
    return kinds


def test_computed_difference_becomes_grouped_comparison_not_stat() -> None:
    contract = materialize(("claim.before", "claim.after", "claim.saved"))
    kinds = elements_by_kind(contract)

    comparison = kinds["grouped_comparison"][0]
    assert comparison.before_claim_id == "claim.before"
    assert comparison.after_claim_id == "claim.after"
    assert comparison.result_claim_id == "claim.saved"
    rendered_stat_claims = {
        element.claim_id for element in kinds.get("stat", ())
    }
    assert not {
        "claim.before",
        "claim.after",
        "claim.saved",
    } & rendered_stat_claims


def test_entity_scoped_time_claims_become_a_time_series() -> None:
    contract = materialize(("claim.q1", "claim.q2", "claim.q3"))
    kinds = elements_by_kind(contract)

    series = kinds["time_series"][0]
    assert series.point_claim_ids == ("claim.q1", "claim.q2", "claim.q3")
    assert "stat" not in kinds or not {
        "claim.q1",
        "claim.q2",
        "claim.q3",
    } & {element.claim_id for element in kinds["stat"]}


def test_shapeless_claim_stays_a_plain_stat() -> None:
    contract = materialize(("claim.lonely",))
    kinds = elements_by_kind(contract)

    assert "grouped_comparison" not in kinds
    assert "formula_ladder" not in kinds
    assert "time_series" not in kinds
    assert kinds["stat"][0].claim_id == "claim.lonely"


def test_viz_claims_satisfy_declared_references() -> None:
    contract = materialize(("claim.before", "claim.after", "claim.saved"))

    assert {"claim.before", "claim.after", "claim.saved"} <= set(contract.claim_refs)


def trust_wall_fixture(*, logo_count: int, quote_claims: tuple[str, ...]):
    units = DocumentUnits.from_formats(["a4"])
    face = FacePlan(
        face_id="face.01",
        face_index=1,
        role="trust_proof",
        narrative_act="trust",
        argument="Dokumentiertes Vertrauen",
        claim_ids=quote_claims,
        dominant_mechanism="evidence_wall",
        density_band="moderate",
    )
    plan = ReportPlanV3(
        product_profile_id="dmc_house_20_face",
        units=units,
        faces=(face,),
        audience="German B2B founder",
        central_thesis="A clear thesis",
        promise="A grounded promise",
        tone_profile="Richard house",
    )
    composition_plan = CompositionPlanV3(
        registry_version=registry_version(),
        policy_id="dmc-composition-scoring",
        policy_version="1.0.0",
        decisions=(
            FaceCompositionDecision(
                face_id="face.01",
                considered=(),
                selected=SelectedComposition(
                    family_id="evidence_wall",
                    family_version=family_version("evidence_wall"),
                    variant_id="logo_wall",
                    policy_id="dmc-composition-scoring",
                    policy_version="1.0.0",
                ),
            ),
        ),
    )
    header_ref = "content.face.01.header"
    wall_label = "content.face.01.wall.label"
    quote_a = "content.face.01.wall.quote_a"
    quote_b = "content.face.01.wall.quote_b"
    facts = {
        "face.01": FaceCompositionFacts(
            face_id="face.01",
            language="de",
            content_by_ref={
                header_ref: "Vertrauen aus dokumentierter Arbeit",
                wall_label: "Kunden und Partner",
                quote_a: "Die Umstellung lief ohne Ausfall.",
                quote_b: "Die Zahlen stimmen jede Woche.",
            },
            regions={
                "trust_header": RegionCompositionFacts(
                    content_refs=(header_ref,),
                    font_size_pt=12,
                ),
                "proof_wall": RegionCompositionFacts(
                    content_refs=(wall_label, quote_a, quote_b),
                    font_size_pt=10,
                ),
            },
            asset_ids=tuple(f"asset.logo.{index}" for index in range(logo_count)),
        )
    }
    return plan, composition_plan, facts


def trust_ledger() -> SourceLedger:
    text = (
        "Die Umstellung lief ohne Ausfall. Die Zahlen stimmen jede Woche. "
        "Dokumentierte Vertrauensbasis."
    )
    source = SourceItem(
        source_id="source.trust",
        source_kind="interview",
        locator="reviews.txt",
        captured_at="2026-08-05T09:30:00+00:00",
        content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        rights_status="client_authorized",
        verbatim_text=text,
        language="de",
        allowed_uses=("report", "quotation"),
    )
    def quote(claim_id: str, value: str) -> Claim:
        start = text.index(value)
        return Claim(
            claim_id=claim_id,
            claim_type="quote",
            normalized_value=value,
            source_ids=("source.trust",),
            source_spans=(
                SourceSpan(
                    source_id="source.trust",
                    start=start,
                    end=start + len(value),
                    verbatim=value,
                ),
            ),
        )
    return SourceLedger(
        sources=(source,),
        claims=(
            quote("claim.review_a", "Die Umstellung lief ohne Ausfall."),
            quote("claim.review_b", "Die Zahlen stimmen jede Woche."),
        ),
    )


def trust_assets(logo_count: int, tmp_path: Path) -> AssetLedger:
    from contracts_v3.asset_ledger import AssetRecord

    assets = []
    for index in range(logo_count):
        path = tmp_path / f"logo{index}.png"
        path.write_bytes(b"logo-fixture")
        assets.append(
            AssetRecord(
                asset_id=f"asset.logo.{index}",
                semantic_class="logo",
                provenance_kind="client_supplied",
                source_locator="client-brand-kit",
                rights_status="cleared",
                content_hash=hashlib.sha256(b"logo-fixture").hexdigest(),
                local_path=str(path),
                pixel_width=600,
                pixel_height=300,
                print_width_mm=40,
                print_height_mm=20,
                allowed_face_ids=("face.01",),
            )
        )
    return AssetLedger(assets=tuple(assets), resolutions=())


def materialize_trust(tmp_path: Path, *, logo_count: int, quote_claims: tuple[str, ...]):
    plan, composition_plan, facts = trust_wall_fixture(
        logo_count=logo_count, quote_claims=quote_claims
    )
    return materialize_render_contract_v3(
        plan,
        composition_plan,
        facts,
        source_ledger=trust_ledger(),
        asset_ledger=trust_assets(logo_count, tmp_path),
        registry=load_registry(REGISTRY_PATH, atlas_path=ATLAS_PATH),
        mode="ship",
        theme_id="light",
        artifact_hashes={"contract_payload": "a" * 64},
    )


def test_three_or_more_logos_group_into_one_logo_wall(tmp_path: Path) -> None:
    contract = materialize_trust(
        tmp_path, logo_count=4, quote_claims=("claim.review_a", "claim.review_b")
    )
    kinds = elements_by_kind(contract)

    wall = kinds["logo_wall"][0]
    assert set(wall.asset_ids) == {f"asset.logo.{index}" for index in range(4)}
    rendered_images = {
        element.asset_id for element in kinds.get("image", ())
    }
    assert not rendered_images & set(wall.asset_ids)


def test_two_grounded_quote_claims_become_a_proof_wall(tmp_path: Path) -> None:
    contract = materialize_trust(
        tmp_path, logo_count=3, quote_claims=("claim.review_a", "claim.review_b")
    )
    kinds = elements_by_kind(contract)

    wall = kinds["proof_wall"][0]
    assert set(wall.claim_ids) == {"claim.review_a", "claim.review_b"}
    assert len(wall.quote_content_refs) == 2


def test_fewer_than_three_logos_stay_individual_images(tmp_path: Path) -> None:
    contract = materialize_trust(
        tmp_path, logo_count=2, quote_claims=("claim.review_a", "claim.review_b")
    )
    kinds = elements_by_kind(contract)

    assert "logo_wall" not in kinds
    assert len(kinds.get("image", ())) == 2


def registry_version() -> str:
    """The live registry version, so fixtures cannot pin a stale one."""
    return load_registry(REGISTRY_PATH, atlas_path=ATLAS_PATH).version


def family_version(family_id: str) -> str:
    """The live version of one family; families move independently."""
    registry = load_registry(REGISTRY_PATH, atlas_path=ATLAS_PATH)
    return next(
        family.version
        for family in registry.families
        if family.family_id == family_id
    )
