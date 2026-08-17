"""Stage 1 — validate input + map to chassis brand_tokens shape.

Pure validation + transformation. No I/O, no external calls. Pydantic
already enforced shape + required fields at the FastAPI route layer
(missing keys → 422); this stage runs the SEMANTIC checks the grammar
mandates:

  - page_count_target ∈ {16, 20, 24, 28}  (grammar §1.2 [HARD])
  - ≥ 3 case studies (count of ST-07A pages)  (grammar §1.4 [HARD])
  - FIXED slot integrity: S1=ST-01, S20=ST-03  (grammar §1.2 [HARD])

…and the mapping the chassis needs:

  - 3 hex inputs → 10 flat BrandConfig fields
  - company → company_name_short
  - website_url → qr_target_url + company_url_display (stripped)
  - brand_profile (if present) richer overrides per-field

All thresholds in this module trace to citations in
`richard-grammar-v2.md` (§1.2 slot plan, §1.4 invariants).
"""

from __future__ import annotations

import re
from typing import Optional

from models import (
    BrandTokensResolved,
    ClientInput,
    RenderRequest,
    ReportJson,
    ValidationIssue,
)


# Universal fallback values used when neither the flat input nor a
# brand_profile supplies the dark/mid neutral. These are brand-agnostic
# defaults — the same constant for every client — and exist only so the
# 10-field BrandConfig shape can be populated when the upstream payload
# carries only the 3-hex minimum. Future Mode-1 brand profiles can
# supply richer neutrals and these defaults are then bypassed.
_DEFAULT_NEUTRAL_DARK = "#0F0F1F"
_DEFAULT_NEUTRAL_MID = "#7A7A8C"

# Allowed page counts per grammar §1.2 + InDesign Spec L17
# (Druckbögen — divisible by 4: 16 / 20 / 24 / 28).
_ALLOWED_PAGE_COUNTS = frozenset({16, 20, 24, 28})

# FIXED slots per grammar §1.2.
_FIXED_S1_TYPE = "ST-01"  # Cover
_FIXED_S20_TYPE = "ST-03"  # Hard-CTA back cover

# Case-study type identifier per Master System Modul 8.
_CASE_STUDY_TYPE = "ST-07A"
_MIN_CASE_STUDIES = 3  # grammar §1.4 invariant: at least 3 (≥3) case studies per report, every client.

# Hex format sanity (rough — Pydantic already enforced min_length=4).
_HEX_RE = re.compile(r"^#?[0-9a-fA-F]{3,8}$")


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────


def validate_and_resolve_brand_tokens(
    request: RenderRequest,
) -> tuple[Optional[BrandTokensResolved], list[ValidationIssue], list[ValidationIssue]]:
    """Run Stage 1 against a RenderRequest.

    Returns a (brand_tokens_or_None, errors, warnings) triple. When
    `errors` is non-empty, `brand_tokens_or_None` may be None (the
    pre-processor cannot produce a valid package for the chassis).
    """
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []

    # Semantic checks on the report structure.
    errors.extend(_check_page_count(request.report_json))
    errors.extend(_check_case_study_count(request.report_json))
    errors.extend(_check_fixed_slots(request.report_json))

    # Light hex sanity on the 3 flat hexes (Pydantic already enforced
    # min_length=4; this catches non-hex characters).
    errors.extend(_check_hex_sanity(request.client))

    # If we already have critical errors, don't bother mapping —
    # downstream can't use a half-validated payload.
    if errors:
        return None, errors, warnings

    # Build the 10-field BrandConfig shape.
    brand_tokens = _resolve_brand_tokens(request.client)
    return brand_tokens, errors, warnings


# ─────────────────────────────────────────────────────────────────────────────
# Semantic checks
# ─────────────────────────────────────────────────────────────────────────────


def _check_page_count(report: ReportJson) -> list[ValidationIssue]:
    page_count = report.meta.page_count_target
    if page_count not in _ALLOWED_PAGE_COUNTS:
        return [
            ValidationIssue(
                code="page_count_invalid",
                message=(
                    f"page_count_target must be one of "
                    f"{sorted(_ALLOWED_PAGE_COUNTS)} "
                    f"(grammar §1.2 [HARD]: Druckbögen, divisible by 4); "
                    f"got {page_count}"
                ),
                location="report_json.meta.page_count_target",
            )
        ]
    return []


def _check_case_study_count(report: ReportJson) -> list[ValidationIssue]:
    count = sum(1 for page in report.pages if page.type == _CASE_STUDY_TYPE)
    if count < _MIN_CASE_STUDIES:
        return [
            ValidationIssue(
                code="case_study_count_too_low",
                message=(
                    f"report must contain at least {_MIN_CASE_STUDIES} "
                    f"{_CASE_STUDY_TYPE} pages (grammar §1.4 invariant: "
                    f"at least 3 (≥3) case studies per report, every "
                    f"client); found {count}"
                ),
                location="report_json.pages",
            )
        ]
    return []


def _check_fixed_slots(report: ReportJson) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    pages_by_slot = {page.slot: page for page in report.pages}

    if 1 in pages_by_slot and pages_by_slot[1].type != _FIXED_S1_TYPE:
        issues.append(
            ValidationIssue(
                code="fixed_slot_s1_wrong_type",
                message=(
                    f"slot 1 must carry {_FIXED_S1_TYPE} (Cover, grammar §1.2 "
                    f'FIXED); got {pages_by_slot[1].type!r}'
                ),
                location="report_json.pages[slot=1]",
            )
        )

    last_slot = report.meta.page_count_target
    if last_slot in pages_by_slot and pages_by_slot[last_slot].type != _FIXED_S20_TYPE:
        issues.append(
            ValidationIssue(
                code="fixed_slot_last_wrong_type",
                message=(
                    f"final slot ({last_slot}) must carry {_FIXED_S20_TYPE} "
                    f"(Hard-CTA back cover, grammar §1.2 FIXED); got "
                    f"{pages_by_slot[last_slot].type!r}"
                ),
                location=f"report_json.pages[slot={last_slot}]",
            )
        )

    return issues


def _check_hex_sanity(client: ClientInput) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for field_name, value in (
        ("brand_hex_dark", client.brand_hex_dark),
        ("brand_hex_light", client.brand_hex_light),
        ("brand_hex_accent", client.brand_hex_accent),
    ):
        if not _HEX_RE.match(value):
            issues.append(
                ValidationIssue(
                    code="hex_value_invalid",
                    message=(
                        f"{field_name} must be a hex colour (3-8 hex chars, "
                        f"optional leading '#'); got {value!r}"
                    ),
                    location=f"client.{field_name}",
                )
            )
    return issues


# ─────────────────────────────────────────────────────────────────────────────
# Brand tokens resolution (3 hexes → 10 flat fields)
# ─────────────────────────────────────────────────────────────────────────────


def _resolve_brand_tokens(client: ClientInput) -> BrandTokensResolved:
    """Map the n8n input shape to the chassis BrandConfig 10-field shape.

    Precedence (most-preferred first):
      1. `client.brand_profile.<field>` (Mode 1 output, when present)
      2. flat hex inputs (`client.brand_hex_dark` etc.)
      3. universal fallback constants for the two neutrals not in the
         3-hex input

    Font fields are placeholders here; Stage 2 (`resolve_fonts.py`)
    fills them in.
    """
    profile = client.brand_profile

    # Hex resolution. brand_profile wins where it speaks; flat fields
    # fill the rest.
    brand_primary = (profile and profile.brand_primary) or client.brand_hex_dark
    brand_accent = (profile and profile.brand_accent) or client.brand_hex_accent
    brand_neutral_light = (profile and profile.brand_neutral_light) or client.brand_hex_light

    # The 3-hex flat input doesn't carry dark/mid neutrals. Prefer
    # brand_profile if present; else universal fallback constants.
    brand_neutral_dark = (
        profile.brand_neutral_dark if profile and profile.brand_neutral_dark
        else _DEFAULT_NEUTRAL_DARK
    )
    brand_neutral_mid = (
        profile.brand_neutral_mid if profile and profile.brand_neutral_mid
        else _DEFAULT_NEUTRAL_MID
    )

    # URLs.
    qr_target_url = client.website_url
    company_url_display = _strip_url_chrome(client.website_url)

    return BrandTokensResolved(
        brand_primary=brand_primary,
        brand_accent=brand_accent,
        brand_neutral_dark=brand_neutral_dark,
        brand_neutral_mid=brand_neutral_mid,
        brand_neutral_light=brand_neutral_light,
        # Font names are placeholders; Stage 2 overrides them.
        font_heading="",
        font_body="",
        qr_target_url=qr_target_url,
        company_name_short=client.company,
        company_url_display=company_url_display,
    )


def _strip_url_chrome(url: str) -> str:
    """Strip protocol + `www.` + trailing slash for display."""
    out = url.strip()
    for prefix in ("https://", "http://"):
        if out.lower().startswith(prefix):
            out = out[len(prefix):]
            break
    if out.lower().startswith("www."):
        out = out[4:]
    return out.rstrip("/")
