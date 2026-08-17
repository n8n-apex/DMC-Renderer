# Richard's DMC Report — Design DNA (6-deck visual analysis)

**Date:** 2026-05-30
**Method:** All **6** finished client decks Richard sent were rasterized to PNG and analyzed **visually, page by page** — 5 by dedicated opus vision agents + my own eyes on a cross-client sample. **84 pages total.** This doc is the reverse-engineered, **brand-agnostic** design system: the **universal grammar** (constant across all clients) separated from the **per-client axes** (what varies). It is the corrected foundation for re-scoping BOTH the pre-processor (asset/data generation) and the renderer (layout). It supersedes the thinner `2026-05-30-reference-design-system.md`, which was built from apex alone.

**Also the SCORING-RUBRIC source:** §C (the universal grammar) seeds the POSITIVE table and §E (the gap analysis) seeds the NEGATIVE table of the Self-Correcting Quality Architecture's Analysis rubric — see `2026-06-03-self-correcting-quality-architecture-design.md` §6. References are scored on *composition/devices*, never on a client's brand values (brand-agnostic safeguard).

**The corpus (note the two formats):**
| Deck | Vertical | Sheets | Logical pages |
|---|---|---|---|
| APEX (KI-Automatisierung) | AI automation | 20 | 20 portrait |
| Niklas Niemeyer / NMR | trades / construction | 20 | 20 portrait |
| Buchagentur | publishing / expert-books | 11 sheets | **cover + 9 SPREADS (left+right) + back = ~20** |
| Alexander Boss / Boss Recruiting | dental recruiting | 11 sheets | **same spread format ≈ 20** |
| Mein Werkzeugkoffer | tools / trades | 11 sheets | **same spread format ≈ 20** |
| Ärztepartner | medical / finance | 11 sheets | **same spread format ≈ 20** |

> **Format revelation:** the "11-page" decks are **facing spreads** — each interior sheet = a **left page + a right page**, and Richard uses a **left = problem/story/case · right = mechanism/solution/list** grammar. So *every* deck is ~20 logical pages. Our renderer must support **both** a 20-page sequential format and the spread (left/right) format.

---

## §A. The universal page ARC (skeleton — constant across all 6)

Cover → Intro/"Ausblick" → **About/Über-uns (+ social proof)** → Problem/symptoms → **Myths** ("7 Mythen" / "5 Denkfehler" / "7 Irrglauben" / "7 Denkfehler") → **[Case study (Fallstudie) + Mechanism] × 3, interleaved** → Data/proof (charts) → Summary/Fazit → FAQ/objections ("Was dich vom Handeln abgehalten hat") → Collaboration/"So läuft die Zusammenarbeit" (numbered Schritte) → **Social proof (testimonials grid + client-logo wall)** → Breathing/atmospheric → **Back-cover CTA** (giant URL).

Every deck hits this arc; the short format compresses by putting two beats on one spread. The "5 vs 7" count (5 Denkfehler / 7 Mythen) is itself a per-client rhetorical scaffold.

---

## §B. PER-CLIENT AXES (what VARIES — this is the §4.0 "data", the proof of brand-agnosticism)

The single most important output of seeing 6 decks: the design system is **one template with swap-in axes**. Hold these as data; never hardcode them.

| Axis | APEX | Niklas/NMR | Buchagentur | Boss | Werkzeugkoffer | Ärztepartner |
|---|---|---|---|---|---|---|
| **headline_type** | serif | **serif + heavy-sans-caps accent word** | serif (Didone) | serif (slab) | **ALL-SANS** | serif (Didone) |
| **palette** | blue/cyan/navy (mono) | royal-blue + charcoal + white | deep teal/petrol | navy + azure | mid-blue + navy | navy + **metallic gold** |
| **accent_mechanic** | tonal (one hue) | contrasting (blue on dark) | **contrasting (magenta-coral)** | contrasting (gold + green) | tonal-ish (blue) | contrasting (gold) |
| **texture/motif** | frosted-glass "X/peak" geometric | darkened photography | paper-grain | flat icons (none) | darkened photography | **parchment/marble + gold veining** |
| **ground/density** | light, airy | **50/50 light↔dark, punchy** | light editorial (dense text) | light + navy panels | light + navy panels | light premium (airy) |
| **qr_enabled** | no (URL pills) | **yes** | yes (case studies) | no (URL) | **yes** | no (URL) |
| **tone** | tech-premium | masculine, bold | editorial luxury | corporate trust | corporate-masculine | private-banking luxury |

**Implications:**
- `headline_type` is REAL and varies (5 serif : 1 all-sans) → never hardcode serif.
- Palettes range from monochrome-tonal (apex) to dual-contrasting (Buchagentur teal+magenta, Boss navy+gold+green, aerzte navy+gold) → our `accent_mechanic` axis is validated, and **gold/magenta/green accents** exist (not just one accent).
- `texture` varies hugely (frosted-glass, parchment, paper-grain, darkened-photo) → a per-client texture/atmosphere asset is needed.
- `qr_enabled` varies → QR must be an axis, not assumed.
- Density varies → a `density` axis (airy ↔ packed) is worth modeling.

---

## §C. The UNIVERSAL grammar (constant — this is the "schema")

### C1 — Type system
- **Display = high-contrast SERIF** (Didone/transitional) on 5/6 decks; **all-sans** on 1 (the axis). Large, near-black/navy on light, white/gold on dark.
- **Two-tone headlines** (signature): a **neutral serif word + a bold-CAPS accent word** in the brand accent (e.g. "Die **WAHRHEIT**", "Ein kurzer **AUSBLICK**", "…zur **NUMMER 1**", "Dein Buch **verkauft** oder **zerstört** dich"). Recurs on covers + section headers.
- **Body = humanist SANS**, justified, narrow multi-column, **heavy inline-bold** emphasis (1–3 bolded phrases per paragraph — a consistent tic).
- **Eyebrows/labels = ALL-CAPS letter-spaced sans**, small, often in accent color ("AUSGANGSSITUATION/ZIEL/LÖSUNG/ERGEBNIS", "FALLSTUDIE N", "DENKFEHLER N", "SCHRITT N", "BEKANNT AUS", "DIE AUTOREN").
- **Giant numerals** — stat numbers AND list/section numbers — a primary visual device (serif or condensed, often italic). Oversized ghost/outline numerals as decoration.
- **Oversized typographic quote marks** (`„`/`"`) before every pull-quote.

### C2 — Photography DOCTRINE (the biggest lever; ours fails here)
- **FOUNDER is the human anchor, used PROMINENTLY** — one of:
  - **full-bleed cover hero portrait** (APEX), or
  - **founder cutout composited on the cover** (Werkzeugkoffer 2 founders over skyline; Buchagentur 1 founder over teal), or
  - **large dedicated founder/duo photo on the intro/about page** (Niklas p2 name-over-photo; Ärztepartner p2 "DIE AUTOREN" duo ~45% of page; Boss p2 team).
  - …and then **recurs small beside pull-quotes** (APEX, Boss, Ärztepartner) for a "signed" feel.
- **CLIENT photo per case study — FIXED SLOT.** Every Fallstudie has a **named client portrait**, a **framed rectangle ~24–40% page-width**, full-color, top-of-column/sidebar, with **name + role + the client's OWN website URL** (+ QR where the brand uses QR). Never empty, never tiny.
- **Full-bleed SCENE photography** (darkened/scrim/vignette so text reads) on **cover, back-cover, and atmospheric "breathing" pages**.
- **DEVICE / PRODUCT mockups** recur: a **phone showing the running ad creative** (Boss, Werkzeugkoffer), a **laptop showing the software dashboard** (Werkzeugkoffer p9), a **3D book mockup** (Buchagentur case studies), an **app-in-hand** (Werkzeugkoffer). These add "real product" credibility + visual interest.
- **TEAM photo** on the about page (Buchagentur trio, Boss duo, Werkzeugkoffer, Niklas cluster).
- **Treatment:** full-color dominant; **darken/scrim** on full-bleed; occasional **duotone** for abstract/metaphor (apex p7 particle, Werkzeugkoffer iceberg/telescope). **Logos** desaturated/grayscale on the logo wall.
- **Personal cues** (the "close to the client" feel the user wants): named faces + named pull-quotes + **per-client URLs** + informal **du/Sie** address + the founder recurring. (No handwriting/signatures in any deck — the warmth is faces + names.)

### C3 — Color / PANEL system (ours is too pale)
- **Light paper ground** (white/ivory/parchment) is the default body canvas on ~all interior pages.
- **DARK filled "authority" panels** are the rhythm beat — **navy / deep-primary / ink**, NEVER a light-accent tint. Used for: recap/"Das Ergebnis" panels, CTA panels, case-study stat rails, "Über-uns" positioning panels, mechanism step-panel stacks, header bands. White/gold text on them. → **Our solid blocks must use `--color-primary`/`--color-ink` + a luminance-derived `--color-on-primary`, never the pale accent.**
- **Numbered pills** (white-on-dark rounded): "Mythos #N / FALLSTUDIE N / SCHRITT N / DENKFEHLER N / Irrglaube N".
- **Stat boxes / big-number callouts** — THE signature: **3-up big-number rows** on every case study; **before/after pairs** (172.549 € → 290.100 €; 14% → 50%; 10.000 → 50.000 €); **stat grids** ("Kernfakten" 3×2); cost-math strips (100 × 48 × 220 × 43,40 € = 763.840 €).
- **Light tint callouts** — "Tipp", insight panels, and **green-tinted "Ergebnis" result boxes** (positive outcomes) with check bullets.
- **CTA URL bands** — full-width saturated stripe; **the URL is the single biggest element**; often gold-underlined; a QR beside it where the brand uses QR.

### C4 — SOCIAL-PROOF apparatus (UNIVERSAL — and 100% MISSING from our output)
Every deck devotes real estate to credibility; this is a whole subsystem we never built:
- **"Bekannt aus" press-logo wall** — real press/marketplace logos (APEX: Forbes, Business Insider, AP, WAZ, Süddeutsche, Merkur, Rheinische Post; Buchagentur: Autorenwelt, BVA, Federwelt, Wikipedia).
- **Rating cards** — **Trustpilot** (Boss 4,3; Buchagentur 4,8), **Agenturmarkt** (Buchagentur 4,7), **Google**, **ProvenExpert / Capterra / Software Advice** (Werkzeugkoffer) — a platform logo + **star row** + score + review-count + "verifiziert".
- **Review-card grids** — **screenshot-style** testimonial cards: circular avatar/initial + reviewer name + date + **gold/green star row** + bold lead + body (Boss p10 ~9 cards; Ärztepartner p10 ~6; Buchagentur p10).
- **Client-logo wall** — a tidy grid of **grayscale/duotone client logos** ("Über 50+ zufriedene Kunden" Boss; Niklas ~14 logos; on white chips).
- **Partner/certification badges** — Siemens Technology Partner, Learning-Suite Certified (APEX); regional crest (Ärztepartner).

### C5 — DATA-VIZ (rhetorical, hand-styled, on-brand — not analytical)
- **Before/after comparison** — paired bars (80% vs 20%), paired columns (Ohne KI vs Mit KI; 14% vs 50%), or **✗-red "old" vs ✓-green/blue "new" two-column lists** (Niklas Zeitung-vs-Internet; Boss; Werkzeugkoffer).
- **Line / curve comparison** (rising "with us" vs flat/collapsing "without"; growth-over-time with A/B markers — Buchagentur, Boss, Ärztepartner).
- **Venn diagrams** (3 translucent circles → center concept "Autorität"/"Freiheit") — APEX, Buchagentur.
- **Donut / pie** (Boss "Wirtschaftsjahr").
- **3D isometric money infographics** — stacked coins, glossy columns, curved arrows, euro labels (Ärztepartner, APEX glossy columns, Werkzeugkoffer multiplication strip).
- **Cycle/loop + horizontal timeline flow** diagrams (APEX p6/p9).
- **Maturity ladder / numbered step flows** (Stufe 1–N; vertical navy-pill chains with curved arrows — Boss, Ärztepartner).
- All **brand-colored, flat or lightly-3D, no axis chrome** — persuasion, not analysis.

### C6 — Decoration / chrome (per-client richness)
- **Running header band** on every interior page: **logo (top-left) + a booking tagline + the URL** ("Trage dich zu einem kostenlosen Erstgespräch ein unter: www.X") + a thin rule. **Page numbers** bottom corner. (Ours has only a bare wordmark.)
- **Logo-MOTIF reused decoratively** — large on the back cover + a faint watermark + as the atmospheric shape (APEX peak/"X").
- **Per-client texture/atmosphere**: frosted-glass geometric shapes (APEX), parchment+gold-veining (Ärztepartner), paper-grain (Buchagentur), darkened cinematic photography (Niklas/Werkzeugkoffer). → a **per-client texture asset** + axis.
- **Line icons** (thin, often in a circle) for process steps / problem cards / checklists.
- **Oversized ghost/outline numerals** + **big quote glyphs** as decoration.
- **Gold/colored hairline rules** under eyebrows + as dividers.

### C7 — Persistent furniture
Running header (logo + booking tagline + URL) · page numbers · uppercase eyebrows · the brand wordmark · the per-client accent rule. Consistent on every interior page.

---

## §D. Per-page-type RECIPE library (canonical, brand-agnostic)

> Each recipe = the universal element set; per-client values (palette, photos, copy, URL) plug in. Photos/charts/social-proof are REQUIRED inputs, not optional.

- **COVER** — full-bleed founder hero OR founder-cutout-on-scene OR scene+stat-pills; top eyebrow/nav; giant (two-tone) display title + "Report 20XX / für [audience]" band; right teaser column ("In diesem Report" + "Fallstudien"); founder name+role; brand wordmark. *(Founder, not abstract art.)*
- **INTRO / Ausblick** — big serif (question) headline; framing essay; "Zielgruppe des Reports" check-list; often a founder photo.
- **ABOUT / Über-uns** — serif headline; positioning statement on a **dark panel**; **team photo**; **stat trio/grid**; **"Bekannt aus" press-logo wall**; **rating card**; author byline.
- **PROBLEM** — symptom list (numbered, big numerals) OR 2×3 icon-card grid; a dark insight/quote panel; sometimes a metaphor photo (iceberg/telescope).
- **MYTHS** — section opener (solid **dark** color-block); "Mythos/Denkfehler/Irrglaube N" pills; myth-quote + rebuttal; often a diagram (Venn/cycle).
- **CASE STUDY / Fallstudie** — kicker "FALLSTUDIE N"; result headline; **large named client portrait** (fixed slot) + name/role + **client URL** (+ QR if axis); **3-up big-number stat row**; sections **Ausgangssituation/Ziel/Lösung/Ergebnis**; **named pull-quote** (oversized quote mark); **green "Ergebnis" result box**; often a **device mockup** (phone ad / book).
- **MECHANISM / how-it-works** — numbered **step cards** + **horizontal/vertical flow diagram** (pills + arrows) + a **dark "Das Ergebnis" recap panel**; often a **maturity ladder** and a **device/dashboard** image.
- **DATA / proof** — a rhetorical **chart** (before/after bars, line compare, donut, 3D money infographic, cost-math strip) drawn from data.
- **SUMMARY / Fazit** — recap; a **These pull-statement**; **before/after stat boxes**; founder pull-quote + small portrait; CTA.
- **FAQ / objections** — numbered Q&A (square numerals); "mit mir persönlich" CTA + (small) QR/URL.
- **COLLABORATION / Ablauf** — full-width **banner/handshake photo** (optional); **numbered Schritt 1–N** cards/flow with durations; dark recap.
- **TESTIMONIALS** *(NEW page type)* — **Trustpilot/Google rating header** + a **grid of screenshot-style review cards** (avatar + stars + text).
- **LOGO WALL** *(NEW page type)* — "Über N+ zufriedene Kunden" + a **grid of grayscale client logos** + a CTA band.
- **BREATHING / atmospheric** — full-bleed per-client texture/atmosphere; geometric/logo motif; little/no text.
- **BACK-COVER CTA** — saturated/dark ground; short headline; **giant URL** (biggest type) + QR (if axis) + logo; per-client texture.

---

## §E. GAP ANALYSIS — our current output vs the DNA (why it reads "bland")

| # | Gap | Owner | Severity |
|---|---|---|---|
| 1 | **Founder photo not used as hero/anchor** (cover uses an abstract fal image; `founder.png` unused) | BOTH | ★★★ |
| 2 | **Entire SOCIAL-PROOF apparatus missing** — no press-logo wall, no rating cards (Trustpilot/Google), no review-card grid, no client-logo wall, no testimonials page | BOTH | ★★★ |
| 3 | **Client case-study photos too small + EMPTY boxes** (p9 Cordes blank); QR oversized stealing the space | BOTH | ★★★ |
| 4 | **Solid panels are PALE** (light-accent) instead of dark navy/primary authority panels | RENDERER | ★★★ |
| 5 | **No device/product mockups** (phone-ad, laptop-dashboard, book) | BOTH | ★★ |
| 6 | **No real charts/infographics** (before/after, line, donut, money infographic, cost-math) — bar_chart exists but unused/no data | BOTH | ★★ |
| 7 | **No running header band** (just a bare wordmark; missing the booking tagline + URL) | RENDERER | ★★ |
| 8 | **QR too big**; should be small/secondary | RENDERER | ★★ |
| 9 | **Too airy / dead white space** — not magazine-dense like Richard's interiors | RENDERER | ★★ |
| 10 | **No two-tone headlines** (serif neutral + bold-caps accent word) | RENDERER | ★ |
| 11 | **Comparison ✗/✓ "old vs new" columns** underused | RENDERER | ★ |
| 12 | **No per-client texture/atmosphere** richness (frosted-glass/parchment/etc.) | BOTH | ★★ |
| 13 | **No oversized quote marks / ghost numerals** decoration | RENDERER | ★ |
| 14 | **Pale tonal palette** makes the demo soft — Richard's are punchier (dark panels, contrasting accents). (Apex's cyan is data, but the demo would pop with a contrasting brand or stronger dark anchors.) | BOTH | ★★ |

---

## §F. RE-SCOPE — who builds what

### The PRE-PROCESSOR must SOURCE/GENERATE + MAP (expanded asset & data schema)
The pre-processor is **not just architecture-robustness** — it owns the **asset & data schema** that drives PDF quality. It must produce, per the page-type recipes:
- **founder photo** (from Drive) → cover/about slot; **client photos** per case study (Drive) → Fallstudie slots; **team photo** → about. *(Richard supplies via Drive; missing = his job.)*
- **press logos** ("Bekannt aus"), **client logos** (logo wall) → sourced/Drive, desaturated.
- **rating data** (platform + score + count + verified) → config/sourced.
- **testimonial/review cards** (name + stars + text + avatar) → content data.
- **device/product mockups** → **fal-generate or composite** (phone-frame around the client's ad creative; laptop dashboard; book mockup).
- **scene / atmospheric / per-client TEXTURE images** → **fal-generate** (driven by the `texture` axis + brand brief).
- **chart DATA** structured from content (before/after pairs, cost-math operands, money-flow figures) so the renderer can draw rhetorical charts.
- the **declarative image→slot MAPPING schema** per page type (which asset fills which slot), and the **axes** (`headline_type`, `palette`, `accent_mechanic`, `texture`, `qr_enabled`, `density`).

### The RENDERER must BUILD (expanded component library + recipes + page types)
- **Photo components:** `founder_hero` (full-bleed/cutout), `client_portrait` (large framed, fixed slot), `device_mockup` (phone/laptop/book frame), `scene_band`, `full_bleed_photo` (+ scrim).
- **Social-proof components:** `press_logo_wall`, `rating_card` (Trustpilot/Google star block), `review_card` + `review_grid`, `client_logo_wall` (grayscale) — and **two new page patterns: TESTIMONIALS + LOGO-WALL.**
- **Panels:** dark `authority_panel`/`recap_panel` using `--color-primary`/`--color-ink` + a luminance-derived `--color-on-primary`; `numbered_pill`; `stat_box` (3-up, before/after, grid); `result_box` (green tint); `cta_url_band` (URL = biggest element, optional QR by axis).
- **Charts (drawn from data):** `before_after_bars`, `line_compare`, `donut`, `money_infographic` (isometric), `cost_math_strip`, `comparison_columns` (✗/✓).
- **Chrome:** `running_header` (logo + booking tagline + URL + rule), `two_tone_headline` (serif neutral + accent caps), oversized `quote_glyph`, `ghost_numeral`, per-client `texture_layer` (axis-driven), smaller QR, **denser multi-column** layouts, spread (left/right) support.

### Net
The renderer **Plan B rebuild got the skeleton right** (tokens, Jinja macros, axis theming, the basic patterns) **but under-scoped the content systems** that actually create Richard's quality: founder-as-hero, the social-proof apparatus, device mockups, real charts, dark authority panels, two-tone headlines, density. The pre-processor **under-scoped the asset/data schema** that feeds them. **Both specs must be revised against this DNA before further building.** That is the corrected plan.
