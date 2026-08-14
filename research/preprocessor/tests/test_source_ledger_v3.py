from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from contracts_v3.source_ledger import (
    Claim,
    ClaimType,
    Computation,
    SourceItem,
    SourceKind,
    SourceLedger,
    SourceSpan,
)
from stages.build_source_ledger import build_source_ledger


FIXTURE = Path(__file__).parent / "fixtures" / "source_bundle_christoph_minimal.json"


def sourced_number() -> tuple[SourceItem, Claim]:
    text = "Die dokumentierte Zeitersparnis beträgt 83 Prozent."
    source = SourceItem(
        source_id="source.interview",
        source_kind=SourceKind.INTERVIEW,
        locator="interview.txt#L1",
        captured_at="2026-08-03T00:00:00Z",
        content_hash=hashlib.sha256(text.encode()).hexdigest(),
        rights_status="client_authorized",
        verbatim_text=text,
        language="de",
    )
    claim = Claim(
        claim_id="claim.time_saved",
        claim_type=ClaimType.NUMBER,
        normalized_value="83",
        unit="percent",
        source_ids=(source.source_id,),
        source_spans=(
            SourceSpan(
                source_id=source.source_id,
                start=40,
                end=42,
                verbatim="83",
            ),
        ),
    )
    return source, claim


def test_number_requires_source_span_or_computation() -> None:
    with pytest.raises(ValidationError, match="source_spans or computation"):
        Claim(
            claim_id="claim.revenue",
            claim_type=ClaimType.NUMBER,
            normalized_value="83",
            unit="percent",
            source_ids=("source.interview",),
            source_spans=(),
        )


def test_quote_requires_source_span() -> None:
    with pytest.raises(ValidationError, match="source_spans or computation"):
        Claim(
            claim_id="claim.quote",
            claim_type=ClaimType.QUOTE,
            normalized_value="Das war der Wendepunkt.",
        )


def test_computed_claim_requires_operands() -> None:
    with pytest.raises(ValidationError, match="operand_claim_ids"):
        Computation(formula="saved / baseline * 100", operand_claim_ids=())


def test_source_item_requires_sha256_content_hash() -> None:
    with pytest.raises(ValidationError, match="content_hash"):
        SourceItem(
            source_id="source.interview",
            source_kind=SourceKind.INTERVIEW,
            locator="interview.txt#L1",
            captured_at="2026-08-03T00:00:00Z",
            rights_status="client_authorized",
            verbatim_text="Evidence",
            language="de",
        )


def test_sourced_number_is_ship_grounded() -> None:
    source, claim = sourced_number()
    ledger = SourceLedger(sources=(source,), claims=(claim,))

    assert ledger.assert_ship_grounded() == ()


def test_ledger_rejects_claim_span_for_unknown_source() -> None:
    _, claim = sourced_number()

    with pytest.raises(ValidationError, match="unknown source"):
        SourceLedger(sources=(), claims=(claim,))


def test_builder_hashes_verbatim_source_and_preserves_text() -> None:
    text = "Original evidence text."
    ledger = build_source_ledger(
        {
            "sources": [
                {
                    "source_id": "source.document",
                    "source_kind": "document",
                    "locator": "brief.txt#L1",
                    "captured_at": "2026-08-03T00:00:00Z",
                    "rights_status": "client_authorized",
                    "verbatim_text": text,
                    "language": "en",
                }
            ],
            "claims": [],
        }
    )

    assert ledger.sources[0].verbatim_text == text
    assert ledger.sources[0].content_hash == hashlib.sha256(text.encode()).hexdigest()


def test_builder_hashes_local_source_bytes(tmp_path: Path) -> None:
    source_path = tmp_path / "brief.txt"
    source_path.write_bytes(b"Exact source bytes\n")

    ledger = build_source_ledger(
        {
            "sources": [
                {
                    "source_id": "source.local_document",
                    "source_kind": "document",
                    "locator": "brief.txt",
                    "captured_at": "2026-08-03T00:00:00Z",
                    "rights_status": "client_authorized",
                    "verbatim_text": "Exact source bytes\n",
                    "language": "en",
                    "local_path": str(source_path),
                }
            ],
            "claims": [],
        }
    )

    assert ledger.sources[0].content_hash == hashlib.sha256(source_path.read_bytes()).hexdigest()


def test_christoph_83_percent_is_recorded_as_ungrounded() -> None:
    source_bundle = json.loads(FIXTURE.read_text())

    ledger = build_source_ledger(source_bundle)
    failures = ledger.assert_ship_grounded()

    assert any(
        failure.code == "ungrounded_numeric_candidate" and failure.token == "83%"
        for failure in failures
    )


@pytest.mark.parametrize(
    "claim_type",
    ("number", "quote", "credential", "named_result", "certification"),
)
def test_builder_converts_unlocated_grounded_claim_to_typed_failure(
    claim_type: str,
) -> None:
    ledger = build_source_ledger(
        {
            "sources": [],
            "claims": [
                {
                    "claim_id": f"claim.{claim_type}",
                    "claim_type": claim_type,
                    "normalized_value": "unsupported value",
                }
            ],
        }
    )

    assert ledger.claims == ()
    assert any(
        failure.code == "ungrounded_claim"
        and failure.claim_id == f"claim.{claim_type}"
        for failure in ledger.assert_ship_grounded()
    )


def test_builder_normalizes_percent_unit() -> None:
    source, claim = sourced_number()
    raw_claim = claim.model_dump(mode="json")
    raw_claim["unit"] = "%"

    ledger = build_source_ledger(
        {
            "sources": [source.model_dump(mode="json")],
            "claims": [raw_claim],
        }
    )

    assert ledger.claims[0].unit == "percent"


def test_builder_records_unknown_source_span_as_typed_failure() -> None:
    _, claim = sourced_number()

    ledger = build_source_ledger(
        {"sources": [], "claims": [claim.model_dump(mode="json")]}
    )

    assert ledger.claims == ()
    assert any(
        failure.code == "invalid_source_reference"
        and failure.claim_id == claim.claim_id
        for failure in ledger.assert_ship_grounded()
    )


def test_builder_records_mismatched_verbatim_span_as_typed_failure() -> None:
    source, claim = sourced_number()
    raw_source = source.model_dump(mode="json")
    raw_source["verbatim_text"] = "A different source body with no matching span."

    ledger = build_source_ledger(
        {"sources": [raw_source], "claims": [claim.model_dump(mode="json")]}
    )

    assert ledger.claims == ()
    assert any(
        failure.code == "source_span_mismatch"
        and failure.claim_id == claim.claim_id
        for failure in ledger.assert_ship_grounded()
    )
