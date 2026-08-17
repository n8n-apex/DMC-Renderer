#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
RUN_STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
SUMMARY_DIR="${PROJECT_ROOT}/research/calibration/runs/${RUN_STAMP}-verification"
SUMMARY_PATH="${SUMMARY_DIR}/verification-summary-${RUN_STAMP}.json"
STEP_TABLE="$(mktemp)"
OVERALL_EXIT=0

cleanup() {
  rm -f "${STEP_TABLE}"
}
trap cleanup EXIT

mkdir -p "${SUMMARY_DIR}/logs"
cd "${PROJECT_ROOT}"

echo "DMC v3 verification ${RUN_STAMP}"
python3 --version
research/preprocessor/.venv/bin/python -m pytest --version
research/v7-renderer/.venv/bin/python -m pytest --version
node --version
gs --version
research/v7-renderer/.venv/bin/python -m playwright --version

export FAL_KEY="must-not-be-used"
export OPENROUTER_API_KEY="must-not-be-used"
export DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}"

run_step() {
  local step_id="$1"
  shift
  local started_at
  local finished_at
  local log_path
  local exit_code
  started_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  log_path="${SUMMARY_DIR}/logs/${step_id}.log"
  echo "Running ${step_id}"
  if "$@" 2>&1 | tee "${log_path}"; then
    exit_code=0
  else
    exit_code=$?
    OVERALL_EXIT=1
  fi
  finished_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf '%s\t%s\t%s\t%s\t%s\n' \
    "${step_id}" "${exit_code}" "${started_at}" "${finished_at}" "${log_path}" \
    >> "${STEP_TABLE}"
}

run_step phase_1_contracts \
  research/preprocessor/.venv/bin/pytest -q \
  research/preprocessor/tests/test_contracts_v3_units.py \
  research/preprocessor/tests/test_source_ledger_v3.py \
  research/preprocessor/tests/test_report_plan_v3.py \
  research/preprocessor/tests/test_asset_ledger_v3.py \
  research/preprocessor/tests/test_pipeline_v3_contracts.py \
  research/preprocessor/tests/test_house_profile_reference_contract.py \
  dmc-renderer/tests/test_adapter_v3.py

run_step phase_2_composition \
  research/preprocessor/.venv/bin/pytest -q \
  research/composition_registry/tests \
  research/preprocessor/tests/test_render_contract_v3.py \
  research/preprocessor/tests/test_plan_compositions_v3.py \
  research/preprocessor/tests/test_materialize_render_contract_v3.py

run_step phase_2_renderer \
  research/v7-renderer/.venv/bin/pytest -q \
  research/v7-renderer/tests/test_render_v3_contract.py \
  research/v7-renderer/tests/test_materialization_ledger.py \
  dmc-renderer/tests/test_service_v3.py \
  dmc-renderer/tests/test_build_v3.py

run_step phase_3_quality_and_exports \
  research/v7-renderer/.venv/bin/pytest -q \
  research/quality_loop/tests/test_ship_gate_v3.py \
  research/quality_loop/tests/test_deterministic_gates_v3.py \
  research/quality_loop/tests/test_materialization_gates_v3.py \
  research/quality_loop/tests/test_reference_rubric_v3.py \
  research/postprocessor/tests \
  dmc-renderer/tests/test_v3_release_flow.py \
  dmc-renderer/tests/test_v3_adversarial_e2e.py

run_step phase_4_workflow_assets_policy \
  research/preprocessor/.venv/bin/pytest -q \
  docs/n8n/tests \
  asset_bank/tests \
  research/design_policy/tests \
  research/calibration/tests \
  research/missing-sources/tests

run_step phase_4_renderer \
  research/v7-renderer/.venv/bin/pytest -q \
  dmc-renderer/tests/test_calibration_fixtures.py \
  dmc-renderer/tests/test_workflow_version_handshake.py

run_step phase_4_node_contracts node --test docs/n8n/tests/*.test.js

run_step phase_5_route_isolation \
  research/v7-renderer/.venv/bin/pytest -q \
  dmc-renderer/tests/test_v2_v3_route_isolation.py

run_step verifier_contract \
  research/preprocessor/.venv/bin/pytest -q \
  scripts/tests/test_verify_v3_program.py

run_step full_historical_v2_suite \
  bash -lc \
  'cd research/v7-renderer && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python -m pytest -q tests/'

STEP_TABLE_PATH="${STEP_TABLE}" \
SUMMARY_PATH_VALUE="${SUMMARY_PATH}" \
RUN_STAMP_VALUE="${RUN_STAMP}" \
OVERALL_EXIT_VALUE="${OVERALL_EXIT}" \
research/preprocessor/.venv/bin/python - <<'PY'
import json
import os
from pathlib import Path

steps = []
for line in Path(os.environ["STEP_TABLE_PATH"]).read_text(encoding="utf-8").splitlines():
    step_id, exit_code, started_at, finished_at, log_path = line.split("\t")
    steps.append(
        {
            "step_id": step_id,
            "exit_code": int(exit_code),
            "status": "passed" if exit_code == "0" else "failed",
            "started_at": started_at,
            "finished_at": finished_at,
            "log_path": log_path,
        }
    )

summary = {
    "schema_version": "1.0",
    "run_stamp": os.environ["RUN_STAMP_VALUE"],
    "external_generation_enabled": False,
    "overall_status": (
        "passed" if os.environ["OVERALL_EXIT_VALUE"] == "0" else "failed"
    ),
    "steps": steps,
}
path = Path(os.environ["SUMMARY_PATH_VALUE"])
path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(f"Verification summary: {path}")
PY

exit "${OVERALL_EXIT}"
