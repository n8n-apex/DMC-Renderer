from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT / "research") not in sys.path:
    sys.path.insert(0, str(ROOT / "research"))

from postprocessor.profiles.schema import (  # noqa: E402
    DigitalProfile,
    DigitalProfileFailure,
    digital_profile_sha256,
    load_digital_profile,
)


PROFILE_PATH = ROOT / "research" / "postprocessor" / "profiles" / "dmc_digital_v1.json"


def test_stored_digital_profile_loads_and_validates() -> None:
    profile = load_digital_profile(PROFILE_PATH)

    assert profile.profile_id == "dmc_digital_v1"
    assert profile.version == "1.0.0"
    assert profile.pdf_standard_target == "preserve_source"
    assert profile.minimum_text_preservation_ratio >= 0.99
    assert profile.preserve_links is True
    assert profile.preserve_page_sizes is True
    assert profile.preserve_metadata is True
    assert profile.preserve_font_references is True
    assert profile.metadata_normalization.strip_creation_date is False
    assert profile.metadata_normalization.strip_modification_date is False
    assert profile.metadata_normalization.normalize_producer is False
    assert profile.production_allowed is True


def test_digital_profile_hash_is_deterministic() -> None:
    first = load_digital_profile(PROFILE_PATH)
    second = load_digital_profile(PROFILE_PATH)

    assert digital_profile_sha256(first) == digital_profile_sha256(second)
    assert len(digital_profile_sha256(first)) == 64


def test_missing_digital_profile_is_blocking(tmp_path: Path) -> None:
    with pytest.raises(DigitalProfileFailure) as caught:
        load_digital_profile(tmp_path / "missing-digital-profile.json")

    assert caught.value.code == "digital_profile_missing"


def test_digital_profile_schema_forbids_unknown_fields() -> None:
    payload = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    payload["magic"] = True

    with pytest.raises(ValidationError):
        DigitalProfile.model_validate(payload)


def test_digital_profile_without_production_approval_is_rejected(tmp_path: Path) -> None:
    payload = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    payload["production_allowed"] = False
    blocked = tmp_path / "blocked-digital.json"
    blocked.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(DigitalProfileFailure) as caught:
        load_digital_profile(blocked)

    assert caught.value.code == "digital_profile_not_production_approved"


def test_metadata_normalization_conflicts_with_preserve_metadata() -> None:
    payload = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    payload["preserve_metadata"] = True
    payload["metadata_normalization"]["strip_creation_date"] = True

    with pytest.raises(ValidationError):
        DigitalProfile.model_validate(payload)
