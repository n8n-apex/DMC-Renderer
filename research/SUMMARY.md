# Phase 1 Synthesis — Research Summary

**Status:** ✅ All 6 research agents complete. Awaiting Richard's approval before Phase 2 architecture.

This synthesizes Tasks A–F into one document with concrete picks. The detail lives in the individual research files; this is the decision sheet.

---

## TL;DR (the picks)

| Decision | Pick | Cost |
|---|---|---|
| **PDF engine** | **WeasyPrint 68.1** (Python-native, free) | $0 |
| **Body font (default)** | **Source Serif 4** (SIL OFL) | $0 |
| **Headline font (default)** | **Inter 800** (SIL OFL) | $0 |
| **Body font (Apex brand)** | **Vollkorn** (SIL OFL, richest free OpenType set) | $0 |
| **Headline font (Apex brand)** | **Inter 900** | $0 |
| **Hyphenation** | **Pyphen** with `hyph-de-2006` (auto in WeasyPrint) | $0 |
| **Typography polish** | Python lxml preprocessor (~150 lines) — Typeset.js-style span wrapping | $0 |
| **Focal-point detection** | MediaPipe → smartcrop.py → Claude Haiku 4.5 (escalation only) → center fallback | ~$0.09–0.66/mo at 100 reports |
| **Decorations** | Iconify via `pyconify` — 28–30 named cluster patterns | $0 (free Iconify sets) |
| **Markdown in body fields** | Light subset: `**bold**` + `*italic*` only | $0 |
| **Quotes/whitespace** | German preprocessor: `„…"` + U+00A0 around numbers/units/titles | $0 |
| **Hosting** | Railway, ~$5–20/mo | ~$10–20/mo |

**All-in renderer monthly cost at 100 reports: ~$10–25/mo.** No subscription, no per-render API fees beyond the optional Claude Vision escalation.

---

## 1 · Engine pick — WeasyPrint 68.1 (free)

**Why WeasyPrint over the 4 alternatives:**

- **vs PrinceXML self-hosted ($3800 + $2500/yr):** the marquee feature Prince was supposed to unlock (`hanging-punctuation`) is missing from every engine including Prince. Free → no quality gap that justifies the cost at our volume.
- **vs Paged.js + Chromium:** drops Chromium/Node dependencies entirely (smaller Docker, easier Railway deploy). Paged.js's `bookmark-level` is a polyfill-only lie — Chromium ignores GCPM bookmarks, so picking Paged.js mandates a post-process outline-injection step. Adds complexity for no quality gain.
- **vs Vivliostyle:** Vivliostyle is great but has weaker Python ergonomics. WeasyPrint is a one-line Python import.
- **vs Typst:** disqualified — HTML is an export-only experimental target, not an input. Can't use it for our pipeline.

**What WeasyPrint actually delivers:**
- Full CSS Paged Media + GCPM support (`@page`, named pages, page-break, running headers/footers via margin boxes, `string-set`, `target-counter` for `page` counter, `bookmark-level`/`bookmark-label`, footnote floats, widows/orphans)
- HarfBuzz text shaping → German `ä/ö/ü/ß`, ligatures, hyphenation all native
- Pyphen for `lang="de"` hyphenation patterns (hyph-de-2006 = Duden-current)
- Inline SVG rendering (clean)
- sRGB color profile embed
- Active 2026 maintenance (v68.1 latest)

**Gotchas to design around** (from Task E):
- CSS Grid in paginated content: only safe for fixed-height tiles (cover, KPI cards). **For flowing body content, use multi-column or block flow, never Grid.**
- WeasyPrint named-pages bug: spurious blank page when `break-before: page` is on a first child ([Kozea/WeasyPrint#1944](https://github.com/Kozea/WeasyPrint/issues/1944)). Workaround: use `@page :first` selector + named-page `page:` property on body section, not on first child.
- Approximate render time: 5–10 sec for a 20-page A4. Memory ~150–300 MB. Fits 1 GB Railway plan.

**Fallback path:** author the CSS to be ~95% Prince-compatible (both implement GCPM the same way). If a side-by-side render of the final fixture reveals a layperson-visible quality gap, swap to PrinceXML self-hosted as a v1.1 — minimal CSS changes.

Full report: `research/A-engine-selection.md`.

---

## 2 · Typography recipe — Inter + Source Serif 4 (default) / Vollkorn + Inter (Apex brand)

**Font picks (all SIL OFL, free, Latin-Extended-A coverage for German diacritics):**

| Brand | Body | Headline | Why |
|---|---|---|---|
| **DMC Default** | Source Serif 4 | Inter 800 | Matched-duo philosophy, broad weights, technical clarity |
| **DMC Apex** | Vollkorn | Inter 900 | Vollkorn has richest OpenType set (true `smcp`, `c2sc`, `dlig`, `ss01`) — closest to InDesign feel |
| **Technical/data-heavy variant** | IBM Plex Serif | IBM Plex Sans | Superfamily, fits charts/numbers |

**`font-feature-settings` recipe** (paste-ready):

```css
:root[lang="de"] {
  --features-body:    "kern" 1, "liga" 1, "calt" 1, "onum" 1, "pnum" 1;
  --features-headline:"kern" 1, "liga" 1, "dlig" 1, "case" 1, "ss01" 1;
  --features-numeric: "lnum" 1, "tnum" 1, "zero" 1;
  /* lfbd/rtbd listed for future-proofing; absent from all free fonts checked */
}

body  { font-feature-settings: var(--features-body); }
h1,h2 { font-feature-settings: var(--features-headline); letter-spacing: -0.01em; }
.numeric { font-feature-settings: var(--features-numeric); }
```

**Critical rule:** `dlig` must stay **OFF** in body for German — otherwise decorative `ct`/`st`/`sp` ligatures fight compound-word morphology (from Task F).

**Optical margin alignment + hanging punctuation** (since native `hanging-punctuation` is Safari-only and free fonts lack `lfbd`/`rtbd`):
- ~150-line Python lxml preprocessor wraps problem glyphs in `.pull-T`, `.pull-V`, `.pull-W`, `.pull-Y` (-0.07em), `.pull-O`, `.pull-C` (-0.04em), `.pull-A` (-0.03em), `.pull-single` (-0.27em), `.pull-double` (-0.46em), `.push-period`, `.push-comma` (+0.3em).
- Idempotent via `data-typeset-done` sentinel.
- Adds `.hangs-open` class to any paragraph starting with `„` or `"` for negative-indent polyfill.

**Hyphenation:** WeasyPrint already uses Pyphen for `lang="de"` + `hyphens: auto`. Just set those in CSS — zero code. Curated `&shy;` exception dictionary for brand names + long proper-noun compounds where Pyphen falls short.

Full report: `research/B-typography-polish.md`.

---

## 3 · Focal-point detection — MediaPipe → smartcrop → Claude Haiku

**4-tier deterministic-first pipeline:**

1. **MediaPipe Face Detection** (free, 3 ms/image) for any image likely to contain a face. Cover hero clamps `focal_y ≤ 60%` to keep face above the bottom-30% text band.
2. **smartcrop.py** (free, deterministic) for environmental scenes with no face (status_quo, fazit).
3. **Claude Haiku 4.5 Vision** (~$0.0022/escalated image) as tier-3 only when MediaPipe + smartcrop disagree by >20% or smartcrop confidence < 6.0.
4. **Center-crop fallback**, flagged for human review.

**Monthly cost projection** (100 reports × 3 AI-gen images each):
- Typical (~12% escalation): **$0.09/mo**
- Worst case (100% escalation): $0.66/mo
- Even if upgraded to Sonnet 4.6: $2.10/mo

**Failure modes that escape the pipeline** (route to human review queue):
- Multiple equally-sized faces in a portrait (founder pair)
- Abstract metaphor cover art (should never enter this pipeline — route to SVG path per VISUAL_ASSETS.md)
- Very low-contrast fog/sunrise scenes (caught by smartcrop-score < 6.0 escalation trigger)
- Subjects deliberately placed in bottom-third (regenerate, not crop)

Adds 2 Python deps (`mediapipe`, `smartcrop`) + 1 optional env var (`ANTHROPIC_API_KEY`).

Full report: `research/C-focal-point.md`.

---

## 4 · Decorative illustrations — Iconify clusters via pyconify

**MVP path:** Iconify (free, MIT, 290k icons, MCP-friendly) via `pyconify` Python library. Each decoration slot resolves to a 220×180 inline `<svg>` viewBox composing 2–3 Iconify primitives.

**Brand tinting** via Iconify's URL-param `color` query (server-side):
```python
icon_url = f"https://api.iconify.design/{prefix}/{name}.svg?color={brand_accent_hex}"
```

**~28–30 named cluster patterns** distributed across 11 ST templates (catalogued in Task D file §5):

| Example cluster | ST | Composes |
|---|---|---|
| `metric-celebration` | ST-07A (case results) | `mdi:pickaxe` + `fluent:savings-24-regular` + 4× `tabler:coin` (accent) |
| `process-flow-chain` | ST-22 (collaboration) | 4–6× `tabler:circle-N` + connectors |
| `belief-quote-stencil` | ST-14 (false beliefs) | Oversized `„` glyph + `fluent:lightbulb-question-24-regular` |
| `mechanism-cycle` | ST-06 (mechanism) | Radial node arrangement, accent connectors |
| `symptom-tile-grid` | ST-09 (status quo) | 6× contextual icons in cells |

**Upgrade ladder** (single `fallback_chain` field in slot payload, resolver walks tiers):
1. `client_library` — per-client commissioned ($50–150 designer or $5–15 Recraft kit)
2. `shared_library` — closed-set of ~10 metaphor SVGs ($500–1500 one-time, budgeted in VISUAL_ASSETS.md)
3. `iconify_cluster` — always-present MVP safety net

**Payload schema:**
```json
{
  "decoration_slot": {
    "fallback_chain": ["client_library", "shared_library", "iconify_cluster"],
    "client_library": { "asset_key": "metric-celebration-apex" },
    "shared_library": { "asset_key": "pickaxe-coins" },
    "iconify_cluster": {
      "pattern": "metric-celebration",
      "icons": ["mdi:pickaxe", "fluent:savings-24-regular", "tabler:coin"]
    }
  }
}
```

Renderer never ships a blank decoration slot — `iconify_cluster` always resolves.

Adds 1 Python dep (`pyconify`). $0 marginal cost.

Full report: `research/D-decorative-illustrations.md`.

---

## 5 · CSS Paged Media — what we use and what we drop

Full matrix in `research/E-paged-media.md`. Critical implications:

**Features we USE in templates:**
- ✅ `@page` named (cover, body, back)
- ✅ `@page :first` for cover-only rules
- ✅ `page-break-before/after/inside`
- ✅ Running headers/footers via `@bottom-left`, `@bottom-center`, `@bottom-right`
- ✅ `string-set` + `content(string)` for chapter title in footer
- ✅ `counter(page)`, `counter(pages)` for "Seite N / M"
- ✅ `bookmark-level` + `bookmark-label` (WeasyPrint emits PDF outline natively)
- ✅ `widows: 2; orphans: 2; page-break-inside: avoid` on case-study + belief blocks
- ✅ Multi-column for flowing body text
- ✅ Inline `<svg>` for decorations + diagrams + charts
- ✅ `@font-face` with subsetted fonts

**Features we DROP:**
- ❌ `hanging-punctuation` native (Safari-only; preprocessor polyfill instead)
- ❌ `lfbd`/`rtbd` OpenType (absent from free fonts; preprocessor handles)
- ❌ JavaScript in templates (WeasyPrint has none; design without it)
- ❌ CSS Grid for body-flow chapter content (silently clipped at page boundaries; use multi-column)
- ❌ `target-counter` beyond `page` (Paged.js doesn't support — WeasyPrint does, but we don't need custom counters in MVP)
- ❌ Sidenotes / float: footnote (over-engineered for MVP; skip)

**Critical gotcha:** the Grid limitation is the one to internalize. **Grid only for fixed-height tiles** (cover, KPI row, info card). **Block flow + multi-column for everything else.**

---

## 6 · German typography rules

Full rules in `research/F-german-typography.md`. The renderer's German preprocessor (Python, ~80 lines):

**Hyphenation:** `<html lang="de">` + `hyphens: auto` in CSS → Pyphen kicks in automatically. Curated `&shy;` dictionary for brand-specific words.

**Quotes:** preprocessor replaces straight quotes with German `„…"` (low-9 + high-9). Handles nested `‚…'` (single).

**No-break-space (U+00A0):** preprocessor inserts between:
- Number + unit: `100 €`, `48 Minuten`, `30 %`, `15 Mitarbeiter`
- Abbreviation pairs: `z. B.`, `d. h.`, `u. a.`
- Title + name: `Dr. Müller`, `Herrn Müller`
- Page refs: `S. 12`
- Day + month in dates

**Note:** U+00A0 is preferred over the typographically-correct U+202F (narrow no-break space) — font support for U+202F is unreliable in some PDF embedders and renders as `.notdef`.

**Hyphen → en-dash:** German uses `–` (U+2013) for parenthetical breaks where English uses `—`. Preprocessor converts ` - ` (spaced hyphen) → ` – ` (spaced en-dash). Plain hyphen stays for compound words.

**Date formatting:** Python `babel.dates.format_date(d, format='long', locale='de_DE')` → `"11. Mai 2026"`.

**Number formatting:** `babel.numbers.format_decimal(n, locale='de_DE')` → `"1.234,56"`.

**OpenType warning:** `dlig` (discretionary ligatures) must stay OFF in body — German compound words break against decorative `ct`/`st`/`sp` ligatures. OK on headlines.

---

## 7 · Architecture implications (preview of Phase 2)

The research validates the 3-layer architecture from the brief addendum:

```
POST /render  →  [Preprocessor]  →  [WeasyPrint]  →  [Postprocessor]  →  PDF
                       ↓                                    ↓
            • German quote/nbsp/hyphen normalizer    • PDF metadata strip
            • Markdown lite (**bold**, *italic*)     • (optional) bookmark verification
            • Typeset.js-style glyph wrapper
            • Focal-point lookup → focal_x/y vars
            • Decoration slot resolution (Iconify)
            • Brand token injection (CSS vars)
            • &shy; insertion for compound words
```

Phase 2 architecture doc will detail file structure, Jinja2 template organization, image-fetch caching, Railway env vars, idempotency hash, and the per-ST CSS file structure.

---

## 8 · Full risk list

| Risk | Severity | Mitigation |
|---|---|---|
| `hanging-punctuation` not native in WeasyPrint | Medium | Python preprocessor polyfill (Typeset.js-style) handles all 11 STs |
| `lfbd`/`rtbd` absent from all free fonts | Medium | Same preprocessor wraps problem capitals + quotes with negative margins |
| WeasyPrint named-pages + `break-before: page` blank-page bug | Low | Use `@page :first` selector pattern instead of named pages on first child |
| CSS Grid breaks on page-overflow for body content | Medium | Use multi-column / block flow for body; Grid only for fixed-height tiles |
| German compound-word hyphenation imperfect for brand names | Low | `&shy;` exception dictionary, curated per client during onboarding |
| Pyphen `hyph-de-2006` may not cover all neologisms | Low | Same exception dictionary; flag in QA |
| MediaPipe misses faces in stylized portraits | Low | Tier-3 Claude Vision escalation catches these |
| Fixture has 7 character-budget violations (over-length) | Medium | `.shrink-fit` CSS fallback (10pt → 9.5pt body) on overflowing pages, structured warning header |
| Fixture has 22 logical pages vs 20 target | Medium | Open Q for Richard (auto-shrink / Writer regen / relax target) |
| `mein_werkzeugkoffer.pdf` (North Star) missing | Medium | Asked Richard to provide before Phase 2 lock |
| Markdown `**bold**` in body fields | Low | Light-markdown preprocessor (handles `**`, `*`, newlines) |
| Page-number metadata stale in fixture | Low | Renderer uses `slot` ordering, recomputes page numbers |
| Iconify network dependency (icons fetched at render) | Low | Cache resolved SVGs locally per-process; offline fallback to embedded subset of ~50 icons |
| AI-generated case portraits look generic vs real customers | Out of scope | Visual-Assets pipeline decision: client-supplied → InitialsAvatar fallback. No invented humans. |

---

## 9 · Open decisions for Richard before Phase 2 starts

Need a green light on these before I write `docs/ARCHITECTURE.md`:

1. **Engine pick confirmation:** WeasyPrint 68.1 (free). Acceptable, or do you want me to spike a Prince-self-hosted comparison render first?
2. **Default font pair confirmation:** Source Serif 4 + Inter 800. Apex brand: Vollkorn + Inter 900. Both OFL-free. OK?
3. **Page-count handling** — 22 produced vs 20 target. Pick: A (auto-shrink ST-05 + ST-FAZIT to 1 page each); B (Writer Pipeline regenerates tighter); C (relax target to 20–24). **My recommendation: A** — renderer adapts, no upstream round-trip.
4. **`mein_werkzeugkoffer.pdf`** — drop into `/Users/utkarsh/Projects/richard/refs/` so Phase 2 + Phase 4 visual comparison can happen.
5. **Decoration MVP scope** — Iconify clusters only (free) for v1.0; reserve client-commissioned kits for v1.1 onboarding upsell. OK?
6. **Anthropic API key** for the focal-point escalation tier — do you have one to add to Railway env vars? Pipeline still works without it (skips to center-fallback) but quality is better with it.
7. **Async render fallback** — synchronous /render up to 120s default; do you want me to scaffold an async /render/start + /render/status pattern for n8n's HTTP timeout protection, or defer to v1.1?
8. **Anthropic-API-key in renderer:** brief says renderer is stateless. The Claude Vision call is per-render. Acceptable, or move focal-point detection to an upstream pre-processing service?

---

## 10 · Status

```
Phase 0  ✅ DONE  — refs analyzed, fixture validated, ST visual map ready
Phase 1  ✅ DONE  — all 6 research tasks complete, picks locked
Phase 2  ⏸  WAITING ON RICHARD'S APPROVAL  ←──── YOU ARE HERE
Phase 3  ⏸  WAITING ON PHASE 2 APPROVAL
Phase 4  ⏸  WAITING ON PHASE 3 COMPLETION
```

When you approve, I dispatch in parallel:
- ARCHITECTURE.md draft (single writer)
- Worktree setup for `dmc-renderer/` (git init, scaffolding without code)
- Font assets download into `assets/fonts/` (Source Serif 4, Inter, Vollkorn — subsetted)
- Test harness skeleton

Then await architecture sign-off before Phase 3 templates.
