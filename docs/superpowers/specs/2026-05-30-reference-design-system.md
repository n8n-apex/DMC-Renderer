# DMC Report — Reference Design System (the build target)

**Date:** 2026-05-30
**Purpose:** The concrete, **brand-agnostic** design system reverse-engineered from Richard's finished reference (`APEX - KI DMC Report v1 (1).pdf`), used as the QUALITY BAR for the renderer rebuild (architecture-migration spec, step 6). Colors/fonts here are described as **roles**, never client hexes — per-client values flow from brand tokens + §4.0 axes. The reference is an *example* of the grammar applied to one client, not a schema source.

> Pairing: design *rules* trace to `richard-grammar-v2.md` (§2 patterns, §3 color/accent, §4.0 axes, §6.1 anti-patterns). This doc records how those rules look when realized, so the rebuilt patterns have a concrete target.

---

## A. Global system (every interior page)

- **Grid:** A4 portrait, ~18–22mm margins, generous whitespace. Default **two-column body** with a wide gutter; often a narrow **sidebar** (photo / name+role / QR / pull-quote) + a wide text column. Copy never fills edge-to-edge.
- **Color (roles, not hexes):** `--color-ink` (dark) = headings + body + cover ground; `--color-accent` = numbers, links/URLs, kicker pills, list/step markers, chart bars, rules — **never body copy** (§3.7); `--color-accent-tint` = panel/callout/badge fills; `--color-surface` = page background. Accent area ≤ ~10%/page (§3.6). For a **tonal** brand (`accent_mechanic=tonal_same_hue`, e.g. apex's cyan) these resolve to one hue family — correct, just less contrast than a 2-hue brand; for `contrasting_hue` the accent pops. Either is valid; it's data.
- **Type system:** **display = serif** (high-contrast/Didone) for section headlines, large; **body = sans**; **labels/eyebrows = sans, uppercase, letter-spaced**; **stat numbers = large, accent**. Display family is chosen by the `headline_type` axis (serif | sans | sans_allcaps), NOT hardcoded.
- **Persistent chrome:** top **header band** (wordmark + thin vertical divider + small uppercase eyebrow); **folio** bottom-left over a **pale gradient wash** that anchors the page bottom.
- **Motifs:** rounded **kicker/badge pills** (uppercase label); large **numbered markers** (numerals, not bullets); thin rules under eyebrows; low-opacity **geometric accent shapes** (the brand's logo motif) on CTA/atmospheric pages.
- **Photos:** full-bleed (cover), full-width banner (collaboration), or framed **sidebar portrait crops** (case studies) — flush, no heavy frames. **Charts/stats:** horizontal **stat strips** (big accent numbers + captions), **bar/column charts** (accent bars + labels), **flow/step diagrams** (connected boxes), floated **stat-callout cards**.

## B. Per-ST layout (brand-agnostic)

- **ST-01 Cover:** full-bleed hero photo + dark scrim; top nav/eyebrow row; lower-left serif name + role; huge serif title; a vertical **stat rail** of short data callouts; subtitle bar.
- **ST-02 Outlook:** large serif question-headline; two-column body; a tint **check-list panel** (audience/"Zielgruppe").
- **ST-05 About:** serif heading; body + a **stat trio** ("in Zahlen", big accent numbers); a grayscale **logo wall** ("bekannt aus").
- **ST-09 Status-quo:** serif heading; intro; **numbered symptom blocks** (big accent numeral + bold title + body); a tint **insight/tip panel**.
- **ST-14 False-beliefs:** section opener with a **solid accent color-block** behind the heading; **numbered belief→reality** blocks (myth quote + distinct "Realität" sub-block + source); optional "ohne/mit" two-panel contrast.
- **ST-07A Case study:** **kicker pill** (FALLSTUDIE n); serif headline; **left sidebar** = portrait + name/role + accent link + **QR** + pull-quote; **right column** = a **stat strip** + uppercase section labels (Ausgangssituation/Ziel/Lösung/Ergebnis) with body.
- **ST-07B Theory:** serif headline; prose; a distinct **key-insight callout** (accent rule + larger italic + tint panel); optional before/after.
- **ST-06 Mechanism:** **numbered step cards** (accent numeral + title + body); a **horizontal flow diagram** of connected boxes; a dark **"Das Ergebnis" recap panel**; optional **bar chart + floated stat-callout cards**.
- **ST-08 FAQ:** serif heading; two-column **Q&A stack** (accent question + body answer).
- **ST-22 Collaboration:** **full-width banner photo** header; **horizontal numbered step flow** (Schritt 1→N) with connectors + optional durations.
- **ST-31/32 Atemseite (breathing):** full-page atmospheric ground (brand texture/gradient asset + translucent geometric shapes), little/no text — a deliberate pacing page.
- **ST-FAZIT Summary:** serif "Zusammenfassung" header band; recap body; a large **These pull-statement**; a **cost block**; a full-width **accent URL band**.
- **ST-03 Hard-CTA back cover:** saturated brand-ground page + low-opacity geometric shapes; short headline; **oversized accent URL** (biggest type on page) as a full-width button; **QR** + logo.

## C. The 22-item richness checklist (the rebuild MUST hit each)

1. Persistent top header band (wordmark + divider + eyebrow). 2. Folio over a bottom gradient wash. 3. Rounded kicker/badge pills. 4. Large accent stat numbers in strips. 5. Floated stat-callout cards. 6. Tint panels for checklists/insights. 7. Two-column body with a sidebar. 8. Full-bleed cover photo + scrim + overlaid title + stat rail. 9. Full-width banner photo (collaboration). 10. Accent numbered markers (not bullets). 11. Solid accent color-block behind a section opener. 12. Horizontal flow/step diagram with connectors. 13. Bar/column chart. 14. Before/after ("ohne/mit") two-panel contrast. 15. Giant full-width URL CTA buttons. 16. Grayscale logo wall. 17. Pull-quote treatment (sidebar). 18. Serif display vs sans body (two families). 19. Uppercase letter-spaced in-body section labels. 20. Low-opacity geometric accent shapes (CTA/atmospheric). 21. Embedded QR in case-study sidebar. 22. Dedicated atmospheric/breathing page.

Each device is realized with **token-driven colors + axis-driven type**; none carries a client literal. This list is the visual-regression + reviewer acceptance bar for step 6.
