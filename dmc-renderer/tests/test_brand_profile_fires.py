"""A profile that is read but never fed to a fixture is still dead.

This closes G1: `build_v3` reads `envelope.brand_profile_id`, but no
calibration envelope ever set it, so every client rendered on default axes.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT / "research", ROOT / "research" / "v7-renderer", ROOT / "dmc-renderer"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from calibration_fixtures_v3 import envelope_for_profile  # noqa: E402
from tokens.brand_profile import profile_for  # noqa: E402


FIXTURE_ROOT = ROOT / "dmc-renderer" / "fixtures" / "calibration"


def _profile(fixture_id: str) -> dict:
    path = FIXTURE_ROOT / f"{fixture_id}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_calibration_fixtures_declare_distinct_profiles() -> None:
    ids = []
    for name in (
        "craft-trade",
        "service-business",
        "medical-practice",
        "apex-dense",
    ):
        profile = _profile(name)
        env = envelope_for_profile(profile, Path("/tmp/dmc-assets"))
        assert env.get("brand_profile_id"), (
            f"{profile['fixture_id']} declares no brand_profile_id"
        )
        ids.append(env["brand_profile_id"])
    assert len(set(ids)) > 1, (
        "every fixture resolving to one profile means axes are not firing"
    )


def test_declared_profile_id_resolves_and_has_data_attributes() -> None:
    profile = _profile("craft-trade")
    env = envelope_for_profile(profile, Path("/tmp/dmc-assets"))
    brand_profile = profile_for(env["brand_profile_id"])
    assert brand_profile.data_attributes(), (
        "profile emits no body data-attrs -> axes.css can never match"
    )
