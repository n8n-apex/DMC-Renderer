from __future__ import annotations

import copy
import hashlib
import json
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


ORIGINAL = ROOT / "dmc-renderer" / "fixtures" / "christoph_v5_payload.json"
FIXTURE = ROOT / "dmc-renderer" / "fixtures" / "v3" / "real" / "christopher-source-envelope.json"
REPORT = ROOT / "dmc-renderer" / "fixtures" / "v3" / "real" / "reports" / "christopher-migration-report.md"
PROFILE = ROOT / "research" / "preprocessor" / "policies" / "dmc_house_20_face.json"
ORIGINAL_SHA256 = "329bfa7681eb7ee490ff36ab9a63ba174f50c9f0c4647cc4f96936e3f3af95a4"


def original_document() -> dict:
    return json.loads(ORIGINAL.read_text(encoding="utf-8"))


def build_record(document: dict | None = None) -> MigrationRecord:
    return build_migration_record(
        client_id="christopher",
        original_path=ORIGINAL,
        project_root=ROOT,
        report_pointer="$",
        document=document,
    )


def test_preserves_exact_original_bytes_hash_and_every_source_reference() -> None:
    record = build_record()

    assert hashlib.sha256(ORIGINAL.read_bytes()).hexdigest() == ORIGINAL_SHA256
    assert record.original_artifact.repository_path == "dmc-renderer/fixtures/christoph_v5_payload.json"
    assert record.original_artifact.sha256 == ORIGINAL_SHA256
    assert record.original_artifact.byte_count == ORIGINAL.stat().st_size
    assert record.original_artifact.report_pointer == "$"
    assert record.verify_original(ROOT) is True

    extracted = extract_source_references(original_document())
    assert len(extracted) == 4
    assert record.source_references == extracted
    assert [reference.raw_value for reference in record.source_references] == [
        "(transcript)",
        "(Deloitte 2026)",
        "(Deloitte 2026)",
        "",
    ]
    assert all(reference.rights_status == "unknown" for reference in record.source_references)


def test_case_selection_stays_pending_and_does_not_infer_from_legacy_order() -> None:
    record = build_record()
    selection = record.case_selection

    assert selection.required_case_count == 3
    assert [case.source_slot for case in selection.candidates] == [6, 8, 10, 12, 13]
    assert selection.chosen_cases == ()
    assert selection.excluded_cases == ()
    assert len(selection.pending_cases) == 5
    assert selection.human_review_status == "pending"


def test_editorial_map_is_explicit_and_ignores_legacy_page_ranges() -> None:
    document = original_document()
    first = build_record(document)
    changed_ranges = copy.deepcopy(document)
    for index, page in enumerate(changed_ranges["pages"], start=1):
        page["page_numbers"] = f"700-{700 + index}"
    second = build_record(changed_ranges)

    assert len(first.editorial_map.faces) == 20
    assert [face.face_index for face in first.editorial_map.faces if face.role == "case_study"] == [6, 10, 12]
    assert all(face.page_range_derived is False for face in first.editorial_map.faces)
    assert first.editorial_map == second.editorial_map


def test_known_invented_83_percent_and_missing_rights_remain_blockers() -> None:
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
        "cta_url_missing",
    } <= codes
    invented = [
        blocker
        for blocker in record.blockers
        if blocker.code == "unsupported_claim" and blocker.raw_value == "83 %"
    ]
    assert len(invented) == 1
    assert invented[0].content_path == "$.pages[12].data.ergebnis_metrics[1].wert"
    assert record.sources == ()
    assert record.claims == ()
    assert record.assets == ()
    assert record.renderable is False


def test_blocked_migration_cannot_false_pass_precomposition() -> None:
    record = build_record()
    source_bundle, brief = record.to_precomposition_inputs(original_document())

    with pytest.raises(PrecompositionBlocked) as caught:
        build_precomposition_bundle_v3(source_bundle, brief, load_product_profile(PROFILE))

    assert "human_case_selection_pending" in caught.value.codes
    assert "unsupported_claim" in caught.value.codes
    assert "ungrounded_numeric_candidate" in caught.value.codes


def test_checked_in_fixture_and_report_are_current_and_review_only() -> None:
    record = MigrationRecord.model_validate_json(FIXTURE.read_text(encoding="utf-8"))

    assert record == build_record()
    assert record.renderable is False
    text = REPORT.read_text(encoding="utf-8")
    assert ORIGINAL_SHA256 in text
    assert "Correctly blocked" in text
    assert "—" not in text
