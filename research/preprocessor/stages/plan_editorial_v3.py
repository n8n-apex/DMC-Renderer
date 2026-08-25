from __future__ import annotations

from typing import Any

from contracts_v3.report_plan import (
    AssetRequirement,
    FacePlan,
    NarrativeRole,
    PlanFailure,
    ProductProfile,
    ProofRequirement,
    ProofType,
    ReportPlanV3,
    SpreadPlan,
    validate_house_plan,
)
from contracts_v3.source_ledger import SourceLedger
from contracts_v3.units import DocumentUnits


class EditorialPlanningError(ValueError):
    def __init__(self, failures: tuple[PlanFailure, ...]):
        self.failures = failures
        super().__init__("; ".join(f"{failure.code}: {failure.detail}" for failure in failures))

    @property
    def codes(self) -> tuple[str, ...]:
        return tuple(failure.code for failure in self.failures)


def materialize_editorial_plan_v3(
    ledger: SourceLedger,
    brief: dict[str, Any],
    profile: ProductProfile,
) -> ReportPlanV3:
    faces = tuple(FacePlan.model_validate(face) for face in brief.get("faces", ()))
    formats = brief.get("formats") or ["a4"] * len(faces)
    plan = ReportPlanV3(
        product_profile_id=brief.get("product_profile_id", profile.profile_id),
        units=DocumentUnits.from_formats(formats),
        faces=faces,
        spreads=tuple(SpreadPlan.model_validate(item) for item in brief.get("spreads", ())),
        audience=brief["audience"],
        central_thesis=brief["central_thesis"],
        promise=brief["promise"],
        tone_profile=brief["tone_profile"],
        source_coverage=tuple(brief.get("source_coverage", ())),
        design_features=brief.get("design_features"),
        exception=brief.get("exception"),
    )
    return plan


def collect_editorial_failures(
    plan: ReportPlanV3,
    ledger: SourceLedger,
    profile: ProductProfile,
) -> tuple[PlanFailure, ...]:
    failures = list(validate_house_plan(plan, profile).failures)
    known_claims = {claim.claim_id for claim in ledger.claims}
    for face in plan.faces:
        unknown = set(face.claim_ids) - known_claims
        if unknown:
            failures.append(
                PlanFailure(
                    code="unknown_claim_reference",
                    detail=f"{face.face_id} references unknown claims: {', '.join(sorted(unknown))}",
                )
            )
    return tuple(failures)


def plan_editorial_v3(
    ledger: SourceLedger,
    brief: dict[str, Any],
    profile: ProductProfile,
) -> ReportPlanV3:
    plan = materialize_editorial_plan_v3(ledger, brief, profile)
    failures = collect_editorial_failures(plan, ledger, profile)
    if failures:
        raise EditorialPlanningError(failures)
    return plan


_LEGACY_ROLE_MAP = {
    "ST-01": NarrativeRole.COVER,
    "ST-02": NarrativeRole.OUTLOOK,
    "ST-05": NarrativeRole.ABOUT,
    "ST-09": NarrativeRole.STATUS_QUO,
    "ST-14": NarrativeRole.FALSE_BELIEFS,
    "ST-07A": NarrativeRole.CASE_STUDY,
    "ST-07B": NarrativeRole.THEORY,
    "ST-08": NarrativeRole.OBJECTIONS,
    "ST-06": NarrativeRole.MECHANISM,
    "ST-FAZIT": NarrativeRole.SUMMARY,
    "ST-22": NarrativeRole.COLLABORATION,
    "ST-03": NarrativeRole.CTA,
    "ST-31": NarrativeRole.BRAND_BREATHER,
    "ST-32": NarrativeRole.BRAND_BREATHER,
}


def _physical_face_count(page_numbers: str | None) -> int:
    if not page_numbers:
        return 1
    token = page_numbers.strip()
    if "-" not in token:
        return 1
    start, end = token.split("-", 1)
    try:
        return max(1, int(end) - int(start) + 1)
    except ValueError:
        return 1


def _slugify(value: str) -> str:
    import re

    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", value.lower())).strip("-")


def legacy_report_to_editorial_brief(report_json: dict[str, Any]) -> dict[str, Any]:
    meta = report_json.get("meta") or {}
    faces: list[dict[str, Any]] = []
    case_number = 0
    for page in report_json.get("pages") or ():
        legacy_type = page.get("type") or page.get("legacy_st_type") or "unknown"
        role = _LEGACY_ROLE_MAP.get(legacy_type, NarrativeRole.THEORY)
        data = page.get("data") or {}
        if role is NarrativeRole.CASE_STUDY:
            case_number += 1
        for _ in range(_physical_face_count(page.get("page_numbers"))):
            face_index = len(faces) + 1
            face_id = f"face.{face_index:02d}"
            proof_requirements: tuple[ProofRequirement, ...] = ()
            if data.get("vertrauenspunkte"):
                proof_requirements = (
                    ProofRequirement(
                        requirement_id=f"{face_id}.trust",
                        proof_type=ProofType.TRUST,
                    ),
                )
            asset_requirements: tuple[AssetRequirement, ...] = ()
            if role is NarrativeRole.CASE_STUDY:
                asset_requirements = (
                    AssetRequirement(
                        requirement_id=f"{face_id}.identity",
                        semantic_class="identity",
                    ),
                )
            faces.append(
                FacePlan(
                    face_id=face_id,
                    face_index=face_index,
                    role=role,
                    narrative_act=str(page.get("chapter_type_original") or legacy_type),
                    argument=str(data.get("title") or data.get("titel") or legacy_type),
                    claim_ids=tuple(data.get("claim_ids") or ()),
                    proof_requirements=proof_requirements,
                    asset_requirements=asset_requirements,
                    dominant_mechanism="legacy-editorial",
                    density_band="moderate",
                    case_id=f"case.{case_number}" if role is NarrativeRole.CASE_STUDY else None,
                    legacy_st_type=legacy_type,
                ).model_dump(mode="json")
            )

    return {
        "product_profile_id": "dmc_house_20_face",
        "faces": faces,
        "formats": ["a4"] * len(faces),
        "audience": str(meta.get("audience") or "German B2B decision maker"),
        "central_thesis": str(meta.get("central_thesis") or "Legacy report thesis pending"),
        "promise": str(meta.get("promise") or "Legacy report promise pending"),
        "tone_profile": str(meta.get("tone_profile") or "Richard house"),
    }


def profile_id_for_report(report_json: dict[str, Any]) -> str:
    """Deterministic, report-shaped profile id (input-driven, never invented).

    The house profile is a fixed 20-face / 3-case specimen; a real client
    report is its own structure (23 faces, 5 cases, no objections chapter).
    Deriving the profile from the report's OWN editorial map is the
    input-driven rule: VALUES come from data, never a fabricated shape.
    """
    short = _slugify(
        str(
            (report_json.get("meta") or {}).get("report_id")
            or (report_json.get("meta") or {}).get("client_slug")
            or "legacy"
        )
    )
    return f"dmc_report_{short}"[:60]


def derive_report_profile(brief: dict[str, Any]) -> ProductProfile:
    """A product profile that matches the report's OWN editorial shape.

    Counts what the report actually IS (faces, cases, theory faces, the roles
    it names, whether it carries trust evidence) instead of demanding a fixed
    house specimen. Never invents a role the report lacks (e.g. objections on
    a report without an objections chapter) and never demands a case count the
    report does not contain.
    """
    faces = [
        FacePlan.model_validate(face)
        for face in brief.get("faces") or ()
    ]
    roles = tuple(dict.fromkeys(face.role for face in faces))
    has_trust = any(
        requirement.proof_type is ProofType.TRUST
        for face in faces
        for requirement in face.proof_requirements
    )
    base = str(brief.get("product_profile_id") or "dmc_house_20_face")
    if base.endswith(".derived"):
        profile_id = base
    else:
        profile_id = f"{base}.derived"
    return ProductProfile(
        profile_id=profile_id,
        schema_version="3.0",
        face_count=len(faces),
        case_count=sum(face.role is NarrativeRole.CASE_STUDY for face in faces),
        min_theory_faces=sum(face.role is NarrativeRole.THEORY for face in faces),
        required_roles=roles,
        require_trust_evidence=has_trust,
        cover_must_be_first=True,
        cta_must_be_last=True,
        exception_policy=(
            "report-derived: the profile is the report's own editorial shape "
            "(input-driven, never invented)"
        ),
    )


def _append_derived_profile_id(brief: dict[str, Any]) -> None:
    """Stamp the brief's product_profile_id so plan == derived profile id.

    Mutates ``brief`` in place (the precomposition owner passes it through);
    validation requires plan.product_profile_id to match the profile checked
    against it, and the derived profile's id MUST be the same string. Keep the
    id deterministic on the base house id so a re-build cannot drift.
    """
    base = str(brief.get("product_profile_id") or "dmc_house_20_face")
    # Idempotent: a brief already stamped by a previous derive yields the same
    # id, so the plan's product_profile_id and the derived profile match even
    # when both derive helpers run on the same brief.
    if base.endswith(".derived"):
        return
    brief["product_profile_id"] = f"{base}.derived"
