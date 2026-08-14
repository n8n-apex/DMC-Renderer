"""Claim-reference and source-appendix gates for v3."""

from __future__ import annotations

import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
PREPROCESSOR_ROOT = HERE.parents[1] / "preprocessor"
if str(PREPROCESSOR_ROOT) not in sys.path:
    sys.path.insert(0, str(PREPROCESSOR_ROOT))

from pydantic import ValidationError  # noqa: E402

from contracts_v3.release import (  # noqa: E402
    FailureOwner,
    FailureSeverity,
    QualityFailure,
)
from contracts_v3.render_contract import (  # noqa: E402
    FrozenRenderContractV3,
    element_claim_refs,
)
from contracts_v3.source_ledger import (  # noqa: E402
    ClaimType,
    SourceAppendixV3,
    SourceLedger,
)


_SPAN_REQUIRED_TYPES = {
    ClaimType.FACT,
    ClaimType.NUMBER,
    ClaimType.QUOTE,
    ClaimType.CREDENTIAL,
    ClaimType.CERTIFICATION,
    ClaimType.NAMED_RESULT,
}


def _failure(
    code: str,
    detail: str,
    *,
    face_ids: tuple[str, ...] = (),
    element_ids: tuple[str, ...] = (),
) -> QualityFailure:
    return QualityFailure(
        owner_stage=FailureOwner.SOURCE_LEDGER,
        code=code,
        severity=FailureSeverity.HARD,
        face_ids=face_ids,
        element_ids=element_ids,
        remediation_class="ground_or_remove_claim",
        detail=detail,
    )


def check_evidence_v3(
    contract: FrozenRenderContractV3,
    source_ledger: SourceLedger,
    *,
    source_appendix: SourceAppendixV3 | dict | None,
) -> tuple[QualityFailure, ...]:
    failures: list[QualityFailure] = []
    claim_by_id = {claim.claim_id: claim for claim in source_ledger.claims}
    element_ids_by_claim: dict[str, list[str]] = {}
    face_ids_by_claim: dict[str, list[str]] = {}
    for fragment in contract.fragments:
        for element in fragment.elements:
            for current_claim_id in element_claim_refs(element):
                element_ids_by_claim.setdefault(current_claim_id, []).append(element.element_id)
                face_id = ".".join(element.element_id.split(".", 2)[:2])
                face_ids_by_claim.setdefault(current_claim_id, []).append(face_id)

    for claim_id in contract.claim_refs:
        if claim_id not in claim_by_id:
            failures.append(
                _failure(
                    "ungrounded_claim",
                    f"contract references absent claim {claim_id}",
                    face_ids=tuple(dict.fromkeys(face_ids_by_claim.get(claim_id, ()))),
                    element_ids=tuple(element_ids_by_claim.get(claim_id, ())),
                )
            )

    # Re-verify grounding shape at ship time: a rendered risky claim must
    # carry source spans or a computation chain even if it bypassed model
    # validation upstream.
    rendered_claim_ids = set(element_ids_by_claim) | set(contract.claim_refs)
    for claim_id in sorted(rendered_claim_ids):
        claim = claim_by_id.get(claim_id)
        if claim is None:
            continue
        if claim.claim_type in _SPAN_REQUIRED_TYPES and not (
            claim.source_spans or claim.computation
        ):
            failures.append(
                _failure(
                    "claim_missing_source_span",
                    f"rendered claim {claim_id} has no source span or computation",
                    face_ids=tuple(dict.fromkeys(face_ids_by_claim.get(claim_id, ()))),
                    element_ids=tuple(element_ids_by_claim.get(claim_id, ())),
                )
            )

    # Source bytes are re-hashed at gate time; the ledger's declared content
    # hash is a claim to verify, not a fact to trust.
    import hashlib

    for source in source_ledger.sources:
        actual_hash = hashlib.sha256(source.verbatim_text.encode("utf-8")).hexdigest()
        if actual_hash != source.content_hash:
            failures.append(
                _failure(
                    "source_bytes_mismatch",
                    f"source {source.source_id} content hash does not match its bytes",
                )
            )

    for grounding_failure in source_ledger.grounding_failures:
        code = (
            grounding_failure.code
            if grounding_failure.code == "ungrounded_numeric_candidate"
            else "ungrounded_claim"
        )
        failures.append(
            _failure(
                code,
                grounding_failure.detail,
                element_ids=tuple(
                    element_ids_by_claim.get(grounding_failure.claim_id or "", ())
                ),
            )
        )

    appendix: SourceAppendixV3 | None = None
    if isinstance(source_appendix, SourceAppendixV3):
        appendix = source_appendix
    elif source_appendix is not None:
        try:
            appendix = SourceAppendixV3.model_validate(source_appendix)
        except ValidationError as error:
            failures.append(
                _failure(
                    "source_appendix_invalid",
                    f"source appendix failed validation: {error.error_count()} errors",
                )
            )
    if appendix is None:
        if contract.claim_refs and not any(
            failure.code == "source_appendix_invalid" for failure in failures
        ):
            failures.append(
                _failure(
                    "source_appendix_missing",
                    "shipped claims require a source appendix artifact",
                )
            )
    else:
        rendered_source_ids = {
            source_id
            for claim_id in rendered_claim_ids
            for source_id in getattr(claim_by_id.get(claim_id), "source_ids", ())
        }
        uncovered = rendered_source_ids - appendix.covered_source_ids()
        if uncovered:
            failures.append(
                _failure(
                    "source_appendix_incomplete",
                    "appendix does not cover rendered sources: "
                    + ", ".join(sorted(uncovered)),
                )
            )
    return tuple(failures)
