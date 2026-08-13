"""Task 8: A3 spreads must yield face-level rasters, not shared page images."""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image


DMC_ROOT = Path(__file__).resolve().parent.parent
if str(DMC_ROOT) not in sys.path:
    sys.path.insert(0, str(DMC_ROOT))

from build_v3 import face_rasters  # noqa: E402


class _Composition:
    family_id = "case_narrative"


class _Fragment:
    def __init__(self, format_value: str, face_ids: tuple[str, ...]) -> None:
        self.format = format_value
        self.face_ids = face_ids
        self.composition = _Composition()


class _Contract:
    def __init__(self, fragments) -> None:
        self.fragments = fragments


def _page(path: Path, *, width: int, height: int) -> Path:
    image = Image.new("RGB", (width, height), (240, 236, 226))
    for x in range(0, width // 2):
        image.putpixel((x, height // 2), (10, 10, 10))
    image.save(path)
    return path


def test_a4_pages_pass_through_as_their_own_face_raster(tmp_path: Path) -> None:
    page = _page(tmp_path / "p1.png", width=800, height=1131)
    contract = _Contract([_Fragment("a4", ("face.01",))])

    rasters = face_rasters(contract, (page,), tmp_path / "faces")

    assert set(rasters) == {"face.01"}
    with Image.open(rasters["face.01"]) as image:
        assert image.size == (800, 1131)


def test_a3_pages_are_split_into_left_and_right_face_rasters(tmp_path: Path) -> None:
    page = _page(tmp_path / "p1.png", width=1600, height=1131)
    contract = _Contract([_Fragment("a3", ("face.07", "face.08"))])

    rasters = face_rasters(contract, (page,), tmp_path / "faces")

    assert set(rasters) == {"face.07", "face.08"}
    with Image.open(rasters["face.07"]) as left, Image.open(rasters["face.08"]) as right:
        assert left.size == (800, 1131)
        assert right.size == (800, 1131)
        # The synthetic ink line lives only in the left half.
        assert left.getpixel((10, 1131 // 2)) == (10, 10, 10)
        assert right.getpixel((10, 1131 // 2)) != (10, 10, 10)


def test_mixed_document_assigns_every_face_its_own_raster(tmp_path: Path) -> None:
    a4_page = _page(tmp_path / "p1.png", width=800, height=1131)
    a3_page = _page(tmp_path / "p2.png", width=1600, height=1131)
    contract = _Contract(
        [
            _Fragment("a4", ("face.01",)),
            _Fragment("a3", ("face.02", "face.03")),
        ]
    )

    rasters = face_rasters(contract, (a4_page, a3_page), tmp_path / "faces")

    assert set(rasters) == {"face.01", "face.02", "face.03"}
    assert len({str(path) for path in rasters.values()}) == 3
