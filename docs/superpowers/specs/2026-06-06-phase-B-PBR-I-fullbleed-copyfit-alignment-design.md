# PBR-I — Full-bleed (digital) + Copy-distribution + Per-page Alignment — Design

**Date:** 2026-06-06 · **Status:** spec (gap-audited inline, §6) → build
**Why:** the three structural complaints from the user's 2026-06-06 visual review, which apply to *every content page* (highest leverage to Richard-quality):
1. **Copy is "jagged… enclosed and tight"** — cramped blocks with large empty bands (p2 status-quo void; p8 mid-gap). The area isn't used to distribute the writing.
2. **Background not full-bleed** — the ground sits inside the @page margins (white border); the user wants it edge-to-edge for the **digital** variant.
3. **Alignment issues inside pages** — baselines/column-edges/blocks not tight at canon type.

**Architecture rule (user-set, binding):** preprocessor = DATA + space-layout SCHEMATIC + copy-fit budgets + ASSETS; **renderer = beautiful PLACEMENT.** Layer-3 splits **digital** (full-bleed) vs **print** (CMYK + bleed marks).

---

## 1. Goal
Make every content page read **Richard-tight**: copy distributed to fill its region (no cramped blocks, no dead voids), the brand ground **full-bleed edge-to-edge** in the digital variant, and per-page elements aligned to the grid — **without** regressing the 21-page budget, the 201-green suite, canon hierarchy, or readability.

Non-goals: a new content pipeline (we work with the copy we have + copy-fit budgets); print-variant CMYK (Layer-3, later); photoreal imagery (Phase C).

---

## 2. The three sub-parts (independent; sequence A→B→C)

### A. Full-bleed ground (digital variant) — RENDERER, contained, visible first
Today: `[data-ground-mode] .page { background-image }` paints the ground in the **content box** (within @page 16/14/20/18mm margins) → a white border frames it.
**Change (digital variant):** route content pages to the existing suppressed **named `bleed` @page** (margin:0 — the same technique ST-01/31 already use), and **re-inset the content** via padding on a new inner wrapper so the body keeps its margins while the **ground paints to the sheet edge**. The running header band + folio move into the padded inner wrapper (or are drawn as bleed-aware margin boxes).
- Gated on a **`variant=digital`** flag (default for now; the print variant keeps the margined ground). This is the digital/print fork the user described — implemented as a render-time switch so Layer-3 can request either.
- Verify: ground reaches all four edges; header/folio still present + aligned; no content clipped at the bleed edge; page count unchanged.

### B. Copy-distribution / anti-cramp — PREPROCESSOR schematic + RENDERER fill
Two coordinated moves:
- **Preprocessor (schematic + copy-fit budgets):** for each pattern, emit (i) the **region schematic** (which regions exist + their target proportion of the content box) and (ii) a **copy-fit budget** per region (min/target/max chars) so the copy is sized to fill — neither starved (void) nor over-stuffed (cramp/overflow). Where the supplied copy is too short for a region, **flag it** (don't fabricate); where too long, flag for trim. This is the "complete preprocessor" half the user asked for.
- **Renderer (fill):** make the per-pattern regions **flex to consume the content box** instead of sitting at a fixed height with a dead band below. Concretely, the worst offenders first — ST-09 (status quo: two tight columns + void), ST-14, ST-02, and the ST-07B mid-gap — get their body/region containers set to distribute (grow line-height/leading within a canon band, or grow the anchor panel up to meet short copy, or pull the next element up) so the page is filled by intentional distribution, not a void.
- Verify on pixels: each touched page **fills** with no cramped block AND no dead band; canon type tiers intact; the dead-space metric (made ground-aware — see §6 gap #4) drops below threshold *honestly*.

### C. Per-page alignment audit — RENDERER
A systematic pass over each page at canon type: header band baseline, body column left edges, stat-block alignment, panel edges, folio position. Fix misalignments with `.st-XX`-scoped CSS (no global shifts). Driven by viewing each rendered page against a grid overlay.

---

## 3. Approach / sequencing
A (full-bleed) first — contained + immediately visible (calibrate the digital look with the user, like the glass prototype). Then B (copy-distribution) — the meatiest, per-pattern, highest payoff. Then C (alignment) — the polish pass. Each: brand-agnostic, token/scoped, verify on pixels + suites + page-budget after every change.

## 4. Constraints (hard)
- 21-page budget held (no new overflow); canon hierarchy intact; brand-agnostic (no client literals); graceful (a brand without a generated ground still renders cleanly, just not full-bleed-textured).
- Two venvs / DYLD / NO git. Re-bake fixture from preprocessor venv when the package schema changes (copy-fit budgets).

## 5. Testing & verification bar
- Full-bleed: a test asserts content pages (digital variant) route to the bleed page + the ground reaches the edges; pixel-verify edges + header/folio.
- Copy-distribution: render the worst-offender pages → no dead band (ground-aware metric) AND no cramp; pixel sign-off vs Richard; page count == 21.
- Alignment: pixel audit per page; both suites green.

## 6. Adversarial gap-audit (folded BEFORE build)

| # | sev | gap | resolution |
|---|---|---|---|
| 1 | CRIT | Full-bleed via margin:0 page **breaks the running header band + folio** (they live in @page margin boxes that vanish at margin:0) → pages lose chrome. | Move the header/folio INTO the padded inner wrapper for the digital variant (drawn in-flow, not as margin boxes), OR keep them as bleed-aware margin boxes. Verify chrome present on every full-bleed content page BEFORE propagating. |
| 2 | CRIT | Full-bleed re-inset could shift pagination → page-count regression (like the stat-wrap bug this session). | After EACH page-type conversion, assert `fitz` count == 21 + no new overflow. Convert one page type, verify, then the next — never all at once. |
| 3 | HIGH | Copy-distribution "grow to fill" can re-introduce **overflow** (growing elements push past the box) or look stretched/airy. | Distribute within a **canon band** (leading/spacing has min+max); never exceed the box; prefer growing an ANCHOR panel up to meet short copy (the fill-variant pattern) over stretching body leading. Pixel sign-off: dense ≠ stretched. |
| 4 | HIGH | The dead-space **metric is confounded by the light ground** (counts it as empty — caused this session's xfails). Copy-distribution "success" can't be measured against it as-is. | Make the metric **ground-aware** (ignore uniform LIGHT brand ground as not-dead) FIRST, or measure distribution by content-coverage, not white-runs. Until then, **pixel sign-off is the bar**, not the metric; un-xfail the dead-space tests only once the metric is fixed. |
| 5 | HIGH | Copy-fit budgets are a **package-schema change** → re-bake fixture + may shift `test_resolved_package_contract` golden + render tests. | Treat like the PBR-E re-bake: update the golden ON PURPOSE (diff = only the new schematic/budget fields), update affected tests, verify both suites. |
| 6 | MED | "Digital variant" flag has no consumer yet (Layer-3 unbuilt) → risk of a dead flag. | Implement the flag as a render-time parameter with a sensible default (digital) NOW; Layer-3 wires print later. Document it; a test exercises both branches so it's not dead. |
| 7 | MED | Full-bleed ground behind text at the page EDGE could reduce contrast near margins. | The ground is the WHISPER texture (luminance ≥235) — safe; verify contrast at the edges; body copy stays in the inset wrapper (never at the extreme edge). |
| 8 | MED | Per-page alignment fixes risk global drift if not scoped. | All alignment fixes `.st-XX`-scoped; re-run the full deck after each to confirm no other page moved. |
| 9 | LOW | Three sub-parts in one item risk a stall. | Independent + sequenced A→B→C; each ships green before the next; B is itself per-pattern (one offender at a time). |

**Net:** PBR-I is the highest-leverage remaining visual work (every page; the user's own three complaints) but also the most structural. The two CRITs (header/folio under margin:0; pagination shifts) and the metric-confound (gap #4) are the real traps — all caught here, all guarded by per-page page-count assertions + pixel sign-off (the metric is NOT trusted until made ground-aware). Build A→B→C, one page type at a time, verifying on pixels + page budget at each step.
