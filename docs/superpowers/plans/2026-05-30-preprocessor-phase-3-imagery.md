# Pre-Processor Phase 3 — Imagery — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Add the imagery substrate the richer PDF needs — a content-addressed **fal cache** (never re-pay for an identical generation), a per-report **generation budget guard**, an axis-driven **texture-template registry**, and (Unit 6) deterministic **device-mockup compositing** — all additive, golden frozen, both suites green. Unit 7 (Drive) is built against fakes (gated on user OAuth creds).

**Architecture:** Phase 3 of 4 implementing `docs/superpowers/specs/2026-05-30-preprocessor-PRD.md` (PRD Units 5+6+7). Built on Phases 1–2 (302 tests). Like prior phases, capabilities are added as **new modules + additive kwargs defaulted off**, NOT wired into `main.py`/the package — so the v1.0 golden stays frozen until Phase 4 wires everything at v2.0.

**Tech stack:** Python 3.11, httpx, Pillow (already present), stdlib `hashlib`/`shutil`. No new runtime deps in Units 5–6 (Unit 7 adds `google-api-python-client`/`google-auth` when creds arrive).

**Scope reconciliation (PRD Unit 5 — deliberate deviations, documented):**
- **The `stages/assets/` file-split is DEFERRED to Phase 4.** The PRD bundles a split with the cache, but `generate_assets.py` (822 lines, 23 tests) gets **reorganized again in Phase 4** (slot-resolver + Drive merge in). Splitting now → re-splitting later = wasted churn + regression risk for zero functional gain. Phase 3 adds the *functional* value additively; Phase 4 does the split once, when the module's final shape is known.
- **Output validation** (Pillow decodable + aspect-in-tolerance + bounded regen, PRD §9.3) is **deferred to Phase 4** wiring (it's a refinement on the live generate path; the cache/budget/texture are the core).
- Wiring the cache/budget/texture into `main.py`'s `generate_assets(...)` call → **Phase 4** (it changes the live path → done with the v2.0 golden re-baseline). Phase 3 ships them as off-by-default capabilities, tested directly.

---

## Conventions (same as Phases 1–2)

- **Working dir:** `/Users/utkarsh/Projects/richard/research/preprocessor/`; interpreter `.venv/bin/python`.
- **Full suite (net):** `.venv/bin/python -m pytest tests/ -q` — baseline entering Phase 3: **302 passed**.
- **Guard:** `tests/test_no_client_name_in_logic.py` (auto-covers new modules). **Golden:** `tests/test_resolved_package_contract.py` (must stay green ALL of Phase 3).
- **The 23-test `generate_assets` module is touched additively** — every new kwarg defaults to off, so the existing 23 tests (which never pass them) exercise today's exact behavior. The counting invariant `total_required == downloaded + generated + stubbed + client_upload_needed + failed` must hold — a cache hit counts as `generated`; an over-budget spec routes to the existing `stub_not_generated` bucket (NO new status — that would break test 7 + the contract).
- **NO GIT.** Per-task **Checkpoint** = new tests pass AND full suite green AND guard green AND golden green.
- **Async tests:** `@pytest.mark.anyio` + a local `anyio_backend` fixture returning `"asyncio"`.

---

## Unit 5 — fal cache + budget + texture templates (PRD Unit 5, §9)

### Task 5.1: Content-addressed cache module (`stages/assets_cache.py`)

A pure-ish cache: the key is `sha256(model + prompt + negative + aspect + resolution)` (the fal call has **no seed**, so these inputs fully determine the output). Standalone + safe (new module, nothing wired yet).

**Files:**
- Create: `stages/assets_cache.py`
- Create: `tests/test_assets_cache.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_assets_cache.py`:

```python
"""Tests for the content-addressed fal cache."""
from __future__ import annotations

from stages.assets_cache import cache_lookup, cache_store, fal_cache_key


def _k(**over) -> str:
    base = dict(model="m", prompt="p", negative_prompt="n", aspect="1:1", resolution="2K")
    base.update(over)
    return fal_cache_key(**base)


def test_key_is_deterministic_and_sha256() -> None:
    assert _k() == _k()
    assert len(_k()) == 64


def test_key_sensitive_to_every_input() -> None:
    base = _k()
    assert base != _k(model="m2")
    assert base != _k(prompt="p2")
    assert base != _k(negative_prompt="n2")
    assert base != _k(aspect="3:4")
    assert base != _k(resolution="4K")


def test_key_handles_none_negative() -> None:
    assert isinstance(fal_cache_key(model="m", prompt="p", negative_prompt=None,
                                    aspect="1:1", resolution="2K"), str)


def test_lookup_miss_then_store_then_hit(tmp_path) -> None:
    cache = tmp_path / "cache"
    src = tmp_path / "src.png"
    src.write_bytes(b"PNGDATA")
    key = "abc123"
    assert cache_lookup(cache, key) is None
    stored = cache_store(cache, key, src)
    assert stored is not None and stored.exists()
    hit = cache_lookup(cache, key)
    assert hit is not None and hit.read_bytes() == b"PNGDATA"


def test_cache_dir_none_is_off(tmp_path) -> None:
    src = tmp_path / "s.png"
    src.write_bytes(b"x")
    assert cache_lookup(None, "k") is None
    assert cache_store(None, "k", src) is None
```

- [ ] **Step 2: Run it — expect failure**

Run: `.venv/bin/python -m pytest tests/test_assets_cache.py -q` → FAIL (`No module named 'stages.assets_cache'`).

- [ ] **Step 3: Implement `stages/assets_cache.py`**

```python
"""Content-addressed cache for fal image generation.

The key is sha256 over the EXACT generation inputs (model + prompt +
negative + aspect + resolution). The fal call carries no seed, so these
inputs fully determine the output → an identical request reuses the stored
PNG ($0, deterministic; temp=0 prompts are stable → stable key). cache_dir
None disables caching (the default everywhere until Phase 4 wires it).
Brand-agnostic.
"""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Optional


def fal_cache_key(
    *, model: str, prompt: str, negative_prompt: Optional[str], aspect: str, resolution: str
) -> str:
    parts = [model or "", prompt or "", negative_prompt or "", aspect or "", resolution or ""]
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
```

- [ ] **Step 4: Run — expect pass**

Run: `.venv/bin/python -m pytest tests/test_assets_cache.py -q` → 5 passed.

- [ ] **Step 5: Checkpoint**

Full suite → expect **307 passed** (302 + 5). Guard + golden green.

### Task 5.2: Wire the cache into `fal_generate_image` (+ forward from `generate_assets`)

Add a `cache_dir` kwarg (default `None` = off) to `fal_generate_image`: on a cache **hit**, copy the stored PNG to the target path and return `generated` (no POST); on a **miss**, generate as today, then store the result. Forward `cache_dir` from `generate_assets`. All additive — the 23 existing tests (no `cache_dir`) are unchanged.

**Files:**
- Modify: `stages/generate_assets.py` (`fal_generate_image` + `generate_assets`)
- Create: `tests/test_fal_cache_wiring.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_fal_cache_wiring.py`:

```python
"""Tests: the fal cache makes an identical second generation free."""
from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from stages.generate_assets import fal_generate_image

_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _transport(counter: dict) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "fal.run" in url:
            counter["posts"] += 1
            return httpx.Response(200, json={"images": [{"url": "https://cdn.test/img.png"}]})
        if "cdn.test" in url:
            return httpx.Response(200, content=_PNG)
        return httpx.Response(404)
    return httpx.MockTransport(handler)


async def _gen(client, out_dir, cache_dir):
    return await fal_generate_image(
        prompt="p", negative_prompt="n", aspect_ratio="1:1", api_key="K", model="m",
        resolution="2K", output_dir=out_dir, slot_id="s", page_slot=1,
        http_client=client, cache_dir=cache_dir,
    )


@pytest.mark.anyio
async def test_second_identical_generation_hits_cache(tmp_path) -> None:
    counter = {"posts": 0}
    client = httpx.AsyncClient(transport=_transport(counter), follow_redirects=True)
    cache = tmp_path / "cache"
    r1 = await _gen(client, tmp_path / "o1", cache)
    r2 = await _gen(client, tmp_path / "o2", cache)
    await client.aclose()
    assert r1.status == "generated" and r2.status == "generated"
    assert counter["posts"] == 1                      # second served from cache
    assert Path(r2.path).exists()


@pytest.mark.anyio
async def test_no_cache_dir_always_posts(tmp_path) -> None:
    counter = {"posts": 0}
    client = httpx.AsyncClient(transport=_transport(counter), follow_redirects=True)
    await _gen(client, tmp_path / "o1", None)
    await _gen(client, tmp_path / "o2", None)
    await client.aclose()
    assert counter["posts"] == 2                       # caching off → both POST
```

- [ ] **Step 2: Run it — expect failure**

Run: `.venv/bin/python -m pytest tests/test_fal_cache_wiring.py -q` → FAIL (`fal_generate_image() got an unexpected keyword argument 'cache_dir'`).

- [ ] **Step 3: Edit `stages/generate_assets.py`**

(a) Add imports near the top (with the other stdlib/stage imports):

```python
import shutil
from stages.assets_cache import cache_lookup, cache_store, fal_cache_key
```

(b) Add `cache_dir` to the `fal_generate_image` signature (keyword-only block, after `timeout`):

```python
    timeout: float = FAL_GENERATE_TIMEOUT_S,
    cache_dir: Optional[Path] = None,
) -> AssetResult:
```

(c) Immediately AFTER the `target_path = ...` line (currently L302) and BEFORE `request_body = {`, insert the cache-hit short-circuit:

```python
    cache_key = fal_cache_key(
        model=model, prompt=prompt, negative_prompt=negative_prompt,
        aspect=aspect, resolution=resolution,
    )
    cached = cache_lookup(cache_dir, cache_key)
    if cached is not None:
        try:
            shutil.copyfile(cached, target_path)
        except OSError:
            cached = None  # cache unreadable → fall through to a real generation
        else:
            return AssetResult(
                slot_id=slot_id, status="generated", path=target_path,
                message=f"fal cache hit ({cache_key[:12]})",
                page_slot=page_slot, image_type=image_type,
                prompt=prompt, negative_prompt=negative_prompt,
            )
```

(d) In the success branch, immediately BEFORE the `return AssetResult(... status="generated" ...)` (currently L354), insert the store:

```python
        cache_store(cache_dir, cache_key, target_path)
```

(e) In `generate_assets`, add `cache_dir: Optional[Path] = None` to its signature (after `fal_resolution`), and pass it into the `fal_generate_image(...)` call (add `cache_dir=cache_dir,` to that call's kwargs).

- [ ] **Step 4: Run the cache-wiring test — expect pass**

Run: `.venv/bin/python -m pytest tests/test_fal_cache_wiring.py -q` → 2 passed.

- [ ] **Step 5: Checkpoint (the 23-test module must be intact)**

Run: `.venv/bin/python -m pytest tests/test_generate_assets.py -q` → expect **23 passed** (unchanged — they pass no `cache_dir`).
Run: `.venv/bin/python -m pytest tests/ -q` → expect **309 passed** (307 + 2).
Guard + golden green.

### Task 5.3: Per-report generation budget guard

Add `max_generations_per_report` (default `None` = unlimited) to `generate_assets`. When the budget is reached, route the remaining generate-specs to the **existing `stub_not_generated` bucket** (NOT a new status), so the counting invariant holds and the 23 tests (which pass no budget) are unchanged. *(Phase-4 refinement, noted: once cache + budget are both wired live, only real POSTs should consume budget; a cache hit shouldn't. In Phase 3 they're tested orthogonally.)*

**Files:**
- Modify: `stages/generate_assets.py` (`generate_assets` Pass-2 loop, ~L758–832)
- Create: `tests/test_generation_budget.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_generation_budget.py`:

```python
"""Tests: the per-report generation budget caps real fal POSTs (over-budget
specs degrade to stub_not_generated, preserving the counting invariant)."""
from __future__ import annotations

import httpx
import pytest

from stages.generate_assets import generate_assets

_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _transport(counter: dict) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "fal.run" in url:
            counter["fal"] += 1
            return httpx.Response(200, json={"images": [{"url": "https://cdn.test/i.png"}]})
        if "cdn.test" in url:
            return httpx.Response(200, content=_PNG)
        return httpx.Response(404)
    return httpx.MockTransport(handler)


# 3 page-level generate-specs (cover_hero, status_quo_scene, fazit_background)
# + 2 report-level (background_texture, atmospheric_gradient) = 5 generate-specs;
# ST-01 also has cover_author (client) → client_upload_needed.
_PAGES = [
    {"slot": 1, "type": "ST-01", "data": {"title": "t"}},
    {"slot": 9, "type": "ST-09", "data": {"title": "t"}},
    {"slot": 20, "type": "ST-FAZIT", "data": {"title": "t"}},
]


def _invariant(plan) -> bool:
    return plan.total_required == (
        plan.total_downloaded + plan.total_generated + plan.total_stubbed
        + plan.total_client_upload_needed + plan.total_failed
    )


@pytest.mark.anyio
async def test_budget_caps_real_generations(tmp_path) -> None:
    counter = {"fal": 0}
    client = httpx.AsyncClient(transport=_transport(counter), follow_redirects=True)
    plan = await generate_assets(
        pages=_PAGES, image_manifest={"images": []},
        brand_primary="#111111", brand_accent="#00aaff",
        output_dir=tmp_path, http_client=client,
        fal_key="FALKEY", max_generations_per_report=2,
    )
    await client.aclose()
    assert counter["fal"] == 2            # only 2 real POSTs made
    assert plan.total_generated == 2
    assert plan.total_stubbed >= 3        # the other 3 generate-specs stubbed
    assert _invariant(plan)


@pytest.mark.anyio
async def test_no_budget_generates_all(tmp_path) -> None:
    counter = {"fal": 0}
    client = httpx.AsyncClient(transport=_transport(counter), follow_redirects=True)
    plan = await generate_assets(
        pages=_PAGES, image_manifest={"images": []},
        brand_primary="#111111", brand_accent="#00aaff",
        output_dir=tmp_path, http_client=client, fal_key="FALKEY",
    )
    await client.aclose()
    assert counter["fal"] == 5            # all 5 generate-specs POST (budget None)
    assert plan.total_generated == 5
    assert _invariant(plan)
```

- [ ] **Step 2: Run it — expect failure**

Run: `.venv/bin/python -m pytest tests/test_generation_budget.py -q` → FAIL (`unexpected keyword argument 'max_generations_per_report'`).

- [ ] **Step 3: Edit `stages/generate_assets.py`**

(a) Add to the `generate_assets` keyword-only signature, after `cache_dir: Optional[Path] = None,`:

```python
    max_generations_per_report: Optional[int] = None,
```

(b) Immediately BEFORE the `for spec in generate_specs:` loop, add a counter:

```python
    generated_count = 0
```

(c) Replace the `if fal_key:` … `else:` block (the whole generate/stub decision, currently ~L782–832) with this budget-aware version (preserving the existing fal-call kwargs and the existing no-key stub message verbatim):

```python
        over_budget = (
            max_generations_per_report is not None
            and generated_count >= max_generations_per_report
        )
        if fal_key and not over_budget:
            try:
                result = await fal_generate_image(
                    prompt=prompt,
                    negative_prompt=negative,
                    aspect_ratio=aspect,
                    api_key=fal_key,
                    model=fal_model,
                    resolution=fal_resolution,
                    output_dir=output_dir,
                    slot_id=slot_id,
                    page_slot=page_slot,
                    image_type=image_type,
                    http_client=http_client,
                    cache_dir=cache_dir,
                )
            except Exception as exc:  # noqa: BLE001 — never abort the others
                result = AssetResult(
                    slot_id=slot_id,
                    status="failed",
                    path=None,
                    message=f"fal generation error for {slot_id}: {exc!r}",
                    page_slot=page_slot,
                    image_type=image_type,
                    prompt=prompt,
                    negative_prompt=negative,
                )
            plan.assets.append(result)
            if result.status == "generated":
                plan.total_generated += 1
                generated_count += 1
            else:
                plan.total_failed += 1
                plan.warnings.append(
                    f"slot {page_slot if page_slot is not None else 'report'}: "
                    f"fal generation failed for {slot_id}"
                )
        else:
            if over_budget:
                message = (
                    f"Generation skipped (budget {max_generations_per_report} "
                    f"reached). Slot={slot_id}, aspect={aspect}. Prompt recorded."
                )
            else:
                message = (
                    f"Generation stubbed (no fal key). Slot={slot_id}, "
                    f"aspect={aspect}. Prompt recorded for QA/replay."
                )
            plan.assets.append(AssetResult(
                slot_id=slot_id,
                status="stub_not_generated",
                path=None,
                message=message,
                page_slot=page_slot,
                image_type=image_type,
                prompt=prompt,
                negative_prompt=negative,
            ))
            plan.total_stubbed += 1
            if over_budget:
                plan.warnings.append(
                    f"slot {page_slot if page_slot is not None else 'report'}: "
                    f"generation budget ({max_generations_per_report}) reached for "
                    f"{slot_id}; stubbed"
                )
```

- [ ] **Step 4: Run the budget test — expect pass**

Run: `.venv/bin/python -m pytest tests/test_generation_budget.py -q` → 2 passed.

- [ ] **Step 5: Checkpoint**

Run: `.venv/bin/python -m pytest tests/test_generate_assets.py -q` → **23 passed** (no budget passed → over_budget always False → identical path).
Run: `.venv/bin/python -m pytest tests/ -q` → expect **311 passed** (309 + 2). Guard + golden green.

### Task 5.4: Axis-driven texture-template registry (`stages/texture_templates.py`)

A standalone registry of texture/atmosphere prompt fragments keyed by `(role, texture_axis)`, tinted by `ground_mode`, filled from the brand brief (style/material/negative). NO client literal — only material/atmosphere vocabulary. **Unwired** (Phase 4 feeds it into the generate path; wiring it now would change the recorded prompts → break the golden).

**Files:**
- Create: `stages/texture_templates.py`
- Create: `tests/test_texture_templates.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_texture_templates.py`:

```python
"""Tests for the axis-driven texture-template registry."""
from __future__ import annotations

from stages.texture_templates import texture_prompt


def test_known_combo_uses_material_vocabulary() -> None:
    prompt, neg = texture_prompt(role="texture", texture_axis="marble_paper", ground_mode="light")
    assert "marbled" in prompt.lower()
    assert "light" in prompt.lower()
    assert "logo" in neg.lower()        # default negative bars logos/text/faces


def test_ground_mode_dark_tints_prompt() -> None:
    prompt, _ = texture_prompt(role="texture", texture_axis="photo", ground_mode="dark")
    assert "dark" in prompt.lower()


def test_brief_fields_incorporated() -> None:
    prompt, neg = texture_prompt(
        role="gradient", texture_axis="smooth", ground_mode="mixed",
        style_prompt="STYLE-DNA-XYZ", material="brushed parchment",
        negative_prompt="warm tones, grunge",
    )
    assert "STYLE-DNA-XYZ" in prompt
    assert "brushed parchment" in prompt
    assert neg == "warm tones, grunge"


def test_unknown_axis_falls_back() -> None:
    prompt, _ = texture_prompt(role="texture", texture_axis="nonexistent")
    assert isinstance(prompt, str) and prompt           # non-empty default


def test_deterministic() -> None:
    a = texture_prompt(role="scene", texture_axis="photo", ground_mode="dark")
    b = texture_prompt(role="scene", texture_axis="photo", ground_mode="dark")
    assert a == b
```

- [ ] **Step 2: Run it — expect failure**

Run: `.venv/bin/python -m pytest tests/test_texture_templates.py -q` → FAIL (`No module named 'stages.texture_templates'`).

- [ ] **Step 3: Implement `stages/texture_templates.py`**

```python
"""Axis-driven texture/atmosphere prompt fragments (DNA §C6 / PRD §9.2).

A registry keyed by (role, texture_axis) → a base atmosphere fragment;
ground_mode tints it; the brand brief's style/material/negative fill it.
NO client literal — only material/atmosphere vocabulary. Standalone; wired
into the generate path in Phase 4. Deterministic + brand-agnostic.
"""
from __future__ import annotations

from typing import Optional

# (role, texture_axis) → atmosphere fragment. role ∈ {texture, gradient, scene}.
_FRAGMENTS: dict[tuple[str, str], str] = {
    ("texture", "smooth"): "a smooth, clean abstract background surface",
    ("texture", "marble_paper"): "an elegant marbled-paper surface with subtle veining",
    ("texture", "crumpled_paper"): "a softly crumpled paper texture with gentle shadows",
    ("texture", "paper_grain"): "a fine paper-grain texture, editorial and tactile",
    ("texture", "photo"): "a darkened cinematic photographic backdrop, softly out of focus",
    ("gradient", "smooth"): "a smooth tonal gradient wash",
    ("gradient", "marble_paper"): "a marbled tonal gradient with faint veining",
    ("gradient", "crumpled_paper"): "a paper-textured tonal gradient",
    ("gradient", "paper_grain"): "a grainy tonal gradient",
    ("gradient", "photo"): "a cinematic vignette gradient over a darkened photo",
    ("scene", "smooth"): "a clean, minimal on-brand scene backdrop",
    ("scene", "photo"): "a darkened, scrimmed photographic scene so text stays legible",
}
_DEFAULT_FRAGMENT = "an abstract, on-brand background surface"

_GROUND_TINT = {
    "light": "on a light, airy ground",
    "dark": "on a deep, dark ground",
    "mixed": "with balanced light-and-dark contrast",
}

_DEFAULT_NEGATIVE = "text, words, letters, logos, watermark, people, faces"


def texture_prompt(
    *,
    role: str,
    texture_axis: str,
    ground_mode: str = "mixed",
    style_prompt: Optional[str] = None,
    material: Optional[str] = None,
    negative_prompt: Optional[str] = None,
) -> tuple[str, str]:
    """Compose a (prompt, negative_prompt) for a texture/atmosphere asset.
    Deterministic; brand values arrive via style_prompt/material/negative."""
    base = (
        _FRAGMENTS.get((role, texture_axis))
        or _FRAGMENTS.get(("texture", texture_axis))
        or _DEFAULT_FRAGMENT
    )
    tint = _GROUND_TINT.get(ground_mode, _GROUND_TINT["mixed"])
    parts = [base, tint]
    if material:
        parts.append(f"material: {material}")
    if style_prompt:
        parts.append(style_prompt)
    prompt = ", ".join(p for p in parts if p)
    negative = negative_prompt or _DEFAULT_NEGATIVE
    return prompt, negative
```

- [ ] **Step 4: Run — expect pass**

Run: `.venv/bin/python -m pytest tests/test_texture_templates.py -q` → 5 passed.

- [ ] **Step 5: Checkpoint (Unit 5 complete)**

Run: `.venv/bin/python -m pytest tests/ -q` → expect **316 passed** (311 + 5). Guard + golden green.

### Unit 5 self-review
- **Coverage (PRD §9):** content-addressed sha256 cache ($0 on identical regen) ✓; per-report budget guard (caps real POSTs; over-budget → existing stub bucket, invariant intact) ✓; axis-driven texture-template registry ✓. **Deferred (stated):** `stages/assets/` file-split + output-validation + wiring cache/budget/texture into `main.py` → Phase 4; cache-vs-budget "real POSTs only" refinement → Phase 4.
- **No regression:** every change additive + off-by-default; the 23 `generate_assets` tests + the golden stay green; new modules brand-agnostic (guard auto-covers).

---

## Unit 6 — Device-mockup compositing (PRD Unit 6, §9.1)

Composite a client's real creative (ad / dashboard / book cover, sourced from Drive) INTO a transparent device-frame PNG's screen hole, so it reads as "displayed on the device." Pure Pillow, deterministic, offline. **Standalone + unwired** (Phase 4 calls it on the case-study `device_mockup` slot). The device-frame PNG asset library is authored separately (reusable, brand-agnostic, one-time); the tests synthesize a placeholder frame so the logic is fully covered now.

**Scope (deliberate, documented):** Phase 3 ships **axis-aligned rectangular screen placement** (resize creative → paste into the screen box → layer the frame on top). The **perspective/QUAD warp** (for angled frames) and the **GaussianBlur drop shadow** (PRD §9.1) are deferred refinements — they need real angled frame assets to be meaningful, and a pure-Python perspective solve adds complexity (numpy isn't a dep). Axis-aligned covers straight-on phone/laptop/book frames, which is the common case.

### Task 6.1: `stages/device_mockup.py` — Pillow compositing

**Files:**
- Create: `stages/device_mockup.py`
- Create: `tests/test_device_mockup.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_device_mockup.py`:

```python
"""Tests for device-mockup compositing (synthetic placeholder frame)."""
from __future__ import annotations

import pytest
from PIL import Image

from stages.device_mockup import composite_device_mockup


def _make_frame(path) -> None:
    # 100x200 opaque-blue device body with a transparent screen hole.
    frame = Image.new("RGBA", (100, 200), (0, 0, 255, 255))
    frame.paste((0, 0, 0, 0), (20, 20, 80, 180))  # screen hole = transparent
    frame.save(path)


def test_creative_shows_through_screen(tmp_path) -> None:
    fp = tmp_path / "frame.png"
    _make_frame(fp)
    cp = tmp_path / "creative.png"
    Image.new("RGB", (10, 10), (255, 0, 0)).save(cp)   # solid red creative
    out = tmp_path / "out.png"
    result = composite_device_mockup(
        creative_path=cp, frame_path=fp, screen_box=(20, 20, 80, 180), output_path=out,
    )
    assert result.size == (100, 200)
    r, g, b, _ = result.getpixel((50, 100))            # screen centre → creative red
    assert r > 200 and g < 60 and b < 60
    r2, g2, b2, _ = result.getpixel((5, 5))            # body corner → frame blue
    assert b2 > 200 and r2 < 60
    assert out.exists()


def test_invalid_screen_box_raises(tmp_path) -> None:
    fp = tmp_path / "f.png"
    _make_frame(fp)
    cp = tmp_path / "c.png"
    Image.new("RGB", (4, 4), (0, 255, 0)).save(cp)
    with pytest.raises(ValueError):
        composite_device_mockup(creative_path=cp, frame_path=fp, screen_box=(50, 50, 50, 50))


def test_missing_creative_raises(tmp_path) -> None:
    fp = tmp_path / "f.png"
    _make_frame(fp)
    with pytest.raises(FileNotFoundError):
        composite_device_mockup(
            creative_path=tmp_path / "nope.png", frame_path=fp, screen_box=(20, 20, 80, 180),
        )


def test_returns_rgba(tmp_path) -> None:
    fp = tmp_path / "f.png"
    _make_frame(fp)
    cp = tmp_path / "c.png"
    Image.new("RGB", (8, 8), (0, 255, 0)).save(cp)
    result = composite_device_mockup(creative_path=cp, frame_path=fp, screen_box=(20, 20, 80, 180))
    assert result.mode == "RGBA"
```

- [ ] **Step 2: Run it — expect failure**

Run: `.venv/bin/python -m pytest tests/test_device_mockup.py -q` → FAIL (`No module named 'stages.device_mockup'`).

- [ ] **Step 3: Implement `stages/device_mockup.py`**

```python
"""Device-mockup compositing (DNA §C2 / PRD §9.1).

Paste a client's real creative (ad / dashboard / book cover, sourced from
Drive) INTO a transparent device-frame PNG's screen hole, so it reads as
"displayed on the device". Pure Pillow, deterministic, offline. The frame
PNGs are a small reusable, brand-agnostic asset library (authored
separately). Axis-aligned screen placement; perspective warp + drop shadow
are deferred refinements. Standalone — wired onto the case-study slot in a
later phase. Brand-agnostic.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

from PIL import Image

_PathLike = Union[str, Path]


def composite_device_mockup(
    *,
    creative_path: _PathLike,
    frame_path: _PathLike,
    screen_box: tuple[int, int, int, int],
    output_path: Optional[_PathLike] = None,
) -> Image.Image:
    """Resize the creative to `screen_box` and place it behind the frame's
    transparent screen hole; layer the frame on top. `screen_box` is
    (left, top, right, bottom) in frame pixel coordinates.

    Returns the composited RGBA image (saved to output_path if given).
    Raises FileNotFoundError if an input is missing, ValueError on a
    degenerate box — the caller decides how to degrade.
    """
    frame = Image.open(frame_path).convert("RGBA")
    creative = Image.open(creative_path).convert("RGBA")

    left, top, right, bottom = screen_box
    width, height = right - left, bottom - top
    if width <= 0 or height <= 0:
        raise ValueError(f"invalid screen_box {screen_box}: non-positive area")

    creative_resized = creative.resize((width, height))
    canvas = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    canvas.paste(creative_resized, (left, top))
    result = Image.alpha_composite(canvas, frame)

    if output_path is not None:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        result.save(out)
    return result
```

- [ ] **Step 4: Run — expect pass**

Run: `.venv/bin/python -m pytest tests/test_device_mockup.py -q` → 4 passed.

- [ ] **Step 5: Checkpoint (Unit 6 complete)**

Run: `.venv/bin/python -m pytest tests/ -q` → expect **320 passed** (316 + 4). Guard + golden green.

### Unit 6 self-review
- **Coverage (PRD §9.1):** deterministic Pillow compositing of a real creative into a device frame ✓ (the core "real product" credibility device). **Deferred (stated):** perspective/QUAD warp + GaussianBlur shadow (need real angled frames; numpy-free perspective is complex) → later; the device-frame PNG asset library → authored input; wiring onto the case-study `device_mockup` slot → Phase 4.
- **Brand-agnostic / deterministic:** the frame is data; the function names no client; pure Pillow, no clock/network; guard auto-covers.

---

## Unit 7 — Drive client (PRD Unit 7, §7.4) — testable core, live adapter gated on creds

The PRD says: *designed now, the live google-api adapter built when the user provides OAuth creds; for local testing a provided file list substitutes for Drive via the same resolver.* So Phase 3 ships the **pure, testable pieces** — parsing a `files.list` response into `DriveFile[]`, feeding the filenames to `resolve_slots` (Unit 4), and the **md5 cache** (skip re-download when the Drive `md5Checksum` matches a local copy) — all tested with fixtures/fakes. The thin `GoogleDriveLister` adapter (`google-api-python-client` + `google-auth`, ~20 lines) + its deps are **deferred to when creds arrive** (can't be exercised without them; YAGNI on the deps until then).

### Task 7.1: `stages/drive_client.py` — listing parse + md5 cache + resolver integration

**Files:**
- Create: `stages/drive_client.py`
- Create: `tests/test_drive_client.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_drive_client.py`:

```python
"""Tests for the Drive client's pure pieces (live google adapter is gated
on OAuth creds and added later). Uses a faked files.list response."""
from __future__ import annotations

from stages.drive_client import (
    DriveFile,
    drive_filenames,
    md5_cache_dest,
    md5_cached_path,
    parse_drive_listing,
)
from stages.resolve_slots import resolve_slots


def test_parse_listing_sorted_and_skips_invalid() -> None:
    resp = {"files": [
        {"id": "b", "name": "team.jpg", "md5Checksum": "m2"},
        {"id": "a", "name": "case-study-1.jpg", "md5Checksum": "m1"},
        {"id": "x"},                      # no name → skipped
        {"name": "y.png"},                # no id → skipped
    ]}
    files = parse_drive_listing(resp)
    assert [f.name for f in files] == ["case-study-1.jpg", "team.jpg"]   # sorted by name
    assert files[0].id == "a" and files[0].md5 == "m1"


def test_parse_empty_response() -> None:
    assert parse_drive_listing({}) == []
    assert parse_drive_listing({"files": []}) == []


def test_filenames_feed_the_slot_resolver() -> None:
    resp = {"files": [{"id": "a", "name": "case-study-1.jpg", "md5Checksum": "m"}]}
    names = drive_filenames(parse_drive_listing(resp))
    slots = resolve_slots("ST-07A", names, case_index=1)
    cp = [s for s in slots if s.slot_kind == "client_portrait"][0]
    assert cp.status == "resolved"
    assert cp.path == "case-study-1.jpg"


def test_md5_cache_hit_and_miss(tmp_path) -> None:
    f = DriveFile(id="a", name="x.png", md5="abc")
    cache = tmp_path / "drive_cache"
    assert md5_cached_path(cache, f) is None              # nothing cached yet
    dest = md5_cache_dest(cache, f)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(b"img")
    hit = md5_cached_path(cache, f)
    assert hit is not None and hit.read_bytes() == b"img"
    assert hit == dest                                    # keyed by id + md5 + ext


def test_md5_cache_off_without_md5_or_dir(tmp_path) -> None:
    assert md5_cached_path(None, DriveFile(id="a", name="x.png", md5="abc")) is None
    assert md5_cached_path(tmp_path, DriveFile(id="a", name="x.png", md5=None)) is None
```

- [ ] **Step 2: Run it — expect failure**

Run: `.venv/bin/python -m pytest tests/test_drive_client.py -q` → FAIL (`No module named 'stages.drive_client'`).

- [ ] **Step 3: Implement `stages/drive_client.py`**

```python
"""Google Drive asset listing + md5-cached download (PRD §7.4).

DESIGNED here; the live google-api-python-client adapter (GoogleDriveLister)
is added when the user provides OAuth creds — it's a thin call to
files().list()/files().get_media(). The pure pieces below — parsing a
files.list response, feeding the slot resolver, and the md5 cache — are
testable now with fakes, and a provided local file list substitutes for
Drive via the same resolver. Brand-agnostic; no client literal.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Protocol


@dataclass(frozen=True)
class DriveFile:
    id: str
    name: str
    md5: Optional[str] = None


def parse_drive_listing(files_list_response: dict) -> list[DriveFile]:
    """Parse a Drive files.list() response → DriveFile[], sorted by name
    (deterministic). Entries missing id or name are skipped defensively."""
    out: list[DriveFile] = []
    for f in (files_list_response or {}).get("files", []):
        fid, name = f.get("id"), f.get("name")
        if not fid or not name:
            continue
        out.append(DriveFile(id=fid, name=name, md5=f.get("md5Checksum")))
    return sorted(out, key=lambda d: d.name)


def drive_filenames(listing: list[DriveFile]) -> list[str]:
    """The filenames to hand to resolve_slots()."""
    return [f.name for f in listing]


def _ext(name: str) -> str:
    i = name.rfind(".")
    return name[i:] if i != -1 else ""


def md5_cache_dest(cache_dir: Path, file: DriveFile) -> Path:
    """The cache path a file is stored at, keyed by id + md5 + extension."""
    return Path(cache_dir) / f"{file.id}_{file.md5}{_ext(file.name)}"


def md5_cached_path(cache_dir: Optional[Path], file: DriveFile) -> Optional[Path]:
    """Return a cached copy's path when (id, md5) already exists → skip the
    re-download. None when caching is off or the file carries no md5."""
    if cache_dir is None or not file.md5:
        return None
    p = md5_cache_dest(cache_dir, file)
    return p if p.exists() else None


class DriveLister(Protocol):
    """Interface the pipeline depends on. The live GoogleDriveLister
    implementation (OAuth2 + files().list) is added when creds arrive; tests
    use a fake. Keeps the pipeline decoupled from the google SDK."""

    def list_files(self, folder_id: str) -> list[DriveFile]: ...
```

- [ ] **Step 4: Run — expect pass**

Run: `.venv/bin/python -m pytest tests/test_drive_client.py -q` → 5 passed.

- [ ] **Step 5: Checkpoint (Unit 7 core + Phase 3 buildable scope complete)**

Run: `.venv/bin/python -m pytest tests/ -q` → expect **325 passed** (320 + 5). Guard + golden green.

### Unit 7 self-review
- **Coverage (PRD §7.4):** `files.list` parse → `DriveFile[]` ✓; filenames feed the Unit-4 resolver ✓; md5 cache (skip re-download on checksum match) ✓; a `DriveLister` Protocol decoupling the pipeline from the SDK ✓. **Deferred (stated, gated on creds):** the live `GoogleDriveLister` adapter + `google-api-python-client`/`google-auth` deps + `files.get_media` streaming download (reuses `download_image`). Built the moment creds are provided.
- **Brand-agnostic / deterministic:** parse sorts by name; names/keys only; no client literal; guard auto-covers.

---

## Phase 3 — overall self-review (buildable scope)
- **Units 5 + 6 + 7 (core) complete:** fal cache + budget + texture templates (Unit 5); device-mockup compositing (Unit 6); Drive listing-parse + md5-cache + resolver integration (Unit 7 core). 302 → **325** (+23); golden frozen; guard green throughout; the 23-test `generate_assets` module intact across two additive touches.
- **Gated/deferred to inputs or Phase 4 (explicit):** live `GoogleDriveLister` adapter + google deps (creds); real device-frame PNG assets + perspective/shadow; `stages/assets/` file-split + output-validation; wiring cache/budget/texture/compositing/Drive into `main.py`/the package → **Phase 4 (v2.0, cross-layer with the renderer)**.