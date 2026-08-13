"""Deterministic renderer for frozen semantic v3 contracts."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Literal

import fitz
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from playwright.sync_api import sync_playwright
from pydantic import BaseModel, ConfigDict, Field


HERE = Path(__file__).resolve().parent
RESEARCH_ROOT = HERE.parent
PREPROCESSOR_ROOT = RESEARCH_ROOT / "preprocessor"
for dependency_root in (RESEARCH_ROOT, PREPROCESSOR_ROOT):
    if str(dependency_root) not in sys.path:
        sys.path.insert(0, str(dependency_root))

from composition_registry.schema import CompositionRegistry  # noqa: E402
from contract_loader_v3 import load_render_contract  # noqa: E402
from contracts_v3.render_contract import FrozenRenderContractV3  # noqa: E402
from families.registry import (  # noqa: E402
    FamilyRendererRegistry,
    default_registry,
)


class StrictFrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RenderBundleV3(StrictFrozenModel):
    content_by_ref: dict[str, str]
    claim_values: dict[str, str]
    asset_paths: dict[str, str]
    # The client's brand accent drives the --accent token at render time.
    # None keeps the neutral house default from tokens.css.
    brand_accent: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    # The full brand token set drives the component library's token contract
    # (type ramp, spacing scale, colour roles). Empty keeps the house set.
    brand_tokens: dict[str, str] = Field(default_factory=dict)
    # Which Layer-B profile decides how this client LOOKS. The grammar
    # forbids defaulting any axis, so an unknown id is refused rather than
    # quietly rendered with house defaults - which is what every build did
    # before this, and why every client came out identical.
    brand_profile_id: str | None = None


class RenderDegradation(StrictFrozenModel):
    fragment_id: str
    from_family_id: str
    to_family_id: str
    code: Literal["named_draft_fallback"] = "named_draft_fallback"
    detail: str


class HtmlRenderResult(StrictFrozenModel):
    html: str
    degradations: tuple[RenderDegradation, ...] = ()


class RenderResultV3(StrictFrozenModel):
    raw_pdf_path: Path
    html_path: Path
    metadata_path: Path
    png_paths: tuple[Path, ...]
    degradations: tuple[RenderDegradation, ...]


class RenderFailureV3(RuntimeError):
    def __init__(
        self,
        *,
        code: str,
        detail: str,
        face_ids: tuple[str, ...],
        element_ids: tuple[str, ...] = (),
    ) -> None:
        self.owner_stage = "renderer"
        self.code = code
        self.detail = detail
        self.face_ids = face_ids
        self.element_ids = element_ids
        super().__init__(f"{code}: {detail}")


def _normalize_pdf_metadata(pdf_path: Path) -> None:
    """Remove Chromium wall-clock metadata while preserving rendered objects."""
    normalized_path = pdf_path.with_suffix(".normalized.pdf")
    with fitz.open(pdf_path) as document:
        metadata = dict(document.metadata)
        metadata.update(
            {
                "creator": "DMC v3 renderer",
                "producer": "DMC v3 renderer",
                "creationDate": "D:20000101000000Z",
                "modDate": "D:20000101000000Z",
            }
        )
        document.set_metadata(metadata)
        document.save(
            normalized_path,
            garbage=4,
            clean=True,
            deflate=True,
            no_new_id=True,
        )
    normalized_path.replace(pdf_path)


def _validate_bundle(contract: FrozenRenderContractV3, bundle: RenderBundleV3) -> None:
    missing_content = set(contract.content_refs) - set(bundle.content_by_ref)
    missing_claims = set(contract.claim_refs) - set(bundle.claim_values)
    missing_assets = set(contract.asset_refs) - set(bundle.asset_paths)
    if missing_content or missing_claims or missing_assets:
        details = []
        if missing_content:
            details.append(f"content={','.join(sorted(missing_content))}")
        if missing_claims:
            details.append(f"claims={','.join(sorted(missing_claims))}")
        if missing_assets:
            details.append(f"assets={','.join(sorted(missing_assets))}")
        raise RenderFailureV3(
            code="render_bundle_incomplete",
            detail="; ".join(details),
            face_ids=tuple(
                face_id for fragment in contract.fragments for face_id in fragment.face_ids
            ),
        )


def _fallback_variant(
    registry: CompositionRegistry,
    family_id: str,
    version: str,
) -> str:
    # Families version independently, so resolve the fallback by family id
    # across every registered version, never the primary fragment's version.
    family = next(
        item
        for item in registry.families
        if item.family_id == family_id
    )
    return sorted(variant.variant_id for variant in family.variants)[0]


_LIBRARY_STYLESHEETS = ("components.css", "viz.css", "viz_compare.css")


def _library_token_root(bundle: "RenderBundleV3") -> str:
    """Compile the component library's token contract from the client brand.

    The preset macros are token-only; without this root they would render
    unstyled. Compiling it from the envelope's brand tokens is what makes the
    devices carry the client's own colour and type, not a house default.
    """
    tokens = dict(bundle.brand_tokens)
    if bundle.brand_accent is not None:
        tokens.setdefault("brand_accent", bundle.brand_accent)
    required = {
        "brand_primary": "#171714",
        "brand_accent": "#c94e2c",
        "brand_neutral_dark": "#171714",
        "brand_neutral_mid": "#656158",
        "brand_neutral_light": "#f5f1e8",
        "font_heading": "DMC Sans",
        "font_body": "DMC Sans",
        "qr_target_url": "",
        "company_name_short": "",
        "company_url_display": "",
    }
    for key, fallback in required.items():
        tokens.setdefault(key, fallback)
    from brand_tokens import parse_brand_tokens
    from tokens.compile_tokens import BrandAxes, compile_tokens

    axes = BrandAxes()
    profile = _brand_profile(bundle)
    if profile is not None:
        axes = BrandAxes(**profile.to_axes_kwargs())
        # Axes P and A are the client's actual colour. Without this the
        # profile switched type and texture while every report kept the
        # same accent, which is why two clients still looked alike.
        tokens["brand_primary"] = profile.primary_dark
        tokens["brand_neutral_dark"] = profile.primary_dark
        tokens["brand_accent"] = profile.accents.data_emphasis
        tokens["font_heading"] = profile.font_head
        tokens["font_body"] = profile.font_body
    css_root, _ = compile_tokens(parse_brand_tokens(tokens), axes)
    return css_root


def _brand_profile(bundle: "RenderBundleV3"):
    """This client's Layer-B profile, or None when the build declares none.

    A declared id that has no profile raises: the grammar's hard rule is
    that a missing axis is a loud config error, never a default.
    """
    if not bundle.brand_profile_id:
        return None
    from tokens.brand_profile import profile_for

    return profile_for(bundle.brand_profile_id)


def _compose_stylesheet(bundle: "RenderBundleV3") -> str:
    """Token root, then the component library, then the v3 family anatomy."""
    parts = [_library_token_root(bundle)]
    for name in _LIBRARY_STYLESHEETS:
        path = HERE / "styles" / name
        if path.is_file():
            parts.append(path.read_text(encoding="utf-8"))
    parts.extend(
        (HERE / "styles_v3" / name).read_text(encoding="utf-8")
        for name in ("tokens.css", "families.css", "axes.css")
    )
    css = "\n".join(parts)
    font_uri = (HERE / "fonts" / "SourceSans3[wght].ttf").resolve().as_uri()
    css = css.replace("__FONT_SOURCE_SANS__", font_uri)
    if bundle.brand_accent is not None:
        css = css.replace("--accent: #c94e2c;", f"--accent: {bundle.brand_accent.lower()};")
    return css


def render_contract_html(
    contract_source: FrozenRenderContractV3 | Path | dict,
    bundle: RenderBundleV3,
    registry: CompositionRegistry,
    *,
    renderer_registry: FamilyRendererRegistry | None = None,
) -> HtmlRenderResult:
    contract = load_render_contract(contract_source, registry)
    _validate_bundle(contract, bundle)
    renderers = renderer_registry or default_registry()
    fragments_html: list[str] = []
    degradations: list[RenderDegradation] = []

    for fragment in contract.fragments:
        key = (
            fragment.composition.family_id,
            fragment.composition.family_version,
        )
        try:
            fragment_html = renderers.render(key, fragment, bundle)
        except Exception as error:
            fallback_id = fragment.fallback_family_id
            if contract.mode != "draft" or fallback_id is None:
                raise RenderFailureV3(
                    code="family_render_failed",
                    detail=f"{fragment.fragment_id}: {error}",
                    face_ids=fragment.face_ids,
                    element_ids=tuple(element.element_id for element in fragment.elements),
                ) from error
            fallback_family = next(
                (
                    item
                    for item in registry.families
                    if item.family_id == fallback_id
                ),
                None,
            )
            if fallback_family is None:
                raise RenderFailureV3(
                    code="named_fallback_failed",
                    detail=f"{fragment.fragment_id}: unknown fallback family {fallback_id}",
                    face_ids=fragment.face_ids,
                    element_ids=tuple(element.element_id for element in fragment.elements),
                ) from error
            fallback_key = (fallback_id, fallback_family.version)
            try:
                _fallback_variant(registry, *fallback_key)
                fragment_html = renderers.render(
                    fallback_key,
                    fragment,
                    bundle,
                    rendered_family_id=fallback_id,
                )
            except Exception as fallback_error:
                raise RenderFailureV3(
                    code="named_fallback_failed",
                    detail=f"{fragment.fragment_id}: {fallback_error}",
                    face_ids=fragment.face_ids,
                    element_ids=tuple(element.element_id for element in fragment.elements),
                ) from fallback_error
            degradations.append(
                RenderDegradation(
                    fragment_id=fragment.fragment_id,
                    from_family_id=fragment.composition.family_id,
                    to_family_id=fallback_id,
                    detail=str(error),
                )
            )
        fragments_html.append(fragment_html)

    css = _compose_stylesheet(bundle)
    environment = Environment(
        loader=FileSystemLoader(HERE / "templates_v3"),
        undefined=StrictUndefined,
        autoescape=True,
    )
    profile = _brand_profile(bundle)
    # The treatment axes reach CSS as attributes on the body, which is the
    # route axes N, HC, G and X never had. Without it the stylesheet cannot
    # tell a ghost_numeral client from a dark_box one.
    axis_attributes = ""
    if profile is not None:
        axis_attributes = " " + " ".join(
            f'{name}="{value}"' for name, value in profile.data_attributes().items()
        )
    html = environment.get_template("base.html.jinja").render(
        contract_id=contract.contract_id,
        css=css,
        fragments_html="".join(fragments_html),
        axis_attributes=axis_attributes,
    )
    return HtmlRenderResult(html=html, degradations=tuple(degradations))


def render_v3(
    contract_source: FrozenRenderContractV3 | Path | dict,
    bundle: RenderBundleV3,
    registry: CompositionRegistry,
    *,
    output_dir: Path,
    renderer_registry: FamilyRendererRegistry | None = None,
) -> RenderResultV3:
    contract = load_render_contract(contract_source, registry)
    html_result = render_contract_html(
        contract,
        bundle,
        registry,
        renderer_registry=renderer_registry,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    html_path = output_dir / "report.rendered.html"
    raw_pdf_path = output_dir / "report.raw.pdf"
    metadata_path = output_dir / "render-metadata.json"
    html_path.write_text(html_result.html, encoding="utf-8")

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(html_path.resolve().as_uri(), wait_until="networkidle")
            page.emulate_media(media="print")
            page.pdf(
                path=str(raw_pdf_path),
                print_background=True,
                prefer_css_page_size=True,
                tagged=True,
            )
            browser.close()
    except Exception as error:
        raise RenderFailureV3(
            code="chromium_pdf_failed",
            detail=str(error),
            face_ids=tuple(
                face_id for fragment in contract.fragments for face_id in fragment.face_ids
            ),
        ) from error

    _normalize_pdf_metadata(raw_pdf_path)

    png_paths: list[Path] = []
    with fitz.open(raw_pdf_path) as document:
        for index, pdf_page in enumerate(document, start=1):
            png_path = output_dir / f"report.raw-p{index}.png"
            pdf_page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False).save(
                png_path
            )
            png_paths.append(png_path)

    metadata = {
        "schema_version": "3.0",
        "contract_id": contract.contract_id,
        "mode": contract.mode,
        "fragment_count": len(contract.fragments),
        "face_count": sum(len(fragment.face_ids) for fragment in contract.fragments),
        "pdf_object_count": len(png_paths),
        "ghostscript_invoked": False,
        "degradations": [
            degradation.model_dump(mode="json")
            for degradation in html_result.degradations
        ],
        "artifact_hashes": contract.artifact_hashes,
    }
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return RenderResultV3(
        raw_pdf_path=raw_pdf_path,
        html_path=html_path,
        metadata_path=metadata_path,
        png_paths=tuple(png_paths),
        degradations=html_result.degradations,
    )
