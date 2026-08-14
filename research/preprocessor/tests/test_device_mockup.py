"""Tests for device-mockup compositing (synthetic placeholder frame)."""
from __future__ import annotations

import pytest
from PIL import Image

from stages.device_mockup import composite_device_mockup


def _make_frame(path) -> None:
    frame = Image.new("RGBA", (100, 200), (0, 0, 255, 255))
    frame.paste((0, 0, 0, 0), (20, 20, 80, 180))  # transparent screen hole
    frame.save(path)


def test_creative_shows_through_screen(tmp_path) -> None:
    fp = tmp_path / "frame.png"
    _make_frame(fp)
    cp = tmp_path / "creative.png"
    Image.new("RGB", (10, 10), (255, 0, 0)).save(cp)
    out = tmp_path / "out.png"
    result = composite_device_mockup(
        creative_path=cp, frame_path=fp, screen_box=(20, 20, 80, 180), output_path=out,
    )
    assert result.size == (100, 200)
    r, g, b, _ = result.getpixel((50, 100))
    assert r > 200 and g < 60 and b < 60
    r2, g2, b2, _ = result.getpixel((5, 5))
    assert b2 > 200 and r2 < 60
    assert out.exists()


def test_invalid_screen_box_raises(tmp_path) -> None:
    fp = tmp_path / "f.png"
    _make_frame(fp)
    cp = tmp_path / "c.png"
    Image.new("RGB", (4, 4), (0, 255, 0)).save(cp)
    with pytest.raises(ValueError):
        composite_device_mockup(creative_path=cp, frame_path=fp, screen_box=(50, 50, 50, 50))


def test_missing_creative_raises(tmp_path) -> None:
    fp = tmp_path / "f.png"
    _make_frame(fp)
    with pytest.raises(FileNotFoundError):
        composite_device_mockup(
            creative_path=tmp_path / "nope.png", frame_path=fp, screen_box=(20, 20, 80, 180),
        )


def test_returns_rgba(tmp_path) -> None:
    fp = tmp_path / "f.png"
    _make_frame(fp)
    cp = tmp_path / "c.png"
    Image.new("RGB", (8, 8), (0, 255, 0)).save(cp)
    result = composite_device_mockup(creative_path=cp, frame_path=fp, screen_box=(20, 20, 80, 180))
    assert result.mode == "RGBA"


def test_resize_uses_explicit_bicubic(tmp_path, monkeypatch) -> None:
    """PRD §9.1 specifies BICUBIC. The resample filter must be passed
    EXPLICITLY (not left to Pillow's version-dependent default) so the golden
    output is deterministic across Pillow versions."""
    fp = tmp_path / "f.png"
    _make_frame(fp)
    cp = tmp_path / "c.png"
    Image.new("RGB", (10, 10), (255, 0, 0)).save(cp)

    # Capture the OUTERMOST resize call (the one device_mockup makes).
    # Pillow's resize() recurses internally with the resolved default filter,
    # so we must inspect the first call's own arguments, not the recursive one.
    calls: list = []
    orig_resize = Image.Image.resize

    def spy_resize(self, size, *args, **kwargs):
        calls.append((args, kwargs))
        return orig_resize(self, size, *args, **kwargs)

    monkeypatch.setattr(Image.Image, "resize", spy_resize)
    composite_device_mockup(creative_path=cp, frame_path=fp, screen_box=(20, 20, 80, 180))

    first_args, first_kwargs = calls[0]
    resample = first_kwargs.get("resample")
    if resample is None and first_args:
        resample = first_args[0]
    assert resample == Image.BICUBIC, (
        "device_mockup must pass resample=BICUBIC explicitly, not rely on "
        f"Pillow's version-dependent default (got {resample!r})"
    )


def test_composite_is_byte_identical_across_runs(tmp_path) -> None:
    """Compositing the SAME inputs twice yields byte-identical PNG output
    (determinism guarantee, PRD §9.1)."""
    fp = tmp_path / "frame.png"
    _make_frame(fp)
    cp = tmp_path / "creative.png"
    # A gradient downscaled to the screen box exercises the resample filter.
    grad = Image.new("RGB", (40, 40))
    grad.putdata([(x * 6, y * 6, (x + y) * 3) for y in range(40) for x in range(40)])
    grad.save(cp)

    out1 = tmp_path / "out1.png"
    out2 = tmp_path / "out2.png"
    composite_device_mockup(creative_path=cp, frame_path=fp, screen_box=(20, 20, 80, 180), output_path=out1)
    composite_device_mockup(creative_path=cp, frame_path=fp, screen_box=(20, 20, 80, 180), output_path=out2)
    assert out1.read_bytes() == out2.read_bytes()
