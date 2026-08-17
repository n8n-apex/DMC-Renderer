# Why the output looks amateur: the five real discrepancies

Date: 2026-08-07. Every claim below is measured, not argued.

## 1. The page-format model is wrong. This is the biggest one.

Measured from Richard's six PDFs:

| Report | Pages | Faces | Page sizes |
|---|---|---|---|
| Apex | 20 | 20 | 20 x A4 (214x301mm) |
| Buchagentur | 11 | 20 | **9 x SPREAD 424x301mm** + 2 x A4 |
| Alexander Boss | 11 | 20 | **9 x SPREAD 426x303mm** + 2 x A4 |
| Werkzeugkoffer | 11 | 20 | **9 x SPREAD 420x297mm** + 2 x A4 |
| Niklas | 20 | 20 | 20 x A4 |
| Aerztepartner | 11 | 20 | **9 x SPREAD 420x297mm** + 2 x A4 |

Four of six reports are built as **nine double-page spreads plus a front and
back cover**. Richard designs on a 420mm-wide canvas nine times per report:
image bleeding across the gutter, text in columns, a device anchored on one
half against prose on the other.

The v3 system produces **19 single A4 pages plus one A3**. The house profile
declares 20 faces with one spread; six of ten families do not support a3 at
all. So the system emits nineteen isolated portrait sheets where the
reference emits nine designed spreads.

That single mismatch produces most of what reads as amateur: single-column
text at ~100 characters per line, devices stranded in narrow rails, no
cross-gutter imagery, no facing-page composition.

## 2. The writer's visual vocabulary is ignored by v3 entirely

`docs/writer-prompt-v5.md` has the writer emit eleven visual-data keys:
`kennzahlen`, `fakten`, `vorher_nachher`, `anteil`, `kostenrechnung`,
`rechnung`, `kategorien`, `zusammensetzung`, `verlauf`, `entitaeten`,
`bildwunsch`.

- **v2 consumes them**: `build_live.py` has 7 references to `kennzahlen`
  alone, 4 to `vorher_nachher`, and maps each key to a device.
- **v3 consumes none of them.** Grepping the entire v3 pipeline
  (`adapter_v3.py`, `stages/*.py`, `pipeline_v3.py`) finds zero readers for
  `kennzahlen`, `fakten`, `vorher_nachher`, `kostenrechnung`, `entitaeten`,
  `bildwunsch`.

v3 reads only `editorial_brief_v3` and `composition_facts_v3` — structures
that exist in no real writer output. They exist only in the hand-written
fixture. **So the copy-to-visualization mapping does not exist in v3.** The
question "how does the system understand the copy to build the
visualizations" has an honest answer today: it does not. v2 did it by key
mapping; the v3 rebuild dropped it and replaced it with claim-shape
inference that only a hand-authored fixture can satisfy.

## 3. The real report JSON is almost purely textual

Counted in `dmc-renderer/fixtures/apex_consulting_payload.json` (the real
client report): 33 distinct data keys across the pages, of which exactly
**one** is a visual-data key (`ergebnis_metrics`, on 5 pages). No
`kennzahlen`, no `vorher_nachher`, no `kostenrechnung`.

The payload predates writer prompt v5 and the schema-resolver node that would
make the writer emit those keys. Both files exist in the repository and
**neither has been pasted into the live n8n workflow**. So even a perfect
mapping layer would find almost nothing to draw. Data visualization is
starved at the source.

## 4. There are no photographs anywhere in the pipeline

- `client_assets/` contains 6 real files, all for one client
  (christoph-winter): a founder portrait and five product shots.
- The apex-dense fixture generates **6 synthetic gradient blobs** in Python.
- Richard's pages are photo-led: full-bleed founder portraits, scene
  photography, device mockups, client logos.

Every page that should carry a photograph currently carries a blue gradient
with an ellipse on it.

## 5. The generative path is not part of the build

`build_v3.py` contains no writer or model call. The v3 build starts from an
envelope that must already contain the finished copy, the claims, the
composition facts and the assets. Today that envelope comes from a
1,901-line fixture written by hand.

So the sentence "the system produces the report" is false at the top of the
chain: something upstream must produce it, and that upstream is currently a
person.

## What follows from this

The fixes, in dependency order — each one is a precondition for the next
mattering:

1. **Adopt the spread format model.** 9 A3 spreads + 2 A4 covers, families
   that support a3, facing-page composition, cross-gutter imagery. Until
   this changes, every other improvement is decoration on the wrong canvas.
2. **Restore the copy-to-device mapping in v3.** Read the writer's eleven
   visual keys, map each to the device kinds the contract already has, keep
   the claim-grounding checks. This is the "how does it understand the copy"
   layer, and v2 already proves the mapping.
3. **Feed the writer that can emit them.** Paste prompt v5 and the schema
   resolver into n8n so new reports carry visual keys; regenerate the apex
   payload rather than testing against a pre-v5 one.
4. **Put real photography in.** Wire `client_assets/` into the asset ledger
   with rights records; a photo-led family renders a photo or it fails.
5. **Only then**: column grids, alignment polish, device density.
