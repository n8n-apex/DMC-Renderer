"""Phase 5: page texture (subtle procedural BRAND MARBLE) tests.

The light-page GROUND is overwritten with a SUBTLE brand marble: the procedural
marble (code, not fal) blended over a solid cream (brand_neutral_light) at
GROUND_MARBLE_ALPHA. swatch "C" == ~16% marble over cream. These tests pin the
two legibility-preserving invariants:

  (a) GROUND_MARBLE_ALPHA is SUBTLE (<= 0.25), the marble is atmosphere, not a
      competing pattern.
  (b) the blend helper produces an image whose MEAN colour stays in the
      warm-cream band (R>=235, G>=232, B>=225), the marble must NOT darken the
      ground, so legibility / design-conformance (warm-cream ground) is kept.

Brand-agnostic: colours come from the apex brand_tokens fixture, never literals.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
V7 = HERE.parent                                  # research/v7-renderer
RESEARCH = V7.parent                              # research
PREPROCESSOR = RESEARCH / "preprocessor"
APEX = V7 / "fixtures" / "apex"

# ground_marble.blend_marble_over_cream lazily imports stages.procedural_texture
# from the preprocessor, and we import the module via its fixtures.apex package
# path, mirroring build_package's sys.path setup so both resolve.
for _p in (str(PREPROCESSOR), str(V7)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fixtures.apex.ground_marble import (  # noqa: E402
    GROUND_MARBLE_ALPHA,
    blend_marble_over_cream,
)


def _apex_brand_tokens() -> dict:
    return json.loads((APEX / "brand_input.json").read_text(encoding="utf-8"))[
        "brand_tokens"
    ]


def test_ground_marble_alpha_is_subtle():
    assert GROUND_MARBLE_ALPHA <= 0.25, (
        f"GROUND_MARBLE_ALPHA {GROUND_MARBLE_ALPHA} is not subtle (<=0.25): "
        "the page marble must be atmosphere behind the copy, not a pattern that "
        "competes with it"
    )
    # also positive (a real blend, not a no-op cream)
    assert GROUND_MARBLE_ALPHA > 0.0, "alpha must be > 0 (some marble shows)"


def test_blend_marble_stays_warm_cream():
    tokens = _apex_brand_tokens()
    # small render keeps the test fast; the mean is resolution-independent.
    img = blend_marble_over_cream(
        width=256,
        height=342,
        brand_neutral_light=tokens["brand_neutral_light"],
        brand_accent=tokens["brand_accent"],
        brand_primary=tokens["brand_primary"],
        alpha=GROUND_MARBLE_ALPHA,
    )
    arr = np.asarray(img.convert("RGB"), dtype=np.float32)
    r, g, b = (float(arr[..., c].mean()) for c in range(3))
    assert r >= 235 and g >= 232 and b >= 225, (
        f"blended ground mean {(round(r, 1), round(g, 1), round(b, 1))} is not in "
        "the warm-cream band (R>=235, G>=232, B>=225); the marble darkened the "
        "ground and would hurt legibility/conformance"
    )
    # warm: red mean should still exceed blue mean (cream is warm)
    assert r >= b, (
        f"blended ground mean {(round(r, 1), round(g, 1), round(b, 1))} lost its "
        "warmth (R must stay >= B)"
    )
