# Pre-Processor (Layer 1) — Product Requirements Document (PRD)

**Status:** Authoritative — the SINGLE SOURCE OF TRUTH for the pre-processor. All development adheres to this.
**Date:** 2026-05-30
**Component:** `research/preprocessor/` (Layer 1 of the DMC report pipeline)
**Consolidates / references (read these):**
- **The WHAT (design requirements):** `2026-05-30-richard-design-dna.md` — the 6-deck visual schema; **§F** is the pre-processor responsibility map; **§B** the per-client axes; **§C2/C4/C5** the photo/social-proof/chart systems; **§D** the per-page recipes.
- **The robustness foundation (build on, now expanded):** `2026-05-30-preprocessor-architecture-research.md` (ADR) + `2026-05-30-preprocessor-architecture-migration-design.md` (migration spec). *This PRD SUPERSEDES their "output-preserving" success criterion (see §11) — post-DNA, the package MUST change.*
- **The downstream contract:** the renderer consumes `resolved_package.json`; field names here codify what the renderer patterns already read.
- **The architecture research feeding this PRD:** 4 parallel opus agents (asset-sourcing+mapping · AI-generation+compositing · content→structured-data · package-contract+axes+integration), 2026-05-30, code-grounded + web-cited; their findings are folded in below.
- **The closed-loop consumer (NEW, 2026-06-03):** `2026-06-03-self-correcting-quality-architecture-design.md` — the package (`ResolvedPackageManifest` v2.0) is the *fix surface* a perception/scoring loop edits per page until each clears a reference-grounded quality bar. The pre-processor is one of the knob-owners the conductor routes fixes to.

---

## 1. Purpose & framing

The pre-processor turns a client's **content (`report_json`) + brand + a Google-Drive asset folder** into a **`resolved_package.json` (v2.0)** that lets the WeasyPrint renderer produce a PDF **as personalized and visually rich as the agency's real client decks**. The DNA analysis proved the current pipeline is under-scoped: it must now reliably **source, generate, map, and structure** a much larger set of assets + data, and do so **deterministically — accurately every time**.

**This is NOT only a robustness rework.** It is a *functional expansion* (the asset/data schema that decides PDF quality) **on top of** the robustness foundation (config, resilience, observability, the Stage runner) from the ADR + migration spec.

## 2. Cardinal principles (non-negotiable, every requirement obeys these)

1. **Brand-agnostic.** No client name/hex/font literal in LOGIC. Per-client = DATA (Drive contents, brand tokens, §B axes, content). The slot registry names slot *kinds* + convention *keys*, never a client. Guard test `test_no_client_name_in_logic` extended to every new module. *(This is the rule that nearly killed the project — see the DNA + context.md.)*
2. **Deterministic — "accurate every time."** Same inputs (Drive folder + content + brand) → same package. Achieved by: pure resolvers (no clock/network in logic), convention-first sorted matching, and **content-addressed caching** for the only nondeterministic actor (fal generation). The golden-file contract test (§10) locks it.
3. **Never silently fail / never a blank box.** Missing-but-required asset → a structured, named `missing_required` error (so Richard knows the exact file to add) — never a fabricated person, never an empty frame. Everything else degrades to a warning; the package always assembles. (Owner decision: **a missing client photo is Richard's to handle via Drive.**)
4. **No regression.** The existing logic is correct + tested (**221 tests**). New work is additive behind the golden-file net; the 221 stay green; new stages get new test files.
5. **Right-sized (YAGNI).** Low-volume internal tool for one agency. Stay Python/FastAPI/Pydantic v2/httpx/Pillow. Reject heavyweight orchestration/queues/brokers. Small, well-chosen libs only (`pydantic-settings`, `stamina`, `structlog`, `rapidfuzz`, `google-api-python-client`).
6. **Typed seams.** Everything serialized to `resolved_package.json` is Pydantic-validated; heavy in-memory carriers may stay dataclasses. The package is a versioned contract.

## 3. Functional requirements (WHAT the pre-processor must produce — from DNA §F)

For each page-type recipe (DNA §D), the package must carry the right **assets + structured data + axes**:

**3.1 Imagery (sourced — from the client's Drive folder, by naming convention):**
- **Founder photo** → cover hero / about. **Team photo** → about.
- **Named client photo on EVERY case study** (one per Fallstudie). **Never a blank box.**
- **Press logos** ("Bekannt aus") + **client logos** (logo wall) → grayscale-ready.
- (Owner decision) missing required client/founder/team photo = **fail loud + flag** (Richard fixes in Drive); the system NEVER fabricates a person.

**3.2 Imagery (generated/composited — synthetic, brand-driven):**
- **Device/product mockups** — composite the client's real ad-creative/dashboard/book into a device frame (Pillow; deterministic).
- **Per-client texture/atmosphere** images (frosted-glass / parchment / paper-grain / darkened-scene), driven by the `texture` axis + brand brief (fal; cached).
- **Scene/atmospheric** backdrops where no real photo exists.

**3.3 Social-proof DATA (validated config/content — NEVER LLM-synthesized):**
- **Rating cards** (platform + score + count + verified) · **review cards** (name, role, stars, text, date) · **press/client logo lists**.

**3.4 Rhetorical chart DATA (no axis chrome — the renderer draws):**
- before/after bars · line/curve compare · donut · 3D money infographic · cost-math strip · ✗/✓ comparison columns. *(The renderer draws; the pre-processor supplies the numbers.)*

**3.5 Per-page typed DATA** matching each DNA §D recipe (e.g. a case study's name/role/url + 3 stats + 4 sections + pull-quote + result box).

**3.6 Per-client AXES (DNA §B):** `headline_type`, `palette`, `accent_mechanic`, `texture`, `qr_enabled`, `density` — resolved, validated, threaded into the package.

**3.7 New page TYPES** (the package must support them): **Testimonials** + **Logo-wall** (+ the spread/left-right format the short decks use).

---

## 4. Architecture overview (HOW)

```
report_json + brand + Drive folder
        │
  [robustness substrate: Settings(DI) · pooled httpx · stamina · structlog+job-id · Stage runner]
        ▼
1 validate_input → 2 resolve_fonts → 2.5 resolve_axes
      │
   [3 validate_copy ‖ 3.5 copyfit ‖ 4 validate_cover]   (advisory, parallel)
      ▼
C  structure_content   → typed PageData + ChartSpec + SocialProof  (deterministic default; strict-LLM for interpretive only)
      ▼
A  map_asset_slots     → ResolvedSlot[] per page  (declarative recipe registry + pure resolver; Drive listing in)
      ▼
B  generate_assets     → Drive download · fal generate(cached,budgeted) · Pillow composite
      ▼
7  plan_layout         → recipe assignment + structural verify
      ▼
8  assemble_package    → validate-then-dump  ResolvedPackageManifest v2.0   ← golden-file contract test
```

**Stage order is data-driven** (Agent D): axes (2.5) precede A & B (both read `texture`/`qr_enabled`/`density`); **C precedes A** (slot mapping needs to know what content/charts exist); **A precedes B** (B generates only the slots A marked `generate`/`composite`). Validate the graph once at startup with stdlib `graphlib.TopologicalSorter` (right-sized; no workflow engine — ADR §A holds).

---

## 5. The package CONTRACT — `ResolvedPackageManifest` v2.0 (the Layer-1↔Layer-2 seam)

Promote the manifest dict → a versioned Pydantic model (`PACKAGE_SCHEMA_VERSION` **"1.0" → "2.0"**, additive major bump). `extra="forbid"` on manifest-level models (a renderer-relevant typo fails loudly); free-form allowed only on leaf `data` fallback.

```
ResolvedPackageManifest
  version: Literal["2.0"]; generated_at; record_id
  brand:         BrandTokens        # existing 10 flat fields (unchanged)
  axes:          ResolvedAxes       # §6 — 6 validated Literal fields
  fonts:         FontBlock          # unchanged
  report_assets: ReportAssets       # textures/atmospheric + press_logos[] + client_logos[] + ratings[]
  pages:         list[ResolvedPage]
  validation:    ValidationBlock    # copy/layout warnings, cover_overall (unchanged)
  asset_summary, asset_warnings     # (unchanged + new statuses)
  provenance:    ProvenanceBlock    # NEW — per-section source: onboard|input|default|content|fal|drive

ResolvedPage
  slot, st_type, css_template, has_cta, page_numbers, cover_validation   # unchanged routing
  recipe:  str                      # DNA §D recipe id ("cover","about","case_study","mechanism","data","testimonials","logo_wall",…)
  slots:   list[ResolvedSlot]       # §7 (Agent A)  — resolved asset→slot map
  data:    PageData                 # §8 (Agent C)  — discriminated union by st_type (+ generic fallback)
  charts:  list[ChartSpec]          # §8 (Agent C)  — rhetorical chart DATA
  social_proof: SocialProofBlock | None   # §8 (Agent C)
```

- **Discriminated unions** (`Field(discriminator="st_type")` / `discriminator="kind"`) for `PageData`, `ChartSpec`, `AssetSpec`, each paired with a **generic fallback variant** (`union_mode="left_to_right"`) so an unknown ST type degrades to a passthrough page (preserves today's never-block behavior + the 16-empty-page fixture).
- **Dataclass-vs-Pydantic split preserved** (ADR): heavy in-memory carriers (`LayoutPlan`, SVG strings) stay dataclasses; only what serializes is Pydantic.
- The renderer's `package_loader` is the paired consumer; the **golden-file contract test** (§10) freezes this v2.0 contract.

## 6. AXES resolution (Agent D) — new `stages/resolve_axes.py`

A pure `resolve_axes(client, brand_profile, report_meta) -> ResolvedAxes`. `ResolvedAxes` = Literal-typed, validated:
```
headline_type:   Literal["serif","sans","sans_allcaps"]
palette:         Literal["mono_tonal","dual_contrasting"]
accent_mechanic: Literal["tonal_same_hue","contrasting_hue"]
texture:         Literal["smooth","marble_paper","crumpled_paper","paper_grain","photo"]
qr_enabled:      bool
density:         Literal["airy","balanced","packed"]
```
**Precedence per axis (brand-agnostic — axes are DATA):** ① explicit `brand_profile.<axis>` (from `/onboard`); ② **derive from resolved brand tokens** where inferable (e.g. `palette`/`accent_mechanic` from the hue distance between `brand_primary` and `brand_accent` — one hue family → `mono_tonal`/`tonal_same_hue`, distant → `dual_contrasting`/`contrasting_hue`); ③ grammar default (`headline_type="serif"` per DNA §B 5:1; `qr_enabled=False`; `density="balanced"`). Each choice recorded in `provenance`. **Plumb `/onboard` VisionAxes through** — extend `BrandProfile` (`models.py:80-83`) + `models_onboard.VisionAxes` to also carry `palette`/`qr_enabled`/`density` (today captured partially, never modeled). Replaces the inline literal at `main.py:255-260`. Test: `test_resolve_axes.py` asserts every axis resolves to a valid Literal for the 6-deck profiles **as data fixtures** (not branches).

## 7. ASSET sourcing, slot MAPPING & validation (Agent A)

**7.1 Slot taxonomy + declarative registry** (replaces the flat `IMAGE_REQUIREMENTS` dict, `generate_assets.py:47-94`). Typed Pydantic, in-code (not YAML — self-validating, testable, satisfies the no-literal guard):
```
SlotSpec
  slot_kind:  Literal["founder_hero","client_portrait","team","press_logo","client_logo",
                      "scene","device_mockup","texture","gradient","logo"]
  cardinality: Literal["one","indexed","many"]    # client_portrait=indexed; press_logo=many
  source:      Literal["drive","manifest","generate","composite"]
  required:    bool
  aspect_ratio: str
  drive_key:   str | None        # naming-convention stem: "founder","case-study-{n}","press-logo-*"
PageTypeRecipe = { st_type: list[SlotSpec] }    # encodes DNA §D
```
Example bindings: ST-01→`founder_hero`(req)+`scene`; About→`team`(req)+`press_logo[]`+`client_logo[]`; **case_study→`client_portrait[n]`(req)**+`device_mockup`(opt); FAZIT→`scene`+small `founder_hero`; breathing/back-cover→`texture`. `client_portrait[n]` binds to the case-study ordinal so each Fallstudie gets its own portrait.

**7.2 Pure deterministic resolver** `resolve_slots(page_plan, drive_listing, manifest) -> list[ResolvedSlot]` (sync, no I/O → trivially testable): normalize every Drive filename once (lowercase, strip ext, `[_\s]→-`, collapse, drop n8n `image-<digits>` suffix) → **convention-first match in priority order** (exact `drive_key` → indexed `drive_key-{n}` → prefix/glob `press-logo-*` **sorted** for stable order → guarded `rapidfuzz` last-resort behind a confidence floor, recorded as `low_confidence` warning, never overriding an exact hit). Determinism: sorted ordering for `many`-slots (Drive `files.list` order is not stable).

**7.3 New asset statuses** (extend `AssetResult`): `resolved` (path set) · **`missing_required`** (no hit + required → structured error naming page+slot_kind+expected `drive_key`) · `absent` (optional miss, explicit flag → renderer reflows). The renderer NEVER gets a blank frame — every `pages[].assets[]` entry is a path or an explicit status. `source=="drive"` excludes `generate`, structurally forbidding a fal "fake person" for founder/client/team kinds. Update the count invariant (`total_required == resolved + generated + stubbed + missing_required + absent + failed`).

**7.4 Drive integration** — `stages/drive_client.py`, **user-OAuth2 + stored refresh token** (consumer Gmail, NOT a service account), `files.list(q="'<folderId>' in parents and trashed=false", fields=…, pageToken)` once per render → in-memory listing into the pure resolver; `files.get_media` streamed, reusing the existing `download_image` retry/timeout; **md5 cache** (skip re-download on `md5Checksum` match). Folder id from `client.drive_folder` (already on the model). `google-api-python-client` + `google-auth` (standard; don't hand-roll OAuth). **Built when the user provides OAuth creds** (designed now; for local testing, provided files substitute for the Drive listing via the same resolver).

## 8. Content → structured DATA (Agent C) — new `stages/structure_content.py` + `models_pagedata.py`

**8.1 Typed per-ST-type schemas** replace `ReportPage.data: dict[str,Any]`. A discriminated union keyed on `type` + a `GenericPageData(extra="allow")` fallback (`models_pagedata.py`, mirroring how `models_onboard.py` isolates contracts): one model per DNA §D recipe (`CoverData, AboutData, CaseStudyData, MechanismData, DataPageData, TestimonialsData, LogoWallData, SummaryData, FaqData, CollaborationData`) + shared leaves (`StatBox(label,value,before,after)`, `PullQuote(text,attribution)`, `Kunde(name,funktion,company_url)`, `RatingCard`, `ReviewCard`, `LogoItem`). **Field names match what the renderer already reads** (codifies the `st_07a.py` contract → no renderer rewrite forced). Every field optional/defaulted (missing pull-quote validates fine).

**8.2 Additive stage.** `structure_content` runs after Stage 4, feeds 6-8. **`ReportPage.data` stays permissive at the route** (no 422); the typed parse happens in the stage; parse failure → warning + keep raw as `GenericPageData` → renderer falls back to `_generic`. Never blocks.

**8.3 Chart DATA** = its own discriminated union (`before_after_bars | line_compare | donut | money_infographic | cost_math_strip | comparison_columns`), persuasion data only. **Three sourcing lanes:** ① **deterministic transform (DEFAULT)** when numbers are literal in content — regex + the existing German-number normalizer (`validate_cover.py:54-60`) extracts before/after pairs, cost-math operands, stat rows. Zero cost, zero hallucination. ② **LLM strict-extraction** ONLY for interpretive figures (which clause is the thesis; 4 paragraphs → a clean cost-math strip) — strict `json_schema` (`strict:true, additionalProperties:false`, `temperature:0`) + Pydantic re-validate + whitelist/clamp pass + bounded self-heal retry (`max_retries=2`), reusing the exact `build_image_prompts.py`/`vision_reading.py` spine. ③ **config/content (validated, never invented)** for ratings/reviews/logos. **LLM is FORBIDDEN from synthesizing a score or review** (fabricating social proof).

## 9. AI generation + compositing (Agent B) — `stages/assets/` (split from `generate_assets.py`)

**9.1 Device/product mockups = Pillow COMPOSITING (deterministic default), not fal.** Decisive: the screen content is a *real client asset* (sourced by §7), and the current fal model (Nano Banana Pro) has **no image-input parameter** — you literally cannot composite a screenshot via it. Ship a small library of **transparent device-frame PNGs** (phone/laptop/3D-book) each with a recorded screen quad; `Image.transform(PERSPECTIVE/QUAD, BICUBIC)` warps the creative into the quad; `alpha_composite()` the frame; `ImageFilter.GaussianBlur` for a soft shadow. Pillow is already a dependency; fully deterministic, free, offline-testable. Frame geometry = the only per-frame constant (data, brand-agnostic).

**9.2 Texture/atmosphere = fal generate** (genuinely synthetic). A typed texture-template registry keyed by `(role, texture_axis, ground_mode)` → a prompt-template fragment (placeholders filled from the brand brief's `texture_material`/`image_style_prompt`/palette/`negative_prompt` — NO client literal). `string.Template`/f-string fragments in a typed dict (Jinja2 only if role logic grows; NOT LangChain). Generated once per report at print size.

**9.3 The pipeline:** `spec → build_image_prompts (batched, temp=0) → cache_key=sha256(model+prompt+negative+aspect+resolution+seed) → cache hit reuse (status="cached", $0) | else (under budget) fal_generate(seed) → validate(dims/aspect) → store → [device slots] Pillow composite`. **Determinism = the content-addressed cache** (persistent dir `var/asset_cache/`, sha256 of exact fal inputs; temp=0 prompts are stable → stable key → never re-pay), NOT the model. **Cost guard:** `max_generations_per_report` (counts only real fal POSTs; on cap → `skipped_cost_cap` + warning). **Output validation:** open with Pillow, assert decodable + aspect-in-tolerance, one bounded regen-on-fail. **Model note for determinism-critical textures:** Nano Banana Pro accepts `seed` but doesn't guarantee reproducibility (autoregressive); prefer `fal-ai/flux-2` (diffusion, seed-reproducible) for textures — env-swappable via `FAL_IMAGE_MODEL`. No new runtime dep (Pillow + httpx present).

## 10. Robustness substrate (from the ADR + migration spec — applies to ALL stages)

Unchanged + now load-bearing for the bigger pipeline:
- **`Stage` Protocol + `run_render_pipeline()` runner** (mirror `stages/onboard/pipeline.py` `_mark` timing + one error policy). The §4 graph runs on it; `graphlib` validates ordering once.
- **Typed `Settings`** (pydantic-settings, `SecretStr` keys, model slugs, timeouts, `max_generations_per_report`, cache dir, Drive creds) via `Depends`; **pooled `httpx.AsyncClient`** via `lifespan` (stages already accept `http_client=`).
- **`stamina` resilience** on ALL external calls (exp backoff + jitter + `Retry-After`); the **fal content-addressed cache + budget guard escalate from nice-to-have to load-bearing** (B now generates multiples per report).
- **structlog + a job/correlation id** through every stage; kill the silent `except: pass`. **Error taxonomy** + a top-level handler so `/render` never bare-500s.
- **Async `/render`** (202 + background + webhook like `/onboard`), keeping cheap Stage-1 validation synchronous. (User-approved.)
- **Stage-6 (`generate_components.py`) RETIRED** — the renderer builds visuals from data; confirmed dead by consumer trace.

## 11. Determinism, non-regression & testing

- **The golden-file contract test on `resolved_package.json` is the spine** — retargeted (Agent D): freeze the **new v2.0 contract**, not the old bytes. Render the sample fixture → normalize volatile fields (`generated_at`/`record_id`/temp paths; the no-`/Users/` guard already exists) → assert the full manifest + validate against `ResolvedPackageManifest`.
- **Determinism preconditions:** axes derivation pure; A's resolver pure; **B pinned by the content-addressed cache** (faked transport + fixture → cache hits → stable manifest, which references paths not pixels).
- **Non-regression:** every new block is optional/defaulted, so the existing fixture validates and the 221 stay green; new stages = new test files; `test_no_client_name_in_logic` extended to `resolve_axes`/`map_slots`/`structure_content`/`drive_client`/`assets/*`. Validate-then-dump at the assemble seam turns contract drift into a loud test failure, not a silent renderer breakage.
- **New test families:** `test_resolve_axes`, `test_slot_resolver` (pure, shuffled-listing determinism), `test_structure_content` (deterministic chart parsers + LLM-faked extraction + degrade-to-warning), `test_compositing` (Pillow device-frame, offline), `test_resolved_package_contract` (golden v2.0).

## 12. Build units (the development will follow these, in order)

Each unit is additive, behind the golden net, both suites green. (Detailed task breakdown → `writing-plans` after this PRD is approved.)

| # | Unit | Owner-area | Key deliverable |
|---|---|---|---|
| 0 | **Contract net first** | D | `ResolvedPackageManifest` v1.0 characterization + golden-file test (freeze current), THEN evolve to v2.0 |
| 1 | Robustness substrate | ADR | Settings+DI, pooled client, structlog+job-id, stamina, error handlers, Stage runner |
| 2 | `resolve_axes` stage | D | 6 validated axes + onboard plumbing + provenance |
| 3 | `structure_content` + `models_pagedata` | C | typed per-ST data + chart parsers (deterministic) + LLM strict-extraction + social-proof models |
| 4 | Slot registry + pure resolver | A | `PageTypeRecipe` + `resolve_slots` + new statuses (no blank box) |
| 5 | `stages/assets/` split + fal cache + budget + texture gen | B | content-addressed cache, cost guard, texture templates |
| 6 | Device-mockup compositing | B | Pillow frame library + perspective composite |
| 7 | Drive client | A | OAuth2 list/get_media + md5 cache *(when creds provided)* |
| 8 | Pipeline integration | D | the §4 graph on the runner + `graphlib` validation + async `/render` |
| 9 | Stage-6 retirement | ADR | delete `generate_components.py` (with renderer Plan B) |
| 10 | Package contract v2.0 finalize | D | promote manifest to v2.0 + golden re-baseline + provenance |

## 13. Out of scope / deferred / dependencies

- **Renderer changes** (the §F component library: rating-card, review-grid, logo-wall, device-frame placement, dark panels, charts-from-data, two-tone headlines, the 2 new page types) — a SEPARATE renderer PRD/spec, downstream of this. *(This PRD makes the renderer's inputs exist; the renderer renders them.)*
- **Google Drive OAuth credentials** — user provides; Unit 7 builds then. Until then the resolver runs on provided files / manifest.
- **Device-frame PNG assets** (phone/laptop/book transparent frames + screen quads) — must be sourced/authored (one-time data).
- **Content the agency supplies** (ratings/reviews/logos) — validated, never invented; the input contract must carry them.
- **No** heavyweight orchestration/queue/DB; **no** service-account Drive; **no** LLM-synthesized social proof.

## 14. Success criteria

1. The package `resolved_package.json` validates against `ResolvedPackageManifest` v2.0 + matches the golden snapshot; all suites green (221 + new).
2. Every required image slot resolves or yields a **named `missing_required`** (zero blank boxes); founder/client/team photos land in the right slots by Drive naming convention, deterministically.
3. Device mockups composite deterministically; textures generate once + cache (never re-pay; bounded cost).
4. Per-page typed data + chart data + social-proof data populate per the DNA recipes; deterministic where the numbers are literal, strict-LLM only where interpretive, never fabricated.
5. 6 axes resolve to valid Literals from brand+onboard+defaults, brand-agnostic (guard green).
6. Provably brand-agnostic (`test_no_client_name_in_logic` extended + green); right-sized (no rejected tech added); deterministic (golden stable run-to-run).

## 15. Self-review

- **Placeholders:** none — each requirement names a concrete stage/model/library + its source agent finding.
- **Consistency:** the §4 graph, the §5 contract, and §6-9 stages reference the same seams (`ResolvedSlot`, `PageData` union, `ResolvedAxes`, `ChartSpec`); D's contract consumes A/B/C outputs exactly.
- **Scope:** one subsystem (Layer 1); the renderer expansion is explicitly deferred to its own spec; Drive build gated on creds.
- **Reconciliation:** §1/§11 explicitly supersede the migration spec's "output-preserving" criterion (post-DNA the package must change) while keeping its robustness mechanisms + incremental, both-suites-green discipline.
- **Brand-agnosticism:** axes + assets + content are DATA; the registry names kinds/keys; LLM/fal driven by brand brief + axes; guard tests lock it. The direct fix for the pollution failure mode.
- **Determinism:** pure resolvers + content-addressed cache + golden contract test — "accurate every time" is structurally enforced, not hoped for.
