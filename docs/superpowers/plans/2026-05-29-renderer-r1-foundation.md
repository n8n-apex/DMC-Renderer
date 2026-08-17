# Renderer R1 — Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the renderer to consume the pre-processor's `resolved_package.json` and emit a working multi-page **apex** PDF — case-study pages rendered real (refactored `st_07a`), every other page a clean brand-styled skeleton (`_generic`).

**Architecture:** A package loader reads `resolved_package.json` → a per-page dispatch registry maps each ST type to a pattern that returns a `PageFragment{html, css}` → an assembler builds ONE HTML document (shared `<head>` + deduped fragment CSS + one `<section class="page">` per package page) → WeasyPrint → RGB PDF → PyMuPDF PNGs → advisory overflow + accent-budget validators. The apex fixture package is regenerated from structured content DATA by a generator that reuses the real pre-processor Stage 8.

**Tech Stack:** Python 3.11, WeasyPrint, PyMuPDF (fitz), qrcode, Pyphen (renderer venv); Pydantic v2 + the pre-processor stages (pre-processor venv).

---

## CRITICAL EXECUTION NOTES (read before starting)

1. **No git in this repo.** The convention is "builds verified by tests, not commits." Every task ends with a **verification checkpoint** (run the named test command and confirm output) — there are NO `git commit` steps. Do not run git.

2. **Two venvs, two sides.**
   - Renderer tasks run in the **renderer venv**: `cd research/v7-renderer && .venv/bin/python -m pytest …`
   - The apex generator (Task 8) + upstream change (Task 1) run in the **pre-processor venv**: `cd research/preprocessor && .venv/bin/python …`
   - Never import renderer modules from the pre-processor or vice-versa at runtime, except the generator script which deliberately adds the pre-processor dir to `sys.path` (it lives on the renderer side but runs under the pre-processor venv).

3. **Guard tests are load-bearing.** `research/v7-renderer/tests/test_chassis_contract.py::test_no_coral_in_chassis_logic` bans the literal `coral` in any non-test `*.py` under `research/v7-renderer/`. `research/preprocessor/tests/test_no_client_name_in_logic.py` bans `APEX/GEVA/Conesso/NMR/Ärztepartner/Buchagentur/Boss/coral` in any non-test `*.py` under `research/preprocessor/`. Consequences baked into this plan:
   - The apex generator + its data files live under `research/v7-renderer/fixtures/apex/` (renderer side → only `coral` banned → `APEX` is fine). They are NEVER placed under `research/preprocessor/`.
   - JSON data files are not scanned by either guard (both `rglob("*.py")`), so `report_content.json` etc. may contain "APEX" freely.

4. **Order matters.** Tasks are linear: 1 → 10. Task 8 (regenerate the apex fixture) must complete before Task 9's integration test and Task 10's real render, because those consume `fixtures/apex/resolved_package.json`. Tasks 2–7 are unit-level and run against the existing (sample) fixture or synthetic inputs, so they do not depend on Task 8.

5. **Baseline before you start.** Confirm the current suites are green:
   - `cd research/v7-renderer && .venv/bin/python -m pytest tests/ -q` → expect **11 passed**.
   - `cd research/preprocessor && .venv/bin/python -m pytest tests/ -q` → expect **217 passed**.

---

## File Structure

**Renderer (`research/v7-renderer/`):**
- `patterns/base.py` — NEW. `PageFragment`, `RenderContext` (the keystone interface).
- `patterns/__init__.py` — MODIFY (docstring-only today). Dispatch `REGISTRY` + `get_renderer()`.
- `patterns/st_07a.py` — REFACTOR. `render_lrp(...)` (full-doc) → `render(page, ctx) -> PageFragment`; add the `ergebnis_metrics` stat strip; rename the `.page` table class to `.lrp-grid`.
- `patterns/_generic.py` — NEW. Brand-styled skeleton fallback for every not-yet-built ST type.
- `package_loader.py` — NEW. `LoadedPackage`, `load_package()`.
- `assembler.py` — NEW. `RenderResult`, `render_package()`, `shared_head_css()`.
- `validators/overflow.py` — REWRITE (docstring-only stub → real per-page overflow check).
- `render.py` — REWORK. CLI → `render_package(fixtures/apex)`.
- `tests/test_render_r1.py` — NEW. Loader / interface / registry / overflow / assembler / integration.
- `fixtures/apex/report_content.json` — NEW DATA. The apex 20-page content (meta + pages).
- `fixtures/apex/brand_input.json` — NEW DATA. The apex 10-field brand tokens + brand_profile.
- `fixtures/apex/image_map.json` — NEW DATA. Which existing asset files map to which slot.
- `fixtures/apex/build_package.py` — NEW. Generator: loads the 3 DATA files, runs the real pre-processor stages, writes `fixtures/apex/resolved_package.json`.

**Pre-processor (`research/preprocessor/`):**
- `stages/plan_layout.py` — MODIFY. `PlannedPage` gains `page_numbers`; `plan_layout` copies it.
- `stages/assemble_package.py` — MODIFY. Emit `page_numbers` in each page manifest entry.
- `tests/test_plan_layout.py` — MODIFY. Add a `page_numbers` flow test.
- `tests/test_assemble_package.py` — MODIFY. Assert `page_numbers` appears in the manifest.

---

### Task 1: Upstream — `page_numbers` through the package manifest

**Why:** The renderer's folio (page-number footer) is per-page. The pre-processor already stores `page_numbers` on `ReportPage` but drops it at `PlannedPage`. Plumb it through so the assembled package carries it. Additive — the 217 pre-processor tests stay green + 2 new assertions.

**Venv:** pre-processor. **Files:**
- Modify: `research/preprocessor/stages/plan_layout.py`
- Modify: `research/preprocessor/stages/assemble_package.py`
- Modify: `research/preprocessor/tests/test_plan_layout.py`
- Modify: `research/preprocessor/tests/test_assemble_package.py`

- [ ] **Step 1: Add the failing plan_layout test**

In `research/preprocessor/tests/test_plan_layout.py`, append:

```python
def test_page_numbers_flows_to_planned_page() -> None:
    """page_numbers on the input page is copied onto the PlannedPage."""
    pages = [
        {"slot": 1, "type": "ST-01", "data": {}, "page_numbers": "1"},
        {"slot": 2, "type": "ST-02", "data": {}, "page_numbers": "2-3"},
    ]
    plan = plan_layout(pages, components={}, page_count_target=20)
    by_slot = {p.slot: p for p in plan.pages}
    assert by_slot[1].page_numbers == "1"
    assert by_slot[2].page_numbers == "2-3"


def test_page_numbers_defaults_to_none_when_absent() -> None:
    """A page without page_numbers yields PlannedPage.page_numbers == None."""
    plan = plan_layout(
        [{"slot": 1, "type": "ST-01", "data": {}}],
        components={},
        page_count_target=20,
    )
    assert plan.pages[0].page_numbers is None
```

- [ ] **Step 2: Run it — expect FAIL**

Run: `cd research/preprocessor && .venv/bin/python -m pytest tests/test_plan_layout.py::test_page_numbers_flows_to_planned_page -q`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'page_numbers'` (or `AttributeError: 'PlannedPage' object has no attribute 'page_numbers'`).

- [ ] **Step 3: Add the field + extractor in `plan_layout.py`**

In `research/preprocessor/stages/plan_layout.py`, add `page_numbers` to the dataclass:

```python
@dataclass
class PlannedPage:
    """One page, enriched with rendering metadata + SVG components."""

    slot: int
    st_type: str
    css_template: str
    components: list[str]    # SVG strings from Stage 6
    has_cta: bool
    data: dict               # original page data, passed through
    page_numbers: Optional[str] = None   # folio text for the renderer (R1)
```

Add the import at the top (the module currently imports only `dataclass, field` and `Any`):

```python
from typing import Any, Optional
```

Add a helper next to `_unpack`:

```python
def _page_numbers(page: Any) -> Optional[str]:
    """Extract page_numbers from a dict or Pydantic ReportPage (None if absent)."""
    if isinstance(page, dict):
        val = page.get("page_numbers")
    else:
        val = getattr(page, "page_numbers", None)
    return str(val) if val is not None else None
```

The `for slot, st_type, data in normalised:` loop discards the original page, so capture page_numbers in a parallel list. Replace the pre-walk + loop header:

```python
    # Pre-walk: enrich each page
    normalised: list[tuple[int, str, dict]] = [_unpack(p) for p in pages]
    page_numbers_list: list[Optional[str]] = [_page_numbers(p) for p in pages]

    # F: CSS template assignment + G: component attachment
    for (slot, st_type, data), page_numbers in zip(normalised, page_numbers_list):
```

And add `page_numbers=page_numbers` to the `PlannedPage(...)` construction:

```python
        planned.append(PlannedPage(
            slot=slot,
            st_type=st_type,
            css_template=css_template,
            components=list(components.get(slot, ())),
            has_cta=has_cta,
            data=data,
            page_numbers=page_numbers,
        ))
```

- [ ] **Step 4: Run the two new tests — expect PASS**

Run: `cd research/preprocessor && .venv/bin/python -m pytest tests/test_plan_layout.py -q`
Expected: PASS (all existing + 2 new).

- [ ] **Step 5: Add the failing assemble_package assertion**

In `research/preprocessor/tests/test_assemble_package.py`, find the test that builds a manifest and inspects `manifest["pages"]` (search for `"pages"`). Add a focused test (place it near the other manifest tests; adapt the existing fixture builders in that file — they already construct a `LayoutPlan`/`PlannedPage`):

```python
def test_manifest_page_carries_page_numbers(tmp_path) -> None:
    """Each manifest page entry includes the page_numbers field from PlannedPage."""
    import asyncio
    from stages.plan_layout import LayoutPlan, PlannedPage
    from stages.generate_assets import AssetPlan
    from models import FontConfig

    planned = [
        PlannedPage(slot=1, st_type="ST-01", css_template="cover",
                    components=[], has_cta=False, data={}, page_numbers="1"),
        PlannedPage(slot=2, st_type="ST-02", css_template="outlook",
                    components=[], has_cta=False, data={}, page_numbers="2-3"),
    ]
    layout_plan = LayoutPlan(pages=planned, page_count=2, page_count_target=20)
    asset_plan = AssetPlan(assets=[])
    font_config = FontConfig(
        font_heading_name="Montserrat", font_body_name="Source Sans 3",
        font_heading_path=None, font_body_path=None, source="chassis_default",
    )
    resolved = asyncio.run(assemble_package(
        brand_tokens={
            "brand_primary": "#111", "brand_accent": "#222",
            "brand_neutral_dark": "#333", "brand_neutral_mid": "#444",
            "brand_neutral_light": "#555", "font_heading": "Montserrat",
            "font_body": "Source Sans 3", "qr_target_url": "https://x.de",
            "company_name_short": "X", "company_url_display": "x.de",
        },
        font_config=font_config, copy_warnings=[], cover_validation=None,
        asset_plan=asset_plan, components={}, layout_plan=layout_plan,
        report_json={"meta": {"report_id": "T"}, "pages": []},
        output_dir=tmp_path,
    ))
    import json
    manifest = json.loads((resolved.output_dir / "resolved_package.json").read_text())
    pn = {p["slot"]: p.get("page_numbers") for p in manifest["pages"]}
    assert pn == {1: "1", 2: "2-3"}
```

> NOTE: If `AssetPlan(assets=[])` raises for missing required fields, check the dataclass defaults in `stages/generate_assets.py` and pass the same zero-count fields the existing `test_assemble_package.py` tests use. Match the file's existing construction style.

- [ ] **Step 6: Run it — expect FAIL (page_numbers KeyError/None)**

Run: `cd research/preprocessor && .venv/bin/python -m pytest tests/test_assemble_package.py::test_manifest_page_carries_page_numbers -q`
Expected: FAIL — assertion error (`page_numbers` is `None`/missing in the manifest).

- [ ] **Step 7: Emit `page_numbers` in the manifest**

In `research/preprocessor/stages/assemble_package.py`, inside `_build_manifest`, the `pages_manifest.append({...})` block (the `for pp in layout_plan.pages:` loop) — add one key:

```python
        pages_manifest.append({
            "slot": pp.slot,
            "st_type": pp.st_type,
            "css_template": pp.css_template,
            "has_cta": pp.has_cta,
            "page_numbers": pp.page_numbers,
            "data": original_data_by_slot.get(pp.slot, pp.data),
            "assets": [_asset_manifest_entry(a, output_dir) for a in page_assets],
            "components": component_rel_paths.get(pp.slot, []),
            "cover_validation": (
                _cover_validation_to_dict(cover_validation)
                if cover_validation and pp.st_type == "ST-01"
                else None
            ),
        })
```

- [ ] **Step 8: Verification checkpoint**

Run: `cd research/preprocessor && .venv/bin/python -m pytest tests/ -q`
Expected: **219 passed** (217 baseline + 2 new plan_layout + the new assemble test = 220; if a count differs, confirm each new test is collected and green — the exact total is "all green, no failures").

---

### Task 2: `patterns/base.py` — the pattern interface (keystone)

**Why:** Every pattern returns a `PageFragment{html, css}`; the assembler collects CSS into the shared head and wraps each `html` in a page container. `RenderContext` gives patterns brand + grammar + lazy asset/component resolution without leaking absolute paths.

**Venv:** renderer. **Files:**
- Create: `research/v7-renderer/patterns/base.py`
- Test: `research/v7-renderer/tests/test_render_r1.py` (new file; grows across Tasks 2–9)

- [ ] **Step 1: Write the failing test** — create `research/v7-renderer/tests/test_render_r1.py`:

```python
"""R1 renderer tests — loader / interface / registry / overflow / assembler / integration."""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHASSIS_ROOT = HERE.parent
sys.path.insert(0, str(CHASSIS_ROOT))

import pytest  # noqa: E402

from brand_tokens import parse_brand_tokens  # noqa: E402
from grammar_loader import load_grammar  # noqa: E402
from patterns.base import PageFragment, RenderContext  # noqa: E402


SAMPLE_BRAND = {
    "brand_primary": "#5a9ab3", "brand_accent": "#85d2ee",
    "brand_neutral_dark": "#0F0F1F", "brand_neutral_mid": "#7A7A8C",
    "brand_neutral_light": "#fdffff", "font_heading": "Montserrat",
    "font_body": "Source Sans 3", "qr_target_url": "https://example.de",
    "company_name_short": "Example", "company_url_display": "example.de",
}


def _ctx(package_dir: Path) -> RenderContext:
    return RenderContext(
        brand=parse_brand_tokens(SAMPLE_BRAND),
        grammar=load_grammar(),
        package_dir=package_dir,
    )


def test_pagefragment_is_frozen_dataclass() -> None:
    frag = PageFragment(html="<p>hi</p>", css=".x{}")
    assert frag.html == "<p>hi</p>" and frag.css == ".x{}"
    with pytest.raises(Exception):
        frag.html = "mutated"  # frozen


def test_rendercontext_resolves_existing_and_missing(tmp_path) -> None:
    (tmp_path / "assets").mkdir()
    img = tmp_path / "assets" / "a.png"
    img.write_bytes(b"\x89PNG\r\n")
    svg = tmp_path / "c.svg"
    svg.write_text("<svg/>", encoding="utf-8")

    ctx = _ctx(tmp_path)
    assert ctx.resolve_asset("assets/a.png") == img.resolve()
    assert ctx.resolve_asset("assets/missing.png") is None
    assert ctx.resolve_asset(None) is None
    assert ctx.resolve_component("c.svg") == "<svg/>"
    assert ctx.resolve_component("missing.svg") is None
    assert ctx.resolve_component(None) is None
```

- [ ] **Step 2: Run it — expect FAIL**

Run: `cd research/v7-renderer && .venv/bin/python -m pytest tests/test_render_r1.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'patterns.base'`.

- [ ] **Step 3: Implement `patterns/base.py`**

```python
"""Pattern interface (R1 keystone).

Every pattern module exposes EXACTLY:

    def render(page: dict, ctx: RenderContext) -> PageFragment: ...

`page` is one package page dict from resolved_package.json:
  {slot, st_type, css_template, has_cta, page_numbers, data, assets,
   components, cover_validation}

A pattern returns a PageFragment: `html` is the page's body markup (the
assembler wraps it in one <section class="page st-XX">), `css` is
pattern-scoped CSS the assembler collects ONCE into the shared <head>.
Patterns own their CSS; they must NOT emit <html>/<head>/<style>/@page/
@font-face/:root — those belong to the shared head (assembler.py).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Allow flat imports from the chassis package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from brand_tokens import BrandConfig  # noqa: E402
from grammar_loader import Grammar  # noqa: E402


@dataclass(frozen=True)
class PageFragment:
    """One rendered page. `html` = body markup; `css` = pattern-scoped CSS."""

    html: str
    css: str


@dataclass(frozen=True)
class RenderContext:
    """Read-only render context handed to every pattern.

    `resolve_asset` / `resolve_component` turn a package-relative path
    (as stored in the manifest) into an absolute Path / SVG string, or
    None when the file is absent — patterns degrade gracefully on None.
    """

    brand: BrandConfig
    grammar: Grammar
    package_dir: Path

    def resolve_asset(self, rel: Optional[str]) -> Optional[Path]:
        if not rel:
            return None
        p = (self.package_dir / rel).resolve()
        return p if p.exists() else None

    def resolve_component(self, rel: Optional[str]) -> Optional[str]:
        p = self.resolve_asset(rel)
        if p is None:
            return None
        try:
            return p.read_text(encoding="utf-8")
        except OSError:
            return None
```

- [ ] **Step 4: Run it — expect PASS**

Run: `cd research/v7-renderer && .venv/bin/python -m pytest tests/test_render_r1.py -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Verification checkpoint**

Run: `cd research/v7-renderer && .venv/bin/python -m pytest tests/ -q`
Expected: all green (11 baseline + 3 new).

---

### Task 3: `patterns/_generic.py` — the R1 skeleton fallback

**Why:** Every ST type that isn't ST-07A (in R1) renders through `_generic`. It must produce a coherent, brand-styled page from whatever `data` is present, never assuming specific keys, and degrade to a near-empty-but-valid page on empty `data`. This is what makes the full multi-page apex doc render in R1.

**Venv:** renderer. **Files:**
- Create: `research/v7-renderer/patterns/_generic.py`
- Test: `research/v7-renderer/tests/test_render_r1.py` (append)

- [ ] **Step 1: Append the failing test** to `tests/test_render_r1.py`:

```python
def test_generic_renders_full_data(tmp_path) -> None:
    from patterns import _generic
    page = {
        "slot": 3, "st_type": "ST-05",
        "data": {
            "title": "Über uns",
            "subtitle": "Ein Satz Untertitel.",
            "body": "Absatz eins.\n\nAbsatz zwei mit **fett**.",
            "credibility_points": ["100+ Projekte", "30-50% Einsparung"],
        },
        "assets": [], "components": [],
    }
    frag = _generic.render(page, _ctx(tmp_path))
    assert isinstance(frag, PageFragment)
    assert "Über uns" in frag.html
    assert "Absatz eins" in frag.html
    assert "100+ Projekte" in frag.html
    assert frag.css.strip()  # non-empty scoped css
    # never leaks head-level rules
    assert "@page" not in frag.css and "@font-face" not in frag.css


def test_generic_handles_empty_data(tmp_path) -> None:
    from patterns import _generic
    page = {"slot": 9, "st_type": "ST-31", "data": {}, "assets": [], "components": []}
    frag = _generic.render(page, _ctx(tmp_path))
    assert isinstance(frag, PageFragment)
    assert "st-generic" in frag.html  # valid container, even if near-empty


def test_generic_renders_background_asset(tmp_path) -> None:
    from patterns import _generic
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "bg.png").write_bytes(b"\x89PNG\r\n")
    page = {
        "slot": 1, "st_type": "ST-01", "data": {"title": "Cover"},
        "assets": [{"slot_id": "cover_hero", "image_type": "background",
                    "path": "assets/bg.png", "status": "generated"}],
        "components": [],
    }
    frag = _generic.render(page, _ctx(tmp_path))
    assert "st-generic-bg" in frag.html
    assert "bg.png" in frag.html
```

- [ ] **Step 2: Run it — expect FAIL** (`ModuleNotFoundError: No module named 'patterns._generic'`)

Run: `cd research/v7-renderer && .venv/bin/python -m pytest tests/test_render_r1.py -k generic -q`

- [ ] **Step 3: Implement `patterns/_generic.py`**

```python
"""Generic skeleton pattern — the R1 fallback for every not-yet-built ST type.

Renders, brand-styled, from whatever `data` is present:
  - a headline (first of title/headline/these/mechanismus/eyebrow, else
    the first string field),
  - an optional subtitle,
  - body prose (intro/body/text/lede/summary + any leftover string
    fields), via preprocess_body,
  - any list fields (list[str] -> bullets; list[dict] -> labelled blocks),
  - an optional full-bleed page background image (first asset whose
    image_type == "background"),
  - any inline SVG components attached to the page.

Never assumes specific keys; empty `data` -> a near-empty but valid page.
Emits NO head-level CSS (no @page/@font-face/:root) — that is the shared
head's job. CSS is scoped under `.st-generic`.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# Allow flat imports from the chassis package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from preprocess import preprocess_body  # noqa: E402
from patterns.base import PageFragment, RenderContext  # noqa: E402


_HEADLINE_KEYS = ("title", "headline", "these", "mechanismus", "eyebrow")
_SUBTITLE_KEYS = ("subtitle", "kicker")
_BODY_KEYS = ("intro", "body", "text", "lede", "summary",
              "kosten_des_nichtstuns")


def _esc(s: str) -> str:
    return (
        str(s).replace("&", "&amp;").replace("<", "&lt;")
        .replace(">", "&gt;").replace('"', "&quot;")
    )


def _first_str(data: dict, keys: tuple[str, ...]) -> tuple[str, str]:
    """Return (key, value) for the first present non-empty string key, else ('','')."""
    for k in keys:
        v = data.get(k)
        if isinstance(v, str) and v.strip():
            return k, v.strip()
    return "", ""


def _render_list(key: str, items: list) -> str:
    """list[str] -> <ul>; list[dict] -> labelled blocks. Returns '' if empty."""
    if not items:
        return ""
    if all(isinstance(it, str) for it in items):
        lis = "".join(f"<li>{_esc(it)}</li>" for it in items if str(it).strip())
        return f'<ul class="gen-list">{lis}</ul>' if lis else ""
    blocks: list[str] = []
    for it in items:
        if isinstance(it, dict):
            label = it.get("label") or it.get("title") or it.get("name") or ""
            value = it.get("value") or it.get("text") or it.get("body") or ""
            parts = []
            if label:
                parts.append(f'<div class="gen-block-label">{_esc(label)}</div>')
            if value:
                parts.append(preprocess_body(str(value)))
            if parts:
                blocks.append(f'<div class="gen-block">{"".join(parts)}</div>')
        elif isinstance(it, str) and it.strip():
            blocks.append(f'<div class="gen-block">{preprocess_body(it)}</div>')
    return "".join(blocks)


def render(page: dict, ctx: RenderContext) -> PageFragment:
    data: dict[str, Any] = page.get("data") or {}

    used: set[str] = set()
    head_key, headline = _first_str(data, _HEADLINE_KEYS)
    if not headline:
        # fall back to the first string field of any name
        for k, v in data.items():
            if isinstance(v, str) and v.strip():
                head_key, headline = k, v.strip()
                break
    if head_key:
        used.add(head_key)

    sub_key, subtitle = _first_str(data, _SUBTITLE_KEYS)
    if sub_key:
        used.add(sub_key)

    body_html_parts: list[str] = []
    for k in _BODY_KEYS:
        v = data.get(k)
        if isinstance(v, str) and v.strip():
            body_html_parts.append(preprocess_body(v))
            used.add(k)

    list_html_parts: list[str] = []
    for k, v in data.items():
        if k in used:
            continue
        if isinstance(v, list):
            rendered = _render_list(k, v)
            if rendered:
                list_html_parts.append(rendered)
                used.add(k)

    # Any leftover scalar string fields -> render so nothing is lost.
    leftover_parts: list[str] = []
    for k, v in data.items():
        if k in used:
            continue
        if isinstance(v, str) and v.strip():
            leftover_parts.append(preprocess_body(v))
            used.add(k)

    # Optional full-bleed background image (first asset of type background).
    bg_html = ""
    for a in (page.get("assets") or []):
        if a.get("image_type") == "background" and a.get("path"):
            p = ctx.resolve_asset(a["path"])
            if p is not None:
                bg_html = (
                    f'<div class="st-generic-bg" '
                    f'style="background-image:url(\'{p.as_uri()}\')"></div>'
                )
            break

    # Inline any SVG components attached to this page.
    comp_html_parts: list[str] = []
    for comp_rel in (page.get("components") or []):
        svg = ctx.resolve_component(comp_rel)
        if svg:
            comp_html_parts.append(f'<div class="gen-component">{svg}</div>')

    headline_html = (
        f'<h1 class="gen-headline">{_esc(headline)}</h1>' if headline else ""
    )
    subtitle_html = (
        f'<p class="gen-subtitle">{_esc(subtitle)}</p>' if subtitle else ""
    )

    html = (
        f'<div class="st-generic">'
        f'{bg_html}'
        f'<div class="gen-content">'
        f'{headline_html}{subtitle_html}'
        f'{"".join(body_html_parts)}'
        f'{"".join(list_html_parts)}'
        f'{"".join(leftover_parts)}'
        f'{"".join(comp_html_parts)}'
        f'</div></div>'
    )

    css = """
.st-generic { position: relative; width: 100%; height: 100%; }
.st-generic-bg {
  position: absolute; inset: 0;
  background-size: cover; background-position: center; z-index: 0;
}
.st-generic .gen-content { position: relative; z-index: 1; }
.gen-headline {
  font-family: 'Montserrat', sans-serif; font-weight: 800;
  font-size: 26pt; color: var(--brand-primary);
  line-height: 1.12; letter-spacing: -0.01em; margin: 0 0 5mm 0;
}
.gen-subtitle {
  font-family: 'Source Sans 3', 'Source Sans Pro', sans-serif;
  font-style: italic; font-weight: 400; font-size: 12pt;
  color: var(--brand-primary); line-height: 1.4; margin: 0 0 6mm 0;
}
.st-generic .gen-content p {
  font-family: 'Source Sans 3', 'Source Sans Pro', sans-serif;
  font-weight: 400; font-size: 10pt; line-height: 1.5; color: #333333;
  margin: 0 0 3mm 0; hyphens: auto; text-align: justify;
}
.st-generic .gen-content p strong {
  font-family: 'Source Sans 3', 'Source Sans Pro', sans-serif;
  font-weight: 700; color: #333333;
}
.gen-list { margin: 0 0 5mm 0; padding-left: 5mm; }
.gen-list li {
  font-family: 'Source Sans 3', 'Source Sans Pro', sans-serif;
  font-size: 10pt; line-height: 1.45; color: #333333; margin: 0 0 1.5mm 0;
}
.gen-block { margin: 0 0 4mm 0; }
.gen-block-label {
  font-family: 'Montserrat', sans-serif; font-weight: 700; font-size: 9.5pt;
  color: var(--brand-primary); letter-spacing: 0.02em; margin: 0 0 1.5mm 0;
}
.gen-component { margin: 4mm 0; }
"""
    return PageFragment(html=html, css=css)
```

- [ ] **Step 4: Run it — expect PASS**

Run: `cd research/v7-renderer && .venv/bin/python -m pytest tests/test_render_r1.py -k generic -q`

- [ ] **Step 5: Verification checkpoint**

Run: `cd research/v7-renderer && .venv/bin/python -m pytest tests/ -q`
Expected: all green.

---

### Task 4: Refactor `st_07a` — full-doc → `render(page, ctx) -> PageFragment` (+ stat strip)

**Why:** `st_07a` today emits a complete `<html>` document via `render_lrp(...)`. R1 needs it to return a `PageFragment`: head-level CSS (`@page`/`@font-face`/`:root`/`body`) moves to the shared head; only the LRP-scoped CSS stays. It must read from the package `page` dict, resolve the portrait from `page["assets"]`, and **render the `ergebnis_metrics` stat strip** (correction #3 — apex case studies carry METRIKEN that must display). The `.page` table class is renamed to `.lrp-grid` to avoid colliding with the assembler's `.page` container.

**Venv:** renderer. **Files:**
- Modify: `research/v7-renderer/patterns/st_07a.py`
- Test: `research/v7-renderer/tests/test_render_r1.py` (append)

**Safety:** No other module imports `render_lrp` except the old `render.py` (reworked in Task 10) — verified: `tests/test_chassis_contract.py` imports none of it. So renaming `render_lrp` → `render` is safe.

- [ ] **Step 1: Append the failing test** to `tests/test_render_r1.py`:

```python
def _apex_case_study_page() -> dict:
    return {
        "slot": 7, "st_type": "ST-07A", "page_numbers": "10",
        "data": {
            "fallstudie_number": 1,
            "ergebnis_headline": "Von operativem Chaos zu skalierbarer KI-Infrastruktur",
            "kurzportraet": "Martina Ammon führt zwei Unternehmen parallel.",
            "ausgangsproblem": "Rapides Wachstum bedeutete täglich manuelle Anfragen.",
            "ziel": "Ohne automatisierte Betriebsebene frisst Kapazität sich selbst.",
            "loesung": "APEX implementierte Custom AI-Agenten in die bestehende Umgebung.",
            "ergebnis_text": "Anfragen in Minuten statt Stunden; Onboarding automatisch.",
            "ergebnis_metrics": [
                {"label": "Support-Reaktionszeit", "value": "24 Std. → Minuten"},
                {"label": "Support-Einsparung / Jahr", "value": "> 200.000 €"},
                {"label": "Automatisierte Kernprozesse", "value": "4"},
            ],
            "pullquote": {"text": "APEX hat unsere Antwortzeiten drastisch reduziert.",
                          "attribution": "Martina Ammon"},
            "kunde": {"name": "Martina Ammon", "funktion": "Gründerin",
                      "company_url": "example.de"},
        },
        "assets": [], "components": [],
    }


def test_st07a_returns_fragment_with_metrics(tmp_path) -> None:
    from patterns import st_07a
    frag = st_07a.render(_apex_case_study_page(), _ctx(tmp_path))
    assert isinstance(frag, PageFragment)
    assert frag.html.strip() and frag.css.strip()
    # head-level rules must NOT be in the fragment css
    assert "@page" not in frag.css
    assert "@font-face" not in frag.css
    assert ":root" not in frag.css
    # uses the renamed grid class, not the assembler's .page container
    assert "lrp-grid" in frag.css
    # case content present
    assert "Von operativem Chaos" in frag.html
    assert "FALLSTUDIE" in frag.html
    # METRIKEN stat strip renders (correction #3)
    assert "stat-strip" in frag.html
    assert "200.000" in frag.html
    assert "Support-Reaktionszeit" in frag.html


def test_st07a_omits_rail_photo_when_absent(tmp_path) -> None:
    from patterns import st_07a
    frag = st_07a.render(_apex_case_study_page(), _ctx(tmp_path))
    # no case_study_portrait asset -> no rail-photo background image
    assert "background-image:url(" not in frag.html or "rail-photo" not in frag.html
```

- [ ] **Step 2: Run it — expect FAIL** (`AttributeError: module 'patterns.st_07a' has no attribute 'render'`)

Run: `cd research/v7-renderer && .venv/bin/python -m pytest tests/test_render_r1.py -k st07a -q`

- [ ] **Step 3: Refactor `st_07a.py`**

Keep the module docstring, the `_qr_svg` helper, and the `_esc` helper. Add to the imports block (after `from preprocess import preprocess_body`):

```python
from patterns.base import PageFragment, RenderContext  # noqa: E402
```

Then **replace the entire `render_lrp(...)` function** (from `def render_lrp(` to the end of the file) with the following `render(...)`:

```python
def render(page: dict, ctx: RenderContext) -> PageFragment:
    """Render the ST-07A LRP case-study page as a PageFragment.

    Reads the package `page` dict (data + assets). Head-level CSS
    (@page/@font-face/:root/body) lives in the shared head (assembler);
    this returns only LRP-scoped CSS + the page body markup.
    """
    brand = ctx.brand
    grammar = ctx.grammar
    page_data: dict = page.get("data") or {}

    # ---- grammar required-present checks (FAIL LOUD) ----
    grammar.get_section("3.5")   # color discipline
    grammar.get_section("2")     # P-6 case study
    grammar.get_section("3.7")   # accent firing locations
    grammar.get_section("4.0")   # type axes

    _ = chassis_config  # kept live for future per-element-class calls

    # ---- QR (white on brand_primary panel) ----
    qr_svg = _qr_svg(url=brand.qr_target_url, fg="#FFFFFF", bg=brand.brand_primary)

    # ---- portrait from page assets (graceful if absent) ----
    photo_uri = None
    for a in (page.get("assets") or []):
        if a.get("slot_id") == "case_study_portrait" and a.get("path"):
            p = ctx.resolve_asset(a["path"])
            if p is not None:
                photo_uri = p.as_uri()
            break

    # ---- body fields (markdown -> HTML) ----
    kurzportraet_html = preprocess_body(page_data.get("kurzportraet", ""))
    ausgangsproblem_html = preprocess_body(page_data.get("ausgangsproblem", ""))
    ziel_html = preprocess_body(page_data.get("ziel", ""))
    loesung_html = preprocess_body(page_data.get("loesung", ""))
    ergebnis_html = preprocess_body(page_data.get("ergebnis_text", ""))
    pullquote_html = preprocess_body(page_data.get("pullquote", {}).get("text", ""))

    # ---- structured strings ----
    fallstudie_number = page_data.get("fallstudie_number", "")
    stamp_text = f"FALLSTUDIE 0{fallstudie_number}" if fallstudie_number else "FALLSTUDIE"
    headline = page_data.get("ergebnis_headline", "")
    kunde = page_data.get("kunde", {}) or {}
    kunde_url = kunde.get("company_url", "") or brand.company_url_display
    attribution = page_data.get("pullquote", {}).get("attribution", "")

    # ---- ergebnis_metrics stat strip (correction #3) ----
    metrics = page_data.get("ergebnis_metrics") or []
    stat_cells: list[str] = []
    for m in metrics:
        if isinstance(m, dict):
            label = m.get("label", "")
            value = m.get("value", "")
        elif isinstance(m, str) and ":" in m:
            label, value = (part.strip() for part in m.split(":", 1))
            label, value = value, label  # display value large, label small
            label, value = m.split(":", 1)[0].strip(), m.split(":", 1)[1].strip()
        else:
            label, value = "", str(m)
        if not (label or value):
            continue
        stat_cells.append(
            f'<div class="stat">'
            f'<div class="stat-value">{_esc(value)}</div>'
            f'<div class="stat-label">{_esc(label)}</div>'
            f'</div>'
        )
    metrics_html = (
        f'<div class="stat-strip">{"".join(stat_cells)}</div>' if stat_cells else ""
    )

    # ---- rail photo markup (omit when no portrait) ----
    rail_photo_html = (
        f'<div class="rail-photo" style="background-image:url(\'{photo_uri}\')" '
        f'aria-label="{_esc(kunde.get("name", ""))} photo"></div>'
        if photo_uri else ""
    )

    css = """
/* LRP-scoped CSS — head-level rules (@page/@font-face/:root/body) live
   in the shared head (assembler.py). Static only, so it dedupes across
   multiple ST-07A pages; per-page values (photo url, QR) are inlined. */
.lrp-grid { width: 100%; border-collapse: collapse; table-layout: fixed; }
.lrp-grid td { vertical-align: top; padding: 0; }
.lrp-grid td.left-rail { width: 28%; }            /* §2 P-6 LRP geometry */
.lrp-grid td.gap { width: 4mm; }

.rail-photo {
  width: 100%; height: 50mm;                       /* §2 P-6 photo height */
  background-size: cover; background-position: center;
  margin: 0 0 5mm 0; border-radius: 0; box-shadow: none;
}
.pullquote-panel {
  background-color: var(--brand-primary); color: #FFFFFF;
  padding: 6mm 5mm; border-radius: 0; box-shadow: none;
}
.pullquote-panel .quote-glyph {
  font-family: 'Source Sans 3', 'Source Sans Pro', sans-serif;
  font-style: italic; font-weight: 700; font-size: 36pt; line-height: 0.5;
  color: var(--brand-accent); margin: 1mm 0;       /* §3.7 firing location */
}
.pullquote-panel .quote-text {
  font-family: 'Source Sans 3', 'Source Sans Pro', sans-serif;
  font-style: italic; font-weight: 400; font-size: 10pt; line-height: 1.4;
  color: #FFFFFF; margin: 0 0 3mm 0;
}
.pullquote-panel .quote-attr {
  font-family: 'Montserrat', sans-serif; font-weight: 700; font-size: 7pt;
  letter-spacing: 0.15em; text-transform: uppercase;
  color: var(--brand-accent); margin: 0 0 3mm 0; line-height: 1.35;
}
.pullquote-panel hr { border: none; border-top: 0.5px solid rgba(255,255,255,0.22); margin: 1mm 0 2mm 0; }
.pullquote-panel .qr-wrap { display: flex; justify-content: center; }
.pullquote-panel .qr { width: 22mm; height: 22mm; border-radius: 0; overflow: hidden; }
.pullquote-panel .url {
  display: block; text-align: center; font-family: 'Montserrat', sans-serif;
  font-weight: 400; font-size: 9pt; color: var(--brand-accent);
  text-decoration: none; margin: 3mm 0 0 0; letter-spacing: 0.005em;
}
.right-col { width: auto; padding: 0 0 0 5mm; }
.fallstudie-stamp-wrap { display: block; margin: 0 0 8mm 0; text-align: left; }
.fallstudie-stamp {
  display: inline-block; border: 1.5px solid var(--brand-accent);
  padding: 4.5mm 12mm; font-family: 'Montserrat', sans-serif;
  font-weight: 700; font-size: 14pt; letter-spacing: 0.18em;
  color: var(--brand-accent); text-transform: uppercase; line-height: 1;
  border-radius: 0; box-shadow: none;              /* §3.7 stamp + §6.1 #1/#2 */
}
.case-headline {
  font-family: 'Montserrat', sans-serif; font-weight: 800; font-size: 24pt;
  color: var(--brand-primary); line-height: 1.10; letter-spacing: -0.02em;
  margin: 0 0 4mm 0; max-width: 100%; word-break: keep-all; overflow-wrap: break-word;
}
.case-lede {
  font-family: 'Source Sans 3', 'Source Sans Pro', sans-serif;
  font-style: italic; font-weight: 400; font-size: 11pt;
  color: var(--brand-primary); line-height: 1.4; margin: 0 0 6mm 0;
}
.body-section { margin: 0 0 7mm 0; }
.body-section h3 {
  font-family: 'Montserrat', sans-serif; font-weight: 700; font-size: 9.5pt;
  color: var(--brand-primary); letter-spacing: 0; margin: 0 0 2.5mm 0;
}
.body-section p {
  font-family: 'Source Sans 3', 'Source Sans Pro', sans-serif;
  font-weight: 400; font-size: 9.5pt; line-height: 1.45; color: #333333;
  margin: 0 0 2mm 0; hyphens: auto; text-align: left;
}
.body-section p strong {
  font-family: 'Source Sans 3', 'Source Sans Pro', sans-serif;
  font-weight: 700; color: #333333;
}
/* ergebnis_metrics stat strip (R1 add) */
.stat-strip { display: flex; gap: 6mm; margin: 6mm 0 0 0; }
.stat { flex: 1; }
.stat-value {
  font-family: 'Montserrat', sans-serif; font-weight: 800; font-size: 15pt;
  color: var(--brand-accent); line-height: 1.05;   /* §3.7 inline data emphasis */
}
.stat-label {
  font-family: 'Source Sans 3', 'Source Sans Pro', sans-serif;
  font-weight: 600; font-size: 7.5pt; color: #333333;
  letter-spacing: 0.04em; text-transform: uppercase; margin-top: 1mm;
}
"""

    html = f"""
<table class="lrp-grid">
  <tr>
    <td class="left-rail">
      <div class="rail-inner">
        {rail_photo_html}
        <div class="pullquote-panel">
          <div class="quote-glyph">„</div>
          {pullquote_html}
          <p class="quote-attr">— {_esc(attribution)}</p>
          <hr/>
          <div class="qr-wrap"><div class="qr">{qr_svg}</div></div>
          <a class="url" href="{_esc(kunde_url)}">{_esc(kunde_url)}</a>
        </div>
      </div>
    </td>
    <td class="gap"></td>
    <td class="right-col">
      <div class="fallstudie-stamp-wrap"><span class="fallstudie-stamp">{_esc(stamp_text)}</span></div>
      <h1 class="case-headline">{_esc(headline)}</h1>
      <div class="case-lede">{kurzportraet_html}</div>
      <div class="body-section"><h3>Ausgangssituation</h3>{ausgangsproblem_html}</div>
      <div class="body-section"><h3>Ziel</h3>{ziel_html}</div>
      <div class="body-section"><h3>Lösung</h3>{loesung_html}</div>
      <div class="body-section"><h3>Ergebnis</h3>{ergebnis_html}</div>
      {metrics_html}
    </td>
  </tr>
</table>
"""
    return PageFragment(html=html, css=css)
```

> NOTE on the metrics `str` branch: the redundant double-assignment lines above are a copy artifact — replace that `elif isinstance(m, str) and ":" in m:` branch body with exactly:
> ```python
>             label = m.split(":", 1)[0].strip()
>             value = m.split(":", 1)[1].strip()
> ```
> `report_content.json` uses the dict form, so the dict branch is the live path; the str branch is defensive.

- [ ] **Step 4: Run it — expect PASS**

Run: `cd research/v7-renderer && .venv/bin/python -m pytest tests/test_render_r1.py -k st07a -q`

- [ ] **Step 5: Verification checkpoint (guard included)**

Run: `cd research/v7-renderer && .venv/bin/python -m pytest tests/ -q`
Expected: all green — including `test_no_coral_in_chassis_logic` (the refactor introduces no `coral`).

---

### Task 5: `patterns/__init__.py` — dispatch registry

**Why:** The assembler needs `get_renderer(st_type)` → the right pattern, defaulting to `_generic`.

**Venv:** renderer. **Files:**
- Modify: `research/v7-renderer/patterns/__init__.py`
- Test: `research/v7-renderer/tests/test_render_r1.py` (append)

- [ ] **Step 1: Append the failing test:**

```python
def test_registry_dispatch() -> None:
    from patterns import get_renderer
    from patterns import st_07a, _generic
    assert get_renderer("ST-07A") is st_07a.render
    assert get_renderer("ST-99") is _generic.render
    assert get_renderer("ST-01") is _generic.render
```

- [ ] **Step 2: Run it — expect FAIL** (`ImportError: cannot import name 'get_renderer'`)

Run: `cd research/v7-renderer && .venv/bin/python -m pytest tests/test_render_r1.py -k registry -q`

- [ ] **Step 3: Implement `patterns/__init__.py`** (replace the docstring-only file):

```python
"""Pattern package — dispatch registry.

R1 ships ONE real pattern (ST-07A); every other ST type renders through
the brand-styled `_generic` skeleton. R2 adds the remaining patterns by
registering them in REGISTRY below.
"""

from __future__ import annotations

from typing import Callable

from patterns.base import PageFragment, RenderContext
from patterns import st_07a, _generic

# ST type -> pattern render function.
REGISTRY: dict[str, Callable[[dict, RenderContext], PageFragment]] = {
    "ST-07A": st_07a.render,
}


def get_renderer(st_type: str) -> Callable[[dict, RenderContext], PageFragment]:
    """Return the pattern render() for an ST type, defaulting to _generic."""
    return REGISTRY.get(st_type, _generic.render)
```

- [ ] **Step 4: Run it — expect PASS**

Run: `cd research/v7-renderer && .venv/bin/python -m pytest tests/test_render_r1.py -k registry -q`

- [ ] **Step 5: Verification checkpoint**

Run: `cd research/v7-renderer && .venv/bin/python -m pytest tests/ -q`
Expected: all green.

---

### Task 6: `package_loader.py` — read `resolved_package.json`

**Why:** Turn the package directory into a typed `LoadedPackage` (BrandConfig + pages + report_assets + fonts). FAIL LOUD when the manifest is missing or `brand` is incomplete (reuse `parse_brand_tokens`'s ValueError). No change to `brand_tokens.py`.

**Venv:** renderer. **Files:**
- Create: `research/v7-renderer/package_loader.py`
- Test: `research/v7-renderer/tests/test_render_r1.py` (append)

> This task tests against the **existing** `fixtures/apex/resolved_package.json` (currently the SAMPLE structure). That's fine — the loader is content-agnostic; it just needs a valid package. Task 8 later overwrites that file with real apex content.

- [ ] **Step 1: Append the failing test:**

```python
FIXTURES_APEX = CHASSIS_ROOT / "fixtures" / "apex"


def test_load_package_returns_typed_package() -> None:
    from package_loader import load_package, LoadedPackage
    from brand_tokens import BrandConfig
    pkg = load_package(FIXTURES_APEX)
    assert isinstance(pkg, LoadedPackage)
    assert isinstance(pkg.brand, BrandConfig)
    assert pkg.brand.brand_primary.startswith("#")
    assert len(pkg.pages) >= 1
    assert all(isinstance(p, dict) and "st_type" in p for p in pkg.pages)
    assert pkg.package_dir == FIXTURES_APEX.resolve()
    assert isinstance(pkg.report_assets, list)
    assert isinstance(pkg.fonts, dict)


def test_load_package_missing_manifest_raises(tmp_path) -> None:
    from package_loader import load_package
    with pytest.raises(FileNotFoundError):
        load_package(tmp_path)  # empty dir, no resolved_package.json


def test_load_package_incomplete_brand_raises(tmp_path) -> None:
    import json
    from package_loader import load_package
    (tmp_path / "resolved_package.json").write_text(
        json.dumps({"brand": {"brand_primary": "#111"}, "pages": []}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError):  # parse_brand_tokens: missing required keys
        load_package(tmp_path)
```

- [ ] **Step 2: Run it — expect FAIL** (`ModuleNotFoundError: No module named 'package_loader'`)

Run: `cd research/v7-renderer && .venv/bin/python -m pytest tests/test_render_r1.py -k load_package -q`

- [ ] **Step 3: Implement `package_loader.py`**

```python
"""Package loader — reads the pre-processor's resolved_package.json.

Turns a package directory into a typed LoadedPackage the assembler
consumes. FAIL LOUD when the manifest is missing or the brand block is
incomplete (parse_brand_tokens raises ValueError naming the missing
field) — the renderer must not render against a half-resolved package.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

# Allow flat imports from the chassis package.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from brand_tokens import BrandConfig, parse_brand_tokens  # noqa: E402


@dataclass
class LoadedPackage:
    brand: BrandConfig
    pages: list[dict]            # package pages verbatim (incl. page_numbers)
    report_assets: list[dict]
    fonts: dict
    package_dir: Path


def load_package(package_dir: Path) -> LoadedPackage:
    package_dir = Path(package_dir).resolve()
    manifest_path = package_dir / "resolved_package.json"
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"resolved_package.json not found in {package_dir}. The renderer "
            f"consumes a pre-processor package; point it at a directory that "
            f"contains resolved_package.json."
        )

    pkg = json.loads(manifest_path.read_text(encoding="utf-8"))

    # FAIL LOUD on incomplete brand (reuses the chassis's 10-field gate).
    brand = parse_brand_tokens(pkg.get("brand", {}))

    pages = pkg.get("pages", [])
    if not isinstance(pages, list):
        raise ValueError(
            f"resolved_package.json 'pages' must be a list; got {type(pages)}."
        )

    return LoadedPackage(
        brand=brand,
        pages=pages,
        report_assets=pkg.get("report_assets", []) or [],
        fonts=pkg.get("fonts", {}) or {},
        package_dir=package_dir,
    )
```

- [ ] **Step 4: Run it — expect PASS**

Run: `cd research/v7-renderer && .venv/bin/python -m pytest tests/test_render_r1.py -k load_package -q`

- [ ] **Step 5: Verification checkpoint**

Run: `cd research/v7-renderer && .venv/bin/python -m pytest tests/ -q`
Expected: all green.

---

### Task 7: `validators/overflow.py` — real per-page overflow check

**Why:** Post-layout truth. Render a page's content as a standalone 1-page document; if WeasyPrint emits >1 physical page, the content overflowed. Advisory (surfaced in `RenderResult.overflow`), never blocks — mirrors `accent_budget`.

**Venv:** renderer. **Files:**
- Modify (rewrite): `research/v7-renderer/validators/overflow.py`
- Test: `research/v7-renderer/tests/test_render_r1.py` (append)

- [ ] **Step 1: Append the failing test:**

```python
def _doc(body: str) -> str:
    return (
        "<html><head><style>"
        "@page { size: A4; margin: 15mm; } "
        "body { font-family: sans-serif; font-size: 12pt; }"
        "</style></head><body>" + body + "</body></html>"
    )


def test_overflow_false_for_fitting_content() -> None:
    from validators.overflow import check_overflow
    assert check_overflow(_doc("<p>A short paragraph that fits one page.</p>")) is False


def test_overflow_true_for_too_much_content() -> None:
    from validators.overflow import check_overflow
    huge = "<p>" + ("Wort " * 6000) + "</p>"
    assert check_overflow(_doc(huge)) is True
```

- [ ] **Step 2: Run it — expect FAIL** (`ImportError: cannot import name 'check_overflow'`)

Run: `cd research/v7-renderer && .venv/bin/python -m pytest tests/test_render_r1.py -k overflow -q`

- [ ] **Step 3: Rewrite `validators/overflow.py`**

```python
"""Text-overflow validator — real (R1).

Post-layout truth: render a single page's content as a standalone
1-page document; if WeasyPrint produces >1 physical page, the content
overflowed its box. Advisory only — the assembler records the flag in
RenderResult.overflow and never blocks the render (mirrors accent_budget).

The per-page standalone render is acceptable at QA/build time; it can be
optimized later if it dominates render time.
"""

from __future__ import annotations

from typing import Optional

import weasyprint


def count_pages(html_doc: str, base_url: Optional[str] = None) -> int:
    """Return the number of physical pages WeasyPrint lays out for `html_doc`."""
    document = weasyprint.HTML(string=html_doc, base_url=base_url).render()
    return len(document.pages)


def check_overflow(html_doc: str, base_url: Optional[str] = None) -> bool:
    """True iff `html_doc` lays out to more than one physical page."""
    return count_pages(html_doc, base_url) > 1
```

- [ ] **Step 4: Run it — expect PASS**

Run: `cd research/v7-renderer && .venv/bin/python -m pytest tests/test_render_r1.py -k overflow -q`

- [ ] **Step 5: Verification checkpoint**

Run: `cd research/v7-renderer && .venv/bin/python -m pytest tests/ -q`
Expected: all green.

---

### Task 8: Regenerate the apex fixture from real content (correction #2)

**Why:** The committed `fixtures/apex/resolved_package.json` is the SAMPLE page structure (mein-werkzeugkoffer: 20 pages, ST-01/02/05/09…, 3× ST-07A). It carries the apex IMAGES but the wrong page set/data. R1 regenerates it from the apex content as **structured DATA**, reusing the real pre-processor Stage 8 (`assemble_package`) so the package schema cannot drift. **No fal / no network / no API keys** — existing apex images are fed in directly as already-generated assets.

**Venv:** pre-processor (the generator imports the pre-processor stages). **Files (all NEW, all on the renderer side so the pre-processor guard never scans them):**
- Create: `research/v7-renderer/fixtures/apex/brand_input.json`
- Create: `research/v7-renderer/fixtures/apex/image_map.json`
- Create: `research/v7-renderer/fixtures/apex/report_content.json`
- Create: `research/v7-renderer/fixtures/apex/build_package.py`

**Slot plan (authoritative — 20 single pages; spreads collapsed):**

| slot | type | page_numbers | source section in `content for apex.md` | data keys |
|---|---|---|---|---|
| 1 | ST-01 | "1" | COVER | title, subtitle, teaser_bullets[], intro |
| 2 | ST-02 | "2" | OUTLOOK | title, body |
| 3 | ST-05 | "3" | ABOUT | title, body, credibility_points[] |
| 4 | ST-09 | "4" | STATUS QUO | title, body, symptoms[] |
| 5 | ST-14 | "5" | FALSE BELIEFS | title, body, beliefs[] |
| 6 | ST-31 | "6" | — (breathing) | {} |
| 7 | ST-07A | "7" | CASE STUDY 1 (Martina Ammon) | full ST-07A (see mapping) |
| 8 | ST-07B | "8" | THEORY 1 | title, body, key_insight |
| 9 | ST-07A | "9" | CASE STUDY 2 (Cordes) | full ST-07A |
| 10 | ST-07B | "10" | THEORY 2 | title, body, key_insight |
| 11 | ST-31 | "11" | — (breathing) | {} |
| 12 | ST-07A | "12" | CASE STUDY 3 (Frese) | full ST-07A |
| 13 | ST-07B | "13" | THEORY 3 | title, body, key_insight |
| 14 | ST-07A | "14" | CASE STUDY 4 (Conesso) | full ST-07A |
| 15 | ST-07A | "15" | CASE STUDY 5 (Hanisch & Klein) | full ST-07A |
| 16 | ST-06 | "16" | MECHANISM | title, body, steps[] |
| 17 | ST-31 | "17" | — (breathing) | {} |
| 18 | ST-FAZIT | "18" | SUMMARY | title, body, these, kosten_des_nichtstuns |
| 19 | ST-22 | "19" | COLLABORATION | title, body, steps[] |
| 20 | ST-03 | "20" | CTA | title, body, cta_text, cta_url |

ST-07A count = 5 (slots 7, 9, 12, 14, 15) ✓ ≥3. slot 1 = ST-01 ✓. slot 20 = ST-03 ✓. page_count_target = 20 ✓. Breathing at 6/11/17 (non-adjacent) ✓.

**ST-07A apex→key mapping (verified against `st_07a`):** `KURZPORTRÄT`→`kurzportraet`, `AUSGANGSPROBLEM`→`ausgangsproblem`, `WENDEPUNKT`→`ziel` (only CS1 + CS5 have it; others → `""`), `LÖSUNG`→`loesung`, `ERGEBNIS`→`ergebnis_text`, headline→`ergebnis_headline`, `FALLSTUDIE N`→`fallstudie_number` (int N), `METRIKEN` lines→`ergebnis_metrics` (each `"Label: value"` → `{"label","value"}`), quote→`pullquote.text`, `— Name`→`pullquote.attribution`, `KUNDE` line→`kunde.name`/`kunde.funktion` (+ `company_url`: `"apex-consulting.ai"`).

- [ ] **Step 1: Create `brand_input.json`** (apex brand as DATA — the 10 chassis fields + the profile that drives `resolve_fonts`):

```json
{
  "brand_tokens": {
    "brand_primary": "#5a9ab3",
    "brand_accent": "#85d2ee",
    "brand_neutral_dark": "#0F0F1F",
    "brand_neutral_mid": "#7A7A8C",
    "brand_neutral_light": "#fdffff",
    "font_heading": "Gestura Headline",
    "font_body": "Source Sans 3",
    "qr_target_url": "https://apex-consulting.ai",
    "company_name_short": "APEX Consulting",
    "company_url_display": "apex-consulting.ai"
  },
  "brand_profile": {
    "font_head": "Gestura Headline",
    "font_body": "Source Sans 3",
    "accent_mechanic": "tonal_same_hue",
    "ground_mode": "cool_light",
    "texture": "smooth",
    "headline_type": "serif"
  }
}
```

- [ ] **Step 2: Create `image_map.json`** (maps the existing PNGs in `fixtures/apex/assets/` to slots; everything not on a page becomes a report-level asset so nothing is lost):

```json
{
  "page_assets": [
    {"slot": 1, "slot_id": "cover_hero", "image_type": "background", "file": "1_cover_hero.png"},
    {"slot": 4, "slot_id": "status_quo_scene", "image_type": "scene", "file": "4_status_quo_scene.png"}
  ],
  "report_assets": [
    {"slot_id": "status_quo_scene_b", "image_type": "scene", "file": "5_status_quo_scene.png"},
    {"slot_id": "background_texture", "image_type": "texture", "file": "report_background_texture.png"},
    {"slot_id": "atmospheric_gradient", "image_type": "gradient", "file": "report_atmospheric_gradient.png"},
    {"slot_id": "extra_square", "image_type": "background", "file": "report_extra_square.png"},
    {"slot_id": "extra_wide", "image_type": "background", "file": "report_extra_wide.png"}
  ]
}
```

> Before writing this file, run `ls research/v7-renderer/fixtures/apex/assets/` and confirm the 7 filenames match. If any differ, correct the `file` values to the real names. Files referenced here MUST exist (the generator asserts this).

- [ ] **Step 3: Create `report_content.json`** — the apex content as structured DATA. Author it by transcribing `content for apex.md` (repo root) into this exact schema, following the slot table + ST-07A mapping above. Below is the complete `meta`, plus FOUR fully-worked pages that fix the exact shape of every page type (generic-with-list, ST-07A, ST-07B, breathing, CTA). **Transcribe the remaining slots verbatim from the named source section**, copying the German text exactly (including the `„` quote glyphs as written).

```json
{
  "meta": {
    "client_slug": "apex",
    "report_id": "APEX-R1",
    "lang": "de",
    "page_format": "A4",
    "page_count_target": 20,
    "awareness_level": 2
  },
  "pages": [
    {
      "slot": 1, "type": "ST-01", "page_numbers": "1",
      "data": {
        "title": "Dein Wachstum frisst dich selbst auf",
        "subtitle": "Wie manuelle Prozesse und fehlendes Automatisierungssystem B2B-Geschäftsführer zum Flaschenhals ihrer eigenen Firma machen.",
        "intro": "Dein Unternehmen wächst. Neue Kunden kommen rein, das Team ist beschäftigt, der Umsatz steigt. Und trotzdem schläfst du schlecht. Dieser Report zeigt, warum mehr Mitarbeiter das Problem nicht lösen – und wie AI-Agenten repetitive Kernprozesse vollständig übernehmen, 30-50% der Betriebskosten eliminieren und dein Unternehmen skalierbar machen.",
        "teaser_bullets": [
          "Warum 60% aller AI-Investitionen keinen messbaren Wert liefern – und welche 3 Bedingungen den Unterschied machen (BCG, 2026).",
          "Wie B2B-Firmen Umsatz skalieren, ohne einen einzigen neuen Mitarbeiter einzustellen.",
          "Welche 5 Prozesse in deinem Unternehmen gerade still Kapazität verbrennen – und wie du sie in unter 30 Tagen automatisierst."
        ]
      }
    },
    {
      "slot": 7, "type": "ST-07A", "page_numbers": "7",
      "data": {
        "fallstudie_number": 1,
        "ergebnis_headline": "Von operativem Chaos zu skalierbarer KI-Infrastruktur",
        "kurzportraet": "Martina Ammon führt parallel eine Anwaltskanzlei und ein Coaching-Business. Zwei Unternehmen, eine Gründerin, ein Team – und ein Kundenstamm, der schneller wuchs als die Kapazität, ihn zu betreuen.",
        "ausgangsproblem": "Rapides Wachstum klingt nach Erfolg. Für Martina Ammon bedeutete es: täglich neue Anfragen, die manuell beantwortet werden mussten. Jede Kundenaufnahme lief über handgeschriebene Formulare und Copy-Paste-Prozesse. Die Gründerin verbrachte mehr Zeit damit, operative Brände zu löschen, als strategisch zu arbeiten.",
        "ziel": "Der Wendepunkt kam, als Martina Ammon erkannte, dass kein weiterer Mitarbeiter das Grundproblem lösen würde: Ohne automatisierte Betriebsebene würde jede neue Kapazität sofort von manuellen Prozessen aufgefressen.",
        "loesung": "APEX Consulting implementierte Custom AI-Agenten direkt in Martina Ammons bestehende Tool-Umgebung – ohne Migration, ohne monatelanges IT-Projekt. Ein automatisierter Kundenaufnahme-Prozess ersetzte die manuellen Formulare. Ein Dokumentenverarbeitungs-Agent übernahm repetitive Dateioperationen. Ein 24/7-Support-Tool beantwortete Standardanfragen ohne menschliches Eingreifen.",
        "ergebnis_text": "Die operative Belastung, die Martina Ammon täglich gebunden hatte, wurde systematisch eliminiert. Kundenanfragen wurden in Minuten statt Stunden beantwortet. Zum ersten Mal konnte die Gründerin wachsendes Volumen bewältigen, ohne proportional mehr Zeit zu investieren.",
        "ergebnis_metrics": [
          {"label": "Support-Reaktionszeit", "value": "24 Std. → Minuten"},
          {"label": "Support-Einsparung / Jahr", "value": "> 200.000 €"},
          {"label": "Automatisierte Kernprozesse", "value": "4"}
        ],
        "pullquote": {
          "text": "APEX hat unsere Antwortzeiten von bis zu 24 Stunden auf wenige Minuten reduziert und uns geholfen, über 200.000 € pro Jahr an Support-Kosten einzusparen.",
          "attribution": "Martina Ammon"
        },
        "kunde": {
          "name": "Martina Ammon",
          "funktion": "Gründerin, Anwaltskanzlei & Coaching-Business",
          "company_url": "apex-consulting.ai"
        }
      }
    },
    {
      "slot": 8, "type": "ST-07B", "page_numbers": "8",
      "data": {
        "title": "Wachstum entsteht nicht durch mehr Köpfe",
        "body": "Wer skaliert, ohne Prozesse zu automatisieren, kauft sich Overhead — kein Wachstum.\n\nDas Muster ist immer dasselbe. Ein Unternehmen wächst. Die erste Reaktion: neue Mitarbeiter einstellen. Das Problem verschwindet nicht — es wird teurer. Denn das eigentliche Engpass-Problem liegt nicht im Headcount, sondern in den Prozessen, die jeder neue Mitarbeiter zusätzlich bedienen muss.",
        "key_insight": "Operative Engpässe durch manuelle Prozesse deckelten die Kapazität — nicht fehlende Nachfrage oder fehlendes Personal."
      }
    },
    {
      "slot": 6, "type": "ST-31", "page_numbers": "6",
      "data": {}
    },
    {
      "slot": 20, "type": "ST-03", "page_numbers": "20",
      "data": {
        "title": "Buche jetzt dein kostenloses Erstgespräch mit APEX",
        "body": "Dein Team verbrennt täglich Stunden mit manuellen Prozessen, die morgen automatisiert sein könnten. Buch jetzt dein Erstgespräch – APEX analysiert deine drei größten Bottlenecks und zeigt dir konkret, welche Prozesse sofort automatisiert werden können. Kein IT-Projekt. Kein Risiko.",
        "cta_text": "Jetzt Erstgespräch buchen",
        "cta_url": "https://apex-consulting.ai/"
      }
    }
  ]
}
```

> **Transcription instruction (no placeholders):** Insert the remaining 15 page objects (slots 2, 3, 4, 5, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19) into the `pages` array, ordered by slot. Use the slot table for `type`/`page_numbers`/`data` keys and the ST-07A mapping for the case studies (slots 9, 12, 14, 15). Copy the German text **verbatim** from the matching section of `content for apex.md`. Breathing pages (slot 11, 17) use `"data": {}` exactly like slot 6. For list fields: `credibility_points`/`symptoms`/`beliefs`/`steps` are arrays of strings (one entry per labelled item in the source); for ST-06 MECHANISM and ST-22 COLLABORATION, each step is the step's heading + its paragraph joined as one string. For slots 9/12/14 (CS2/CS3/CS4) there is no WENDEPUNKT → set `"ziel": ""`.

- [ ] **Step 4: Create `build_package.py`** (the generator — reuses the real Stage 8; runs under the pre-processor venv):

```python
"""Regenerate fixtures/apex/resolved_package.json from structured apex DATA.

Reuses the REAL pre-processor stages (resolve_fonts, generate_components,
plan_layout, assemble_package) so the package schema cannot drift from
what /render produces. NO fal / NO network / NO API keys: the existing
apex images in fixtures/apex/assets/ are fed in directly as already-
generated AssetResults.

Run (pre-processor venv):
    cd research/preprocessor && .venv/bin/python ../v7-renderer/fixtures/apex/build_package.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent              # research/v7-renderer/fixtures/apex
V7 = HERE.parent.parent                              # research/v7-renderer
RESEARCH = V7.parent                                 # research
PREPROCESSOR = RESEARCH / "preprocessor"
sys.path.insert(0, str(PREPROCESSOR))

from models import ReportJson, BrandProfile          # noqa: E402
from stages.resolve_fonts import resolve_fonts        # noqa: E402
from stages.generate_components import generate_components_for_report  # noqa: E402
from stages.plan_layout import plan_layout            # noqa: E402
from stages.assemble_package import assemble_package  # noqa: E402
from stages.generate_assets import AssetPlan, AssetResult  # noqa: E402
from stages.validate_copy import validate_copy        # noqa: E402
from stages.validate_copyfit import validate_copyfit  # noqa: E402


def _load(name: str) -> dict:
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def _build_asset_plan(image_map: dict) -> AssetPlan:
    assets: list[AssetResult] = []
    assets_dir = HERE / "assets"
    for entry in image_map.get("page_assets", []):
        f = assets_dir / entry["file"]
        if not f.exists():
            raise FileNotFoundError(f"page asset missing: {f}")
        assets.append(AssetResult(
            slot_id=entry["slot_id"], status="generated", path=f,
            message="reused apex fixture image (R1 generator)",
            page_slot=int(entry["slot"]), image_type=entry["image_type"],
            prompt=None, negative_prompt=None,
        ))
    for entry in image_map.get("report_assets", []):
        f = assets_dir / entry["file"]
        if not f.exists():
            raise FileNotFoundError(f"report asset missing: {f}")
        assets.append(AssetResult(
            slot_id=entry["slot_id"], status="generated", path=f,
            message="reused apex fixture image (R1 generator)",
            page_slot=None, image_type=entry["image_type"],
            prompt=None, negative_prompt=None,
        ))
    return AssetPlan(
        assets=assets,
        total_required=len(assets), total_downloaded=0, total_stubbed=0,
        total_client_upload_needed=0, total_failed=0, total_generated=len(assets),
        warnings=[],
    )


async def main() -> int:
    brand_input = _load("brand_input.json")
    image_map = _load("image_map.json")
    report_content = _load("report_content.json")

    brand_tokens = brand_input["brand_tokens"]
    brand_profile = BrandProfile(**brand_input["brand_profile"])

    report_model = ReportJson(**report_content)
    pages = report_model.pages
    page_count_target = report_model.meta.page_count_target

    font_config = resolve_fonts(brand_profile)
    components = generate_components_for_report(
        pages,
        brand_primary=brand_tokens["brand_primary"],
        brand_accent=brand_tokens["brand_accent"],
        brand_neutral_light=brand_tokens["brand_neutral_light"],
    )
    plan = plan_layout(pages, components=components, page_count_target=page_count_target)
    asset_plan = _build_asset_plan(image_map)
    copy_warnings = validate_copy(pages) + validate_copyfit(pages)

    resolved = await assemble_package(
        brand_tokens=brand_tokens,
        font_config=font_config,
        copy_warnings=copy_warnings,
        cover_validation=None,
        asset_plan=asset_plan,
        components=components,
        layout_plan=plan,
        report_json=report_content,
        output_dir=HERE,
    )

    # ---- sanity assertions (FAIL LOUD if the package is wrong) ----
    pkg = json.loads((HERE / "resolved_package.json").read_text(encoding="utf-8"))
    st_types = [p["st_type"] for p in pkg["pages"]]
    assert len(pkg["pages"]) == 20, f"expected 20 pages, got {len(pkg['pages'])}"
    assert st_types[0] == "ST-01" and st_types[-1] == "ST-03", st_types
    assert st_types.count("ST-07A") == 5, st_types
    assert all("page_numbers" in p for p in pkg["pages"]), "page_numbers missing"
    cover_assets = [a["slot_id"] for a in pkg["pages"][0]["assets"]]
    assert "cover_hero" in cover_assets, cover_assets
    assert len(pkg["report_assets"]) >= 4, pkg["report_assets"]

    print(f"[build_apex] wrote {resolved.package_path}")
    print(f"[build_apex] pages={len(pkg['pages'])} st07a={st_types.count('ST-07A')} "
          f"report_assets={len(pkg['report_assets'])} warnings={resolved.total_warnings}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
```

- [ ] **Step 5: Run the generator + verify the package**

Run: `cd research/preprocessor && .venv/bin/python ../v7-renderer/fixtures/apex/build_package.py`
Expected: prints `[build_apex] wrote …/fixtures/apex/resolved_package.json` and `pages=20 st07a=5 report_assets>=4 …` with **no AssertionError**.

- [ ] **Step 6: Confirm pre-processor suite still green** (no regressions; the generator imports stages but doesn't change them)

Run: `cd research/preprocessor && .venv/bin/python -m pytest tests/ -q`
Expected: all green (same total as Task 1's checkpoint).

---

### Task 9: `assembler.py` — shared head + dispatch + WeasyPrint + validators

**Why:** The orchestrator. Loads the package, dispatches each page to its pattern, builds ONE document (shared `<head>` + deduped fragment CSS + one `<section class="page">` per page with a per-page folio via WeasyPrint `string-set`), renders to PDF, rasterizes PNGs, runs overflow + accent-budget validators. Catches per-page pattern errors → falls back to `_generic` → records a warning (never crashes; always emits a PDF).

**Venv:** renderer. **Depends on:** Task 8 (the regenerated fixture) for the integration test. **Files:**
- Create: `research/v7-renderer/assembler.py`
- Test: `research/v7-renderer/tests/test_render_r1.py` (append)

- [ ] **Step 1: Append the failing tests:**

```python
def test_shared_head_has_page_fonts_and_folio() -> None:
    from assembler import shared_head_css
    css = shared_head_css(parse_brand_tokens(SAMPLE_BRAND), CHASSIS_ROOT / "fonts")
    assert "@page" in css
    assert "@font-face" in css
    assert "--brand-primary" in css
    assert "string(pagefolio)" in css  # per-page folio mechanism


def test_render_package_apex(tmp_path) -> None:
    """Integration: the regenerated apex package renders to a 20-page PDF."""
    from assembler import render_package, RenderResult
    result = render_package(FIXTURES_APEX, tmp_path)
    assert isinstance(result, RenderResult)
    assert result.pdf_path.exists()
    assert result.pdf_path.stat().st_size > 5000
    assert result.page_count == 20            # logical package pages
    assert len(result.png_paths) >= 20        # physical pages rasterized
    assert isinstance(result.overflow, list)
    assert isinstance(result.warnings, list)
```

- [ ] **Step 2: Run it — expect FAIL** (`ModuleNotFoundError: No module named 'assembler'`)

Run: `cd research/v7-renderer && .venv/bin/python -m pytest tests/test_render_r1.py -k "shared_head or render_package_apex" -q`

- [ ] **Step 3: Implement `assembler.py`**

```python
"""Assembler — package -> one HTML document -> PDF + PNGs + validators.

Flow:
  load_package() -> for each page dispatch to its pattern -> PageFragment
  -> assemble ONE document (shared <head> + deduped fragment CSS + one
  <section class="page st-XX"> per page, each carrying a per-page folio
  via WeasyPrint `string-set: pagefolio`) -> WeasyPrint write_pdf ->
  PyMuPDF rasterize -> overflow + accent-budget validators.

Never crashes: a pattern that raises is caught, the page falls back to
_generic (then to a placeholder), and a warning is recorded. The render
ALWAYS returns a RenderResult with a PDF + a warnings list.

R1 boundaries (documented, not bugs):
  - Print bleed / crop marks: Layer 3 (post-processor) scope; R1 emits
    plain A4 RGB.
  - Full-bleed page backgrounds size to the page CONTENT box (not the
    physical sheet); visual-tuning is R2.
  - report_assets are loaded into LoadedPackage and carried in the
    package, but axis-driven page backgrounds need the §4.0 axes which
    live on the pre-processor BrandProfile, NOT the 10-field BrandConfig
    the renderer consumes — so auto-applying them is R2 (would require
    threading axes into BrandConfig). Per-page background ASSETS (e.g.
    the cover hero) ARE rendered, via _generic.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import weasyprint  # noqa: E402

from package_loader import load_package  # noqa: E402
from grammar_loader import load_grammar  # noqa: E402
from patterns import get_renderer  # noqa: E402
from patterns import _generic  # noqa: E402
from patterns.base import PageFragment, RenderContext  # noqa: E402
from validators.overflow import check_overflow  # noqa: E402
from validators.accent_budget import AccentBudgetValidator  # noqa: E402

FONT_DIR = (HERE / "fonts").resolve()


@dataclass
class RenderResult:
    pdf_path: Path
    png_paths: list[Path]
    page_count: int              # logical package pages
    overflow: list[str]          # per-page overflow flags (advisory)
    accent_budget_passed: bool
    warnings: list[str] = field(default_factory=list)


def _esc(s: str) -> str:
    return (
        str(s).replace("&", "&amp;").replace("<", "&lt;")
        .replace(">", "&gt;").replace('"', "&quot;")
    )


def shared_head_css(brand, font_dir: Path) -> str:
    """Cross-page CSS owned by the head: @font-face x4, :root brand vars,
    @page (A4 + margins + wordmark + per-page folio), body, .page.
    """
    font_uri = Path(font_dir).resolve().as_uri()
    return f"""
@font-face {{ font-family:'Montserrat'; src:url('{font_uri}/Montserrat%5Bwght%5D.ttf') format('truetype'); font-weight:100 900; font-style:normal; }}
@font-face {{ font-family:'Montserrat'; src:url('{font_uri}/Montserrat-Italic%5Bwght%5D.ttf') format('truetype'); font-weight:100 900; font-style:italic; }}
@font-face {{ font-family:'Source Sans 3'; src:url('{font_uri}/SourceSans3%5Bwght%5D.ttf') format('truetype'); font-weight:200 900; font-style:normal; }}
@font-face {{ font-family:'Source Sans 3'; src:url('{font_uri}/SourceSans3-Italic%5Bwght%5D.ttf') format('truetype'); font-weight:200 900; font-style:italic; }}
:root {{
  --brand-primary: {brand.brand_primary};
  --brand-accent: {brand.brand_accent};
  --brand-neutral-dark: {brand.brand_neutral_dark};
  --brand-neutral-mid: {brand.brand_neutral_mid};
  --brand-neutral-light: {brand.brand_neutral_light};
}}
@page {{
  size: A4 portrait;
  margin: 16mm 14mm 20mm 18mm;
  background-color: var(--brand-neutral-light);
  @top-left {{
    content: "{_esc(brand.company_name_short)}";
    font-family: 'Montserrat', sans-serif; font-weight: 400; font-size: 8pt;
    color: var(--brand-primary); letter-spacing: 0.005em; padding: 6mm 0 0 0;
  }}
  @bottom-left {{
    content: string(pagefolio);
    font-family: 'Montserrat', sans-serif; font-weight: 400; font-size: 7.5pt;
    color: var(--brand-neutral-mid); padding: 0 0 4mm 0;
  }}
}}
* {{ box-sizing: border-box; }}
html {{ font-size: 10pt; }}
body {{
  font-family: 'Source Sans 3', 'Source Sans Pro', sans-serif;
  color: #333333; margin: 0; line-height: 1.42;
}}
.page {{ position: relative; break-after: page; }}
.page:last-child {{ break-after: auto; }}
"""


def _folio(page: dict, index: int) -> str:
    val = page.get("page_numbers")
    folio = str(val) if val else str(index + 1)
    return folio.replace("\\", "").replace("'", "")


def _section(page: dict, frag: PageFragment, index: int) -> str:
    st = str(page.get("st_type", "")).lower()
    folio = _folio(page, index)
    return (
        f'<section class="page {st}" '
        f'style="string-set: pagefolio \'{folio}\';">{frag.html}</section>'
    )


def render_package(package_dir: Path, output_dir: Path) -> RenderResult:
    package_dir = Path(package_dir).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    pkg = load_package(package_dir)
    grammar = load_grammar()
    warnings: list[str] = []

    # ---- dispatch each page (never crash) ----
    fragments: list[tuple[dict, PageFragment]] = []
    for page in pkg.pages:
        st_type = str(page.get("st_type", ""))
        slot = page.get("slot")
        ctx = RenderContext(brand=pkg.brand, grammar=grammar, package_dir=pkg.package_dir)
        try:
            frag = get_renderer(st_type)(page, ctx)
        except Exception as exc:  # noqa: BLE001 — isolate per-page failures
            warnings.append(f"slot {slot} ({st_type}): pattern raised {exc!r}; using generic")
            try:
                frag = _generic.render(page, ctx)
            except Exception as exc2:  # noqa: BLE001
                warnings.append(f"slot {slot} ({st_type}): generic raised {exc2!r}; placeholder")
                frag = PageFragment(
                    html=f'<div class="st-generic"><p>page {slot} could not render</p></div>',
                    css="",
                )
        fragments.append((page, frag))

    # ---- shared head + deduped fragment CSS ----
    head = shared_head_css(pkg.brand, FONT_DIR)
    seen: set[str] = set()
    css_blocks: list[str] = []
    for _, frag in fragments:
        if frag.css and frag.css not in seen:
            seen.add(frag.css)
            css_blocks.append(frag.css)

    body = "".join(_section(page, frag, i) for i, (page, frag) in enumerate(fragments))
    html_doc = (
        '<!DOCTYPE html><html lang="de"><head><meta charset="utf-8">'
        f"<style>{head}{''.join(css_blocks)}</style></head>"
        f"<body>{body}</body></html>"
    )

    # ---- WeasyPrint -> PDF ----
    pdf_path = output_dir / "report.pdf"
    weasyprint.HTML(string=html_doc, base_url=str(HERE)).write_pdf(str(pdf_path))

    # ---- rasterize PNGs (best-effort) ----
    png_paths: list[Path] = []
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(pdf_path)
        for i, pg in enumerate(doc):
            pix = pg.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
            png = output_dir / f"report-p{i + 1}.png"
            pix.save(str(png))
            png_paths.append(png)
        doc.close()
    except ImportError:
        warnings.append("PyMuPDF (fitz) unavailable; PNGs skipped")

    # ---- overflow validator (advisory, per page, standalone render) ----
    overflow: list[str] = []
    for i, (page, frag) in enumerate(fragments):
        one_doc = (
            "<!DOCTYPE html><html lang=\"de\"><head><meta charset=\"utf-8\">"
            f"<style>{head}{frag.css}</style></head>"
            f"<body>{_section(page, frag, i)}</body></html>"
        )
        try:
            if check_overflow(one_doc, base_url=str(HERE)):
                overflow.append(f"slot {page.get('slot')} ({page.get('st_type')}) overflow")
        except Exception as exc:  # noqa: BLE001 — advisory only
            warnings.append(f"overflow check failed for slot {page.get('slot')}: {exc!r}")

    # ---- accent-budget validator (stub today; seam is real) ----
    ab = AccentBudgetValidator(brand=pkg.brand).validate(
        rendered_html=html_doc, rendered_pdf_pages=[]
    )

    return RenderResult(
        pdf_path=pdf_path,
        png_paths=png_paths,
        page_count=len(fragments),
        overflow=overflow,
        accent_budget_passed=ab.passed,
        warnings=warnings,
    )
```

- [ ] **Step 4: Run it — expect PASS**

Run: `cd research/v7-renderer && .venv/bin/python -m pytest tests/test_render_r1.py -k "shared_head or render_package_apex" -q`
Expected: PASS. (Renders 20 pages — may take a few seconds.)

- [ ] **Step 5: Verification checkpoint**

Run: `cd research/v7-renderer && .venv/bin/python -m pytest tests/ -q`
Expected: all green — 11 baseline + all R1 tests, including `test_no_coral_in_chassis_logic`.

---

### Task 10: Rework `render.py` + full end-to-end verification

**Why:** Replace the single-page GEVA harness with the multi-page entrypoint, produce a real apex PDF on disk, and verify the whole system (both suites + guards + a live render).

**Venv:** renderer (+ a final pre-processor check). **Files:**
- Modify (rework): `research/v7-renderer/render.py`

- [ ] **Step 1: Rework `render.py`** — replace the whole file with:

```python
"""Renderer entrypoint — multi-page apex build through the chassis.

Reads the pre-processor's resolved_package.json (fixtures/apex/) and
emits a multi-page RGB PDF: case-study pages real (st_07a), every other
page a brand-styled _generic skeleton.

Hard constraints preserved from the prior frame:
  - INPUT-DRIVEN: all brand/content values come from the package; no
    client name or hex literal in logic.
  - NO SILENT FONT FALLBACK: _preflight_fonts() requires the 4 variable
    fonts on disk (Montserrat + Source Sans 3) before rendering.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from assembler import render_package  # noqa: E402

FONT_DIR = (HERE / "fonts").resolve()
FIXTURES_APEX_DIR = (HERE / "fixtures" / "apex").resolve()
OUTPUT_DIR = (HERE / "output").resolve()

_REQUIRED_FONTS = (
    "Montserrat[wght].ttf",
    "Montserrat-Italic[wght].ttf",
    "SourceSans3[wght].ttf",
    "SourceSans3-Italic[wght].ttf",
)


def _preflight_fonts() -> None:
    missing = [n for n in _REQUIRED_FONTS if not (FONT_DIR / n).exists()]
    if missing:
        raise FileNotFoundError(
            f"Required fonts missing from {FONT_DIR}: {missing}. The chassis "
            f"does NOT silently fall back to a system font. Fetch the "
            f"Montserrat + Source Sans 3 variable bundle from Google Fonts."
        )


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _preflight_fonts()

    result = render_package(FIXTURES_APEX_DIR, OUTPUT_DIR)

    print(f"[render] PDF: {result.pdf_path} "
          f"({result.pdf_path.stat().st_size:,} bytes)")
    print(f"[render] logical pages: {result.page_count}  "
          f"rasterized PNGs: {len(result.png_paths)}")
    print(f"[render] accent_budget_passed: {result.accent_budget_passed}")
    if result.overflow:
        print(f"[render] OVERFLOW (advisory): {result.overflow}")
    if result.warnings:
        print(f"[render] warnings: {result.warnings}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run the live render**

Run: `cd research/v7-renderer && .venv/bin/python render.py`
Expected: `[render] PDF: …/output/report.pdf (…)` with `logical pages: 20`, `rasterized PNGs: 20` (or more if any page overflows). Overflow/warnings printed are advisory — note them but they don't fail the build.

- [ ] **Step 3: Eyeball the output**

Run: `ls -la research/v7-renderer/output/ && open research/v7-renderer/output/report.pdf` (or view `report-p1.png … report-p20.png`).
Confirm visually: cover shows the hero image + headline; case-study pages (physical pages for slots 7/9/12/14/15) show the LRP layout with the FALLSTUDIE stamp, pullquote panel + QR, body sections, and the METRIKEN stat strip; folios appear bottom-left; the cyan brand palette is applied.

- [ ] **Step 4: Full renderer suite (with guards)**

Run: `cd research/v7-renderer && .venv/bin/python -m pytest tests/ -q`
Expected: all green — 11 contract tests + `test_no_coral_in_chassis_logic` + every R1 test from Tasks 2–9.

- [ ] **Step 5: Full pre-processor suite (with guard)**

Run: `cd research/preprocessor && .venv/bin/python -m pytest tests/ -q`
Expected: all green — 217 baseline + the `page_numbers` tests from Task 1 + `test_no_client_name_in_preprocessor_logic`.

- [ ] **Step 6: Confirm the success criteria**

Manually confirm against the spec's success definition:
- `render_package(fixtures/apex)` emits a multi-page RGB PDF (case studies real, others skeleton) with the correct page count (20) + folios. ✓ (Step 2/3)
- Renderer 11 contract tests + no-coral guard + new R1 tests green. ✓ (Step 4)
- Pre-processor 217 + page_numbers tests + guard green. ✓ (Step 5)
- Chassis stays brand-agnostic (no client name / hex in logic). ✓ (guards in Steps 4/5)

---

## Self-Review (planner checklist — completed)

**1. Spec coverage:** package_loader (Task 6 / spec §4) ✓; assembler + shared head (Task 9 / §3) ✓; pattern interface (Task 2 / §2) ✓; st_07a refactor (Task 4 / §5) ✓; _generic skeleton (Task 3 / §6) ✓; apex content fixture + slot plan + ST-07A data contract (Task 8 / §7) ✓; assets/components/report_assets (Tasks 3 + 8 / §8) ✓; real overflow validator (Task 7 / §9) ✓; upstream page_numbers (Task 1 / §10) ✓; error handling never-crash (Task 9 / §11) ✓; testing (every task / §12) ✓; reworked render.py (Task 10 / §13) ✓. The **3 corrections** are resolved: ST-07A data keys (Tasks 4 + 8), apex-fixture-is-sample → regenerated (Task 8), METRIKEN stat strip now renders (Task 4).

**2. Placeholder scan:** No "TBD/implement later". The one transcription instruction (Task 8 Step 3) references an authoritative in-repo source (`content for apex.md`) with an exact slot table + key mapping + 5 fully-worked page examples — data entry, not undefined logic. The `st_07a` metrics-`str` branch has an explicit correction note.

**3. Type consistency:** `PageFragment(html, css)` and `RenderContext(brand, grammar, package_dir)` are defined once (Task 2) and used identically in Tasks 3/4/5/9. `render(page, ctx) -> PageFragment` signature is uniform across st_07a + _generic + the registry's `Callable` type. `LoadedPackage` fields (Task 6) match the assembler's reads (Task 9). `RenderResult` fields (Task 9) match render.py's reads (Task 10). `PlannedPage.page_numbers` (Task 1) matches the manifest emit + the generator's data + the assembler's `_folio`. `AssetResult`/`AssetPlan` constructions (Task 8) match the dataclass fields read by `assemble_package`.

**4. R1 boundaries (documented, not gaps):** print bleed/CMYK → Layer 3; full-bleed cover background sizing + axis-driven report_asset backgrounds → R2 (axes are not on the 10-field BrandConfig); the 12 specific ST patterns → R2; facing-page spreads → R2; real accent_budget rasterization → stays stub.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-29-renderer-r1-foundation.md`. Execute task-by-task with **superpowers:subagent-driven-development** (fresh opus subagent per task, review between tasks) — the project convention. Each task is self-contained with complete code + a verification checkpoint (no git in this repo; tests are the gate).
