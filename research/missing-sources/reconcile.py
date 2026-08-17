"""Hash-first reconciliation for recovered source authorities."""

from __future__ import annotations

import difflib
import hashlib
import json
import re
import zipfile
from pathlib import Path


class ReconciliationFailure(RuntimeError):
    pass


def validate_recovered_authority(
    path: Path,
    *,
    expected_sha256: str,
    repository_root: Path,
) -> str:
    allowed_root = (repository_root / "refs" / "source-authorities").resolve()
    resolved = path.resolve()
    if not resolved.is_relative_to(allowed_root):
        raise ReconciliationFailure("recovered authority must live under refs/source-authorities")
    if not resolved.is_file():
        raise ReconciliationFailure(f"recovered authority is missing: {resolved}")
    actual = hashlib.sha256(resolved.read_bytes()).hexdigest()
    if actual != expected_sha256:
        raise ReconciliationFailure(
            f"recovered authority hash mismatch: expected {expected_sha256}, got {actual}"
        )
    return actual


def reconcile_lines(authority: str, prompt: str, memory: str) -> dict:
    authority_lines = authority.splitlines()
    prompt_lines = prompt.splitlines()
    memory_lines = memory.splitlines()
    return {
        "prompt_matches_authority": authority_lines == prompt_lines,
        "memory_matches_authority": authority_lines == memory_lines,
        "prompt_diff": list(
            difflib.unified_diff(
                authority_lines,
                prompt_lines,
                fromfile="recovered-authority",
                tofile="writer-prompt-v5",
                lineterm="",
            )
        ),
        "memory_diff": list(
            difflib.unified_diff(
                authority_lines,
                memory_lines,
                fromfile="recovered-authority",
                tofile="memory-transcription",
                lineterm="",
            )
        ),
    }


def _docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("word/document.xml").decode("utf-8")
    xml = re.sub(r"</w:p>", "\n", xml)
    return re.sub(r"<[^>]+>", "", xml)


def reconcile_manifest(manifest_path: Path, repository_root: Path) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    results = []
    for authority in manifest["authorities"]:
        if authority["status"] != "recovered":
            results.append(
                {
                    "authority_id": authority["authority_id"],
                    "status": "unresolved",
                }
            )
            continue
        recovered_path = repository_root / authority["recovered_path"]
        validate_recovered_authority(
            recovered_path,
            expected_sha256=authority["sha256"],
            repository_root=repository_root,
        )
        item = {
            "authority_id": authority["authority_id"],
            "status": "hash_verified",
            "sha256": authority["sha256"],
        }
        if authority["kind"] == "copy_policy":
            text = _docx_text(recovered_path)
            prompt = (repository_root / authority["comparison_targets"][0]).read_text(
                encoding="utf-8"
            )
            memory = (repository_root / authority["comparison_targets"][1]).read_text(
                encoding="utf-8"
            )
            item["line_reconciliation"] = reconcile_lines(text, prompt, memory)
        results.append(item)
    return {"schema_version": "1.0", "results": results}
