"""Stage 4 — cover stack validation per Richard's 11_Cover_Headlines doc.

Scores the cover page's headline / subheadline / bullets against three
matrices (H1-H8 / S1-S5 / B1-B5), detects the headline type (Etikett
vs Diagnose), resolves the headline size class for the renderer
(short → 36-44pt, long → 24-30pt), and emits an overall verdict
(pass / pass_with_warnings / needs_review).

Heuristics philosophy (per the prompt): the scoring is text-analysis —
keyword presence, regex pattern matches, length checks. It's a first
pass that Richard's QA can override; it is NOT a replacement for human
judgment on copy quality. Each scoring function documents its heuristic
in its docstring so the limitations are explicit. Where an LLM-based
scorer would be more accurate (e.g. "does this read like a magazine
cover" — H5), that is noted in the function's comment.

Cross-cuts:
  - The S3 buzzword check imports from stages.validate_copy
    (BUZZWORD_DENYLIST_ALL) so the lists never drift.
  - The B3 generic-bullet check uses the same denylist.

Entry point: `validate_cover(cover_page_data: dict, awareness_level: int = 2)`.
Returns a `CoverValidation` Pydantic model with all scores + verdict.
"""

from __future__ import annotations

import re
from typing import Optional

from models import CoverValidation, ScoreDetail
from stages.validate_copy import (
    BUZZWORD_DENYLIST_ALL,
    KONJUNKTIV_WORDS,
    _buzzword_regex,
)


# ─────────────────────────────────────────────────────────────────────────────
# Heuristic constants
# ─────────────────────────────────────────────────────────────────────────────

# Audience-indicator stems. Matched with German inflection tolerance
# (e.g. "Agentur" also matches "Agenturen", "Berater" also "Beraterin").
_AUDIENCE_STEMS: tuple[str, ...] = (
    "Agentur", "Berater", "Coach", "Dienstleister", "Praxis",
    "Geschäftsführer", "Unternehmer", "Makler", "Handwerk",
    "Zahnarzt", "Physio", "Steuerberater", "Architekt",
    "Anwalt", "Therapeut", "Mediziner", "B2B",
)

# Numeric / temporal specificity signals (H2 / S2).
# Numbers, percentages, currency, time spans, "200k"-style abbreviations.
_NUMERIC_RE = re.compile(
    r"(\d+\s*[k%€$]|"
    r"\d+\.\d+|\d+,\d+|"
    r"\d+\s*(?:Tag|Tagen|Woche|Wochen|Monat|Monaten|Jahr|Jahren|Minute|Minuten|Stunde|Stunden|Sek)|"
    r"\b\d+\b)",
    re.IGNORECASE,
)

# Concrete-situation verbs (H3 / S2). German B2B copy that uses these
# verbs IS specific — they describe a state the reader is in, not an
# abstract goal.
_SITUATION_VERBS: tuple[str, ...] = (
    "stecken", "stecke", "verlieren", "verlierst", "verloren",
    "auffressen", "verbrennen", "verbrennst", "verbrennt",
    "ärgern", "kämpfen", "kämpfst", "scheitern", "scheiterst",
    "verbrauchen", "verbrauchst", "verpasst", "verpasst",
    "kostet", "kosten", "kostest", "abmühen",
    "festfahren", "festfährst", "bleiben", "bleibst", "bleibt",
    "übersehen", "übersiehst", "unterschätzen",
)

# Novelty-signal phrases (H8). Words that promise "you don't know this".
_NOVELTY_PATTERNS: tuple[str, ...] = (
    r"\bwarum\b", r"\bwieso\b",
    r"\bder grund\b", r"\bdie gründe\b",
    r"\bder eine grund\b",
    r"\bder fehler\b", r"\bdie fehler\b",
    r"\bdas geheimnis\b", r"\bdie wahrheit\b",
    r"\bwas\s+\S+\s+nicht\s+(weißt|wissen|weiß)\b",
    r"\bkaum jemand\b",
    r"\bdie meisten\b.*\b(falsch|nicht)\b",
    r"\bniemand\s+(sagt|spricht|redet)\b",
    r"\bnoch nicht\b",
)

# Ad-language markers (H7). Penalised — Richard's copy reads editorial.
_AD_LANGUAGE_PATTERNS: tuple[str, ...] = (
    r"\bjetzt\s+(entdecke|sichere|hol)", r"\bjetzt\s+kostenlos\b",
    r"\bhier\s+(klicke|finde|kaufe)", r"\bklicke?\s+hier\b",
    r"\bsicher\s+dir\b",
    r"\bdie\s+beste\s+lösung\b",
    r"\bnur\s+heute\b", r"\bnur\s+für\s+kurze\s+zeit\b",
    r"!{2,}",  # multiple exclamation marks
)

# Curiosity openers (H6, B1) — these signal "I'm posing a question".
_CURIOSITY_OPENERS: tuple[str, ...] = (
    "warum", "wieso", "wie", "was", "welche", "welcher", "welches",
    "die n gründe",  # placeholder for digit
    "der eine grund",
    "was passiert wenn", "was wäre wenn",
    "die wahrheit", "der fehler", "der grund",
    "die eine änderung",
)

# Method-reveal pattern (H6, B2). If the headline / bullet says
# "Wie du X erreichst" or "Mit Y zu Z" with concrete X/Y/Z, it gives
# away the method.
_METHOD_REVEAL_PATTERNS: tuple[str, ...] = (
    r"\bmit\s+(?:der\s+|dem\s+|unserer\s+)?\w+\s+(?:erreichst|schaffst|kommst)\b",
    r"\bnutze\s+\w+\s+um\s+\w+\s+zu\b",
    r"\bso\s+erreichst\s+du\b",
)

# Subjunctive forms (S5) imported from Stage 3 (KONJUNKTIV_WORDS).

# Agitation cues (S1) — subheadlines that name the pain.
_AGITATION_CUES: tuple[str, ...] = (
    r"\bkostet?\b", r"\bverlier(?:st|en|t)\b", r"\bschief\b",
    r"\bscheiterst?\b", r"\bohne\b", r"\bnoch\b",
    r"\bfehler\b", r"\bproblem\b", r"\b(?:zurück)?bleib(?:st|t|en)\b",
    r"\bverpasst?\b",
)

# Shiny-Object cues (S1) — subheadlines that promise the outcome.
_SHINY_OBJECT_CUES: tuple[str, ...] = (
    r"\berreichst\b", r"\bschaffst\b", r"\bwirst\b", r"\bkannst\b",
    r"\bbekommst\b", r"\bgewinnst\b",
    r"\bwie\s+du\s+\w+\s+(?:erreichst|schaffst|gewinnst)\b",
)

# Headline-subtype detection patterns (H4 awareness-matrix lookup).
# Each subtype maps to a list of distinctive regex patterns. First match
# wins; if zero match, subtype is None (H4 gives a neutral 1).
_SUBTYPE_PATTERNS: dict[str, tuple[str, ...]] = {
    "Selbsttest": (
        r"\btest\b", r"\bquiz\b", r"\bfinde\s+heraus\b",
        r"\bbist\s+du\b", r"\bwelcher\s+typ\b",
    ),
    "Marktveränderung": (
        r"\bdie\s+neue\s+realität\b", r"\bhat\s+sich\s+verändert\b",
        r"\balte\s+regeln\b", r"\bder\s+markt\s+ändert\b",
    ),
    "Status-Anerkennung": (
        r"\btop[-\s]?performer\b", r"\bdie\s+wahrheit\s+über\b",
        r"\bwarum\s+erfolgreiche\b", r"\bdie\s+besten\b",
    ),
    "Fehler/Gründe": (
        r"\b(?:die\s+)?\d+\s+gründe\b", r"\b(?:die\s+)?\d+\s+fehler\b",
        r"\bgründe\s+warum\b", r"\bder\s+(?:eine\s+)?grund\b",
        r"\bder\s+(?:eine\s+)?fehler\b",
    ),
    "Plateau": (
        r"\bstecken\s+bleib(?:st|t|en)\b", r"\bplateau\b",
        r"\bdurchbruch\b", r"\bfest(?:gefahren|fährst|sitzt)\b",
        r"\bnicht\s+weiter\s+kommst\b",
    ),
    "Reframe": (
        r"\bin\s+wirklichkeit\b", r"\bdie\s+wahre\s+ursache\b",
        r"\bwas\s+niemand\s+(?:sagt|redet)\b",
        r"\bder\s+eigentliche\s+grund\b",
    ),
    "Ergebnis/Transformation": (
        r"\bin\s+\d+\s+(?:tagen|wochen|monaten)\b",
        r"\bverdoppel(?:n|st|t)\b", r"\bverdreifach(?:en|st|t)\b",
        r"\bvon\s+\S+\s+zu\s+\S+\b",
        r"\btransformation\b",
    ),
    "Named Mechanism": (
        r"\b\w+[-\s](?:methode|system|framework|modell|formel)\b",
    ),
    "Proof/Fallstudie": (
        r"\bfallstudie\b", r"\bcase\s+study\b",
        r"\bso\s+haben\s+wir\b",
    ),
}

# H4 awareness-matrix per §8 of Richard's doc.
_H4_RECOMMENDED: dict[int, tuple[str, ...]] = {
    1: ("Selbsttest", "Marktveränderung"),
    2: ("Status-Anerkennung", "Fehler/Gründe", "Plateau"),
    3: ("Reframe", "Ergebnis/Transformation"),
    4: ("Named Mechanism", "Proof/Fallstudie"),
    5: ("Named Mechanism", "Status-Anerkennung"),
}
# Subtypes explicitly warned-against at certain awareness levels.
_H4_WARNED: dict[int, tuple[str, ...]] = {
    1: ("Named Mechanism", "Proof/Fallstudie"),
    4: ("Selbsttest",),
    5: ("Selbsttest", "Marktveränderung"),
}

# Disqualification patterns (instant flag — overrides scoring).
_DISQ_PRICE_RE = re.compile(
    r"(\d+\s*[€$]|\d+\s*EUR|\bpreis\b|\bkostenlos\b|\bgratis\b|\bfree\b)",
    re.IGNORECASE,
)
_DISQ_ENDLICH_RE = re.compile(r"^\s*endlich\b", re.IGNORECASE)
_DISQ_AUDIENCE_BROAD_PATTERNS: tuple[str, ...] = (
    r"\bfür\s+alle\s+unternehmer\b",
    r"\bfür\s+jeden\b",
    r"\bfür\s+alle\s+firmen\b",
    r"\bfür\s+alle\s+menschen\b",
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _word_count(text: str) -> int:
    return len(re.findall(r"\S+", text or ""))


def _detect_headline_type(headline: str) -> str:
    """Return 'Typ A — Etikett' (4-8 words), 'Typ B — Diagnose' (≥12 words),
    or 'ambiguous' (9-11 words).

    Word count is the primary discriminator per Richard's §1.
    """
    n = _word_count(headline)
    if n == 0:
        return "ambiguous"
    if n <= 8:
        return "Typ A — Etikett"
    if n >= 12:
        return "Typ B — Diagnose"
    return "ambiguous"


def _detect_headline_subtype(headline: str) -> Optional[str]:
    """Return the first subtype whose patterns match, or None.

    Used by H4 to look up the awareness-matrix recommendation. None
    indicates the heuristic can't classify the headline — H4 then
    assigns a neutral score (1).
    """
    low = headline.lower()
    for subtype, patterns in _SUBTYPE_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, low):
                return subtype
    return None


def resolve_headline_size_class(headline: str) -> str:
    """Renderer sizing hint:
       'short' → 36-44pt display (Etikett, 4-8 words)
       'long'  → 24-30pt wrapping 2-3 lines (Diagnose, 12-30 words)
    9-11 word "ambiguous" headlines round up to 'long' (safer for
    multi-line readability).
    """
    n = _word_count(headline)
    return "short" if n <= 8 else "long"


def _any_match(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def _audience_present(text: str) -> bool:
    for stem in _AUDIENCE_STEMS:
        if _buzzword_regex(stem).search(text):
            return True
    return False


def _has_numeric_specificity(text: str) -> bool:
    return bool(_NUMERIC_RE.search(text))


def _has_situation_verb(text: str) -> bool:
    return _any_match(text, tuple(rf"\b{re.escape(v)}\b" for v in _SITUATION_VERBS))


def _has_novelty_signal(text: str) -> bool:
    return _any_match(text, _NOVELTY_PATTERNS)


def _has_ad_language(text: str) -> bool:
    return _any_match(text, _AD_LANGUAGE_PATTERNS)


def _has_method_reveal(text: str) -> bool:
    return _any_match(text, _METHOD_REVEAL_PATTERNS)


def _has_curiosity_opener(text: str) -> bool:
    stripped = text.strip().lower()
    for opener in _CURIOSITY_OPENERS:
        if stripped.startswith(opener):
            return True
    return False


def _contains_buzzword(text: str) -> bool:
    for buzz in BUZZWORD_DENYLIST_ALL:
        if _buzzword_regex(buzz).search(text):
            return True
    return False


def _contains_konjunktiv(text: str) -> bool:
    for word in KONJUNKTIV_WORDS:
        if re.search(rf"\b{re.escape(word)}\b", text, re.IGNORECASE):
            return True
    return False


def _bullet_strength(bullet: str) -> int:
    """Rough strength score per bullet. Used by B5 to find the strongest.

    +2 for numeric/temporal specificity, +1 for curiosity opener,
    +1 for situation verb.
    """
    score = 0
    if _has_numeric_specificity(bullet):
        score += 2
    if _has_curiosity_opener(bullet):
        score += 1
    if _has_situation_verb(bullet):
        score += 1
    return score


# ─────────────────────────────────────────────────────────────────────────────
# H1 — H8 scoring
# ─────────────────────────────────────────────────────────────────────────────


def score_h1_zielgruppen_filter(headline: str) -> tuple[int, str]:
    """H1: Is the target audience immediately clear?
       2 — specific audience named ('Agentur', 'Physiopraxis', ...)
       0 — could be for anyone (no audience stem matched)
    The 0/2 binary is intentional; "implied" is hard to detect reliably
    so we don't award a middle score by guess.
    """
    if _audience_present(headline):
        return 2, "specific audience term present (e.g. Agentur / Berater / Coach)"
    return 0, "no specific audience term — headline could read as for-anyone"


def score_h2_konkretheit(headline: str) -> tuple[int, str]:
    """H2: Numeric / temporal specificity present?
       2 — at least one number / percent / currency / timeframe
       0 — entirely abstract
    """
    if _has_numeric_specificity(headline):
        return 2, "numeric or temporal specificity present"
    return 0, "no number, percentage, or timeframe — entirely abstract"


def score_h3_problempraezision(headline: str) -> tuple[int, str]:
    """H3: Does the headline describe a concrete SITUATION?
       2 — situation verb present ('stecken', 'verbrennen', 'auffressen')
       0 — no situation verb (abstract / benefit-only headline)
    Limitation: the verb list is finite. A headline using a synonym we
    haven't enumerated will under-score.
    """
    if _has_situation_verb(headline):
        return 2, "concrete-situation verb present (e.g. stecken / kostet / verbrennt)"
    return 0, "no situation verb — problem is abstract / benefit-only"


def score_h4_bewusstseinslevel_fit(
    headline: str, awareness_level: int
) -> tuple[int, str]:
    """H4: Does the headline subtype match the reader's awareness level?
       2 — subtype is in the recommended list for this level
       0 — subtype is in the warned-against list for this level
       1 — subtype detected but not recommended/warned (acceptable)
       1 — subtype could not be detected (neutral, can't penalise)
    Heuristic limitation: subtype detection relies on signal phrases.
    Headlines that don't use a recognisable signal land in 'unknown'.
    """
    subtype = _detect_headline_subtype(headline)
    if subtype is None:
        return 1, "headline subtype not detected — neutral score"
    if subtype in _H4_WARNED.get(awareness_level, ()):
        return (
            0,
            f"{subtype!r} is warned against at awareness level {awareness_level}",
        )
    if subtype in _H4_RECOMMENDED.get(awareness_level, ()):
        return (
            2,
            f"{subtype!r} is recommended for awareness level {awareness_level}",
        )
    return (
        1,
        f"{subtype!r} is acceptable but not optimal for awareness level {awareness_level}",
    )


def score_h5_magazin_wuerdigkeit(headline: str) -> tuple[int, str]:
    """H5: Could it appear on a real magazine cover?
    NOTE: length is intentionally NOT a criterion (per Richard's doc;
    a 25-word Diagnose can be 'magazine-worthy' too).

    Heuristic: penalise clickbait markers (excessive '!', ad language).
    This is the WEAKEST heuristic in the matrix — an LLM-based scorer
    would do meaningfully better here because 'reads editorial' is a
    judgment call regex can't fully make. Documented as a known
    limitation in the Phase B writeup.
    """
    if _has_ad_language(headline):
        return 0, "clickbait / ad-language markers present"
    if headline.isupper():
        return 0, "headline is ALL CAPS — reads as ad, not editorial"
    if headline.count("!") > 1:
        return 1, "more than one exclamation mark — slightly promotional"
    return 2, "no clickbait / ad-language markers detected"


def score_h6_how_to_verbot(headline: str) -> tuple[int, str]:
    """H6: Does the headline NOT reveal the full solution?
       2 — opens curiosity without revealing
       0 — gives away the method
       1 — ambiguous (mentions direction but doesn't fully reveal)
    """
    if _has_method_reveal(headline):
        return 0, "method-reveal pattern present (e.g. 'Mit X erreichst du Y')"
    if _has_curiosity_opener(headline) or _has_novelty_signal(headline):
        return 2, "opens curiosity without revealing the method"
    return 1, "neither reveals nor opens curiosity — flag for review"


def score_h7_kein_werbegeruch(headline: str) -> tuple[int, str]:
    """H7: Does it sound like content, not advertising?
       2 — no ad-language markers
       0 — ad-language markers present
    """
    if _has_ad_language(headline):
        return 0, "ad-language markers present (Jetzt / Hier / Klicke / Die beste …)"
    return 2, "no ad-language markers"


def score_h8_novelty_signal(headline: str) -> tuple[int, str]:
    """H8: Does it signal something the reader doesn't know yet?
       2 — novelty marker present ('Warum …', 'Der Grund …',
            'Kaum jemand …', 'Die meisten … falsch')
       0 — no novelty marker
    """
    if _has_novelty_signal(headline):
        return 2, "novelty signal present (Warum / Der Grund / Kaum jemand …)"
    return 0, "no novelty signal — no curiosity-trigger phrase"


_H_SCORERS: tuple[tuple[str, callable], ...] = (
    ("H1", score_h1_zielgruppen_filter),
    ("H2", score_h2_konkretheit),
    ("H3", score_h3_problempraezision),
    # H4 takes awareness_level — handled separately below.
    ("H5", score_h5_magazin_wuerdigkeit),
    ("H6", score_h6_how_to_verbot),
    ("H7", score_h7_kein_werbegeruch),
    ("H8", score_h8_novelty_signal),
)


# ─────────────────────────────────────────────────────────────────────────────
# S1 — S5 scoring
# ─────────────────────────────────────────────────────────────────────────────


def score_s1_one_job(subtitle: str) -> tuple[int, str]:
    """S1: Does the subheadline do ONE job (Agitation OR Shiny Object)?
       2 — exactly one of the two cue families fires
       0 — BOTH fire (subtitle tries to do both jobs)
       1 — neither fires (subtitle is neutral — acceptable but weak)
    """
    has_agitation = _any_match(subtitle, _AGITATION_CUES)
    has_shiny = _any_match(subtitle, _SHINY_OBJECT_CUES)
    if has_agitation and has_shiny:
        return 0, "subtitle does BOTH Agitation AND Shiny Object — pick one"
    if has_agitation:
        return 2, "subtitle does Agitation (one clear job)"
    if has_shiny:
        return 2, "subtitle does Shiny Object (one clear job)"
    return 1, "subtitle is neutral — neither Agitation nor Shiny Object cues"


def score_s2_konkretheit(subtitle: str) -> tuple[int, str]:
    """S2: At least one concrete element (number / timeframe / situation)?"""
    if _has_numeric_specificity(subtitle) or _has_situation_verb(subtitle):
        return 2, "concrete element (number, timeframe, or situation verb) present"
    return 0, "subtitle is entirely abstract — no concrete anchor"


def score_s3_kein_buzzword(subtitle: str) -> tuple[int, str]:
    """S3: No buzzwords from Stage 3's denylist."""
    if _contains_buzzword(subtitle):
        return 0, "subtitle contains a buzzword from the §3.9 denylist"
    return 2, "no buzzwords"


def score_s4_neugier_gap(subtitle: str) -> tuple[int, str]:
    """S4: Opens a curiosity gap the report can answer?
       2 — curiosity opener OR novelty signal, no method-reveal
       0 — method-reveal pattern present (no gap left)
       1 — neutral statement (closes nothing, opens nothing)
    """
    if _has_method_reveal(subtitle):
        return 0, "subtitle reveals the method — no curiosity gap left"
    if _has_curiosity_opener(subtitle) or _has_novelty_signal(subtitle):
        return 2, "subtitle opens a curiosity gap"
    return 1, "subtitle neither opens nor closes a gap"


def score_s5_baulig_ton(subtitle: str) -> tuple[int, str]:
    """S5: 'Baulig-Ton' — short impulse sentences, absolute statements,
    NO Konjunktiv.
       2 — no Konjunktiv, ≤25 words
       0 — Konjunktiv present
       1 — long-winding (>40 words) with no Konjunktiv
    """
    if _contains_konjunktiv(subtitle):
        return 0, "subtitle contains Konjunktiv — Richard's style is absolute"
    n = _word_count(subtitle)
    if n > 40:
        return 1, f"subtitle is long ({n} words) — Baulig-Ton prefers shorter"
    return 2, f"no Konjunktiv; {n} words — within Baulig-Ton range"


_S_SCORERS: tuple[tuple[str, callable], ...] = (
    ("S1", score_s1_one_job),
    ("S2", score_s2_konkretheit),
    ("S3", score_s3_kein_buzzword),
    ("S4", score_s4_neugier_gap),
    ("S5", score_s5_baulig_ton),
)


# ─────────────────────────────────────────────────────────────────────────────
# B1 — B5 scoring (operate on the bullets list)
# ─────────────────────────────────────────────────────────────────────────────


def score_b1_neugier_anker(bullets: list[str]) -> tuple[int, str]:
    """B1: Does each bullet trigger a question?
       2 — every bullet opens with a curiosity word
       1 — most do (≥ half)
       0 — few or none
    """
    if not bullets:
        return 0, "no bullets to score"
    n_trigger = sum(1 for b in bullets if _has_curiosity_opener(b))
    ratio = n_trigger / len(bullets)
    if ratio == 1.0:
        return 2, f"all {len(bullets)} bullets open with a curiosity word"
    if ratio >= 0.5:
        return 1, f"{n_trigger}/{len(bullets)} bullets open with a curiosity word"
    return 0, f"only {n_trigger}/{len(bullets)} bullets open with a curiosity word"


def score_b2_how_to_verbot(bullets: list[str]) -> tuple[int, str]:
    """B2: No bullet gives the complete answer.
       2 — no method-reveal in any bullet
       0 — at least one bullet reveals the method
    """
    if not bullets:
        return 0, "no bullets to score"
    revealers = [b for b in bullets if _has_method_reveal(b)]
    if revealers:
        return 0, f"{len(revealers)} bullet(s) reveal the method — keep curiosity"
    return 2, "no bullet reveals the method"


def score_b3_konkretheit(bullets: list[str]) -> tuple[int, str]:
    """B3: No bullet is generic.
    A bullet is GENERIC if it contains a buzzword from the denylist,
    OR matches a vague-promise phrase without numeric proof nearby.
       2 — zero generic bullets
       1 — at most one generic bullet
       0 — multiple generic bullets
    """
    if not bullets:
        return 0, "no bullets to score"
    generic_count = 0
    for b in bullets:
        if _contains_buzzword(b):
            generic_count += 1
            continue
        # Vague-promise heuristic (subset of Stage 3 check)
        if re.search(
            r"\b(?:bessere ergebnisse|mehr erfolg|mehr umsatz|optimale lösung)\b",
            b, re.IGNORECASE,
        ):
            generic_count += 1
    if generic_count == 0:
        return 2, "no generic bullets detected"
    if generic_count == 1:
        return 1, "one generic bullet — consider rewriting"
    return 0, f"{generic_count} generic bullets — rewrite with specifics"


def score_b4_einzelwirkung(bullets: list[str]) -> tuple[int, str]:
    """B4: Each bullet stands alone (no inter-bullet linking words).
    Heuristic: penalise bullets that open with linking words like
    'Anschließend', 'Danach', 'Und dann', 'Schließlich'.
       2 — no linking-word openers
       0 — any linking-word opener present
    """
    if not bullets:
        return 0, "no bullets to score"
    linkers = ("und dann", "danach", "anschließend", "schließlich",
               "darüber hinaus", "außerdem")
    for b in bullets:
        low = b.strip().lower()
        if any(low.startswith(linker) for linker in linkers):
            return 0, f"bullet opens with a linking word — not standalone: {b!r}"
    return 2, "every bullet stands alone (no linking-word openers)"


def score_b5_reihenfolge(bullets: list[str]) -> tuple[int, str]:
    """B5: Strongest bullet at position 1 or last (not middle).

    "Strongest" = highest _bullet_strength score. Limitation: when
    multiple bullets tie for strongest, we award credit if ANY of the
    tied bullets is at the endpoints.
    """
    if not bullets or len(bullets) < 2:
        return 1, "fewer than 2 bullets — order can't be evaluated"
    strengths = [_bullet_strength(b) for b in bullets]
    max_strength = max(strengths)
    strongest_positions = [i for i, s in enumerate(strengths) if s == max_strength]
    endpoint_positions = {0, len(bullets) - 1}
    if any(p in endpoint_positions for p in strongest_positions):
        return 2, "strongest bullet is at position 1 or last"
    return 0, "strongest bullet sits in the middle — move to position 1 or last"


_B_SCORERS: tuple[tuple[str, callable], ...] = (
    ("B1", score_b1_neugier_anker),
    ("B2", score_b2_how_to_verbot),
    ("B3", score_b3_konkretheit),
    ("B4", score_b4_einzelwirkung),
    ("B5", score_b5_reihenfolge),
)


# ─────────────────────────────────────────────────────────────────────────────
# Disqualifications
# ─────────────────────────────────────────────────────────────────────────────


def check_disqualifications(headline: str, subtitle: str = "") -> list[str]:
    """Instant flags. Each entry is a stable code; the human-readable
    explanation lives in the CoverValidation.warnings list.
    """
    flags: list[str] = []
    if _DISQ_PRICE_RE.search(headline):
        flags.append("price_in_headline")
    if _DISQ_ENDLICH_RE.search(headline):
        flags.append("endlich_opener")
    if _any_match(headline, _DISQ_AUDIENCE_BROAD_PATTERNS):
        flags.append("audience_too_broad")
    if _contains_buzzword(headline):
        flags.append("generic_buzzwords_in_headline")
    return flags


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────


def validate_cover(
    cover_page_data: dict, awareness_level: int = 2
) -> CoverValidation:
    """Score a cover page's 5-element stack.

    Expected `cover_page_data` keys:
      - eyebrow         (optional string)
      - title           (the headline — required for meaningful scores)
      - subtitle        (the subheadline — required for S-scoring)
      - teaser_bullets  (list[str], 3-4 expected)
      - proof_anchor    (optional string)

    `awareness_level` selects which subtypes H4 marks as recommended /
    warned-against. Default 2 (most common for unknown brands).
    """
    headline = (cover_page_data.get("title") or "").strip()
    subtitle = (cover_page_data.get("subtitle") or "").strip()
    bullets = cover_page_data.get("teaser_bullets") or []
    bullets = [b for b in bullets if isinstance(b, str) and b.strip()]

    warnings: list[str] = []

    # Stack completeness checks (warnings, not score-affecting)
    if not headline:
        warnings.append("headline missing from cover stack")
    if not subtitle:
        warnings.append("subheadline missing from cover stack")
    if len(bullets) < 3:
        warnings.append(f"fewer than 3 bullets (got {len(bullets)})")

    # Headline type + size class
    headline_type = _detect_headline_type(headline)
    headline_size_class = resolve_headline_size_class(headline)

    # Typ-A-for-unknown-brand warning
    if headline_type.startswith("Typ A") and awareness_level <= 3:
        warnings.append(
            "Typ A (Etikett) detected — verify brand is known; "
            "unknown brands should use Typ B (Diagnose)"
        )

    # H-matrix
    h_details: list[ScoreDetail] = []
    h_score = 0
    for code, scorer in _H_SCORERS:
        score, reason = scorer(headline)
        h_details.append(ScoreDetail(criterion=code, score=score, reason=reason))
        h_score += score
    # H4 takes awareness_level
    h4_score, h4_reason = score_h4_bewusstseinslevel_fit(headline, awareness_level)
    h_details.insert(3, ScoreDetail(criterion="H4", score=h4_score, reason=h4_reason))
    h_score += h4_score

    # S-matrix (only meaningful when subtitle is non-empty)
    s_details: list[ScoreDetail] = []
    s_score = 0
    for code, scorer in _S_SCORERS:
        score, reason = scorer(subtitle)
        s_details.append(ScoreDetail(criterion=code, score=score, reason=reason))
        s_score += score

    # B-matrix
    b_details: list[ScoreDetail] = []
    b_score = 0
    for code, scorer in _B_SCORERS:
        score, reason = scorer(bullets)
        b_details.append(ScoreDetail(criterion=code, score=score, reason=reason))
        b_score += score

    # Disqualifications
    disqualifications = check_disqualifications(headline, subtitle)

    # Overall verdict
    overall = _resolve_overall(h_score, s_score, b_score, disqualifications)

    return CoverValidation(
        headline_type=headline_type,
        headline_size_class=headline_size_class,
        awareness_level=awareness_level,
        h_score=h_score,
        h_scores_detail=h_details,
        s_score=s_score,
        s_scores_detail=s_details,
        b_score=b_score,
        b_scores_detail=b_details,
        disqualifications=disqualifications,
        warnings=warnings,
        overall=overall,
    )


def _resolve_overall(
    h_score: int, s_score: int, b_score: int, disqs: list[str]
) -> str:
    """Map the three scores + disqualifications to one of three buckets.

    Thresholds from Richard's doc:
      H: ≥15 use / 13-14 sharpen / 11-12 flag-weakest / 9-10 type-change /
         <9 inputs-incomplete
      S: ≥9 use / 7-8 sharpen / <7 rewrite
      B: ≥9 use / 7-8 sharpen / <7 rewrite

    pass            — H≥13 AND S≥9 AND B≥9 AND no disqualifications
    pass_with_warnings — H≥11 AND S≥7 AND B≥7 AND no disqualifications
    needs_review    — any disqualification OR (H<11 OR S<7 OR B<7)
    """
    if disqs:
        return "needs_review"
    if h_score < 11 or s_score < 7 or b_score < 7:
        return "needs_review"
    if h_score >= 13 and s_score >= 9 and b_score >= 9:
        return "pass"
    return "pass_with_warnings"
