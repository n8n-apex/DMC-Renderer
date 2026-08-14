"""Exact document-unit and PDF geometry checks for v3."""

from __future__ import annotations

import sys
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


HERE = Path(__file__).resolve().parent
PREPROCESSOR_ROOT = HERE.parents[1] / "preprocessor"
if str(PREPROCESSOR_ROOT) not in sys.path:
    sys.path.insert(0, str(PREPROCESSOR_ROOT))

from contracts_v3.release import (  # noqa: E402
    FailureOwner,
    FailureSeverity,
    QualityFailure,
)
from contracts_v3.report_plan import ProductProfile, ReportPlanV3  # noqa: E402
from contracts_v3.render_contract import FrozenRenderContractV3  # noqa: E402


class PdfPageFact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    width_mm: float = Field(gt=0)
    height_mm: float = Field(gt=0)


def _failure(code: str, detail: str, face_ids: tuple[str, ...] = ()) -> QualityFailure:
    return QualityFailure(
        owner_stage=FailureOwner.EDITORIAL,
        code=code,
        severity=FailureSeverity.HARD,
        face_ids=face_ids,
        remediation_class="replan_document_units",
        detail=detail,
    )


def _matches_size(page: PdfPageFact, width: float, height: float) -> bool:
    return abs(page.width_mm - width) <= 2 and abs(page.height_mm - height) <= 2


# Measured from all six of Richard's reports via research/reference-atlas
# (spread objects halved to a per-face figure). These are his OWN averages,
# floored to the integer below, so the gate never demands more than he
# actually delivers for that role:
#
#   about 6.6  trust_proof 5.8  collaboration 4.9  cover 4.3  outlook 3.6
#   theory 3.5  case_study 3.3  mechanism 3.3  objections 3.2  summary 3.2
#   cta 2.7  false_beliefs 2.5  status_quo 2.3  brand_breather 1.0
#
# He averages 3.6 images per face; a v3 build measured 0.6. That gap, not
# layout and not word count, is what leaves 38-43% of a theory face empty:
# every one of our theory faces carries zero images where he puts three.
ROLE_IMAGE_FLOOR = {
    "about": 6,
    "trust_proof": 5,
    "collaboration": 4,
    "cover": 4,
    "outlook": 3,
    "theory": 3,
    "case_study": 3,
    "mechanism": 3,
    "objections": 3,
    "summary": 3,
    "cta": 2,
    "false_beliefs": 2,
    "status_quo": 2,
    "brand_breather": 1,
}

_IMAGE_BEARING = {"image", "qr"}
_GALLERY_KINDS = {"logo_wall", "evidence_gallery"}


def _visual_marks(contract, face_id: str) -> int:
    """How many distinct pictures this face puts on the sheet.

    A wall counts every asset it carries, because that is what the reader
    sees; the element is one node in the contract but many marks on paper.
    """
    marks = 0
    prefix = f"{face_id}."
    for fragment in contract.fragments:
        for element in fragment.elements:
            if not element.element_id.startswith(prefix):
                continue
            if element.kind in _IMAGE_BEARING:
                marks += 1
            elif element.kind in _GALLERY_KINDS:
                marks += len(getattr(element, "asset_ids", ()) or ())
    return marks


def check_structure_v3(
    plan: ReportPlanV3,
    contract: FrozenRenderContractV3,
    profile: ProductProfile,
    pdf_pages: tuple[PdfPageFact, ...],
) -> tuple[QualityFailure, ...]:
    failures: list[QualityFailure] = []
    if plan.units.face_count != profile.face_count:
        failures.append(
            _failure(
                "wrong_face_count",
                f"profile requires {profile.face_count}, plan has {plan.units.face_count}",
                tuple(face.face_id for face in plan.faces),
            )
        )
    # Visual density floor. Capacity has only ever been a ceiling: it checks
    # that copy does not overflow and never that a face carries enough to be
    # worth its area. A face can render at 5.7% ink coverage and pass every
    # other gate.
    for face in plan.faces:
        floor = ROLE_IMAGE_FLOOR.get(face.role.value)
        if not floor:
            continue
        marks = _visual_marks(contract, face.face_id)
        if marks < floor:
            failures.append(
                _failure(
                    "visual_density_below_reference",
                    (
                        f"{face.face_id} ({face.role.value}) carries {marks} "
                        f"pictures; the reference corpus averages {floor} or "
                        "more for this role"
                    ),
                    (face.face_id,),
                )
            )

    if len(contract.fragments) != plan.units.fragment_count:
        failures.append(
            _failure(
                "wrong_fragment_count",
                f"plan has {plan.units.fragment_count}, contract has {len(contract.fragments)}",
            )
        )
    if len(pdf_pages) != plan.units.expected_pdf_objects:
        failures.append(
            _failure(
                "wrong_pdf_object_count",
                f"expected {plan.units.expected_pdf_objects}, PDF has {len(pdf_pages)}",
            )
        )

    for index, allocation in enumerate(plan.units.allocations):
        fragment = contract.fragments[index] if index < len(contract.fragments) else None
        page = pdf_pages[index] if index < len(pdf_pages) else None
        if fragment is not None and (
            fragment.format != allocation.format.value
            or fragment.face_ids != allocation.face_ids
        ):
            failures.append(
                _failure(
                    "malformed_a3_allocation",
                    f"{allocation.fragment_id} contract allocation differs from plan",
                    allocation.face_ids,
                )
            )
        if page is None:
            continue
        is_a4 = _matches_size(page, 210, 297)
        is_a3 = _matches_size(page, 420, 297)
        if not is_a4 and not is_a3:
            failures.append(
                _failure(
                    "unsupported_pdf_page_size",
                    f"object {index + 1} is {page.width_mm:.2f} x {page.height_mm:.2f} mm",
                    allocation.face_ids,
                )
            )
        elif allocation.format.value == "a3" and not is_a3:
            failures.append(
                _failure(
                    "malformed_a3_allocation",
                    f"{allocation.fragment_id} is planned A3 but rendered at A4 geometry",
                    allocation.face_ids,
                )
            )
        elif allocation.format.value == "a4" and not is_a4:
            failures.append(
                _failure(
                    "unsupported_pdf_page_size",
                    f"{allocation.fragment_id} is planned A4 but rendered at another size",
                    allocation.face_ids,
                )
            )

    case_count = sum(face.role.value == "case_study" for face in plan.faces)
    if case_count != profile.case_count:
        failures.append(
            _failure(
                "wrong_case_count",
                f"profile requires {profile.case_count}, plan has {case_count}",
            )
        )
    present_roles = {face.role for face in plan.faces}
    for role in profile.required_roles:
        if role not in present_roles:
            failures.append(
                _failure(
                    "required_role_missing",
                    f"stable role {role.value} is absent",
                )
            )
    return tuple(failures)
