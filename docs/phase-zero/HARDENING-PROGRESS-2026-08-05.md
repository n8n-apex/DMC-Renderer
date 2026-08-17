# v3 integration hardening: session progress (2026-08-05)

Continuation of `docs/superpowers/plans/2026-08-05-v3-integration-hardening.md`
after the Codex handoff. Companion audit: `CODEX-AUDIT-2026-08-05.md`.

## Verified starting state

Codex left the repository in an unfinished TDD red phase: Task 1 was checked
complete, but 14 Node tests, 10 workflow-contract Python tests, 28
build-manifest tests, and 4 handshake tests were failing red tests written for
Task 2 with no implementation behind them.

## Task 2: workflow authority (complete, green)

- All five paste targets and the writer prompt now declare the frozen
  six-field 3.2.1 handshake; `workflow-contract-v3.json` is at contract 3.2.1
  with recomputed byte hashes.
- `source-ledger-node-v3.js` no longer requires `node:crypto`: it carries a
  portable FIPS 180-4 SHA-256 proven by fixed test vectors, so the full source
  executes inside an n8n Code node with no CommonJS globals. Computed claims
  now enforce operand arity (difference/ratio take exactly two) and unit
  dimensions (`incompatible computation units`).
- `claim-gate-v3.js` grounds JSON *number* primitives at every depth with
  nearest-inherited claim IDs, checks strings inside arrays, and adds key
  semantics: `ergebnis_text` demands a `named_result` claim,
  `vertrauenspunkte` entries demand `credential` claims.
- `writer_gate.js` rejects German adjective inflections of banned vocabulary
  (`robuster`, `revolutionäre`) and detects short English titles and mixed
  English prose by English-marker dominance while German loanwords stay safe.
- `BuildVersions` gained a required `workflow_authority` mode: `verified`
  demands the complete strict-semver six-field set; `non_workflow` forbids
  carrying any workflow version. `_with_workflow_provenance_v3` stamps
  `verified` only on complete ingress.
- Suites: 51 Node, 27 docs/n8n Python, 21 handshake, 31 build-manifest, all
  green; 623 preprocessor tests green.

## Task 3: deployment closure (complete, green)

- Image built from current source; `scripts/smoke_v3_container.sh` passed
  end-to-end: `/health/v3` OK, `/render-v3` returned a structured
  `review_candidate` with matching contract and gate hashes, `/render`
  unchanged (route isolation green).

## Task 4: immutable artifacts and evidence-based release (complete, green)

- New `research/artifacts/` package: `BuildRecordV3` binds input hash,
  workflow versions, source/asset/editorial ledger hashes, composition and
  render-contract hashes, PDF hashes, gate report and export report hashes.
  `FilesystemArtifactStore` persists atomically (staging dir + one rename),
  is idempotent for identical content, and refuses to overwrite a retained
  build with different bytes.
- Retention classes: rejected and draft retain diagnosis only (no PDFs);
  review retains the ledger, HTML, raw PDF, and marked review PDF;
  approved_digital/approved_print add the delivery PDFs and export reports.
- The fail-open default `result.get("release_state", "ship_ready")` is gone:
  a missing or unknown release state is a 500, never a shipped PDF.
- `ship_ready` now requires a validated `VisualReviewEvidenceV3` record: at
  least two distinct raters, rubric version, the exact candidate PDF hash, a
  decision timestamp, and the hash of the threshold policy in force. Boolean
  approval flags without evidence raise `visual_review_evidence_missing`;
  evidence that does not match the rendered PDF raises
  `visual_review_evidence_invalid`.
- Review candidates are served only as a visibly stamped copy
  ("REVIEW-KANDIDAT <hash> | KEINE AUSLIEFERUNG" on every page); raw bytes
  stay internal for provenance.
- HTTP responses carry `X-DMC-Artifact-Manifest-SHA256` and JSON bodies for
  rejected/draft include the manifest reference.

## Verification

- `scripts/verify_v3_program.sh` run 20260805T172137Z: all nine focused v3
  groups passed; the historical v2 suite failed with exactly the recorded
  baseline of 15 failures (count unchanged, as the plan requires).
- A post-Task-4 verifier run and a container rebuild + smoke re-run were
  started to restamp the tree after the artifact-layer changes.

## Task 5: Jousef and Christopher migration (complete, green, 2026-08-06)

`research/migrations/legacy_report_v3.py` builds deterministic, review-only
migration records: original bytes hash-preserved, every source reference
extracted mechanically with `rights_status="unknown"`, case selection left
PENDING for the owner, a static explicit 20-face editorial map immune to page
ranges, and typed blockers (Jousef 180, Christopher 61 — including the
invented "83 %" pinned at its exact JSON path). Blocked migrations cannot
false-pass precomposition. Fixtures under `dmc-renderer/fixtures/v3/real/`.

## Task 6: composition selection on real features (complete, green, 2026-08-06)

- `DesignFeaturesV3` (tone tokens, brand energy, imagery density, chart
  opportunity) on the report plan; scoring policy v1.1.0 adds feature weights,
  affinity token maps, and density-band word targets as policy data.
- Families are scored on tone alignment, density fit, evidence-density fit,
  chart opportunity, and asset availability, all recorded per candidate.
- Variants are scored deterministically with the policy tie-breakers applied
  and recorded (`VariantTieBreak`), replacing alphabetical selection.
- Capacity now enforces the physical region-height line budget, treats
  words-over-target as at least `near_limit`, and supports tighten-only
  variant envelope scales.
- Proven, pinned flips: tone/brand/imagery flip family and variant; density
  band alone flips the family; evidence count alone flips it; asset
  availability alone flips it. Identical inputs stay byte-deterministic.

## Task 9: review-safe n8n workflow export (complete, green, 2026-08-06)

`docs/n8n/workflows/DMC-Ingestion-Pipeline-v3-review.json` (47 nodes,
inactive, review-only, webhook re-pathed) with a provenance manifest and 36
structural tests (63 total in `docs/n8n/tests`). The deployed original in
Downloads is preserved byte-identically. Evidence order wired: Source Ledger
v3 before the writer, Claim Gate v3 after parsed output, Writer Gate v3,
bounded retry, loud failure. Release states, timeout, and dependency failure
route separately; ship-path uploads are disabled pending validated release
evidence; run inputs persist to Drive binaries, never Airtable long-text.
Owner placeholders: review folder id, delivery folder id, four Airtable
columns. Caveat: structurally test-enforced, not yet executed in a live n8n.

## Task 7 progress (foundation landed 2026-08-06, green)

- Family anatomy system: `families/anatomy.py` maps every region of all ten
  families to a semantic anatomy role; load-bearing elements get element-level
  anatomy classes. `styles_v3/families.css` (token-only, no client literals)
  gives each family and variant its own grid layout, and the renderer now
  loads it. The `case_narrative` vertical slice renders identity,
  before/turn/after, proof, and result anatomy through a dedicated renderer.
- Raster-difference tests (`test_family_visual_distinctness.py`) prove that
  different families and different variants of the same family render
  visibly different pages, and that the DOM carries per-family anatomy.
- The materialization gate rejected the first photo_bleed treatment
  (negative-margin bleed pushed geometry outside the face); it was rewritten
  as an in-bounds ink field. The deterministic geometry gates remain the
  authority over any visual treatment.
- Semantic data visualization (landed 2026-08-06): eight typed element kinds
  (grouped comparison, formula ladder, time series, distribution, composition
  breakdown, evidence gallery, logo wall, proof wall) joined the frozen
  contract with full reference validation. Selection is driven by claim
  relationship and evidence shape in the materialize stage: a computed
  difference renders as a before/after comparison with its delta, a wider
  computation as a formula ladder, entity-scoped claims across distinct time
  scopes as a time series, and a shapeless claim stays a plain stat. Printed
  values are always the verbatim claim text; parsed magnitudes only scale the
  bars. Consumed operands never double-render. The registry moved to revision
  1.2.0 (additive allowed-kinds only); its golden-manifest integrity guard
  caught the content drift and was regenerated with the revision.
- Still open in Task 7: the remaining family slices with atlas reference-face
  assertions, palette/type-bound enforcement tests, and the atlas comparison
  gate before promotion.

## Task 7 execution brief (next)

Order of work, using the reusable machinery indexed in
`CODEX-AUDIT-2026-08-05.md` §4:

1. Red raster-difference tests: render the same face content under two
   different selected families and two meaningful variants; assert page
   rasters differ materially (pixel diff over threshold), and that each
   family's DOM carries its own anatomy classes.
2. `case_narrative` vertical slice first: identity band, before/turn/after
   device, proof block, result band — as an explicit per-family renderer
   replacing the generic region loop, with a family template + CSS in
   `templates_v3/families/` and `styles_v3/families.css` (token-only, no
   client literals; reuse the theme-lock token ramp and the viz.css premium
   recipe).
3. Element contracts for semantic viz (time series, grouped comparison,
   composition, process, formula ladder, distribution, evidence gallery,
   logo wall, proof wall) in `render_contract.py` + materialization, selected
   by claim relationship and evidence shape (computation → formula ladder;
   before/after pair → grouped comparison; time-indexed claims → time
   series), never by decorative variety.
4. Remaining families one slice at a time with reference-face assertions
   against their `atlas_face_ids`.
5. Keep the evidence grounding guard absolute: every rendered figure stays
   bound to claim IDs (Task 8 will bind tokens to content paths).

## Open human and external gates (unchanged, cannot be coded around)

Rights confirmations, two independent visual raters plus an approved
threshold, a printer-approved production profile, recovery of the three
missing source authorities, credential rotation, a read-only export of the
deployed n8n workflow, and owner approval for any route change.
