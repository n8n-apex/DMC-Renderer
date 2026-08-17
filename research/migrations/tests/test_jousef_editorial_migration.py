from __future__ import annotations

import copy
import hashlib
import json
import re
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
MIGRATIONS = ROOT / "research" / "migrations"
PREPROCESSOR = ROOT / "research" / "preprocessor"
for path in (MIGRATIONS, PREPROCESSOR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from contracts_v3.report_plan import load_product_profile  # noqa: E402
from legacy_report_v3 import (  # noqa: E402
    MigrationRecord,
    build_migration_record,
    extract_source_references,
)
from pipeline_v3 import PrecompositionBlocked, build_precomposition_bundle_v3  # noqa: E402


ORIGINAL = ROOT / "dmc-renderer" / "fixtures" / "apex_consulting_payload.json"
FIXTURE = ROOT / "dmc-renderer" / "fixtures" / "v3" / "real" / "jousef-source-envelope.json"
REPORT = ROOT / "dmc-renderer" / "fixtures" / "v3" / "real" / "reports" / "jousef-migration-report.md"
PROFILE = ROOT / "research" / "preprocessor" / "policies" / "dmc_house_20_face.json"
ORIGINAL_SHA256 = "242c70ce4ffd002ef819b651cb8f2563d3dfb2c5f339a2579da0331a39950e0f"


def original_document() -> dict:
    return json.loads(ORIGINAL.read_text(encoding="utf-8"))


def build_record(document: dict | None = None) -> MigrationRecord:
    return build_migration_record(
        client_id="jousef",
        original_path=ORIGINAL,
        project_root=ROOT,
        report_pointer="$.payload",
        document=document,
    )


def test_preserves_exact_original_bytes_hash_and_every_source_reference() -> None:
    record = build_record()

    assert hashlib.sha256(ORIGINAL.read_bytes()).hexdigest() == ORIGINAL_SHA256
    assert record.original_artifact.repository_path == "dmc-renderer/fixtures/apex_consulting_payload.json"
    assert record.original_artifact.sha256 == ORIGINAL_SHA256
    assert record.original_artifact.byte_count == ORIGINAL.stat().st_size
    assert record.original_artifact.report_pointer == "$.payload"
    assert record.verify_original(ROOT) is True

    extracted = extract_source_references(original_document())
    assert len(extracted) == 37
    assert record.source_references == extracted
    assert all(reference.rights_status == "unknown" for reference in record.source_references)
    assert any(reference.raw_value == "(BCG, 2025)" for reference in record.source_references)
    assert any(
        reference.raw_value == "https://drive.google.com/uc?id=1AhpgWjMu98VdUWI_pm-5kkejh_1Qqtfx"
        for reference in record.source_references
    )
    assert any(
        reference.content_path == "$.brand_tokens.qr_target_url"
        and reference.raw_value == "https://apex-consulting.ai/"
        for reference in record.source_references
    )


def test_case_selection_stays_pending_until_an_owner_selects_exactly_three() -> None:
    record = build_record()
    selection = record.case_selection

    assert selection.required_case_count == 3
    assert [case.source_slot for case in selection.candidates] == [6, 8, 10, 12, 13]
    assert selection.chosen_cases == ()
    assert selection.excluded_cases == ()
    assert {item.case_id for item in selection.pending_cases} == {
        case.case_id for case in selection.candidates
    }
    assert all(item.reason for item in selection.pending_cases)
    assert selection.human_review_status == "pending"
    assert selection.approved_by is None


def test_editorial_map_has_twenty_explicit_faces_and_never_uses_page_ranges() -> None:
    document = original_document()
    first = build_record(document)
    changed_ranges = copy.deepcopy(document)
    for index, page in enumerate(changed_ranges["payload"]["pages"], start=1):
        page["page_numbers"] = f"900-{900 + index}"
    second = build_record(changed_ranges)

    assert len(first.editorial_map.faces) == 20
    assert [face.face_id for face in first.editorial_map.faces] == [
        f"face.{index:02d}" for index in range(1, 21)
    ]
    assert [face.face_index for face in first.editorial_map.faces] == list(range(1, 21))
    assert [face.face_index for face in first.editorial_map.faces if face.role == "case_study"] == [6, 10, 12]
    assert all(face.mapping_basis == "explicit_source_path" for face in first.editorial_map.faces)
    assert all(face.page_range_derived is False for face in first.editorial_map.faces)
    assert first.editorial_map == second.editorial_map


def test_unsupported_claims_rights_and_missing_proof_remain_typed_blockers() -> None:
    record = build_record()
    codes = set(record.blocker_codes)

    assert {
        "human_case_selection_pending",
        "source_spans_missing",
        "source_rights_unresolved",
        "unsupported_claim",
        "objections_evidence_missing",
        "trust_proof_unverified",
        "case_portrait_unresolved",
        "founder_portrait_rights_unresolved",
    } <= codes
    assert record.sources == ()
    assert record.claims == ()
    assert record.assets == ()
    assert record.renderable is False
    numeric_paths = {
        blocker.content_path
        for blocker in record.blockers
        if blocker.code == "unsupported_claim" and blocker.claim_kind == "number"
    }
    assert "$.payload.pages[0].data.intro_body" in numeric_paths


def test_blocked_migration_cannot_false_pass_precomposition() -> None:
    record = build_record()
    source_bundle, brief = record.to_precomposition_inputs(original_document())

    with pytest.raises(PrecompositionBlocked) as caught:
        build_precomposition_bundle_v3(source_bundle, brief, load_product_profile(PROFILE))

    assert "human_case_selection_pending" in caught.value.codes
    assert "source_rights_unresolved" in caught.value.codes
    assert "ungrounded_numeric_candidate" in caught.value.codes


def test_checked_in_fixture_and_report_are_current_and_review_only() -> None:
    record = MigrationRecord.model_validate_json(FIXTURE.read_text(encoding="utf-8"))

    assert record == build_record()
    assert record.renderable is False
    text = REPORT.read_text(encoding="utf-8")
    assert ORIGINAL_SHA256 in text
    assert "Correctly blocked" in text
    assert "—" not in text
    assert not re.search(r"\bship[_ -]?ready\b", text, re.IGNORECASE)
