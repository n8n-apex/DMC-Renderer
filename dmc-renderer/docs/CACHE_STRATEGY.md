# DMC Renderer — Cache Strategy

**Tl;dr — the renderer has no cache.** It is a pure, stateless,
synchronous transformation: `payload → PDF`. Every render fetches every
image, every render re-runs every preprocessing step, every render
re-rasterizes every component. Determinism comes from the renderer
being a pure function, not from caching.

If anything upstream needs to avoid re-rendering, n8n implements the
cache.

---

## Why no cache (the explicit reasoning)

Phase 1 locked **"Stateless renderer: same input → same output. No
cache layer in renderer. n8n handles upstream caching if needed."**
(`research/SUMMARY.md` locked decision #7.)

This is not a "we'll add it later" placeholder. The reasons:

1. **Pure functions compose better.** A cacheless renderer is trivially
   reasoned about: input determines output. No "did the cache invalidate"
   debugging. n8n can hash the request body and short-circuit before
   calling us.
2. **Cache invalidation is the cache's job.** If we cached, we'd need to
   know when to invalidate (Writer regenerated the content? brand colors
   changed? font subset changed?) The hash of the request body answers
   all these for free at the n8n layer.
3. **Operational simplicity.** No Redis. No volume mounts. No "wipe the
   cache" procedure. The renderer's filesystem is read-only at runtime
   except for `/tmp/render-{report_id}/` which gets RM'd at end of
   request. Railway can swap containers any time.
4. **Determinism testing.** We can verify "same payload → same PDF" by
   running the renderer twice and `cmp`-ing the bytes. With a cache,
   that test is testing the cache, not the renderer.

---

## Per-render scratch directory

The one bit of filesystem state the renderer uses:

```
/tmp/render-CL-20260508-092136-MCE/
├── cover_hero.png
├── cover_author.jpg
├── about_logo.png
├── status_quo_scene.png
├── fazit_background.jpg
└── (no other files — only the fetched images)
```

- Created at request start: `mkdir -p /tmp/render-{report_id}/`
- Populated by the image fetcher: each `payload.images` URL → local file named after the slot
- Referenced by CSS via `url('file:///tmp/render-{report_id}/cover_hero.png')`
- Deleted at request end (success or failure): `shutil.rmtree(...)` in a `finally:` block

A failing render still cleans up. A killed process (SIGKILL) leaves the directory; we accept that and rely on Railway's tmpfs ephemerality.

---

## Image fetching

```python
import urllib.request
from pathlib import Path

def fetch_images(images: dict, scratch_dir: Path, timeout_s: int = 30):
    for slot, url in images.items():
        ext = guess_ext(url)             # png/jpg/svg from content-type or URL
        target = scratch_dir / f"{slot}.{ext}"
        with urllib.request.urlopen(url, timeout=timeout_s) as resp:
            target.write_bytes(resp.read())
```

Behavior:

| Concern | Strategy |
|---|---|
| Timeout per image | 30 seconds. If reached → render fails with 500 `image_fetch_failed`. |
| Total image-fetch budget | Implicitly bounded by the 120 s overall render timeout. With 5 images at 30 s worst-case each = 150 s but in practice well under. |
| Concurrency | Sequential. 5 images at ~200 ms each is ~1 s total — concurrency adds complexity for no observable win. If a future client has 20+ images, switch to `asyncio` or `ThreadPoolExecutor`. |
| Retries | None. Drive URLs verified upstream — the renderer's job isn't to compensate for upstream flakiness. If a fetch fails, the operator decides whether to retry the whole render. |
| Content-type validation | We trust whatever the URL serves. CSS will fail gracefully (broken image) if the bytes aren't a valid image. Future: validate magic bytes match the file extension. |
| Auth | None. URLs must be publicly fetchable. If a client moves to authenticated CDN, that's a Phase 1.2 enhancement (signed URLs with short TTL). |

---

## What n8n caches (informational — not the renderer's job)

For reference: n8n's upstream caching strategy.

| Layer | What's cached | Cache key |
|---|---|---|
| Writer output | The generated `payload` JSON | Hash of (prompt, model, brand) |
| Final PDF | The rendered PDF bytes | Hash of (payload, images, brand_tokens) |
| Image assets | Optional — Drive URLs are stable so this is a small win | URL → bytes (browser-style HTTP cache) |

The renderer is unaware of any of these. When n8n receives the same
request twice, n8n short-circuits before the renderer is called. When
the renderer IS called, it always does the full work.

---

## What if we need a cache later?

Plausible future trigger: per-page incremental rendering for interactive
previews. The user tweaks one paragraph in the Writer UI, n8n re-emits
the payload with only one page changed, we'd like to re-render only
that page.

If we get there:

- Cache key = hash of `(payload.pages[i].data, images, brand_tokens)`
- Storage = local LRU on disk (capped at 1 GB) or Redis if running ≥2 renderer instances
- Invalidation = LRU only; never time-based
- Endpoint behavior unchanged — `/render` still produces the full PDF; the cache is opaque

**Don't build this until the use case forces it.** Today the entire
20-page render is ~12 s — comfortably under the 120 s budget for an
interactive feel anyway.

---

## What we explicitly DON'T cache (today)

- Compiled Jinja templates: re-loaded from disk per request. Cost is < 100 ms.
- WeasyPrint font configurations: re-built per render. Cost is similar.
- Preprocessor regex compilation: in-process, re-used; this is module-level state, not a cache.
- Coral validator color lookup tables: in-process, deterministic, re-used.

These aren't "no cache" so much as "no cross-request cache". Within a
single request, expensive setup runs once.

---

## Determinism vs reproducibility

| Property | Holds? | Note |
|---|---|---|
| Same payload, same image bytes → same PDF | yes | The renderer is a pure function modulo a deterministic timestamp seed. |
| Re-render after Drive image silently changes → same PDF | **no** | We fetch fresh every time. If Drive serves different bytes, you get a different PDF. This is by design — the renderer reflects current reality, not historical state. |
| Re-render after a font is added/removed → same PDF | **no** | Bundled fonts are part of the renderer's identity. Same Docker image = same fonts. Different image = potentially different output. n8n caches by request body, not by renderer image — if you change the renderer, invalidate n8n's cache by bumping the renderer's `X-Renderer-Version` and using it in the cache key.|
| Re-render at a later wall-clock time → same PDF | yes (modulo subset noise) | Timestamps are seeded from `report_id`, not `now()`. Font subsetting can vary by a few bytes. Visible output is identical. |

---

## Operational notes

- `/tmp/render-*/` directories should never accumulate on a healthy
  renderer. If you see them lingering, it's a bug — file a ticket.
- Railway's container filesystem is ephemeral (destroyed on each deploy).
  A botched cleanup is forgiven by the container lifecycle.
- If we ever introduce on-host cache, **document the eviction policy in
  this file** — the absence of such a section is the contract.
