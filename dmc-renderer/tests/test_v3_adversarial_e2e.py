from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest


TESTS_ROOT = Path(__file__).resolve().parent
DMC_ROOT = TESTS_ROOT.parent
FIXTURE_ROOT = DMC_ROOT / "fixtures" / "v3"
if str(DMC_ROOT) not in sys.path:
    sys.path.insert(0, str(DMC_ROOT))
if str(TESTS_ROOT) not in sys.path:
    sys.path.insert(0, str(TESTS_ROOT))

from build_v3 import ReleaseContextV3, build_and_render_v3  # noqa: E402
from test_build_v3 import valid_envelope  # noqa: E402


INVALID_FIXTURES = (
    "wrong-face-count.json",
    "five-cases.json",
    "ungrounded-number.json",
    "missing-portrait.json",
    "overcapacity.json",
)


def _recipe(name: str) -> dict:
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


def _apply_recipe(envelope: dict, recipe: dict) -> dict:
    mutated = copy.deepcopy(envelope)
    mutation = recipe["mutation"]
    if mutation == "none":
        return mutated
    if mutation == "remove-final-planned-face":
        mutated["editorial_brief_v3"]["faces"].pop()
        mutated["editorial_brief_v3"]["formats"].pop()
        return mutated
    if mutation == "promote-two-theory-faces-to-cases":
        theory_faces = [
            face
            for face in mutated["editorial_brief_v3"]["faces"]
            if face["role"] == "theory"
        ][:2]
        for index, face in enumerate(theory_faces, start=4):
            face["role"] = "case_study"
            face["case_id"] = f"case.{index}"
        return mutated
    if mutation == "insert-ungrounded-83-percent":
        mutated["payload"]["pages"][0]["data"]["body"] += " 83% garantiert."
        return mutated
    if mutation == "remove-first-case-identity-asset":
        mutated["assets"] = [
            asset
            for asset in mutated["assets"]
            if not (
                asset["semantic_class"] == "identity"
                and asset["allowed_face_ids"] == ["face.06"]
            )
        ]
        return mutated
    if mutation == "expand-first-face-copy-beyond-all-capacities":
        facts = mutated["composition_facts_v3"][0]
        for content_ref in facts["content_by_ref"]:
            facts["content_by_ref"][content_ref] = "Überlanger Inhalt " * 2500
        return mutated
    raise AssertionError(f"unknown fixture mutation: {mutation}")


def _earliest_failure(error: Exception) -> tuple[str, str]:
    failures = tuple(getattr(error, "failures", ()) or ())
    if failures:
        first = failures[0]
        return first.owner_stage, first.code
    owner = getattr(error, "owner_stage", "unknown")
    elimination_codes = tuple(getattr(error, "elimination_codes", ()) or ())
    code = elimination_codes[0] if elimination_codes else getattr(error, "code", type(error).__name__)
    return owner, code


def test_valid_fixture_reaches_review_candidate_and_has_no_unvalidated_delivery(
    tmp_path: Path,
) -> None:
    """A structurally-valid 20-face envelope must NEVER deliver an unvalidated
    PDF, whatever its release state.

    Since the 2026-08-08 pixel-policy recalibration to Richard's corpus, the
    synthetic envelope is rejected on the density blockers (no real photos;
    the documented G24 gap). The load-bearing assertion is the second one:
    no delivery bytes are ever emitted without validated evidence. A
    future client fixture with real photographs should reach review_candidate,
    which is why it stays in the accepted set."""
    recipe = _recipe("valid-20-face.json")
    envelope = _apply_recipe(valid_envelope(tmp_path / "assets"), recipe)

    result = build_and_render_v3(
        envelope,
        output_dir=tmp_path / "valid",
        cleanup=False,
        release_context=ReleaseContextV3(allow_synthetic_assets=True),
    )

    assert result["release_state"] in recipe["expected_release_states"]
    assert result["delivery_pdf_bytes"] is None


@pytest.mark.parametrize("fixture_name", INVALID_FIXTURES)
def test_invalid_fixture_fails_at_earliest_owner_without_delivery(
    fixture_name: str,
    tmp_path: Path,
) -> None:
    recipe = _recipe(fixture_name)
    envelope = _apply_recipe(
        valid_envelope(tmp_path / fixture_name.removesuffix(".json")),
        recipe,
    )

    result = None
    with pytest.raises(Exception) as caught:
        result = build_and_render_v3(
            envelope,
            output_dir=tmp_path / f"run-{fixture_name}",
            cleanup=False,
        )

    assert _earliest_failure(caught.value) == (
        recipe["expected_owner"],
        recipe["expected_code"],
    )
    assert result is None or result["delivery_pdf_bytes"] is None
