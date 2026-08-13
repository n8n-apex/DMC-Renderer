from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class AdapterFailure(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(min_length=1)
    content_path: str
    detail: str = Field(min_length=1)


class CanonicalReportMeta(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    client_slug: str = Field(min_length=1)
    report_id: str = Field(min_length=1)
    lang: str = "de"
    page_format: str = "A4"
    page_count_target: int = Field(gt=0)
    export_mode: str | None = None


class CanonicalPageInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    slot: int = Field(gt=0)
    legacy_st_type: str = Field(min_length=1)
    page_numbers: str | None = None
    chapter_type_original: str | None = None
    data: dict[str, Any]


class CanonicalReportInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    meta: CanonicalReportMeta
    pages: tuple[CanonicalPageInput, ...]


class AdaptedEnvelopeV3(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["3.0"] = "3.0"
    record_id: str
    report_json: CanonicalReportInput
    images: dict[str, Any]
    brand_tokens: dict[str, Any]
    sources: tuple[dict[str, Any], ...]
    claims: tuple[dict[str, Any], ...]
    assets: tuple[dict[str, Any], ...]
    adapter_failures: tuple[AdapterFailure, ...] = ()

    @property
    def failure_codes(self) -> tuple[str, ...]:
        return tuple(failure.code for failure in self.adapter_failures)


_ALIASES = {
    "headline": "title",
    "titel": "title",
    "einleitung": "body",
    "intro": "body",
    "beschreibung": "body",
    "schritte": "steps",
}

_ESTABLISHED_LEGACY_TYPES = {
    "ST-01",
    "ST-02",
    "ST-03",
    "ST-05",
    "ST-06",
    "ST-07A",
    "ST-07B",
    "ST-08",
    "ST-09",
    "ST-14",
    "ST-22",
    "ST-31",
    "ST-32",
    "ST-FAZIT",
}


def _canonicalize(
    value: Any,
    *,
    content_path: str,
    failures: list[AdapterFailure],
) -> Any:
    if isinstance(value, list):
        return [
            _canonicalize(
                item,
                content_path=f"{content_path}[{index}]",
                failures=failures,
            )
            for index, item in enumerate(value)
        ]
    if not isinstance(value, dict):
        return value

    canonical: dict[str, Any] = {}
    for key, child in value.items():
        if key in _ALIASES:
            continue
        canonical[key] = _canonicalize(
            child,
            content_path=f"{content_path}.{key}",
            failures=failures,
        )
    for alias, target in _ALIASES.items():
        if alias not in value:
            continue
        child = _canonicalize(
            value[alias],
            content_path=f"{content_path}.{alias}",
            failures=failures,
        )
        if target in canonical and canonical[target] != child:
            failures.append(
                AdapterFailure(
                    code="conflicting_alias_values",
                    content_path=f"{content_path}.{alias}",
                    detail=f"{alias} conflicts with canonical field {target}",
                )
            )
            continue
        canonical[target] = child
    return canonical


def adapt_envelope_v3(envelope: dict[str, Any]) -> AdaptedEnvelopeV3:
    payload = envelope["payload"]
    failures: list[AdapterFailure] = []
    meta = CanonicalReportMeta.model_validate(payload["meta"])
    if meta.page_count_target not in {16, 20, 24, 28}:
        failures.append(
            AdapterFailure(
                code="unsupported_page_count_target",
                content_path="payload.meta.page_count_target",
                detail=f"target {meta.page_count_target} is unsupported and was not changed",
            )
        )

    pages = []
    for page_index, page in enumerate(payload.get("pages", ())):
        legacy_type = page["type"]
        if legacy_type not in _ESTABLISHED_LEGACY_TYPES:
            failures.append(
                AdapterFailure(
                    code="unsupported_legacy_st_type",
                    content_path=f"payload.pages[{page_index}].type",
                    detail=f"legacy page type {legacy_type!r} is not in the established grammar",
                )
            )
        pages.append(
            CanonicalPageInput(
                slot=page["slot"],
                legacy_st_type=legacy_type,
                page_numbers=page.get("page_numbers"),
                chapter_type_original=page.get("chapter_type_original"),
                data=_canonicalize(
                    page.get("data") or {},
                    content_path=f"payload.pages[{page_index}].data",
                    failures=failures,
                ),
            )
        )
    return AdaptedEnvelopeV3(
        record_id=str(envelope.get("record_id") or meta.report_id),
        report_json=CanonicalReportInput(meta=meta, pages=tuple(pages)),
        images=dict(envelope.get("images") or {}),
        brand_tokens=dict(envelope.get("brand_tokens") or {}),
        sources=tuple(envelope.get("sources") or ()),
        claims=tuple(envelope.get("claims") or ()),
        assets=tuple(envelope.get("assets") or ()),
        adapter_failures=tuple(failures),
    )
