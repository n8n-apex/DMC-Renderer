from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PREPROCESSOR_ROOT = ROOT / "research" / "preprocessor"
QUALITY_ROOT = ROOT / "research" / "quality_loop"
for path in (PREPROCESSOR_ROOT, QUALITY_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from contracts_v3.asset_ledger import AssetLedger  # noqa: E402
from contracts_v3.report_plan import (  # noqa: E402
    AssetRequirement,
    FacePlan,
    NarrativeRole,
    ProductProfile,
    ReportPlanV3,
)
from contracts_v3.render_contract import FrozenRenderContractV3  # noqa: E402
from contracts_v3.source_ledger import GroundingFailure, SourceLedger  # noqa: E402
from contracts_v3.units import DocumentUnits  # noqa: E402
from gates.assets_v3 import check_assets_v3  # noqa: E402
from gates.evidence_v3 import check_evidence_v3  # noqa: E402
from gates.structure_v3 import PdfPageFact, check_structure_v3  # noqa: E402
from stages.build_asset_ledger_v3 import build_asset_ledger_v3  # noqa: E402


def plan(
    *,
    formats: tuple[str, ...] = ("a4", "a4"),
    roles: tuple[str, ...] = ("cover", "cta"),
) -> ReportPlanV3:
    units = DocumentUnits.from_formats(formats)
    faces = tuple(
        FacePlan(
            face_id=face_id,
            face_index=index,
            role=roles[index - 1],
            narrative_act="act",
            argument="argument",
            dominant_mechanism="editorial",
            density_band="moderate",
        )
        for index, face_id in enumerate(
            (face_id for allocation in units.allocations for face_id in allocation.face_ids),
            start=1,
        )
    )
    return ReportPlanV3(
        product_profile_id="test-profile",
        units=units,
        faces=faces,
        audience="audience",
        central_thesis="thesis",
        promise="promise",
        tone_profile="tone",
    )


def profile(
    *,
    face_count: int = 2,
    case_count: int = 0,
    required_roles: tuple[str, ...] = ("cover", "cta"),
) -> ProductProfile:
    return ProductProfile.model_construct(
        profile_id="test-profile",
        face_count=face_count,
        case_count=case_count,
        min_theory_faces=0,
        required_roles=tuple(NarrativeRole(role) for role in required_roles),
        require_trust_evidence=False,
        cover_must_be_first=True,
        cta_must_be_last=True,
        exception_policy="none",
    )


def contract_for(current_plan: ReportPlanV3) -> FrozenRenderContractV3:
    fragments = []
    content_refs = []
    for allocation in current_plan.units.allocations:
        elements = []
        for face_id in allocation.face_ids:
            content_ref = f"content.{face_id}.title"
            content_refs.append(content_ref)
            elements.append(
                {
                    "kind": "heading",
                    "element_id": f"{face_id}.heading.01",
                    "region_id": "headline",
                    "content_ref": content_ref,
                    "level": 1,
                    "required_visibility": True,
                }
            )
        element_ids = [item["element_id"] for item in elements]
        fragments.append(
            {
                "fragment_id": allocation.fragment_id,
                "format": allocation.format.value,
                "face_ids": list(allocation.face_ids),
                "composition": {
                    "family_id": "editorial_lead",
                    "family_version": "1.0.0",
                    "variant_id": "proof_rail",
                    "theme_id": "light",
                },
                "elements": elements,
                "region_assignments": [
                    {"region_id": "headline", "element_ids": element_ids}
                ],
                "expected_materialization": {
                    "required_element_ids": element_ids,
                    "minimum_font_pt": {item: 28 for item in element_ids},
                },
            }
        )
    return FrozenRenderContractV3.model_validate(
        {
            "contract_id": "contract.structure",
            "mode": "ship",
            "product_profile_id": current_plan.product_profile_id,
            "fragments": fragments,
            "content_refs": content_refs,
            "claim_refs": [],
            "asset_refs": [],
            "artifact_hashes": {"contract_payload": "a" * 64},
        }
    )


def codes(failures) -> tuple[str, ...]:
    return tuple(item.code for item in failures)


def test_structure_gate_names_wrong_face_fragment_and_pdf_object_counts() -> None:
    current_plan = plan()
    contract = contract_for(current_plan).model_copy(
        update={"fragments": contract_for(current_plan).fragments[:1]}
    )

    failures = check_structure_v3(
        current_plan,
        contract,
        profile(face_count=3),
        (PdfPageFact(width_mm=210, height_mm=297),),
    )

    assert {"wrong_face_count", "wrong_fragment_count", "wrong_pdf_object_count"} <= set(codes(failures))


def test_structure_gate_rejects_malformed_a3_and_unsupported_page_size() -> None:
    current_plan = plan(formats=("a3",), roles=("cover", "cta"))

    malformed = check_structure_v3(
        current_plan,
        contract_for(current_plan),
        profile(),
        (PdfPageFact(width_mm=210, height_mm=297),),
    )
    unsupported = check_structure_v3(
        plan(),
        contract_for(plan()),
        profile(),
        (
            PdfPageFact(width_mm=200, height_mm=200),
            PdfPageFact(width_mm=210, height_mm=297),
        ),
    )

    assert "malformed_a3_allocation" in codes(malformed)
    assert "unsupported_pdf_page_size" in codes(unsupported)


def test_structure_gate_checks_case_count_and_stable_roles() -> None:
    current_plan = plan()

    failures = check_structure_v3(
        current_plan,
        contract_for(current_plan),
        profile(case_count=1, required_roles=("cover", "about", "cta")),
        (
            PdfPageFact(width_mm=210, height_mm=297),
            PdfPageFact(width_mm=210, height_mm=297),
        ),
    )

    assert "wrong_case_count" in codes(failures)
    assert "required_role_missing" in codes(failures)


def test_evidence_gate_blocks_ungrounded_83_percent_and_missing_appendix() -> None:
    source_ledger = SourceLedger(
        sources=(),
        claims=(),
        grounding_failures=(
            GroundingFailure(
                code="ungrounded_numeric_candidate",
                token="83%",
                content_path="report_json.pages[3].data.result",
                detail="numeric token has no grounded claim",
            ),
        ),
    )
    current_contract = contract_for(plan()).model_copy(
        update={"claim_refs": ("claim.expected",)}
    )

    failures = check_evidence_v3(
        current_contract,
        source_ledger,
        source_appendix=None,
    )

    assert "ungrounded_numeric_candidate" in codes(failures)
    assert "ungrounded_claim" in codes(failures)
    assert "source_appendix_missing" in codes(failures)


def test_five_missing_case_portraits_are_five_blocking_asset_failures() -> None:
    faces = tuple(
        FacePlan(
            face_id=f"face.{index:02d}",
            face_index=index,
            role="case_study",
            narrative_act="case",
            argument="case",
            asset_requirements=(
                AssetRequirement(
                    requirement_id=f"face.{index:02d}.identity",
                    semantic_class="identity",
                    required_for_ship=True,
                ),
            ),
            dominant_mechanism="case_narrative",
            density_band="moderate",
            case_id=f"case.{index}",
        )
        for index in range(1, 6)
    )
    current_plan = ReportPlanV3(
        product_profile_id="test-profile",
        units=DocumentUnits.from_formats(["a4"] * 5),
        faces=faces,
        audience="audience",
        central_thesis="thesis",
        promise="promise",
        tone_profile="tone",
    )
    ledger = build_asset_ledger_v3({"assets": []}, current_plan)

    failures = check_assets_v3(current_plan, ledger, contract=None)

    assert codes(failures).count("missing_required_asset") == 5
    assert all(item.owner_stage.value == "assets" for item in failures)
