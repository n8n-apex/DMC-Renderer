from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[3]
PREPROCESSOR_ROOT = ROOT / "research" / "preprocessor"
QUALITY_ROOT = ROOT / "research" / "quality_loop"
for path in (PREPROCESSOR_ROOT, QUALITY_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from contracts_v3.materialization import (  # noqa: E402
    BoundingBoxMm,
    ElementObservation,
    MaterializationLedger,
    MaterializationViolation,
)
from contracts_v3.render_contract import FrozenRenderContractV3  # noqa: E402
from gates.materialization_v3 import (  # noqa: E402
    MaterializationGatePolicy,
    check_materialization_v3,
)
from gates.pixels_v3 import (  # noqa: E402
    PixelSample,
    check_pixel_gates_v3,
    load_pixel_policy,
)


POLICY_PATH = QUALITY_ROOT / "policies" / "pixel_policy_v1.json"


def contract() -> FrozenRenderContractV3:
    element_ids = ("face.01.body.01", "face.01.body.02")
    return FrozenRenderContractV3.model_validate(
        {
            "contract_id": "contract.materialization-gate",
            "mode": "ship",
            "product_profile_id": "test",
            "fragments": [
                {
                    "fragment_id": "fragment.01",
                    "format": "a4",
                    "face_ids": ["face.01"],
                    "composition": {
                        "family_id": "editorial_lead",
                        "family_version": "1.0.0",
                        "variant_id": "proof_rail",
                        "theme_id": "light",
                    },
                    "elements": [
                        {
                            "kind": "body",
                            "element_id": element_ids[0],
                            "region_id": "narrative",
                            "content_ref": "content.body.1",
                            "required_visibility": True,
                        },
                        {
                            "kind": "body",
                            "element_id": element_ids[1],
                            "region_id": "narrative",
                            "content_ref": "content.body.2",
                            "required_visibility": True,
                        },
                    ],
                    "region_assignments": [
                        {"region_id": "narrative", "element_ids": list(element_ids)}
                    ],
                    "expected_materialization": {
                        "required_element_ids": list(element_ids),
                        "minimum_font_pt": {element_id: 10 for element_id in element_ids},
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
    box: BoundingBoxMm,
    visible: bool = True,
    foreground: str = "rgb(20, 20, 20)",
    background: str = "rgb(245, 245, 245)",
    intersections: tuple[str, ...] = (),
) -> ElementObservation:
    return ElementObservation(
        element_id=element_id,
        face_id="face.01",
        region_id="narrative",
        content_ref="content.body.1",
        bounding_box_mm=box,
        font_size_pt=10,
        line_height_pt=13,
        visible=visible,
        clipped=False,
        overflowed=False,
        foreground_color=foreground,
        background_color=background,
        intersecting_element_ids=intersections,
    )


def test_materialization_gate_names_hidden_low_contrast_and_unsafe_bounds() -> None:
    frozen = contract()
    first_id, second_id = frozen.fragments[0].expected_materialization.required_element_ids
    ledger = MaterializationLedger(
        contract_id=frozen.contract_id,
        observations=(
            observation(
                first_id,
                box=BoundingBoxMm(x=2, y=2, width=50, height=10),
                foreground="rgb(120, 120, 120)",
                background="rgb(130, 130, 130)",
            ),
            observation(
                second_id,
                box=BoundingBoxMm(x=20, y=30, width=50, height=10),
                visible=False,
            ),
        ),
        missing_required_element_ids=(),
        violations=(
            MaterializationViolation(
                code="element_hidden",
                element_ids=(second_id,),
                detail="hidden",
            ),
        ),
    )

    failures = check_materialization_v3(
        frozen,
        ledger,
        policy=MaterializationGatePolicy(safe_inset_mm=6, minimum_contrast_ratio=4.5),
    )

    assert {"element_hidden", "low_contrast", "content_outside_safe_bounds"} <= {
        failure.code for failure in failures
    }


def test_overlap_is_hard_unless_the_exact_pair_is_allowed() -> None:
    frozen = contract()
    first_id, second_id = frozen.fragments[0].expected_materialization.required_element_ids
    ledger = MaterializationLedger(
        contract_id=frozen.contract_id,
        observations=(
            observation(
                first_id,
                box=BoundingBoxMm(x=20, y=20, width=50, height=20),
                intersections=(second_id,),
            ),
            observation(
                second_id,
                box=BoundingBoxMm(x=30, y=25, width=50, height=20),
                intersections=(first_id,),
            ),
        ),
        missing_required_element_ids=(),
        violations=(
            MaterializationViolation(
                code="element_overlap",
                element_ids=(first_id, second_id),
                detail="overlap",
            ),
        ),
    )

    blocked = check_materialization_v3(frozen, ledger)
    allowed = check_materialization_v3(
        frozen,
        ledger,
        policy=MaterializationGatePolicy(
            allowed_overlap_pairs=((first_id, second_id),)
        ),
    )

    assert "element_overlap" in {failure.code for failure in blocked}
    assert "element_overlap" not in {failure.code for failure in allowed}


def test_missing_required_element_remains_a_hard_failure() -> None:
    frozen = contract()
    missing_id = frozen.fragments[0].expected_materialization.required_element_ids[1]
    ledger = MaterializationLedger(
        contract_id=frozen.contract_id,
        observations=(),
        missing_required_element_ids=(missing_id,),
        violations=(
            MaterializationViolation(
                code="required_element_missing",
                element_ids=(missing_id,),
                detail="missing",
            ),
        ),
    )

    failures = check_materialization_v3(frozen, ledger)

    assert failures[0].severity.value == "hard"
    assert failures[0].code == "required_element_missing"


def test_accent_budget_is_measured_and_opt_out_is_explicit(tmp_path: Path) -> None:
    image_path = tmp_path / "accent.png"
    image = Image.new("RGB", (100, 100), (245, 245, 245))
    for x in range(50):
        for y in range(100):
            image.putpixel((x, y), (200, 50, 30))
    image.save(image_path)
    policy = load_pixel_policy(POLICY_PATH)

    blocked = check_pixel_gates_v3(
        (
            PixelSample(
                face_id="face.01",
                family_id="editorial_lead",
                image_path=str(image_path),
                accent_rgb=(200, 50, 30),
            ),
        ),
        policy,
    )
    opted_out_policy = policy.model_copy(
        update={
            "families": {
                **policy.families,
                "editorial_lead": policy.families["editorial_lead"].model_copy(
                    update={"accent_budget_opt_out": True}
                ),
            }
        }
    )
    allowed = check_pixel_gates_v3(
        (
            PixelSample(
                face_id="face.01",
                family_id="editorial_lead",
                image_path=str(image_path),
                accent_rgb=(200, 50, 30),
            ),
        ),
        opted_out_policy,
    )

    assert "accent_budget_exceeded" in {failure.code for failure in blocked}
    # The opt-out silences only the accent budget; the other measured pixel
    # features remain active, so we assert the accent failure alone is gone
    # rather than an empty failure tuple.
    assert "accent_budget_exceeded" not in {failure.code for failure in allowed}


def test_pixel_policy_covers_every_promoted_family() -> None:
    policy = load_pixel_policy(POLICY_PATH)

    assert len(policy.families) == 10
    assert all(
        family.accent_budget_opt_out or family.max_accent_fraction > 0
        for family in policy.families.values()
    )
