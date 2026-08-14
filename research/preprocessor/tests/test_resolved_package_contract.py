"""Golden-file contract test for resolved_package.json (schema v2.0).

Runs /render on a HERMETIC copy of the sample request (no image URLs, no
API keys) so the package is fully deterministic + offline, normalizes the
only volatile field (generated_at), and compares to a frozen snapshot.

The sample fixture's `client_slug` is "mein-werkzeugkoffer" and there is NO
`client_assets/mein-werkzeugkoffer/` folder, so every drive slot resolves to
absent / missing_required and NOTHING is copied — the package stays hermetic
(no `/Users/`, `/tmp/`, or `/var/folders/` path ever appears).

This is the spine of the no-regression discipline: any later change that
alters the package shape must update the snapshot ON PURPOSE.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import main  # noqa: E402  (flat import via conftest sys.path)

_HERE = Path(__file__).resolve().parent
_SAMPLE = _HERE / "fixtures" / "sample_render_request.json"
_GOLDEN = _HERE / "golden" / "resolved_package.v2.json"

_TOP_LEVEL_KEYS = {
    "version", "generated_at", "record_id", "brand", "axes", "brand_axes",
    "provenance", "fonts", "pages", "report_assets", "slot_summary",
    "validation", "asset_summary", "asset_warnings",
}


def _normalize(manifest: dict) -> dict:
    """Replace volatile fields so the snapshot is stable run-to-run."""
    out = dict(manifest)
    out["generated_at"] = "NORMALIZED"
    return out


def _run_render_hermetic(monkeypatch) -> dict:
    # No external services: clear keys so generate_assets stubs everything.
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("FAL_KEY", raising=False)

    payload = json.loads(_SAMPLE.read_text(encoding="utf-8"))
    # Empty manifest → no downloads → no network.
    payload.setdefault("image_manifest", {})["images"] = []

    from settings import Settings
    main.app.dependency_overrides[main.get_settings] = lambda: Settings(
        _env_file=None, openrouter_api_key=None, fal_key=None
    )
    try:
        with TestClient(main.app) as client:
            resp = client.post("/render", json=payload)
        assert resp.status_code == 200, resp.text
        output_dir = Path(resp.json()["output_dir"])
        manifest = json.loads((output_dir / "resolved_package.json").read_text(encoding="utf-8"))
    finally:
        main.app.dependency_overrides.clear()
    return manifest


def test_resolved_package_matches_golden_v2(monkeypatch) -> None:
    actual = _normalize(_run_render_hermetic(monkeypatch))

    # Structural invariant (independent of the snapshot bytes).
    assert set(actual.keys()) >= _TOP_LEVEL_KEYS
    assert actual["version"] == "2.0"

    if not _GOLDEN.exists():
        _GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        _GOLDEN.write_text(
            json.dumps(actual, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        pytest.fail("golden snapshot did not exist; created it — re-run to compare")

    expected = json.loads(_GOLDEN.read_text(encoding="utf-8"))
    assert actual == expected, (
        "resolved_package.json drifted from the frozen v2.0 contract. "
        "If this change is intentional, delete tests/golden/resolved_package.v2.json "
        "and re-run to re-baseline."
    )
