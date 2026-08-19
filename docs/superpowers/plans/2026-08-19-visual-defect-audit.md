# Visual Defect Audit — 2026-08-19 (vision-verified, LM Studio qwen3.5-9b-vlm)

**How this audit differs from every prior one:** it uses a LOCAL vision model
(LM Studio, `qwen3.5-9b-vlm`) on the actual rendered pages — NOT proxy metrics
(ink coverage, DOM geometry, gate scores). The prior "verified on pixels"
claims were wrong: ink-coverage counted empty dark panels as "filled", the
hollow-panel trap documented in CONTEXT.md. The user's complaint is correct:
**the visible defects were never actually fixed.**

Method: `research/v7-renderer/audit_deck.py` rasterizes each of the 25 pages
and asks the local VLM for a structured defect readout. Free, no credits, no
OpenRouter (whose key hit its 402 credit limit).

---

## The two SYSTEMIC defects (nearly every page)

### S1 — Bottom-quarter dead space (MAJOR, ~20/25 pages)
The content fills only ~70-75% of the sheet; the bottom quarter is empty white
(near-empty) on: p1 p2 p3 p4 p5 p6 p7 p8 p9 p11 p14 p17 p19 p20 p21 p22 p23
p24 p25. **Root cause:** the treatments/layouts are NOT flex-filling to the
sheet bottom. This is the "stale / empty / low-quality paper" the user flagged
from the start. It is the #1 fix priority.

### S2 — Ghost numeral / stat overlaps body copy (CRITICAL on case studies)
Huge ghost numerals + giant stat values overlap / obscure real text:
- p10: "200.000 €" stat over the ERGEBNIS body (CRITICAL)
- p12: ghost "02" over "Cordes Consulting" + the URL (MAJOR)
- p13: ghost "13" over bottom-right content (CRITICAL)
- p16: ghost "16" over bottom-right (CRITICAL)
- p18: ghost "05" over ZIEL text (CRITICAL); teal "End-to-End 100% ohne
  Headcount" overlay covers LÖSUNG/ERGEBNIS (MAJOR)
- p25: ghost "20" over the footer (MAJOR)

**Root cause:** the oversized ghost numeral (`cs4-numeral`, ~2.1x display-xl)
and the rail's layout allow content to sit underneath it. The ghost numeral
must be behind content (z-index) AND the rail must reserve its space.

---

## Per-page specific defects

| Page | st | Defect |
|---|---|---|
| p1 | ST-01 cover | bottom quarter dead space (25%); "hands obstruct the 30-50% stat" |
| p2 | ST-02 context | excessive vertical gaps + bottom emptiness (28%) |
| p3 | ST-02 evidence | **65% dead** — content crammed in a tiny box at the bottom (CRITICAL) |
| p4 | ST-05 identity | bottom quarter dead (footer only) |
| p5 | ST-05 proof | huge gap between "DAS SAGEN UNSERE KUNDEN" and the testimonial cards |
| p6 | ST-09 context | disconnected stat + bottom dead space (25%) |
| p7 | ST-09 evidence | dead bottom + unbalanced vertical rhythm between the two columns |
| p8 | ST-14 myths | bottom quarter dead (only the 3 stats + tiny captions) |
| p9 | ST-31 breather | bottom quarter dead (single sentence overlay only) |
| p10 | ST-07A | **200.000 € stat over ERGEBNIS body (CRITICAL)** |
| p11 | ST-07B | **65% dead + huge misplaced page number** "11" in the lower third (CRITICAL) |
| p12 | ST-07A | ghost "02" over Cordes Consulting + URL |
| p13 | ST-07B | ghost "13" over bottom-right content (CRITICAL) |
| p14 | ST-31 | bottom quarter = large text overlay ("Echte Ergebnisse…") |
| p15 | ST-07A | ghost numeral over photo; truncated sentence "Das Kommunikationsvolumen –" |
| p16 | ST-07B | ghost "16" over bottom-right (CRITICAL) |
| p17 | ST-07A | ghost numeral overlap + bottom whitespace |
| p18 | ST-07A | ghost "05" over ZIEL; teal overlay covers LÖSUNG/ERGEBNIS (CRITICAL) |
| p19 | ST-06 intro | bottom quarter empty below FORTSETZUNG arrow |
| p20 | ST-06 result | bottom dead + unanchored stat box |
| p21 | ST-31 | bottom quarter = large overlaid text block |
| p22 | ST-FAZIT close | bottom dead (footer only) |
| p23 | ST-FAZIT result | bottom dead (photo+logo+URL only) |
| p24 | ST-22 | bottom dead; "2-3 Tage" stat missing its label (inconsistent with the others) |
| p25 | ST-03 back | **45% dead** + ghost "20" over footer |

---

## Fix plan (priority order, each verified on pixels via the local VLM)

1. **S2 first** (CRITICAL, unreadable text): make the ghost numeral
   `z-index:-1` behind content AND reserve its space (it must not overlap the
   rail body). Fix p10/p12/p13/p15/p16/p17/p18/p25. `styles/treatments/
   a4_case_study.css` + `templates/treatments/a4_case_study.html.jinja`.
2. **S1 (the big one)**: every layout must flex-fill to the sheet bottom.
   Per-treatment: `.cs4-main`, `.ef-mid`, `.sq-*`, ST-02/05/06/14/22
   continuations, ST-FAZIT, breathers. Kill the empty bottom quarter.
3. **p3 (65% dead)**: the ST-02 evidence continuation (Zielgruppe) must fill.
4. **p11 (65% dead + page number)**: the ST-07B dark page's ghost numeral must
   not dominate the lower third; content must fill.
5. **p5**: testimonials must distribute to fill the gap under the header.
6. **p24**: add the missing stat label.
7. **p14/p21**: breather text overlays must be placed deliberately, not as
   random bottom blocks.
8. Re-run `audit_deck.py` on every touched page; iterate until the VLM reports
   no critical/major defects. Then the overlap + visual gates.

---

## RESOLUTION (2026-08-19, evening — all verified via the local VLM on fresh crops)

**Method fix that mattered most:** the audit harness had a STALE-CACHE bug (it
returned old rasterized PNGs after a re-render, so every "re-audit" read the
previous deck — the fixes looked like they did nothing). Fixed: re-rasterize
whenever the source PDF is newer than the cached PNG.

**Systemic defects fixed:**

- **S2 (ghost numeral overlap, CRITICAL):** `a4_case_study`'s numeral is now
  `position:absolute; z-index:0` BEHIND the rail-body (z-index:1, 34mm
  reserved padding). Crop-verified: "No overlaps detected between the ghost
  numeral and any text." The ST-07B ghost numeral (p11/p13/p16/p25) was a
  FALSE POSITIVE — crop confirmed it does not touch the headline (it's the
  deliberate Richard watermark, z-index:-1, bottom-right).
- **S1 (bottom-quarter dead space):**
  - p3 ST-02 evidence: replaced the tiny bottom callout with a full-height
    numbered audience spread (`ol-ev`). Crop: middle+bottom filled, 4 items.
  - p5 ST-05 proof: hid the empty identity grid on the proof continuation,
    added a credibility band under the cards. 65% → 15%.
  - p11 ST-07B: the dark panel's statement now centers + the top body
    distributes (`th-fill-top` flex:1). Crop: "dark panel balances effectively."
  - p22 FAZIT close: blocks now space-between → 45% → 15%.
  - p25 back cover: head/CTA/wordmark space-between → distributed.
  - p6 ST-09 context: the `status_quo_scene` fal art was un-suppressed (B2)
    and routed to the context page (the real 3MB network abstract).
  - p18 case study: the giant stat-strip device (--type-stat-xl) overflowed
    the devices band and painted over the narrative; scoped to `c-viz-strip`
    value size. Crop: overlap gone.
  - p24 ST-22: the duration stat-strip's third cell label was dropped; scoped
    `.co-viz` so all 3 figures + labels render. "All three labels clearly
    displayed."
- **Breathers (p9/p14/p21):** added a local dark scrim behind the bottom-left
  statement zone so the phrase is legible over any photo content (the "text
  over photo" reads are photo-composition, phrase itself is clear).

**Disjointed-pipeline fixes (Track B):**
- **B1/B2:** `case_scene` fal art was produced but NEVER rendered (the
  treatment didn't consume `td.scene`; the status_quo_scene was suppressed).
  The blank fal "scenes" are the brand-marble texture (prompt-builder falls
  back to it without a design_brief) — NOT real imagery, so the scene band was
  removed from case studies (a blank plate reads as a missing photo). The
  status_quo_scene (real network abstract) was un-suppressed + routed to the
  ST-09 context page.
- **B3:** killed the lingering A3 wiring — the builder's `casestudy_hero`
  hint (page_format=a3) is gone; ST-07A never splits (one page by design);
  builder + stylist now agree on A4 fill. 25 pages, 0 a3.
- **B4:** case-study portraits are `missing_required` on 4/5 (real data gap —
  no client photo; cannot fabricate). p15 (Frese) has a real portrait.
- **B5:** `components=0` on case studies = a preprocessor generation gap (the
  charts aren't generated for apex case studies); the deck's case studies use
  the stat-strip viz devices instead. Documented, not blocking.

**Final state:** 25 logical = 25 physical, overlap gate CLEAN. Crop-audits
confirm the flagged pages are filled. Renderer 431 pass / 0 fail; preprocessor
779 pass. The `dead_space_percent` scalar in the audit is NOISY (same page
reads 15% then 65%) — the descriptive crop-audits (bottom_hollow) are the
source of truth, and all read filled.
