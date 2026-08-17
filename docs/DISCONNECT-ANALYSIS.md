# DMC renderer — the visual disconnect (2026-07-11)

Deep multi-agent code trace (7 investigators + synthesis + adversarial critic) + hands-on
verification of the load-bearing claims. Question: why does a real client deck render FLAT
(0 charts, 0 data-viz, 0 device mockups, 1 generated component, lots of dead space) when the
codebase has a rich chart / diagram / mockup / treatment library?

Answer in one line: **the library is not missing and not disabled — it RAN. Every rich layer
was starved at a different disconnected door, and the biggest door is that the page-filling
TREATMENT layer and the richness-GENERATING pipeline are two mutually-exclusive render tracks,
so treated pages silently drop every chart/component/diagram the pipeline produced.**

---

## The master disconnect (VERIFIED in code + pixels)

Two independent systems both decide "what's on the page," and they do not talk:

- **Generator track** (preprocessor): `generate_components.py` → `page["components"]` (SVG charts),
  `synthesize_visuals.py` → `data.viz` (the 16-preset "Power-BI" library), `plan_diagrams.py`
  → `data.diagram` (Venn / before-after / process / objection). These render **only via the
  legacy pattern path** — `patterns/base.py:105-136 chart_svgs()` reads `page["components"]`;
  only `st_02/st_09/st_14` patterns read `data.diagram`.
- **Treatment track** (renderer): `assembler.py:_render_one_page` tries the treatment engine
  FIRST; if it returns a fragment, the page uses it and the **legacy path never runs**
  (treatment-first, legacy-fallback — mutually exclusive per page).

Verified facts:
- `grep` across all 6 built treatment templates: **none** read `td.viz`, `td.components`,
  `chart_svgs`, or `data.diagram`. They render only their OWN inline viz (a donut/ring/gauge
  parsed from a `%`-string, or the Ergebnis numbers) — `editorial.jinja:113`, `a3_case_study.jinja:80`,
  `a4_case_study.jinja:90`, `horizontal_process` (viz_proportion).
- christoph resolved package: **1 component total** (ST-06), `data.viz = None` on all 15 pages,
  `data.diagram = None` on all 15 pages.
- **Pixel proof:** the generated ST-06 component SVG carries the label `PROZESS · MECHANIK`.
  That string appears **nowhere** in the rendered `report.html`. ST-06 rendered via the
  `horizontal_process` treatment → the generated diagram was dropped. The p12 "process cards"
  are the treatment re-drawing the step titles, not the generated infographic.

**Consequence for my own recent work:** giving the text pages the always-fitting
`a4_editorial_fill` treatment (to kill dead space) also routes them AROUND the legacy path — so
those pages can never show a generated chart until a treatment hosts one. The fill was right for
whitespace, but it makes the host-slot fix a hard prerequisite, not optional.

---

## Ranked root causes (all evidence-cited)

1. **No built treatment HOSTS a generated chart/viz/diagram.** The one treatment designed to
   (`a4_bi_dashboard`, archetype `dashboard`, `required_fields=('viz',)`) is a metadata-only
   STUB with no template (`treatment_catalog.py:86`; only 6 of ~16 templates exist). This is the
   **master gate** — it makes causes 2-5 invisible even after they're fixed.
2. **German-key ↔ builder-predicate contract mismatch.** The writer emits
   `schritte{titel,beschreibung}` / `ergebnis_metrics{label,wert}` / `schmerzpunkte` / `irrtuemer`;
   the builders gate on English `steps{n,short}` / `stats{value,label}` / `pills` / `quadrants`.
   No adapter bridges them → `generate_components` returns `{}` on pages that DO carry buildable
   data (`generate_components.py:1450/1469/1482/1491`).
3. **The only live viz producer is anemic + offline-gated.** `synthesize_visuals.py:233` only ever
   appends ONE preset (`bar_compare`), and only on `von X auf Y` phrasing the christoph copy lacks;
   offline (no `OPENROUTER_API_KEY`) it emits 0 viz. 15 of 16 presets have no producer.
4. **`plan_diagrams` implements 2 of 5 declared detectors** (`plan_diagrams.py:42` vs `:98-101`):
   `before_after` / `process_flow` / `q_a` are dead priorities; `stat_callout` returned None on all
   15 pages; a headroom gate drops diagrams on text-heavy pages anyway.
5. **All imagery is stubbed (independent axis).** Empty `images{}` + no `FAL_KEY` + no
   `client_assets/christoph-winter/` folder → 0 resolved slots deck-wide → image-led treatments +
   device mockups can't run. (This is the axis Yosef's incoming images + laptop mockups feed.)
6. **Three divergent assemblers, no source of truth (the "mycelium").** `service.py` → `build_live`
   (a hand-rolled clone of `main.py:/render` that ADDS normalize+synthesize but DROPS the
   founder-scrape / device-mockup stage), and `route_package` names a THIRD (`build_package.py`).
   Which visuals appear depends on which fork + which env keys ran. Stage 8.5 is wrapped in a
   try/except that silently swallows the whole diagram pass offline (`build_live.py:462-472`).
7. **Deepest cause — the writer schema is contractually text-only.** `writer-prompt-v3.md:136`
   forbids any key outside the fixed German schema, whose only quantitative field is
   `ergebnis_metrics` (3 pages). The rich library has almost nothing to bind to. Fixing everything
   below still yields "process flow + a comparison + a few gauges," NOT a full Power-BI dashboard —
   that needs either richer writer data or author-driven chart keys.

---

## Lean target flow (what it should be)

```
prose envelope
  → ONE adapter (German keys → internal visual contract, in one place)
  → strengthened synthesize_visuals (normalized fields + verbatim numbers → full preset set, offline)
  → generate_components / charts_svg / plan_diagrams (all detectors implemented) produce SVGs
  → EVERY built treatment has a viz/component/diagram host slot (reads td.viz / page.components / data.diagram)
  → a4_bi_dashboard authored as the dedicated Power-BI spread
  → images resolve through ONE door (client_assets/<slug>/ OR envelope images{}, + FAL when keyed)
  → rich page, deterministically, with graceful degradation instead of silent flatness
ONE assembler owns it (service → single canonical build; retire the build_live / main / build_package fork).
```

---

## Fix plan (dependency-ordered; corrected by the critic's verification)

**Start here — these three turn EXISTING envelope data into VISIBLE charts with no writer change:**

- **[MASTER GATE] Give the built treatments a host slot.** Render `page["components"]` (via
  `chart_svgs`), `data.viz` (via `components/viz.jinja`), and `data.diagram` (via
  `components/diagram.jinja`) inside `a4_editorial_fill` + `a4_case_study` (they catch most pages).
  Without this, everything below renders nowhere. `treatment_engine.py:331` already passes `td.viz`.
  *(Critic's correction: this is the true master gate, and it must host diagrams too — adding
  diagram reads to the legacy `patterns/st_07b.py`/`st_05.py` is misdirected because those pages get
  treatments and never hit the legacy path.)*
- **German→contract adapter (one place).** Extend `build_live._normalize_page_data` (already invoked)
  to map `schritte→steps`, `ergebnis_metrics{label,wert}→stats{value,label}` + parse `X → Y` / `%`,
  `irrtuemer→belief/compare pairs`. Feeds `generate_components`, `charts_svg`, and steps below.
  *(A partial adapter already exists — it produced the ST-06 SVG; verify what it already maps first.)*
- **Enrich `synthesize_visuals`** to emit donut / gauge / ba_bars / stat_strip / kpi_card / timeline
  deterministically from normalized fields (offline, no key), instead of only `bar_compare`.

**Then, in order:**
- Implement `plan_diagrams`' 3 missing detectors from the step/belief lists; relax the headroom gate.
- Route the `2 Std → 20 Min` `ergebnis_metrics` pairs into a real before/after bar (fix `wert`↔`value`).
- Converge the 3 assemblers into one owner; surface (don't swallow) the Stage-8.5 errors.
- **Wire client imagery through one door** (`client_assets/<slug>/` + complete `SLOT_TO_ST`; `FAL_KEY`
  for generated backgrounds) — **this is the axis Yosef's images + laptop mockups plug into.**
- **[XL, last]** Author `a4_bi_dashboard` (the Power-BI spread) + ship the device-mockup pipeline
  (phone/laptop frames) — biggest effort, lowest immediate lift, but the highest-fidelity ceiling.

---

## Honest scoping (so expectations are right)
- The first three steps make the deck **stop being flat** using data that already exists — but the
  realistic output is **process flows + comparisons + a few gauges/donuts**, not a full Power-BI
  dashboard. `schmerzpunkte`/`irrtuemer` are pure prose (no x/y/numeric), so they yield styled
  cards, not real matrices/bar charts.
- The full **Power-BI dashboard spread** needs the `a4_bi_dashboard` treatment AND genuinely numeric
  data (either richer writer output or author-driven chart keys).
- **Device mockups + real portraits** need the image-wiring step — which is exactly what Yosef's
  incoming images + laptop mockups are for.

## The one verification still worth running
A real end-to-end render on the **full outer `{payload, images, brand_tokens}` envelope as n8n
actually sends it** (not the inner payload with empty images), inventorying per page: which path
fired (treatment vs legacy), component/viz/diagram counts in the DATA, and whether each appears in
the PIXELS. (This session verified the treated-page drop with the ST-06 SVG; the remaining unknown
is what a production envelope with real images/brand carries.)

---
## FOLLOW-UP 2026-07-16: the disconnect MOVED (read `docs/STATE-OF-THE-BUILD.md`)
The original disconnect (treatments vs generators mutually exclusive; the live
flow not routing through built components) is CLOSED: treatments host viz /
components / scenes / images and all 13 stages run every render.
THE DISCONNECT THAT REMAINS IS ONE LAYER UP — the DEVICE VOCABULARY: the renderer
can draw 16 viz presets, the live adapter emits 4 (donut, stat_strip,
transform_arrow, bar_compare). Same shape of bug as before (built but
unreachable), now in the TRANSLATION layer: device choice is a per-FIELD reflex,
not a read of what the data MEANS. Full analysis + the role->device catalog from
Richard's 2026-07-16 refs: `docs/DEVICE-VOCABULARY-GAP-2026-07-16.md`.
