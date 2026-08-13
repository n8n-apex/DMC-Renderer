"""Deterministic perception module -- the "eyes" of the self-correcting quality loop.

Given a RENDERED page (the multi-page report PDF + a rasterized PNG of one page)
plus that page's source data, this computes deterministic FACTS about what
actually got drawn. There is NO vision model here: every fact is a pure
function of pixels, the embedded font table, extracted text, or the resolved
package data. (Vision-based perception is a deliberately separate later task.)

Design notes:
  * Each fact is computed by its own small pure helper so it can be tested in
    isolation; ``perceive`` merely composes them into a ``PageFacts``.
  * Everything is brand-agnostic. The only literal font names baked in are the
    renderer-engine fallback-detection strings ("Source-Serif-4", "PT-Serif",
    "Hiragino") -- those are facts about the WeasyPrint/fontconfig pipeline, not
    brand identity (see tests/test_font_embedding.py which does the same).
  * Pure stdlib + PyMuPDF (fitz) + Pillow (PIL). numpy is intentionally NOT used
    (it is not installed in the renderer venv); per-row stats come from
    PIL.ImageStat which is fast enough (~0.05s for a full A4-at-2x page).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF
from PIL import Image, ImageStat

# --- Renderer-engine font facts (NOT brand identity; see module docstring). ---
# The intended display serif. If its embedded subset name appears on the page,
# the display face really loaded.
_DISPLAY_FONT_MARKER = "Source-Serif-4"
# The exact symptom of the format-4-only-cmap bug: silent fallback to a system
# serif / CJK face. Presence of either means a fallback happened.
_SYSTEM_FALLBACK_MARKERS = ("PT-Serif", "Hiragino")

# Case-insensitive placeholder/boilerplate strings that must never reach a
# rendered page. These are generic copy-fit failure signatures, not brand text.
_PLACEHOLDER_NEEDLES = (
    "lorem ipsum",
    "could not render",
    "first name last name",
    "placeholder",
    "tbd",
    "xxxx",
)

# Dead-space thresholds. A pixel row is "empty"/dead when it is BOTH near the
# light ground (high mean brightness) AND nearly uniform (low stddev) -- i.e. no
# ink crossed it. These are luminance-domain (0..255) thresholds on a grayscale
# conversion, calibrated against the real Apex render: a full-bleed cover scores
# ~0.0 and the sparse case-study page ~0.39, a wide and stable separation.
_EMPTY_ROW_MEAN_MIN = 235.0  # brighter than this == near white ground
_EMPTY_ROW_STDDEV_MAX = 7.0  # flatter than this == no ink variation in the row

# --- Unified emptiness ("empty_gap") thresholds. -----------------------------
# WHY a SECOND metric: ``dead_space_gap`` counts only near-WHITE rows, so a page
# can GAME it by painting its empty region DARK -- a large solid dark panel with
# almost no content reads as a void to a human but the white-only metric scores
# it ~0 (real proof: the ST-07B fill theory page is a dark navy panel filling
# ~30% of the sheet with ONE sentence; its dead_space_gap is ~0 yet it is
# obviously hollow). ``empty_gap`` closes that hole: measured over the CENTRAL
# content column (panels don't span the full width), a row is "empty" when it is
# uniform near-WHITE (a background gap) OR uniform near-DARK (a content-less solid
# panel). A genuinely PACKED dark panel is NOT empty -- its light text/imagery
# breaks the rows up (raising stddev), so it does not register. Calibrated on
# real renders: hollow ST-07B dark void 0.293, white gaps 0.18-0.73 (all FIRE);
# packed dark stat panels 0.018-0.067 (CLEAR). See rubric.N08_EMPTY_GAP_THRESHOLD.
_EMPTY_GAP_CROP_LEFT = 0.10   # crop L/R page margins to the central content column
_EMPTY_GAP_CROP_RIGHT = 0.90
_EMPTY_GAP_WHITE_MEAN_MIN = 235.0  # uniform near-white row (background gap)
_EMPTY_GAP_WHITE_STDDEV_MAX = 8.0
_EMPTY_GAP_DARK_MEAN_MAX = 55.0    # uniform near-dark row (hollow solid panel)
_EMPTY_GAP_DARK_STDDEV_MAX = 18.0

# --- Stat-callout numeral heuristic (format facts, NOT brand/content). -------
# A "stat callout" in the design grammar is an OVERSIZED NUMERAL: a compact,
# digit-led device ("15", "750", "129.000", "> 200.000 €", "24 Std. → Min").
# When ergebnis_metrics[].value is a PROSE sentence instead, that is a content
# defect the system must SEE (and route to the preprocessor, not the renderer).
#
# Generic numeric UNITS (currency, percent, time, multipliers, magnitudes) are
# format tokens, not brand/content words -- a value reading like "<NUM> <unit>"
# is still a numeral-like callout. These are kept deliberately generic.
_STAT_UNIT_TOKEN = r"(?:€|\$|%|x|h|std\.?|min\.?|k|mio\.?|tage?|jahre?)"
# Compact pattern: optional comparator/prefix, a numeric leading token, an
# optional unit, an optional arrow + trailing remainder (e.g. "24 Std. → Min").
_STAT_NUMERAL_RE = re.compile(
    rf"^[<>~]?\s*[\d.,]+\s*{_STAT_UNIT_TOKEN}?\s*(?:→|->)?.*$",
    re.IGNORECASE,
)
# Tokens stripped before the "digit-dominant and short" test: whitespace,
# currency/percent, comparators, arrows, separators, and generic units.
_STAT_STRIP_RE = re.compile(
    rf"[\s€\$%<>~]|→|->|[.,]|{_STAT_UNIT_TOKEN}",
    re.IGNORECASE,
)
# A short value (<= this many chars) that carries at least one digit reads as a
# numeral callout (e.g. "4", "15x"); longer / multi-word values do not.
_STAT_SHORT_MAX = 12


@dataclass
class PageFacts:
    """Deterministic facts about a single rendered page."""

    page_index: int
    st_type: str
    display_font_embedded: bool
    embedded_fonts: list[str]
    min_text_contrast: float
    required_slots_missing: list[str]
    dead_space_fraction: float
    dead_space_gap: float
    empty_gap: float
    placeholder_text_present: bool
    placeholder_hits: list[str]
    header_furniture_present: bool
    qr_present: bool
    qr_gating_violation: bool
    non_numeral_stat_values: list[str]
    # N04: True when any text is drawn beyond the page rectangle (off-page /
    # clipped at the trim). Page-bounds overflow only; within-page element
    # overflow (e.g. viz text past its circle) is prevented at the viz source.
    content_overflow: bool = False


# --------------------------------------------------------------------------- #
# Per-fact pure helpers
# --------------------------------------------------------------------------- #

def get_embedded_fonts(pdf_path: Path | str, page_index: int) -> list[str]:
    """Raw font (subset) names found on the page.

    Mirrors tests/test_font_embedding.py: open the PDF, read the page font
    table, and take the font name at tuple index [3] of each entry.
    """
    doc = fitz.open(str(pdf_path))
    try:
        return [f[3] for f in doc.get_page_fonts(page_index)]
    finally:
        doc.close()


def display_font_embedded(embedded_fonts: list[str]) -> bool:
    """True iff the display serif (Source Serif 4) actually embedded.

    The format-4-cmap bug this guards manifested as the display serif being
    ABSENT entirely (silently swapped for a system serif), so the signal is
    simply whether the display marker is present in the page's font table.

    A stray system *sans* fallback for an incidental glyph (e.g. Hiragino for a
    CJK/symbol character) is a SEPARATE glyph-coverage matter and must NOT negate
    a present display serif. Conflating the two made N03 a FALSE POSITIVE: a page
    whose headlines correctly load Source Serif 4 still failed because one stray
    glyph pulled in Hiragino-Sans. ``_SYSTEM_FALLBACK_MARKERS`` is kept for a
    future dedicated glyph-coverage fact.
    """
    return _DISPLAY_FONT_MARKER in " ".join(embedded_fonts)


def text_overflows_page(
    pdf_path: Path | str, page_index: int, tol: float = 2.0
) -> bool:
    """True iff any TEXT span is drawn beyond the page rectangle by > ``tol`` pt.

    Deterministic PAGE-BOUNDS overflow (off-page / clipped at the trim): catches
    content running off the physical page. It does NOT catch within-page element
    overflow (text past a circle or panel) — that class is prevented at the viz /
    render source (auto-fit) and judged by the vision grader. Brand-agnostic:
    inspects only geometry, never text content.
    """
    doc = fitz.open(str(pdf_path))
    try:
        page = doc[page_index]
        r = page.rect
        data = page.get_text("dict")
        for block in data.get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    x0, y0, x1, y1 = span.get("bbox", (0.0, 0.0, 0.0, 0.0))
                    if (
                        x0 < r.x0 - tol
                        or y0 < r.y0 - tol
                        or x1 > r.x1 + tol
                        or y1 > r.y1 + tol
                    ):
                        return True
        return False
    finally:
        doc.close()


def _hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    h = hex_str.lstrip("#")
    if len(h) == 3:  # short form e.g. "fff"
        h = "".join(ch * 2 for ch in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _relative_luminance(hex_str: str) -> float:
    """WCAG 2.x relative luminance of an sRGB hex color."""
    def _lin(c: int) -> float:
        s = c / 255.0
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4

    r, g, b = _hex_to_rgb(hex_str)
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def min_text_contrast(brand: dict[str, Any]) -> float:
    """WCAG contrast ratio of ink text vs page ground, from brand tokens.

    Brand-agnostic: uses whatever hex the brand provides. In light-ground mode
    the ink is ``brand_neutral_dark`` and the ground is ``brand_neutral_light``.
    Ratio is (L1 + 0.05) / (L2 + 0.05) with L1 the lighter luminance.
    """
    ink = _relative_luminance(brand["brand_neutral_dark"])
    ground = _relative_luminance(brand["brand_neutral_light"])
    light, dark = max(ink, ground), min(ink, ground)
    return (light + 0.05) / (dark + 0.05)


def required_slots_missing(page_data: dict[str, Any]) -> list[str]:
    """Every slot with status 'missing_required', reported by its 'expected' value."""
    slots = page_data.get("slots") or []
    return [
        s["expected"]
        for s in slots
        if s.get("status") == "missing_required" and s.get("expected")
    ]


def dead_space_fraction(page_png_path: Path | str) -> float:
    """Fraction of the page's vertical extent that is empty/dead whitespace.

    WHY rows (not a fixed region): a sparse page leaves contiguous empty bands
    wherever content was expected but not drawn (e.g. a missing portrait, an
    under-filled column). We scan EVERY pixel row of the rasterized page and
    count a row as dead when it is both near the light ground (high mean
    brightness) and nearly uniform (low stddev) -- i.e. no ink crossed it.

    Normal top/bottom margins ARE counted as empty, which is intentional and
    harmless: a dense full-bleed page has almost no such rows, so the metric
    still cleanly separates sparse from dense (validated by the discriminative
    test). Returns a fraction in [0, 1]. Grayscale luminance is used so colored
    ink (charts, accent panels) registers as non-empty.
    """
    dead = _dead_row_flags(page_png_path)
    if not dead:
        return 0.0
    return sum(dead) / len(dead)


def _dead_row_flags(page_png_path: Path | str) -> list[bool]:
    """Per-row dead/not-dead flags for the page (one bool per pixel row).

    A row is "dead" when it is BOTH near the light ground (mean brightness >=
    _EMPTY_ROW_MEAN_MIN) AND nearly uniform (stddev <= _EMPTY_ROW_STDDEV_MAX) --
    i.e. no ink crossed it. This is the SINGLE per-row dead test shared by both
    ``dead_space_fraction`` (how many rows are dead overall) and
    ``dead_space_gap`` (the largest contiguous run of dead rows), so the two
    facts can never disagree on what "dead" means.
    """
    with Image.open(page_png_path) as im:
        gray = im.convert("L")
        width, height = gray.size
        flags: list[bool] = []
        for y in range(height):
            row = gray.crop((0, y, width, y + 1))
            stat = ImageStat.Stat(row)
            mean = stat.mean[0]
            stddev = stat.stddev[0]
            flags.append(
                mean >= _EMPTY_ROW_MEAN_MIN and stddev <= _EMPTY_ROW_STDDEV_MAX
            )
    return flags


def dead_space_gap(page_png_path: Path | str) -> float:
    """Largest CONTIGUOUS run of dead rows, as a fraction of page height.

    WHY contiguity (vs ``dead_space_fraction``'s total count): a purposeless
    empty REGION -- a real gap where content was expected but not drawn (a
    missing portrait, an under-filled column, a big bottom void) -- shows up as
    ONE long unbroken band of dead rows. A well-filled but AIRY page (normal
    margins + line leading + a multi-column grid) accumulates a high TOTAL dead
    fraction from many SHORT scattered gaps between lines/blocks, yet has no
    single long band. Measured on the real Apex render: the airy-but-good ST-09
    page has total dead fraction ~0.46 (over the old 0.30 cut!) but its largest
    contiguous run is only ~0.06, whereas a page with a real bottom void
    (ST-02) runs ~0.39 contiguous. The contiguous run is therefore the correct
    signal for a real empty region and does not false-fire on airiness.

    Returns a fraction in [0, 1] (uses the SAME per-row dead test as
    ``dead_space_fraction`` via ``_dead_row_flags``).
    """
    dead = _dead_row_flags(page_png_path)
    if not dead:
        return 0.0
    longest = 0
    current = 0
    for is_dead in dead:
        if is_dead:
            current += 1
            if current > longest:
                longest = current
        else:
            current = 0
    return longest / len(dead)


def _unified_empty_gap(page_png_path: Path | str) -> float:
    """Largest CONTIGUOUS run of EMPTY rows under the unified emptiness test.

    Unlike ``dead_space_gap`` (near-white only), a row counts as empty when --
    measured over the CENTRAL content column (left/right page margins cropped,
    since panels do not span the full width) -- it is uniform near-WHITE (a
    background gap) OR uniform near-DARK (a content-less solid panel, no text or
    imagery on it). This catches BOTH a white void AND a hollow dark/colored
    panel, while a genuinely PACKED dark panel does NOT register (its light text
    raises the row stddev above the dark-empty bar). Returns a fraction in
    [0, 1]. See the module-level _EMPTY_GAP_* thresholds for the calibration.
    """
    with Image.open(page_png_path) as im:
        gray = im.convert("L")
        width, height = gray.size
        if height == 0:
            return 0.0
        x0 = int(width * _EMPTY_GAP_CROP_LEFT)
        x1 = int(width * _EMPTY_GAP_CROP_RIGHT)
        longest = 0
        current = 0
        for y in range(height):
            stat = ImageStat.Stat(gray.crop((x0, y, x1, y + 1)))
            mean = stat.mean[0]
            stddev = stat.stddev[0] if stat.stddev else 0.0
            white_empty = (
                mean >= _EMPTY_GAP_WHITE_MEAN_MIN
                and stddev <= _EMPTY_GAP_WHITE_STDDEV_MAX
            )
            dark_empty = (
                mean <= _EMPTY_GAP_DARK_MEAN_MAX
                and stddev <= _EMPTY_GAP_DARK_STDDEV_MAX
            )
            if white_empty or dark_empty:
                current += 1
                if current > longest:
                    longest = current
            else:
                current = 0
    return longest / height


def get_page_text(pdf_path: Path | str, page_index: int) -> str:
    """Extract the page's text layer via PyMuPDF."""
    doc = fitz.open(str(pdf_path))
    try:
        return doc[page_index].get_text()
    finally:
        doc.close()


def placeholder_hits(page_text: str) -> list[str]:
    """Which placeholder/boilerplate needles appear in the page text (case-insensitive)."""
    low = page_text.lower()
    return [needle for needle in _PLACEHOLDER_NEEDLES if needle in low]


def header_furniture_present(page_text: str, brand: dict[str, Any]) -> bool:
    """True iff the running-header band rendered.

    Signal: the brand's running-header content (short company name and/or the
    display URL) appears in the page text. If neither is present on a content
    page, the header furniture is missing.
    """
    low = page_text.lower()
    name = (brand.get("company_name_short") or "").strip().lower()
    url = (brand.get("company_url_display") or "").strip().lower()
    return bool((name and name in low) or (url and url in low))


def qr_present(page_data: dict[str, Any]) -> bool:
    """Best-effort deterministic detection of a QR-like asset on the page.

    Approach: a DATA-DRIVEN scan of ``page_data`` for any reference to "qr"
    (in assets, components, or anywhere else in the page dict). This is chosen
    over pixel-based QR detection because it is reliable and unambiguous --
    image-based "high-frequency near-square block" detection is brittle here
    (charts, mockups and dense panels can false-trigger), and reliability
    matters more than cleverness for a gating signal.
    """
    assets = page_data.get("assets") or []
    components = page_data.get("components") or []
    for collection in (assets, components):
        for item in collection:
            if "qr" in str(item).lower():
                return True
    # Fall back to scanning the whole page dict (catches has_cta/cta blocks that
    # embed a qr reference) without depending on any one key's shape.
    return "qr" in str(page_data).lower()


def _value_is_numeral_like(value: str) -> bool:
    """True iff a stat-callout VALUE reads as an oversized numeral (format only).

    A value is numeral-like if ANY of:
      1. after stripping whitespace / currency / percent / comparators / arrows /
         separators / generic units it is digit-DOMINANT and short (<= 6 of the
         remaining chars and majority digits) -- e.g. "129.000", "> 200.000 €";
      2. it matches the compact "<num> <unit> (-> rest)" callout pattern with a
         numeric leading token -- e.g. "24 Std. → Minuten";
      3. it is short (<= _STAT_SHORT_MAX chars) AND contains at least one digit
         -- e.g. "4", "15x".
    Otherwise it is PROSE. The heuristic is brand-agnostic: it judges FORMAT
    (digits vs words), never content. Multi-word / long phrases like
    "0 neue Mitarbeiter" fall through every branch (the leading digit is there,
    but it is neither short nor digit-dominant nor a compact <num+unit> token).
    """
    v = (value or "").strip()
    if not v:
        return False

    # Branch 1: strip format tokens, then test digit-dominance + brevity.
    stripped = _STAT_STRIP_RE.sub("", v)
    if stripped:
        digits = sum(ch.isdigit() for ch in stripped)
        if len(stripped) <= 6 and digits >= len(stripped) - digits and digits > 0:
            return True

    # Branch 2: compact <comparator?><num><unit?><arrow?><rest> callout.
    if any(ch.isdigit() for ch in v) and _STAT_NUMERAL_RE.match(v):
        # Require the FIRST non-space/non-comparator token to be numeric so a
        # prose sentence that merely opens with a digit ("0 neue Mitarbeiter")
        # is not mistaken for a callout: its first token after the digit is a
        # word, and the pattern's leading token must be the whole digit run.
        lead = v.lstrip("<>~ ")
        first_token = lead.split()[0] if lead.split() else ""
        # The leading token is numeric (digits + separators + an optional unit),
        # AND the value is either a single token or a compact arrow callout.
        token_is_numeric = bool(re.fullmatch(r"[\d.,]+", first_token))
        if token_is_numeric:
            rest = lead[len(first_token):].strip()
            if rest == "" or rest.startswith(("→", "->")) or re.match(
                rf"^{_STAT_UNIT_TOKEN}\b", rest, re.IGNORECASE
            ):
                return True

    # Branch 3: short value that carries a digit.
    if len(v) <= _STAT_SHORT_MAX and any(ch.isdigit() for ch in v):
        return True

    return False


def non_numeral_stat_values(page_data: dict[str, Any]) -> list[str]:
    """Stat-callout VALUES that read as PROSE rather than an oversized numeral.

    Reads ``page_data["data"]["ergebnis_metrics"]`` (absent/empty on non
    case-study pages -> ``[]``) and returns each ``value`` that is NOT
    numeral-like. These are a content gap (route to the preprocessor), not a
    renderer-fixable defect.
    """
    metrics = (page_data.get("data") or {}).get("ergebnis_metrics") or []
    return [
        m["value"]
        for m in metrics
        if m.get("value") is not None and not _value_is_numeral_like(str(m["value"]))
    ]


# Back-compat alias (the function was private; consumers outside this module
# should use the public name).
_non_numeral_stat_values = non_numeral_stat_values


def qr_gating_violation(qr_is_present: bool, axes: dict[str, Any]) -> bool:
    """True iff QR presence disagrees with the brand's qr_enabled axis.

    Brand-agnostic QR-gating rule from the design DNA: a QR present when the
    axis disables QR, OR a QR missing when the axis enables it.
    """
    return qr_is_present != bool(axes.get("qr_enabled"))


# --------------------------------------------------------------------------- #
# Composition
# --------------------------------------------------------------------------- #

def perceive(
    pdf_path: Path | str,
    page_index: int,
    page_png_path: Path | str,
    page_data: dict[str, Any],
    axes: dict[str, Any],
    brand: dict[str, Any],
) -> PageFacts:
    """Compute all deterministic facts for one rendered page.

    Args:
        pdf_path: path to the rendered multi-page report PDF.
        page_index: 0-based index of the target page within that PDF.
        page_png_path: path to a PNG raster of that one page.
        page_data: the page dict from the resolved package.
        axes: the package axes dict.
        brand: the package brand dict (hex colors + fonts + furniture text).
    """
    embedded = get_embedded_fonts(pdf_path, page_index)
    page_text = get_page_text(pdf_path, page_index)
    hits = placeholder_hits(page_text)
    qr_is_present = qr_present(page_data)

    return PageFacts(
        page_index=page_index,
        st_type=str(page_data.get("st_type", "")),
        display_font_embedded=display_font_embedded(embedded),
        embedded_fonts=embedded,
        min_text_contrast=min_text_contrast(brand),
        required_slots_missing=required_slots_missing(page_data),
        dead_space_fraction=dead_space_fraction(page_png_path),
        dead_space_gap=dead_space_gap(page_png_path),
        empty_gap=_unified_empty_gap(page_png_path),
        placeholder_text_present=bool(hits),
        placeholder_hits=hits,
        header_furniture_present=header_furniture_present(page_text, brand),
        qr_present=qr_is_present,
        qr_gating_violation=qr_gating_violation(qr_is_present, axes),
        non_numeral_stat_values=non_numeral_stat_values(page_data),
        content_overflow=text_overflows_page(pdf_path, page_index),
    )
