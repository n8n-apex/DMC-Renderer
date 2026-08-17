# Renderer R2 — Pattern Library (match-reference) — Design / PRD

**Status:** In design — pending user review
**Date:** 2026-05-29
**Component:** `research/v7-renderer/` (Layer 2 chassis) — renderer only. No pre-processor or post-processor changes.
**Predecessors:** `2026-05-29-renderer-r1-foundation-design.md` (R1, built), `2026-05-29-renderer-scope-analysis.md`.
**Visual target:** `APEX - KI DMC Report v1 (1).pdf` (repo root) — the finished apex report.

---

## 1. Goal

Build the full grammar pattern library — **12 ST-type patterns** — so the renderer composes a report whose **layout language matches the finished reference PDF**, replacing R1's `_generic` skeleton for every ST type. Each pattern is **brand-agnostic and deterministic**: it reads `ctx.brand` + `page["data"]` + `page["assets"]` and renders with `var(--brand-*)` only — the same patterns render any client from that client's package, with no client name or hex in logic (guard-enforced). Apex is the **verification fixture**, never hardcoded.

**Confirmed scope decisions (user, 2026-05-29):**
1. **Match the reference closely** — enrich each pattern's *data contract* (optional structured keys) + the apex *fixture data* so the rich layouts are exercised. (No pre-processor model change — `ReportPage.data` is already free-form; richness travels in data.)
2. **ST-22** renders as a **bespoke horizontal connector flow** (ST-06 stays vertical step cards).
3. **Breathing pages (ST-31/32)** use a report **background asset when present**, else a brand-tonal CSS ground.
4. **Full library** — all 12 patterns, incl. ST-08 (FAQ) and ST-32 even though apex doesn't use them (verified via unit tests with synthetic data).
5. **No "sparse content" pre-processor warning** — the content pipeline always completes before render (Airtable kick-off), so rich fields are guaranteed present at render time.

**Non-goals (unchanged R1 boundaries):** real accent-budget rasterization (stays stub); one A4 page per package page (reference pages are single — no spreads); Layer-3 CMYK/bleed.

---

## 2. Principles (carried from R1, non-negotiable)

- **Pattern interface unchanged:** every pattern module exposes `def render(page: dict, ctx: RenderContext) -> PageFragment` (`patterns/base.py`). Returns body HTML + pattern-scoped CSS. NO `@page`/`@font-face`/`:root` in a fragment (those are the assembler's shared head).
- **Brand-agnostic + deterministic:** colors via `var(--brand-*)`; fonts are the chassis bundle; zero AI calls; identical input → identical PDF. Guard tests `test_no_coral_in_chassis_logic` (renderer) must stay green.
- **Graceful degradation:** every enriched `data` key is OPTIONAL. A pattern renders what's present and omits cleanly what's absent — a thin page is simpler, never broken.
- **DRY via shared components** (new `patterns/_components.py`): reusable HTML builders + CSS snippets shared across patterns.
- **CSS dedup intact:** the assembler dedupes identical fragment CSS blocks; patterns keep per-page dynamic values (image URLs, etc.) INLINE on elements, not in the CSS string.

---

## 3. Architecture

Three layers of work, all inside `research/v7-renderer/`:

1. **Data contract (§5):** a documented, brand-agnostic set of optional structured `data` keys per ST type — the interface every client's content targets. This is prose/schema, not code (the `data` dict is free-form).
2. **Shared components (§4):** `patterns/_components.py` — `qr_svg`, `numbered_step_card`, `numbered_block`, `stat_strip`, `dark_cta_panel`, `horizontal_flow`, `bar_mini`. Each is a pure function returning an HTML string, paired with a module-level CSS constant patterns include.
3. **The 12 patterns (§6):** one module per ST type implementing `render(page, ctx)`, composing components + brand vars, registered in `patterns/__init__.py`'s `REGISTRY`.

Plus **apex fixture enrichment (§7)** and a **visual-fidelity verification loop (§8)**.

`st_07a` (the existing real pattern) is left working as-is; it MAY adopt the shared `qr_svg`/`stat_strip` for DRY, but only if the change is trivial and keeps its tests green — never a rewrite.

---

## 4. Shared components (`patterns/_components.py`)

Each component = `def build_X(...) -> str` (HTML) + a `X_CSS: str` constant. A pattern returns `PageFragment(html=..., css=PATTERN_CSS + X_CSS + Y_CSS)`. Component CSS is **static, class-based** (so it dedupes; no per-instance values in CSS — dynamic values are inline on elements).

| Component | Builds | Used by |
|---|---|---|
| `qr_svg(url, fg, bg)` | inline SVG QR (extracted verbatim from `st_07a._qr_svg`) | ST-03, ST-FAZIT, (st_07a) |
| `numbered_step_card(n, title, body_html)` | vertical card: accent number tab + title + body | ST-06 |
| `numbered_block(n, title, body_html, *, reality_html=None)` | numbered row: big accent index + title + body; optional second "reality" sub-block | ST-09, ST-14 |
| `stat_strip(stats)` | N-up strip of `{value (accent, large), label (caps)}` | ST-05, ST-01 proof |
| `dark_cta_panel(headline, url, *, qr_svg=None, body_html=None)` | saturated brand-ground panel: white headline + oversized accent URL + optional QR | ST-03, ST-FAZIT |
| `horizontal_flow(steps)` | horizontal row of step nodes connected by accent arrows; each node = number + title + body (+ optional duration) | ST-22 |
| `bar_mini(stats)` | small inline CSS bar-chart (proportional accent bars + labels) | ST-01 |

All components honor anti-patterns §6.1 (no rounded corners except CTA box / step cards per `chassis_config`; no drop shadows). Accent (`var(--brand-accent)`) fires only at §3.7 locations (numbers, kickers, URLs, stat values, glyphs, attributions).

---

## 5. Per-ST data contract (brand-agnostic interface)

All keys OPTIONAL; patterns degrade gracefully. `*_html` are produced by `preprocess_body`. (Existing R1 keys marked ✓; enriched keys are new.)

- **ST-01 Cover:** `title`✓, `subtitle`✓, `eyebrow`/`kicker_pills[str]`, `intro`✓, `inclusions[str]` ("INKLUSIVE IM REPORT"), `proof_stats[{value,label}]`, `teaser_items[str]` (= R1 `teaser_bullets`✓), `author{name, role}`. Assets: `cover_hero` (background), `cover_author` (portrait, optional).
- **ST-02 Outlook:** `title`✓, `body`✓, `zielgruppe[str]` (check-list), `author{name,role}` + soft CTA `cta_text`/`cta_url`.
- **ST-03 Hard CTA:** `title`✓, `body`✓, `cta_text`✓, `cta_url`✓. QR from `ctx.brand.qr_target_url`.
- **ST-05 About:** `title`✓, `body`✓, `stats[{value,label}]` ("IN ZAHLEN"), `partners[str]` ("BEKANNT AUS" / logo names), `credibility_points[str]`✓. Asset: team photo (optional).
- **ST-06 Mechanism:** `title`✓, `body`✓, `steps[{n,title,body}]`✓(strings→split), `ergebnis` (result recap).
- **ST-07B Theory:** `title`✓, `body`✓, `key_insight`✓, optional `compare{ohne[str], mit[str]}` (before/after variant).
- **ST-08 FAQ:** `title`, `faqs[{frage, antwort}]`. (Not used by apex; verified via synthetic fixture.)
- **ST-09 Status quo:** `title`✓, `body`✓, `symptoms[{title,body}]` (R1 had flat strings → enrich to objects).
- **ST-14 False beliefs:** `title`✓, `body`✓, `beliefs[{irrglaube, realitaet, quelle?}]` (R1 had flat strings → enrich to objects).
- **ST-22 Collaboration:** `title`✓, `body`✓, `steps[{n,title,body,dauer?}]` → horizontal flow.
- **ST-31 / ST-32 Atemseite:** no text; optional `phrase` (single calm line). Background: first report asset of type texture/gradient if present, else CSS ground.
- **ST-FAZIT Summary:** `title`✓, `body`✓, `these`✓, `kosten_des_nichtstuns`✓, `cta_text`/`cta_url`. Asset: photo (optional).

> Where R1 used flat string lists (`symptoms[str]`, `beliefs[str]`, `steps[str]`), patterns accept BOTH a string item (render as body) and an object item (render structured) — so the enrichment is backward-compatible and graceful.

---

## 6. Per-pattern layout intent (from grammar + reference PDF)

Each is a single A4 page. "Accent" = `var(--brand-accent)`; "primary" = `var(--brand-primary)`; body `#333` Blocksatz. Reference page numbers (`ref pN`) are the visual target; exact pixels are achieved in the §8 visual loop, not pre-specified.

- **ST-01 Cover** (P-1; ref p1) — full-bleed `cover_hero` background (dark) behind everything; top row: wordmark left + `kicker_pills` (small accent-outlined pills); right column "INKLUSIVE IM REPORT": `inclusions` bullets + `bar_mini(proof_stats)`; numbered `teaser_items` ("DU LERNST"); large two-weight display `title` lower-left; `subtitle` bar; `author.name`/role bottom-left over the photo. Complexity High.
- **ST-02 Outlook** (P-2; ref p2) — big display headline; two-column justified `body`; `zielgruppe` check-list (accent ticks); optional small founder photo + soft CTA. Complexity Low.
- **ST-03 Hard CTA** (P-12; ref p20) — `dark_cta_panel`: saturated brand ground, short white `title`, oversized accent `cta_url` (largest type on page, §3.6), `qr_svg(brand.qr_target_url)` + wordmark bottom; ghost "company" motif (P-15). Complexity Medium.
- **ST-05 About** (P-3; ref p3) — framed team photo (if asset) with headline; left `body` + `partners` row ("BEKANNT AUS"); right dark panel `stat_strip(stats)` ("IN ZAHLEN", 3 big accent numbers); `credibility_points`. Complexity Medium-High.
- **ST-06 Mechanism** (P-8; ref p17) — stacked `numbered_step_card` per `steps[]` (accent number tab + title + body); optional `ergebnis` recap panel; large ghost side element. Step cards MAY use rounded corners via `chassis_config.allow_rounded_corners('mechanism-step-card')`. Complexity Medium.
- **ST-07B Theory** (P-7; ref p11/p13) — headline + `body` prose + `key_insight` callout (accent rule + larger italic). If `compare{ohne,mit}` present: a two-card before/after block. Complexity Low-Medium.
- **ST-08 FAQ** (P-2/4) — title + `faqs[]` as a Q&A stack: question in accent/primary bold, answer body below; two-column flow if long. Complexity Medium. (Synthetic-data verified.)
- **ST-09 Status quo** (P-4; ref p4) — intro question headline + `body`; `symptoms[]` via `numbered_block` (big accent index + bold title + body); optional accent callout. Complexity Low-Medium.
- **ST-14 False beliefs** (P-5; ref p5) — "Die N größten …" headline; `beliefs[]` via `numbered_block` with the `reality_html` sub-block (IRRGLAUBE quoted + REALITÄT rebuttal + `quelle`). Complexity Low-Medium.
- **ST-22 Collaboration** (P-10/13; ref p9) — `horizontal_flow(steps)`: a left-to-right row of numbered step nodes joined by accent arrows, each with title + body + optional `dauer`; intro headline + `body` above. Complexity Medium-High (bespoke, per user).
- **ST-31 / ST-32 Atemseite** (ref p19) — full-page calm ground: first report `texture`/`gradient` asset as `background` if present, else a brand-tonal CSS wash (`--brand-neutral-light` → faint `--brand-primary` radial); ≥20% whitespace (§3.4); optional centered `phrase`. Complexity Low.
- **ST-FAZIT Summary** (P-9; ref p14) — dark header band ("Zusammenfassung") + optional photo; `body` argument; `these` as a large pull-statement; `kosten_des_nichtstuns` block; `dark_cta_panel`/accent CTA box with `cta_url`. Complexity Medium.

---

## 7. Anti-patterns + accent discipline (applies to every pattern)

- §6.1 #1 no rounded corners (exceptions: CTA box, mechanism/process step cards — gate via `chassis_config`); #2 no drop shadows (no exceptions). Patterns call `chassis_config.allow_rounded_corners(<element-class>)` where relevant rather than hardcoding radius.
- §3.7 accent fires ONLY at: kickers/stamps, panel fills, oversized quote glyphs, URLs in CTA contexts, inline data emphasis / stat numbers, line-icons/checks, attribution labels. Patterns must not paint large body areas in accent.
- §3.4 breathing/whitespace respected on light pages.

---

## 8. Verification — the "100% sure before showing output" mechanism

Per pattern (TDD, renderer venv — `source .venv/bin/activate` for WeasyPrint):
1. **Unit tests** (`tests/test_render_r2.py`): `render(page, ctx)` returns a `PageFragment`; with full data → the layout's key elements/classes present + content present; with empty `{}` / missing keys → still a valid fragment (graceful); fragment css has no `@page`/`@font-face`/`:root`; brand colors only via `var(--brand-*)` (no client hex).
2. **Integration:** `render_package(fixtures/apex)` → 20 pages, never crashes, overflow advisory only.
3. **Visual-fidelity loop (the gate before showing the user):** after each batch, run `render.py` → rasterize the batch's pages → compare each against its reference-PDF page (a reviewer subagent reads both images and reports layout-language match: are the expected structural elements present and arranged as in the reference?). Iterate the pattern until it matches. Slot-15-style overflow is tuned here (tighten type scale / spacing) so no case-study page overflows.
4. **Guards:** `test_no_coral_in_chassis_logic` + the pre-processor `test_no_client_name_in_preprocessor_logic` stay green.

R2 is "done" only when all 4 batches pass the visual loop and the full apex `report.pdf` reads as a faithful, on-brand match to the reference.

---

## 9. Build order — 4 batches

Each batch: (a) enrich that batch's apex fixture data; (b) build its components + patterns; (c) register in `REGISTRY`; (d) unit tests; (e) render + visual-verify its pages vs. the reference.

1. **Numbered family:** `_components` (numbered_step_card, numbered_block) + ST-09, ST-14, ST-06. (Biggest reuse.)
2. **Editorial + FAQ:** ST-02, ST-07B, ST-08.
3. **Dark-ground/CTA + breathing:** `_components` (qr_svg, dark_cta_panel) + ST-03, ST-FAZIT, ST-31, ST-32.
4. **Heavy bespoke:** `_components` (stat_strip, bar_mini, horizontal_flow) + ST-01, ST-05, ST-22.

---

## 10. Apex fixture enrichment

`fixtures/apex/report_content.json` is enriched per batch with the §5 structured fields, transcribed from `content for apex.md` + the reference PDF (DATA only — no pattern logic ever names apex). The generator (`fixtures/apex/build_package.py`), Stage-8 reuse, and `image_map.json` are unchanged except that newly-referenced assets (if any) are added to `image_map.json`. Re-run the generator after each enrichment so the package reflects the new data.

---

## 11. Module layout

```
research/v7-renderer/
  patterns/
    _components.py          # NEW — shared HTML builders + CSS constants
    __init__.py             # MODIFY — register all 12 in REGISTRY
    st_01.py … st_fazit.py  # IMPLEMENT each render(page, ctx) (replace stubs)
    st_08.py, st_32.py      # NEW files (no stub today)
    base.py, st_07a.py      # unchanged (st_07a may optionally import _components.qr_svg)
  tests/test_render_r2.py   # NEW — per-pattern unit tests
  fixtures/apex/
    report_content.json     # enrich with structured fields
    image_map.json          # add any newly-referenced assets
```

---

## 12. Success criteria

`render_package(fixtures/apex)` emits a 20-page RGB PDF whose every page reads as a faithful, on-brand match to the reference PDF's layout language; all 12 patterns implemented + registered; the apex images placed where layouts call for imagery (missing apex portraits degrade gracefully); renderer suite (R1 26 + R2 unit tests) + `no-coral` guard green; pre-processor 220 + guard green; no page overflows; chassis stays brand-agnostic + deterministic (same patterns render any client from its own package).

---

## 13. Self-review notes

- **Placeholders:** none — every pattern has a concrete layout intent + data contract; pixel fidelity is achieved in the §8 visual loop (by design, not deferral).
- **Consistency:** the pattern interface, `var(--brand-*)` discipline, CSS-dedup rule, and graceful-degradation rule are uniform across all 12 and match R1's built contract.
- **Scope:** one focused subsystem (the renderer pattern library); appropriately one spec, sequenced as 4 batches in the plan.
- **Brand-agnosticism:** richness lives in data + the contract; logic names no client; guard tests enforce. Apex is the verification fixture only.

