# SESSION STATE — 2026-07-13 (pre-compaction consolidation)

Owner directive: "update all context so that when compaction happens, you retain
maximum knowledge about the things that are fucking up because of you right now.
I will give my detailed feedback after compaction." His verdict on the current
deck: **"Very bad treatments, there are many other things."** Detailed feedback
PENDING — do not start new build work until it arrives; fix against it.

---

## 1. KNOWN DEFECTS VISIBLE IN THE OWNER'S SCREENSHOTS (my own read; his list may add more)

### D1. ST-FAZIT page (p15) — MULTIPLE breakages, worst page
- **The portrait RAIL fired on the FAZIT page** (founder photo repeats there,
  over a mostly EMPTY navy column). ROOT CAUSE: the slot registry gives
  ST-FAZIT a `founder_hero` slot (slot_registry.py ~line 55) → founder.webp
  resolves on the FAZIT page too → `_primary_image` returns it → the
  a4_editorial_fill PORTRAIT-RAIL variant (keyed on bare `td.image`) fires.
  **The rail variant must be gated to ST-05 (About), not to any page where an
  image happens to resolve.** The FAZIT rail has no stats/ident content → dead
  navy column.
- **Hero-quote OVERFLOW**: the kernbotschaft at `--type-signature` (28pt) in the
  now-58%-wide main column CLIPS mid-word ("Modernisierungsmeth[ode]" cut at the
  rail edge). `overflow-wrap` is not enough at that size; when the rail variant
  fires the hero-quote must scale down (or the rail must not fire, per above).
- **Sceneband/CTA COLLISION**: the fal fazit_background renders as the 40mm
  sceneband but the CTA foot ("JETZT TERMIN VEREINBAREN / inventory-one.com")
  prints OVER the image (overlap). The mid (with sceneband) + foot exceed the
  fill column when the rail variant narrows it; also the FAZIT "background"
  image_type probably should NOT render as a small photo band at all (it is a
  full-bleed ATMOSPHERE asset, not a scene snapshot).

### D2. ST-03 back cover (p17) — top ~60% empty navy with one lone rust triangle
The geo-shape device renders alone in a huge void; content (DER NÄCHSTE
SCHRITT + headline + lede + rule + CTA + QR + wordmark) is bottom-anchored.
Needs the reference back-cover anatomy (check refs: niklas p20 / boss p11 —
both carry a strong statement + more structure in the upper field).

### D3. ST-22 (p16) — still ~60% empty middle
Known thin-copy page, but the owner keeps flagging it; the CTA-anchored layout
alone does not save it. Options recorded: richer writer copy (schritte for
ST-22), or a designed device (scene band / steps) for the middle.

### D4. Case-study pages (p12/p13 etc.) — "very bad treatments" likely includes:
- Left-field bottom VOID returns on case studies WITHOUT a device (only case 1
  got a product shot; cases 3/4/5 have no vorher_nachher → no arrow → empty
  foot band).
- Rail ERGEBNIS statement-stats style is weak: prose values render as wrapped
  bold lines with awkward hyphenation ("meh-rere Tage"); label caps + value
  reads cluttered. The `(vorher: ...)` parenthetical values are ugly as stats.
- Rail middle is airy on cases with only 2 stats.
- NN initials avatar repeats identically on every case (5×) — monotonous; the
  reference decks vary their case-page proof (photos, product shots).

### D5. Cover (p1) — soft/blurry founder photo
500×500 site headshot stretched full-width. PENDING OWNER DECISION: supply the
hi-res wood-wall photo (overwrite client_assets/christoph-winter/founder.webp)
or gate low-res images off the cover. Cover otherwise renders the Richard
anatomy (photo top / navy field / two-tone headline).

### D6. fal scene band styling is a crop-strip
The generated art renders as a 40mm cover-cropped strip (ST-09 works okay; on
FAZIT it collides, see D1). The strip treatment is a first pass; the reference
decks integrate photos as duotone plates / full-bleed grounds with overlapping
mockups (see mein_werkzeugkoffer p16 left zone).

---

## 2. WHAT WAS BUILT TONIGHT (all verified in pixels at the time; file inventory)

### Pipeline / keys
- `service.py` + `render_christoph.py` now load `/Users/utkarsh/Projects/richard/.env`
  (OPENROUTER_API_KEY + FAL_KEY were set there by the owner but NEVER loaded —
  that was the "fal breakage"). `build_live._build` passes the keys through.
- **fal generation worked end-to-end** once a 5s default httpx timeout was
  raised (timeout=120 for fal, 60 for openrouter prompt-builder): all 5 assets
  generated (cover_hero unused-by-cover?, status_quo_scene, fazit_background,
  report texture, atmospheric gradient) and are CACHED under
  `$TMPDIR/dmc_live_cfg/asset_cache` (+ restructure_cache for copy-fit).
- LLM copy-fit (route_package restructure) ran with the key.

### Treatments / hosts (research/v7-renderer)
- `a4_editorial_fill`: PORTRAIT-RAIL variant (`.ef-grid.has-rail` + `.ef-rail`:
  photo plate + ident + on-dark stats; `.ef-main` carries the old fill column,
  58% when railed) — **defect D1: fires on any td.image; must be ST-05-gated**.
  Plus `.ef-sceneband` (fal art host, 40mm strip) — defect D1/D6.
- `horizontal_process` REBUILT to the reference anatomy (mein_werkzeugkoffer
  p16/17): LEFT mockup hero (trio) + centered headline + lede; MIDDLE navy
  numbered-steps panel (accent italic 01–04, hairline dividers); RIGHT navy
  ERGEBNIS rail (payoff centered + CTA at foot). Owner has NOT yet judged this
  rebuild (it may be part of "very bad treatments" — await feedback).
- `a4_case_study`: `.cs4-devices` band (one hero device: product img REPLACES
  arrow when present); footer chrome present.
- `st_14` proof band: ONE flex row (donuts + compact range tiles); donut
  GRADIENT stroke restored (`.fb-proof-viz` had overridden `stroke` on the
  gradient arc — override removed).
- Footer page-chrome (wordmark · url · folio) baseline-aligned (was 3 mis-set
  segment rules).

### Adapter / routing (dmc-renderer)
- `build_live.py`: ST-06 claims `product-1` (hero trio) BEFORE the bildwunsch
  router; case-study bildwunsch now gets product-2 (phone). ORDERING CONTRACT:
  any data enrichment must run BEFORE `structure_content` (its typed snapshot
  is what assemble_package prefers — keys added later VANISH from the package).
- `fixtures/christoph_v4_payload.json` + `render_christoph.py` = the standing
  repro harness (scratchpads are ephemeral; repo files survive).

### Reference corpus (research/quality_loop)
- classify.py: 6→11 labels, corpus-verified kickers + 300-char heading zone +
  `_MANUAL_LABELS` (human-verified ST-09/ST-07B pages) + apex deck flagged
  `machine_generated` (always OTHER). ALL 11 page types now retrieve real
  Richard references. **THE reference pages for design work:**
  - ST-06 mechanism: `mein_werkzeugkoffer` p9 (PDF p16/17 spread!), buchagentur p9
  - ST-03 closers: boss p10, aerztepartner p11, niklas p20
  - ST-09: buchagentur p3; ST-07B: niklas p7/9/11/13, boss p4
- **PROCESS RULE (owner-enforced): any page critique/redesign STARTS by
  retrieving Richard's same-type page from this index and rebuilding to THAT
  anatomy. Never invent layouts.**

### Engine safety (earlier today, still in force)
- `candidate_fits` requires BUILT template (stubs never assigned; render_fn
  honored; cache invalidated on register).
- A3 HERO SUSPENDED: mid-deck A3 landscape compresses surrounding A4 pages to
  ~71% in Chromium mixed-size print (bisect-proven). ST-06 tail A3 is safe.
  Engine fix (print-per-format + gs merge) is backlog.
- `_component_svgs`: (OSError, ValueError) catch + `is_relative_to` containment.
- shared `synthesize_visuals.donut_spec/percent_arc`: >100% never a ring;
  one-figure-one-device; pair numbers seed the dedup.

## 3. HOW TO RENDER / VERIFY (post-compaction quickstart)
```bash
cd /Users/utkarsh/Projects/richard/dmc-renderer
set -a; source ../.env; set +a   # loads OPENROUTER_API_KEY + FAL_KEY (owner's)
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib \
  ../research/v7-renderer/.venv/bin/python render_christoph.py
# -> _local_out/render/report.pdf + _local_out/png/p-NN.png (17 sheets expected)
# assets cache under $TMPDIR/dmc_live_cfg/ makes keyed re-renders ~free
```
Tests: `research/v7-renderer` venv, pytest on test_treatment_dispatch,
test_treatment_stylist, test_treatment_pagesize, test_no_literals_in_architecture,
test_tokens (44 green as of tonight). Deliverable path convention:
`_renders/dmc_christoph_v4_keyed_2026-07-13.pdf`.

## 4. OPEN DECISIONS / PENDING
1. **OWNER'S DETAILED FEEDBACK (post-compaction) — the priority queue.**
2. Hi-res founder photo (cover blur) — owner to supply or approve gating.
3. Writer-side: figures for ST-06 (gauge), richer ST-22 copy, more bildwunsch
   entries if more product placements wanted; the invented "83 %" is STILL in
   the writer's slot-13 output (flagged, unfixed upstream).
4. Big tracks untouched: H1-H3 QC-loop wiring (grader Chromium recalibration
   done? NO — still WeasyPrint-calibrated), G assembler convergence, A5
   bi_dashboard, container rebuild with all of tonight's changes (the running
   container is STALE vs the local code).

---
## STATUS SYNC 2026-07-14 (post-review fix run)
The /code-review xhigh + fix run addressed the register: D1 FIXED (variant
contract td.variant, adapter-decided; quote hyphenation; duotone growing
sceneband), D2 FIXED (ST-03 full-bleed atmosphere ground + 297mm fill), D3
IMPROVED (ablauf_text -> verbatim numbered steps -> timeline), D4 IMPROVED
(s.sub citations, paren-split statement stats, threshold, avatar removed),
D6 FIRST PASS (duotone plates). NEW this run: TRUE FULL-BLEED rails (bleed
page + section padding + self-drawn tp-chrome; Chromium ignores @page
background-image entirely - background-color only), baked ground veil
(_veiled_ground_uri), ~30 adapter/synthesis correctness fixes (see
REBUILD-LOG 2026-07-14). 53 tests green. Deliverable:
_renders/dmc_christoph_v4_fixed_2026-07-14.pdf. STILL OPEN: D5 cover photo
(owner), Montserrat TTF (owner), fal fazit_background carries baked-in page
text (fal prompt lane), ST-03 wash strength tunable, container STALE.

---
## SUPERSEDED 2026-07-16
This document is now HISTORICAL. The current authoritative entry point is
`docs/STATE-OF-THE-BUILD.md`. Defect register status: D1/D2/D3/D4/D6 CLOSED
(see VISUAL-APPEAL-MASTER-BACKLOG STATUS SYNC 2026-07-16 + REBUILD-LOG
2026-07-14/15/16); D5 (hi-res cover photo) still owner-blocked. The container is
no longer stale (rebuilt 2026-07-16). The deck now prints at TRUE design scale
(the ~85% silent shrink is fixed) and in the real brand font.
