"""REAL Apex photo-resolution integration test (the Phase-4a feature proof).

Unlike the hermetic golden (`test_resolved_package_contract.py`, which uses
`client_slug="mein-werkzeugkoffer"` with NO local folder so every drive slot
is absent/missing_required), this test runs `/render` with
`client_slug="apex"` against the repo's REAL `client_assets/apex/` folder:

    founder.png, case-study-3.png, proof-1.png, proof-2.png, proof-3.png

It proves resolve_slots + assemble_package resolve those real photos AND copy
them into the package end-to-end. It is hermetic in the network sense (no API
keys → generate stubs; empty image_manifest → no downloads), but it
deliberately DOES touch the local apex folder. It must NOT touch the sample
fixture (the golden stays hermetic).
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

import main  # noqa: E402  (flat import via conftest sys.path)

_HERE = Path(__file__).resolve().parent
_SAMPLE = _HERE / "fixtures" / "sample_render_request.json"
# The repo's real client_assets/ (preprocessor root), resolved absolutely so
# the override is cwd-independent.
_CLIENT_ASSETS = _HERE.parent / "client_assets"


def _apex_payload() -> dict:
    """Start from the sample fixture and retarget it at the apex client.

    The sample already satisfies Stage-1 validation (page_count_target=20,
    slot1=ST-01, slot20=ST-03, three ST-07A pages with fallstudie 1/2/3, an
    ST-05 page) — we only swap the slug so resolve_slots reads
    client_assets/apex/, and we keep the manifest empty so no network call
    happens.
    """
    payload = json.loads(_SAMPLE.read_text(encoding="utf-8"))
    payload["report_json"]["meta"]["client_slug"] = "apex"
    payload.setdefault("image_manifest", {})["images"] = []
    return payload


def _run_render_apex() -> dict:
    from settings import Settings

    # No external services → generate-class assets stub, no downloads. Point
    # client_assets_dir at the repo's REAL folder (absolute) so apex resolves.
    main.app.dependency_overrides[main.get_settings] = lambda: Settings(
        _env_file=None,
        openrouter_api_key=None,
        fal_key=None,
        client_assets_dir=str(_CLIENT_ASSETS),
    )
    try:
        with TestClient(main.app) as client:
            resp = client.post("/render", json=_apex_payload())
        assert resp.status_code == 200, resp.text
        out_dir = Path(resp.json()["output_dir"])
        manifest = json.loads(
            (out_dir / "resolved_package.json").read_text(encoding="utf-8")
        )
    finally:
        main.app.dependency_overrides.clear()
    return manifest, out_dir


def _page(manifest: dict, slot: int) -> dict:
    return next(p for p in manifest["pages"] if p["slot"] == slot)


def test_apex_real_photos_resolve_and_copy_into_package() -> None:
    assert _CLIENT_ASSETS.joinpath("apex", "founder.png").exists(), (
        "fixture precondition: client_assets/apex/founder.png must exist"
    )
    manifest, out_dir = _run_render_apex()

    # ── ST-01 (slot 1): founder portrait resolved + copied to disk ──
    cover = _page(manifest, 1)
    founder = next(s for s in cover["slots"] if s["slot_id"] == "founder")
    assert founder["status"] == "resolved"
    assert founder["path"].startswith("assets/"), founder["path"]
    assert (out_dir / founder["path"]).exists(), (
        f"founder photo not copied into package at {founder['path']}"
    )

    # ── ST-07A with fallstudie_number==3 (slot 14): case-study-3 resolved ──
    case3 = _page(manifest, 14)
    portrait3 = next(s for s in case3["slots"] if s["slot_id"] == "case_study_portrait")
    assert portrait3["status"] == "resolved", portrait3
    assert portrait3["path"].startswith("assets/")
    assert (out_dir / portrait3["path"]).exists()

    # ── ST-05 (slot 3): 3 proof photos resolved (proof-1/2/3) ──
    about = _page(manifest, 3)
    proofs = [s for s in about["slots"] if s["slot_id"] == "proof"]
    assert len(proofs) == 3, [s["slot_id"] for s in about["slots"]]
    assert all(s["status"] == "resolved" for s in proofs), proofs
    for s in proofs:
        assert s["path"].startswith("assets/")
        assert (out_dir / s["path"]).exists()

    # ── slot_summary: at least the 5 real photos resolved ──
    assert manifest["slot_summary"]["resolved"] >= 5, manifest["slot_summary"]

    # ── case studies whose number != 3 are missing_required + NAMED ──
    for slot, expected_stub in ((10, "case-study-1"), (12, "case-study-2")):
        page = _page(manifest, slot)
        portrait = next(
            s for s in page["slots"] if s["slot_id"] == "case_study_portrait"
        )
        assert portrait["status"] == "missing_required", portrait
        assert portrait["expected"], "missing_required slot must NAME the file"
        assert expected_stub in str(portrait["expected"]), portrait["expected"]

    # The named misses also surface in slot_summary.missing for QA.
    missing_expected = {m["expected"] for m in manifest["slot_summary"]["missing"]}
    assert {"case-study-1", "case-study-2"} <= missing_expected, missing_expected
