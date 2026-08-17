# Founder Asset Scraper — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use `- [ ]`. **NO GIT** (checkpoint = full preprocessor suite green). Activate the preprocessor venv. **No real network in the unit suite** — channel clients behind interfaces with fakes; one opt-in env-gated real test. Heavy ML deps behind lazy imports.

**Goal:** Source real, specific founder imagery from the founder's public YouTube + Instagram, select the best shots, gate them on the loop's VIS quality bar, and feed them into the slot resolver to fill founder slots (cover/about/team/scene) — closing the N07 "generic imagery" + founder-as-hero gaps. Per `docs/superpowers/specs/2026-06-04-founder-asset-scraper-design.md`.

**Architecture:** new `research/preprocessor/stages/scrape_founder_assets/` package: channel clients (YouTube via yt-dlp, Instagram via instaloader) behind a `ChannelClient` protocol → a deterministic Selector (face-detect + sharpness) → a swappable Restorer (conservative) → the VIS quality gate (existing OpenRouter client) → storage (scratch→keep-accepted→delete-raw) → slot-resolver hand-off. A small async orchestrator runs the paths in parallel and emits per-slot filled/flagged results.

**Tech:** yt-dlp, ffmpeg (system), instaloader, opencv-python-headless, mediapipe (or retina-face) for face detect; restorer interface (v1 default = prefer-high-res + Lanczos; CodeFormer/GFPGAN opt-in behind the interface, needs torch+weights — NOT a v1 hard dep).

---

### Task 1 — Input model: founder channel URLs
**Files:** `research/preprocessor/models_package.py` (or the input model), `tests/test_models_*.py`.
- [ ] Failing test: the input model accepts optional `founder_youtube_url` + `founder_instagram_url` (validated as URLs or None); absent → None, no crash.
- [ ] Implement the optional fields (keep backward compatible — existing payloads without them still validate).
- [ ] Run → PASS. Checkpoint: `python -m pytest research/preprocessor/tests -q`.

### Task 2 — `ChannelClient` protocol + fakes + scaffolding
**Files:** `stages/scrape_founder_assets/__init__.py`, `clients.py`, `models.py`, `tests/test_scrape_clients.py`.
- [ ] Failing test: a `FakeChannelClient(scripted_assets)` implements `fetch_candidates(url, *, limit) -> list[Candidate]` returning `Candidate{source, kind('avatar'|'banner'|'thumbnail'|'frame'|'post'), local_path, width, height, meta}`; a `ScrapeResult` dataclass aggregates candidates + per-channel status (`ok`/`blocked`/`empty`/`error`) + reason.
- [ ] Implement the protocol + dataclasses + fake. No network.
- [ ] Run → PASS. Checkpoint.

### Task 3 — YouTube client (yt-dlp + ffmpeg, filtered)
**Files:** `clients_youtube.py`, `tests/test_youtube_client.py`.
- [ ] Failing tests (yt-dlp/ffmpeg behind a thin injectable runner so tests use a FAKE runner — no network): given a fake yt-dlp that returns channel metadata + a Shorts list with durations, `YouTubeClient.fetch_candidates(url, limit)` (a) always collects avatar/banner + recent video thumbnails WITHOUT requesting a video download; (b) downloads ONLY Shorts with `duration <= MAX_SHORT_SECONDS` (=90), up to `MAX_SHORTS` (=K); (c) for any video with `duration > MAX_LONG_FRAME_SECONDS` (=180) it uses the THUMBNAIL only (asserts no frame-extract call); (d) ffmpeg frame sampling (fake) returns frames at ~1/2s.
- [ ] Implement `YouTubeClient` with an injectable `runner` (real = subprocess yt-dlp/ffmpeg; tests = fake). Real path lazy-imports/execs the tools; the duration filter is the hard guard.
- [ ] Run → PASS. Checkpoint.

### Task 4 — Instagram client (instaloader, public, graceful)
**Files:** `clients_instagram.py`, `tests/test_instagram_client.py`.
- [ ] Failing tests (instaloader behind an injectable loader fake — no network): `InstagramClient.fetch_candidates(url, limit)` returns profile-pic + recent IMAGE posts (skips video/reel items); on a simulated 429/login-redirect/exception it returns a `ScrapeResult(status='blocked'|'error', reason=...)` with candidates=[] and DOES NOT raise (graceful).
- [ ] Implement with the injectable loader + rate-respecting config; real path lazy-imports instaloader.
- [ ] Run → PASS. Checkpoint.

### Task 5 — Selector (face detect + sharpness, deterministic)
**Files:** `selector.py`, `tests/test_selector.py` + small bundled fixture images (a sharp frontal face, a blurry one, a no-face one).
- [ ] Failing tests: `score_candidate(path) -> CandidateScore{has_face, frontal, face_area_frac, sharpness, slot_affinity}` using OpenCV Laplacian variance (sharpness) + a face detector (mediapipe/retinaface, behind a lazy import; tests may use a tiny stub detector OR the real one on bundled fixtures). `select_for_slots(candidates, slots) -> dict[slot -> ranked list]`: a sharp frontal large face ranks first for `founder`/`about_portrait`; blurry/no-face rejected.
- [ ] Implement. Sharpness = `cv2.Laplacian(gray, CV_64F).var()` with a documented threshold; frontal via landmark symmetry; face_area_frac for "prominent".
- [ ] Run → PASS. Checkpoint.

### Task 6 — Restorer (conservative, swappable)
**Files:** `restorer.py`, `tests/test_restorer.py`.
- [ ] Failing tests: `Restorer.ensure_print_quality(path, target_px) -> path` — if source ≥ target, returns as-is (NO upscale); if below, upscales conservatively (default = Pillow Lanczos) and returns the new path; the interface allows a `face_restore` backend (CodeFormer/GFPGAN) to be plugged in but it is NOT required for v1 (default backend is dependency-light). Assert "prefer high-res source" (no-op when big enough).
- [ ] Implement the interface + the Lanczos default; document the CodeFormer/GFPGAN backend as opt-in (lazy, torch+weights).
- [ ] Run → PASS. Checkpoint.

### Task 7 — VIS quality gate
**Files:** `quality_gate.py`, `tests/test_quality_gate.py`.
- [ ] Failing tests (FakeVisionClient): `passes_quality(path, vis_client) -> (bool, reason)` asks the vision model "is this a real, specific, sharp photo (not generic/stock, not AI-fake)?"; a scripted PASS accepts, a scripted FAIL rejects with reason. Reuse the brand-agnostic VIS prompt discipline (composition/specificity, not brand identity).
- [ ] Implement (calls the existing OpenRouter vision client; injectable for tests).
- [ ] Run → PASS. Checkpoint.

### Task 8 — Storage + data handling
**Files:** `storage.py`, `tests/test_storage.py`.
- [ ] Failing tests (tmp dirs): `commit_accepted(accepted, founder_id, dest_root)` copies accepted assets into `dest_root/client-assets/<founder_id>/` with slot-keyed names; `cleanup_scratch(scratch_dir)` deletes the raw downloads. Assert: accepted assets present in dest; scratch (raw videos/rejected frames) deleted; the original founder dest is namespaced. (Supabase + weekly cron are DEFERRED — add a documented `StorageBackend` interface with a `LocalStorage` impl now; Supabase impl later.)
- [ ] Implement local storage + scratch cleanup behind a `StorageBackend` interface.
- [ ] Run → PASS. Checkpoint.

### Task 9 — Orchestrator + pipeline wiring
**Files:** `orchestrator.py`, `tests/test_orchestrator.py`, plus the pipeline hook in `main.py`/the stage runner.
- [ ] Failing tests (all fakes): `scrape_founder_assets(youtube_url, instagram_url, slots, *, clients, selector, restorer, gate, storage) -> FounderAssetResult` runs YT + IG (fakes) in parallel, selects per slot, restores, gates (fake VIS), commits accepted, returns per-slot `filled(path)|flagged(reason)`. Tests: (a) both channels ok → founder/about/team slots filled from best candidates; (b) IG blocked + YT ok → still fills from YT, IG noted; (c) all candidates fail the VIS gate → all slots flagged (never fabricated), no crash; (d) raw scratch cleaned up regardless of outcome.
- [ ] Implement the async orchestrator (parallel paths, graceful per-channel failure, per-slot result, scratch cleanup in a finally). Wire it as an async pre-processor stage that runs before slot resolution so its assets are available to the resolver; gate behind the presence of founder URLs (no URLs → stage no-ops, no crash).
- [ ] Run → PASS. Checkpoint: full preprocessor suite green.

### Task 10 — PROVE on a real founder (env-gated)
**Files:** `tests/test_founder_scraper_real.py` (skipif tools/keys absent), a small `run_scrape.py` CLI.
- [ ] `run_scrape.py <youtube_url> <instagram_url>` runs the real pipeline into a tmp/output dir and prints per-slot filled/flagged + the accepted asset paths.
- [ ] Env-gated real test: given a real founder's YouTube (+ Instagram if reachable), the pipeline produces at least one VIS-accepted founder image OR flags gracefully; never crashes; scratch cleaned. (Author supplies the real URLs.)
- [ ] Run it once on the author-supplied URLs; paste the per-slot result. Checkpoint: full preprocessor suite green + (renderer/quality_loop suites untouched, still green).

---

## Deferred (flagged, not in v1)
LinkedIn; client `case_study_portrait` sourcing (clients' faces, not in founder channels); IG reels/video; CodeFormer/GFPGAN face-restore backend (opt-in behind the Restorer interface); residential-proxy + curl_cffi IG hardening; Supabase StorageBackend + the weekly cleanup cron going live.

## Self-review
- **Spec coverage:** inputs (T1), channel clients with the long-video filter (T2/T3), graceful IG (T4), face+sharpness selection (T5), conservative restore (T6), VIS gate (T7), keep-accepted/delete-raw storage (T8), orchestrator+wiring+graceful+flags (T9), real proof (T10). All cite the spec.
- **No real network in unit tests** — every external tool/client behind an injectable interface with fakes; one opt-in real test.
- **Honest:** client photos + LinkedIn + IG-hardening + Supabase explicitly deferred; never-fabricate enforced (flag on no acceptable asset); VIS gate is the acceptance bar.
- **Brand-agnostic:** URLs in, no client literals; guard extended to the new stage.
