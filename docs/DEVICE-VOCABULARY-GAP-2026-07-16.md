# The device-vocabulary gap (owner refs: Luka Martic + Frese Recruiting, 2026-07-16)

## THE MEASURED DISCONNECT (this is the whole problem in one line)
- The RENDERER can draw **16 presets**: ba_bars, bar_compare, completion_ring,
  donut, gauge, icon_array, kpi_card, mega_numeral, money_bar, phase_timeline,
  radial_cluster, ranked_bars, split_bar, stat_strip, step_cascade,
  transform_arrow.
- The LIVE ADAPTER only ever emits **4**: donut, stat_strip, transform_arrow,
  bar_compare.
- So 12 of 16 devices are BUILT AND UNREACHABLE. The deck feels same-y because
  the translation layer speaks a 4-word vocabulary, not because the renderer
  is weak.

## WHY (the rule shape, build_live._normalize_page_data)
Device choice is a per-FIELD syntactic reflex:
  kennzahlen + "%"        -> donut
  vorher_nachher          -> transform_arrow
  kostenrechnung          -> stat_strip
  anteil                  -> donut
Nothing looks at what the figure MEANS. Richard picks the device from the
data's RHETORICAL ROLE, and his writer supplies the shape that role needs.

## THE REFERENCE VOCABULARY (what the two new PDFs actually use)
Cataloged from the pages, with the role -> device mapping Richard implies:

ROLE                                  DEVICE (reference)
------------------------------------  ---------------------------------------
one sourced market fact               ICON-STAT CARD: circle line-icon + big
                                      figure + body + source line. Used in
                                      ROWS of 3-5 (Frese p3: 500+/200+/10+/5/6;
                                      Martic p5: 87.8%/45/47%).
trend over time                       COLUMN CHART with per-bar value labels,
                                      last bar highlighted (Frese p5
                                      "Vakanzzeit-Treppe 2018-2025").
two quantities diverging over time    LINE CHART, 2 curves + gap annotation +
                                      arrow (Martic p5 "Schere zwischen
                                      Aufwand und Umsatz").
a calculation / cost derivation       FORMULA LADDER: numbered rows
                                      (chip + value + unit + label) ending in a
                                      dark RESULT box (Martic p6: 5x160=800 ->
                                      47% -> 35 EUR -> 13.160 EUR/Monat), or an
                                      inline formula row (Frese p9:
                                      8 x 35,28 EUR x 210 = 133.358 EUR).
a capacity/share split                SPLIT BAR with both end labels + inner
                                      percentages (Martic p6: 800h |53%/47%|
                                      376h).
before/after per category             GROUPED HORIZONTAL BARS, grey=vorher /
                                      blue=nachher + legend + KPI stack beside
                                      (Martic p9: Reporting/Setup/Werbemittel;
                                      16h -> 2h -> 14h gained).
before/after of ONE ratio             TWO 100% STACKED BARS stacked vertically
                                      (Martic p11: 87/13 -> 10/90).
composition of a whole                100% STACKED BAR + legend + headline
                                      figure (Frese p11: 43/45/10/1 -> 99%).
entities compared on one metric       LABELED BARS WITH ENTITY MARKS (Frese
                                      p11: country flags + Ausbildungsdauer
                                      bars 3/3/3-5/4-5 Jahre).
a market/system structure             BESPOKE NODE DIAGRAM, two panels
                                      contrasted (Frese p6: closed loop in RED
                                      vs hub-and-spoke in BLUE), or a funnel
                                      of icons (Frese p3: 3 buildings -> 1
                                      person).
a process                             ICON CHAIN with dashed arrows (Martic p7
                                      foot), or a NUMBERED ZIGZAG TIMELINE with
                                      icons (Frese p4: 7 steps alternating).
recurring pain points                 NUMBERED CARD GRID: oversized numeral +
                                      icon + title + body (Martic p4: 01-06).
objections / false beliefs            OBJECTION CARD: dark navy label block
                                      (01-05) + chevron + light body panel
                                      (both decks).
the payoff / thesis                   DARK CALLOUT BAND with a line icon
                                      (EUR / target / crown).
proof of trust                        LOGO WALL (grey logos, even grid).
case study                            LEFT photo rail + KPI stack, CENTER
                                      icon-labeled sections (Ausgangssituation/
                                      Ziel/Loesung/Ergebnis), RIGHT contact
                                      card + result cards.

## THE STRUCTURAL LESSONS (beyond the device list)
1. EVERY sourced figure carries its source INLINE, in a small caption under the
   body ("(Destatis, 2018)", "(McKinsey, 2012 und 2023)"). Never detached.
2. Devices come in ROWS/GRIDS (3-5 icon-stat cards across), not one lonely ring
   per page. Density is designed, not avoided.
3. The icon language is constant: thin line icons in circles, one per concept.
   The system currently has NO icon vocabulary at all.
4. Cards are the base unit: white card, hairline border, soft shadow, generous
   padding, on a light blue-white gradient ground with a faint tech texture.
5. Dark navy is the EMPHASIS register (callouts, objection labels, hero stats),
   used sparingly against the light ground - not as a full-height rail on every
   page.
6. A page mixes 2-4 device TYPES (e.g. Frese p5: 3 icon-stat cards + a column
   chart + a quote). Our pages carry one device type, repeated.

## WHAT THIS IMPLIES FOR THE BUILD (the fix, at the right layer)
The gap is NOT "add more CSS". It is three wiring layers:
  A. WRITER CONTRACT: the writer must emit the data SHAPE each role needs
     (a series for a trend, a ladder for a calculation, an entity list for a
     comparison). Today it emits kennzahlen/vorher_nachher/anteil only, so the
     adapter can only ever reach 4 devices. Roles the writer cannot express
     cannot be drawn, no matter how good the renderer is.
  B. DEVICE SELECTION: replace the per-field reflex with a ROLE -> DEVICE
     table (deterministic, data-shape-driven, one entry per row above), so the
     12 unreachable presets become reachable and selection is explainable.
  C. MISSING PRIMITIVES: icon-stat card, column chart w/ labels, formula
     ladder, grouped bars + legend, 100% stacked bar, entity-labeled bars,
     node diagram, icon chain, icon set. Some map onto existing presets
     (split_bar, ranked_bars, step_cascade, icon_array, phase_timeline exist
     and are unused!), the rest are new.

## ANSWER TO "does the preprocessor run, or just the render?"
ALL stages run in-process on EVERY render (build_live._build, verified by call
sites): validate_and_resolve_brand_tokens (751) -> resolve_fonts (755) ->
resolve_axes (760) -> validate_copy/copyfit (765) -> synthesize_page_visuals
(657, per page) -> structure_content (872) -> resolve_slots (882) ->
generate_assets/fal (905) -> generate_components (924) -> plan_layout (931) ->
assemble_package (936) -> route_package (957) -> assembler.render_package.
There is no "render-only" mode and no skipped preprocessor. The layout IS being
computed every time. The dullness is NOT a skipped stage: it is that the
stages which choose devices (synthesize_visuals + the build_live field rules)
know 4 devices, and generate_components builds bespoke SVG for only 4 page
types (ST-06/09/14/07A).
