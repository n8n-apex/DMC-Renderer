"""Tests for Stage 4 — validate_cover (Richard's 11_Cover_Headlines doc).

The 12 spec test cases plus a few targeted edge cases that exercise
particular scoring functions.
"""

from __future__ import annotations

import pytest

from stages.validate_cover import (
    check_disqualifications,
    resolve_headline_size_class,
    score_b1_neugier_anker,
    score_b3_konkretheit,
    score_h2_konkretheit,
    score_h7_kein_werbegeruch,
    score_s1_one_job,
    validate_cover,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _baulig_strong_cover() -> dict:
    """A strong Typ-B Diagnose cover that should score near the top of all
    three matrices. Reference case from Richard's doc.
    """
    return {
        "eyebrow": "BERATUNGSREPORT 2026",
        "title": (
            "Warum 73% der Berater nach 18 Monaten stecken bleiben — "
            "und der eine Hebel den Top-Performer kennen"
        ),
        "subtitle": (
            "Die meisten Berater kämpfen seit Jahren mit dem gleichen Plateau. "
            "Dieser Report zeigt warum — und welche eine Änderung den Durchbruch bringt."
        ),
        "teaser_bullets": [
            "Warum 9 von 10 Beratern den falschen Engpass diagnostizieren",
            "Der unsichtbare Hebel den 73% übersehen",
            "Die eine Änderung die alles verändert",
            "Was Top-Performer anders machen (und warum es funktioniert)",
        ],
        "proof_anchor": "BAULIG CONSULTING — 12 Jahre, 4.000+ Berater betreut",
    }


def _weak_etikett_cover() -> dict:
    """A short, vague Etikett cover that should fall into needs_review."""
    return {
        "title": "Innovative Lösungen für mehr Erfolg",
        "subtitle": "Wir helfen Ihnen erfolgreich zu sein.",
        "teaser_bullets": [
            "Bessere Ergebnisse",
            "Mehr Erfolg",
            "Optimale Lösung",
        ],
    }


# ─────────────────────────────────────────────────────────────────────────────
# The 12 spec test cases
# ─────────────────────────────────────────────────────────────────────────────


def test_1_baulig_strong_headline_passes_with_high_score() -> None:
    """Reference Diagnose-style headline scores high across H matrix
    and the overall verdict is at minimum pass_with_warnings.
    """
    result = validate_cover(_baulig_strong_cover(), awareness_level=2)
    assert result.h_score >= 13, (
        f"strong Diagnose headline should H≥13; got {result.h_score} "
        f"(detail: {[(d.criterion, d.score) for d in result.h_scores_detail]})"
    )
    assert result.headline_type == "Typ B — Diagnose"
    assert result.headline_size_class == "long"
    assert result.overall in {"pass", "pass_with_warnings"}, (
        f"strong headline should pass; got overall={result.overall}, "
        f"warnings={result.warnings}, disqs={result.disqualifications}"
    )


def test_2_weak_etikett_needs_review() -> None:
    """A vague Typ-A headline with no audience and no specifics lands in
    needs_review and a Typ-A-warning fires (unknown brand assumption).
    """
    result = validate_cover(_weak_etikett_cover(), awareness_level=2)
    assert result.headline_type == "Typ A — Etikett"
    assert result.headline_size_class == "short"
    assert result.overall == "needs_review"
    # Typ A on awareness ≤3 always emits the unknown-brand warning.
    assert any("Typ A" in w for w in result.warnings), (
        f"expected Typ-A warning; got {result.warnings}"
    )


def test_3_price_in_headline_disqualified() -> None:
    """A headline that names a price triggers price_in_headline."""
    data = {
        "title": "Erreichen Sie mehr Umsatz für nur 99€ im Monat",
        "subtitle": "Die meisten Berater kennen diesen Hebel nicht.",
        "teaser_bullets": ["Warum?", "Wieso?", "Was kostet es?"],
    }
    result = validate_cover(data, awareness_level=2)
    assert "price_in_headline" in result.disqualifications
    assert result.overall == "needs_review"


def test_4_endlich_opener_disqualified() -> None:
    """A headline opening with `Endlich` triggers endlich_opener."""
    data = {
        "title": "Endlich messbare Ergebnisse für deine Agentur",
        "subtitle": "Was die meisten Agenturen übersehen.",
        "teaser_bullets": ["Warum?", "Wieso?", "Was?"],
    }
    result = validate_cover(data, awareness_level=2)
    assert "endlich_opener" in result.disqualifications
    assert result.overall == "needs_review"


def test_5_strong_subheadline_scores_high() -> None:
    """A subheadline that names the pain (Agitation, with a number)
    scores at the top of S.
    """
    data = {
        "title": "Warum 73% der Agenturen ihr Wachstum verlieren",
        "subtitle": (
            "9 von 10 Agenturen verlieren in 18 Monaten den Anschluss. "
            "Dieser Report zeigt warum."
        ),
        "teaser_bullets": [
            "Warum übersehen 73% den Engpass?",
            "Der Fehler den niemand sieht",
            "Was Top-Performer anders machen",
        ],
    }
    result = validate_cover(data, awareness_level=2)
    assert result.s_score >= 8, (
        f"strong subheadline should S≥8; got {result.s_score} "
        f"(detail: {[(d.criterion, d.score) for d in result.s_scores_detail]})"
    )


def test_6_subheadline_doing_both_jobs_flagged_by_s1() -> None:
    """A subheadline that does BOTH Agitation and Shiny Object scores
    0 on S1.
    """
    subtitle = (
        "Du verlierst seit Jahren Umsatz — und kannst es endlich ändern, "
        "wenn du die richtige Methode kennst."
    )
    score, reason = score_s1_one_job(subtitle)
    assert score == 0, (
        f"S1 should flag dual-purpose subtitle; got {score} ({reason})"
    )


def test_7_strong_bullets_score_high() -> None:
    """All-curiosity bullets with numeric specificity score B≥9."""
    bullets = [
        "Warum 73% der Berater den falschen Hebel ziehen",
        "Wie 3 Wochen alles verändern können",
        "Was die Top 10% anders machen",
        "Der eine Grund warum 9 von 10 scheitern",
    ]
    data = {
        "title": "Warum 73% der Berater nach 18 Monaten stecken bleiben",
        "subtitle": "Was die Top-Performer anders machen.",
        "teaser_bullets": bullets,
    }
    result = validate_cover(data, awareness_level=2)
    assert result.b_score >= 9, (
        f"strong bullets should B≥9; got {result.b_score} "
        f"(detail: {[(d.criterion, d.score) for d in result.b_scores_detail]})"
    )


def test_8_weak_bullets_score_low() -> None:
    """Generic bullets with buzzwords land in 0 on B1 and B3."""
    bullets = [
        "Mehr Erfolg",
        "Bessere Ergebnisse",
        "Innovative Methoden für nachhaltigen Erfolg",
    ]
    b1_score, _ = score_b1_neugier_anker(bullets)
    b3_score, _ = score_b3_konkretheit(bullets)
    assert b1_score == 0, f"weak bullets should B1=0; got {b1_score}"
    assert b3_score == 0, f"weak bullets should B3=0; got {b3_score}"


def test_9_awareness_mismatch_drops_h4() -> None:
    """A 'Selbsttest' subtype headline shown to an awareness-level-5
    reader is in the warned-against list → H4=0.
    """
    data = {
        # "Bist du" + "test" → Selbsttest subtype
        "title": "Bist du der eine Berater der diesen Test besteht?",
        "subtitle": "Die Wahrheit über deine Positionierung.",
        "teaser_bullets": ["Warum?", "Wieso?", "Was?"],
    }
    # Run at awareness 5 — Selbsttest is warned-against there
    result = validate_cover(data, awareness_level=5)
    h4 = next(d for d in result.h_scores_detail if d.criterion == "H4")
    assert h4.score == 0, (
        f"Selbsttest at awareness 5 should H4=0; got {h4.score} "
        f"(reason: {h4.reason})"
    )

    # Compare to awareness 1 where Selbsttest IS recommended → H4=2
    result_low = validate_cover(data, awareness_level=1)
    h4_low = next(d for d in result_low.h_scores_detail if d.criterion == "H4")
    assert h4_low.score == 2, (
        f"Selbsttest at awareness 1 should H4=2; got {h4_low.score} "
        f"(reason: {h4_low.reason})"
    )


def test_10_complete_cover_stack_returns_three_matrices_and_verdict() -> None:
    """Sanity: a complete cover stack produces all three matrices, the
    five required top-level fields, and one overall verdict.
    """
    result = validate_cover(_baulig_strong_cover(), awareness_level=2)
    # H has 8 criteria
    assert {d.criterion for d in result.h_scores_detail} == {
        "H1", "H2", "H3", "H4", "H5", "H6", "H7", "H8",
    }
    # S has 5
    assert {d.criterion for d in result.s_scores_detail} == {
        "S1", "S2", "S3", "S4", "S5",
    }
    # B has 5
    assert {d.criterion for d in result.b_scores_detail} == {
        "B1", "B2", "B3", "B4", "B5",
    }
    assert 0 <= result.h_score <= 16
    assert 0 <= result.s_score <= 10
    assert 0 <= result.b_score <= 10
    assert result.overall in {"pass", "pass_with_warnings", "needs_review"}


def test_11_missing_subheadline_warning() -> None:
    """No subtitle key → a stack-completeness warning fires."""
    data = {
        "title": "Warum 73% der Berater nach 18 Monaten stecken bleiben",
        "teaser_bullets": [
            "Warum übersehen 73%?",
            "Der Hebel den niemand sieht",
            "Was Top-Performer anders machen",
        ],
    }
    result = validate_cover(data, awareness_level=2)
    assert any("subheadline missing" in w for w in result.warnings), (
        f"expected subheadline-missing warning; got {result.warnings}"
    )


def test_12_only_two_bullets_warning() -> None:
    """Stack with only 2 bullets emits 'fewer than 3 bullets' warning."""
    data = {
        "title": "Warum 73% der Berater stecken bleiben",
        "subtitle": "Was Top-Performer anders machen.",
        "teaser_bullets": [
            "Warum übersehen 73%?",
            "Der Hebel den niemand sieht",
        ],
    }
    result = validate_cover(data, awareness_level=2)
    assert any("fewer than 3 bullets" in w for w in result.warnings), (
        f"expected fewer-than-3-bullets warning; got {result.warnings}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Targeted scorer tests (beyond the 12 spec cases)
# ─────────────────────────────────────────────────────────────────────────────


def test_h2_numeric_detection() -> None:
    """H2: numbers get 2, abstract headlines get 0."""
    assert score_h2_konkretheit("80% mehr Umsatz in 3 Wochen")[0] == 2
    assert score_h2_konkretheit("Mehr Umsatz durch bessere Methoden")[0] == 0


def test_h7_ad_language_zeroes() -> None:
    """H7: ad-language ('Jetzt sichere dir', '!!') scores 0."""
    assert score_h7_kein_werbegeruch("Jetzt sichere dir den Erfolg!!!")[0] == 0
    assert score_h7_kein_werbegeruch("Warum 73% scheitern")[0] == 2


def test_size_class_short_vs_long() -> None:
    """Renderer-sizing helper: ≤8 words → short, ≥9 → long."""
    assert resolve_headline_size_class("Warum Berater scheitern") == "short"  # 3 words
    assert resolve_headline_size_class(
        "Warum 73% der Berater nach 18 Monaten stecken bleiben und niemand spricht"
    ) == "long"  # >8 words


def test_disqualification_buzzword_in_headline() -> None:
    """A headline that uses an §3.9 buzzword fires generic_buzzwords_in_headline."""
    flags = check_disqualifications(
        "Innovative Lösungen für deine Agentur", subtitle=""
    )
    assert "generic_buzzwords_in_headline" in flags


def test_audience_too_broad_disqualified() -> None:
    """'für alle Unternehmer' fires audience_too_broad."""
    flags = check_disqualifications(
        "Der ultimative Hebel für alle Unternehmer", subtitle=""
    )
    assert "audience_too_broad" in flags


def test_empty_cover_no_crash() -> None:
    """Empty cover data must not raise; produces full warnings."""
    result = validate_cover({}, awareness_level=2)
    assert "headline missing from cover stack" in result.warnings
    assert "subheadline missing from cover stack" in result.warnings
    assert any("fewer than 3 bullets" in w for w in result.warnings)
