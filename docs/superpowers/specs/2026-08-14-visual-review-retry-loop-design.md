# Visual-Review Retry Loop with Fail-Closed Shipping (design)

Date: 2026-08-14

## Problem

The v3 pipeline can produce a delivery PDF without a valid visual-review
decision. The convergence loop grades pages, but when the vision client
(OpenRouter) fails after its internal attempts, the failure becomes an
`other` flag and the build still ships. `converge_v3.py` only runs the
deterministic conductor gates; `vis_client.py` raises after 3 attempts; the
service returns a PDF regardless.

The owner's requirement (2026-08-14): **never ship an ungraded deck, and
never block without a retry path.** Blocking alone is also a defect, because a
transient reviewer failure would permanently strand a good build.

## Decision (owner-approved)

- **3 visual-review attempts per page** (each attempt = review + optional
  conductor repair + re-render).
- **3 exponential-backoff retries** for transient reviewer/API failures,
  applied at each attempt.
- **1 whole-deck retry pass** after per-page attempts are exhausted: run the
  full deck through one global art-direction pass, then review all pages again.
- After all retries: return **`review_required`** with **no delivery PDF**.

## Architecture

A new `VisualReviewLoopV3` component orchestrates build → review → repair →
re-review, replacing the current read-only grading. It composes existing
pieces: the v3 builder, the conductor's `propose`/`apply`/`apply_type`, the
vision client, and the registry.

```
build_and_render_v3 (existing)
  └─ VisualReviewLoopV3.run(envelope)
       │
       ├─ for attempt in 1..3 (per page):
       │     ├─ build candidate (immutable attempt record)
       │     ├─ score page via VisionClient (3 backoff retries, then fail-closed)
       │     ├─ score meets threshold? ── yes → next page
       │     ├─ conductor.propose(failures)  (renderer-fixable only)
       │     ├─ has fix? ── yes → apply → rebuild → loop
       │     └─ no fix / exhausted / stalled → flag page, keep best build
       │
       ├─ whole-deck pass (once):
       │     ├─ apply one global art-direction pass to remaining pages
       │     └─ re-review all flagged pages (3 attempts each)
       │
       └─ decide:
             ├─ all pages pass → ReleaseState.SHIP_READY (requires threshold
             │    evidence + human calibration, unchanged)
             ├─ reviewable but incomplete → REVIEW_CANDIDATE (unchanged)
             └─ review failed/unavailable/stalled/exhausted
                  → NEW ReleaseState.REVIEW_REQUIRED, no delivery PDF
```

## Data flow

- **Immutable attempt record** per build: contract hash, render hash, page
  scores, conductor report, flags. Stored in the existing artifact store
  (`research/artifacts/`) as `review_required` retention class.
- **Transient-failure classification**: network/5xx/parse errors on the vision
  client are transient (retry with backoff). A page that the reviewer
  *rejects* is a design defect (repair), not transient.
- **Threshold evidence**: unchanged — two raters, exact candidate hash, policy
  hash, decision timestamp. No threshold → `REVIEW_CANDIDATE`, never ship.

## Error handling

- Vision client exhausted (3 backoff retries fail): page → `review_required`.
- Conductor has no fix for a defect (capability gap): page → flagged, not
  papered over (existing CAPABILITY_GAPS rule).
- Oscillation (repair made things worse): roll back, keep best build, flag.
- Any internal error in the loop: fail closed → `review_required`, no PDF.

## Release states (extension)

Add to `ReleaseState`:
- `REVIEW_REQUIRED = "review_required"` — a human must look at the deck; no
  delivery PDF is emitted. This is distinct from `REVIEW_CANDIDATE` (which is
  structurally reviewable and can still reach ship via evidence).

`ShipGateV3` legal transitions updated: `REVIEW_REQUIRED` may transition to
`REVIEW_CANDIDATE` (after human review) or `REJECTED`/`DRAFT` (unchanged).

## HTTP surface

`/render-v3` returns:
- `ship_ready` / `review_candidate`: unchanged behavior (PDF for ship).
- `review_required`: JSON with `{release_state, failures, attempt_records,
  artifact_manifest}` and **no PDF body**. HTTP 202 (accepted for review).

## Testing

- Unit: transient-failure retry (backoff counts, exhaustion → review_required).
- Unit: conductor repair loop (3 attempts, improvement, rollback on worse).
- Unit: whole-deck pass triggers exactly once.
- Unit: `review_required` never carries a PDF; ShipGate transitions.
- E2E (fake vision client): a deck that fails review returns
  `review_required`; a deck that passes returns `review_candidate`.

## Out of scope

- The generator/director asset subsystem (fal API, whole-vision prompt
  generation) — separate design; this loop consumes whatever the builder
  produces.
- Human rating calibration (unchanged, still owner-gated).
