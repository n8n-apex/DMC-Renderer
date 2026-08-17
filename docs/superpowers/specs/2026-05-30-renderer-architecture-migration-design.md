# Renderer Architecture Migration — Design / PRD

**Status:** In design — pending user review
**Date:** 2026-05-30
**Component:** `research/v7-renderer/` (Layer 2) + one additive contract change in `research/preprocessor/`
**Predecessor:** `2026-05-30-renderer-architecture-research.md` (the ADR this implements)
**Build target (quality bar):** `2026-05-30-reference-design-system.md` — the concrete per-ST layouts + the **22-item richness checklist** the step-6 rebuild must hit (brand-agnostic; the reference is a quality bar, not a schema source).
**Decisions locked (user, 2026-05-30):** stay on **WeasyPrint**; **proper re-foundation, spec-first**.

---

## 1. Goal

Re-found the renderer on a real software architecture so it produces **reference-quality** output AND is **provably brand-agnostic** — killing both the "blandness" and the "client-pollution" failure modes at their root. Same engine (WeasyPrint), fundamentally better structure:

> `report.json (content) + brand tokens + §4.0 axes + assets` → **design-token layer** → **Jinja2 templates** built from an **atomic component library** → **axis-driven theming** → WeasyPrint → **visual-regression-tested** PDF.

The current renderer hand-builds HTML/CSS in Python f-strings with literal fonts/colors/labels baked into code. That is the disease. This spec replaces it layer by layer, incrementally, keeping the `PageFragment`/assembler contract and the test suites green throughout.

## 2. Non-negotiable principles

- **Grammar is the source of truth for design RULES.** `richard-grammar-v2.md` (+ Richard's 5 LIVE spec docs) defines the *universal* DMC design system. The reference apex PDF is a **quality bar only**, never a schema source. Every design decision is classified: **universal rule → code/tokens** (cited to a grammar §); **per-client value → data** (brand tokens, axes, content, images).
- **Zero client specifics in logic.** No client hex, font literal, name, or German label in code/CSS. Enforced by extended guard tests (§9). Per-client = data swap only.
- **Deterministic.** No AI, no randomness in the renderer; identical input → identical PDF; verified by visual-regression baselines.
- **Incremental + reversible.** Each migration step keeps `PageFragment` + the assembler dispatch intact and the suites green; baselines snapshot before each step so any regression is caught.

## 3. Target architecture (the layers)

```
data/report.json ─┐
brand tokens ─────┤→ (L1) token layer ──→ :root CSS vars + <html data-*> axes
§4.0 axes ────────┘                               │
assets (local now / Drive later) ─────────────────┤
                                                   ▼
                          (L3) atomic components ── compose ──> (L2) Jinja2 page templates
                                                   │
                                                   ▼
                          (L5) assembler → ONE HTML doc (shared head from tokens) → WeasyPrint → PDF/PNGs
                                                   │
                                                   ▼
                          (L6) visual-regression: rasterize → pixel-diff vs committed baselines
```

Files (target):
```
research/v7-renderer/
  tokens/
    base.tokens.json        # NEW — universal design constants (type scale, spacing, semantic roles), DTCG-style, cited to grammar §
    compile_tokens.py       # NEW — Python compiler: base + per-client brand/axes → CSS :root vars + data-* map
  templates/                # NEW — Jinja2: base.html.jinja (doc shell + shared head), one <st>.html.jinja per pattern
  components/               # NEW — atomic component macros (.jinja) + their scoped CSS
  styles/                   # NEW — static stylesheets (component + layout CSS using semantic vars only)
  render_context.py         # NEW/!=: brand + axes + asset resolver + grammar handed to templates
  assembler.py              # MODIFIED — render via Jinja2 + token layer; keep PageFragment + dispatch + validators
  package_loader.py         # MODIFIED — read brand_axes from package
  patterns/                 # becomes thin: each pattern = data-prep → renders its Jinja template (no inline HTML/CSS strings)
  tests/test_visual_regression.py   # NEW — pixel-diff harness + baselines/
research/preprocessor/
  stages/assemble_package.py + plan/onboard contracts  # MODIFIED (additive) — emit brand_axes into the package
```

## 4. L1 — Design-token layer (Python-native, no Node)

**Why Python-native:** the project is Python; brand values already arrive from the pre-processor as a dict. Adding Node/Style Dictionary is unjustified weight. We adopt the **DTCG authoring format** (`$value`/`$type`) for the base file, compiled by a small Python function — same discipline, no extra toolchain.

- **`tokens/base.tokens.json`** — the UNIVERSAL design constants only (no client values): three tiers —
  - *primitives placeholders* (filled per-client): `color.brand.primary`, `color.brand.accent`, `font.family.heading`, …
  - *semantic aliases* (the vocabulary components use): `color.surface`, `color.on-surface`, `color.accent`, `color.ink`, `font.display`, `font.body`, `space.{1..8}`, `type.scale.{eyebrow,body,h3,h2,display}`, `radius.cta`. Each carries a comment citing the grammar/spec § that grounds it (e.g. type sizes ← InDesign Spec L183; accent rules ← §3.6/§3.7).
  - *component tokens* (optional): `stat.value.size`, `pill.border`, …
- **`compile_tokens.py`** — `compile_tokens(brand: BrandConfig, axes: BrandAxes) -> (css_root: str, data_attrs: dict)`:
  - binds per-client primitives from `brand` (colors, fonts) into the semantic aliases,
  - resolves axis-dependent semantics (e.g. `font.display` = serif-family when `headline_type=serif`, else sans),
  - emits the `:root { --color-…; --font-…; --space-… }` block + a `data_attrs` map (`{"data-headline-type":"serif", "data-ground-mode":"…", "data-texture":"…"}`).
- **Components reference SEMANTIC vars only** (`var(--color-accent)`, `var(--font-display)`) — never primitives, never client hexes. Per-client = swap primitives; structure untouched.

## 5. L4 — Axis-driven theming (the brand-agnostic enabler)

The §4.0 axes (`headline_type` serif|sans|sans_allcaps, `ground_mode`, `texture`, `accent_mechanic`) currently live on the pre-processor `BrandProfile` but are **dropped before the renderer** (R1 left BrandConfig at 10 fields). Thread them through:

1. **Pre-processor (additive) — precise data-flow.** The axes already exist on `client.brand_profile` (`headline_type`, `ground_mode`, `texture`, `accent_mechanic`). Thread them to the package: `main.py /render` passes a `brand_axes` dict (built from `brand_profile`, falling back to grammar defaults for absent axes) into `assemble_package(...)`; `assemble_package` gains a `brand_axes` param and emits a top-level `brand_axes` block in `resolved_package.json`. **The apex fixture generator (`fixtures/apex/build_package.py`) does the same** — it already loads `brand_input.json.brand_profile`, so it builds `brand_axes` from it and passes it through. 217+ pre-processor tests stay green + one new assertion (manifest carries `brand_axes`).
2. **Renderer:** `package_loader` reads `brand_axes` → a frozen `BrandAxes` dataclass on the render context (defaults applied if the block is absent, so older packages still load).
3. **Theming mechanism:** the assembler sets `<html {data_attrs}>` (from `compile_tokens`). The token layer + component CSS respond via attribute selectors — e.g. `[data-headline-type="serif"]{--font-display:var(--font-serif)}`, `[data-ground-mode="dark"]{--color-surface:var(--color-ink)}`. **Logic never branches on client identity** — only on axis values.
4. **Serif support:** bundle a chassis-default **serif display font** (file in `fonts/`); `--font-serif` points to it. `--font-display` resolves to the client's `font_heading` when its file is available, else the axis-default family (serif→bundled serif, sans→Montserrat). This is how we get the reference's serif headings *without* hardcoding serif. (Token roles: `--font-display` serif/sans by axis, `--font-head` sans for labels/eyebrows, `--font-body` sans.)
5. **`ground_mode` / `texture` → page-background treatment (fixes the "texture stuck on a separate page" complaint).** These axes drive a **subtle full-page wash/texture behind CONTENT pages** (via the `report_assets` texture/gradient + a tint), not just isolated breather pages. So the atmospheric material reads as the report's consistent ground, with **ST-31/32 breathing pages remaining deliberate, fuller-bleed atmospheric pacing pages** (a real grammar pattern, §Atemseite) — distinct in *degree*, not orphaned. Applied via tokens/`data-ground-mode`, brand-agnostic.

## 6. L2 — Templating (Jinja2) + L3 — components

- **Jinja2** replaces every f-string. `templates/base.html.jinja` = the document shell + shared `<head>` (token `:root`, `@page` chrome — header band, folio, gradient wash —, `@font-face`). One `templates/<st>.html.jinja` per pattern.
- **`PageFragment` contract preserved:** a pattern's `render(page, ctx)` now does *data prep only*, then renders its Jinja template to the fragment HTML; pattern CSS lives in `styles/` (class-based, semantic vars), collected/deduped by the assembler exactly as today. The assembler dispatch registry is unchanged.
- **Atomic component library (`components/`)** — Jinja macros, grammar-grounded, brand-agnostic: `pill`, `eyebrow`, `stat_value`, `stat_strip`, `numbered_marker`, `numbered_block`, `callout_panel` (tint), `dark_cta_panel`, `qr`, `media_figure` (photo w/ caption), `bar_chart`, `step_card`, `horizontal_flow`, `logo_wall`, `page_header_band`, `footer_wash`. Patterns compose these — no bespoke HTML strings. This is the "richness toolkit" mapped to the §3.7 accent-location devices + the reference's recurring motifs, colored entirely by tokens.

## 7. L5 — Assembler / engine (WeasyPrint, mostly unchanged)

`render_package` keeps: load package → per-page dispatch → `PageFragment` → one doc → WeasyPrint → PNGs → validators (overflow, accent-budget). Changes: the shared head comes from `compile_tokens` + `base.html.jinja` (not a hand-built string); `<html>` carries the axis `data-*`. The proven background-on-block rule and per-page folio (`string-set`) carry over.

## 8. L6 — Visual-regression testing

`tests/test_visual_regression.py`: render the apex fixture → rasterize each page (PyMuPDF, fixed DPI) → pixel-diff against committed baselines in `tests/baselines/` (Pillow/`pixelmatch`-py, small tolerance). Baselines are intentional artifacts: regenerated only when a design change is reviewed + accepted. This makes "did the look change" a test result, not a vibe-check, and proves theming changes are scoped (per-brand fixtures). (No git here — baselines are on-disk files; updating them is a deliberate step.)

## 9. Pollution-prevention (extended guards)

- Keep `test_no_coral_in_chassis_logic` + `test_no_client_name_in_preprocessor_logic`.
- **Add:** a guard that bans raw hex colors and font-family string literals in `components/`, `templates/`, `styles/`, and pattern `.py` (allowed ONLY in `tokens/base.tokens.json` primitives and the per-client data). And a ban on `if <client> ==` / brand-name branching.
- Net effect: a literal color/font/label outside the token+data layer fails the suite — the structural lock against the failure that has bitten us.

## 10. Asset layer (local now → Drive in production)

- **Now (test run):** patterns resolve images via the package `assets[]` + `image_map.json` (declarative filename→slot map) — already in place; the photos you dropped (`founder.png`, the 4 client shots) get wired into cover/about/case-study/collaboration slots. `media_figure` component handles framing; missing → graceful.
- **Production (separate build, after OAuth creds):** a `drive_assets` module — user-OAuth2 + refresh token, `files.list` per-client folder, `files.get_media` download, the same declarative naming→schema map, md5 cache, fail-loud on missing required slots. Designed now, built when creds arrive. **Not in this migration's code scope.**

## 11. Migration path (incremental, suites green at each step)

1. **Tokenize in place:** replace literal colors/fonts/spaces across current patterns + assembler with semantic CSS vars from a hand-written `:root`; **snapshot visual-regression baselines** (safety net). Output ~unchanged.
2. **Add the token compiler:** `base.tokens.json` + `compile_tokens.py`; generate the `:root` (replacing the hand-written one). Per-client values from the package.
3. **Thread axes:** pre-processor emits `brand_axes`; renderer reads it; assembler sets `data-*`; wire serif via the axis. (Now headings can be serif for apex, sans for others — no hardcoding.)
4. **Introduce Jinja2 on ONE pattern** (keep `PageFragment`): convert it, verify ≈zero pixel-diff, then convert the rest pattern-by-pattern.
5. **Build the atomic component library**; refactor patterns to compose macros; lift CSS into `styles/`.
6. **Rebuild patterns to reference quality** on the new foundation, **per `2026-05-30-reference-design-system.md`** (the per-ST layouts + the 22-item richness checklist = the acceptance bar). This step explicitly **fixes the dropped-asset/component bug**: every pattern MUST consume what the package carries — `page["assets"]` (e.g. the ST-09 scene that was being dropped, the cover hero, case-study portraits) via `media_figure`, AND `page["components"]` (the Stage-6 SVGs) inline — with the renderer's own token-driven `bar_chart`/`stat_strip` components used where the package has no SVG. Grammar-driven, token-colored, axis-themed. Re-baseline visuals intentionally; review page-by-page against the reference + tick off all 22 richness items.

Steps 1–5 are the re-foundation; step 6 is where the output becomes beautiful — but now on solid ground. (The assembler's never-crash isolation + `_generic` fallback + per-page overflow/accent-budget validators are preserved throughout; component + pattern unit tests accompany each, on top of the visual-regression suite.)

## 12. Scope boundaries

**In:** token layer, Jinja2, component library, axis threading (incl. the additive pre-processor `brand_axes`), serif font, visual-regression harness, guard extensions, pattern rebuild to reference quality (WeasyPrint).
**Out (separate cycles):** Google Drive retrieval build (designed §10, built post-OAuth); Prince/DocRaptor engine swap (held in reserve); Layer-3 CMYK (already owned by the post-processor); spreads.

## 13. Success criteria

- Output reads as a faithful, on-brand match to the reference's design language (rich layouts, integrated photos/charts, color-blocks/callouts/pills, serif display headings via the axis) — verified page-by-page against the reference as the bar.
- Provably brand-agnostic: no client hex/font/name/label outside `tokens` + data; extended guards green; flipping the brand+axes re-themes everything with zero logic change (demonstrated with a second synthetic brand fixture).
- Deterministic: visual-regression baselines stable run-to-run.
- Both suites green (renderer + pre-processor) at every migration step.

## 14. Self-review notes

- **Placeholders:** none — each layer has a concrete library + file + responsibility.
- **Consistency:** `PageFragment` + assembler dispatch preserved throughout; axes flow pre-processor→package→loader→context→`data-*`→CSS uniformly; tokens are the single theming surface.
- **Scope:** one subsystem (the renderer foundation) + one additive upstream contract (`brand_axes`); Drive + Prince explicitly deferred.
- **Brand-agnosticism:** grammar = rules, tokens = universal constants, data = per-client; guard tests lock it. This is the direct fix for the pollution that caused the prior cleanup.
