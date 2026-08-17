# Phase B (part 1) — Reflow to 20 pages — Design

**Date:** 2026-06-05 · **Status:** spec for gap-audit (then build)
**Scope:** Renderer per-pattern layouts (`research/v7-renderer/styles/st_*.css` + 2 templates) + one shared token + flag genuine copy-fit for the preprocessor.
**Why:** Phase A raised type to canon → the apex deck overflows to **25 physical pages** (5 spill: ST-05/09/14/07A/06). The *theme* is right; per-pattern layouts were tuned for the old smaller type. This restores a clean **20-page** deck.

---

## 1. Goal
Make the 5 overflowing patterns fit one A4 content box (**261mm**) under canon type, **without** stripping content or lowering canon hierarchy (headlines stay H1 32 / display-xl 40; stats stay their tier). Where overflow is genuinely a copy-length problem (not spacing), **flag it** (overflow validator) and route the real fix to the preprocessor — never silently shrink below canon or clip.

## 2. Approach (decision)
**Surgical, per-pattern, `.st-XX`-scoped CSS spacing tightening** — the approach all 5 diagnoses converged on. Rationale: lowest-risk, preserves canon hierarchy, touches no shared component globally (any shared-component height change is applied as a `.st-XX`-scoped override, not a global edit), and aligns with canon ("magazine-dense, structured whitespace around an anchor"). Plus one structural change (ST-06 flow-strip) and one new token (`--type-lede`).
- **NOT** the density-axis-as-fit-knob route (that is the quality loop's Conductor job — Phase E). Phase B sets a baseline that fits synchronously.
- **NOT** shrinking headlines/stats below canon tiers.

## 3. Per-pattern changes (from the 5 diagnoses)

### 3.1 ST-05 (About) — `styles/st_05.css` (~24mm recovered; needs ~17mm)
- `.ab-header` margin-bottom `--space-3`→`--space-2`; `.ab-lead` padding top/bottom `--space-3`→`--space-2`; `.ab-grid` margin `--space-3`→`--space-2`.
- `.ab-portrait` margin-bottom `--space-4`→`--space-3`; `.ab-stats` margin-bottom `--space-4`→`--space-3`.
- stat-cell padding `--space-2 0`→`--space-1 0` (×3 cells).
- proof gallery tile height: scoped override `.st-05 .ab-proof .c-proof-gallery__item { height: 28mm }` (was 37mm global — overridden ONLY for st-05).
- `.ab-proof` margin `--space-3`→`--space-2`.

### 3.2 ST-09 (Status Quo) — `styles/st_09.css` (~18mm; needs ~17mm)
- scene banner `min-height`/`.c-media`/`.c-media-img` height `32mm`→`22mm` (still a cinematic band).
- `.sq-cell` bottom padding `--space-2`→`--space-1`.
- callout: scoped `.st-09 .sq-callout .c-callout-panel { padding: var(--space-3) }` (was `--space-4` global); `.sq-callout` margin-top `--space-2`→`--space-1`.

### 3.3 ST-14 (False Beliefs) — `styles/st_14.css` (~21mm; needs ~15mm)
- opener: scoped `.st-14 .fb-opener .c-color-block { padding: var(--space-4) var(--space-5) }` (top/bottom 8→6mm); `.fb-opener` margin `--space-3`→`--space-2`.
- intro → use new `--type-lede` (12pt) instead of `--type-h3` (14pt); line-height 1.32→1.24; margin `--space-4`→`--space-3`.
- item separators padding+margin `--space-3`→`--space-2` (both).
- scoped micro-margins: `.c-numbered-block__title` `--space-2`→`--space-1`; `.c-numbered-block__reality` + `__source` margin-top `--space-2`→`--space-1` (all `.st-14`-scoped).

### 3.4 ST-06 (Mechanism) — `styles/st_06.css` + `templates/st_06.html.jinja` (~24mm CSS + ~27mm structural)
- CSS: step-card padding `--space-2`→`--space-1`; cell bottom margin `--space-1`→`1mm`; card body line-height 1.25→1.2; scoped `.st-06 .mx-recap .c-dark-recap { padding: var(--space-3) var(--space-5) }`; `.mx-steps`/`.mx-flow` margin-bottom→0; intro lede line-height 1.34→1.28.
- **STRUCTURAL: suppress the horizontal flow-strip when `steps|length >= 5`** (template conditional in `st_06.html.jinja`). The 6 labeled step cards ARE the flow; the strip is redundant overhead. Editorial upgrade, recovers ~27mm. (When <5 steps, keep the strip.)

### 3.5 ST-07A (Case Study, fill) — `styles/st_07a.css` + `templates/st_07a.html.jinja` (~19mm; needs ~42mm on Hanisch)
- fill-scoped spacing: `.cs-main--fill .c-section-label` margin `--space-3`→`--space-2`; `.cs-main--fill .cs-section` margin `--space-2`→`--space-1`; `.cs-header--fill` margin `--space-3`→`--space-2`; kicker/headline margins →`--space-1`.
- fill lede: add `cs-lede--fill` modifier (template) → `font-size: var(--type-cta)` (11.5pt) instead of `--type-h3` (14pt).
- **HONEST RESIDUAL (~23mm) = COPY length** (Hanisch is the only CS with the `Ziel` section populated + the longest lede). CSS cannot fix this without clipping. → **§5 copy-fit.**

## 4. Shared token
Add `--type-lede` = **12pt** to `base.tokens.json` (between body 10.5 and h3 14), emitted by `compile_tokens`. Used by ST-14 intro (and available to ST-06/others). Avoids the `12pt` literal the diagnoses flagged (token-purity / brand-agnostic).

## 5. Genuine copy-fit (route to preprocessor — the "complete preprocessor" half)
Spacing cannot fix content that is simply too long. The diagnoses surfaced real copy-volume limits the **preprocessor** must guard (validators/copy-fit, the CF.1 infra already exists):
- **ST-07A Hanisch:** the `Ziel` section + long lede push ~23mm over even after reflow. Fix options (preprocessor): trim/merge the `Ziel` section, or shorten lede/body to a per-section budget. Until then the overflow validator **flags** it (never clip).
- **Content caps** (flag, don't fabricate): ST-05 ≤3 stats + ≤3–4 credibility points + ≤3 proof photos; ST-09/ST-14 headline + lede length caps; ST-14 reality-body char budget.
These are a **follow-on preprocessor task within Phase B/C**, NOT part of the CSS reflow. Phase-B-reflow's renderer job: get 4/5 patterns fitting + ST-07A as close as CSS allows + the validator honestly flagging the residual.

## 6. Constraints
- Brand-agnostic (no client/hex/font literal); scoped CSS only; shared-component height changes applied ONLY as `.st-XX`-scoped overrides.
- Canon hierarchy intact (no headline/stat below tier; no silent font-shrink to fit beyond the existing st_07a `_is_long_value` stat path).
- **Verify on pixels:** render the full real apex deck → **page count == 20** (or, if ST-07A Hanisch genuinely can't fit by CSS, an explicit flagged exception documented + routed to preprocessor); view cover + the 5 reflowed pages vs Richard; both suites green.
- The 5 xfailed dead-space fill tests + the visual-regression baseline get re-evaluated/re-baked AFTER reflow restores 20 pages + human sign-off.
- Renderer venv + `DYLD_FALLBACK_LIBRARY_PATH`; NO git.

## 7. Testing
- Per-pattern: a render-and-measure test (the overflow validator) confirms each reflowed page no longer overflows (where CSS-fixable).
- Full deck render → assert page count 20 (modulo the flagged ST-07A copy-fit exception).
- Token: `--type-lede` emitted at 12pt.
- View pixels (the bar): the 5 pages still look canon-rich (dense ≠ cramped), headlines/stats at tier.
- Both suites green; visual-regression re-bake last, after sign-off.

## 8. Risks
- Tightening reads "cramped" rather than "dense" → mitigated by keeping canon hierarchy + verifying on pixels (canon decks ARE dense).
- ST-06 flow-strip suppression is a visible composition change → it's an editorial upgrade (cards are the flow); verify on pixels; reversible.
- ST-07A Hanisch still spills → honestly flagged; real fix is preprocessor copy-fit (§5). Do NOT clip or sub-canon-shrink to force-fit.
- Shared `proof-gallery`/`callout`/`color-block`/`dark-recap` height overrides must stay `.st-XX`-scoped so other patterns are unaffected. (Gap-audit CONFIRMED safe: each of these shared components is imported by ONLY its owner pattern.)

## 9. Gap-audit resolutions (2026-06-05, folded before build)

| # | sev | gap | resolution |
|---|---|---|---|
| 1 | CRIT | ST-06 flow-strip suppression breaks `test_st06_rebuild_composes_step_cards_flow_and_dark_recap` (asserts `c-hflow`/`c-hflow__arrow` present on the 6-step apex fixture) | **Build MUST update that test**: assert flow ABSENT when steps≥5, PRESENT when steps≤4; fix the "signature device" docstring. |
| 2 | HIGH | ST-07A fill lede used `--type-cta` (11.5pt) — 1pt over body 10.5 = no hierarchy + semantic pollution | **Use `--type-lede` (12pt) for BOTH the ST-07A fill lede AND the ST-14 intro** (one lede token, consistent). §3.3/§3.5 updated. |
| 3 | HIGH | `--type-lede` is a hard dependency; CSS using it silently fails if token absent | **Build order: token task FIRST** (add `--type-lede`=12pt to base.tokens.json + regen), THEN the CSS tasks. |
| 4 | HIGH | ST-09 fit is marginal (~1mm headroom) | Add `.st-09 .sq-header { margin-bottom: var(--space-2) }` (+1mm → ~2mm headroom); banner 22mm is a pixel sign-off (fallback 26mm if it loses anchor presence). |
| 5 | MED | ST-05 stat-cell padding →2mm risks an airless stat rail | **Hold stat-cell padding at `--space-2` (3mm)** — the other ST-05 changes already recover >needed; pixel-verify. |
| 6 | MED | ST-06 flow-strip framed as "editorial upgrade" (it isn't — it serves the scanner, 50/50 principle); CSS figure ~17mm not ~24mm | Reframe as a **space-fit necessity requiring a 90-second-browse pixel sign-off**; structural suppression is load-bearing (CSS alone ~17mm < 27mm needed). |
| 7 | MED | dead-space-test re-bake scope overbroad | Only the **ST-07A** dead-space + visual baseline are adjacent to this reflow; ST-07B/22/FAZIT fill tests stay xfailed (out of reflow scope → Phase E). |
| 8 | MED | §5 content caps are qualitative | Concrete preprocessor caps (follow-on): ST-05 ≤3 stats / ≤4 credibility / ≤3 proof; ST-09 headline ≤~90 chars; ST-14 title ≤60 / myth ≤85 / reality-bodies ≤~1150 chars total; ST-07A per-section + lede budgets. |
| 9 | LOW | non-Hanisch ST-07A slots (7/9/12/14) not explicitly confirmed fitting at canon type | **Verify at the §7 full-deck render** that only the 5 named patterns overflowed (confirm the other 4 case studies fit). |

**Net:** the scoped-CSS approach is sound; build with these folded. The genuine residual (ST-07A Hanisch ~23mm) is honestly a copy-fit/preprocessor item, not forced by clipping or sub-canon shrink.
