"""Pattern package — dispatch registry.

R1 ships ONE real pattern (ST-07A); every other ST type renders through
the brand-styled `_generic` skeleton. R2 adds the remaining patterns by
registering them in REGISTRY below.
"""

from __future__ import annotations

from typing import Callable

from patterns.base import PageFragment, RenderContext
from patterns import (st_07a, _generic, st_09, st_14, st_06, st_02, st_07b,
                      st_08, st_03, st_fazit, st_31, st_32, st_01, st_05, st_22)

# ST type -> pattern render function.
REGISTRY: dict[str, Callable[[dict, RenderContext], PageFragment]] = {
    "ST-07A": st_07a.render,
    "ST-09": st_09.render,
    "ST-14": st_14.render,
    "ST-06": st_06.render,
    "ST-02": st_02.render,
    "ST-07B": st_07b.render,
    "ST-08": st_08.render,
    "ST-03": st_03.render,
    "ST-FAZIT": st_fazit.render,
    "ST-31": st_31.render,
    "ST-32": st_32.render,
    "ST-01": st_01.render,
    "ST-05": st_05.render,
    "ST-22": st_22.render,
}


# Phase 4: route ST-07A through the reference-derived TEMPLATE engine when the
# TEMPLATE_DRIVEN_ST07A flag is set, so it can be A/B-compared on pixels against
# the hand-built st_07a pattern before any permanent swap.
import os  # noqa: E402

if os.environ.get("TEMPLATE_DRIVEN_ST07A"):
    from patterns import st_07a_tpl  # noqa: E402

    REGISTRY["ST-07A"] = st_07a_tpl.render


def get_renderer(st_type: str) -> Callable[[dict, RenderContext], PageFragment]:
    """Return the pattern render() for an ST type, defaulting to _generic."""
    return REGISTRY.get(st_type, _generic.render)
