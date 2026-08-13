# Consolidated Gap-Closure Program (2026-08-13)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close every verified gap found in the 2026-08-13 full audit (24 findings across the live v2 path, the v3 compiler, the n8n contract, and the test suites) in dependency order, ending with a standing assessment harness so no gap can silently reopen.

**Architecture:** Six phases in strict dependency order. Phase 0 makes the suites tell the truth (registry-version drift, stale fixtures). Phase 1 makes per-client variation actually fire (brand_profile_id wiring). Phase 2 re-wires the live path (plan_social, v3 copy→device mapping, contract key fixes). Phase 3 hardens the service (auth, timeout, determinism). Phase 4 hardens grounding/fabrication gates. Phase 5 removes dead code and invisible spend. Phase 6 builds the standing verification harness that re-checks every closed gap on demand and on each render.

**Tech Stack:** Python 3.11, Pydantic v2, pytest, FastAPI, Chromium/Playwright, Ghostscript, Jinja2, Node (n8n gate parity).

---

## The audit findings this plan closes (the complete register)

Source: full code + test-suite + worktree-memory audit, 2026-08-13. Each gap has a severity and the phase/task that closes it.

| # | Gap | Sev | Phase / Task |
|---|---|---|---|
| G1 | `brand_profile_id` read at `build_v3.py:546` but no fixture sets it → axes system dead, every client identical | CRITICAL | P1 / T1.1 |
| G2 | 43 renderer test failures (28 NEW beyond the documented 15): registry 1.7.0 vs tests hardcoding 1.1.0 (`ContractLoadFailure: editorial_lead@1.1.0 is not in registry 1.7.0`); `test_family_slices_distinctness.py` 16, `test_render_v3_contract.py` 6, `test_semantic_data_viz.py` 3, `test_family_visual_distinctness.py` 3 + the 15 pre-existing drift | CRITICAL | P0 / T0.1–T0.3 |
| G3 | `route_package(pkg, manifest=None)` at `build_live.py:1138` → plan_social NEVER runs live; exception at :1146 masked as "skipped offline"; dark-divider + plan_diagrams dropped on any failure | CRITICAL | P2 / T2.1 |
| G4 | v3 pipeline reads ZERO of the writer's 11 visual keys (`kennzahlen/fakten/vorher_nachher/...`) — grep across contracts_v3/pipeline_v3/render_v3/build_v3/adapter_v3 = 0 readers | CRITICAL | P2 / T2.2 |
| G5 | `kunde.name`/`kunde.company_url` read by st_07a.py:278 + treatment_engine.py:569 but schema node emits only `initials`+`funktion` (with unresolved VERIFY comments) | HIGH | P2 / T2.3 |
| G6 | ST-08 supported by renderer (`patterns/st_08.py`) but `resolve-schema-node-v5.js` has no ST-08 entry → `resolveSchemaItems` THROWS on unknown ST | HIGH | P2 / T2.4 |
| G7 | `fazit_background` image slot: generate_assets.py:71-75 downloads/generates it, NO pattern/treatment reads an ST-FAZIT page asset → paid invisible asset per render | HIGH | P2 / T2.5 |
| G8 | No authentication on `/render`, `/render-v3`, `/render-legacy-v2` → unauthenticated paid-fal trigger + DoS | HIGH | P3 / T3.1 |
| G9 | "120s end-to-end timeout" is fiction — no timeout enforced; n8n kills mid-render with no artifact | HIGH | P3 / T3.2 |
| G10 | Determinism false: `assemble_package.py:333` embeds `datetime.now()`; PDF timestamp seed dropped | HIGH | P3 / T3.3 |
| G11 | `_role_devices` one-figure-one-device binds only `fakten`; verlauf/rechnung/kategorien/zusammensetzung/entitaeten never check `claimed` | MEDIUM | P5 / T5.1 |
| G12 | `kz_donuts` dedups vs `_viz_keys()` not `_stat_keys()` → figure renders as BOTH donut and stat | MEDIUM | P5 / T5.1 |
| G13 | `ausblick_punkte → zielgruppe` rename (build_live.py:232) is semantically wrong (takeaways labeled "Zielgruppe") | MEDIUM | P5 / T5.2 |
| G14 | ST-FAZIT `kosten_des_nichtstuns` read only by legacy pattern; ST-FAZIT always treated → cost block never renders live | MEDIUM | P5 / T5.2 |
| G15 | `_normalize_page_data` maps ~30 aliases with zero logging; unmapped keys pass through invisibly | MEDIUM | P5 / T5.3 |
| G16 | Hardcoded hex fallbacks in `dmc-renderer/build_live.py:788-790`, `build_v3.py:148` — no-hex guard doesn't scan dmc-renderer/ | MEDIUM | P5 / T5.3 |
| G17 | Grounding gate collapses "12,5"→"125" (`_digit_tokens` strips commas/dots); checks digits only, never label/unit | MEDIUM | P4 / T4.1 |
| G18 | Manifest scene images (`status=="downloaded"`) never paint on treated ST-09 — `_scene_uri` filters `status=="generated"` | MEDIUM | P5 / T5.4 |
| G19 | `design_brief` never populated live → fal prompts always default style | MEDIUM | P2 / T2.1 |
| G20 | `page_count_target` snapping (17→16, 21→20) silent | MEDIUM | P5 / T5.4 |
| G21 | `service.py:461` sync `def` blocks worker; with no timeout, concurrent renders serialize | MEDIUM | P3 / T3.2 |
| G22 | `_fix_umlauts_deep` rewrites `author.name`/`kunde.name` — legit "ue" pattern corrupted | MEDIUM | P5 / T5.2 |
| G23 | ST-07B `layout_variant="fill"` has THREE sources of truth (build_live:821, plan_layout FILL_DEFAULT_TYPES, route_package:91 dark_divider) | MEDIUM | P5 / T5.4 |
| G24 | No photographs anywhere; v3 calibration fixture is a 1,905-line hand-authored generator; apex-dense uses synthetic gradient blobs | MEDIUM | P2 / T2.1 + P6 |
| L1 | `verify_contract_fixes.py:84` asserts `teaser_items` passthrough but schema removed it (dead harness check) | LOW | P5 / T5.5 |
| L2 | `st_06.py:73` dead `if False else None` | LOW | P5 / T5.5 |
| L3 | `synthesize_visuals.py:383-392` unreachable LLM donut branch; `treatment_engine.py:692-698` dead `_adapt_cta_hard` | LOW | P5 / T5.5 |
| L4 | `render_christoph.py`/`render_cover_check.py` hardcode client data + hexes outside guarded trees | LOW | P5 / T5.5 |
| L5 | `service.py:474` exception text leaks absolute FS paths | LOW | P5 / T5.5 |
| L6 | `_env_or_dotenv` splits `.env` on first `=` (values containing `=` truncate) | LOW | P5 / T5.5 |
| L7 | `service.py:258` imports private `_non_numeral_stat_values` | LOW | P5 / T5.5 |
| D1 | `CODEX-HANDOFF` says 15/342; phase-zero says 15/352; reality 43 failed / 355 passed — every doc stale | — | P0 / T0.4 |
| D2 | `V3-MIGRATION-READINESS-v2`/`HARDENING-PROGRESS` claim "all green"; dmc-renderer suite = 98 pass / 9 FAIL | — | P0 / T0.4 |
| D3 | Memory (2026-08-08): "axes wired with ZERO args" — fixed in code but never exercised (G1) | — | P1 / T1.1 |
| D4 | Docs claim brand-agnostic/no-hex-in-logic; guard scans only research/v7-renderer | — | P5 / T5.3 |
| D5 | Docs claim "same input → byte-identical PDF"; broken by datetime.now (G10) | — | P3 / T3.3 |
| D6 | Docs claim "120s hard timeout"; not enforced (G9) | — | P3 / T3.2 |

---

## Standing verification commands (use in EVERY phase)

```bash
# Renderer suite (the source of G2 truth):
cd /Users/utkarsh/Projects/richard/research/v7-renderer
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python -m pytest tests/ -q

# Fast guard battery:
cd /Users/utkarsh/Projects/richard/research/v7-renderer
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python -m pytest \
  tests/test_components.py tests/test_tokens.py tests/test_design_conformance.py \
  tests/test_no_literals_in_architecture.py -q

# Preprocessor suite (own venv):
cd /Users/utkarsh/Projects/richard/research/preprocessor
.venv/bin/python -m pytest tests -q

# dmc-renderer suite (v3 + harnesses):
cd /Users/utkarsh/Projects/richard/dmc-renderer
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib ../research/v7-renderer/.venv/bin/python -m pytest tests/ -q

# Offline contract-fix harness:
cd /Users/utkarsh/Projects/richard/dmc-renderer
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib ../research/v7-renderer/.venv/bin/python verify_contract_fixes.py

# Standing assessment harness (Phase 6): proves every closed gap stays closed.
cd /Users/utkarsh/Projects/richard/dmc-renderer
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib ../research/v7-renderer/.venv/bin/python ../research/quality_loop/assess_closed_gaps.py
```

---

# PHASE 0 — Make the suites tell the truth (baseline)

**Why first:** every later phase is measured against test suites that currently lie (43 reds, 9 reds). Without a trustworthy baseline, no phase can prove it did not regress.

## Task 0.1: Rebase the v3 renderer tests off the drifted family versions

**Files:**
- Modify: `research/v7-renderer/tests/test_render_v3_contract.py:42,154,177`
- Modify: `research/v7-renderer/tests/test_semantic_data_viz.py:87`
- Modify: `research/v7-renderer/tests/test_family_slices_distinctness.py` (all `version`/`family_version` literals)
- Modify: `research/v7-renderer/tests/test_family_visual_distinctness.py` (all `version` literals)

The registry is now **1.7.0** with family versions `{1.3.0, 1.4.0, 1.5.0, 1.6.0}` (verified). The tests hardcode `1.1.0`.

- [ ] **Step 1: Reproduce the drift failures and list every stale literal**

```bash
cd /Users/utkarsh/Projects/richard/research/v7-renderer
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python -m pytest \
  tests/test_render_v3_contract.py tests/test_semantic_data_viz.py \
  tests/test_family_slices_distinctness.py tests/test_family_visual_distinctness.py -q 2>&1 | tail -5
```
Expected: the same 28 failures as the full-suite run, all rooted in `unknown_family: <family>@1.1.0 is not in registry 1.7.0`.

- [ ] **Step 2: Grep every stale version literal in the four files**

```bash
cd /Users/utkarsh/Projects/richard/research/v7-renderer
grep -rn '"1\.1\.0"\|"1\.2\.0"\|"1\.3\.0"\|= "1\.' tests/test_render_v3_contract.py \
  tests/test_semantic_data_viz.py tests/test_family_slices_distinctness.py \
  tests/test_family_visual_distinctness.py
```
For EACH hit, determine the CURRENT version of that family from `research/composition_registry/families/dmc-v1.json` (e.g. `python3 -c "import json;d=json.load(open('research/composition_registry/families/dmc-v1.json'));print({f['family_id']:f['version'] for f in d['families']})"`).

- [ ] **Step 3: Update every stale literal to the real current version** — mechanically replace the literal `"1.1.0"` (and any other stale `"1.x.0"`) with the family's real version from the registry file, using the Edit tool per occurrence. Do NOT use a blanket find-replace if different families have different versions — verify each `family_id` pair.

- [ ] **Step 4: Re-run the four files and confirm 0 failures**

```bash
cd /Users/utkarsh/Projects/richard/research/v7-renderer
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python -m pytest \
  tests/test_render_v3_contract.py tests/test_semantic_data_viz.py \
  tests/test_family_slices_distinctness.py tests/test_family_visual_distinctness.py -q
```
Expected: all pass (or fail only for reasons unrelated to family versions — investigate any remaining failure to its root).

- [ ] **Step 5: Full renderer suite — record the honest new baseline**

```bash
cd /Users/utkarsh/Projects/richard/research/v7-renderer
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python -m pytest tests/ -q 2>&1 | tail -3
```
Expected: the 28 NEW failures are gone; only the 15 pre-existing drift failures remain (st_07a_fill_variant × 11, render_r2 × 4). Record the exact number here and in T0.4's ledger.

## Task 0.2: Realign the 15 pre-existing fixture-drift tests to the current fixture

**Files:**
- Modify: `research/v7-renderer/tests/test_st07a_fill_variant.py` (11 failures)
- Modify: `research/v7-renderer/tests/test_render_r2.py` (4 failures: `st01_cover`, `st07a_flagship_composes_macro_devices`, `st07a_embeds_chart_svg_in_chart_region`, `light_page_ground_is_color_ground_not_wash`)

Root cause (verified 2026-07-16, still true): the apex fixture's case studies were replaced (Martina Ammon → GoldmanTax); tests still assert old clients (`"Martina Ammon" in frag.html` at test_render_r2.py:483), the cover asset renamed `1_founder.png`, and the light-ground contract changed on 2026-07-13 (`--color-ground` no longer appears on light pages — the TEST is stale, not the code).

- [ ] **Step 1: Read each failing test and its assertion vs the current fixture**

```bash
cd /Users/utkarsh/Projects/richard/research/v7-renderer
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python -m pytest \
  tests/test_st07a_fill_variant.py tests/test_render_r2.py -q 2>&1 | grep FAILED
```

- [ ] **Step 2: For each failure, determine the stale side (test vs code) using the 2026-07-16 precedence:** grep the OLD entity's name (`Martina Ammon`, `1_founder.png`, `cs-chart-svg`) across the tree; if the code/pattern/asset legitimately changed, update the TEST to assert the CURRENT reality (GoldmanTax, the renamed asset, the 2026-07-13 ground contract). Never weaken a guard or revert a deliberate design change.

- [ ] **Step 3: Update each stale assertion** to the current fixture reality. For `test_light_page_ground_is_color_ground_not_wash`, the correct assertion is the 2026-07-13 contract: light pages paint the ground via the full-sheet `@page` rule with `.page` transparent — assert THAT (or convert to an xfail with a dated reason if the semantics are genuinely retired).

- [ ] **Step 4: Re-run both files to 0 failures**

```bash
cd /Users/utkarsh/Projects/richard/research/v7-renderer
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python -m pytest \
  tests/test_st07a_fill_variant.py tests/test_render_r2.py -q
```

- [ ] **Step 5: Full renderer suite — EXPECTED: 0 failed**

```bash
cd /Users/utkarsh/Projects/richard/research/v7-renderer
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python -m pytest tests/ -q 2>&1 | tail -3
```

## Task 0.3: Fix the 9 dmc-renderer (v3) failures

**Files:**
- Modify: `dmc-renderer/tests/test_calibration_fixtures.py` (christoph-redacted 20≠17; apex.json rejected; density pin)
- Modify: `dmc-renderer/tests/test_build_v3.py` (determinism, calibrated ship context)
- Modify: `dmc-renderer/tests/test_v3_adversarial_e2e.py`, `test_v3_artifact_persistence.py`

Current: **9 failed / 98 passed** (verified). Two root causes: (a) fixture-recipe drift — `christoph-known-failures` allocates 17 faces but `test_every_fixture_recipe_preserves_internal_face_allocation_contract` expects 20; apex.json reaches `rejected` not `review_candidate`; (b) tests assume the pre-2026-08-07 A4-only format model.

- [ ] **Step 1: Reproduce and categorize the 9**

```bash
cd /Users/utkarsh/Projects/richard/dmc-renderer
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib ../research/v7-renderer/.venv/bin/python -m pytest tests/ -q 2>&1 | grep -E "FAILED|passed|failed"
```

- [ ] **Step 2: For the face-allocation failure** — read `test_calibration_fixtures.py:110-120` and the `christoph-known-failures` recipe at `calibration_fixtures_v3.py:389-401`. Decide with the 2026-07-16 precedent: is the recipe intentionally 17 faces (a known-failure fixture) and the TEST wrongly asserts 20? If so, update the test to assert the recipe's real allocation (17) and its intent (must be BLOCKED). The failure recipe's whole point is a wrong count.

- [ ] **Step 3: For the apex.json `rejected` failure** — render the apex-dense fixture and read the rejection reasons:
```bash
cd /Users/utkarsh/Projects/richard/dmc-renderer
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib ../research/v7-renderer/.venv/bin/python -m pytest \
  tests/test_calibration_fixtures.py::test_materially_different_clients_produce_distinct_plans_and_pdfs -x 2>&1 | tail -20
```
The rejection is either a real hard failure (fix the fixture/code — do not weaken the gate) or a stale expectation (the A4→spread migration legitimately changed the release path). Determine which with evidence, then fix the correct side.

- [ ] **Step 4: Fix the remaining failures the same way** — each either a fixture/test drift or a real regression. If real, fix the code per the component's contract.

- [ ] **Step 5: Full dmc-renderer suite to 0 failed**

```bash
cd /Users/utkarsh/Projects/richard/dmc-renderer
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib ../research/v7-renderer/.venv/bin/python -m pytest tests/ -q 2>&1 | tail -3
```

- [ ] **Step 6: Annotate the stale docs (closes D2)** — add a dated supersede banner to `docs/phase-zero/V3-MIGRATION-READINESS-v2.md` and `HARDENING-PROGRESS-2026-08-05.md` pointing to the baseline ledger: "all-green claims superseded 2026-08-13; the dmc-renderer suite had 9 failures realigned in T0.3."

## Task 0.4: Write the honest baseline ledger

**Files:**
- Create: `docs/phase-zero/BASELINE-LEDGER-2026-08-13.md`

- [ ] **Step 1: Create the ledger** recording, as of today, the exact post-fix counts: renderer suite, preprocessor suite (currently 731 pass), dmc-renderer suite, guard battery (45), and the two offline harnesses. State explicitly: "CODEX-HANDOFF's 15/342, phase-zero's 15/352, and V3-MIGRATION-READINESS-v2's 'all green' are ALL SUPERSEDED by this ledger."

- [ ] **Step 2: Re-run all five commands from the Standing Verification block** and paste the exact tail line of each into the ledger.

- [ ] **Step 3: Annotate the stale handoff (closes D1)** — add a dated supersede note to `CODEX-HANDOFF.md` §7 and the phase-zero docs: the "15 failed/342 passed" and "15 failed/352 passed" counts are stale; the authoritative baseline is this ledger (post T0.1–T0.3, expected 0 failures across renderer + dmc-renderer suites).

---

# PHASE 1 — Make per-client variation actually fire

**Why:** G1 is the owner's #1 recorded complaint ("every client looks identical"). The axes system is built but dead because no fixture sets `brand_profile_id`.

## Task 1.1: Wire brand_profile_id through the calibration envelopes + a rendered-proof test

**Files:**
- Modify: `dmc-renderer/calibration_fixtures_v3.py` (envelope build at :272-305 and recipe assembly at :361-372; second envelope at :1852-1864)
- Modify: `dmc-renderer/calibration_fixtures_v3.py` profile dicts (each profile declares its profile_id)
- Modify: `dmc-renderer/build_v3.py:546` (already reads it — verify, do not change unless broken)
- Test: `dmc-renderer/tests/test_brand_profile_fires.py` (NEW)
- Test: `research/preprocessor/tests/test_brand_profile_reaches_render_v3.py` (extend — currently only asserts the kwarg exists, NOT that it fires)

Available profiles (verified in `research/v7-renderer/tokens/brand-profiles.json`): `geva, aerz, nikl, alex, buch`. The calibration visual_brand values (`apex-blau-tinte`, etc.) must map deterministically to a profile id.

- [ ] **Step 1: Write the failing test first** — prove that two materially different calibration fixtures resolve DIFFERENT brand profiles and DIFFERENT body `data-` attributes:

```python
# dmc-renderer/tests/test_brand_profile_fires.py
"""A profile that is read but never fed to a fixture is still dead.

This test closes G1: `build_v3` reads `envelope.brand_profile_id`, but no
calibration envelope ever set it, so every client rendered on default axes.
"""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / ".." / "research" / "v7-renderer"))

FIXTURE_ROOT = ROOT / "fixtures" / "calibration"

from calibration_fixtures_v3 import envelope_for_profile  # noqa: E402
from tokens.brand_profile import profile_for  # noqa: E402


def _profiles():
    manifest = json.loads((FIXTURE_ROOT / "manifest.json").read_text())
    for entry in manifest["fixtures"]:
        yield json.loads((FIXTURE_ROOT / entry["path"]).read_text())


def test_calibration_fixtures_declare_distinct_profiles() -> None:
    ids = []
    for profile in _profiles():
        env = envelope_for_profile(profile, Path("/tmp/dmc-assets"))
        assert env.get("brand_profile_id"), f"{profile['fixture_id']} declares no brand_profile_id"
        ids.append(env["brand_profile_id"])
    assert len(set(ids)) > 1, "every fixture resolving to one profile means axes are not firing"


def test_declared_profile_id_resolves_and_has_data_attributes() -> None:
    profile = next(_profiles())
    env = envelope_for_profile(profile, Path("/tmp/dmc-assets"))
    brand_profile = profile_for(env["brand_profile_id"])
    assert brand_profile.data_attributes(), "profile emits no body data-attrs -> axes.css can never match"
```

Note: the fixture profile table lives in `dmc-renderer/fixtures/calibration/*.json` (one per fixture, registered in `manifest.json`); `envelope_for_profile(profile, asset_dir)` at `calibration_fixtures_v3.py:351` dispatches apex-dense to `apex_dense_envelope`. The task must (a) add a `profile_id` key to each fixture JSON mapping it to one of the five real profiles in `research/v7-renderer/tokens/brand-profiles.json` (`geva, aerz, nikl, alex, buch`), (b) set `envelope["brand_profile_id"] = profile["profile_id"]` inside `envelope_for_profile` AND `apex_dense_envelope` (both currently lack it), and (c) verify every `deepcopy`-mutated recipe inherits it.

- [ ] **Step 2: Run it — expect FAIL**

```bash
cd /Users/utkarsh/Projects/richard/dmc-renderer
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib ../research/v7-renderer/.venv/bin/python -m pytest \
  tests/test_brand_profile_fires.py -q
```

- [ ] **Step 3: Add a `brand_profile_id` to each calibration profile** in `calibration_fixtures_v3.py`'s profile table (e.g. map each fixture to one of the five real profiles deterministically — craft-trade→geva, medical-practice→aerz, apex-dense→nikl, or add the mapping as a `profile_id` key per fixture). Pass it into the envelope at :272-305 and the second envelope at :1852-1864, and into `envelope["brand_profile_id"]` for every recipe (the `christoph-known-failures`/`missing-proof` mutated copies must inherit it via `deepcopy` — verify).

- [ ] **Step 4: Wire it into build_v3** — confirm `build_v3.py:546` reads `envelope.get("brand_profile_id")`; if the envelope keys it under a different name, align. Do not change the read logic if it is already correct.

- [ ] **Step 5: Run the new test + the existing profile test**

```bash
cd /Users/utkarsh/Projects/richard/dmc-renderer
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib ../research/v7-renderer/.venv/bin/python -m pytest \
  tests/test_brand_profile_fires.py -q
cd /Users/utkarsh/Projects/richard/research/preprocessor
.venv/bin/python -m pytest tests/test_brand_profile_reaches_render_v3.py -q
```

- [ ] **Step 6: RENDERED proof (the real gate)** — render two materially different calibration fixtures end to end and confirm their rendered CSS `body` carries DIFFERENT `data-` attributes and different `--accent`/`--color-*`:

```bash
cd /Users/utkarsh/Projects/richard/dmc-renderer
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib ../research/v7-renderer/.venv/bin/python -c "
import json
from pathlib import Path
import sys
sys.path.insert(0, '.')
from calibration_fixtures_v3 import envelope_for_profile
from build_v3 import build_and_render_v3
root = Path('fixtures/calibration')
manifest = json.loads((root / 'manifest.json').read_text())
for entry in manifest['fixtures']:
    profile = json.loads((root / entry['path']).read_text())
    if profile['fixture_id'] in ('calibration.craft-trade', 'calibration.medical-practice'):
        env = envelope_for_profile(profile, Path('/tmp/dmc-assets'))
        out = build_and_render_v3(env, output_dir=Path('/tmp/dmc-profile-' + profile['fixture_id']))
        print(profile['fixture_id'], '->', env.get('brand_profile_id'))
"
# then grep the two report.rendered.html for data-belief-treatment / data-image-modes
grep -o 'data-belief-treatment="[^"]*"\|data-image-modes="[^"]*"' /tmp/dmc-profile-calibration.craft-trade/report.rendered.html | head -1
grep -o 'data-belief-treatment="[^"]*"\|data-image-modes="[^"]*"' /tmp/dmc-profile-calibration.medical-practice/report.rendered.html | head -1
```
Expected: the two `data-` attribute values DIFFER. If they match, the profile is still not flowing — debug the envelope→bundle→`data_attributes()` chain until they differ.

- [ ] **Step 7: Full dmc-renderer + preprocessor suites stay green**

```bash
cd /Users/utkarsh/Projects/richard/dmc-renderer
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib ../research/v7-renderer/.venv/bin/python -m pytest tests/ -q 2>&1 | tail -2
cd /Users/utkarsh/Projects/richard/research/preprocessor && .venv/bin/python -m pytest tests -q 2>&1 | tail -2
```

- [ ] **Step 8: Update the baseline ledger** — mark G1 CLOSED with the rendered proof (the two differing data-attr lines).

- [ ] **Step 9: Annotate the stale memory (closes D3)** — the worktree memory `work_status.md` (2026-08-08) still says "render_v3.py calls compile_tokens with ZERO arguments." Append a dated note: "FIXED in code 2026-08-10+ (brand_profile.py, brand-profiles.json, render_v3.py:179-191); the remaining defect was that no fixture set brand_profile_id — closed 2026-08-13 by T1.1."

---

# PHASE 2 — Re-wire the live path (the "system does it" fixes)

## Task 2.1: Make plan_social run on every live render

**Files:**
- Modify: `dmc-renderer/build_live.py` (:1136-1146 route_package call)
- Modify: `research/preprocessor/stages/route_package.py` (verify the manifest gate and what happens when manifest=None)
- Modify: `dmc-renderer/synthesize_visuals.py` or the social wiring (`route_package` is gated on `manifest is not None` at route_package.py:44)
- Test: `dmc-renderer/tests/test_plan_social_live.py` (NEW)

- [ ] **Step 1: Write the failing test** — assert that a live `build_live` render path builds a classified manifest from `client_assets/<slug>/ig/` (the persisted IG pool documented in CONTEXT.md) and calls `route_package` with it, OR fails loudly when it cannot:

```python
# dmc-renderer/tests/test_plan_social_live.py
"""G3: social routing must run on the live path, not only the fixture."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from build_live import _build_social_manifest  # noqa: E402


def test_live_build_derives_a_manifest_from_client_ig_dir(tmp_path) -> None:
    ig = tmp_path / "ig"
    ig.mkdir()
    (ig / "jousefmrd_1.jpg").write_bytes(b"fake")
    (ig / "jousefmrd_2.jpg").write_bytes(b"fake")
    manifest = _build_social_manifest(ig)
    assert manifest is not None
    assert len(manifest.assets) >= 2


def test_live_build_without_ig_dir_does_not_silently_pass() -> None:
    manifest = _build_social_manifest(Path("/tmp/does-not-exist-ig"))
    # either a real manifest (empty) or an explicit None that route_package
    # treats as "social skipped LOUDLY", never a silent swallow
    assert manifest is not None or True  # replaced by the concrete contract below
```

- [ ] **Step 2: Run it — expect FAIL** (the helper does not exist).

- [ ] **Step 3: Implement `_build_social_manifest`** in `build_live.py` — scan `<client_dir>/ig/` for the classified asset manifest (the `asset_manifest.json` pattern already proven in `fixtures/apex/asset_manifest.json` + `plan_social`), and pass it to `route_package(..., manifest=..., ...)` at :1137.

- [ ] **Step 4: Make the :1146 except block honest** — split it: only "no assets present" may log `skipped offline`; ANY other exception must propagate (or be logged at ERROR + surfaced in the response). It currently swallows dark-divider cadence + plan_diagrams too.

- [ ] **Step 5: Wire `design_brief`** (G19) — `envelope_to_render_request` at build_live.py:784-801 must set `client.design_brief` from the envelope when present, so fal prompts stop defaulting.

- [ ] **Step 6: Run the new test + the existing plan_social + preprocessor suites**

```bash
cd /Users/utkarsh/Projects/richard/dmc-renderer
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib ../research/v7-renderer/.venv/bin/python -m pytest \
  tests/test_plan_social_live.py -q
cd /Users/utkarsh/Projects/richard/research/preprocessor
.venv/bin/python -m pytest tests -q 2>&1 | tail -2
```

- [ ] **Step 7: Rendered proof** — render the christoph fixture via `render_christoph.py` and confirm a testimonial/breather/case-study-phone binding appears on the page that the fixture previously only showed hand-placed. Screenshot the page and record in the ledger.

## Task 2.2: Restore the copy→device mapping in v3 (the writer's 11 visual keys)

**Files:**
- Modify: `research/preprocessor/pipeline_v3.py` (or a NEW `research/preprocessor/stages/visual_key_mapping_v3.py`)
- Modify: `research/preprocessor/contracts_v3/render_contract.py` (consume the mapped device specs)
- Modify: `research/v7-renderer/families/viz_bridge.py` (existing bridge: v3 typed elements → v2 presets — extend it to the 11 keys)
- Test: `research/preprocessor/tests/test_visual_key_mapping_v3.py` (NEW)

**Why:** v2 proves the mapping (build_live `_normalize_page_data` → `_role_devices`); v3 dropped it entirely. Every writer key the schema node emits must reach a device kind.

- [ ] **Step 1: Write the failing test** — for each of the 11 keys, a synthetic page carrying that key must produce a typed element in the render contract:

```python
# research/preprocessor/tests/test_visual_key_mapping_v3.py
"""G4: v3 must read the writer's visual keys, like v2 does."""
from visual_key_mapping_v3 import map_visual_keys_to_elements


def test_every_writer_visual_key_maps_to_a_typed_element() -> None:
    for key in ("kennzahlen", "fakten", "vorher_nachher", "anteil", "kostenrechnung",
                "rechnung", "kategorien", "zusammensetzung", "verlauf",
                "entitaeten", "bildwunsch"):
        elements = map_visual_keys_to_elements(key, _sample_for(key))
        assert elements, f"{key} maps to nothing"


def test_figures_remain_verbatim_and_grounded() -> None:
    # the figure must appear verbatim; the mapping must not invent numbers
    ...
```

- [ ] **Step 2: Run it — expect FAIL** (module does not exist).

- [ ] **Step 3: Implement `map_visual_keys_to_elements`** — port the v2 role→device logic (build_live `_role_devices` + the ROLE-DEVICE-CONTRACT table) into a pure v3 mapper that emits `render_contract.py` element kinds, keeping the no-fabrication rule (printed value = the key's figure verbatim; geometry derived from it). Wire it into `materialize_render_contract_v3` (or `plan_compositions_v3`) so real envelopes flow.

- [ ] **Step 4: Wire the schema side** — confirm `resolve-schema-node-v5.js` still emits the 11 keys (it does per the 2026-07-16 work) and that the adapter v3 path carries them.

- [ ] **Step 5: Run the new test + renderer + preprocessor suites**

```bash
cd /Users/utkarsh/Projects/richard/research/preprocessor
.venv/bin/python -m pytest tests/test_visual_key_mapping_v3.py tests -q 2>&1 | tail -2
cd /Users/utkarsh/Projects/richard/research/v7-renderer
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python -m pytest tests/ -q 2>&1 | tail -2
```

- [ ] **Step 6: Rendered proof** — a fixture with a `fakten` row and a `verlauf` series must render an icon-stat row + column chart in the PDF pixels. Record in the ledger.

## Task 2.3: Emit `kunde.name`/`kunde.company_url` (G5)

**Files:**
- Modify: `docs/resolve-schema-node-v5.js:249-252` (add `name`, `company_url` sub-keys; resolve the VERIFY comments)
- Modify: `dmc-renderer/build_live.py` (carry `kunde.name`/`company_url` through `_normalize_page_data`; add to the ST-07A branch)

- [ ] **Step 1: Update the schema node** — add `{ key: "name", max: 60, desc: "Customer name from DATA." }` and `{ key: "company_url", max: 120, desc: "Customer company URL from DATA." }` to the `kunde` fields; delete the two VERIFY hedges.

- [ ] **Step 2: Verify the adapter carries them** — `build_live.py` currently never touches `kunde`. Add the passthrough (the adapter does not strip unknown keys, but the ST-07A branch at :333-350 folds page data — verify `kunde` survives intact).

- [ ] **Step 3: Extend `verify_contract_fixes.py`** with a passthrough check for `kunde.name`/`company_url`; run it (expect 10/10 + the new checks green).

- [ ] **Step 4: Render proof** — christoph deck: a case-study page shows the customer name + URL in the person block. Record in ledger.

## Task 2.4: ST-08 must not fatal the n8n workflow (G6)

**Files:**
- Modify: `docs/resolve-schema-node-v5.js` (add an ST-08 entry so `resolveSchemaItems` no longer throws)
- Modify: `research/v7-renderer/patterns/st_08.py` (verify it reads keys the schema will emit)

- [ ] **Step 1: Add the ST-08 schema entry** — mirror the ST-14/Q&A shape (ST-08 is the FAQ/objection page): `headline`, `intro`, `qa_pairs: [{frage, antwort}]` (German keys matching what `st_08.py` reads — read st_08.py first).

- [ ] **Step 2: Verify st_08.py reads exactly those keys** — align names if the pattern differs.

- [ ] **Step 3: Test the schema node resolves** — run the node's JS test harness (docs/n8n/tests) and confirm ST-08 resolves without throwing.

## Task 2.5: Kill the invisible `fazit_background` spend (G7)

**Files:**
- Modify: `research/preprocessor/stages/generate_assets.py:71-75` (remove the ST-FAZIT background from the generation/download set, OR wire a real consumer)
- Modify: `research/v7-renderer/patterns/st_fazit.py` + `templates/st_fazit.html.jinja` (IF keeping the asset: resolve it like st_31 does for its ground)

Decision rule: an asset with no consumer is waste. Either (a) wire `st_fazit.py` to read the page's `fazit_background` asset as its ground (mirror `st_31.py`'s `_PHOTO_GROUND_TYPES`), or (b) remove the slot. Prefer (a) — the ST-FAZIT closing page is a designed dark close and a real ground would improve it.

- [ ] **Step 1: Decide (a) or (b) with evidence** — read `st_fazit.py` + `st_fazit.html.jinja`; if a ground slot is cheap, wire it; else remove the slot from `generate_assets.py` skip/slots.

- [ ] **Step 2: Implement, then render the ST-FAZIT page and verify** (ground paints OR no fal call fires for it). Record in ledger.

---

# PHASE 3 — Harden the service

## Task 3.1: Authenticate all endpoints (G8)

**Files:**
- Modify: `dmc-renderer/service.py` (all render routes + health-exempt)

- [ ] **Step 1: Add a shared-secret check** — a `@app.middleware("http")` that requires `Authorization: Bearer ${RENDERER_SHARED_SECRET}` on `/render`, `/render-v3`, `/render-legacy-v2` (401 otherwise), while exempting `/health`, `/health/v3`. Read the secret from `os.environ` with the `_env_or_dotenv` fallback (build_live.py:82-97 pattern).

- [ ] **Step 2: Test it** — extend `dmc-renderer/tests/test_service_v3.py` with an unauthenticated-401 case and an authenticated-200 case (using the TestClient + a fake key).

- [ ] **Step 3: Run the service tests.** Record in ledger. (Note: the container smoke `scripts/smoke_v3_container.sh` must set the env var — update it.)

## Task 3.2: Enforce a real end-to-end timeout (G9 + G21)

**Files:**
- Modify: `dmc-renderer/service.py` (:461 render_endpoint sync def)

- [ ] **Step 1: Make the render endpoint honor a hard cap** — wrap the render in an async def with `asyncio.wait_for(..., timeout=cfg.render_timeout_s)` (default 120), or run the sync build in a worker with a watchdog that cancels the request after 120s and returns a 504. At minimum, an explicit `X-Render-Deadline` enforcement must exist.

- [ ] **Step 2: Also bound the fal/LLM stages** — verify httpx timeouts are set (240s fal, 40s LLM already exist) and add a total-budget guard so N parallel fal calls cannot exceed the cap.

- [ ] **Step 3: Test** — a test that a fake slow build raises a timeout error (monkeypatch the build to sleep past the cap) and the endpoint returns 504/422, not a hung worker.

- [ ] **Step 4: Update ARCHITECTURE.md/CACHE_STRATEGY.md** to state the REAL timeout policy (closes D6: the "120s hard cap, enforced by the renderer" claim is now true). Record in ledger.

## Task 3.3: Restore determinism (G10)

**Files:**
- Modify: `research/preprocessor/stages/assemble_package.py:333`
- Modify: `dmc-renderer/service.py` (timestamp seeding)

- [ ] **Step 1: Replace `datetime.now(timezone.utc)` with a seeded value** — derive `generated_at` from the report id hash (deterministic), OR make it an explicit parameter so re-rendering the same input yields identical package bytes.

- [ ] **Step 2: Re-seed the PDF creation timestamp** in the Chromium path (was WeasyPrint `--info-create-date`; now gone). Verify what Chromium/Playwright writes and stamp the trailer deterministically from `report_id` (via fitz/pikepdf post-pass).

- [ ] **Step 3: Test** — render the same fixture twice, compare package + PDF bytes (allow only the known font-subset delta if still present; document it). Record in ledger.

- [ ] **Step 4: Annotate the stale docs (closes D5)** — add a dated supersede banner to `dmc-renderer/docs/ARCHITECTURE.md:13,31` and `docs/n8n/CACHE_STRATEGY.md`: the "same input → byte-identical PDF seeded from report_id" claim is only true once T3.3 lands; before that the package embeds `datetime.now()`.

---

# PHASE 4 — Harden grounding / fabrication

## Task 4.1: Fix the digit-collapse and add label/unit grounding (G17)

**Files:**
- Modify: `dmc-renderer/synthesize_visuals.py` (`_digit_tokens` :39-47, `_ground_device` :94-119, `digit_key` :86-91)

- [ ] **Step 1: Write the failing test** — "12,5" must NOT ground "125", and "2 Stunden" must NOT ground "2 h":

```python
# dmc-renderer/tests/test_grounding_decimal_and_units.py
"""G17: the grounding gate must not collapse decimals or ignore units."""
from synthesize_visuals import _digit_tokens, _ground_device


def test_decimal_is_not_collapsed() -> None:
    assert "125" not in _digit_tokens("12,5")


def test_label_and_unit_are_checked() -> None:
    # a device that swaps the unit must be rejected even if digits match
    ...
```

- [ ] **Step 2: Run it — expect FAIL.**

- [ ] **Step 3: Fix `_digit_tokens`** to keep the decimal separator significant (tokenize "12,5" as one token, not "125"), and extend `_ground_device` to require the label/unit tokens to appear in the page copy (not just the digits).

- [ ] **Step 4: Also fix the `digit_key` unit-class quirk** (:86-91: currency produces an empty unit class → "40 €" == "40" collide; and "2 Std." vs "2 Stunden" evade dedup) — normalize unit spellings.

- [ ] **Step 5: Run the new + existing synthesize_visuals tests.** Record in ledger.

---

# PHASE 5 — Dead code, invisible spend, semantic mislabels

## Task 5.1: Bind one-figure-one-device across ALL role devices (G11 + G12)

**Files:**
- Modify: `dmc-renderer/build_live.py` (`_role_devices` :672-769; `kz_donuts` :506-522)

- [ ] **Step 1: Write failing tests** — a figure already claimed by a donut must not re-appear in a `verlauf`/`rechnung` device (G11), and a figure in a `stats` rail must not also become a `kz_donuts` donut (G12).

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Make `claimed` bind across all role branches** and make `kz_donuts` check `_stat_keys()` too.

- [ ] **Step 4: Run the new tests + preprocessor suite.** Record in ledger.

## Task 5.2: Fix the semantic mislabels (G13, G14, G22)

**Files:**
- Modify: `dmc-renderer/build_live.py:232-233` (G13: `ausblick_punkte` → a real takeaways field, not `zielgruppe`)
- Modify: `research/v7-renderer/patterns/st_02.py:54` (G13: read the corrected field / label "Was Sie mitnehmen" not "Zielgruppe des Reports")
- Modify: `dmc-renderer/build_live.py` (G14: map `kosten_des_nichtstuns` onto the treated ST-FAZIT path OR make the treated template read it)
- Modify: `dmc-renderer/build_live.py:173-184,639` (G22: exempt `author.name`/`kunde.name` from the umlaut rewrite — apply only to prose fields)

- [ ] **Step 1: Write failing tests for each** (an ST-02 with takeaways must NOT label them Zielgruppe; an ST-FAZIT with `kosten_des_nichtstuns` must render the cost block in the treated path; a founder name "Waehrend" must survive the umlaut pass).

- [ ] **Step 2: Implement each fix.** G13 needs a schema-node addition too (`docs/resolve-schema-node-v5.js` ST-02 section) — add `takeaways` and keep `zielgruppe` distinct.

- [ ] **Step 3: Render ST-02 + ST-FAZIT and verify on pixels.** Record in ledger.

## Task 5.3: Stop silent alias swallowing + extend the no-hex guard (G15, G16, D4)

**Files:**
- Modify: `dmc-renderer/build_live.py` (`_normalize_page_data`)
- Modify: `research/v7-renderer/tests/test_no_literals_in_architecture.py` (extend to scan `dmc-renderer/`)
- Modify: `dmc-renderer/build_live.py:788-790`, `build_v3.py:148` (replace raw hex with token/constant references)

- [ ] **Step 1: Extend the guard** to scan `dmc-renderer/*.py` (excluding `render_christoph.py`/`render_cover_check.py` which are fixtures by intent — move them under a fixtures dir or an explicit allowlist).

- [ ] **Step 2: Run it — expect it to flag build_live.py:788-790 + build_v3.py:148** (the hex fallbacks). Replace with named constants (e.g. a `FALLBACK_BRAND` dict in a tokens module) so the guard passes and the rule is enforced repo-wide.

- [ ] **Step 3: Add alias logging to `_normalize_page_data`** — log (WARNING) every alias applied and every unmapped key, so silent schema drift surfaces in the render log.

- [ ] **Step 4: Run the guard + full renderer suite.** Record in ledger.

## Task 5.4: Scene filtering, page-count snap, layout-variant sources (G18, G20, G23)

**Files:**
- Modify: `research/v7-renderer/treatment_engine.py:367-373` (G18: `_scene_uri` must accept `status in {"generated","downloaded"}` so client-supplied scenes paint)
- Modify: `dmc-renderer/build_live.py:859-868` (G20: surface the page-count snap in the response/headers, not just a deep warning)
- Modify: `dmc-renderer/build_live.py:821` + `research/preprocessor/stages/plan_layout.py:75-77,176-177` + `route_package.py:91-93` (G23: single source of truth for ST-07B `layout_variant="fill"` + `page_mode`)

- [ ] **Step 1: Write failing tests** (scene with `downloaded` status paints; page-count snap emits a header; ST-07B variant comes from ONE source).
- [ ] **Step 2: Implement each.**
- [ ] **Step 3: Run the affected suites + render ST-09 (scene) and ST-07B (variant) on pixels.** Record in ledger.

## Task 5.5: Low-severity cleanup (L1–L7)

**Files:** as listed in each item below.
- [ ] **Step 1: L1** — `verify_contract_fixes.py:84-85`: remove the `teaser_items` passthrough check (schema removed it) or repoint it to a real key.
- [ ] **Step 2: L2** — `st_06.py:73`: delete the `if False else None` dead expression.
- [ ] **Step 3: L3** — delete the unreachable LLM-donut branch (`synthesize_visuals.py:383-392`) and dead `_adapt_cta_hard` (`treatment_engine.py:692-698`); if the LLM donut path is intended for the future, keep it behind an explicit flag with a comment.
- [ ] **Step 4: L4** — move `render_christoph.py`/`render_cover_check.py` client literals under a fixtures-style allowlist or a fixtures dir (they are standing harnesses, not production logic).
- [ ] **Step 5: L5** — `service.py:474`: sanitize exception text (strip absolute paths) before returning.
- [ ] **Step 6: L6** — `_env_or_dotenv`: parse `.env` with `split("=", 1)` already? Verify; if not, fix so values containing `=` parse correctly.
- [ ] **Step 7: L7** — `service.py:258`: replace the private `_non_numeral_stat_values` import with the public API (or a local implementation).
- [ ] **Step 8: Full suites green; update ledger.**

---

# PHASE 6 — The standing assessment harness (your #1 pain point)

**Why this phase exists:** every prior gap closed in this repo was closed in code and then silently reopened because nothing re-checked it. This phase makes assessment the standing loop, so "MD files created but never assessed" cannot happen again.

## Task 6.1: Build the closed-gap assessment harness

**Files:**
- Create: `research/quality_loop/assess_closed_gaps.py`
- Create: `research/quality_loop/closed_gaps_registry.json`
- Test: `research/quality_loop/tests/test_assess_closed_gaps.py`

The registry is a JSON list of every gap G1–G24/L1–L7/D1–D6 with: id, description, the check type (suite-count / grep / test-name / render-proof), the exact check command or python predicate, and the current status. The harness runs every check and prints a PASS/FAIL table plus an overall exit code (0 = all closed).

- [ ] **Step 1: Create `closed_gaps_registry.json`** — one entry per gap. Each check is one of:
  - `suite`: run a pytest file and assert 0 failures (e.g. G2 → `research/v7-renderer/tests/`),
  - `grep`: assert a symbol is present/absent in a file (e.g. G4 → grep the v3 pipeline for `kennzahlen`),
  - `test`: run a named test (e.g. G1 → `test_brand_profile_fires.py`),
  - `render`: a recorded render-proof (path to the PNG + the expected pixel fact).

- [ ] **Step 2: Implement `assess_closed_gaps.py`** — load the registry, run each check, print the table, exit non-zero on any failure. It must be runnable from any cwd (absolute path resolution) and must NOT require network or API keys.

- [ ] **Step 3: Write the test** — the harness runs against the registry and reports honestly (a gap marked closed whose check fails is reported as REOPENED).

- [ ] **Step 4: Wire it as the standing gate** — add it to the container smoke (`scripts/smoke_v3_container.sh`) after the render, and document the one command in the baseline ledger:
```bash
cd /Users/utkarsh/Projects/richard/dmc-renderer
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib ../research/v7-renderer/.venv/bin/python \
  ../research/quality_loop/assess_closed_gaps.py
```

## Task 6.2: Make the plan itself assessed

- [ ] **Step 1: Add a status column to the gap register** (top of this file) that is updated as each task closes, and cross-link each gap's closing task number.

- [ ] **Step 2: Commit the baseline ledger + this plan into the standing docs** — the ledger's Step-2 rerun becomes the "assess" half of the loop: every future session STARTS by running `assess_closed_gaps.py` and the baseline-ledger commands, and only works on what fails.

---

## Execution order summary (do not reorder)

1. Phase 0 (T0.1 → T0.4): suites honest.
2. Phase 1 (T1.1): client variation fires, with rendered proof.
3. Phase 2 (T2.1 → T2.5): live-path rewiring.
4. Phase 3 (T3.1 → T3.3): service hardening.
5. Phase 4 (T4.1): grounding hardening.
6. Phase 5 (T5.1 → T5.5): dead code + mislabels.
7. Phase 6 (T6.1 → T6.2): standing assessment — the loop that keeps all of the above closed.

## Definition of done (the whole program)

- Renderer suite: **0 failed**. Preprocessor: **731+ passed**. dmc-renderer: **0 failed**. Guard battery: **45+ passed**. Both offline harnesses: green.
- Two materially different calibration fixtures produce **different rendered axes and different accents** (G1 rendered proof).
- A live `build_live` render runs `plan_social` (G3), and a v3 envelope carrying `fakten` renders an icon-stat row (G4).
- Every endpoint except health requires auth (G8); a render cannot exceed the timeout cap (G9); same input → same bytes (G10).
- `assess_closed_gaps.py` exits 0 with every gap CLOSED, and is wired into the container smoke.
- The baseline ledger + this plan's register are the standing entry point; nothing is marked done without its render-proof or suite line.
