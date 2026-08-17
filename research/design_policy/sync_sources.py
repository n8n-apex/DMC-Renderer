"""Verify pinned design-source snapshots without network access."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


def load_sources(path: Path) -> dict:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "1.0":
        raise ValueError("unsupported design-source manifest schema")
    for source in manifest.get("sources", ()):
        if not re.fullmatch(r"[0-9a-f]{40}", source.get("commit_sha", "")):
            raise ValueError("design source must be pinned to an exact commit")
        if source.get("license") != "MIT":
            raise ValueError("only MIT design sources are approved")
        if source.get("retrieval_date") != "2026-08-03":
            raise ValueError("retrieval date is required")
    return manifest


def verify_sources(manifest: dict, policy_root: Path) -> dict:
    mismatches: list[dict[str, str]] = []
    verified = 0
    for source in manifest["sources"]:
        for file in source["files"]:
            path = policy_root / file["local_snapshot_path"]
            if not path.is_file():
                mismatches.append(
                    {"source_id": source["source_id"], "code": "snapshot_missing", "path": str(path)}
                )
                continue
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != file["sha256"]:
                mismatches.append(
                    {
                        "source_id": source["source_id"],
                        "code": "snapshot_hash_mismatch",
                        "path": str(path),
                        "expected": file["sha256"],
                        "actual": actual,
                    }
                )
            else:
                verified += 1
    return {"accepted": not mismatches, "verified_count": verified, "mismatches": mismatches}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if not args.verify:
        parser.error("normal operation supports --verify only; retrieval is deliberate")
    policy_root = Path(__file__).resolve().parent
    report = verify_sources(load_sources(policy_root / "sources.json"), policy_root)
    if report["accepted"]:
        print(f"verified {report['verified_count']} pinned design-source files")
        return 0
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
