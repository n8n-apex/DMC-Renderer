# Template Bank — System Framework Design (DMC "open, browse by context, renderer fills")

> **Status (REV 2):** audit-corrected. Pending final adversarial pass, implementation
> plan, inline build + pixel verification. Owner: whole system.
> **Date:** 2026-08-25 (rev 1: 2026-08-25, corrected after adversarial audit)

---

## 0. Why this exists (the user's requirement, exactly)

> "It should be the entire system in itself... the system needs to open, browse by
> context, and the renderer fills it... a system bank of templates... purely
> judgment-based on how and where they need to be placed, in what context they need
> to be used. The data will be added by the renderer."

The system must own a **browsable-by-context catalog of templates/modules/devices**
(judgment + placement). Pipeline flow: **pre-processor plans (which template for
which page, in what context) → renderer draws (fills that template with the page's
data) → post-processor packages.**

## 1. The corrected current state (audit-verified, not assumption)

**The critical correction: an entire v3 composition system ALREADY EXISTS and is
LIVE in a secondary app, and its schema is the bank we need.** My first-grep
conclusion that `composition_registry` was "dormant" was WRONG.

| System | What it holds | Live? | Deployed? |
|---|---|---|---|
| **Legacy patterns** `patterns/st_XX.py` | per-page render functions | live (bypass pages) | via v2 /render |
| **Treatments** `treatment_*.py` + `templates/treatments/` | ~20 page layouts, 7 built | live | via v2 /render |
| **Devices / viz presets** `components/viz*.jinja` | ~25 atomic data-viz macros | live | via v2 /render |
| **v3 Composition Registry** `composition_registry/` | 10 `CompositionFamily` + **role vocabulary (`cover, outlook, about, status_quo, false_beliefs, case_study, theory, mechanism, trust_proof, summary, objections, collaboration, cta, brand_breather`)** + **per-region capacity/contract** (words, lines, font, aspect) | **LIVE in `dmc-renderer/build_v3.py` + `plan_compositions_v3` + `/render-v3`** | **NOT deployed** (Railway runs `main:app` → `/render` v2 only; `/render-v3` is in `service.py`, not deployed) |

So the true picture: **the richest bank schema (v3) exists but on a non-deployed
route; the deployed executor (v2 treatments+viz) is the live render layer.** The
framework's job is to unify these: **v3 registry = the bank's catalog/metadata;
v2 treatment engine + viz = the executor; `/render` (deployed) = the canonical path.**

Also verified: `treatment_stylist.assign` (v2) ALREADY emits `PageAssignment`
(plan-like: index/slot/st_type/treatment/format/reason) and the apex deck DOES
change when treatments are on (v2 tasks run by default). The "planner" we need is
essentially this `assign()` + the v3 role/capacity metadata, unified.

## 2. The single hierarchy (one vocabulary, three levels)

```
TEMPLATE   = page composition (the sheet). e.g. a4_bi_dashboard, a4_case_study,
             a4_editorial_fill. Carries: name, archetype, supported ROLE(S) (from
             the v3 RoleName), required data contract, format, region grid,
             "best for / avoid when", known failures.
   │  composes
MODULE     = reusable mid-level BLOCK. e.g. dark stat rail, callout, Q&A ladder,
             testimonial wall, step spine, hero band. Carries: name, which
             templates use it, which devices fill it.
   │  fills
DEVICE     = atomic data-viz primitive. e.g. mega_numeral, radial_cluster,
             split_bar, donut, stat_strip, quote, arrow. Carries: name, data
             contract, which modules host it, FT-VV story type (comparison /
             distribution / change / part-to-whole / correlation / flow / ranking).
```

- "Pattern" (legacy `patterns/`) is retired as a NAME: those become the fallback
  executor, or are replaced as templates cover their types.
- Browse-by-context = query the registry by **ROLE** (v3 RoleName) + data contract
  + reference match. This is the judgment.

## 3. The system flow (bank = preprocessor planner → renderer executor)

```
PRE-PROCESSOR  report JSON + client data
   │  ┌──────────────────────────────────────────────┐
   ▼  │  BANK CATALOG (registry over                  │
  PLANNER │   template/module/device, browsable by   │
   per page: ROLE → template → regions → devices →   │   ROLE(contract) )
   emit plan{template_id, regions, device ids, data} │      ▲
   └────────────── plan ──► RENDERER ────────────────┼──────┘
                          (fills template+devices)   │   POST (pack)
```

So: **pre-processor owns the bank + the per-page plan; renderer is the pure
executor.** The existing `treatment_stylist.assign` (v2) + `viz.jinja` +
`treatment_engine.render` ARE the executor; the v3 registry is the catalog.

## 4. What gets BUILT (the vertical slice on the LIVE path)

1. **Bank registry = v3 registry, adopted.** Use `composition_registry.CompositionRegistry`
   + the v3 `RoleName` + `RegionCapacity` as the bank's catalog schema (roles,
   contracts, regions). Seed it with the 7 live treatments + ~25 devices mapped to
   roles/modules + the 10 v3 family metadata as the "context" layer.
2. **Planner = `assign()` unified with the catalog.** Extend `treatment_stylist`
   to produce an explicit `PagePlan` (the existing `PageAssignment`, enriched with
   role from v3 RoleName + chosen devices). This is the "judgment" the user wants,
   exposed as a real plan object, not an internal list.
3. **Renderer adapter (executor).** `treatment_engine.render` stays the executor
   (it already takes `treatment_name`, reads `data.viz`, renders). The plan's device
   list is realized by the preprocessor writing `page.data.viz` (as today) OR a
   thin `render(page, ctx, name, devices)` extension IF needed (audit F3: only if
   the plan must override data.viz at render time - avoid, keep renderer pure).
4. **Browsable catalog surface.** A `catalog()` function + JSON dump the planner AND
   a human can open (browse by ROLE). The planner reads the same catalog. This is the
   "open, browse by context" deliverable.
5. **Make it irreversibly live (audit F6):** for non-bypass pages, the render path
   REQUIRES a plan (raise if missing), no silent legacy fallback. This prevents the
   bank becoming vocabulary #5.

## 5. FT Visual Vocabulary seed (license-clean, MIT)

Adopt its **story taxonomy** as the DEVICE layer's judgment ("which visual for which
story") and its **~60 static template types** as DEVICE candidates - ported (re-skin
to our token flat-on-cream recipe, no FT branding, no gradient/glow per our guard).
BUT the audit's point stands: `viz_compare/viz_transform/viz_proportion` ALREADY
implement the FT-VV core (bars, slope/arrow, donut, ladder). So "porting FT" is
largely **cataloging what already exists under the FT story tags**, plus a few new
devices only when real data appears. Do NOT import FT source JS; import taxonomy +
geometry only.

## 6. Non-goals (v1)

- No new `bank/` namespace parallel to `composition_registry` (audit F1). Land ON it.
- Not porting all 60 FT templates (catalog the existing ~25, add only when data drives).
- Not replacing the deployed v2 executor with v3 (`/render-v3` is not deployed; a
  route unification is a separate migration).
- Not building the post-processor (packaging as-is).

## 7. Verification discipline

Each step: render apex, READ the page on pixels vs reference; guard battery (no
literals / no em dashes / no panel-contrast violations); targeted tests; the bank
catalog must be queryable in tests (browse by role returns sane template set).

## 8. Open decisions (confirm before build)

1. **Executor + route:** build the bank ON the deployed v2 path (`/render` via
   `treatment_stylist` + `viz`) as the executor (recommended), and treat the v3
   registry as catalog metadata; OR flip the deploy to `/render-v3` and bank it
   there (bigger change, touches Railway route + Dockerfile CMD + service.py).
2. **Plan object:** enrich the existing `PageAssignment` into a first-class `PagePlan`
   (recommended, minimal) vs a new planner object in a separate stage.
3. **Catalog surface:** a Python `catalog()` + JSON dump (recommended v1) vs a full
   UI. User said "open" - JSON the planner itself opens.