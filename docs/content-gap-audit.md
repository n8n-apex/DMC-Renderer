# Content gap audit: AI run vs Richard's real deck (same client)

Comparison: the christoph-winter writer run (`CL-20260527-183949-LJN`) against
Richard's own hand-written **mein Werkzeugkoffer** deck (`DMC-Report
Mein_Werkzeugkoffer.pdf`, `pdftotext` -> /tmp/richard_werkzeug.txt). Same
product, same audience, same fact base. So every gap below is craft, input, or
prompt, not subject matter.

Tag each fix: **[PROMPT]** = writer-prompt change. **[DATA]** = the upstream
research/ingestion must supply material the writer cannot invent.

---

## THE THROUGH-LINE: the copy does not feed the design's big slots

The premium design creates its appeal through what a reader sees in a 90-second
skim: big headlines, hero numbers, pullquote panels, "Fakt ist:" callout boxes,
and a whole page built around a worked calculation. Those slots demand specific
copy shapes. Richard writes TO them. The AI writes acceptable body paragraphs
and leaves every large slot holding something generic, unsourced, or empty. Fix
the copy so the skimmable layer carries the argument alone, and the design's
appeal is earned instead of decorative.

---

## 1. Headlines are descriptive labels, not verdicts  [PROMPT]
- Richard (each headline is a judgment that survives on its own): "Das stille
  Millionen-Leck", "Inventar wird zum Fuehrungsproblem", "Excel wird zum
  Risiko", "Bezahlte Zeit ohne Ergebnis", "Du verlierst taeglich Kapital".
- AI (labels that name the topic): "Who we are: A system built for the field,
  not the office", "When tools simply disappear into depreciation".
- Fix: every section headline must state the verdict, not the subject. The
  90-second skim of headlines alone should deliver the whole argument.

## 2. No coined cost-concept  [PROMPT]
- Richard coins a memorable name for the wound and reuses it: "das stille
  Millionen-Leck", "bezahlte Unterbrechung", "stille Verluste", "blinder Fleck".
  These become the cover line and the "Fakt ist:" callouts.
- AI coins nothing. "Control problem" is a category, not a coined concept.
- Fix: require one coined, concrete money-concept, introduced on the cover and
  reused at the close. It is what the design's big callout boxes hold.

## 3. No evidentiary spine: every number floats  [DATA + PROMPT]
- Richard sources nearly every figure: (PKS, 2023), (KPMG, 2025), (GDV, 2022),
  (Brooks et al., 2020), (GLCI, 2025), (Destatis, 2024), (VGR, 2025). His
  authority IS the citations.
- AI: "200 to 250 customers", "over 10,000 active users", "50 replacement
  devices a week", "five to ten minutes a day" - not one source. And it
  fabricated "83%".
- Fix: the writer can only cite what it is given, so the research step must
  supply sourced industry figures [DATA]. The prompt must forbid an unsourced
  statistic in the proof slots and forbid computing a number [PROMPT]. This
  directly feeds the design's stat callouts, which look premium and say nothing
  when the number is unsourced or invented.

## 4. No worked arithmetic proof  [DATA + PROMPT]
- Richard's deck has a page built entirely on shown math: "100 Mitarbeiter x 48
  Minuten Suchzeit x 220 Arbeitstage x 43,40 EUR = 763.840 EUR". And a second:
  1 pair of gloves x 100 workers x 52 weeks = 15.000 EUR/year. Devastating
  because the reader watches the number get built from their own inputs.
- AI: "500 to 1000 unproductive paid minutes daily" and stops. No build, no
  annual figure, no page.
- Fix: give the writer the reader's own operating inputs (headcount, hourly
  cost, minutes lost) [DATA] and require one transparent, step-by-step
  calculation ending in an annual euro figure [PROMPT]. The design has a page
  type for exactly this; right now it renders empty.

## 5. Pain given as 3 categories, not concrete moments  [PROMPT]
- Richard: "Sieht dein Alltag so aus?" then SEVEN named moments with texture -
  "Suche statt Start" (a worker searches the truck at 7am because yesterday's
  load was never logged), "Stillstand auf der Baustelle", "Nachkauf trotz
  Bestand". Each is a scene.
- AI: 3 tidy buckets ("Blind reordering", "Minutes lost searching", "Audit
  panic"). Real, but categories, not moments.
- Fix: pains must be specific moments in the reader's day, as many as the data
  supports, not three because three feels finished. Feeds the design's
  icon-tile grid, which needs distinct scenes to fill it.

## 6. False beliefs paraphrased, not quoted in the reader's own words  [PROMPT]
- Richard: SEVEN beliefs, each a verbatim objection in the reader's mouth - "Bei
  uns klaut keiner.", "Excel reicht doch aus.", "Das lohnt sich fuer uns
  nicht.", "Das wirkt wie Ueberwachung." - then answered straight.
- AI: 3 beliefs, paraphrased into statements, not quoted.
- Fix: state each belief as the short quoted objection the reader actually says,
  then answer. The design's belief cards are built to show the quote big.

## 7. The surveillance objection is never named and disarmed  [PROMPT]
- This is the single most important move for THIS product, and the biggest miss.
  Richard names the fear in the reader's voice - "Das wirkt wie Ueberwachung." -
  and answers it head on: "Ein System schafft keine Ueberwachung, sondern
  Klarheit." He also frames employees as the beneficiaries, not the watched.
- AI handles it implicitly (worker at center) but never NAMES the objection, so
  it never actually disarms it. The reader's real fear goes unaddressed.
- Fix: require the surveillance objection to be named in the reader's own words
  and answered directly, once, in the beliefs section.

## 8. Almost no pullquote-ready lines  [PROMPT]
- Richard's deck is full of liftable verdicts: "Nicht das einzelne Werkzeug ist
  teuer. Teuer ist die bezahlte Unterbrechung." / "Was im Betrieb nicht sichtbar
  ist, wird nicht ernst genommen." / "Die Frage ist nicht, ob das passiert. Die
  Frage ist, ob du akzeptierst, dass es so bleibt."
- AI's only pullquote is mundane: "They liked it because they can report
  problems via the app. People do not like calling."
- Fix: each section should yield one sharp, standalone line the design's
  pullquote panel can hold. This is a design-driven copy requirement, not
  decoration.

## 9. "Acknowledge then destabilize" is missing  [PROMPT]
- Richard's signature open: credit the reader's competence, then make that
  success the danger - "Du bist kein Anfaenger und auch kein Blender. Genau
  deshalb ist deine Situation so gefaehrlich."
- AI goes straight to diagnosis with no warm-then-turn.
- Fix: the outlook/status-quo opener should acknowledge what the reader built,
  then turn it into the exposure.

## 10. Cost-of-inaction is not priced at the close  [PROMPT]
- Richard kills the comfort of waiting and prices it: "Nichtstun ist keine
  neutrale Entscheidung." / annual euro leak restated.
- AI's Fazit restates the thesis ("employees are the best tracking") but never
  prices waiting.
- Fix: the summary/CTA must state what one more year of the status quo costs, in
  the reader's own unit.

## 11. Craft tics  [PROMPT]
- The "not X, but Y" reframe fires 3x across the deck (outlook + fazit + stacked
  in the fazit). Richard fires it ONCE, at the diagnosis flip. Cap it deck-wide.
- Product naming is inconsistent: "Inventory ONE", "mein Werkzeugkoffer", and
  "decentralized tool allocation system" all used for the same thing. Pick the
  named mechanism and hold it.

---

## What is PROMPT vs what is DATA (so effort lands right)

- **[PROMPT] only** (rewrite the writer prompt): 1, 2, 5, 6, 7, 8, 9, 10, 11,
  and the "cap the reframe / demand a coined concept / headline-as-verdict"
  rules. These are achievable now and lift the copy toward Richard's craft.
- **[DATA] gated** (needs the upstream research to actually produce Richard-grade
  source material): 3 (sourced statistics) and 4 (the worked economics), plus
  the named, textured case-study baselines. Richard's deck clearly sat on a real
  research pass (dozens of citations, real industry economics). The writer
  cannot cite or calculate from facts it was never given. Until the ingestion
  produces that substrate, the proof pages stay thinner than his no matter how
  good the prompt is.

Bottom line: the prompt fixes close most of the VOICE gap. The design's appeal
gap (hero numbers, worked-math page, sourced proof) is half prompt and half a
research-substrate problem upstream.
