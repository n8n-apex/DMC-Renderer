// ════════════════════════════════════════════════════════════════════

const WORKFLOW_VERSIONS_V3 = Object.freeze({
  workflow_contract_version: "3.2.1",
  writer_prompt_version: "5.1.1",
  schema_resolver_version: "5.2.1",
  writer_gate_version: "3.1.1",
  source_ledger_version: "3.2.1",
  claim_gate_version: "3.2.1",
});
// SCHEMA RESOLVE  (Phase 2 — per-chapter output schema + intent + ledger)
// ════════════════════════════════════════════════════════════════════
// Runs INSIDE the chapter loop, one chapter item per iteration. Attaches:
//   output_schema          structured field defs (Parse Writer Response
//                          validates required keys against this)
//   output_schema_text     the same spec rendered for the writer prompt
//   output_schema_skeleton a JSON template the model mirrors (json_object)
//   required_fields        flat list of required keys (quick validation)
//   writer_intent          what this chapter must achieve, one paragraph
//   used_ledger_text       headlines/openers used in prior chapters, read
//                          from workflow static data; Parse Writer Response
//                          writes it. Self-resets per report (by content_id).
// Everything else on the item passes through untouched.
//
// CONTRACT NOTES:
// - JSON KEYS stay GERMAN (renderer contract). As of v5 (2026-07-16) the
//   writer OUTPUTS GERMAN values directly (no downstream translation); the
//   FIELD DESCRIPTIONS here stay English as instructions to the writer.
// - ST-07A is a fully BUILT renderer pattern. As of v5 the renderer also
//   draws the VISUAL-DATA devices added below (icon_stat_row, column chart,
//   formula ladder, grouped/stacked/entity bars, donut, before/after) via
//   the German->contract adapter in dmc-renderer/build_live.py. Every visual
//   key below was verified to be CONSUMED by that adapter on 2026-07-16.
// - Two sub-key names I could NOT see in bytes are marked VERIFY (inside
//   ergebnis_metrics and kunde) — confirm against your ST-07A renderer,
//   change here only.
// - Per-field `max` are ceilings summing to ~the chapter budget. Visual
//   fields are OPTIONAL and only consume budget when the data supports them.
//   No inflating minimums (that was finding 5).
// ════════════════════════════════════════════════════════════════════

// ---- v5 VISUAL-DATA field defs (2026-07-16) -------------------------
// All OPTIONAL and grounded. Every one is read by build_live.py (line refs
// are to that file): kennzahlen 463, fakten 661, bildwunsch 981,
// vorher_nachher 516, anteil 538, kostenrechnung 562, rechnung 689,
// kategorien 703, zusammensetzung 717, verlauf 677, entitaeten 733.
// Shapes match the adapter's expected sub-keys exactly.
// NOT wired (the current adapter does not read them, so emitting them wastes
// writer budget): `vergleich`, a `kosten` sub-key on schmerzpunkte, a per-step
// `ergebnis` on schritte. Add them here only once build_live consumes them.

const F_kennzahlen = { key: "kennzahlen", required: false, type: "array", min_items: 0, max_items: 4, item: { type: "object", fields: [
  { key: "wert", max: 30, desc: "The figure exactly as the data gives it, digits and unit (e.g. '13.160 €', '47 %'). Value only, never a sentence." },
  { key: "label", max: 60, desc: "What the figure measures, in words." },
  { key: "quelle", max: 40, desc: "Source as (Quelle, Jahr), e.g. (Destatis, 2018). Include only if the data attaches a source; omit this sub-key otherwise." },
] }, desc: "Hard figures on this page, from the section data ONLY. Every real figure in the prose also appears here so the design can print it big. Omit the whole field if the page has no real figure." };

const F_fakten = { key: "fakten", required: false, type: "array", min_items: 0, max_items: 5, item: { type: "object", fields: [
  { key: "figur", max: 30, desc: "The figure, digits and unit. Value only." },
  { key: "label", max: 60, desc: "What it measures, short." },
  { key: "text", max: 140, desc: "One sentence of context from the data. Omit this sub-key if the data gives none." },
  { key: "quelle", max: 40, desc: "Source as (Quelle, Jahr). Omit this sub-key if the data has none." },
  { key: "icon", max: 20, desc: "One key from this closed set, ONLY if it truly fits: zeit, geld, person, team, dokument, prozess, wachstum, warnung, ziel, standort, kalender, suche, chart, check, welt, schule, schutz, idee. Omit otherwise." },
] }, desc: "3 to 5 sourced market figures shown side by side as a row of icon-stat cards. Use this instead of many single kennzahlen when the page carries a cluster of facts. A single lonely figure belongs in the prose, not here. Omit if the page has no such cluster." };

const F_bildwunsch = { key: "bildwunsch", required: false, type: "object", fields: [
  { key: "art", max: 30, desc: "One of exactly: portrait | geraet_mockup_phone | geraet_mockup_laptop | proof_galerie | logo_wand | szene. This routes the image slot; it is the only sub-key the renderer reads." },
], desc: "What image the page wants, so the design can place the client's real asset. Omit if the page needs no image." };

const F_vorher_nachher = { key: "vorher_nachher", required: false, type: "object", fields: [
  { key: "von", max: 30, desc: "Start figure, from the data." },
  { key: "nach", max: 30, desc: "End figure, from the data." },
  { key: "einheit", max: 30, desc: "Shared unit if it separates cleanly (e.g. 'pro Woche'). Omit this sub-key otherwise." },
  { key: "label", max: 60, desc: "What changed." },
], desc: "One before/after the data states (a time or cost that dropped), drawn as paired bars or an arrow. Only when the data gives BOTH ends. Omit otherwise." };

const F_anteil = { key: "anteil", required: false, type: "object", fields: [
  { key: "prozent", max: 20, desc: "The percentage exactly as in the data. Never one you computed yourself." },
  { key: "label", max: 80, desc: "What it is a share of." },
], desc: "One real proportion the data states, drawn as a ring/gauge. Omit if the data states no percentage." };

const F_kostenrechnung = { key: "kostenrechnung", required: false, type: "object", fields: [
  { key: "schritte", type: "array", min_items: 2, max_items: 6, item: { type: "object", fields: [
    { key: "label", max: 60, desc: "The input, e.g. 'Minuten pro Tag'." },
    { key: "wert", max: 30, desc: "The figure for this input, from the data." },
  ] }, desc: "One row per input. Show each input the data gives." },
  { key: "summe", max: 30, desc: "The resulting figure (the product of the inputs). This is the one place a calculation is allowed, because every input is present." },
  { key: "zeitraum", max: 30, desc: "The period, e.g. 'pro Jahr'." },
], desc: "The worked cost, ONLY when the data gives EVERY input. If any input is missing, omit the whole field and make the point in words." };

const F_rechnung = { key: "rechnung", required: false, type: "object", fields: [
  { key: "titel", max: 60, desc: "What is being worked out." },
  { key: "schritte", type: "array", min_items: 2, max_items: 6, item: { type: "object", fields: [
    { key: "wert", max: 30, desc: "The figure for this step." },
    { key: "einheit", max: 30, desc: "Its unit. Omit this sub-key if none." },
    { key: "label", max: 60, desc: "What this input is." },
  ] }, desc: "The rungs of the ladder, one per input." },
  { key: "ergebnis", type: "object", fields: [
    { key: "wert", max: 30, desc: "The resulting figure." },
    { key: "label", max: 60, desc: "What the result is." },
  ], desc: "The dark result tile at the foot of the ladder." },
], desc: "A derivation that ends in a result, drawn as a numbered ladder down to a result box. Same law as kostenrechnung: only when the data gives every input. This is the richer, laddered form. Omit otherwise." };

const F_kategorien = { key: "kategorien", required: false, type: "object", fields: [
  { key: "titel", max: 60, desc: "What is compared." },
  { key: "vorher_label", max: 40, desc: "Label for the before column, e.g. 'Vorher (manuell)'. Omit this sub-key if none." },
  { key: "nachher_label", max: 40, desc: "Label for the after column, e.g. 'Nachher (automatisiert)'. Omit this sub-key if none." },
  { key: "einheit", max: 30, desc: "Shared unit. Omit this sub-key if none." },
  { key: "zeilen", type: "array", min_items: 2, max_items: 6, item: { type: "object", fields: [
    { key: "label", max: 50, desc: "The category." },
    { key: "vorher", max: 30, desc: "Before figure, from the data." },
    { key: "nachher", max: 30, desc: "After figure, from the data." },
  ] }, desc: "One row per category, both figures from the data." },
], desc: "Before/after for SEVERAL categories, drawn as grouped bars with a legend. Use vorher_nachher when the data gives only one pair. Omit if the data gives no per-category before/after." };

const F_zusammensetzung = { key: "zusammensetzung", required: false, type: "object", fields: [
  { key: "titel", max: 60, desc: "What whole is split." },
  { key: "quelle", max: 40, desc: "Source as (Quelle, Jahr). Omit this sub-key if none." },
  { key: "teile", type: "array", min_items: 2, max_items: 6, item: { type: "object", fields: [
    { key: "prozent", max: 20, desc: "The share, exactly as in the data. Never computed." },
    { key: "label", max: 50, desc: "The part." },
  ] }, desc: "The parts of the whole (the first bar)." },
  { key: "teile_label", max: 40, desc: "Label for the first bar, e.g. 'Vorher'. Omit this sub-key if there is no comparison." },
  { key: "vergleich_label", max: 40, desc: "Label for the second bar, e.g. 'Nachher'. Omit this sub-key if there is no comparison." },
  { key: "vergleich_teile", type: "array", min_items: 0, max_items: 6, item: { type: "object", fields: [
    { key: "prozent", max: 20, desc: "The share, from the data." },
    { key: "label", max: 50, desc: "The part." },
  ] }, desc: "Optional second bar for a before/after of the split. Omit this sub-key when there is no comparison." },
], desc: "How a whole splits, drawn as a 100% stacked bar (two bars when a comparison is given). Shares come straight from the data, never computed. Omit if the data states no composition." };

const F_verlauf = { key: "verlauf", required: false, type: "object", fields: [
  { key: "titel", max: 60, desc: "What is tracked over time." },
  { key: "einheit", max: 30, desc: "The unit. Omit this sub-key if none." },
  { key: "quelle", max: 40, desc: "Source as (Quelle, Jahr). Omit this sub-key if none." },
  { key: "punkte", type: "array", min_items: 2, max_items: 8, item: { type: "object", fields: [
    { key: "label", max: 20, desc: "The point label, e.g. '2018'." },
    { key: "wert", max: 30, desc: "The figure at that point, from the data." },
  ] }, desc: "At least TWO points, in order. The design needs 2 or more or it draws nothing." },
  { key: "hervorheben", max: 20, desc: "The label of the point to pick out (e.g. the latest). Omit this sub-key if none." },
], desc: "A development over time, drawn as a labelled column chart with one bar highlighted. Needs 2 or more points. Omit otherwise." };

const F_entitaeten = { key: "entitaeten", required: false, type: "object", fields: [
  { key: "titel", max: 60, desc: "What is measured across the actors." },
  { key: "einheit", max: 30, desc: "The unit. Omit this sub-key if none." },
  { key: "quelle", max: 40, desc: "Source as (Quelle, Jahr). Omit this sub-key if none." },
  { key: "eintraege", type: "array", min_items: 2, max_items: 6, item: { type: "object", fields: [
    { key: "name", max: 40, desc: "The entity, e.g. 'Deutschland'." },
    { key: "wert", max: 30, desc: "Its figure on this metric, from the data." },
    { key: "marke", max: 12, desc: "A short mark or country code, e.g. 'DE'. Omit this sub-key if none. Never an emoji." },
  ] }, desc: "One row per entity, at least two." },
], desc: "Several actors measured on ONE metric, drawn as labelled bars with entity marks. Omit if the data compares no real entities on one metric." };

const SCHEMAS = {
  "ST-01": {
    intent: "The cover. One headline that names the reader's stake or the payoff of reading, plus a sharpening subtitle. No 'ultimate guide' clichés. This is the first thing the reader sees — earn the open.",
    fields: [
      { key: "titel", required: true, max: 90, desc: "Main cover headline. Concrete and specific to this audience and topic. Names a stake or a payoff." },
      { key: "untertitel", required: true, max: 160, desc: "One supporting line that sharpens the promise in plain language." },
      { key: "kicker", required: false, max: 60, desc: "Small eyebrow line above the title (report type or audience). Omit if it would be filler." },
      { key: "title_accent", required: false, max: 40, desc: "The punch run inside the title that the two-tone headline colours in accent (a substring of the title, e.g. 'zum Risiko' in 'Warum Excel zum Risiko wird'). Omit to let the headline accent its last word by default." },
      { key: "kicker_pills", required: false, type: "array", min_items: 0, max_items: 3, item: { type: "string", max: 24 }, desc: "1 to 3 short uppercase tags for the pill row on the cover (report type, year, audience). Omit if none add signal." },
      // teaser_items NOT wired (2026-07-16, render-verified): the cover's "In diesem
      // Report" rail sits at the foot of a band that already carries the byline, a
      // 3-line title and a 3-line subtitle. Rendered with 3 realistic German lines it
      // overflowed and was SILENTLY CLIPPED by the bleed page (item 1 cut mid-word,
      // item 3 gone) with the sheet count still correct, so no QC would catch it. Even
      // 2 short phrases left only ~3.5mm of the designed 20mm bottom padding. Feeding
      // this slot needs a LAYOUT change (reserve the rail's height, or cap the title),
      // not a writer key. Left unfed: the template guards it, so it renders nothing.
      F_kennzahlen,
      F_bildwunsch,
    ],
  },
  "ST-02": {
    intent: "Set up the whole report. Tell the reader, in their terms, why this topic matters right now, then promise concretely what they'll walk away with. A contract with the reader, not a teaser — each outlook point is a real takeaway.",
    fields: [
      { key: "titel", required: true, max: 80, desc: "Section headline for the outlook." },
      { key: "einleitung", required: true, max: 300, desc: "Opening paragraph — why this topic matters to the reader now." },
      { key: "ausblick_punkte", required: true, type: "array", min_items: 3, max_items: 4, item: { type: "string", max: 120 }, desc: "What the reader will take away. Each a concrete promise, not a teaser." },
      { key: "abschluss", required: false, max: 140, desc: "One closing line that sets up the read." },
      { key: "pullquote", required: false, max: 160, desc: "The report's thesis as one short quotable line, drawn from the section data. The layout lifts it out large. Omit if nothing in DATA earns it." },
      { key: "pullquote_attribution", required: false, max: 60, desc: "Who the pull-quote is attributed to, if the data names them. Omit if unattributed or no pullquote." },
      F_kennzahlen,
      F_fakten,
      F_entitaeten,
    ],
  },
  "ST-05": {
    intent: "Introduce the company through the reader's problem, not a corporate bio. Say plainly what they do and the one thing that makes their approach different. Only use credibility points that are real in DATA.",
    fields: [
      { key: "titel", required: true, max: 80, desc: "Section headline." },
      { key: "einleitung", required: true, max: 260, desc: "Who the company is, framed in the reader's terms." },
      { key: "angebot_text", required: true, max: 320, desc: "What they actually do / the core offer, concretely." },
      { key: "vertrauenspunkte", required: false, type: "array", min_items: 0, max_items: 4, item: { type: "string", max: 90 }, desc: "2 to 4 trust points drawn ONLY from real facts in the section data (customer count, named client, real result). If only two real points exist, return two. Never invent a third, and never attribute a certification, award, or title to any person unless the data states it in those words. Omit the field if no real points exist." },
      { key: "partners", required: false, type: "array", min_items: 0, max_items: 8, item: { type: "string", max: 50 }, desc: "The names of real clients or partners from DATA (the 'Vertrauen von' / 'Bekannt aus' credential wall). Names only, from the data, never invented. Omit if the data names none." },
      F_kennzahlen,
      F_fakten,
      F_bildwunsch,
    ],
  },
  "ST-09": {
    intent: "Name the reader's current painful reality so precisely they feel seen. Use their own words from DATA. Each pain point is a specific symptom they recognise, not a generic industry complaint. End by pointing toward the way out without selling yet.",
    fields: [
      { key: "titel", required: true, max: 90, desc: "Section headline naming the current state." },
      { key: "einleitung", required: true, max: 300, desc: "Set the scene: the reality the reader lives in today." },
      { key: "schmerzpunkte", required: true, type: "array", min_items: 3, max_items: 3, item: { type: "object", fields: [
        { key: "titel", max: 50, desc: "Short label for the pain." },
        { key: "beschreibung", max: 180, desc: "The specific symptom, grounded in the audience's own words." },
      ] }, desc: "The specific pains the reader recognises." },
      { key: "ueberleitung", required: false, max: 180, desc: "Transition into the rest of the report." },
      F_kennzahlen,
      F_fakten,
      F_kostenrechnung,
      F_rechnung,
      F_vorher_nachher,
      F_kategorien,
      F_verlauf,
    ],
  },
  "ST-14": {
    intent: "Take the myths that keep the reader stuck. For each: state the belief fairly, then the reality that breaks it, then a short why. Use the reality and the factual basis from DATA — do not invent the counter-argument.",
    fields: [
      { key: "titel", required: true, max: 90, desc: "Section headline." },
      { key: "einleitung", required: true, max: 220, desc: "Frame why these beliefs are worth confronting." },
      { key: "irrtuemer", required: true, type: "array", min_items: 3, max_items: 3, item: { type: "object", fields: [
        { key: "irrtum", max: 120, desc: "The false belief, stated fairly." },
        { key: "realitaet", max: 120, desc: "The reality that breaks it (from DATA's reality field)." },
        { key: "erklaerung", max: 160, desc: "Answer the belief using only a fact from the section data. If the data has a hard number for this belief, use it. If it does not, answer in plain words with NO number. Never invent a statistic to make the point land." },
        { key: "quelle", max: 40, desc: "Source for this belief's counter-fact as (Quelle, Jahr), if the data attaches one. Renders as the belief's source line. Omit this sub-key if the data has no source." },
      ] }, desc: "The myths and their corrections." },
      { key: "abschluss", required: false, max: 120, desc: "One closing line." },
      F_kennzahlen,
      F_fakten,
      F_zusammensetzung,
    ],
  },
  "ST-07A": {
    intent: "Tell one customer's story as a clean before / turn / after. Ground every claim in DATA. Use only the real metrics present — if there are fewer than three, use what's real; never pad. If DATA has no customer quote, omit the pullquote entirely. If the customer is from a different industry than the reader, present that honestly as evidence the approach travels.",
    fields: [
      { key: "kurzportrait", required: true, max: 160, desc: "Who the customer is and what they do, one or two sentences." },
      { key: "ausgangsproblem", required: true, max: 180, desc: "The problem they had before. Concrete." },
      { key: "wendepunkt", required: true, max: 140, desc: "What changed / why they acted." },
      { key: "loesung", required: true, max: 180, desc: "What they did with the product. Specific." },
      { key: "ergebnis_text", required: true, max: 180, desc: "The outcome, in prose." },
      { key: "ergebnis_metrics", required: true, type: "array", min_items: 1, max_items: 3, item: { type: "object", fields: [
        { key: "label", max: 40, desc: "What the number measures." },
        { key: "wert", max: 30, desc: "The number itself. VERIFY this sub-key name ('wert' vs 'value') against your ST-07A renderer." },
      ] }, desc: "Only the REAL metrics from DATA. Never invent. 1-3 items." },
      { key: "kunde", required: true, type: "object", fields: [
        { key: "name", max: 60, desc: "Customer company/name from DATA. Rendered in the case-study person block." },
        { key: "company_url", max: 120, desc: "Customer company URL from DATA. Rendered as the case-study link." },
        { key: "initials", max: 8, desc: "Customer initials from DATA." },
        { key: "funktion", max: 60, desc: "Customer role/title from DATA." },
      ], desc: "The customer's identity, from DATA." },
      { key: "pullquote", required: false, max: 160, desc: "A REAL customer quote from DATA. OMIT this field entirely if DATA has none — never invent one." },
      { key: "pullquote_attribution", required: false, max: 60, desc: "Who said the quote. Omit if no pullquote." },
      F_vorher_nachher,
      F_kategorien,
      F_bildwunsch,
    ],
  },
  "ST-07B": {
    intent: "Pull one transferable principle out of the result that precedes this chapter, and explain in plain terms why it holds. One idea, made obvious. Tie it back to the reader's situation in a line.",
    fields: [
      { key: "titel", required: true, max: 90, desc: "Section headline naming the principle." },
      { key: "kernaussage", required: true, max: 160, desc: "The principle in one sentence — the takeaway." },
      { key: "erklaerung", required: true, max: 280, desc: "Why it's true, plainly. Tie to the result it follows from." },
      { key: "bezug", required: false, max: 120, desc: "One line linking back to the reader's situation." },
      { key: "compare", required: false, type: "object", fields: [
        { key: "ohne", type: "array", min_items: 1, max_items: 5, item: { type: "string", max: 80 }, desc: "The 'without the principle' column: plain lines from the data." },
        { key: "mit", type: "array", min_items: 1, max_items: 5, item: { type: "string", max: 80 }, desc: "The 'with the principle' column, matched across." },
      ], desc: "An optional before/after grid contrasting without vs with the principle. Both columns must carry content or the grid does not render. Omit unless the data draws the contrast." },
      F_anteil,
      F_kennzahlen,
      F_zusammensetzung,
    ],
  },
  "ST-06": {
    intent: "Explain how the method actually works, step by step, using the mechanism steps in DATA. Make each step concrete enough that the reader could picture it happening in their business. No black boxes, no jargon.",
    fields: [
      { key: "titel", required: true, max: 90, desc: "Section headline." },
      { key: "einleitung", required: true, max: 220, desc: "Frame what the method does before the steps." },
      { key: "schritte", required: true, type: "array", min_items: 3, max_items: 4, item: { type: "object", fields: [
        { key: "titel", max: 50, desc: "Short step label." },
        { key: "beschreibung", max: 160, desc: "What happens in this step, concretely (from DATA's steps)." },
      ] }, desc: "The steps of the mechanism." },
      { key: "abschluss", required: false, max: 140, desc: "One closing line. This becomes the treatment's result band, so make it the method's payoff sentence." },
      F_bildwunsch,
    ],
  },
  "ST-FAZIT": {
    intent: "Tie the thread together: remind the reader what they now understand that they didn't before, and leave them with the single message to remember. Short and clean.",
    fields: [
      { key: "titel", required: true, max: 80, desc: "Section headline for the conclusion." },
      { key: "zusammenfassung", required: true, max: 360, desc: "Pull the thread together — what the reader now knows." },
      { key: "kernbotschaft", required: true, max: 160, desc: "The one thing to remember. (The renderer maps this to the thesis pull-statement.)" },
      { key: "kosten_des_nichtstuns", required: false, max: 160, desc: "The cost of one more year of the status quo, in the reader's own unit, taken from the data. Feeds the summary's cost-of-inaction block (an otherwise-empty slot the renderer reads). If a cost was named on the cover, use the same words here. Omit if the data states no such cost." },
      F_kennzahlen,
    ],
  },
  "ST-22": {
    intent: "Show what working together looks like in concrete terms — the process or the offer, plainly stated, so the next step feels easy and low-risk.",
    fields: [
      { key: "titel", required: true, max: 80, desc: "Section headline." },
      { key: "einleitung", required: true, max: 220, desc: "What working together looks like." },
      { key: "ablauf_text", required: true, max: 240, desc: "The concrete next-step process or offer." },
      F_kennzahlen,
    ],
  },
  "ST-03": {
    intent: "One clear action. Say why acting now is worth it in a sentence or two, give the button label, and use the exact booking URL from DATA. If DATA has no URL, leave url empty — do not invent one.",
    fields: [
      { key: "titel", required: true, max: 80, desc: "The action headline." },
      { key: "text", required: true, max: 150, desc: "One short paragraph — why act now." },
      { key: "button_text", required: true, max: 40, desc: "The button label (e.g. 'Book your call')." },
      { key: "url", required: true, max: 200, desc: "Copy the cta_url from DATA EXACTLY. If DATA has no URL, output an empty string — never invent one." },
      // F_kennzahlen removed (contract audit 2026-07-16): the CTA back cover has no
      // stats/viz slot, so figures emitted here were dropped. State no figures on the CTA.
    ],
  },
};

const CLAIM_IDS_FIELD = Object.freeze({
  key: "claim_ids",
  required: false,
  type: "array",
  min_items: 1,
  max_items: 32,
  item: Object.freeze({ type: "string", min: 1, max: 96 }),
  desc: "Claim IDs from the canonical source ledger that support assertions in this object. Omit when this object makes no evidence-bearing assertion.",
});

function claimIdsField() {
  return { ...CLAIM_IDS_FIELD, item: { ...CLAIM_IDS_FIELD.item } };
}

function withClaimIds(fields) {
  const transformed = fields
    .filter(field => field.key !== "claim_ids")
    .map(field => {
      const copy = { ...field };
      if (ft(field) === "object") {
        copy.fields = withClaimIds(field.fields || []);
      } else if (ft(field) === "array" && field.item && field.item.type === "object") {
        copy.item = { ...field.item, fields: withClaimIds(field.item.fields || []) };
      } else if (field.item) {
        copy.item = { ...field.item };
      }
      return copy;
    });
  transformed.push(claimIdsField());
  return transformed;
}

function claimIdsPaths(fields, pathPrefix, out) {
  pathPrefix = pathPrefix || "$";
  out = out || [];
  out.push(pathPrefix + ".claim_ids");
  fields.forEach(field => {
    if (field.key === "claim_ids") return;
    if (ft(field) === "object") {
      claimIdsPaths(field.fields || [], pathPrefix + "." + field.key, out);
    } else if (ft(field) === "array" && field.item && field.item.type === "object") {
      claimIdsPaths(field.item.fields || [], pathPrefix + "." + field.key + "[]", out);
    }
  });
  return out;
}

// ---- renderers ----
function ft(f) { return f.type || "string"; }
function tag(f) { return f.required ? "REQUIRED" : "OPTIONAL"; }

// Recursive sub-field renderer (handles arbitrary nesting: an object sub-field,
// or an array-of-objects sub-field, inside another object/array). The 2-level
// version could not describe verlauf/rechnung/kategorien/zusammensetzung/
// entitaeten (object-with-an-array-inside) and printed their inner shape as a
// scalar; this recurses so the writer sees the real shape.
function renderSub(sf, pad) {
  const t = ft(sf);
  if (t === "array") {
    const it = sf.item || {};
    const kind = it.type === "object" ? "objects" : (it.type === "array" ? "arrays" : "strings, each max " + (it.max || "?") + " chars");
    let s = `${pad}- ${sf.key} [array of ${sf.min_items != null ? sf.min_items : 0}-${sf.max_items != null ? sf.max_items : "?"} ${kind}]: ${sf.desc || ""}`;
    if (it.type === "object") (it.fields || []).forEach(x => { s += "\n" + renderSub(x, pad + "  "); });
    return s;
  }
  if (t === "object") {
    let s = `${pad}- ${sf.key} [object]: ${sf.desc || ""}`;
    (sf.fields || []).forEach(x => { s += "\n" + renderSub(x, pad + "  "); });
    return s;
  }
  return `${pad}- ${sf.key} [max ${sf.max}]: ${sf.desc || ""}`;
}

function describeField(f) {
  const t = ft(f);
  if (t === "array") {
    const it = f.item || {};
    if (it.type === "object") {
      const sub = (it.fields || []).map(sf => renderSub(sf, "    ")).join("\n");
      return `FIELD: ${f.key}  [${tag(f)}, array of ${f.min_items}-${f.max_items} items, each an object]\n  ${f.desc || ""}\n${sub}`;
    }
    return `FIELD: ${f.key}  [${tag(f)}, array of ${f.min_items}-${f.max_items} strings, each max ${it.max} chars]\n  ${f.desc || ""}`;
  }
  if (t === "object") {
    const sub = (f.fields || []).map(sf => renderSub(sf, "    ")).join("\n");
    return `FIELD: ${f.key}  [${tag(f)}, object]\n  ${f.desc || ""}\n${sub}`;
  }
  return `FIELD: ${f.key}  [${tag(f)}, max ${f.max} chars]\n  ${f.desc || ""}`;
}

function schemaToText(fields) { return fields.map(describeField).join("\n\n"); }

// Recursive skeleton value (mirrors renderSub's depth handling).
function skelVal(f) {
  const t = ft(f);
  if (t === "array") {
    const it = f.item || {};
    if (it.type === "object") { const o = {}; (it.fields || []).filter(sf => sf.key !== "claim_ids").forEach(sf => o[sf.key] = skelVal(sf)); return [o]; }
    if (it.type === "array") { return [skelVal(it)]; }
    return ["string"];
  }
  if (t === "object") {
    const o = {}; (f.fields || []).filter(sf => sf.key !== "claim_ids").forEach(sf => o[sf.key] = skelVal(sf)); return o;
  }
  return "string";
}
// Skeleton includes ONLY required fields, so the optional VISUAL fields do not
// pre-show empty slots that would nudge the model to fill them against the
// "omit empty optionals" rule. Optional fields are still fully described in
// output_schema_text; the writer emits them only when the data supports them.
function skeleton(fields) {
  const o = {}; fields.filter(f => f.required).forEach(f => o[f.key] = skelVal(f)); return JSON.stringify(o, null, 2);
}
function requiredKeys(fields) { return fields.filter(f => f.required).map(f => f.key); }

function normSt(v) {
  if (!v) return "";
  return String(v).toUpperCase().replace(/\s+/g, "").replace(/_/g, "-");
}

function resolveSchemaItems(entries, getWorkflowStaticData) {
  return entries.map(entry => {
  const j = entry.json;
  const stRaw = j.page_st_type ?? j.chapter_type ?? j.st_type ?? "";
  const st = normSt(stRaw);
  const schema = SCHEMAS[st];
  if (!schema) {
    throw new Error('Schema Resolve: unknown ST type "' + stRaw + '" (normalized "' + st + '"). Known: ' + Object.keys(SCHEMAS).join(", "));
  }
  const outputFields = withClaimIds(schema.fields);

  // running de-dup ledger, self-resetting per report
  const cid = j.content_id ?? j.contentId ?? "";
  const store = getWorkflowStaticData("global");
  if (store.ledgerContentId !== cid) {
    store.ledgerContentId = cid;
    store.usedHeadlines = [];
    store.usedOpeners = [];
  }
  const uh = Array.isArray(store.usedHeadlines) ? store.usedHeadlines : [];
  const uo = Array.isArray(store.usedOpeners) ? store.usedOpeners : [];
  const usedLedgerText = (uh.length || uo.length)
    ? ("HEADLINES ALREADY USED (do not repeat or paraphrase):\n" + uh.map(h => "- " + h).join("\n") +
       "\n\nOPENERS ALREADY USED (open differently):\n" + uo.map(o => "- " + o).join("\n"))
    : "(this is the first chapter — no prior headlines or openers yet)";

  return {
    json: {
      ...j,
      output_schema: outputFields,
      output_schema_text: schemaToText(outputFields),
      output_schema_skeleton: skeleton(outputFields),
      required_fields: requiredKeys(outputFields),
      claim_ids_paths: claimIdsPaths(outputFields),
      writer_intent: schema.intent,
      used_ledger_text: usedLedgerText,
      ...WORKFLOW_VERSIONS_V3,
    },
  };
  });
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    WORKFLOW_VERSIONS_V3,
    CLAIM_IDS_FIELD,
    withClaimIds,
    claimIdsPaths,
    resolveSchemaItems,
  };
}

if (typeof $input !== "undefined") {
  return resolveSchemaItems($input.all(), $getWorkflowStaticData);
}
