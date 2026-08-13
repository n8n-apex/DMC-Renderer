"""Task 7: selected families and variants must not render identical pages."""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageChops


RENDERER_ROOT = Path(__file__).resolve().parent.parent
RESEARCH_ROOT = RENDERER_ROOT.parent
PREPROCESSOR_ROOT = RESEARCH_ROOT / "preprocessor"
for path in (RENDERER_ROOT, RESEARCH_ROOT, PREPROCESSOR_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from composition_registry.registry import load_registry  # noqa: E402
from contracts_v3.render_contract import FrozenRenderContractV3  # noqa: E402
from render_v3 import RenderBundleV3, render_contract_html, render_v3  # noqa: E402


ROOT = Path(__file__).resolve().parents[3]
REGISTRY_PATH = ROOT / "research" / "composition_registry" / "families" / "dmc-v1.json"
ATLAS_PATH = ROOT / "research" / "reference-atlas" / "reference-atlas.json"

CONTENT = {
    "content.face.01.title": "Die Bearbeitung sinkt von zwei Stunden auf Minuten",
    "content.face.01.lede": (
        "Der Betrieb verliert jede Woche bezahlte Stunden an eine Aufgabe, "
        "die niemand bestellt hat. Die folgenden Seiten zeigen den Mechanismus "
        "dahinter und den dokumentierten Weg hinaus."
    ),
    "content.face.01.support": (
        "Jede Unterbrechung kostet Anlauf, und der Anlauf ist unsichtbar. "
        "Erst die Messung macht ihn sichtbar."
    ),
    "content.face.01.proof_label": "Dokumentierte Bearbeitungszeit pro Vorgang",
    "content.face.01.quote": "Die Bearbeitung sank von 120 auf 20 Minuten.",
}
CLAIMS = {"claim.duration": "20 Minuten"}


def registry_model():
    return load_registry(REGISTRY_PATH, atlas_path=ATLAS_PATH)


def bundle() -> RenderBundleV3:
    return RenderBundleV3(
        content_by_ref=dict(CONTENT),
        claim_values=dict(CLAIMS),
        asset_paths={},
    )


def contract_for(family_id: str, variant_id: str) -> FrozenRenderContractV3:
    """Map one shared content pool into a family's own regions."""
    registry = registry_model()
    family = next(
        item
        for item in registry.families
        if item.family_id == family_id
    )
    family_version = family.version
    elements: list[dict] = []
    assignments: list[dict] = []
    content_pool = [
        "content.face.01.lede",
        "content.face.01.support",
        "content.face.01.proof_label",
    ]
    heading_used = False
    stat_used = False
    for region in family.regions:
        if not region.required:
            continue
        region_elements: list[str] = []
        if not heading_used and "heading" in region.allowed_element_kinds:
            element_id = f"face.01.{region.region_id}.heading.01"
            elements.append(
                {
                    "kind": "heading",
                    "element_id": element_id,
                    "region_id": region.region_id,
                    "content_ref": "content.face.01.title",
                    "level": 1,
                    "required_visibility": True,
                }
            )
            region_elements.append(element_id)
            heading_used = True
        elif "body" in region.allowed_element_kinds and content_pool:
            element_id = f"face.01.{region.region_id}.body.01"
            elements.append(
                {
                    "kind": "body",
                    "element_id": element_id,
                    "region_id": region.region_id,
                    "content_ref": content_pool.pop(0),
                    "required_visibility": True,
                }
            )
            region_elements.append(element_id)
        elif not stat_used and "stat" in region.allowed_element_kinds:
            element_id = f"face.01.{region.region_id}.stat.01"
            elements.append(
                {
                    "kind": "stat",
                    "element_id": element_id,
                    "region_id": region.region_id,
                    "claim_id": "claim.duration",
                    "label_content_ref": "content.face.01.proof_label",
                    "required_visibility": True,
                }
            )
            region_elements.append(element_id)
            stat_used = True
        elif "quote" in region.allowed_element_kinds:
            element_id = f"face.01.{region.region_id}.quote.01"
            elements.append(
                {
                    "kind": "quote",
                    "element_id": element_id,
                    "region_id": region.region_id,
                    "content_ref": "content.face.01.quote",
                    "required_visibility": True,
                }
            )
            region_elements.append(element_id)
        if region_elements:
            assignments.append(
                {"region_id": region.region_id, "element_ids": region_elements}
            )
    payload = {
        "schema_version": "3.0",
        "contract_id": f"contract.distinctness.{family_id}.{variant_id}",
        "mode": "ship",
        "product_profile_id": "dmc_house_20_face",
        "fragments": [
            {
                "fragment_id": "fragment.01",
                "format": "a4",
                "face_ids": ["face.01"],
                "composition": {
                    "family_id": family_id,
                    "family_version": family_version,
                    "variant_id": variant_id,
                    "theme_id": "light",
                },
                "elements": elements,
                "region_assignments": assignments,
                "expected_materialization": {
                    "required_element_ids": [
                        element["element_id"] for element in elements
                    ],
                    "minimum_font_pt": {},
                },
            }
        ],
        "content_refs": sorted(
            {
                element[key]
                for element in elements
                for key in ("content_ref", "label_content_ref")
                if key in element
            }
        ),
        "claim_refs": sorted(
            {element["claim_id"] for element in elements if "claim_id" in element}
        ),
        "asset_refs": [],
        "artifact_hashes": {"contract_payload": "a" * 64},
    }
    return FrozenRenderContractV3.model_validate(payload)


def first_page_raster(tmp_path: Path, label: str, contract) -> Image.Image:
    result = render_v3(
        contract,
        bundle(),
        registry_model(),
        output_dir=tmp_path / label,
    )
    return Image.open(result.png_paths[0]).convert("L")


def mean_pixel_difference(first: Image.Image, second: Image.Image) -> float:
    if first.size != second.size:
        return 255.0
    difference = ImageChops.difference(first, second)
    histogram = difference.histogram()
    total = sum(count * value for value, count in enumerate(histogram))
    return total / (first.size[0] * first.size[1])


def test_different_families_render_visibly_different_pages(tmp_path: Path) -> None:
    editorial = first_page_raster(
        tmp_path, "editorial", contract_for("editorial_lead", "proof_rail")
    )
    case = first_page_raster(
        tmp_path, "case", contract_for("case_narrative", "right_rail")
    )

    assert mean_pixel_difference(editorial, case) > 2.0


def test_meaningful_variants_render_visibly_different_pages(tmp_path: Path) -> None:
    proof_rail = first_page_raster(
        tmp_path, "proof_rail", contract_for("editorial_lead", "proof_rail")
    )
    photo_bleed = first_page_raster(
        tmp_path, "photo_bleed", contract_for("editorial_lead", "photo_bleed")
    )

    assert mean_pixel_difference(proof_rail, photo_bleed) > 1.0


def test_family_dom_carries_its_own_anatomy_classes() -> None:
    editorial = render_contract_html(
        contract_for("editorial_lead", "proof_rail"), bundle(), registry_model()
    ).html
    case = render_contract_html(
        contract_for("case_narrative", "right_rail"),
        bundle(),
        registry_model(),
    ).html

    assert 'data-anatomy="editorial_lead"' in editorial
    assert 'data-anatomy="case_narrative"' in case
    assert "anatomy-" in editorial and "anatomy-" in case
    assert editorial.replace("editorial_lead", "X").replace(
        "proof_rail", "Y"
    ) != case.replace("case_narrative", "X").replace("right_rail", "Y")
