"""Versioned, brand-agnostic RUBRIC config -- the "constitution" of the loop.

This module is pure DATA. It encodes the design-DNA rubric (spec §6: the
positive and negative tables) as a list of ``RubricRow`` records. The scoring
LOGIC lives separately in ``analysis.py`` so the judgment criteria can be
versioned, audited, and swapped without touching the scorer.

Brand-agnostic by construction: rows reference only ``PageFacts`` attribute
NAMES (booleans/floats already computed by perception) -- never client hex,
client names, or font-family literals. The engine-level font markers live
inside perception.py, not here.

Each row carries:
  * ``detect`` -- the evidence class needed to adjudicate it:
        "DET"     pure deterministic (a computed fact decides it),
        "VIS"     needs a vision model (not wired in this phase),
        "DET∧VIS" needs BOTH (we conservatively skip until VIS is wired).
  * ``fact_key`` -- the PageFacts attribute that scores the row, or None when
        no fact is computed yet (the capability map: None == "needs_fact").
  * ``knob_class`` -- which subsystem can FIX the defect ("renderer",
        "preprocessor", "asset_gen"); this routes the repair, not the score.
  * ``hard_fail`` -- a latching gate: any fired hard-fail row makes the page
        un-shippable regardless of reward (the anti-reward-hacking invariant).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Union

RUBRIC_VERSION = "1.0"

# N08 dead/hollow-space gate (spec §6.2). N08 now fires on the UNIFIED emptiness
# metric ``empty_gap`` -- the largest CONTIGUOUS run of rows that, over the
# central content column, are uniform near-WHITE (a background gap) OR uniform
# near-DARK (a content-less solid panel). This closes a metric-gaming hole: the
# old white-only ``dead_space_gap`` scored a hollow DARK panel (a big solid panel
# with one sentence) at ~0, so a page could "pass" by painting its empty region
# dark. ``empty_gap`` catches BOTH white gaps AND hollow dark/colored panels,
# while NOT firing on genuinely PACKED dark panels (light text breaks up their
# rows). Calibrated on real renders: hollow ST-07B dark void 0.293, white gaps
# 0.18-0.73 (all FIRE); packed dark stat panels 0.018-0.067 (CLEAR). Clean cut:
# packed/good <= 0.12, hollow/gappy >= 0.185 -- nothing real sits in (0.12,
# 0.185), so 0.13 is the honest anti-gaming separator.
N08_EMPTY_GAP_THRESHOLD = 0.13

# Legacy near-white-only contiguous-band threshold. N08 no longer uses this (the
# white-only band was GAMEABLE by a hollow dark panel; see
# N08_EMPTY_GAP_THRESHOLD). Kept defined for back-compat so ``dead_space_gap``
# consumers (run_one_page / brain trajectory / reporting) and imports do not
# break.
N08_DEAD_SPACE_GAP_THRESHOLD = 0.10

# Legacy total-near-white-fraction threshold. N08 no longer uses this (it
# OVER-FIRES on airy-but-good pages -- ST-09 scores ~0.46 here yet looks good).
# Kept defined so ``dead_space_fraction`` consumers / imports do not break.
N08_DEAD_SPACE_THRESHOLD = 0.30

# N05 contrast hard-fail cut (spec §6.2). Below WCAG AA 4.5:1 on headline/URL
# text we both penalize (-10) AND latch a hard-fail. Spec note: the real spec
# scopes the hard-fail to headline/URL specifically; we currently only have a
# single page-level min_text_contrast fact, so we apply the cut to that --
# documented simplification until per-run contrast is computed.
N05_CONTRAST_MIN = 4.5


@dataclass(frozen=True)
class RubricRow:
    """One rubric criterion (a row of spec §6's positive or negative table)."""

    id: str
    polarity: str  # 'positive' | 'negative'
    rewards_or_penalizes: str
    detect: str  # 'DET' | 'VIS' | 'DET∧VIS'  (also tolerates 'VIS+DET')
    weight: int
    hard_fail: bool
    fact_key: Optional[str]  # PageFacts attribute, or None if no fact yet
    knob_class: str  # 'renderer' | 'preprocessor' | 'asset_gen'
    applies_to: Union[list[str], str]  # list of st_types or 'all'


# --------------------------------------------------------------------------- #
# POSITIVE TABLE (spec §6.1)
# --------------------------------------------------------------------------- #
_POSITIVE: list[RubricRow] = [
    RubricRow("P01", "positive", "founder-as-hero", "DET∧VIS", 10, False, None, "renderer", "all"),
    RubricRow("P02", "positive", "two-tone headline", "DET", 5, False, None, "renderer", "all"),
    RubricRow("P03", "positive", "dark authority panel", "DET", 8, False, None, "renderer", "all"),
    RubricRow("P04", "positive", "readable on-panel text", "DET", 6, False, None, "renderer", "all"),
    RubricRow("P05", "positive", "named client photo / case study", "DET∧VIS", 10, False, None, "asset_gen", "all"),
    RubricRow("P06", "positive", "big-number stat devices", "DET", 7, False, None, "renderer", "all"),
    RubricRow("P07", "positive", "social-proof apparatus", "DET∧VIS", 9, False, None, "renderer", "all"),
    # P08 running-header furniture, spec §6.1 -- LIVE (header_furniture_present).
    RubricRow("P08", "positive", "running-header furniture", "DET", 4, False,
              "header_furniture_present", "renderer", "all"),
    # P09 serif/sans pairing, fonts loaded, spec §6.1 -- LIVE (display_font_embedded).
    RubricRow("P09", "positive", "serif/sans pairing, fonts loaded", "DET", 4, False,
              "display_font_embedded", "renderer", "all"),
    RubricRow("P10", "positive", "decorative glyphs", "DET∧VIS", 3, False, None, "renderer", "all"),
    RubricRow("P11", "positive", "real charts", "DET∧VIS", 7, False, None, "renderer", "all"),
    RubricRow("P12", "positive", "magazine density", "VIS+DET", 5, False, None, "renderer", "all"),
    RubricRow("P13", "positive", "per-client texture", "DET∧VIS", 4, False, None, "asset_gen", "all"),
    RubricRow("P14", "positive", "full-bleed photo treated", "DET∧VIS", 4, False, None, "renderer", "all"),
    RubricRow("P15", "positive", "numbered pills / labels", "DET", 3, False, None, "renderer", "all"),
    RubricRow("P16", "positive", "device/product mockup", "DET∧VIS", 3, False, None, "renderer", "all"),
]


# --------------------------------------------------------------------------- #
# NEGATIVE TABLE (spec §6.2). HARD-FAIL rows latch the page below ship.
# --------------------------------------------------------------------------- #
_NEGATIVE: list[RubricRow] = [
    # N01 empty required photo box, spec §6.2 -- HARD-FAIL. A missing client
    # photo is not fixable in-renderer; it must be supplied/generated -> asset_gen.
    RubricRow("N01", "negative", "empty required photo box", "DET∧VIS", 0, True,
              "required_slots_missing", "asset_gen", "all"),
    RubricRow("N02", "negative", "pale tint not dark panel", "DET", -12, False, None, "renderer", "all"),
    # N03 font fallback / wrong family, spec §6.2 -- HARD-FAIL when font not embedded.
    RubricRow("N03", "negative", "font fallback / wrong family", "DET", 0, True,
              "display_font_embedded", "renderer", "all"),
    # N04 overflow / clipping, spec §6.2 -- HARD-FAIL, LIVE (content_overflow):
    # fires when any text is drawn beyond the page bounds (off-page / clipped).
    RubricRow("N04", "negative", "overflow / clipping", "DET", 0, True, "content_overflow", "renderer", "all"),
    # N05 low text contrast, spec §6.2 -- penalty -10 when contrast<4.5, treated
    # as HARD-FAIL per spec note "HARD-FAIL on headline/URL" (documented
    # simplification: applied to the single page-level contrast fact).
    RubricRow("N05", "negative", "low text contrast", "DET", -10, True,
              "min_text_contrast", "renderer", "all"),
    # N06 oversized QR / qr_enabled false, spec §6.2 -- LIVE (qr_gating_violation).
    RubricRow("N06", "negative", "oversized QR / qr_enabled false", "DET", -8, False,
              "qr_gating_violation", "renderer", "all"),
    RubricRow("N07", "negative", "generic-stock imagery", "VIS", -10, False, None, "asset_gen", "all"),
    # N08 dead/hollow space, spec §6.2 -- LIVE. Fires on the UNIFIED emptiness
    # metric (empty_gap > N08_EMPTY_GAP_THRESHOLD): the largest contiguous run of
    # rows that are uniform near-white (a gap) OR uniform near-dark (a
    # content-less solid panel). This catches a hollow DARK panel that the old
    # white-only band scored ~0, closing the dark-void gaming hole.
    RubricRow("N08", "negative", "dead/hollow space (white gaps OR content-less solid panels)",
              "VIS+DET", -6, False, "empty_gap", "renderer", "all"),
    # N09 missing header furniture, spec §6.2 -- LIVE, fires when header absent.
    RubricRow("N09", "negative", "missing header furniture", "DET", -5, False,
              "header_furniture_present", "renderer", "all"),
    RubricRow("N10", "negative", "untreated full-bleed photo", "DET∧VIS", -8, False, None, "renderer", "all"),
    # N11 missing recipe-required device, spec §6.2 -- fact not computed yet.
    RubricRow("N11", "negative", "missing recipe-required device", "DET", -6, False, None, "renderer", "all"),
    # N12 accent over-budget, spec §6.2 -- fact not computed yet.
    RubricRow("N12", "negative", "accent over-budget", "DET", -5, False, None, "renderer", "all"),
    # N13 empty/stub chart, spec §6.2 -- fact not computed yet.
    RubricRow("N13", "negative", "empty/stub chart", "DET", -6, False, None, "renderer", "all"),
    # N14 placeholder/lorem/"could not render" leakage, spec §6.2 -- HARD-FAIL.
    RubricRow("N14", "negative", 'placeholder/lorem/"could not render" leakage', "DET", 0, True,
              "placeholder_text_present", "preprocessor", "all"),
    # N15 stat callout is prose, not a numeral -- LIVE. A case-study stat device
    # must read as an OVERSIZED NUMERAL ("15", "> 200.000 €", "24 Std -> Min");
    # a prose sentence in ergebnis_metrics[].value is a CONTENT gap, not
    # renderer-fixable -> route to the preprocessor. Penalty -5 (not hard-fail).
    RubricRow("N15", "negative", "stat callout is prose, not a numeral", "DET", -5, False,
              "non_numeral_stat_values", "preprocessor", ["ST-07A"]),
]


# The full versioned rubric: positives first, then negatives, in spec order.
RUBRIC: list[RubricRow] = _POSITIVE + _NEGATIVE


def positive_max() -> int:
    """Sum of all positive-row weights -- the page_reward normalization base.

    This is the single global maximum used for this one-page proof. Per-page-type
    maxima (only the positives a given st_type can actually earn) come later;
    documented here so the simplification is explicit.
    """
    return sum(row.weight for row in RUBRIC if row.polarity == "positive")
