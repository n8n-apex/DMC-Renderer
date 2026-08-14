"""A real report's own copy must supply its evidence and its devices."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from stages.build_source_ledger import build_source_ledger
from stages.derive_claims_v3 import COPY_DERIVED_USE, derive_evidence


ROOT = Path(__file__).resolve().parents[3]
REAL_PAYLOAD = ROOT / "dmc-renderer" / "fixtures" / "apex_consulting_payload.json"
CAPTURED_AT = datetime(2026, 8, 7, tzinfo=timezone.utc)


def _real_bundle() -> dict:
    payload = json.loads(REAL_PAYLOAD.read_text(encoding="utf-8"))
    return {"report_json": payload["payload"]}


def test_every_derived_claim_span_matches_the_copy_byte_for_byte() -> None:
    evidence = derive_evidence(_real_bundle(), captured_at=CAPTURED_AT)
    text_by_source = {
        source["source_id"]: source["verbatim_text"] for source in evidence.sources
    }

    assert evidence.claims
    for claim in evidence.claims:
        for span in claim["source_spans"]:
            text = text_by_source[span["source_id"]]
            assert text[span["start"] : span["end"]] == span["verbatim"]


def test_derived_claims_are_marked_as_copy_grounded_not_verified() -> None:
    evidence = derive_evidence(_real_bundle(), captured_at=CAPTURED_AT)

    assert all(COPY_DERIVED_USE in claim["allowed_uses"] for claim in evidence.claims)
    assert all(COPY_DERIVED_USE in src["allowed_uses"] for src in evidence.sources)


def test_a_real_report_stops_being_ungrounded_once_its_copy_is_read() -> None:
    """The exact failure that blocked the real payload must be gone."""
    bundle = _real_bundle()

    before = build_source_ledger(bundle)
    assert any(
        failure.code == "ungrounded_numeric_candidate"
        for failure in before.grounding_failures
    )

    evidence = derive_evidence(bundle, captured_at=CAPTURED_AT)
    after = build_source_ledger(
        {**bundle, "sources": evidence.sources, "claims": evidence.claims}
    )

    assert after.grounding_failures == ()
    assert len(after.claims) == len(evidence.claims)


def test_the_real_report_earns_devices_bound_to_real_claims() -> None:
    evidence = derive_evidence(_real_bundle(), captured_at=CAPTURED_AT)
    claim_ids = {claim["claim_id"] for claim in evidence.claims}

    assert evidence.devices
    for device in evidence.devices:
        assert set(device.claim_ids) <= claim_ids
        assert len(device.claim_ids) == len(set(device.claim_ids))
