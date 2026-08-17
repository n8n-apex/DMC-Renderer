# Richard's Infographic / Diagram Vocabulary + Text-Pairing (canonical)

**Date:** 2026-06-14
**Source:** forensic catalog of 81 visual devices across all 5 reference decks (buch, niklas, alex, aerzte, apexv1), deduped into archetypes + the text-complement role of each. Companion to `2026-06-14-richard-design-system-EXTRACTED.md`.
**Status:** the visual-device vocabulary the renderer must reproduce, flat-on-cream. No em dashes; verbatim client numbers only.

> **Blanket prerequisite (P0):** every existing viz preset is functionally right but cosmetically OFF-BRAND. They carry dark-glass fills + accent glow + drop-shadows (the locked viz.css recipe). Richard's devices are FLAT on cream, one depth plane: navy ink, teal-MICRO figures/series/arcs, light-gray `#CCC` context, faint <20% grid, hairline dividers, NO shadow/glow/gradient-depth. Re-theming the whole library flat-on-cream is the single biggest visible fix.

## The 13 device archetypes (what + how it pairs with text)

Each visual does ONE of six jobs, matched to the claim: **prove · quantify · contrast · sequence · summarize · break.**

1. **Portrait hero + stat/benefit band** (ubiquitous; prove+quantify) — founder face + KPI cluster/benefit list; cover & author pages. Flat, bounded portrait (no card/shadow), serif headline w/ teal keywords opposite. *Layout template, not a preset.*
2. **Big-numeral stat rail / KPI cluster** (ubiquitous; quantify+summarize) — 2-4 oversized serif figures + tiny caps labels, hairline dividers; teal MICRO on the figure only, or ONE floating dark island. Covers: `stat_strip`/`kpi_card`/`mega_numeral`/`money_bar` (re-theme flat).
3. **Before/after & versus** (common; contrast+quantify) — paired bars (teal "after", gray "before") or two label+figure groups with a thin connector. Covers: `ba_bars`/`transform_arrow`/`split_bar` (re-theme flat).
4. **Numbered problem/solution list** (ubiquitous; sequence+break) — big outdented serif numeral (teal/navy), hanging indent, NO boxes; the single most common device. *Mostly a layout/type pattern; `step_cascade` partial.*
5. **Sequential process / methodology flow** (common; sequence+summarize) — ordered step plates / phase ladder / single curved arrow; teal-MICRO numerals + hairline connectors; durations as a Gantt bar set. Covers: `step_cascade`/`phase_timeline` (re-theme flat, no dark spine).
6. **Proportion / part-to-whole** (occasional; quantify+summarize) — donut/ring/gauge/waffle/split; teal arc on light-gray track, verbatim figure centered. Covers: `donut`/`completion_ring`/`gauge`/`icon_array`/`radial_cluster`/`split_bar` (re-cut flat, strip glow).
7. **Ranked / categorical bars** (occasional; quantify+contrast) — sorted horizontal bars, teal primary + gray context, figure at bar end. Covers: `ranked_bars` (re-theme flat).
8. **Trend / time-series line chart** (occasional; quantify+prove) — curve over time, teal primary + gray secondary, faint grid. **MISSING / deferred — build flat-on-cream.**
9. **Conceptual / spatial diagram** (common; contrast+summarize+break) — Venn, brain-quadrant, exploded burst, mechanism/gears, domino cascade, 2x2 grid; thin navy/teal outlines, teal-tint overlaps, floating callouts. **Mostly MISSING** beyond `venn`; build flat editorial line-work (not 3D/airbrush).
10. **Social-proof wall** (common; prove+quantify) — logo wall (grayed), testimonial cards (soft-tint or pull-quote, not dark cards), rating badges (teal-MICRO stars). **MISSING as components.**
11. **Full-bleed photo + dark overlay + footer CTA** (common; prove+break+act) — the ONE sanctioned dark-ground archetype; closing/Fazit + emotional dividers. *Layout recipe.*
12. **Device / product mockup showcase** (common; prove+break) — bounded phone/laptop/book on cream, no card/shadow. *Image-asset placement; layout reserves the pocket.*
13. *(within #1/#4)* **Author/credential sidebar + pull-quote** — inline portrait breaking dense prove, with a pull-quote band.

## Text-pairing principles (encode these in the layout)

1. **Cohabit the same Y-band.** Text + its paired visual sit side by side at the same vertical anchor (2-col 50/50 or 35/65/30-70), never stacked into a leftover bottom strip. The visual starts where its paragraph starts.
2. **One dominant anchor per page** (max 1-2 visuals); the hero gets cream air on all sides; a chart gets its own ~60-65% pocket, never wedged.
3. **The visual does one of six jobs, matched to the claim** (prove/quantify/contrast/sequence/summarize/break). Pick the device by what the copy is doing, not by decoration.
4. **Balance across the spread, not the page.** Text-heavy page faces a visual-led page; dense sections get a story-left / proof-right spread; ~55% content / ~45% breathing, page ends where content ends.
5. **Numbers before narrative.** Quantitative devices are placed to be scanned first, then prose explains the mechanism. Never repeat a metric more than once per spread.
6. **Wayfinding in the margin, not banners.** Floating eyebrow + serif headline (1-3 teal keywords) + rotated trim side-labels + optional ghost numerals. No solid header bars, no dark full-height sidebars.
7. **One depth plane.** Everything floats on continuous cream: no white cards, borders, or drop-shadows. Contained devices use a SINGLE floating dark island in the middle third with cream air around it.
8. **Teal is the pointer, not the paint** (≤8-10% page weight): the keyword, the stat figure, the primary series, the active step number, the rating, the chip. Everything else navy ink + muted gray context.
9. **Close monumentally.** The emotional/CTA beat abandons the 2-col grid for a full-bleed dark ground, centered white serif, minimal link/QR. The one sanctioned dark archetype, earning weight by contrast with the cream pages.

## Coverage gaps (prioritized)

- **P0 — Re-theme the entire existing viz library flat-on-cream** (strip dark-glass/glow/shadow/gradient-depth; rebuild on transparent cream w/ navy ink, teal-MICRO, gray context, faint grid, hairlines). Closes the biggest tell and realigns ~80% of quantitative devices at once.
- **P1 — Trend/time-series line chart** (missing/deferred; build flat-on-cream).
- **P1 — Conceptual/spatial diagrams beyond Venn** (brain-quadrant, exploded burst, mechanism/gears, domino cascade, 2x2 grid) as flat editorial line-work.
- **P2 — Social-proof devices** (logo wall, testimonial array, rating badge) flat-on-cream.
- **P2 — Composed layout patterns** that are NOT data presets but are the most frequent devices: portrait-hero+stat band, big-numeral hanging-indent list, numbered icon+photo+text blocks, bounded mockup pocket, full-bleed dark photo + CTA / Fazit. Belong in the per-page-type LAYOUT templates so presets have correctly-shaped pockets.
- **P3 — Semantic-color discipline:** good/after vs bad/before carried by teal-vs-gray (single semantic green only where it truly means saving/down), never a decorative second color.
