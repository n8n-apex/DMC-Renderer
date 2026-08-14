"""No family may refuse Richard's own densest page of its kind."""

from __future__ import annotations

import collections
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
REGISTRY = ROOT / "research" / "composition_registry" / "families" / "dmc-v1.json"
ATLAS = ROOT / "research" / "reference-atlas" / "reference-atlas.json"

# Which editorial roles each family is built to carry.
FAMILY_ROLES = {
    "editorial_lead": ["cover", "outlook"],
    "evidence_wall": ["about", "trust_proof"],
    "theory_interpretation": ["theory", "status_quo"],
    "false_belief_stack": ["false_beliefs"],
    "case_narrative": ["case_study"],
    "mechanism_spread": ["mechanism"],
    "summary_synthesis": ["summary"],
    "objection_response": ["objections"],
    "collaboration_pathway": ["collaboration"],
    "closing_cta": ["cta"],
}


def _reference_word_counts() -> dict[str, list[int]]:
    atlas = json.loads(ATLAS.read_text(encoding="utf-8"))
    counts: dict[str, list[int]] = collections.defaultdict(list)
    for face in atlas["faces"]:
        if face.get("role") and face.get("word_count"):
            counts[face["role"]].append(face["word_count"])
    return counts


def _family_capacity(family: dict, language: str = "de") -> int:
    return sum(
        next(c["max_words"] for c in region["capacities"] if c["language"] == language)
        for region in family["regions"]
    )


@pytest.mark.parametrize("family_id", sorted(FAMILY_ROLES))
def test_the_family_can_hold_the_densest_reference_page_of_its_kind(family_id) -> None:
    """A capacity that refuses the reference is a wrong standard, not a strict one.

    theory_interpretation allowed 510 words against his 521, and closing_cta
    allowed 175 against his 209, so both would have rejected pages he has
    actually shipped.
    """
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    family = next(f for f in registry["families"] if f["family_id"] == family_id)
    counts = _reference_word_counts()
    reference = [w for role in FAMILY_ROLES[family_id] for w in counts.get(role, [])]
    if not reference:
        pytest.skip(f"no reference faces for {family_id}")

    capacity = _family_capacity(family)

    assert capacity >= max(reference), (
        f"{family_id} holds {capacity} words but his densest page of this kind "
        f"is {max(reference)}"
    )
