# Path to Richard-Quality + Inputs Needed From the User — 2026-06-06

**Source:** user's visual review of the live apex render (cover p1, status-quo p2, about p3, methodik p16, + back cover p21 and the liked pages p12/p14/p15) on 2026-06-06. This doc captures (a) the diagnosis of what's holding visual appeal back, (b) the architectural principle the user set, (c) the re-prioritized build path, and (d) **the inputs the user must provide** — because this is input-dependent software and several quality ceilings are set by inputs, not code.

---

## 0. The architectural principle (user-set, now binding)

> "The pre-processor is not supposed to handle photoputting. That should be done by the renderer… The pre-processor should essentially give **data** and create **space layout / schematics** for the renderer to put the data over there in a more beautiful way."

**Division of labour (locked):**
- **Pre-processor = DATA + LAYOUT SCHEMATIC + ASSETS.** It outputs: the typed content/data, a per-page *space schematic* (which regions exist, what goes in each, how much space each gets, copy-fit budgets so copy is sized to the area), and the resolved assets (generated backgrounds, resolved photos). It does NOT place pixels.
- **Renderer = BEAUTIFUL PLACEMENT.** It takes the schematic + assets and does the visual craft: attach backgrounds (full-bleed where wanted), place photos in frames, distribute copy to fill regions, align everything. "Photoputting" lives here.
- **Post-processor (Layer 3) = two output variants:** **digital** (full-bleed backgrounds, screen RGB) and **print** (bleed marks, CMYK, legibility-safe). The user explicitly wants the *digital* variant to have backgrounds expanded to the full page edge-to-edge.

This reframes the remaining Phase-B/C items: backgrounds-on-all-pages and copy-distribution are **renderer** jobs fed by **preprocessor schematics + assets**.

---

## 1. What the user observed → diagnosis → owner

| # | Observation (user) | Diagnosis (verified) | Owner / type |
|---|---|---|---|
| 1 | "The percentage number on the top-right of the cover is misaligned / cut off." | `.cv-rail` is fixed `width:50mm` but stats render at `--type-stat-xl` (60pt); a long value ("30-50%") is wider than 50mm → overflows off the right page edge. | **Renderer BUG** (st_01.css). Fix: long-value step-down (like st_07a `_is_long_value`) or widen/auto-size the rail. |
| 2 | "The background should expand entirely to the page; it's not full-bleed." | Content pages sit inside the @page margins (white border); only ST-01/31 are full-bleed. | **Renderer capability** — full-bleed ground option for content pages (digital variant). |
| 3 | "The background is dull — not the one we generated. The generated ones should show on ALL pages. Why aren't they?" | The real generated `report_assets` (atmospheric/marble/texture) are consumed only by ST-31/ST-22; the 8 content pages show only Phase-A's procedural grey grain ground. | **Renderer capability** (PBR-A, now bigger): attach the *generated* background behind every content page. |
| 4 | "The copy is jagged — enclosed and tight. The area isn't used to distribute the writing." | Per-pattern layouts leave the copy in cramped blocks with large empty bands (e.g. p2 status-quo: two tight columns up top, big white void below). The preprocessor hands the renderer copy without a space schematic / copy-fit, so the renderer can't fill the area. | **Both:** preprocessor must emit a *space schematic + copy-fit budgets*; renderer must distribute copy to fill. |
| 5 | "Pages 10/11 have backgrounds; why not elsewhere? If that's a renderer job, keep it there." | Correct — ST-31 breathers resolve a ground; content patterns don't. | **Renderer** (same as #3). |
| 6 | "Alignment issues inside pages." | Per-page micro-alignment (baselines, column edges, stat blocks) not yet audited at canon type. | **Renderer** — per-page alignment audit. |
| 7 | "I like p12, p14, p15 — and p12 could use a marble background like p11." | The fill case studies read well; even they want the atmospheric ground. | Confirms #3 — grounds wanted even on the good pages. |

**Net:** the dominant levers are (A) **show the real generated backgrounds full-bleed on every page** (renderer), (B) **distribute the copy to fill the area** (preprocessor schematic + renderer), (C) **fix alignment/overflow bugs** (cover stat, per-page). These are *capability + craft* — but several quality ceilings above them are set by **inputs** (§3).

---

## 2. The build path to Richard quality (re-prioritized with this feedback)

Ordered by visual-appeal impact × independence. Each: brand-agnostic, token-only, verify on pixels.

1. **Cover stat overflow fix** (renderer bug, quick) — long stat values step down / rail auto-sizes so nothing clips. [#1]
2. **Generated backgrounds on every page, full-bleed** (renderer; was PBR-A, now the headline) — content patterns resolve the report atmospheric/texture ground and render it as a full-bleed layer behind the content, with copy on a legible scrim/panel. Graceful fallback to today's ground when no asset. This is the "digital variant" full-bleed look. [#2,#3,#5,#7]
3. **Copy distribution / anti-cramping** (preprocessor schematic + renderer fill) — preprocessor emits per-page *region schematic* + *copy-fit budgets* (target copy length per region so it fills, neither cramped nor void); renderer distributes copy to the regions and removes dead bands. [#4]
4. **Per-page alignment audit** (renderer) — baselines, column edges, stat blocks, header alignment, at canon type. [#6]
5. **Remaining PBR items** — fazit background (D), social-proof component (C), ST-builder infographics renderer-head (B-renderer), each fed by the schematic principle.
6. **Layer-3 post-processor** — split digital (full-bleed RGB) vs print (CMYK + bleed marks), per the user's two-variant model.
7. **Phase C/D (imagery quality)** — print-res images, art-directed background generation (so backgrounds aren't "dull"), founder/asset quality — *gated on the inputs in §3*.

---

## 3. INPUTS NEEDED FROM THE USER (the core answer)

This software is input-dependent: several quality ceilings are set by what comes IN, not by the renderer. Below, by impact, with the format/quality that matters and what the system does WITHOUT each (graceful fallback) so the cost of omitting is clear.

### Tier 1 — the biggest "generic → designed" levers
1. **Brand typeface files (licensed `.ttf`/`.otf`)** — display + body (e.g. APEX's real "Gestura Headline").
   - *Why:* the #1 generic tell. Today the brand font can't load → falls back to Source Serif/Sans, so every deck reads "templated." Richard's decks use the real brand face.
   - *Caveat:* WeasyPrint only loads fonts with a format-12 cmap; we verify embedding with `pdffonts`. If a provided font won't load, we pick a curated premium near-match.
   - *Without it:* curated premium fallback (Source family) — good, but not the brand's identity.
2. **High-resolution founder + team photography** — professional, **≥2480px long edge** (300dpi A4), clean/branded background.
   - *Why:* the cover hero + about/team. Scraping yields variable, sometimes soft, images; a provided pro photo is dramatically better and print-safe.
   - *Without it:* best scraped image (quality varies), or a flagged empty slot (never a fake person).
3. **Real client social proof** — the single biggest *content* gap:
   - **Client logos** (vector/PNG) for the "bekannt aus" / references wall.
   - **Client case-study photos** (real faces/scenes) for the ST-07A portraits.
   - **Testimonials** (quote + name + role + company) — REAL, never fabricated.
   - **Per-case metrics** (the real before/after numbers).
   - *Why:* Richard's decks are dense with real logos, faces, quotes, numbers. Ours render text-on-panels because this content isn't supplied.
   - *Without it:* graceful no-box (no fake logos/faces/quotes) — but the page stays sparse.

### Tier 2 — data + identity
4. **Structured data for charts & stats** — the real numbers as DATA, not buried in prose (before/after %, € amounts, timelines, counts).
   - *Why:* feeds the chart engine + crisp big-number stat callouts. Today numbers are trapped in prose ("prose-as-stat"), so charts/stats stay empty.
   - *Without it:* conservative prose→chart extraction only (limited), prose stays prose.
5. **Logo files** — wordmark + icon mark, **vector (SVG/PDF) preferred** — cover, back cover, header, sign-off.
6. **Full brand palette** — primary + accent + 2–3 secondary/neutral, OR a **brand URL** for onboarding to extract.
   - *Without it:* primary+accent+grey ramp only (the layered brand color is lost).
7. **Brand personality / the 7 design axes** — headline serif|sans, light|dark ground, texture (e.g. marble / frosted-glass), density, accent behaviour, QR yes/no — OR a **brand URL** so `/onboard` derives them.
   - *Without it:* sensible defaults → two different brands get structurally similar decks.

### Tier 3 — generation art-direction (mostly system-side, optional input)
8. **Background/texture style direction** — a one-line style or 1–2 reference images (e.g. "frosted-glass geometric like our site", "warm marble") so the generated atmospheric backgrounds match the brand and aren't "dull."
   - *Why:* you noticed p11's marble is good and want that quality everywhere; the generation prompt currently produces generic/dull grounds.
   - *Without it:* a generic atmospheric prompt (the "dull" look).
9. **Copy length discipline** — if you control the upstream content prompt, target per-section word counts so copy fits each region (or we enforce copy-fit and flag overflows like the Hanisch case study).

### What is already handled (no input needed)
Layout grammar, type scale, depth/grain, the closed-loop quality scoring, brand-agnostic theming, page furniture, the fill compositions, the QR/CTA, the back-cover skeleton.

---

## 4. The honest split: inputs vs. code

- **Code can deliver now (no new input):** full-bleed generated backgrounds on every page (the assets already exist per render), copy distribution + anti-cramping schematics, alignment/overflow fixes, the Layer-3 digital/print split, the remaining PBR items. → these are the next build items.
- **Inputs raise the ceiling:** the brand FONT (Tier-1 #1), real PHOTOS (Tier-1 #2), real SOCIAL PROOF (Tier-1 #3), and structured DATA (Tier-2 #4) are what separate "well-built generic" from "Richard." No renderer trick manufactures a real client logo or the brand's actual typeface.

**Recommended first move from the user:** provide Tier-1 #1 (brand font) + #2 (a hi-res founder photo) + #3 (client logos/testimonials/metrics) for one real client. That, plus the code items in §2.1–§2.4, is the fastest path to a deck that reads like Richard's.
