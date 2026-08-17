from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


POLICY_ROOT = Path(__file__).resolve().parent.parent
if str(POLICY_ROOT) not in sys.path:
    sys.path.insert(0, str(POLICY_ROOT))

from sync_sources import load_sources, verify_sources  # noqa: E402


def test_all_sources_are_commit_pinned_mit_and_locally_verified() -> None:
    manifest = load_sources(POLICY_ROOT / "sources.json")
    report = verify_sources(manifest, POLICY_ROOT)

    assert report["accepted"] is True
    assert len(manifest["sources"]) == 3
    for source in manifest["sources"]:
        assert len(source["commit_sha"]) == 40
        assert source["license"] == "MIT"
        assert source["retrieval_date"] == "2026-08-03"
        assert source["files"]


def test_selected_material_covers_print_relevant_categories_only() -> None:
    manifest = load_sources(POLICY_ROOT / "sources.json")
    paths = {
        file["upstream_path"]
        for source in manifest["sources"]
        for file in source["files"]
    }

    required_fragments = {
        "skills/fundamentals/typography-principles.md",
        "skills/editorial/SKILL.md",
        "visual-critique/skills/critique-composition/SKILL.md",
        "visual-critique/skills/critique-information-density/SKILL.md",
        "design-systems/skills/design-system-governance/SKILL.md",
        "ui-design/skills/data-visualization/SKILL.md",
        "design-ops/skills/handoff-spec/SKILL.md",
    }
    assert required_fragments <= paths
    assert not any("premium" in path.lower() for path in paths)
    assert not any("interaction-design" in path for path in paths)


def test_verify_cli_never_needs_network() -> None:
    result = subprocess.run(
        [sys.executable, str(POLICY_ROOT / "sync_sources.py"), "--verify"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "verified" in result.stdout.lower()
