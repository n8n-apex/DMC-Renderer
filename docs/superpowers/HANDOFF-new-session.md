# HANDOFF — New session bootstrap (read this first, in order)

You are continuing work on **"richard"** — a system that generates premium German
B2B "DMC" marketing-report PDFs at the visual quality of Richard Niemeyer's
hand-designed InDesign decks. The user is a demanding visual designer; **do not
trust your own eyes or your measurements — the ONLY ground truth is the local
LM Studio vision model on the ACTUAL rendered/exported page**.

---

## 0. THE MOST IMPORTANT LESSON (read before anything)

- **This session's chat model CANNOT see images.** The `Read` tool on a PNG/
  PDF returns "this model does not support image input". You are effectively
  blind to pixels.
- **Your real eyes = LM Studio** (`qwen3.5-9b-vlm` at `http://localhost:1234/v1/chat/completions`).
  Route EVERY page/asset/screenshot through it. Use **honest, non-leading
  prompts** (ask "what is wrong?", never "is X fixed? yes/no" leading).
- The user has repeatedly caught false "fixed" claims. **Never say fixed until
  the LM Studio model confirmed it on the real PDF**, and even then be humble.
- Pixel/DOM measurements are useful for mechanics but have MISLED repeatedly
  (a "clean seam" at one row hid a ragged boundary the model saw). Always
  confirm with the model on the whole page.

---

## 1. WHERE THINGS ARE (navigate the repo)

- **Context / single source of truth:** `/Users/utkarsh/Projects/richard/CONTEXT.md` (82 KB, READ IT).
- **Repo root:** `/Users/utkarsh/Projects/richard/` (git repo; commit often with
  clear messages).
- **Reference decks (Richard's, the bar):** root `refs/` + the apex ref PDF
  `APEX - KI DMC Report v1 (1).pdf` (>100MB, rasterize with
  `pdftoppm -f N -l N -png -r 70 "<pdf>" /tmp/apexref` then Read the PNG via LM Studio).
- **Design docs / specs / plans (markdown):**
  - `docs/superpowers/` — CURRENT-STATE.md, specs/, plans/ (dated files).
    The MOST RECENT relevant ones: `plans/2026-08-19-visual-defect-audit.md`,
    `specs/2026-08-19-case-study-contrast-calibration-design.md`,
    `plans/2026-08-18-fullbleed-shrink-investigation.md`,
    `plans/2026-08-16-ralph-director-pagination-repair.md`,
    `plans/2026-08-15-director-fault-audit.md`.
  - `docs/superpowers/specs/2026-06-14-richard-design-system-EXTRACTED.md` and
    `2026-06-14-richard-infographic-vocabulary-EXTRACTED.md` — Richard's design
    grammar (the bar).
- **The pipeline (3 layers):**
  - Layer 1 Pre-processor: `research/preprocessor/` (Stages 1-8, build_package).
  - Layer 2 Renderer: `research/v7-renderer/` (the HTML/CSS/Jinja → Chromium PDF).
  - Layer 3 Post: Ghostscript flatten (PDF 1.3 @300dpi, appended in assembler).
- **Renderer internals:** `research/v7-renderer/assembler.py` (head CSS, @page,
  chrome bars), `styles/` (st_*.css + treatments/), `templates/` (+ treatments/),
  `patterns/` (st_*.py), `components/` (jinja macros), `tokens/compile_tokens.py`,
  `fixtures/apex/` (build_package.py + resolved_package.json = the fixture deck),
  `render.py` (CLI + gates), `audit_deck.py` + `audit_regions.py` (my audit tools).
- **Quality loop:** `research/quality_loop/` (perception, rubric, analysis,
  vis_client, references/).
- **Secrets/env:** `research/preprocessor/.env` (gitignored).
  **Vision routing is in it:** `VISION_API_BASE=http://localhost:1234/v1/chat/completions`,
  `OPENROUTER_VISION_MODEL=qwen3.5-9b-vlm`. The OpenRouter key is DORMANT (402) —
  never rely on it for vision. LM Studio must be running for any visual check.
- **The current deck:** `research/v7-renderer/output/report.pdf` (25 pages).

---

## 2. RUN + VERIFY (the loop you'll use constantly)

- Rebuild fixture pkg (runs real stages): `cd research/preprocessor && source .venv/bin/activate && python ../v7-renderer/fixtures/apex/build_package.py --no-fal`
- Render: `cd research/v7-renderer && source .venv/bin/activate && export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib && python render.py` (add `--fast --no-visual-gate` for speed).
- Page count check: `python -c "import fitz; print(len(fitz.open('output/report.pdf')))"` — target 25 logical = 25 physical.
- **Vision audit:** `python audit_deck.py --model qwen3.5-9b-vlm --pages N --out /tmp/a.json`
  (ALL image requests to LM Studio; audit_deck caches PNGs — delete `/tmp/deck_audit`
  or it audits STALE renders).
- **Region audit:** `python audit_regions.py --pages N-M --focus both`
  (high-DPI footer + numbered-section checks + a `probe_contrast` DET walker).
- **To look at page N:** rasterize `output/report-pN.png` or crop the PDF, then
  send to LM Studio with an HONEST prompt.

---

## 3. THE HONEST CURRENT STATE (what the user is angry about)

The user's latest complaints (learned from THEM, on the REAL deck) — NONE have
been durably fixed across sessions:

1. **Case-study pages 10, 12, 15, 17, 18 are still broken in their view:**
   - the **cream left field still overlaps/spills on the blue right rail** at the
     boundary, and/or white shows at the bottom of the cream ("cream is a box").
   - **"APEX CONSULTING" in the footer is still CUT OFF** at the bottom/left edge.
   - the whole boundary is "not aligned properly" — reads as two pages slapped
     together, no polish.
2. **Page 2** looks "crammed": the text/infographic layout is tight; the Power BI
   viz should push down a bit so body / infographic / footer align perfectly.
3. **Page 6** has a "50%" and a blue rectangle box with no clear purpose
   (a viz island / scene band that reads as unexplained).
4. Page 4: "Jousef gründete APEX Consulting..." placement/vertical rhythm.

Note the contradiction to take seriously: multiple past commits (cream bleed,
chrome-bar anchor, seam keyline, footer split) claim these fixed, and LM Studio
has even read p10 as "clean" — but the USER still sees the defects. The fixes
either regressed, target the wrong element, or only fixed the mid-row while
the real issue is elsewhere (e.g. the footer is cut at the very bottom/left by
the 303mm bleed + the tp-chrome positioning). **You must find the REAL current
PDF state, not assume prior commits worked.**

## 4. WHAT TO DO FIRST (a disciplined order)

1. **Re-establish ground truth.** Render the fresh deck (section 2). Rasterize
   pages 10, 12, 15, 17, 18, 2, 6. Send EACH to LM Studio with a brutally honest
   "list everything wrong" prompt (no leading). Record the defects with locations.
2. **Find the footer-cut root cause.** The `.tp-chrome-top/.tp-chrome-bottom`
   bars (assembler.py ~line 509-560) were made `position:absolute` against the
   303mm section; the footer bar is `bottom:6mm`. Verify in the REAL PDF whether
   the footer WORDMARK (left) and URL are geometrically below/at the visible
   sheet edge (the 6mm bleed math may be wrong, or the bar's height clips the
   text). A human-precise fix, not another guess.
3. **Find the cream/blue boundary root cause.** `.cs4-main` = 303mm, `.cs4-rail`
   = absolute `left:60%` + `border-left` keyline. The user sees overlap/spill.
   Look at the ACTUAL seam across the FULL height (not one row) + whether the
   cream extends past 60% or the rail starts before 60%. Fix the coordinate
   contract so they share ONE clean 60/40 line with no spill either way.
4. **Page 2 cramming** — the vertical rhythm between body / infographic /
   footer + the Power BI viz placement.
5. **Page 6 blue rectangle** — identify what element it is (`status_quo_scene`
   or a viz island) and make it a deliberate, explained device or remove it.
6. **Page 4 vertical distribution.**
7. Re-audit EVERY touched page via LM Studio (honest prompts) + overlap/visual
   gates; keep the 25-page count. Run the renderer + preprocessor suites.

## 5. HARD RULES (non-negotiable, from the project)

- **Brand-agnostic:** no client name/hex/font literal in LOGIC. Guard tests ban
  APEX/GEVA/etc literals + em-dashes (U+2014) in authored/treatment chrome.
- **NEVER fabricate** a person/metric/review/photo — real data only, else omit.
- **Verify on pixels via LM Studio** (the user's standing demand), not measurements.
- **No git-free edges:** commit with clear messages; keep suites green.
- The user wants you to use SKILLS per phase (brainstorm → spec → plan → TDD →
  code review → ralph loop) — not ad-hoc patching.

## 6. KEY PLACES FOR THE CASE-STUDY/FOOTER WORK

- `research/v7-renderer/styles/treatments/a4_case_study.css` — `.cs4-main`,
  `.cs4-rail` (the 60/40 + keyline + on-dark).
- `research/v7-renderer/assembler.py` — lines ~500-565: `.tp-chrome-*` bars
  (the footer-cut culprit domain), plus `.page.tp-rail`/`.page[data-page-mode]`
  height/bleed (~825-900) and `@page cover/bleed`.
- `research/v7-renderer/styles/st_02.css` — page 2 (outlook) rhythm; `st_31.css`
  + `viz.css` — page 6 (breather scene + viz); `st_05.css` — page 4 (about).
- `research/v7-renderer/render.py` — gates + `--export-idml`.
- **Existing audit artifacts you can read:** `/tmp/audit_contrast.json`,
  `/tmp/region_audit.json`, `/tmp/deck_audit*.json`.

**Your objective this session:** make pages 10/12/15/17/18 (footer + cream/blue
seam), 2 (rhythm), 6 (blue box), 4 (placement) actually correct ON THE REAL PDF,
as confirmed by LM Studio with honest prompts — and stop reporting done until
the model on the real PDF says the defect is gone.
