# Phase A — Renderer Theme-Lock — Design

**Date:** 2026-06-05 · **Status:** Approved + gap-audited (14 gaps folded, see §11)
**Scope layer:** Renderer (`research/v7-renderer/`) only. Package contract + preprocessor untouched.
**Part of:** the 8-root-cause visual-appeal program (`docs/superpowers/2026-06-05-visual-appeal-gap-map.md`). This phase = Theme 1 (timid tokens) + Theme 7 (generic furniture).

---

## 1. Goal

Make the shared renderer theme produce pages with the hierarchy, depth, and per-brand identity of a hand-designed InDesign deck — by (a) raising the type/spacing/color tokens to the documented DMC canon, (b) replacing flat/invisible grounds with a perceptible, canon-legal ground, and (c) wiring the design axes so different brands render differently. One-time **theme-lock**: shared values fixed once so a later per-page loop never thrashes 20 pages.

## 2. Why (root causes this closes) — current state corrected per gap-audit

From the audit + canon (`08_DMC_Design_System_v2.md`, `DMC_InDesign_Spec_v1.md` MODUL 4/6/7, `richard-grammar-v2.md`):

- **Shout components render at 15pt.** `.c-these`, `.c-key-insight__body`, `.c-authority__heading`, stat values all use `--type-h2` = 15pt. Canon: H2 18–22, H1 28–40, big stat **48–72**; no token for the 48–72 range exists. (`components.css:572/760/834/151`, `base.tokens.json`)
- **Invisible page ground.** The `.page` light ground is the 5%-accent `--color-ground-wash` (`compile_tokens.py:149,154`), consumed by `assembler.py:302-305` (light/cool_light hook) **and** `assembler.py:168` (the @page folio-band gradient). It is imperceptible.
- **Pale tint panels (the real targets).** **Correction:** `.c-authority` and `.c-dark-recap` are **already** solid `--color-ink` (`components.css:520,553`) — not pale. The genuinely pale `--color-accent-tint` surfaces are `.c-callout-panel` (:296), `.c-cost-block` (:857), `.c-stat-callout` (:494), `.c-hflow__step` (:396), and `.c-key-insight` (:748, tint *by design*). Phase A does **not** "retire pale authority panels" (they aren't pale); it (a) re-points authority/recap through a new `--color-panel` indirection so recipes can flip ink↔primary, and (b) makes a *per-component* decision about the genuine tint surfaces (see §5.3).
- **Inert axes.** `texture` and `accent_mechanic` are emitted as `data-*`/computed but reach no CSS; `ground_mode` only paints the faint wash; `density="balanced"` (default) matches no rule. Every brand collapses to one look. (`compile_tokens.py:174-179`, `density.css`)
- **Headings render in the body face.** Montserrat is resolved but never `@font-face`-loads (format-4 cmap) → falls back to Source Sans 3 = body. (`base.tokens.json` `$comment`, `assembler.py:155-158`)
- **Generic furniture.** Tight asymmetric margins, identical per-page header, bare folio, no hairline system. (`assembler.py:162/244/180`)

## 3. Non-goals (later phases)

- **Per-pattern adoption** across all 13 `styles/st_*.css` + templates → **Phase B**. Phase A delivers the shared layer + verifies on the cover + 1–2 representative pages.
- Wiring generated background/texture **image assets** (`report_assets`) onto content pages, recovering dropped infographics, fill-variant defaults, QR removal → **Phase B**.
- Improving **per-brand axis values** at source (onboarding palette/texture/density) → **Phase C**. Phase A makes axes *act*; Phase C makes them *carry richer values*.
- **Generic per-page bleed opt-in → deferred to Phase B** (gap #14: overlaps the existing chrome-suppressing `@page bleed`; R1 renders to the content box, not the physical sheet, so a "3mm bleed" is meaningless until Layer-3).
- Image resolution/prompts, founder-photo quality, the quality loop → Phases C/D/E.

## 4. Governing constraints

- **Brand-agnostic.** No client name/hex/font literal in renderer LOGIC. New color values **derive from brand tokens** or are **universal design constants** (pt sizes, accent alphas, canon neutral constants — the same class as the existing `body #333` / `on-dark #fff` in `base.tokens.json`). Guard tests stay green.
- **Canon is the schema source — never a client's finished PDF.**
- **No PowerPoint effects.** No drop shadows / glow / 3D on type or panels (`08_v2` A.1; grammar §6.1 #2). No rounded text panels (#1, except the two canon exceptions: CTA box, mechanism step cards). No gradient on type (#4). Depth = dark panels, hairlines, ghost numerals, texture grounds, big numbers.
- **Accent ≤ 10% area/page** (`08_v2` C.2). The header accent tick (§5.7) is sized to stay within budget.
- **Font loadability.** Only format-12-cmap faces load in WeasyPrint here (Adobe Source family). Verify embedding with `pdffonts`, never a visual diff.
- **No silent feature collapse.** Any mechanism must be verified to actually paint in **WeasyPrint 68.1** (its SVG engine supports only `feOffset`/`feBlend` — `feTurbulence`/`feColorMatrix` are ignored; see §5.4).
- **No regression / golden contract unchanged.** Renderer unit suite stays green; the `resolved_package.json` contract is not touched (renderer-internal). **Exception:** the 20-page apex **visual-regression baseline is intentionally re-committed this phase** after human sign-off — it is *not* part of the must-stay-green set (§7, gap #10).
- **Verification bar.** Render the **real apex deck** (20 pages) and compare **whole pages** to Richard's references. Verify by viewing pixels; page count = 20.
- **Ops.** No git. Renderer venv + `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib`. One-doc-per-process in font tests.

## 5. Locked design decisions

### 5.1 Type scale — "B" (universal ramp)
New/changed tokens in `base.tokens.json` `type` (net-new: `source`, `caption`, `cta`, `signature`, `pullquote`, `stat-xl`, `stat`; changed: `h3` 11→14, `h2` 15→20, `display` 24→32):

| token | pt | token | pt |
|---|---|---|---|
| `source` | 7.5 | `h2` (thesis/subhead) | **20** |
| `caption` | 8.5 | `signature` | 28 |
| `eyebrow`/`label` | 9.5 | `display` (H1) | **32** |
| `body` | 10.5 | `display-xl` (cover) | 40 |
| `cta` | 11.5 | `stat-xl` (**new**, Zahl_Gross) | **60** |
| `h3` | 14 | `stat` (**new**, case result) | 40 |
| `pullquote` | 18 | `hero` (cover max) | 48 |

- **Re-points:** `.c-these`, `.c-key-insight__body`, `.c-authority__heading` → `--type-h2` (20). `.c-stat-strip`/`.c-stat-rail`/`.c-stat-callout` values → `--type-stat-xl` (60); `.c-stat` compact tier = 40. `.c-two-tone` → `--type-display` (32).
- **Tracking:** H1 −0.015em; stat −0.025em; eyebrow/label keep their existing ALL-CAPS letter-spacing (≈+0.16em, canon Label_Klein).
- Tokens carry `$comment` canon citations (provenance, not literals).
- Net-new tokens are **added before** re-points so no token is referenced before it exists; any pull-quote `calc()` in `components.css` that referenced the old display is re-derived.

### 5.2 Display typeface — serif default, axis-backed
- Default display = **Source Serif 4** when `headline_type` ∈ {unset, `serif`}. **Note:** the current `BrandAxes`/resolver default for `headline_type` is `sans`; Phase A changes that default to `serif` (renderer-consumed; the value still comes from the axis). Body stays **Source Sans 3**.
- `sans` → Source Sans 3 ExtraBold display; `sans_allcaps` → Source Sans 3 + `text-transform:uppercase` + `letter-spacing:0.04em` (a real `[data-headline-type="sans_allcaps"]` rule — currently inert).
- Client house font keeps priority. Any non-Source face must ship a format-12 cmap or it silently falls back → flagged, not hardcoded.
- `render.py` `_REQUIRED_FONTS` preflight corrected to the faces actually `@font-face`-loaded (today it checks Montserrat).

### 5.3 Color system
- **Neutral ramp** = expose the **existing brand neutral tokens** as named roles (no new derivation, no binning): `--color-neutral-dark` = brand neutral-dark, `--color-neutral-mid` = brand neutral-mid, `--color-neutral-light` = brand neutral-light. Body text stays `#333` (universal canon constant). This defuses any hardcoded-grey risk — the roles are the brand's own values.
- **`--color-panel` / `--color-on-panel` (new, emitted by `compile_tokens`):** `--color-panel = --color-primary` when `axes.accent_mechanic == "contrasting_hue"` (else `--color-ink`); `--color-on-panel` via the existing luminance on-color rule (`compile_tokens.py:150-159`). `.c-authority` + `.c-dark-recap` change their **hardcoded `--color-ink`** to `var(--color-panel)` (mechanical indirection so recipe #2 can flip them to primary); the `.c-authority--primary` modifier is removed (recipe drives ink-vs-primary).
- **Per-component tint decision (gap #11):**

  | component | Phase A fill |
  |---|---|
  | `.c-authority`, `.c-dark-recap` | `var(--color-panel)` (was hardcoded `--color-ink`) |
  | `.c-key-insight` | **KEEP** `--color-accent-tint` (accent-ruled tint payoff, by design) |
  | `.c-callout-panel`, `.c-cost-block`, `.c-stat-callout`, `.c-hflow__step`, `.c-bar-chart` track | **KEEP** `--color-accent-tint` (functional tints, unchanged) |

- **Accent** discipline unchanged (≤10% area; fires on numbers/labels/rules/pills/glyphs/links). `--color-accent-tint` (12%) retained.
- **`--color-ground-wash` is NOT deleted** (gap #5/#8): it remains for the @page folio-band gradient (`assembler.py:168`). Its role as the `.page` **content ground** is replaced by `--color-ground` (§5.4). "Retired" means demoted from content-ground duty, not removed.

### 5.4 Ground system (mechanical rules, not a palette-keyed selector)
**The "three recipes" (#1 warm-editorial / #2 clean-corporate / #3 rich-premium) are emergent presentations of three mechanical rules** — there is no separate palette-keyed selector (gaps #2/#3 made that unbuildable: `palette`/`accent_mechanic` reach no CSS):

1. **Perceptible content ground (always-on, replaces the invisible wash).** `[data-ground-mode=light|cool_light] .page { background-color: var(--color-ground); }`. `--color-ground` is **derived in `compile_tokens` (Python)**: blend `--color-neutral-light` toward `--color-neutral-dark` by ~5% (perceptible body, clamped L>0.93), emitted as `rgb()`. Brand-derived, no hue/temperature literal (canon has no warm/cool axis; "warm/cool" language is dropped). `[data-ground-mode=dark|tonal]` → ink ground + on-dark text (already partly wired; strengthened).
2. **Whisper grain (always-on for light grounds = the "rich" default the user picked).** A static, brand-agnostic neutral-noise **data-URI PNG tile** is layered on `.page` as a second `background-image` at **~0.035 effective alpha**, `background-repeat:repeat`, z-order below content. **NOT `feTurbulence`** — verified to collapse to a flat off-color solid in WeasyPrint 68.1 (gap #4, empirically tested). The tile is generated once by a committed deterministic Pillow script (`scripts/gen_grain_tile.py`, 128×128, seeded), embedded as base64 in the head CSS (base64 ≠ `#hex`, so the literal guard stays green). Lives in `assembler.py` head CSS (the documented carve-out from the components.css class-scope guard).
3. **Stronger texture character (axis-gated).** `[data-texture=marble_paper|crumpled_paper]` swaps the whisper tile for a stronger texture treatment; `[data-texture=smooth]` keeps just the perceptible ground (whisper grain still on — see note). `[data-texture=photo]` reserved for Phase B image grounds.

**Default note:** because `texture` defaults to `smooth`, the whisper grain is **decoupled from the texture axis** (it is part of the always-on light-ground ground), so the *no-signal default is "rich"* (perceptible ground + whisper grain + ink panel) as chosen — without a cross-layer change. Stronger marble/parchment is the only thing the `texture` axis adds.

**`cool_light` reachability:** `[data-ground-mode=cool_light]` is wired in CSS, but the preprocessor `GroundMode` enum may not yet emit `cool_light` (`resolve_axes.py`). If unreachable, the branch is harmless dead CSS; making it reachable is a Phase-C onboarding item (noted §9).

### 5.5 Depth toolkit (canon-legal, shared)
Shared, reusable so every pattern can use them: oversized **ghost numeral**, **hairline-rule system** (`--rule-hairline` weight/role: eyebrow rule, section divider, accent top-rule on panels), **dark panel** surface, **big-number** treatment. **No shadows, no rounded text panels.**
- **Routing (gap #9):** decorative **attribute-driven** rules (grain, ground, `[data-texture]`) live in `assembler.py` head CSS (excluded from the components.css class-scope guard + the styles/*.css hex scan). New **class-scoped** `.c-*` utilities (`.c-rule`, `.c-ghost-num`) go in `components.css` **and the allowed-prefix tuple in `tests/test_components.py::test_components_css_is_token_only_and_class_scoped` is updated** to include them. Grain stays hex-free (base64/`currentColor`/`rgba()` only).

### 5.6 Axis wiring
| axis | today | Phase A effect |
|---|---|---|
| `headline_type` | serif vs sans; default `sans` | default→`serif`; add `sans_allcaps` rule |
| `texture` | **inert** | `[data-texture]` → stronger marble/parchment overlay (whisper grain is always-on, decoupled) |
| `ground_mode` | 5% wash only | perceptible `--color-ground`; dark/tonal ink ground |
| `accent_mechanic` (`contrasting_hue`) | inert | `--color-panel` = primary vs ink (Python, in compile_tokens) |
| `density` | only compact/spacious; padding hardcoded | add `[data-density="balanced"]`; panel padding scales via `--density-*` (NOT body leading — §5.7) |

### 5.7 Furniture / grid (Theme 7, canon)
- **Margins** T16 / B20 / I18 / O14 mm (canon).
- **Body leading = ABSOLUTE 14pt FEST** (gaps #7/#13): `line-height: 14pt` (pt unit) on body/`p`, **never a unitless multiplier** (canon InDesign L241 "Leading FEST, nicht automatisch"; grammar L534-540). 10.5pt body → 14/10.5 ≈ 1.333 lands on a consistent 14pt rhythm. **`html` font-size stays 10pt** (inert for absolute-pt tokens); `body` sets `font-size: var(--type-body)` (10.5pt). **`--density-lead` is demoted:** density drives column-gap + paragraph-spacing only; body leading is FEST 14pt under all densities. (WeasyPrint has no native baseline-grid/`line-height-step`; we get the 14pt rhythm via fixed leading, not a true grid-snap — wording softened accordingly.)
- **Header:** gains a **static accent tick** = a `6mm × 0.6mm` `var(--color-accent)` segment adjacent to the (currently unused) eyebrow slot. **Per-page section/chapter TEXT is deferred** (gap #12): no package field carries it yet, and the header is a single running element that can't vary per page without a string-set rework — so Phase A ships only the static tick + the structural eyebrow slot; per-page eyebrow text is a later phase when the package can carry it.
- **Footer:** add a `0.2mm var(--color-muted)` hairline above/below the folio. **Folio stays small mid-grey, corner, NEVER accent** (grammar §6.1 #14) — the accent tick is **header-only**.

## 6. Architecture & files

| file | change |
|---|---|
| `tokens/base.tokens.json` | type ramp B (+ `stat-xl`/`stat`/`source`/`caption`/`cta`/`signature`/`pullquote`); `$comment` citations; font block stays Source family |
| `tokens/compile_tokens.py` | emit neutral-role aliases + `--color-panel`/`--color-on-panel` (accent_mechanic branch) + `--color-ground` (derived) + `--type-stat*`; `headline_type` default→serif + `sans_allcaps` data-attr path |
| `styles/components.css` | re-point shout components (§5.1); authority/recap → `var(--color-panel)`; keep listed tint panels; new `.c-rule`/`.c-ghost-num` utilities |
| `styles/density.css` | add `[data-density="balanced"]`; route panel padding through `--density-*`; body leading removed from the `--density-lead` path |
| `assembler.py` (head CSS) | `--color-ground` light/cool_light `.page` ground; **keep** `--color-ground-wash` for the @page folio band (`:168`); always-on whisper-grain `background-image` (base64 PNG) + `[data-texture]` overlays; margins; body `line-height:14pt`; header accent tick; footer hairline |
| `render.py` | fix `_REQUIRED_FONTS` to the loaded faces |
| `scripts/gen_grain_tile.py` (new) | deterministic Pillow noise tile → committed base64 string used by the head CSS |
| `tests/test_components.py` | extend allowed-prefix tuple for `.c-rule`/`.c-ghost-num` |

**Data flow:** `axes` → `compile_tokens(brand, axes)` → CSS custom props + `data-*` attrs on `<html>` → `components.css` / `assembler.py` head CSS consume them. No new package fields; no contract change.

## 7. Testing strategy

- **Unit (renderer venv):** `compile_tokens` emits the B ramp + `--color-panel` (=primary when `accent_mechanic=contrasting_hue`, else ink) + `--color-ground` (derived from brand neutrals, not a constant) + `--type-stat-xl/stat`; `[data-headline-type=sans_allcaps]`, `[data-texture]`, `[data-density=balanced]` produce expected declarations; **body `line-height` is emitted as absolute `14pt`** (FEST). One-doc-per-process for font assertions.
- **Texture paints (gap #4):** render a `.page` and assert **pixel variance > 0** over a clean (text-free) margin band for the grained default, and the grain is *not* a flat solid — so a future regression to a collapsed/flat ground fails automatically (not just human review).
- **Guard:** extend `test_no_client_name_in_logic` / `test_no_literals_in_architecture` to any new module; **update the `test_components.py` allowed-prefix tuple** for the new `.c-rule`/`.c-ghost-num` utilities; grain base64 contains no `#hex`/client literal.
- **Contract:** golden `resolved_package.json` test unchanged + green (proves the seam is untouched).
- **Font embedding:** `pdffonts` shows Source Serif 4 + Source Sans 3 embedded (not system fallback).
- **Visual-regression (gap #10):** `test_visual_regression_apex` **WILL fail on every changed page — expected, not a regression.** Do **not** re-baseline to chase green. Re-baseline **LAST**, only after the §4 human whole-page review vs Richard confirms each render is *better* — so a worse render is never frozen. The apex baselines are intentionally regenerated this phase and are excluded from the must-stay-green set.
- **Visual (the bar):** render the real apex deck (20 pages); compare cover + a case-study + the about page (min) to Richard; page count = 20.

## 8. Risks & mitigations

- **Grain renders flat** (the feTurbulence trap) → mitigated: tiled base64 PNG (verified to paint), + the variance>0 test.
- **Bigger type overflows existing pages** → expected; per-pattern reflow is Phase B; Phase A flags (never silently shrinks) via the advisory overflow validator. (The existing ST-07A `--long` auto-shrink is a per-pattern concern revisited in Phase B.)
- **Leading regression** → body leading pinned to absolute 14pt FEST; unit-tested; (the old "~1.42×10pt" framing is dropped — it doesn't survive the 10.5pt body bump).
- **Font swap regression** → `pdffonts` + render tests; serif default already loads.
- **Guard/allowlist breakage** → §7 explicitly extends the allowlist + keeps grain hex-free.

## 9. Open questions

- `cool_light` `GroundMode` may be unreachable from the preprocessor today (`resolve_axes.py`); the CSS branch is harmless until Phase C wires onboarding to emit it. Non-blocking.

## 10. Self-review

Placeholder scan: none. Consistency: token/var names in §5/§6/§7 align; recipe rules §5.4 match the axis table §5.6; per-component tint table §5.3 matches §5.1 re-points. Scope: per-pattern adoption + bleed opt-in explicitly deferred. Ambiguity: grain mechanism, leading model, recipe selection, panel targets, ground derivation, header/footer geometry all pinned to concrete values/rules.

## 11. Gap-audit resolutions (2026-06-05, 14 confirmed)

| # | sev | gap | resolution |
|---|---|---|---|
| 1 | blocker | feTurbulence grain collapses to flat in WeasyPrint 68.1 | §5.4: tiled base64 PNG tile + variance>0 test |
| 2 | blocker | recipe selection keyed on axes with no DOM hook | §5.4/§5.6: panel ink/primary decided in compile_tokens (Python via `accent_mechanic`); no palette-keyed CSS selector |
| 3 | blocker | "warm/cool palette" undefined + warm ground no derivation | §5.4: drop temperature language; `--color-ground` = derived neutral blend |
| 4 | blocker | grain has no opacity/mechanism numbers | §5.4: 0.035 alpha, 128px tile, static, gated |
| 5 | high | `--color-ground-wash` retired but consumed by folio gradient + light hook | §5.3/§5.4/§6: keep the var for `:168` folio; new `--color-ground` for content ground |
| 6 | high | spec mis-described authority panels as pale (already ink) | §2/§5.3: corrected; re-targeted to the real tint panels |
| 7 | med | FEST leading framed as a multiplier | §5.7/§8: absolute `14pt`, unit-tested |
| 8 | med | ground-wash folio consumer not in file list | §6: assembler `:168` named |
| 9 | med | components.css allowlist + hex guard block new utilities | §5.5/§7: route attribute rules in assembler head; update allowlist; hex-free grain |
| 10 | med | 20-page visual baseline will fail / re-baseline trap | §4/§7: intentional review-gated re-baseline; don't chase green |
| 11 | med | which panels convert to dark under-enumerated | §5.3: per-component tint table |
| 12 | med | header section-context/tick + footer hairline unsourced | §5.7: defer per-page text; static tick geometry; footer hairline color; folio never accent |
| 13 | med | 14pt grid vs html font-size/density leading unreconciled | §5.7: body line-height 14pt FEST; html stays 10pt; density off body leading |
| 14 | low | `[data-bleed]` overlaps existing `@page bleed` | §3: deferred to Phase B |
