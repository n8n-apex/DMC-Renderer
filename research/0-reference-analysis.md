# Phase 0 — Reference Analysis & ST Visual Map

**Author note:** `mein_werkzeugkoffer.pdf` (the brief's North Star) is not present in `/Users/utkarsh/Projects/richard/refs/` or anywhere on this machine. Phase 0 was conducted against the 4 PDFs that ARE present:

- `refs/aerztepartner.pdf` (11 PDF pages = 1 cover + 9 landscape spreads + 1 back; effective 20 A4 pages)
- `refs/buchagentur.pdf` (11 PDF pages, same mode)
- `refs/alexander_boss.pdf` (11 PDF pages, same mode)
- `refs/niklas_niemeyer.pdf` (20 single A4 portrait pages — same logical content, different export choice)

These cover the same DMC framework with sufficient tonal range. `aerztepartner.pdf` is the closest tonal analog to what the brief calls out (founder-led B2B, data-heavy, case-study-driven, German-aggressive copy). Richard should drop `mein_werkzeugkoffer.pdf` into `refs/` and I'll incorporate before Phase 2 architecture is locked.

PDF page renders for all 4 are in `refs/renders/{aerz|buch|alex|nikl}_p{NN}.png`.

---

## 1 · Export-mode finding

3 of 4 references export as **11 PDF pages = 1 portrait cover + 9 landscape 2-up spreads + 1 portrait back** (= 20 logical A4 pages laid out as facing-page spreads).
1 of 4 (nikl) exports as **20 single A4 portrait pages**.

Both are the same 20-page logical report. The renderer ships **single A4 portrait pages** as primary (matches the brief's `export_mode: "single-page"`). 2-up spread mode is a v1.1 if needed.

---

## 2 · Per-reference design language

### 2.1 Typography stack (verified via PDF font-table extraction)

| Reference | Headline font | Body font | Display caps | Producer |
|---|---|---|---|---|
| aerz | **Merriweather** Bold / ExtraBold (serif) | **Lato** Reg/Bold + Source Sans 3 Reg | Bebas Neue Pro ExpEb | Adobe InDesign 21.2 (Mac) |
| buch | **Merriweather** Bold (serif) | **Instrument Sans** Reg/SemiBold + Inter Reg | (none distinct) | Adobe InDesign 21.2 (Win) |
| alex | **Source Sans 3** Black/ExtraBold (sans) | Source Sans 3 Reg/SemiBold | Bebas Neue, Montserrat ExtraBold | Affinity 3.0.3 + PDFlib |
| nikl | **Azo Sans** Bold (commercial sans) | **Source Sans Pro** Reg/SemiBold | (Minion Pro Reg as serif accent) | Adobe InDesign 21.2 (Win) |

**Observations:**
- 2 of 4 use **serif headline + sans body** (Merriweather + Lato/Instrument)
- 2 of 4 use **sans headline + sans body** (Source Sans 3 Black, Azo Sans Bold)
- All 4 use a **humanist sans for body** (Source Sans family in 3 of 4, Lato in 1, Instrument Sans in 1)
- Only nikl uses a commercial font (Azo Sans, ~€100+ license)
- All other fonts in use are SIL-OFL or Adobe-bundled

**Implication:** the default font palette for the renderer should be all-free. The Source Sans family + Merriweather + Bebas Neue covers the look. A client wanting Azo Sans must supply a licensed file (bring-your-own).

### 2.2 Color palette (pixel-sampled from cover pages)

| Reference | Primary | Accent | Neutral-Dark | Neutral-Bg | Hero treatment |
|---|---|---|---|---|---|
| aerz | `#1A2B5C` deep navy | `#E6B85C` gold | `#2B2B2B` | `#F5F1EA` cream | Photo + dark gradient bottom |
| buch | `#022D2D` deep teal | `#5FB6A8` sea-green | `#2B2B2B` | `#F1ECE0` cream | Photo + dark teal full bg |
| alex | `#0E2540` navy | `#F5C518` bright yellow | `#2B2B2B` | `#FFFFFF` | Photo with right-third overlay panel |
| nikl | `#0E0E10` charcoal | `#FF7A1A` orange + `#2A6CD9` blue | `#FFFFFF` light text | `#0E0E10` mostly dark | Photo + dark gradient bottom |

Every report uses **exactly 2-3 design colors + neutrals**, exactly per the Design System v2 §C.2 "Drei-Farben-Regel." Brand-token system must accept primary + accent + (optional) second-accent.

### 2.3 Layout grid (estimated by ruler measurement on renders)

All 4 references use a **12-column underlying grid** with:
- Outer margins: ~18–22mm
- Inner / gutter: ~6–8mm
- Generous whitespace (≥20% of every page is blank per spec §D.1)
- Asymmetric layouts: image bleeds to one side, headline overlaps image, body offset from headline

**Baseline rhythm:** body text appears to use 14pt leading at 11pt body size (a 1.27× ratio). Headlines snap to 2× or 2.5× the baseline.

### 2.4 Negative space & rhythm

- Every 5–7 pages a "dark-dominant" or "atmospheric photo" page acts as a visual break (spec §C.3 "Hell-Dunkel-Rhythmus")
- Headlines are never wider than ~75% of column width — they breathe
- Pullquotes float into negative space rather than into running text
- Body text columns are usually 50–58 characters wide (well within editorial readability)

### 2.5 Data-viz treatment

- Charts are **vector**, never raster. Single accent line + grey, max 6 data points (spec §7.2). Inline labels (no legend boxes).
- Stat blocks: 40–72pt numbers, tiny labels, used 3-up in a row
- Comparison tables: 2-col with checkmark/cross icons in left column
- Trustpilot mock-cards: avatar circle + name + star row + body + date (always green stars on white)

### 2.6 Portraits & scene crops

- **Portraits**: always head-shoulders, eye-level, professional. Either freed (transparent bg) or with shallow-DOF blurred background. Subject's eyes are at the top third of the frame.
- **Scenes**: always industry-specific (workshop / clinic / construction site / desk-with-papers). Never generic stock. Strong directional light (golden hour or window light). Bottom 30–40% of the frame is deliberately darker for headline overlay.

---

## 3 · Universal page-type set (the 14 STs that actually appear)

Across all 4 references, only 14 ST types from the Master System's 37-type catalog are in use. The brief's 11-ST MVP set covers the most common 11 of these:

| ST | Name | Frequency | Used by fixture? |
|---|---|---|---|
| ST-01 | Cover | every report, p1 | ✅ |
| ST-02 | Outlook / Ausblick | every report | ✅ |
| ST-03 | CTA / Rückseite | every report, last | ✅ |
| ST-05 | About / Über-Uns | every report | ✅ |
| ST-06 | Mechanism / Mechanismus | every report | ✅ |
| ST-07A | Case Study / Fallstudie | every report (3–5×) | ✅ (5×) |
| ST-07B | Theory / Gegenseite | every report (paired with cases) | ✅ (3×) |
| ST-09 | Status Quo | every report | ✅ |
| ST-14 | False Beliefs / Irrglauben | every report | ✅ |
| ST-22 | Collaboration / Prozess-Ablauf | every report | ✅ |
| ST-FAZIT | Summary | every report (≠ official ST) | ✅ |
| ST-21 | Comparison Matrix | 2 of 4 | ❌ (deferred per brief) |
| ST-25 | Stat-Row (3-up) | 2 of 4 | ❌ (deferred) |
| ST-26 | Trust-Wall (reviews/logos) | every report | ❌ (deferred per brief; SerpAPI Trustpilot is v1.1) |

The brief's 11-ST MVP is the minimum to ship.

---

## 4 · ST schema → visual rendering map

For each of the 11 ST schemas in the brief, this is the visual translation (based on reference observation).

### ST-01 — Cover (1 page, portrait)
**Fields:** title, subtitle, intro_body, teaser_bullets[3]

**Layout (drawn from aerz p1 / alex p1 / nikl p1):**
- Full-bleed background photo (cover_hero from manifest), dark gradient overlay covering bottom 60%
- Top sub-text strip: target audience + report-year (small, all-caps, accent color or white). Example: "ZAHNÄRZTE-REPORT Q1-2026"
- Right column or right-third panel: "INKLUSIVE IM REPORT" / "FALLSTUDIEN" mini-cards with 3 teaser_bullets
- Bottom 30%: big two-line title in display weight (40–60pt), bottom-aligned, with accent-color word in the title
- Sub-title underneath at 16–18pt regular
- Tiny brand mark top-right corner
- Author small portrait + name strip just above title (optional, depending on layout variant)

**Required image slots:** cover_hero (3:4 portrait), cover_author (1:1 thumb, optional)

### ST-02 — Outlook (2 pages, "2-3")
**Fields:** headline, asymmetrie_opener, body

**Layout (drawn from aerz p2 / buch p2):**
- Headline at p2 top in serif/display, ~40pt
- asymmetrie_opener as a callout block — slightly inset, larger leading, often italic or accent-color (the "status anerkannt + destabilisiert" frame)
- body flows across both pages as 2-column or single-column with generous margins
- Bottom of p2: small author portrait + brief author-bio strip (small, italic) — comes from brand_tokens (founder_full_name, founder_role, logo_dark_url)
- p3 right margin: optional zielgruppe panel (target audience definition)

### ST-03 — CTA / Back Cover (1 page, last)
**Fields:** headline, body, cta_text, cta_url

**Layout (drawn from aerz p11 / buch p11 / nikl p20):**
- Background tinted with `brand_primary` or a low-key atmospheric photo (less prominent than cover)
- Brand logo top center
- Headline ~30pt sans, centered, white-on-dark or dark-on-cream
- 2-3 lines of body, centered
- Large CTA URL: ~28pt monospace or display, in `brand_accent`, with QR code adjacent
- QR code generated from `brand_tokens.qr_target_url` (≥30mm × 30mm)
- Small "100% kostenfrei" / "unverbindlich" reassurance line at bottom

### ST-05 — About (1 page)
**Fields:** headline, intro, body, credibility_points[3-5]

**Layout (drawn from aerz p2-right / buch p2-right):**
- Headline at top, serif or display weight
- intro paragraph at ~16pt above body
- body in 1-col, ~11pt, leading 14pt
- credibility_points rendered as 3–5 stat-blocks in a row OR a 2×2 grid: each block = small label above, big value in accent color (e.g. "Seit 2017 / spezialisiert auf B2B-Positionierung")
- Optional team photo or about_logo (small, top-right)
- Bottom strip: brand logo + tiny brand line

### ST-06 — Mechanism (1 page)
**Fields:** headline, mechanism_name, mechanism_description, steps[3-5], closing_redirect

**Layout (drawn from aerz p7-right "Vorsorge-Karussell" / alex p4 / nikl p14-15):**
- Headline + mechanism_name (the named/proprietary system) as the visual anchor — name often in accent color or as a "tag" label
- mechanism_description as 2-3 sentence intro
- steps rendered as numbered cards in either:
  - **Linear column** (numbered 01–05, each with title + description, stacked vertically)
  - **Circular flow** (5 numbered nodes radially arranged, connected by thin lines)
- Each step uses a large stencil number (60–96pt) + title + 80–200 char body
- closing_redirect at bottom as a soft-CTA paragraph or accent box

**`reveal_level` field** (what / how-partial / hidden):
- "what" → step body fully shown
- "how-partial" → body shown but redacted with em-dashes or "..."
- "hidden" → step shows only number + title, body is a teaser

This is critical for the spec's "How-to-Verbot" (Module 11.8) — never reveal full method.

### ST-07A — Case Study (1 page, the most complex template)
**Fields:** fallstudie_number, ergebnis_headline, kurzportraet, ausgangsproblem, wendepunkt (opt), loesung, ergebnis_text, ergebnis_metrics[2-4], kunde{name, funktion, initials, company_url}, pullquote{text, attribution}

**Layout (drawn from aerz p5-left / alex p5 / nikl p8 — same template across all):**

Two-column grid, ~60/40 split:
- **Left column (60%):** structured by 4 sub-headings stacked vertically
  - "AUSGANGSSITUATION" → ausgangsproblem
  - "ZIEL" → wendepunkt (the turning point)
  - "LÖSUNG" → loesung
  - "ERGEBNIS" → ergebnis_text + ergebnis_metrics rendered as a 2–4 cell mini-grid of label+value
- **Right column (40%):** dark panel (brand_primary or near-black) containing:
  - Massive stencil number ("01", "02", "03"…) — 80–120pt, top-right corner
  - kunde portrait OR initials avatar circle (if portrait missing) — fallback for missing portraits per brief
  - kunde.name in white sans (~14pt)
  - kunde.funktion (~10pt, neutral-mid)
  - kunde.company_url small at bottom (accent color)
  - 3 ergebnis_metrics rendered as big-number stats stacked
- **Pullquote** as a floating bar across full width, positioned ~70% down the page, in italic serif, with attribution

**Required image slots:** case_study_{N}_portrait (1:1) — optional; falls back to initials avatar built from kunde.initials

### ST-07B — Theory (1 page, between cases)
**Fields:** headline, subheadline (opt), body, key_insight

**Layout (drawn from aerz p5-right / aerz p6-right / nikl p9 / nikl p11):**
- Headline at top, display weight
- subheadline below in lighter weight (if present)
- body as a single column, justified, 11pt
- key_insight as a pullquote-style call-out OR a comparison-chart asset OR an inline diagram (mechanism Venn or comparison table)

**Per VISUAL_ASSETS.md decision:** the renderer-side decoration slot here may pull in a small diagram (Venn / Comparison / Chart) from the SVG component library if `decoration_slot` is set in the payload. The fixture appears to omit decoration_slot — so MVP renders ST-07B as a clean text-only theory page.

### ST-09 — Status Quo (2 pages, "6-7")
**Fields:** headline, asymmetrie_opener, body, symptoms[3-5], closing

**Layout (drawn from aerz p3 + p4 / alex p3 / nikl p4):**
- **Page 1 (left)**: headline (top), asymmetrie_opener (callout), body (2-col flow). Large numbered or icon-bulleted symptom list bottom-half OR floats to page 2.
- **Page 2 (right)**: continues body; renders 3–5 `symptoms` as a 2-col grid of icon+title+description cards (Status-Quo tile variant) OR as a stacked numbered list. closing renders at the bottom as a "moment of truth" beat — italic or boxed.
- Optional `status_quo_scene` image (from manifest) as full-bleed for one of the two pages OR as an inset on the headline page.

Aerz uses 2 atmospheric photos (one per spread side); nikl uses a 6-tile icon grid (the "Geizige Kunden / Empfehlungen / Auslastung / Offene Stellen / Social Media / Digitalisierung" page). Either layout pattern works — pick by page-density.

### ST-14 — False Beliefs (2 pages, "8-9")
**Fields:** headline, intro, beliefs[3]

**Layout (drawn from aerz p4-right / nikl p6 / buch p4 / alex p3-right):**
- Headline + intro at top of p8
- 3 belief-blocks, each rendered as:
  - belief quoted in „…" with leading-quote stencil (large opening „ in accent color)
  - "REALITÄT" or "WAHRHEIT" label + reality line in accent color or bold
  - body paragraph beneath
- Blocks distributed across both pages, 1.5 per page typical, separated by horizontal rule or thin accent line
- Background: dark panel for ENTIRE spread is common (nikl, aerz) OR cream with each block in a tinted box

### ST-22 — Collaboration / "So läuft die Zusammenarbeit ab" (1 page)
**Fields:** headline, intro, steps[4-6]

**Layout (drawn from aerz p10-left / buch p10-left / alex p9-right / nikl p18):**
- Headline at top, intro short paragraph
- 4–6 steps rendered as numbered cards:
  - 2-col grid (2 rows × 3 cols for 6 steps; 2 rows × 2 cols for 4) OR vertical stack
  - Each card: "SCHRITT N" label + title (3-6 words) + duration (e.g. "2 Stunden" or "3 Tage") + description
  - Steps numbered, each in accent-color circle or with stencil number
- Often paired with a small process worker photo (left) — for MVP omit (not in image manifest)
- Bottom strip: optional brand logo or CTA bar

### ST-FAZIT — Summary (1 page, the editorial close)
**Fields:** headline, body, bold_thesis, cost_of_inaction, closing_question

**Layout (drawn from nikl p16 / aerz p9-left / buch p8-right):**
- Background: `fazit_background` image full-bleed with dark gradient OR brand_primary tinted with subtle texture
- Headline (top, large display weight, often part-accent-color)
- body as 1-col, justified
- bold_thesis as a pullquote-style call-out (the "das ist nicht deine Schuld" beat) — italic, larger, accent color
- cost_of_inaction as a numbered list or smaller block with accent-color number
- closing_question as a final single-line italic at the very bottom, leading into the CTA page

---

## 5 · Fixture → renderer expectations (Apex / Jousef payload)

The fixture has 17 page-entries spanning the 20-page target. ST-09 and ST-14 span 2 pages each (page_numbers `6-7` and `8-9`); ST-02 spans `2-3`; ST-06 spans `15-16`; ST-FAZIT spans `17-18`.

**⚠️ Issue: page-number overlaps in fixture**
- Slot 11 (ST-07B Theory 3) → `page_numbers: "15"`
- Slot 14 (ST-06 Mechanism) → `page_numbers: "15-16"` (overlaps slot 11)
- Slot 12 (ST-07A Case 4) → `page_numbers: "16"` (overlaps slot 14)
- Slot 13 (ST-07A Case 5) → `page_numbers: "18"` (skips 17)
- Slot 15 (ST-FAZIT) → `page_numbers: "17-18"` (overlaps slot 13)

**Resolution:** the renderer should treat `slot` (sequential integer) as the source-of-truth for ordering. The `page_numbers` field is **derived metadata** that may be stale in the fixture. Recommend flagging this back to the Writer Pipeline owner. For MVP, the renderer uses `slot` to sequence pages and recomputes `page_numbers` from the slot count.

**Renderer expected page sequence** (using slot order, ST page-count rules):

| Output page | Source slot | ST | Notes |
|---|---|---|---|
| 1 | 1 | ST-01 | Cover |
| 2-3 | 2 | ST-02 | Outlook spread (Outlook page 1 + 2) |
| 4-5 | 3 | ST-05 | About spread (renderer auto-splits if body too long, else 1 page + filler) |
| 6-7 | 4 | ST-09 | Status Quo 2-page |
| 8-9 | 5 | ST-14 | False Beliefs 2-page |
| 10 | 6 | ST-07A | Case 1 |
| 11 | 7 | ST-07B | Theory 1 |
| 12 | 8 | ST-07A | Case 2 |
| 13 | 9 | ST-07B | Theory 2 |
| 14 | 10 | ST-07A | Case 3 |
| 15 | 11 | ST-07B | Theory 3 |
| 16 | 12 | ST-07A | Case 4 |
| 17 | 13 | ST-07A | Case 5 |
| 18-19 | 14 | ST-06 | Mechanism 2-page |
| 20 | 15 | ST-FAZIT | Summary |
| 21 | 16 | ST-22 | Collaboration |
| 22 | 17 | ST-03 | CTA back cover |

→ **22 pages total**, not 20. Either the page_count_target needs an update, OR the renderer auto-merges ST-05 + ST-22 + ST-FAZIT to fit 20. **Open question for Richard:** which?

For Phase 2 architecture, I'll assume the renderer respects `slot` order, treats `page_numbers` as advisory, and emits as many pages as the slot-list dictates. If page_count_target is exceeded, a warning is emitted in response headers. The Writer Pipeline can be tightened later to converge on exactly 20.

---

## 6 · Visual primitives library (the 13 reusable building blocks)

Every page composes from this set of CSS/SVG components. Built once, used across every ST.

| Primitive | Used in | Notes |
|---|---|---|
| `StencilNumber` | ST-07A panel, ST-06 step numbers, ST-09 symptoms | 60–120pt, accent color |
| `NumberedRow` | ST-09, ST-22, ST-FAZIT | number + headline + body, optional icon |
| `StatBlock` | ST-05, ST-07A panel | big value + tiny label, 3-up or 4-up grid |
| `CompareTable` | ST-07B (chart variant), Tier-2 | 2-col schlecht/gut with check/cross |
| `Pullquote` | ST-02, ST-07A, ST-07B, ST-FAZIT | large quote, accent color, optional mini-portrait |
| `ReviewCard` | (Tier-2: ST-26) | Trustpilot mock-card; deferred |
| `LogoWall` | (Tier-2: ST-31) | deferred |
| `CtaBar` | ST-03, ST-FAZIT footer | full-width bar with URL + QR |
| `HeroPhoto` | ST-01, ST-FAZIT, optional ST-09 | full-bleed with dark gradient overlay |
| `IconTile` | ST-09 tile variant | icon + title + body 6-cell grid |
| `MiniChart` | ST-07B chart variant | inline SVG, single accent line |
| `ProcessCard` | ST-22 | numbered card with title + duration + body |
| `QrCode` | ST-03, ST-FAZIT | inline SVG, 30mm minimum |
| `InitialsAvatar` | ST-07A when portrait missing | initials in colored circle, fallback for missing case_study_N_portrait |

All primitives are CSS+SVG components rendered server-side. None are AI-generated. None are external API calls.

---

## 7 · ST-by-ST decoration slot recommendations (for Phase 1 Task D output)

For each ST template, what decoration slot makes sense thematically (will be confirmed by Task D's research output):

| ST | Suggested decoration | Use case |
|---|---|---|
| ST-01 | (none — hero photo is the visual) | n/a |
| ST-02 | Subtle accent-line motif or single icon in margin | breathing decoration |
| ST-05 | Credentials/trust icons (shield, target, check) in the credibility_points block | reinforces trust |
| ST-06 | Mechanism diagram (CircularFlow or LinearFlow SVG component) | the named mechanism |
| ST-07A | (none — portrait + stencil is the visual) | n/a |
| ST-07B | Inline diagram per theory: Venn / Comparison / Chart | the editorial illustration |
| ST-09 | Status-Quo icon tiles (6 icons composed) | symptom visualization |
| ST-14 | Quote-mark stencil per belief | leading „ as graphic element |
| ST-22 | Process flow connector lines | optional |
| ST-FAZIT | Background photo + horizon line motif | resolved-state framing |
| ST-03 | QR code + accent geometric flourish | CTA polish |

**MVP scope:** every ST renders without decoration if the slot is absent. Decoration is enhancement, never required. Task D's recommendation will define which decorations are mandatory for MVP.

---

## 8 · Open issues for Richard

1. **mein_werkzeugkoffer.pdf is missing** — please drop it into `refs/` so I can validate against the North Star before Phase 2 lock.
2. **Fixture page-number overlaps** (§5 above) — slots 11/12/13/14/15 have overlapping or skipping `page_numbers`. Confirm: renderer uses `slot` ordering and emits its own page numbers, OR Writer Pipeline emits canonical sequential page_numbers and renderer respects them.
3. **22 pages > 20 target** — the fixture as-is produces ~22 pages with the visual rules in this doc. Should ST-05 or ST-22 squeeze to 1 page each? (Currently I have ST-05 as a spread but per the schema it's 1 page; if 1 page total it lines up at 20.) Confirm.
4. **Default brand fonts** — for the Apex fixture, brand_tokens currently say `font_heading: "Inter"` and `font_body: "Source Serif Pro"`. Both free, both in the recommended palette. I'll use these as defaults. ✓
5. **decoration_slot in payload** — fixture omits this field. MVP behavior: absent = no decoration. Confirm.
6. **3 ST-07B "Theory" instances** in fixture pair with cases 1-3; cases 4 + 5 have no Theory pages. Confirm intentional. (Spec implies 1 Theory per Case; here the 4th and 5th cases get no Theory page.)

---

## 9 · Status

- **Phase 0** ✅ complete (this doc)
- **Phase 1** ⏳ 6 research agents running in parallel (Tasks A–F)
- Once Phase 1 returns → `research/SUMMARY.md` synthesizing all picks → wait for Richard's approval before Phase 2.
