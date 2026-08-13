from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DMC_ROOT = PROJECT_ROOT / "dmc-renderer"
if str(DMC_ROOT) not in sys.path:
    sys.path.insert(0, str(DMC_ROOT))

import service  # noqa: E402


REQUIRED_RUNTIME_TREES = (
    "research/composition_registry/",
    "research/reference-atlas/",
    "research/postprocessor/",
    "research/design_policy/",
    "research/artifacts/",
)
REQUIRED_WORKFLOW_FILES = (
    "docs/writer-prompt-v5.md",
    "docs/resolve-schema-node-v5.js",
    "docs/n8n/writer_gate.js",
    "docs/n8n/source-ledger-node-v3.js",
    "docs/n8n/claim-gate-v3.js",
    "docs/n8n/workflow-contract-v3.json",
)
REQUIRED_SYSTEM_TOOLS = {
    "ghostscript",
    "pdfinfo",
    "pdftotext",
    "pdffonts",
    "pdfimages",
}


def test_container_build_context_and_image_include_the_v3_runtime_closure() -> None:
    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")
    dockerignore = (PROJECT_ROOT / ".dockerignore").read_text(encoding="utf-8")

    for source in (*REQUIRED_RUNTIME_TREES, *REQUIRED_WORKFLOW_FILES):
        assert f"COPY {source}" in dockerfile
        assert f"!{source}" in dockerignore
    assert "poppler-utils" in dockerfile


def test_readiness_contract_covers_browser_and_every_required_system_tool() -> None:
    tool_commands = getattr(service, "V3_SYSTEM_TOOL_COMMANDS", None)

    assert isinstance(tool_commands, dict)
    assert set(tool_commands) == REQUIRED_SYSTEM_TOOLS
    assert callable(getattr(service, "_playwright_chromium_ready", None))


def test_v3_readiness_verifies_imports_and_immutable_file_hashes() -> None:
    readiness = getattr(service, "_v3_runtime_readiness", None)

    assert callable(readiness)
    report = readiness(
        project_root=PROJECT_ROOT,
        import_probe=lambda _module_name: True,
        browser_probe=lambda: True,
        tool_probe=lambda _tool_name, _command: True,
    )

    assert report["ok"] is True
    assert report["checks"]["imports"]["ok"] is True
    assert report["checks"]["immutable_files"]["ok"] is True
    assert report["checks"]["browser"]["ok"] is True
    assert report["checks"]["tools"]["ok"] is True

    workflow = report["checks"]["immutable_files"]["workflow_artifacts"]
    contract = json.loads(
        (PROJECT_ROOT / "docs/n8n/workflow-contract-v3.json").read_text(encoding="utf-8")
    )
    assert set(workflow) == {
        artifact["artifact_id"] for artifact in contract["artifacts"]
    }
    assert all(item["ok"] for item in workflow.values())


def test_v3_readiness_fails_closed_when_one_tool_is_missing() -> None:
    readiness = getattr(service, "_v3_runtime_readiness", None)

    assert callable(readiness)
    report = readiness(
        project_root=PROJECT_ROOT,
        import_probe=lambda _module_name: True,
        browser_probe=lambda: True,
        tool_probe=lambda tool_name, _command: tool_name != "pdffonts",
    )

    assert report["ok"] is False
    assert report["checks"]["tools"]["items"]["pdffonts"]["ok"] is False
    assert "tool:pdffonts" in report["failures"]


def test_v3_readiness_rejects_a_workflow_contract_missing_required_artifacts(
    tmp_path: Path,
) -> None:
    for relative_path in service.V3_IMMUTABLE_JSON_FILES.values():
        source = PROJECT_ROOT / relative_path
        target = tmp_path / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    contract_path = tmp_path / service.V3_IMMUTABLE_JSON_FILES["workflow_contract"]
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    for artifact in contract["artifacts"]:
        source = PROJECT_ROOT / artifact["repository_path"]
        target = tmp_path / artifact["repository_path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    contract["artifacts"] = []
    contract_path.write_text(json.dumps(contract), encoding="utf-8")

    report, failures = service._immutable_runtime_file_checks(tmp_path)

    assert report["ok"] is False
    assert failures == ["workflow_contract:artifact_set"]


def test_health_v3_returns_503_on_readiness_failure_without_rendering(monkeypatch) -> None:
    endpoint = getattr(service, "health_v3_endpoint", None)

    assert callable(endpoint)
    monkeypatch.setattr(
        service,
        "_v3_runtime_readiness",
        lambda: {
            "ok": False,
            "checks": {},
            "failures": ["tool:pdfinfo"],
        },
    )
    monkeypatch.setattr(
        service,
        "build_and_render_v3",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("health must not render")
        ),
    )

    response = endpoint()

    assert response.status_code == 503
    assert json.loads(response.body)["failures"] == ["tool:pdfinfo"]


def test_health_v3_returns_200_only_when_every_check_passes(monkeypatch) -> None:
    endpoint = getattr(service, "health_v3_endpoint", None)

    assert callable(endpoint)
    monkeypatch.setattr(
        service,
        "_v3_runtime_readiness",
        lambda: {
            "ok": True,
            "checks": {
                "imports": {"ok": True},
                "immutable_files": {"ok": True},
                "browser": {"ok": True},
                "tools": {"ok": True},
            },
            "failures": [],
        },
    )

    response = endpoint()

    assert response.status_code == 200
    assert json.loads(response.body)["ok"] is True
    assert "/health/v3" in {route.path for route in service.app.routes}


def test_container_smoke_script_builds_and_exercises_v3_without_repointing_render() -> None:
    smoke_path = PROJECT_ROOT / "scripts/smoke_v3_container.sh"

    assert smoke_path.is_file()
    assert smoke_path.stat().st_mode & 0o111
    script = smoke_path.read_text(encoding="utf-8")
    for required_text in (
        "docker build",
        "/health/v3",
        "/render-v3",
        "valid_envelope",
        "x-dmc-release-state",
        "x-dmc-contract-hash",
        "x-dmc-gate-report-sha256",
        "/render",
        "test_v2_v3_route_isolation.py",
    ):
        assert required_text in script
    assert "\u2014" not in script
