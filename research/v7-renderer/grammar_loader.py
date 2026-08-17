"""Grammar loader — KEYSTONE of the chassis.

================================================================
SOURCE-OF-TRUTH BOUNDARY
================================================================

This module is the renderer's only authorized source of grammar — the
rules for visual intent that determine what a "correct" rendered page
looks like.

INSIDE the boundary (authoritative for visual intent):
  richard-grammar-v2.md  (at the project root)
  byte-fresh at every load. This file is the human-authored,
  byte-verified encoding of Richard's brand language — built from a
  64-page visual sweep plus the 5 LIVE Richard spec documents, and
  validated against the matrix's 2026-05-18 RICHARD-PRIMARY
  RE-RATIFICATION block.

OUTSIDE the boundary (NOT authoritative for visual intent):
  - Pattern files (templates/st_*.py)
  - Render-time prose / user feedback / chat instructions
  - render_v7.py (the prior monolith; symptom artifact only)
  - The retired SKILL.md at
    research/idml-spike/skills/richard-design-system/SKILL.md
    (marked DEAD in its first line; left on disk for supersession audit)
  - This loader's own code comments
  None of these may be a source of grammar.

THE RULE:
  Patterns MUST derive every grammar decision from this loader.
  Patterns MUST NOT re-derive grammar from prose, screenshots, or
  hand-tuning at render time. If a pattern needs a fact this loader
  does not expose, the failure mode is FAIL LOUD (raise) — never fall
  back to a guess.

THE TRUST GATE (RATIFIED-BY):
  The grammar file carries a `RATIFIED-BY:` line in its header. Until
  a human (the ratifier) has read the grammar against the source PDFs
  AND Richard's 5 LIVE spec docs and filled that line with their name,
  the loader REFUSES to load — raising GrammarUnratifiedError at load
  time, not mid-render. The signature IS the audit; an unaudited
  signature defeats the gate. While blank, the chassis is deliberately
  non-functional. That is correct. Same pattern as BrandConfigError
  in brand_tokens.py: fail loud at config time.

WHY THIS EXISTS:
  render_v7.py — the prior monolithic renderer — failed because it had
  no source-of-truth layer. Every visual value in it was a Python
  literal typed by hand after a feedback round, with no link to the
  grammar files. That produced 12 hand-tuning iterations that never
  converged and shipped six universal anti-pattern violations. This
  loader is the structural fix: visual values live in
  richard-grammar-v2.md (and what the matrix has ratified against it),
  not in code.

MOVE 0 (2026-05-23) — REPOINTED:
  The loader previously read SKILL.md (the dead grammar — overfit to 2
  pages of one client). It now reads richard-grammar-v2.md (Layer A /
  Layer B grammar, byte-verified against 64 reference pages across 5
  clients plus 5 LIVE Richard spec docs). SKILL.md is marked DEAD in
  place but not deleted (supersession audit trail). The RATIFIED-BY
  gate is the trust-boundary fix introduced in this same move.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# ============================================================
# Path to the source-of-truth grammar file.
#
# The grammar lives at the project root (one level up from research/).
# If the chassis is later promoted to a different repo location
# (dmc-renderer/), this anchor needs revisiting (env var, packaged
# resource, etc.) — flagged in CHASSIS-NOTES.md.
# ============================================================
_DEFAULT_GRAMMAR_PATH = (
    Path(__file__).resolve().parent
    / ".." / ".." / "richard-grammar-v2.md"
).resolve()


class GrammarMissingError(RuntimeError):
    """A pattern asked for a grammar section that does not exist.

    This is FAIL LOUD per the chassis contract. Do not catch this and
    fall back to a default — the correct response is to fix the grammar
    (add the section) or fix the pattern's expectation (it asked for
    the wrong section), not to paper over the gap.
    """
    pass


class GrammarUnratifiedError(RuntimeError):
    """The grammar file's RATIFIED-BY: header line is blank.

    This is the trust-boundary gate. The grammar is not loaded until a
    human ratifier has audited it against the source documents and
    filled the RATIFIED-BY: line in the header. While blank, the loader
    REFUSES to read the file — chassis is intentionally non-functional.

    Same pattern as BrandConfigError in brand_tokens.py: fail loud at
    config time, not mid-render. The chassis must not render against
    an unaudited grammar — the GEVA-shaped failure of the prior frame
    came from exactly this missing trust layer.

    To resolve: a human reads the grammar against the reference PDFs
    AND Richard's 5 LIVE spec docs, confirms it is correct, then edits
    the RATIFIED-BY: line in the grammar header (replacing the
    underscores with their name, e.g.,
        `RATIFIED-BY:    Utkarsh 2026-05-23`).
    """
    pass


@dataclass(frozen=True)
class GrammarSection:
    """One §-section of the source-of-truth grammar file.

    `number` is the §-section identifier (e.g., "1", "2", "5a", "10").
    `title` is the heading text after the §-number (e.g., "The palette").
    `body` is the raw markdown content between this heading and the next,
    byte-fresh from disk. Patterns parse the body text as they need
    specific facts; the loader does not pre-parse.
    """
    number: str
    title: str
    body: str


@dataclass(frozen=True)
class Grammar:
    """The loaded grammar object that patterns consume.

    Built once at chassis startup by load_grammar(). Patterns hold a
    reference to this object and call get_section() / has_section() —
    they never re-read the grammar file directly. That is the discipline
    that keeps richard-grammar-v2.md as the single source of truth.
    """
    source_path: Path
    sections: dict[str, GrammarSection]

    def get_section(self, number: str) -> GrammarSection:
        """Return the grammar section by §-number.

        Raises GrammarMissingError if absent. FAIL-LOUD path — patterns
        must not silently default.
        """
        if number not in self.sections:
            raise GrammarMissingError(
                f"Grammar section §{number} not found in {self.source_path}. "
                f"Available sections: {sorted(self.sections.keys())}. "
                f"Patterns must not fall back to a guess; fix the grammar "
                f"or the pattern's expectation."
            )
        return self.sections[number]

    def has_section(self, number: str) -> bool:
        """Non-raising existence check.

        Use sparingly — prefer get_section() and let the FAIL-LOUD path
        catch missing grammar. has_section() exists for the contract
        test and for legitimate optional-section logic (rare).
        """
        return number in self.sections


# ============================================================
# Parser
#
# richard-grammar-v2.md section convention (current format, MOVE 1):
#   ## §0  HOW TO READ THIS GRAMMAR         (h2, top-level §-section)
#   ## §1  THE REPORT                       (h2, top-level §-section)
#   ### §1.2  THE 20-PAGE SLOT PLAN  [HARD] (h3, sub-section)
#   ## §2  LAYER-A PATTERN LIBRARY          (h2)
#   ### §3.6  ACCENT BUDGET PER PAGE  [HARD]  (h3, dot-numbered)
#   ### §4.0  AXES                          (h3, dot-numbered with .0)
#   ### §6.1  UNIVERSAL [HARD]              (h3)
#
# Pattern: `##` or `###`, ONE space, `§`, the section identifier
# (a number or a number.subnumber, e.g. "0", "1", "1.2", "3.6",
# "4.0", "6.1"), ONE OR MORE whitespace (the format uses two spaces
# but be lenient), then the title (which may itself contain spaces,
# [HARD]/[SOFT] tier tags, or parenthetical clarifications).
#
# We match both h2 and h3 §-headings into a flat section dict.
#
# HISTORY:
#   Move 0 (2026-05-23): SKILL.md retired; loader repointed at
#       richard-grammar-v2.md. Old regex (`^#{2,3} (\d+[a-z]?)\. (.+)$`)
#       did not match the new format; gate blocked load before parser
#       was exercised.
#   Move 1 (2026-05-23): regex updated to the new format. Section
#       identifier may now be N or N.M (dot-numbered, no letter
#       suffix). Bare-text §0.X labels in §0's body (no `##`/`###`
#       prefix) are NOT headings — they are inline section markers
#       Richard uses for reading order. The regex correctly skips
#       them because they have no markdown heading prefix.
# ============================================================

_SECTION_HEADING_RE = re.compile(
    r"^#{2,3} §(\d+(?:\.\d+)?)\s+(.+)$",
    re.MULTILINE,
)


# ============================================================
# RATIFIED-BY trust gate
#
# The grammar header has a line like:
#   RATIFIED-BY:    ____________________   (Utkarsh, after auditing...)
# Until a human replaces the underscores with their name, the loader
# refuses to read the file. Same fail-loud pattern as BrandConfigError.
# ============================================================

_RATIFIED_BY_RE = re.compile(r"^RATIFIED-BY:\s*(.+)$", re.MULTILINE)


def _check_ratified_by(text: str, path: Path) -> None:
    """Inspect the grammar header for a filled RATIFIED-BY: line.

    Searches the first ~30 lines for a line matching RATIFIED-BY:.
    Extracts the value, strips parenthetical comment + whitespace +
    underscores, and raises GrammarUnratifiedError if what remains is
    empty. This is the trust-boundary gate: the loader REFUSES to load
    an unratified grammar.

    The value is considered blank if it is empty, all whitespace, or
    all underscores (the literal state of a fresh grammar header
    before a human ratifier has filled it).
    """
    # Look only in the header (first 30 lines) — the field is required
    # to be in the header block, not hidden somewhere deeper.
    header = "\n".join(text.splitlines()[:30])

    match = _RATIFIED_BY_RE.search(header)
    if not match:
        raise GrammarUnratifiedError(
            f"Grammar file {path} has no `RATIFIED-BY:` line in its first "
            f"30 lines. The trust-boundary gate requires a `RATIFIED-BY:` "
            f"header line before the loader will read the file. Either "
            f"add one (with the human ratifier's name) or stop and ask "
            f"why the grammar is missing its trust header — a grammar "
            f"with no trust line is structurally untrusted and the "
            f"chassis cannot render against it."
        )

    raw_value = match.group(1)
    # Strip an inline parenthetical comment (e.g. "(after auditing...)").
    value_no_paren = re.sub(r"\(.*$", "", raw_value).strip()
    # Strip surrounding whitespace, then strip underscores (the literal
    # blank-by-underscores state of a fresh grammar header).
    value_clean = value_no_paren.strip().strip("_").strip()

    if not value_clean:
        raise GrammarUnratifiedError(
            f"Grammar at {path} is UNRATIFIED: the `RATIFIED-BY:` line "
            f"is blank (value was: {value_no_paren!r}). The chassis "
            f"refuses to render with an unratified grammar — by design. "
            f"\n\nTo resolve: read the grammar against the reference "
            f"PDFs (the 64-page visual corpus) AND Richard's 5 LIVE spec "
            f"docs (01_DMC_Master_System_v1.md, 08_DMC_Design_System_v2"
            f".md, DMC_InDesign_Spec_v1.md, 04_DMC_Copy_Masterbook_v3"
            f".md, 05_DMC_Intelligence_Layer_v4.md). Confirm the grammar "
            f"is correct. Then edit the grammar header and replace the "
            f"underscores in the `RATIFIED-BY:` line with your name and "
            f"date (e.g., `RATIFIED-BY:    Utkarsh 2026-05-23`). The "
            f"signature IS the audit; an unaudited signature defeats "
            f"the gate."
        )


def load_grammar(grammar_path: Optional[Path] = None) -> Grammar:
    """Load the grammar from richard-grammar-v2.md.

    Called once at chassis startup. Returns a frozen Grammar object that
    patterns consume read-only.

    Raises FileNotFoundError if the grammar file is missing — the
    chassis cannot operate without its source of truth. Do not handle
    this by falling back to defaults; the chassis is broken and the
    operator must fix the path or restore the file.

    Raises GrammarUnratifiedError if the grammar's `RATIFIED-BY:`
    header line is blank — the trust-boundary gate. Until a human has
    audited the grammar and filled the RATIFIED-BY: line, the loader
    refuses to read the file. This is intentional. This fires BEFORE
    section parsing so an unratified grammar never reaches any
    downstream code.

    Raises RuntimeError if the grammar is present and ratified but
    parses to zero sections (signals a format change the parser cannot
    handle — see the Move 0 surfaced issue note above the parser regex).
    """
    path = (grammar_path or _DEFAULT_GRAMMAR_PATH).resolve()

    if not path.exists():
        raise FileNotFoundError(
            f"Source-of-truth grammar file not found: {path}. "
            f"The chassis cannot operate without richard-grammar-v2.md. "
            f"Do not patch around this by adding defaults to the loader; "
            f"fix the path or restore the file."
        )

    text = path.read_text(encoding="utf-8")

    # ======== TRUST GATE (R9/F1 trust-boundary fix) ========
    # The grammar header carries a RATIFIED-BY: line that must be filled
    # by a human ratifier. While blank (underscores), the loader refuses
    # to load — chassis is intentionally non-functional. This fires
    # BEFORE section parsing so an unratified grammar never reaches any
    # downstream code.
    _check_ratified_by(text, path)

    matches = list(_SECTION_HEADING_RE.finditer(text))

    sections: dict[str, GrammarSection] = {}
    for i, m in enumerate(matches):
        number = m.group(1)
        title = m.group(2).strip()
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[body_start:body_end].strip()
        sections[number] = GrammarSection(number=number, title=title, body=body)

    if not sections:
        raise RuntimeError(
            f"Parsed zero §-sections from {path}. The grammar format may "
            f"have changed (the parser expects `## §N  TITLE` or "
            f"`### §N.M  TITLE` per the Move 1 regex), or the parser "
            f"regex needs revision. Do not proceed with an empty "
            f"grammar — that defeats the source-of-truth boundary."
        )

    return Grammar(source_path=path, sections=sections)
