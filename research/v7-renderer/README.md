> **STALE: DO NOT ORIENT FROM THIS FILE.** It describes an earlier frame and is wrong on load-bearing facts. Authoritative current sources: `context.md`, `docs/superpowers/CURRENT-STATE.md`, `richard-grammar-v2.md`. Corrections that bite: the engine is **Chromium print-to-PDF plus Ghostscript flatten**, NOT WeasyPrint (legacy `--engine weasyprint` fallback only); bundled fonts are **Source Serif 4 and Source Sans 3** variable faces, NOT Montserrat; the renderer consumes a **multi-page `resolved_package.json` via `--package-dir`**, NOT a single-page GEVA fixture. (Banner added 2026-06-21.)

# v7-renderer — chassis (Layer 2 of three)

Print-grade PDF renderer for German B2B consulting reports. The chassis is **Layer 2 (compositor)** of a three-layer architecture: pre-processor (content + AI assets + Typst SVG components) → **this chassis** (WeasyPrint compositor) → post-processor (Ghostscript RGB → CMYK + PDF/X-4).

The chassis is brand-agnostic and hue-agnostic. It reads a flat 10-field `BrandConfig` plus the ratified design grammar (`richard-grammar-v2.md`) and emits an RGB PDF. The grammar is the source of truth; the chassis never names a client or hardcodes a hex.

## Setup

```bash
source research/v7-renderer/.venv/bin/activate
cd research/v7-renderer
```

The venv's `activate` script exports `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` so WeasyPrint finds Homebrew's Pango/GLib on macOS (Move 1 install: `brew install pango glib`, plus `pip install pyphen` for German hyphenation).

The 4 variable font files must be present under `fonts/`:
`Montserrat[wght].ttf`, `Montserrat-Italic[wght].ttf`, `SourceSans3[wght].ttf`, `SourceSans3-Italic[wght].ttf` (fetched in Move 2a from Google Fonts). The render fails loud at preflight if any are missing.

## Render

```bash
python render.py
```

Renders `research/v7-test/fixture_mw_geva.json` (a single ST-07A LRP page) through the chassis. Produces `output/geva.html`, `output/geva.pdf`, and `output/geva-p1.png`. Exit 0 on success.

The render path: fixture → `parse_brand_tokens` → `load_grammar` (trust gate fires if `RATIFIED-BY` is blank) → `patterns.st_07a.render_lrp` → WeasyPrint → `AccentBudgetValidator` (stub) → PyMuPDF rasterize.

## Test

```bash
python -m pytest tests/ -v
```

11 tests via pytest 9.x. All must pass (exit 0). The last test — `test_no_coral_in_chassis_logic` — is the permanent regression guard; it scans production source for `\bcoral\b` and fails if it appears in any active code line.

## Where to read more

| File | What it covers |
|---|---|
| `CHASSIS-NOTES.md` | Current chassis architecture, source-of-truth boundary, brand model, validator, fonts, body specs, what's next |
| `BUILD-NOTES.md` | Historical retrospective of the original Phase 4 build (pre-decontamination). Header explicitly marks it as history |
| `/Users/utkarsh/Projects/richard/richard-grammar-v2.md` | The ratified design grammar — Layer-A structural patterns + Layer-B per-client profiles + anti-patterns + print export specs |
| `docs/superpowers/plans/2026-05-16-grammar-contract-reconciliation-matrix.md` | Ratification history — see the 2026-05-18 RICHARD-PRIMARY block and the 2026-05-23 MOVE 1 block for the decontamination record |

## What NOT to do

The chassis carries permanent guards against the failure mode it just escaped (a single client's values frozen as universal architecture). Do not undo them:

- **Do not add client-specific values to chassis logic.** Hex colours, font names, geometry choices, treatment options all live in brand fixtures and the grammar's per-client §4.1 profiles — never in `if`, `else`, function names, class names, or constants.
- **Do not name a specific accent colour value in active code.** The accent is `brand.brand_accent`. The hex it resolves to is the client's business. `test_no_coral_in_chassis_logic` is the regression guard — it scans production source for the prior frame's contaminating accent word and fails the suite if it returns.
- **Do not reintroduce a nested preferences object on BrandConfig, or a client-default fallback profile.** `BrandConfig` is flat 10 fields. `parse_brand_tokens` reads them and returns. There is no defaulting branch. `test_brand_tokens_parses_flat_config` asserts the 9 struck fields are absent from the dataclass.
- **Do not load the retired prior grammar file** (at `research/idml-spike/skills/richard-design-system/`, marked DEAD on its first line). The grammar loader points at `richard-grammar-v2.md`. Editing the loader path back is a regression.
- **Do not give patterns a global anti-pattern flag.** Rounded corners and drop shadows are per-element-class decisions via `chassis_config.allow_rounded_corners(class_name)`. CTA boxes round; mechanism step cards round (VARIATION); nothing else.

The principle in one sentence: **this system is input-driven software** — the content payload, brand profile, and grammar are the inputs; the chassis processes them generically. If you find yourself writing `if client == "GEVA"` or naming a hex value in logic, you are writing a one-off script, not software.
