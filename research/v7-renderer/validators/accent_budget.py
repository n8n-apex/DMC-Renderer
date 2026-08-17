"""Accent budget validator.

Checks that the client's accent colour (whatever hue the brand profile's
`brand_accent` field supplies — hue-agnostic) stays within budget on
every rendered page.

Two rules, AND'd:

  AREA   — accent pixels ≤ 10% of page surface, per page.
           Citation: `08_DMC_Design_System_v2.md` C.2 L162 (verbatim):
             "Akzentfarbe → Highlights, Zahlen, Icons, sparsam
              eingesetzt (max. 10% Flächenanteil pro Seite)"
           Grammar §3.6 ACCENT BUDGET PER PAGE [HARD].

  LOCATION — accent fires only at allowed element classes (kickers /
           FALLSTUDIE stamp, panel fills, oversized quote glyphs, URLs,
           inline data emphasis, icons, attribution labels).
           Citation: grammar §3.7 ACCENT FIRING LOCATIONS [HARD]
           (allowed-list, hue-agnostic).

Hue-agnostic — the validator reads `brand.brand_accent` from the brand
profile and matches pixel clusters against that hex (±ΔE 10). It never
references a literal colour name; the brand's accent hex is the only
input.

History: renamed from validators/coral.py in M2c (2026-05-23). "coral"
was one client's brand_accent value, not a chassis concept. The matrix
2026-05-23 MOVE 1 block ROW C1 textual correction authorized the
rename. Two-path selection seam (C2) deleted with the rename: there is
one validator, one path.

Error code: `accent_budget_exceeded`. Per the matrix 2026-05-23 MOVE 1
block, the n8n branch that previously matched `coral_budget_exceeded`
is updated to match the new string (string-only coupling, no Python
import path).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Allow flat imports from the chassis package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from brand_tokens import BrandConfig  # noqa: E402


# ============================================================
# The single error code emitted on validation failure.
#
# Stable kebab-case identifier. The n8n pipeline branches on this code.
# Renamed from `coral_budget_exceeded` to `accent_budget_exceeded` per
# the matrix 2026-05-23 MOVE 1 block ROW C1 textual correction
# (authorized rename, user 2026-05-19 / 2026-05-23).
# ============================================================

ACCENT_BUDGET_EXCEEDED: str = "accent_budget_exceeded"


@dataclass(frozen=True)
class AccentBudgetResult:
    """Result of an accent-budget check.

    `passed`     — True iff the page satisfies both AREA and LOCATION rules.
    `error_code` — ACCENT_BUDGET_EXCEEDED on failure; None on pass.
    `details`    — human-readable explanation; not API-stable.
    """
    passed: bool
    error_code: Optional[str]
    details: Optional[str]


class AccentBudgetValidator:
    """Single-path accent budget + firing-location validator.

    Constructed once per render. Reads `brand.brand_accent` from the
    BrandConfig; that hex is the matching target. Hue-agnostic.

    Usage:
        validator = AccentBudgetValidator(brand=resolved_brand_config)
        result = validator.validate(rendered_html, rendered_pdf_pages)
        if not result.passed:
            raise RenderValidationError(result.error_code, result.details)
    """

    def __init__(self, brand: BrandConfig):
        self.brand = brand

    def validate(
        self,
        rendered_html: str,
        rendered_pdf_pages: list,
    ) -> AccentBudgetResult:
        """Run the accent-budget check on the rendered output.

        Stub. Real implementation (post-decontamination) is described in
        `_check_accent_budget` below — it rasterizes each page, finds
        pixel clusters matching `brand.brand_accent` (±ΔE 10), computes
        area share, and classifies each cluster's nearest DOM ancestor
        against the §3.7 firing-location whitelist.
        """
        return self._check_accent_budget(rendered_html, rendered_pdf_pages)

    def _check_accent_budget(
        self,
        rendered_html: str,
        rendered_pdf_pages: list,
    ) -> AccentBudgetResult:
        """Combined AREA + LOCATION check (stub for post-decontamination).

        Real implementation:
          AREA (§3.6):
            - Rasterize each page (PyMuPDF, 144 dpi).
            - Find connected accent regions (`brand.brand_accent` ±ΔE 10).
            - Compute pixel ratio; assert ≤10% per page.
          LOCATION (§3.7):
            - Parse rendered HTML into a DOM.
            - For each accent region, map to its DOM ancestor via
              bbox-to-element matching.
            - Classify ancestor into the §3.7 allowed-list:
              kickers / FALLSTUDIE stamp; panel fills (CTA panels,
              callout panels); oversized quote glyphs (P-15); URLs in
              CTA contexts; inline data emphasis; line-icons / checks;
              attribution labels in pullquotes.
          On any violation:
            return AccentBudgetResult(
                passed=False,
                error_code=ACCENT_BUDGET_EXCEEDED,
                details="page N: <hue>-cluster at <bbox> classified as
                         <non-allowed-element-class>",
            )

        Until that lands, this stub returns passed=True. The chassis
        seam is real (this validator is instantiated and called per
        render); the pixel/DOM logic is a separate move.
        """
        return AccentBudgetResult(
            passed=True,
            error_code=None,
            details="accent-budget validation stub (post-decontamination work)",
        )
