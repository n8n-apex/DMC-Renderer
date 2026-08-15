"""Content-addressed cache for fal image generation.

The key is sha256 over the EXACT generation inputs (model + prompt +
negative + aspect + resolution). The fal call carries no seed, so these
inputs fully determine the output -> an identical request reuses the stored
PNG ($0, deterministic; temp=0 prompts are stable -> stable key). cache_dir
None disables caching (the default everywhere until a later phase wires it).
Brand-agnostic.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Optional


def cache_salt(
    *,
    client_slug: str,
    brand_primary: str,
    brand_accent: str,
    design_brief: Optional[dict],
    builder_version: str,
) -> str:
    """A stable digest of every per-client input that should bust the image
    cache: the client, the two brand colours, the design brief, and the
    prompt-builder version. Two different clients can never collide on an
    identically-derived prompt. Brand-agnostic: hashes VALUES, names nothing.
    """
    brief = json.dumps(design_brief or {}, sort_keys=True, ensure_ascii=False)
    parts = [client_slug or "", brand_primary or "", brand_accent or "",
             brief, builder_version or ""]
    return hashlib.sha256("\x00".join(parts).encode("utf-8")).hexdigest()


def fal_cache_key(
    *, model: str, prompt: str, negative_prompt: Optional[str], aspect: str,
    resolution: str, salt: str = "", image_bytes: Optional[bytes] = None,
) -> str:
    """Content-addressed cache key.

    `image_bytes` (the INPUT reference raster for image-to-image) MUST be part
    of the key (US-405): two edits with the same prompt but different input
    images are different generations. A change to the input image busts the
    cache, exactly like a change to the prompt.
    """
    parts = [model or "", prompt or "", negative_prompt or "", aspect or "",
             resolution or "", salt or ""]
    if image_bytes is not None:
        parts.append(hashlib.sha256(image_bytes).hexdigest())
    return hashlib.sha256("\x00".join(parts).encode("utf-8")).hexdigest()


def cache_lookup(cache_dir: Optional[Path], key: str) -> Optional[Path]:
    """Return the cached PNG path for `key`, or None (miss / caching off)."""
    if cache_dir is None:
        return None
    p = Path(cache_dir) / f"{key}.png"
    return p if p.exists() else None


def cache_store(cache_dir: Optional[Path], key: str, src_path) -> Optional[Path]:
    """Copy a freshly-generated PNG into the cache under `key`. No-op when
    caching is off or the copy fails. Returns the cache path or None."""
    if cache_dir is None:
        return None
    try:
        dst_dir = Path(cache_dir)
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / f"{key}.png"
        shutil.copyfile(src_path, dst)
        return dst
    except OSError:
        return None
