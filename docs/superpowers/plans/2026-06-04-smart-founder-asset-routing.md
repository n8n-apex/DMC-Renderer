# Smart Founder Asset Understanding & Routing — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use `- [ ]`. **NO GIT** (checkpoint = full preprocessor suite green). Activate the preprocessor venv (`cd research/preprocessor && source .venv/bin/activate`). **No real network in the unit suite** — the VIS classifier sits behind an injectable client with a Fake; one opt-in env-gated live test. Brand-agnostic: no client literals in logic; the guard test must stay green. Never fabricate — a report element with no suitable real asset is FLAGGED.

**Goal:** Generalize the founder-asset scraper from fixed-slot filling into a Perception→Analysis→Routing pipeline: harvest a rich pool, VIS-classify each asset's *role* + *visual appeal*, and route each to the report element where it adds the most appeal (real "founder-at-device" photos fill the working/device role directly — no synthetic frames).

**Architecture:** new `classifier.py` (VIS asset classifier, injectable, Fake for tests) + `router.py` (pure role→element routing with DET cross-checks, best-appeal-first, de-dup, flag-on-empty) → orchestrator generalized to scrape→perceive→classify→route→place via the proven `slot_bridge` (drive elements) + an AssetResult emission for the `device_mockup` composite element. Per `docs/superpowers/specs/2026-06-04-founder-social-mockup-design.md`.

**Tech:** existing OpenRouter VIS client pattern (sync httpx, lazy), Pydantic v2 models, OpenCV/Pillow DET signals (already built in `selector.py`).

---

### Task 1 — Models: AssetJudgement + RoutedElement
**Files:** Create/extend `stages/scrape_founder_assets/models.py`; Test `stages/scrape_founder_assets/tests/test_asset_models.py`.

- [ ] **Step 1: Write the failing test**
```python
from stages.scrape_founder_assets.models import AssetJudgement, RoutedElement, ASSET_ROLES

def test_asset_judgement_defaults_and_roles():
    j = AssetJudgement(role="founder_working", has_overlaid_text=False, visual_appeal=3)
    assert j.role == "founder_working" and j.visual_appeal == 3 and j.notes == ""
    assert "founder_portrait" in ASSET_ROLES and "content_card" in ASSET_ROLES

def test_routed_element_shape():
    r = RoutedElement(element="cover_hero", status="filled", path="/x.jpg", role="founder_portrait", appeal=3)
    assert r.status == "filled" and r.role == "founder_portrait"
    r2 = RoutedElement(element="team", status="flagged", reason="no suitable asset")
    assert r2.status == "flagged" and r2.path is None
```
- [ ] **Step 2: Run → FAIL** (`python -m pytest stages/scrape_founder_assets/tests/test_asset_models.py -q`) — ImportError.
- [ ] **Step 3: Implement** in `models.py`:
```python
from typing import Literal, Optional
ASSET_ROLES = (
    "founder_portrait", "founder_working", "founder_speaking", "group_team",
    "lifestyle", "content_card", "logo", "other",
)
AssetRole = Literal[
    "founder_portrait", "founder_working", "founder_speaking", "group_team",
    "lifestyle", "content_card", "logo", "other",
]

class AssetJudgement(BaseModel):
    model_config = _Permissive
    role: AssetRole
    has_overlaid_text: bool = False
    visual_appeal: int = 0  # 0-3
    notes: str = ""

class RoutedElement(BaseModel):
    model_config = _Permissive
    element: str
    status: Literal["filled", "flagged"]
    path: Optional[str] = None
    role: Optional[str] = None
    appeal: Optional[int] = None
    reason: Optional[str] = None
```
- [ ] **Step 4: Run → PASS.** Checkpoint: `python -m pytest stages/scrape_founder_assets/tests -q`.

---

### Task 2 — VIS asset classifier (injectable, Fake, fail-closed)
**Files:** Create `stages/scrape_founder_assets/classifier.py`; Test `tests/test_classifier.py`.

- [ ] **Step 1: Write the failing test**
```python
from stages.scrape_founder_assets.classifier import (
    FakeAssetClassifier, classify_asset, _CLASSIFY_PROMPT, AssetClassifierClient,
)
def test_classify_returns_role_and_appeal():
    fake = FakeAssetClassifier({"role": "founder_working", "has_overlaid_text": False, "visual_appeal": 3, "notes": "at a laptop"})
    j = classify_asset("/x.jpg", fake)
    assert j.role == "founder_working" and j.visual_appeal == 3

def test_classify_fails_closed_on_error():
    class Boom:
        def classify(self, p): raise RuntimeError("vision down")
    j = classify_asset("/x.jpg", Boom())
    assert j.role == "other" and j.visual_appeal == 0  # never raises, never a confident role

def test_prompt_is_brand_agnostic_and_role_aware():
    p = _CLASSIFY_PROMPT.lower()
    assert "role" in p and "overlaid" in p and "ignore brand" in p
    for r in ("founder_working", "founder_speaking", "content_card"):
        assert r in _CLASSIFY_PROMPT
```
- [ ] **Step 2: Run → FAIL** (ImportError).
- [ ] **Step 3: Implement** `classifier.py` mirroring `quality_gate.RealVisionGate` (sync httpx lazy import, OPENROUTER key/model from settings/env, fenced-JSON tolerant parse). Define `_CLASSIFY_PROMPT` (brand-agnostic; asks for the JSON `{role, has_overlaid_text, visual_appeal 0-3, notes}` choosing role from the ASSET_ROLES list; "judge what the image DEPICTS + quality; ignore brand identity"). `AssetClassifierClient` Protocol (`classify(path)->dict`); `FakeAssetClassifier` (single dict | by-path | sequence, records calls); `RealAssetClassifier`; `classify_asset(path, client) -> AssetJudgement` wrapping in try/except → `AssetJudgement(role="other", visual_appeal=0, notes=f"classifier error: {exc}")`.
- [ ] **Step 4: Run → PASS.** Checkpoint.

---

### Task 3 — Router: role → report element (pure, DET-guarded, de-duped)
**Files:** Create `stages/scrape_founder_assets/router.py`; Test `tests/test_router.py`.

- [ ] **Step 1: Write the failing test**
```python
from stages.scrape_founder_assets.router import route_assets, ROLE_TO_ELEMENTS, ELEMENT_PRIORITY
from stages.scrape_founder_assets.models import Candidate, AssetJudgement

def _c(p, src="instagram"): return Candidate(source=src, kind="post", local_path=p, width=1080, height=1350)
class _Det:  # stand-in DET score
    def __init__(self, frontal=True, pc=True, faces=1): self.frontal=frontal; self.print_capable=pc; self.faces=faces

def test_routes_by_role_best_appeal_first_with_dedup():
    items = [
        (_c("/p1.jpg"), _Det(), AssetJudgement(role="founder_portrait", visual_appeal=3)),
        (_c("/p2.jpg"), _Det(), AssetJudgement(role="founder_portrait", visual_appeal=2)),
        (_c("/w1.jpg"), _Det(), AssetJudgement(role="founder_working", visual_appeal=3)),
    ]
    out = route_assets(items)
    by_el = {r.element: r for r in out}
    assert by_el["cover_hero"].path == "/p1.jpg"          # best-appeal portrait
    assert by_el["about_portrait"].path == "/p2.jpg"        # de-dup -> next portrait
    assert by_el["device_mockup"].path == "/w1.jpg"         # working photo -> device/working role
    assert by_el["cover_hero"].path != by_el["about_portrait"].path

def test_portrait_element_requires_frontal_printcapable_face():
    # VIS says portrait but DET says no frontal/print-capable face -> NOT placed into a face element
    items = [(_c("/x.jpg"), _Det(frontal=False, pc=False, faces=0),
              AssetJudgement(role="founder_portrait", visual_appeal=3))]
    out = {r.element: r for r in route_assets(items)}
    assert out["cover_hero"].status == "flagged"

def test_empty_pool_flags_never_fabricates():
    out = route_assets([])
    assert all(r.status == "flagged" and r.path is None for r in out)
```
- [ ] **Step 2: Run → FAIL** (ImportError).
- [ ] **Step 3: Implement** `router.py`:
  - `ROLE_TO_ELEMENTS: dict[role, list[element]]` per spec §4.3 (founder_portrait→[cover_hero, about_portrait]; founder_working→[device_mockup]; founder_speaking→[scene]; group_team→[team]; lifestyle→[scene]; content_card→[proof]; logo→[logo]).
  - `ELEMENT_PRIORITY: list[str]` fill order (cover_hero, about_portrait, team, device_mockup, scene, proof, logo).
  - DET constraints: face elements (cover_hero, about_portrait) require `det.frontal and det.print_capable`; team prefers `faces>=2` else any; others no face requirement.
  - `route_assets(items)`: for each element in priority, gather candidates whose role maps to it AND pass the element's DET constraint AND `appeal>=APPEAL_MIN(=2)` AND source not already used; pick highest appeal (tie: print-capable, then nothing); mark used; else `RoutedElement(flagged, reason)`. Return one RoutedElement per element in `ELEMENT_PRIORITY`.
- [ ] **Step 4: Run → PASS.** Checkpoint.

---

### Task 4 — slot_bridge: map routed elements → resolver drive-key filenames
**Files:** Modify `stages/scrape_founder_assets/slot_bridge.py`; Test extend `tests/test_slot_bridge.py`.

- [ ] **Step 1: Write the failing test** — `place_routed(routed, client_assets_dir)` copies each FILLED RoutedElement to the resolver filename for its element: cover_hero/about_portrait→`founder.jpg`/`team.jpg` (single), proof→`proof-<n>.jpg` (many), scene→`proof-<n>` or a scene drive-key; device_mockup is NOT a drive file (skipped here, handled in Task 5). Assert the REAL `resolve_slots("ST-01"/"ST-05", names)` picks them up.
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** an `ELEMENT_TO_DRIVE_KEY` map (cover_hero→founder, about_portrait→team, scene→proof, content_card/proof→proof, logo→logo; device_mockup→None) + `place_routed(...)` reusing the existing copy/many-index logic. Keep the old `place_for_resolver` working (or refactor it to call the new one).
- [ ] **Step 4: Run → PASS.** Checkpoint.

---

### Task 5 — Orchestrator: scrape pool → perceive → classify → route → place
**Files:** Modify `stages/scrape_founder_assets/orchestrator.py`; Test extend `tests/test_orchestrator.py`.

- [ ] **Step 1: Write the failing test** (all fakes): a new `understand_and_route(*, youtube_url, instagram_url, founder_id, scratch_dir, dest_root, classifier=Fake, ...)` that: fetches the pool (fake channels), DET-scores, classifies (FakeAssetClassifier by-path), routes, places drive elements via `place_routed`, and for a `device_mockup`-routed `founder_working` asset emits an `AssetResult`-shaped entry. Assert: (a) clean portrait → committed `founder.jpg`; (b) a working photo → device_mockup AssetResult with its path; (c) an all-cards pool → portrait/team flagged (never fabricated); (d) scratch cleaned in `finally`.
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** `understand_and_route` alongside the existing `scrape_founder_assets` (keep the old one for back-compat / existing tests). Compose: `_fetch_channel` (reuse) → DET via `selector.score_candidate` → `classify_asset` per candidate → `route_assets` → `place_routed` for drive elements + collect device_mockup as an `AssetResult(slot_id="device_mockup", status="resolved", path=..., image_type="device")`. Return `{routed: list[RoutedElement], device_assets: list[AssetResult], flags}`. Scratch cleanup in `finally`.
- [ ] **Step 4: Run → PASS.** Checkpoint: full preprocessor suite.

---

### Task 6 — Brand-agnostic guard + env-gated live test
**Files:** the guard test (existing), `tests/test_smart_routing_live.py` (skipif no `IG_LIVE_TEST_URL`/keys).
- [ ] **Step 1:** Extend the brand-agnostic guard to scan `classifier.py` + `router.py` (no client literals).
- [ ] **Step 2:** Env-gated live test: given a real founder URL + keys, run `understand_and_route`, print each element's `(status, role, appeal, path)`; assert it never crashes, never fabricates, scratch cleaned.
- [ ] **Step 3: Run** the guard (unit) green; live test skipped by default.
- [ ] **Step 4:** Checkpoint: full preprocessor suite green.

---

### Task 7 — Verify on a real founder (manual, view the pixels)
- [ ] Run `understand_and_route` live on the author's founder URLs into a tmp dir; print the routing table; **VIEW** the committed element images (never trust "filled"); confirm roles are sensible (portrait crisp, working photo = real at-device shot, cards → proof, no text-graphics in photo elements).
- [ ] Optional: controlled apex render swap (as in Phase 2) to view a routed asset on a page.
- [ ] Checkpoint: full preprocessor suite + scraper suite green; clean up one-off scripts.

---

## Self-review
- **Spec coverage:** Perception (existing DET, Task 5 wiring), Analysis/classifier (T2), Routing w/ DET guards + de-dup + flag (T3), integration via proven bridge + device composite (T4/T5), guard + live (T6), pixel verification (T7). All cite the spec.
- **No real network in units** — VIS behind injectable client + Fake; one opt-in live test.
- **Honest:** never-fabricate (flag-on-empty tested T3/T5), brand-agnostic guard (T6), sparse-feed reality preserved. No synthetic frames anywhere.
- **Type consistency:** `AssetJudgement`/`RoutedElement`/`AssetRole` defined in T1 and used unchanged in T2–T5; `route_assets`/`place_routed`/`understand_and_route` signatures stable across tasks.
- **Reuse, not rewrite:** existing `selector`, `quality_gate` VIS pattern, `_fetch_channel`, de-dup logic, `slot_bridge`, `AssetResult` all reused.
