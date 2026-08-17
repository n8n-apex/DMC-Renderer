"""Conservative, swappable print-quality ensurer for founder imagery.

Scraped founder images feed a printed report (A4 @ ~300dpi), which wants
roughly 2500px on the long edge. The research finding driving this module is
that **heavily upscaling a real founder's face** (e.g. via CodeFormer/GFPGAN)
risks a "waxy" / synthetic look that reads as AI-fake. So the policy here is:

1. **Prefer the high-res source.** If the source already meets the target long
   edge, return it untouched (no upscale at all).
2. **Upscale conservatively** otherwise — bring the long edge up to the target
   while preserving aspect ratio, but never blow an image up by more than
   ``MAX_UPSCALE_FACTOR`` (a tiny thumbnail enlarged ~12x looks fake; capping
   at 4x keeps it plausible even if it falls short of the ideal print size).
3. **Keep the backend swappable / opt-in.** The default ``LanczosBackend`` is
   dependency-light (PIL only — no torch, no network). A face-restore backend
   (CodeFormer/GFPGAN) can be plugged in later behind the same ``Backend``
   protocol *without* making torch a v1 hard dependency. See
   ``FaceRestoreBackend`` note below — it is intentionally NOT implemented.

Pure + brand-agnostic: no network, no client literals, local files only.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol, Tuple

from PIL import Image

# Default print target: A4 @ ~300dpi wants ~2500px on the long edge.
DEFAULT_TARGET_LONG_EDGE_PX: int = 2500

# Conservative cap on enlargement. A real founder's face enlarged far beyond
# this starts to look synthetic ("waxy"), so we refuse to upscale past 4x even
# if that leaves us short of the ideal print size — a slightly-soft real photo
# beats an obviously-fake one.
MAX_UPSCALE_FACTOR: float = 4.0


class Backend(Protocol):
    """A pluggable upscaler.

    ``upscale`` reads the image at ``path``, enlarges it so its long edge is
    ``target_long_edge_px`` (preserving aspect ratio), writes the result to
    ``dest`` and returns ``(out_path, out_w, out_h)``.

    Implementations carry a ``name`` used for provenance in ``RestoreResult``.

    A future ``FaceRestoreBackend`` (CodeFormer/GFPGAN) can implement this same
    protocol to do face-aware restoration instead of plain resampling. It is
    deliberately NOT implemented here: it would pull in torch, so it stays an
    opt-in plug-in rather than a v1 hard dependency.
    """

    name: str

    def upscale(
        self, path: str, target_long_edge_px: int, dest: str
    ) -> Tuple[str, int, int]:
        ...


@dataclass
class RestoreResult:
    """Outcome of ``ensure_print_quality`` for one image."""

    path: str  # output path (== input when returned as-is)
    upscaled: bool
    from_size: Tuple[int, int]  # (w, h)
    to_size: Tuple[int, int]  # (w, h)
    backend: str


class LanczosBackend:
    """Default dependency-light backend: PIL Lanczos resampling.

    No torch, no network — just ``Image.resize(..., Image.LANCZOS)``. Good
    enough for a conservative bump in size; it does not invent face detail, so
    it cannot make a face look synthetic.
    """

    name = "lanczos"

    def upscale(
        self, path: str, target_long_edge_px: int, dest: str
    ) -> Tuple[str, int, int]:
        with Image.open(path) as im:
            im.load()
            w, h = im.size
            scale = target_long_edge_px / float(max(w, h))
            out_w = max(1, round(w * scale))
            out_h = max(1, round(h * scale))
            resized = im.resize((out_w, out_h), Image.LANCZOS)
            resized.save(dest)
        return (dest, out_w, out_h)


def _default_dest(path: str) -> str:
    """Sibling output path next to ``path`` (``foo.png`` -> ``foo.print.png``)."""
    root, ext = os.path.splitext(path)
    return f"{root}.print{ext or '.png'}"


class Restorer:
    """Ensures images meet print resolution, conservatively and swappably."""

    def __init__(self, backend: Backend | None = None) -> None:
        self.backend: Backend = backend if backend is not None else LanczosBackend()

    def ensure_print_quality(
        self,
        path: str,
        target_long_edge_px: int = DEFAULT_TARGET_LONG_EDGE_PX,
        *,
        dest: str | None = None,
    ) -> RestoreResult:
        """Return a print-ready version of ``path``.

        - If the source long edge already meets ``target_long_edge_px``, return
          it AS-IS (``upscaled=False``, ``path`` unchanged) — prefer the
          high-res source over any synthetic enlargement.
        - Otherwise upscale via the backend to the target long edge (aspect
          preserved), but never beyond ``MAX_UPSCALE_FACTOR``. Writes to
          ``dest`` (default: a sibling ``*.print.*`` path).
        """
        with Image.open(path) as im:
            src_w, src_h = im.size
        from_size = (src_w, src_h)
        long_edge = max(src_w, src_h)

        # 1. Prefer the high-res source: already big enough -> no-op.
        if long_edge >= target_long_edge_px:
            return RestoreResult(
                path=path,
                upscaled=False,
                from_size=from_size,
                to_size=from_size,
                backend=self.backend.name,
            )

        # 2. Conservative upscale, capped at MAX_UPSCALE_FACTOR.
        capped_long_edge = min(
            target_long_edge_px,
            int(round(long_edge * MAX_UPSCALE_FACTOR)),
        )
        out_path = dest if dest is not None else _default_dest(path)
        out_path, out_w, out_h = self.backend.upscale(
            path, capped_long_edge, out_path
        )
        return RestoreResult(
            path=out_path,
            upscaled=True,
            from_size=from_size,
            to_size=(out_w, out_h),
            backend=self.backend.name,
        )
