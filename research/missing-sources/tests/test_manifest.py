from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest


SOURCE_ROOT = Path(__file__).resolve().parent.parent
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from reconcile import (  # noqa: E402
    ReconciliationFailure,
    reconcile_lines,
    validate_recovered_authority,
)


def test_manifest_records_three_unresolved_authorities() -> None:
    manifest = json.loads((SOURCE_ROOT / "manifest.json").read_text())

    assert len(manifest["authorities"]) == 3
    assert {item["authority_id"] for item in manifest["authorities"]} == {
        "copy-law",
        "luka-martic-reference",
        "frese-recruiting-v2-reference",
    }
    assert all(item["status"] == "missing" for item in manifest["authorities"])
    assert all(item["expected_source"] and item["last_known_filename"] for item in manifest["authorities"])
    assert all(item["why_it_matters"] for item in manifest["authorities"])


def test_recovered_files_must_live_under_source_authorities(tmp_path: Path) -> None:
    outside = tmp_path / "Downloads" / "copy-law.docx"
    outside.parent.mkdir()
    outside.write_bytes(b"authority")

    with pytest.raises(ReconciliationFailure, match="source-authorities"):
        validate_recovered_authority(
            outside,
            expected_sha256=hashlib.sha256(outside.read_bytes()).hexdigest(),
            repository_root=tmp_path,
        )


def test_hash_is_checked_before_recovered_authority_is_read(tmp_path: Path) -> None:
    recovered = tmp_path / "refs" / "source-authorities" / "copy-law.docx"
    recovered.parent.mkdir(parents=True)
    recovered.write_bytes(b"authority")

    with pytest.raises(ReconciliationFailure, match="hash mismatch"):
        validate_recovered_authority(
            recovered,
            expected_sha256="0" * 64,
            repository_root=tmp_path,
        )


def test_line_reconciliation_reports_differences_without_changing_inputs() -> None:
    authority = "Rule one\nRule two\nRule three\n"
    prompt = "Rule one\nRule changed\nRule three\n"
    memory = "Rule one\nRule two\n"

    report = reconcile_lines(authority, prompt, memory)

    assert report["prompt_matches_authority"] is False
    assert report["memory_matches_authority"] is False
    assert any(line.startswith("-") for line in report["prompt_diff"])
    assert authority == "Rule one\nRule two\nRule three\n"
