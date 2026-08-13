# DMC Renderer — Font Loading

How fonts get into the WeasyPrint render. Short version: bundled in the
Docker image at `/app/fonts/`, declared via `@font-face`, never fetched
at runtime.

---

## Bundled fonts

All TTF files live at `dmc-renderer/fonts/` in the repo and are copied
to `/app/fonts/` in the Docker image (see § Dockerfile entry).

| Family | Weight | Style | File | Source / License |
|---|---|---|---|---|
| Inter | 400 | normal | `Inter-Regular.ttf` *(to bundle — see § Pending below)* | Google Fonts (SIL OFL 1.1) |
| Inter | 700 | normal | `Inter-700.ttf` | Google Fonts (SIL OFL 1.1) |
| Inter | 800 | normal | `Inter-800.ttf` | Google Fonts (SIL OFL 1.1) |
| Inter | 900 | normal | `Inter-900.ttf` | Google Fonts (SIL OFL 1.1) |
| Source Serif 4 | 400 | normal | `SourceSerif4-Regular.ttf` | Adobe (SIL OFL 1.1) |
| Source Serif 4 | 400 | italic | `SourceSerif4-Italic.ttf` | Adobe (SIL OFL 1.1) |
| Source Serif 4 | 700 | normal | `SourceSerif4-Bold.ttf` | Adobe (SIL OFL 1.1) — **v6.1 addition** |
| Vollkorn | 700 | normal | `Vollkorn-Bold.ttf` | Google Fonts (SIL OFL 1.1) — used for Apex display headlines |

**v6.1 fix landed:** `SourceSerif4-Bold.ttf` is now bundled. Body `<strong>` resolves to true same-family serif bold instead of the v6 cross-family Inter-800 workaround.

### Pending (to add before Phase 3 first ST renders)

- `Inter-Regular.ttf` — currently the palette uses `Inter-700.ttf` as a placeholder for weight 400. This means body sans text (when used) is rendered too heavy. Low priority because the current Apex templates use Serif for body and Inter only for labels/headlines (all of which are 700+).

To add: download from <https://github.com/rsms/inter/releases/latest> (look for `Inter-4.x.zip` → `extras/ttf/Inter-Regular.ttf`), drop into `dmc-renderer/fonts/`, add `@font-face` declaration in `base.css.j2`.

### Total bundle size

Current 7 TTFs ≈ **1.8 MB**. Docker layer cost is negligible.

---

## `@font-face` declarations

Emitted once in `base.css.j2`, used by every template:

```css
/* Inter — sans, headlines + labels */
@font-face { font-family: 'Inter'; font-style: normal; font-weight: 400;
             src: url('file:///app/fonts/Inter-Regular.ttf') format('truetype'); }
@font-face { font-family: 'Inter'; font-style: normal; font-weight: 700;
             src: url('file:///app/fonts/Inter-700.ttf')     format('truetype'); }
@font-face { font-family: 'Inter'; font-style: normal; font-weight: 800;
             src: url('file:///app/fonts/Inter-800.ttf')     format('truetype'); }
@font-face { font-family: 'Inter'; font-style: normal; font-weight: 900;
             src: url('file:///app/fonts/Inter-900.ttf')     format('truetype'); }

/* Source Serif 4 — body + italic accents + bold emphasis */
@font-face { font-family: 'Source Serif 4'; font-style: normal; font-weight: 400;
             src: url('file:///app/fonts/SourceSerif4-Regular.ttf') format('truetype'); }
@font-face { font-family: 'Source Serif 4'; font-style: italic; font-weight: 400;
             src: url('file:///app/fonts/SourceSerif4-Italic.ttf')  format('truetype'); }
@font-face { font-family: 'Source Serif 4'; font-style: normal; font-weight: 700;
             src: url('file:///app/fonts/SourceSerif4-Bold.ttf')    format('truetype'); }

/* Vollkorn — Apex display override */
@font-face { font-family: 'Vollkorn'; font-style: normal; font-weight: 700;
             src: url('file:///app/fonts/Vollkorn-Bold.ttf') format('truetype'); }
```

Templates reference these by `font-family` name in CSS rules (`font-family: 'Source Serif 4', Georgia, serif;`). Fallback names in the family list are noisy fallbacks that shouldn't fire — if WeasyPrint can't find the bundled face, the operator sees a warning in logs and the visible output falls back to whatever system font WeasyPrint picks.

---

## Why we don't fetch fonts at render time

- **Determinism.** A font that renders today must render the same way tomorrow. Network-fetched fonts can change subtly (e.g. Google Fonts variants getting a new hinting pass) without warning.
- **Latency.** Even a cached fetch adds 100–500 ms; bundled fonts add zero.
- **Failure modes.** A flaky CDN at render time → render fails. Bundled fonts always work.
- **Determinism (again).** Bundled fonts mean the renderer's Docker image is a self-contained reproducible build. Re-render any historical payload against the historical image → exactly the same PDF bytes (modulo timestamp).

---

## Dockerfile entry

```dockerfile
# Bundle fonts into /app/fonts/
COPY fonts/ /app/fonts/

# Make WeasyPrint discover them (pango/fontconfig)
RUN fc-cache -f /app/fonts/
```

The `fc-cache` step registers the fonts with fontconfig so WeasyPrint's
text shaper (Pango → HarfBuzz) finds them. Without `fc-cache`, fonts
load via `@font-face` URLs but glyph fallback (e.g. for German umlauts
within a font that lacks them) may misbehave.

---

## Same-family bold (the v6 → v6.1 fix)

In v5 + v6, the palette mapped `Source Serif 4` weight 700 to
`SourceSerif4-Regular.ttf` because no bold TTF was bundled. Result:
`<strong>` in body text rendered at the same visual weight as regular.

The v6 agent worked around this by routing `<strong>` to `font-family:
Inter; font-weight: 800` — a cross-family sans bold inside serif body
text. Visible bold ✓, but typographically inconsistent.

v6.1 fix:

1. Added `SourceSerif4-Bold.ttf` to `_fonts/` (and the production bundle at `fonts/`).
2. Updated the `@font-face` mapping so weight 700 normal points to the bold binary, not the regular binary.
3. Reverted the `.body-section p strong` CSS to `font-family: 'Source Serif 4'; font-weight: 700;` — true same-family bold.
4. Re-rendered the Conesso assembly. Visually verified the bold spans render in serif (not sans) and stay within the same family as the surrounding paragraph.

This now matches the reference reports (aerztepartner, buchagentur, alex_boss) which all use same-family bold for body emphasis.

---

## Adding a new font (procedure)

When a client's `brand_tokens.font_heading` or `font_body` doesn't match
any bundled family:

1. **Get the TTF (or convert from OTF).** Prefer SIL OFL or Apache-2.0 licensed fonts. Commercial fonts require a license check — get sign-off.
2. **Place at `dmc-renderer/fonts/<FamilyName-Weight>.ttf`.** Filename convention: `Family-Weight.ttf` (e.g. `Inter-700.ttf`), `Family-WeightItalic.ttf` (e.g. `SourceSerif4-Italic.ttf` for italics regardless of weight — Adobe convention preserved).
3. **Add `@font-face` block** to `templates/base.css.j2` matching the existing pattern. Weight + style values must match what CSS rules will request.
4. **Update `FONT_ALIASES` in render.py** if the brand sends a legacy/alternate name (see [BRAND_TOKENS.md § Font name normalization](BRAND_TOKENS.md#font-name-normalization)).
5. **Rebuild Docker image.** The bundle changes, so `fc-cache` re-runs at image build.
6. **Test render the Apex fixture** with `brand_tokens.font_heading` (or `font_body`) set to the new family name. Verify visual output uses the new face — easiest check is rendering a single character (like uppercase Q) which has distinctive forms across families.

---

## Font subsetting

WeasyPrint embeds full font files in the PDF by default. For our font set (~1.8 MB of TTFs), a 20-page report PDF is ~500 KB — fonts are the biggest single contributor.

Subsetting (embedding only the glyphs actually used) would shrink that to ~150 KB per report. WeasyPrint 68+ supports automatic subsetting via the Pango stack, but enabling it costs a tiny bit of determinism: subset byte-ranges can differ across runs.

**Current call:** subset enabled (default). The deterministic byte requirement is on the *visible* output, not the byte-identical PDF. If a downstream consumer needs byte-identical PDFs, switch to non-subset embedding via:

```python
weasyprint.HTML(...).write_pdf(target, optimize_images=True, font_config=non_subset_config)
```

…and accept the 4× file size penalty. Not needed today.
