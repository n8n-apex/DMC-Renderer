# DMC Visual Asset Pipeline — Architecture & Prompt Specs

**Companion to PRD.md.** Defines how *every* visual element in a DMC report is produced.

> **Architecture decision:** Only **photography** is AI-generated (Nano Banana Pro).
> **Illustrations, diagrams, charts, icons, flows, comparisons, and metaphor
> objects are all renderer-side** — SVG components driven by data and tinted
> via CSS variables. This eliminates the "AI might give us 3D isometric today"
> failure mode, makes every diagram repeatable across reports, and turns the
> illustration library into a one-time investment instead of a per-render cost.

---

## 0 · Why the previous approach was failing

| Symptom in the four sample images | Root cause |
|---|---|
| Polygonal avatars for case studies | Generated humans where references use real customer photos or no photo |
| Generic "dark office at night" | Not industry-specific; references show the client's actual world |
| 3D isometric for mechanism diagrams | Master System §7.2 forbids 3D outright; references use 2D editorial diagrams |
| Treating charts as image-gen targets | Charts are vector data → always render as SVG, never generate as raster |
| One image-gen prompt for fundamentally different asset categories | Photography needs cinematography language; diagrams need geometry-from-data; both being routed through the same template guarantees mediocrity at both |

---

## 1 · The asset router

For each visual slot in a page, a Router Agent decides the asset category before the right pipeline is invoked. Routing is deterministic for Tier-1 page types based on `page_st_type` + `image_slot_id` + briefing flags.

### 1.1 Asset categories and their pipelines

| Category | Pipeline | Notes |
|---|---|---|
| `REAL_PHOTO_HUMAN` | **Client-supplied photo only.** No AI generation. If missing → `InitialsBlock` CSS component. | Author portraits, customer case-study portraits, team photos |
| `REAL_PHOTO_CONTEXT` | **Nano Banana Pro** — cinematic industry-specific photography | The only AI path |
| `DIAGRAM` | **Renderer SVG component**, data-driven, brand-tinted via CSS vars | 8 archetypes; see §3 |
| `ICON` | **Lucide / Tabler** icon set, CSS-tinted | Inside diagram nodes, status-quo tiles, Schritt cards |
| `METAPHOR_OBJECT` | **SVG library asset** (commissioned once), brand-tinted | Brain, pickaxe-and-coins, leaky bucket, etc. |
| `DATA_CHART` | **Renderer SVG via D3** from numbers in briefing | Bar / line / column / horizontal-bar |
| `PROCESS_FLOW` | **Renderer CSS component** (numbered cards, connected) | Schritt 1–6 process cards |
| `COMPARISON_TABLE` | **Renderer CSS component** (2-col with check/cross) | Vorher/Nachher, Alt-vs-Neu |
| `DEVICE_MOCKUP` | **Renderer composite** — real screenshot inside SVG device frame | Phone / laptop / iPad with real screens |
| `LOGO_OR_BRAND` | Fetched from asset library | Client logo, "bekannt aus" media logos |

### 1.2 Reference-page → asset-category lookup table

| Reference page | Visual element | Category |
|---|---|---|
| All covers (ST-01) | Author / hero photo | `REAL_PHOTO_HUMAN` (mandatory client supply) |
| All covers backdrop | Workshop / practice / office | `REAL_PHOTO_CONTEXT` |
| ST-05 Über-Uns | Team photo | `REAL_PHOTO_HUMAN` |
| ST-05 Über-Uns | Bekannt-aus + Trustpilot | `LOGO_OR_BRAND` |
| ST-09 (icon-tile variant) | 6 small icon-tiles | `ICON` ×6 |
| ST-09 (numbered-list variant) | none | — |
| ST-14 Irrglauben | none (text only on dark panel) | — |
| ST-06 (aerz Vorsorge-Karussell) | 5 numbered circular nodes | `DIAGRAM:CircularFlow` + `ICON` ×5 |
| ST-06 (alex Not-Hire-Ökonomie) | Vertical flow w/ circular nodes | `DIAGRAM:LinearFlow` |
| ST-07A Fallstudie | Customer portrait | `REAL_PHOTO_HUMAN` (or `InitialsBlock`) |
| ST-07B (buch brain) | Single brain illustration | `METAPHOR_OBJECT:Brain` |
| ST-07B (buch Venn) | Three overlapping circles | `DIAGRAM:Venn3` |
| ST-07B (alex chart) | Comparison line chart | `DATA_CHART` |
| ST-07B (nikl phone screens) | Phone with screenshot | `DEVICE_MOCKUP` |
| ST-08 Charts spread (aerz p8) | 4 different charts | `DATA_CHART` ×4 |
| ST-22 Prozess (Schritt 1–6) | Numbered Schritt cards | `PROCESS_FLOW` |
| ST-26 Trust-Wall | 6–8 review cards | CSS component (avatars + stars in `ReviewCard`) |
| ST-31 Logo wall | Client logos | `LOGO_OR_BRAND` |
| ST-FAZIT | Atmospheric resolved-state photo | `REAL_PHOTO_CONTEXT` |
| ST-03 Rückseite | Optional muted backdrop | `REAL_PHOTO_CONTEXT` (low-key) |
| aerz p4 | Pickaxe-and-coins still life | `METAPHOR_OBJECT:PickaxeCoins` (commissioned SVG) |

**Per typical 20-page report, only ~4–6 visuals go through Nano Banana Pro.** Everything else renders deterministically from the briefing JSON.

---

## 2 · System prompt — `REAL_PHOTO_CONTEXT` (the only AI route)

This replaces the entire previous prompt template. Photography is the only thing the AI is asked to do. The prompt has three modes; everything else is a parameter.

```
You are the Photography Prompt Generator for DMC Reports — premium German B2B
direct-marketing magazines. You produce prompts for Nano Banana Pro that yield
photorealistic, editorial-quality images anchored in the SPECIFIC INDUSTRY of
the client. No generic stock. No clip-art. No 3D. No isometric. No illustrations.

Your output goes directly into Nano Banana Pro. Return ONE paragraph, no
labels, no JSON.

== HARD RULES (never violate) ==
- The image MUST depict the client's actual industry world. Never generic
  "modern office." If the client is dental → real dental practice. Construction
  → real construction site. Tax advisor → real tax advisor's desk. The reader
  must recognize their own world in the first half-second.
- No 3D, no isometric, no illustrated style. This route is photography only.
- No identifiable invented faces. When showing people generically, use back-
  views, silhouettes, soft-focus, or cropped (hands, posture) framing. Never
  invent sharp face features.
- No text, no logos, no watermarks, no embedded UI / charts on screens unless
  explicitly requested.
- Composition leaves NEGATIVE SPACE per `text_overlay_zone` so headlines sit
  on the image without clashing with detail behind them.

== THE THREE MODES ==

MODE: COVER_HERO  (3:4 portrait)
A cinematic photograph from inside the client's industry world during golden
hour or soft-blue overcast light. Shot on a 35mm or 50mm lens at f/2.8 to
f/4 for environmental depth, eye-level. The center-right of the frame is the
well-lit subject area; the left third is darker for headline overlay.
Real materials of that industry — [polished concrete / sawdust / dental chair
upholstery / law-office leather]. No staged poses. Documentary realism, the
kind of shot a serious magazine photographer would take on assignment.

MODE: STATUS_QUO  (any ratio per slot)
A medium shot inside the client's industry world capturing FRICTION or
STAGNATION specific to that industry — not generic overwhelm. A construction
foreman staring at a clipboard while a half-finished site stretches behind
him. A dentist's reception with three phone lines blinking and a stack of
unprocessed insurance forms. A book agent's desk with manuscripts piled
beside a cold coffee. The mood is "this is the real Tuesday afternoon," not
dystopian. Soft natural light, slight desaturation toward the shadows.
Documentary editorial style.

MODE: FAZIT_RESOLVED  (3:4 portrait)
The same industry world as MODE COVER_HERO or STATUS_QUO, but in its resolved
state. The construction site is finished and tidy at sunrise. The dental
reception is calm with one patient being greeted. The book agent's desk has
one book on it, neatly placed. Warmer light temperature, more breathing space,
fewer objects. Same camera grammar (35mm/50mm, f/2.8–4). The "after" to the
"before."

== HOW TO USE BRAND COLOR ==
Brand colors enter as ENVIRONMENTAL color, never as a filter or LUT:
- "Late golden light through scaffolding casts warm tones close to the
  client's accent #E6B85C onto the polished concrete floor."
- "Workspace painted in a deep teal close to #022D2D, with brass desk
  accessories adding accent warmth."
Avoid: "in the brand color" or "tinted [color]." The image must look like
a real place that happens to harmonize with the brand.

== PHOTOREALISM CUES ==
Add 1–2 imperfections per prompt: "natural skin texture on hands," "subtle
lens flare from a window," "slight motion blur on a moving figure in the
deep background," "fine dust visible in the backlight."

== INPUT VARIABLES YOU RECEIVE ==
client_industry, client_brand_palette (hex codes), mode (COVER_HERO |
STATUS_QUO | FAZIT_RESOLVED), text_overlay_zone (left | right | bottom |
none), aspect_ratio, page_content_summary.

Use page_content_summary to decide WHICH industry-specific scene to depict.
A page about scheduling chaos needs a calendar/clipboard scene, not a
generic worker. A page about client trust needs a face-to-face moment.

Return one paragraph, 80–140 words, ready for Nano Banana Pro.
```

---

## 3 · Renderer-side illustration library (the new core asset)

The library has three layers, all renderer-side, all CSS-tintable.

### 3.1 Layer A — Diagram archetypes (parametric SVG)

Each archetype is one templated SVG component. The renderer takes data from the briefing JSON and produces a finished diagram. No image generation involved.

| Archetype | Visual | Data shape |
|---|---|---|
| `CircularFlow` | N nodes (3–6) on a circle, connected by arc-segments | `{nodes: [{label, icon}], direction: cw\|ccw}` |
| `LinearFlow` | N nodes horizontal or vertical with arrows | `{nodes: [{label, icon}], orientation: h\|v}` |
| `Venn2` / `Venn3` | 2 or 3 overlapping translucent circles | `{circles: [{label, color_token}], intersections: [...]}` |
| `AxisQuadrant` | 2D plot with axis labels and 2–4 plotted points | `{axis_x: {label}, axis_y: {label}, points: [{x, y, label, accent: bool}]}` |
| `Funnel` | Vertical funnel with 3–5 horizontal bands | `{stages: [{label, value}]}` |
| `Cascade` | Stepped staircase with labels per step | `{steps: [{label, body}]}` |
| `ConcentricRings` | 3–4 concentric rings, innermost is goal | `{rings: [{label}]}` |
| `Tree` | Root with branches | `{root: {label}, branches: [{label, leaves: [...]}]}` |

These are SVG files in `templates/diagrams/*.svg.njk` (Nunjucks templates). Each is ~80–150 lines. The renderer fills slots with data + applies CSS variables for color.

**Color tinting:** every fillable region uses `fill="var(--color-primary)"` or `fill="currentColor"`. The brand-token CSS injector (PRD §6.1) sets the variables at render time. One archetype, infinite color palettes.

### 3.2 Layer B — Icon set

Use **Lucide** (open-source, MIT, Feather successor) as the canonical set. ~1500 icons, but you'll use ~50 for DMC reports.

Hot list of the icons you'll actually need (mapped to DMC content):
```
clock, calendar, target, search, magnifier, building, factory,
hammer, wrench, hard-hat, stethoscope, tooth, scale, scales,
gavel, shield, key, lock, calculator, file-text, briefcase,
trending-up, trending-down, chart-bar, chart-line, alert-triangle,
alert-circle, check, x, arrow-right, arrow-up, arrow-down,
percent, euro-sign, users, user, user-check, user-x, mail,
phone, message, megaphone, flag, award, star, thumbs-up,
zap, lightbulb, settings, refresh-cw, link, layers
```

All embed as inline SVG. CSS `color:` controls stroke; CSS `fill:` controls fill where applicable. Same architecture as Tabler / Heroicons if Lucide doesn't fit.

### 3.3 Layer C — Metaphor objects (the commissioned ones)

These are the unique illustrated still-lifes from the references that can't be assembled from primitives. The hard cases.

| Asset | Reference | Estimated commission cost |
|---|---|---|
| `Brain` (neural-network style, used in buch p4) | buch | $50–120 |
| `PickaxeCoins` (effort with no payoff, aerz p4) | aerz | $80–150 |
| `LeakyBucket` (loss / waste) | (composable) | $50–100 |
| `Pyramid` (hierarchy) | (composable) | trivial |
| `BrickWall` (obstacle) | — | $50–100 |
| `Scales` (justice / balance) | — | $50–100 |
| `Magnifier` (search / discovery) | — | already in Lucide |
| `Hourglass` (urgency) | — | already in Lucide |
| `Stairs` (progress) | — | composable from Cascade |
| `Compass` (direction) | — | already in Lucide |

**Build process per metaphor:**
1. Commission on Fiverr / 99designs / a hired illustrator. Brief: "single-color editorial line illustration, vector SVG, transparent background, optimized for tinting via CSS `currentColor`, 1024×1024 viewbox."
2. Receive `.svg`. Review.
3. Add to `assets/illustrations/`. Reference from templates as `<svg><use href="..." /></svg>`.
4. CSS `color: var(--color-primary)` re-tints it for every brand.

**Total one-time cost: $500–1500** for ~10 metaphors. After that, library is closed-set forever. New report needs a new metaphor → commission, add to library, never pay again.

This is how every high-end editorial design team works — they have a closed in-house library of metaphor SVGs. You're building the same thing, just owned by code instead of a designer's local Illustrator folder.

---

## 4 · `REAL_PHOTO_HUMAN` — the policy (unchanged)

Stop generating fake humans for case studies.

| Situation | Behavior |
|---|---|
| Customer photo provided | Use it. Resize/crop per template ratio. |
| No customer photo, real name allowed | `InitialsBlock` component: initials in a colored circle + name + role. No photo. |
| No customer photo, pseudonym | Same `InitialsBlock`, with pseudonym. |
| Author photo missing | **Block the report.** Per Master System §3.1, author photo is a Gate-1 input. Don't ship without it. |

**Why no generated humans:** generated polygonal heads or stylized stand-ins read as "we don't have this customer's photo and tried to hide it." A clean `InitialsBlock` reads as a deliberate Robb-Report-style anonymous case study.

---

## 5 · n8n routing

Replace the current image-prompt node with this fan-out:

```
[Page in report]
   │
   ▼
[Router: asset_category]   ← deterministic for Tier-1 ST types
   │
   ├─ REAL_PHOTO_HUMAN ────→ [Asset library lookup]
   │                          └─ if missing → [InitialsBlock CSS component]
   │
   ├─ REAL_PHOTO_CONTEXT ──→ [PHOTOGRAPHY prompt builder]
   │                          → [Nano Banana Pro]
   │                          → [Vision validator (§6)]
   │                          → [Cache to S3/R2]
   │
   ├─ DIAGRAM:<archetype> ─→ [Forward to renderer; SVG component takes data]
   ├─ ICON ───────────────→ [Forward to renderer; Lucide lookup]
   ├─ METAPHOR_OBJECT ────→ [Forward to renderer; library SVG + CSS tint]
   ├─ DATA_CHART ─────────→ [Forward to renderer; D3 SVG from numbers]
   ├─ PROCESS_FLOW ───────→ [Forward to renderer; CSS component]
   ├─ COMPARISON_TABLE ───→ [Forward to renderer; CSS component]
   ├─ DEVICE_MOCKUP ──────→ [Compositor: real screenshot + SVG frame]
   └─ LOGO_OR_BRAND ──────→ [Asset library lookup]
```

Eight of the ten routes terminate at the renderer with no AI involvement. Only `REAL_PHOTO_HUMAN` (sometimes) and `REAL_PHOTO_CONTEXT` (always) are AI-touched.

---

## 6 · Validation step (photography only — required)

Every Nano Banana Pro output goes through a vision-model validator before caching:

```
validator(image, mode, expected_palette, expected_industry):
  checks:
    - photoreal: photographic look, not painted / 3D / illustrated
    - 3D-detect: rejects any isometric / rendered look (auto-reject)
    - text-detect: rejects images with embedded text/numbers
    - palette: are dominant colors within ΔE 15 of expected client palette?
    - industry-anchor: scene matches the named industry (semantic match)
    - face-policy: any sharp invented faces? (reject if subject_is_real_person == false)
  returns: {pass: bool, reasons: [], retry_with_corrections: str | null}
```

Use Gemini 2.5 Pro Vision or Claude Sonnet as the validator. Reject + retry up to 2× with corrected prompt. After 2 failures → human review queue.

(No equivalent validator needed for renderer-side outputs because they are deterministic — what you author is what you get.)

---

## 7 · Why this architecture is hard to break

| Failure mode | What stops it |
|---|---|
| AI gives 3D isometric mechanism | Mechanisms are now CSS/SVG, not AI |
| AI gives polygonal avatar | Removed from pipeline — InitialsBlock instead |
| Chart numbers come out garbled | Charts are D3 SVG from data, not AI |
| Brand color drift | All renderer outputs use CSS variables; per-client palette swaps with one var change |
| New client adds 17th industry | Photography prompt accepts industry as input — no template change |
| New diagram type needed | Add one new archetype to Layer A — every report can use it |
| Metaphor needed that's not in library | Commission once → library → reusable forever |

---

## 8 · Summary — what to change today

1. **Add the Router Agent.** Switch routes by asset category from the §1.2 lookup. Deterministic for Tier-1.
2. **Kill the polygonal-avatar prompt entirely.** Replace with `InitialsBlock` CSS component.
3. **Replace the entire current 5-template image-gen prompt with the single PHOTOGRAPHY prompt** in §2 above.
4. **Build out the renderer's illustration library** in three layers: archetypes (§3.1), Lucide icons (§3.2), commissioned metaphors (§3.3).
5. **Add the vision validator** as a quality gate after every Nano Banana output.
6. **Make industry specificity mandatory** in every photography prompt — no "modern office." Every prompt names the client's actual industry world.

The architecture is now: **one AI route for photography, nine deterministic routes for everything else.** Realism stops being something the AI is asked for and instead emerges from using the right tool for each visual category.
