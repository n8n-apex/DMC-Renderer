#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PYTHON_BIN="${PROJECT_ROOT}/research/v7-renderer/.venv/bin/python"
IMAGE_TAG="${DMC_V3_SMOKE_IMAGE:-dmc-renderer:v3-smoke}"
CONTAINER_NAME="dmc-v3-smoke-${$}"
SMOKE_ROOT="$(mktemp -d "${PROJECT_ROOT}/.smoke-v3.XXXXXX")"
REQUEST_PATH="${SMOKE_ROOT}/request.json"
HEALTH_PATH="${SMOKE_ROOT}/health.json"
HEADERS_PATH="${SMOKE_ROOT}/render-v3.headers"
PDF_PATH="${SMOKE_ROOT}/report-v3-review.pdf"
RESULT_PATH="${SMOKE_ROOT}/smoke-result.json"

cleanup() {
  docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
  rm -rf "${SMOKE_ROOT}"
}
trap cleanup EXIT

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Existing renderer virtualenv is required: ${PYTHON_BIN}" >&2
  exit 1
fi
# G8: all render routes require the shared secret (env, else the preprocessor
# .env). The smoke must prove the AUTHENTICATED path; a missing secret means
# the container cannot serve renders and the smoke cannot pass.
RENDERER_SHARED_SECRET="${RENDERER_SHARED_SECRET:-}"
if [[ -z "${RENDERER_SHARED_SECRET}" && -f "${PROJECT_ROOT}/research/preprocessor/.env" ]]; then
  RENDERER_SHARED_SECRET="$("${PYTHON_BIN}" -c "
from pathlib import Path
p = Path('${PROJECT_ROOT}/research/preprocessor/.env')
for line in p.read_text().splitlines():
    if line.startswith('RENDERER_SHARED_SECRET='):
        print(line.split('=', 1)[1].strip().strip(chr(34)).strip(chr(39))); break
")"
fi
if [[ -z "${RENDERER_SHARED_SECRET}" ]]; then
  echo "RENDERER_SHARED_SECRET is required for the authenticated smoke" >&2
  exit 1
fi
AUTH_HEADER="Authorization: Bearer ${RENDERER_SHARED_SECRET}"
if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required" >&2
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  echo "Docker daemon is not ready" >&2
  exit 1
fi

SMOKE_PORT="${DMC_V3_SMOKE_PORT:-$("${PYTHON_BIN}" - <<'PY'
import socket

with socket.socket() as probe:
    probe.bind(("127.0.0.1", 0))
    print(probe.getsockname()[1])
PY
)}"

PROJECT_ROOT_VALUE="${PROJECT_ROOT}" \
SMOKE_ROOT_VALUE="${SMOKE_ROOT}" \
REQUEST_PATH_VALUE="${REQUEST_PATH}" \
"${PYTHON_BIN}" - <<'PY'
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

project_root = Path(os.environ["PROJECT_ROOT_VALUE"])
smoke_root = Path(os.environ["SMOKE_ROOT_VALUE"])
request_path = Path(os.environ["REQUEST_PATH_VALUE"])
sys.path.insert(0, str(project_root / "dmc-renderer"))
sys.path.insert(0, str(project_root / "dmc-renderer/tests"))

import service
from test_build_v3 import valid_envelope

recipe = json.loads(
    (project_root / "dmc-renderer/fixtures/v3/valid-20-face.json").read_text(
        encoding="utf-8"
    )
)
if recipe["mutation"] != "none" or "review_candidate" not in recipe["expected_release_states"]:
    raise SystemExit("valid mechanical fixture recipe is no longer review-candidate capable")

envelope = valid_envelope(smoke_root / "assets")
for asset in envelope["assets"]:
    asset["local_path"] = f"/smoke-input/assets/{Path(asset['local_path']).name}"

contract = json.loads(
    (project_root / "docs/n8n/workflow-contract-v3.json").read_text(encoding="utf-8")
)
envelope["workflow_contract_version"] = contract["contract_version"]
for artifact in contract["artifacts"]:
    envelope[artifact["envelope_version_field"]] = artifact["semantic_version"]

bundle = service.expected_workflow_verification_bundle_v3()
bundle["verification_bundle_sha256"] = hashlib.sha256(
    json.dumps(bundle, sort_keys=True, separators=(",", ":")).encode("utf-8")
).hexdigest()
envelope["workflow_verification_v3"] = bundle
request_path.write_text(
    json.dumps(envelope, ensure_ascii=False, sort_keys=True),
    encoding="utf-8",
)
PY

echo "Building ${IMAGE_TAG} from ${PROJECT_ROOT}"
docker build -t "${IMAGE_TAG}" "${PROJECT_ROOT}"

docker run --rm -d \
  --name "${CONTAINER_NAME}" \
  -p "127.0.0.1:${SMOKE_PORT}:8099" \
  -v "${SMOKE_ROOT}:/smoke-input:ro" \
  -e "RENDERER_SHARED_SECRET=${RENDERER_SHARED_SECRET}" \
  "${IMAGE_TAG}" >/dev/null

BASE_URL="http://127.0.0.1:${SMOKE_PORT}"
HEALTH_READY=0
for _attempt in $(seq 1 90); do
  if curl -fsS "${BASE_URL}/health/v3" -o "${HEALTH_PATH}"; then
    HEALTH_READY=1
    break
  fi
  sleep 1
done
if [[ "${HEALTH_READY}" != "1" ]]; then
  docker logs "${CONTAINER_NAME}" >&2 || true
  echo "Container did not reach v3 readiness" >&2
  exit 1
fi

HEALTH_PATH_VALUE="${HEALTH_PATH}" "${PYTHON_BIN}" - <<'PY'
import json
import os
from pathlib import Path

health = json.loads(Path(os.environ["HEALTH_PATH_VALUE"]).read_text(encoding="utf-8"))
if health.get("ok") is not True:
    raise SystemExit(f"v3 readiness failed: {health.get('failures')}")
required = {"ghostscript", "pdfinfo", "pdftotext", "pdffonts", "pdfimages"}
tools = health["checks"]["tools"]["items"]
if set(tools) != required or not all(item["ok"] for item in tools.values()):
    raise SystemExit("v3 system tool closure is incomplete")
if not health["checks"]["browser"]["ok"]:
    raise SystemExit("Playwright Chromium is not ready")
if not all(
    item["ok"]
    for item in health["checks"]["immutable_files"]["workflow_artifacts"].values()
):
    raise SystemExit("workflow artifact bytes do not match the bundled contract")
PY

HTTP_STATUS="$(curl -sS \
  -D "${HEADERS_PATH}" \
  -o "${PDF_PATH}" \
  -w '%{http_code}' \
  -H 'Content-Type: application/json' \
  -H "${AUTH_HEADER}" \
  --data-binary "@${REQUEST_PATH}" \
  "${BASE_URL}/render-v3")"
if [[ "${HTTP_STATUS}" != "200" ]]; then
  docker logs "${CONTAINER_NAME}" >&2 || true
  echo "POST /render-v3 returned HTTP ${HTTP_STATUS}" >&2
  exit 1
fi

header_value() {
  local header_name="$1"
  awk -F ': ' -v key="${header_name}" '
    tolower($1) == key { sub(/\r$/, "", $2); value = $2 }
    END { print value }
  ' "${HEADERS_PATH}"
}

RELEASE_STATE="$(header_value x-dmc-release-state)"
CONTRACT_HASH="$(header_value x-dmc-contract-hash)"
GATE_HASH="$(header_value x-dmc-gate-report-sha256)"
WORKFLOW_HASH="$(header_value x-dmc-workflow-verification-sha256)"
REVIEW_ONLY="$(header_value x-dmc-review-only)"
if [[ "${RELEASE_STATE}" != "review_candidate" || "${REVIEW_ONLY}" != "true" ]]; then
  echo "Expected a review_candidate response" >&2
  exit 1
fi
if [[ ! "${CONTRACT_HASH}" =~ ^[0-9a-f]{64}$ ]]; then
  echo "Invalid contract hash header" >&2
  exit 1
fi
if [[ ! "${GATE_HASH}" =~ ^[0-9a-f]{64}$ ]]; then
  echo "Invalid gate report hash header" >&2
  exit 1
fi
if [[ ! "${WORKFLOW_HASH}" =~ ^[0-9a-f]{64}$ ]]; then
  echo "Invalid workflow verification hash header" >&2
  exit 1
fi
if [[ "$(dd if="${PDF_PATH}" bs=4 count=1 2>/dev/null)" != "%PDF" ]]; then
  echo "Review response is not a PDF" >&2
  exit 1
fi

EXPECTED_WORKFLOW_HASH="$(REQUEST_PATH_VALUE="${REQUEST_PATH}" "${PYTHON_BIN}" - <<'PY'
import json
import os
from pathlib import Path

body = json.loads(Path(os.environ["REQUEST_PATH_VALUE"]).read_text(encoding="utf-8"))
print(body["workflow_verification_v3"]["verification_bundle_sha256"])
PY
)"
if [[ "${WORKFLOW_HASH}" != "${EXPECTED_WORKFLOW_HASH}" ]]; then
  echo "Workflow verification hash does not match the submitted fixture" >&2
  exit 1
fi

LEGACY_BODY='{"payload":{},"images":{}}'
DEFAULT_STATUS="$(curl -sS -o "${SMOKE_ROOT}/render-default.json" -w '%{http_code}' \
  -H 'Content-Type: application/json' -H "${AUTH_HEADER}" -d "${LEGACY_BODY}" "${BASE_URL}/render")"
NAMED_STATUS="$(curl -sS -o "${SMOKE_ROOT}/render-legacy.json" -w '%{http_code}' \
  -H 'Content-Type: application/json' -H "${AUTH_HEADER}" -d "${LEGACY_BODY}" "${BASE_URL}/render-legacy-v2")"
if [[ "${DEFAULT_STATUS}" != "400" || "${NAMED_STATUS}" != "400" ]]; then
  echo "Legacy route preflight behavior changed" >&2
  exit 1
fi
if ! cmp -s "${SMOKE_ROOT}/render-default.json" "${SMOKE_ROOT}/render-legacy.json"; then
  echo "Default and named legacy routes no longer share preflight behavior" >&2
  exit 1
fi

"${PYTHON_BIN}" -m pytest -q \
  "${PROJECT_ROOT}/dmc-renderer/tests/test_v2_v3_route_isolation.py"

# US-020: the standing closed-gap assessment harness gates the smoke. Fast
# mode skips the two full-suite checks (their record is the baseline ledger)
# but still proves every code-closed gap stays closed. A reopened gap fails
# the container smoke.
"${PYTHON_BIN}" "${PROJECT_ROOT}/research/quality_loop/assess_closed_gaps.py" --fast

RELEASE_STATE_VALUE="${RELEASE_STATE}" \
CONTRACT_HASH_VALUE="${CONTRACT_HASH}" \
GATE_HASH_VALUE="${GATE_HASH}" \
WORKFLOW_HASH_VALUE="${WORKFLOW_HASH}" \
RESULT_PATH_VALUE="${RESULT_PATH}" \
"${PYTHON_BIN}" - <<'PY'
import json
import os
from pathlib import Path

result = {
    "release_state": os.environ["RELEASE_STATE_VALUE"],
    "delivery_pdf_available": False,
    "hashes": {
        "render_contract": os.environ["CONTRACT_HASH_VALUE"],
        "gate_report": os.environ["GATE_HASH_VALUE"],
        "workflow_verification_bundle": os.environ["WORKFLOW_HASH_VALUE"],
    },
    "legacy_render_route": "unchanged",
}
path = Path(os.environ["RESULT_PATH_VALUE"])
path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps(result, indent=2, sort_keys=True))
PY
