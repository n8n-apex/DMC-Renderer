"""Proof B seam tests: report-derived profile + client-assets resolver.

Built alongside dmc-renderer/tests/test_proof_b_apex.py; these cover the two
new preprocessor stages directly (fail-closed, input-driven, deterministic).
"""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest


def _envelope() -> dict:
    root = Path(__file__).resolve().parent.parent.parent.parent / "dmc-renderer"
    return json.loads((root / "fixtures" / "apex_consulting_payload.json").read_text())


def test_report_derived_profile_is_idempotent():
    from stages.plan_editorial_v3 import (
        _append_derived_profile_id,
        derive_report_profile,
        legacy_report_to_editorial_brief,
    )

    brief = legacy_report_to_editorial_brief(_envelope()["payload"])
    _append_derived_profile_id(brief)
    first = brief["product_profile_id"]
    profile_a = derive_report_profile(brief)
    # Re-running the acquire helpers on the same brief cannot drift the id.
    _append_derived_profile_id(brief)
    assert brief["product_profile_id"] == first
    assert derive_report_profile(brief).profile_id == profile_a.profile_id


def test_double_derive_keeps_same_brief_id():
    """Idempotency guard: importing and re-stamping a brief twice (e.g. the
    build_live path stamping then derive_report_profile reading) never ends up
    ``.derived.derived``."""
    from stages.plan_editorial_v3 import (
        _append_derived_profile_id,
        derive_report_profile,
        legacy_report_to_editorial_brief,
    )

    brief = legacy_report_to_editorial_brief(_envelope()["payload"])
    _append_derived_profile_id(brief)
    _append_derived_profile_id(brief)
    profile = derive_report_profile(brief)
    assert profile.profile_id.endswith(".derived")
    assert not profile.profile_id.endswith(".derived.derived")
    assert brief["product_profile_id"] == profile.profile_id


def test_client_assets_resolver_fails_closed_on_drive_urls(tmp_path: Path):
    """A Drive URL with no cached local copy must NOT produce a fabricated
    AssetRecord — it yields nothing (the case face honestly flags asset_gen)."""
    from stages.resolve_client_assets_v3 import resolve_client_assets_v3

    env = {
        "images": {
            "cover_hero": "https://drive.google.com/uc?id=1AhpgWjMu98VdUWI_pm-5kkejh_1Qqtfx"
        }
    }
    records = resolve_client_assets_v3(env, client_assets_root=tmp_path)
    assert records == ()


def test_client_assets_resolver_tags_local_identity_slot(tmp_path: Path):
    """A REAL local case portrait file resolves to an identity AssetRecord
    (the honest production path: the Drive folder already fetched)."""
    from PIL import Image
    from stages.resolve_client_assets_v3 import resolve_client_assets_v3

    portrait = tmp_path / "case_3_portrait.png"
    Image.new("RGB", (600, 800), (200, 40, 40)).save(portrait)
    env = {"images": {"case_study_portrait_3": str(portrait)}}
    records = resolve_client_assets_v3(env, client_assets_root=tmp_path)
    assert len(records) == 1
    assert records[0].semantic_class.value == "identity"
    assert records[0].pixel_width == 600
    assert records[0].pixel_height == 800
    local = Path(records[0].local_path)
    assert local.exists() or records[0].source_locator.endswith("case_3_portrait.png")


def test_client_assets_resolver_scene_is_not_identity(tmp_path: Path):
    """A scene/background image must not satisfy the case identity assets."""
    from PIL import Image
    from stages.resolve_client_assets_v3 import resolve_client_assets_v3

    scene = tmp_path / "status_quo_scene.png"
    Image.new("RGB", (1600, 900), (30, 30, 80)).save(scene)
    env = {"images": {"status_quo_scene": str(scene)}}
    records = resolve_client_assets_v3(env, client_assets_root=tmp_path)
    assert len(records) == 1
    assert records[0].semantic_class.value == "context"