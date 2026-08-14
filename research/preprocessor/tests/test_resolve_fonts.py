"""Tests for Stage 2 — resolve_fonts."""

from __future__ import annotations

from pathlib import Path

from models import BrandProfile
from stages.resolve_fonts import (
    DEFAULT_FONT_BODY_FILE,
    DEFAULT_FONT_BODY_NAME,
    DEFAULT_FONT_HEADING_FILE,
    DEFAULT_FONT_HEADING_NAME,
    resolve_fonts,
)


def test_no_brand_profile_resolves_to_chassis_defaults() -> None:
    """When no brand_profile is supplied, both fonts default to the
    chassis Priorität-2 system fonts (Montserrat + Source Sans 3).
    """
    cfg = resolve_fonts(brand_profile=None)
    assert cfg.font_heading_name == DEFAULT_FONT_HEADING_NAME
    assert cfg.font_body_name == DEFAULT_FONT_BODY_NAME
    assert cfg.source == "chassis_default"
    # Paths populated and point at the chassis fonts directory.
    assert cfg.font_heading_path is not None
    assert cfg.font_body_path is not None
    assert cfg.font_heading_path.endswith(DEFAULT_FONT_HEADING_FILE)
    assert cfg.font_body_path.endswith(DEFAULT_FONT_BODY_FILE)


def test_empty_brand_profile_also_defaults() -> None:
    cfg = resolve_fonts(brand_profile=BrandProfile())
    assert cfg.source == "chassis_default"
    assert cfg.font_heading_name == DEFAULT_FONT_HEADING_NAME
    assert cfg.font_body_name == DEFAULT_FONT_BODY_NAME


def test_brand_profile_with_montserrat_resolves_to_chassis() -> None:
    """If the brand_profile explicitly names the chassis default heading
    font, that's still the chassis-default resolution.
    """
    cfg = resolve_fonts(BrandProfile(font_head="Montserrat", font_body="Source Sans 3"))
    assert cfg.source == "chassis_default"
    assert cfg.font_heading_path is not None
    assert cfg.font_body_path is not None


def test_source_sans_pro_alias_resolves_as_default() -> None:
    """Source Sans 3 IS Source Sans Pro (Adobe renamed in 2021). A
    profile naming the legacy alias still resolves to the chassis
    Source Sans 3 file.
    """
    cfg = resolve_fonts(BrandProfile(font_body="Source Sans Pro"))
    assert cfg.source == "chassis_default"
    assert cfg.font_body_name == DEFAULT_FONT_BODY_NAME


def test_custom_heading_font_marks_customer_upload_needed() -> None:
    """A request for a non-default heading font cannot be served by the
    chassis bundle today — Phase A flags it as needing customer upload
    (no fetch in Phase A; that's Phase F's job).
    """
    cfg = resolve_fonts(BrandProfile(font_head="Acme Display"))
    assert cfg.source == "customer_upload_needed"
    assert cfg.font_heading_name == "Acme Display"
    assert cfg.font_heading_path is None
    # Body still defaults.
    assert cfg.font_body_name == DEFAULT_FONT_BODY_NAME
    assert cfg.font_body_path is not None


def test_custom_body_font_marks_customer_upload_needed() -> None:
    cfg = resolve_fonts(BrandProfile(font_body="Acme Text"))
    assert cfg.source == "customer_upload_needed"
    assert cfg.font_body_name == "Acme Text"
    assert cfg.font_body_path is None


def test_chassis_default_paths_resolve_to_existing_files() -> None:
    """Sanity: the chassis font files referenced by Stage 2 actually
    exist on disk. Catches the case where the chassis fonts dir moved
    or the variable files were renamed.
    """
    cfg = resolve_fonts(brand_profile=None)
    assert Path(cfg.font_heading_path).exists(), (
        f"chassis heading font missing on disk: {cfg.font_heading_path}"
    )
    assert Path(cfg.font_body_path).exists(), (
        f"chassis body font missing on disk: {cfg.font_body_path}"
    )
