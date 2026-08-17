from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT / "research") not in sys.path:
    sys.path.insert(0, str(ROOT / "research"))

from postprocessor.profiles.schema import (  # noqa: E402
    PrintProfile,
    PrintProfileFailure,
    assert_profile_for_export,
    load_print_profile,
)


PROFILE_PATH = ROOT / "research" / "postprocessor" / "profiles" / "dmc_print_test.json"
ICC_PATH = ROOT / "research" / "postprocessor" / "tests" / "fixtures" / "srgb.icc"


def test_test_profile_has_verified_redistributable_icc_fixture() -> None:
    profile = load_print_profile(PROFILE_PATH)

    assert profile.profile_id == "dmc_print_test"
    assert profile.production_allowed is False
    assert hashlib.sha256(ICC_PATH.read_bytes()).hexdigest() == profile.icc_sha256
    assert profile.icc_path == str(ICC_PATH.resolve())


def test_missing_printer_profile_is_blocking(tmp_path: Path) -> None:
    with pytest.raises(PrintProfileFailure) as caught:
        load_print_profile(tmp_path / "missing-profile.json")

    assert caught.value.code == "print_profile_missing"


def test_production_export_rejects_test_profile() -> None:
    profile = load_print_profile(PROFILE_PATH)

    with pytest.raises(PrintProfileFailure) as caught:
        assert_profile_for_export(profile, production=True)

    assert caught.value.code == "print_profile_not_production_approved"


def test_profile_schema_forbids_unknown_and_incomplete_policy() -> None:
    payload = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    payload["magic"] = True

    with pytest.raises(ValidationError):
        PrintProfile.model_validate(payload)
