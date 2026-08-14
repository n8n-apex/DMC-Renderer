"""Tests for the v2.0 package contract."""
from __future__ import annotations
import pytest
from pydantic import ValidationError
from models_package import ResolvedPackageManifest, ResolvedPageV2


def _minimal() -> dict:
    return {
        "version": "2.0", "generated_at": "NORMALIZED", "record_id": "RID",
        "brand": {},
        "axes": {"headline_type": "serif", "palette": "mono_tonal",
            "accent_mechanic": "tonal_same_hue", "texture": "smooth",
            "ground_mode": "light", "qr_enabled": False, "density": "balanced"},
        "provenance": {"headline_type": "default"},
        "fonts": {"heading": {}, "body": {}}, "report_assets": [],
        "pages": [{"slot": 1, "st_type": "ST-01", "data": {}, "charts": [],
                   "social_proof": None, "slots": [], "assets": []}],
        "validation": {}, "asset_summary": {}, "asset_warnings": [],
    }


def test_v2_manifest_validates() -> None:
    m = ResolvedPackageManifest.model_validate(_minimal())
    assert m.version == "2.0"
    assert m.axes.ground_mode == "light"
    assert m.pages[0].st_type == "ST-01"


def test_v2_rejects_wrong_version() -> None:
    bad = _minimal(); bad["version"] = "1.0"
    with pytest.raises(ValidationError):
        ResolvedPackageManifest.model_validate(bad)


def test_v2_rejects_unknown_toplevel_key() -> None:
    bad = _minimal(); bad["surprise"] = 1
    with pytest.raises(ValidationError):
        ResolvedPackageManifest.model_validate(bad)


def test_page_allows_missing_optional_blocks() -> None:
    p = ResolvedPageV2.model_validate({"slot": 2, "st_type": "ST-02"})
    assert p.charts == [] and p.social_proof is None and p.slots == []
