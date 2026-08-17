from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PREPROCESSOR_ROOT = ROOT / "research" / "preprocessor"
if str(PREPROCESSOR_ROOT) not in sys.path:
    sys.path.insert(0, str(PREPROCESSOR_ROOT))

from contracts_v3.source_ledger import SourceLedger  # noqa: E402


NODE_MODULE = ROOT / "docs" / "n8n" / "source-ledger-node-v3.js"


def representative_input() -> dict:
    return {
        "sources": [
            {
                "source_kind": "interview",
                "locator": "client-interview.txt",
                "captured_at": "2026-08-05T09:30:00+05:30",
                "rights_status": "client_authorized",
                "text": "Die Bearbeitung sank von 120 auf 20 Minuten.",
                "language": "de",
                "allowed_uses": ["report", "quotation"],
            }
        ],
        "claims": [
            {
                "key": "start-time",
                "kind": "direct",
                "claim_type": "number",
                "value": "120 Minuten",
                "source_locator": "client-interview.txt",
                "verbatim": "120",
                "confidence": 0.98,
                "allowed_uses": ["body", "chart"],
            },
            {
                "key": "end-time",
                "kind": "direct",
                "claim_type": "number",
                "value": "20 Minuten",
                "source_locator": "client-interview.txt",
                "verbatim": "20",
                "confidence": 0.99,
                "allowed_uses": ["body", "chart"],
            },
            {
                "key": "time-saved",
                "kind": "computed",
                "claim_type": "number",
                "operation": "difference",
                "formula": "start-time - end-time",
                "operand_keys": ["start-time", "end-time"],
                "value": "100 Minuten",
                "confidence": 0.97,
                "allowed_uses": ["body", "chart"],
            },
        ],
    }


def test_node_source_ledger_validates_directly_as_python_source_ledger() -> None:
    script = (
        "const fs = require('node:fs');"
        f"const {{ buildSourceLedger }} = require({json.dumps(str(NODE_MODULE))});"
        "const input = JSON.parse(fs.readFileSync(0, 'utf8'));"
        "process.stdout.write(JSON.stringify(buildSourceLedger(input)));"
    )
    completed = subprocess.run(
        ["node", "-e", script],
        input=json.dumps(representative_input()),
        text=True,
        capture_output=True,
        check=True,
        cwd=ROOT,
    )

    ledger = SourceLedger.model_validate_json(completed.stdout)

    assert ledger.schema_version == "3.0"
    assert ledger.claims[2].computation is not None
    assert ledger.claims[2].computation.formula == "start-time - end-time"
