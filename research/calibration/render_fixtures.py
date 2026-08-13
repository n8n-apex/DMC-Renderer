"""Execute every calibration recipe with frozen local assets and no generation."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from pathlib import Path


RESEARCH_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = RESEARCH_ROOT.parent
DMC_ROOT = PROJECT_ROOT / "dmc-renderer"
for path in (RESEARCH_ROOT, DMC_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from build_v3 import ReleaseContextV3, build_and_render_v3  # noqa: E402
from calibration_fixtures_v3 import envelope_for_profile  # noqa: E402


# Calibration fixtures run on the frozen synthetic asset bank by design (the
# pipeline must be exercised deterministically without real client photos). A
# calibration build still stops at review_candidate and needs human evidence
# to ship, so synthetic assets are declared allowed here — never in production.
_CALIBRATION_CONTEXT = ReleaseContextV3(allow_synthetic_assets=True)


def _failure_codes(error: Exception) -> tuple[str, ...]:
    failures = tuple(getattr(error, "failures", ()) or ())
    if failures:
        return tuple(dict.fromkeys(getattr(item, "code", type(item).__name__) for item in failures))
    elimination = tuple(getattr(error, "elimination_codes", ()) or ())
    if elimination:
        return elimination
    return (getattr(error, "code", type(error).__name__),)


def run_calibration_fixtures(
    manifest_path: Path,
    *,
    output_root: Path,
    builder: Callable = build_and_render_v3,
) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    output_root.mkdir(parents=True, exist_ok=True)
    records = []
    for entry in manifest["fixtures"]:
        profile = json.loads((manifest_path.parent / entry["path"]).read_text(encoding="utf-8"))
        fixture_root = output_root / entry["fixture_id"]
        envelope = envelope_for_profile(profile, fixture_root / "assets")
        try:
            result = builder(
                envelope,
                output_dir=fixture_root / "build",
                cleanup=False,
                release_context=_CALIBRATION_CONTEXT,
            )
            actual_state = result["release_state"]
            failure_codes: tuple[str, ...] = tuple(
                failure["code"] for failure in result.get("failures", ())
            )
            gate_hash = result.get("gate_report_sha256")
        except Exception as error:
            actual_state = "rejected"
            failure_codes = _failure_codes(error)
            gate_hash = None
        expected_codes = set(entry["expected_blockers"])
        matched = (
            actual_state == entry["expected_gate_state"]
            and expected_codes <= set(failure_codes)
        )
        records.append(
            {
                "fixture_id": entry["fixture_id"],
                "expected_gate_state": entry["expected_gate_state"],
                "actual_gate_state": actual_state,
                "expected_blockers": entry["expected_blockers"],
                "actual_failure_codes": list(failure_codes),
                "gate_report_sha256": gate_hash,
                "matched_expectation": matched,
            }
        )
    report = {
        "schema_version": "1.0",
        "external_generation_enabled": False,
        "fixture_manifest_version": manifest["manifest_version"],
        "fixtures": records,
    }
    (output_root / "calibration-fixture-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report
