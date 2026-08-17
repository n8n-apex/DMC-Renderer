# Brand Design Brief — Onboard Analysis Layer (Design / PRD)

**Status:** Approved — ready for implementation
**Date:** 2026-05-29
**Component:** `research/preprocessor/stages/onboard/` — new `brand_brief.py` layer
**Builds on:** the `/onboard` Mode-1 pipeline (capture → dom → pixel → vision → reconcile)

---

## 1. Goal

Add the "designer's eye" layer the token extractor lacks: a **rich, image-generation-ready brand visual guideline** produced by **Claude Opus 4.6** (vision) from the captured screenshots. This is what Stage 5's fal.ai generators need to render *on-brand* imagery — replacing the thin `texture_class + 2 hexes` prompt material they have today.

The token extractor (`vision_reading`, Sonnet) stays as-is — it produces the *precise* color/font tokens (the eyedropper). This new layer produces the *qualitative* design language (the eye). Two models, two concerns.

## 2. Output schema — `BrandDesignBrief` (hybrid)

Structured visual-language fields **plus** ready-to-paste image-generation strings.

```python
# models_onboard.py

class ImageryGuidance(BaseModel):
    style: str        # photographic | illustrated | 3d_render | abstract | mixed | none
    subjects: str     # what is depicted (people, product, abstract shapes, …)
    treatment: str    # full_bleed | duotone | cutout | gradient_mesh | framed | …
    lighting: str     # bright | soft | moody | high_key | …
    avoid: list[str]  # imagery that would read off-brand

class BrandDesignBrief(BaseModel):
    visual_style_summary: str          # 1–2 sentence art-director read
    mood: list[str]                    # ["premium", "calm", "clinical"]
    imagery: ImageryGuidance
    color_usage: str                   # dominance, gradients, contrast — cites the REAL hexes
    shape_language: str                # rounded/sharp, geometric motifs, organic vs angular
    texture_material: str              # flat | soft_gradient | glass | paper | noise | …
    typography_character: str          # geometric/humanist, weight, case, pairing — beyond serif/sans
    composition: str                   # density, whitespace, alignment, layout archetype
    iconography: str                   # line | filled | weight | none
    image_style_prompt: str            # MASTER reusable fal.ai style preset (incl. real hexes, no subject)
    negative_prompt: str               # what makes an image look off-brand
    confidence: float                  # 0.0–1.0 overall
```

`OnboardResult` gains `design_brief: Optional[BrandDesignBrief] = None` — a **sibling** to `brand_profile` (keeps `brand_profile` the renderer's clean shape).

## 3. How it feeds image generation

`image_style_prompt` is the brand's reusable **style DNA** (mood + lighting + texture + rendering style + real hexes, *no subject*). Stage 5 composes it per asset: `f"{image_style_prompt}. Subject: {asset_subject}. Aspect {ratio}."` for cover hero (3:4), status-quo scene (16:9), texture, gradient. `negative_prompt` is passed through to the generator. (Wiring into Stage 5's stubbed generators is a small follow-up — out of scope here; this layer produces + stores the brief.)

## 4. The layer — `stages/onboard/brand_brief.py`

```python
async def generate_brand_brief(
    *, hero_png, fullpage_png, palette: PixelPalette, dom: DomSignals,
    vision: Optional[VisionReading], api_key: Optional[str], model: str,
    http_client=None, timeout: float = 90.0,
) -> Optional[BrandDesignBrief]:
```
- Calls OpenRouter chat completions, `temperature 0`, strict `json_schema` matching `BrandDesignBrief`.
- Sends the downscaled screenshots (reuses the shared image encoder, see §6), the measured palette (real hexes — safe; the brief *describes*, it doesn't pick tokens), the resolved fonts, and the Sonnet axes as grounding.
- Returns `None` on any failure (no key, no hero, non-200, parse/validation error). Mirrors `read_vision`.

### 4.1 System prompt (verbatim)

```
You are a senior brand designer and art director with deep experience in visual
identity and editorial design. You are shown screenshots of a company's website,
plus its MEASURED color palette (exact hex values from pixel analysis) and the
fonts actually rendered on the page.

Produce a precise, image-generation-ready brand visual guideline — the kind a
designer hands to an illustrator or a generative image model so everything they
create looks unmistakably on-brand.

Rules:
- Analyze ONLY what is visible in the screenshots plus the provided palette/fonts.
  Never invent facts about the company.
- Be concrete and specific. Generic words alone ("modern, clean, professional")
  are useless — name the actual visual devices: lighting quality, gradient
  direction, corner radius, whitespace density, photographic vs illustrated
  treatment, shape language, etc.
- Reference the REAL hex values when describing color usage.
- `image_style_prompt` MUST be a single reusable paragraph an image model
  (fal.ai / Flux / Nano Banana) can prepend to ANY subject to render it in this
  brand's style. Include the palette hexes, mood, lighting, texture/material, and
  rendering style. Do NOT name a specific subject — it is a style preset.
- `negative_prompt` lists what would make an image look OFF-brand.
- Output STRICT JSON matching the schema. No prose outside the JSON.
```

### 4.2 User prompt (assembled, then + image parts)

```
MEASURED PALETTE (exact hexes from pixel analysis — quote these verbatim in
color_usage and image_style_prompt):
  [0] #599ab3  (~38% coverage)
  [1] #85d2ee  (~21% coverage)
  ...
RESOLVED FONTS (from the DOM):
  heading: Gestura Headline TRIAL Semibold
  body:    <name or "unknown">
DESIGNER AXES (already classified by the token pass):
  accent_mechanic=tonal_same_hue; ground_mode=cool_light; texture=smooth;
  headline_type=serif
The website screenshots are attached. Produce the brand_design_brief JSON now.
```
(When `vision is None`, the axes line is omitted.)

## 5. Integration & data flow

`pipeline.py` calls `generate_brand_brief(...)` right after `read_vision(...)`, fed the same downscaled screenshots + palette + dom + the `VisionReading`. It assigns `result.design_brief = brief` after `reconcile(...)` (same pattern as setting diagnostics). If the brief is `None`, append a `needs_review` reason ("design brief unavailable"). Endpoint/webhook payload already serialize `OnboardResult`, so the brief rides along automatically. Model behind env `OPENROUTER_BRIEF_MODEL` (default `anthropic/claude-opus-4.6`).

## 6. Shared image encoder (DRY)

Extract the downscale-and-encode helper into `stages/onboard/_imaging.py`:
```python
def encode_image_data_url(path: Optional[str], *, max_edge: int = 1568) -> Optional[str]: ...
```
`vision_reading._encode_image` becomes a thin alias importing it (keeps its existing test green). `brand_brief` imports the same helper. One downscale implementation, two callers.

## 7. Error handling (mirrors `read_vision`)

| Failure | Behavior |
|---|---|
| No API key / no hero screenshot | return `None`; pipeline sets `design_brief=None` + review note |
| Non-200 / provider error-in-200 | return `None` |
| JSON parse / schema validation error | return `None` |
| Oversized image | impossible — shared encoder downscales (the live-found 6.9MB→400 bug) |
| Any exception in the layer | caught; return `None` (pipeline never crashes) |

`design_brief` is always nullable; its absence never blocks onboarding.

## 8. Testing (no real API in unit tests)

| Test | Coverage |
|---|---|
| `test_brand_brief_prompt_carries_palette_fonts_axes` | user prompt includes hexes, fonts, and the Sonnet axes |
| `test_brand_brief_parses_ok` | mock 200 → populated `BrandDesignBrief`, incl. `image_style_prompt` + `negative_prompt` |
| `test_brand_brief_api_error_returns_none` | mock 500 → `None` |
| `test_brand_brief_no_key_returns_none` | no key → `None` (no HTTP) |
| `test_brand_brief_tolerates_whitespace_padding` | OpenRouter leading-whitespace body still parses |
| `test_imaging_encode_downscales_large` | shared encoder caps a 1440×9000 PNG under 5 MB, JPEG data URL |
| `test_pipeline_attaches_design_brief` | pipeline wires `design_brief` from a mocked brief fn |
| `test_no_client_name_in_logic` | guard already rglobs `stages/onboard/` — must stay green |

**Live validation (post-build):** one real Opus 4.6 call against apex-consulting.ai to confirm the slug + vision+strict-schema works and the `image_style_prompt` is usable.

## 9. Scope boundaries

**DO:** `brand_brief.py`, `_imaging.py` (extract+reuse), `BrandDesignBrief`/`ImageryGuidance` models, `OnboardResult.design_brief`, pipeline wiring, tests, env var.
**DO NOT:** wire the brief into Stage 5's generators (separate follow-up); change `vision_reading`'s token contract; touch the renderer; make real API calls in tests.

**Success =** `/onboard` produces a populated `design_brief` (structured fields + `image_style_prompt` + `negative_prompt`) alongside `brand_profile`; all unit tests pass; chassis untouched; one live Opus run validates the real output.
