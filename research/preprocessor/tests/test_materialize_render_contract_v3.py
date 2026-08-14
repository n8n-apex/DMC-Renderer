from __future__ import annotations

from pathlib import Path

import pytest

from composition_registry.registry import load_registry
from contracts_v3.asset_ledger import AssetLedger
from contracts_v3.report_plan import FacePlan, ReportPlanV3
from contracts_v3.source_ledger import SourceLedger
from contracts_v3.units import DocumentUnits
from stages.materialize_render_contract_v3 import (
    ContractMaterializationFailure,
    materialize_render_contract_v3,
)
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


def twenty_face_fixture() -> tuple[
    ReportPlanV3,
    CompositionPlanV3,
    dict[str, FaceCompositionFacts],
]:
    formats = ["a4"] * 9 + ["a3"] + ["a4"] * 9
    units = DocumentUnits.from_formats(formats)
    faces = tuple(
        FacePlan(
            face_id=f"face.{index:02d}",
            face_index=index,
            role="theory",
            narrative_act="interpretation",
            argument=f"Argument {index}",
            dominant_mechanism="interpretation",
            density_band="moderate",
        )
        for index in range(1, 21)
    )
    plan = ReportPlanV3(
        product_profile_id="dmc_house_20_face",
        units=units,
        faces=faces,
        audience="German B2B founder",
        central_thesis="A clear thesis",
        promise="A grounded promise",
        tone_profile="Richard house",
    )
    selection = SelectedComposition(
        family_id="theory_interpretation",
        family_version=family_version("theory_interpretation"),
        variant_id="comparison_band",
        policy_id="dmc-composition-scoring",
        policy_version="1.0.0",
    )
    composition_plan = CompositionPlanV3(
        registry_version=registry_version(),
        policy_id="dmc-composition-scoring",
        policy_version="1.0.0",
        decisions=tuple(
            FaceCompositionDecision(
                face_id=face.face_id,
                considered=(),
                selected=selection,
            )
            for face in faces
        ),
    )
    facts: dict[str, FaceCompositionFacts] = {}
    for face in faces:
        principle_heading = f"content.{face.face_id}.principle.heading"
        principle_body = f"content.{face.face_id}.principle.body"
        mechanism_a = f"content.{face.face_id}.mechanism.a"
        mechanism_b = f"content.{face.face_id}.mechanism.b"
        facts[face.face_id] = FaceCompositionFacts(
            face_id=face.face_id,
            language="de",
            content_by_ref={
                principle_heading: "Ein belastbares Prinzip",
                principle_body: "Die Interpretation bleibt klar und überprüfbar.",
                mechanism_a: "Ausgangslage",
                mechanism_b: "Wirkung",
            },
            regions={
                "principle": RegionCompositionFacts(
                    content_refs=(principle_heading, principle_body),
                    font_size_pt=10,
                ),
                "mechanism": RegionCompositionFacts(
                    content_refs=(mechanism_a, mechanism_b),
                    font_size_pt=10,
                    list_item_count=2,
                ),
            },
        )
    return plan, composition_plan, facts


def hashes() -> dict[str, str]:
    return {
        "source_ledger": "a" * 64,
        "report_plan": "b" * 64,
        "asset_ledger": "c" * 64,
        "family_registry": "d" * 64,
        "composition_policy": "e" * 64,
    }


def materialize():
    plan, composition_plan, facts = twenty_face_fixture()
    return materialize_render_contract_v3(
        plan,
        composition_plan,
        facts,
        source_ledger=SourceLedger(sources=(), claims=()),
        asset_ledger=AssetLedger(assets=(), resolutions=()),
        registry=load_registry(REGISTRY_PATH, atlas_path=ATLAS_PATH),
        mode="ship",
        theme_id="light",
        artifact_hashes=hashes(),
    )


def test_all_twenty_faces_and_a3_spread_are_accounted_for() -> None:
    contract = materialize()

    assert len(contract.fragments) == 19
    assert sum(len(fragment.face_ids) for fragment in contract.fragments) == 20
    assert contract.fragments[9].format == "a3"
    assert contract.fragments[9].face_ids == ("face.10", "face.11")


def test_element_ids_and_contract_hash_are_stable() -> None:
    first = materialize()
    second = materialize()

    assert first == second
    assert first.contract_id == second.contract_id
    assert first.artifact_hashes["contract_payload"] == second.artifact_hashes[
        "contract_payload"
    ]
    element_ids = [
        element.element_id
        for fragment in first.fragments
        for element in fragment.elements
    ]
    assert len(element_ids) == len(set(element_ids))


def test_contract_contains_references_not_source_copy() -> None:
    contract = materialize()
    serialized = contract.model_dump_json()

    assert "Die Interpretation bleibt klar" not in serialized
    assert all(ref.startswith("content.face.") for ref in contract.content_refs)


def test_numeric_copy_without_claim_id_is_rejected() -> None:
    plan, composition_plan, facts = twenty_face_fixture()
    first = facts["face.01"]
    changed_content = dict(first.content_by_ref)
    changed_content["content.face.01.mechanism.a"] = "83 Prozent schneller"
    facts["face.01"] = first.model_copy(update={"content_by_ref": changed_content})

    with pytest.raises(ContractMaterializationFailure) as caught:
        materialize_render_contract_v3(
            plan,
            composition_plan,
            facts,
            source_ledger=SourceLedger(sources=(), claims=()),
            asset_ledger=AssetLedger(assets=(), resolutions=()),
            registry=load_registry(REGISTRY_PATH, atlas_path=ATLAS_PATH),
            mode="ship",
            theme_id="light",
            artifact_hashes=hashes(),
        )

    assert caught.value.code == "numeric_content_without_claim"
    assert caught.value.face_ids == ("face.01",)


def test_a_spread_records_each_half_of_the_sheet_separately() -> None:
    """A sheet may pair two compositions, as 28 of 36 reference spreads do.

    The fragment still names one leading composition, and it must be the
    left face's own, so nothing downstream can read a spread as uniform.
    """
    plan, composition_plan, facts = twenty_face_fixture()
    decisions = list(composition_plan.decisions)
    decisions[10] = decisions[10].model_copy(
        update={
            "selected": decisions[10].selected.model_copy(
                update={"variant_id": "diagram_split"}
            )
        }
    )

    contract = materialize_render_contract_v3(
        plan,
        composition_plan.model_copy(update={"decisions": tuple(decisions)}),
        facts,
        source_ledger=SourceLedger(sources=(), claims=()),
        asset_ledger=AssetLedger(assets=(), resolutions=()),
        registry=load_registry(REGISTRY_PATH, atlas_path=ATLAS_PATH),
        mode="ship",
        theme_id="light",
        artifact_hashes=hashes(),
    )

    spreads = [fragment for fragment in contract.fragments if fragment.format == "a3"]
    assert spreads
    for fragment in spreads:
        assert len(fragment.face_compositions) == len(fragment.face_ids)
        assert fragment.face_compositions[0] == fragment.composition
    assert any(
        fragment.face_compositions[0].variant_id
        != fragment.face_compositions[1].variant_id
        for fragment in spreads
    )


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
