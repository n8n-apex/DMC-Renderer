from __future__ import annotations

from enum import Enum
from typing import Iterable

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FragmentFormat(str, Enum):
    A4 = "a4"
    A3 = "a3"


class FaceAllocation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    fragment_id: str = Field(min_length=1)
    format: FragmentFormat
    face_ids: tuple[str, ...]

    @model_validator(mode="after")
    def validate_face_count(self) -> "FaceAllocation":
        expected = 1 if self.format is FragmentFormat.A4 else 2
        if len(self.face_ids) != expected:
            raise ValueError(f"{self.format.value} requires {expected} face ids")
        return self


class DocumentUnits(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    allocations: tuple[FaceAllocation, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_faces(self) -> "DocumentUnits":
        face_ids = [face_id for item in self.allocations for face_id in item.face_ids]
        if len(face_ids) != len(set(face_ids)):
            raise ValueError("face ids must be unique across fragments")
        return self

    @property
    def face_count(self) -> int:
        return sum(len(item.face_ids) for item in self.allocations)

    @property
    def fragment_count(self) -> int:
        return len(self.allocations)

    @property
    def expected_pdf_objects(self) -> int:
        return self.fragment_count

    @classmethod
    def from_formats(cls, formats: Iterable[FragmentFormat | str]) -> "DocumentUnits":
        allocations: list[FaceAllocation] = []
        next_face = 1
        for fragment_index, raw_format in enumerate(formats, start=1):
            fragment_format = FragmentFormat(raw_format)
            faces_in_fragment = 1 if fragment_format is FragmentFormat.A4 else 2
            face_ids = tuple(
                f"face.{face_index:02d}"
                for face_index in range(next_face, next_face + faces_in_fragment)
            )
            allocations.append(
                FaceAllocation(
                    fragment_id=f"fragment.{fragment_index:02d}",
                    format=fragment_format,
                    face_ids=face_ids,
                )
            )
            next_face += faces_in_fragment
        return cls(allocations=tuple(allocations))
