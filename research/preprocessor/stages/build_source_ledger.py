from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Iterable

from contracts_v3.source_ledger import (
    Claim,
    ClaimType,
    GroundingFailure,
    SourceItem,
    SourceLedger,
)


# The one tokenizer that defines what counts as a number in report copy.
# The claim deriver uses it too, so derived claims cover exactly the
# tokens this gate would otherwise report as ungrounded.
NUMBER_TOKEN_RE = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)?\s*%?")
_GROUNDED_CLAIM_TYPES = {
    ClaimType.FACT.value,
    ClaimType.NUMBER.value,
    ClaimType.QUOTE.value,
    ClaimType.CREDENTIAL.value,
    ClaimType.CERTIFICATION.value,
    ClaimType.NAMED_RESULT.value,
}
_UNIT_ALIASES = {
    "%": "percent",
    "prozent": "percent",
    "percent": "percent",
    "€": "EUR",
    "eur": "EUR",
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _source_item(raw: dict[str, Any]) -> SourceItem:
    values = dict(raw)
    local_path = values.pop("local_path", None)
    if "content_hash" not in values:
        source_bytes = (
            Path(local_path).read_bytes()
            if local_path
            else values.get("verbatim_text", "").encode("utf-8")
        )
        values["content_hash"] = _sha256(source_bytes)
    return SourceItem.model_validate(values)


def page_strings(bundle: dict[str, Any]) -> Iterable[tuple[str, str]]:
    pages = ((bundle.get("report_json") or {}).get("pages") or [])

    def walk(value: Any, content_path: str) -> Iterable[tuple[str, str]]:
        if isinstance(value, str):
            yield content_path, value
        elif isinstance(value, dict):
            for key, child in value.items():
                yield from walk(child, f"{content_path}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                yield from walk(child, f"{content_path}[{index}]")

    for page_index, page in enumerate(pages):
        yield from walk(page.get("data") or {}, f"report_json.pages[{page_index}].data")


def normalize_number_token(token: str) -> tuple[str, str | None]:
    compact = token.replace(" ", "")
    unit = "percent" if compact.endswith("%") else None
    value = compact.removesuffix("%").replace(",", ".")
    return value, unit


def _claims(
    raw_claims: Iterable[dict[str, Any]],
    sources: tuple[SourceItem, ...],
) -> tuple[tuple[Claim, ...], tuple[GroundingFailure, ...]]:
    claims: list[Claim] = []
    failures: list[GroundingFailure] = []
    source_by_id = {source.source_id: source for source in sources}
    for raw in raw_claims:
        values = dict(raw)
        unit = values.get("unit")
        if isinstance(unit, str):
            values["unit"] = _UNIT_ALIASES.get(unit.strip().lower(), unit)
        if (
            values.get("claim_type") in _GROUNDED_CLAIM_TYPES
            and not values.get("source_spans")
            and not values.get("computation")
        ):
            claim_id = str(values.get("claim_id") or "unknown")
            failures.append(
                GroundingFailure(
                    code="ungrounded_claim",
                    claim_id=claim_id,
                    detail=f"claim {claim_id} has no source span or computation",
                )
            )
            continue
        claim = Claim.model_validate(values)
        unknown_sources = set(claim.source_ids) - set(source_by_id)
        if unknown_sources:
            failures.append(
                GroundingFailure(
                    code="invalid_source_reference",
                    claim_id=claim.claim_id,
                    detail=(
                        f"claim {claim.claim_id} references unknown sources: "
                        f"{', '.join(sorted(unknown_sources))}"
                    ),
                )
            )
            continue
        mismatched_span = next(
            (
                span
                for span in claim.source_spans
                if source_by_id[span.source_id].verbatim_text[span.start:span.end]
                != span.verbatim
            ),
            None,
        )
        if mismatched_span is not None:
            failures.append(
                GroundingFailure(
                    code="source_span_mismatch",
                    claim_id=claim.claim_id,
                    detail=f"claim {claim.claim_id} source span does not match verbatim text",
                )
            )
            continue
        claims.append(claim)
    return tuple(claims), tuple(failures)


def _spans_by_locator(
    sources: tuple[SourceItem, ...], claims: tuple[Claim, ...]
) -> dict[str, tuple[tuple[int, int], ...]]:
    """Claim spans grouped by the content path their source was read from."""

    locator_by_source = {source.source_id: source.locator for source in sources}
    spans: dict[str, list[tuple[int, int]]] = {}
    for claim in claims:
        for span in claim.source_spans:
            locator = locator_by_source.get(span.source_id)
            if locator is not None:
                spans.setdefault(locator, []).append((span.start, span.end))
    return {locator: tuple(items) for locator, items in spans.items()}


def _ungrounded_numeric_candidates(
    bundle: dict[str, Any],
    claims: tuple[Claim, ...],
    sources: tuple[SourceItem, ...] = (),
) -> tuple[GroundingFailure, ...]:
    covered = {(claim.normalized_value.replace(",", "."), claim.unit) for claim in claims}
    # A claim whose own span sits on this numeral in this exact field is
    # stronger proof than a value that merely matches somewhere in the
    # report, so it grounds the token regardless of how its unit reads.
    spans_by_locator = _spans_by_locator(sources, claims)
    failures: list[GroundingFailure] = []
    seen: set[tuple[str, str]] = set()
    for content_path, text in page_strings(bundle):
        spans = spans_by_locator.get(content_path, ())
        for match in NUMBER_TOKEN_RE.finditer(text):
            token = match.group(0).strip()
            value, unit = normalize_number_token(token)
            key = (content_path, token)
            token_end = match.start() + len(token)
            span_covered = any(
                start <= match.start() and end >= token_end for start, end in spans
            )
            if (value, unit) in covered or span_covered or key in seen:
                continue
            seen.add(key)
            failures.append(
                GroundingFailure(
                    code="ungrounded_numeric_candidate",
                    token=token,
                    content_path=content_path,
                    detail=f"numeric token {token!r} has no grounded claim",
                )
            )
    return tuple(failures)


def build_source_ledger(source_bundle: dict[str, Any]) -> SourceLedger:
    sources = tuple(_source_item(raw) for raw in source_bundle.get("sources", ()))
    claims, claim_failures = _claims(source_bundle.get("claims", ()), sources)
    return SourceLedger(
        sources=sources,
        claims=claims,
        grounding_failures=(
            claim_failures
            + _ungrounded_numeric_candidates(source_bundle, claims, sources)
        ),
    )
