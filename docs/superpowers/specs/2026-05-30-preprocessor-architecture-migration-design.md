# Pre-processor Architecture Migration — Design / PRD

**Status:** In design — pending user review
**Date:** 2026-05-30
**Component:** `research/preprocessor/` (Layer 1)
**Predecessor:** `2026-05-30-preprocessor-architecture-research.md` (the ADR this implements — 5-agent study, findings A–E)
**Decisions locked (user, 2026-05-30):** spec **all 4 tiers**; stay **Python / FastAPI / Pydantic v2 / httpx**; **output-preserving** (221 tests stay green, only ADD tests); then proceed to renderer **Plan B**.

---

## 1. Goal

Re-found the pre-processor's **cross-cutting infrastructure** — config, observability, resilience, typed contracts, orchestration — on best-practice patterns, so the (already correct, already tested) **logic becomes robust, observable, and cheap to extend**, *without changing behavior*. Same stack, fundamentally better wiring:

> `n8n request` → **typed Settings + pooled client (DI)** → **Stage runner** (typed seams, per-stage timing, one error policy) → stages calling externals through **one resilience policy** (retry+jitter, `Retry-After`, fal idempotency, budget guard) → **schema-validated `resolved_package.json`** → all under **structured logging with a correlation id**.

Today the `/render` handler hand-sequences 8 stages inline, reads scattered `os.getenv`, builds a fresh httpx client per call, has **zero logging**, retries inconsistently, **re-pays for fal on every retry**, and emits an **unvalidated** package dict. None of that is the logic — it's the missing infrastructure layer. This spec adds it tier by tier, each step keeping the suite green.

## 2. Non-negotiable principles

- **Behavior-preserving.** The `resolved_package.json` output is unchanged; the 221 tests stay green; we only ADD tests. The pre-processor analog of the renderer's visual-regression gate is a **golden-file + Pydantic schema contract test on `resolved_package.json`** (§5), added *first* as the safety net.
- **Brand-agnostic (cardinal rule).** No client name/hex/font literal in logic. `test_no_client_name_in_logic` stays green; every NEW module (`config`, `_resilience`, `pipeline`, `errors`, `logging_setup`, `stages/assets/`) carries zero client specifics.
- **Right-sized / YAGNI.** Reject heavyweight orchestration, brokers, and tracing (ADR §A/B/D). Stay stdlib + three small, well-chosen libs: `pydantic-settings`, `stamina`, `structlog`. No Redis/arq, no Celery, no circuit breaker, no OpenTelemetry-now (clean upgrade paths noted in §9).
- **Incremental + reversible.** Each tier — and each step within it — ships independently with both suites green. No big-bang.

## 3. Target architecture (files)

```
research/preprocessor/
  config.py               # NEW — Settings(BaseSettings): SecretStr keys, model slugs, timeouts, dirs, webhook; @lru_cache get_settings()
  logging_setup.py        # NEW — structlog config (stdlib integration, JSON to stdout) + job/correlation-id binding
  errors.py               # NEW — PreprocessorError taxonomy (ExternalCallError, AssetGenerationError, PackageAssemblyError)
  _resilience.py          # NEW — shared retry policy (stamina) + Retry-After parser + per-service httpx.Timeout constants
  pipeline.py             # NEW — Stage Protocol + run_render_pipeline() runner (mirrors stages/onboard/pipeline.py)
  main.py                 # MODIFIED — lifespan (pooled httpx client) + Depends(settings/client); thin routes; /render→202+webhook; exception handlers
  models.py               # MODIFIED — ResolvedPackageManifest (promote manifest dict → typed); typed stage seams
  stages/
    assets/               # NEW package (split of generate_assets.py, 822 lines, 4 responsibilities):
      download.py         #   normalise_gdrive_url, download_image
      fal_client.py       #   fal_generate_image + generators + content-addressed cache + budget guard
      prompts.py          #   _compose_prompt + brief-field helpers (or fold into build_image_prompts.py)
      inventory.py        #   generate_assets orchestrator + _index_manifest
    generate_components.py # DELETED in Tier 3 (Stage-6 retirement), with test_generate_components.py
    validate_input.py / resolve_fonts.py / validate_copy.py / validate_copyfit.py /
    validate_cover.py / plan_layout.py / assemble_package.py   # MODIFIED only where seams tighten; keys now arrive via Settings
    onboard/              # unchanged (already the reference pattern we mirror)
  tests/
    test_resolved_package_contract.py  # NEW — golden-file + ResolvedPackageManifest schema on the sample fixture
    test_pipeline.py                   # NEW — Stage runner + per-seam contract tests
    test_resilience.py                 # NEW — retry/backoff/Retry-After/idempotency/budget
    test_error_handling.py             # NEW — top-level handler returns the envelope, not a bare 500
    test_config.py                     # NEW — Settings load + defaults + SecretStr masking
```

---

## 4. Tier 0 — Config + pooled client + structured logging (the foundation)

**4.1 Central typed config (`config.py`).** A single `Settings(BaseSettings)` with `model_config = SettingsConfigDict(env_file=".env", extra="ignore")` so `.env` loads **in-process** (today it loads only via `uvicorn --env-file`, so tests/scripts silently get defaults — ADR §D). Fields: `openrouter_api_key: SecretStr | None`, `fal_key: SecretStr | None`, model slugs (`openrouter_vision_model`, `openrouter_brief_model`, `openrouter_prompt_model`, `fal_image_model`, `fal_image_resolution`), per-service timeouts, `report_generator_webhook`, `onboard_output_dir`, plus Tier-1 knobs (`max_generations_per_report`, retry attempts, cache dir). Expose `@lru_cache def get_settings()`; inject via `settings: Settings = Depends(get_settings)`.
- **Output-preserving lever:** stages keep receiving keys/model-slugs as **function args** (exactly as today). The route stops calling `os.getenv(...)` and passes `settings.x` instead. So **no stage signature or stage test changes** — it's pure centralization. Deletes the 10 scattered `os.getenv` (`main.py:102-112,226-232`) and the inline `_DEFAULT_*` slug literals (`main.py:80-82,228,231,232`).

**4.2 Pooled httpx client (`lifespan` + DI).** Create ONE `httpx.AsyncClient` (with `httpx.Limits` + explicit `httpx.Timeout`) in a FastAPI `lifespan`, store on `app.state`, close on shutdown; inject via `Depends`. Pass it as the `http_client=` arg the stages **already accept** (`generate_assets`, `build_image_prompts`, `vision_reading`, `brand_brief`, `run_onboard_pipeline` all take `http_client: Optional[...] = None` — ADR §B). So this is wiring, not a rewrite; tests still inject `MockTransport` fakes. Removes per-call client construction (no connection reuse today).

**4.3 Structured logging + correlation id (`logging_setup.py`).** Adopt **structlog** (stdlib integration via `ProcessorFormatter`, JSON renderer to stdout) — chosen over bare stdlib because its `contextvars` binding propagates a `job_id` through the deep async stage tree with no per-call plumbing (ADR §D). Mint a `job_id` on **both** routes (`/onboard` already mints one at `main.py:95`; add one to `/render`) and bind it so every line correlates. **Replace the two silent `except: pass`** (`main.py:132` webhook, `main.py:139` disk-fallback) with logged handling, and add a `logger.warning(...)` at each structured-failure site (`generate_assets` `:364,774`, onboard `capture.py`/`pipeline.py`) **without changing the fail-soft return value**. Net: the existing "fail-soft, record reason in payload" behavior is preserved AND becomes queryable.

## 5. Tier 1 — Resilience + the contract safety net

**5.1 Unified retry policy (`_resilience.py`).** Adopt **`stamina`** (opinionated tenacity wrapper: exp backoff + jitter by default, async-native — ADR §C). One shared helper wraps the injected client with the standard policy: **max 3 attempts** (max **2** for the costly fal POST), retry only `httpx.TransportError`/`TimeoutException` + HTTP `{429,500,502,503,504}`, never 4xx≠429, **honor `Retry-After`** on 429/503, explicit `httpx.Timeout` per service (keep today's values: download 30s, fal 180s, OpenRouter prompt 120s / vision 60s / brief 240s, webhook 30s). Route **all** call sites through it — unifying the three current ad-hoc behaviors (download's linear `0.5*attempt` no-jitter; the no-retry LLM/fal POSTs; the tight webhook loop). Tests: `MockTransport` + `stamina.set_active(False)` (or `attempts=1`) so no wall-clock sleeps; success/non-200/parse paths return identically → existing assertions hold.

**5.2 fal idempotency — never pay twice (`stages/assets/fal_client.py`).** Two complementary, simple mechanisms (ADR §C):
- **Content-addressed cache:** `key = sha256(model + prompt + aspect + resolution + output_format)`; store at `{cache_dir}/{key}.png`; **check-before-POST** → cache hit skips the paid generation entirely (survives re-runs).
- **fal queue `request_id`:** switch the generation POST from synchronous `fal.run/{model}` to the **queue** (`queue.fal.run`), persist `request_id`, and on a *download* failure re-fetch the **result** by `request_id` rather than re-generating. (Sequence this last / behind a flag — it's the largest change; the cache alone already covers re-runs.)

**5.3 Per-report budget guard.** `Settings.max_generations_per_report` (high default so existing fixtures never trip). `inventory.py` counts generations; once exceeded, remaining generate-class specs **degrade to `stub_not_generated` + a warning** ("image budget exhausted"). Fail-safe against silent overspend.

**5.4 Formalize graceful degradation.** Make "external call failed → degrade to `stub`/`failed` + a warning, never raise" the documented contract for *all* externals (already true for the LLM calls and fal). Ensure **every** swallowed failure adds a warning string (the webhook path currently does not). Preserves the project's "warn, never block" rule.

**5.5 The contract safety net (`test_resolved_package_contract.py` + `ResolvedPackageManifest`).** The single highest-value test — it locks the Layer-1↔Layer-2 seam (ADR §D):
- **Golden-file:** render the committed sample fixture, normalize volatile fields (`generated_at`, `record_id`, temp paths — the test already asserts no `/Users/` leaks), assert the full `resolved_package.json` against a committed snapshot.
- **Schema:** promote the manifest from a raw dict (`assemble_package._build_manifest`) to a Pydantic **`ResolvedPackageManifest`** model; `assemble_package` validates-then-dumps (output bytes unchanged), giving the renderer a **versioned, explicit** contract (the existing `PACKAGE_SCHEMA_VERSION="1.0"` now means something).
> This pairs with the renderer's `package_loader`: the same shape it consumes is now the shape Layer 1 guarantees. **Added first** in the migration order so every later step renders against a locked target.

## 6. Tier 2 — Orchestration, typed seams, async `/render`, assets split

**6.1 Stage runner (`pipeline.py`).** A `Stage` `typing.Protocol` (typed input/output) + `run_render_pipeline(request, *, settings, http_client) -> ResolvedPackage` runner that sequences the stages over a small frozen context, wrapping each in **per-stage timing** (reuse the `_mark` idiom from `stages/onboard/pipeline.py`) + **one error policy**. Reject Hamilton/Prefect/Dagster (ADR §A). First move is mechanical: **extract the `/render` body out of the route** into this runner (pure move, same calls/order); the route just calls it and maps to the response.

**6.2 Typed seams.** Kill the raw dicts at boundaries (ADR §A): move `brand_axes` construction out of the route literal (`main.py:255-260`) into a small **axes resolver** helper; stop the mid-pipeline `.model_dump()` round-trips (thread typed objects, convert once at the assemble/response boundary); collapse the duplicated `_unpack_page` normalizers (`plan_layout.py:108`, `generate_assets.py:528`) into one shared typed helper. Keep the intentional dataclass-vs-Pydantic split (Pydantic for serialized contracts; dataclasses for in-memory heavy objects). Add **per-seam contract tests** (`test_pipeline.py`).

**6.3 Async `/render` (202 + background + webhook).** Mirror `/onboard` (ADR §B): add `RenderAccepted{status, job_id, record_id}`; keep **cheap Stage-1 validation synchronous** (return 422/200-error inline so "reject loud" stays immediate); background the expensive Stages 5/8 and deliver `RenderResponse` to a callback/env webhook via the existing `_deliver_result` shape + disk fallback; idempotent payload keyed on `record_id`. Stay on `BackgroundTasks` (no Redis/arq). ⚠️ **This is the ONE item that changes the external contract** — n8n must handle a 202+webhook for `/render` as it already does for `/onboard`. **Flagged for explicit go/defer** (§9): if n8n isn't ready, all of Tier 2 except this lands, and `/render` stays synchronous with no loss to the other tiers.

**6.4 Split `generate_assets.py` (822 → `stages/assets/`).** Pure move-refactor into `download.py` / `fal_client.py` / `prompts.py` / `inventory.py` (its docstring already names these 4 jobs). Update imports + test paths; behavior identical. This is also where Tier-1's fal cache/budget naturally live.

## 7. Tier 3 — Stage-6 retirement (land with renderer Plan B)

**Confirmed dead by consumer trace (ADR §E):** Stage-6 SVGs are generated → written to `components/` → indexed in the manifest, but **no rendered page consumes them** — every dedicated renderer pattern builds its visual from `page["data"]`; only `patterns/_generic.py:135` reads `page["components"]`, and `_generic` is never dispatched for the ST types Stage 6 targets. The committed apex package has **1** SVG (slot 16), and `st_06.py` ignores it. The prerequisite ("renderer owns charts first") is **already met**.

**Safe retirement sequence (output-preserving):**
1. Keep the manifest `components` **field** (renderer reads `page.get("components") or []` defensively) — decouples deletion from any renderer change.
2. Neutralize the producer: `components = {}` in the runner (formerly `main.py:236`). Re-run both suites + render apex; confirm the PDF is byte-stable for slot 16 (it builds from `data`).
3. After it's observed stable, **delete** `stages/generate_components.py` (1,580) + `tests/test_generate_components.py` (403) + the imports in the runner and `fixtures/apex/build_package.py`.
4. (Later) strip the now-vestigial `components` plumbing from `plan_layout`/`assemble_package` + the one SVG-content test.

Removes ~1,980 lines of source+test and the entire stale-**Inter**-font-width liability. **Sequencing:** spec'd now, **executed alongside renderer Plan B** so the "renderer builds all charts from data" story is proven end-to-end in one pass.

## 8. Migration path (incremental, both suites green at each step)

1. **Contract net first:** add `test_resolved_package_contract.py` golden-file + introduce `ResolvedPackageManifest` (validate-then-dump; bytes unchanged). *Safety net for everything after.* [Tier 1.5]
2. `config.py` + `Settings` DI; replace `os.getenv` in the routes. Stages untouched. [Tier 0]
3. `lifespan` + pooled httpx client; thread via `http_client=`. [Tier 0]
4. `logging_setup.py` + job-id; kill the 2 silent excepts; log failure sites (returns unchanged). [Tier 0]
5. `_resilience.py` (stamina); route all external calls through it (unify backoff + jitter + `Retry-After`). [Tier 1]
6. fal content-addressed cache + budget guard (+ new tests; high default so fixtures don't trip). [Tier 1]
7. `errors.py` taxonomy + `add_exception_handler` (so `/render` never bare-500s) + error-path test. [Tier 0/1 bridge]
8. Extract `run_render_pipeline` (pure move) + `Stage` Protocol + runner + per-stage timing. [Tier 2]
9. Tighten seams (axes resolver out of route; drop `.model_dump()` round-trips; one `_unpack_page`) + per-seam contract tests. [Tier 2]
10. Split `generate_assets.py` → `stages/assets/`; (optional) switch fal to queue+`request_id`. [Tier 1/2]
11. Async `/render` (202+webhook) — **flagged contract change**; update endpoint test. [Tier 2]
12. **(with Plan B)** Stage-6: neutralize → observe stable → delete module+test+imports → strip vestigial plumbing. [Tier 3]

Each step is independently shippable and revertible; the 221 tests stay green and new tests accumulate.

## 9. Scope boundaries

**In:** typed `Settings`/secrets; pooled client + `lifespan` + DI; structured logging + job-id; error taxonomy + handlers; `stamina` retry policy; fal idempotency cache + budget guard + graceful-degradation formalization; golden-file + `ResolvedPackageManifest` contract test; `Stage` runner + typed seams; `generate_assets` split; async `/render`; Stage-6 retirement (with Plan B).
**Out (separate cycles, with rationale):** Google Drive retrieval build (post-OAuth — already designed in the renderer spec §10); **arq/Redis** job queue (only if durable retries / status endpoint / concurrency later force it — `BackgroundTasks` + disk-fallback + idempotent `record_id` suffices now); **OpenTelemetry** tracing (2-line upgrade once a backend is justified by volume); fal **queue** switch may be deferred behind a flag (cache covers re-runs); `validate_cover` matrix split (optional, low priority); **key rotation** (ops, not code — prior decision "unnecessary"; re-confirm, it's a config-only swap once Settings lands).
**Conditional:** async `/render` (§6.3) requires n8n to accept 202+webhook for `/render` — **go/defer is a user decision**; deferring it costs nothing else in Tier 2.

## 10. Success criteria

- **Behavior unchanged:** `resolved_package.json` is byte-identical for the sample fixture (golden-file passes); all 221 tests green + the new test files added.
- **Config:** zero `os.getenv` outside `config.py`; secrets are `SecretStr` (never logged); `.env` loads in-process (tests included).
- **Observability:** every request/job carries a correlation id; zero silent `except: pass`; failures are logged with context.
- **Resilience:** one retry policy across all externals (exp backoff + jitter + `Retry-After`); **fal never re-pays on retry/re-run**; the budget guard caps spend; a single failed asset degrades to a stub + warning and never kills the run.
- **Contracts:** `resolved_package.json` validates against `ResolvedPackageManifest` and is versioned; per-seam contract tests green; the `/render` body is a testable function independent of FastAPI.
- **Brand-agnostic:** `test_no_client_name_in_logic` green; no client specifics in any new module.
- **Right-sized:** no Redis/queue/broker, no circuit breaker, no tracing backend added.

## 11. Self-review notes

- **Placeholders:** none — each tier names concrete files, libraries, and interfaces.
- **Consistency:** every tier is output-preserving and rides the contract net added in step 1; the runner mirrors the existing `onboard/pipeline.py`; Settings/DI thread uniformly; the manifest model is the single seam authority shared with the renderer's `package_loader`.
- **Scope:** one subsystem (Layer 1 infrastructure); behavior frozen; Drive/queue/tracing/rotation explicitly deferred; async `/render` flagged as the only external-contract change with a clean defer option.
- **Brand-agnosticism:** new modules are pure infrastructure (no design/brand decisions); the guard test stays green; this work does not touch the grammar=rules / data=values separation.
- **Ambiguity check:** the one genuine fork (async `/render`) is called out as a user go/defer decision rather than silently assumed.
