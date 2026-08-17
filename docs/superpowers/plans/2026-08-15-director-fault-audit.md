# Director Contract — Reference-Conditioned Generation (BINDING, 2026-08-15)

> This document is the single source of truth for how contextual art is
> generated. It supersedes all earlier "prompt-to-image" behavior. Every
> section is a requirement; there are no suggestions, assumptions, or
> placeholders. If an implementation does not satisfy a line below, it is a
> fault.

## 0. The two irreducible rules (owner-confirmed verbatim)

1. **Fal owns contextual art ONLY.** It never draws numbers, charts,
   dashboards, axes, labels, or exact data relationships. All data-bearing
   devices are renderer-native and deterministic.
2. **Generation is IMAGE-TO-IMAGE, never prompt-to-image.** The selected
   Richard reference face image is an INPUT to the model
   (`fal-ai/nano-banana-pro/edit`, `image_urls`). The model transforms that
   reference's visual grammar; it does not imagine a scene from prose alone.

A generation that violates either rule is rejected, regardless of how it looks.

---

## 1. Fault record (why this contract exists)

### 1.1 The current prompt-to-image path (REJECTED)

The last Conesso generation sent this prompt to `fal-ai/nano-banana-pro`
(text-to-image):

```text
Abstract editorial visualization for Conesso GmbH: a before/after
transformation: the old manual state on one side, the automated state on the
other, connected by a clear motion arc. The scene evokes the figures von 30 auf
2 Minuten, von 60 auf 5 Minuten, 3 kritische Workflows eliminiert without
writing them as text. Style: composition inspired by an Editorial reframe with
conclusion block reference spread; device language: Long-form argument;
headline; sectional body; dark teal conclusion panel; colour palette: deep
#1A2540 ground with #E97E47 accent light; premium editorial print quality,
refined geometry, soft depth. Aspect ratio 16:9.
```

Negative prompt:

```text
photorealistic people, faces, hands, text, words, letters, numbers, charts,
graphs, screenshots, logos, watermark, mockup, UI, bright colours, clutter,
gradients without structure
```

**Why this is a fault, exactly:**

| # | Fault | Evidence |
|---|---|---|
| F1 | The reference image is NOT an input. Only a prose label ("dark teal conclusion panel") reaches fal. | The call uses `fal-ai/nano-banana-pro` (t2i) which accepts no image. |
| F2 | "before/after transformation" is an abstract category, not a composition. It gives fal license to invent tubes/rings/blobs. | Generated scene is a generic abstract. |
| F3 | The negative prompt forbids numbers/charts/screenshots/UI even though the page's proof depends on those relationships. | Contradictory contract. |
| F4 | The prompt names figures but forbids writing them as text — fal cannot represent "30→2" honestly, so it omits the evidence. | Scene carries no argument. |
| F5 | No placement contract: the image is always inserted as a fixed 36mm strip after section 1 (`loop.index == 1`), regardless of the reference anatomy. | All five case studies share the same slot, ignoring reference region structure. |
| F6 | The regenerated scenes were produced by a one-off script, not the live `generate_assets` path; exact prompts were not persisted at generation time. | Supabase `director_decisions` holds stale decisions (ref_face_id 7 = apex itself, pre-diversification). |
| F7 | The reference atlas annotations for Apex are stale (built from an older deck layout), so even the selector's metadata can misdescribe a correctly chosen page. | Apex p7 atlas row describes the prior report's page 7 role. |

### 1.2 Measured geometry faults (renderer, independent of fal)

| Page | Element | Measured | Fault |
|---|---|---|---|
| p7/9/12/14/15 | `.csh-right` vs `.csh-dash` | right column ≈ 983px; dash ≈ 354–408px auto-height, top-pinned | unowned void between dash and quote |
| p18 | `.fz-viz` vs `.c-viz-cluster__row` | parent 85px; content 146px; parent `overflow:hidden` | radial 58%/61% clipped |
| p16 | `.c-stat-callout__value` | box 111px; `30-50%` scrollWidth 176px; nowrap | stat overflows its box |

---

## 2. Reference selection (preconditions)

1. **Selector scope:** `st_type` + `format` + `density` + `exclude_report`
   (the client's own deck is never its own taste reference). Verified live:
   apex → niklas p8/p10/p12 + buchagentur p5/p6, 5-of-5 distinct.
2. **The selected row MUST carry a real raster** (`ref_faces.png_path`,
   sha256-verified) or a Supabase Storage object. A row without an image is
   not selectable.
3. **Reference anatomy** (`ref_faces.role`, `mechanism`, `devices`, `density`,
   `argument`) must be RE-VERIFIED for any reference used in generation. The
   atlas metadata is not trusted blindly: if a reference face lacks anatomy,
   the Director must classify it deterministically from the page raster/PDF
   text before using it. No stale annotation may drive a prompt.

---

## 3. The Director page brief (input to everything downstream)

The Director emits ONE document per page. Required fields (no omissions):

```json
{
  "client_slug": "apex",
  "report_id": "<report id>",
  "page_key": "slot.14",
  "st_type": "ST-07A",
  "selected_reference": {
    "face_id": 11,
    "report": "buchagentur",
    "page_no": 5,
    "raster_uri": "file:///…/references/pages/buchagentur/p5.png",
    "storage_object": "references/source-pdfs/buchagentur.pdf" ,
    "sha256": "<hash>",
    "anatomy": {
      "regions": ["narrative_left", "proof_right"],
      "devices": ["stat_stack", "dark_full_height_panel", "quote"],
      "mechanism": "case-study proof spread",
      "density": "dense"
    }
  },
  "selection_rationale": "…",
  "visual_job": "show three real workflow transformations as one coherent operating system",
  "must_show": [
    "30 Minuten -> 2 Minuten (onboarding)",
    "60 Minuten -> 5 Minuten (copywriting)",
    "3 kritische Workflows eliminiert"
  ],
  "must_not_imply": ["new metric", "fake interface", "real customer photograph", "price"],
  "region_plan": [
    {"region": "left_story", "role": "narrative", "bounds": [0.0, 0.0, 0.56, 1.0]},
    {"region": "right_proof", "role": "full_height_data_panel", "bounds": [0.58, 0.0, 1.0, 1.0]},
    {"region": "supporting_art", "role": "contextual_illustration", "bounds": [0.05, 0.48, 0.52, 0.68]}
  ],
  "renderer_devices": ["transform_arrow", "grouped_bars", "stat_stack"],
  "generator": {
    "role": "contextual art only",
    "input_image": "<selected reference raster>",
    "endpoint": "fal-ai/nano-banana-pro/edit",
    "instruction": "preserve the dark full-height proof panel grammar and stat rhythm of the reference; replace its client imagery with a calm abstract visualization of three workflow lanes converging into one operating system; keep the dark ground and accent light; do NOT add text, numbers, charts, faces, or UI",
    "aspect_ratio": "16:9",
    "resolution": "2K"
  }
}
```

**Placement is part of the brief.** The renderer consumes `region_plan`
verbatim. No asset is inserted into a region the Director did not name.

---

## 4. The generation call (BINDING, image-to-image)

### 4.1 Endpoint and payload

- Model: **`fal-ai/nano-banana-pro/edit`** (NOT `…/pro` text-to-image).
- Input: `image_urls` MUST contain the selected reference raster as a
  **data URI (base64)** — fal accepts data URIs; the local reference PNG is
  small enough (reference pages are rasterized, not the 721MB source PDF).
- `prompt` MUST contain only the transformation instruction from
  `generator.instruction` (what to preserve, what to place). It MUST NOT
  contain figures, charts, or "make an abstract X" boilerplate.
- `aspect_ratio`: from the brief (16:9 for the supporting-art region).
- `resolution`: "2K".
- `seed`: fixed per (page_key, reference_sha256, brief_version) for
  determinism and cache-busting on intent change.
- Cache key MUST include: endpoint, prompt, input image bytes, aspect,
  resolution, seed. The current fal cache key already hashes prompt+model+…
  but MUST be extended to include the input image bytes.

### 4.2 What fal is allowed to do

- Transform the reference's **compositional grammar** (dark panel rhythm,
  stat pacing, region feel) into a contextual illustration.
- Use the page's concrete subject (workflow lanes converging; onboarding
  process; automation threads) as the *content* of that grammar.

### 4.3 What fal is NEVER allowed to do

- Render numbers, text, charts, dashboards, axes, screenshots, UI, faces,
  or exact data relationships (those are renderer-native).
- Invent metrics, clients, or evidence.
- Ignore the input reference (the edit must be visibly grounded in it).

---

## 5. Renderer-native devices own ALL data-bearing relationships

| Argument shape | Renderer device | Example |
|---|---|---|
| before/after pair | `transform_arrow` | 30 Minuten → 2 Minuten |
| multi-category before/after | `grouped_bars` | onboarding/copy/check-in lanes |
| completion | `completion_ring` / `stat_strip` | 6 von 6 |
| magnitude | `stat_strip` / `mega_numeral` | > 200.000 € |
| sourced market facts | `icon_stat_row` | 58%/61% |

The A3 right proof region must be a **full-height authority panel**
(reference-backed), hosting the page's native devices, with the quote seated
inside/below it. No unowned dashboard/quote void.

---

## 6. Persistence (provenance, mandatory)

Every generation MUST write to `director_decisions` (or an equivalent):

```json
{
  "client_slug": "apex",
  "report_id": "…",
  "face_key": "slot.14",
  "st_type": "ST-07A",
  "ref_face_id": 11,
  "ref_sha256": "…",
  "rationale": "…",
  "visual_job": "…",
  "brief": {"region_plan": …, "devices": …},
  "generator_brief": {
    "endpoint": "fal-ai/nano-banana-pro/edit",
    "prompt": "<exact prompt sent>",
    "input_image_sha256": "…",
    "aspect_ratio": "16:9",
    "resolution": "2K",
    "seed": 12345
  },
  "output_sha256": "…",
  "created_at": "…"
}
```

The exact prompt, reference image hash, endpoint, model, seed, and output
hash must be retrievable later to answer "what was generated and why."

---

## 7. Review (semantic + visual, both required)

The VIS judge receives per row:

- the generated page PNG
- the selected reference PNG(s)
- `visual_job`, `must_show`, `must_not_imply`, `region_plan`

It answers BOTH:

1. Composition: is this as strong as the selected Richard reference?
2. Argument: does the visual make the page's stated argument easier to
   understand (and does it avoid `must_not_imply`)?

A page passes only when both answers are positive. A generated image that
"fills whitespace" but fails #2 is rejected.

---

## 8. Acceptance criteria (all must hold)

- [ ] No `fal-ai/nano-banana-pro` (t2i) call remains in the generation path.
- [ ] Every generation sends the selected reference raster via `image_urls`.
- [ ] Every `director_decisions` row stores the exact prompt, reference
      sha256, endpoint, seed, and output sha256.
- [ ] The renderer consumes `region_plan`; no asset is placed in an unnamed
      region.
- [ ] All data-bearing devices are renderer-native (no fal-drawn numbers).
- [ ] A3 right proof region is a full-height reference-backed panel; the
      dashboard/quote void is gone.
- [ ] FAZIT `.fz-viz` shows the full radial cluster (no clipping).
- [ ] ST-06 `30-50%` fits inside its stat box at the computed width.
- [ ] One Conesso p14 experiment is generated, reviewed, and inspected
      BEFORE the remaining four case studies are regenerated.

---

## 9. Implementation order (locked)

1. Fix FAZIT `flex-shrink` clipping; fix ST-06 stat fit (isolated geometry
   defects, regression-tested).
2. Replace `case_scene` fixed-strip placement with `region_plan` consumption;
   make the A3 right proof region full-height + native devices.
3. Re-verify/classify reference anatomy for the selected faces; persist.
4. Add `fal_generate_image_edit()` (image-to-image via `/edit` +
   `image_urls`), extend the cache key with input bytes, wire the Director
   brief through.
5. Generate ONE Conesso p14 contextual art image (reference-conditioned);
   run semantic review; inspect the rendered page.
6. Only after 5 passes: regenerate the other four case studies and re-render
   the deck.

---

## 10. EVIDENCE CORRECTION — 2026-08-16 (the reported "clean" gate was wrong)

The `[qa] visual gate: CLEAN` result shipped a PDF that fails visual inspection
on ALL 20 pages. The gate's score-pass was a checklist artifact; the rendered
artifact is not acceptable. This section supersedes any claim that US-402/
US-403/US-408/US-509/US-510 completed the visual contract.

### 10.1 Method

A full 20-page pre-press inspection was run via the OpenRouter vision client
(`VisionClient.extract_json`, OpenRouter key from `preprocessor/.env`) against
`research/v7-renderer/output/report-p*.png`, with a prompt demanding every
defect: clipped text, cross-section contamination, alignment breaks, dead
zones, broken devices, and a print verdict. Full JSON: `/tmp/vision_audit_20.json`.

Result: **20/20 pages verdict = no.**

### 10.2 Per-page worst defects (verbatim evidence)

| Page | Worst defect |
|---|---|
| p1 | Dead white band at bottom (~10% height), no footer anchor |
| p2 | Ring sizes inconsistent — third ring ('30 bis 50 %') materially smaller |
| p3 | Massive left-column dead zone + near-empty bottom quarter; Referenzen thumbnails clip text |
| p4 | 25–30% blank lower page below the callout |
| p5 | **Venn diagram overprints item-3 text** — third lie obscured/cut |
| p6 | Multiple text strings hard-clipped at right page edge (screen props) + 15% bottom band |
| p7 | **Duplicate stat content in right column** ('> 200.000 €' + '4 automatisierte Kernprozesse' rendered twice) |
| p8 | Bottom ~40% empty; body columns share no top baseline |
| p9 | 30% dead band between quote and lower stat block in right column |
| p10 | '40 %' stat is a broken context-free fragment; label is an incomplete sentence |
| p11 | Brand/logo clipped at left edge ('ldman'); 15% bottom band |
| p12 | **Broken arrow device: 'MIT APEX' shows only 'Minuten' with no number** |
| p13 | 15% empty dark band below the quote; page number clipped |
| p14 | ~40% dead band between dark KPI box and pull-quote |
| p15 | **'ohne Headco…' hard-clipped at right page edge** — key metric cut off |
| p16 | **'30-50%' clipped at right edge — '%' cut off by the box** (the recurring fault) |
| p17 | 15% bottom band; quote floats unanchored |
| p18 | **Founder headshot + name bleeding in from the next page** (contamination) |
| p19 | **Header text clipped/obscured by the portrait overlay bleeding from p18**; stat baselines misaligned |
| p20 | 45% lower-half dead zone; ghost '20' clipped at page edges; QR misaligned |

### 10.3 Root-cause classes (what must be fixed, not papered over)

1. **Fixed one-page skeleton per section** — every section is forced into one
   sheet; overflow is "squeezed" (p16) or fragments (p18→p19).
2. **No section/physical-page identity** — the package is a flat `pages[]`
   list; continuation boundaries do not exist, so p18 content bleeds into p19.
3. **Director sidecar, not Director contract** — the brief has no
   `region_plan`/`page_arc`; the renderer never consumes it.
4. **QA not reference-grounded and not on the final artifact** — the gate
   passes zero reference images, runs before convergence, and misses
   intrinsic clipping (scrollWidth 176px vs clientWidth 111px on p16).
5. **Device bugs left in place** — p7 duplicate stats, p12 arrow with no
   destination value, p2 inconsistent rings, p5 Venn/text collision.

The fix program is defined in
`docs/superpowers/plans/2026-08-16-ralph-director-pagination-repair.md`.
