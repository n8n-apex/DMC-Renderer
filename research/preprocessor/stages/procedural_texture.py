"""Procedural brand-background textures — CODE-generated (numpy + Pillow), not fal.

Generates seeded, BRAND-COLOURED, print-resolution background textures purely in
numpy + Pillow. No API, no network, deterministic, resolution-independent — it can
render at the exact 300-DPI print floor (fal's 2K is BELOW it). The renderer places
the resulting PNG as the full content ground (assembler report-ground injection).

Why code > fal for ABSTRACT brand grounds: exact brand colour (from tokens, not a
black-box prompt), deterministic/seeded reproducibility, any resolution, free +
instant + offline, and it never reads as "generic AI slop" (the dull look). fal
stays available for photoreal needs.

Patterns implemented:
  - "marble"   : domain-warped fractal-noise veins (this module).
Future kinds (same interface): "mycelium"/"neural" via reaction-diffusion
(Gray-Scott) or flow-field / DLA — organic branching/cellular textures.

All colour inputs are BRAND DATA (hex from tokens) — brand-agnostic, no literals.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image


def _hex_to_rgb(h: str) -> np.ndarray:
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], dtype=np.float32)


def _rgb_to_hex(v: np.ndarray) -> str:
    return "#%02x%02x%02x" % tuple(int(max(0, min(255, x))) for x in v)


def _mix(a: np.ndarray, b: np.ndarray, t: float) -> np.ndarray:
    return a * (1.0 - t) + b * t


def _fractal_noise(h: int, w: int, octaves: int, rng: np.random.Generator) -> np.ndarray:
    """Smooth fractal VALUE noise: sum of octaves of random grids, each smoothly
    bicubic-upsampled to full size via Pillow. Pure numpy+PIL (no scipy/noise lib).
    Returns a float field in roughly 0..1."""
    out = np.zeros((h, w), np.float32)
    amp, total = 1.0, 0.0
    for o in range(1, octaves + 1):
        gh = max(2, h // (2 ** (octaves - o + 1)))
        gw = max(2, w // (2 ** (octaves - o + 1)))
        grid = (rng.random((gh, gw)) * 255.0).astype(np.uint8)
        up = np.asarray(
            Image.fromarray(grid).resize((w, h), Image.BICUBIC), dtype=np.float32
        ) / 255.0
        out += amp * up
        total += amp
        amp *= 0.5
    return out / total


def brand_marble_stops(
    neutral_light: str, accent: str, primary: str
) -> list[tuple[float, str]]:
    """A WHISPER-LIGHT colour ramp from the brand: near-white with the brand hue at
    a barely-perceptible intensity (≤~12%). The background must NOT compete with the
    copy — it is atmosphere, not pattern — so the tint stays in a very narrow, very
    light band. All values derive from the brand tokens (brand-agnostic)."""
    white = _hex_to_rgb(neutral_light)
    acc = _hex_to_rgb(accent)
    prim = _hex_to_rgb(primary)
    return [
        (0.0, neutral_light),
        (0.55, _rgb_to_hex(_mix(white, acc, 0.045))),   # whisper
        (0.85, _rgb_to_hex(_mix(white, acc, 0.085))),
        (1.0, _rgb_to_hex(_mix(white, prim, 0.11))),     # the strongest point — still very light
    ]


def marble(
    width: int,
    height: int,
    stops: list[tuple[float, str]],
    *,
    seed: int = 7,
    x_period: float = 1.6,
    y_period: float = 3.2,
    turb_power: float = 1.5,
    vein_sharpness: float = 1.15,
) -> Image.Image:
    """Perlin-style MARBLE: low-frequency flowing veins (Perlin's classic marble),
    mapped through the brand colour ramp. `stops` = ascending (pos 0..1, '#hex')
    LIGHT→accent (pos 0 = ground/near-white, pos 1 = the thin vein colour).

    The vein direction is set by x_period/y_period (kept LOW so the veins are large
    and flowing, not speckle); a fractal `turbulence` field distorts the sine bands
    into organic marble; `vein_sharpness` raises the vein field to a power so only
    the thin vein CENTRES take the accent colour and the rest stays the light ground.
    Seeded → deterministic."""
    rng = np.random.default_rng(seed)
    h, w = height, width
    turb = _fractal_noise(h, w, 5, rng)  # 0..1 organic distortion
    yy = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, None]
    xx = np.linspace(0.0, 1.0, w, dtype=np.float32)[None, :]
    xy = xx * x_period + yy * y_period + turb_power * turb
    sine = np.abs(np.sin(xy * np.pi))            # 0 at vein centres, 1 between
    # thin, sharp veins: (1-sine)^k → ~1 only at the vein centres, ~0 elsewhere
    field = np.clip((1.0 - sine) ** vein_sharpness, 0.0, 1.0)

    pos = np.array([p for p, _ in stops], dtype=np.float32)
    cols = np.stack([_hex_to_rgb(c) for _, c in stops])  # (n, 3)
    img = np.empty((h, w, 3), dtype=np.float32)
    for ch in range(3):
        img[..., ch] = np.interp(field, pos, cols[:, ch])
    return Image.fromarray(img.astype(np.uint8), "RGB")


def generate_brand_texture(
    kind: str,
    width: int,
    height: int,
    *,
    brand_neutral_light: str,
    brand_accent: str,
    brand_primary: str,
    seed: int = 7,
) -> Image.Image:
    """Brand-agnostic entry point: produce a `kind` texture at WxH from brand colours.
    Currently supports kind="marble"; raises for unknown kinds (callers fall back to
    fal / token ground)."""
    if kind == "marble":
        stops = brand_marble_stops(brand_neutral_light, brand_accent, brand_primary)
        return marble(width, height, stops, seed=seed)
    raise ValueError(f"unknown procedural texture kind: {kind!r}")


def write_texture(img: Image.Image, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format="PNG")
    return path
