"""Task 8: every risky rendered token binds to claim, span, and element."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


HERE = Path(__file__).resolve().parent
RESEARCH_ROOT = HERE.parents[2] / "research"
PREPROCESSOR_ROOT = RESEARCH_ROOT / "preprocessor"
for path in (RESEARCH_ROOT, PREPROCESSOR_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from contracts_v3.render_contract import FrozenRenderContractV3  # noqa: E402
from contracts_v3.source_ledger import (  # noqa: E402
    Claim,
    Computation,
    SourceAppendixV3,
    SourceLedger,
)
from quality_loop.gates.evidence_v3 import check_evidence_v3  # noqa: E402


def contract_with_viz(claim_refs: tuple[str, ...]) -> FrozenRenderContractV3:
    return FrozenRenderContractV3.model_validate(
        {
            "schema_version": "3.0",
            "contract_id": "contract.binding",
            "mode": "ship",
            "product_profile_id": "dmc_house_20_face",
            "fragments": [
                {
                    "fragment_id": "fragment.01",
                    "format": "a4",
                    "face_ids": ["face.01"],
                    "composition": {
                        "family_id": "case_narrative",
                        "family_version": "1.1.0",
                        "variant_id": "right_rail",
                        "theme_id": "light",
                    },
                    "elements": [
                        {
                            "kind": "grouped_comparison",
                            "element_id": "face.01.evidence_rail.grouped_comparison.01",
                            "region_id": "evidence_rail",
                            "before_claim_id": "claim.before",
                            "after_claim_id": "claim.after",
                            "result_claim_id": "claim.saved",
                            "label_content_ref": "content.face.01.label",
                            "required_visibility": True,
                        }
                    ],
                    "region_assignments": [
                        {
                            "region_id": "evidence_rail",
                            "element_ids": [
                                "face.01.evidence_rail.grouped_comparison.01"
                            ],
                        }
                    ],
                    "expected_materialization": {
                        "required_element_ids": [
                            "face.01.evidence_rail.grouped_comparison.01"
                        ],
                        "minimum_font_pt": {},
                    },
                }
            ],
            "content_refs": ["content.face.01.label"],
            "claim_refs": sorted(claim_refs),
            "asset_refs": [],
            "artifact_hashes": {"contract_payload": "a" * 64},
        }
    )


def spanless_claim(claim_id: str, value: str) -> Claim:
    return Claim.model_construct(
        claim_id=claim_id,
        claim_type="number",
        normalized_value=value,
        unit=None,
        time_scope=None,
        entity_scope=None,
        source_ids=(),
        source_spans=(),
        computation=None,
        confidence=1.0,
        allowed_uses=(),
    )


def appendix(source_ids: tuple[str, ...]) -> SourceAppendixV3:
    return SourceAppendixV3(
        entries=tuple(
            {"source_id": source_id, "citation_text": f"(Quelle {index}, 2026)"}
            for index, source_id in enumerate(source_ids, start=1)
        )
    )


def test_viz_element_claims_are_traced_to_their_element_ids() -> None:
    contract = contract_with_viz(("claim.before", "claim.after", "claim.saved"))
    failures = check_evidence_v3(
        contract,
        SourceLedger(sources=(), claims=()),
        source_appendix=appendix(()),
    )

    ungrounded = [f for f in failures if f.code == "ungrounded_claim"]
    assert len(ungrounded) == 3
    for failure in ungrounded:
        assert "face.01.evidence_rail.grouped_comparison.01" in failure.element_ids


def test_rendered_claim_without_source_span_or_computation_fails() -> None:
    contract = contract_with_viz(("claim.before", "claim.after", "claim.saved"))
    ledger = SourceLedger.model_construct(
        schema_version="3.0",
        sources=(),
        claims=(
            spanless_claim("claim.before", "120 Minuten"),
            spanless_claim("claim.after", "20 Minuten"),
            spanless_claim("claim.saved", "100 Minuten"),
        ),
        grounding_failures=(),
    )

    failures = check_evidence_v3(
        contract,
        ledger,
        source_appendix=appendix(()),
    )

    spanless = [f for f in failures if f.code == "claim_missing_source_span"]
    assert len(spanless) == 3
    assert all(
        "face.01.evidence_rail.grouped_comparison.01" in failure.element_ids
        for failure in spanless
    )


def test_computed_claim_with_grounded_operands_carries_no_span_failure() -> None:
    contract = contract_with_viz(("claim.before", "claim.after", "claim.saved"))
    saved = Claim(
        claim_id="claim.saved",
        claim_type="number",
        normalized_value="100 Minuten",
        computation=Computation(
            formula="before - after",
            operand_claim_ids=("claim.before", "claim.after"),
        ),
    )
    ledger = SourceLedger.model_construct(
        schema_version="3.0",
        sources=(),
        claims=(saved,),
        grounding_failures=(),
    )

    failures = check_evidence_v3(contract, ledger, source_appendix=appendix(()))

    assert not [f for f in failures if f.code == "claim_missing_source_span"]


def test_source_appendix_must_cover_every_rendered_source() -> None:
    contract = contract_with_viz(("claim.before", "claim.after", "claim.saved"))
    saved = Claim.model_construct(
        claim_id="claim.saved",
        claim_type="number",
        normalized_value="100 Minuten",
        unit=None,
        time_scope=None,
        entity_scope=None,
        source_ids=("source.a", "source.b"),
        source_spans=(),
        computation=Computation(
            formula="before - after",
            operand_claim_ids=("claim.before", "claim.after"),
        ),
        confidence=1.0,
        allowed_uses=(),
    )
    ledger = SourceLedger.model_construct(
        schema_version="3.0",
        sources=(),
        claims=(saved,),
        grounding_failures=(),
    )

    incomplete = check_evidence_v3(
        contract,
        ledger,
        source_appendix=appendix(("source.a",)),
    )
    assert any(f.code == "source_appendix_incomplete" for f in incomplete)

    complete = check_evidence_v3(
        contract,
        ledger,
        source_appendix=appendix(("source.a", "source.b")),
    )
    assert not any(
        f.code in {"source_appendix_incomplete", "source_appendix_missing"}
        for f in complete
    )


def test_source_content_hash_is_recomputed_from_bytes() -> None:
    from contracts_v3.source_ledger import SourceItem

    tampered = SourceItem.model_construct(
        source_id="source.a",
        source_kind="document",
        locator="doc.txt",
        captured_at="2026-08-05T09:30:00+00:00",
        content_hash="0" * 64,
        rights_status="client_authorized",
        verbatim_text="Der wahre Text.",
        language="de",
        allowed_uses=("report",),
    )
    ledger = SourceLedger.model_construct(
        schema_version="3.0",
        sources=(tampered,),
        claims=(),
        grounding_failures=(),
    )

    failures = check_evidence_v3(
        contract_with_viz(("claim.before", "claim.after", "claim.saved")),
        ledger,
        source_appendix=appendix(()),
    )

    assert any(f.code == "source_bytes_mismatch" for f in failures)


def test_missing_appendix_still_fails_closed() -> None:
    contract = contract_with_viz(("claim.before", "claim.after", "claim.saved"))
    ledger = SourceLedger.model_construct(
        schema_version="3.0",
        sources=(),
        claims=(spanless_claim("claim.saved", "100 Minuten"),),
        grounding_failures=(),
    )

    failures = check_evidence_v3(contract, ledger, source_appendix=None)

    assert any(f.code == "source_appendix_missing" for f in failures)


def test_numeric_exemptions_are_typed_and_verified() -> None:
    from stages.plan_compositions_v3 import (
        FaceCompositionFacts,
        RegionCompositionFacts,
    )

    facts = FaceCompositionFacts(
        face_id="face.01",
        language="de",
        content_by_ref={"content.face.01.founding": "Gegründet 1998 in Hamburg"},
        regions={
            "case_story": RegionCompositionFacts(
                content_refs=("content.face.01.founding",),
                font_size_pt=10,
            )
        },
        numeric_exemptions={"content.face.01.founding": "year"},
    )
    assert facts.numeric_exemptions["content.face.01.founding"] == "year"

    with pytest.raises(Exception):
        FaceCompositionFacts(
            face_id="face.01",
            language="de",
            content_by_ref={"content.face.01.founding": "Gegründet 1998"},
            regions={},
            numeric_exemptions={"content.face.01.founding": "decorative"},
        )
