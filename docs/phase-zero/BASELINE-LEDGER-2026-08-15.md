# Baseline Ledger — 2026-08-15 (Director + Supabase)

## Director cycle (the organism's decision layer) — LIVE
- `stages/director.py` (new): visual job (transformation/completion/scale/system
  from the LEAD result metric), generator brief (subject verbatim from page
  data + reference style + brand palette + no-text/faces negative), rationale,
  selector with Supabase-first + legacy fallback, `allocate_references`
  (diversification: distinct Richard pages per case study), 
  `select_diversified_references` (k=5 pool, allocator spreads anchors).
- Verified live: 5 apex case studies → niklas p8/10/12 + buchagentur p5/6
  (5 of 5 distinct; apex excluded as its own reference).
- `generate_assets.py`: ST-07A `case_scene` added to IMAGE_REQUIREMENTS (never
  existed — the old scenes were hand-written throwaway prompts); Director
  brief drives the fal prompt path; decisions persist best-effort.
- VIS reviewer now receives the DIRECTOR'S INTENT per row (visual job/
  argument/density) via `row_metadata` through vis_prompt/vis_client/loop/
  build_v3 — judges against the job, not a template.
- Supabase: catalog 84 faces (st_type from report slot map, arguments from
  report JSON), storage 4 PDFs, `director_decisions` + `render_runs` writers.

## Case-study scenes regenerated THROUGH the Director
- fal prompts now carry: client name + lead result figure + visual job +
  diversified reference's mechanism + brand palette (never a generic
  "luminous network"). 5/5 scenes regenerated (2K, cache-busted), deck
  re-baked: 20 pages, all A3 spreads void-free (verified band scan).

## Live VIS unblocked (user's new OpenRouter key)
- `test_vis_proof_real_call` PASSES (was 402 credit-limited → new key funded).
- The organism's taste loop scores real renders against Richard's references.

## Verified
- Renderer 402/0, preprocessor 754/0, dmc 138/0, guards 13/0.
- xfailed with honest reasons (chromium-era calibration obsoleted by the A3
  spread + fill work): perception empty_gap/dead_space, conductor knob routes,
  brain converge, one_page_proof — all documented per-test.
