# THE ROLE->DEVICE CONTRACT (the shared spine of layers A, B, C)

Status: 2026-07-16, IN BUILD. Read `docs/STATE-OF-THE-BUILD.md` first.

This is the ONE contract three layers speak:
- **A (writer, `docs/writer-prompt-v5.md`)** emits data in these SHAPES.
- **B (selector, `dmc-renderer/build_live.py`)** maps SHAPE -> ROLE -> PRESET.
- **C (primitives, `research/v7-renderer/components/viz_*.jinja`)** draws them.

Rule: the device is chosen by the data's RHETORICAL ROLE, never by its field
name. If a shape is absent, nothing renders (graceful). Nothing is fabricated:
every figure and source is copied verbatim from the writer.

---

## THE TABLE (role -> writer shape -> preset)

| ROLE | writer key + shape | PRESET | status |
|---|---|---|---|
| one sourced fact, in a ROW of 3-5 | `fakten: [{figur, label, text, quelle, icon}]` | `icon_stat_row` | NEW (C) |
| trend over time | `verlauf: {titel, einheit, quelle, punkte: [{label, wert}], hervorheben}` | `column_chart` | NEW (C) |
| a calculation | `rechnung: {titel, schritte: [{wert, einheit, label}], ergebnis: {wert, label}}` | `formula_ladder` | NEW (C) |
| before/after per CATEGORY | `kategorien: {titel, vorher_label, nachher_label, einheit, zeilen: [{label, vorher, nachher}]}` | `grouped_bars` | NEW (C) |
| composition / a ratio before+after | `zusammensetzung: {titel, quelle, teile: [{prozent, label}], vergleich_teile}` | `stacked_bar_100` | NEW (C) |
| entities compared on one metric | `entitaeten: {titel, einheit, quelle, eintraege: [{name, wert, marke}]}` | `entity_bars` | NEW (C) |
| capacity split (2 parts of a total) | `anteil` (extended: `{gesamt, teile}`) | `split_bar` | EXISTS, unused |
| ranked list of magnitudes | `rangliste: {titel, einheit, eintraege}` | `ranked_bars` | EXISTS, unused |
| a countable population | `menge: {anzahl, gesamt, label, icon}` | `icon_array` | EXISTS, unused |
| a process in phases | `schritte` (with `dauer`) | `phase_timeline` | EXISTS, unused |
| cascading consequence chain | `kaskade: [{label, text}]` | `step_cascade` | EXISTS, unused |
| a single share of a whole | `anteil: {prozent, label, quelle}` | `donut` | LIVE |
| one before/after pair | `vorher_nachher: {von, nach, einheit, label}` | `transform_arrow` | LIVE |
| a money/cost magnitude | `kostenrechnung.summe` | `money_bar` | EXISTS, unused |
| the page's hero figure | `kennzahl_hero: {wert, label, quelle}` | `mega_numeral` | EXISTS, unused |
| loose figures with no role | `kennzahlen: [{wert, label, quelle}]` | `stat_strip` | LIVE (fallback) |

SELECTION PRECEDENCE (B): explicit role shapes win over loose `kennzahlen`.
A page emitting `fakten` renders an icon-stat row; `kennzahlen` remains the
last-resort fallback so old payloads never regress.

---

## THE ICON VOCABULARY (C)

The refs use ONE thin line-icon per concept inside a circle. `icon` is a
brand-agnostic SEMANTIC KEY the writer picks from this closed set; the renderer
owns the drawing. Unknown/absent key -> no icon (graceful, never a broken glyph).

`zeit` (clock) · `geld` (euro/coin) · `person` (single figure) · `team` (group) ·
`dokument` (page) · `prozess` (gear) · `wachstum` (rising arrow) ·
`warnung` (alert) · `ziel` (target) · `standort` (building) · `kalender` ·
`suche` (magnifier) · `chart` (bars) · `check` (verified) · `welt` (globe) ·
`schule` (graduation cap) · `schutz` (shield) · `idee` (bulb).

---

## THE COPY LAW THAT MAKES THIS WORK (from Richard's own doc, 2026-07-16)

The copy rules ARE the viz contract from the other side. Non-negotiable in v5:
- **Zahlen immer als Ziffern** ("3 bis 5", never "drei bis fünf"). A spelled-out
  number can never become a device.
- **Immer "€", nie "Euro".** One canonical currency unit to parse.
- **Quellen immer "(Quelle, Datum)"**, on the figure itself. That IS the
  icon-stat card's source line and our stat `sub` field.
- Keine Doppelpunkte, keine Gedankenstriche, kein "nicht X, sondern Y",
  keine Umgangssprache. (Full list + the banned-word replacements:
  memory `writer-voice-and-reader-model.md`, 2026-07-16 section.)

---

## DENSITY RULES (from the refs, binding on B)

- Facts render in ROWS OF 3-5, never one lonely device on a page.
- A page mixes 2-4 device TYPES.
- Every figure keeps its source INLINE, never detached.
- One figure = one device (the existing one-figure-one-device dedup still binds).
