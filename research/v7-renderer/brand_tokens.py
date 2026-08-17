"""Brand-tokens ingestion — flat dict → BrandConfig.

Parses a flat brand-token dict into BrandConfig. No design_preferences,
no apex defaults. The input surface is the four upstream design fields
that Richard's pipeline actually sends (primaerfarbe_hex, akzentfarbe_hex,
logo_vorhanden, autorenfoto_vorhanden — per Master System Modul 4.1
L228-233) plus production-curated values (fonts, neutrals, URL, identity)
that the production side wraps around the upstream payload.

The chassis is INPUT-DRIVEN: client-specific values live ONLY in this
dict (and the fixture that feeds it). Logic never names a client; logic
reads `brand_accent` (whatever hex the client supplies) and uses it.

History (Move 2c, 2026-05-23): this module previously carried
BrandConfigError, APEX_DEFAULT_PROFILE, APEX_CORAL_COUNT_BUDGET, and a
9-field design_preferences nested object on BrandConfig. All deleted per
the 2026-05-18 RICHARD-PRIMARY block + 2026-05-23 MOVE 1 ROW C1
correction (A1 DELETE, A2 STRUCK, C1 STRUCK, D1 STRUCK, D2 STRUCK, B2
STRUCK byproducts). The flat 10-field shape below is what survives.
"""

from __future__ import annotations

from dataclasses import dataclass


# Required keys the input brand-token dict MUST supply. Anything missing
# raises ValueError at parse time, never mid-render.
_REQUIRED_KEYS: tuple[str, ...] = (
    "brand_primary",
    "brand_accent",
    "brand_neutral_dark",
    "brand_neutral_mid",
    "brand_neutral_light",
    "font_heading",
    "font_body",
    "qr_target_url",
    "company_name_short",
    "company_url_display",
)


@dataclass(frozen=True)
class BrandConfig:
    """Resolved brand configuration. The single object patterns consume
    for per-brand values.

    The input-driven principle: every field below is a per-client VALUE.
    Logic that consumes BrandConfig refers to fields by name (e.g.
    `brand.brand_accent`), never to the hex the field happens to hold
    for a particular client. The chassis treats every client's profile
    the same way; per-client examples are catalogued only in
    richard-grammar-v2.md §4.1 (data, not logic).
    """
    brand_primary: str           # hex; client's primary dark colour
    brand_accent: str            # hex; client's accent (hue-agnostic)
    brand_neutral_dark: str      # hex
    brand_neutral_mid: str       # hex
    brand_neutral_light: str     # hex; page-background-ish
    font_heading: str            # literal font-family name (e.g. "Montserrat")
    font_body: str               # literal font-family name (e.g. "Source Sans 3")
    qr_target_url: str           # URL the QR code encodes
    company_name_short: str      # wordmark / running header text
    company_url_display: str     # display URL shown in pullquote panel


def parse_brand_tokens(brand_tokens: dict) -> BrandConfig:
    """Read a flat brand-token dict, return a BrandConfig.

    The 10 required keys (see `_REQUIRED_KEYS`) must all be present.
    Missing any required key raises ValueError naming the missing field.
    No defaulting, no apex fallback, no design_preferences branching —
    the chassis does not synthesize required values.
    """
    missing = [k for k in _REQUIRED_KEYS if k not in brand_tokens]
    if missing:
        raise ValueError(
            f"brand_tokens is missing required key(s): {missing}. "
            f"The chassis does not synthesize brand values. "
            f"Supply all of: {list(_REQUIRED_KEYS)}."
        )

    return BrandConfig(
        brand_primary=brand_tokens["brand_primary"],
        brand_accent=brand_tokens["brand_accent"],
        brand_neutral_dark=brand_tokens["brand_neutral_dark"],
        brand_neutral_mid=brand_tokens["brand_neutral_mid"],
        brand_neutral_light=brand_tokens["brand_neutral_light"],
        font_heading=brand_tokens["font_heading"],
        font_body=brand_tokens["font_body"],
        qr_target_url=brand_tokens["qr_target_url"],
        company_name_short=brand_tokens["company_name_short"],
        company_url_display=brand_tokens["company_url_display"],
    )
