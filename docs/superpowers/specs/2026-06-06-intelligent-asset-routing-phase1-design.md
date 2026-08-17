# Intelligent Asset-Routing — Phase 1 Design (Social Layout Planner)

**Date:** 2026-06-06
**Status:** Approved (brain = hybrid AI-perceives/rules-place; placement = dynamic-per-report reserved homes + graceful fallback). Phase 1 = the rules-place half, driven by a HAND-AUTHORED classified manifest (no VIS, no credits). Phase 2 (later) = the live VIS perception that produces the manifest.

## 0. Goal (what Phase 1 proves)
Replace the HAND-EDITED fixture social placements (this session: profile-grid breather, testimonial cards, founder-in-action breathers, founder sign-off) with a **deterministic Social Layout Planner** that DECIDES them from a **classified-asset manifest** + the report content, and writes them into the package — so a `build_package.py` run reproduces the deck without hand-edits. The manifest is the (Phase-2) interceptor's output, hand-authored for apex now.

## 1. Where it lives (division of labour)
Entirely pre-processor. New stage `stages/plan_social.py`, run in `build_package.py` (and later the live `/render` pipeline) AFTER `structure_content`/`resolve_slots`, its bindings applied to the package. Renderer is unchanged (the vocabulary — `phone_mockup` grid/single, ST-05 `testimonials`, ST-31 `social_post`, ST-FAZIT founder sign-off — already exists and is token-only).

## 2. Components (small, isolated, testable)
- **`models_social.py` (or extend models):** `AssetClassification` (path, role, is_testimonial_card, brand_text, visual_appeal, has_overlaid_text) + `AssetManifest` (handle, assets: list) + `SocialBinding` (target_kind, page_slot|None, element, assets: list[str], handle, caption) + `SocialPlan` (bindings: list, dropped: list[reason]).
- **`stages/plan_social.py`:** `plan_social(manifest, pages, *, case_clients, breather_slots, about_slot, asset_exists) -> SocialPlan` — PURE function (injected `asset_exists(path)->bool` so it never binds a missing file). Deterministic. + `apply_social_plan(package: dict, plan: SocialPlan) -> dict` — writes bindings onto the package pages (idempotent).
- **`fixtures/apex/asset_manifest.json`:** the hand-authored apex classification (the 13 IG assets → roles/cards/brand_text), simulating the interceptor.
- **`build_package.py` wiring:** load manifest → `plan_social(...)` → `apply_social_plan(pkg)` → re-write `resolved_package.json`.
- **`tests/test_plan_social.py`:** deterministic planner + applier + graceful-empty tests.

## 3. Routing rules (role → element), allocated dynamically, only when the asset exists
1. **Profile-grid breather:** ≥6 gate-passing *posts* (roles: speaking/working/scene/client_photo, NOT cards/portrait) → bind a `profile_grid` (9, appeal-ranked) to ONE breather (the LAST breather slot, deterministic).
2. **Scene breathers:** remaining breather slots (in order) → the next best single `scene/speaking/working` photo each → `social_post` single OR a plain full-bleed photo ground.
3. **About testimonials:** ≥1 `is_testimonial_card` → bind the cards (appeal-ranked, ≤2) to the About page `testimonials`; this triggers the copy-fit (trim About body to 2 paras + the template already drops the redundant credibility list).
4. **Case-study matched post:** a non-card post whose `brand_text` (normalized) is contained in a case study's client name → bind a `social_post` single phone to that case study. **Confident single match only**; ambiguous/none → skip (NEVER a mismatched client).
5. **Founder slots** (cover hero / About portrait / FAZIT sign-off): Phase 1 sets the FAZIT sign-off `author` from the manifest handle/name when present; cover/About founder slots already resolve via `resolve_slots` (left as-is this phase to avoid disrupting working slots).
Each asset used once (de-dup). Appeal-ranked selection. Everything graceful → absent asset = the home's non-social default renders.

## 4. Data flow
`asset_manifest.json` (hand-authored) → `plan_social` (+ report content: case-study client names from ST-07A data, breather slots = ST-31 slots, about slot = ST-05) → `SocialPlan` → `apply_social_plan` mutates the package pages (ST-31 `data.social_post`/`grid`, ST-05 `data.testimonials` + body trim, ST-07A `data.social_post`, ST-FAZIT `data.author`) → renderer places it. Phase 2 swaps the hand-authored manifest for the live VIS interceptor output (same schema).

## 5. ADVERSARIAL GAP-AUDIT (found UP FRONT, before code)
1. **Manifest↔file drift** → bind only if `asset_exists(path)`; else add to `plan.dropped`. Test asserts every manifest path exists.
2. **Client-match false +/-** → normalized case-insensitive containment, CONFIDENT SINGLE match only; 0 or >1 → skip + record dropped reason. Test both directions.
3. **ST-05 overflow** (proven: testimonials need the body trim) → when testimonials bound, the applier ALSO trims About body to 2 paras (the copy-fit decision travels WITH the binding). Verify: rendered ST-05 = 1 page.
4. **Breather assignment order** → grid → LAST breather slot; scenes → earlier slots in slot order (stable, deterministic). Test the assignment map.
5. **Founder-slot conflict** → Phase 1 does NOT touch cover/About founder slots (already resolved); only sets FAZIT `author`. No double-binding.
6. **Re-bake idempotency / golden drift** → `apply_social_plan` is pure+deterministic; the existing preprocessor golden + `build_package.py` contract asserts will shift by EXACTLY the social bindings → re-baseline after diffing (same pattern as PBR-E). New contract asserts: grid breather present, ST-05 testimonials present, no overflow.
7. **Manifest schema = Phase-2 contract** → a pydantic `AssetManifest`/`AssetClassification`; Phase 2 VIS must emit the same shape (documented).
8. **Brand-agnostic** → ZERO client literals in `plan_social.py` (no "Frese"/"jousefmrd"/"APEX"); all from manifest/content. Extend the brand-agnostic guard to the new file.
9. **Graceful empty pool** → empty/absent manifest → `SocialPlan` with no bindings → deck renders all defaults (atmospheric breathers, photo gallery), no crash, no blanks. Test.
10. **De-dup** → an asset bound to one home is not reused elsewhere (e.g., a grid post also a breather scene). Track used paths. Test.

## 6. Testing strategy
- `plan_social` PURE tests: (a) full apex pool → expected bindings (grid on last breather, 2 testimonials→about, Frese post→Frese case study, scenes→other breathers); (b) empty pool → zero bindings; (c) client-match +/- ; (d) <6 posts → no grid (scenes only); (e) de-dup; (f) asset_exists=False → dropped, not bound.
- `apply_social_plan` tests: bindings land on the right pages; ST-05 body trimmed when testimonials bound; idempotent (apply twice == once).
- **Verify on REAL data (mandatory):** run `build_package.py` → `render.py` → VIEW pixels p3 (testimonials, decrammed), the breathers (grid + scenes), a matched case study, p19 (sign-off). Confirm the planner reproduces the hand-placed deck + deck stays ~20–21pp, no new overflow. HEAVY scrutiny → any gap (code/layout/logic) → fix → re-render → re-verify (the loop).
- Brand-agnostic guard extended to `plan_social.py` + `asset_manifest.json` (no hex/font literals in logic; client strings live only in the manifest DATA).

## 7. Out of scope (Phase 2+)
Live VIS perception (the interceptor producing the manifest); persisting `founder_instagram_url`; cover/About founder-slot re-routing; laptop/browser mockups; dynamic page ADD/REMOVE (Phase 1 reuses the existing 3 breathers + ST-05 + case studies as the home pool).

## 8. Self-review
- **Scope:** one stage (decide social placement from a manifest) + its manifest + wiring + tests. Bounded, single plan.
- **Isolation:** `plan_social` is a pure function (injected `asset_exists`); `apply_social_plan` is the only mutator; manifest is data. Each testable alone.
- **Honest:** no fabrication (client-match guard; graceful fallback; manifest is REAL classifications of REAL scraped assets). Brand-agnostic enforced.
- **Reuses:** the renderer vocabulary (built this session), the existing stage pipeline + golden-rebake pattern.
