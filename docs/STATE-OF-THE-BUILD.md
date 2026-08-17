# STATE OF THE BUILD - the single authoritative entry point (2026-07-16)

READ THIS FIRST after any compaction. Everything else is detail hanging off it.
This file is the CURRENT truth; the dated docs are the archaeology.

---

## 0. WHAT THE PROJECT IS

An autonomous pipeline that turns an n8n writer JSON into a premium German
"DMC report" PDF matching the decks Richard Zimmermann hand-designs in InDesign.

  n8n envelope {payload, images, brand_tokens}
    -> dmc-renderer/build_live.py      (adapter + all preprocessor stages, in-process)
    -> research/v7-renderer/assembler.py render_package  (treatment-first, legacy fallback)
    -> Chromium print-to-PDF -> Ghostscript flatten -> PNGs

HTTP door: `dmc-renderer/service.py` (POST /render, :8099). Container: repo-root
`Dockerfile`. The owner judges ONLY the rendered pixels, never test counts.

---

## 1. THE ANSWER TO "DOES THE PREPROCESSOR RUN, OR JUST THE RENDER?"

**Every stage runs in-process on EVERY render. There is no render-only mode.**
Verified by call site in `build_live._build` (2026-07-16):

| order | stage | line |
|---|---|---|
| 1 | validate_and_resolve_brand_tokens | 751 |
| 2 | resolve_fonts | 755 |
| 3 | resolve_axes | 760 |
| 4 | validate_copy + validate_copyfit | 765 |
| 5 | synthesize_page_visuals (per page) | 657 |
| 6 | structure_content | 872 |
| 7 | resolve_slots | 882 |
| 8 | generate_assets (fal) | 905 |
| 9 | generate_components | 924 |
| 10 | plan_layout | 931 |
| 11 | assemble_package | 936 |
| 12 | route_package | 957 |
| 13 | assembler.render_package | (caller) |

The layout IS computed every time. The preprocessor is NEVER skipped. Any future
"maybe it's only rendering" theory is already disproven: re-run this grep.

---

## 2. THE CURRENT #1 PROBLEM: THE DEVICE-VOCABULARY GAP

**The renderer can draw 16 viz presets. The live adapter emits 4.**

- CAN DRAW: ba_bars, bar_compare, completion_ring, donut, gauge, icon_array,
  kpi_card, mega_numeral, money_bar, phase_timeline, radial_cluster,
  ranked_bars, split_bar, stat_strip, step_cascade, transform_arrow.
- ACTUALLY EMITTED: **donut, stat_strip, transform_arrow, bar_compare**.
- => **12 devices are built and unreachable.** This is why every page feels the
  same. The renderer is not weak; the TRANSLATION layer speaks 4 words.

ROOT CAUSE: device choice is a per-FIELD syntactic reflex in
`build_live._normalize_page_data` (has "%" -> donut; vorher_nachher -> arrow;
kostenrechnung -> stat_strip; anteil -> donut). Nothing reads what the figure
MEANS. Richard chooses by RHETORICAL ROLE and his writer emits the shape each
role needs.

Full role->device catalog + the reference analysis:
**`docs/DEVICE-VOCABULARY-GAP-2026-07-16.md`** (from the 2026-07-16 refs:
"DMC Report Luka Martic" + "InDesign Frese Recruiting Report v2", in
~/Downloads/drive-download-20260716T070244Z-1-001/).

THE FIX IS 3 LAYERS (owner gave the GO 2026-07-16; A+B done, C in build):
- **A. WRITER CONTRACT (owner's n8n lane, GATES THE CEILING)** - the writer emits
  only kennzahlen/vorher_nachher/anteil. A role it cannot express can never be
  drawn. Needs: series (trend), ladder (calculation), entity list (comparison).
  **DONE: `docs/writer-prompt-v5.md` written 2026-07-16.** It adds the role
  shapes (fakten / verlauf / rechnung / kategorien / zusammensetzung /
  entitaeten + icon hints, all OPTIONAL and additive so v4 payloads never
  regress) AND Richard's own copy law, which arrived as
  "Wichtig für Copy (KI-Floskeln).docx" and is now READ + recorded (memory
  `writer-voice-and-reader-model.md`). Owner must paste v5 into n8n.
- **B. ROLE->DEVICE SELECTOR - DONE 2026-07-16.** `build_live._role_devices`
  maps the v5 role shapes to presets AFTER the legacy pass, with explicit roles
  winning and `kennzahlen` kept as the last-resort fallback. Verified: a page
  with all 6 shapes emits icon_stat_row + column_chart + formula_ladder +
  grouped_bars + stacked_bar_100 + entity_bars; an unknown icon key sanitizes to
  None; an empty page emits nothing; a v4-only payload still emits exactly its
  donut (no regression). The one-figure-one-device dedup binds across BOTH
  passes (roles receive the legacy pass's claimed digit-keys).
- **C. MISSING PRIMITIVES - DONE 2026-07-16.** BUILT + DISPATCHED + PIXEL-PROVEN:
  `components/icons.jinja` (closed 18-key line-icon set; unknown key -> nothing),
  `components/viz_facts.jinja` (icon_stat_row, column_chart),
  `components/viz_compare.jinja` (formula_ladder, grouped_bars, stacked_bar_100,
  entity_bars) + `styles/viz_compare.css` wired as a VIZ_CSS sibling in
  assembler. Node diagram + icon chain DEFERRED (most bespoke, least reused).
  Constraints learned: box-shadow is BANNED on viz (test_viz_flat_on_cream, the
  owner's "dull" complaint) so cards use hairline border + surface fill; a 3-across
  figure must ladder its type (40/28/20pt) or "87,8 %" breaks over two lines;
  percent widths must stay WHOLE (43%, not 43.0%) or the device fabricates
  precision the writer never stated.

---

## 3. HOW TO RENDER + VERIFY (the standing loop)

```bash
cd /Users/utkarsh/Projects/richard/dmc-renderer
set -a; source ../research/preprocessor/.env >/dev/null 2>&1; set +a   # keys, never echo them
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib \
  ../research/v7-renderer/.venv/bin/python render_christoph.py
# -> _local_out/render/report.pdf + _local_out/png/p-NN.png  (17 sheets, A3 at 14)
```
Guard battery (53 green as of 2026-07-16):
```bash
cd /Users/utkarsh/Projects/richard/research/v7-renderer
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python -m pytest \
  tests/test_treatment_dispatch.py tests/test_treatment_stylist.py \
  tests/test_treatment_pagesize.py tests/test_no_literals_in_architecture.py \
  tests/test_tokens.py tests/test_footer.py tests/test_treatment_slice.py \
  tests/test_treatment_qc.py -q
```
Container:
```bash
cd /Users/utkarsh/Projects/richard
docker build -t dmc-renderer .
docker rm -f dmc-renderer; docker run -d --name dmc-renderer \
  --env-file research/preprocessor/.env -p 8099:8099 dmc-renderer
curl -fsS http://127.0.0.1:8099/health
# POST needs the ENVELOPE shape {payload, images, brand_tokens} - the fixture
# file is the BARE payload; wrap it (see render_christoph.py lines 26-36).
```
VERIFICATION RULES (learned the hard way, see §5):
- Verify on PIXELS, and on a SECOND fixture (apex), never one deck.
- Physical sheets == logical pages, measured on the PDF, not the DOM.
- print-emulation DOM measurement LIES about fragmentation.
- Absolute scale needs a known-geometry probe in mm (see §5 the scale bug).

---

## 4. CURRENT VERIFIED STATE (2026-07-16)

**THE DEVICE VOCABULARY IS LIVE AND PIXEL-PROVEN.** `fixtures/christoph_v5_payload.json`
(the SAME client data, reshaped into v5 roles - nothing invented) renders 17
sheets / A3@14 with the new devices on the page. Proof: ST-14 (p-05) used to show
2 donuts plus an orphan "70% to 75%" with no device; it now renders a 3-card
ICON-STAT ROW (icon + figure + label + inline source per card) - Richard's own
pattern, produced by the system. Render it with:
`cd dmc-renderer && sed -e 's/christoph_v4_payload.json/christoph_v5_payload.json/' -e 's|_local_out|_local_out_v5|' render_christoph.py > render_v5_tmp.py` then run that (delete it after; it must run FROM dmc-renderer/ or build_live will not import).

- christoph deck: **17 sheets, A3 at 14, TRUE design scale**, all 6 rails bleed
  16..296.5mm x to 210mm, 6 product mockups placed, 5 viz figures, founder
  portrait on cover+About. Deliverable:
  `_renders/dmc_christoph_v4_fixed_2026-07-15.pdf`.
- apex fixture: 20 logical == 20 physical, A3 at 15.
- Tests: 53 green (battery above). Wiring gate: 7 passed / 1 apex-only skip.
- Container: rebuilt on current code, LIVE + healthy on :8099.
- fal + OpenRouter: live end-to-end; assets cached under `$TMPDIR/dmc_live_cfg/`.
- Fonts: **Montserrat now genuinely renders** (see §5).

OPEN / OWNER LANE:
1. Hi-res founder photo for the cover (current is a 500px site headshot).
2. fal `fazit_background` has PAGE TEXT baked into the generated art
   (build_image_prompts feeds page copy to fal) - regenerate or crop.
3. `Wichtig für Copy (KI-Floskeln).docx` unread - gates writer-prompt v5.
4. The writer still emits an invented "83 %" in slot-13 output (flagged, upstream).

---

## 5. THE BUGS THAT DEFINED THIS BUILD (do not re-discover these)

Full regression catalog: memory `regressions-and-guardrails.md` (classes 1-21).
The five that cost the most:

1. **THE SILENT GLOBAL SHRINK (2026-07-15, the biggest).** When ANY fragment
   exceeds its page box, Chromium print SCALES THE WHOLE DOCUMENT down. 0.4mm
   of frame borders on the bleed rails made every deck print at **~84.6% of
   design size for weeks** - no warning, no spill (the shrink PREVENTS the
   spill, so page-count QC is blind). Proven by re-adding the borders. Guard
   now lives in the assembler print pass ("fragment overflow (silent-shrink
   trigger)"). COROLLARY: every layout tuned before 2026-07-15 encoded 85% of
   its true sizes; refits step type DOWN one tier (st_14, st_07b done).
2. **THE RAIL ANCHOR (2026-07-15).** An absolutely-positioned rail reaching past
   its grid with negative offsets has its paint TRUNCATED BY THE FOLLOWING
   PAGE's geometry. About->chromed page = 271mm; About alone = 296.5mm. The
   case rails escaped only by page-order luck. Fix: anchor rails to the SECTION
   (grid position:static; top:16mm/bottom:0/right:0) with ABSOLUTE widths
   (88.8mm editorial-fill / 85.2mm case) - a percentage would resolve against
   the 210mm section, not the 178mm grid, and eat 13mm of text.
3. **FULL-BLEED KNIFE EDGES (2026-07-15).** Every bleed page's 297mm ground sits
   at ~297.1mm in a 297mm area and spills PER DECK BY LUCK (christoph fit; apex
   spilled + shifted every later page). All bleed pages clamped to 296.5mm +
   clip. LESSON: a passing deck is NOT evidence - test a second deck.
4. **CHROMIUM IGNORES @page BACKGROUND-IMAGE** (gradients never paint; the
   veil-over-texture had to be BAKED into a derived asset,
   `assembler._veiled_ground_uri`, keyed by brand hex + written atomically).
   Chromium also CLIPS content at the page area, so negative-offset "bleeds" on
   chromed pages are no-ops -> true bleed = margin-0 named page + margins-as-
   padding + self-drawn chrome (the `.tp-rail` stamp).
5. **BUNDLED != WIRED (2026-07-16).** Montserrat TTFs sat in `fonts/` since May
   with NO @font-face, so every deck silently printed in Source Sans 3 and only
   a log line said so. Fixed: @font-face for Montserrat + Playfair Display +
   listed in tokens' `$extra-bundled-families`. LESSON: assets need a WIRING
   check, not a presence check - the same class as the 12 dead viz presets.

Other durable traps: keys in .env are NOT auto-loaded; httpx default timeout is
5s (killed every fal call); undefined CSS var voids the whole declaration
(`--type-h1` does not exist); head CSS loses to treatment sheets at equal
specificity; two `page:` declarations on one section make Chromium lay out on
one geometry and print on another; assemble_package prefers structure_content's
typed snapshot, so enrichment AFTER that stage silently vanishes.

---

## 6. THE CODE REVIEWS (what they found, so we don't redo them)

- **2026-07-10** - `docs/code-review-2026-07-10.md`.
- **2026-07-14 (xhigh)** - 10 finder angles + 6 verifier groups + sweep over the
  treatment/adapter build. ~45 confirmed findings, 15 reported. Headline finds:
  the fake bleeds (cream halos), the LLM synthesis path never running (key read
  from os.environ AND before key resolution), literal "None" baked into copy,
  German decimal-comma dedup collisions, falsy-zero eating real figures, the
  mid-deck A3 tail-guard gap. All fixed; details in REBUILD-LOG 2026-07-14.
- **2026-07-15 (xhigh, on our OWN fix run)** - 15 findings; this is the review
  that exposed the silent shrink. Also: kostenrechnung dedup deleting the SUMME
  row, LLM donuts trusting model-supplied percent verbatim (fabrication class),
  the German sentence splitter breaking on ordinals/abbreviations AND flipping
  layout routing, unit-blind digit_key ("40 %" == "40 Stunden"), founder-gate
  filename divergence, brand-blind veil cache. All fixed; REBUILD-LOG 2026-07-15
  + tail entries.
- LESSON (durable): reviewing your OWN fix run finds a different bug class than
  reviewing the original code. Do it after every large fix run.

---

## 7. THE PROCESS RULES THE OWNER ENFORCES

1. **Reference-first**: any page critique/redesign STARTS by retrieving Richard's
   same-type page from `research/quality_loop/references` (all 11 ST types
   covered). Never invent layouts.
2. **The SYSTEM must auto-produce the quality.** A page hand-fixed once does not
   count. If a capable component exists but the live flow does not route through
   it, THAT is the bug ("wired to the teeth").
3. **Show the artifact**, not the test count. Render fresh, look at pixels, show
   the whole deck, not a slice.
4. **No em dashes** anywhere authored. Brand-agnostic architecture: no client
   literals or raw hex in styles/templates/patterns/treatment_*.py.
5. **Direct, no-spin status**: say done vs planned; name the broken layer.

---

## 8. MAP OF THE MD LAYER (what to read for what)

IN-REPO (`/Users/utkarsh/Projects/richard/docs/`):
| file | what it holds |
|---|---|
| **STATE-OF-THE-BUILD.md** | THIS FILE. Read first. |
| **DEVICE-VOCABULARY-GAP-2026-07-16.md** | the #1 problem: 16 presets vs 4 emitted + the role->device catalog from the new refs |
| **REBUILD-LOG.md** | the dated build journal (every fix run, incl. what I broke) |
| SESSION-STATE-2026-07-13.md | the pre-compaction dump + defect register D1-D6 (mostly CLOSED; historical) |
| VISUAL-APPEAL-MASTER-BACKLOG.md | the exhaustive backlog + status sync |
| DISCONNECT-ANALYSIS.md | the original treatment/generator disconnect analysis |
| SYSTEM-MAP.md | architecture map |
| code-review-2026-07-10.md | the first formal review |
| writer-prompt-v2/v3/v4.md | the writer contract lineage (v5 = the next one) |
| richard-voice-corpus.md | Richard's real voice, extracted from his PDFs |
| content-gap-audit.md | substance/ingestion audit |

MEMORY (`~/.claude/projects/-Users-utkarsh-Projects-richard/memory/`):
| file | what it holds |
|---|---|
| MEMORY.md | the index (points here first) |
| regressions-and-guardrails.md | **21 regression classes** + the binding rules |
| treatment-library-state.md | which treatments are BUILT/LIVE vs stubs |
| generative-pipeline-wiring-state.md | fal/OpenRouter wiring truth + cache traps |
| richard-design-system.md | the canonical target style |
| substance-vs-presentation-core-risk.md | why generated output never convinces |
| writer-voice-and-reader-model.md | the voice fix + prompt-craft lessons |
| deck-breathing-layout-philosophy.md | breathe/balance rules |
| client-feedback-punchlist.md | Richard's own 2026-06-23 punch list |
| ai-decorative-assets.md | the fal img2img material recipe |
| viz-and-asset-api-research.md | why charts are hand-built, not an API |
| wiring-first-roadmap.md | the 7-phase wiring plan (reorder per substance risk) |
| no-em-dashes.md / deliver-complete-promised-solution.md | hard rules |
| n8n-software-render-wiring.md | the n8n <-> service contract |

NOT this project (same memory dir, different work): uc2/uc3/uc4/uc5-uc6
build-state, linkedin-sourcing-automation, ewb-isihome.
