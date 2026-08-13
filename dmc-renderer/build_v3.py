"""Isolated end-to-end v3 build from source envelope to observed raw PDF."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Literal

import fitz
from PIL import Image, ImageDraw
from pydantic import BaseModel, ConfigDict, Field, ValidationError


DMC_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = DMC_ROOT.parent
RESEARCH_ROOT = PROJECT_ROOT / "research"
PREPROCESSOR_ROOT = RESEARCH_ROOT / "preprocessor"
V3_RENDERER_ROOT = RESEARCH_ROOT / "v7-renderer"
for dependency_root in (DMC_ROOT, RESEARCH_ROOT, PREPROCESSOR_ROOT, V3_RENDERER_ROOT):
    if str(dependency_root) not in sys.path:
        sys.path.insert(0, str(dependency_root))

from build_live import build_precomposition_package_v3  # noqa: E402
from composition_registry.registry import load_registry  # noqa: E402
from contracts_v3.build_manifest import PrecompositionBundleV3, stable_hash  # noqa: E402
from materialization import probe_materialization  # noqa: E402
from render_v3 import RenderBundleV3, render_v3  # noqa: E402
from stages.materialize_render_contract_v3 import (  # noqa: E402
    materialize_render_contract_v3,
)
from stages.plan_compositions_v3 import (  # noqa: E402
    FaceCompositionFacts,
    load_composition_policy,
    plan_compositions_v3,
)


REGISTRY_PATH = RESEARCH_ROOT / "composition_registry" / "families" / "dmc-v1.json"
ATLAS_PATH = RESEARCH_ROOT / "reference-atlas" / "reference-atlas.json"
POLICY_PATH = PREPROCESSOR_ROOT / "policies" / "composition_scoring_v1.json"
PRODUCT_PROFILE_PATH = PREPROCESSOR_ROOT / "policies" / "dmc_house_20_face.json"
PIXEL_POLICY_PATH = RESEARCH_ROOT / "quality_loop" / "policies" / "pixel_policy_v1.json"
FONT_PATH = V3_RENDERER_ROOT / "fonts" / "SourceSans3[wght].ttf"

from contracts_v3.release import (  # noqa: E402
    FailureOwner,
    FailureSeverity,
    QualityFailure,
    ReleaseState,
)
from contracts_v3.render_contract import element_asset_refs  # noqa: E402
from contracts_v3.report_plan import load_product_profile  # noqa: E402
from contracts_v3.source_ledger import SourceAppendixV3  # noqa: E402
from quality_loop.gates.assets_v3 import (  # noqa: E402
    check_asset_bytes_v3,
    check_assets_v3,
)
from quality_loop.gates.evidence_v3 import check_evidence_v3  # noqa: E402
from quality_loop.gates.materialization_v3 import check_materialization_v3  # noqa: E402
from quality_loop.gates.pixels_v3 import (  # noqa: E402
    PixelSample,
    check_pixel_gates_v3,
    load_pixel_policy,
)
from quality_loop.gates.structure_v3 import PdfPageFact, check_structure_v3  # noqa: E402
from postprocessor.export_digital import (  # noqa: E402
    DIGITAL_EXPORT_REPORT_NAME,
    export_digital,
)
from postprocessor.export_print import (  # noqa: E402
    PRINT_PREFLIGHT_REPORT_NAME,
    export_print,
)
from postprocessor.profiles.schema import (  # noqa: E402
    assert_profile_for_export,
    load_print_profile,
)
from quality_loop.ship_gate_v3 import GateBundleV3, ShipGateV3  # noqa: E402
from artifacts.schema import (  # noqa: E402
    RETENTION_CLASSES,
    BuildRecordV3,
    VisualReviewEvidenceV3,
    retention_class_for_state,
)
from artifacts.store import FilesystemArtifactStore  # noqa: E402


class BuildV3Failure(RuntimeError):
    def __init__(
        self,
        *,
        code: str,
        detail: str,
        owner_stage: str = "v3_orchestrator",
        face_ids: tuple[str, ...] = (),
        element_ids: tuple[str, ...] = (),
    ) -> None:
        self.owner_stage = owner_stage
        self.code = code
        self.detail = detail
        self.face_ids = face_ids
        self.element_ids = element_ids
        super().__init__(f"{code}: {detail}")


class ReleaseContextV3(BaseModel):
    """Explicit human and export inputs that deterministic code cannot infer."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    visual_review_complete: bool = False
    visual_accepted: bool = False
    visual_threshold_calibrated: bool = False
    export_targets: tuple[Literal["digital", "print"], ...] = Field(
        default=("digital",),
        min_length=1,
    )
    print_profile_path: Path | None = None
    threshold_policy_path: Path | None = None
    production_export: bool = True
    # Calibration-only: the frozen synthetic asset bank lets the pipeline run
    # deterministically without real client photos. A calibration build still
    # stops at review_candidate (it needs human evidence + a real asset audit
    # to ship), so exempting it from the placeholder rule never weakens the
    # production guarantee. Production builds keep this False.
    allow_synthetic_assets: bool = False


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _pdf_page_facts(pdf_path: Path) -> tuple[PdfPageFact, ...]:
    with fitz.open(pdf_path) as document:
        return tuple(
            PdfPageFact(
                width_mm=page.rect.width * 25.4 / 72,
                height_mm=page.rect.height * 25.4 / 72,
            )
            for page in document
        )


def _accent_rgb(envelope: dict) -> tuple[int, int, int]:
    import brand_fallbacks as _fallbacks

    value = str(
        (envelope.get("brand_tokens") or {}).get("brand_accent")
        or _fallbacks.FALLBACK_V3_ACCENT
    )
    if len(value) == 7 and value.startswith("#"):
        try:
            return tuple(int(value[index : index + 2], 16) for index in (1, 3, 5))
        except ValueError:
            pass
    return (201, 78, 44)


def face_rasters(
    contract,
    png_paths: tuple[Path, ...],
    output_dir: Path,
) -> dict[str, Path]:
    """Give every face its own raster; A3 spreads split into exact halves.

    Without the split, both faces of an A3 fragment would be measured
    against the full spread image and every face-level pixel gate would be
    geometrically wrong.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    rasters: dict[str, Path] = {}
    for fragment, png_path in zip(contract.fragments, png_paths, strict=True):
        if fragment.format == "a3" and len(fragment.face_ids) == 2:
            with Image.open(png_path) as page:
                half_width = page.width // 2
                halves = (
                    page.crop((0, 0, half_width, page.height)),
                    page.crop((half_width, 0, half_width * 2, page.height)),
                )
                for face_id, half in zip(fragment.face_ids, halves):
                    target = output_dir / f"{face_id}.png"
                    half.save(target, format="PNG", optimize=False)
                    rasters[face_id] = target
        else:
            for face_id in fragment.face_ids:
                target = output_dir / f"{face_id}.png"
                with Image.open(png_path) as page:
                    page.convert("RGB").save(target, format="PNG", optimize=False)
                rasters[face_id] = target
    return rasters


def _pixel_samples(contract, png_paths: tuple[Path, ...], envelope: dict) -> tuple[PixelSample, ...]:
    samples: list[PixelSample] = []
    accent = _accent_rgb(envelope)
    rasters = face_rasters(
        contract,
        png_paths,
        Path(png_paths[0]).parent / "face-rasters" if png_paths else Path("face-rasters"),
    )
    for fragment in contract.fragments:
        face_compositions = fragment.face_compositions or ()
        for index, face_id in enumerate(fragment.face_ids):
            # A spread's halves can carry different families, so each face is
            # measured against its OWN family policy, not the sheet's first.
            family_id = (
                face_compositions[index].family_id
                if index < len(face_compositions)
                else fragment.composition.family_id
            )
            samples.append(
                PixelSample(
                    face_id=face_id,
                    family_id=family_id,
                    image_path=str(rasters[face_id]),
                    accent_rgb=accent,
                )
            )
    return tuple(samples)


def _review_pngs(png_paths: tuple[Path, ...], output_dir: Path) -> tuple[Path, ...]:
    review_paths: list[Path] = []
    for index, source_path in enumerate(png_paths, start=1):
        target_path = output_dir / f"review-p{index:02d}.png"
        with Image.open(source_path) as source:
            image = source.convert("RGB")
            draw = ImageDraw.Draw(image)
            band_height = max(32, image.height // 24)
            draw.rectangle((0, 0, image.width, band_height), fill=(23, 23, 20))
            draw.text(
                (max(12, image.width // 80), max(8, band_height // 4)),
                "REVIEW CANDIDATE | NOT FOR DELIVERY",
                fill=(245, 241, 232),
            )
            image.save(target_path, format="PNG", optimize=False)
        review_paths.append(target_path)
    return tuple(review_paths)


def _quality_failure_from_exception(error: Exception) -> QualityFailure:
    owner_value = getattr(error, "owner_stage", "quality_gate")
    try:
        owner = FailureOwner(owner_value)
    except ValueError:
        owner = FailureOwner.QUALITY_GATE
    code = getattr(error, "code", "unknown_failure_code")
    if code == "ghostscript_failed":
        code = "print_preflight_failed"
    return QualityFailure(
        owner_stage=owner,
        code=code,
        severity=FailureSeverity.HARD,
        face_ids=tuple(getattr(error, "face_ids", ()) or ()),
        element_ids=tuple(getattr(error, "element_ids", ()) or ()),
        remediation_class="repair_export_or_profile",
        detail=str(error),
    )


def _degradation_failures(render_result) -> tuple[QualityFailure, ...]:
    return tuple(
        QualityFailure(
            owner_stage=FailureOwner.RENDERER,
            code="render_degradation",
            severity=FailureSeverity.HARD,
            face_ids=(),
            remediation_class="restore_exact_family_renderer",
            detail=(
                f"{item.fragment_id}: {item.from_family_id} fell back to "
                f"{item.to_family_id}: {item.detail}"
            ),
        )
        for item in render_result.degradations
    )


def _resolve_visual_review(
    envelope: dict,
    context: ReleaseContextV3,
    raw_pdf_sha256: str,
) -> tuple[ReleaseContextV3, VisualReviewEvidenceV3 | None]:
    """Derive visual-review booleans from validated evidence only.

    Boolean approval flags never authorize ship_ready on their own; they must
    be backed by a typed evidence record whose candidate hash matches the
    exact rendered PDF and whose threshold policy hash matches the policy in
    force.
    """
    raw_evidence = envelope.get("visual_review_evidence_v3")
    if raw_evidence is None:
        if (
            context.visual_review_complete
            or context.visual_accepted
            or context.visual_threshold_calibrated
        ):
            raise BuildV3Failure(
                code="visual_review_evidence_missing",
                detail=(
                    "visual approval flags require a validated "
                    "visual_review_evidence_v3 record"
                ),
                owner_stage="release",
            )
        return context, None

    try:
        evidence = VisualReviewEvidenceV3.model_validate(raw_evidence)
    except ValidationError as error:
        raise BuildV3Failure(
            code="visual_review_evidence_invalid",
            detail=f"evidence record failed validation: {error.error_count()} errors",
            owner_stage="release",
        ) from error
    if evidence.candidate_sha256 != raw_pdf_sha256:
        raise BuildV3Failure(
            code="visual_review_evidence_invalid",
            detail=(
                "evidence candidate hash does not match the rendered PDF: "
                f"{evidence.candidate_sha256[:16]} != {raw_pdf_sha256[:16]}"
            ),
            owner_stage="release",
        )
    if context.threshold_policy_path is None or not context.threshold_policy_path.is_file():
        raise BuildV3Failure(
            code="visual_review_evidence_invalid",
            detail="no visual threshold policy is in force for this build",
            owner_stage="release",
        )
    policy_sha256 = _sha256_file(context.threshold_policy_path)
    if evidence.threshold_policy_sha256 != policy_sha256:
        raise BuildV3Failure(
            code="visual_review_evidence_invalid",
            detail="evidence threshold policy hash does not match the policy in force",
            owner_stage="release",
        )
    resolved = context.model_copy(
        update={
            "visual_review_complete": True,
            "visual_accepted": evidence.accepted,
            "visual_threshold_calibrated": True,
        }
    )
    return resolved, evidence


def _marked_review_pdf(raw_pdf_path: Path, output_path: Path, candidate_sha256: str) -> Path:
    """Copy the raw PDF with a visible review marking on every page."""
    marking = f"REVIEW-KANDIDAT {candidate_sha256[:16]} | KEINE AUSLIEFERUNG"
    with fitz.open(raw_pdf_path) as document:
        for page in document:
            page.insert_text(
                (14, 14),
                marking,
                fontsize=8,
                color=(0.78, 0.12, 0.12),
                overlay=True,
            )
        document.save(output_path)
    return output_path


def _evaluate_release(
    failures: list[QualityFailure],
    context: ReleaseContextV3,
):
    return ShipGateV3.evaluate(
        GateBundleV3(
            mode="ship",
            failures=tuple(failures),
            deterministic_checks_complete=True,
            visual_review_complete=context.visual_review_complete,
            visual_accepted=context.visual_accepted,
            visual_threshold_calibrated=context.visual_threshold_calibrated,
        )
    )


def _facts_by_face(envelope: dict) -> dict[str, FaceCompositionFacts]:
    raw_facts = envelope.get("composition_facts_v3")
    if not raw_facts:
        raise BuildV3Failure(
            code="composition_facts_missing",
            detail="v3 requires explicit semantic region facts from the writer stage",
            owner_stage="editorial_planning",
        )
    if isinstance(raw_facts, dict):
        items = raw_facts.values()
    else:
        items = raw_facts
    parsed = tuple(FaceCompositionFacts.model_validate(item) for item in items)
    facts_by_face = {item.face_id: item for item in parsed}
    if len(facts_by_face) != len(parsed):
        raise BuildV3Failure(
            code="duplicate_composition_facts",
            detail="composition fact face IDs must be unique",
            owner_stage="editorial_planning",
        )
    return facts_by_face


def _assert_fragment_format_support(plan, composition_plan, registry) -> None:
    decision_by_face = {
        decision.face_id: decision for decision in composition_plan.decisions
    }
    family_by_key = {
        (family.family_id, family.version): family for family in registry.families
    }
    for allocation in plan.units.allocations:
        for face_id in allocation.face_ids:
            selected = decision_by_face[face_id].selected
            family = family_by_key[(selected.family_id, selected.family_version)]
            if allocation.format.value not in family.formats:
                raise BuildV3Failure(
                    code="family_format_unsupported",
                    detail=(
                        f"{selected.family_id}@{selected.family_version} does not support "
                        f"{allocation.format.value}"
                    ),
                    owner_stage="composition_planner",
                    face_ids=(face_id,),
                )


def _artifact_store_root(explicit: Path | None) -> Path | None:
    if explicit is not None:
        return Path(explicit)
    configured = os.environ.get("DMC_V3_ARTIFACT_ROOT")
    if configured:
        return Path(configured)
    return None


def build_and_render_v3(
    envelope: dict,
    *,
    output_dir: Path | None = None,
    cleanup: bool = True,
    release_context: ReleaseContextV3 | None = None,
    artifact_store_root: Path | None = None,
    composition_plan_override: object | None = None,
    facts_override: dict | None = None,
) -> dict:
    """Run all frozen v3 stages with no ambient generation or network calls.

    `composition_plan_override` lets the convergence loop re-run a build with
    a conductor-patched plan. It is the ONLY way a plan enters from outside,
    and the conductor is the only thing that produces one, so a caller cannot
    quietly hand-tune a plan past the planner.
    """
    context = release_context or ReleaseContextV3()
    working_dir = output_dir or Path(tempfile.mkdtemp(prefix="dmc_v3_"))
    working_dir.mkdir(parents=True, exist_ok=True)
    try:
        precomposition = build_precomposition_package_v3(envelope, working_dir)
        precomposition_path = Path(precomposition["package_path"])
        bundle = PrecompositionBundleV3.model_validate_json(
            precomposition_path.read_text(encoding="utf-8")
        )

        registry = load_registry(REGISTRY_PATH, atlas_path=ATLAS_PATH)
        policy = load_composition_policy(POLICY_PATH)
        facts_by_face = facts_override or _facts_by_face(envelope)
        composition_plan = composition_plan_override or plan_compositions_v3(
            bundle.report_plan,
            facts_by_face,
            source_ledger=bundle.source_ledger,
            asset_ledger=bundle.asset_ledger,
            registry=registry,
            policy=policy,
            font_path=FONT_PATH,
        )
        _assert_fragment_format_support(bundle.report_plan, composition_plan, registry)
        composition_plan_path = working_dir / "composition-plan-v3.json"
        composition_plan_path.write_text(
            json.dumps(
                composition_plan.model_dump(mode="json"),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        registry_hash = _sha256_file(REGISTRY_PATH)
        policy_hash = _sha256_file(POLICY_PATH)
        artifact_hashes = {
            **bundle.manifest.artifact_hashes,
            "family_registry": registry_hash,
            "composition_policy": policy_hash,
            "composition_plan": stable_hash(composition_plan),
        }
        contract = materialize_render_contract_v3(
            bundle.report_plan,
            composition_plan,
            facts_by_face,
            source_ledger=bundle.source_ledger,
            asset_ledger=bundle.asset_ledger,
            registry=registry,
            mode="ship",
            theme_id="light",
            artifact_hashes=artifact_hashes,
        )
        contract_path = working_dir / "frozen-render-contract-v3.json"
        contract_path.write_text(
            json.dumps(
                contract.model_dump(mode="json"),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        raw_accent = str(
            (envelope.get("brand_tokens") or {}).get("brand_accent") or ""
        ).strip()
        render_bundle = RenderBundleV3(
            content_by_ref={
                content_ref: text
                for facts in facts_by_face.values()
                for content_ref, text in facts.content_by_ref.items()
            },
            claim_values={
                claim.claim_id: claim.normalized_value for claim in bundle.source_ledger.claims
            },
            asset_paths={
                asset.asset_id: asset.local_path for asset in bundle.asset_ledger.assets
            },
            brand_accent=(
                raw_accent
                if len(raw_accent) == 7 and raw_accent.startswith("#")
                else None
            ),
            brand_tokens={
                key: str(value)
                for key, value in (envelope.get("brand_tokens") or {}).items()
                if isinstance(value, str)
            },
            # The Layer-B profile decides ground, texture, headline
            # construction, belief treatment and the client's actual colour.
            # `render_v3` reads it, `brand_profile.py` loads it, and this
            # line was missing, so every client rendered on default axes and
            # two profiles as different as GEVA and Buchagentur produced
            # byte-identical output.
            brand_profile_id=envelope.get("brand_profile_id") or None,
        )
        render_result = render_v3(
            contract,
            render_bundle,
            registry,
            output_dir=working_dir,
        )
        materialization_path = working_dir / "materialization-ledger.json"
        ledger = probe_materialization(
            render_result.html_path,
            contract,
            output_path=materialization_path,
            fail_on_hard=False,
        )
        pdf_bytes = render_result.raw_pdf_path.read_bytes()
        build_hash = _sha256_bytes(
            json.dumps(
                {
                    "contract": contract.artifact_hashes["contract_payload"],
                    "html": _sha256_file(render_result.html_path),
                    "materialization": _sha256_file(materialization_path),
                    "pdf": _sha256_bytes(pdf_bytes),
                    "builder": _sha256_file(Path(__file__)),
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        )

        product_profile = load_product_profile(PRODUCT_PROFILE_PATH)
        failures = list(
            check_structure_v3(
                bundle.report_plan,
                contract,
                product_profile,
                _pdf_page_facts(render_result.raw_pdf_path),
            )
        )
        failures.extend(
            check_evidence_v3(
                contract,
                bundle.source_ledger,
                source_appendix=envelope.get("source_appendix_v3"),
            )
        )
        failures.extend(
            check_assets_v3(bundle.report_plan, bundle.asset_ledger, contract)
        )
        used_face_ids: dict[str, list[str]] = {}
        for fragment in contract.fragments:
            for element in fragment.elements:
                for asset_id in element_asset_refs(element):
                    face_id = ".".join(element.element_id.split(".", 2)[:2])
                    used_face_ids.setdefault(asset_id, []).append(face_id)
        failures.extend(
            check_asset_bytes_v3(
                bundle.asset_ledger,
                used_face_ids={
                    asset_id: tuple(dict.fromkeys(faces))
                    for asset_id, faces in used_face_ids.items()
                },
                minimum_dpi=150.0 if "print" in context.export_targets else None,
                reference_date=envelope.get("build_date_v3"),
                allow_synthetic_assets=context.allow_synthetic_assets,
            )
        )
        failures.extend(check_materialization_v3(contract, ledger))
        failures.extend(
            check_pixel_gates_v3(
                _pixel_samples(contract, render_result.png_paths, envelope),
                load_pixel_policy(PIXEL_POLICY_PATH),
            )
        )
        failures.extend(_degradation_failures(render_result))

        print_profile = None
        if "print" in context.export_targets:
            if context.print_profile_path is None:
                failures.append(
                    QualityFailure(
                        owner_stage=FailureOwner.PRINT_EXPORT,
                        code="print_profile_missing",
                        severity=FailureSeverity.HARD,
                        remediation_class="provide_validated_print_profile",
                        detail="print export requires an explicit profile path",
                    )
                )
            else:
                try:
                    print_profile = load_print_profile(context.print_profile_path)
                    assert_profile_for_export(
                        print_profile,
                        production=context.production_export,
                    )
                except Exception as error:  # validated below as a hard failure
                    failures.append(_quality_failure_from_exception(error))

        raw_pdf_sha256 = _sha256_bytes(pdf_bytes)
        context, visual_review_evidence = _resolve_visual_review(
            envelope, context, raw_pdf_sha256
        )

        gate_result = _evaluate_release(failures, context)
        review_png_paths: tuple[Path, ...] = ()
        review_pdf_path: Path | None = None
        review_pdf_bytes: bytes | None = None
        delivery_pdf_path: Path | None = None
        delivery_pdf_bytes: bytes | None = None
        digital_pdf_path: Path | None = None
        print_pdf_path: Path | None = None
        digital_export_report_path: Path | None = None
        print_preflight_report_path: Path | None = None
        if gate_result.state is ReleaseState.REVIEW_CANDIDATE:
            review_png_paths = _review_pngs(render_result.png_paths, working_dir)
            review_pdf_path = _marked_review_pdf(
                render_result.raw_pdf_path,
                working_dir / "report.review.pdf",
                raw_pdf_sha256,
            )
            review_pdf_bytes = review_pdf_path.read_bytes()
        elif gate_result.state is ReleaseState.SHIP_READY:
            try:
                if "digital" in context.export_targets:
                    digital_pdf_path = working_dir / "report.digital.pdf"
                    export_digital(
                        render_result.raw_pdf_path,
                        RESEARCH_ROOT
                        / "postprocessor"
                        / "profiles"
                        / "dmc_digital_v1.json",
                        digital_pdf_path,
                    )
                    digital_export_report_path = (
                        working_dir / DIGITAL_EXPORT_REPORT_NAME
                    )
                    delivery_pdf_path = digital_pdf_path
                if "print" in context.export_targets and print_profile is not None:
                    print_pdf_path = working_dir / "report.print.pdf"
                    export_print(
                        render_result.raw_pdf_path,
                        print_profile,
                        print_pdf_path,
                        production=context.production_export,
                    )
                    print_preflight_report_path = (
                        working_dir / PRINT_PREFLIGHT_REPORT_NAME
                    )
                    if delivery_pdf_path is None:
                        delivery_pdf_path = print_pdf_path
            except Exception as error:
                failures.append(_quality_failure_from_exception(error))
                gate_result = _evaluate_release(failures, context)
                for produced_path in (
                    digital_pdf_path,
                    print_pdf_path,
                    digital_export_report_path,
                    print_preflight_report_path,
                ):
                    if produced_path is not None:
                        produced_path.unlink(missing_ok=True)
                digital_pdf_path = None
                print_pdf_path = None
                digital_export_report_path = None
                print_preflight_report_path = None
                delivery_pdf_path = None
            if delivery_pdf_path is not None:
                delivery_pdf_bytes = delivery_pdf_path.read_bytes()

        exact_artifact_hashes: dict[str, object] = {
            "contract": _sha256_file(contract_path),
            "composition_plan": _sha256_file(composition_plan_path),
            "raw_pdf": _sha256_file(render_result.raw_pdf_path),
            "rendered_html": _sha256_file(render_result.html_path),
            "materialization_ledger": _sha256_file(materialization_path),
            "raster_pages": [_sha256_file(path) for path in render_result.png_paths],
            "review_rasters": [_sha256_file(path) for path in review_png_paths],
            "composition_policy": policy_hash,
            "family_registry": registry_hash,
        }
        if review_pdf_path is not None:
            exact_artifact_hashes["review_pdf"] = _sha256_file(review_pdf_path)
        if digital_pdf_path is not None:
            exact_artifact_hashes["digital_pdf"] = _sha256_file(digital_pdf_path)
        if print_pdf_path is not None:
            exact_artifact_hashes["print_pdf"] = _sha256_file(print_pdf_path)
        gate_report_path = working_dir / "gate-report-v3.json"
        gate_report_path.write_text(
            json.dumps(
                {
                    "schema_version": "3.0",
                    "release_state": gate_result.state.value,
                    "gate_result": gate_result.model_dump(mode="json"),
                    "artifact_hashes": exact_artifact_hashes,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        gate_report_sha256 = _sha256_file(gate_report_path)

        release_state_value = gate_result.state.value
        retention_class = retention_class_for_state(
            release_state_value,
            export_targets=(
                context.export_targets
                if gate_result.state is ReleaseState.SHIP_READY
                else ()
            ),
        )
        manifest_versions = bundle.manifest.versions
        workflow_versions = {
            field: getattr(manifest_versions, field) or "non_workflow"
            for field in (
                "workflow_contract",
                "writer_prompt",
                "schema_resolver",
                "writer_gate",
                "source_ledger",
                "claim_gate",
            )
        }
        pdf_hashes = {"raw_pdf": raw_pdf_sha256}
        if review_pdf_path is not None:
            pdf_hashes["review_pdf"] = exact_artifact_hashes["review_pdf"]
        if digital_pdf_path is not None:
            pdf_hashes["digital_pdf"] = exact_artifact_hashes["digital_pdf"]
        if print_pdf_path is not None:
            pdf_hashes["print_pdf"] = exact_artifact_hashes["print_pdf"]
        export_report_hashes: dict[str, str] = {}
        if (
            digital_export_report_path is not None
            and digital_export_report_path.is_file()
        ):
            export_report_hashes["digital_export_report"] = _sha256_file(
                digital_export_report_path
            )
        if (
            print_preflight_report_path is not None
            and print_preflight_report_path.is_file()
        ):
            export_report_hashes["print_preflight_report"] = _sha256_file(
                print_preflight_report_path
            )
        build_record = BuildRecordV3(
            build_id=f"build.{gate_report_sha256[:16]}",
            release_state=release_state_value,
            retention_class=retention_class,
            input_sha256=_sha256_bytes(
                json.dumps(
                    envelope, sort_keys=True, separators=(",", ":"), default=str
                ).encode("utf-8")
            ),
            workflow_versions=workflow_versions,
            source_ledger_sha256=bundle.manifest.artifact_hashes["source_ledger"],
            asset_ledger_sha256=bundle.manifest.artifact_hashes["asset_ledger"],
            editorial_plan_sha256=bundle.manifest.artifact_hashes["report_plan"],
            composition_plan_sha256=exact_artifact_hashes["composition_plan"],
            render_contract_sha256=exact_artifact_hashes["contract"],
            pdf_hashes=pdf_hashes,
            gate_report_sha256=gate_report_sha256,
            export_report_hashes=export_report_hashes,
            visual_review_evidence=visual_review_evidence,
        )
        artifact_manifest = None
        store_root = _artifact_store_root(artifact_store_root)
        if store_root is not None:
            retained_kinds = RETENTION_CLASSES[retention_class].retained_kinds
            candidate_files: dict[str, tuple[str, bytes | Path]] = {
                "build_record": (
                    "build-record.json",
                    (
                        json.dumps(
                            build_record.model_dump(mode="json"),
                            ensure_ascii=False,
                            indent=2,
                            sort_keys=True,
                        )
                        + "\n"
                    ).encode("utf-8"),
                ),
                "gate_report": ("gate-report-v3.json", gate_report_path),
                "render_contract": (
                    "frozen-render-contract-v3.json",
                    contract_path,
                ),
                "composition_plan": ("composition-plan-v3.json", composition_plan_path),
                "materialization_ledger": (
                    "materialization-ledger.json",
                    materialization_path,
                ),
                "rendered_html": ("report.html", render_result.html_path),
                "raw_pdf": ("report.raw.pdf", render_result.raw_pdf_path),
            }
            if review_pdf_path is not None:
                candidate_files["review_pdf"] = ("report.review.pdf", review_pdf_path)
            raw_appendix = envelope.get("source_appendix_v3")
            if raw_appendix is not None:
                try:
                    validated_appendix = SourceAppendixV3.model_validate(raw_appendix)
                except ValidationError:
                    validated_appendix = None
                if validated_appendix is not None:
                    candidate_files["source_appendix"] = (
                        "source-appendix.json",
                        (
                            json.dumps(
                                validated_appendix.model_dump(mode="json"),
                                ensure_ascii=False,
                                indent=2,
                                sort_keys=True,
                            )
                            + "\n"
                        ).encode("utf-8"),
                    )
            if digital_pdf_path is not None:
                candidate_files["digital_pdf"] = ("report.digital.pdf", digital_pdf_path)
            if print_pdf_path is not None:
                candidate_files["print_pdf"] = ("report.print.pdf", print_pdf_path)
            if (
                digital_export_report_path is not None
                and digital_export_report_path.is_file()
            ):
                candidate_files["digital_export_report"] = (
                    DIGITAL_EXPORT_REPORT_NAME,
                    digital_export_report_path,
                )
            if (
                print_preflight_report_path is not None
                and print_preflight_report_path.is_file()
            ):
                candidate_files["print_preflight_report"] = (
                    PRINT_PREFLIGHT_REPORT_NAME,
                    print_preflight_report_path,
                )
            retained_files = {
                kind: spec
                for kind, spec in candidate_files.items()
                if kind in retained_kinds
            }
            artifact_manifest = FilesystemArtifactStore(store_root).persist(
                build_record,
                files=retained_files,
            )

        result = {
            "pdf_bytes": pdf_bytes,
            "raw_pdf_bytes": pdf_bytes,
            "review_pdf_bytes": review_pdf_bytes,
            "artifact_manifest": artifact_manifest,
            "delivery_pdf_bytes": delivery_pdf_bytes,
            "pdf_path": None if cleanup else str(render_result.raw_pdf_path),
            "delivery_pdf_path": (
                None if cleanup or delivery_pdf_path is None else str(delivery_pdf_path)
            ),
            "digital_pdf_path": (
                None if cleanup or digital_pdf_path is None else str(digital_pdf_path)
            ),
            "print_pdf_path": (
                None if cleanup or print_pdf_path is None else str(print_pdf_path)
            ),
            "html_path": None if cleanup else str(render_result.html_path),
            "contract_path": None if cleanup else str(contract_path),
            "composition_plan_path": None if cleanup else str(composition_plan_path),
            # The loop needs the plan it just built from in order to patch it.
            "composition_plan": composition_plan,
            "registry": registry,
            "facts_by_face": facts_by_face,
            "materialization_ledger_path": None if cleanup else str(materialization_path),
            "gate_report_path": None if cleanup else str(gate_report_path),
            "review_png_paths": (
                [] if cleanup else [str(path) for path in review_png_paths]
            ),
            "review_png_count": len(review_png_paths),
            "release_state": gate_result.state.value,
            "failures": [
                failure.model_dump(mode="json") for failure in gate_result.failures
            ],
            "gate_report_sha256": gate_report_sha256,
            "export_report_hashes": export_report_hashes,
            "workflow_verification_bundle_sha256": envelope.get(
                "workflow_verification_bundle_sha256"
            ),
            "delivery_pdf_hash": (
                _sha256_bytes(delivery_pdf_bytes)
                if delivery_pdf_bytes is not None
                else None
            ),
            "face_count": bundle.report_plan.units.face_count,
            "fragment_count": bundle.report_plan.units.fragment_count,
            "physical_pages": len(render_result.png_paths),
            "hashes": {
                "contract": contract.artifact_hashes["contract_payload"],
                "composition_policy": policy_hash,
                "family_registry": registry_hash,
                "build": build_hash,
                "raw_pdf_sha256": raw_pdf_sha256,
            },
            "materialization_violation_count": len(ledger.violations),
        }
        return result
    finally:
        if cleanup:
            shutil.rmtree(working_dir, ignore_errors=True)
