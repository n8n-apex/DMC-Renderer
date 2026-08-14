"""Phase 4, Task 2 — extract reference LayoutTemplates with a VLM.

For each reference page (PNG + its text layer) the vision model is asked for the
page's COMPOSITION as geometry + ROLES only (never brand colours, fonts, or
specific copy). The returned dict is validated through the renderer's
``LayoutTemplate`` model, clustered by st_type, and the v1 archetype per type
(the first/best exemplar) is written to ``layout_templates/<st_type>/<variant>.json``.

Brand-agnostic by construction: the prompt forbids client identity and the
schema's ``color_roles`` accept only token ROLE names (a hex would fail
``LayoutTemplate.validate``). The extraction call is INJECTABLE (``extract_fn``)
so the stage is fully unit-testable offline with a fake — no live call needed to
prove the wiring.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable, Optional

_HERE = Path(__file__).resolve().parent          # .../quality_loop/references
_QL_ROOT = _HERE.parent                           # .../quality_loop
_RESEARCH = _QL_ROOT.parent                       # .../research
_RENDERER = _RESEARCH / "v7-renderer"
# Import the canonical model from the renderer (single source of truth).
if str(_RENDERER) not in sys.path:
    sys.path.insert(0, str(_RENDERER))
from layout_template import (  # noqa: E402
    COLOR_ROLES, REGION_ROLES, SCALE_ROLES, LayoutTemplate,
)

INDEX_PATH = _HERE / "index.json"
# Templates are renderer DATA (the renderer consumes them), so they live under
# the renderer tree where the template engine + the no-literals guard look.
DEFAULT_OUT_ROOT = _RENDERER / "layout_templates"


# --------------------------------------------------------------------------- #
# The brand-agnostic extraction prompt (composition + geometry + roles ONLY)
# --------------------------------------------------------------------------- #
def build_extract_prompt(st_type: str) -> tuple[str, str]:
    """Return (system, user) prompts for extracting a page's LayoutTemplate.

    The prompt asks ONLY about composition/geometry/roles and explicitly forbids
    brand identity (colours, fonts, specific text). Coordinates are 0..1 page
    fractions (top-left origin). ``color_roles`` must be role NAMES, never hexes.
    """
    system = (
        "You are a layout analyst. Given an image of ONE page from a designed "
        "report, extract its COMPOSITION as geometry and ROLES only. IGNORE all "
        "brand identity: do not report specific colours (no hex), font names, "
        "company names, or verbatim copy. Reply with ONE JSON object only."
    )
    user = (
        f"Page type: {st_type}. Return a JSON object with these keys:\n"
        '- "variant": a short kebab-case name for this composition.\n'
        '- "grid": {"columns": int, "margin": {"top","right","bottom","left": '
        "0..1 fractions}, \"gutter\": 0..1}.\n"
        '- "regions": a list of {"role", "x","y","w","h" (0..1 page fractions, '
        'top-left origin), "z": int, "fit": "wrap"|"shrink"|"clamp"}. '
        f"role MUST be one of: {sorted(REGION_ROLES)}.\n"
        '- "type_roles": {"headline","lede","body","label": a scale role}. '
        f"scale roles: {sorted(SCALE_ROLES)}.\n"
        '- "color_roles": {"ground","ink","accent","footer": a token ROLE NAME}. '
        f"colour role NAMES only (never a hex/value): {sorted(COLOR_ROLES)}.\n"
        '- "whitespace_target": 0..1 (fraction of the page intentionally empty).\n'
        "Every region must lie inside the page (x+w<=1, y+h<=1)."
    )
    return system, user


def make_vision_extract_fn(vis_client: Any) -> Callable[[str, str, str], dict]:
    """Adapt a vision client into an ``extract_fn(png, text, st_type) -> dict``.

    Uses the client's generic ``extract_json`` (system, user, image -> dict). The
    page text is available for context but the prompt is image-led; we pass it so
    a future prompt can use it without changing this signature.
    """
    def _fn(png_path: str, page_text: str, st_type: str) -> dict:
        system, user = build_extract_prompt(st_type)
        return vis_client.extract_json(png_path, system, user)
    return _fn


# --------------------------------------------------------------------------- #
# Extraction + validation for ONE page
# --------------------------------------------------------------------------- #
def extract_template(
    deck: str,
    page_no: int,
    st_type: str,
    png_path: str,
    *,
    extract_fn: Callable[[str, str, str], dict],
    page_text: str = "",
) -> dict:
    """Extract + VALIDATE one reference page into a LayoutTemplate dict.

    ``extract_fn`` returns the composition body (grid/regions/type_roles/
    color_roles/whitespace_target); this stage stamps the st_type, variant, and
    source_refs and validates the whole thing via ``LayoutTemplate.from_dict``
    (raises ValueError on any geometry / role / brand-leak violation).
    """
    body = dict(extract_fn(png_path, page_text, st_type))
    body["st_type"] = st_type
    body.setdefault("variant", "default")
    body["source_refs"] = [{"deck": deck, "page_no": page_no}]
    LayoutTemplate.from_dict(body)  # validate (raises on a bad template)
    return body


# --------------------------------------------------------------------------- #
# Deck-wide: cluster by st_type, pick the v1 archetype, write the library
# --------------------------------------------------------------------------- #
def build_templates(
    *,
    extract_fn: Callable[[str, str, str], dict],
    index_path: Path | str = INDEX_PATH,
    out_root: Path | str = DEFAULT_OUT_ROOT,
    st_types: Optional[list[str]] = None,
    text_fn: Optional[Callable[[str, int], str]] = None,
) -> dict[str, str]:
    """Extract one archetype LayoutTemplate per st_type and write the library.

    Clusters the reference index by st_type; for each (excluding OTHER) picks the
    FIRST exemplar as the v1 archetype (deterministic; no averaging — a real
    exemplar beats a synthesized mush). Writes
    ``out_root/<st_type>/<variant>.json``. Returns ``{st_type: written_path}``.

    ``text_fn(png_or_pdf, page_index)`` optionally supplies the page text; default
    passes "" (the prompt is image-led).
    """
    index = json.loads(Path(index_path).read_text(encoding="utf-8"))
    out_root = Path(out_root)
    by_type: dict[str, list[dict]] = {}
    for e in index:
        st = str(e.get("st_type", ""))
        if st in ("", "OTHER"):
            continue
        if st_types is not None and st not in st_types:
            continue
        by_type.setdefault(st, []).append(e)

    written: dict[str, str] = {}
    for st, examples in by_type.items():
        ex = examples[0]  # v1 archetype: first exemplar (deterministic)
        png_abs = str((_QL_ROOT / ex["png_path"]).resolve())
        text = text_fn(png_abs, 0) if text_fn else ""
        body = extract_template(
            ex["deck"], ex["page_no"], st, png_abs,
            extract_fn=extract_fn, page_text=text,
        )
        dest = out_root / st / f"{body['variant']}.json"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(body, indent=2, ensure_ascii=False), encoding="utf-8")
        written[st] = str(dest)
    return written
