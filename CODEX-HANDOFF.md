# CODEX HANDOFF: the DMC report renderer

**You are taking over development of this project.** This file is the single entry
point. Everything below is verified against the code as of 2026-07-16, with
absolute paths so you can open any file directly.

Repo root: `/Users/utkarsh/Projects/richard`

---

## 0. READ THIS FIRST (in this order, then stop and start working)

| # | File | Why |
|---|---|---|
| 1 | THIS FILE | the map and the invariants |
| 2 | `/Users/utkarsh/Projects/richard/docs/STATE-OF-THE-BUILD.md` | the current truth: pipeline, state, the 5 defining bugs, owner's rules |
| 3 | `/Users/utkarsh/Projects/richard/docs/renderer-contract-audit-2026-07-16.md` | the most recent work: every empty slot in the deck, what got fixed, what is open |

Do NOT rebuild context by reading the whole `docs/` folder. It contains
historical files that are superseded. Section 2 below tells you which are current
and which are history.

---

## 1. WHAT THIS PROJECT IS

An autonomous pipeline that generates premium German **"DMC reports"**: printed
lead-magnet reports that a German Mittelstand company hands to its own prospects.

The chain:

```
n8n (writer LLM) --> {payload, images, brand_tokens} envelope
     --> dmc-renderer/build_live.py     (adapter + 13 preprocessing stages)
     --> research/v7-renderer/assembler.py  (treatment-first render)
     --> Chromium print-to-PDF --> Ghostscript flatten --> PNGs
```

### The ST section codes (you will see these everywhere)

A report is a sequence of typed pages. The code is the type, and it names the
pattern, the template, the stylesheet, and the schema entry. `ST-07A` means
`patterns/st_07a.py` + `templates/st_07a.html.jinja` + `styles/st_07a.css`.

| Code | Section | Its job |
|---|---|---|
| ST-01 | Cover | The cover. Coins the report's named cost. |
| ST-02 | Outlook | Sets up the report and promises what the reader takes away. |
| ST-05 | About | Introduces the company through the reader's problem, not a corporate bio. |
| ST-09 | Status Quo | Names the reader's current painful reality. Carries the cost calculation. |
| ST-14 | False Beliefs | The myths that keep the reader stuck, each answered. |
| ST-07A | Case Study | One customer's story as before / turn / after. Repeats per case. |
| ST-07B | Theory | The transferable principle behind the case that precedes it. |
| ST-06 | Mechanism | How the method works, step by step. |
| ST-FAZIT | Summary | Ties the thread together. Carries the cost of inaction. |
| ST-22 | Collaboration | What working together looks like. |
| ST-03 | CTA | The back cover. One ask: a conversation. |

Full visual map of each section: `/Users/utkarsh/Projects/richard/research/0-reference-analysis.md`.

### What "done" means (the quality bar)

The output must match **Richard's hand-designed InDesign decks**. Richard is the
client. His real decks are the spec, and they are in the repo root as PDFs:

- `/Users/utkarsh/Projects/richard/APEX - KI DMC Report v1 (1).pdf`
- `/Users/utkarsh/Projects/richard/Buchagentur DMC-Report (1).pdf`
- `/Users/utkarsh/Projects/richard/DMC-Report Alexander Boss doppelt (1).pdf`
- `/Users/utkarsh/Projects/richard/DMC-Report Mein_Werkzeugkoffer.pdf`
- `/Users/utkarsh/Projects/richard/Niklas Niemeyer DMC-Report Druckfertig (1).pdf`
- `/Users/utkarsh/Projects/richard/aerztepartner_v0.2 (1).pdf`
- More templates: `/Users/utkarsh/Projects/richard/files from richard/`

**The system must produce that quality automatically.** Hand-editing an output to
make it look good is not a fix. If a deck only looks right because someone tuned
the fixture, the system is still broken.

---

## 2. THE DOCUMENT MAP (every file, with status)

### 2a. CURRENT. These describe the system as it is now.

| Absolute path | What it is |
|---|---|
| `/Users/utkarsh/Projects/richard/docs/STATE-OF-THE-BUILD.md` | **The entry point.** Pipeline + the proven "all stages run every render" call-site table, the device-vocabulary gap and its fix, render/verify loops, the 5 defining bugs, the code reviews, owner's process rules, and a map of the other MD files. |
| `/Users/utkarsh/Projects/richard/docs/renderer-contract-audit-2026-07-16.md` | Per-section audit of what each renderer READS vs what the writer schema EMITS. 13 verified empty/wasted slots, 11 fixed, with the pixel verification of the cover. Most recent work. |
| `/Users/utkarsh/Projects/richard/docs/ROLE-DEVICE-CONTRACT.md` | The contract that maps a data ROLE (trend, calculation, composition, entity comparison) to a rendered DEVICE. The spine of the writer prompt and the adapter. |
| `/Users/utkarsh/Projects/richard/docs/DEVICE-VOCABULARY-GAP-2026-07-16.md` | The measurement that drove the current architecture: the renderer can draw 16 devices, the adapter could only reach 4. Includes the role to device catalog derived from Richard's newest references. |
| `/Users/utkarsh/Projects/richard/docs/writer-prompt-v5.md` | **The live writer system prompt** (paste target for n8n). German output, Richard's copy law, the device shapes, plus the per-section schema additions appendix. |
| `/Users/utkarsh/Projects/richard/docs/resolve-schema-node-v5.js` | **The live n8n `Resolve Schema & Build Prompts` code node** (paste target). Defines which keys each section may emit. A device key missing here is dark no matter what the prompt says. |
| `/Users/utkarsh/Projects/richard/docs/n8n/WRITER-GATE-WIRING.md` + `/Users/utkarsh/Projects/richard/docs/n8n/writer_gate.js` | **The third n8n paste target: a deterministic content-QC gate that runs AFTER the writer.** It catches what the prompt cannot guarantee: computed numbers (the invented "83%"), banned vocabulary, credential claims not in the data ("TÜV certified"), and language drift. The prompt alone gets about 95% compliance; this closes the rest. Do not treat the writer prompt as the only n8n lever. |
| `/Users/utkarsh/Projects/richard/docs/SYSTEM-MAP.md` | Deep subsystem audit and rebuild blueprint, grounded in a real render. Large. Read its CRITIQUE section second: it corrects parts of the map. |
| `/Users/utkarsh/Projects/richard/docs/REBUILD-LOG.md` | Running log of the rebuild loop, iteration by iteration. Large (91 KB). Use it to answer "why is this like this", not as a spec. |

### 2b. HISTORICAL. True when written, now partly superseded. Read for cause, not current state.

| Absolute path | What it is |
|---|---|
| `/Users/utkarsh/Projects/richard/docs/DISCONNECT-ANALYSIS.md` | 2026-07-11 multi-agent trace of why a real deck rendered flat. The origin of the treatment work. |
| `/Users/utkarsh/Projects/richard/docs/VISUAL-APPEAL-MASTER-BACKLOG.md` | The visual-appeal backlog with loop status. Many items are done. |
| `/Users/utkarsh/Projects/richard/docs/SESSION-STATE-2026-07-13.md` | A pre-compaction snapshot. Superseded by STATE-OF-THE-BUILD. |
| `/Users/utkarsh/Projects/richard/docs/code-review-2026-07-10.md` | Code review, all 15 findings fixed. |
| `/Users/utkarsh/Projects/richard/docs/content-gap-audit.md` | AI output vs Richard's real deck for the same client. Good for understanding the content gap. |
| `/Users/utkarsh/Projects/richard/docs/richard-voice-corpus.md` | Verbatim voice anchors extracted from four real Richard decks. Feeds the writer prompt. |
| `/Users/utkarsh/Projects/richard/docs/writer-prompt-v4.md` | The previous live prompt. **v5 supersedes it**, but v4 is the proven base: if v5 ever looks wrong, diff against v4. |
| `/Users/utkarsh/Projects/richard/docs/writer-prompt-v3.md`, `writer-prompt-v2.md` | Older prompt generations. History only. |
| `/Users/utkarsh/Projects/richard/01_DMC_Master_System_v1.md`, `08_DMC_Design_System_v2.md`, `PRD.md`, `VISUAL_ASSETS.md`, `context.md`, `renderer_json.md`, `richard-grammar-v2.md` | Original briefs and design-system notes at the repo root. Background on intent. |

### 2b-2. FOUNDATIONAL RESEARCH. `/Users/utkarsh/Projects/richard/research/*.md`

These answer "why is it built this way". Read before proposing an architectural
change, so you do not relitigate a decision that was already researched.

| Absolute path | What it answers |
|---|---|
| `/Users/utkarsh/Projects/richard/research/SUMMARY.md` | Phase 1 synthesis of all the research below. Start here. |
| `/Users/utkarsh/Projects/richard/research/0-reference-analysis.md` | Reference analysis and the ST visual map (what each ST section is). |
| `/Users/utkarsh/Projects/richard/research/0b-fixture-issues.md` | Known fixture problems. |
| `/Users/utkarsh/Projects/richard/research/A-engine-selection.md` | **Why Chromium and not WeasyPrint.** Read before touching the render engine. |
| `/Users/utkarsh/Projects/richard/research/B-typography-polish.md` | Typography decisions. |
| `/Users/utkarsh/Projects/richard/research/C-focal-point.md` | Focal point and composition. |
| `/Users/utkarsh/Projects/richard/research/D-decorative-illustrations.md` | Decorative asset strategy. |
| `/Users/utkarsh/Projects/richard/research/E-paged-media.md` | **CSS Paged Media feature matrix.** What actually works in print, per engine. Directly relevant to the bleed and page-box bugs. |
| `/Users/utkarsh/Projects/richard/research/F-german-typography.md` | German typography rules (hyphenation, quotes, long compounds). |

### 2b-3. PLANS AND SPECS. `/Users/utkarsh/Projects/richard/docs/superpowers/`

27 implementation plans in `plans/` and about 10 design specs in `specs/`, dated
2026-05-16 onward (renderer R1/R2 foundations, the preprocessor architecture
migration in 4 phases, brand extraction, closed-loop page convergence). This is
the build's design history. Use it to understand how a subsystem was intended to
work; it is not current-state.

### 2c. PROJECT MEMORY. Durable lessons, not a spec. `/Users/utkarsh/.claude/projects/-Users-utkarsh-Projects-richard/memory/`

**These are the highest-value files for avoiding repeated mistakes.**

| File | What it is |
|---|---|
| `MEMORY.md` | Index of the memory folder. |
| `regressions-and-guardrails.md` | **Read this one.** 30 numbered regression classes: every bug that came back, with its rule. 36 KB. |
| `writer-voice-and-reader-model.md` | Voice, reader model, and **Richard's copy law transcribed verbatim**. |
| `richard-design-system.md` | The design grammar derived from his decks. |
| `treatment-library-state.md` | State of the treatment system. |
| `generative-pipeline-wiring-state.md` | How the generative stages are wired. |
| `deck-breathing-layout-philosophy.md`, `no-em-dashes.md`, `substance-vs-presentation-core-risk.md`, `ai-decorative-assets.md`, `deliver-complete-promised-solution.md` | Standing principles. |

**WARNING, different projects share that memory folder.** These files are about
OTHER Richard workstreams (n8n automation use cases), NOT this renderer. Ignore
them for renderer work: `uc2-plaud-close-build-state.md`,
`uc3-ewb-v2-build-state.md`, `uc4-onedrive-kundenordner-build-state.md`,
`uc5-uc6-learningsuite-build-state.md`, `linkedin-sourcing-automation-build-state.md`,
`ewb-isihome-real-not-fabricated.md`, `n8n-software-render-wiring.md`,
`client-messages-always-de-and-en.md`, `automate-the-human-process-not-just-the-api.md`.

---

## 3. THE CODE MAP

| Absolute path | Owns |
|---|---|
| `/Users/utkarsh/Projects/richard/dmc-renderer/build_live.py` (1146 lines) | **The adapter and the orchestrator.** Turns the German n8n envelope into the renderer contract, then runs all preprocessing stages. Most integration bugs live here. |
| `/Users/utkarsh/Projects/richard/dmc-renderer/service.py` (220 lines) | FastAPI door on port 8099 (`POST /render`). |
| `/Users/utkarsh/Projects/richard/dmc-renderer/synthesize_visuals.py` (463 lines) | Derives grounded stat/before-after devices from a page's own copy. Contains `digit_key` and `donut_spec`, used by the adapter for de-duplication. |
| `/Users/utkarsh/Projects/richard/research/v7-renderer/assembler.py` (1277 lines) | **The renderer.** Fonts, page CSS, treatment routing, Chromium print, Ghostscript flatten. `render_package` at line 965. |
| `/Users/utkarsh/Projects/richard/research/v7-renderer/treatment_engine.py` (958 lines) | Chooses and adapts a treatment per page. |
| `/Users/utkarsh/Projects/richard/research/v7-renderer/treatment_stylist.py` (595 lines) | Per-page styling decisions, adjacency rules. |
| `/Users/utkarsh/Projects/richard/research/v7-renderer/patterns/` (22 files) | Per-section Python that maps `page['data']` into template context. `st_01.py` is the cover. |
| `/Users/utkarsh/Projects/richard/research/v7-renderer/templates/` (15 files) | Per-section Jinja. |
| `/Users/utkarsh/Projects/richard/research/v7-renderer/components/` (42 files) | The macro library: viz devices, icons, stat rails. |
| `/Users/utkarsh/Projects/richard/research/v7-renderer/styles/` (20 files) | CSS. `components.css` is global and guarded; `st_XX.css` are page-scoped. |
| `/Users/utkarsh/Projects/richard/research/v7-renderer/tests/` (44 files) | The test suite, including the guard battery. |
| `/Users/utkarsh/Projects/richard/research/v7-renderer/fixtures/apex/` | The apex fixture package and its viz curation (`viz_curation.py` holds the no-fabrication guard). |
| `/Users/utkarsh/Projects/richard/dmc-renderer/fixtures/` | Real client payloads: `christoph_v4_payload.json`, `christoph_v5_payload.json`, `apex_consulting_payload.json`. |
| `/Users/utkarsh/Projects/richard/dmc-renderer/render_christoph.py` | **Standing harness:** renders the full christoph deck and rasterizes every page. |
| `/Users/utkarsh/Projects/richard/dmc-renderer/render_cover_check.py` | **Standing harness:** renders only the cover with the audit-fixed slots populated, rasterizes page 1. Fast loop for cover work. |
| `/Users/utkarsh/Projects/richard/dmc-renderer/verify_contract_fixes.py` | **Standing harness:** offline check (network stubbed) that the 2026-07-16 adapter contract fixes still hold. Expect 10/10. Run after any `build_live.py` change. |

### Assets, references, and deployment

| Absolute path | What it is |
|---|---|
| `/Users/utkarsh/Projects/richard/refs/` | The four clean source PDFs used for voice extraction (`buchagentur`, `alexander_boss`, `niklas_niemeyer`, `aerztepartner`) plus `refs/renders`. These are the inputs behind `docs/richard-voice-corpus.md`. |
| `/Users/utkarsh/Projects/richard/docs/voice-extract/` | The `pdftotext` output of those PDFs (`*.txt` and `*.raw.txt`). The raw evidence behind every voice anchor. |
| `/Users/utkarsh/Projects/richard/client_assets/` | Per-client real assets (e.g. `christoph-winter/`) plus a `README.md` explaining the layout. |
| `/Users/utkarsh/Projects/richard/incoming_assets/` | Per-client incoming assets, one folder per case-study client: `conesso`, `cordes`, `frese`, `goldmantax`, `hanisch`. These names match the apex case studies, which is how fixture drift is traced. |
| `/Users/utkarsh/Projects/richard/_renders/` | Historical render outputs. |
| `/Users/utkarsh/Projects/richard/dmc-renderer/_local_out*/` | Local harness outputs: `pkg/`, `render/report.pdf`, `png/`. |
| `/Users/utkarsh/Projects/richard/Dockerfile` | The container build. The service runs on port 8099 via OrbStack/Docker. Local harness renders are the fast loop; the container is the deployment path. |
| `/Users/utkarsh/Projects/richard/research/idml-spike/`, `pattern-spike/`, `quality_loop/`, `v7-test/`, `decoration-samples/` | Exploratory spikes. Not part of the live pipeline. |

### The pipeline, with current call sites in `build_live.py`

Verified 2026-07-16 after the latest edits. **There is no render-only mode.**
Every stage runs on every render; if the layout looks unprocessed, the cause is
data, not a skipped stage.

```
_build()                       line  883
  validate_and_resolve_brand_tokens   910
  resolve_fonts                       914
  resolve_axes                        919
  validate_copy + validate_copyfit    924
  structure_content                  1031
  resolve_slots                      1041
  generate_assets (fal)              1064
  generate_components_for_report     1083
  plan_layout                        1090
  assemble_package                   1095
  route_package                      1116
  --> assembler.render_package (research/v7-renderer/assembler.py:965)

per page, earlier, inside envelope_to_render_request():
  synthesize_page_visuals             810
public entry: build_live_package()   1136
```

---

## 4. HOW TO RUN IT

Environment facts:

- Python venv: `/Users/utkarsh/Projects/richard/research/v7-renderer/.venv` (Python 3.11.15)
- Every command needs `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` on this machine.
- `gs` and `pdftoppm` are installed at `/opt/homebrew/bin/`.
- API keys live in `/Users/utkarsh/Projects/richard/research/preprocessor/.env`
  (`OPENROUTER_API_KEY`, `FAL_KEY`). **Use them via environment only. Never write a
  key value into any file, and never echo one to check presence. Use `${VAR:+SET}`.**

Render the standing client fixture end to end and rasterize every page:

```bash
cd /Users/utkarsh/Projects/richard/dmc-renderer && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib ../research/v7-renderer/.venv/bin/python render_christoph.py
```

Render only the cover and rasterize page 1 (fast loop for cover work):

```bash
cd /Users/utkarsh/Projects/richard/dmc-renderer && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib ../research/v7-renderer/.venv/bin/python render_cover_check.py
```

Check the adapter contract fixes offline (no API key needed, expect 10/10):

```bash
cd /Users/utkarsh/Projects/richard/dmc-renderer && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib ../research/v7-renderer/.venv/bin/python verify_contract_fixes.py
```

Run the test suite:

```bash
cd /Users/utkarsh/Projects/richard/research/v7-renderer && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python -m pytest tests/ -q
```

Run the fast guard battery (design invariants, tokens, no-literals):

```bash
cd /Users/utkarsh/Projects/richard/research/v7-renderer && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python -m pytest tests/test_components.py tests/test_tokens.py tests/test_design_conformance.py tests/test_no_literals_in_architecture.py -q
```

Outputs land in `_local_out*/` next to the harness: `pkg/` (resolved package),
`render/report.pdf` + `report.html`, `png/` (rasterized pages).

---

## 5. INVARIANTS. Do not break these.

These are enforced by tests or by hard experience. Each one cost a real
debugging cycle.

1. **The no-fabrication guard is a correctness invariant.** Every figure a device
   displays must appear verbatim in that page's own copy.
   `research/v7-renderer/fixtures/apex/viz_curation.py::_figure_grounded`. Never
   weaken or bypass it. Note it deliberately EXCLUDES `data['viz']` from its
   evidence: a device must not ground itself.
2. **No client literals, no raw hex, no em dashes** in `templates/`, `styles/`,
   `patterns/`, `components/`. Enforced by
   `tests/test_no_literals_in_architecture.py`. Client numbers live in fixtures.
3. **`box-shadow` is banned on viz.** Enforced by `test_viz_flat_on_cream`. Use a
   hairline border plus a surface fill. Shadows were the owner's "dull" complaint.
4. **Stat-value selectors in `styles/components.css` must use `var(--type-stat-xl)`.**
   Enforced by `tests/test_components.py::test_shout_components_use_real_tiers`.
   To shrink a figure in a narrow column, scope it DOWN in the page's own
   stylesheet. See `styles/st_06.css:161` and `styles/st_01.css` for the two
   worked examples.
5. **An undefined CSS var voids the whole declaration.** `--type-h1` does not
   exist. The real tiers are: `--type-stat-xl` 60pt, `--type-stat` 40pt,
   `--type-display` 32pt, `--type-signature` 28pt, `--type-h2` 20pt,
   `--type-pullquote` 18pt, `--type-h3` 14pt.
6. **A figure must never break across lines.** German figures like `300.000 €` will
   split mid-number in a narrow column. `white-space: nowrap` alone is not enough:
   it converts the break into a horizontal overflow. The size must come down too.
7. **Ordering contract:** `assemble_package` prefers `structure_content`'s typed
   snapshot. Enrichment added AFTER that stage silently vanishes.
8. **Chromium ignores `@page` background-image gradients.** A veil must be baked
   into a derived asset. See `assembler._veiled_ground_uri`.
9. **Bleed pages are knife edges.** Content is clamped to 296.5mm inside a 297mm
   sheet with overflow hidden. This means **overflow on a bleed page is silently
   clipped while the page count stays correct.** Page-count QC cannot see it.

---

## 6. THE BUGS THAT DEFINED THIS BUILD

Read these so you do not reintroduce them. Full detail in
`docs/STATE-OF-THE-BUILD.md` and `memory/regressions-and-guardrails.md`.

1. **The silent global shrink.** Chromium scales the WHOLE document down when any
   fragment exceeds its page box. A 0.4mm border made the entire deck print at
   ~84.6% for weeks. There was no spill, because the shrink prevented it, which
   blinded the page-count check.
2. **The device-vocabulary gap.** The renderer could draw 16 viz presets; the
   adapter emitted 4. Twelve devices were built and unreachable for months while
   the owner complained the deck felt "dull and same-y". Cause: device choice was
   a per-FIELD syntactic reflex instead of a data ROLE decision.
3. **The rename mismatch class.** A renderer reads `proof_stats`; the adapter fills
   `stats`. The data exists and is dropped at the key boundary, so the slot renders
   empty. Found on the cover in the 2026-07-16 contract audit. When a slot is
   empty, grep the READER for its exact field name, then grep the adapter for who
   writes THAT name.
4. **Fixture drift under a hardcoded table.** The apex case studies were replaced
   (Martina Ammon became GoldmanTax); five curation bindings and about 14 tests
   still named the old clients. When fixture data is replaced, grep the OLD
   entity's name across the whole tree.
5. **Bundled but not wired.** Montserrat TTFs sat in `fonts/` since May with no
   `@font-face`, so every deck reviewed for months silently printed in the
   fallback face. Assets need a wiring check, not a presence check.

---

## 7. CURRENT STATE (2026-07-16)

### Working and verified
- All preprocessing stages run on every render, proven by call site.
- The role to device selector (`build_live._role_devices`) plus the primitives:
  `icon_stat_row`, `column_chart`, `formula_ladder`, `grouped_bars`,
  `stacked_bar_100`, `entity_bars`, and an 18-key icon set.
- Montserrat and Playfair Display are bundled and wired.
- The deck prints at true design scale (the shrink is fixed).
- The contract audit's 11 shipped fixes, including the cover stat rail and the
  founder byline on the cover and summary, pixel-verified.

### Open, and why
1. **The n8n side is NOT yet updated.** This is the single biggest lever. Three
   paste targets, all owner action, all in this repo:
   `docs/writer-prompt-v5.md` (the writer system prompt),
   `docs/resolve-schema-node-v5.js` (the `Resolve Schema & Build Prompts` node),
   and `docs/n8n/writer_gate.js` (the post-writer content-QC gate, wiring in
   `docs/n8n/WRITER-GATE-WIRING.md`). Until these are live, real decks stay
   v4-shaped and the new devices never appear in production output.
2. **15 tests fail from the apex fixture drift** (bug 4 above). Full suite as of
   2026-07-16 after all current work: **15 failed, 342 passed, 1 skipped, 5 xfailed**
   > **SUPERSEDED 2026-08-13:** this count is stale. The authoritative baseline
   > is `docs/phase-zero/BASELINE-LEDGER-2026-08-13.md` — renderer 398 passed /
   > 0 failed, preprocessor 731 passed, dmc-renderer 103 passed / 4 xfailed,
   > guard battery 45 passed, offline harness 10/10. The 15 failures were
   > realigned to the current fixture (US-001..US-003).
   (about 8 minutes). That count is unchanged by the recent contract fixes, so it is
   pre-existing, not inherited on faith: the failing test files contain zero
   references to the changed modules. They are still 15 blind spots on the flagship
   case-study and cover pages, which is exactly where a quality regression would
   land unseen. Fixing them means realigning the tests to the current fixture
   (GoldmanTax, not Martina Ammon) and to the 2026-07-13 light-ground contract.
3. **The cover teaser rail** (`teaser_items`) is deliberately unwired. Feeding it
   overflows and is silently clipped. It needs a layout change, not a data key.
4. **ST-05 testimonials** are image assets, not copy. They need an asset-resolution
   step or the dead pattern block should be removed.
5. **The founder photo is a 500px site headshot.** It visibly limits the cover.
6. **The fal `fazit_background` prompt bakes page text into the generated art**,
   because `build_image_prompts` feeds page copy to fal.

---

## 8. HOW THE OWNER WORKS (follow these)

- **"Done" means the artifact was shown, never a claim.** A PDF with its page count
  and the real components present. Not "should work".
- **Look at the pixels.** Markup assertions pass while a figure breaks across two
  lines. Render it and open the PNG.
- **A "pre-existing failure" is a claim to verify, not an excuse to inherit.**
- **Do not weaken a guard to make a test pass.** Fix the drifted side.
- **No em dashes** in printed German copy, and the owner applies the same rule to
  documents written for him.
- He wants the SYSTEM to produce the quality. Hand-tuning an output is not a fix.

---

## 9. GOTCHAS THAT WILL COST YOU TIME

1. **This is NOT a git repository.** `git status`, `git diff`, `git stash`, and
   `git blame` do not work anywhere under `/Users/utkarsh/Projects/richard`. There
   is no history and no undo. Consequences:
   - "unmodified since date X" is an mtime claim, not history.
   - You cannot neutralize a change by stashing. Prove causality by call path
     instead: grep the changed symbol in the failing files, and name the only real
     caller.
   - **Back up a file before a large edit**, because there is no way to recover it.
2. **Two source documents from Richard are GONE from disk.** The copy-law file
   ("Wichtig für Copy (KI-Floskeln).docx") and the newest reference PDFs (Luka
   Martic, Frese Recruiting Report v2) were in `~/Downloads/drive-download-*` and
   that folder no longer exists. **Their content survives, transcribed verbatim**,
   in two places: the GERMAN COPY LAW section of
   `/Users/utkarsh/Projects/richard/docs/writer-prompt-v5.md`, and
   `memory/writer-voice-and-reader-model.md`. Treat those as the source of truth
   now, and ask the owner to re-share the originals if you need them.
3. **The n8n side is not in this repo.** The writer prompt and schema node live in
   the owner's n8n instance. The two files in `docs/` are the paste targets.
4. **`docs/` contains superseded files.** Use section 2 above to tell current from
   historical. Do not treat `SESSION-STATE-2026-07-13.md` or the older
   `writer-prompt-v*.md` as current.
5. **Rendering needs Chromium plus Ghostscript**, and the OrbStack/Docker container
   is a separate deployment path. Local renders through the harness scripts are the
   fast loop.

---

## 10. IF YOU ONLY DO ONE THING

Render the deck, open the PNGs, and compare them page by page against Richard's
real PDFs in the repo root. Every meaningful improvement in this project has come
from looking at the output next to his, naming one concrete difference, and fixing
that. Every regression has come from trusting an assertion instead of the pixels.
