"""Read figures out of German prose and infer what device they earn.

The writer's structured visual keys (kennzahlen, vorher_nachher, verlauf)
only exist under prompt v5, which is not live. Every real report today
carries its numbers inside sentences: "von 42 auf 6 Stunden", "70 % der
Anfragen", "2023 waren es 310, 2024 dann 540". Without reading those, the
system has nothing to draw and every page renders as prose.

This stage extracts each figure with its exact character span, classifies
its measure, and infers the relationships that earn a device:

    von X auf Y            -> before/after transition
    three+ figures tied to
    distinct years         -> time series
    N % of something        -> share

Nothing is invented: a figure is only reported with the exact substring it
came from, so every downstream claim can carry a real source span, and a
relationship is only reported when its linguistic marker is present.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


# The grouped form must actually carry a thousands group, or `\d{1,3}`
# wins the alternation and reads "2019" as the figure "201".
_NUMBER = r"\d{1,3}(?:[.\s]\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?"

_UNIT_WORDS = (
    ("stunden", "hour"), ("stunde", "hour"),
    ("minuten", "minute"), ("minute", "minute"),
    ("tage", "day"), ("tagen", "day"), ("tag", "day"),
    ("wochen", "week"), ("woche", "week"),
    ("monate", "month"), ("monaten", "month"), ("monat", "month"),
    ("jahre", "year"), ("jahren", "year"),
    ("kunden", "customer"), ("kunde", "customer"),
    ("mitarbeiter", "person"), ("personen", "person"),
    ("projekte", "project"), ("projekten", "project"),
    ("anfragen", "request"), ("angebote", "offer"),
    ("prozent", "percent"), ("%", "percent"),
    ("€", "eur"), ("eur", "eur"),
)

_YEAR = re.compile(r"\b(19[89]\d|20[0-4]\d)\b")
_TRANSITION = re.compile(
    rf"von\s+(?P<before>{_NUMBER})\s*(?P<bunit>[%€]|[A-Za-zÄÖÜäöüß]+)?\s+auf\s+"
    rf"(?P<after>{_NUMBER})\s*(?P<aunit>[%€]|[A-Za-zÄÖÜäöüß]+)?",
    re.IGNORECASE,
)
_SHARE = re.compile(
    # The label is the noun the share is OF: one German noun plus an
    # optional second capitalised noun, never the rest of the sentence.
    rf"(?P<value>{_NUMBER})\s*(?P<punit>%|Prozent)\s+(?:der|des|aller|von)\s+"
    r"(?P<subject>[A-Za-zÄÖÜäöüß][\wÄÖÜäöüß-]{2,30}"
    r"(?:\s+[A-ZÄÖÜ][\wÄÖÜäöüß-]{2,30})?)",
)
_FIGURE = re.compile(rf"(?<![\w.,])(?P<value>{_NUMBER})(?!\d)\s*(?P<unit>%|€|[A-Za-zÄÖÜäöüß]+)?")

MeasureKind = Literal["hour", "minute", "day", "week", "month", "year",
                      "customer", "person", "project", "request", "offer",
                      "percent", "eur", "count"]


class Figure(BaseModel):
    """One number found in prose, with the exact text it came from."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    verbatim: str = Field(min_length=1)
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    measure: MeasureKind
    context: str = Field(min_length=1)


class DeviceIntent(BaseModel):
    """A relationship in the prose that earns one visual device."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["before_after", "time_series", "share"]
    figures: tuple[Figure, ...] = Field(min_length=1)
    label: str = Field(min_length=1)
    # For a series, the year each figure was stated under, in figure order.
    time_scopes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_time_scopes(self) -> "DeviceIntent":
        if self.time_scopes and len(self.time_scopes) != len(self.figures):
            raise ValueError("a time scope per figure or none at all")
        return self


def _unit_kind(unit: str | None) -> MeasureKind | None:
    """The measure a unit word names, or None when it is not a unit at all.

    German puts a verb straight after the number ("auf 2 verkuerzt"), so a
    word is only a unit when it names a measure we recognise. Anything else
    is prose and must stay out of the figure.
    """
    if not unit:
        return None
    lowered = unit.strip().lower()
    for token, kind in _UNIT_WORDS:
        if lowered == token or lowered.startswith(token):
            return kind  # type: ignore[return-value]
    return None


def _measure(unit: str | None, value: str) -> MeasureKind:
    return _unit_kind(unit) or "count"


_SENTENCE_END = re.compile(r"[.!?]")
_NOUN = re.compile(r"[A-ZÄÖÜ][\wÄÖÜäöüß]*(?:-[A-ZÄÖÜa-zäöüß][\wÄÖÜäöüß]*)*")


def _transition_label(text: str, transition_start: int) -> str:
    """Name what changed: the last German noun before the "von X auf Y".

    German capitalises its nouns, so the subject of a transition is the
    nearest capitalised word ahead of the marker, inside the same sentence.
    """
    boundaries = [
        match.end()
        for match in _SENTENCE_END.finditer(text)
        if match.end() <= transition_start
    ]
    sentence_start = boundaries[-1] if boundaries else 0
    clause = text[sentence_start:transition_start]
    nouns = [
        match.group(0)
        for match in _NOUN.finditer(clause)
        # A capitalised word that only opens the sentence is not the subject.
        if match.start() > 0
    ]
    if nouns:
        return nouns[-1]
    return clause.strip() or text[transition_start:].strip()[:60]


def _context(text: str, start: int, end: int, width: int = 60) -> str:
    left = max(0, start - width)
    right = min(len(text), end + width)
    return text[left:right].strip()


def _figure_from_match(
    text: str,
    match: re.Match[str],
    value_group: str,
    unit_group: str | None,
) -> Figure:
    """Cut the figure out of the source text using the match's own spans.

    Reconstructing "{value} {unit}" and searching for it loses the exact
    characters the writer used ("30 Prozent" becomes "30 %"), which breaks
    the span every downstream claim depends on.
    """
    start = match.start(value_group)
    end = match.end(value_group)
    kind: MeasureKind = "count"
    if unit_group is not None and match.group(unit_group) is not None:
        unit_kind = _unit_kind(match.group(unit_group))
        if unit_kind is not None:
            kind = unit_kind
            end = match.end(unit_group)
    return Figure(
        verbatim=text[start:end],
        start=start,
        end=end,
        measure=kind,
        context=_context(text, start, end),
    )


def extract_figures(text: str) -> tuple[Figure, ...]:
    """Every number in the prose, with its span and measure."""
    figures: list[Figure] = []
    for match in _FIGURE.finditer(text):
        # A year followed by an ordinary word is a date, not a quantity:
        # "2019 arbeiten" is time, "2019 Kunden" is a count.
        if _YEAR.fullmatch(match.group("value")) and _unit_kind(match.group("unit")) is None:
            continue
        figures.append(_figure_from_match(text, match, "value", "unit"))
    return tuple(figures)


def infer_device_intents(text: str) -> tuple[DeviceIntent, ...]:
    """Relationships the prose actually states, never inferred decoration."""
    intents: list[DeviceIntent] = []

    for match in _TRANSITION.finditer(text):
        before = _figure_from_match(text, match, "before", "bunit")
        after = _figure_from_match(text, match, "after", "aunit")
        # "von 30 Minuten auf 2" states one measure; the second figure
        # inherits it rather than being demoted to a bare count.
        if after.measure == "count" and before.measure != "count":
            after = after.model_copy(update={"measure": before.measure})
        elif before.measure == "count" and after.measure != "count":
            before = before.model_copy(update={"measure": after.measure})
        intents.append(
            DeviceIntent(
                kind="before_after",
                figures=(before, after),
                label=_transition_label(text, match.start()),
            )
        )

    for match in _SHARE.finditer(text):
        share = _figure_from_match(text, match, "value", "punit")
        intents.append(
            DeviceIntent(
                kind="share",
                figures=(share,),
                label=match.group("subject").strip(),
            )
        )

    # A series needs three or more figures of one measure, each tied to a
    # distinct year in its own context.
    by_measure: dict[str, list[Figure]] = {}
    for figure in extract_figures(text):
        # The year that tags a figure is the nearest one before it, not any
        # year inside a wide context window.
        preceding = [
            match for match in _YEAR.finditer(text) if match.end() <= figure.start
        ]
        if not preceding:
            continue
        nearest = preceding[-1]
        if figure.start - nearest.end() > 40:
            continue
        by_measure.setdefault(
            f"{figure.measure}|{nearest.group(0)}", []
        ).append(figure)
    year_groups: dict[str, list[tuple[str, Figure]]] = {}
    for key, figures in by_measure.items():
        measure, _, year = key.partition("|")
        year_groups.setdefault(measure, []).append((year, figures[0]))
    for measure, tagged in year_groups.items():
        if len(tagged) >= 3:
            ordered = tuple(sorted(tagged, key=lambda item: item[1].start))
            figures = tuple(figure for _, figure in ordered)
            intents.append(
                DeviceIntent(
                    kind="time_series",
                    figures=figures,
                    label=_transition_label(text, figures[0].start),
                    time_scopes=tuple(year for year, _ in ordered),
                )
            )
    return tuple(intents)
