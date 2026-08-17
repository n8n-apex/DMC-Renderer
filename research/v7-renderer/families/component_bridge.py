"""Bridge: v3 contract elements into the SVG component generators.

`research/preprocessor/stages/generate_components.py` holds eleven
brand-parameterised SVG generators -- process_flow, curved_arrow_flow,
matrix_2x2, causality_chain, metaphor_split, bar_chart, line_chart,
stat_block, compare_table, paired_comparison, venn_diagram. v3 has never
called one of them, which is why an ordered process renders as a bullet
list and a comparison renders as two stacked columns of text.

Measured stakes: Richard lays roughly 55 vector marks per face and one of
his pages alone draws 169 rectangles as a tiled grid. v3 draws about 7.
Three attempts to close that with CSS all failed and were reverted; the
marks in his pages are drawn STRUCTURES, and this is the module that makes
them.

Grounding is unchanged from the rest of the pipeline: a component is only
built from content and claims the contract already declares, the figures
it prints are the claims' own verbatim strings, and a component the data
cannot fill returns empty rather than a decorated placeholder.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Mapping

PREPROCESSOR_ROOT = Path(__file__).resolve().parents[3] / "preprocessor"
if str(PREPROCESSOR_ROOT) not in sys.path:
    sys.path.insert(0, str(PREPROCESSOR_ROOT))

from stages.generate_components import (  # noqa: E402
    compare_table,
    curved_arrow_flow,
    paired_comparison,
    process_flow,
)


# The component generators take real hex, not CSS custom properties: they
# compute derived tints and stroke colours arithmetically. The document's
# own tokens are resolved by the caller and passed through.
DEFAULT_PRIMARY = "#171713"
DEFAULT_ACCENT = "#5B7C8D"

# Above this many steps the linear flow crowds; the curved multi-row flow
# carries them without shrinking the type.
_CURVED_FLOW_THRESHOLD = 4


def _text(content_by_ref: Mapping[str, str], ref: str) -> str:
    return content_by_ref.get(ref, "")


def _first_sentence(text: str, limit: int = 68) -> str:
    """A step label, not a paragraph. Components size type to the label."""
    head = text.split(". ")[0].strip()
    if len(head) <= limit:
        return head
    return head[: limit - 1].rsplit(" ", 1)[0] + "…"


def _steps(element: Any, content_by_ref: Mapping[str, str]) -> list[dict]:
    """Steps in the shape each generator reads.

    The two flow generators want different keys -- `process_flow` reads
    `n`/`short`, `curved_arrow_flow` reads `number`/`title`/`description` --
    so both are supplied and each takes what it needs.
    """
    steps: list[dict] = []
    for index, ref in enumerate(element.item_content_refs, start=1):
        text = _text(content_by_ref, ref)
        if not text:
            continue
        label = _first_sentence(text)
        steps.append(
            {
                "n": index,
                "short": label,
                "number": f"{index:02d}",
                "title": label,
                "description": text,
            }
        )
    return steps


def render(
    element: Any,
    *,
    content_by_ref: Mapping[str, str],
    claim_values: Mapping[str, str],
    primary: str = DEFAULT_PRIMARY,
    accent: str = DEFAULT_ACCENT,
) -> str:
    """One SVG component, or empty when this element earns none."""
    kind = element.kind

    if kind == "process":
        steps = _steps(element, content_by_ref)
        if len(steps) < 2:
            return ""
        if len(steps) > _CURVED_FLOW_THRESHOLD:
            return curved_arrow_flow(steps, primary=primary, accent=accent)
        return process_flow(steps, primary=primary, accent=accent)

    if kind == "comparison":
        left = [_text(content_by_ref, r) for r in element.left_content_refs]
        right = [_text(content_by_ref, r) for r in element.right_content_refs]
        left = [item for item in left if item]
        right = [item for item in right if item]
        if not left or not right:
            return ""
        paired = list(zip(left, right))
        if not paired:
            return ""
        # A short contrast reads as paired panels; a longer one is a table,
        # because paired panels stop being legible past a few rows.
        if len(paired) <= 3:
            return paired_comparison(
                [
                    {"before": _first_sentence(a), "after": _first_sentence(b)}
                    for a, b in paired
                ],
                primary=primary,
                accent=accent,
            )
        return compare_table(
            [
                {"left": _first_sentence(a), "right": _first_sentence(b)}
                for a, b in paired
            ],
            ("OHNE", "MIT"),
            primary=primary,
            accent=accent,
        )

    return ""
