from __future__ import annotations

import pytest
from pydantic import ValidationError

from contracts_v3.units import DocumentUnits, FaceAllocation, FragmentFormat


def test_a3_spread_counts_as_two_faces_and_one_fragment() -> None:
    units = DocumentUnits.from_formats(["a4", "a3", "a4"])

    assert units.face_count == 4
    assert units.fragment_count == 3
    assert units.expected_pdf_objects == 3
    assert units.allocations[1].face_ids == ("face.02", "face.03")


def test_a4_fragment_requires_one_face_id() -> None:
    with pytest.raises(ValidationError, match="requires 1 face ids"):
        FaceAllocation(
            fragment_id="fragment.01",
            format=FragmentFormat.A4,
            face_ids=("face.01", "face.02"),
        )


def test_a3_fragment_requires_two_face_ids() -> None:
    with pytest.raises(ValidationError, match="requires 2 face ids"):
        FaceAllocation(
            fragment_id="fragment.01",
            format=FragmentFormat.A3,
            face_ids=("face.01",),
        )


def test_face_ids_must_be_unique_across_fragments() -> None:
    with pytest.raises(ValidationError, match="face ids must be unique"):
        DocumentUnits(
            allocations=(
                FaceAllocation(
                    fragment_id="fragment.01",
                    format=FragmentFormat.A4,
                    face_ids=("face.01",),
                ),
                FaceAllocation(
                    fragment_id="fragment.02",
                    format=FragmentFormat.A4,
                    face_ids=("face.01",),
                ),
            )
        )


def test_unit_names_are_never_implicit() -> None:
    with pytest.raises(ValidationError):
        DocumentUnits.model_validate({"count": 20})
