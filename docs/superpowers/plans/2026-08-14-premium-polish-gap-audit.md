# Premium & Polish Gap Audit — 2026-08-14 (user's remaining issues)

> User verdict after the Director Organism program: "A lot has been fixed. But
> some issues remain." This doc maps EVERY user-reported issue to its code
> location, the root cause, and the fix. It is the single source of truth for
> the ralph program US-301..US-3xx that follows.

## Issue 1 — A3 case-study spreads have hollow bands (p7/9/12/14/15)

**User:** "Pages 7 and 9 contain blank space / negative space. Could have been
filled with a visual element or a couple of visual elements supporting those
sections. That could have been created using the fal API — the fal API hasn't
been used."

**Measured evidence** (left column, 8 vertical bands, ink %):

| Page | b1 | b2 | b3 | b4 | b5 | b6 | b7 | b8 |
|---|---|---|---|---|---|---|---|---|
| p7 | 12.4 | 11.8 | 8.7 | **0.0** | 11.1 | **0.0** | 7.6 | 2.5 |
| p9 | 11.8 | 14.8 | 11.8 | **0.0** | 11.4 | **0.0** | 10.4 | 2.5 |
| p14 | 11.5 | 11.0 | 10.4 | **0.0** | 10.0 | **0.0** | 8.2 | 1.1 |
| p15 | 10.3 | 16.6 | 10.1 | **0.0** | 11.1 | **0.0** | 9.0 | 2.3 |
| p12 | 11.4 | 55.0 | 81.5 | 48.1 | 20.6 | 12.6 | 10.4 | 2.5 |

Bands 4 and 6 are **completely empty** on 4 of 5 spreads — two horizontal voids
in the left column between the narrative sections. p12 (Frese) is dense only
because it has more copy.

**Root cause:** `styles/st_07a.css` — `.st-07a.format-a3 .csh-narr { flex: 1;
justify-content: space-between }` spreads the 2–3 narrative sections across
261mm with **nothing between them**. The A3 canvas is 2× the A4 canvas but
carries the same content volume; the sections get spaced apart, leaving voids.
The renderer has no *supporting visual* device for these gaps.

**Fix (preprocessor + renderer + fal):**
1. **New renderer device**: `.csh-scene` — a supporting full-bleed visual band
   (rounded image frame, brand lift) that can sit *between* narrative sections
   on the A3 spread. Rendered only when the page resolves a
   `data.case_scene` / `scene_uri` slot. Brand-agnostic, token-only.
2. **fal generation**: generate one brand-toned *abstract/domain scene* per
   case study (navy/cyan network, flow, system metaphor — never a face, never
   fake data) via `fal_generate_image` (model `fal-ai/nano-banana-pro`, cache
   `/tmp/fal_cache`), drop into `fixtures/apex/assets/` as `csN_scene.png`,
   route via the slot registry (`case_scene` slot) in `build_package.py`.
3. **Layout**: `.csh-narr` gets `gap` instead of `space-between` when a scene
   is present; the scene absorbs one of the void bands (place between
   `ausgangsproblem` and `loesung`). When NO scene resolves (live clients
   without fal), the current space-between distribution stays — graceful.

## Issue 2 — p18 (ST-FAZIT): text wall / cramped

**User:** "Page 18 has a lot of text that should have been fixed. There should
be some breather."

**Measured:** p18 body = 1025 chars of prose, 6 figures crammed into one
paragraph ("25-30% ... 77% ... 58% ... 61% ... 40% ... 60%"), then the these
statement + cost block + dark island + CTA. Quadrants 41.9/42.4/37.9/35.5 —
the densest interior page.

**Root cause:** `templates/st_fazit.html.jinja` fill variant stacks
body → these → viz island → cost → CTA with `var(--space-4)` gaps only;
`styles/st_fazit.css` `.fz-body { font-size: var(--type-body);
line-height: 1.42; text-align: justify; hyphens: auto }` — a 1025-char
justified block with six inline figures reads as a wall.

**Fix:**
1. **Preprocessor**: split the ST-FAZIT body into short paragraphs at the
   figure boundaries (each figure gets its own sentence/paragraph — a
   "breather" structure, no copy invented, no figure dropped).
2. **Renderer**: `.fz-body--fill` gets a larger line-height (1.55) + paragraph
   spacing `var(--space-3)`, and the block narrows to `max-width: 168mm`
   (leave air on both sides); the `fz-viz` island gets `margin-top` breathing
   instead of hugging the these statement.
3. The 58%/61% radial_cluster already carries 2 of the 6 figures; the other 4
   stay in the prose (they're cited figures — moving them into devices would
   need real device space; the paragraph split is the honest fix).

## Issue 3 — Ring/cluster center figures are NOT centered (SVG text baseline)

**User:** "p9: '6 von 6' written inside the circle is not properly placed; the
'30 bis 50 %' thingy is also not perfectly placed. p18: 58% and 61% are not
perfectly aligned within the box."

**Root cause (ALL four components):** SVG `<text>` uses `text-anchor="middle"`
for horizontal centering but the **vertical position is baseline-anchored** —
`y="50"` / `y="64"` / `y="66"` / `y="92"` places the text *baseline* at that y,
not the glyph center. A figure like "58%" (ascenders + descender-bearing %)
sits visibly ABOVE the circle's visual center.

Affected locations (all with `text-anchor="middle"` but no
`dominant-baseline`):
- `components/viz_proportion.jinja:27` — donut center `y="66"` (circle cy=60)
- `components/viz_proportion.jinja:78` — gauge center `y="92"`
- `components/viz_proportion.jinja:108` — radial_cluster center `y="50"` (cy=45) ← p18's 58%/61%, p2's 30/60/30-bis-50
- `components/viz_transform.jinja:143` — completion_ring center `y="64"` (cy=60) ← p9's "6 von 6"
- `templates/st_07a.html.jinja:254` — csh-donut figure (flex-centered span, but `fitfs(96, 30)` caps font-size; may also need a `line-height` guard)

**Fix:** add `dominant-baseline="central"` (Chromium supports it; weasy
ignores gracefully) and set `y` to the circle's cy (45/60/66/100 → 45/60/60/100)
so the glyph center lands on the circle center. For the csh-donut flex span,
keep inset-0 flex centering but add `line-height: 1` (already) + verify the
fitfs cap with the larger "30 bis 50 %" string.

## Issue 4 — "Reparative treatments" text (user's example of polish)

**User:** "I see 'reparative treatments'. That's okay, not nitty-gritties, but
that is where premium and polishing lies."

**Finding:** NOT in the apex deck — grep over `report.html`, the fixture JSON,
and the print PDF text layer finds no "reparativ*". The user may be recalling
it from another deck/context. Action: verify once more during the program; if
truly absent, note it as a non-issue in the ledger (honesty rule — do not
"fix" something that isn't there).

## Issue 5 — n8n callability (user question)

**Answer: YES, the system is callable by n8n.**
- Workflow: `docs/n8n/workflows/DMC-Ingestion-Pipeline-v3-review.json`
  ("Build Renderer Envelope v3 (review)" node) POSTs to
  `https://dmc-renderer.up.railway.app/render-v3` (or `$env.RENDERER_URL`).
- Endpoints (service.py): `/health`, `/health/v3`, `/render`, `/render-v3`
  (shared-secret auth via `RENDERER_SHARED_SECRET`).
- Run: uvicorn on port 8099 (`docs/n8n/deployment-checklist-v3.md`).
- The node computes `clientSlug` + `recordId` but never merged them into
  `payload.meta` — **fixed in US-206** (derivation in adapter_v3 + build_live).
- Contract handshake: workflow_contract_version 3.2.1 + 5 artifact sha256s
  (409 on mismatch).

## The ralph program that follows (US-301..US-3xx)

1. **US-301** — SVG center-text vertical centering (`dominant-baseline="central"`
   + y=cy) across donut/gauge/cluster/ring/csh-donut; regression test that the
   emitted SVG carries the attribute.
2. **US-302** — `.csh-scene` supporting-visual device (renderer): template
   block between `ausgangsproblem`/`loesung` + scoped CSS (rounded frame,
   brand lift); graceful absent.
3. **US-303** — fal generation + slot routing for the 5 case-study scenes into
   the apex fixture (brand-toned abstract scenes, no faces, no data).
4. **US-304** — ST-FAZIT breather: preprocessor paragraph split + renderer
   spacing (line-height 1.55, wider paragraph gap, island margin).
5. **US-305** — re-bake + full render + quantitative verification (void-band
   scan shows no 0.0% bands on A3 left columns; p18 quadrant balance) + all
   suites + G27 registry entry + ledger.
6. **US-306** — FINAL RENDER (last step) — hand the deck to the user.
