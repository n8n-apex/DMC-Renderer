# DMC Renderer — Architecture

**Status:** Phase 2 — architecture lock. Phase 3 (templates) gated on review.
**Last update:** 2026-05-11. Authored after v6 visual approval.

---

## 1. What this service is (one paragraph)

The DMC Renderer is a stateless synchronous HTTP service that converts a
JSON payload (produced upstream by an n8n pipeline) into a print-ready A4
PDF report. One POST in, one binary PDF out. No queues, no callbacks, no
database. Same input bytes produce byte-identical PDF bytes — the renderer
is a pure function from payload to PDF. Caching, retries, and persistence
are upstream concerns handled by n8n.

---

## 2. System contract

| | |
|---|---|
| Endpoint | `POST /render` |
| Auth | `Authorization: Bearer ${RENDERER_SHARED_SECRET}` |
| Request media type | `application/json` |
| Request body | `{ payload, images, brand_tokens }` — see [API_CONTRACT.md](API_CONTRACT.md) |
| Response media type (success) | `application/pdf` |
| Response media type (failure) | `application/json` with `{ error, details, fixture_path? }` |
| Timeout | 120 s end-to-end (hard cap, enforced by the renderer) |
| Statelessness | No DB, no in-memory cache, no on-disk persistence across requests |
| Determinism | Same input → byte-identical PDF (modulo a fixed PDF creation timestamp seeded from `payload.meta.report_id`) |
| Concurrency | Single-threaded per request. Multiple gunicorn workers OK. |
| Health check | `GET /healthz` → `200 OK {"ok": true, "version": "..."}` |

A request never modifies anything outside `/tmp/render-{report_id}/`,
which is deleted at the end of the request. There is no `/data`, no
state directory, no logs persisted to disk (Railway captures stdout).

---

## 3. Request lifecycle

```
1. POST /render arrives
2. Validate Authorization → 401 if missing/wrong
3. Parse JSON → 400 if malformed
4. Validate payload shape against API_CONTRACT.md → 400 if invalid
5. mkdir /tmp/render-{report_id}/                      ← scratch
6. Fetch all images from payload.images into scratch   ← per-render fetch
7. Apply markdown preprocessor to body fields           ← preprocess.py
8. Compute page count from payload.pages[].page_numbers
9. Render Jinja → HTML+CSS → WeasyPrint → PDF bytes
10. Run CoralBudget validator on each rendered page    ← coral_validator
11. If any page > 2 coral fires: 422 with details      ← hard gate
12. Return PDF bytes with Content-Type: application/pdf
13. rm -rf /tmp/render-{report_id}/                     ← cleanup
```

Steps 6–9 must complete inside the 120 s budget. Typical observed render
time (Phase 1 contact-sheet prototype on Apple Silicon): ~12 s for a
20-page report. Headroom is generous.

---

## 4. Authentication

A single shared secret, validated on every request:

```python
expected = os.environ["RENDERER_SHARED_SECRET"]
header = request.headers.get("Authorization", "")
if header != f"Bearer {expected}":
    return 401, {"error": "unauthorized", "details": "invalid bearer token"}
```

The secret is set as a Railway environment variable and shared with the
n8n pipeline. No per-client tokens, no rotating keys, no IAM. If we ever
need multi-tenant auth, that's a separate phase.

**Operational note:** Railway secrets are encrypted at rest. The renderer
reads `os.environ` once at import time. Restart required after rotation.

---

## 5. Page count computation

The renderer is the source of truth for the total page count appearing in
each page's header strip (`S. N / TOTAL`). Upstream produces a *plan*; the
renderer produces the *fact*.

Algorithm:

```python
def total_pages(payload):
    total = 0
    for page in payload["pages"]:
        pn = page["page_numbers"]   # "1" or "2-3" or "16-17"
        if "-" in pn:
            lo, hi = map(int, pn.split("-"))
            total += hi - lo + 1
        else:
            total += 1
    return total
```

A `page_numbers` value of `"2-3"` means the template emits **two**
sequential A4 portrait pages and is responsible for choosing where the
break falls. A value of `"10"` is a single page.

### Defensive monotonic check

Chapter Plan Generator v2 emits sequential page_numbers with no
collisions, but the renderer still verifies monotonicity and warns on
overlap:

```python
def assert_monotonic(payload):
    last_hi = 0
    for page in payload["pages"]:
        pn = page["page_numbers"]
        lo, hi = (int(x) for x in (pn.split("-") if "-" in pn else (pn, pn)))
        if lo <= last_hi:
            warnings.warn(f"page_numbers collision at slot {page['slot']}: {pn} <= prev {last_hi}")
        last_hi = hi
```

Warnings go to stdout (captured by Railway). The renderer does NOT abort
on collision — it renders what it was given. The warning is a tripwire
for upstream debugging.

---

## 6. Markdown preprocessing

Writer output contains `**bold**` and `*italic*` markdown markers in body
fields. The renderer converts these to `<strong>` and `<em>` HTML tags
before the Jinja pass.

Lives at `dmc-renderer/preprocess.py`. Conversion rules:

| Markdown | HTML |
|---|---|
| `**text**` | `<strong>text</strong>` |
| `*text*` | `<em>text</em>` |
| `\n\n` (double newline) | `</p><p>` (paragraph break) |
| `\n` (single newline) | `<br/>` |

**Fields preprocessed** (per [API_CONTRACT.md](API_CONTRACT.md) — only
prose fields, never labels or short strings):

| ST type | Fields |
|---|---|
| ST-01 | `intro_body` |
| ST-02 | `body` |
| ST-03 | `body` |
| ST-05 | `body` |
| ST-06 | `mechanism_description`, `steps[].description`, `closing_redirect` |
| ST-07A | `kurzportraet`, `ausgangsproblem`, `wendepunkt`, `loesung`, `ergebnis_text`, `pullquote.text` |
| ST-07B | `body`, `key_insight` |
| ST-09 | `body`, `symptoms[].description`, `closing` |
| ST-14 | `intro`, `beliefs[].body` |
| ST-22 | `intro`, `steps[].description` |
| ST-FAZIT | `body`, `bold_thesis`, `cost_of_inaction`, `closing_question` |

Labels, headlines, values, durations, button text are **not**
preprocessed — they're short structured strings, never marked-up prose.

The preprocessor is a strict regex pass; nested markdown is not
supported. `***text***` does NOT produce nested `<strong><em>`. If Writer
emits nested markers, the closing emphasis defers to the outermost
opening.

---

## 7. Coral budget validator

Ported from `research/decoration-samples/_build/coral_validator.py` to
`dmc-renderer/validators/coral.py`. Two checks run on every render:

1. **Source mode** (cheap, in-process): scan the final rendered HTML for
   hex colors within ΔE76 < 10 of `brand_accent`. Flag any color other
   than the literal accent itself. Fail-soft (warning), since CSS-level
   near-coral is usually intentional brand variation.

2. **Raster mode** (authoritative, runs on rendered PNG of each page):
   downsample to 800 px max edge, scan all pixels, find connected regions
   of coral, count regions with ≥ 50 pixels. **If any page has > 2 coral
   fires, return HTTP 422.**

The rasterization for validation re-uses the WeasyPrint render — no
double render. We use `weasyprint.HTML.write_pdf()` to produce the PDF,
then `fitz.open(pdf_bytes).get_pixmap(...)` to rasterize each page at a
2.0× matrix (~144 dpi — sufficient for color detection, cheap on time).

422 response body:

```json
{
  "error": "coral_budget_exceeded",
  "details": "page 3 (slot 8, type ST-07A): 4 coral fires detected — max 2",
  "fixture_path": "payload.pages[7]",
  "fires": [
    {"page": 3, "bbox": [264,609,13,17], "pixels": 112},
    {"page": 3, "bbox": [278,609,14,17], "pixels": 134},
    {"page": 3, "bbox": [340,720,18,20], "pixels": 160},
    {"page": 3, "bbox": [120,820,80,12], "pixels": 320}
  ]
}
```

**Cover (ST-01) and CTA (ST-03)** pages have a slightly higher budget
(3 fires) since their layout legitimately uses coral in the headline and
button. Encoded in `validators/coral.py`:

```python
CORAL_BUDGET = {"ST-01": 3, "ST-03": 3, "_default": 2}
```

This is a hard gate. The renderer will not return a PDF that violates
coral discipline. Upstream catches the 422 and either re-prompts Writer
or surfaces the failure to the operator.

---

## 8. Error responses

All errors return JSON with `Content-Type: application/json`.

| Code | Meaning | Example |
|---|---|---|
| **400** | Malformed payload — missing required field, bad JSON, invalid ST type | `{"error":"missing_field","details":"payload.pages[2].data.headline is required for ST-09","fixture_path":"payload.pages[2]"}` |
| **401** | Missing or wrong `Authorization` header | `{"error":"unauthorized","details":"bearer token mismatch"}` |
| **422** | Render succeeded but failed post-validation (coral budget, page count overrun, font load failure) | `{"error":"coral_budget_exceeded","details":"page 3: 4 fires","fires":[...]}` |
| **500** | Internal renderer error (WeasyPrint exception, font missing, OOM, image fetch failure) | `{"error":"render_failed","details":"WeasyPrint: 'Source Serif 4' not found","traceback_id":"abc123"}` |

`traceback_id` for 500s correlates with the stdout traceback Railway
captures — n8n logs the id and the operator looks it up.

The renderer NEVER returns 200 with a non-PDF body, and NEVER returns a
PDF with a 4xx/5xx code.

---

## 9. Image fetching

See [CACHE_STRATEGY.md](CACHE_STRATEGY.md). One-line summary: every render
fetches every image from `payload.images` to `/tmp/render-{report_id}/`,
references local paths in CSS, cleans up at end of render. No cache.

Drive URLs in the images map are publicly accessible — verified upstream.
The renderer uses `urllib.request.urlopen` with a 30 s per-image timeout.
If any image fails to fetch, return 500 with `details` naming the failed
URL. (We don't downgrade to a placeholder — the operator decides whether
to re-run.)

---

## 10. Font loading

See [FONT_LOADING.md](FONT_LOADING.md). Fonts bundled in the Docker
image at `/app/fonts/`. `@font-face` declarations reference
`file:///app/fonts/...` URLs. No network at render time.

Faces loaded:

- **Inter** 400, 700, 800, 900 (sans, headlines)
- **Source Serif 4** 400 normal, 400 italic, 700 bold (serif, body)
- **Vollkorn** 700 (display serif, Apex-specific override)

**v6.1 fix landed:** `Source Serif 4` weight 700 now resolves to the real
SourceSerif4-Bold.ttf binary (not Regular.ttf as in v5/v6). Body
`<strong>` renders as same-family serif bold — matches reference reports'
typographic discipline.

---

## 11. Brand tokens

See [BRAND_TOKENS.md](BRAND_TOKENS.md). n8n sends `brand_tokens` as a
top-level merge object. Renderer merges into a Jinja context. Templates
emit CSS custom properties (`--brand-accent: ...;`). Missing keys fall
back to defaults in `dmc-renderer/templates/base.css.j2`.

---

## 12. Determinism

PDF bytes must be reproducible: re-rendering the same payload at a later
time yields the same bytes. This matters for:

- n8n cache key generation (hash of PDF → asset id)
- Operator audit trail
- Regression testing across renderer versions

Sources of nondeterminism the renderer must control:

| Source | Strategy |
|---|---|
| PDF creation timestamp | Seed from `payload.meta.report_id` (a deterministic string) — pass `--info-create-date` to WeasyPrint or post-process the trailer dictionary |
| QR code rendering | Same payload data + same `box_size` + same `error_correction` → same matrix. Verified. |
| Image fetch order | Iterate `payload.images` keys in declared order, not dict-iter order (Python 3.7+ preserves declaration order — safe). |
| Floating point in layout | WeasyPrint uses fixed-point internally; deterministic for same input. |
| Font subsetting | Set `WEASYPRINT_FONT_SUBSET=embed-all` or accept that subsets differ; subset bytes differ but visible output is identical. We accept subset variation for now. |

Determinism is "byte-identical PDF bytes" except for the font subset
section, which can vary by a few bytes between renders. n8n's cache hash
should hash the rendered PNG of page 1, not the PDF bytes, to absorb
subset noise.

---

## 13. Phase 3 preview (template plan — not implemented yet)

This section documents the *plan*; no template code lives in the repo
until Phase 3 is green-lit.

```
dmc-renderer/
  ├── docs/
  │   ├── ARCHITECTURE.md         ← this file
  │   ├── API_CONTRACT.md
  │   ├── BRAND_TOKENS.md
  │   ├── FONT_LOADING.md
  │   └── CACHE_STRATEGY.md
  ├── fixtures/
  │   └── apex_consulting_payload.json   ← canonical reference fixture
  ├── fonts/                       ← bundled (FONT_LOADING.md)
  │   ├── Inter-{400,700,800,900}.ttf
  │   ├── SourceSerif4-{Regular,Italic,Bold}.ttf
  │   └── Vollkorn-Bold.ttf
  ├── app.py                       ← Flask/FastAPI entrypoint
  ├── render.py                    ← payload → pdf core
  ├── preprocess.py                ← markdown → HTML
  ├── pagecount.py                 ← total_pages, assert_monotonic
  ├── images.py                    ← per-render fetch
  ├── validators/
  │   └── coral.py                 ← port of _build/coral_validator.py
  ├── templates/
  │   ├── base.html.j2             ← shared header strip, fonts, body wrapper
  │   ├── base.css.j2              ← CSS custom properties from brand_tokens
  │   ├── components/
  │   │   ├── stat_block.html.j2
  │   │   ├── pullquote.html.j2
  │   │   ├── qr_block.html.j2
  │   │   ├── initials_block.html.j2
  │   │   ├── sidebar_panel.html.j2
  │   │   ├── footer_cta_band.html.j2
  │   │   ├── process_flow.html.j2
  │   │   ├── matrix_2x2.html.j2
  │   │   ├── causality_chain.html.j2
  │   │   ├── metaphor_split.html.j2
  │   │   ├── bar_chart.html.j2
  │   │   ├── line_chart.html.j2
  │   │   └── compare_table.html.j2
  │   ├── st-01.html.j2            ← Cover
  │   ├── st-02.html.j2            ← Outlook
  │   ├── st-03.html.j2            ← CTA
  │   ├── st-05.html.j2            ← About
  │   ├── st-06.html.j2            ← Mechanism
  │   ├── st-07a.html.j2           ← Case Study
  │   ├── st-07b.html.j2           ← Theory
  │   ├── st-09.html.j2            ← Status Quo
  │   ├── st-14.html.j2            ← False Beliefs
  │   ├── st-22.html.j2            ← Collaboration / Process
  │   └── st-fazit.html.j2         ← Summary
  ├── tests/
  │   ├── test_pagecount.py
  │   ├── test_preprocess.py
  │   ├── test_coral.py
  │   └── test_render_apex.py      ← end-to-end: render apex fixture, assert no validation failures
  ├── Dockerfile
  ├── requirements.txt
  ├── railway.json
  └── README.md
```

### Phase 3 build order

The first templates we build are the structural anchors. Once those work,
the rest follow the same pattern with content variation.

1. **ST-01** — Cover. Simplest page, validates fonts + brand tokens + image fetch.
2. **ST-FAZIT** — Summary. Validates the markdown preprocessor on long body fields.
3. **ST-05** — About. Validates the credibility_points stat-grid pattern.
4. **ST-09** — Status Quo. Validates the symptoms list (6 cards) + 2-page spread handling.
5. **ST-14** — False Beliefs. Validates the beliefs[] iteration.
6. **ST-07A** — Case Study. Most complex single-page template (sidebar + main + stats + QR). v6 prototype already in research/.
7. **ST-07B** — Theory. Companion to ST-07A; reuses sidebar pattern.
8. **ST-02** — Outlook. Two-page spread.
9. **ST-06** — Mechanism. Process_flow component lives here.
10. **ST-22** — Collaboration. Steps timeline.
11. **ST-03** — CTA. Closing page; partial coral budget exception.

End-to-end test (`test_render_apex.py`) loads the canonical Apex fixture
and asserts the full 20-page PDF renders without any validator failures.

---

## 14. Async, queues, retries — deferred

Phase 1 locked Option 6 (deferred async). The renderer is synchronous,
single-attempt, 120 s. If a render fails, n8n decides whether to retry.
We have not built and will not build:

- Job queue (no Redis / Celery)
- Webhook callbacks
- Multi-step rendering with intermediate persistence
- Progress streaming

When a Phase 1.1 use-case forces it (e.g. interactive previews, partial
results, multi-minute renders), we add an `/enqueue` + `/job/{id}`
surface alongside (not instead of) `/render`. Not now.

---

## 15. Logging & observability

The renderer logs to stdout, Railway captures. One log line per request,
JSON:

```json
{
  "ts": "2026-05-11T17:34:01Z",
  "method": "POST", "path": "/render",
  "status": 200, "duration_ms": 11842,
  "report_id": "CL-20260508-092136-MCE",
  "client_slug": "jousef",
  "page_count": 20,
  "pdf_bytes": 487213,
  "coral_fires_per_page": [1, 0, 2, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 0, 0, 2, 2]
}
```

Errors log an additional line with traceback_id, traceback, and the
fixture_path that triggered the failure.

No external APM (Datadog/Sentry) in Phase 2. Railway logs + n8n's
operator surface are the entire observability story.

---

## 16. Versioning

`GET /healthz` returns `{"ok": true, "version": "..."}` where version is
the git commit SHA at image build time, baked into the Docker image via
`ARG GIT_SHA`. The PDF response includes `X-Renderer-Version: <sha>` so
n8n can correlate rendered PDFs with the renderer that produced them.

Breaking API changes (e.g. new required fields in payload) bump a separate
`X-Api-Version: v1` header. v1 is the only version for the foreseeable
future. When we need v2, we add `/v2/render` alongside `/render`.

---

## 17. Open questions for Phase 3 review

These are flagged for your call before Phase 3 starts:

- **Single-render vs spread**: when `page_numbers` is `"2-3"`, the
  template decides where the break falls. Should we expose a
  `prefer_break_after: "ledе" | "headline" | "auto"` knob in `data`, or
  hard-code per ST template? Recommendation: hard-code, surface only if a
  client report needs it.
- **Web fonts fallback**: if a brand_token sends `font_heading: "Custom Brand Sans"` that we don't have bundled, do we 404 or fall back to Inter? Recommendation: fall back to the template default with a warning logged. Brand-mismatched fonts in n8n are an operator issue, not a render failure.
- **PDF/A compliance**: not requested. Mention here in case it becomes a compliance requirement for clients in regulated industries.
- **Right-to-left languages**: not in scope; all current ST templates assume LTR. When needed, a separate phase.

---

## Appendix: file path conventions

| Path | Purpose |
|---|---|
| `/tmp/render-{report_id}/` | Scratch directory for one request. Deleted at end. |
| `/app/fonts/` | Bundled fonts (read-only, baked into image) |
| `/app/templates/` | Bundled Jinja templates |
| `/app/fixtures/` | Bundled reference fixtures (used by tests, not by production) |

The renderer never writes outside `/tmp/render-{report_id}/`. The image
filesystem can be mounted read-only at runtime.
