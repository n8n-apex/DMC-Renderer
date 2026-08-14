"""Figures must be read out of real German prose, with exact spans."""

from __future__ import annotations

import json
from pathlib import Path

from stages.extract_figures_v3 import extract_figures, infer_device_intents


ROOT = Path(__file__).resolve().parents[3]
REAL_PAYLOAD = ROOT / "dmc-renderer" / "fixtures" / "apex_consulting_payload.json"


def test_every_figure_carries_its_exact_source_span() -> None:
    text = "Die Bearbeitung dauerte 42 Stunden pro Woche und kostet 13.160 € im Monat."

    figures = extract_figures(text)

    assert [figure.verbatim for figure in figures] == [
        "42 Stunden",
        "13.160 €",
    ]
    for figure in figures:
        assert text[figure.start : figure.end] == figure.verbatim
    assert figures[0].measure == "hour"
    assert figures[1].measure == "eur"


def test_bare_years_are_dates_not_measured_quantities() -> None:
    assert extract_figures("Seit 2019 arbeiten wir daran.") == ()


def test_transition_phrasing_earns_a_before_after_device() -> None:
    text = "Die Bearbeitung sank von 42 auf 6 Stunden pro Woche."

    intents = infer_device_intents(text)

    transitions = [item for item in intents if item.kind == "before_after"]
    assert len(transitions) == 1
    before, after = transitions[0].figures
    assert before.verbatim.startswith("42")
    assert after.verbatim.startswith("6")


def test_share_phrasing_earns_a_share_device() -> None:
    intents = infer_device_intents("70 % der Anfragen laufen unverändert weiter.")

    shares = [item for item in intents if item.kind == "share"]
    assert len(shares) == 1
    assert shares[0].figures[0].verbatim.startswith("70")
    assert "Anfragen" in shares[0].label


def test_three_year_tagged_figures_earn_a_series() -> None:
    text = (
        "2023 waren es 310 Angebote. 2024 stiegen sie auf 540 Angebote. "
        "2025 lagen sie bei 780 Angebote."
    )

    series = [item for item in infer_device_intents(text) if item.kind == "time_series"]

    assert len(series) == 1
    assert len(series[0].figures) >= 3


def test_the_real_client_payload_yields_devices_from_its_prose() -> None:
    """The report that produced only text must now produce device intents."""
    payload = json.loads(REAL_PAYLOAD.read_text(encoding="utf-8"))
    found = {"before_after": 0, "share": 0, "time_series": 0}
    total_figures = 0
    for page in payload["payload"]["pages"]:
        for value in page.get("data", {}).values():
            if not isinstance(value, str):
                continue
            total_figures += len(extract_figures(value))
            for intent in infer_device_intents(value):
                found[intent.kind] += 1

    assert total_figures > 20, total_figures
    assert sum(found.values()) > 0, found


def test_a_verb_after_a_number_is_not_its_unit() -> None:
    text = "Onboarding-Prozesse von 30 Minuten auf 2 verkürzt."

    after = infer_device_intents(text)[0].figures[1]

    assert after.verbatim == "2"
    # The sentence states the unit once; both ends of the transition are
    # minutes, which is what a two-bar comparison has to plot.
    assert after.measure == "minute"


def test_a_share_keeps_the_words_the_prose_actually_used() -> None:
    written = infer_device_intents("30 Prozent der Betriebskosten entfallen.")[0]
    signed = infer_device_intents("30 % der Betriebskosten entfallen.")[0]

    assert written.figures[0].verbatim == "30 Prozent"
    assert signed.figures[0].verbatim == "30 %"


def test_a_share_label_is_a_noun_phrase_not_half_a_sentence() -> None:
    intent = infer_device_intents(
        "50 % der Betriebskosten eliminieren und dein Unternehmen skalieren."
    )[0]

    assert intent.label == "Betriebskosten"


def test_every_device_figure_matches_its_own_source_span() -> None:
    text = (
        "Die Bearbeitung sank von 42 Stunden auf 6 Stunden, "
        "und 70 % der Anfragen laufen weiter."
    )

    for intent in infer_device_intents(text):
        for figure in intent.figures:
            assert text[figure.start : figure.end] == figure.verbatim


def test_a_transition_is_labelled_with_what_changed() -> None:
    cases = {
        "Nach der Implementierung sank die Onboarding-Zeit von 30 Minuten auf 2 Minuten.":
            "Onboarding-Zeit",
        "Fokus Marketing verkürzte das Kunden-Onboarding von 30 Minuten auf 2.":
            "Kunden-Onboarding",
        "Wir haben Onboarding-Prozesse von 30 Minuten auf 2 verkürzt.":
            "Onboarding-Prozesse",
    }
    for text, expected in cases.items():
        intent = next(i for i in infer_device_intents(text) if i.kind == "before_after")
        assert intent.label == expected, text


def test_a_transition_label_never_reaches_into_the_previous_sentence() -> None:
    text = (
        "Die Conesso GmbH beseitigte den Founder-Burnout. "
        "Danach sank die Bearbeitung von 42 auf 6."
    )

    intent = next(i for i in infer_device_intents(text) if i.kind == "before_after")

    assert "Conesso" not in intent.label
