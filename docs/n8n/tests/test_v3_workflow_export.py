"""Structural tests for the review-safe v3 n8n workflow export.

The derived export docs/n8n/workflows/DMC-Ingestion-Pipeline-v3-review.json is
generated FROM the owner's active export (~/Downloads/DMC Ingestion
Pipeline.json, never modified) and must stay import-plausible while being
review-only: inactive, review-labeled, five authoritative contract nodes with
byte-exact embedded artifacts, gate order + bounded retry, /render-v3 envelope
with idempotency, per-release-state response branches, REVIEW-folder-only
uploads, disabled ship path, credentials by reference only, and no large JSON
stuffed into Airtable long-text fields.

Every test loads the derived export and manifest fresh from disk.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import deque
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
N8N_ROOT = ROOT / "docs" / "n8n"
DERIVED_PATH = N8N_ROOT / "workflows" / "DMC-Ingestion-Pipeline-v3-review.json"
MANIFEST_PATH = N8N_ROOT / "workflows" / "DMC-Ingestion-Pipeline-v3-review.manifest.json"
CONTRACT_PATH = N8N_ROOT / "workflow-contract-v3.json"

FIVE_CONTRACT_NODE_NAMES = (
    "Section Writer v5",
    "Resolve Schema and Build Prompts v5",
    "Writer Gate v3",
    "Source Ledger v3",
    "Claim Gate v3",
)

# node name -> repository file whose exact bytes must be embedded as jsCode
CODE_EMBEDS = {
    "Source Ledger v3": "docs/n8n/source-ledger-node-v3.js",
    "Claim Gate v3": "docs/n8n/claim-gate-v3.js",
    "Writer Gate v3": "docs/n8n/writer_gate.js",
    "Resolve Schema and Build Prompts v5": "docs/resolve-schema-node-v5.js",
}

SECRET_PATTERNS = (
    r"Bearer\s+[A-Za-z0-9_\-\.=]{16,}",
    r"sk-[A-Za-z0-9_\-]{16,}",
    r"sk-or-v1-[A-Za-z0-9]{8,}",
    r"xox[baprs]-[A-Za-z0-9\-]{8,}",
    r"pat[A-Za-z0-9]{14}\.[A-Za-z0-9a-f]{16,}",
    r"AIza[0-9A-Za-z\-_]{30,}",
    r"-----BEGIN[A-Z ]*PRIVATE KEY-----",
    r"ya29\.[A-Za-z0-9_\-]{20,}",
)


# --- fresh loaders (no module-level caching by design) -----------------------

def load_derived() -> dict:
    return json.loads(DERIVED_PATH.read_text(encoding="utf-8"))


def load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def load_contract() -> dict:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def nodes_by_name(workflow: dict) -> dict:
    result = {}
    for node in workflow["nodes"]:
        assert node["name"] not in result, f"duplicate node name {node['name']!r}"
        result[node["name"]] = node
    return result


def main_adjacency(workflow: dict) -> dict:
    """name -> list of (target_name, source_output_index) over main connections."""
    adj: dict = {}
    for source, by_type in workflow.get("connections", {}).items():
        for out_index, targets in enumerate(by_type.get("main", [])):
            for target in targets or []:
                adj.setdefault(source, []).append((target["node"], out_index))
    return adj


def reachable_from(adj: dict, start: str) -> set:
    seen = set()
    queue = deque([start])
    while queue:
        current = queue.popleft()
        for target, _ in adj.get(current, []):
            if target not in seen:
                seen.add(target)
                queue.append(target)
    return seen


def main_targets(workflow: dict, source: str, out_index: int) -> list:
    outputs = workflow["connections"][source]["main"]
    assert len(outputs) > out_index, (
        f"{source!r} has no main output index {out_index}"
    )
    return [t["node"] for t in outputs[out_index] or []]


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --- 0. files exist and parse ------------------------------------------------

def test_derived_export_and_manifest_exist_and_parse() -> None:
    workflow = load_derived()
    manifest = load_manifest()
    assert isinstance(workflow.get("nodes"), list) and workflow["nodes"]
    assert isinstance(workflow.get("connections"), dict) and workflow["connections"]
    assert isinstance(manifest, dict) and manifest


# --- 1. inactive + review-only labeling --------------------------------------

def test_workflow_is_inactive_and_named_review_only() -> None:
    workflow = load_derived()
    assert workflow["active"] is False
    assert workflow["name"] == "DMC Ingestion Pipeline v3 REVIEW"
    assert "REVIEW" in workflow["name"]


def test_review_webhook_path_cannot_collide_with_deployed_workflow() -> None:
    workflow = load_derived()
    webhooks = [
        n for n in workflow["nodes"] if n["type"] == "n8n-nodes-base.webhook"
    ]
    assert webhooks, "review workflow must keep a webhook trigger"
    for node in webhooks:
        path = node["parameters"]["path"]
        assert path != "report-generator", "must not reuse the deployed webhook path"
        assert "review" in path.lower()


# --- 2. five contract nodes, byte-exact embedded artifacts -------------------

def test_five_contract_node_names_present_exactly_once_and_enabled() -> None:
    workflow = load_derived()
    names = [n["name"] for n in workflow["nodes"]]
    for expected in FIVE_CONTRACT_NODE_NAMES:
        assert names.count(expected) == 1, expected
    by_name = nodes_by_name(workflow)
    for expected in FIVE_CONTRACT_NODE_NAMES:
        assert not by_name[expected].get("disabled", False), expected


@pytest.mark.parametrize("node_name", sorted(CODE_EMBEDS))
def test_code_nodes_embed_repository_paste_target_bytes(node_name: str) -> None:
    workflow = load_derived()
    node = nodes_by_name(workflow)[node_name]
    assert node["type"] == "n8n-nodes-base.code"
    js_code = node["parameters"]["jsCode"]
    repo_path = ROOT / CODE_EMBEDS[node_name]
    repo_bytes = repo_path.read_bytes()
    assert sha256_text(js_code) == hashlib.sha256(repo_bytes).hexdigest(), (
        f"{node_name} jsCode is not byte-identical to {CODE_EMBEDS[node_name]}"
    )


def test_embedded_code_hashes_match_contract_hashes() -> None:
    workflow = load_derived()
    contract = load_contract()
    by_name = nodes_by_name(workflow)
    contract_by_node = {
        a["expected_node_name"]: a["sha256"] for a in contract["artifacts"]
    }
    for node_name in CODE_EMBEDS:
        expected = contract_by_node[node_name]
        actual = sha256_text(by_name[node_name]["parameters"]["jsCode"])
        assert actual == expected, node_name


def test_section_writer_v5_embeds_writer_prompt_artifact_bytes() -> None:
    workflow = load_derived()
    contract = load_contract()
    node = nodes_by_name(workflow)["Section Writer v5"]
    message = node["parameters"]["messages"]["messageValues"][0]["message"]
    assert not message.startswith("="), (
        "system prompt must be a literal, not an n8n expression"
    )
    expected = next(
        a["sha256"]
        for a in contract["artifacts"]
        if a["artifact_id"] == "writer_prompt"
    )
    assert sha256_text(message) == expected
    prompt_bytes = (ROOT / "docs" / "writer-prompt-v5.md").read_bytes()
    assert sha256_text(message) == hashlib.sha256(prompt_bytes).hexdigest()


# --- 3. execution order + bounded retry --------------------------------------

def test_source_ledger_runs_before_writer_and_gates_run_after_parse() -> None:
    workflow = load_derived()
    adj = main_adjacency(workflow)

    from_ledger = reachable_from(adj, "Source Ledger v3")
    assert "Section Writer v5" in from_ledger
    assert "Parse Writer Response" in from_ledger
    assert "Claim Gate v3" in from_ledger
    assert "Writer Gate v3" in from_ledger

    # Claim Gate consumes parsed writer output AFTER the writer.
    from_writer = reachable_from(adj, "Section Writer v5")
    assert "Parse Writer Response" in from_writer
    assert "Claim Gate v3" in from_writer
    # Source Ledger must never run downstream of the writer.
    assert "Source Ledger v3" not in from_writer

    assert main_targets(workflow, "Parse Writer Response", 0) == ["Claim Gate v3"]
    assert main_targets(workflow, "Claim Gate v3", 0) == ["Writer Gate v3"]
    assert main_targets(workflow, "Writer Gate v3", 0) == ["Both Gates Pass? (v3)"]


def test_gate_if_condition_requires_both_gates() -> None:
    workflow = load_derived()
    node = nodes_by_name(workflow)["Both Gates Pass? (v3)"]
    assert node["type"] == "n8n-nodes-base.if"
    blob = json.dumps(node["parameters"])
    assert "claim_gate.pass" in blob
    assert "writer_gate.pass" in blob


def test_gate_fail_branch_retries_writer_at_most_twice_then_fails_loudly() -> None:
    workflow = load_derived()
    by_name = nodes_by_name(workflow)
    adj = main_adjacency(workflow)

    # pass branch continues, fail branch enters the retry preparation
    assert main_targets(workflow, "Both Gates Pass? (v3)", 0) == ["Edit Fields"]
    assert main_targets(workflow, "Both Gates Pass? (v3)", 1) == [
        "Prepare Gate Retry (review)"
    ]
    assert main_targets(workflow, "Prepare Gate Retry (review)", 0) == [
        "Retry Budget Left? (max 2)"
    ]

    budget = by_name["Retry Budget Left? (max 2)"]
    budget_blob = json.dumps(budget["parameters"])
    assert "gate_retry_count" in budget_blob
    assert "2" in budget_blob

    # retry goes back to the writer (and re-feeds the positional Merge)
    retry_targets = main_targets(workflow, "Retry Budget Left? (max 2)", 0)
    assert "Section Writer v5" in retry_targets

    # exhausted budget reaches an ENABLED loud stop-and-error
    exhausted = reachable_from(adj, "Build Gate Failure Report (review)") | {
        "Build Gate Failure Report (review)"
    }
    assert main_targets(workflow, "Retry Budget Left? (max 2)", 1) == [
        "Build Gate Failure Report (review)"
    ]
    stop_nodes = [
        n
        for n in workflow["nodes"]
        if n["type"] == "n8n-nodes-base.stopAndError" and n["name"] in exhausted
    ]
    assert len(stop_nodes) == 1
    assert not stop_nodes[0].get("disabled", False)
    assert "gate" in stop_nodes[0]["parameters"]["errorMessage"].lower()

    # retry instruction is actually appended to the writer request
    writer_text = by_name["Section Writer v5"]["parameters"]["text"]
    assert "gate_retry_instruction" in writer_text


# --- 4. /render-v3 envelope, idempotency, correlation ------------------------

def test_render_call_posts_canonical_v3_envelope_to_render_v3() -> None:
    workflow = load_derived()
    by_name = nodes_by_name(workflow)
    http = by_name["POST: Render v3 (review)"]
    assert http["type"] == "n8n-nodes-base.httpRequest"
    assert not http.get("disabled", False)
    url = http["parameters"]["url"]
    assert "/render-v3" in url
    assert not url.rstrip("'\" }").endswith("/render"), url

    headers = {
        h["name"]: h["value"]
        for h in http["parameters"]["headerParameters"]["parameters"]
    }
    assert "Idempotency-Key" in headers
    assert "X-DMC-Correlation-ID" in headers
    assert "render_idempotency_key" in headers["Idempotency-Key"]
    assert "render_correlation_id" in headers["X-DMC-Correlation-ID"]

    # no other enabled HTTP node may call the legacy /render route
    for node in workflow["nodes"]:
        if node["type"] != "n8n-nodes-base.httpRequest":
            continue
        if node.get("disabled", False):
            continue
        node_url = str(node["parameters"].get("url", ""))
        assert "/render'" not in node_url and not node_url.endswith("/render"), (
            f"{node['name']} still calls the legacy /render route"
        )


def test_envelope_builder_carries_six_versions_bundle_and_run_scoped_keys() -> None:
    workflow = load_derived()
    contract = load_contract()
    builder = nodes_by_name(workflow)["Build Renderer Envelope v3 (review)"]
    code = builder["parameters"]["jsCode"]

    assert f'workflow_contract_version: "{contract["contract_version"]}"' in code
    for artifact in contract["artifacts"]:
        assert (
            f'{artifact["envelope_version_field"]}: "{artifact["semantic_version"]}"'
            in code
        ), artifact["envelope_version_field"]
        assert artifact["sha256"] in code, artifact["artifact_id"]
        assert artifact["expected_node_name"] in code, artifact["artifact_id"]

    assert "workflow_verification_v3" in code
    assert "verification_bundle_sha256" in code
    for key in ("payload", "images", "brand_tokens"):
        assert key in code

    # idempotency key + correlation id derive from the run and record
    assert "$execution.id" in code
    assert "render_idempotency_key" in code
    assert "render_correlation_id" in code


# --- 5. response states route to separate branches ---------------------------

def test_response_states_route_to_separate_branches() -> None:
    workflow = load_derived()
    switch = nodes_by_name(workflow)["Route Render v3 Response"]
    assert switch["type"] == "n8n-nodes-base.switch"
    output_keys = [
        rule["outputKey"] for rule in switch["parameters"]["rules"]["values"]
    ]
    assert output_keys == ["rejected", "draft", "review_candidate", "ship_ready"]
    assert switch["parameters"]["options"].get("fallbackOutput") == "extra"

    blob = json.dumps(switch["parameters"])
    assert "422" in blob and "202" in blob
    assert "x-dmc-release-state" in blob

    branch_heads = [
        main_targets(workflow, "Route Render v3 Response", i)[0] for i in range(5)
    ]
    assert branch_heads == [
        "Handle Rejected (review)",
        "Handle Draft (review)",
        "Capture Review Artifacts (review)",
        "Hold Ship Evidence (review)",
        "Handle Render Dependency Failure (review)",
    ]
    assert len(set(branch_heads[:4])) == 4, "release states must not share a head"


def test_timeout_and_dependency_failure_have_their_own_branches() -> None:
    workflow = load_derived()
    http = nodes_by_name(workflow)["POST: Render v3 (review)"]
    assert http.get("onError") == "continueErrorOutput"

    assert main_targets(workflow, "POST: Render v3 (review)", 0) == [
        "Route Render v3 Response"
    ]
    assert main_targets(workflow, "POST: Render v3 (review)", 1) == [
        "Timeout? (render v3)"
    ]
    assert main_targets(workflow, "Timeout? (render v3)", 0) == [
        "Handle Render Timeout (review)"
    ]
    assert main_targets(workflow, "Timeout? (render v3)", 1) == [
        "Handle Render Dependency Failure (review)"
    ]


# --- 6. drive uploads: REVIEW folder only, ship path disabled ---------------

def test_enabled_drive_uploads_only_target_the_review_folder_placeholder() -> None:
    workflow = load_derived()
    drive_nodes = [
        n for n in workflow["nodes"] if n["type"] == "n8n-nodes-base.googleDrive"
    ]
    assert drive_nodes, "review workflow must include Drive upload nodes"
    enabled = [n for n in drive_nodes if not n.get("disabled", False)]
    assert enabled, "the review path needs at least one enabled Drive upload"
    for node in enabled:
        folder = node["parameters"]["folderId"]
        assert folder["value"] == "REPLACE_WITH_REVIEW_FOLDER_ID", node["name"]
        assert "REVIEW" in str(folder.get("cachedResultName", "")), node["name"]
        assert "REVIEW" in node["name"]


def test_ship_path_nodes_are_disabled_and_require_release_evidence() -> None:
    workflow = load_derived()
    by_name = nodes_by_name(workflow)

    ship_drive = by_name["Drive: Upload Delivery PDF (DISABLED until release evidence)"]
    assert ship_drive.get("disabled", False) is True
    assert "release evidence" in ship_drive.get("notes", "").lower()
    assert (
        ship_drive["parameters"]["folderId"]["value"]
        == "REPLACE_WITH_DELIVERY_FOLDER_ID_AFTER_RELEASE_EVIDENCE"
    )

    ship_slack = by_name["Slack: Ship Ready (DISABLED until release evidence)"]
    assert ship_slack.get("disabled", False) is True

    # nothing enabled may point at a delivery/final folder
    for node in workflow["nodes"]:
        if node["type"] != "n8n-nodes-base.googleDrive":
            continue
        if node.get("disabled", False):
            continue
        blob = json.dumps(node["parameters"]).lower()
        assert "delivery" not in blob and "final" not in blob, node["name"]


# --- 7. review labeling + artifact-manifest retention + idempotent uploads ---

def test_enabled_slack_messages_in_review_path_are_review_labeled() -> None:
    workflow = load_derived()
    slack_nodes = [
        n
        for n in workflow["nodes"]
        if n["type"] == "n8n-nodes-base.slack" and not n.get("disabled", False)
    ]
    assert slack_nodes
    for node in slack_nodes:
        assert "[REVIEW-ONLY]" in node["parameters"]["text"], node["name"]


def test_airtable_review_updates_are_labeled_and_retain_manifest_hash() -> None:
    workflow = load_derived()
    by_name = nodes_by_name(workflow)

    candidate = by_name["Airtable: Mark Review Candidate (review-only)"]
    columns = candidate["parameters"]["columns"]["value"]
    assert "REVIEW-ONLY" in str(columns.get("render_status", ""))
    manifest_field = str(columns.get("artifact_manifest_sha256", ""))
    assert "artifact_manifest_sha256" in manifest_field, (
        "the X-DMC-Artifact-Manifest-SHA256 value must be written to Airtable"
    )

    capture = by_name["Capture Review Artifacts (review)"]
    assert "x-dmc-artifact-manifest-sha256" in capture["parameters"]["jsCode"]

    # every enabled review-path Airtable status write is visibly review-labeled
    for name, node in by_name.items():
        if node["type"] != "n8n-nodes-base.airtable" or node.get("disabled", False):
            continue
        if node["parameters"].get("operation") not in {"update", "upsert"}:
            continue
        status = str(node["parameters"]["columns"]["value"].get("render_status", ""))
        if status:
            assert "REVIEW" in status.upper(), name


def test_retries_reuse_the_same_upload_identity() -> None:
    workflow = load_derived()
    by_name = nodes_by_name(workflow)
    http = by_name["POST: Render v3 (review)"]
    # the render call may retry; the idempotency key is run+record scoped, so a
    # retry replays the same key instead of minting a new artifact identity
    assert http.get("retryOnFail") is True
    review_upload = by_name["Drive: Upload Review PDF (REVIEW folder)"]
    assert "render_idempotency_key" in review_upload["parameters"]["name"]


# --- 8. credentials by reference only, no secret values ----------------------

def test_credentials_are_reference_only_and_copied_from_original() -> None:
    workflow = load_derived()
    seen_credential_types = set()
    for node in workflow["nodes"]:
        for cred_type, cred in (node.get("credentials") or {}).items():
            seen_credential_types.add(cred_type)
            assert set(cred) == {"id", "name"}, (
                f"{node['name']} credential {cred_type} must be a reference"
            )
    # references carried over from the original export
    assert {"airtableTokenApi", "googleDriveOAuth2Api", "slackOAuth2Api"} <= (
        seen_credential_types
    )


@pytest.mark.parametrize("pattern", SECRET_PATTERNS)
def test_no_obvious_secret_values_anywhere(pattern: str) -> None:
    raw = DERIVED_PATH.read_text(encoding="utf-8")
    assert not re.search(pattern, raw), f"possible secret matching {pattern}"


# --- 9. large JSON stays out of Airtable long-text fields --------------------

def test_airtable_fields_never_receive_the_source_ledger_json() -> None:
    workflow = load_derived()
    for node in workflow["nodes"]:
        if node["type"] != "n8n-nodes-base.airtable":
            continue
        columns = node["parameters"].get("columns", {})
        for field, value in (columns.get("value") or {}).items():
            text = str(value)
            assert "source_ledger" not in text, (
                f"{node['name']} writes the source ledger into field {field!r}"
            )
            assert "JSON.stringify" not in text, (
                f"{node['name']} stringifies large JSON into field {field!r}"
            )


def test_run_inputs_persist_to_drive_binary_artifact_not_airtable() -> None:
    workflow = load_derived()
    by_name = nodes_by_name(workflow)

    persist = by_name["Persist Run Inputs To Drive (review)"]
    code = persist["parameters"]["jsCode"]
    for category in ("source", "claim", "asset", "editorial", "composition"):
        assert category in code, f"run-inputs bundle must cover {category} inputs"
    assert "binary" in code

    upload = by_name["Drive: Upload Run Inputs (REVIEW folder)"]
    assert not upload.get("disabled", False)
    assert upload["parameters"]["folderId"]["value"] == "REPLACE_WITH_REVIEW_FOLDER_ID"

    adj = main_adjacency(workflow)
    assert (
        "Drive: Upload Run Inputs (REVIEW folder)"
        in reachable_from(adj, "Persist Run Inputs To Drive (review)")
    )


# --- 10. manifest provenance -------------------------------------------------

def test_manifest_records_source_provenance_and_derived_hash() -> None:
    manifest = load_manifest()

    source = manifest["source_export"]
    assert source["sha256"], "source export sha256 missing"
    assert source["byte_count"] > 0
    assert source["mtime_iso"]
    assert source["preserved_read_only"] is True

    derived = manifest["derived_export"]
    actual = hashlib.sha256(DERIVED_PATH.read_bytes()).hexdigest()
    assert derived["sha256"] == actual, (
        "manifest derived sha256 is stale — regenerate the manifest"
    )
    assert derived["byte_count"] == len(DERIVED_PATH.read_bytes())
    assert derived["active"] is False

    original_path = Path(source["path"]).expanduser()
    if not original_path.exists():
        pytest.skip("owner's original export not present on this machine")
    original_bytes = original_path.read_bytes()
    assert hashlib.sha256(original_bytes).hexdigest() == source["sha256"], (
        "the owner's original export changed or was overwritten"
    )
    assert len(original_bytes) == source["byte_count"]


def test_manifest_pins_contract_version_and_five_artifact_hashes() -> None:
    manifest = load_manifest()
    contract = load_contract()
    assert manifest["workflow_contract"]["contract_version"] == "3.2.1"
    recorded = {
        a["artifact_id"]: a["sha256"]
        for a in manifest["workflow_contract"]["artifacts"]
    }
    expected = {a["artifact_id"]: a["sha256"] for a in contract["artifacts"]}
    assert recorded == expected
    assert len(recorded) == 5


def test_manifest_documents_generation_rules_and_placeholders() -> None:
    manifest = load_manifest()
    workflow_raw = DERIVED_PATH.read_text(encoding="utf-8")

    rules = manifest["generation_rules"]
    assert isinstance(rules, list) and len(rules) >= 5

    placeholders = manifest["placeholders_to_fill"]
    assert placeholders, "manifest must list owner-fill placeholders"
    names = {p["placeholder"] for p in placeholders}
    assert "REPLACE_WITH_REVIEW_FOLDER_ID" in names
    for placeholder in placeholders:
        assert placeholder["placeholder"] in workflow_raw, (
            f"{placeholder['placeholder']} documented but absent from the export"
        )
