# Acceptance criteria: the Apex bar

The system is accepted when, given a real client's evidence, it produces on
its own judgment a 20-face report that a blind reviewer scores at the level
of Richard's Apex report. Everything below is that sentence made measurable.

Reference: `APEX - KI DMC Report v1 (1).pdf` (printed truth; the legacy
envelope's `#e94560` token does not match the print — the print wins, and
the print is blue).

## 1. Density (the master criterion)

- Mean 240-340 words per face (Apex measures 337.7; corpus 248.8-345.0).
- No content face below ~120 words except cover and CTA closes.
- Copy fits: never exceeds region word capacity or physical height budget.

## 2. Structure

- Exactly 20 faces, exactly 3 complete cases, one A3 spread.
- Richard's arc: verdict cover, outlook, about, status quo, false beliefs,
  case/theory pairs, mechanism, trust wall, summary, objections,
  collaboration, double CTA close.

## 3. Visual measure (bands measured from the Apex print itself)

Stored in `research/calibration/reference-bands/apex-v1.json`:

| Feature | Reference range (observed) |
|---|---|
| Ink occupancy | 0.09 - 0.36 |
| Whitespace fraction | 0.51 - 0.85 |
| Vertical hierarchy share | 0.18 - 0.67 |
| Type rhythm bands | 14 - 44 |
| Image coverage | 0.04 - 0.29 |

Candidate faces must land inside these bands per family. The current
candidate (2026-08-06, before the density build) measures ink 0.045 mean,
whitespace 0.90, bands 4.2 — the quantified gap being closed now.

## 4. Evidence honesty

- Every rendered figure binds to a claim with an exact source span or a
  computation chain; a source appendix covers every rendered source.
- Charts are selected by evidence shape (before/after difference, formula
  chain, entity-over-time), never decoration. Nothing invented, ever.

## 5. Client response

- Materially different clients produce visibly different reports (pinned:
  five profiles, five distinct PDFs, distinct plans for distinct characters).

## 6. The referee

- Two independent blind raters score reference and candidate faces on the
  same rubric; the candidate's score meets the threshold derived from the
  reference ratings. This is the only criterion code cannot self-satisfy,
  and it is the definition of "hits the Apex bar."

## Working order until accepted

Measure the reference, render the candidate, measure the gap, close the
largest gap, repeat. Never weaken a gate to pass it; never fabricate
evidence, ratings, or approvals to close a gap.
