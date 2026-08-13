# DMC Renderer — Brand Tokens

How per-client brand styling flows from the n8n payload into rendered CSS.

**Source of truth fields:** see [`fixtures/apex_consulting_payload.json`](../fixtures/apex_consulting_payload.json) `brand_tokens` block.

---

## Required fields

These keys MUST be present in every request's `brand_tokens`. Missing → 400.

| Key | Type | Example | Notes |
|---|---|---|---|
| `brand_primary` | hex color `#rrggbb` | `"#1a1a2e"` | Display type, headlines, navy sidebar, primary text on light backgrounds. |
| `brand_accent` | hex color `#rrggbb` | `"#e94560"` | The coral. Fires sparingly. Coral-budget validator enforces ≤2 per page (cover/CTA: ≤3). |
| `brand_neutral_dark` | hex color | `"#0f0f1f"` | Deeper than primary — used for dark backgrounds when `primary` is itself dark. |
| `brand_neutral_mid` | hex color | `"#7a7a8c"` | Labels, captions, secondary text. **Note:** sometimes reads as faintly pink due to slight purple bias; if the brand wants clearly-neutral gray, use `#3d3d4a` or similar in section labels — handled at template level. |
| `brand_neutral_light` | hex color | `"#f5f5f7"` | Subtle backgrounds, page-fill behind imagery. |
| `font_heading` | font family name | `"Inter"` | Must resolve to a `@font-face` declared in [FONT_LOADING.md](FONT_LOADING.md). |
| `font_body` | font family name | `"Source Serif Pro"` | Must resolve to a `@font-face`. **Note:** Apex sends "Source Serif Pro" but the renderer ships "Source Serif 4" — see § Font name normalization below. |
| `qr_target_url` | URL | `"https://apex-consulting.ai/"` | The URL encoded in every QR code on the report. Single QR target per report — case study QR, CTA QR, and any future QR-bearing component all encode the same URL. |
| `company_name_short` | string | `"Jousef"` | Founder's name or company short form. Appears in headers, footers, and the case-study sidebar `KUNDE` field when no per-case `kunde.name` is provided. |
| `company_url_display` | string | `"apex-consulting.ai"` | Display version of the URL (without `https://`). Used in CTA bands and footer rules. |

Validation: each hex must match `^#[0-9a-fA-F]{6}$`. URLs must be `http(s)://`. Font names are passed through verbatim (matched against bundled `@font-face` at render).

---

## Optional fields

| Key | Type | Default | Notes |
|---|---|---|---|
| `logo_dark_url` | URL | `null` → text-wordmark fallback | Logo for use on light backgrounds. If present, fetched and rendered as an image. If absent (or fetch fails), template falls back to a typographic wordmark using `company_name_short` + `brand_primary`. |
| `logo_light_url` | URL | `null` → text-wordmark fallback | Same as above, for dark backgrounds (e.g. on the navy sidebar). |
| `founder_full_name` | string | `""` | Used in the cover page's author byline and the about page's portrait caption. Empty string is valid and renders as just the role/company. |
| `founder_role` | string | `""` | Pairs with `founder_full_name`. |

Optional means **the key may be absent or empty-string**; the renderer treats both identically. Apex currently sends both founder fields as `""` because Jousef hasn't decided on a final byline format.

---

## Merge semantics

```python
DEFAULTS = {
    "brand_primary":       "#1a1a2e",  # navy
    "brand_accent":        "#e94560",  # coral
    "brand_neutral_dark":  "#0f0f1f",
    "brand_neutral_mid":   "#7a7a8c",
    "brand_neutral_light": "#f5f5f7",
    "font_heading":        "Inter",
    "font_body":           "Source Serif 4",
    "qr_target_url":       "",         # required-but-validated; default never used in practice
    "company_name_short":  "",
    "company_url_display": "",
    "logo_dark_url":       None,
    "logo_light_url":      None,
    "founder_full_name":   "",
    "founder_role":        "",
}

def merge_brand_tokens(request_tokens: dict) -> dict:
    out = DEFAULTS.copy()
    out.update(request_tokens)             # top-level shallow merge
    return out
```

**Top-level shallow merge.** Per-client tokens override defaults; missing keys fall back. No nested merging (no key in `brand_tokens` is currently an object, so this isn't a concern). No deep diff or schema-driven merge — keep it boring.

---

## Use in templates

Templates emit CSS custom properties at the top of every page's stylesheet:

```css
/* base.css.j2 — emitted from brand_tokens */
:root {
  --brand-primary:        {{ brand_tokens.brand_primary }};
  --brand-accent:         {{ brand_tokens.brand_accent }};
  --brand-neutral-dark:   {{ brand_tokens.brand_neutral_dark }};
  --brand-neutral-mid:    {{ brand_tokens.brand_neutral_mid }};
  --brand-neutral-light:  {{ brand_tokens.brand_neutral_light }};
  --font-heading: {{ brand_tokens.font_heading | json_quote }};
  --font-body:    {{ brand_tokens.font_body    | json_quote }};
}
```

Then every component CSS references the vars:

```css
h1, h2.fallstudie-headline { font-family: var(--font-heading); color: var(--brand-primary); }
.coral { color: var(--brand-accent); }
.label-small-caps { color: var(--brand-neutral-mid); }
```

Brand-specific overrides (e.g. Apex's Vollkorn-instead-of-Inter for display type) are handled by setting `font_heading: "Vollkorn"` in `brand_tokens` — no per-client CSS branches.

---

## Font name normalization

Writer/n8n sends font names like `"Source Serif Pro"` but the bundled font face is named `"Source Serif 4"` (the modern release). The renderer normalizes on intake:

```python
FONT_ALIASES = {
    "Source Serif Pro": "Source Serif 4",  # legacy → current
    "Source Sans Pro":  "Source Sans 3",    # if needed
}

def normalize_font_name(name: str) -> str:
    return FONT_ALIASES.get(name, name)
```

If the normalized name still doesn't match any bundled `@font-face`, the renderer logs a warning and the template falls back to whatever the parent CSS selector resolves to (typically the OS default). Renders are produced but operators see the warning in Railway logs.

---

## Adding a new brand

1. Inspect the client's brand guide. Map their colors to the 5 brand color slots above. If they have more than 5 distinct brand colors, pick the 5 most-used; the renderer doesn't have a sixth slot.
2. Pick `font_heading` and `font_body`. If neither matches a bundled face, **add the TTF files to `dmc-renderer/fonts/`** and declare the `@font-face` in `base.css.j2`. See [FONT_LOADING.md](FONT_LOADING.md) for the procedure.
3. If logos are provided, upload to a publicly fetchable URL (Drive `uc?id=...` works; CDN is preferred for production). Set `logo_dark_url` and `logo_light_url`.
4. Test render the canonical Apex fixture **with this new brand_tokens** swapped in. Verify the coral budget validator still passes (1 fire/page is the discipline regardless of client).
5. Run the [reference parity check](ARCHITECTURE.md#13-phase-3-preview-template-plan---not-implemented-yet) on the new render to make sure the visual signature transfers.

---

## What brand_tokens does NOT control

These are renderer-internal and stay constant across all clients:

- Baseline grid (14 pt unit)
- Page format (always A4 portrait until a client requires Letter)
- Margin geometry (`16mm 18mm 14mm 18mm` default)
- Section header pattern (small caps Inter 700 with brand_neutral_mid)
- Stat block layout (3 columns, ratios fixed)
- Footer CTA band geometry
- QR module size + error correction level
- Coral budget rules (≤2 per page, except ST-01 / ST-03)

When a client needs a different baseline grid or different margins, that's a new template variant, not a new brand_tokens key.
