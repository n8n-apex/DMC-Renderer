# Autonomy Spine, Phase 1: Cache Hardening, Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every generation cache content-addressed on ALL inputs that change its output (model, prompt text, brand, client, design brief, copy budget), so decayed/stale data can never silently reach the rendered report, and lock it with a guard test.

**Architecture:** Three independent caches each get their key widened: the fal image cache (`assets_cache.py`), the restructure LLM-copy cache (`restructure_page.py`), and the vision-score cache (`vis_client.py`). The pattern is identical everywhere: the key must hash every input that can change the output, including the code/prompt that produces it. A new guard test asserts each key is sensitive to those inputs, so this class of decay cannot return silently. This is spine part 7 (regression hardening), sequenced first because it is independent, low-risk, and every later phase is verified through the grader and the rendered output, which are only trustworthy once stale data cannot leak.

**Tech Stack:** Python 3.11, pytest, hashlib (stdlib). Two virtualenvs: the preprocessor venv at `research/preprocessor/.venv` (tests import `from stages...`), and the quality_loop tooling (tests import `from vis_client import ...`). No network in any test. Brand-agnostic: no client name, hex, or font literal in logic. No em dashes in any authored text.

**Source spec:** `docs/superpowers/specs/2026-06-20-autonomy-spine-design.md` section 6 (cache mandate) + infection rows #4, #5, #6.

---

## File structure

| File | Responsibility | Change |
|---|---|---|
| `research/preprocessor/stages/assets_cache.py` | fal image cache key + lookup/store | add `cache_salt()` helper + `salt` param to `fal_cache_key` |
| `research/preprocessor/stages/generate_assets.py` | calls `fal_cache_key` at line 305 | compute the salt once, thread it into the call |
| `research/preprocessor/stages/restructure_page.py` | restructure cache key (line 389) | derive a prompt signature from `_SYSTEM_PROMPT`; add `copy_budget` to the key |
| `research/preprocessor/stages/restructure_page.py` | `restructure_page()` caller (line 423) | pass `copy_budget` into `restructure_cache_key` |
| `research/quality_loop/vis_client.py` | vis-score cache key (line 131) + `score_page` (line 286) | add `model` + `prompt_sig` to the key; thread them from `score_page` |
| `research/preprocessor/tests/test_assets_cache.py` | fal cache tests | add salt-sensitivity assertions |
| `research/preprocessor/tests/test_restructure_page.py` | restructure tests | add prompt-sig + copy_budget sensitivity test |
| `research/quality_loop/tests/test_vis_client.py` | vis cache tests | add model + prompt_sig sensitivity test |

Run commands (use the local venv):
- Preprocessor: `cd /Users/utkarsh/Projects/richard/research/preprocessor && .venv/bin/python -m pytest <test> -v`
- Quality loop: `cd /Users/utkarsh/Projects/richard/research/quality_loop && python -m pytest <test> -v` (use the same venv if quality_loop has none of its own; it imports top-level modules so run from that dir).

**Before editing any file, back it up first** (project guardrail: `cp <file> /tmp/p1_backup/<file>.orig`). NOT a git tree per project convention, so the backup is the rollback.

---

## Task 1: fal image cache key includes brand, client, and design-brief salt

**Files:**
- Modify: `research/preprocessor/stages/assets_cache.py:18-22`
- Test: `research/preprocessor/tests/test_assets_cache.py`

- [ ] **Step 1: Write the failing test** (append to `test_assets_cache.py`)

```python
from stages.assets_cache import cache_salt  # add to the existing import line


def test_cache_salt_is_deterministic_and_sensitive() -> None:
    base = dict(client_slug="acme", brand_primary="#111111",
                brand_accent="#222222", design_brief={"mood": "calm"},
                builder_version="v1")
    s = cache_salt(**base)
    assert s == cache_salt(**base)              # deterministic
    assert len(s) == 64                         # sha256 hex
    assert s != cache_salt(**{**base, "client_slug": "other"})
    assert s != cache_salt(**{**base, "brand_primary": "#999999"})
    assert s != cache_salt(**{**base, "brand_accent": "#999999"})
    assert s != cache_salt(**{**base, "design_brief": {"mood": "bold"}})
    assert s != cache_salt(**{**base, "builder_version": "v2"})


def test_fal_key_sensitive_to_salt() -> None:
    base = _k()
    assert base != _k(salt="abc")               # salt changes the key
    assert _k(salt="abc") == _k(salt="abc")      # but stays deterministic
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/utkarsh/Projects/richard/research/preprocessor && .venv/bin/python -m pytest tests/test_assets_cache.py -v`
Expected: FAIL with `ImportError: cannot import name 'cache_salt'` (and `_k() got an unexpected keyword argument 'salt'`).

- [ ] **Step 3: Implement** (edit `assets_cache.py`)

Add the salt helper and extend the key. Replace lines 18-22 with:

```python
import json


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
    resolution: str, salt: str = "",
) -> str:
    parts = [model or "", prompt or "", negative_prompt or "", aspect or "",
             resolution or "", salt or ""]
    return hashlib.sha256("\x00".join(parts).encode("utf-8")).hexdigest()
```

(Add `import json` near the top imports if not already present.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/utkarsh/Projects/richard/research/preprocessor && .venv/bin/python -m pytest tests/test_assets_cache.py -v`
Expected: PASS (all existing tests still green; the `salt=""` default keeps them unchanged).

- [ ] **Step 5: Back up, then wire the caller** (edit `generate_assets.py`)

First read the top-level `generate_assets(...)` function signature and the loop body that calls `_fal_generate` (the function whose body is at lines 280-395) to find the in-scope `client_slug`, brand colours, and `design_brief`. Add a `cache_salt` param to `_fal_generate` (the function containing line 305), defaulting to `""`, and pass `salt=cache_salt_value` into `fal_cache_key` at line 305:

```python
    cache_key = fal_cache_key(
        model=model, prompt=prompt, negative_prompt=negative_prompt,
        aspect=aspect, resolution=resolution, salt=cache_salt_value,
    )
```

In the top-level generate loop, compute it once (using a module-level `_PROMPT_BUILDER_VERSION = "2026-06-20.1"` constant added near the top of `generate_assets.py`):

```python
from stages.assets_cache import cache_salt  # add to existing import (line 38)

salt = cache_salt(
    client_slug=client_slug, brand_primary=brand_primary,
    brand_accent=brand_accent, design_brief=design_brief,
    builder_version=_PROMPT_BUILDER_VERSION,
)
```

Thread `cache_salt_value=salt` down to each `_fal_generate(...)` call. If a brand colour or `design_brief` is not directly in scope at the loop, read upward to the function parameters (the audit confirms brand + design_brief reach `generate_assets`); do not fabricate a literal.

- [ ] **Step 6: Run the full preprocessor asset suite**

Run: `cd /Users/utkarsh/Projects/richard/research/preprocessor && .venv/bin/python -m pytest tests/test_assets_cache.py tests/test_generate_assets.py tests/test_fal_cache_wiring.py -v`
Expected: PASS. If `test_fal_cache_wiring.py` asserts an exact key value, update that expected value (the key intentionally changed); note the change in the test docstring.

---

## Task 2: restructure cache key derives from the actual system prompt + copy budget

**Files:**
- Modify: `research/preprocessor/stages/restructure_page.py:32,389-395,423`
- Test: `research/preprocessor/tests/test_restructure_page.py`

- [ ] **Step 1: Write the failing test** (append to `test_restructure_page.py`)

```python
from stages.restructure_page import restructure_cache_key
import stages.restructure_page as rp


def test_restructure_key_tracks_prompt_and_budget(monkeypatch) -> None:
    pd = {"body": "a long paragraph", "ziel": "the goal"}
    base = restructure_cache_key(model="m", st_type="ST-05", page_data=pd, copy_budget=900)
    # copy_budget is part of the key
    assert base != restructure_cache_key(model="m", st_type="ST-05", page_data=pd, copy_budget=600)
    # editing the system prompt invalidates the key (no manual version bump)
    monkeypatch.setattr(rp, "_PROMPT_SIG", "DIFFERENT")
    assert base != restructure_cache_key(model="m", st_type="ST-05", page_data=pd, copy_budget=900)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/utkarsh/Projects/richard/research/preprocessor && .venv/bin/python -m pytest tests/test_restructure_page.py::test_restructure_key_tracks_prompt_and_budget -v`
Expected: FAIL (`restructure_cache_key() got an unexpected keyword argument 'copy_budget'`, and `_PROMPT_SIG` does not exist).

- [ ] **Step 3: Implement** (edit `restructure_page.py`)

After `_SYSTEM_PROMPT` is defined (it starts at line 60), add a derived signature so editing the prompt auto-invalidates the cache. Near the other module constants add:

```python
# Derived from the ACTUAL system prompt: editing _SYSTEM_PROMPT changes this,
# so a prompt edit invalidates every cached rewrite with no manual bump.
_PROMPT_SIG = hashlib.sha256(_SYSTEM_PROMPT.encode("utf-8")).hexdigest()[:16]
```

Replace `restructure_cache_key` (lines 389-395) with:

```python
def restructure_cache_key(
    *, model: str, st_type: str, page_data: dict, copy_budget: Optional[int] = None
) -> str:
    sel = {f: page_data.get(f) for f in _LONG_TEXT_FIELDS if page_data.get(f) is not None}
    blob = "\x00".join([
        model, st_type, _PROMPT_SIG, str(copy_budget),
        json.dumps(sel, sort_keys=True, ensure_ascii=False),
    ])
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
```

- [ ] **Step 4: Wire the caller** (line 423)

Read the `restructure_page()` body to find the copy-budget variable in scope (the over-budget trigger; the budget is the per-st_type character budget). Pass it into the key call at line 423:

```python
        cache_path = cache_dir / f"{restructure_cache_key(model=model, st_type=st_type, page_data=page_data, copy_budget=copy_budget)}.json"
```

If the budget variable has a different local name, use that name; do not invent a literal.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /Users/utkarsh/Projects/richard/research/preprocessor && .venv/bin/python -m pytest tests/test_restructure_page.py -v`
Expected: PASS. If a golden-snapshot test pins an exact cache filename, regenerate it (the key intentionally changed) and note it.

---

## Task 3: vision-score cache key includes the model and the prompt signature

**Files:**
- Modify: `research/quality_loop/vis_client.py:131-148,286`
- Test: `research/quality_loop/tests/test_vis_client.py`

- [ ] **Step 1: Write the failing test** (append to `test_vis_client.py`)

```python
def test_vis_cache_key_tracks_model_and_prompt(tmp_path) -> None:
    from vis_client import cache_key
    page = tmp_path / "p.png"; page.write_bytes(b"PNG")
    ref = tmp_path / "r.png"; ref.write_bytes(b"REF")
    rows = ["P05", "N08"]
    base = cache_key(str(page), [str(ref)], rows, model="m1", prompt_sig="s1")
    assert base == cache_key(str(page), [str(ref)], rows, model="m1", prompt_sig="s1")
    assert base != cache_key(str(page), [str(ref)], rows, model="m2", prompt_sig="s1")
    assert base != cache_key(str(page), [str(ref)], rows, model="m1", prompt_sig="s2")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/utkarsh/Projects/richard/research/quality_loop && python -m pytest tests/test_vis_client.py::test_vis_cache_key_tracks_model_and_prompt -v`
Expected: FAIL (`cache_key() got an unexpected keyword argument 'model'`).

- [ ] **Step 3: Implement** (edit `vis_client.py`)

Replace `cache_key` (lines 131-148) with a version that folds in the model and a prompt signature:

```python
def cache_key(
    page_png: str,
    reference_pngs: list[str],
    row_ids: list[str],
    *,
    model: str = "",
    prompt_sig: str = "",
) -> str:
    """sha256 over the page bytes + each reference's bytes + sorted row ids +
    the MODEL + a prompt signature. Sensitive to every input that changes the
    score, so swapping to a stronger grader (or editing the prompt) busts the
    cache instead of silently serving old scores.
    """
    h = hashlib.sha256()
    h.update(PROMPT_VERSION.encode("utf-8"))
    h.update(b"\x00model\x00")
    h.update((model or "").encode("utf-8"))
    h.update(b"\x00psig\x00")
    h.update((prompt_sig or "").encode("utf-8"))
    h.update(b"\x00page\x00")
    h.update(Path(page_png).read_bytes())
    for ref in reference_pngs:
        h.update(b"\x00ref\x00")
        h.update(Path(ref).read_bytes())
    h.update(b"\x00rows\x00")
    h.update("\x1f".join(sorted(row_ids)).encode("utf-8"))
    return h.hexdigest()
```

- [ ] **Step 4: Wire the call site** (line 286, in `score_page`)

Add a module helper that signs the actual prompt the call uses, then pass model + sig. First read `vis_prompt.py` to find the prompt-building function (e.g. `build_prompt(row_ids)` or the system prompt constant). Add near the top of `vis_client.py`:

```python
def _prompt_signature(row_ids: list[str]) -> str:
    """Hash of the actual built prompt for these rows, so a prompt-text change
    busts the cache. Imports vis_prompt lazily to keep the offline import clean.
    """
    import vis_prompt
    text = vis_prompt.build_prompt(sorted(row_ids))  # adjust to vis_prompt's real API
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
```

Change line 286 from `key = cache_key(page_png, reference_pngs, row_ids)` to:

```python
        key = cache_key(
            page_png, reference_pngs, row_ids,
            model=self.model, prompt_sig=_prompt_signature(row_ids),
        )
```

If `vis_prompt`'s builder has a different name or signature, match it; if no single function returns the score prompt text, sign the system-prompt constant it uses instead. Do not invent.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /Users/utkarsh/Projects/richard/research/quality_loop && python -m pytest tests/test_vis_client.py -v`
Expected: PASS (the existing offline tests still pass; `_prompt_signature` only runs on the real `score_page` path which the tests mock or avoid).

---

## Task 4: the anti-decay guard test (the regression lock)

**Files:**
- Create: `research/preprocessor/tests/test_cache_keys_guard.py`

- [ ] **Step 1: Write the guard test**

```python
"""Guard: every generation cache key must be sensitive to the inputs that can
change its output (model / prompt / brand). This is the lock against the
"I changed it and nothing changed" decay. If a future edit drops one of these
inputs from a key, this test fails."""
from __future__ import annotations

from stages.assets_cache import fal_cache_key, cache_salt
from stages.restructure_page import restructure_cache_key


def test_fal_key_includes_salt() -> None:
    base = fal_cache_key(model="m", prompt="p", negative_prompt=None,
                         aspect="1:1", resolution="2K", salt="")
    salted = fal_cache_key(model="m", prompt="p", negative_prompt=None,
                           aspect="1:1", resolution="2K", salt="x")
    assert base != salted, "fal key must include the brand/client salt"


def test_salt_includes_brand_and_client() -> None:
    a = cache_salt(client_slug="c1", brand_primary="#1", brand_accent="#2",
                   design_brief=None, builder_version="v")
    b = cache_salt(client_slug="c2", brand_primary="#1", brand_accent="#2",
                   design_brief=None, builder_version="v")
    assert a != b, "salt must distinguish clients"


def test_restructure_key_includes_budget() -> None:
    pd = {"body": "x"}
    assert (restructure_cache_key(model="m", st_type="ST-05", page_data=pd, copy_budget=900)
            != restructure_cache_key(model="m", st_type="ST-05", page_data=pd, copy_budget=600))
```

(The vis-score model/prompt sensitivity is covered by Task 3's test in the quality_loop suite; this file covers the two preprocessor caches that share the venv.)

- [ ] **Step 2: Run the guard**

Run: `cd /Users/utkarsh/Projects/richard/research/preprocessor && .venv/bin/python -m pytest tests/test_cache_keys_guard.py -v`
Expected: PASS.

- [ ] **Step 3: Run the brand-agnostic guard to confirm no literal leaked**

Run: `cd /Users/utkarsh/Projects/richard/research/preprocessor && .venv/bin/python -m pytest tests/ -k "no_client_name or literal" -v`
Expected: PASS (the new code hashes values, names no client).

---

## Task 5: full-suite regression check + purge the stale apex PNGs

- [ ] **Step 1: Run the full preprocessor suite**

Run: `cd /Users/utkarsh/Projects/richard/research/preprocessor && .venv/bin/python -m pytest tests/ -q`
Expected: PASS (or only the pre-existing, unrelated failures noted in `regressions-and-guardrails.md`; verify each failure with a swap-test before touching production, never "fix" production to satisfy a stale test).

- [ ] **Step 2: Run the quality_loop suite**

Run: `cd /Users/utkarsh/Projects/richard/research/quality_loop && python -m pytest tests/ -q`
Expected: PASS.

- [ ] **Step 3: Purge stale cached PNGs from the old (input-blind) key scheme**

The 5 stale apex fal PNGs and the 40 weeks-old vis-score caches were keyed under the old scheme and can no longer be trusted. Locate and delete them so the next run regenerates/regrades against the new keys:

Run: `find /Users/utkarsh/Projects/richard -type d \( -name ".vis_cache" -o -name "asset_cache" -o -name "restructure_cache" \) -not -path "*/.venv/*"` then remove the cached artifacts inside (keep the dirs). Confirm with the user before deleting if any dir is large or shared.

- [ ] **Step 4: Verify (the binding check)**

This phase changes no rendered pixels; its proof is the tests above plus a re-grade that no longer returns a cached verdict after a model change. Confirm: with the new keys, a second identical run is a cache HIT (fast, free), and changing the model or the salt forces a MISS (re-generation/re-grade). State the result plainly; do not claim done without the test output.

---

## Self-review

- **Spec coverage:** infection #4 (fal key) -> Task 1; #5 (restructure key + prompt-derived invalidation) -> Task 2; #6 (vis key model+prompt) -> Task 3; the section-6 guard ("a key that omits model/prompt/brand is a bug") -> Task 4. The two-divergent-restructure-dirs sub-issue (#5) is a caller/CWD concern resolved in Phase 4 (the orchestrator passes one absolute cache dir); noted, not silently dropped. Output-namespacing (#12) is deferred to Phase 4 (the orchestrator runs each job in a per-job output dir).
- **Placeholders:** none. Every code step shows the code; caller steps cite the exact file:line and the new call, with a "read the local context first" instruction where the surrounding variable names must be confirmed (never a fabricated literal).
- **Type consistency:** `cache_salt` and `fal_cache_key(salt=...)` names match across Tasks 1, 4; `restructure_cache_key(copy_budget=...)` matches across Tasks 2, 4; `cache_key(model=, prompt_sig=)` matches across Task 3.
- **Brand-agnostic + no em dashes:** confirmed throughout.
