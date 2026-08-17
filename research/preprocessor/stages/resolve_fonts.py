"""Stage 2 — resolve font configuration.

Looks at the (optional) brand_profile.font_head + font_body. If they
match the chassis's Priorität-2 system fonts (Montserrat + Source
Sans 3, already on disk in `research/v7-renderer/fonts/`), point at
those. If a different font is requested, mark
`source="customer_upload_needed"` — Phase F (`/onboard`) will fetch
or the customer will upload separately.

No fetching in Phase A. No Google Fonts API call in Phase A. Pure
lookup against the chassis defaults.

Citations:
  - DMC_InDesign_Spec_v1.md L484-489: Priorität-2 system fonts
    (Headlines Montserrat ExtraBold/Bold/SemiBold;
     Fließtext Source Sans Pro Regular/SemiBold/Bold/Italic)
  - 08_DMC_Design_System_v2.md B.2 L91-92: Priorität-1 customer font
    overrides when the client supplies a Hausschrift
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from models import BrandProfile, FontConfig


# Path to the chassis fonts directory. The pre-processor sits at
# `research/preprocessor/stages/`; the chassis fonts live at
# `research/v7-renderer/fonts/`. From this file: parent.parent.parent
# = research/, then + v7-renderer/fonts.
_CHASSIS_FONTS_DIR = (
    Path(__file__).resolve().parent.parent.parent / "v7-renderer" / "fonts"
).resolve()

# Chassis-default Priorität-2 system fonts (already on disk; see
# CHASSIS-NOTES.md "Fonts" section). Brand-agnostic — used for every
# client that doesn't supply a Hausschrift.
DEFAULT_FONT_HEADING_NAME = "Montserrat"
DEFAULT_FONT_BODY_NAME = "Source Sans 3"
DEFAULT_FONT_HEADING_FILE = "Montserrat[wght].ttf"
DEFAULT_FONT_BODY_FILE = "SourceSans3[wght].ttf"

# Aliases that resolve to the chassis defaults. Adobe renamed Source
# Sans Pro → Source Sans 3 in 2021; both names resolve to the same
# typeface lineage in the variable font file.
_HEADING_ALIASES = frozenset({"montserrat"})
_BODY_ALIASES = frozenset({"source sans 3", "source sans pro", "sourcesans3", "sourcesanspro"})


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────


def resolve_fonts(brand_profile: Optional[BrandProfile]) -> FontConfig:
    """Resolve heading + body fonts. Returns a FontConfig.

    Logic:
      - If brand_profile.font_head requests a non-chassis-default
        family → mark heading as customer_upload_needed.
      - If brand_profile.font_body requests a non-chassis-default
        family → mark body as customer_upload_needed.
      - Otherwise (default path): both fonts resolve to the chassis's
        on-disk Montserrat + Source Sans 3 variable files.

    `source` summarises the resolution:
      "chassis_default"        — both fonts resolved to chassis defaults
      "customer_upload_needed" — at least one font needs fetch/upload
    """
    heading_name, heading_path = _resolve_heading(brand_profile)
    body_name, body_path = _resolve_body(brand_profile)

    if heading_path is None or body_path is None:
        source = "customer_upload_needed"
    else:
        source = "chassis_default"

    return FontConfig(
        font_heading_name=heading_name,
        font_body_name=body_name,
        font_heading_path=str(heading_path) if heading_path else None,
        font_body_path=str(body_path) if body_path else None,
        source=source,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _resolve_heading(profile: Optional[BrandProfile]) -> tuple[str, Optional[Path]]:
    """Return (font_family_name, on_disk_path_or_None)."""
    requested = (profile.font_head if profile and profile.font_head else None)
    if requested and requested.strip().lower() not in _HEADING_ALIASES:
        # A non-default heading font is requested. Stage 2 in Phase A
        # does NOT fetch; mark needed and let Phase F handle it.
        return (requested.strip(), None)
    # Default path.
    return (
        DEFAULT_FONT_HEADING_NAME,
        _CHASSIS_FONTS_DIR / DEFAULT_FONT_HEADING_FILE,
    )


def _resolve_body(profile: Optional[BrandProfile]) -> tuple[str, Optional[Path]]:
    """Return (font_family_name, on_disk_path_or_None)."""
    requested = (profile.font_body if profile and profile.font_body else None)
    if requested and requested.strip().lower() not in _BODY_ALIASES:
        return (requested.strip(), None)
    return (
        DEFAULT_FONT_BODY_NAME,
        _CHASSIS_FONTS_DIR / DEFAULT_FONT_BODY_FILE,
    )
