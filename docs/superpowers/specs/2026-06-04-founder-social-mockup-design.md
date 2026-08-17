# Smart Founder Asset Understanding & Routing — Design

**Date:** 2026-06-04
**Status:** Design for review (corrected per author steer; no implementation until sign-off).

## 0. Course-correction (what changed)

Two earlier framings were wrong and are recorded so we don't repeat them:
- **Video-frame mockups** — disproven by real data (captioned, low-res, vertical b-roll).
- **Synthetic device-frame compositing** (sourcing bezel PNGs, pasting a creative into a phone) — rejected by the author: too rigid, and unnecessary. **The founder's Instagram already contains real photos of them holding a phone, at a laptop, on stage, in lifestyle/professional contexts.** A real "founder at a laptop" photo *is* the laptop shot — authentically. No synthetic frame.

**The actual ask:** the scraper should harvest a **rich variety** of the founder's real assets, and the system should be **smart enough to *intercept* each asset — understand what it depicts and how it can be turned into a report element that increases visual appeal** — then route it to where it belongs. This is the Interceptor's Perception→Analysis discipline applied to assets.

## 1. Why this exists

Today the scraper fills a fixed handful of slots (founder/team/scene) and discards the rest. But a founder's feed is a rich pool — speaking-on-stage shots, at-desk/working shots, group/event photos, lifestyle, professional portraits, content/testimonial cards. The reference decks derive much of their visual appeal from *varied, real, contextual founder imagery* placed intelligently. We are leaving most of that on the floor and have no understanding of what each scraped asset *is* or where it would shine.

## 2. What it solves vs. does NOT (honest boundaries)

**Solves:** (a) harvest a broad, deduped pool of the founder's real images; (b) a VIS-driven **asset-understanding layer** that classifies each image's *role* + *visual-appeal* + *suitability*; (c) a **router** that places each asset into the report element where it adds the most appeal (cover hero, about portrait, "founder working" imagery, stage/credibility, team, scene/atmosphere, social-proof). Real "founder-at-device" photos fill the `device_mockup`/working-imagery role directly.

**Does NOT (stays flagged, never faked):** client case-study *portraits* (client faces); invented metrics/social proof; charts. No synthetic device frames. A role with no suitable real asset is **flagged**, never fabricated.

**Cardinal rules:** brand-agnostic (no client literals in logic); never fabricate; VIS-gated; real/specific only.

## 3. Inputs
The full scraped pool per founder (IG posts incl. carousels, avatar, banner, YT thumbnails + eligible-short frames) — kept as a pool, not narrowed to 4 slots up front. Plus deterministic signals already computed (faces, sharpness, resolution, aspect).

## 4. Architecture — Perception → Analysis → Routing

### 4.1 Perception (deterministic, cheap — already mostly built)
Per asset: resolution, aspect, sharpness, face count + boxes, print-capable flag. Pre-filters garbage before any VIS spend.

### 4.2 Analysis — the asset "interceptor" (VIS, brand-agnostic)
One VIS call per surviving asset returns a structured judgement:
```
{ role: "founder_portrait" | "founder_working" | "founder_speaking" | "group_team"
        | "lifestyle" | "content_card" | "logo" | "other",
  has_overlaid_text: bool,
  visual_appeal: 0-3,
  notes: str }
```
`role` is what it DEPICTS (a real founder-at-laptop → `founder_working`); `has_overlaid_text` separates clean photos from designed cards; `visual_appeal` ranks within a role. Brand-agnostic prompt (depicts/quality only, ignore brand identity). Cached per image.

### 4.3 Routing — role → report element (maximize appeal, never fabricate)
A deterministic map from role → candidate report slots, then fill best-appeal-first with de-dup:
| role | report element(s) |
|---|---|
| founder_portrait (clean, frontal, print-capable) | cover hero, about portrait |
| founder_working (at laptop/phone/desk) | "process/working" imagery, about scene, **device_mockup role** |
| founder_speaking (stage/event) | credibility/scene |
| group_team | team |
| lifestyle | scene/atmosphere |
| content_card / testimonial | social-proof element (NOT a portrait) |
| logo | logo slots |
A slot with no role-appropriate, VIS-passing asset → **flagged**. The router emits per-element `filled(path, role, appeal)` | `flagged(reason)`.

### 4.4 Reuse
Extends the existing scraper: `selector.py` (DET signals) stays; the VIS `quality_gate` generalizes from a binary accept/reject into the richer `role+appeal` classifier (same OpenRouter client, injectable, FakeVisionGate in tests). The orchestrator's de-dup/fill logic generalizes from fixed slots → role-routed elements. The `slot_bridge` maps routed assets to resolver drive-key filenames (already built).

## 5. Integration
- Routed *drive* assets (portrait/team/working/scene/proof) → `client_assets/<slug>/` via `slot_bridge` → resolver → package → renderer (proven end-to-end in Phase 2).
- The `device_mockup` slot (`source="composite"`) is satisfied by a real `founder_working` photo routed into the composite asset channel (no synthetic frame).
- Runs OUT-OF-BAND (slow: VIS per asset), populating the store ahead of synchronous `/render`.

## 6. Failure modes & risks (named)
- **VIS cost** — one call per asset; bounded by the DET pre-filter + a per-founder asset cap; cached.
- **Role mis-classification** — mitigated by DET cross-checks (a "portrait" must actually have a frontal print-capable face) + appeal threshold; low-confidence → flag, not place.
- **Sparse feeds** — some founders post only cards (e.g. agencies): portrait/working roles may be unfillable → flagged honestly (as already seen with jousefmrd, whose only clean photos were avatars).
- **Whose content per case study** — not solved; v1 routes the founder's own assets to report-level elements, not per-client-case content.

## 7. Testing strategy
- Perception + router tested deterministically with scripted classifications (role→element, de-dup, flag-on-empty) — no network.
- The VIS classifier behind the injectable client; `FakeVisionGate`-style scripted roles in tests; one opt-in env-gated live test on a real founder (classify real assets, view the routing).
- Brand-agnostic guard extended.

## 8. Out of scope (deferred)
Synthetic device frames; perspective/shadow compositing; client case-study portraits; per-case-study client content; Supabase persistence.

## 9. Self-review
- **Scope:** one subsystem (understand + route the founder asset pool). Bounded.
- **Honest:** records the two disproven approaches; never-fabricate + brand-agnostic + VIS-gate enforced; sparse-feed reality named.
- **Reuses** the built scraper (DET selector, VIS client, de-dup/fill, slot_bridge, generated-asset channel) — this is a generalization, not a rewrite.
- **Author intent captured:** scrape a rich variety; an Interceptor-style VIS layer that understands each asset and how it should be used; real photos (incl. founder-at-device) over synthetic mockups.
