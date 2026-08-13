"""Anti-pollution guard: no raw hex colors / font-family literals / client
branching in the NEW (token-only) architecture. Per-client colors + fonts live
in DATA and arrive at render time as semantic tokens (var(--...)); universal
primitives live ONLY in tokens/base.tokens.json. The font-loading @font-face +
@page chrome in assembler.py (repo root, NOT under patterns/) is the accepted
carve-out and is deliberately NOT scanned here.

Scanned (must be literal-free, semantic tokens ONLY):
  - tokens/compile_tokens.py + templating.py        (the token compiler glue)
  - templates/**/*.jinja                            (page skeletons + treatments)
  - styles/**/*.css                                 (Plan B layout sheets + treatments)
  - patterns/**/*.py                                (rebuilt page patterns +
        _generic fallback; patterns/_components.py survives but only holds
        qr_svg, whose fg/bg are ARGS, so it carries no literal of its own)
  - components/**/*.jinja                           (the shared macro library)
  - treatment_stylist.py + treatment_engine.py      (future treatment files,
        listed now so they are covered the moment they are created)

Audit notes: the original globs were non-recursive and would have missed any
files placed under subdirectories such as templates/treatments/ or
styles/treatments/. Both tests here should be GREEN now (no treatment files
exist yet) and will turn RED automatically if a future treatment file introduces
a brand literal or an em dash in authored chrome.

Client-name branching in *.py is already gated by
tests/test_chassis_contract.py::test_no_coral_in_chassis_logic (it scans every
production *.py for a hardcoded client accent name). This guard does NOT
duplicate that; it adds (a) literal coverage across the .jinja + pattern set and
(b) a structural `if ... client ...` branch check spanning the .jinja files too.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# --- the scanned set ---------------------------------------------------------
SCANNED: list[Path] = [ROOT / "tokens" / "compile_tokens.py", ROOT / "templating.py"]
# Recursive globs cover any subdirectories (e.g. templates/treatments/).
# __pycache__ dirs are filtered out to avoid matching .pyc or stale artifacts.
SCANNED += sorted([p for p in (ROOT / "templates").rglob("*.jinja") if "__pycache__" not in p.parts])
SCANNED += sorted([p for p in (ROOT / "styles").rglob("*.css") if "__pycache__" not in p.parts])
# Plan B: the rebuilt patterns + the shared Jinja macro library are now part of
# the token-only architecture and must carry semantic tokens (var(--...)) ONLY.
# assembler.py lives at the repo ROOT (not under patterns/), so this glob does
# NOT pick it up, the font-face/chrome carve-out is excluded by construction.
SCANNED += sorted([p for p in (ROOT / "patterns").rglob("*.py") if "__pycache__" not in p.parts])
SCANNED += sorted([p for p in (ROOT / "components").rglob("*.jinja") if "__pycache__" not in p.parts])
# Treatment engine files: listed now so they are covered as soon as they exist.
# The loop below guards `if not f.exists()`, so listing them before creation is safe.
SCANNED += [
    ROOT / "treatment_stylist.py",
    ROOT / "treatment_catalog.py",
    ROOT / "treatment_engine.py",
]

# D4: extend the no-literal rule to the dmc-renderer ADAPTER LOGIC. Per-client
# colors/fonts arrive as envelope tokens; fallbacks live in the named-constant
# module (brand_fallbacks.py) so logic carries no raw hex. The two standing
# harness scripts (render_christoph.py / render_cover_check.py) are fixtures by
# intent - they hardcode one client for a reproducible render - so they are the
# accepted carve-out, kept explicit here.
_DMC = ROOT.parent / "dmc-renderer"
if _DMC.is_dir():
    for name in (
        "build_live.py", "build_v3.py", "adapter_v3.py",
        "synthesize_visuals.py", "service.py",
    ):
        candidate = _DMC / name
        if candidate.exists():
            SCANNED.append(candidate)

# --- patterns ----------------------------------------------------------------
# A raw hex COLOR literal: # + 3/4/6/8 hex digits at a word boundary. We strip
# numeric HTML entities (&#10003; / &#x2713;) first so a character reference is
# never mistaken for a hex color, and we ignore a `#` that is clearly part of a
# URL fragment / anchor (…://… or href="…#…") rather than a color.
_HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
_NUMERIC_ENTITY = re.compile(r"&#x?[0-9a-fA-F]+;")
_URL_HASH = re.compile(r"https?://\S*#|#[A-Za-z][\w-]*\b")  # scheme URLs / id-anchors

# Forbidden font-family string literals (any of the brand faces, in ' or ").
# Broad on purpose: bare family stems (Playfair, Source Sans, Source Serif,
# Vollkorn, Montserrat, Gestura) all fail, with or without a trailing weight.
_FONT_LIT = re.compile(
    r"""['"]\s*(Montserrat|Playfair|Source\s+Sans|Source\s+Serif|Vollkorn|Gestura)"""
)

# Structural client-name branching: `if … client …` in active logic. (The
# hardcoded-client-accent-name case for *.py is owned by
# test_no_coral_in_chassis_logic; this catches the branch shape and extends the
# spirit to .jinja templates/macros.)
_CLIENT_BRANCH = re.compile(r"\bif\b[^\n]*\bclient\b", re.IGNORECASE)


def _strip_comment(path: Path, line: str) -> str:
    """Return the code portion of a line (drop trailing comments) so prose that
    merely *mentions* a client name (e.g. 'the apex deck IS serif') can't trip
    the structural branch check. Conservative: only strips obvious comment
    syntax for the relevant file types; literal regexes still scan the FULL line
    (a hex/font literal in a comment is still a leak worth catching)."""
    suffix = path.suffix
    if suffix == ".py":
        # naive but sufficient: a `#` that starts a comment. Patterns here put
        # no `#hex` in code, so the first `#` reliably begins a comment.
        return line.split("#", 1)[0]
    if suffix == ".css":
        return re.sub(r"/\*.*?\*/", "", line)
    if suffix == ".jinja":
        return re.sub(r"\{#.*?#\}", "", line)
    return line


def _is_hex_color(line: str) -> bool:
    """True iff the line contains a raw hex *color* literal (after discounting
    numeric HTML entities and URL/anchor `#…` fragments)."""
    scrubbed = _NUMERIC_ENTITY.sub("", line)
    scrubbed = _URL_HASH.sub("", scrubbed)
    return bool(_HEX.search(scrubbed))


def test_no_raw_literals_in_architecture_files():
    violations: list[str] = []
    for f in SCANNED:
        if not f.exists():
            continue
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            code = _strip_comment(f, line)
            if _is_hex_color(line):
                violations.append(f"{f.name}:{i}: [hex] {line.strip()}")
            if _FONT_LIT.search(line):
                violations.append(f"{f.name}:{i}: [font] {line.strip()}")
            if _CLIENT_BRANCH.search(code):
                violations.append(f"{f.name}:{i}: [client-branch] {line.strip()}")
    assert not violations, (
        "brand literal / client branch leaked into a token-only architecture "
        "file. Put universal primitives in tokens/base.tokens.json; per-client "
        "colors + fonts arrive as semantic tokens (var(--...)) at render time:\n"
        + "\n".join(violations)
    )


def test_no_em_dashes_in_treatment_files():
    """Em dashes (U+2014) are banned from all authored treatment chrome: templates,
    stylesheets, and the treatment engine/stylist modules. The project hard rule
    is to use commas, colons, periods, or parens instead. Genuine client DATA
    (fixtures, JSON, runtime strings) is NOT scanned here, so it is naturally
    exempt. Only authored chrome is covered.

    This test is GREEN while no treatment files exist and will turn RED
    automatically if a future file introduces an em dash in authored content.
    """
    EM_DASH = chr(0x2014)  # the em dash, built via chr() so this file stays glyph-clean

    # Collect the treatment-system files to scan.
    treatment_files: list[Path] = []

    templates_treatments = ROOT / "templates" / "treatments"
    if templates_treatments.exists():
        treatment_files += sorted(
            [p for p in templates_treatments.rglob("*.jinja") if "__pycache__" not in p.parts]
        )

    styles_treatments = ROOT / "styles" / "treatments"
    if styles_treatments.exists():
        treatment_files += sorted(
            [p for p in styles_treatments.rglob("*.css") if "__pycache__" not in p.parts]
        )

    for name in ("treatment_stylist.py", "treatment_catalog.py", "treatment_engine.py"):
        candidate = ROOT / name
        if candidate.exists():
            treatment_files.append(candidate)

    violations: list[str] = []
    for path in treatment_files:
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if EM_DASH in line:
                violations.append(f"{path.name}:{lineno}: {line.strip()}")

    assert not violations, (
        "Em dash (U+2014) found in authored treatment chrome. "
        "The project hard rule: never use em dashes in anything authored. "
        "Use commas, colons, periods, or parens instead. "
        "Genuine client data (fixtures, JSON) is not scanned here and is exempt.\n"
        + "\n".join(violations)
    )
