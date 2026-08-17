# Pre-processor Architecture Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Each implementer should also use superpowers:test-driven-development.

**Goal:** Re-found the pre-processor's cross-cutting infrastructure (config, observability, resilience, typed contracts, orchestration) on best-practice patterns **without changing behavior** — the `resolved_package.json` output stays byte-identical and the 221 tests stay green; we only ADD tests.

**Architecture:** FastAPI app whose `/render` route delegates to a typed `Stage` runner; one pooled `httpx.AsyncClient` + typed `Settings` injected via `Depends`; all external calls go through one `stamina` retry policy (jitter + `Retry-After` + fal idempotency + budget guard); structured logging with a correlation id; the package output is validated against a Pydantic `ResolvedPackageManifest` and locked by a golden-file contract test. Implements the spec `2026-05-30-preprocessor-architecture-migration-design.md` (predecessor ADR `2026-05-30-preprocessor-architecture-research.md`).

**Tech Stack:** Python 3.11, FastAPI, Pydantic v2, **pydantic-settings** (NEW), httpx, **stamina** (NEW), **structlog** (NEW), pytest. Layer 1 at `research/preprocessor/`.

---

## Conventions & Guardrails (read before any task)

- **NO GIT in this repo.** Builds are verified by tests, not commits. Each task ENDS with a verification checkpoint (run the suite), NOT a `git commit`. Never run git.
- **Test command (the gate):** `cd research/preprocessor && .venv/bin/python -m pytest tests/ -q` → baseline **221 passed**. After each task: the count only grows (new tests) and nothing regresses.
- **Single-test run:** `.venv/bin/python -m pytest tests/test_X.py::test_name -q` (from `research/preprocessor/`).
- **Install a dependency:** `cd research/preprocessor && .venv/bin/python -m pip install <pkg>` THEN add the pinned line to `research/preprocessor/requirements.txt`. (This venv uses plain pip — NOT uv. No activation needed.)
- **Output-preserving rule:** Task 1 adds a golden-file contract test on `resolved_package.json` (the safety net). It MUST stay green after every later task. The package output never changes in this plan. (Async `/render` in Task 19 changes the HTTP *response shape*, not the package; its endpoint test is updated deliberately.)
- **Brand-agnostic guard:** `tests/test_no_client_name_in_logic.py` MUST stay green. No client name/hex/font literal in any new module.
- **Python 3.11 trap:** never put a backslash inside an f-string `{…}` expression (hard SyntaxError). Precompute into variables.
- **Imports:** `conftest.py` puts the preprocessor root on `sys.path`, so tests use flat imports (`from config import Settings`, `from stages.X import …`).
- **Fixtures:** `tests/fixtures/sample_render_request.json` is the canonical `/render` input (used by `test_render_endpoint.py`). With no API keys set, Stage 5 takes the stub path → deterministic output (good for golden-file).
- **Stages keep receiving keys/models/clients as function ARGS.** The route reads `Settings` + the pooled client and passes them in (as it does today with `os.getenv`). This keeps stage signatures + stage tests unchanged.

---

## File Structure

**Created:**
- `research/preprocessor/config.py` — `Settings(BaseSettings)` + `get_settings()`
- `research/preprocessor/logging_setup.py` — structlog config + correlation-id helpers
- `research/preprocessor/errors.py` — `PreprocessorError` taxonomy
- `research/preprocessor/_resilience.py` — shared retry policy (stamina) + `Retry-After` + timeout constants
- `research/preprocessor/pipeline.py` — `Stage` Protocol + `run_render_pipeline()`
- `research/preprocessor/stages/assets/{__init__,download,fal_client,prompts,inventory}.py` — split of `generate_assets.py`
- `research/preprocessor/tests/test_resolved_package_contract.py`, `test_config.py`, `test_resilience.py`, `test_error_handling.py`, `test_pipeline.py`
- `research/preprocessor/tests/golden/resolved_package.golden.json` — committed snapshot

**Modified:**
- `research/preprocessor/main.py` — lifespan + DI; thin routes; exception handlers; async `/render`
- `research/preprocessor/models.py` — `ResolvedPackageManifest` + `RenderAccepted`
- `research/preprocessor/stages/assemble_package.py` — validate-then-dump via the manifest model; warnings on swallowed failures
- `research/preprocessor/requirements.txt` — add `pydantic-settings`, `stamina`, `structlog`

**Deleted (Tier 3, with renderer Plan B):**
- `research/preprocessor/stages/generate_components.py` + `tests/test_generate_components.py`

---

## TIER 1.5 — The contract safety net (do FIRST)

### Task 1: Golden-file contract test on `resolved_package.json`

**Files:**
- Test: `tests/test_resolved_package_contract.py`
- Data: `tests/golden/resolved_package.golden.json` (bootstrapped on first run)

- [ ] **Step 1: Write the contract test** (mirrors the renderer's visual-regression bootstrap — first run writes the golden, later runs assert).

```python
# tests/test_resolved_package_contract.py
"""Locks the Layer-1↔Layer-2 seam: the resolved_package.json manifest
for the sample fixture must not change unless deliberately re-baselined
(set UPDATE_GOLDEN=1). This is the pre-processor's analog of the
renderer's visual-regression baseline."""
from __future__ import annotations
import json, os
from pathlib import Path
from fastapi.testclient import TestClient

HERE = Path(__file__).resolve().parent
GOLDEN = HERE / "golden" / "resolved_package.golden.json"
SAMPLE = HERE / "fixtures" / "sample_render_request.json"

VOLATILE = {"generated_at", "output_dir", "package_path"}  # absolute/time-varying

def _normalize(pkg: dict) -> dict:
    pkg = json.loads(json.dumps(pkg))  # deep copy
    for k in VOLATILE:
        if k in pkg:
            pkg[k] = "<normalized>"
    return pkg

def _render_manifest(tmp_path) -> dict:
    os.environ.pop("OPENROUTER_API_KEY", None)
    os.environ.pop("FAL_KEY", None)
    from main import app
    with TestClient(app) as client:
        resp = client.post("/render", json=json.loads(SAMPLE.read_text()))
    assert resp.status_code == 200, resp.text
    pkg_path = Path(resp.json()["package_path"])
    return json.loads(pkg_path.read_text())

def test_resolved_package_matches_golden(tmp_path):
    actual = _normalize(_render_manifest(tmp_path))
    if os.getenv("UPDATE_GOLDEN") == "1" or not GOLDEN.exists():
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(json.dumps(actual, indent=2, ensure_ascii=False))
        return  # bootstrapped — re-run asserts
    expected = json.loads(GOLDEN.read_text())
    assert actual == expected, "resolved_package.json changed — re-baseline with UPDATE_GOLDEN=1 ONLY if intended"
```

- [ ] **Step 2: Bootstrap the golden** — Run: `.venv/bin/python -m pytest tests/test_resolved_package_contract.py -q`. Expected: PASS (writes the golden on first run).
- [ ] **Step 3: Prove it asserts** — Run the same command again. Expected: PASS (now comparing against the committed golden). Sanity-check: temporarily change a literal in `assemble_package._build_manifest` (e.g. the schema version), re-run → it MUST FAIL; revert.
- [ ] **Step 4: Verify suite** — `.venv/bin/python -m pytest tests/ -q`. Expected: **222 passed** (221 + this).

> NOTE: if `/render` is async by the time later tasks run, this test's `/render` call must be updated alongside Task 19. Until then it is synchronous.

### Task 2: Promote the manifest to a typed `ResolvedPackageManifest`

**Files:**
- Modify: `models.py` (add model), `stages/assemble_package.py` (validate-then-dump)
- Test: `tests/test_assemble_package.py` (add one)

- [ ] **Step 1: Read** `stages/assemble_package.py` `_build_manifest` to capture the EXACT current manifest shape (top-level keys: `schema_version`, `brand`, `brand_axes`, `fonts`, `pages`, `report_assets`, `validation`, `asset_summary`, `generated_at`, …). The model must match it field-for-field.
- [ ] **Step 2: Write a failing test** that the dumped manifest validates against the new model.

```python
# tests/test_assemble_package.py  (append)
def test_manifest_validates_against_model(tmp_path):
    from models import ResolvedPackageManifest
    # build a package via the existing helper used elsewhere in this file,
    # then load resolved_package.json and validate:
    import json
    pkg = json.loads((tmp_path / "resolved_package.json").read_text())
    ResolvedPackageManifest.model_validate(pkg)  # raises if shape drifts
```
(Use the same package-building setup the other tests in this file already use; reuse their fixture/helper.)

- [ ] **Step 3: Add the model** in `models.py` mirroring the captured shape. Use `model_config = ConfigDict(extra="allow")` on nested page/data blocks (per-ST `data` is free-form) but pin the TOP-LEVEL keys explicitly. Example skeleton (fill to match the real shape):

```python
class ResolvedPackageManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")  # top-level is a fixed contract
    schema_version: str
    brand: dict[str, Any]
    brand_axes: dict[str, Any]
    fonts: dict[str, Any]
    pages: list[dict[str, Any]]
    report_assets: dict[str, Any] = Field(default_factory=dict)
    validation: dict[str, Any] = Field(default_factory=dict)
    asset_summary: dict[str, Any]
    generated_at: str
```

- [ ] **Step 4: validate-then-dump** in `assemble_package.py`: after building the manifest dict, do `manifest = ResolvedPackageManifest.model_validate(manifest_dict).model_dump()` (or validate the dict and dump the original — bytes must be unchanged) BEFORE `json.dump`. The serialized output must be identical.
- [ ] **Step 5: Verify** — `.venv/bin/python -m pytest tests/ -q`. Expected: **223 passed**, and `test_resolved_package_contract.py` STILL green (output unchanged). If the golden changed, the model altered the bytes — fix the model/dump so output is identical.

---

## TIER 0 — Config + pooled client + structured logging

### Task 3: `config.py` typed Settings

**Files:** Create `config.py`; Test `tests/test_config.py`

- [ ] **Step 1: Install** — `.venv/bin/python -m pip install pydantic-settings` and add `pydantic-settings>=2.5` to `requirements.txt`.
- [ ] **Step 2: Write failing test** `tests/test_config.py`:

```python
def test_settings_defaults_and_secret_masking(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-secret")
    monkeypatch.setenv("FAL_KEY", "fal-secret")
    from config import Settings
    s = Settings(_env_file=None)  # ignore the real .env in tests
    assert s.openrouter_api_key.get_secret_value() == "sk-secret"
    assert s.fal_image_model == "fal-ai/nano-banana-pro"   # default preserved
    assert s.openrouter_vision_model == "anthropic/claude-sonnet-4.6"
    assert "sk-secret" not in repr(s)            # SecretStr masks in repr
    assert s.max_generations_per_report == 12

def test_get_settings_is_cached():
    from config import get_settings
    assert get_settings() is get_settings()
```

- [ ] **Step 3: Run → FAIL** (`No module named 'config'`).
- [ ] **Step 4: Implement `config.py`** (defaults MUST equal today's inline `os.getenv` defaults so behavior is identical):

```python
from __future__ import annotations
from functools import lru_cache
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)
    openrouter_api_key: SecretStr | None = None
    fal_key: SecretStr | None = None
    openrouter_vision_model: str = "anthropic/claude-sonnet-4.6"
    openrouter_brief_model: str = "anthropic/claude-opus-4.6"
    openrouter_prompt_model: str = "anthropic/claude-sonnet-4.6"
    fal_image_model: str = "fal-ai/nano-banana-pro"
    fal_image_resolution: str = "2K"
    report_generator_webhook: str | None = None
    onboard_output_dir: str | None = None
    # Tier-1 knobs (used later; harmless now)
    max_generations_per_report: int = 12
    retry_attempts: int = 3
    fal_cache_dir: str | None = None

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 5: Run → PASS**, then full suite → **225 passed**.

### Task 4: Wire `Settings` into the routes (replace `os.getenv`)

**Files:** Modify `main.py`

- [ ] **Step 1:** In `main.py`, add `from config import Settings, get_settings` and inject `settings: Settings = Depends(get_settings)` into both `onboard()` and `render()`.
- [ ] **Step 2:** Replace each `os.getenv(...)` (lines ~102-112, ~226-232) with the matching `settings.*` — using `.get_secret_value()` for the two secrets. Delete the `_DEFAULT_VISION_MODEL`/`_DEFAULT_BRIEF_MODEL` constants (now defaults in `Settings`). Pass `settings.*` into the stage calls exactly where `os.getenv` was passed. **Do not change stage signatures.**
- [ ] **Step 3: Verify** — full suite → **225 passed**; golden-file green (defaults unchanged ⇒ output unchanged). Grep check: `grep -rn "os.getenv" main.py` → only non-config uses remain (ideally none).

### Task 5: `lifespan` + pooled `httpx.AsyncClient` via DI

**Files:** Modify `main.py`

- [ ] **Step 1:** Add a `lifespan` async context manager that creates ONE `httpx.AsyncClient(timeout=httpx.Timeout(30.0), limits=httpx.Limits(max_keepalive_connections=10, max_connections=20))`, stores it on `app.state.http_client`, and closes it on exit. Pass `lifespan=lifespan` to `FastAPI(...)`.
- [ ] **Step 2:** Add a dependency `def get_http_client(request: Request) -> httpx.AsyncClient: return request.app.state.http_client` and inject it into both routes.
- [ ] **Step 3:** Pass the injected client as the existing `http_client=` arg into `generate_assets(...)`, `run_onboard_pipeline(...)` (and any other stage that accepts it). The stages already self-construct only when `http_client is None`, so tests that inject `MockTransport` are unaffected.
- [ ] **Step 4: Verify** — full suite → **225 passed** (TestClient triggers lifespan; `test_render_endpoint.py` + `test_onboard_endpoint.py` exercise the pooled client). Golden green.

### Task 6: Structured logging + correlation id (`logging_setup.py`)

**Files:** Create `logging_setup.py`; Modify `main.py`

- [ ] **Step 1: Install** — `.venv/bin/python -m pip install structlog` and add `structlog>=24.4` to `requirements.txt`.
- [ ] **Step 2: Write failing test** (append to `tests/test_config.py` or a new `tests/test_logging.py`):

```python
def test_bind_job_id_and_logger():
    from logging_setup import configure_logging, bind_job_id, get_logger
    configure_logging()
    bind_job_id("job-123")
    log = get_logger("test")
    log.info("hello")          # must not raise; job_id is in contextvars
```

- [ ] **Step 3: Run → FAIL**.
- [ ] **Step 4: Implement `logging_setup.py`** (structlog with stdlib integration + JSON to stdout + contextvars):

```python
from __future__ import annotations
import logging, structlog

def configure_logging() -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        cache_logger_on_first_use=True,
    )

def bind_job_id(job_id: str) -> None:
    structlog.contextvars.bind_contextvars(job_id=job_id)

def get_logger(name: str = "preprocessor"):
    return structlog.get_logger(name)
```

- [ ] **Step 5:** In `main.py`, call `configure_logging()` once at import/lifespan startup; in BOTH routes mint a `job_id` (`/onboard` already has one at line ~95 — reuse it; `/render` needs `job_id = uuid4().hex`) and call `bind_job_id(job_id)` at the top of the handler.
- [ ] **Step 6: Verify** — run new test → PASS; full suite → **226 passed**; golden green.

### Task 7: Replace silent `except: pass` + log failure sites

**Files:** Modify `main.py`, `stages/generate_assets.py`, `stages/onboard/{capture,pipeline}.py`

- [ ] **Step 1:** In `main.py`, replace `except httpx.HTTPError: pass` (~line 132) with `except httpx.HTTPError as exc: get_logger().warning("webhook_delivery_failed", attempt=_attempt, error=str(exc))` and `except OSError: pass` (~line 139) with a logged `error`. **Control flow unchanged** (still falls through to disk fallback / gives up).
- [ ] **Step 2:** At each structured-failure site that returns a `failed`/`{}`/`None` (`generate_assets.py` ~364, ~774; `onboard/capture.py`; `onboard/pipeline.py` ~88), add a `get_logger().warning(...)` with context BEFORE the existing return. **Do not change the return value** (fail-soft preserved).
- [ ] **Step 3: Verify** — full suite → **226 passed**; golden green (return values unchanged ⇒ output unchanged).

---

## TIER 1 — Resilience + idempotency + budget

### Task 8: `_resilience.py` — shared retry policy (stamina)

**Files:** Create `_resilience.py`; Test `tests/test_resilience.py`

- [ ] **Step 1: Install** — `.venv/bin/python -m pip install stamina` and add `stamina>=24.3` to `requirements.txt`.
- [ ] **Step 2: Write failing tests** locking the policy behavior:

```python
# tests/test_resilience.py
import httpx, pytest, stamina

def setup_module(_): stamina.set_active(False)  # no wall-clock sleeps in tests

def test_is_retryable_classification():
    from _resilience import is_retryable
    assert is_retryable(httpx.ConnectError("x"))
    assert is_retryable(httpx.ReadTimeout("x"))
    r = httpx.Response(503, request=httpx.Request("GET", "http://x"))
    assert is_retryable(httpx.HTTPStatusError("x", request=r.request, response=r))
    r4 = httpx.Response(404, request=httpx.Request("GET", "http://x"))
    assert not is_retryable(httpx.HTTPStatusError("x", request=r4.request, response=r4))

@pytest.mark.asyncio
async def test_retry_after_seconds_parsed():
    from _resilience import parse_retry_after
    r = httpx.Response(429, headers={"Retry-After": "2"}, request=httpx.Request("GET","http://x"))
    assert parse_retry_after(r) == 2.0
    r2 = httpx.Response(429, request=httpx.Request("GET","http://x"))
    assert parse_retry_after(r2) is None
```

- [ ] **Step 3: Run → FAIL**.
- [ ] **Step 4: Implement `_resilience.py`**:

```python
from __future__ import annotations
import asyncio, httpx, stamina

RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})

# Per-service timeouts (keep today's values).
TIMEOUT_DOWNLOAD = httpx.Timeout(30.0, connect=5.0)
TIMEOUT_FAL      = httpx.Timeout(180.0, connect=5.0)
TIMEOUT_LLM      = httpx.Timeout(120.0, connect=5.0)
TIMEOUT_WEBHOOK  = httpx.Timeout(30.0, connect=5.0)

def is_retryable(exc: Exception) -> bool:
    if isinstance(exc, (httpx.TransportError, httpx.TimeoutException)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in RETRYABLE_STATUS
    return False

def parse_retry_after(resp: httpx.Response) -> float | None:
    val = resp.headers.get("Retry-After")
    if val is None: return None
    try: return float(val)
    except ValueError: return None  # HTTP-date form: ignore, fall back to backoff

async def request_with_retry(client, method, url, *, attempts=3, **kw) -> httpx.Response:
    """One policy for all external HTTP: exp backoff + jitter via stamina,
    Retry-After honored on 429/503, retry only transient classes."""
    async for attempt in stamina.retry_context(on=is_retryable, attempts=attempts):
        with attempt:
            resp = await client.request(method, url, **kw)
            if resp.status_code in RETRYABLE_STATUS:
                wait = parse_retry_after(resp)
                if wait: await asyncio.sleep(wait)
                resp.raise_for_status()   # -> HTTPStatusError -> retried
            return resp
```

- [ ] **Step 5: Run → PASS**; full suite → **228 passed**.

### Task 9: Route all external calls through the resilience helper

**Files:** Modify `stages/generate_assets.py`, `stages/build_image_prompts.py`, `stages/onboard/{vision_reading,brand_brief}.py`, `main.py` (webhook)

- [ ] **Step 1:** Replace each ad-hoc call/loop with `await request_with_retry(client, "POST"|"GET", url, attempts=…, timeout=TIMEOUT_…, ...)`: downloads (drop the linear `0.5*attempt` loop), fal POST (`attempts=2`), the 3 OpenRouter POSTs (`attempts=settings.retry_attempts`), and the webhook (replace the manual `_WEBHOOK_RETRIES` loop in `main.py`). Keep the existing fail-soft handling AROUND the call (so a final failure still degrades to stub/`{}`/`None` + a logged warning).
- [ ] **Step 2:** Ensure tests still inject their `MockTransport`/`patch` clients; add `stamina.set_active(False)` in the relevant test modules' setup so non-200 paths don't sleep. (Existing `test_generate_assets.py` asserts on retry — verify those still pass; adjust the assertion to the unified helper if needed, keeping the same observable outcome.)
- [ ] **Step 3: Verify** — full suite → **228 passed**; golden green (with keys unset, no external calls happen ⇒ output unchanged).

### Task 10: fal content-addressed cache (idempotency — don't re-pay)

**Files:** Modify `stages/generate_assets.py` (fal generation path); Test `tests/test_generate_assets.py`

- [ ] **Step 1: Write failing test**: calling the fal generator twice with identical (model, prompt, aspect, resolution, format) does the network POST ONCE; the second call returns the cached file.

```python
@pytest.mark.asyncio
async def test_fal_generation_is_cached(tmp_path, monkeypatch):
    from stages.generate_assets import fal_generate_image
    calls = {"n": 0}
    async def fake_post(*a, **k):
        calls["n"] += 1
        return _fake_fal_response()   # reuse the module's existing fake helper
    # ... patch the POST, call fal_generate_image twice with same args + cache_dir=tmp_path
    # assert calls["n"] == 1 and both return a path under tmp_path
```

- [ ] **Step 2: Run → FAIL**.
- [ ] **Step 3: Implement**: before the fal POST, compute `key = hashlib.sha256(f"{model}|{prompt}|{aspect}|{resolution}|{fmt}".encode()).hexdigest()`; if `{cache_dir}/{key}.png` exists, return it (status `generated`, message `"cache_hit"`); else POST, download, save to that path. `cache_dir` comes from `Settings.fal_cache_dir` (default to a stable subdir of the output dir).
- [ ] **Step 4: Run → PASS**; full suite → **229 passed**; golden green (keys unset ⇒ fal not invoked).

### Task 11: Per-report image budget guard

**Files:** Modify `stages/generate_assets.py` (the `generate_assets` orchestrator); Test `tests/test_generate_assets.py`

- [ ] **Step 1: Write failing test**: with `max_generations=1` and 2 generate-class slots, exactly 1 is `generated`; the rest are `stub_not_generated` with a budget warning.
- [ ] **Step 2: Run → FAIL**.
- [ ] **Step 3: Implement**: thread a `max_generations` param (from `Settings.max_generations_per_report`) into `generate_assets`; count generations; once the count reaches the cap, remaining generate-class specs short-circuit to `AssetResult(status="stub_not_generated", message="image budget exhausted")` + a logged warning. Default is high (12) so existing fixtures never trip.
- [ ] **Step 4: Run → PASS**; full suite → **230 passed**; golden green (sample fixture stays under budget).

### Task 12: Formalize graceful degradation (warnings on every swallowed failure)

**Files:** Modify `stages/assemble_package.py` (+ verify other sites)

- [ ] **Step 1:** Audit every place an external failure is swallowed (`failed`/`{}`/`None`) and ensure it produces BOTH a logged warning (Task 7) AND a user-facing warning string in the assembled package's `validation.warnings` (so Richard sees it). The webhook failure path is the main gap.
- [ ] **Step 2: Write a test** asserting a simulated failed asset yields a `failed` status AND a warning in the package summary (it must NOT raise).
- [ ] **Step 3: Run → PASS**; full suite → **231 passed**; golden green (no failures in the clean sample ⇒ unchanged).

### Task 13: Error taxonomy + exception handlers (`errors.py`)

**Files:** Create `errors.py`; Modify `main.py`; Test `tests/test_error_handling.py`

- [ ] **Step 1: Write failing test**: monkeypatch a stage to raise inside `/render`; assert the response is a structured envelope (`status="error"`, `errors[...]`) with the `job_id`, NOT a bare 500.

```python
def test_render_unexpected_error_returns_envelope(monkeypatch):
    from fastapi.testclient import TestClient
    import main
    def boom(*a, **k): raise RuntimeError("kaboom")
    monkeypatch.setattr(main, "generate_assets", boom)  # or patch where used
    with TestClient(main.app) as c:
        r = c.post("/render", json=_sample())
    assert r.status_code in (200, 500)        # whichever the envelope uses
    body = r.json()
    assert body["status"] == "error"
    assert any("kaboom" in (e.get("message","")) for e in body["errors"])
```

- [ ] **Step 2: Run → FAIL**.
- [ ] **Step 3: Implement `errors.py`**:

```python
class PreprocessorError(Exception):
    code = "preprocessor_error"
class ExternalCallError(PreprocessorError): code = "external_call_error"
class AssetGenerationError(PreprocessorError): code = "asset_generation_error"
class PackageAssemblyError(PreprocessorError): code = "package_assembly_error"
```

- [ ] **Step 4:** In `main.py`, register `app.add_exception_handler(PreprocessorError, …)` and a catch-all `Exception` handler that logs (with `job_id`) and returns the SAME envelope shape the routes use (`RenderResponse(status="error", errors=[ValidationIssue(code=…, message=str(exc))])`). Fail loud only here; advisory validators stay non-blocking.
- [ ] **Step 5: Run → PASS**; full suite → **232 passed**; golden green.

---

## TIER 2 — Orchestration, typed seams, assets split, async `/render`

### Task 14: Extract `run_render_pipeline` (pure move) into `pipeline.py`

**Files:** Create `pipeline.py`; Modify `main.py`

- [ ] **Step 1:** Move the Stage 1-8 body of the `render()` handler (`main.py` ~176-272) verbatim into `async def run_render_pipeline(request, *, settings, http_client) -> ResolvedPackage` in `pipeline.py`. The route becomes: bind job id → call `run_render_pipeline(...)` → map to `RenderResponse`. NO logic change, same call order, same args.
- [ ] **Step 2: Verify** — full suite → **232 passed**; golden green. (`test_render_endpoint.py` proves the move preserved behavior.)

### Task 15: `Stage` Protocol + runner + per-stage timing

**Files:** Modify `pipeline.py`; Test `tests/test_pipeline.py`

- [ ] **Step 1: Write failing test**: `run_render_pipeline` returns a result whose timing map has one entry per stage (e.g. `result.timings` or a logged `stage_timing` per stage); mirror the `_mark` idiom from `stages/onboard/pipeline.py`.
- [ ] **Step 2: Run → FAIL**.
- [ ] **Step 3: Implement**: define a `Stage` `typing.Protocol` (documented `name` + callable contract) and wrap each stage call in a `_mark(name, t0)` timing helper + uniform try/except that routes unexpected raises to the Task-13 taxonomy. Keep stage 1's early-return as a short-circuit.
- [ ] **Step 4: Run → PASS**; full suite → **233 passed**; golden green.

### Task 16: Tighten the typed seams

**Files:** Modify `pipeline.py`, `stages/validate_input.py` (or a new `resolve_axes` helper), `stages/plan_layout.py`, `stages/generate_assets.py`

- [ ] **Step 1:** Move `brand_axes` construction out of the route/runner literal (was `main.py:255-260`) into a small typed `resolve_axes(brand_profile) -> dict` helper. Add a unit test for it.
- [ ] **Step 2:** Replace the duplicated `_unpack_page` normalizers (`plan_layout.py:108`, `generate_assets.py:528`) with ONE shared typed helper (e.g. `models.as_report_pages(...)`). Add a unit test.
- [ ] **Step 3:** Remove mid-pipeline `.model_dump()` round-trips where a typed object can be threaded and dumped once at the assemble/response boundary (only where it does not change output bytes).
- [ ] **Step 4: Verify** — full suite → **235 passed**; golden green (these are internal refactors ⇒ output unchanged).

### Task 17: Split `generate_assets.py` → `stages/assets/`

**Files:** Create `stages/assets/{__init__,download,fal_client,prompts,inventory}.py`; Delete the monolith body; Modify imports + `tests/test_generate_assets.py`

- [ ] **Step 1:** Create the `stages/assets/` package and MOVE functions by responsibility (no logic change): `download.py` (`normalise_gdrive_url`, `download_image`), `fal_client.py` (`_fal_aspect`, `fal_generate_image`, the `generate_*` generators, cache + budget from Tasks 10-11), `prompts.py` (`_compose_prompt`, `_brief_field`), `inventory.py` (`generate_assets` orchestrator + `_index_manifest`). Re-export the public names from `stages/assets/__init__.py` so `from stages.generate_assets import generate_assets` callers can switch to `from stages.assets import generate_assets`.
- [ ] **Step 2:** Update `main.py`/`pipeline.py` imports and `fixtures/apex/build_package.py`. Update `tests/test_generate_assets.py` import paths (behavior assertions unchanged).
- [ ] **Step 3: Verify** — full suite → **235 passed**; golden green. Grep: `grep -rn "generate_assets" --include=*.py . | grep import` resolves only to the new package.

### Task 18 (OPTIONAL): fal queue + `request_id` re-fetch

**Files:** Modify `stages/assets/fal_client.py`; Test `tests/test_generate_assets.py`

- [ ] **Step 1:** Behind a `Settings` flag (`fal_use_queue: bool = False`), submit to `queue.fal.run`, persist `request_id`, poll for completion, and on a *download* failure re-fetch the result by `request_id` (no re-generation). Add tests using the existing `MockTransport` handler routing.
- [ ] **Step 2: Verify** — full suite green; golden green (flag default off ⇒ unchanged). *Skip if deferring; the cache (Task 10) already covers re-runs.*

### Task 19: Async `/render` (202 + background + webhook)

**Files:** Modify `main.py`, `models.py`; Test `tests/test_render_endpoint.py`, `tests/test_resolved_package_contract.py`

- [ ] **Step 1:** Add `RenderAccepted(status, job_id, record_id)` to `models.py`.
- [ ] **Step 2:** Split `render()`: run CHEAP Stage-1 validation synchronously (return 422/`status="error"` inline — "reject loud" stays immediate); on success, `background_tasks.add_task(_run_and_deliver_render, request, job_id, settings, ...)` and return `202` + `RenderAccepted`. `_run_and_deliver_render` runs `run_render_pipeline` then delivers `RenderResponse` via the existing `_deliver_result` shape (webhook + disk fallback), with an idempotent payload keyed on `record_id`.
- [ ] **Step 3:** Update `test_render_endpoint.py` to assert `202` + delivered payload (model it on `test_onboard_endpoint.py`). Update `test_resolved_package_contract.py` to read the delivered/written package instead of the sync response body (e.g. point delivery at a temp dir and read `resolved_package.json` there).
- [ ] **Step 4: Verify** — full suite green; the golden assertion still holds against the delivered package (package bytes unchanged; only transport changed).

---

## TIER 3 — Stage-6 retirement (execute WITH renderer Plan B)

> Do these only once renderer Plan B confirms the renderer builds every visual from `page["data"]` (already true today — see ADR §E). Sequenced last so "renderer owns charts" is proven end-to-end.

### Task 20: Neutralize the Stage-6 producer

**Files:** Modify `pipeline.py` (formerly `main.py:236`)

- [ ] **Step 1:** Replace the `generate_components_for_report(...)` call with `components = {}` (keep the manifest `components` field — renderer reads it defensively). 
- [ ] **Step 2: Verify** — full suite green; **re-render the apex fixture** (`cd research/preprocessor && .venv/bin/python ../v7-renderer/fixtures/apex/build_package.py`) then render the PDF (per context.md) and confirm slot 16 is byte-stable. **Re-baseline the golden** (`UPDATE_GOLDEN=1`) since the package's `components` arrays legitimately go empty — this is the ONE intentional output change, reviewed.

### Task 21: Delete the Stage-6 module + test

**Files:** Delete `stages/generate_components.py`, `tests/test_generate_components.py`; Modify imports in `pipeline.py`/`main.py` + `fixtures/apex/build_package.py`

- [ ] **Step 1:** Remove the files and all imports of `generate_components_for_report`.
- [ ] **Step 2: Verify** — full suite green (count drops by the deleted test file's tests; that's expected). Golden green.

### Task 22: Strip vestigial `components` plumbing

**Files:** Modify `stages/plan_layout.py`, `stages/assemble_package.py`, `tests/test_assemble_package.py`

- [ ] **Step 1:** Remove the now-unused `components` carrying from `PlannedPage`, `_write_components`/`_component_path_map`, and the one SVG-content test. Keep the manifest `components: []` field for renderer compatibility (or coordinate its removal with the renderer in Plan B).
- [ ] **Step 2: Verify** — full suite green; golden green (the field stays `[]`).

---

## Self-Review

- **Spec coverage:** Tier 0 → Tasks 3-7; Tier 1 → Tasks 8-13 (+ contract net Tasks 1-2); Tier 2 → Tasks 14-19; Tier 3 → Tasks 20-22. All spec §4-7 items mapped. ✔
- **Placeholder scan:** every task has concrete files, real test code, and either real implementation or a precise mechanical transformation (splits/moves). Third-party specifics (stamina/pydantic-settings/structlog) are pinned by tests that lock behavior. ✔
- **Type/name consistency:** `Settings`/`get_settings`, `ResolvedPackageManifest`, `request_with_retry`/`is_retryable`/`parse_retry_after`, `run_render_pipeline`, `RenderAccepted`, `PreprocessorError` taxonomy — used consistently across tasks. ✔
- **Output-preserving:** the golden-file (Task 1) is added first and asserted after every task; the ONLY intentional re-baseline is Task 20 (empty `components`), explicitly flagged. ✔
- **No-git adaptation:** every task ends in a suite-run checkpoint, not a commit. ✔
- **Brand-agnostic:** all new modules are pure infrastructure; the guard test stays green. ✔
