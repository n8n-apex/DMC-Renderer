> **STALE: DO NOT ORIENT FROM THIS FILE.** It describes an earlier frame and is wrong on load-bearing facts. Authoritative current sources: `context.md`, `docs/superpowers/CURRENT-STATE.md`, `richard-grammar-v2.md`. Corrections that bite: the engine is **Chromium print-to-PDF plus Ghostscript flatten**, NOT WeasyPrint (legacy `--engine weasyprint` fallback only); bundled fonts are **Source Serif 4 and Source Sans 3** variable faces, NOT Montserrat; the renderer consumes a **multi-page `resolved_package.json` via `--package-dir`**, NOT a single-page GEVA fixture. (Banner added 2026-06-21.)

# Chassis notes — `research/v7-renderer/`

**Orientation doc.** Read this first if you are new to the chassis or returning after a context break. It describes the chassis as it is *today* — post-decontamination (Moves 0-2c, May 23 2026; pytest migration + this doc rewrite, Move 3+4, May 23 2026).

For the historical build log (the original Phase 4 GEVA build, pre-decontamination), see `BUILD-NOTES.md`. Its body documents architectural choices that have since been removed; the header warns explicitly.

---

## What the chassis IS

**Layer 2 (compositor) of a three-layer renderer architecture.**

```
  Layer 1 — PRE-PROCESSOR              Layer 2 — RENDERER             Layer 3 — POST-PROCESSOR
  (Python + Typst + AI gen)            (this chassis, WeasyPrint)     (Ghostscript + pikepdf + veraPDF)
  ────────────────────────────         ─────────────────────────      ──────────────────────────────────
  Ingest content payload               Take a pre-resolved package    Take WeasyPrint's RGB PDF
  Validate copy rules                  Apply CSS page templates       RGB → CMYK (ISO Coated v2 300%)
  Resolve fonts (customer-first)       (per the grammar's Layer-A     Preserve K=100 black text
  Plan layout                          structural patterns)           Stamp PDF/X-4 output intent
  Pre-render Typst SVG components      Composite Typst SVGs + AI      Write TrimBox/BleedBox (3mm bleed)
  Generate AI image assets             PNGs into the layout           Fix WeasyPrint transparency bug
  (Nano Banana Pro / Flux 2)           Output RGB PDF                 veraPDF compliance check
```

**Chassis scope (Layer 2 only):**
- Reads a flat brand profile (BrandConfig) + the ratified grammar
- Applies CSS templates encoding Richard's Layer-A patterns (§2 of the grammar)
- Composites pre-rendered assets into pages
- Emits an RGB PDF via WeasyPrint
- Rasterizes a PNG for visual inspection
- Routes the rendered output through the `AccentBudgetValidator` (currently a stub)

**Chassis does NOT:**
- Generate textures, atmospheric gradients, or 3D-style icons (Layer 1 — AI image generation)
- Compute precision diagram geometry (Layer 1 — Typst component factory)
- Validate copy rules — buzzword denylist, voice-marker minimums, "Nicht X, sondern Y" cap (Layer 1)
- Convert RGB to CMYK or stamp print-shop metadata (Layer 3)

If a future change request asks the chassis to do any of the above, the answer is "that's a different layer."

---

## Source of truth

**`richard-grammar-v2.md`** at the project root (`/Users/utkarsh/Projects/richard/richard-grammar-v2.md`).

883 lines, ratified (`RATIFIED-BY: Utkarsh 2026-05-23`). Layer-A structural patterns (§2 P-1 through P-15) + Layer-B per-client brand profiles (§4.1, five clients catalogued). Anti-patterns (§6). Print export specs (§7). Provenance discipline (§9).

Loaded by `grammar_loader.py` at chassis startup. Trust gate: `load_grammar()` refuses to read a grammar whose `RATIFIED-BY` header line is blank — raises `GrammarUnratifiedError` at load time, before any pattern runs. This is the structural fix for the prior frame's "render against unaudited grammar" failure mode.

A prior grammar file exists at `research/idml-spike/skills/richard-design-system/` (full filename in the decontamination-history section below). It is **superseded**. Its first line carries a `# DEAD —` marker. The loader no longer reads it. Do not cite it as a source of truth.

Where two LIVE Richard docs disagree:
- `08_DMC_Design_System_v2.md` governs over `DMC_InDesign_Spec_v1.md` (v2 is philosophy; the spec implements it)
- All other LIVE doc pairs are subject-matter-disjoint

---

## Brand model — flat BrandConfig

`brand_tokens.py` defines `BrandConfig` with **10 flat fields, no nested objects**:

| Field | Purpose |
|---|---|
| `brand_primary` | hex; the client's primary dark colour |
| `brand_accent` | hex; the client's accent — **hue-agnostic**. The chassis treats whatever hex the client supplies the same way. Per-client examples are catalogued in grammar §4.1; the chassis never names a specific accent value in code. |
| `brand_neutral_dark` / `_mid` / `_light` | hex; client neutrals |
| `font_heading` | literal font-family name (e.g. `"Montserrat"`) |
| `font_body` | literal font-family name (e.g. `"Source Sans 3"`) |
| `qr_target_url` | URL the QR code encodes |
| `company_name_short` | wordmark / running header text |
| `company_url_display` | display URL shown in pullquote panel |

`parse_brand_tokens(dict) -> BrandConfig` reads a flat dict and returns the config. Missing any required key raises plain `ValueError` naming the missing field. **No nested preferences object. No client-default fallback profile. No synthesis.** Input-driven: the dict's keys are what the chassis sees; the chassis does not invent values. (For what the prior shape carried, see the decontamination-history section at the bottom of this file.)

A future client (Layer 1 pre-processor's output) supplies these 10 keys. The chassis is brand-agnostic; logic refers to fields by name (`brand.brand_accent`), never to the hex.

---

## Validator — `AccentBudgetValidator`

`validators/accent_budget.py`. Single-path validator. Checks two rules, AND'd:

- **AREA (§3.6):** accent pixels ≤ 10% of page surface, per page. Citation: `08_DMC_Design_System_v2.md` C.2 L162.
- **LOCATION (§3.7):** accent fires only at allowed element classes (kickers / FALLSTUDIE stamp, panel fills, oversized quote glyphs, URLs in CTA contexts, inline data emphasis, line-icons / checks, attribution labels in pullquotes).

Hue-agnostic — the validator reads `brand.brand_accent` from the profile and matches pixel clusters against that hex (±ΔE 10). It never references a literal colour name.

**Current state:** stub. `validate()` returns `AccentBudgetResult(passed=True, error_code=None, details="accent-budget validation stub")`. Real rasterization-based implementation is post-decontamination work.

**Error code emitted on failure:** `accent_budget_exceeded`. String-match coupling to the n8n workflow that branches on this code (no Python import dependency). The n8n side was updated alongside the chassis rename.

---

## Anti-pattern toggles — `chassis_config.py`

Two functions, per-element-class signature:

- `allow_rounded_corners(element_class: str) -> bool`
- `allow_drop_shadows(element_class: str) -> bool`

Rules (grammar §6.1):
- **Rounded corners default: forbidden.** Exceptions:
  1. CTA boxes (`cta-box` class) may have 2-3mm border-radius optionally. Citation: `DMC_InDesign_Spec_v1.md` L548-552.
  2. Mechanism / process step cards (`mechanism-step-card`, `process-step-card` classes) — VARIATION (per-brand). Evidence in two reference clients.
- **Drop shadows: forbidden everywhere, no exceptions.**

Patterns must call these functions to ask. They must not hardcode the answer. The functions know the grammar; the patterns don't.

A previous shape gated these decisions on a global mode flag and a per-brand override dict — both deleted in M2c (see decontamination-history section at the bottom). The rule lives in the grammar, not in a global flag or a per-brand override.

---

## Fonts

Variable fonts under `research/v7-renderer/fonts/`:

| File | Role |
|---|---|
| `Montserrat[wght].ttf` | headlines (weight axis 100-900) |
| `Montserrat-Italic[wght].ttf` | italic headlines if needed |
| `SourceSans3[wght].ttf` | body (weight axis 200-900) |
| `SourceSans3-Italic[wght].ttf` | italic body (lede, attribution) |

Source: Google Fonts. CSS uses `font-weight: <N>` against the variable axis; one `@font-face` declaration per style covers the full weight range. URL-encoded brackets (`%5B`, `%5D`) in CSS `src:` because the upstream filenames carry literal brackets.

These are the **Priorität 2 system fonts** per `DMC_InDesign_Spec_v1.md` L484-489 ("Headlines: Montserrat (ExtraBold, Bold, SemiBold) / Fließtext: Source Sans Pro (Regular, SemiBold, Bold, Italic)"). Source Sans 3 IS Source Sans Pro (Adobe renamed the family in 2021; same typeface lineage).

**Priorität 1 (customer-supplied font via CD asset upload):** not yet implemented. That's pre-processor work — Layer 1 resolves customer fonts and passes the resolved filenames into BrandConfig's `font_heading` / `font_body` fields.

---

## Body colour, margins, layout primitives

| Rule | Value | Citation |
|---|---|---|
| Body text colour | `#333333` (Dunkelgrau) | InDesign Spec L243 [HARD] |
| Body alignment | Blocksatz + hyphenation (Pyphen) | InDesign Spec L244-246 [HARD] |
| Body geometry | 2-column ~84mm + 6mm gutter | InDesign Spec L53-65 [HARD] |
| First-line indent | 4mm on paragraphs after the first | InDesign Spec L273 [HARD] |
| Page margins | T16 / O14 / B20 / I18 (derived-default) | 08_v2 L15-16 governs ("Maße ergeben sich aus Zeichenlimits"); the mm values are the OUTPUT of the derive-from-character-limits process for the 2-col 84mm body — **not** canonical inputs. Real derivation from body geometry is post-decontamination structural work. |
| Bleed | 3mm all sides | InDesign Spec L26-29 [HARD] |
| Headline size | 28-40pt (default 32pt) | InDesign Spec L183 [SOFT] |
| Pullquote size | 17-20pt | InDesign Spec L285 [SOFT] |
| ≤3 design colours per report | enforced (validator pending) | 08_v2 C.2 L156 [HARD] |
| ≤20% whitespace per page | enforced (validator pending) | 08_v2 D.1 L180 [HARD] |
| Anti-pattern #1 (no rounded corners) | except CTA box / step card | InDesign Spec L548-552, grammar §6.1 [HARD with named exceptions] |

The pattern (`patterns/st_07a.py`) hardcodes these values in CSS with citation comments next to each rule. A pattern that does not cite the grammar for a numeric value is incorrect.

---

## Module map

| File | Purpose |
|---|---|
| `render.py` | Entrypoint. Reads the fixture, resolves brand tokens, loads grammar (trust gate), dispatches to a pattern, renders via WeasyPrint, routes through AccentBudgetValidator, rasterizes a PNG. |
| `grammar_loader.py` | **KEYSTONE.** Loads `richard-grammar-v2.md`. Trust-boundary gate refuses to load unratified grammar. Exposes `Grammar.get_section()` / `has_section()` with FAIL-LOUD on missing. Regex parses `## §N TITLE` / `### §N.M TITLE` heading format. |
| `brand_tokens.py` | Parses a flat 10-key brand_tokens dict into BrandConfig. ValueError on missing required key. No defaults, no synthesis. |
| `chassis_config.py` | Per-element-class anti-pattern toggles. `allow_rounded_corners(element_class)` + `allow_drop_shadows(element_class)`. |
| `preprocess.py` | Body field markdown → HTML transforms. Bold / italic / paragraph / line-break only. Pyphen-driven hyphenation is configured in WeasyPrint via `hyphens: auto` + `lang="de"` (M1 install). |
| `validators/accent_budget.py` | `AccentBudgetValidator`. Single-path, area+location, hue-agnostic. Stub today; real validation post-decontamination. |
| `validators/overflow.py` | Text-overflow validator stub. |
| `validators/contrast.py` | WCAG contrast validator stub. |
| `patterns/st_07a.py` | LRP case-study page template. The only fully-implemented pattern today. Reads BrandConfig + grammar §2/§3.5/§3.7/§4.0; emits a complete HTML+CSS document. |
| `patterns/st_*.py` (others) | Stubs for the 13-pattern build subset (matrix ROW SLOT-PLAN). |
| `fonts/` | The 4 variable font files. Old `Inter-*.ttf` + `SourceSerif4-*.ttf` files remain on disk as historical artifacts (not referenced by any active CSS). |
| `assets/` | Marble texture + GEVA photo placeholder. |
| `output/` | Render outputs: `geva.html`, `geva.pdf`, `geva-p1.png`. |
| `tests/test_chassis_contract.py` | 11 contract tests; pytest-discoverable; no rendering, no WeasyPrint. |
| `.venv/` | Python 3.11 + WeasyPrint + Pyphen + PyMuPDF + qrcode + pytest. `bin/activate` exports `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` so WeasyPrint finds Homebrew Pango/GLib on macOS (Move 1 checkpoint). |

---

## How to test

```bash
source research/v7-renderer/.venv/bin/activate
cd research/v7-renderer
python -m pytest tests/ -v
```

11 tests, all pass. Pytest discovers them; no `conftest.py` is needed (the test file's own `sys.path` setup handles imports). Exit 0 on success.

The 11 tests:

| Test | What it pins |
|---|---|
| `test_grammar_loader_allows_ratified_default_grammar` | Trust gate GREEN side against the live grammar |
| `test_grammar_loader_blocks_underscores_as_blank` | Trust gate RED side via temp fixture |
| `test_grammar_loader_allows_ratified_fixture` | Trust gate GREEN side via temp fixture |
| `test_grammar_loader_exposes_section_bodies` | Parser title + body extraction |
| `test_grammar_loader_fail_loud_on_missing_section` | `get_section()` raises on absent section |
| `test_brand_tokens_parses_flat_config` | 10-field flat BrandConfig + 9 struck fields absent |
| `test_brand_tokens_missing_key_raises_value_error` | Plain ValueError on missing required key |
| `test_accent_budget_validator_returns_result` | Single-path validator; no `.path` field on result |
| `test_accent_budget_error_code_constant` | Error code value `"accent_budget_exceeded"` |
| `test_chassis_per_element_anti_pattern_toggles` | Per-element-class anti-pattern rules |
| `test_no_coral_in_chassis_logic` | **Regression guard.** Any reintroduction of `\bcoral\b` in production code (outside removal-history comments or .venv 3rd-party libs) fails the suite. |

The last one is the structural lock against re-contamination. Do not bypass it.

---

## How to render

```bash
source research/v7-renderer/.venv/bin/activate
cd research/v7-renderer
python render.py
```

Expected log lines:

```
[render] BrandConfig resolved: primary=#1A2540 accent=#E97E47 fonts=Montserrat/Source Sans 3
[render] Grammar loaded. sections=30 source=richard-grammar-v2.md
[render] HTML: .../output/geva.html  (~34 KB)
[render] PDF:  .../output/geva.pdf   (~800 KB)
[render] AccentBudgetValidator: passed=True details='accent-budget validation stub (post-decontamination work)'
[render] PNG p1: .../output/geva-p1.png  (1489×2105)
```

Exit 0. The PNG is the rasterized first page for visual inspection.

If WeasyPrint fails at `import weasyprint` with `OSError: cannot load library 'libgobject-2.0-0'`, source the venv's `bin/activate` first (it sets `DYLD_FALLBACK_LIBRARY_PATH` to find Homebrew's Pango/GLib). If the issue persists, ensure `brew install pango glib` has run.

---

## What's next (out of chassis scope)

These are the layers around the chassis that haven't been built yet. They are NOT chassis work; do not pull them in here.

1. **Layer 1 — Pre-processor.** Three sub-systems:
   - **Content preparation (Python):** ingest the JSON payload, validate copy rules (buzzword denylist, voice-marker minimums, construction limits from `04_DMC_Copy_Masterbook_v3.md` + `05_DMC_Intelligence_Layer_v4.md`), resolve customer fonts (Priorität 1), plan the page sequence per the 20-page slot plan.
   - **Typst component factory:** prior-art exists at `research/decoration-samples/_build/build_v6.py` (8 components with Richard's B1-B8 fixes verified during the M1 checkpoint). Components emit self-contained SVG strings that WeasyPrint composites inline.
   - **AI asset generation:** Nano Banana Pro (configured at `https://fal.run/fal-ai/nano-banana-pro`) + Flux 2 for textured paper backgrounds, atmospheric gradient washes, 3D-rendered decorative icons. Per-client palette control via hex-locked prompts.

2. **Layer 3 — Post-processor.** Ghostscript RGB → CMYK with ISO Coated v2 300% (FOGRA39); pikepdf for TrimBox/BleedBox stamping + WeasyPrint transparency-group fix; veraPDF for PDF/X-4 compliance; `-dKPreserve=2` to keep body text K=100 black per `08_v2` H.1 L370.

3. **Multi-page fixture.** Today the chassis renders a single ST-07A page from `research/v7-test/fixture_mw_geva.json`. The real target is a 20-page (or 16/24/28) report, sequenced per Master System Modul 9.1. The 13-pattern build subset (ROW SLOT-PLAN) is what fills the slot plan; today only ST-07A LRP is fully implemented. The other 12 patterns are stubs awaiting per-pattern build.

4. **Real AccentBudgetValidator.** Rasterize each page (PyMuPDF), find connected accent-coloured regions (`brand.brand_accent` ±ΔE 10), compute area share, classify each region's nearest DOM ancestor against the §3.7 firing-location whitelist. Emit `accent_budget_exceeded` with a useful `details` string on violation.

5. **The remaining grammar validators.** Whitespace ≥20% per page (rasterize, count empty pixels). ≤3 design-colour clusters per report (distinct-hue-cluster count across pages). Atemseite rhythm (every 5-7 pages, no two adjacent). CTA-Kadenz (S2 soft / S9 mid / S18 mid / S20 hard). All HARD per the matrix but unimplemented.

---

## Decontamination history (brief)

The chassis was built in mid-May 2026 around one client's fixture (GEVA). That build froze GEVA-shaped values as architecture: the word "coral" became a class name, a validator name, a constant, a config key, and a CSS class. Apex-contract defaults froze as `APEX_DEFAULT_PROFILE`. The grammar was the dead `SKILL.md` (overfit to 2 pages of one client). All five removed in a five-move decontamination (Moves 0-4, May 23 2026):

- **Move 0** — repointed `grammar_loader` from `SKILL.md` to `richard-grammar-v2.md`; added RATIFIED-BY trust gate.
- **Move 1** — updated the parser regex for the new heading format; remapped `get_section()` call sites; installed Pyphen.
- **Move 2a** — fetched Montserrat + Source Sans 3 variable fonts; deleted Inter / Source Serif 4 from active CSS.
- **Move 2b** — removed the BARRED §5c micro-header callout grid (no Richard citation; UNGROUNDED per grammar §8).
- **Move 2c** — full chassis decontamination: deleted `APEX_DEFAULT_PROFILE`, `APEX_CORAL_COUNT_BUDGET`, `BrandConfigError`, `design_preferences`, `brand_secondary_panel`, `coral_budget_per_page`, `callout_row_color`, `section_label_style`; collapsed `BrandConfig` to 10 flat fields; renamed `validators/coral.py` → `validators/accent_budget.py` (`CoralValidator` → `AccentBudgetValidator`, `CORAL_BUDGET_EXCEEDED` → `ACCENT_BUDGET_EXCEEDED`); rewrote tests; added `test_no_coral_in_chassis_logic` as the permanent regression guard.
- **Move 3** — migrated the test suite from a hand-rolled `if __name__ == "__main__"` runner to pytest (9.0.3).
- **Move 4** — rewrote these orientation docs (CHASSIS-NOTES, BUILD-NOTES, README).

Full record in `docs/superpowers/plans/2026-05-16-grammar-contract-reconciliation-matrix.md` — see the 2026-05-18 RICHARD-PRIMARY block and the 2026-05-23 MOVE 1 block.
