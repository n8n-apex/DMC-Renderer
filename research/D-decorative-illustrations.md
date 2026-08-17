# Phase-1 Research Task D — Decorative-Illustration Slot System

**Goal:** every decoration slot in a DMC report must render *something* on first try (never blank) and that "something" should ladder up toward editorial quality (like aerz p4's pickaxe + coin jar). This doc defines slot-system schema, the MVP path, the upgrade ladder, and a concrete cluster-pattern library for the 11 universal page types.

Anchor reference: `aerz_p04.png` — pickaxe + glass jar of coins + scattered banknotes — a *composite metaphor still-life* sitting in a square decoration zone left of the body copy. That visual is the gold standard. Everything below is calibrated to either fill that slot with a cheap-but-tasteful single icon at the bad end, or with a per-client commissioned SVG at the good end.

---

## 1 · Per-approach findings

### A. Iconify.design — open icon meta-set (recommended MVP backbone)

- **Inventory:** ~292,406 icons across 209 sets as of 2026 (Iconify icon-sets index). Each set has its own license; many are MIT, several are CC BY 4.0 or Apache-2.0.
- **License sanity:**
  - Tabler Icons — **MIT**, 6,146 icons. ([tabler/tabler-icons](https://github.com/tabler/tabler-icons))
  - Fluent UI System Icons (Microsoft) — **MIT**, ~19,296 icons (Iconify). ([microsoft/fluentui-system-icons LICENSE](https://github.com/microsoft/fluentui-system-icons/blob/main/LICENSE))
  - Streamline Plump — **CC BY 4.0**, ~1,500 icons (attribution required).
  - Flat Color Icons (Icons8) — **MIT** for the OSS subset.
  - Lucide / Heroicons / Material Symbols — all MIT/Apache-2.0/OFL.
- **Fetch path:** raw SVG via `https://api.iconify.design/{prefix}/{name}.svg?width=128&color=%23022D2D`. The API supports `color` (recolours `currentColor` paths only — monotone sets only), `width`, `height`, `rotate`, `flip`, `box=1`. ([Iconify Render-SVG docs](https://iconify.design/docs/api/svg.html))
- **Python client:** `pyconify` (PyPI) wraps the same API and caches SVGs locally to `~/.iconify-cache/`. Functions: `pyconify.svg(prefix, name, color=…)`, `pyconify.icon_data(...)`, `pyconify.search(...)`. ([pyapp-kit/pyconify](https://github.com/pyapp-kit/pyconify))
- **The "cluster" idea:** any single icon is too small/plain to feel editorial — but **2–3 icons composed in an overlapping z-stack with a 10–25% drop-shadow circle behind them** reads as a curated still-life. Worked example for the pickaxe slot: `fluent:savings-24-regular` (jar) + `mdi:pickaxe` (tool) + tiny `tabler:coin` × 3 confetti — all stroked in `--color-primary` with `--color-accent` highlights. Renders for free in <50ms.
- **Highest-value sets for DMC:**
  - **Flat Color Icons** (`flat-color-icons:*`) — pre-coloured flat illustrations; closest to the "Freepik flat illustration" look but free + MIT.
  - **Streamline Plump** (`streamline-plump-*`) — friendly editorial line illustrations; very close to the line-art used in premium B2B magazines. CC BY 4.0 — attribution required in colophon.
  - **Tabler** (`tabler:*`) and **Fluent regular/filled** (`fluent:*-24-regular`) — clean monotone icons; perfect for tinting to brand colour.
  - **Healthicons / Material Symbols / Carbon** — industry-specific glyphs (e.g. `healthicons:dental-implant`).

### B. AI text-to-SVG (SVGMaker, Recraft) — onboarding-time bespoke kits

- **SVGMaker** offers `POST /v1/generate` with `style` (`flat`, `linocut`, `engraving`, more) and `composition` parameters; API key auth, credit-priced (1–3 credits per generation, free tier ~100/mo, Pro $19/mo). Has an MCP server (`GenWaveLLC/svgmaker-mcp`). ([SVGMaker API reference](https://svgmaker.io/docs/api-reference))
- **Recraft V4 / V4 Pro text-to-vector** — native SVG output with brand-style reference upload. Pricing $0.08/image (V4) and $0.30/image (V4 Pro) via fal.ai or WaveSpeedAI. Brand-style: upload 3–5 reference SVGs and it locks to that visual language. ([Recraft V4 vector on fal.ai](https://fal.ai/models/fal-ai/recraft/v4/text-to-vector))
- **Per-client onboarding workflow:** at onboarding, ask Recraft to generate 12–15 brand-styled illustration tokens with a single style-anchor prompt; manually accept/reject. Cost per client: **~$5–15** (15 generations × $0.30, plus rejects). Result lives in `assets/illustrations/{client_slug}/`.
- **Quality bar:** Recraft V4 Pro is now the only AI text-to-vector that ships clean, structured SVG paths (most others rasterize then trace). Verified by 2026 reviewer benchmarks. ([vectosolve 2026 review](https://vectosolve.com/blog/best-ai-svg-generators-text-to-vector-2026))

### C. Generative SVG with constraints (`svgwrite`, `rough.js`)

- `svgwrite` is pure-Python, no deps, but unmaintained since 2023 — bugfix only. ([svgwrite GitHub](https://github.com/mozman/svgwrite))
- Works fine for parametric *geometric* art (charts, diagrams, abstract pattern fills) but cannot improvise a recognisable pickaxe-jar still-life. You'd be encoding every illustration by hand.
- `rough.js` (sketchy hand-drawn aesthetic) is JS-only; would require Node sub-process.
- **Verdict:** kill as a primary path. Keep as a fallback for procedural **textures/backgrounds** (dotted grids, hand-drawn underlines, ribbon flourishes — see §5). Re-use the chart pipeline you already have.

### D. Magnific / Freepik flat illustrations

- Freepik holds millions of flat illustrations as AI/EPS/JPG (vector source); the *free* tier requires attribution ("Designed by Freepik") on every published page; Premium ($9/mo) removes attribution.
- Vector source available but quality is wildly uneven and curation cost is high (you'd browse for an hour per slot).
- License audit per asset is manual — risk of accidentally shipping a non-CC asset.
- **Verdict:** good as a *human-curated* fallback for the commissioned tier (i.e. a designer pulls 3 Freepik assets to anchor a client kit), but not as an automated route. Magnific is image-upscale only — not relevant here.

### E. Pre-commissioned per-client SVG library

- Hire an illustrator at onboarding (Fiverr/99designs/local). Brief: "12 single elements + 6 composite patterns + 4 textures, single-colour line-art, transparent BG, 1024×1024 viewBox, `currentColor`-ready."
- Cost: **$50–150 one-time per client**. Time: 2–5 working days.
- Quality: matches aerz p4 exactly — bespoke editorial illustration.
- Companion `VISUAL_ASSETS.md §3.3` already accounts for this as `METAPHOR_OBJECT` and budgets $500–1500 total for a shared closed-set library of ~10 metaphors usable across all clients. **The per-client version layered on top is the premium offer.**

---

## 2 · Comparison table

| Approach | Visual quality (1–5) | Cost / client | Time-to-deploy | Dynamic vs static | Best fit |
|---|---|---|---|---|---|
| **A. Iconify clusters** | 3 (with 2–3 icon composition) | **$0** | Hours | Dynamic — composed per slot | **MVP, every client, every report** |
| **B. AI SVG (Recraft brand-styled)** | 3–4 | $5–15 one-time | 1 hour onboarding | Static per-client kit | Premium tier add-on |
| **B. AI SVG (SVGMaker per-slot)** | 3 | ~$0.30 per call | Hours | Dynamic but slow/unreliable | Last-resort filler |
| **C. Procedural (svgwrite/rough)** | 2 (geometric only) | $0 | Days | Dynamic | Textures + abstract pattern fills only |
| **D. Freepik flat library** | 3–4 | $108/yr Premium | Days (manual curation) | Static | Designer-curated boost during onboarding |
| **E. Commissioned per-client kit** | 5 (matches aerz p4) | $50–150 one-time | 2–5 days | Static | Premium / enterprise tier |
| Shared metaphor library ($500–1500 once, reused) | 5 | $0 marginal | 4–8 weeks once | Static | Foundation under all tiers |

---

## 3 · Recommended MVP + upgrade tiers

**MVP — Iconify clusters only.** Free, immediate, every slot gets *something* tasteful on first render. ~50 cluster patterns covering 11 ST types × 2–3 patterns × variants. Selection is deterministic given `{page_st, theme_tag}`; no AI in the hot path.

**Tier 1 upgrade — shared metaphor library.** Commission ~10 high-value composites once ($500–1500 total). Live alongside Iconify; slot resolver prefers a library asset when its `asset_key` is referenced. (Already in `VISUAL_ASSETS.md §3.3`.)

**Tier 2 upgrade — per-client AI brand kit (Recraft V4 Pro).** $5–15 at onboarding, 12–15 tokens. Branded look across the whole report. Slot resolver prefers `client_library` when the `asset_key` exists for that client.

**Tier 3 upgrade — per-client commissioned kit.** $50–150, 2–5 days, premium/enterprise clients only. Same lookup path as Tier 2; just better source.

Order of precedence in resolver: `client_library` → `shared_library` → `iconify_cluster`. Falling back to the next tier is never blank — the MVP cluster is the safety net.

---

## 4 · Decoration-slot payload schema

```jsonc
{
  "decoration_slot": {
    "slot_id": "st04-overwhelm-left",          // stable id within the page template
    "type": "iconify_cluster" | "client_library" | "shared_library" | "ai_svg" | "procedural",
    "theme_tag": "metric-celebration" | "overwhelm" | "system-leak" | "mindset-trap" | "case-study-win" | "process-flow" | "trust-cluster" | "cta-magnet" | "...",
    "pattern": "metric-cluster-1",              // when type == iconify_cluster — references §5 below
    "icons": [                                  // when type == iconify_cluster — names + per-icon transforms
      { "iconify": "fluent:savings-24-regular", "color": "var(--color-primary)", "x": 0,  "y": 0,  "size": 96, "z": 1 },
      { "iconify": "mdi:pickaxe",                "color": "var(--color-primary)", "x": 28, "y": 18, "size": 72, "z": 2, "rotate": -15 },
      { "iconify": "tabler:coin",                "color": "var(--color-accent)",  "x": 12, "y": 64, "size": 18, "z": 3, "opacity": 0.9 }
    ],
    "asset_key": "metric-celebration",          // when type == client_library or shared_library
    "ai_prompt": "linocut still-life ...",      // when type == ai_svg
    "style_token": {                            // shared across all types
      "primary":  "var(--color-primary)",
      "accent":   "var(--color-accent)",
      "neutral":  "var(--color-neutral-mid)",
      "bg_circle": false,                       // optional 25%-alpha circle behind the cluster
      "frame": "none" | "circle" | "rounded-rect",
      "viewport": { "w": 220, "h": 180 }
    },
    "fallback_chain": ["client_library:metric-celebration", "shared_library:metric-celebration", "iconify_cluster:metric-cluster-1"]
  }
}
```

The resolver walks `fallback_chain` until something resolves; if everything fails, it renders the **last** entry (always an Iconify cluster) — so a slot is *never blank*.

---

## 5 · Iconify cluster-pattern library — 2–3 patterns per ST template

Each pattern is a named triple-or-quad of Iconify icons with z-order + positioning hint. All icons are MIT/Apache/OFL unless noted (Streamline Plump = CC BY 4.0, attribute in colophon). Brand tinting via the `color` URL param; positioning via SVG `<g transform>` wrappers inside a 220×180 viewBox.

### ST-01 — Cover (decorative corner glyphs only; hero is always a real photo)
- **`cover-mini-celebration`** *(top-right corner accent)*
  - `fluent:sparkle-24-filled` (base, large, accent colour)
  - `tabler:star` (small, top-left of sparkle, primary)
  - *positioning: 60×60 SVG, sparkle centred, star at 10/10 offset*
- **`cover-mini-target`** *(when cover hook is goal-oriented)*
  - `fluent:target-arrow-24-regular`
  - `mdi:bullseye-arrow` (overlapping centre)
  - tiny `tabler:check` accent dot bottom-right

### ST-02 — Ausblick / Editorial (one decorative spot illustration, top-right of body)
- **`editorial-compass`** *(intro / what-you-will-learn)*
  - `streamline-plump:compass-1` (base, primary)
  - `tabler:map-pin` (smaller, top-right corner of compass)
- **`editorial-open-book`**
  - `fluent:book-open-globe-24-regular` (primary)
  - `tabler:bookmark` (small, gold accent)
- **`editorial-pathway`**
  - `tabler:route` (primary)
  - `fluent:location-arrow-24-filled` (accent at path end)

### ST-03 / ST-05 — Über-Uns / Autorität (decorative cluster beside stats)
- **`authority-trust-stack`**
  - `fluent:shield-checkmark-24-filled` (base, primary)
  - `tabler:award` (overlapping bottom-right, accent)
  - `flat-color-icons:approval` (tiny, top-right) — uses native colour, no tinting
- **`authority-experience`**
  - `streamline-plump:hierarchy-9` (org tree, primary)
  - `tabler:users-group` (overlapping right, accent)

### ST-04 / ST-09 — Problem / Status-Quo (the *overwhelm* slot — the most common decoration zone)
- **`status-quo-overwhelm`**
  - `mdi:clock-alert` (stress, primary)
  - `tabler:files` (paperwork pile, primary, behind)
  - `fluent:warning-24-regular` (small accent dot, top-right)
- **`status-quo-tangled`**
  - `tabler:tangle` (knot, primary)
  - `streamline-plump:question-circle` (small, accent)
- **`status-quo-leak`** *(use when narrative is "you're losing X")*
  - `fluent:drink-bottle-off-24-regular` (jar/bottle, primary)
  - `tabler:droplet` × 3 (small drops, accent, descending y-positions)

### ST-05 / ST-14 — Irrglauben (decorative thumbprint above each Denkfehler card OR one master cluster for the page)
- **`mindset-trap`** *(master cluster — page lead)*
  - `streamline-plump:brain` (primary)
  - `tabler:chain-broken` (overlapping, accent) — the broken link
  - tiny `fluent:lightbulb-filament-24-regular` (top-right, accent)
- **`mindset-mirror`**
  - `mdi:mirror-rectangle` (primary)
  - `tabler:question-mark` (overlap, accent)

### ST-06 — Mechanismus (decorative anchor near the diagram, NOT the diagram itself)
- **`mechanism-gears`**
  - `fluent:settings-24-filled` (large, primary)
  - `tabler:settings-2` (smaller, overlapping right, accent)
  - `mdi:wrench` (tiny, bottom-left)
- **`mechanism-keystone`**
  - `tabler:key` (primary, 30° rotate)
  - `fluent:puzzle-piece-24-regular` (overlapping, accent)
- **`mechanism-cascade`**
  - `tabler:stairs` (primary)
  - `streamline-plump:arrow-up-1` (accent, rising right)

### ST-07A — Fallstudie (decoration in the dark right-panel above the stat trio — the "celebration" slot)
- **`metric-celebration`** *(when ergebnis is a money number — the pickaxe-jar substitute)*
  - `fluent:money-hand-24-regular` (jar/hand, primary)
  - `mdi:pickaxe` (overlap top-left, accent, -15° rotate)
  - `tabler:coin` × 4 (confetti dots, accent, scattered) — **closest free analogue to aerz p4**
- **`metric-rocket`** *(growth-rate ergebnis)*
  - `fluent:rocket-24-filled` (primary)
  - `tabler:flame` (overlap bottom, accent)
  - `mdi:chevron-triple-up` (small, behind, accent)
- **`metric-trophy`** *(non-monetary win — bookings, reach)*
  - `fluent:trophy-24-filled` (primary)
  - `tabler:medal` (overlapping, accent)
  - `streamline-plump:confetti-2` (around, accent + neutral)

### ST-07B — Fallstudie-Gegenseite (when there is no comparison-table or chart, fill the visual zone)
- **`opposition-tug`**
  - `tabler:arrows-left-right` (primary, large)
  - `fluent:scales-24-regular` (centred, accent)
- **`opposition-old-vs-new`**
  - `tabler:device-desktop-analytics` (right side, primary)
  - `mdi:newspaper-variant-outline` (left side, neutral) — the "before"
- **`opposition-bridge`**
  - `streamline-plump:bridge-1` (primary)
  - `tabler:arrow-narrow-right` (small, accent, centred)

### ST-08 — FAQ / Einwandbehandlung (small glyph repeating beside each objection)
- **`objection-hand`**
  - `fluent:hand-stop-24-regular` (primary)
  - `tabler:circle-x` (small overlap, neutral)
- **`objection-thought-bubble`**
  - `streamline-plump:speech-bubble-question` (primary)
  - `tabler:exclamation-circle` (accent, small)

### ST-12 / ST-FAZIT — Fazit / Summary (decorative anchor over the soft-CTA)
- **`summary-light`**
  - `fluent:lightbulb-filament-24-filled` (primary, large)
  - `tabler:sparkles` (around, accent)
- **`summary-bridge-forward`**
  - `tabler:flag` (primary)
  - `fluent:arrow-trending-lines-24-regular` (overlap, accent)

### ST-22 — Process / Zusammenarbeit (small step-glyph in each Schritt card OR one master cluster)
- **`process-handshake`** *(master cluster)*
  - `fluent:handshake-24-regular` (primary)
  - `tabler:check` (overlap, accent)
  - `streamline-plump:arrow-right-1` (small, accent)
- **`process-onboarding`**
  - `tabler:user-plus` (primary)
  - `fluent:calendar-checkmark-24-regular` (overlap, accent)

### ST-15 / ST-16 — Trust-Wall / CTA / Rückseite (back-page decorative seal)
- **`cta-magnet`**
  - `fluent:phone-24-filled` (primary)
  - `tabler:circle-dashed` (around it, accent)
- **`cta-qr-anchor`** *(beside the QR)*
  - `fluent:scan-camera-24-regular` (primary)
  - `tabler:point` (accent dot)
- **`trust-seal`**
  - `fluent:ribbon-star-24-filled` (primary)
  - `tabler:check` (overlap, accent)

### Totals
- **11 ST contexts × 2–3 patterns each ≈ 28–30 named cluster patterns** in the MVP library.
- Plus 4 "modifier" textures (procedural via `svgwrite`): `dotted-grid`, `diagonal-stripes`, `underline-flourish`, `corner-flourish`. These compose under any cluster as the `bg_circle` / `frame` layer.

---

## 6 · Python integration sketch

```python
# renderer/decorations.py
from __future__ import annotations

import functools
from dataclasses import dataclass
from pathlib import Path

import pyconify  # PyPI: wraps api.iconify.design + local SVG cache
from lxml import etree

CACHE_DIR = Path("/tmp/dmc-cache/iconify")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
pyconify.set_cache_dir(CACHE_DIR)  # offline-warm cache; first call is online


@dataclass
class IconRef:
    iconify: str            # "fluent:savings-24-regular"
    color: str              # "#022D2D" or "currentColor"
    x: int = 0
    y: int = 0
    size: int = 96
    z: int = 1
    rotate: float = 0.0
    opacity: float = 1.0


@functools.lru_cache(maxsize=2048)
def fetch_iconify_svg(prefix: str, name: str, color: str, size: int) -> str:
    """Returns inner SVG markup (without outer <svg> wrapper) for placement in a <g>."""
    raw = pyconify.svg(prefix, name, color=color, height=size, width=size)
    root = etree.fromstring(raw)
    # strip outer <svg>; keep its viewBox to compute scale
    inner = b"".join(etree.tostring(child) for child in root).decode()
    return f'<g data-iconify="{prefix}:{name}">{inner}</g>'


def render_iconify_cluster(slot: dict, brand: dict) -> str:
    """Compose 2-4 Iconify icons inside a single <svg> viewBox.

    Returns an inline <svg> string ready to drop into the HTML template.
    WeasyPrint renders inline <svg> as vectors in the PDF.
    """
    vp = slot["style_token"]["viewport"]
    pieces = []

    if slot["style_token"].get("bg_circle"):
        pieces.append(
            f'<circle cx="{vp["w"]//2}" cy="{vp["h"]//2}" r="{min(vp["w"], vp["h"])//2 - 4}" '
            f'fill="{brand["accent"]}" opacity="0.12"/>'
        )

    for icon in sorted(slot["icons"], key=lambda i: i["z"]):
        ref = IconRef(**icon)
        color = ref.color.replace("var(--color-primary)", brand["primary"]) \
                          .replace("var(--color-accent)",  brand["accent"])
        body = fetch_iconify_svg(*ref.iconify.split(":"), color=color, size=ref.size)
        transform = f'translate({ref.x} {ref.y}) rotate({ref.rotate} {ref.size/2} {ref.size/2})'
        pieces.append(
            f'<g transform="{transform}" opacity="{ref.opacity}">{body}</g>'
        )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vp["w"]} {vp["h"]}" '
        f'width="{vp["w"]}" height="{vp["h"]}" role="img" aria-hidden="true">'
        + "".join(pieces)
        + "</svg>"
    )


def resolve_decoration(slot: dict, brand: dict, client_slug: str) -> str:
    """Walk the fallback chain — never returns empty."""
    for entry in slot["fallback_chain"]:
        kind, key = entry.split(":", 1)
        if kind == "client_library":
            path = Path(f"assets/illustrations/{client_slug}/{key}.svg")
            if path.exists():
                return _tint_inline_svg(path.read_text(), brand)
        elif kind == "shared_library":
            path = Path(f"assets/illustrations/_shared/{key}.svg")
            if path.exists():
                return _tint_inline_svg(path.read_text(), brand)
        elif kind == "iconify_cluster":
            pattern_slot = _materialize_cluster_pattern(slot, key)
            return render_iconify_cluster(pattern_slot, brand)
    # last-resort: a single Iconify sparkle so slot is *never blank*
    return render_iconify_cluster(_fallback_sparkle_slot(brand), brand)
```

**WeasyPrint nuance:** WeasyPrint accepts inline `<svg>` and renders it as vector in the PDF, but it has limitations applying *outer* CSS `fill:` rules to inline SVG paths and historically crashed on `currentColor`. ([Kozea/WeasyPrint #1497](https://github.com/Kozea/WeasyPrint/issues/1497), [#1258](https://github.com/Kozea/WeasyPrint/issues/1258)) — **mitigation: bake the colour into each path attribute before injecting** (which is exactly what `pyconify.svg(..., color=…)` already does on the Iconify side). Don't rely on `currentColor` at WeasyPrint render time.

**Caching:** all Iconify fetches go through `pyconify`'s local cache; after the first warm-up run, a 20-page report uses 0 network calls. Cluster patterns are hashed (`{pattern_id}+{primary}+{accent}`) and the final composed `<svg>` is memoised.

**Determinism:** the `decoration_slot.pattern` field is filled by Agent 3 (Struktur) using a deterministic lookup from `{page_st_type, theme_tag}` — never AI in the hot path. Stable inputs → identical output for re-renders.

---

## 7 · Evidence with URL citations

- Iconify icon-sets index, 209 sets / ~292k icons: [icon-sets.iconify.design](https://icon-sets.iconify.design/)
- Iconify Render-SVG API (URL pattern, `color`/`width`/`height`): [iconify.design/docs/api/svg.html](https://iconify.design/docs/api/svg.html)
- Iconify API repo: [iconify/api](https://github.com/iconify/api)
- pyconify (Python wrapper, local cache): [pyapp-kit/pyconify](https://github.com/pyapp-kit/pyconify)
- Tabler Icons (MIT, 6,146 icons): [tabler/tabler-icons](https://github.com/tabler/tabler-icons)
- Fluent UI System Icons (MIT, ~19k via Iconify): [microsoft/fluentui-system-icons LICENSE](https://github.com/microsoft/fluentui-system-icons/blob/main/LICENSE), [icones.js.org/collection/fluent](https://icones.js.org/collection/fluent)
- Flat Color Icons set page on Iconify: [icon-sets.iconify.design/flat-color-icons/](https://icon-sets.iconify.design/flat-color-icons/)
- SVGMaker API reference (REST, credits, styles): [svgmaker.io/docs/api-reference](https://svgmaker.io/docs/api-reference); MCP server: [GenWaveLLC/svgmaker-mcp](https://github.com/GenWaveLLC/svgmaker-mcp)
- Recraft V4 text-to-vector ($0.08 / V4 Pro $0.30): [fal.ai/models/fal-ai/recraft/v4/text-to-vector](https://fal.ai/models/fal-ai/recraft/v4/text-to-vector), [fal.ai/models/fal-ai/recraft/v4/pro/text-to-vector](https://fal.ai/models/fal-ai/recraft/v4/pro/text-to-vector)
- 2026 AI SVG generator benchmark (only Recraft + SVGMaker ship clean paths): [vectosolve.com](https://vectosolve.com/blog/best-ai-svg-generators-text-to-vector-2026)
- svgwrite (unmaintained, geometric only): [mozman/svgwrite](https://github.com/mozman/svgwrite)
- WeasyPrint inline-SVG limitations (fill/currentColor): [Kozea/WeasyPrint #1497](https://github.com/Kozea/WeasyPrint/issues/1497), [#1258](https://github.com/Kozea/WeasyPrint/issues/1258), [Image and SVG Handling — DeepWiki](https://deepwiki.com/Kozea/WeasyPrint/4.2-image-and-svg-handling)
- Freepik commercial-use vector library + licence: [freepik.com/free-photos-vectors/commercial-use](https://www.freepik.com/free-photos-vectors/commercial-use)
- Existing companion docs: `PRD.md §12`, `VISUAL_ASSETS.md §3.3` (this proposal extends both — they already budget for `METAPHOR_OBJECT` and a closed-set illustration library).

---

**Bottom line.** The MVP is "Iconify clusters in every slot, deterministically chosen, brand-tinted, composed of 2–3 overlapping icons in a 220×180 viewBox." That alone closes the never-blank requirement at $0 marginal cost. The same slot-payload schema accepts richer assets (shared commissioned library, per-client AI kit, per-client commissioned kit) without any template changes — `fallback_chain` walks tiers in preference order and the cluster is always the safety net at the bottom.
