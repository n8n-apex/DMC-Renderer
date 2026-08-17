from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "verify_v3_program.sh"


def test_verifier_is_strict_versioned_and_writes_a_timestamped_summary() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "set -euo pipefail" in text
    assert "python3 --version" in text
    assert "node --version" in text
    assert "gs --version" in text
    assert "research/calibration/runs" in text
    assert "verification-summary-" in text
    assert "test_contracts_v3_units.py" in text
    assert "research/composition_registry/tests" in text
    assert "test_ship_gate_v3.py" in text
    assert "docs/n8n/tests" in text
    assert "phase_4_renderer" in text
    assert "DYLD_FALLBACK_LIBRARY_PATH" in text
    assert "test_v2_v3_route_isolation.py" in text
    assert "cd research/v7-renderer" in text
    assert ".venv/bin/python -m pytest -q tests/" in text
    assert "DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python" in text


def test_verifier_has_valid_shell_syntax() -> None:
    completed = subprocess.run(
        ["bash", "-n", str(SCRIPT)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
