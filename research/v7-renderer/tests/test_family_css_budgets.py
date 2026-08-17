"""Task 7: brand tokens, palette budgets, and type bounds hold in rendered CSS."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


RENDERER_ROOT = Path(__file__).resolve().parent.parent
RESEARCH_ROOT = RENDERER_ROOT.parent
if str(RESEARCH_ROOT) not in sys.path:
    sys.path.insert(0, str(RESEARCH_ROOT))

ROOT = Path(__file__).resolve().parents[3]
FAMILIES_CSS = RENDERER_ROOT / "styles_v3" / "families.css"
TOKENS_CSS = RENDERER_ROOT / "styles_v3" / "tokens.css"
REGISTRY_PATH = ROOT / "research" / "composition_registry" / "families" / "dmc-v1.json"

_HEX_COLOR = re.compile(r"#[0-9a-fA-F]{3,8}\b")
_FONT_SIZE_PT = re.compile(r"font-size:\s*([\d.]+)pt")
_CLIENT_LITERALS = (
    "apex",
    "jousef",
    "christoph",
    "buchagentur",
    "alexander",
    "niklas",
    "werkzeug",
    "aerzte",
)


def family_blocks() -> dict[str, str]:
    """Split families.css into per-family text by data-family-id selectors."""
    css = FAMILIES_CSS.read_text(encoding="utf-8")
    blocks: dict[str, list[str]] = {}
    for match in re.finditer(
        r'\.fragment\[data-family-id="([a-z_]+)"\][^{]*\{[^}]*\}', css
    ):
        blocks.setdefault(match.group(1), []).append(match.group(0))
    return {family: "\n".join(parts) for family, parts in blocks.items()}


def test_family_css_is_token_only_with_no_hex_colors() -> None:
    css = FAMILIES_CSS.read_text(encoding="utf-8")

    assert not _HEX_COLOR.search(css), "families.css must use tokens, never hex"


def test_family_css_carries_no_client_literals() -> None:
    # Comments may cite atlas faces (apex-09, niklas-11) as provenance;
    # only effective CSS - selectors and declarations - must stay client-free.
    css = FAMILIES_CSS.read_text(encoding="utf-8")
    effective = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL).lower()

    for literal in _CLIENT_LITERALS:
        assert literal not in effective, (
            f"client literal {literal!r} leaked into effective family CSS"
        )


def test_hex_colors_live_only_in_the_token_root() -> None:
    tokens = TOKENS_CSS.read_text(encoding="utf-8")
    root_block = re.search(r":root\s*\{[^}]*\}", tokens).group(0)
    outside = _HEX_COLOR.findall(tokens.replace(root_block, ""))

    assert not outside, "hex colors outside :root break the theme boundary"


def test_every_family_block_respects_the_accent_budget() -> None:
    for family, block in family_blocks().items():
        accent_uses = block.count("var(--accent)")
        assert accent_uses <= 8, (
            f"{family} uses the accent token {accent_uses} times; "
            "the family palette budget is 8"
        )


def test_family_font_sizes_stay_inside_registry_type_bounds() -> None:
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    bounds_by_family = {
        family["family_id"]: (
            min(bound["min_pt"] for bound in family["typography_bounds"]),
            max(bound["max_pt"] for bound in family["typography_bounds"]),
        )
        for family in registry["families"]
    }

    for family, block in family_blocks().items():
        minimum, maximum = bounds_by_family[family]
        for value in _FONT_SIZE_PT.findall(block):
            size = float(value)
            assert minimum <= size <= maximum, (
                f"{family} declares {size}pt outside its registry type bounds "
                f"[{minimum}, {maximum}]"
            )


def test_image_choreography_is_constrained_globally() -> None:
    tokens = TOKENS_CSS.read_text(encoding="utf-8")
    families = FAMILIES_CSS.read_text(encoding="utf-8")

    assert "object-fit" in tokens or "object-fit" in families
    assert ".fragment" in tokens and "overflow: hidden" in tokens
