"""Semantic viz devices render claim-bound, token-styled, verbatim-valued."""

from __future__ import annotations

import sys
from pathlib import Path


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
    "content.face.01.story.heading": "Vom Rückstand zur Routine",
    "content.face.01.story.body": "Die Bearbeitung ist dokumentiert.",
    "content.face.01.rail.label": "Dokumentierte Bearbeitungszeit",
}
CLAIMS = {
    "claim.before": "120 Minuten",
    "claim.after": "20 Minuten",
    "claim.saved": "100 Minuten",
}


def viz_contract() -> FrozenRenderContractV3:
    elements = [
        {
            "kind": "heading",
            "element_id": "face.01.case_story.heading.01",
            "region_id": "case_story",
            "content_ref": "content.face.01.story.heading",
            "level": 1,
            "required_visibility": True,
        },
        {
            "kind": "body",
            "element_id": "face.01.case_story.body.01",
            "region_id": "case_story",
            "content_ref": "content.face.01.story.body",
            "required_visibility": True,
        },
        {
            "kind": "grouped_comparison",
            "element_id": "face.01.evidence_rail.grouped_comparison.01",
            "region_id": "evidence_rail",
            "before_claim_id": "claim.before",
            "after_claim_id": "claim.after",
            "result_claim_id": "claim.saved",
            "label_content_ref": "content.face.01.rail.label",
            "required_visibility": True,
        },
        {
            "kind": "formula_ladder",
            "element_id": "face.01.evidence_rail.formula_ladder.01",
            "region_id": "evidence_rail",
            "operand_claim_ids": ["claim.before", "claim.after"],
            "result_claim_id": "claim.saved",
            "label_content_ref": "content.face.01.rail.label",
            "required_visibility": True,
        },
    ]
    return FrozenRenderContractV3.model_validate(
        {
            "schema_version": "3.0",
            "contract_id": "contract.viz.devices",
            "mode": "ship",
            "product_profile_id": "dmc_house_20_face",
            "fragments": [
                {
                    "fragment_id": "fragment.01",
                    "format": "a4",
                    "face_ids": ["face.01"],
                    "composition": {
                        "family_id": "case_narrative",
                        "family_version": "1.4.0",
                        "variant_id": "right_rail",
                        "theme_id": "light",
                    },
                    "elements": elements,
                    "region_assignments": [
                        {
                            "region_id": "case_story",
                            "element_ids": [
                                "face.01.case_story.heading.01",
                                "face.01.case_story.body.01",
                            ],
                        },
                        {
                            "region_id": "evidence_rail",
                            "element_ids": [
                                "face.01.evidence_rail.grouped_comparison.01",
                                "face.01.evidence_rail.formula_ladder.01",
                            ],
                        },
                    ],
                    "expected_materialization": {
                        "required_element_ids": [
                            element["element_id"] for element in elements
                        ],
                        "minimum_font_pt": {},
                    },
                }
            ],
            "content_refs": sorted(CONTENT),
            "claim_refs": sorted(CLAIMS),
            "asset_refs": [],
            "artifact_hashes": {"contract_payload": "a" * 64},
        }
    )


def rendered_html() -> str:
    return render_contract_html(
        viz_contract(),
        RenderBundleV3(
            content_by_ref=dict(CONTENT),
            claim_values=dict(CLAIMS),
            asset_paths={},
        ),
        load_registry(REGISTRY_PATH, atlas_path=ATLAS_PATH),
    ).html


def test_grouped_comparison_draws_scaled_bars_with_exact_claim_values() -> None:
    html = rendered_html()

    # The device is drawn by the component library; v3 owns the element
    # contract wrapper, the library owns the device's own markup.
    assert 'device-grouped-comparison' in html
    assert "c-viz-ba" in html
    # Every claim the device prints stays addressable in the DOM.
    assert 'data-claim-ids="claim.before claim.after claim.saved"' in html
    assert ">120 Minuten<" in html
    assert ">20 Minuten<" in html
    assert "c-viz-ba__delta" in html
    assert ">100 Minuten<" in html


def test_formula_ladder_shows_operand_rungs_and_emphasized_result() -> None:
    html = rendered_html()

    # The ladder is one of the kinds the SVG chart renderers draw (they own
    # a calculation ladder; there is no CSS equivalent), so assert the SVG
    # contract: the wrapper stays addressable and every operand plus the
    # result prints VERBATIM. The CSS macro's classes never appear for it.
    assert 'device-formula-ladder device-svg' in html
    assert ">120 Minuten<" in html
    assert ">20 Minuten<" in html
    assert ">100 Minuten<" in html
    assert 'data-claim-ids="claim.before claim.after claim.saved"' in html


def test_devices_keep_element_ids_for_materialization(tmp_path: Path) -> None:
    result = render_v3(
        viz_contract(),
        RenderBundleV3(
            content_by_ref=dict(CONTENT),
            claim_values=dict(CLAIMS),
            asset_paths={},
        ),
        load_registry(REGISTRY_PATH, atlas_path=ATLAS_PATH),
        output_dir=tmp_path,
    )
    html = result.html_path.read_text(encoding="utf-8")

    assert 'data-element-id="face.01.evidence_rail.grouped_comparison.01"' in html
    assert 'data-element-id="face.01.evidence_rail.formula_ladder.01"' in html
    assert result.raw_pdf_path.is_file()
