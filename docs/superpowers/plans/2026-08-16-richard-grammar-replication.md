# Richard Grammar Replication Program — Fault Ledger + Pattern Catalog (2026-08-16)

## 1. The vision-audited truth

All 20 of our pages audited via Gemini vision (gemini-3.5-flash): **every page = reject**.
Averages: overall 3.0, data_devices 1.9, imagery 2.1, typography 3.8, alignment 3.5.

## 2. Richard's pattern catalog (extracted from 8 of HIS pages, Gemini vision)

| Grammar rule | Richard's pages | Our violation |
|---|---|---|
| **Flat, sharp, shadowless** | "None. Completely flat. Strictly sharp 90° corners. Zero drop shadows" (7/8) | rounded cards, heavy drop shadows, pills, checkmarks |
| **Dark panel = full-height vertical strip** | 40% dark charcoal/teal/navy column, textured, structural anchor | floating dark boxes |
| **ONE accent, sparingly** | gold/teal on metrics, dividers, URLs, quote bar, diagram nodes only | accent everywhere, green checkmarks |
| **Data devices ARE the graphics** | stat stacks (gold numerals + thin gold rules), comparison line graphs, step flowcharts, Venn, QR — all vector, all real | static clipped text, prose in metric slots, abstract waves |
| **Giant ghost section number** | massive low-contrast numeral overlapping the dark panel = signature | ghost letterform 'A' watermarks |
| **Imagery: ONE sharp-framed real photo** | rectangular photo (portrait/handshake/executives) inside dark panel, thin border | amateur snapshots, abstract wave art |
| **Typography** | massive bold ALL-CAPS sans headline; narrow measure 45-70 chars; selective bolding | 100+ char lines, tight leading, bold-italic walls |
| **Whitespace** | asymmetric 60/40 split, wide gutters, generous margins | crowded stacks, trapped voids |

**Richard NEVER uses abstract generative art.** His graphics are data-driven vector devices +
real photography. The fal abstract waves violate his core rule.

## 3. Per-page fault ledger (Gemini vision, all 20 pages)

### Pervasive (affect most pages)
- **F1 measure**: body line length 100-120+ chars (p4, p7, p9, p14, p15, p18...) → cap ~70 chars (max-width + larger leading)
- **F2 header CTA**: "Trage dich zu einem kostenlosen Erstgespräch ein…" in the running header (p4, p7, p9, p12, p18, p19) → REMOVE from header
- **F3 cheap-SaaS components**: rounded stat boxes (p1), pills (p5, p16), drop shadows (p3, p18), green checkmarks (p2), LinkedIn-badge circular portrait (p18), circles-on-a-stick timeline (p19)
- **F4 generic art**: abstract waves on A3 spreads (p9, p14, p15), ghost 'A' watermark (p8, p10, p13), breather vector-circle overlays (p6, p11)
- **F5 clip/typo data**: "30-50%" clipped by border (p16), uncapitalized German in metrics (p12, p15), prose in metric slots (p9, p12)

### Per page (from the audit)
- p1: stat box overlaps founder arm; pills uneven; green headline low contrast; cramped bullets
- p2: radial cluster tries to show "30 bis 50 %" in a single-integer ring (squished); crowded lower half; checkmark box
- p3: overcrowded (intro+stats+2 testimonial cards+3 photos+logos); testimonial cards = SaaS aesthetics; low-quality snapshots; IN ZAHLEN = mobile-widget card
- p4: 120-char lines; teal numbers disconnected from headers; 50% banner = web-UI card
- p5: Venn = PowerPoint ellipses w/ shadows; bold-italic vibrating texture; REALITÄT bars misaligned; heavy teal title block
- p6: generic vector circles over photo; low-end snapshot; thesis cramped bottom-left over dark head; teal line = crutch
- p7: header CTA; fiber-optic stock art = zero data; '->' instead of arrow glyph; tight Lösungs/Ergebnis gap
- p8: hyphenated "fehlen-des" orphan; ghost 'A'; truncated column rule; weak horizontal rule
- p9: meaningless wave art; 100+ char lines; prose in metric slot; '6 von 6' circle floating unaligned
- p10: hyphenation across column break ("berich-/ten"); gutter rule suffocates; ghost shape; Kernaussage pushed to bottom edge
- p11: GoldmanTax logo cropped by subject head; thin circle overlays; white bar at bottom = misaligned crop; weak separator
- p12: amateur founders-with-plaque snapshot; uncapitalized "von bis zu…"; weak metric shift (plain text + arrow); header CTA
- p13: "skalie-/ren" hyphenation; ghost 'A'; column split mid-sentence ("setzen / bereits"); 58% stat buried in body
- p14: meaningless 3D wave; massive dark void above the graphic; 100+ char lines; weak metric hierarchy
- p15: generic wave; uncapitalized "von fragmentiert"; no structured data devices ("100 % automatisiert" is plain text)
- p16: **30-50% clipped by container border** (the recurring one); ragged step-card grid; redundant stat (3x); SCHRITT pills
- p17: neon sign brand mismatch; camera rig blocks subject; white serif over high-contrast folds; teal line
- p18: pull quote = 100% duplicate of body sentence; radial card = SaaS dashboard; LinkedIn-badge headshot; severe vertical crowding
- p19: circles-on-a-stick timeline; rules start right of the line (trapped space); header CTA; duration labels float disconnected
- p20: footer centered vs left grid; URL teal low contrast; informal "Du" + "Buch" typo; thin teal line

## 4. The fix program (ralph US-501+)

1. **US-501 F2** — remove the header CTA ("Trage dich zu…") from the running header; header becomes wordmark + folio only
2. **US-502 F1** — measure/leading pass: body max-width to ~70 chars equivalent, line-height 1.5-1.6, paragraph spacing
3. **US-503 F3** — flat-design purge: remove drop shadows, rounded corners on cards/panels, pills→flat labels, checkmarks→flat rules, circular portrait→sharp-framed rectangular
4. **US-504 F5** — data-device grammar: fix the 30-50% clip (box width), metric capitalization (German sentence case), prose→real devices (transform_arrow with real arrow glyph, stat stacks)
5. **US-505 F4** — art policy: kill abstract fal waves + ghost 'A'; replace with Richard's grammar (giant ghost SECTION NUMBER on dark panels; data devices; sharp-framed photo)
6. **US-506** — the signature move: giant low-contrast section numeral on each dark panel (Richard's "massive '01' overlapping the dark sidebar")
7. **US-507** — breathe: whitespace distribution per page (60/40 asymmetric, wide gutters)
8. **US-508** — typography: ALL-CAPS bold sans headline treatment, selective bolding, hyphenation control, pull-quote dedup
9. **US-509** — re-render + full 20-page vision audit; iterate until ≥5 pages clear and no rejects on the core pages
10. **US-510** — FINAL upgraded PDF delivered to the user

---

## 5. EVIDENCE CORRECTION — 2026-08-16 (US-501..510 are REOPENED)

The completion summary above (US-501..US-510 marked done) is **reopened**. The
latest full-page visual inspection (OpenRouter vision, `/tmp/vision_audit_20.json`)
returns **verdict=no on 20/20 pages**. The grammar pass changed local CSS and
devices without changing the ownership model; the visible defects remain.

### Confirmed failures in the delivered artifact

- **p16 ST-06:** `30-50%` clipped — DOM `clientWidth=111px`, `scrollWidth=176px`.
  The vision read: "'30-50' is visibly cut off — the '%' is clipped by the box."
  The earlier "pixel verified" notes for this figure were wrong.
- **p18/p19:** FAZIT founder headshot + name/title block bleeds INTO the ST-22
  banner ("contamination"), and ST-22's banner text is obscured by it.
- **p15 ST-07A:** 'ohne Headco…' hard-clipped at the right page edge.
- **p12 ST-07A:** the arrow device shows 'MIT APEX → Minuten' with **no number**
  on the destination side — a broken data device.
- **p7 ST-07A:** the same two KPIs ('> 200.000 €', '4 automatisierte
  Kernprozesse') render **twice** in the right column.
- **p5 ST-14:** the Venn diagram overprints/cuts the third myth's text.
- **p8/p10/p13:** dark theory pages still read as empty lower-half fields.
- **p20:** lower half ~45% empty; the ghost '20' is clipped at the page edges.

### Root cause (why "done" was wrong)

1. Page templates decide composition before the Director sees the reference.
2. The Director emits no page-level region/continuation plan.
3. Reference selection is not consumed by the renderer.
4. The final visual gate passes zero references and does not inspect the final
   post-convergence PDF; intrinsic clipping is invisible to it.
5. One-page and 20-page assumptions remain embedded in the package, templates,
   tests, and overflow checks.

### Status change (Ralph)

Reopen: **US-402, US-403, US-408, US-509, US-510** (passes → false). New repair
stories US-601..US-609 are defined in
`docs/superpowers/plans/2026-08-16-ralph-director-pagination-repair.md`. The
next work is the Director→pagination contract, NOT another CSS sweep.
