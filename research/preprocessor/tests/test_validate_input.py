"""Tests for Stage 1 — validate_and_resolve_brand_tokens."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from models import RenderRequest
from stages.validate_input import validate_and_resolve_brand_tokens


# ─────────────────────────────────────────────────────────────────────────────
# Sample request loader (uses the on-disk fixture)
# ─────────────────────────────────────────────────────────────────────────────


_FIXTURE_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "sample_render_request.json"
)


def _load_sample() -> dict[str, Any]:
    with _FIXTURE_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def _request(overrides: dict[str, Any] | None = None) -> RenderRequest:
    data = _load_sample()
    if overrides:
        _deep_merge(data, overrides)
    return RenderRequest.model_validate(data)


def _deep_merge(target: dict, patch: dict) -> None:
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(target.get(k), dict):
            _deep_merge(target[k], v)
        else:
            target[k] = v


# ─────────────────────────────────────────────────────────────────────────────
# Green path
# ─────────────────────────────────────────────────────────────────────────────


def test_sample_fixture_validates_clean() -> None:
    """The on-disk sample fixture parses, validates, and resolves to a
    populated BrandTokensResolved with zero errors and zero warnings.
    """
    brand_tokens, errors, warnings = validate_and_resolve_brand_tokens(_request())
    assert errors == [], f"unexpected errors: {errors}"
    assert warnings == [], f"unexpected warnings: {warnings}"
    assert brand_tokens is not None


def test_brand_tokens_mapping_matches_chassis_brandconfig_shape() -> None:
    """The resolved object has exactly the 10 flat fields that chassis
    BrandConfig consumes (M2c-collapsed shape).
    """
    brand_tokens, _, _ = validate_and_resolve_brand_tokens(_request())
    expected = {
        "brand_primary", "brand_accent", "brand_neutral_dark",
        "brand_neutral_mid", "brand_neutral_light", "font_heading",
        "font_body", "qr_target_url", "company_name_short",
        "company_url_display",
    }
    actual = set(brand_tokens.model_dump().keys())
    assert actual == expected, (
        f"BrandTokensResolved shape drifted from chassis BrandConfig 10 fields. "
        f"missing={expected - actual} extra={actual - expected}"
    )


def test_hex_mapping_dark_accent_light() -> None:
    """The 3 input hexes land on the documented destinations:
       hex_dark → brand_primary, hex_accent → brand_accent,
       hex_light → brand_neutral_light.
    """
    brand_tokens, _, _ = validate_and_resolve_brand_tokens(_request())
    assert brand_tokens.brand_primary == "#1A2540"
    assert brand_tokens.brand_accent == "#E97E47"
    assert brand_tokens.brand_neutral_light == "#F5EFE3"


def test_derived_neutrals_use_universal_defaults_when_not_supplied() -> None:
    """The 3-hex flat input doesn't carry dark/mid neutrals. When no
    brand_profile is supplied, the chassis-agnostic defaults fill in.
    """
    brand_tokens, _, _ = validate_and_resolve_brand_tokens(_request())
    # Defaults are documented in stages/validate_input.py.
    assert brand_tokens.brand_neutral_dark == "#0F0F1F"
    assert brand_tokens.brand_neutral_mid == "#7A7A8C"


def test_brand_profile_overrides_universal_defaults() -> None:
    """When the optional brand_profile supplies richer neutrals,
    Stage 1 prefers them over the universal fallback constants.
    """
    brand_tokens, _, _ = validate_and_resolve_brand_tokens(
        _request({
            "client": {
                "brand_profile": {
                    "brand_neutral_dark": "#101010",
                    "brand_neutral_mid": "#888899",
                }
            }
        })
    )
    assert brand_tokens.brand_neutral_dark == "#101010"
    assert brand_tokens.brand_neutral_mid == "#888899"


def test_brand_profile_overrides_flat_hex_when_richer() -> None:
    """Per spec: 'If brand_profile exists (from Mode 1), prefer its
    richer data.' A brand_profile.brand_primary supersedes the flat
    client.brand_hex_dark mapping.
    """
    brand_tokens, _, _ = validate_and_resolve_brand_tokens(
        _request({
            "client": {
                "brand_profile": {"brand_primary": "#000FFF"}
            }
        })
    )
    assert brand_tokens.brand_primary == "#000FFF"


def test_company_and_url_mapping() -> None:
    """company → company_name_short; website_url → qr_target_url +
    company_url_display (stripped of protocol/www/trailing slash).
    """
    brand_tokens, _, _ = validate_and_resolve_brand_tokens(_request())
    assert brand_tokens.company_name_short == "mein.werkzeug.koffer GmbH"
    assert brand_tokens.qr_target_url == "https://www.meinwerkzeugkoffer.de"
    assert brand_tokens.company_url_display == "meinwerkzeugkoffer.de"


# ─────────────────────────────────────────────────────────────────────────────
# Red path — semantic validation errors
# ─────────────────────────────────────────────────────────────────────────────


def test_page_count_not_divisible_by_4_errors() -> None:
    brand_tokens, errors, _ = validate_and_resolve_brand_tokens(
        _request({"report_json": {"meta": {"page_count_target": 17}}})
    )
    assert brand_tokens is None
    assert any(e.code == "page_count_invalid" for e in errors)


def test_page_count_22_errors() -> None:
    """22 is divisible by 2 but not allowed (allowed = {16,20,24,28})."""
    brand_tokens, errors, _ = validate_and_resolve_brand_tokens(
        _request({"report_json": {"meta": {"page_count_target": 22}}})
    )
    assert brand_tokens is None
    assert any(e.code == "page_count_invalid" for e in errors)


def test_fewer_than_3_case_studies_errors() -> None:
    """Mutate the sample so it carries only 2 ST-07A pages."""
    sample = _load_sample()
    # Replace the 3rd case study (slot 14) with a different type.
    for page in sample["report_json"]["pages"]:
        if page["slot"] == 14:
            page["type"] = "ST-09"
    req = RenderRequest.model_validate(sample)
    brand_tokens, errors, _ = validate_and_resolve_brand_tokens(req)
    assert brand_tokens is None
    assert any(e.code == "case_study_count_too_low" for e in errors)


def test_v2_five_case_studies_pass() -> None:
    """The legacy v2 validator permits at least three case studies."""
    sample = _load_sample()
    # Sample has 3 ST-07A (slots 10/12/14); promote two ST-07B slots to ST-07A
    # so the report carries exactly five case studies.
    for page in sample["report_json"]["pages"]:
        if page["slot"] in (11, 13):
            page["type"] = "ST-07A"
    case_count = sum(1 for p in sample["report_json"]["pages"] if p["type"] == "ST-07A")
    assert case_count == 5
    req = RenderRequest.model_validate(sample)
    _, errors, _ = validate_and_resolve_brand_tokens(req)
    assert not any(e.code == "case_study_count_too_low" for e in errors)


def test_v2_case_study_too_low_message_says_at_least_not_exactly() -> None:
    """The legacy v2 message must describe its at-least-three rule."""
    sample = _load_sample()
    # Drop to 2 case studies to trigger the error and inspect its message.
    for page in sample["report_json"]["pages"]:
        if page["slot"] == 14:
            page["type"] = "ST-09"
    req = RenderRequest.model_validate(sample)
    _, errors, _ = validate_and_resolve_brand_tokens(req)
    msg = next(e.message for e in errors if e.code == "case_study_count_too_low")
    assert "exactly three" not in msg.lower()
    assert "at least" in msg.lower()


def test_s1_wrong_type_errors() -> None:
    """Slot 1 must be ST-01 per grammar §1.2 FIXED."""
    sample = _load_sample()
    for page in sample["report_json"]["pages"]:
        if page["slot"] == 1:
            page["type"] = "ST-02"  # wrong type for FIXED slot 1
    req = RenderRequest.model_validate(sample)
    brand_tokens, errors, _ = validate_and_resolve_brand_tokens(req)
    assert brand_tokens is None
    assert any(e.code == "fixed_slot_s1_wrong_type" for e in errors)


def test_s20_wrong_type_errors() -> None:
    """Final slot (S20 for a 20-page report) must be ST-03."""
    sample = _load_sample()
    for page in sample["report_json"]["pages"]:
        if page["slot"] == 20:
            page["type"] = "ST-22"
    req = RenderRequest.model_validate(sample)
    brand_tokens, errors, _ = validate_and_resolve_brand_tokens(req)
    assert brand_tokens is None
    assert any(e.code == "fixed_slot_last_wrong_type" for e in errors)


def test_invalid_hex_errors() -> None:
    """A non-hex character in a colour input is rejected."""
    brand_tokens, errors, _ = validate_and_resolve_brand_tokens(
        _request({"client": {"brand_hex_dark": "#GGGGGG"}})
    )
    assert brand_tokens is None
    assert any(e.code == "hex_value_invalid" for e in errors)


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic input validation — missing required field raises ValidationError
# ─────────────────────────────────────────────────────────────────────────────


def test_missing_brand_hex_dark_pydantic_raises() -> None:
    """Pydantic at the route boundary catches missing required fields
    BEFORE Stage 1 runs (the spec calls this 'REJECT LOUD'). A missing
    brand_hex_dark raises pydantic.ValidationError here.
    """
    sample = _load_sample()
    del sample["client"]["brand_hex_dark"]
    with pytest.raises(Exception):  # pydantic.ValidationError subclass
        RenderRequest.model_validate(sample)
