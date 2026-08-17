"""Shared image helper for the onboard vision layers.

Downscales + JPEG-recompresses an image to a base64 data URL that stays
well under provider size limits (Anthropic rejects images >~5MB; a
full-page screenshot is easily 5-7MB). Safe for accuracy: the vision
models only reason over the image; exact hex values come from
pixel_palette on the original PNG, never from the compressed copy.
"""

from __future__ import annotations

import base64
import io
from pathlib import Path
from typing import Optional

from PIL import Image

MAX_EDGE = 1568
JPEG_QUALITY = 85


def encode_image_data_url(path: Optional[str], *, max_edge: int = MAX_EDGE) -> Optional[str]:
    if not path:
        return None
    p = Path(path)
    if not p.exists():
        return None
    try:
        img = Image.open(p).convert("RGB")
        if max(img.size) > max_edge:
            img.thumbnail((max_edge, max_edge))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=JPEG_QUALITY)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{b64}"
    except Exception:
        b64 = base64.b64encode(p.read_bytes()).decode("ascii")
        return f"data:image/png;base64,{b64}"
