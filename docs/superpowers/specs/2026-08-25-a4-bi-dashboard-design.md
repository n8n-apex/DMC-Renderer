# a4_bi_dashboard — "Power-BI" 50/50 Data-Infographic Spread — Design / Spec

> **Status:** Proposed — pending adversarial gap-audit + a full Ralph/QA loop
> before any code is written. **Date:** 2026-08-25
> **Component:** `research/v7-renderer/` (Layer 2 chassis) + `fixtures/apex/viz_curation.py`.
> **Predecessors:** `docs/VISUAL-APPEAL-MASTER-BACKLOG.md` A5 ("Author
> a4_bi_dashboard — the true Power-BI 50/50 data-infographic spread ... the ONLY
> dashboard-archetype treatment ... currently a metadata-only STUB")
> + the treatment-system build plan (`2026-06-18-treatment-system-build.md`)
> + the data-viz preset library design
> (`docs/superpowers/specs/2026-06-14-data-viz-preset-library-design.md`).

---

## 0. Why this exists (the user's ask, precisely)

> "We need a system bank ... pre-made templates ... the data is added by the
> renderer. It should be judgment-based on how and where they need to be placed,
> in what context they need to be used. ... Let's build a4_bi_dashboard."

The deck already has **device** presets (`ba_bars`, `transform_arrow`,
`completion_ring`, `mega_numeral`, `radial_cluster`, `donut`, `gauge`,
`money_bar`, `split_bar`, `icon_array`, `stat_strip`, `ranked_bars`,
`phase_timeline`, `step_cascade` — dispatched by `components/viz.jinja`,
styled in `styles/viz.css`). What it lacks is a **composition-level template** —
a *designed spread* placing multiple devices + narrative + stats into a fixed,
tasteful canvas, where the renderer fills in the data. `a4_bi_dashboard` is that
template and is currently a **metadata-only stub**.

## 1. Facts verified in code (not assumptions)

| Fact | Source |
|---|---|
| Catalog: `required_fields=("viz",)`, archetype `dashboard`, `formats={a3,a4}` | `treatment_catalog.py:96` |
| Candidate lists already name it: ST-02 FIRST, ST-09 middle, ST-07A last | `treatment_stylist.py` handler |
| A treatment is never assigned until `treatment_is_built()` passes — the stub is inert today | `treatment_engine.py:996` |
| Assignment is gated: a physical page must be non-bypass + its adapted `td.viz` must be non-empty | `treatment_engine.py` `+_generic` (Std5) |
| **ST-09 continuations are exempt from the continuation bypass**; ST-02 continuations ARE bypassed | `treatment_stylist.py:490` |
| In the current apex package, the only page that is (a) not a bypass-continuation AND (b) carries a non-empty `data.viz` AND (c) has real narrative is the **ST-09 context page** (mega_numeral "50 %" + status-quo intro + symptoms) | `resolved_package.json` |
| A faithful "dashboard" needs ≥2 devices; today each apex page carries exactly ONE viz spec | verified `resolved_package.json` |

## 2. Host decision (judgment, explicit)

**ADVERSARIAL FINDING (2026-08-25 audit — this REPLACES the assumption below):**
Richard's actual "data spread" is NOT a grid of Power-BI cards. Reading the apex
reference deck (same-client authority) via the local VLM:
- `apex p3`: a **hybrid**: full-width hero image top, then a TWO-COLUMN body —
  LEFT editorial narrative (60%) + RIGHT dark-navy STAT PANEL (40%) with a
  VERTICAL STACK of big numerals ("100+", "250.000", "30%") under labels, plus
  a logo/media band at bottom.
- `niklas p2`: two-column editorial 50/50 — left narrative, right parallel prose
  + a ZIELGRUPPE box + author metrics. No card grid.
- `apex p4/p6`: two-column editorial (symptoms/myths + a navy callout).

So the true anatomy of `a4_bi_dashboard` is: a TWO-COLUMN spread — LEFT
editorial narrative + RIGHT dark-navy STAT STACK (big numerals in a panel, the
`stat_strip`/`radial_cluster`/`ranked_bars`/`mega_numeral` devices, not a card
grid), with optional hero image top. This reuses the already-proven dark-rail
language of a4_case_study and matches the reference — NOT a dashboard card-grid.

**Recommended host (v1): ST-09 context.** It is exempt from the continuation
bypass, carries grounded viz (50 % + 25–30 % copy — verified 2 real figures),
and its narrative reads exactly as the LEFT column should. Evidence (no viz)
stays on its current fill path.

**Deliberate non-goals for v1:**
- Do NOT un-bypass ST-02 to force it here (separate stylist decision).
- Do NOT fabricate figures — single-spec page renders a single-device panel.
- Do NOT build a card-grid dashboard (proven wrong by the audit).

## 3. Two-layer build (audit-corrected)

**Layer A — renderer treatment template + css + tests (the re-usable bank item).**
- `templates/treatments/a4_bi_dashboard.html.jinja` — a definitely-full-height
  flex column matching the reference anatomy:
  - OPTIONAL `hero` strip (when `td.image`).
  - HEAD row: eyebrow + two-tone headline + lede (the narrative intro).
  - `grid` = the reference split: LEFT `td.body`/`td.sections` narrative column;
    RIGHT a DARK PANEL (the existing `--color-ink` + `--color-on-dark` rail
    language) holding the page's `td.viz` devices VERTICALLY (stat_strip /
    mega_numeral / radial_cluster / ranked_bars — whatever the page carries),
    plus `td.stats` as smaller numerals where no viz device exists.
  - OPTIONAL foot: the cta_url band or the credentials/logo line (from `td.credentials`).
  Token-only, graceful-omits, flat/sharp; every device via the existing
  `viz.jinja` dispatch. A single-spec page renders ONE device centered in the
  panel — honest, not a fake grid.
- `styles/treatments/a4_bi_dashboard.css` — the 60/40 two-column geometry,
  the dark-panel stat stack, the hero strip, the footer band. Reuses the
  dark-rail CSS recipes already proven in `a4_case_study` so it matches the
  deck's material language (marble/glass ground, accent hairline, on-dark).
- Tests: (a) ST-09-context-like fake page with ≥1 viz → treatment assigned +
  devices render; (b) a page WITHOUT viz → never selected; (c) the right panel
  contains the devices and the left contains narrative body when both present;
  (d) guards pass; (e) the `required_fields=("viz",)` contract unchanged.

**Layer B — context curation (`fixtures/apex/viz_rich.py`).**
Adds a multi-spec `viz` to ST-09 context ONLY when ≥2 grounded figures exist in
the page's owned copy. Reuses `_figure_grounded` (imported — never duplicated).
Figures STRICTLY verbatim (the two verified: 50 % burn-out figure + 25–30 %
Betriebskosten). If fewer figures are grounded, enrichment is skipped → the
page renders single-device (honest, premium).

## 3. Open decision for the user (must confirm before build)

1. **Host scope:** only ST-09 context (recommended) vs also un-bypass ST-02.
2. **Depth:** Layer A only (honest single-device today, template+eats next deck)
   vs also Layer B (rich 2–3 device on apex).
3. **Format:** A4 default; allow a3 only when the stylist promotes AND viz count
   ≥3 (wide canvas).

## 4. Verification discipline

Every edit → re-render + **READ `output/report-pNN.png` on pixels**, judging the
WHOLE page vs the reference (never devices appear); guard battery
(`test_no_literals_in_architecture.py`, `test_no_client_name_in_logic.py`);
no full pytest suite (user mandate); a targeted QA loop before ship.