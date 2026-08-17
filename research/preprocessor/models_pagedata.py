"""Typed per-ST page-data schemas (DNA §D recipes).

Field names match EXACTLY what the renderer patterns read (verified against
research/v7-renderer/patterns/*.py). Every field is optional/defaulted so
missing content validates (degrade, never block). List items the renderer
also accepts as "label: value"/bare strings keep a `str` alternative so the
typed view never rejects valid current data. Each model is extra="allow"
(unexpected keys are preserved, not rejected). Unknown ST types →
GenericPageData. parse_page_data() never raises.

Brand-agnostic: field NAMES + shapes only; no client value here.
"""
from __future__ import annotations

from typing import Optional, Union

from pydantic import BaseModel, ConfigDict, Field, ValidationError

_Permissive = ConfigDict(extra="allow")


class StatItem(BaseModel):
    model_config = _Permissive
    value: Optional[str] = None
    label: Optional[str] = None


class Author(BaseModel):
    model_config = _Permissive
    name: Optional[str] = None
    role: Optional[str] = None


class Kunde(BaseModel):
    model_config = _Permissive
    name: Optional[str] = None
    funktion: Optional[str] = None
    company_url: Optional[str] = None


class PullQuote(BaseModel):
    model_config = _Permissive
    text: Optional[str] = None
    attribution: Optional[str] = None


class Step(BaseModel):
    model_config = _Permissive
    title: Optional[str] = None
    body: Optional[str] = None


class CollabStep(BaseModel):
    model_config = _Permissive
    n: Optional[Union[int, str]] = None
    title: Optional[str] = None
    body: Optional[str] = None
    dauer: Optional[str] = None


class FaqItem(BaseModel):
    model_config = _Permissive
    frage: Optional[str] = None
    antwort: Optional[str] = None


class Symptom(BaseModel):
    model_config = _Permissive
    title: Optional[str] = None
    body: Optional[str] = None


class Belief(BaseModel):
    model_config = _Permissive
    irrglaube: Optional[str] = None
    realitaet: Optional[str] = None
    quelle: Optional[str] = None


class Compare(BaseModel):
    model_config = _Permissive
    ohne: list[str] = Field(default_factory=list)
    mit: list[str] = Field(default_factory=list)


class CoverData(BaseModel):
    model_config = _Permissive
    title: Optional[str] = None
    subtitle: Optional[str] = None
    kicker_pills: list[str] = Field(default_factory=list)
    proof_stats: list[Union[StatItem, str]] = Field(default_factory=list)
    author: Optional[Author] = None


class IntroData(BaseModel):
    model_config = _Permissive
    title: Optional[str] = None
    body: Optional[str] = None
    zielgruppe: list[str] = Field(default_factory=list)


class CtaData(BaseModel):
    model_config = _Permissive
    title: Optional[str] = None
    body: Optional[str] = None
    cta_url: Optional[str] = None
    cta_text: Optional[str] = None


class AboutData(BaseModel):
    model_config = _Permissive
    title: Optional[str] = None
    body: Optional[str] = None
    stats: list[Union[StatItem, str]] = Field(default_factory=list)
    partners: list[str] = Field(default_factory=list)
    credibility_points: list[str] = Field(default_factory=list)


class MechanismData(BaseModel):
    model_config = _Permissive
    title: Optional[str] = None
    body: Optional[str] = None
    steps: list[Union[Step, str]] = Field(default_factory=list)
    ergebnis: Optional[str] = None
    bars: list[Union[StatItem, str]] = Field(default_factory=list)
    metrics: list[Union[StatItem, str]] = Field(default_factory=list)


class CaseStudyData(BaseModel):
    model_config = _Permissive
    kurzportraet: Optional[str] = None
    ausgangsproblem: Optional[str] = None
    ziel: Optional[str] = None
    loesung: Optional[str] = None
    ergebnis_text: Optional[str] = None
    ergebnis_headline: Optional[str] = None
    fallstudie_number: Optional[Union[int, str]] = None
    ergebnis_metrics: list[Union[StatItem, str]] = Field(default_factory=list)
    kunde: Optional[Kunde] = None
    pullquote: Optional[PullQuote] = None


class ComparisonData(BaseModel):
    model_config = _Permissive
    title: Optional[str] = None
    body: Optional[str] = None
    key_insight: Optional[str] = None
    compare: Optional[Compare] = None


class FaqData(BaseModel):
    model_config = _Permissive
    title: Optional[str] = None
    body: Optional[str] = None
    intro: Optional[str] = None
    faqs: list[Union[FaqItem, str]] = Field(default_factory=list)


class ProblemData(BaseModel):
    model_config = _Permissive
    title: Optional[str] = None
    body: Optional[str] = None
    symptoms: list[Union[Symptom, str]] = Field(default_factory=list)


class MythsData(BaseModel):
    model_config = _Permissive
    title: Optional[str] = None
    body: Optional[str] = None
    beliefs: list[Union[Belief, str]] = Field(default_factory=list)


class CollaborationData(BaseModel):
    model_config = _Permissive
    title: Optional[str] = None
    body: Optional[str] = None
    steps: list[Union[CollabStep, str]] = Field(default_factory=list)


class AtmosphericData(BaseModel):
    model_config = _Permissive
    phrase: Optional[str] = None


class FazitData(BaseModel):
    model_config = _Permissive
    title: Optional[str] = None
    body: Optional[str] = None
    these: Optional[str] = None
    kosten_des_nichtstuns: Optional[str] = None
    cta_url: Optional[str] = None


class GenericPageData(BaseModel):
    model_config = _Permissive


# ---- restructure_page (Stage 4.7 "the editor") output models ----------------
# The LLM is a PARAPHRASE-ONLY editor: it returns condensed prose + AT MOST ONE
# diagram of an LLM-allowed kind (stat/process/q_a) built from verbatim spans.
# All fields optional/defaulted (extra="ignore") so a malformed model never
# raises — the stage's deterministic validation suite is what enforces safety.
class RestructureDiagram(BaseModel):
    model_config = ConfigDict(extra="ignore")
    kind: Optional[str] = None             # validated against {stat, process, q_a}
    payload: Optional[dict] = None
    replace_field: Optional[str] = None


class PageRestructure(BaseModel):
    model_config = ConfigDict(extra="ignore")
    prose: dict[str, str] = Field(default_factory=dict)
    diagram: Optional[RestructureDiagram] = None
    source: str = "restructure_page"
    reverted_fields: list[str] = Field(default_factory=list)
    reverted_whole_page: bool = False


ST_TYPE_TO_PAGEDATA: dict[str, type[BaseModel]] = {
    "ST-01": CoverData,
    "ST-02": IntroData,
    "ST-03": CtaData,
    "ST-05": AboutData,
    "ST-06": MechanismData,
    "ST-07A": CaseStudyData,
    "ST-07B": ComparisonData,
    "ST-08": FaqData,
    "ST-09": ProblemData,
    "ST-14": MythsData,
    "ST-22": CollaborationData,
    "ST-31": AtmosphericData,
    "ST-32": AtmosphericData,
    "ST-FAZIT": FazitData,
}


def parse_page_data(st_type: str, data) -> tuple[BaseModel, Optional[str]]:
    """Parse a page's raw `data` into its typed model (dispatched by st_type).
    Unknown type -> GenericPageData (no warning; passthrough is expected).
    ValidationError on a known type -> GenericPageData + a warning. Never raises.
    """
    if not isinstance(data, dict):
        return GenericPageData(), f"{st_type}: data was not a dict; kept as generic"
    model_cls = ST_TYPE_TO_PAGEDATA.get(st_type)
    if model_cls is None:
        return GenericPageData.model_validate(data), None
    try:
        return model_cls.model_validate(data), None
    except ValidationError as exc:
        return (
            GenericPageData.model_validate(data),
            f"{st_type}: page-data parse failed ({exc.error_count()} error(s)); kept as generic",
        )
