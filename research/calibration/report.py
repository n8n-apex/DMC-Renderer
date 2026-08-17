"""Deterministic summaries for calibration matrix executions."""

from __future__ import annotations

import hashlib
import json


def summarize_matrix(results) -> dict:
    payload = [result.model_dump(mode="json") for result in results]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "schema_version": "1.0",
        "job_count": len(payload),
        "passed_count": sum(item["passed"] for item in payload),
        "failed_count": sum(not item["passed"] for item in payload),
        "matrix_sha256": hashlib.sha256(encoded).hexdigest(),
        "results": payload,
    }
