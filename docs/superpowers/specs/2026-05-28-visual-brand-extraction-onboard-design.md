# Visual Brand Extraction (`/onboard` Mode 1) — Design / PRD

**Status:** Approved — ready for implementation planning
**Date:** 2026-05-28
**Owner:** Utkarsh
**Component:** `research/preprocessor/` (Layer 1 pre-processor) — Mode 1 (`/onboard`)
**Depends on:** grammar `richard-grammar-v2.md` §4 (Layer-B Brand Profile Schema)

---

## 1. Goal

Replace the current text-LLM scraper (which reads raw HTML/markdown and guesses
4 flat hex values) with a pipeline that **sees the client's website like an
expert designer** and produces a structured, *brand-accurate* Layer-B profile
that the renderer already knows how to consume.

One sentence: **`/onboard` takes a website URL and returns a `BrandProfile`
(the §4.0 brand-identity subset) with exact, measured colors and resolved
fonts — never guessed values.**

---

## 2. Why the current approach fails (and the core fix)

The current scraper asks **one wrong tool** (a text LLM) to do everything:

1. A text LLM cannot *perceive* design — it reads CSS strings, it can't see a render.
2. Raw HTML carries hundreds of hex values (cookie banners, third-party widgets,
   framework defaults) — no way to tell brand from noise.
3. `font-family` stacks list *fallbacks*, not what actually renders.
4. Texture / icon style / composition are invisible to text parsing.

**The fix is NOT "swap in a vision LLM to do everything."** Vision LLMs have a
documented weakness that is exactly what we care about: they are unreliable at
*exact values* (hex codes, precise font names). They are excellent at
*perception and judgment*.

**Core principle — the designer's eye + the eyedropper:**
A human designer also can't name a hex by eye; they use the eyedropper tool. So
we give the system both halves of the workflow:

- **The eye** (vision model): identifies which color is the brand primary vs.
  accent, the visual style, the type character — the *judgment*.
- **The eyedropper** (pixel sampling) + **the DOM** (`getComputedStyle`):
  supply the *exact* measured values.

The model **aims**; measurement **supplies the value**. The stored value is
always a real measured color, so the client's teal is *their* teal, not a
generic "turquoise."

---

## 3. Architecture principle: the contract chain (no open loops)

Every stage's **output is the next stage's typed input**. No stage reaches into
global state; each consumes only the previous stage's contract (plus the
original request where needed). This makes each stage independently testable
(feed it a fixture of the previous stage's output) and guarantees there are no
dangling outputs (something nothing consumes) or dangling inputs (something
nothing produces).

### 3.1 The broader system loop

```
[Airtable: new client row created]
   │  (n8n trigger)
   ▼
POST /onboard ──► OnboardRequest { record_id, website_url, flat_hex_fallback?, callback_url? }
   │
   │  202 Accepted { job_id, record_id }     ← returns immediately
   ▼
[5-layer visual pipeline runs in background]
   │
   ▼
POST callback_url (report-generator webhook) ──► OnboardResult { brand_profile, confidence, provenance, needs_review }
   │
   ▼
[n8n writes brand_profile → Airtable client record]   ← handled by n8n (Zimmermann)
   ⋮  (later, at report-production time)
POST /render ──► RenderRequest { client:{ …, brand_profile }, report_json, image_manifest }
   │
   ▼
[Stages 1–8 consume brand_profile]  ──►  resolved_package.json  ──►  renderer (Layer 2)
```

### 3.2 The two loop-closures that already exist

`/onboard`'s output plugs into seams the codebase **already has** — we are not
inventing downstream consumers:

1. **`brand_profile` is already an accepted input.** `ClientInput.brand_profile`
   exists today, and `validate_input._resolve_brand_tokens()` already *prefers*
   it over the flat hexes (precedence: profile → flat hex → default). Onboard's
   output therefore has a defined consumer now.
2. **Fonts already have a resolver.** `font_head` / `font_body` feed Stage 2
   `resolve_fonts()`, which already maps known → chassis-default and unknown →
   `customer_upload_needed`. Onboard produces the name; the existing stage
   classifies it.

The only downstream model change is **extending** `BrandProfile` with optional
fields — backward-compatible; Stage 1 keeps working unchanged.

### 3.3 The internal pipeline chain (inside `/onboard`)

| # | Stage (`stages/onboard/…`) | Input (= prev output) | Output contract |
|---|---|---|---|
| 0 | `capture.py` | `OnboardRequest` | `CaptureResult{ hero_png, fullpage_png, raw_dom_eval, status, notes }` |
| 1 | `dom_extract.py` | `CaptureResult.raw_dom_eval` | `DomSignals{ css_color_vars, font_head, font_body, sampled_colors, logo_url? }` |
| 2 | `pixel_palette.py` | `CaptureResult` (hero_png) | `PixelPalette{ colors:[{hex, coverage_pct, region}], lightest_idx, darkest_idx }` |
| 3 | `vision_reading.py` | `hero_png + fullpage_png + PixelPalette + DomSignals` | `VisionReading{ role_refs, axes, confidence, notes } \| None` |
| 4 | `reconcile.py` | `DomSignals + PixelPalette + VisionReading + OnboardRequest` | `OnboardResult{ brand_profile, field_confidence, provenance, needs_review, review_reasons }` |

Orchestrated by `pipeline.py :: async run_onboard_pipeline(req) -> OnboardResult`.

### 3.4 The rule that makes the chain airtight (anti-hallucination)

**Layer 3 (the vision model) never emits a hex.** It emits **references into
Layer 2's measured palette** (`primary → palette index`, `accent → palette
index`, …) plus the perceptual axis labels. Layer 4 dereferences those indices
into the real measured hex.

The contract literally cannot carry an invented color, because the only colors
that exist are the ones the eyedropper measured. An out-of-range index is
rejected in validation and treated as a "vision miss" (fall to heuristic).

---

## 4. Endpoint & payload contracts

### 4.1 `/onboard` is asynchronous

The job is 15–40s (Playwright navigation + screenshots + a vision call).
Synchronous handling would risk n8n HTTP timeouts. So:

- `POST /onboard` validates the request, starts the pipeline as a FastAPI
  **BackgroundTask**, and returns `202 Accepted { status, job_id, record_id }`
  immediately.
- When the pipeline finishes, the background task **POSTs `OnboardResult`** to
  `callback_url` (default = env `REPORT_GENERATOR_WEBHOOK`).
- Webhook POST has 2 retries; on final failure the result is **persisted to
  disk** (so it is never lost) and logged.

### 4.2 Request / response models

```python
# models_onboard.py

class FlatHexFallback(BaseModel):
    dark: str
    light: str
    accent: str

class OnboardRequest(BaseModel):
    record_id: str
    website_url: str
    # OPTIONAL — onboard REPLACES the text scraper that used to produce these,
    # so at onboard-time they may not exist yet. Fallback chain degrades past
    # them to chassis defaults + needs_review.
    flat_hex_fallback: Optional[FlatHexFallback] = None
    callback_url: Optional[str] = None   # default: env REPORT_GENERATOR_WEBHOOK

class OnboardAccepted(BaseModel):
    status: str = "accepted"
    job_id: str
    record_id: str

class OnboardResult(BaseModel):
    record_id: str
    job_id: str
    status: str                       # "success" | "partial" | "failed"
    brand_profile: BrandProfile       # the clean §4.0 subset (Stage-1 ready)
    field_confidence: dict[str, float]
    provenance: dict[str, str]        # per-field source
    needs_review: bool
    review_reasons: list[str]
    diagnostics: OnboardDiagnostics

class OnboardDiagnostics(BaseModel):
    render_mode: str                  # "ok" | "spa_blank" | "timeout" | "nav_error"
    screenshots: list[str]            # relative paths
    timings_ms: dict[str, int]        # per-stage
    vision_model: Optional[str]
    palette_size: int
```

**Confidence / provenance / diagnostics live in `OnboardResult`, never inside
`BrandProfile`** — so `BrandProfile` stays the exact clean shape Stage 1
consumes. n8n writes the `brand_profile` block to Airtable and may store
`needs_review` / `field_confidence` in separate Airtable fields.

### 4.3 Internal contracts (pipeline-private)

```python
# models_onboard.py (continued)

class CaptureResult(BaseModel):
    hero_png: Optional[str]           # path; None if capture failed
    fullpage_png: Optional[str]
    raw_dom_eval: dict                # raw output of page.evaluate(); parsed by dom_extract
    status: str                       # "ok" | "spa_blank" | "timeout" | "nav_error"
    notes: list[str]

class DomSignals(BaseModel):
    css_color_vars: dict[str, str]    # {"--brand": "#1A2540", ...} (color-valued only)
    font_head: Optional[str]
    font_body: Optional[str]
    sampled_colors: list[str]         # computed colors weighted by area/position (hex)
    logo_url: Optional[str]

class PaletteColor(BaseModel):
    hex: str
    coverage_pct: float
    region: str                       # "hero" | "fullpage"

class PixelPalette(BaseModel):
    colors: list[PaletteColor]        # ranked by coverage
    lightest_idx: Optional[int]       # candidate background / neutral_light
    darkest_idx: Optional[int]        # candidate neutral_dark

class VisionRoleRefs(BaseModel):
    primary: Optional[int]            # index into PixelPalette.colors
    accent: Optional[int]
    neutral_dark: Optional[int]
    neutral_mid: Optional[int]
    neutral_light: Optional[int]

class VisionAxes(BaseModel):
    accent_mechanic: Optional[str]    # §4.0 M: "contrasting_hue" | "tonal_same_hue"
    ground_mode: Optional[str]        # §4.0 G
    texture: Optional[str]            # §4.0 X
    headline_type: Optional[str]      # §4.0 H: "serif" | "sans" | "sans_allcaps"

class VisionReading(BaseModel):
    role_refs: VisionRoleRefs
    axes: VisionAxes
    confidence: dict[str, float]      # per role + per axis (0.0–1.0)
    notes: Optional[str]
```

---

## 5. Output schema — the §4.0 brand-identity subset

`BrandProfile` is **extended** (every field optional → backward-compatible with
Stage 1, which reads each defensively). Colors + fonts are *consumed by the
renderer today*; the four perceptual axes are *captured for forward use*
(see Open Decision 8.1).

```python
# models.py — BrandProfile (extended)

class BrandProfile(BaseModel):
    model_config = ConfigDict(extra="allow")

    # — Consumed by renderer today (§4.0 P, A, neutrals) —
    brand_primary: Optional[str] = None
    brand_accent: Optional[str] = None
    brand_neutral_dark: Optional[str] = None
    brand_neutral_mid: Optional[str] = None
    brand_neutral_light: Optional[str] = None

    # — Fonts (§4.0 font_head, font_body) —
    font_head: Optional[str] = None
    font_body: Optional[str] = None

    # — NEW: captured-for-forward-use perceptual axes (not yet consumed) —
    accent_mechanic: Optional[str] = None   # §4.0 M
    ground_mode: Optional[str] = None       # §4.0 G
    texture: Optional[str] = None           # §4.0 X
    headline_type: Optional[str] = None     # §4.0 H
```

### 5.1 Field derivation map

| Field | §4.0 | Primary source | Fallback chain |
|---|---|---|---|
| `brand_primary` | P | vision `primary` → palette hex | darkest prominent pixel → `flat_hex.dark` → default + review |
| `brand_accent` | A | vision `accent` → palette hex | most-saturated high-coverage non-neutral → `flat_hex.accent` → default + review |
| `brand_neutral_light` | G | vision `neutral_light` → palette | lightest pixel (background) → `flat_hex.light` → default |
| `brand_neutral_dark` | (G) | vision `neutral_dark` → palette | darkest pixel → default const |
| `brand_neutral_mid` | — | vision `neutral_mid` → palette | midpoint(dark, light) → default const |
| `font_head` | font_head | DOM `h1` computed family | null → Stage 2 chassis default |
| `font_body` | font_body | DOM `body` computed family | null → Stage 2 chassis default |
| `accent_mechanic` | M | vision `M` | null |
| `ground_mode` | G | vision `G` | null |
| `texture` | X | vision `X` | null |
| `headline_type` | H | vision `H` | null |

### 5.2 Axes NOT in scope (report-design decisions, not website facts)

These §4.0 axes are **excluded** because a website does not contain them — they
are decisions about how to render the DMC report, and the renderer cannot
consume them yet (only 1 of 13 patterns is built): the accent **role-map**
(`cover/cta/icons/checks/stamp_outline…`), `HC` headline construction,
`S` spread-vs-single, `CG` case-study geometry, `N` belief-card treatment,
`RW` rating widget, `motif`. The §4.0 "reject-loud if any axis missing" rule
applies to a *full* Layer-B profile gate; it does **not** apply here because
`ClientInput.brand_profile` is an all-optional partial profile by design.

---

## 6. Error / gap handling (every failure mode is defined)

Onboard NEVER crashes and NEVER blocks — it degrades and flags, mirroring the
Stage 3 / Stage 4 "warn, never block" philosophy.

| Failure | Behavior |
|---|---|
| SPA renders blank / nav timeout | `render_mode = spa_blank/timeout`; skip pixel + vision; colors → flat-hex/default; `needs_review = true` |
| Cookie/consent wall not dismissed | proceed with whatever rendered; note in diagnostics |
| Empty palette (all-image hero) | colors → DOM tokens → flat-hex → default |
| Vision API error / timeout | `VisionReading = None`; reconcile uses pixel heuristics + flat-hex; `needs_review = true` |
| Vision returns out-of-range palette index | reject that ref; heuristic for that field |
| Font unrecognizable / icon-font / generic | `font_* = null` → Stage 2 chassis default |
| Webhook POST fails | retry ×2; then persist `OnboardResult` to disk + log |
| Critical-field confidence < threshold (0.6) | `needs_review = true` + reason string |
| Network/library exception anywhere | caught at `pipeline.py`; `status = failed`; partial result + flat-hex/default; webhook still fires |

`status` resolution: `success` (all critical fields from vision/pixel/DOM,
confidence ≥ threshold) · `partial` (some fallback used or review needed) ·
`failed` (capture produced nothing usable; pure flat-hex/default output).

---

## 7. Testing plan

Mirrors the existing per-stage test style. **No real network or browser in
tests** — everything mocked or fixture-driven.

| Test file | Coverage |
|---|---|
| `test_onboard_dom_extract.py` | pure `parse(raw_dom_eval)`; font normalization; color-var filtering; empty/missing inputs |
| `test_onboard_pixel_palette.py` | known-color PNG fixtures → asserted hex + coverage ranking; lightest/darkest detection; empty image |
| `test_onboard_vision_reading.py` | mock OpenRouter `httpx`; prompt assembly carries palette + fonts; strict-schema parse; **out-of-range index rejected**; None on API error |
| `test_onboard_reconcile.py` | pure; synthetic layer outputs → asserts resolution + provenance + every fallback branch + `needs_review` logic |
| `test_onboard_capture.py` | mock Playwright (or `file://` static fixture); status codes; cookie-dismiss heuristic; never raises |
| `test_onboard_pipeline.py` | layers wired with mocks → `OnboardResult`; fallback paths; determinism (identical inputs → identical output) |
| `test_onboard_endpoint.py` | TestClient → `202` + `job_id`; background invocation; webhook POST (mocked) + retry/persist on failure |
| `test_no_client_name_in_logic.py` | **extend** existing guard to scan `stages/onboard/` |

Determinism: vision call pinned `temperature = 0` + strict JSON schema; pixel +
DOM layers are deterministic by construction.

---

## 8. Resolved decisions

1. **Capture-for-forward-use axes (§5):** RESOLVED — **include** `accent_mechanic
   / ground_mode / texture / headline_type`. Zero extra cost (the vision call
   produces them anyway) and they are genuine brand-identity axes; storing them
   now closes a future loop when the renderer grows to consume them.
2. **OpenRouter model slug:** RESOLVED — verified live on OpenRouter:
   **`anthropic/claude-sonnet-4.6`** (vision/multimodal capable; 1M context;
   $3 / $15 per M tok). Held in env `OPENROUTER_VISION_MODEL` (default = this
   slug) so swapping is one line. Dated pin `anthropic/claude-4.6-sonnet-20260217`
   and floating `anthropic/claude-sonnet-latest` also exist if we later want to
   pin or float.
3. **Disk persistence on webhook failure:** RESOLVED — write `OnboardResult` JSON
   under `ONBOARD_OUTPUT_DIR` if set, else a
   `tempfile.mkdtemp(prefix="dmc_onboard_")` directory (mirrors the Stage 8
   pattern). The path is logged.

---

## 9. Dependencies, env, ops

**New Python deps:** `playwright` (+ `playwright install chromium` baked into the
Railway image — heavier image + more memory; budget for it), `Pillow`
(pixel quantization). OpenRouter uses existing `httpx`.

**New env vars:** `OPENROUTER_API_KEY` (secret — runtime only, never committed
or hardcoded), `OPENROUTER_VISION_MODEL` (default `anthropic/claude-sonnet-4.6`),
`REPORT_GENERATOR_WEBHOOK`
(`https://n8n.zimmermannsysteme.de/webhook/report-generator`),
`ONBOARD_OUTPUT_DIR` (optional; webhook-failure persistence).

**Module layout:**
```
research/preprocessor/
  models.py                       # BrandProfile extended (optional fields)
  models_onboard.py               # NEW — all onboard contracts
  main.py                         # /onboard endpoint (202 + BackgroundTask)
  stages/onboard/
    __init__.py
    capture.py                    # Playwright session: screenshots + DOM eval
    dom_extract.py                # pure parse(raw_dom_eval) -> DomSignals
    pixel_palette.py              # Pillow quantize -> PixelPalette
    vision_reading.py             # OpenRouter Sonnet call -> VisionReading
    reconcile.py                  # pure -> OnboardResult
    pipeline.py                   # async orchestrator
  tests/
    test_onboard_*.py             # per above
```

---

## 10. Scope boundaries

**DO build:** the 5-layer `/onboard` pipeline, the extended `BrandProfile`, the
onboard contracts, the async endpoint + webhook handoff, the full test suite.

**DO NOT (this phase):** touch the renderer (`research/v7-renderer/`); make real
fal.ai calls; extract the report-design axes (role-map, HC, S, CG, N, RW,
motif); build the content/intelligence scraper (reviews, Northdata — that is the
separate `10_DMC_Scraping_Workflow` concern); write to Airtable directly (n8n
owns persistence via the webhook).

**Success =** `/onboard` returns `202`, runs the visual pipeline, POSTs a
`BrandProfile` with measured (never guessed) colors + resolved fonts +
confidence/provenance/needs_review to the webhook; all new tests pass; existing
135 pre-processor tests + 11 chassis tests stay green.
