from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


RENDERER_ROOT = Path(__file__).resolve().parent.parent
RESEARCH_ROOT = RENDERER_ROOT.parent
PREPROCESSOR_ROOT = RESEARCH_ROOT / "preprocessor"
for path in (RENDERER_ROOT, RESEARCH_ROOT, PREPROCESSOR_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from contracts_v3.materialization import (  # noqa: E402
    BoundingBoxMm,
    ElementObservation,
)
from contracts_v3.render_contract import FrozenRenderContractV3  # noqa: E402
from materialization import (  # noqa: E402
    MaterializationFailure,
    probe_materialization,
    reconcile_materialization,
)


def contract(*, format: str = "a4", face_ids: tuple[str, ...] = ("face.01",)):
    elements = [
        {
            "kind": "body",
            "element_id": f"{face_ids[-1]}.narrative.body.01",
            "region_id": "narrative",
            "content_ref": "content.body.1",
            "required_visibility": True,
        },
        {
            "kind": "body",
            "element_id": f"{face_ids[-1]}.narrative.body.02",
            "region_id": "narrative",
            "content_ref": "content.body.2",
            "required_visibility": True,
        },
    ]
    element_ids = [item["element_id"] for item in elements]
    return FrozenRenderContractV3.model_validate(
        {
            "contract_id": "contract.materialization",
            "mode": "ship",
            "product_profile_id": "dmc_house_20_face",
            "fragments": [
                {
                    "fragment_id": "fragment.01",
                    "format": format,
                    "face_ids": list(face_ids),
                    "composition": {
                        "family_id": "theory_interpretation",
                        "family_version": "1.0.0",
                        "variant_id": "comparison_band",
                        "theme_id": "light",
                    },
                    "elements": elements,
                    "region_assignments": [
                        {"region_id": "narrative", "element_ids": element_ids}
                    ],
                    "expected_materialization": {
                        "required_element_ids": element_ids,
                        "minimum_font_pt": {item: 10 for item in element_ids},
                    },
                }
            ],
            "content_refs": ["content.body.1", "content.body.2"],
            "claim_refs": [],
            "asset_refs": [],
            "artifact_hashes": {"contract_payload": "a" * 64},
        }
    )


def observation(
    element_id: str,
    *,
    visible: bool = True,
    clipped: bool = False,
    overflowed: bool = False,
    font_size_pt: float = 11,
    box: BoundingBoxMm | None = None,
    intersections: tuple[str, ...] = (),
) -> ElementObservation:
    return ElementObservation(
        element_id=element_id,
        face_id="face.01",
        region_id="narrative",
        content_ref="content.body.1",
        bounding_box_mm=box or BoundingBoxMm(x=10, y=10, width=30, height=10),
        font_size_pt=font_size_pt,
        line_height_pt=13,
        visible=visible,
        clipped=clipped,
        overflowed=overflowed,
        foreground_color="rgb(0, 0, 0)",
        background_color="rgb(255, 255, 255)",
        intersecting_element_ids=intersections,
    )


def test_reconciliation_names_clip_hidden_overlap_overflow_and_font_failures() -> None:
    frozen = contract()
    first_id, second_id = frozen.fragments[0].expected_materialization.required_element_ids
    ledger = reconcile_materialization(
        frozen,
        (
            observation(
                first_id,
                clipped=True,
                overflowed=True,
                font_size_pt=9,
                intersections=(second_id,),
            ),
            observation(second_id, visible=False, intersections=(first_id,)),
        ),
        fail_on_hard=False,
    )

    assert set(ledger.violation_codes) == {
        "element_clipped",
        "element_hidden",
        "element_overlap",
        "element_overflow",
        "font_below_contract_minimum",
    }


def test_missing_required_element_is_a_hard_materialization_failure() -> None:
    frozen = contract()
    first_id = frozen.fragments[0].expected_materialization.required_element_ids[0]

    with pytest.raises(MaterializationFailure) as caught:
        reconcile_materialization(frozen, (observation(first_id),))

    assert caught.value.code == "required_element_missing"
    assert caught.value.ledger.missing_required_element_ids


def test_a3_coordinates_are_face_relative_and_ledger_is_written(tmp_path: Path) -> None:
    frozen = contract(format="a3", face_ids=("face.01", "face.02"))
    first_id, second_id = frozen.fragments[0].expected_materialization.required_element_ids
    html_path = tmp_path / "probe.html"
    html_path.write_text(
        f"""<!doctype html><style>
        * {{ box-sizing: border-box; }} body {{ margin: 0; }}
        .fragment {{ width: 420mm; height: 297mm; display: grid; grid-template-columns: 210mm 210mm; }}
        .face {{ width: 210mm; height: 297mm; position: relative; }}
        .target {{ position: absolute; margin: 0; left: 10mm; top: 12mm; width: 30mm; height: 8mm; font-size: 12pt; line-height: 14pt; }}
        </style><section class="fragment">
        <article class="face" data-face-id="face.01"></article>
        <article class="face" data-face-id="face.02">
          <p class="target" data-element-id="{first_id}" data-region-id="narrative" data-content-ref="content.body.1">One</p>
          <p class="target" style="top:30mm" data-element-id="{second_id}" data-region-id="narrative" data-content-ref="content.body.2">Two</p>
        </article></section>""",
        encoding="utf-8",
    )
    output_path = tmp_path / "materialization-ledger.json"

    ledger = probe_materialization(
        html_path,
        frozen,
        output_path=output_path,
        fail_on_hard=False,
    )

    assert output_path.is_file()
    assert json.loads(output_path.read_text(encoding="utf-8"))["schema_version"] == "3.0"
    assert ledger.observations[0].face_id == "face.02"
    assert ledger.observations[0].bounding_box_mm.x == pytest.approx(10, abs=0.3)
    assert ledger.observations[0].bounding_box_mm.y == pytest.approx(12, abs=0.3)
