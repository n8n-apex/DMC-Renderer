# Full-Bleed Shrink Investigation — Findings (2026-08-18)

## The symptom

Every full-bleed page in the deck (cover ST-01, breathers ST-31/32, back cover
ST-03) renders at ~92% of the sheet height with a **25-40% white bottom band**.
The dark content ends at ~60% and the page's lower third is pure white
(measured: bands 6-8 at 0% ink on p1/p8/p20/p24, deterministic across runs).
The Ghostscript flatten is NOT the cause: the pre-flatten `report_print.pdf`
shows the identical defect, so the shrink happens in **Chromium's print pass**.

## ROOT CAUSE (proven by isolation + deck bisect)

**A mid-deck A3 named page (`@page a3-landscape`) makes Chromium's mixed-size
print compress EVERY A4 page to ~92%.** The treatments had promoted the 5 case
studies to `format-a3` spreads; the deck therefore carried A3 sheets mid-deck.
Chromium, forced to mix A3 and A4 in one print job, silently shrinks all A4
pages to fit — the cover/breathers/back (which are full-bleed 297mm A4) each
rendered at ~92% with a white bottom band. This matches the defect documented
in CURRENT-STATE ("mid-deck A3 breaks Chromium's mixed-size A4 print").

Evidence chain:
1. A single `<div style="height:297mm">` in a margin:0 A4 page = 100%, 1 page.
2. The SAME full deck with `format-a3` removed from the HTML = cover 100%.
3. The deck with `format-a3` present = cover 61.5% + white bands 6-8.
4. Named `@page cover`/`@page bleed` alone do NOT cause the shrink (isolated
   reproductions at 100% with `body{margin:0}` + `height:100%` wrapper).
5. The body-default-margin red herring: `body { margin: 0 }` is already in the
   chassis; the 92% in early repros was the missing wrapper `height: 100%`.

## The fix (Ralph FB-1..FB-4, all DONE)

- **FB-1 — no A3 case studies**: `treatment_stylist.py` no longer honors the
  explicit `page_format:"a3"` signal. All 5 case studies render `a4_case_study`
  (A4 single pages — also Richard's own rule: "Case studies are A4 single
  pages (Einzelseite), NOT auto-promoted"). The a3 intent is recorded in the
  assignment reason. 4 tests updated to the no-A3 contract.
- **FB-2 — full-bleed wrappers**: `assembler.py` full-bleed clamp changed from
  `height: 296.5mm` to `height: 100%` (a fixed sub-sheet wrapper height makes
  Chromium scale the 297mm child). Content containers (`.cv`, `.br-bleed`,
  `.cta-bleed`) stay at fixed 297mm (never a 100% chain — that collapses).
- **FB-3 — ST-09 split**: the status-quo page (3-para body + 6 rich symptoms +
  viz) exceeded one A4 and clipped. `plan_section_pages._split_st09` splits it
  at the context/evidence boundary (page 1 = title+body+viz, page 2 =
  symptoms+title); the ST-09 continuation pages are TREATED (a4_editorial_fill
  — the symptom grid + prose both fill the sheet).
- **FB-4 — overlap + visual gates**: `overlap_detector.py` exempts the rail
  treatments' self-drawn chrome (`tp-chrome-*`, the same furniture the @page
  margin boxes paint on normal pages). `render.py` maps the ST-09 evidence
  continuation to a density-only gate (its symptom grid IS the device, not a
  numeric figure; the `?figures` regex misfires on the symptoms' prose
  durations). **GATE CLEAN at 25 pages.**

## Results (pixel-verified)

- **Cover (p1): 100% ink top-to-bottom** (was 61.5% + 40% white).
- Breathers (p8/p20) and back cover (p25): full-bleed.
- **25 logical = 25 physical pages, zero overflow, no blank sheets.**
- Overlap gate CLEAN; reference-grounded visual gate CLEAN.
- Renderer 431 passed / 5 xfailed (pre-existing); preprocessor 779 passed.

## Acceptance
- ✅ Cover, all breathers, back cover, and all dark-divider pages render
  full-bleed (bottom bands ≥ 90% ink).
- ✅ 25 logical = 25 physical pages, zero overflow, no blank sheets.
- ✅ The gate (overlap + reference-grounded visual) is CLEAN.
- ✅ All suites pass (renderer + preprocessor).

## Leftover (next task, separate): the fal generator "not working" question.
RESOLVED 2026-08-18: the default fixture build (`build_package.py`) was offline
by default with `--fal` opt-in, so `render.py` on the fixture never generated
new graphics. Flipped the default: **fal runs ON by default** (`--no-fal` =
offline reproducible path), matching the live `/render` path (main.py, which
always calls `generate_assets`). Ran it: **generated 9 assets, 0 failed** —
including 5 NEW case-study scene images (`7/9/12/14/15_case_scene.png`, fresh
fal art bound to the 5 ST-07A pages) + regenerated cover hero / status-quo
scene / atmospheric gradient. Cache is content-addressed on prompt, so
deterministic builds reuse cached generations (no repeat spend).

⚠️ **OPENROUTER KEY LIMIT (user action needed)**: the reference-grounded visual
gate now fails with `HTTP 402` — the `OPENROUTER_API_KEY` in
`research/preprocessor/.env` has hit its usage/credit limit (requested 65536
tokens, only 63426 affordable). The gate correctly fails CLOSED (never silently
passes). The deck is structurally clean (overlap CLEAN, 25 logical = 25
physical, real content); to run the vision gate, raise the key's limit or add
credits at https://openrouter.ai/settings/keys, then re-run
`cd research/v7-renderer && source .venv/bin/activate && python render.py --fast`.

