"""Tests for restorer.py — conservative, swappable print-quality ensurer.

The print report wants ~2500px on the long edge (A4 @ ~300dpi). The research
finding is that heavily upscaling a real founder's face reads as "waxy"/fake,
so the rule is: PREFER the high-res source (no-op if already big enough),
upscale CONSERVATIVELY (capped), and keep the backend swappable so a
face-restore backend (CodeFormer/GFPGAN) can be plugged in later.

Fixtures are plain PIL images in tmp (no network, no torch).
"""
from __future__ import annotations

from PIL import Image

from stages.scrape_founder_assets.restorer import (
    MAX_UPSCALE_FACTOR,
    LanczosBackend,
    RestoreResult,
    Restorer,
)


def _write_image(path, size):
    """Write a solid RGB image of the given (w, h)."""
    Image.new("RGB", size, (123, 200, 50)).save(path)
    return str(path)


def test_high_res_source_returned_as_is(tmp_path):
    """A source already at/above the target long edge is returned unchanged."""
    src = _write_image(tmp_path / "big.png", (3000, 2000))  # long edge 3000
    res = Restorer().ensure_print_quality(str(src), target_long_edge_px=2500)

    assert isinstance(res, RestoreResult)
    assert res.upscaled is False
    assert res.path == str(src)  # path unchanged
    assert res.from_size == (3000, 2000)
    assert res.to_size == (3000, 2000)
    with Image.open(res.path) as im:
        assert im.size == (3000, 2000)


def test_below_target_is_upscaled_lanczos(tmp_path):
    """A below-target source is upscaled to the target long edge (aspect kept)."""
    src = _write_image(tmp_path / "small.png", (800, 400))  # long edge 800
    dest = tmp_path / "out.png"
    res = Restorer().ensure_print_quality(
        str(src), target_long_edge_px=2500, dest=str(dest)
    )

    assert res.upscaled is True
    assert res.path == str(dest)
    assert res.path != str(src)  # a NEW file
    assert res.from_size == (800, 400)
    # long edge hits the target (within rounding); aspect (2:1) preserved.
    w, h = res.to_size
    assert max(w, h) == 2500
    assert abs(w / h - 2.0) < 0.01
    with Image.open(res.path) as im:
        assert im.size == (w, h)
    assert res.backend == "lanczos"


def test_upscale_capped(tmp_path):
    """A tiny source is upscaled only up to MAX_UPSCALE_FACTOR, not to target."""
    assert MAX_UPSCALE_FACTOR == 4.0
    src = _write_image(tmp_path / "tiny.png", (200, 200))  # long edge 200
    dest = tmp_path / "capped.png"
    res = Restorer().ensure_print_quality(
        str(src), target_long_edge_px=2500, dest=str(dest)
    )

    assert res.upscaled is True
    # capped at 200 * 4.0 = 800, NOT the 2500 target.
    assert max(res.to_size) == 800
    assert max(res.to_size) != 2500  # the cap held
    with Image.open(res.path) as im:
        assert max(im.size) == 800


def test_backend_is_swappable(tmp_path):
    """The upscale path routes through the injected backend."""
    src = _write_image(tmp_path / "small.png", (800, 400))
    dest = tmp_path / "fake_out.png"

    calls = []

    class FakeBackend:
        name = "fake"

        def upscale(self, path, target_long_edge_px, dest):
            calls.append((path, target_long_edge_px, dest))
            # produce a real file so downstream open() works.
            Image.new("RGB", (2500, 1250), (0, 0, 0)).save(dest)
            return (dest, 2500, 1250)

    res = Restorer(backend=FakeBackend()).ensure_print_quality(
        str(src), target_long_edge_px=2500, dest=str(dest)
    )

    assert len(calls) == 1
    assert calls[0][0] == str(src)
    assert calls[0][2] == str(dest)
    assert res.upscaled is True
    assert res.backend == "fake"
    assert res.to_size == (2500, 1250)


def test_default_backend_is_lanczos():
    """Default backend is the dependency-light PIL Lanczos backend."""
    r = Restorer()
    assert isinstance(r.backend, LanczosBackend)
    assert r.backend.name == "lanczos"
