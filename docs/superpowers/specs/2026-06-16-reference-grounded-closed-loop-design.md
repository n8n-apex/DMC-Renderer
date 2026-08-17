# Reference-Grounded Closed Loop: Design

**Date:** 2026-06-16
**Status:** design (awaiting user review before plan)
**Goal:** Make Richard's reference decks the live source that both DRIVES and CHECKS the build, by wiring the existing `research/quality_loop` into the pipeline, turning on reference-grounded vision grading, growing the auto-fix surface, and replacing the hardcoded layout mapping with templates derived from the references.

---

## 1. Why this exists (the problem in one paragraph)

The render pipeline today is content-driven and deterministic: `preprocessor` Stages 1-8 turn copy plus brand axes into `resolved_package.json`, the `v7-renderer` fills hardcoded CSS templates, Ghostscript flattens. The reference PDFs in `refs/` are NEVER read at runtime (confirmed by grep: zero usage in preprocessor or renderer). They reached the output only through a human reading them, writing prose docs, and hand-translating those docs into CSS. That human-in-the-seam is lossy, forgetful, and grades work against its own intentions instead of the reference. Every recurring regression (neon glow, palette drift, empty bottoms, the "6 von 6" ring spilling its circle) is a symptom of a person standing in for a feedback loop that was designed but never switched on.

A reference-grounded quality loop already exists in `research/quality_loop/`: a reference library, a deterministic perception layer, a reference-grounded vision-comparison grammar, a fix-routing conductor, and a convergence brain with anti-regression guards. The vision wiring is complete end to end (`brain.converge_page`/`converge_deck` already accept a `vis_client`, already call `vis_client.score_page(...)`, already feed `analysis.score(..., vis_results=...)`; `run_deck.py --vis` already builds a real client; all reference decks are already rasterized to PNG). It has simply never been run as part of the build, and its judgment is currently deterministic-only because nothing feeds it vision results in normal operation.

This spec closes that loop.

---

## 2. Architecture

The end-to-end build becomes one pipeline with the references wired in at two points (DRIVE and CHECK):

```
Stages 1-8 (preprocessor)                          content + brand axes -> resolved_package.json
   |   Stage 7 (plan_layout) selects a reference-DERIVED LayoutTemplate per page   <-- refs (Part 4, DRIVE)
   v
v7-renderer render (render.py)                     initial PDF + page PNGs
   v
Stage 9: CONVERGE (quality_loop, vision ON)                                        <-- refs (Parts 1-3, CHECK)
   |   per page: perceive -> grade vs same-type reference pages -> auto-fix -> re-render -> ship best
   |   emits convergence_report.json (per-page verdict + residual defects by owner)
   v
Ghostscript flatten (postprocess)                  report.pdf
```

The references stop being prose. They become (a) the structured templates the renderer builds from and (b) the ground truth the loop grades against. The same source drives and checks, so derivation and verification cannot drift apart.

### Components touched / created

| Concern | Today | After |
| --- | --- | --- |
| Vision endpoint | `_OPENROUTER_URL` hardcoded in `vis_client.py` | `VISION_API_BASE` + model + key from `.env`; hosted/local/self-hosted is a config flip |
| Vision grading | wired but never fed in normal runs | ON by default in Stage 9 (strong model), cached, iteration-capped |
| The loop | side harness (`run_deck.py`) run by hand, never | mandatory Stage 9 of the end-to-end build, with a `--fast` skip |
| Auto-fixes | one knob (`N08` dead space -> density/layout) | plus overflow-fit, panel-treatment, qr, photo-treatment, header-furniture knobs |
| Overflow defects | hard-fail row `N04` with NO computed fact (passes silently) | deterministic overflow/clip perception fact; the loop catches the ring-class bug |
| Layout source | `ST_TO_TEMPLATE` dict: st_type -> hand-written CSS | reference-derived `LayoutTemplate` per st_type, rendered by a template engine |

---

## 3. Part 1: turn on reference-grounded vision grading

Scope: small. The plumbing exists; this is configuration, one endpoint generalization, and a validation step.

1. **Make the vision endpoint provider-agnostic.** In `quality_loop/vis_client.py`, replace the hardcoded `_OPENROUTER_URL` with a `VISION_API_BASE` read from `.env` (default to the current OpenRouter completions URL). The payload is already OpenAI-compatible `chat/completions` with `image_url` data URLs, so OpenRouter, a local Ollama/MLX server, or a self-hosted vLLM/TGI endpoint are all drop-in. Keep `OPENROUTER_API_KEY` and `OPENROUTER_VISION_MODEL` semantics (key never printed or logged, already enforced).
2. **Select a strong vision model.** Set `OPENROUTER_VISION_MODEL` in `research/preprocessor/.env` to a strong vision-capable model (32B-to-72B class or a top hosted model). The `_FALLBACK_MODEL` (`google/gemini-2.0-flash-001`) stays as the no-config fallback only.
3. **Grader smoke check (engineering hygiene, not a quality gate).** A one-time check that the live client returns well-formed `{row_id: {score, rationale}}` and that it separates a known-good reference page from a deliberately broken render. If it cannot tell them apart, the model or prompt is wrong and we stop before trusting it.
4. **Keep the on-disk cache** (`references/.vis_cache`) so re-runs of unchanged pages are nearly free. `PROMPT_VERSION` bump invalidates the cache when prompt semantics change.

Deliverable: running the loop with `vis_client=VisionClient()` produces real composition scores that `analysis.score` adjudicates against the rubric VIS / DET-and-VIS rows.

---

## 4. Part 2: run the loop as Stage 9 (inline, post-render)

Scope: small-to-medium.

**Where it runs.** The loop must re-render during convergence and already lives in the renderer environment (it imports `assembler.render_package`). So Stage 9 is a mandatory post-render stage of the end-to-end build, executing in the renderer environment, NOT vision calls fired from inside the preprocessor's FastAPI request. Same outcome (every build self-corrects and grades), cleaner process boundary.

**Module.** A new `quality_loop/stage_converge.py` (or a thin entry on `run_deck.py`) that:
- takes the package dir plus the freshly rendered PDF and page PNGs,
- builds a real `VisionClient`, calls `converge_deck(...)` (already supports `vis_client=`),
- lets the conductor apply auto-fixes and re-render the affected pages (the conductor is the only mutator; it patches a COPY of the package, never the fixture),
- writes the converged best-state PDF plus `convergence_report.json`.

**`ConvergenceReport` schema (new):**
```
{
  "deck_cleared": bool,
  "deck_reward": float,
  "pages": [
    {
      "page_no": int,
      "st_type": str,
      "cleared": bool,
      "reward": float,
      "fired_defects": [{"id": "N08", "label": "dead/hollow space", "owner": "renderer"}],
      "fixes_applied": [{"defect_id": "N08", "knob": "density", "from": "compact", "to": "spacious"}],
      "residual_by_owner": {"renderer": [...], "preprocessor": [...], "asset_gen": [...]}
    }
  ]
}
```
This report is the verification artifact. It replaces eyeballing: it states, per page, what the machine could and could not fix, grouped by who must fix the rest.

**Wiring into the build.** `render.py` gains a converge step after the initial render and before Ghostscript, gated by a `--fast` flag that skips Stage 9 for quick local iteration. Default build runs Stage 9; `--fast` does not. Caching plus an iteration cap (already in the brain's guards) blunt repeat cost.

---

## 5. Part 3: grow the auto-fix knobs and add the overflow fact

Scope: medium. Two kinds of work: one new perception fact, and several new conductor knobs.

### 5.1 The overflow/clip fact (highest value: kills the ring-class bug)

`rubric.py` already defines `N04` "overflow / clipping" as a HARD-FAIL row, but it has no computed fact, so overflow currently passes silently. This is exactly the "6 von 6" ring spilling its circle and any text leaking a panel.

Add a deterministic `overflow_detected` fact to `perception.py` (PyMuPDF plus Pillow, no vision): detect content drawn outside its container or the page content box (glyph/path bounding boxes exceeding region bounds; SVG text exceeding its shape's bbox where detectable from the rendered raster). Wire it as `N04`'s `fact_key`. Because `N04` is a latching hard-fail, any page with overflow becomes un-shippable until fixed, which forces the issue to the surface every build.

### 5.2 New conductor knobs

Each knob is a `DEFECT_KNOBS` entry plus an axis ladder plus the renderer honoring that axis. Where the renderer already has the axis, the knob is pure wiring; where it does not, the loop keeps flagging the defect honestly (the anti-faking rule) until the renderer grows the capability.

| Defect | Knob (axis ladder) | Renderer support | Notes |
| --- | --- | --- | --- |
| `N04` overflow/clip | `fit` ladder: shrink offending viz center text / clamp element to bounds | NEW small capability: auto-fit viz centers + clamp | directly fixes the ring bug |
| `N02` pale tint not dark panel | `panel_treatment`: paper -> matte -> glass -> dark | exists (material-panel system, PBR-H) | step toward dark authority panel |
| `N06` oversized QR / qr gating | `qr_scale` / honor `qr_enabled` | exists (qr gating) | mostly wiring |
| `N10` untreated full-bleed photo | `photo_treatment`: none -> scrim -> duotone | exists (full-bleed treated variant, PBR-I) | mostly wiring |
| `N09` missing header furniture | `header_furniture`: off -> on | NEW small capability | running-header toggle |

`N08` keeps its existing density and case-study layout knobs.

---

## 6. Part 4: reference-derived structured layout templates (the long pole)

Scope: large. Delivered last and incrementally, one st_type at a time, never a big-bang replacement. This is what turns the system into a true "copy and repurpose" machine.

### 6.1 `LayoutTemplate` schema (new, brand-agnostic by construction)

```
LayoutTemplate:
  st_type: str               # e.g. "ST-07A"
  variant: str               # e.g. "authority-rail", "magazine"
  grid: { columns: int, margin_top/right/bottom/left: float (page fractions), gutter: float }
  regions: [
    { role: str,             # headline | lede | body | portrait | stat_rail | viz | footer | ghost_numeral | logo_wall | quote | cta
      x: float, y: float, w: float, h: float,   # normalized 0..1 page fractions
      z: int,                # stacking, for overlaps
      constraints: { min_h?: float, fit?: "shrink"|"wrap"|"clamp" } }
  ]
  type_roles: { headline: <scale role>, lede: <scale role>, body: <scale role>, label: <scale role> }
  color_roles: { ground: "neutral_light", ink: "neutral_dark", accent: "primary", footer: "neutral_mid" }
  whitespace_target: float   # fraction of page intentionally empty
  source_refs: [ { deck: str, page_no: int } ]   # provenance, for the loop to grade against
```
Stores geometry, ROLES, and categorical axes only. NO client hex, names, or fonts. Color values resolve from brand tokens at render time exactly as today, so the template is reusable across brands.

### 6.2 Extraction (`reference_layout_extract.py`, new)

For each reference page: feed the page PNG plus its text layer to the vision model and emit a `LayoutTemplate`. `references/classify.py` already labels every reference page by st_type, so pages cluster by type. For v1, pick the BEST exemplar per st_type as the archetype (plus a small set of named variants where the references clearly show distinct compositions), rather than averaging geometry (averaging risks a mushy, wrong layout). Store under `quality_loop/references/templates/<st_type>/<variant>.json`.

### 6.3 Template-driven renderer (incremental)

Introduce ONE generic template-driven pattern in `v7-renderer` that places the existing component/macro library (portrait, stat_rail, viz, ghost_numeral, pull_quote, logo wall, etc.) per the template regions. Migrate one st_type at a time: keep the existing hand-built pattern for a type until its template-driven version passes both the conformance gate and the vision loop against the references, then switch that type over. Recommended first migration: **case_study (ST-07A)** (most reference exemplars, best understood, already rebuilt once).

### 6.4 Selection (`plan_layout.py`, Stage 7)

Change Stage 7 from `st_type -> css_template name` to `st_type (+ axes) -> LayoutTemplate` (choose the archetype or variant best matching the page's content shape and axes). `ST_TO_TEMPLATE` is replaced by template selection; unknown types fall back to a generic template so the render never fails.

### 6.5 Closure

The loop grades each rendered page against the very reference pages listed in its template's `source_refs`. Derivation and verification share one ground truth.

---

## 7. Phasing and verification gates

Ship in order; each phase is independently shippable and verified before the next.

1. **Phase 1 (Part 1):** vision endpoint configurable, strong model set, grader smoke check passes. Verify: live `score_page` returns well-formed scores and separates good vs broken page.
2. **Phase 2 (Part 2):** Stage 9 wired into the build with `--fast` skip; `convergence_report.json` emitted. Verify: a full build produces the report; `--fast` skips the loop; the converged PDF is never worse than the initial (monotone-best guard).
3. **Phase 3 (Part 3):** overflow fact plus knobs. Verify: a deliberately overflowing viz (the ring) is caught by `N04` and either auto-fit or flagged; each new knob demonstrably steps its axis and reduces its defect.
4. **Phase 4 (Part 4):** template extraction, template engine, case_study migrated first, then the other five types one at a time. Verify per type: render from template -> conformance gate green -> vision loop reward at or above threshold against `source_refs` -> switch the type over.

**Standing verification on every phase:** render, read the actual page PNGs, and let the loop compare them to the reference pages. Never claim a page is done on the basis that an element merely appeared. The deterministic `tests/test_design_conformance.py` gate stays as the fast pre-check; the loop is the composition check.

---

## 8. Guardrails (carried in, non-negotiable)

- **Brand-agnostic logic.** Templates and all renderer/preprocessor/loop logic carry geometry, roles, and categorical axes only: no client hex, names, or font literals. Extend the existing literal-guard test (`test_no_literals_in_architecture.py`) to scan `references/templates/` and the new modules. Client data lives in fixtures.
- **References ground composition, not brand values.** The vision prompt grammar already enforces this; keep it. Reference retrieval stays spread across multiple decks, never anchored on one client.
- **No fabrication.** No invented person, metric, quote, or relationship. Real data or graceful omit.
- **Secrets.** Vision key only from `.env`; presence checked, value never printed, logged, or committed. No git in this repo.
- **Anti-faking.** The conductor reports what it cannot fix (by owner) rather than rigging a render that papers over a gap. The monotone-best guard means a knob that makes a page worse can never ship that worse page.
- **No em dashes anywhere.**

---

## 9. Risks and mitigations

- **Inline cost and latency.** Every default build makes live vision calls plus several re-renders. Mitigate: aggressive cache, iteration cap, and the `--fast` flag for local iteration. The vision endpoint is configurable, so a cheaper or local model can be swapped in for dev.
- **Self-hosting the model.** A strong open-weights VLM (32B-72B) needs a GPU; Railway is CPU-first and a poor fit. If self-hosting is ever wanted, target a scale-to-zero GPU host (Modal, RunPod, Replicate, Baseten) or a GPU VM, and point `VISION_API_BASE` at it. A quantized 7B on this Mac via Ollama/MLX is a free dev tier. This is a deployment choice, decided later, not an architecture change.
- **Extraction fidelity (Part 4).** Turning reference pages into structured geometry is judgment-heavy. Mitigate: extract per-page, choose the best exemplar per type for v1 (no averaging), and let the loop validate each template against its `source_refs` before the type is switched over.
- **Big-bang regression risk (Part 4).** Mitigate: the template engine runs alongside the existing patterns; migrate one st_type at a time, each double-gated (conformance plus loop).
- **Grader trust.** A weak model gives noisy grades. Mitigate: strong model from the start (user decision), plus the one-time smoke check.

---

## 10. Resolved decisions (from brainstorming)

- **Scope:** full repurpose (Parts 1+2+3+4).
- **Where the loop runs:** inline as a mandatory post-render build stage, executing in the renderer environment, with a `--fast` skip.
- **Vision model:** a strong hosted vision model from **OpenRouter** (pay-per-image), chosen and used now. The endpoint is configurable so local or self-hosted is a later config flip. The local Mac (24GB unified memory) is an explicit FALLBACK only if OpenRouter fails, and at 24GB realistically runs a ~7B-class quantized VLM via Ollama/MLX, i.e. a degraded dev tier, not parity with the hosted model.
- **Part 4 first migration:** case_study (ST-07A).

---

## 11. Out of scope (explicit)

- Building a Supabase-backed reference library (the local file-based `references/` index is sufficient for this work; the Phase-C Supabase idea is deferred).
- Self-hosting deployment / GPU provisioning (config is made ready; ops is a later, separate decision).
- New report content or copy: this is layout, grading, and repair, not authoring.
