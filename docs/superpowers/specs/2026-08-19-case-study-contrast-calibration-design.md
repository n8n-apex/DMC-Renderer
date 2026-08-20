# Case-Study Contrast Calibration — Design (2026-08-19)

**Approved approach: A + B (both, ensure everything is covered).**

## The defect (verified by LM Studio audit of p10/12/15/17/18)

The case-study pages render as **dark text on dark background** — the narrative,
section headers and stats are all low-contrast / illegible. Root cause: a
footer-bleed fix added `background-color: var(--color-ink)` to the whole
`.page.tp-rail` section, which painted the ENTIRE sheet dark navy INCLUDING the
left 60% cream field that is designed to be light. Dark-ink narrative text on a
dark navy ground = invisible. The right rail's dark-on-dark is the same class
(stats in a dark accent tone reading muddy on the navy rail).

## Part A — Restore the two-field anatomy (renderer CSS)

The case study (a4_case_study) is DESIGNED with two fields:
- **Left cream narrative field (~60%)**: light surface ground + dark-ink text
  (headline, sections, lede, devices).
- **Right dark rail (~40%)**: navy ink ground + on-dark text (numeral, person,
  stats, quote).

Changes:
1. `assembler.py` — remove `background-color: var(--color-ink)` from
   `.page.tp-rail` (the whole-page ink paint that broke the left field).
2. `a4_case_study.css` — `.cs4-main` gets an EXPLICIT light ground
   (`var(--color-surface)`) so the left field is guaranteed light regardless of
   any section-level bleed hack. Verify the right rail `.cs4-rail` keeps its
   ink ground + on-dark text.
3. Teams: header/label/stat colors that must READ on the rail (light on dark).
   `.cs4-stat-value` is-figure already on-dark; verify the stats that landed
   dark-ink (my earlier `--color-ink` change to stat strips) are re-scoped to
   on-dark WITHIN the rail.
4. **Left-field contrast**: the `c-viz-strip__value` / mega-numeral / stat
   devices that sit on the light cream field use dark ink; the rail uses on-dark.
   A per-host scoping keeps each zone contrast.

## Fix B — Global readability tokens (token layer, systemic guard)

Introduce a **readable-foreground guarantee** in the token layer so text never
sits invisible on its panel:

1. `compile_tokens` exposes panel-aware foreground roles:
   - `--color-ink` (near-black) for text ON light grounds.
   - `--color-on-dark` (near-white) for text ON dark grounds.
   - (the existing `--color-accent` is for graphics only: rules, dots, small
     highlights — never full body text on a same-hue ground).
2. A DET contrast **guard** in the audit pipeline: after each render, probe
   every text-bearing element's computed (color, background) and flag any pair
   with contrast below the readable floor (e.g. WCAG-ish threshold on the
   computed tokens). The guard runs in the **region audit** (LM Studio, high
   DPI) AND a deterministic luminance check, so a future regression is caught
   before ship.

## Verification (non-negotiable)

- Every case-study page (p10/12/15/17/18) audited on LM Studio at high DPI:
   the left narrative + right rail both legible (model returns no
   critical contrast issues).
- The whole 25-page deck run through the audit + overlap/visual gates.
- Renderer + preprocessor suites pass.

## Files touched
- `research/v7-renderer/assembler.py` (remove rail-wide ink)
- `research/v7-renderer/styles/treatments/a4_case_study.css` (two-field anatomy,
  explicit light left field, rail on-dark scoping)
- `research/v7-renderer/tokens/compile_tokens.py` (readable-text pairs)
- `research/v7-renderer/audit_regions.py` (+ deterministic contrast probe)
- `research/quality_loop/overlap_detector.py`-style DET (new contrast fact)