"""Task 7: the six remaining family slices render distinct, atlas-bound anatomy.

Each family maps one shared content pool into its own regions so that raster
differences come from family and variant CSS, never from content. The atlas
binding test keeps every family's anatomy anchored to real reference faces:
atlas_face_ids must exist in the reference atlas, and every required region
must carry a real anatomy role (never the generic "supporting" fallback).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageChops


RENDERER_ROOT = Path(__file__).resolve().parent.parent
RESEARCH_ROOT = RENDERER_ROOT.parent
PREPROCESSOR_ROOT = RESEARCH_ROOT / "preprocessor"
for path in (RENDERER_ROOT, RESEARCH_ROOT, PREPROCESSOR_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from composition_registry.registry import load_registry  # noqa: E402
from contracts_v3.render_contract import FrozenRenderContractV3  # noqa: E402
from families.anatomy import FAMILY_REGION_ANATOMY  # noqa: E402
from render_v3 import RenderBundleV3, render_contract_html, render_v3  # noqa: E402


ROOT = Path(__file__).resolve().parents[3]
REGISTRY_PATH = ROOT / "research" / "composition_registry" / "families" / "dmc-v1.json"
ATLAS_PATH = ROOT / "research" / "reference-atlas" / "reference-atlas.json"

REF_TITLE = "content.face.01.title"
REF_LEDE = "content.face.01.lede"
REF_SUPPORT = "content.face.01.support"
REF_PROOF_LABEL = "content.face.01.proof_label"
STEP_REFS = tuple(f"content.face.01.step.{index}" for index in ("a", "b", "c", "d", "e"))
OBJECTION_REFS = tuple(f"content.face.01.objection.{index}" for index in ("a", "b", "c"))
REBUTTAL_REFS = tuple(f"content.face.01.rebuttal.{index}" for index in ("a", "b", "c"))

CONTENT = {
    REF_TITLE: "Die Bearbeitung sinkt von zwei Stunden auf Minuten",
    REF_LEDE: (
        "Der Betrieb verliert jede Woche bezahlte Stunden an eine Aufgabe, "
        "die niemand bestellt hat. Die folgenden Seiten zeigen den Mechanismus "
        "dahinter und den dokumentierten Weg hinaus."
    ),
    REF_SUPPORT: (
        "Jede Unterbrechung kostet Anlauf, und der Anlauf ist unsichtbar. "
        "Erst die Messung macht ihn sichtbar und damit verhandelbar."
    ),
    REF_PROOF_LABEL: "Dokumentierte Bearbeitungszeit pro Vorgang",
    STEP_REFS[0]: "Aufnahme des dokumentierten Ist-Zustands im Betrieb",
    STEP_REFS[1]: "Messung der tatsächlichen Bearbeitungszeit pro Vorgang",
    STEP_REFS[2]: "Aufbau des neuen Ablaufs entlang der Messung",
    STEP_REFS[3]: "Begleiteter Testlauf mit dem bestehenden Team",
    STEP_REFS[4]: "Übergabe mit dokumentiertem Ergebnis",
    OBJECTION_REFS[0]: "Das funktioniert in unserem Betrieb nicht",
    OBJECTION_REFS[1]: "Dafür fehlt uns die Zeit im Tagesgeschäft",
    OBJECTION_REFS[2]: "Das haben wir schon einmal versucht",
    REBUTTAL_REFS[0]: (
        "Der Ablauf wird am dokumentierten Ist-Zustand aufgebaut, "
        "nicht an einer Vorlage. Was nicht passt, wird nicht übernommen."
    ),
    REBUTTAL_REFS[1]: (
        "Die Messung läuft im bestehenden Tagesgeschäft mit. "
        "Es gibt keinen Parallelbetrieb und keine zweite Buchführung."
    ),
    REBUTTAL_REFS[2]: (
        "Der Unterschied ist die Messung vor der Änderung. "
        "Erst wenn der Verlust sichtbar ist, trägt die neue Routine."
    ),
}
CLAIMS = {"claim.duration": "20 Minuten", "claim.before": "120 Minuten"}


def _heading(region_id: str, content_ref: str, *, level: int, index: int) -> dict:
    return {
        "kind": "heading",
        "element_id": f"face.01.{region_id}.heading.{index:02d}",
        "region_id": region_id,
        "content_ref": content_ref,
        "level": level,
        "required_visibility": True,
    }


def _body(region_id: str, content_ref: str, *, index: int) -> dict:
    return {
        "kind": "body",
        "element_id": f"face.01.{region_id}.body.{index:02d}",
        "region_id": region_id,
        "content_ref": content_ref,
        "required_visibility": True,
    }


def _stat(region_id: str) -> dict:
    return {
        "kind": "stat",
        "element_id": f"face.01.{region_id}.stat.01",
        "region_id": region_id,
        "claim_id": "claim.duration",
        "label_content_ref": REF_PROOF_LABEL,
        "required_visibility": True,
    }


def _process(region_id: str) -> dict:
    return {
        "kind": "process",
        "element_id": f"face.01.{region_id}.process.01",
        "region_id": region_id,
        "item_content_refs": list(STEP_REFS),
        "required_visibility": True,
    }


def _pairs(region_id: str) -> list[dict]:
    elements: list[dict] = []
    for index, (objection, rebuttal) in enumerate(
        zip(OBJECTION_REFS, REBUTTAL_REFS), start=1
    ):
        elements.append(_heading(region_id, objection, level=3, index=index))
        elements.append(_body(region_id, rebuttal, index=index))
    return elements


# One shared content pool mapped into each family's own regions. Families that
# are compared against each other receive the same element multiset so that
# only the family anatomy can make the pages differ.
FAMILY_PLANS: dict[str, list[dict]] = {
    "theory_interpretation": [
        _heading("principle", REF_TITLE, level=1, index=1),
        _body("principle", REF_LEDE, index=1),
        _body("principle", REF_SUPPORT, index=2),
        _process("mechanism"),
        _stat("mechanism"),
    ],
    "mechanism_spread": [
        _heading("method_frame", REF_TITLE, level=1, index=1),
        _body("method_frame", REF_LEDE, index=1),
        _body("method_frame", REF_SUPPORT, index=2),
        _stat("method_frame"),
        _process("steps"),
    ],
    "summary_synthesis": [
        _heading("synthesis", REF_TITLE, level=1, index=1),
        _body("synthesis", REF_LEDE, index=1),
        _body("synthesis", REF_SUPPORT, index=2),
        _stat("payoff"),
    ],
    "editorial_lead": [
        _heading("headline", REF_TITLE, level=1, index=1),
        _body("narrative", REF_LEDE, index=1),
        _body("narrative", REF_SUPPORT, index=2),
        _stat("anchor"),
    ],
    "objection_response": [
        _heading("objection_frame", REF_TITLE, level=1, index=1),
        _body("objection_frame", REF_LEDE, index=1),
        *_pairs("responses"),
    ],
    "false_belief_stack": [
        _heading("opening", REF_TITLE, level=1, index=1),
        _body("opening", REF_LEDE, index=1),
        *_pairs("beliefs"),
    ],
    "collaboration_pathway": [
        _heading("commitment", REF_TITLE, level=1, index=1),
        _body("commitment", REF_LEDE, index=1),
        _stat("commitment"),
        _process("pathway"),
    ],
}

# variant pairs under test for the six newly sliced families
VARIANT_PAIRS = {
    "theory_interpretation": ("diagram_split", "comparison_band"),
    "mechanism_spread": ("stacked_path", "horizontal_spread"),
    "summary_synthesis": ("proof_rail", "comparison_dashboard"),
    "objection_response": ("numbered_ladder", "response_grid"),
    "collaboration_pathway": ("step_cards", "guided_path"),
    "false_belief_stack": ("numbered_rows", "card_grid"),
}

# each of the six families must differ from at least one neighbor rendered
# with an equivalent element multiset built from the same content pool
CROSS_FAMILY_PAIRS = (
    ("theory_interpretation", "diagram_split", "mechanism_spread", "stacked_path"),
    ("summary_synthesis", "proof_rail", "editorial_lead", "proof_rail"),
    ("objection_response", "numbered_ladder", "false_belief_stack", "numbered_rows"),
    ("collaboration_pathway", "step_cards", "mechanism_spread", "stacked_path"),
)

# required-region anatomy the DOM must carry, per family
EXPECTED_REGION_ROLES = {
    "theory_interpretation": {"principle": "argument", "mechanism": "mechanism_field"},
    "mechanism_spread": {"method_frame": "verdict", "steps": "process_path"},
    "summary_synthesis": {"synthesis": "verdict", "payoff": "result_band"},
    "objection_response": {
        "objection_frame": "verdict",
        "responses": "objection_ladder",
    },
    "collaboration_pathway": {"commitment": "result_band", "pathway": "process_path"},
    "false_belief_stack": {"opening": "verdict", "beliefs": "objection_ladder"},
}


_REGISTRY = None


def registry_model():
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = load_registry(REGISTRY_PATH, atlas_path=ATLAS_PATH)
    return _REGISTRY


def bundle() -> RenderBundleV3:
    return RenderBundleV3(
        content_by_ref=dict(CONTENT),
        claim_values=dict(CLAIMS),
        asset_paths={},
    )


def _content_refs(elements: list[dict]) -> list[str]:
    refs: set[str] = set()
    for element in elements:
        for key in ("content_ref", "label_content_ref"):
            if key in element:
                refs.add(element[key])
        refs.update(element.get("item_content_refs", []))
    return sorted(refs)


def slice_contract(family_id: str, variant_id: str) -> FrozenRenderContractV3:
    elements = FAMILY_PLANS[family_id]
    registry = load_registry(REGISTRY_PATH, atlas_path=ATLAS_PATH)
    family = next(
        item for item in registry.families if item.family_id == family_id
    )
    family_version = family.version
    assignments: list[dict] = []
    for element in elements:
        region_id = element["region_id"]
        for assignment in assignments:
            if assignment["region_id"] == region_id:
                assignment["element_ids"].append(element["element_id"])
                break
        else:
            assignments.append(
                {"region_id": region_id, "element_ids": [element["element_id"]]}
            )
    payload = {
        "schema_version": "3.0",
        "contract_id": f"contract.slice.{family_id}.{variant_id}",
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
        "content_refs": _content_refs(elements),
        "claim_refs": sorted(
            {element["claim_id"] for element in elements if "claim_id" in element}
        ),
        "asset_refs": [],
        "artifact_hashes": {"contract_payload": "a" * 64},
    }
    return FrozenRenderContractV3.model_validate(payload)


def mean_pixel_difference(first: Image.Image, second: Image.Image) -> float:
    if first.size != second.size:
        return 255.0
    difference = ImageChops.difference(first, second)
    histogram = difference.histogram()
    total = sum(count * value for value, count in enumerate(histogram))
    return total / (first.size[0] * first.size[1])


@pytest.fixture(scope="module")
def raster(tmp_path_factory):
    base = tmp_path_factory.mktemp("family-slices")
    cache: dict[tuple[str, str], Image.Image] = {}

    def get(family_id: str, variant_id: str) -> Image.Image:
        key = (family_id, variant_id)
        if key not in cache:
            result = render_v3(
                slice_contract(family_id, variant_id),
                bundle(),
                registry_model(),
                output_dir=base / f"{family_id}-{variant_id}",
            )
            cache[key] = Image.open(result.png_paths[0]).convert("L")
        return cache[key]

    return get


@pytest.mark.parametrize("family_id", sorted(VARIANT_PAIRS))
def test_variants_render_visibly_different_pages(family_id: str, raster) -> None:
    first_variant, second_variant = VARIANT_PAIRS[family_id]
    difference = mean_pixel_difference(
        raster(family_id, first_variant), raster(family_id, second_variant)
    )
    assert difference > 1.0, (
        f"{family_id} variants {first_variant} and {second_variant} render "
        f"nearly identical pages (mean pixel diff {difference:.3f})"
    )


@pytest.mark.parametrize(
    ("family_id", "variant_id", "other_family_id", "other_variant_id"),
    CROSS_FAMILY_PAIRS,
)
def test_families_render_visibly_different_from_neighbors(
    family_id: str,
    variant_id: str,
    other_family_id: str,
    other_variant_id: str,
    raster,
) -> None:
    difference = mean_pixel_difference(
        raster(family_id, variant_id), raster(other_family_id, other_variant_id)
    )
    assert difference > 2.0, (
        f"{family_id} renders nearly identically to {other_family_id} "
        f"under equivalent content (mean pixel diff {difference:.3f})"
    )


@pytest.mark.parametrize("family_id", sorted(EXPECTED_REGION_ROLES))
def test_family_dom_carries_family_anatomy(family_id: str) -> None:
    variant_id = VARIANT_PAIRS[family_id][0]
    html = render_contract_html(
        slice_contract(family_id, variant_id), bundle(), registry_model()
    ).html

    assert f'data-anatomy="{family_id}"' in html
    for region_id, role in EXPECTED_REGION_ROLES[family_id].items():
        assert f'class="region region-{region_id} anatomy-{role}"' in html, (
            f"{family_id}.{region_id} does not carry anatomy role {role}"
        )
        assert f'data-region-id="{region_id}" data-anatomy-role="{role}"' in html
    assert 'data-anatomy-role="supporting"' not in html, (
        f"{family_id} renders a required region with the generic supporting role"
    )


def test_atlas_faces_exist_and_anatomy_covers_required_regions() -> None:
    """Bind every family's anatomy to its atlas grounding.

    The atlas_face_ids of every registry family must exist in the reference
    atlas, the anatomy map must only reference regions the registry defines,
    and every required region must carry a real anatomy role.
    """
    registry_raw = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    atlas_face_ids = {
        face["id"]
        for face in json.loads(ATLAS_PATH.read_text(encoding="utf-8"))["faces"]
    }

    for family in registry_raw["families"]:
        family_id = family["family_id"]
        assert family["atlas_face_ids"], f"{family_id} has no atlas grounding"
        unknown = set(family["atlas_face_ids"]) - atlas_face_ids
        assert not unknown, (
            f"{family_id} references atlas faces that do not exist: {sorted(unknown)}"
        )

        anatomy = FAMILY_REGION_ANATOMY.get(family_id, {})
        region_ids = {region["region_id"] for region in family["regions"]}
        stale = set(anatomy) - region_ids
        assert not stale, (
            f"{family_id} anatomy references regions the registry does not "
            f"define: {sorted(stale)}"
        )
        for region in family["regions"]:
            if not region["required"]:
                continue
            role = anatomy.get(region["region_id"], "supporting")
            assert role != "supporting", (
                f"{family_id}.{region['region_id']} is required but is left on "
                "the generic supporting role"
            )
