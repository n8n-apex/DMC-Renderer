# Founder Asset Scraper — Design

**Date:** 2026-06-04
**Status:** Approved scope, ready for implementation plan.

## 1. Why this exists (the gap it closes)

The VIS-on deck scoreboard (closed-loop, June 2026) put the largest honest gap in **asset_gen (10 flags)**: missing client photos (N01) **and generic/stock imagery (N07)** — the VIS model repeatedly flagged our AI-abstract gradients/line-strokes as "generic, not specific to a real business." The single biggest design lever in the reference DNA (§C2/§E ★★★) is **founder-as-hero with real, specific photography**. We have almost none: photos resolve on only 5/20 pages; the rest is text-on-panels or generic abstract art.

A founder's **public** distribution channels (YouTube, Instagram) are full of real, specific, on-brand imagery of the founder and their work. Sourcing that imagery directly attacks the N07 "generic" flags and fills the founder slots with the real person — which no renderer trick can manufacture.

## 2. What it solves vs. explicitly does NOT (honest boundaries)

**Solves (v1):** the **founder imagery** slots — `cover_hero`, `founder`, `about_portrait`, `team`, and scene/atmosphere backgrounds — with real, specific photos of the founder/their work. Raises VIS P01 (founder-as-hero) and kills N07 (generic) on those slots.

**Does NOT solve (stays flagged, not faked):**
- `case_study_portrait` (N01 hard-fail) — these are the *clients'* faces. A founder's own channels do not contain clean isolated client portraits. Remains a separate asset problem.
- Charts / prose-numbers (N15) — unrelated lever.
- **LinkedIn** — excluded from v1 (most aggressive anti-scraping, login-required, legally fraught).

**Cardinal rules (preserved):** never fabricate a person; a slot with no acceptable scraped asset is **flagged**, never filled with a fake. Real/specific only. Brand-agnostic: the pipeline takes URLs as input, hardcodes no client identity.

## 3. Inputs

Founder channel URLs, ingested from Airtable (via the existing n8n → preprocessor payload; add fields to the input model):
- `founder_youtube_url` (present today)
- `founder_instagram_url` (to be added to Airtable + payload)
- (`founder_linkedin_url` reserved, unused in v1)

## 4. Pipeline

A new pre-processor stage `stages/scrape_founder_assets/` with a small orchestration controller running the two channel paths in parallel, then a shared selection→restore→gate→store flow.

### 4.1 YouTube path (`yt-dlp` + `ffmpeg`) — filtered to bound data
1. **Channel avatar + banner** — via `yt-dlp` channel metadata/thumbnails. Clean, often high-res. NO video download.
2. **Video thumbnails** for the recent N videos — `--write-thumbnail`. Designed images, founder often featured. NO video download.
3. **Shorts only** (duration ≤ ~90s): download up to K recent Shorts (small files), `ffmpeg` sample ~1 frame / 2s → candidate frames.
4. **Long videos (> ~3 min): thumbnail only.** Never downloaded/ffmpeg'd. (The hard filter the author required — no 1-hour downloads.)

### 4.2 Instagram path (`instaloader`, public, in parallel)
- Profile picture + recent **image** posts (skip reels/videos in v1). Already images → straight to selection.
- Rate-respecting (instaloader's RateController + human-like delays). Best-effort: on login-redirect/429/block, **fail gracefully** (no crash), leave the slot to be flagged.

### 4.3 Selection (deterministic)
For every candidate image/frame:
- **Face detection + frontal check** — MediaPipe BlazeFace or RetinaFace (landmarks → frontal/large-enough face).
- **Sharpness** — OpenCV Laplacian variance; reject blurry.
- Rank candidates per target slot (e.g. a clean frontal sharp face → `founder`/`about_portrait`; a wider/group shot → `team`; a treated scene → atmosphere).

### 4.4 Restore / upscale (conservative)
- Prefer the **highest-res source** (avatars/IG posts are often ≥1080px) — avoid upscaling when not needed.
- When upscaling is needed: **CodeFormer (w≈0.7)** or GFPGAN for faces, Real-ESRGAN for backgrounds — but conservatively (heavy restoration looks "waxy"/synthetic and would read as fake).

### 4.5 Quality gate (the acceptance bar — author's choice)
- Every selected+restored asset passes through the **loop's VIS check (N07: specific-not-generic + sharp + not-AI-fake)**. Only assets that PASS are accepted into the slot pool. Below-bar assets are flagged, never shipped.

### 4.6 Slot mapping + hand-off
- Accepted assets are written into the client-asset pool the existing **slot resolver** reads (`client-assets/<founder>/`), keyed so the resolver fills `cover_hero` / `founder` / `about_portrait` / `team` / scene slots. Unfilled slots → flagged for the loop (never fabricated).

### 4.7 Orchestration controller (small, deterministic + probabilistic)
- Per founder: run YT + IG paths in parallel; collect candidates; deterministic filters/thresholds (duration, face, sharpness); probabilistic only on the final best-shot pick + the VIS judgment; gracefully handle a blocked/empty channel; emit a per-slot result (filled / flagged-with-reason). Never crashes the render on a scrape failure.

## 5. Data handling (the author's explicit concern)

- Download to a **scratch temp dir**; extract/select; **keep only the accepted assets**, then **delete the raw downloads** (Shorts videos, rejected frames, extra posts). No hoarding GBs of video.
- Accepted assets stored **locally now** (`client-assets/<founder>/`); **Supabase bucket later**.
- **Weekly cleanup cron** clears the Supabase scratch/screenshot files to keep the bucket healthy (designed now, active once Supabase is wired).

## 6. Architecture / integration

- New stage package `research/preprocessor/stages/scrape_founder_assets/` (channel clients + selector + restorer + orchestrator).
- **Reuses:** the existing Playwright capture (`onboard/capture.py`) where browser automation is needed; the asset cache + slot resolver (`assets_cache.py`, `local_assets.py`, slot resolution) for hand-off; the structlog/settings/resilience substrate.
- **New deps:** `yt-dlp`, `ffmpeg` (system), `instaloader`, a face detector (`mediapipe` or `retina-face`), OpenCV (`opencv-python-headless`), an upscaler (CodeFormer/GFPGAN/Real-ESRGAN — pinned at build time, behind a swappable interface). Heavy ML deps behind lazy imports so the rest of the preprocessor isn't burdened.
- Runs as an async stage in the pipeline (like the other async asset stages), with the VIS gate calling the existing OpenRouter vision client.

## 7. Failure modes & risks (named, not hidden)

- **IG reliability**: free instaloader works low-volume; production-reliable IG needs **residential/mobile proxies + `curl_cffi` + sticky sessions** (datacenter IPs rejected; raw requests fingerprinted; GraphQL ids rotate ~2–4 weeks). v1 = best-effort free; proxy hardening is the documented next step. Graceful failure when blocked.
- **Face upscaling → "waxy"/fake**: mitigated by prefer-high-res-source + conservative restore + VIS "looks-generated" gate.
- **Client case-study photos** not solved — explicit, stays flagged.
- **Rights/ToS**: using a founder's *own* public posts for their *own* report is the intended, defensible use; the pipeline does not redistribute third-party/client media. (Operational/legal note, not a code concern.)

## 8. Testing strategy

- **No real network in the unit suite.** Channel clients behind an interface with **fakes** (scripted fixture images). Face-detect/sharpness/selection/restore tested on small bundled fixture images deterministically. The VIS gate uses the existing `FakeVisionClient`.
- **One opt-in real integration test** (env-gated on the keys/tools present) that runs a real founder URL end-to-end.
- Brand-agnostic guard extended to the new stage (no client literals).

## 9. Out of scope for v1 (deferred, flagged)
LinkedIn; client case-study portraits; Instagram reels/video; residential-proxy hardening; Supabase storage + the cleanup cron going live (designed, local-first); any auto-posting/write actions.

## 10. Self-review
- **Scope is single-subsystem** (founder imagery sourcing) — appropriately bounded.
- **Every decision from the design dialogue is captured**: YT thumbnails/avatar + Shorts-only frames + long-video filter; IG public posts; face+sharpness selection; conservative CodeFormer/GFPGAN restore; VIS gate; keep-only-accepted data handling; local→Supabase; weekly cleanup; founder slots only; LinkedIn + client photos out.
- **Risks named** (IG proxies, face-upscale waxiness, client photos unsolved) — no overclaiming.
- **Honest interfaces** for testability (channel clients + vision gate mockable).
