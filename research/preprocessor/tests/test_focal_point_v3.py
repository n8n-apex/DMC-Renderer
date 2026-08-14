"""An image is cropped to its subject, not to its middle."""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[3]
RENDERER = ROOT / "research" / "v7-renderer"
if str(RENDERER) not in sys.path:
    sys.path.insert(0, str(RENDERER))

from families.focal_point import focal_point, object_position  # noqa: E402


def _image_with_subject(tmp_path: Path, cx: float, cy: float) -> Path:
    """A flat frame with one detailed blob at (cx, cy) as fractions."""
    im = Image.new("RGB", (600, 400), (200, 200, 200))
    draw = ImageDraw.Draw(im)
    x, y = int(600 * cx), int(400 * cy)
    # High-frequency structure is what edge density finds.
    for offset in range(0, 60, 4):
        draw.ellipse([x - offset, y - offset, x + offset, y + offset],
                     outline=(10, 10, 10), width=2)
    path = tmp_path / f"subject_{cx}_{cy}.png"
    im.save(path)
    return path


def test_a_subject_on_the_left_anchors_left(tmp_path) -> None:
    x, _ = focal_point(str(_image_with_subject(tmp_path, 0.2, 0.5)))

    assert x < 40.0


def test_a_subject_on_the_right_anchors_right(tmp_path) -> None:
    x, _ = focal_point(str(_image_with_subject(tmp_path, 0.8, 0.5)))

    assert x > 60.0


def test_a_low_subject_anchors_low(tmp_path) -> None:
    """The founder shot's subject sits at 63% down; centring would cut it."""
    _, y = focal_point(str(_image_with_subject(tmp_path, 0.5, 0.8)))

    assert y > 60.0


def test_a_flat_image_centres_rather_than_guessing(tmp_path) -> None:
    """No dominant subject means centring is correct, not a fallback."""
    flat = tmp_path / "flat.png"
    Image.new("RGB", (600, 400), (180, 180, 180)).save(flat)

    assert focal_point(str(flat)) == (50.0, 50.0)


def test_the_anchor_never_pins_to_the_very_edge(tmp_path) -> None:
    """A crop anchored at 0% clips the subject against the frame."""
    x, y = focal_point(str(_image_with_subject(tmp_path, 0.02, 0.02)))

    assert 15.0 <= x <= 85.0 and 15.0 <= y <= 85.0


def test_an_unreadable_file_centres_instead_of_raising(tmp_path) -> None:
    broken = tmp_path / "broken.png"
    broken.write_bytes(b"not an image")

    assert focal_point(str(broken)) == (50.0, 50.0)


def test_it_emits_a_css_object_position(tmp_path) -> None:
    value = object_position(_image_with_subject(tmp_path, 0.3, 0.7))

    assert value.count("%") == 2
    assert value.replace("%", "").replace(".", "").replace(" ", "").isdigit()


def test_the_real_founder_shot_anchors_below_centre() -> None:
    """The measurement that motivated this: 62.9% down, not 50%."""
    founder = ROOT / "research" / "preprocessor" / "client_assets" / "apex" / "founder.png"
    if not founder.exists():
        return
    _, y = focal_point(str(founder))

    assert y > 55.0
