# Richard's DMC-Report Design System — Forensic Extraction (canonical)

**Date:** 2026-06-14
**Source:** forensic analysis of Richard's real hand-designed decks (`refs/buchagentur.pdf`, `refs/niklas_niemeyer.pdf`, `refs/alexander_boss.pdf`, `refs/aerztepartner.pdf`), 6 dimensions, 72 findings, rendered to PNG and read on pixels.
**Status:** THE target style. The renderer must be re-architected to this. Supersedes the current "big banner / dark sidebar / white ground / crammed" output.

> No em dashes anywhere (user rule). All client numbers stay verbatim (no fabrication).

## USER OVERRIDES (binding, take precedence over the extraction below)

1. **Keep visual DEPTH.** Do NOT flatten everything / strip all shadows. Depth is what reads premium. Remove only the gaudy neon cyan GLOW (bright accent-tinted shadows). Tasteful neutral dimensionality, dark island panels, photographic depth all stay. (Overrides the "zero shadows, one flat plane" wording below.)
2. **EVERY page carries a visual.** Each page must have an infographic / diagram / chart / photo matched to its content. No page is text-only.
3. **Fill the page.** No parked empty areas (esp. bottoms). Distribute content + visual to fill; if a page is text-light, the visual fills it.
4. **Image pages: shrink the text, feature the image, ADD an infographic** to visualize data. Image + lean text + data-viz on the same page = aesthetic + informative.
5. **Page count is NOT a constraint.** Use as many pages as the layout needs (split dense pages, give visuals their own room). Never cram to hit 20.

---

## The system

### Ground & texture (the #1 rule)
- Warm cream ground **#F6F3ED** (range R245-250 / G242-247 / B235-243), **never pure white**. Near-imperceptible paper grain (mono noise 1-2% or woven texture ~0.5%).
- The ground reads **continuously behind every element**. No white cards, no container fills, no border-boxes, **zero drop-shadows**. Everything shares one depth plane, floating on cream.

### Color (4-color, surgical)
- Cream ground `#F6F3ED`.
- Ink/body **soft navy `#2E3E50`** for ALL text + headlines (never black).
- **Muted teal accent `#4A7C7E`** (sage `#6B8B7E`), MICRO only: 1-3 headline keywords, 2-4 stat figures, chart primary series, small chips, hairlines. Teal ≤ ~8-10% of page weight. Never a banner / full-height fill.
- **Dark island panel `#1A3A36`** (deep teal) or `#1E3A4C` (navy) — only for discrete contained panels (stat rails, pull-quote bands), never structural framing.
- Footer neutral warm gray-brown `#5E5E58`. Secondary chart series light gray `#CCC` low-opacity. Soft-callout tints `#E8F4F1` / `#F5F5F3`.

### Type (serif/sans contrast IS the hierarchy, not weight or color blocks)
- **Headlines: serif** (Garamond/Bodoni-class), navy, left-aligned. Primary 40-48pt, secondary 28-32pt, leading 1.1-1.2. **1-3 keywords tinted teal inline** (full word, no box/underline).
- **Body: sans** (Helvetica/DIN-class) ~11pt, leading 1.5-1.6, navy, never tight.
- Subhead sans 14-16pt navy. Eyebrow/kicker sans 8-9pt ALL-CAPS +0.05-0.15em tracking, navy or teal, 8-12mm above headline. Section markers (Ausgangssituation/Ziel/Umsetzung/Ergebnis) small-caps sans 9pt navy, tracked. Pull-quote serif 16-22pt. Headline:body ratio ~4:1. Eyebrows + section markers stay navy; teal is reserved for headline keywords + data.

### Grid, margins, baseline rhythm
- Outer margins ~0.5-0.6in (top 8-12%, sides 6-8%, bottom 6-8% breathing footer zone). Content never touches the edge except deliberate full-height case-study photos.
- **2-column, adapted per page type**: balanced 50/50, asymmetric 30/70 (case study), 35/65 / 40/60 (content+data). Gutter generous ~0.5in.
- **Text and its paired visual COHABIT the same Y-band** (side by side), not stacked.
- Baseline unit ≈ 18pt; all vertical spacing in 6pt multiples (headline→body ~24pt, block→block 20-28pt, cluster 8-12pt). No two elements within ~0.5cm.
- Target **~55% content / ~45% breathing; never exceed ~70% content coverage.**

### Headers (NO banner)
- Eyebrow + serif headline (teal keywords) + sans subhead, floating on cream, ~12-18% page height, 8-12mm air above / 12-15mm below. No fill, no bar, no bottom border.
- Optional **ghost numeral** "01"-"07" in light gray `#E4E4E0` 8-15% opacity, 180-280pt, horizontal, parked upper-right within the header band only.

### Footers & running elements (understated)
- Page number bottom-right outer margin, sans 8-10pt, muted gray-brown `#5E5E58`. Optional small wordmark + plain-text URL same tone. Optional 0.5pt light-gray hairline, or nothing. Float far apart, no fill/box.
- **Rotated side-labels** ("FALLSTUDIE 01", "BONUS: …") 90° along the trim, 2-3mm from edge, condensed sans 6-8pt, muted gray/teal — these REPLACE dark vertical sidebars.

### Elements
- **Stat rail:** dark navy/teal island panel, teal/white numeral 48-72pt over small label, stacked w/ 12pt gaps; embedded mid-column or right-of-margin, NOT full-height.
- **Numbered list:** big outdented teal/navy numeral 40-48pt, hanging indent, no box.
- **Pull-quote:** contained dark band, white serif 18-22pt, 40-48pt quote-mark, attribution cream — a deliberate section break.
- **Soft callout:** light-tint panel 2-3cm, navy text — never a dark full-height sidebar.
- **Chip-row:** light-teal pills, navy text 8-12pt, in flow.
- **Photo:** bounded, inset ~0.25-0.5in, thin border or none, NO card/shadow, caption 8-9pt below. Case-study hero may bleed to the OUTER edge only.
- **Charts:** directly on cream (transparent bg), no fill/heavy-border/shadow, faint <20% grid, teal primary; ~60-65% column width, left-aligned with open right margin; share the text's Y-band; never wedged into leftover space.

### Space philosophy
- Negative space is designed. Dark panels FLOAT in the middle third with cream air on all sides (never sink to the bottom). One dominant visual anchor per page (max 1-2). Restraint over decoration; surgical accents over color blocks.

---

## Per-page-type layout recipes

- **Cover:** cream (or dark photographic hero variant). Bounded hero photo ~50% (inset, not full-bleed-overlay); serif headline 40-48pt with 1-2 teal keywords in the opposite half; eyebrow/wordmark/tagline asymmetric; generous cream breathing. No banner.
- **Article / content:** floating header cluster (+ optional ghost numeral); balanced 2-col (50/50 or 35/65); body left, paired visual or numbered list right in the SAME Y-band; block gaps on baseline grid; page number bottom-right; ~55/45 content/breathing.
- **Case study (Fallstudie):** asymmetric. LEFT ~25-30%: bounded portrait + metadata + 1-2 small dark stat panels embedded; section markers small-caps navy. RIGHT ~70%: serif headline + prose + one floating teal/navy insight panel (cream air around it). Rotated "FALLSTUDIE 0X" on the trim. (Alt: full-height portrait bleeding to OUTER edge + inset text column.) No full-height dark sidebar.
- **Data / infographic:** balanced 50/50 equal weight. LEFT serif headline + intro + optional numbered points; RIGHT one chart at 60-65% width on cream (transparent, faint grid, teal series), same Y-band; ~0.5in gutter; one chart, its own pocket.
- **Fact sheet / bonus:** body prose left ~60%; RIGHT 3-5 stacked stat-rail cards (dark panels, big teal numerals). Optional soft-callout band as a break. Rotated "BONUS: …" on trim. Cards float; no full-height fill.
- **Closing / Fazit (back cover):** monumental. Full-bleed DARK ground (navy `#1E3A4C` / deep teal `#1A3A36`), optional photographic vignette 40-60% opacity. Centered (abandon 2-col): white serif statement 36-48pt, sans subline white, eyebrow "FAZIT" above. CTA = minimal white link or ~1in QR bottom-center, NOT a button.

---

## Top changes from our current output (most impactful first)

1. **Kill all full-width solid-color headline banners** → serif headline floating on cream with inline teal keywords. (The #1 off-brand tell.)
2. **Delete dark full-height sidebars** → floating dark island panels + a ~25-30% photo/metadata column (case study) + rotated trim labels for wayfinding.
3. **White → warm cream `#F6F3ED` + grain**, continuous behind everything; remove all white cards, borders, drop-shadows (one depth plane).
4. **Serif-headline / sans-body, navy ink `#2E3E50`** (not black); 1-3 teal keywords per headline; body 11pt / 1.5-1.6.
5. **Teal becomes MICRO** (≤ ~8-10% page weight): keywords, stat figures, chart series, chips only. Never a fill.
6. **Open margins + baseline grid**: ~0.5-0.6in margins, ~0.5in gutters, ~45% breathing / never >70% content; vertical spacing in 18pt multiples; distribute whitespace.
7. **Charts get their own pocket on cream** (transparent, faint grid, teal series, ~60-65% width, open right margin), sharing the text's Y-band; never wedged.
8. **Horizontal cohabitation + per-type templates** (cover / article / case study / data / fact sheet / closing) instead of one universal layout; pair text+visual in the same Y-band.
9. **Rebuild closings as the monumental dark archetype** (full-bleed navy, centered white serif, QR/link CTA).
10. **Breathing footer system**: page number in muted warm-gray, optional small wordmark + plain URL, optional hairline, floating in the cream lower zone.
