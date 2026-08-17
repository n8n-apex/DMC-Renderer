"""Derive the evidence a real report already contains from its own copy.

A live writer payload arrives as prose. It carries no claims array, so every
numeral in it is reported as an ungrounded candidate and precomposition
refuses the report. That is the correct refusal for a report with no
evidence, but it is the wrong reading of this input: the figures ARE there,
inside the sentences, in copy the client approved.

This stage reads that copy and states exactly what it can prove:

    every numeral becomes a claim whose source span is the approved copy,
    byte-exact, so the rendered figure provably matches the written one

That is copy grounding, not external verification. It proves the report
prints what the client approved; it does not prove the client is right.
Claims made here carry ``copy_derived`` in ``allowed_uses`` so no downstream
stage can mistake them for externally sourced evidence.

On top of the claims it reports the relationships the prose actually states
(a transition, a share, a series), which is what earns a page a device
instead of another paragraph.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from stages.build_source_ledger import (
    NUMBER_TOKEN_RE,
    normalize_number_token,
    page_strings,
)
from stages.extract_figures_v3 import Figure, extract_figures, infer_device_intents


COPY_DERIVED_USE = "copy_derived"
_UNIT_BY_MEASURE = {
    "percent": "percent",
    "eur": "EUR",
    "hour": "hour",
    "minute": "minute",
    "day": "day",
    "week": "week",
    "month": "month",
    "year": "year",
}
_PATH_SAFE = re.compile(r"[^a-z0-9]+")


class DerivedDevice(BaseModel):
    """One device the prose earned, bound to the claims it plots."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["before_after", "time_series", "share"]
    content_path: str = Field(min_length=1)
    claim_ids: tuple[str, ...] = Field(min_length=1)
    label: str = Field(min_length=1)


class DerivedEvidence(BaseModel):
    """Source items, claims and devices read out of one report's copy."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sources: tuple[dict[str, Any], ...] = ()
    claims: tuple[dict[str, Any], ...] = ()
    devices: tuple[DerivedDevice, ...] = ()


def _source_id(content_path: str) -> str:
    slug = _PATH_SAFE.sub(".", content_path.lower()).strip(".")
    return f"src.copy.{slug}"


def _claim_id(source_id: str, start: int, verbatim: str) -> str:
    digest = hashlib.sha256(f"{source_id}|{start}|{verbatim}".encode("utf-8"))
    return f"claim.copy.{digest.hexdigest()[:16]}"


def _unit_for(figure: Figure, token_unit: str | None) -> str | None:
    # The tokenizer's own reading wins when it found one, so a derived claim
    # matches the gate's coverage key exactly.
    return token_unit or _UNIT_BY_MEASURE.get(figure.measure)


def _figure_covering(figures: tuple[Figure, ...], start: int, end: int) -> Figure | None:
    return next(
        (figure for figure in figures if figure.start <= start and figure.end >= end),
        None,
    )


def derive_evidence(
    report_bundle: dict[str, Any],
    *,
    captured_at: datetime,
    language: str = "de",
    rights_status: str = "client_approved_copy",
) -> DerivedEvidence:
    """Read claims and device intents out of an already written report."""

    sources: list[dict[str, Any]] = []
    claims: list[dict[str, Any]] = []
    claims_by_id: dict[str, dict[str, Any]] = {}
    devices: list[DerivedDevice] = []
    claim_id_by_span: dict[tuple[str, int, int], str] = {}

    for content_path, text in page_strings(report_bundle):
        if not NUMBER_TOKEN_RE.search(text):
            continue
        source_id = _source_id(content_path)
        sources.append(
            {
                "source_id": source_id,
                "source_kind": "client_upload",
                "locator": content_path,
                "captured_at": captured_at,
                "rights_status": rights_status,
                "verbatim_text": text,
                "language": language,
                "allowed_uses": (COPY_DERIVED_USE,),
            }
        )
        figures = extract_figures(text)
        for match in NUMBER_TOKEN_RE.finditer(text):
            token = match.group(0).strip()
            value, token_unit = normalize_number_token(token)
            start = match.start()
            end = start + len(token)
            figure = _figure_covering(figures, start, end)
            claim_id = _claim_id(source_id, start, token)
            claim_id_by_span[(content_path, start, end)] = claim_id
            claim = {
                "claim_id": claim_id,
                "claim_type": "number",
                "normalized_value": value,
                "unit": _unit_for(figure, token_unit) if figure else token_unit,
                "source_ids": (source_id,),
                "source_spans": (
                    {
                        "source_id": source_id,
                        "start": start,
                        "end": end,
                        "verbatim": text[start:end],
                    },
                ),
                "allowed_uses": (COPY_DERIVED_USE,),
            }
            claims.append(claim)
            claims_by_id[claim_id] = claim

        for intent in infer_device_intents(text):
            bound = tuple(
                claim_id
                for claim_id in (
                    _claim_for_figure(claim_id_by_span, content_path, figure)
                    for figure in intent.figures
                )
                if claim_id is not None
            )
            # A device may only plot figures that became claims; a partially
            # bound device would draw a number nothing grounds.
            if len(bound) != len(intent.figures) or len(set(bound)) != len(bound):
                continue
            # The relationship is recorded on the claims themselves, as scope,
            # never as an invented delta or remainder claim. Selection reads
            # claim shape, so a derived report and a written one take the
            # same path through the materializer.
            _apply_scopes(claims_by_id, bound, intent)
            devices.append(
                DerivedDevice(
                    kind=intent.kind,
                    content_path=content_path,
                    claim_ids=bound,
                    label=intent.label,
                )
            )

    return DerivedEvidence(
        sources=tuple(sources), claims=tuple(claims), devices=tuple(devices)
    )


def _apply_scopes(
    claims_by_id: dict[str, dict[str, Any]],
    claim_ids: tuple[str, ...],
    intent: Any,
) -> None:
    """Record a stated relationship as claim scope.

    Two claims sharing an entity scope across a before and an after scope
    are a transition; three or more across distinct years are a series; a
    percent claim carrying only an entity scope is a share. Nothing here
    computes a new number, so no figure enters the ledger unwritten.
    """
    if intent.kind == "before_after":
        for claim_id, scope in zip(claim_ids, ("before", "after")):
            claims_by_id[claim_id]["entity_scope"] = intent.label
            claims_by_id[claim_id]["time_scope"] = scope
    elif intent.kind == "time_series":
        for claim_id, scope in zip(claim_ids, intent.time_scopes):
            claims_by_id[claim_id]["entity_scope"] = intent.label
            claims_by_id[claim_id]["time_scope"] = scope
    elif intent.kind == "share":
        claims_by_id[claim_ids[0]]["entity_scope"] = intent.label


def _claim_for_figure(
    claim_id_by_span: dict[tuple[str, int, int], str],
    content_path: str,
    figure: Figure,
) -> str | None:
    for (path, start, end), claim_id in claim_id_by_span.items():
        if path != content_path:
            continue
        if figure.start <= start and figure.end >= end:
            return claim_id
    return None
