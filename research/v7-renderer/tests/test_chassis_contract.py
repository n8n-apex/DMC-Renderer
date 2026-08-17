"""Chassis contract test — proves the decontaminated skeleton stands.

Asserts the chassis seams work WITHOUT rendering a page. No PDF emitted,
no WeasyPrint invoked, no template parsed. Tests cover:

  - Grammar loader trust gate (red + green) + parser + missing-section
    behaviour against the live richard-grammar-v2.md and against a
    synthetic ratified fixture grammar.
  - BrandConfig flat-shape parsing.
  - AccentBudgetValidator single-path validate() (the M2c rename of
    the old CoralValidator).
  - Chassis per-element-class anti-pattern toggles (M2c signature).
  - Regression: zero "coral" in chassis logic.

Run via pytest (Move 3 migrated the suite from a hand-rolled runner):
    cd research/v7-renderer && python -m pytest tests/ -v
"""

from __future__ import annotations

import pathlib
import re
import sys
import tempfile
from pathlib import Path

# ---- sys.path setup ----------------------------------------------------------
# Allow flat imports from research/v7-renderer/ regardless of cwd.
HERE = Path(__file__).resolve().parent
CHASSIS_ROOT = HERE.parent
sys.path.insert(0, str(CHASSIS_ROOT))

# ---- Chassis imports ---------------------------------------------------------
from grammar_loader import (  # noqa: E402
    load_grammar,
    GrammarMissingError,
    GrammarUnratifiedError,
    Grammar,
    GrammarSection,
)
from brand_tokens import (  # noqa: E402
    parse_brand_tokens,
    BrandConfig,
)
from chassis_config import (  # noqa: E402
    allow_rounded_corners,
    allow_drop_shadows,
)
from validators.accent_budget import (  # noqa: E402
    AccentBudgetValidator,
    AccentBudgetResult,
    ACCENT_BUDGET_EXCEEDED,
)


# ---- Fixtures — minimal brand_tokens, NO render ------------------------------
#
# Single sample fixture (the GEVA shape — keeping the client label is OK per
# the M2c spec, "GEVA" is a fixture LABEL identifying which client's data is
# transcribed, not a logic discriminator). All keys are the flat 10-field
# shape BrandConfig now expects post-M2c.

SAMPLE_BRAND_TOKENS = {
    "brand_primary": "#1A2540",
    "brand_accent": "#E97E47",
    "brand_neutral_dark": "#0F0F1F",
    "brand_neutral_mid": "#7A7A8C",
    "brand_neutral_light": "#F5EFE3",
    "font_heading": "Montserrat",
    "font_body": "Source Sans 3",
    "qr_target_url": "https://www.gevagmbh.de",
    "company_name_short": "mein.werkzeug.koffer",
    "company_url_display": "www.meinwerkzeugkoffer.de",
}


# ---- Fixture grammars for parser/gate tests ---------------------------------
#
# The real grammar (richard-grammar-v2.md at the project root) is RATIFIED
# (Utkarsh 2026-05-23). Tests against the default path test live-grammar
# behaviour; tests against the fixtures below test parser edge cases.

_FIXTURE_GRAMMAR_RATIFIED = """\
================================================================================
GRAMMAR STATUS: TEST FIXTURE — synthetic grammar for chassis-contract tests.
RATIFIED-BY:    test_fixture (synthetic; never for production)
================================================================================

## §1  The palette

Fixture palette section. Mentions primary #1A2540 and panel #1F3D6D.

## §2  Layout

Fixture layout section body.

### §3.5  Color discipline

Fixture color discipline section.

## §10  Type system

Fixture type system mentioning Source Sans 3 Regular for body.
"""

_FIXTURE_GRAMMAR_UNRATIFIED = _FIXTURE_GRAMMAR_RATIFIED.replace(
    "RATIFIED-BY:    test_fixture (synthetic; never for production)",
    "RATIFIED-BY:    ____________________   (blank by design)",
)


def _write_fixture(text: str) -> Path:
    """Write fixture grammar to a tempfile; return path. Caller owns cleanup."""
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    )
    tmp.write(text)
    tmp.close()
    return Path(tmp.name)


# ---- Tests -------------------------------------------------------------------

def test_grammar_loader_allows_ratified_default_grammar() -> None:
    """TRUST GATE — GREEN side against the real default grammar.

    The grammar has been ratified (`RATIFIED-BY: Utkarsh 2026-05-23`),
    so load_grammar() at the default path now succeeds. The gate's RED
    side is proven by test_grammar_loader_blocks_underscores_as_blank.
    Also serves as the parser-regex smoke test against the live grammar.
    """
    grammar = load_grammar()  # no path → uses _DEFAULT_GRAMMAR_PATH

    assert isinstance(grammar, Grammar)
    assert grammar.sections, (
        "loader returned an empty grammar from the ratified default path"
    )
    for required in ["0", "1", "2", "3", "4", "5", "6", "7"]:
        assert grammar.has_section(required), (
            f"missing required top-level grammar section §{required}"
        )
    for required in ["3.5", "3.7", "4.0"]:
        assert grammar.has_section(required), (
            f"missing required sub-numbered grammar section §{required}"
        )


def test_grammar_loader_blocks_underscores_as_blank() -> None:
    """TRUST GATE — RED side: underscores-only RATIFIED-BY value counts
    as blank and raises GrammarUnratifiedError.
    """
    path = _write_fixture(_FIXTURE_GRAMMAR_UNRATIFIED)
    raised: Exception | None = None
    try:
        load_grammar(path)
    except GrammarUnratifiedError as e:
        raised = e
    assert raised is not None, (
        "underscore-only RATIFIED-BY value must count as blank"
    )
    assert "RATIFIED-BY" in str(raised)


def test_grammar_loader_allows_ratified_fixture() -> None:
    """TRUST GATE — GREEN side via temp fixture: filled RATIFIED-BY value
    allows the load to proceed.
    """
    path = _write_fixture(_FIXTURE_GRAMMAR_RATIFIED)
    grammar = load_grammar(path)

    assert isinstance(grammar, Grammar)
    assert grammar.source_path == path.resolve()
    assert grammar.sections, "loader returned an empty grammar"
    assert grammar.has_section("1")
    assert grammar.has_section("10")


def test_grammar_loader_exposes_section_bodies() -> None:
    """Parser exposes section content correctly (title + body extraction).
    """
    path = _write_fixture(_FIXTURE_GRAMMAR_RATIFIED)
    grammar = load_grammar(path)

    sec1 = grammar.get_section("1")
    assert isinstance(sec1, GrammarSection)
    assert "palette" in sec1.title.lower(), f"§1 title was {sec1.title!r}"
    assert "#1A2540" in sec1.body and "#1F3D6D" in sec1.body, (
        "§1 body missing one of the navy hex values"
    )

    sec10 = grammar.get_section("10")
    assert "type system" in sec10.title.lower(), f"§10 title was {sec10.title!r}"
    assert "Source Sans 3" in sec10.body


def test_grammar_loader_fail_loud_on_missing_section() -> None:
    """get_section() raises GrammarMissingError on absent section."""
    path = _write_fixture(_FIXTURE_GRAMMAR_RATIFIED)
    grammar = load_grammar(path)

    raised: Exception | None = None
    try:
        grammar.get_section("999")
    except GrammarMissingError as e:
        raised = e

    assert raised is not None, "get_section() did not raise on missing section"
    msg = str(raised)
    assert "999" in msg, (
        f"error message did not include the missing section number: {msg!r}"
    )
    assert "fall back" in msg, (
        f"error message must warn against falling back to a guess: {msg!r}"
    )


def test_brand_tokens_parses_flat_config() -> None:
    """parse_brand_tokens() returns a BrandConfig with the flat 10-field
    shape — no design_preferences, no apex defaults, no struck fields.
    """
    config = parse_brand_tokens(SAMPLE_BRAND_TOKENS)

    assert isinstance(config, BrandConfig)
    assert config.brand_primary == "#1A2540"
    assert config.brand_accent == "#E97E47"
    assert config.brand_neutral_dark == "#0F0F1F"
    assert config.brand_neutral_mid == "#7A7A8C"
    assert config.brand_neutral_light == "#F5EFE3"
    assert config.font_heading == "Montserrat"
    assert config.font_body == "Source Sans 3"
    assert config.qr_target_url == "https://www.gevagmbh.de"
    assert config.company_name_short == "mein.werkzeug.koffer"
    assert config.company_url_display == "www.meinwerkzeugkoffer.de"

    # Dead fields must be absent from BrandConfig dataclass.
    dead_fields = (
        "design_preferences_present",
        "case_study_geometry",
        "fallstudie_kicker_style",
        "pullquote_treatment",
        "page_background",
        "section_label_style",
        "coral_budget_per_page",
        "callout_row_color",
        "brand_secondary_panel",
    )
    surviving = {f.name for f in BrandConfig.__dataclass_fields__.values()}
    for dead in dead_fields:
        assert dead not in surviving, (
            f"dead field {dead} still present on BrandConfig: {sorted(surviving)}"
        )


def test_brand_tokens_missing_key_raises_value_error() -> None:
    """parse_brand_tokens() raises plain ValueError when a required key
    is missing — no synthesis, no apex fallback.
    """
    incomplete = {k: v for k, v in SAMPLE_BRAND_TOKENS.items() if k != "brand_accent"}
    raised: Exception | None = None
    try:
        parse_brand_tokens(incomplete)
    except ValueError as e:
        raised = e
    assert raised is not None, (
        "missing required key must raise ValueError; the chassis does not "
        "synthesize brand values"
    )
    assert "brand_accent" in str(raised), (
        f"error must name the missing field: {raised!r}"
    )


def test_accent_budget_validator_returns_result() -> None:
    """AccentBudgetValidator.validate() returns an AccentBudgetResult.

    Single path (C2 STRUCK — no .path attribute, no count vs location
    branch). The stub returns passed=True; the real rasterization-based
    check is post-decontamination work.
    """
    config = parse_brand_tokens(SAMPLE_BRAND_TOKENS)
    validator = AccentBudgetValidator(brand=config)
    result = validator.validate(rendered_html="<stub/>", rendered_pdf_pages=[])

    assert isinstance(result, AccentBudgetResult)
    assert result.passed is True
    # The result must NOT have a `path` field (C2 STRUCK in matrix).
    result_fields = {f.name for f in AccentBudgetResult.__dataclass_fields__.values()}
    assert "path" not in result_fields, (
        f"AccentBudgetResult must not have a .path field (C2 STRUCK): "
        f"{sorted(result_fields)}"
    )


def test_accent_budget_error_code_constant() -> None:
    """ACCENT_BUDGET_EXCEEDED string identifier is stable for n8n branching."""
    assert ACCENT_BUDGET_EXCEEDED == "accent_budget_exceeded"


def test_chassis_per_element_anti_pattern_toggles() -> None:
    """allow_rounded_corners and allow_drop_shadows take an element-class
    string and answer per-class (M2c signature; no design_preferences).

    Rules (grammar §6.1):
      - CTA box: rounded corners allowed (exception 1, InDesign Spec L548-552)
      - Mechanism step card: rounded corners allowed (exception 2, VARIATION)
      - Everything else: no rounded corners
      - Drop shadows: forbidden everywhere (no exceptions)
    """
    # Rounded corners — exception classes
    assert allow_rounded_corners("cta-box") is True
    assert allow_rounded_corners("mechanism-step-card") is True
    assert allow_rounded_corners("process-step-card") is True

    # Rounded corners — non-exception classes (must be False)
    assert allow_rounded_corners("body-section") is False
    assert allow_rounded_corners("pullquote-panel") is False
    assert allow_rounded_corners("rail-photo") is False
    assert allow_rounded_corners("fallstudie-stamp") is False
    assert allow_rounded_corners("") is False
    assert allow_rounded_corners("unknown-class") is False

    # Drop shadows — forbidden on every class
    assert allow_drop_shadows("cta-box") is False
    assert allow_drop_shadows("mechanism-step-card") is False
    assert allow_drop_shadows("body-section") is False
    assert allow_drop_shadows("anything") is False


def test_no_coral_in_chassis_logic() -> None:
    """Regression: the string 'coral' must not appear in chassis logic.

    Coral is one client's accent hex value (GEVA profile §4.1 of the
    grammar). It is NOT a chassis concept, validator name, class name,
    config key, or CSS class. This test scans production source files
    and fails if 'coral' appears in any active code line. Removal-history
    comments (containing REMOVED, M2*, or "renamed from") are allowed
    because they document the decontamination. Third-party packages
    under .venv are excluded — PIL/pymupdf/tinycss2 carry "coral" as a
    CSS X11 colour name, which is environment data, not chassis logic.

    Future contributor: if you reintroduce "coral" anywhere except as a
    literal hex value in a brand fixture, or in a removal-history note,
    this test will fail. That is the gate.
    """
    chassis_root = pathlib.Path(__file__).resolve().parent.parent
    # styles/_grain.py is a machine-generated binary-as-text constant (base64 PNG
    # grain tile). A 59 KB random base64 string can contain any 5-letter substring
    # by chance if regenerated with a different seed — including "coral".  It holds
    # zero logic, zero design decisions, and zero client-name discriminators; it is
    # purely deterministic, brand-agnostic pixel data.  Scanning it for "coral" is
    # therefore both fragile (false positives on regen) and meaningless (there is
    # nothing to enforce there).  The defensive test
    # test_grain_constant_has_no_client_substring in test_texture_ground.py covers
    # the CURRENT constant separately and is the correct gate for that file.
    _GENERATED_DATA_EXCLUSIONS = {"_grain.py"}
    violations: list[str] = []
    for py_file in chassis_root.rglob("*.py"):
        if "test_" in py_file.name or "__pycache__" in str(py_file):
            continue
        if ".venv" in str(py_file):
            continue
        if py_file.name in _GENERATED_DATA_EXCLUSIONS:
            continue
        for i, line in enumerate(py_file.read_text().splitlines(), 1):
            if re.search(r"\bcoral\b", line, re.IGNORECASE):
                # Allow removal-history comments
                if "REMOVED" in line or "renamed from" in line.lower() or "M2" in line:
                    continue
                violations.append(f"{py_file.name}:{i}: {line.strip()}")
    assert not violations, (
        f"'coral' found in chassis logic ({len(violations)} hits):\n"
        + "\n".join(violations)
    )
