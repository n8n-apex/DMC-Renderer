from __future__ import annotations

import json
from pathlib import Path

import pytest

from adapter_v3 import adapt_envelope_v3
from build_live import build_live_package, selected_contract_version
from pipeline_v3 import PrecompositionBlocked


FIXTURE = Path(__file__).parent.parent / "fixtures" / "christoph_v5_payload.json"


def recursive_string_characters(value) -> int:
    if isinstance(value, str):
        return len(value)
    if isinstance(value, dict):
        return sum(recursive_string_characters(item) for item in value.values())
    if isinstance(value, list):
        return sum(recursive_string_characters(item) for item in value)
    return 0


def minimal_envelope() -> dict:
    return {
        "payload": {
            "meta": {
                "client_slug": "example-client",
                "report_id": "example-v3",
                "lang": "de",
                "page_format": "A4",
                "page_count_target": 23,
            },
            "pages": [
                {
                    "slot": 1,
                    "type": "ST-07A",
                    "page_numbers": "1",
                    "data": {
                        "headline": "Canonical title",
                        "einleitung": "Canonical body",
                        "schritte": [
                            {"titel": "First step", "beschreibung": "Do the work"}
                        ],
                    },
                }
            ],
        },
        "images": {"unmapped_custom_asset": "https://example.com/proof.png"},
        "brand_tokens": {"founder_full_name": "Ada Example"},
        "sources": [],
        "claims": [],
    }


def test_adapter_creates_one_canonical_key_without_alias_inflation() -> None:
    envelope = minimal_envelope()
    before = recursive_string_characters(envelope["payload"]["pages"][0]["data"])

    adapted = adapt_envelope_v3(envelope)
    data = adapted.report_json.pages[0].data

    assert data["title"] == "Canonical title"
    assert data["body"] == "Canonical body"
    assert data["steps"][0] == {"title": "First step", "body": "Do the work"}
    assert not ({"headline", "titel", "einleitung", "schritte"} & data.keys())
    assert recursive_string_characters(data) == before


def test_adapter_preserves_unsupported_target_and_records_failure() -> None:
    adapted = adapt_envelope_v3(minimal_envelope())

    assert adapted.report_json.meta.page_count_target == 23
    assert "unsupported_page_count_target" in adapted.failure_codes


def test_adapter_does_not_author_or_route() -> None:
    adapted = adapt_envelope_v3(minimal_envelope())
    page_data = adapted.report_json.pages[0].data

    assert "author" not in page_data
    assert "fallstudie_number" not in page_data
    assert adapted.images == {
        "unmapped_custom_asset": "https://example.com/proof.png"
    }


def test_adapter_records_conflicting_alias_values() -> None:
    envelope = minimal_envelope()
    envelope["payload"]["pages"][0]["data"]["title"] = "Different title"

    adapted = adapt_envelope_v3(envelope)

    assert "conflicting_alias_values" in adapted.failure_codes
    assert adapted.report_json.pages[0].data["title"] == "Different title"


def test_adapter_records_unknown_legacy_page_type() -> None:
    envelope = minimal_envelope()
    envelope["payload"]["pages"][0]["type"] = "ST-UNKNOWN"

    adapted = adapt_envelope_v3(envelope)

    assert "unsupported_legacy_st_type" in adapted.failure_codes


def test_current_christoph_target_and_case_count_are_not_changed() -> None:
    payload = json.loads(FIXTURE.read_text())
    adapted = adapt_envelope_v3(
        {"payload": payload, "images": {}, "brand_tokens": {}, "sources": [], "claims": []}
    )

    assert adapted.report_json.meta.page_count_target == 23
    assert len(adapted.report_json.pages) == 17
    assert sum(page.legacy_st_type == "ST-07A" for page in adapted.report_json.pages) == 5


def test_v2_is_the_default_contract_version(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DMC_CONTRACT_VERSION", raising=False)

    assert selected_contract_version() == "v2"


def test_v3_contract_version_is_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DMC_CONTRACT_VERSION", "v3")

    assert selected_contract_version() == "v3"


def test_unknown_contract_version_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DMC_CONTRACT_VERSION", "future")

    with pytest.raises(ValueError, match="DMC_CONTRACT_VERSION"):
        selected_contract_version()


def test_explicit_v3_routes_christoph_to_precomposition_gate(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("DMC_CONTRACT_VERSION", "v3")
    payload = json.loads(FIXTURE.read_text())

    with pytest.raises(PrecompositionBlocked) as error:
        build_live_package(
            {
                "payload": payload,
                "images": {},
                "brand_tokens": {},
                "sources": [],
                "claims": [],
                "assets": [],
            },
            tmp_path,
        )

    assert "unsupported_page_count_target" in error.value.codes
    assert "face_count_mismatch" in error.value.codes
    assert "case_count_mismatch" in error.value.codes
    assert error.value.codes.count("missing_required") == 5
    assert not (tmp_path / "package.json").exists()


def test_meta_identity_derived_when_missing() -> None:
    """A bare meta (no client_slug/report_id — the n8n envelope node does not
    merge them) is derived deterministically: client_slug slugifies
    brand_tokens.company_name_short, report_id falls back to the record id.
    No literal, no network, no fabrication."""
    env = minimal_envelope()
    env["payload"]["meta"] = {
        "lang": "de", "page_format": "A4", "page_count_target": 20,
    }
    env["brand_tokens"] = {
        "company_name_short": "Apex Consulting",
    }
    env["record_id"] = "rec_123abc"
    adapted = adapt_envelope_v3(env)
    assert adapted.report_json.meta.client_slug == "apex-consulting"
    assert adapted.report_json.meta.report_id == "rec_123abc"


def test_meta_identity_derived_without_record_id() -> None:
    """Even without a record id, a report id is never empty: the client slug
    doubles as the report id stem."""
    env = minimal_envelope()
    env["payload"]["meta"] = {
        "lang": "de", "page_format": "A4", "page_count_target": 20,
    }
    env["brand_tokens"] = {"company_name_short": "BuchAgentur"}
    env.pop("record_id", None)
    adapted = adapt_envelope_v3(env)
    assert adapted.report_json.meta.client_slug == "buchagentur"
    assert adapted.report_json.meta.report_id


def test_explicit_meta_identity_wins_over_derivation() -> None:
    """A payload that DOES carry client_slug/report_id is never overridden."""
    env = minimal_envelope()
    env["brand_tokens"] = {"company_name_short": "Apex Consulting"}
    adapted = adapt_envelope_v3(env)
    assert adapted.report_json.meta.client_slug == "example-client"
    assert adapted.report_json.meta.report_id == "example-v3"
