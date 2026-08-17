# DMC V3 Master Program Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the permissive v2 report pipeline with a traceable, capacity-aware, reference-calibrated v3 compiler without breaking the current development route before v3 proves itself.

**Architecture:** Four implementation streams execute in dependency order: authoritative contracts, composition and deterministic rendering, exact-artifact quality and export, then workflow parity, asset governance, design-policy promotion, and broad calibration.

**Tech Stack:** Python 3.11, Pydantic v2, pytest, Jinja2, Chromium, Playwright, PyMuPDF, pikepdf, Ghostscript, JavaScript, JSON Schema

---

## Program rules

- Use the v3 architecture specification at `docs/superpowers/specs/2026-08-03-dmc-system-architecture-design.md` as the authority.
- Use the atlas at `research/reference-atlas/` as the v1 reference evidence.
- Keep `POST /render` and package v2 operational until the v3 migration gate passes.
- Label all v2 artifacts as legacy or draft. Never describe them as v3 ship ready.
- Do not add creative families before canonical evidence, page, and asset contracts exist.
- Do not make a quality rule advisory when its failure invalidates evidence, structure, required assets, visibility, or export.
- Do not silently change promoted composition or policy versions.
- This repository is not under git. Use dated local backups before editing existing files.

## Phase 1: Authoritative contracts

Execute `docs/superpowers/plans/2026-08-03-contract-and-editorial-planner.md` completely.

Exit evidence:

- Current Christopher is rejected before composition for wrong face count, five cases, five missing portraits, and ungrounded `83%`.
- A valid synthetic fixture produces stable source, editorial, and asset ledgers.
- Page, face, spread, fragment, and PDF-object units are explicit.

Stop gate: do not start renderer migration if the precomposition bundle still contains free-form page dictionaries or unreferenced numeric strings.

## Phase 2: Composition and deterministic renderer

Execute `docs/superpowers/plans/2026-08-03-composition-and-renderer.md` completely.

Exit evidence:

- Ten atlas-grounded composition families are versioned.
- Selection is feasibility-first and deterministic.
- One valid 20-face contract renders without ST-based selection or silent fallback.
- Every required element appears in a materialization ledger.

Stop gate: do not call a candidate reviewable if capacity or required visibility is inferred only from the absence of an extra PDF page.

## Phase 3: Quality gate and exports

Execute `docs/superpowers/plans/2026-08-03-quality-and-postprocessor.md` completely.

Exit evidence:

- Deterministic hard failures block delivery.
- The gate examines the exact returned artifact hashes.
- Digital export preserves at least 99 percent of normalized raw text.
- Print export requires a production-approved profile and emits a preflight report.

Stop gate: do not route production traffic to v3 while a missing required asset or ungrounded claim can still return a delivery PDF.

## Phase 4: Workflow, asset bank, policy, and calibration

Execute `docs/superpowers/plans/2026-08-03-n8n-assets-and-calibration.md` completely.

Exit evidence:

- Deployed n8n artifacts prove parity with repository hashes.
- Asset selection is provenance-aware and semantic-class safe.
- Selected TypeUI and Designer Skills knowledge is pinned, licensed, print-translated, and versioned.
- At least five diverse client fixtures pass through the calibration matrix.
- Composition families and design policies have a tested promotion path.

Stop gate: do not load unpromoted families or policies in production.

## Phase 5: Migration decision

**Files:**

- Create: `docs/phase-zero/V3-MIGRATION-READINESS.md`
- Create: `dmc-renderer/tests/test_v2_v3_route_isolation.py`
- Modify: `dmc-renderer/service.py`

- [x] Run the complete v2 suite and record current failures without rewriting requirements to make it green.
- [x] Run every v3 test group from the four plans.
- [x] Render all calibration fixtures with external generation disabled and frozen assets.
- [x] Render the same valid fixture twice and compare contract, HTML, ledger, and PDF hashes.
- [ ] Conduct blind review of v3 candidates against the matching atlas families.
- [x] Write `V3-MIGRATION-READINESS.md` with every gate result, unresolved risk, human rating summary, and artifact links.
- [x] Change the default route only after every hard gate passes and the owner explicitly approves migration. No change was made because the gates did not pass.
- [x] Keep a named `legacy-v2` route for a bounded deprecation window. Remove it in a separate approved plan.

## Final verification command

After all four plans have been implemented, add `scripts/verify_v3_program.sh` that runs the exact focused commands from each plan followed by the full suite. The script must use `set -euo pipefail`, print tool versions, and write a timestamped JSON summary under `research/calibration/runs/`.

The program is complete only when the migration-readiness document proves:

- Source-to-pixel claim traceability
- Exactly 20 physical faces for the house profile
- Exactly three complete cases
- Capacity-feasible composition selection
- Zero silent ship-mode fallback
- Zero missing required visible elements
- Blocking evidence and asset failures
- Searchable digital output
- Profile-validated print output
- Reproducible version and artifact manifests
- Human-calibrated visual quality at or above the approved threshold
