# Image Pipeline Completion — Prompt-Builder + real fal.ai (Design / PRD)

**Status:** Approved — ready for implementation
**Date:** 2026-05-29
**Component:** `research/preprocessor/stages/` — `build_image_prompts.py` (new) + `generate_assets.py` (Stage 5 restructure)

## 1. Goal

Replace Stage 5's two stubs with the real two-call image pipeline:
1. **Prompt-builder** — one batched **Sonnet 4.6** call turns the brand design brief + the report's image requirements into per-image fal prompts.
2. **Generation** — each prompt → real **Nano Banana Pro** (`fal-ai/nano-banana-pro`) call → download the image into the package.

Today the brief's `image_style_prompt` is concatenated with a hardcoded subject and never sent anywhere. This makes it: brief → *Sonnet prompt-builder* → *fal* → on-disk image.

## 2. fal.ai contract (verified)

- `POST https://fal.run/fal-ai/nano-banana-pro` · header `Authorization: Key {FAL_KEY}`
- Input: `prompt` (str, req), `aspect_ratio` (enum: `auto,21:9,16:9,3:2,4:3,5:4,1:1,4:5,3:4,2:3,9:16`), `resolution` (`1K|2K|4K`), `num_images` (int), `output_format` (`png|jpeg|webp`).
- **No `negative_prompt`** → fold into the prompt: `f"{prompt}\n\nAvoid: {negative_prompt}"`.
- Output: `{"images": [{"url": ...}], "description": ...}` → download `images[0].url`.
- Pricing: $0.15/img (1K/2K), $0.30 (4K). Default `resolution=2K`.

## 3. Prompt-builder — `stages/build_image_prompts.py`

```python
async def build_image_prompts(
    *, design_brief, asset_specs: list[dict], api_key: Optional[str],
    model: str, http_client=None, timeout: float = 120.0,
) -> dict[str, dict]:
    """Batched Sonnet call. asset_specs items: {slot_id, role, aspect_ratio, context}.
    Returns {slot_id: {"prompt": str, "negative_prompt": str}}. Returns {} on any
    failure / no key / no brief (caller falls back to concatenation)."""
```

**System prompt (verbatim):**
```
You are an expert prompt engineer for a generative image model (fal.ai Nano Banana
Pro / Flux). You are given a brand visual guideline (its reusable style, palette
hexes, mood, lighting, texture/material, shape language, do/don'ts) and a list of
specific image slots a report needs — each with a role (cover-hero background,
status-quo scene, section background texture, atmospheric gradient), an aspect
ratio, and the page's text context.

For EACH slot, write the single best image-generation prompt and a negative prompt
so the image is: (1) unmistakably on-brand per the guideline — apply the palette
hexes, lighting, texture, and mood; (2) fit-for-purpose for its role and aspect;
(3) production-safe.

Hard rules:
- Backgrounds and hero images MUST be uncluttered with clear negative space for
  text overlaid later — no embedded words, letters, logos, UI chrome, or watermarks.
- No real recognizable faces unless the role is explicitly a portrait.
- Respect the guideline's avoid-list; match the aspect ratio's composition.
- Each prompt is concrete and visual; no meta commentary.
Output STRICT JSON: {"prompts": [{"slot_id","prompt","negative_prompt"}, ...]}
covering every slot you were given.
```

**User prompt:** serialize the brief (`image_style_prompt`, `mood`, `color_usage`, `texture_material`, `imagery`, `shape_language`, `composition`) + a numbered list of the asset_specs (slot_id, role, aspect_ratio, context). Strict `json_schema` response_format with `prompts: array of {slot_id, prompt, negative_prompt}` (all required, additionalProperties false). Parse → map by slot_id. Tolerate OpenRouter whitespace padding (use `resp.json()`).

## 4. Generation + restructure — `stages/generate_assets.py`

- New `async def fal_generate_image(*, prompt, negative_prompt, aspect_ratio, api_key, model, resolution, output_dir, slot_id, page_slot, image_type, http_client=None, timeout=180.0) -> AssetResult`:
  - Fold negative into prompt. POST to `https://fal.run/{model}` with `{prompt, aspect_ratio, num_images:1, resolution, output_format:"png"}` + `Authorization: Key {api_key}`.
  - 200 → `images[0].url` → download to `assets/{page_slot or 'report'}_{slot_id}.png` → `AssetResult(status="generated", path=…, prompt=…, negative_prompt=…)`.
  - failure → `AssetResult(status="failed", path=None, prompt=…, negative_prompt=…)` + the caller adds a warning.
- Aspect map: use each spec's `aspect_ratio` directly (values already valid fal enums: `3:4`, `16:9`); report-level texture/gradient use `3:4`.
- **Restructure `generate_assets`** to two passes:
  1. Walk pages + report-level: handle manifest-download + client-upload as today; **collect** generate-specs into a list (per-page `source_default=="generate"` + the 2 report-level), each `{slot_id, role/image_type, aspect_ratio, page_slot, context}` (context = `_page_text_preview(data)` for pages; fixed phrases for texture/gradient).
  2. `built = await build_image_prompts(design_brief=…, asset_specs=specs, api_key=openrouter_key, model=prompt_model, http_client=…)` if `openrouter_key and specs` else `{}`.
  3. For each spec: `pb = built.get(slot_id)`; `prompt, negative = (pb["prompt"], pb["negative_prompt"]) if pb else (_compose_prompt(style_prompt, subject, aspect, fallback=…), brief_negative)`. If `fal_key`: `result = await fal_generate_image(...)` → append (count `total_generated` or `total_failed`). Else: stub `AssetResult(status="stub_not_generated", path=None, prompt=prompt, negative_prompt=negative)` (+ `total_stubbed`).
- New `generate_assets` params (keyword): `openrouter_key`, `prompt_model`, `fal_key`, `fal_model`, `fal_resolution`.
- `AssetResult` dataclass + `AssetPlan` gain `total_generated: int = 0`. `AssetSummary` (models.py) gains `total_generated: int = 0`. `assemble_package` asset_summary + `/render` response include it.

## 5. main.py wiring

`/render` reads env and passes to `generate_assets`:
`openrouter_key=os.getenv("OPENROUTER_API_KEY")`, `prompt_model=os.getenv("OPENROUTER_PROMPT_MODEL","anthropic/claude-sonnet-4.6")`, `fal_key=os.getenv("FAL_KEY")`, `fal_model=os.getenv("FAL_IMAGE_MODEL","fal-ai/nano-banana-pro")`, `fal_resolution=os.getenv("FAL_IMAGE_RESOLUTION","2K")`. (`import os` already present.)

## 6. Error handling

| Failure | Behavior |
|---|---|
| No `openrouter_key` or prompt-builder fails | fall back to `_compose_prompt` concatenation; continue |
| No `fal_key` | stub (`stub_not_generated`) with the built prompt recorded — no crash |
| fal non-200 / download fail | `status="failed"` + warning; continue other assets |
| Any exception | caught per-asset; that asset → failed; pipeline continues |

`/render` stays non-blocking — images are best-effort; missing ones are flagged, never fatal.

## 7. Tests (no real network)

- `tests/test_build_image_prompts.py`: prompt assembly carries brief + specs; mock 200 → slot_id→prompt map; mock 500 → `{}`; no key → `{}`.
- `tests/test_generate_assets.py` (extend): with `fal_key` + mocked fal 200 → asset `status="generated"`, file written, `prompt` recorded, `total_generated` counted; mocked fal 500 → `failed`; no `fal_key` → `stub_not_generated` with prompt; prompt-builder mocked so no real OpenRouter call.
- `tests/test_assemble_package.py`: `asset_summary` includes `total_generated`.
- Guard + full suite stay green.

**Live validation (post-build):** one real `/onboard`-brief + one real Nano Banana Pro generation for an apex asset; show the saved image path + that it's a real PNG.

## 8. Scope
DO: the two files above + models `total_generated` + main wiring + tests. DON'T: change the brief/onboard contract; touch the renderer; alter the SVG/Stage-6 path.
