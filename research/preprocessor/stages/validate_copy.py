"""Stage 3 — copy validation per grammar §3.9.

Walks every string value in every page's `data` block and flags copy
violations against Richard's rules. ALL outputs are WARNINGS — Stage 3
never blocks a render. Richard's QA process decides what to fix.

Cross-page state is tracked for two construction limits:
  - "Nicht X, sondern Y" — max 1× per report (flag from 2nd occurrence)
  - Dreiwort-Satz-Kette  — max 1× per report (three consecutive ≤3-word sentences)

Rules implemented (each yields `rule` codes a downstream consumer can
branch on):

  buzzword_denylist                — innovativ, maßgeschneidert, etc.
                                     (with context exceptions for
                                     nachhaltig / einzigartig / der-beste)
  konjunktiv                       — könnte, würde, sollte, …
  vague_promise                    — bessere Ergebnisse, etc. without
                                     numeric specificity
  verboten_opening                 — Richard's §9 forbidden openers
  passive_voice                    — wird/werden/wurde + past participle
  construction_limit_nicht_sondern — second+ occurrence in the report
  construction_limit_dreiwort_chain — second+ chain in the report

The text walker is recursive over dicts/lists so e.g. `kunde.name` and
`teaser_bullets[2]` both get checked. Empty data fields produce zero
warnings (graceful — many pages have nothing on them yet).
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

from models import CopyWarning, ReportPage


# ─────────────────────────────────────────────────────────────────────────────
# Rule constants (exported — Stage 4 cross-references the denylist on S3)
# ─────────────────────────────────────────────────────────────────────────────

# Hard buzzwords — flagged on every occurrence with no context exception.
BUZZWORD_DENYLIST_HARD: tuple[str, ...] = (
    "innovativ",
    "maßgeschneidert",
    "ganzheitlich",
    "state-of-the-art",
    "Passion",
    "Leidenschaft",
    "Herzblut",
    "game-changer",
    "Synergie",
    "Mehrwert",
)

# Conditional buzzwords — flagged unless their context exception is met.
BUZZWORD_DENYLIST_CONDITIONAL: tuple[str, ...] = (
    "nachhaltig",   # OK in actual sustainability context
    "einzigartig",  # OK if followed by concrete proof within 50 chars
    "der beste",    # same
)

# Combined for Stage 4's S3 cross-check.
BUZZWORD_DENYLIST_ALL: tuple[str, ...] = (
    BUZZWORD_DENYLIST_HARD + BUZZWORD_DENYLIST_CONDITIONAL
)

# Sustainability-context indicators (page-level — if any of these appears
# anywhere on the page, "nachhaltig" is allowed on that page).
SUSTAINABILITY_INDICATORS: tuple[str, ...] = (
    "Umwelt", "ökologisch", "CO2", "CO₂", "Sustainability",
    "Nachhaltigkeit", "Klima", "erneuerbar", "recycelt",
    "Bio", "fair trade", "umweltfreundlich",
)

# Subjunctive (Konjunktiv II) — Richard's style uses absolute statements.
KONJUNKTIV_WORDS: tuple[str, ...] = (
    "könnte", "könnten", "könntest", "könntet",
    "würde", "würden", "würdest", "würdet",
    "sollte", "sollten", "solltest", "solltet",
    "dürfte", "dürften",
    "müsste", "müssten", "müsstest", "müsstet",
    "hätte", "hätten", "hättest", "hättet",
    "wäre", "wären", "wärest", "wäret",
)

# Vague promises — flagged unless a number appears within ±30 chars.
VAGUE_PROMISES: tuple[str, ...] = (
    "bessere Ergebnisse",
    "mehr Erfolg",
    "optimale Lösung",
    "höhere Effizienz",
)
# Special-cased because the standalone "effizient" needs the same
# specificity check.
VAGUE_STANDALONE_EFFIZIENT = re.compile(r"\beffizient\b", re.IGNORECASE)

# Verboten openings — strings that, if they appear as the FIRST words of
# any text field, are flagged. Source: Richard's 11_Cover_Headlines §9.
VERBOTEN_OPENINGS: tuple[str, ...] = (
    "In der heutigen Geschäftswelt",
    "Digitalisierung ist heute wichtiger denn je",
    "Wir alle kennen das Gefühl",
    "Das Agenturbusiness boomt",
    "Jetzt ist der richtige Zeitpunkt",
    "Endlich",
    "Die Lösung für alle",
)

# "Nicht X, sondern Y" — em-dash variant accepted.
_NICHT_SONDERN_RE = re.compile(
    r"\bnicht\b[^.!?\n]{0,80}\b(?:sondern)\b",
    re.IGNORECASE,
)

# Passive voice — "wird/werden/wurde/worden" + up to 5 words +
# past participle "ge…t" / "ge…en" / "…iert".
_PASSIVE_RE = re.compile(
    r"\b(wird|werden|wurde|wurden|worden)\b"
    r"(?:\s+\S+){0,5}\s+"
    r"\b(?:ge\w+(?:t|en)|\w+iert)\b",
    re.IGNORECASE,
)


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────


def validate_copy(pages: list[ReportPage] | list[dict]) -> list[CopyWarning]:
    """Run Stage 3 against the report's pages. Returns a list of
    CopyWarning objects (possibly empty). Never raises on missing /
    empty fields — pages with no copy produce zero warnings.

    Accepts both Pydantic `ReportPage` instances and plain dicts (the
    FastAPI route passes the former; tests sometimes pass the latter).
    """
    warnings: list[CopyWarning] = []

    # Cross-report counters — flagged from the 2nd occurrence onward.
    nicht_sondern_seen = 0
    dreiwort_chain_seen = 0

    for page in pages:
        slot, page_type, data = _unpack_page(page)
        if not isinstance(data, dict):
            continue

        # Collect the whole page's text once for context checks
        # (e.g. sustainability-context exception for "nachhaltig").
        page_full_text = " ".join(_collect_all_strings(data))
        sustainability_context = _is_sustainability_context(page_full_text)

        for field_name, text in _walk_strings(data):
            warnings.extend(
                _check_buzzwords_hard(text, slot, page_type, field_name)
            )
            warnings.extend(
                _check_buzzwords_conditional(
                    text, slot, page_type, field_name,
                    sustainability_context=sustainability_context,
                )
            )
            warnings.extend(_check_konjunktiv(text, slot, page_type, field_name))
            warnings.extend(_check_vague_promises(text, slot, page_type, field_name))
            warnings.extend(_check_verboten_openings(text, slot, page_type, field_name))
            warnings.extend(_check_passive_voice(text, slot, page_type, field_name))

            # Cross-page counter: "Nicht X, sondern Y".
            for match in _NICHT_SONDERN_RE.finditer(text):
                nicht_sondern_seen += 1
                if nicht_sondern_seen > 1:
                    warnings.append(CopyWarning(
                        page_slot=slot, page_type=page_type, field_name=field_name,
                        rule="construction_limit_nicht_sondern",
                        detail=(
                            f"'Nicht … sondern …' construction "
                            f"(occurrence #{nicht_sondern_seen} in report) — "
                            f"max 1 per report; offending text: "
                            f"{_clip(match.group(0))!r}"
                        ),
                    ))

            # Cross-page counter: Dreiwort-Satz-Kette.
            chains = _find_dreiwort_chains(text)
            for chain_text in chains:
                dreiwort_chain_seen += 1
                if dreiwort_chain_seen > 1:
                    warnings.append(CopyWarning(
                        page_slot=slot, page_type=page_type, field_name=field_name,
                        rule="construction_limit_dreiwort_chain",
                        detail=(
                            f"Three-word-sentence chain "
                            f"(occurrence #{dreiwort_chain_seen} in report) — "
                            f"max 1 per report; chain: {_clip(chain_text)!r}"
                        ),
                    ))

    return warnings


# ─────────────────────────────────────────────────────────────────────────────
# Per-rule checkers
# ─────────────────────────────────────────────────────────────────────────────


def _buzzword_regex(stem: str) -> re.Pattern[str]:
    """Build a regex that catches a German buzzword + any inflectional
    suffix (`innovativ` → also `innovative`, `innovativer`, `innovativen`).

    For multi-word phrases ("state-of-the-art", "der beste") we match
    the literal phrase — inflection isn't a concern there.
    """
    escaped = re.escape(stem)
    if " " in stem or "-" in stem:
        return re.compile(rf"\b{escaped}\b", re.IGNORECASE)
    # German adjective endings (-e, -er, -en, -es, -em, -sten, -ste, etc.)
    return re.compile(rf"\b{escaped}\w{{0,5}}\b", re.IGNORECASE)


def _check_buzzwords_hard(
    text: str, slot: int, page_type: str, field_name: str
) -> list[CopyWarning]:
    out: list[CopyWarning] = []
    for buzz in BUZZWORD_DENYLIST_HARD:
        pattern = _buzzword_regex(buzz)
        for match in pattern.finditer(text):
            out.append(CopyWarning(
                page_slot=slot, page_type=page_type, field_name=field_name,
                rule="buzzword_denylist",
                detail=(
                    f"Found {match.group(0)!r} — consider replacing with a "
                    f"specific, evidence-bearing claim"
                ),
            ))
    return out


def _check_buzzwords_conditional(
    text: str, slot: int, page_type: str, field_name: str,
    *, sustainability_context: bool,
) -> list[CopyWarning]:
    out: list[CopyWarning] = []

    # nachhaltig — only if page-level context isn't actual sustainability
    if not sustainability_context:
        for match in _buzzword_regex("nachhaltig").finditer(text):
            out.append(CopyWarning(
                page_slot=slot, page_type=page_type, field_name=field_name,
                rule="buzzword_denylist",
                detail=(
                    f"Found {match.group(0)!r} outside a sustainability "
                    f"context — replace with a specific claim"
                ),
            ))

    # einzigartig — needs numeric proof within ±50 chars (inflection-aware)
    for match in _buzzword_regex("einzigartig").finditer(text):
        window_start = max(0, match.start() - 50)
        window = text[window_start:match.end() + 50]
        if not re.search(r"\d", window):
            out.append(CopyWarning(
                page_slot=slot, page_type=page_type, field_name=field_name,
                rule="buzzword_denylist",
                detail=(
                    f"Found {match.group(0)!r} without concrete proof "
                    f"(no number within ±50 chars) — add specificity"
                ),
            ))

    # der beste — multi-word phrase, no inflection variants
    for match in re.finditer(r"\bder beste\b", text, re.IGNORECASE):
        window_start = max(0, match.start() - 50)
        window = text[window_start:match.end() + 50]
        if not re.search(r"\d", window):
            out.append(CopyWarning(
                page_slot=slot, page_type=page_type, field_name=field_name,
                rule="buzzword_denylist",
                detail=(
                    f"Found {match.group(0)!r} without concrete proof "
                    f"(no number within ±50 chars) — add specificity"
                ),
            ))

    return out


def _check_konjunktiv(
    text: str, slot: int, page_type: str, field_name: str
) -> list[CopyWarning]:
    out: list[CopyWarning] = []
    for word in KONJUNKTIV_WORDS:
        for match in re.finditer(rf"\b{re.escape(word)}\b", text, re.IGNORECASE):
            out.append(CopyWarning(
                page_slot=slot, page_type=page_type, field_name=field_name,
                rule="konjunktiv",
                detail=(
                    f"Subjunctive {match.group(0)!r} found — Richard's style "
                    f"uses absolute statements"
                ),
            ))
    return out


def _check_vague_promises(
    text: str, slot: int, page_type: str, field_name: str
) -> list[CopyWarning]:
    out: list[CopyWarning] = []
    # Phrase-level vague promises
    for phrase in VAGUE_PROMISES:
        for match in re.finditer(rf"\b{re.escape(phrase)}\b", text, re.IGNORECASE):
            if _has_number_near(text, match.start(), match.end()):
                continue
            out.append(CopyWarning(
                page_slot=slot, page_type=page_type, field_name=field_name,
                rule="vague_promise",
                detail=(
                    f"Vague promise {match.group(0)!r} without numeric "
                    f"specificity within ±30 chars — quantify or remove"
                ),
            ))

    # Standalone effizient
    for match in VAGUE_STANDALONE_EFFIZIENT.finditer(text):
        if _has_number_near(text, match.start(), match.end()):
            continue
        out.append(CopyWarning(
            page_slot=slot, page_type=page_type, field_name=field_name,
            rule="vague_promise",
            detail=(
                f"{match.group(0)!r} without numeric specificity within "
                f"±30 chars — quantify (e.g. '40% effizienter')"
            ),
        ))
    return out


def _check_verboten_openings(
    text: str, slot: int, page_type: str, field_name: str
) -> list[CopyWarning]:
    """Flag if `text` (after leading whitespace) opens with one of the
    forbidden phrases from Richard's 11_Cover_Headlines §9.
    """
    stripped = text.lstrip()
    if not stripped:
        return []
    out: list[CopyWarning] = []
    for opener in VERBOTEN_OPENINGS:
        if stripped.lower().startswith(opener.lower()):
            out.append(CopyWarning(
                page_slot=slot, page_type=page_type, field_name=field_name,
                rule="verboten_opening",
                detail=(
                    f"Field opens with {opener!r} — Richard's §9 forbids "
                    f"this; rewrite with a concrete situation"
                ),
            ))
            break  # only the first matching opener counts
    return out


def _check_passive_voice(
    text: str, slot: int, page_type: str, field_name: str
) -> list[CopyWarning]:
    out: list[CopyWarning] = []
    for match in _PASSIVE_RE.finditer(text):
        out.append(CopyWarning(
            page_slot=slot, page_type=page_type, field_name=field_name,
            rule="passive_voice",
            detail=(
                f"Passive construction {_clip(match.group(0))!r} — German "
                f"B2B copy can use some passive but prefer active voice"
            ),
        ))
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _walk_strings(data: Any, prefix: str = "") -> Iterator[tuple[str, str]]:
    """Yield (field_path, string_value) for every string in `data`.

    Recurses into dicts and lists; field paths look like
    `kunde.name`, `teaser_bullets[2]`, `pullquote.attribution`.
    """
    if isinstance(data, str):
        yield (prefix or "<root>", data)
    elif isinstance(data, dict):
        for k, v in data.items():
            sub = f"{prefix}.{k}" if prefix else str(k)
            yield from _walk_strings(v, sub)
    elif isinstance(data, list):
        for idx, item in enumerate(data):
            yield from _walk_strings(item, f"{prefix}[{idx}]")
    # Other scalar types (int, bool, None) — skip silently.


def _collect_all_strings(data: Any) -> list[str]:
    """Flatten every string in `data` into a single list (for context
    queries like sustainability-context detection).
    """
    return [text for _, text in _walk_strings(data)]


def _is_sustainability_context(page_text: str) -> bool:
    """True iff any sustainability indicator appears anywhere on the page."""
    lower = page_text.lower()
    return any(ind.lower() in lower for ind in SUSTAINABILITY_INDICATORS)


def _has_number_near(text: str, start: int, end: int, window: int = 30) -> bool:
    """True iff a digit appears within `window` characters either side
    of the match. Used to spare "80% bessere Ergebnisse" from the
    vague-promise rule.
    """
    around = text[max(0, start - window): end + window]
    return bool(re.search(r"\d", around))


def _find_dreiwort_chains(text: str) -> list[str]:
    """Return every chain of THREE consecutive sentences each ≤ 3 words.

    Sentences split on terminal punctuation + whitespace. Each returned
    chain is the concatenated original substring of the 3 sentences.
    """
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    chains: list[str] = []
    short_run: list[str] = []
    for sent in sentences:
        clean = sent.strip()
        if not clean:
            short_run = []
            continue
        # Strip terminal punctuation for word-count.
        words = re.findall(r"\S+", re.sub(r"[.!?]+$", "", clean))
        if len(words) <= 3:
            short_run.append(clean)
            if len(short_run) == 3:
                chains.append(" ".join(short_run))
                short_run = []  # don't double-count overlapping chains
        else:
            short_run = []
    return chains


def _clip(text: str, limit: int = 60) -> str:
    """Truncate long match strings for human-readable warning details."""
    text = text.strip().replace("\n", " ")
    if len(text) <= limit:
        return text
    return text[:limit - 1] + "…"


def _unpack_page(page: ReportPage | dict) -> tuple[int, str, Any]:
    """Normalise a page representation to (slot, type, data)."""
    if isinstance(page, ReportPage):
        return page.slot, page.type, page.data
    # dict-like
    return int(page["slot"]), str(page["type"]), page.get("data", {})
