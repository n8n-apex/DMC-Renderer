# Renderer contract audit (2026-07-16)

Per-section audit of the German report pipeline: what each section's renderer
READS vs what the writer schema EMITS. Method: a workflow fanned one auditor
agent per ST section (reading `patterns/st_XX.py` + `templates/st_XX.html.jinja`
+ the `build_live.py` adapter + `docs/resolve-schema-node-v5.js`), each followed
by an adversarial verify pass that tried to REFUTE every claimed gap by grepping
the adapter for any fill or rename before confirming. 22 agents, 0 errors.

Two failure modes:
- **missing_field** — the renderer reads a contract field nothing fills → an empty
  slot on the page.
- **wasted_key** — the writer emits a key nothing reads → budget into a void.

13 gaps survived verification. **ST-09, ST-07A, ST-22 came back clean.** The cover
(ST-01) is by far the most under-wired page (5 gaps, 2 high).

## STATUS (2026-07-16): 12 of 13 FIXED and verified; 1 deferred

Applied via 3 adapter edits (`build_live.py`) + schema-node edits
(`resolve-schema-node-v5.js`). Verified by a harness kept IN THE REPO at
`/Users/utkarsh/Projects/richard/dmc-renderer/verify_contract_fixes.py` (10/10,
network stubbed, runs offline) plus a real-payload run of christoph_v5 (adapter
stable, cover+summary bylines fill). Re-run it after any adapter change:

```bash
cd /Users/utkarsh/Projects/richard/dmc-renderer && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib ../research/v7-renderer/.venv/bin/python verify_contract_fixes.py
``` Key insight: the adapter does NOT strip unknown keys,
so a schema key named exactly what the renderer reads (`partners`, `title_accent`,
`kicker_pills`, `teaser_items`, `compare`, `pullquote`) PASSES THROUGH with no
adapter change — only `proof_stats` (derived from `stats`), `author` (injected),
and belief `quelle` (dropped by the irrtuemer→beliefs transform) needed adapter code.

- ✅ ST-01 proof_stats — adapter maps `stats`→`proof_stats` for ST-01.
- ✅ ST-01 + ST-FAZIT author — founder-identity gate widened to `("ST-05","ST-01","ST-FAZIT")`.
- ✅ ST-05 partners — pass-through key added to schema.
- ✅ ST-01 teaser_items / kicker_pills / title_accent — pass-through keys added.
- ✅ ST-02 pullquote (+attribution) — pass-through (adapter already normalizes a string pullquote).
- ✅ ST-14 beliefs[].quelle — schema sub-key + adapter carries it through the transform.
- ✅ ST-07B compare — pass-through object key added.
- ✅ ST-03 kennzahlen — removed (wasted; CTA has no figure slot).
- ✅ ST-06 bildwunsch.zweck — removed from F_bildwunsch globally (read nowhere).
### PIXEL VERIFICATION (2026-07-16): rendered the cover and LOOKED

`dmc-renderer/render_cover_check.py` renders the christoph v5 deck with a cover that
exercises the fixes, and rasterizes page 1. All five wired slots reached the page
(proof_stats 2, author "Christoph Winter / Gründer", 2 pills, title accent, teaser).
**Looking found two defects that every assertion passed:**

1. **`300.000 €` broke MID-NUMBER** ("300.00" / "0 €") in the cover rail. A figure must
   never split. Cause: the rail is a narrow overlay column but the value used the global
   shout tier `--type-stat-xl` (60pt). **FIXED** in `styles/st_01.css` by scoping the
   cover rail value down to `--type-signature` (28pt) + `white-space: nowrap`, exactly
   as `styles/st_06.css:161` already does for its narrow column. The guarded global tier
   in components.css is untouched (test_components asserts it, 45 guard tests still green).
   Re-rendered: both figures now sit on one line inside the card.
   Note: an intermediate 40pt + nowrap still overflowed the card horizontally — the
   nowrap turned a mid-number break into a horizontal overflow, which is why the size
   had to come down too. Verified by looking, not by markup.

2. **The teaser rail was SILENTLY CLIPPED.** With 3 realistic German lines, item 1 cut
   mid-word and item 3 vanished, **while the sheet count stayed correct at 17** (the
   bleed page's overflow:hidden ate it), so no page-count QC could catch it. Even after
   shortening to 2 short phrases it fit with only ~3.5mm of the designed 20mm bottom
   padding left. **NOT SHIPPED**: `teaser_items` was removed from the schema again. The
   cover band already carries a byline + 3-line title + 3-line subtitle; feeding this
   slot needs a LAYOUT change (reserve the rail's height, or cap the title length), not
   a writer key. A key whose safety silently depends on the title's length is worse than
   an absent module.

- ⏸️ ST-05 testimonials — DEFERRED. These are IMAGE assets (quote-card graphics), not
  copy, so no writer/adapter data-mapping can fill them; the pattern block degrades
  gracefully (renders nothing when absent), so there is no visible defect today.
  Real fix = an asset-resolution step that populates `d["testimonials"]` with
  resolved image paths (a separate task), OR delete the dead block. Left intact
  (not deleted — it is a designed feature) pending that decision.

## HIGH — real content slots empty on the page

### 1. ST-01 `proof_stats` — the cover stat rail is empty on every cover with figures
`patterns/st_01.py:139` reads `d.get("proof_stats")` for the vertical stat rail
overlaid on the photo. Nothing assigns `proof_stats`. The writer's `kennzahlen`
land in `d["stats"]` (adapter `build_live.py:506` + `synthesize_visuals.py:460`),
but the pattern only reads `proof_stats`, and ST-01 bypasses the treatment engine
(the only reader of `stats`). Verified: grep for a `proof_stats` assignment = none.
**Fix (adapter):** after the `synthesize_visuals` call in `envelope_to_render_request`,
`if st == "ST-01" and norm.get("stats") and not norm.get("proof_stats"): norm["proof_stats"] = norm["stats"]`.
Alt: `patterns/st_01.py:139` iterate `d.get("proof_stats") or d.get("stats")`.
Keep `kennzahlen` in `SCHEMAS["ST-01"]` — it is the source.

### 2. ST-01 `author` — the founder byline never fills on the cover
`patterns/st_01.py:153,162-163` read `author.name` / `author.role` for the cover
byline. The founder-identity injection (`build_live.py:814`) is gated to
`st == "ST-05"` only, so the cover is excluded; `brand_tokens.founder_full_name`
exists but is wired only to About. The founder portrait renders (Drive slot) but
the identity byline stays blank.
**Fix (adapter):** widen the gate at `build_live.py:814` from `st == "ST-05"` to
`st in ("ST-05", "ST-01")`.

## MEDIUM

### 3. ST-05 `partners` — the "Vertrauen von" credential wall is empty
Read by BOTH renderers: `patterns/st_05.py:160` (logo-wall name fallback) and
`treatment_engine._adapt_st05:607` (`td.credentials` → editorial credential wall).
Nothing fills `partners`: grep in `build_live.py` = 0 hits; `SCHEMAS["ST-05"]` has
no partners key.
**Fix (schema + adapter):** add an optional `partner` / `bekannt_aus` array (real
names from DATA only) to `SCHEMAS["ST-05"]`, rename to `d["partners"]` in the ST-05
adapter branch (`build_live.py:213`), same one-liner as `vertrauenspunkte`→`credibility_points`.

### 4. ST-FAZIT `author` — the signed close carries no founder name
Same shape as gap 2. The fill-variant summary has a signed close that reads
`author`, but the founder-identity block is ST-05-only.
**Fix (adapter):** widen the `build_live.py:814` gate to include `"ST-FAZIT"`.
Leave `SCHEMAS["ST-FAZIT"]` unchanged (a byline is an envelope fact, not writer copy).

### 5. ST-05 `testimonials` — dead pattern block (or needs asset resolution)
`patterns/st_05.py:136-142` renders testimonial cards from `d["testimonials"]`,
which are IMAGE assets, not copy. Nothing resolves them.
**Fix:** either add a client-asset resolution step that populates `d["testimonials"]`
with quote-card image paths, or delete the dead pattern block. Do NOT add a writer
schema key — the copy writer cannot produce image assets.

### 6. ST-03 `kennzahlen` — WASTED (writer invited to emit figures the CTA can't show)
I added `F_kennzahlen` to `SCHEMAS["ST-03"]` (the back-cover CTA), but `patterns/st_03.py`
renders no stats/viz slot, so it is dropped.
**Fix (my schema node):** remove `F_kennzahlen` from `SCHEMAS["ST-03"]` (one line).
Alt: wire a proof slot into the CTA renderer if trust figures beside the CTA are wanted.

## LOW / cosmetic / defer

- **ST-01 `teaser_bullets`** — the "In diesem Report" contents rail never renders
  (no source). Add an optional `teaser_punkte` array + adapter map, or delete the
  template block. (Medium-ish: a whole designed cover module is absent.)
- **ST-01 `kicker_pills`** — pill row empty; the kicker still renders as the audience
  line, so no content lost. Decorative.
- **ST-01 `title_accent`** — the two-tone headline already renders via a last-word
  fallback; only the explicit accent control is unfed. Cosmetic.
- **ST-02 `pullquote`** — a latent thesis pull-quote slot; the writer never emits it
  (guarded, so no empty box). Add optional `pullquote`(+`_attribution`) to `SCHEMAS["ST-02"]`
  if wanted; the adapter already normalizes a string pullquote.
- **ST-14 `beliefs[].quelle`** — no per-belief source line. Add an optional `quelle`
  sub-key to the `irrtuemer` items if per-belief attribution is wanted.
- **ST-07B `compare`** — an unused two-column compare slot; add a `compare` object
  to `SCHEMAS["ST-07B"]` if wanted.
- **ST-06 `bildwunsch.zweck`** — `art` routes the image slot but `zweck` (the intent
  hint) is read by nothing. Minor wasted sub-key.

## Clean sections
ST-09, ST-07A, ST-22 — no confirmed gaps.
