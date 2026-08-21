> **STALE: DO NOT ORIENT FROM THIS FILE.** It describes an earlier frame and is wrong on load-bearing facts. Authoritative current sources: `context.md`, `docs/superpowers/CURRENT-STATE.md`, `richard-grammar-v2.md`. Corrections that bite: the engine is **Chromium print-to-PDF plus Ghostscript flatten**, NOT WeasyPrint (legacy `--engine weasyprint` fallback only); bundled fonts are **Source Serif 4 and Source Sans 3** variable faces, NOT Montserrat; the renderer consumes a **multi-page `resolved_package.json` via `--package-dir`**, NOT a single-page GEVA fixture. (Banner added 2026-06-21.)

# DMC Report PDF Renderer — Production PRD

**Status:** Draft for validation
**Author:** Research conducted against `aerztepartner_v0.2`, `Buchagentur`, `Alexander Boss`, `Niklas Niemeyer` reference PDFs + Master System v1 + Design System v2
**Decision:** Build on **HTML/CSS Paged Media → WeasyPrint → standard PDF 1.7**, deployed as a Railway-hosted Docker service

> **Distribution model:** DMC reports are distributed digitally (email attachments, download links, landing-page embeds) — **not printed**. All print-specific requirements (CMYK, ICC profiles, PDF/X-3, bleed, crop marks) are out of scope. Output is sRGB PDF 1.7.

---

## 0 · Executive summary

A Railway-hosted Docker service that consumes a single JSON payload (`report` + `brand` + `assets`) and returns a digital PDF file matching the visual quality of the reference reports.

The reference reports were originally produced in Adobe InDesign 21.2 / Affinity 3.0.3. This system reproduces their visual character via HTML/CSS Paged Media + the WeasyPrint renderer. Because output is digital-only, we use WeasyPrint (free, no license cost) as the sole production renderer; Paged.js drives live preview during development.

The system is **lean** because templates are written once and reused across all clients — every customer is a JSON file plus an asset folder, not a design project.

---

## 1 · Phase 3 findings — cross-reference: spec ↔ reality

The Master System defines 37 page types (ST-01 … ST-37). The reference PDFs use only ~14 of them. The PRD reflects what reports actually contain, not the full spec.

### 1.1 Page-types observed across all 4 reports

| ST | Name | Used in | Notes |
|---|---|---|---|
| ST-01 | Cover | all 4 | Hero portrait + headline + teaser bullets — universal |
| ST-02 | Ausblick / Editorial | all 4 | Text-heavy intro page — universal |
| ST-05 | Autorität / Über-Uns | all 4 | Team photo + stats + Trustpilot + "bekannt aus" — **richer than spec** (combines ST-05 + ST-25 + ST-26 + ST-31 visually) |
| ST-06 | Mechanismus-Einführung | all 4 | 5–7 numbered steps, sometimes with flow diagram. nikl splits it across 2 pages. |
| ST-07A | Fallstudie Einzelseite | all 4, ×3 | Repeating template: portrait + Ausgangs/Ziel/Lösung/Ergebnis + big number panel |
| ST-07B | Fallstudien-Gegenseite | all 4 | **Three sub-variants**: (a) comparison-table, (b) chart, (c) text + small diagram |
| ST-08 | FAQ / Einwandvorwegnahme | all 4 | 4–6 numbered objection-quote boxes |
| ST-09 | Status-Quo-Spiegel | all 4 | **Two visual variants**: (a) numbered 6–8 row symptom list, (b) 6-tile icon grid |
| ST-14 | Irrglauben-Block | all 4 | **Spec says 3, reports show 5–7** — deviation, see §1.3 |
| ST-21 | Vergleichsmatrix | nikl, alex | Two-column "schlecht / gut" comparison |
| ST-22 | Prozess-Ablauf | all 4 | 4–6 Schritt cards, numbered, sometimes split across columns |
| ST-25 | Zahlen-Seite | aerz, alex | "At Year 10/25/50 → 200k/500k/1M" stat-card row |
| ST-26 | Testimonial-Cluster | all 4 | **Spec says 3–4, reports show 6–8 reviews** — deviation |
| ST-31 | Logo-Wand | all 4 | 9–13 client logos in grid; sometimes embedded in ST-05 |
| ST-03 | Rückseite | all 4 | Single-page back: logo, body, big URL, QR — universal |

**Custom page-type observed but NOT in spec:** "Fazit" — a transition close before the back-cover. Combines emotional hook + bridge sentence + soft-CTA bar. Appears in nikl p16, alex p9 (left), aerz p9 (left), buch p8 (right). Treat as a new page type, **ST-FAZIT**, in the implementation.

### 1.2 Page-types defined in spec but NOT used in any reference report

ST-04, ST-10, ST-11, ST-12 (Alltagsmoment), ST-13, ST-15, ST-16, ST-17, ST-18, ST-19, ST-20, ST-23, ST-24, ST-27, ST-28, ST-29, ST-30, ST-32, ST-33, ST-34, ST-35, ST-36, ST-37, ST-07C.

These are **Tier 3 (later)** — build only when a report actually requires one.

### 1.3 Key deviations between spec and reality

| Spec says | Reports show | Treatment in PRD |
|---|---|---|
| ST-14 = "Irrglauben-Dreier-Block" (3 elements) | 5–7 Irrglauben in all reports | Template accepts variable count 3–8; spec to be updated |
| ST-26 = "3–4 Zitate" testimonial-cluster | 6–8 Trustpilot review-cards | Template accepts variable count 4–9 |
| ST-05 = author/team page only | also embeds stat blocks + Trustpilot widget + logo strip | Template is composite — slot-array allows mixing sub-components |
| Slot-plan 16/20/24/28 pages | 3 of 4 reports exported as 11-page 2-up landscape spreads (= 20 logical A4) | Renderer supports **single-page A4** AND **2-up imposition** export modes |
| "Cover ~600 chars" | Buchagentur cover ≈ 1228 chars (incl. teaser bullets) | Cover text-budget should be 800–1400 chars when teaser-bullets included |
| Spec mentions "InDesign as primary" | Reality: 3× InDesign + 1× Affinity Publisher | Confirms multiple producer-tools — output format (PDF) is the only stable contract |

### 1.4 Visual primitives library (the reusable building blocks)

Every page composes from this set of ~12 primitives. Builds the entire system:

1. **Stencil number** (`01`, `02`, `03`) — 60–120pt, used in mechanism steps, FS panels, objection cards
2. **Numbered text-row** — number + headline + body (+ optional icon)
3. **Stat-block** — big number + tiny label, used 3-up or 4-up in a row
4. **Comparison table** — 2 columns "schlecht / gut" with check/cross icons
5. **Pullquote bar** — large quote in accent color, sometimes with mini-portrait
6. **Trustpilot review card** — avatar + name + 5-star + body + date
7. **Logo wall** — 3–5-col grid of grayscale logos
8. **Dark CTA bar** — full-width footer with bright URL + QR
9. **Hero photo** — full-bleed image with dark gradient overlay + light text
10. **Numbered icon-tile** — 4–6 icon+title+body grid
11. **Mini chart** (line / bar / horizontal-bar) — 1 accent color vs greys
12. **Process step-card** — numbered card with title + body, sometimes with icon

These are CSS components built once; templates compose them.

### 1.5 Brand snapshot per report (verified by pixel sampling)

| Report | Primary | Accent | Neutral-Dark | Neutral-Bg | Headline font | Body font |
|---|---|---|---|---|---|---|
| aerz | `#1A2B5C` (deep navy) | `#E6B85C` (gold) | `#2B2B2B` | `#F5F1EA` cream | **Merriweather** (serif) | **Lato** Reg/Bold |
| buch | `#022D2D` (deep teal) | `#5FB6A8` (sea green) | `#2B2B2B` | `#F1ECE0` cream | **Merriweather** (serif) | **Instrument Sans** + Inter |
| alex | `#0E2540` (navy) | `#F5C518` (yellow) | `#2B2B2B` | `#FFFFFF` | **Source Sans 3 Black** + Bebas Neue display | **Source Sans 3** Reg/Semi |
| nikl | `#0E0E10` (charcoal) | `#FF7A1A` (orange) + `#2A6CD9` (blue) | `#FFFFFF` (light text on dark) | `#0E0E10` | **Azo Sans** Bold (commercial) + Minion Pro accents | **Source Sans Pro** Reg/Semi |

**Font licensing note:** Azo Sans is commercial — a client wanting that exact look must supply a licensed file or accept Montserrat-ExtraBold as a free substitute. All other fonts in observed reports are SIL-OFL or Adobe-bundled.

---

## 2 · Phase 4 findings — feasibility per template

All Tier-1 templates are reproducible in HTML/CSS Paged Media with WeasyPrint.

| Template | CSS features required | Complexity | Risk |
|---|---|---|---|
| Cover (ST-01) | `@page :first`, full-page background image, mixed-color headline, teaser-bullet column | Medium | Photo focal-point; mitigate via pre-cropped 3:4 hero asset |
| Ausblick (ST-02) | 2-column flow, sidebar panels, small portrait, drop-cap optional | Low | Variable copy length |
| Über-Uns (ST-05 composite) | Grid layout, embedded logo strip, Trustpilot widget mock | Medium | Variable stat-block count (3 vs 6) |
| Problem-Liste (ST-09 var. A) | Numbered ordered-list, custom counter styles, large stencil numerals | Low | Long quotes overflowing |
| Problem-Tile (ST-09 var. B) | CSS Grid 3×2 or 2×3 tiles, SVG icons | Low | None significant |
| Irrglauben (ST-14 expanded) | 5–7 quote-boxes on dark panel, numbered, large stencil numerals | Low | Variable count 3–8 |
| Mechanismus (ST-06) | Numbered cards, optional flow-diagram (SVG inline) | Medium | Diagram rendering — generate SVG before render |
| Fallstudie (ST-07A) | 2-column with right-side dark panel, big stencil number, 3 stat blocks, photo | Medium | Photo aspect-ratio variability |
| Gegenseite (ST-07B) — comparison | 2-column table, check/cross icons, alternating row colors | Low | Variable row count |
| Gegenseite (ST-07B) — chart | Inline SVG bar/line chart, paired with text and pullquote | Medium | SVG generation step required |
| Gegenseite (ST-07B) — text+photo | 2-column with embedded laptop image + body | Low | None |
| Prozess (ST-22) | 4–6 numbered cards in 2-col grid or stacked | Low | None |
| FAQ / Einwand (ST-08) | 4–6 numbered Q+A cards, dark CTA bar at bottom | Low | None |
| Trust-Wall reviews (ST-26 expanded) | 6–8 cards in 2–3 col grid, embedded star SVG | Low | Avatar fallback when missing |
| Logo wall (ST-31) | 3–5 col grid of grayscale (filter: grayscale) logos | Low | Logos must be uniform-height, transparent PNG/SVG |
| Fazit (custom ST) | Full-page background photo + serif headline + body + CTA bar + QR | Medium | None significant |
| Rückseite (ST-03) | Background tint, big URL display, QR code, brand mark | Low | QR generation step |

### 2.1 Renderer choice — WeasyPrint, period

- **Production: WeasyPrint** — free, Python-based. Handles all CSS Paged Media features needed for digital PDF output: `@page` rules, named pages, multi-column, page breaks, custom counters, running headers/footers, generated content. Excellent text shaping via HarfBuzz. Outputs sRGB PDF 1.7. No license cost.
- **Dev/preview: Paged.js** — JavaScript polyfill running in-browser. Same HTML/CSS works in both, so what you see in preview is what WeasyPrint produces.

Prince was originally considered for its CMYK / ICC / bleed / crop-mark capabilities. None apply to digital distribution, so Prince is dropped — saving the €500/yr server license and removing the "which renderer?" decision entirely.

---

## 3 · Phase 5 findings — loophole + risk catalog

### 3.1 Text overflow (#1 risk)
- **Cause:** Copy generator emits 1800 chars; template fits 1200.
- **Mitigation:** Already enforced upstream by Zeichenlimits per ST. Add a **render-time overflow detector**: WeasyPrint logs `WARNING: ...overflow on page N...` when content exceeds its frame. Capture and gate on it.
- **On detection:** fail the build with `{page, st, expected_chars, actual_chars}` and route back to Agent 4.
- **Hard fallback:** if Agent 4 cannot trim after 2 retries → apply CSS class `.shrink-fit` (10pt → 9.5pt body) on offending page only and re-render. If still overflows → human escalation.

### 3.2 Image handling
- **Aspect-ratio mismatch:** AI image is 1:1 but template wants 3:4 portrait → focal-point loss.
- **Mitigation:** Each template declares required aspect ratios in JSON schema. Pre-render validator runs on every image; if mismatch >5%, route back to image agent with target ratio. If image is **only** wrong by <5%, use `object-fit: cover` with `object-position: top center` (configurable per-template).
- **Resolution:** Templates require min 1500px on the long edge. Validator rejects below.
- **Missing image:** Render with placeholder SVG + flag in QA report; do not silently ship.

### 3.3 Font licensing
- **Free / OFL fonts:** Merriweather, Lato, Source Sans 3, Source Sans Pro, Source Serif 4, Instrument Sans, Inter, Montserrat, Bebas Neue, Roboto, Open Sans — all safe to bundle in the Docker image.
- **Restricted:** Azo Sans (nikl), Minion Pro (Adobe-bundled, restricted server use). Treat as **bring-your-own-font**: client supplies licensed `.otf`/`.ttf` and we mount it at render time.
- **Default substitution map:** `Azo Sans → Montserrat ExtraBold`, `Minion Pro → Source Serif 4`, `Helvetica/Arial → Inter`. Apply silently with a warning in `x-warnings`.

### 3.4 Color
- Output is sRGB throughout. Default for digital-display PDFs.
- AI-generated images are sRGB; client logos may be sRGB or untagged — normalize to sRGB tag at fetch time.
- No color-space conversion step needed.

### 3.5 Variable page counts (16 / 20 / 24 / 28)
- The slot-plan is data-driven: `report.pages = [{type, data}, ...]`.
- For digital-only output, page count can be any positive integer; the 4-multiple rule from the Master System (a print-imposition convention) becomes a content-style choice rather than a hard requirement.
- We still default to 16/20/24/28 because the Master System slot plans assume those counts.
- Validator: warns (not fails) if `len(pages) % 4 != 0`.

### 3.6 Case-study count variance (3 vs 8)
- Templates accept `case_studies: []` array; renderer iterates and pairs each ST-07A with its corresponding ST-07B sub-variant.
- If `len(case_studies) < 2` → block render (spec rule from Master System Module 3.1).
- If `len(case_studies) > 4` → spread across additional pages + warn.

### 3.7 Internationalization / Unicode
- All German text — extensive use of ä, ö, ü, ß, €, °. Confirmed in PDF text extraction.
- **Risk:** TrueType fonts may not include all glyphs. Pre-render glyph-coverage check against text content; fail with diagnostic if any glyph missing.
- **Hyphenation:** WeasyPrint uses Pyphen with `lang="de"` on `<html>`; produces correct German hyphenation.
- **Quotation marks:** `„text"` (low-9 / high-9) — confirm in copy generator output.

### 3.8 QR codes
- Generated dynamically per client via `qrcode` Python lib. Output SVG inlined in HTML.
- Min display size: 30×30mm on screen (not the 40mm print minimum from Master System ST-03).
- Error-correction level: M (15%).
- Embed URL with UTM params: `?utm_source=dmc-report&utm_medium=pdf&utm_campaign={client_slug}`.

### 3.9 Railway hosting / Docker constraints
- **Image size budget:** ~250–350MB realistic (WeasyPrint + Python + fonts + Node).
- **Memory:** WeasyPrint typically uses 150–300MB per render of a 20-page report; Railway 512MB plan is **workable**, 1GB plan ($5/mo) recommended for headroom.
- **Render time:** ~5–10 sec per report on 1 vCPU.
- **Concurrency:** Single instance can serve ~6 concurrent renders; for higher load, scale horizontally.
- No license keys, no third-party API calls during render.

### 3.10 Other risks
- **PDF metadata leakage:** strip `producer` / `creator` from output.
- **Asset cache invalidation:** if client logo updates, ensure CDN/Airtable URL is fingerprinted, not cached forever.
- **ST numbering drift:** mapping differs between Master System and current implementation; lock the canonical mapping in code.

---

## 4 · System architecture

### 4.1 Service shape

```
n8n workflow ─POST /render─→  Renderer service (Railway)  ─→  PDF (binary) → n8n
                                       │
                                       ├─ HTML template engine (Nunjucks/Handlebars)
                                       ├─ Brand-token CSS injector
                                       ├─ SVG generator (charts, QR codes)
                                       ├─ Image preprocessor (validate + sRGB normalize)
                                       └─ WeasyPrint → PDF
```

### 4.2 Input schema (POST `/render` body)

```jsonc
{
  "report": {
    "meta": {
      "client_slug": "buchagentur",
      "report_id": "buchagentur-2026-01",
      "lang": "de",
      "page_format": "A4",
      "export_mode": "single-page" | "two-up-spread",  // default: single-page
      "page_count_target": 20  // 16 | 20 | 24 | 28 — soft target
    },
    "pages": [
      {
        "slot": 1,
        "type": "ST-01",
        "data": { "headline": "...", "subheadline": "...", "teaser_bullets": [...], "author": {...}, "fallstudien_preview": [...] }
      },
      {
        "slot": 10,
        "type": "ST-07A",
        "data": {
          "fallstudie_number": 1,
          "ergebnis_headline": "342.000 € in 8 Wochen",
          "kurzportraet": "...",
          "ausgangsproblem": "...",
          "wendepunkt": "...",
          "loesung": "...",
          "ergebnis": [{"label":"Umsatz vorher","value":"28.000 €"}, ...],
          "kunde_foto_url": "https://...",
          "kunde_name": "Michael Wohlfart",
          "kunde_funktion": "Geschäftsführer Karosseriebooster",
          "kunde_url": "https://kanzlerbooster.de",
          "pullquote": "Wir nutzen das Buch als Leadmagnet ..."
        }
      }
      // … additional pages
    ]
  },
  "brand": {
    "client_name": "Buchagentur.de",
    "logo_url": "https://airtable.../buchagentur-logo.svg",
    "primary": "#022D2D",
    "accent": "#5FB6A8",
    "neutral_dark": "#2B2B2B",
    "neutral_bg": "#F1ECE0",
    "fonts": {
      "headline": "Merriweather",
      "body": "Instrument Sans",
      "display": "Bebas Neue"
    },
    "qr_target_url": "https://buchagentur.de/erstgespraech",
    "trustpilot": {"score": 4.8, "count": "84 Bewertungen"}
  },
  "assets": {
    "manifest": [
      { "id": "cover_hero", "url": "...", "type": "image", "expected_ratio": "3:4" },
      { "id": "fs1_portrait", "url": "...", "type": "image", "expected_ratio": "1:1" },
      { "id": "diagram_d01", "url": "...", "type": "svg|image", "expected_ratio": "16:9" }
    ]
  },
  "render_options": {
    "quality": "draft" | "screen"   // default: screen
  }
}
```

### 4.3 Output

- Default: binary PDF (Content-Type: `application/pdf`, ~2–6 MB per 20-page report)
- Optional: signed S3/Cloudflare-R2 URL (set `?return=url` query param)
- Headers: `X-Render-Time-Ms`, `X-Page-Count`, `X-Renderer-Version`, `X-Warnings` (JSON of any non-fatal issues)

### 4.4 API contract

| Method | Path | Purpose |
|---|---|---|
| POST | `/render` | Render a report → PDF |
| POST | `/preview` | Render single page as PNG (for review) — body: `{report, brand, slot}` |
| POST | `/validate` | Dry-run: check schema + assets + overflow risk; no PDF output |
| GET | `/health` | Liveness; returns version + renderer status |
| GET | `/templates` | List available template ST IDs and required schema per type |

### 4.5 Hosting

- **Railway** Docker service, 1GB RAM plan recommended (512MB workable for low concurrency)
- Persistent disk: NOT required (renders are stateless)
- Optional: attach Cloudflare R2 bucket for output storage if `?return=url`
- Env vars: `PORT`, `LOG_LEVEL`, `MAX_CONCURRENT_RENDERS`

---

## 5 · Template inventory

### Tier 1 — required for MVP

| # | Template | ST | Complexity |
|---|---|---|---|
| 1 | Cover | ST-01 | Medium |
| 2 | Ausblick | ST-02 | Low |
| 3 | Über-Uns composite | ST-05+ | Medium |
| 4 | Problem (numbered + tile variants) | ST-09 a/b | Low |
| 5 | Irrglauben (variable 3–8) | ST-14 | Low |
| 6 | Mechanismus | ST-06 | Medium |
| 7 | Fallstudie A | ST-07A | Medium |
| 8 | Gegenseite — 3 sub-variants | ST-07B a/b/c | Medium |
| 9 | Prozess | ST-22 | Low |
| 10 | FAQ / Einwand | ST-08 | Low |
| 11 | Trust-Wall (reviews + logos) | ST-26 + ST-31 | Low |
| 12 | Fazit | ST-FAZIT (new) | Medium |
| 13 | Rückseite | ST-03 | Low |

### Tier 2 — needed for full coverage (build after MVP works)

| # | Template | ST | Complexity |
|---|---|---|---|
| 14 | Vergleichsmatrix Alt vs. Neu | ST-21 | Low |
| 15 | Zahlen-Seite (3-up stat row) | ST-25 | Low |
| 16 | Atemseite | ST-32 | Low |
| 17 | Vorher-Nachher | ST-24 | Low |
| 18 | Charts spread (4 charts) | ST-08-spread | Medium |

### Tier 3 — edge cases, build only on demand

ST-04, ST-10, ST-11, ST-12, ST-13, ST-15, ST-16, ST-17, ST-18, ST-19, ST-20, ST-23, ST-27, ST-28, ST-29, ST-30, ST-33, ST-34, ST-35, ST-36, ST-37, ST-07C.

### Component primitives (built once, used everywhere)

| Component | File |
|---|---|
| StencilNumber | `components/StencilNumber.html` |
| NumberedRow | `components/NumberedRow.html` |
| StatBlock | `components/StatBlock.html` |
| CompareTable | `components/CompareTable.html` |
| Pullquote | `components/Pullquote.html` |
| ReviewCard | `components/ReviewCard.html` |
| LogoWall | `components/LogoWall.html` |
| CtaBar | `components/CtaBar.html` |
| HeroPhoto | `components/HeroPhoto.html` |
| IconTile | `components/IconTile.html` |
| MiniChart | `components/MiniChart.html` |
| ProcessCard | `components/ProcessCard.html` |
| QrCode | `components/QrCode.html` |

---

## 6 · Brand-token system

### 6.1 CSS custom properties (one source of truth)

Loaded into `:root` per render, derived from `brand` JSON:

```css
:root {
  /* Colors */
  --color-primary:        #022D2D;
  --color-accent:         #5FB6A8;
  --color-accent-2:       #2A6CD9;   /* optional, for nikl-style 2-accent */
  --color-neutral-dark:   #2B2B2B;
  --color-neutral-mid:    #6B6B6B;
  --color-neutral-light:  #E5E0D5;
  --color-bg:             #F1ECE0;
  --color-bg-dark:        #022D2D;
  --color-text-on-light:  #2B2B2B;
  --color-text-on-dark:   #FFFFFF;

  /* Typography */
  --font-headline:        "Merriweather", "Source Serif 4", serif;
  --font-body:            "Instrument Sans", "Source Sans 3", sans-serif;
  --font-display:         "Bebas Neue", "Montserrat", sans-serif;
  --font-mono:            "JetBrains Mono", monospace;

  /* Type scale (pt — WeasyPrint uses these as logical px-equivalents in PDF) */
  --fs-h1:                36pt;
  --fs-h2:                22pt;
  --fs-h3:                16pt;
  --fs-body:              10.5pt;
  --fs-caption:           8pt;
  --fs-stat-large:        56pt;
  --fs-stencil:           96pt;

  /* Layout */
  --margin-outer:         18mm;
  --margin-inner:         18mm;
  --margin-top:           20mm;
  --margin-bottom:        18mm;
  --gutter:               6mm;

  /* Brand assets */
  --logo-url:             url("...");
  --watermark-url:        url("...");
}
```

### 6.2 Defaults & fallbacks

Every brand token has a default. If a brand JSON is missing a key, the renderer uses the default (logged as a warning, not an error). Schema validation enforces at minimum: `primary`, `accent`, `neutral_dark`, `logo_url`, `qr_target_url`.

### 6.3 Font availability

Pre-loaded in Docker image at `/usr/share/fonts/dmc/`:
- Merriweather (Reg/Bold/Black + Italic)
- Source Sans 3 (Light/Reg/Semi/Bold/Black)
- Source Sans Pro (Reg/Semi/Bold)
- Source Serif 4 (Reg/Bold)
- Lato (Light/Reg/Bold/Heavy)
- Instrument Sans (Reg/Bold)
- Inter (Reg/Bold)
- Montserrat (Reg/Bold/ExtraBold)
- Bebas Neue (Regular)
- Roboto (Reg/Bold)

Custom client font: mounted at render time from `brand.fonts.custom_font_url` if present, registered via `@font-face` in CSS injector.

---

## 7 · Dynamic content handling

### 7.1 Text overflow strategy — fail-and-route-back primary, auto-shrink secondary

```
1. Render PDF normally
2. Inspect WeasyPrint log for overflow warnings
3. If overflow detected:
   a. Capture {page, st, expected_chars, actual_chars} → return as warning
   b. Renderer returns 422 with diagnostic; n8n routes to Agent 4 for trim
4. If Agent 4 returns same/longer copy after retry:
   a. Apply CSS class `.shrink-fit` (10pt → 9.5pt body) on offending page only
   b. Re-render
5. If still overflow:
   a. Hard-fail; require human intervention
```

### 7.2 Image slot system

Each template declares its image slots in `template.schema.json`:

```jsonc
{
  "id": "ST-07A",
  "image_slots": [
    { "id": "kunde_foto", "required": true, "ratio": "1:1", "min_px": 800,  "fallback": "placeholder_avatar.svg" },
    { "id": "screenshot", "required": false, "ratio": "16:9", "min_px": 1200 }
  ]
}
```

Renderer validates assets against these before invoking WeasyPrint. Failures produce structured warnings.

### 7.3 Charts and stat-boxes

- **Stat-boxes:** pure CSS — no image generation needed.
- **Mini bar/line charts:** generated as inline SVG via D3/Vega-Lite at render time, fed by `data` array. Strict color rules: 1 accent line + grey. No legends.
- **Big charts** (aerz p8-style): same pipeline, larger viewport. SVG inline keeps file size small and renders crisp at any zoom level.
- **No raster chart images** — keeps PDFs vector and lighter.

### 7.4 Variable counts

| Element | Variable | Range | Behavior |
|---|---|---|---|
| Case studies | `report.fallstudien` | 2–5 | <2 fail; >5 split across spreads |
| Irrglauben | `page.data.items` | 3–8 | template auto-grids |
| Trustpilot reviews | `page.data.reviews` | 4–9 | template auto-grids 2-col or 3-col |
| Logos | `page.data.logos` | 6–18 | grid auto-flows |
| Mechanism steps | `page.data.steps` | 3–7 | numbered list flows |
| Stat blocks per page | `page.data.stats` | 3–4 | row of equal-width blocks |

Each template specifies min/max in its schema; validator enforces.

---

## 8 · Rendering pipeline

```
1. n8n receives: trigger from Airtable "report status = ready-to-render"
2. n8n posts JSON to Renderer:  POST /render { report, brand, assets, render_options }
3. Renderer:
   3.1  Validate JSON against schema  (zod)
   3.2  For each asset.url: fetch → cache locally → validate dimensions/format → normalize sRGB tag
   3.3  Generate dynamic SVGs (charts, QR codes)
   3.4  Inject brand tokens into base.css
   3.5  For each page in report.pages:
        - Look up template by ST id
        - Render template via Nunjucks with page.data
        - Append rendered HTML to <main>
   3.6  Compose final HTML doc with @page rules, fonts, brand CSS
   3.7  Run WeasyPrint:  weasyprint index.html /tmp/out.pdf
   3.8  Parse WeasyPrint log for warnings; collect into x-warnings
   3.9  Strip identifying metadata (producer/creator)
   3.10 Return binary PDF or upload to R2 + return URL
4. n8n receives PDF; writes to Airtable attachment field; notifies Slack
5. (Failure path) any 4xx/5xx → n8n routes to error queue + retries Agent 4 trim if 422 overflow
```

### 8.1 Renderer

WeasyPrint is the only renderer. Paged.js drives in-browser preview during template development; both consume the same HTML/CSS so previews are faithful.

---

## 9 · n8n integration

### 9.1 HTTP Request node config

| Field | Value |
|---|---|
| Method | `POST` |
| URL | `https://renderer.up.railway.app/render` |
| Authentication | Header Auth: `Authorization: Bearer ${RENDERER_API_KEY}` |
| Send Headers | `Content-Type: application/json` |
| Send Body | JSON, fully assembled in upstream "Build payload" node |
| Response | Binary file (`Response Format: File`), filename: `{{$json.report.meta.report_id}}.pdf` |
| Timeout | 60s |
| Retry on fail | 2× with 5s backoff |

### 9.2 Build-payload node (Function node before HTTP Request)

Pulls from Airtable:
- `Reports` table → report meta + pages JSON
- `Clients` table → brand tokens (color, fonts, logo URL, CTA URL)
- `Assets` table → image manifest with public URLs

Returns the full `{report, brand, assets, render_options}` payload.

### 9.3 Response handling

- Success (`200`): write PDF to Airtable Attachment field; post Slack notification with download link; mark `status = rendered`.
- Validation error (`400`): write error to Airtable `render_errors` field; mark `status = render-failed`; alert.
- Overflow (`422`): parse warning JSON; identify offending page; trigger Agent 4 retry sub-workflow.
- Server error (`5xx`): retry up to 2×; if still failing → human escalation.

---

## 10 · File & folder structure

```
renderer/
├── Dockerfile
├── docker-compose.yml          (for local dev)
├── package.json                (Node 20 + TypeScript)
├── tsconfig.json
├── README.md
├── src/
│   ├── server.ts               (Express/Fastify HTTP)
│   ├── render.ts               (orchestrator)
│   ├── schema/
│   │   ├── report.schema.ts    (zod)
│   │   ├── brand.schema.ts
│   │   └── pages/              (per-ST schemas)
│   │       ├── ST-01.ts
│   │       ├── ST-02.ts
│   │       └── …
│   ├── renderers/
│   │   └── weasyprint.ts       (thin wrapper around WeasyPrint subprocess)
│   ├── assets/
│   │   ├── fetch.ts
│   │   └── validate.ts
│   ├── svg/
│   │   ├── chart.ts            (d3-node)
│   │   └── qr.ts               (qrcode lib)
│   ├── templates/
│   │   ├── base.html
│   │   ├── base.css
│   │   ├── pages/
│   │   │   ├── ST-01.html
│   │   │   ├── ST-02.html
│   │   │   └── …
│   │   └── components/
│   │       ├── StencilNumber.html
│   │       ├── NumberedRow.html
│   │       └── …
│   └── tokens/
│       └── default-brand.css
├── fonts/
│   ├── merriweather/
│   ├── source-sans-3/
│   └── …
├── tests/
│   ├── fixtures/
│   │   ├── buchagentur.report.json
│   │   ├── buchagentur.brand.json
│   │   └── …
│   ├── integration/
│   └── visual/                 (image-diff against reference PDFs)
└── scripts/
    ├── extract-from-airtable.ts
    └── validate-fonts.sh
```

### Naming conventions

- Templates: `ST-01.html`, `ST-07A.html`. ST IDs are canonical.
- CSS classes: BEM-ish, `.cover`, `.cover__headline`, `.fs-card__stencil-number`
- Brand tokens: `--color-primary`, `--font-headline`, `--fs-h1` (CSS custom properties only)
- Asset cache: `/tmp/dmc-cache/{client_slug}/{asset_id}.{ext}`

---

## 11 · Build plan (ordered)

1. **Scaffold** — Repo + Dockerfile (WeasyPrint + Python + Node + bundled fonts) + HTTP server with `/health` + a "hello world" template that renders to PDF.

2. **Cover end-to-end** — Build ST-01 against `buchagentur.report.json` fixture. Wire up brand-token CSS injector. Wire up image fetch+cache. Goal: visual match within ~10% of reference Buchagentur cover.

3. **Tier 1 templates** in this order: ST-02 → ST-05 → ST-09 → ST-14 → ST-06 → ST-07A → ST-07B (3 variants) → ST-22 → ST-08 → ST-26 → ST-FAZIT → ST-03. After each one lands, render the full Buchagentur fixture and visual-diff vs reference.

4. **Pipeline hardening** — zod schema validation for all ST types · asset validation pipeline · overflow detection · warning/error reporting · `/preview` endpoint for single-page renders · `/validate` endpoint for dry-runs.

5. **Second / third / fourth report** — render `aerztepartner` from JSON, then `nikl` (single-page A4 mode + custom font path), then `alex` (Affinity-source — confirms portability). Patch any template gaps surfaced.

6. **Production readiness** — Railway deployment · n8n workflow wiring · smoke tests · README · hand-off.

---

## 12 · Known limitations & trade-offs

### What this system can do
- ✅ Reproduce ~90% of the visual quality of the reference PDFs for digital viewing
- ✅ Render any client's report in 5–10 seconds end-to-end
- ✅ Apply per-client branding (color, fonts, logo) with zero template changes
- ✅ Handle variable copy length, variable case-study count, variable logo count
- ✅ Output sRGB PDF 1.7 ready for email / download / web embed
- ✅ Scale horizontally on Railway with zero per-render licensing

### What this system can NOT do (vs the InDesign source)
- ❌ Editorial-grade typography polish (manual kerning of specific letter-pairs, optical margin alignment, hanging punctuation). WeasyPrint's HarfBuzz is good but not InDesign-good.
- ❌ Asymmetric, "broken-grid" layouts where a designer hand-places elements per-page. Templates impose a grid.
- ❌ Hand-cropped photo focal points. Cover image-cropping is automated; if the AI image has a poor focal point, the result is mediocre. Mitigation: pre-crop assets in a separate pipeline, or invest in a vision-model focal-point step.
- ❌ Decorative illustrations like the aerz pickaxe-and-coins composite (p4). These remain manual one-offs unless commissioned as SVG once and inserted via slot.
- ❌ Print output. Out of scope by design — if a client ever needs a printed version, route the PDF through a separate print-prep pipeline rather than rebuild this.

### Where human review is still needed
- First render of a new client (visual QA before sending)
- Photo curation and crop decisions
- Brand-color picker if `brand.json` was auto-generated from logo (verify it looks right on dark/light pages)
- Post-render proofread (the QA agent catches copy issues, not visual ones)

### Quality ceiling
The output is "good digital-PDF B2B magazine" — comparable to the reference DMC reports themselves. Not Forbes / Robb Report territory, but the references aren't either; they're at "premium B2B direct-marketing PDF" tier, which is the achievable ceiling for this system.

---

## 13 · Decision points the user must confirm before build starts

The following decisions were resolved by the digital-only clarification:
- ~~**Renderer choice**~~ — **DECIDED: WeasyPrint** (free, no license, sufficient for sRGB digital PDF).
- ~~**Color mode**~~ — **DECIDED: sRGB throughout.**
- ~~**Bleed / crop marks / PDF/X-3**~~ — **DECIDED: none.**

Remaining open decisions:

1. **Custom font policy:** Bring-your-own-from-client (legal-clean) or auto-substitute with free closest-match? **Recommendation: BYO with auto-substitute fallback + warning in `x-warnings`.**
2. **Asset hosting:** Airtable URLs directly, or proxy through Cloudflare R2 for caching? **Recommendation: R2 cache layer, Airtable as source-of-truth.**
3. **Hosting plan:** Railway 512MB ($5 starter) or 1GB ($5 pro plan)? With WeasyPrint, 512MB is workable for low concurrency. **Recommendation: start at 512MB, upgrade if memory pressure shows up under load.**
4. **ST canonical mapping:** Adopt the spec's ST IDs as-is (ST-01 … ST-37 + new ST-FAZIT) or renumber to a flat 1..N? **Recommendation: keep ST IDs — already in Master System and team-shared vocabulary.**
5. **Output spread mode:** Does n8n need 2-up landscape spreads exported, or only single A4 portrait? Affects template count slightly. **Recommendation: ship single-A4-portrait first; add 2-up imposition in a v1.1 if needed for sharing/preview.**
6. **Image generation pipeline integration:** Confirm AI image outputs target the aspect ratios this PRD specifies (1:1 portraits, 3:4 covers, 16:9 charts/screenshots), or add an aspect-ratio routing step.

---

PRD complete — awaiting validation before building.
