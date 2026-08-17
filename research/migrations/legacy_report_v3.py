"""Editorial migration of legacy v1/v2 report payloads into v3 review inputs.

A legacy report JSON (the rendered payload of a shipped v1/v2 report) is NOT a
valid v3 source. It contains finished copy, invented or unverifiable numbers,
inline citations without spans, and assets without rights. This module migrates
such a payload into an honest, review-only ``MigrationRecord``:

- the original bytes are pinned by hash and verified separately from any
  migrated content (``OriginalArtifact`` / ``verify_original``);
- every source reference found in the original (inline citations, explicit
  ``quelle`` fields, URL fields, inline URLs) is preserved verbatim with
  rights_status "unknown" until a human resolves it;
- case selection stays "pending": the legacy report carries five case studies,
  the v3 house structure carries exactly three, and choosing is a human
  decision (``ThreeCaseSelectionRecord``);
- the 20-face editorial map is defined explicitly from source content paths
  and never derived by snapping legacy page ranges;
- everything unresolved (rights, spans, numeric claims, objections evidence,
  trust proof, portraits) is recorded as a typed blocker, and
  ``to_precomposition_inputs`` feeds those blockers plus the raw report pages
  into the existing v3 pipeline so a blocked migration can never false-pass
  precomposition.

Nothing in this module invents copy, claims, portraits, rights, or approval.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable, Literal

from pydantic import BaseModel, ConfigDict, Field

from case_selection import CaseCandidate, CaseDecision, ThreeCaseSelectionRecord
from contracts_v3.asset_ledger import AssetRecord
from contracts_v3.source_ledger import Claim, SourceItem


# The same numeric-token pattern the v3 source ledger uses for grounding.
_NUMBER_RE = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)?\s*%?")
# Inline URL inside prose or asset fields.
_URL_RE = re.compile(r"https?://\S+")
# Citation parenthetical carrying a four-digit year, e.g. "(BCG, 2025)".
_CITATION_RE = re.compile(r"\([^()]*\b(?:19|20)\d{2}\)")

# Field names that explicitly declare a source in legacy payloads.
_EXPLICIT_SOURCE_KEYS = {"quelle"}

_LEGACY_CASE_TYPE = "ST-07A"
_LEGACY_THEORY_TYPE = "ST-07B"
_TRUST_FIELD_KEYS = ("credibility_points", "vertrauenspunkte")
_CTA_URL_KEYS = ("cta_url", "url")
_TITLE_KEYS = ("title", "titel", "headline")
_PORTRAIT_IMAGE_HINTS = ("author", "founder", "portrait", "portraet")


class OriginalArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    repository_path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_count: int = Field(gt=0)
    report_pointer: str = Field(min_length=1)


class SourceReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    reference_kind: Literal["explicit_source_field", "url_field", "citation", "inline_url"]
    content_path: str = Field(min_length=1)
    raw_value: str
    rights_status: Literal["unknown"] = "unknown"


class EditorialFace(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    face_id: str = Field(min_length=1)
    face_index: int = Field(gt=0)
    role: Literal[
        "cover",
        "outlook",
        "about",
        "status_quo",
        "false_beliefs",
        "case_study",
        "theory",
        "mechanism",
        "trust_proof",
        "summary",
        "objections",
        "collaboration",
        "cta",
        "brand_breather",
    ]
    narrative_act: str = Field(min_length=1)
    argument: str = Field(min_length=1)
    mapping_basis: Literal["explicit_source_path"] = "explicit_source_path"
    page_range_derived: Literal[False] = False
    source_content_paths: tuple[str, ...] = ()
    case_slot: int | None = None
    source_gap: str | None = None


class EditorialMap(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["3.0"] = "3.0"
    product_profile_id: str = Field(min_length=1)
    faces: tuple[EditorialFace, ...]


class MigrationBlocker(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(min_length=1)
    detail: str = Field(min_length=1)
    content_path: str | None = None
    claim_kind: str | None = None
    raw_value: str | None = None


class MigrationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["3.0"] = "3.0"
    client_id: str = Field(min_length=1)
    original_artifact: OriginalArtifact
    source_references: tuple[SourceReference, ...]
    case_selection: ThreeCaseSelectionRecord
    editorial_map: EditorialMap
    blockers: tuple[MigrationBlocker, ...]
    # Verified v3 material. Migration alone can never populate these: every
    # source needs resolved rights and spans, every claim needs grounding, and
    # every asset needs cleared rights. They stay empty until humans resolve
    # the blockers above.
    sources: tuple[SourceItem, ...] = ()
    claims: tuple[Claim, ...] = ()
    assets: tuple[AssetRecord, ...] = ()

    @property
    def blocker_codes(self) -> tuple[str, ...]:
        return tuple(blocker.code for blocker in self.blockers)

    @property
    def renderable(self) -> bool:
        return not self.blockers

    def verify_original(self, project_root: Path) -> bool:
        path = Path(project_root) / self.original_artifact.repository_path
        if not path.is_file():
            return False
        data = path.read_bytes()
        return (
            hashlib.sha256(data).hexdigest() == self.original_artifact.sha256
            and len(data) == self.original_artifact.byte_count
        )

    def to_precomposition_inputs(
        self, document: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Adapt this record to the existing ``build_precomposition_bundle_v3`` API.

        The bundle is honest: no sources, claims, or assets are fabricated.
        The raw report pages ride along as ``report_json`` so the source
        ledger detects every ungrounded numeric candidate itself, and every
        migration blocker is surfaced as an adapter failure so the pipeline
        must refuse the build.
        """
        report_node = _resolve_pointer(document, self.original_artifact.report_pointer)
        source_bundle: dict[str, Any] = {
            "report_json": report_node,
            "sources": [],
            "claims": [],
            "assets": [],
            "adapter_failures": [
                {
                    "code": blocker.code,
                    "detail": blocker.detail,
                    "content_path": blocker.content_path,
                }
                for blocker in self.blockers
            ],
        }
        faces = []
        case_ids_seen = 0
        for face in self.editorial_map.faces:
            plan_face: dict[str, Any] = {
                "face_id": face.face_id,
                "face_index": face.face_index,
                "role": face.role,
                "narrative_act": face.narrative_act,
                "argument": face.argument,
                "dominant_mechanism": "legacy-editorial",
                "density_band": "moderate",
            }
            if face.role == "case_study":
                case_ids_seen += 1
                plan_face["case_id"] = f"case.{case_ids_seen}"
                plan_face["asset_requirements"] = (
                    {
                        "requirement_id": f"{face.face_id}.identity",
                        "semantic_class": "identity",
                    },
                )
            # Richard's covers carry 1-9 images and his CTA pages 1-6; ours
            # requested none, so the cover rendered as a solid ink rectangle
            # with type on it. Measured from the reference atlas.
            if face.role in ("cover", "cta"):
                plan_face["asset_requirements"] = (
                    {
                        "requirement_id": f"{face.face_id}.context",
                        "semantic_class": "context",
                    },
                )
            if face.role == "trust_proof":
                plan_face["proof_requirements"] = (
                    {
                        "requirement_id": f"{face.face_id}.trust",
                        "proof_type": "trust",
                    },
                )
            faces.append(plan_face)
        brief: dict[str, Any] = {
            "product_profile_id": self.editorial_map.product_profile_id,
            "faces": faces,
            "formats": ["a4"] * len(faces),
            "audience": "German B2B decision maker (legacy report; pending human brief)",
            "central_thesis": "Pending human synthesis from resolved sources",
            "promise": "Pending human synthesis from resolved sources",
            "tone_profile": "Richard house",
        }
        return source_bundle, brief


def _resolve_pointer(document: dict[str, Any], pointer: str) -> dict[str, Any]:
    if pointer == "$":
        return document
    if not pointer.startswith("$."):
        raise ValueError(f"unsupported report pointer: {pointer!r}")
    node: Any = document
    for part in pointer[2:].split("."):
        node = node[part]
    return node


def _walk_strings(value: Any, content_path: str) -> Iterable[tuple[str, str]]:
    if isinstance(value, str):
        yield content_path, value
    elif isinstance(value, dict):
        for key, child in value.items():
            yield from _walk_strings(child, f"{content_path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_strings(child, f"{content_path}[{index}]")


def _terminal_key(content_path: str) -> str:
    tail = content_path.rsplit(".", 1)[-1]
    return tail.split("[", 1)[0]


def extract_source_references(document: dict[str, Any]) -> tuple[SourceReference, ...]:
    """Collect every source reference present in the original document.

    Extraction is purely mechanical, never interpretive:

    - a field named ``quelle`` is an explicit source declaration and is
      preserved whole;
    - a field whose key ends in ``url`` is a URL slot and is preserved whole,
      including when it is empty (an empty slot is still a reference a human
      must resolve);
    - inside any other string, citation parentheticals carrying a four-digit
      year and inline ``http(s)`` URLs are preserved verbatim.

    Every reference starts with rights_status "unknown". Resolving rights is a
    human task; this code never upgrades it.
    """
    references: list[SourceReference] = []
    for content_path, text in _walk_strings(document, "$"):
        key = _terminal_key(content_path)
        if key in _EXPLICIT_SOURCE_KEYS:
            references.append(
                SourceReference(
                    reference_kind="explicit_source_field",
                    content_path=content_path,
                    raw_value=text,
                )
            )
            continue
        if key.lower().endswith("url"):
            references.append(
                SourceReference(
                    reference_kind="url_field",
                    content_path=content_path,
                    raw_value=text,
                )
            )
            continue
        for match in _CITATION_RE.finditer(text):
            references.append(
                SourceReference(
                    reference_kind="citation",
                    content_path=content_path,
                    raw_value=match.group(0),
                )
            )
        for match in _URL_RE.finditer(text):
            references.append(
                SourceReference(
                    reference_kind="inline_url",
                    content_path=content_path,
                    raw_value=match.group(0),
                )
            )
    return tuple(references)


def _pages(report_node: dict[str, Any]) -> list[dict[str, Any]]:
    return list(report_node.get("pages") or [])


def _slots_of_type(pages: list[dict[str, Any]], st_type: str) -> list[int]:
    """1-based positions of pages of the given legacy type, in document order."""
    return [index for index, page in enumerate(pages, start=1) if page.get("type") == st_type]


def _page_data(pages: list[dict[str, Any]], slot: int) -> dict[str, Any]:
    return pages[slot - 1].get("data") or {}


def _page_path(pointer: str, slot: int) -> str:
    return f"{pointer}.pages[{slot - 1}].data"


def _title_of(data: dict[str, Any], fallback: str) -> str:
    for key in _TITLE_KEYS:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return fallback


def _case_label(data: dict[str, Any], slot: int) -> str:
    kunde = data.get("kunde")
    if isinstance(kunde, dict):
        for key in ("name", "funktion"):
            value = kunde.get(key)
            if isinstance(value, str) and value.strip():
                return value
    headline = data.get("ergebnis_headline")
    if isinstance(headline, str) and headline.strip():
        return headline
    return f"{_LEGACY_CASE_TYPE} page slot {slot}"


def _build_case_selection(
    pages: list[dict[str, Any]], pointer: str
) -> ThreeCaseSelectionRecord:
    candidates = tuple(
        CaseCandidate(
            case_id=f"case.candidate.slot{slot:02d}",
            source_slot=slot,
            source_content_path=_page_path(pointer, slot),
            source_label=_case_label(_page_data(pages, slot), slot),
        )
        for slot in _slots_of_type(pages, _LEGACY_CASE_TYPE)
    )
    pending = tuple(
        CaseDecision(
            case_id=candidate.case_id,
            reason=(
                "The legacy report carries more case studies than the three the "
                "v3 house structure allows. Choosing which three survive is an "
                "editorial decision reserved for a human owner; no automated "
                "selection is permitted."
            ),
        )
        for candidate in candidates
    )
    return ThreeCaseSelectionRecord(
        candidates=candidates,
        pending_cases=pending,
        human_review_status="pending",
    )


# The house 20-face structure this migration targets. Case studies sit at
# faces 6, 10, and 12. Every entry names its source explicitly:
#   ("type", st_type)      -> the first legacy page of that ST type
#   ("theory", n)          -> the n-th ST-07B theory page (0-based)
#   ("case", n)            -> house case slot n (1-based); selection pending
#   ("trust", None)        -> the trust-evidence field on the legacy about page
#   (None, None)           -> no legacy source exists for this face
_HOUSE_LAYOUT: tuple[tuple[int, str, tuple[str | None, Any], str], ...] = (
    (1, "cover", ("type", "ST-01"), "Hook and compression of the report promise"),
    (2, "outlook", ("type", "ST-02"), "Frames the stakes after the cover"),
    (3, "about", ("type", "ST-05"), "Earns credibility before the diagnosis"),
    (4, "status_quo", ("type", "ST-09"), "Builds pain and self-recognition"),
    (5, "false_beliefs", ("type", "ST-14"), "Reframes the prospect's false beliefs"),
    (6, "case_study", ("case", 1), "First proof peak after the diagnosis"),
    (7, "theory", ("theory", 0), "Generalizes the first proof into a mechanism"),
    (8, "theory", ("theory", 1), "Sustains the argument between proof peaks"),
    (9, "theory", ("theory", 2), "Completes the theory arc before the second proof"),
    (10, "case_study", ("case", 2), "Second proof peak"),
    (11, "mechanism", ("type", "ST-06"), "Turns proof into a repeatable model"),
    (12, "case_study", ("case", 3), "Third and strongest proof peak"),
    (13, "summary", ("type", "ST-FAZIT"), "Begins the conversion act"),
    (14, "objections", (None, None), "Removes hesitation before the process explanation"),
    (15, "trust_proof", ("trust", None), "Stacks verifiable trust evidence"),
    (16, "collaboration", ("type", "ST-22"), "Makes the collaboration concrete, part one"),
    (17, "collaboration", ("type", "ST-22"), "Makes the collaboration concrete, part two"),
    (18, "cta", ("type", "ST-03"), "Primary conversion pause"),
    (19, "brand_breather", (None, None), "Deliberate visual breath before the close"),
    (20, "cta", ("type", "ST-03"), "Final back page close"),
)


def _trust_field_path(pages: list[dict[str, Any]], pointer: str) -> str | None:
    for slot in _slots_of_type(pages, "ST-05"):
        data = _page_data(pages, slot)
        for key in _TRUST_FIELD_KEYS:
            if data.get(key):
                return f"{_page_path(pointer, slot)}.{key}"
    return None


def _build_editorial_map(pages: list[dict[str, Any]], pointer: str) -> EditorialMap:
    """Define the 20-face map explicitly from source content paths.

    Legacy pages are located by their ST type in document order. Legacy
    ``page_numbers`` strings are never read: physical page ranges of the old
    render carry no editorial meaning and mutating them must not change this
    map.
    """
    theory_slots = _slots_of_type(pages, _LEGACY_THEORY_TYPE)
    trust_path = _trust_field_path(pages, pointer)
    faces: list[EditorialFace] = []
    for face_index, role, (source_kind, source_arg), act in _HOUSE_LAYOUT:
        face_id = f"face.{face_index:02d}"
        source_paths: tuple[str, ...] = ()
        case_slot: int | None = None
        source_gap: str | None = None
        argument: str

        if source_kind == "type":
            slots = _slots_of_type(pages, source_arg)
            if slots:
                slot = slots[0]
                source_paths = (_page_path(pointer, slot),)
                argument = _title_of(_page_data(pages, slot), f"{source_arg} section")
            else:
                source_gap = f"legacy report has no {source_arg} page"
                argument = f"{role} face; no legacy {source_arg} source present"
        elif source_kind == "theory":
            if source_arg < len(theory_slots):
                slot = theory_slots[source_arg]
                source_paths = (_page_path(pointer, slot),)
                argument = _title_of(
                    _page_data(pages, slot), f"{_LEGACY_THEORY_TYPE} section {source_arg + 1}"
                )
            else:
                source_gap = (
                    f"legacy report has no {_LEGACY_THEORY_TYPE} page for theory face "
                    f"{source_arg + 1}"
                )
                argument = f"theory face {source_arg + 1}; no legacy source present"
        elif source_kind == "case":
            case_slot = source_arg
            source_gap = "case selection pending human review"
            argument = (
                f"Case study slot {source_arg}; awaiting human selection from the "
                "legacy case candidates"
            )
        elif source_kind == "trust":
            if trust_path is not None:
                source_paths = (trust_path,)
                argument = "Trust evidence carried by the legacy about section (unverified)"
            else:
                source_gap = "legacy report declares no trust evidence fields"
                argument = "Trust proof face; no legacy trust evidence present"
        else:
            source_gap = "house structure face without legacy source content"
            argument = f"{role.replace('_', ' ').capitalize()} face required by the house structure"

        faces.append(
            EditorialFace(
                face_id=face_id,
                face_index=face_index,
                role=role,  # type: ignore[arg-type]
                narrative_act=act,
                argument=argument,
                source_content_paths=source_paths,
                case_slot=case_slot,
                source_gap=source_gap,
            )
        )
    return EditorialMap(product_profile_id="dmc_house_20_face", faces=tuple(faces))


def _numeric_findings(
    pages: list[dict[str, Any]], pointer: str
) -> tuple[tuple[str, str], ...]:
    """Every unique (content_path, token) numeric candidate in the report copy."""
    findings: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for page_index, page in enumerate(pages):
        base = f"{pointer}.pages[{page_index}].data"
        for content_path, text in _walk_strings(page.get("data") or {}, base):
            for match in _NUMBER_RE.finditer(text):
                token = match.group(0).strip()
                key = (content_path, token)
                if key in seen:
                    continue
                seen.add(key)
                findings.append(key)
    return tuple(findings)


def _founder_portrait_blocker(document: dict[str, Any]) -> MigrationBlocker:
    images = document.get("images")
    if isinstance(images, dict):
        for key, value in images.items():
            if any(hint in key.lower() for hint in _PORTRAIT_IMAGE_HINTS):
                return MigrationBlocker(
                    code="founder_portrait_rights_unresolved",
                    detail=(
                        "the legacy payload references a founder portrait but carries "
                        "no usage rights; a human must clear them"
                    ),
                    content_path=f"$.images.{key}",
                    raw_value=value if isinstance(value, str) else None,
                )
    return MigrationBlocker(
        code="founder_portrait_rights_unresolved",
        detail=(
            "the legacy payload carries no founder portrait; sourcing one and "
            "clearing its rights is a human task"
        ),
    )


def _cta_url_blocker(
    pages: list[dict[str, Any]], pointer: str
) -> MigrationBlocker | None:
    slots = _slots_of_type(pages, "ST-03")
    if not slots:
        return MigrationBlocker(
            code="cta_url_missing",
            detail="the legacy report has no CTA page, so no CTA URL exists",
        )
    slot = slots[0]
    data = _page_data(pages, slot)
    for key in _CTA_URL_KEYS:
        if key in data:
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return None
            return MigrationBlocker(
                code="cta_url_missing",
                detail="the legacy CTA page declares an empty CTA URL; a human must supply it",
                content_path=f"{_page_path(pointer, slot)}.{key}",
                raw_value=value if isinstance(value, str) else None,
            )
    return MigrationBlocker(
        code="cta_url_missing",
        detail="the legacy CTA page declares no CTA URL field; a human must supply one",
        content_path=_page_path(pointer, slot),
    )


def _build_blockers(
    document: dict[str, Any],
    pages: list[dict[str, Any]],
    pointer: str,
    references: tuple[SourceReference, ...],
    selection: ThreeCaseSelectionRecord,
) -> tuple[MigrationBlocker, ...]:
    blockers: list[MigrationBlocker] = []

    blockers.append(
        MigrationBlocker(
            code="human_case_selection_pending",
            detail=(
                f"{len(selection.candidates)} legacy case candidates await a human "
                f"owner choosing exactly {selection.required_case_count}"
            ),
        )
    )
    for candidate in selection.candidates:
        blockers.append(
            MigrationBlocker(
                code="case_portrait_unresolved",
                detail=(
                    f"case candidate {candidate.case_id} ({candidate.source_label}) has "
                    "no rights-cleared portrait or identity asset"
                ),
                content_path=candidate.source_content_path,
            )
        )

    blockers.append(
        MigrationBlocker(
            code="source_spans_missing",
            detail=(
                "the legacy payload is rendered copy without underlying transcripts "
                "or documents, so no claim can be grounded with verbatim source spans"
            ),
        )
    )
    for reference in references:
        blockers.append(
            MigrationBlocker(
                code="source_rights_unresolved",
                detail=(
                    f"rights for source reference at {reference.content_path} are "
                    "unknown until a human resolves them"
                ),
                content_path=reference.content_path,
                raw_value=reference.raw_value,
            )
        )

    for content_path, token in _numeric_findings(pages, pointer):
        blockers.append(
            MigrationBlocker(
                code="unsupported_claim",
                detail=(
                    f"numeric claim {token!r} at {content_path} has no grounded "
                    "source span or computation"
                ),
                content_path=content_path,
                claim_kind="number",
                raw_value=token,
            )
        )

    blockers.append(
        MigrationBlocker(
            code="objections_evidence_missing",
            detail=(
                "the house structure requires an objections face, but the legacy "
                "report carries no objections content or supporting evidence"
            ),
        )
    )

    trust_path = _trust_field_path(pages, pointer)
    blockers.append(
        MigrationBlocker(
            code="trust_proof_unverified",
            detail=(
                "the legacy report asserts trust points that have never been "
                "verified against sources"
                if trust_path
                else "the legacy report declares no verifiable trust evidence"
            ),
            content_path=trust_path,
        )
    )

    blockers.append(_founder_portrait_blocker(document))

    cta_blocker = _cta_url_blocker(pages, pointer)
    if cta_blocker is not None:
        blockers.append(cta_blocker)

    return tuple(blockers)


def build_migration_record(
    *,
    client_id: str,
    original_path: Path,
    project_root: Path,
    report_pointer: str,
    document: dict[str, Any] | None = None,
) -> MigrationRecord:
    raw = original_path.read_bytes()
    if document is None:
        document = json.loads(raw.decode("utf-8"))

    artifact = OriginalArtifact(
        repository_path=original_path.resolve()
        .relative_to(Path(project_root).resolve())
        .as_posix(),
        sha256=hashlib.sha256(raw).hexdigest(),
        byte_count=len(raw),
        report_pointer=report_pointer,
    )

    references = extract_source_references(document)
    report_node = _resolve_pointer(document, report_pointer)
    pages = _pages(report_node)
    selection = _build_case_selection(pages, report_pointer)
    editorial_map = _build_editorial_map(pages, report_pointer)
    blockers = _build_blockers(document, pages, report_pointer, references, selection)

    return MigrationRecord(
        client_id=client_id,
        original_artifact=artifact,
        source_references=references,
        case_selection=selection,
        editorial_map=editorial_map,
        blockers=blockers,
    )
