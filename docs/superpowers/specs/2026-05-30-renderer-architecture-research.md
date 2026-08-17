# Renderer Architecture — Research & Decision (ADR)

**Date:** 2026-05-30
**Question:** Are we building the renderer the way expert teams build a brand-agnostic, data-driven, print-grade document engine — or are we vibe-coding it? What engine / libraries / methodology should we use?
**Method:** 3 parallel deep-research agents (engines; software architecture; InDesign/IDML + Drive). Sources cited inline.

---

## TL;DR recommendation

1. **The engine is NOT our main problem — the architecture is.** Our blandness + dropped assets + pollution risk come from hand-written **f-string HTML/CSS** with hardcoded literals, not from WeasyPrint's ceiling. WeasyPrint can do multi-column, color blocks, images, charts — we simply didn't use it.
2. **Fix the architecture (essential, do first):** **Jinja2 templates** (structure out of Python) + **design tokens** (DTCG / Style Dictionary → CSS vars) + **atomic components** + **axis-driven theming via `data-*` attributes** + **visual-regression tests**. This is what makes it genuinely brand-agnostic and kills the client-pollution failure mode.
3. **Stay on WeasyPrint for now** (free, deterministic, pure-Python; CMYK/bleed are already handled by our Ghostscript post-processor, so the engine only needs faithful RGB). **Keep PrinceXML/DocRaptor as an optional later ceiling-raise** if, after the architecture fix, a specific WeasyPrint limit (column balancing, advanced floats) still blocks the design — note the cost (Prince ~$2,500/yr, or DocRaptor metered + sends our HTML to a third party).
4. **Do NOT move to InDesign/IDML.** Our own prior `idml-spike` already concluded this; it's wireframe-only, needs a designer in the loop per report, and InDesign Server is ~$5–13.5k/yr + heavy ops. Overkill for templated B2B reports.
5. **Drive asset layer (when we wire production):** user-OAuth2 + refresh token (consumer Gmail → not a service account), `files.list` folder query + `files.get_media`, a **declarative naming→schema map** (our `image_map.json` already is this), md5 cache, fail-loud on missing slots.

---

## Finding 1 — Rendering engine

Key reframe: **our post-processor already does RGB→CMYK→PDF/X-4 (Ghostscript)**, so the engine only needs a faithful RGB+ICC PDF. CMYK/bleed are NOT engine-selection criteria.

| Engine | Design fidelity | Determinism | Notes |
|---|---|---|---|
| **WeasyPrint** (current) | Medium — no cross-page column balancing, weaker float/flex, no JS | Excellent | Free, BSD, pure-Python. "Good enough" tier; v68 closed much of the gap. |
| **PrinceXML / DocRaptor** | **Highest** HTML engine (page floats, footnotes, robust floats, baseline grid) | Excellent | Prince ~$2,500/yr; DocRaptor = Prince-as-a-service (metered, external). Drop-in for our HTML/CSS. |
| **Paged.js + headless Chromium** | High | **Weak** (Chrome version drift) | Stagnant project; non-deterministic. Avoid. |
| **Typst** | High | Excellent | Strongest *non-CSS* path, but a full authoring rewrite. |
| **react-pdf / Satori** | Low for 20-pp docs | Good | Wrong tool. |
| **InDesign Server / IDML** | Maximum (it *is* the source spec) | Good | ~$20k/yr all-in + Adobe lock-in. Overkill. |

**Verdict:** WeasyPrint now; Prince/DocRaptor is the only option that raises the ceiling while preserving our HTML/CSS investment — adopt only if a concrete limit forces it.
Sources: WeasyPrint limits (github.com/Kozea/WeasyPrint/issues/816), DocRaptor/Prince (docraptor.com/prince-alternatives, princexml.com/purchase), Chromium caveats (andre.arko.net/2025/05/25/chrome-headless-print-to-pdf), InDesign Server cost (metadesignsolutions.com/blog/beyond-the-license…).

## Finding 2 — Software architecture (the real lever)

The problem: every page "pattern" hand-builds HTML via f-strings + a big inline CSS string, with literal fonts (`'Montserrat'`), raw colors (`#fff`/`#333`), and German labels baked into code. That fuses content/structure/style/theme and invites client-pollution.

**Target architecture:** `data (report.json) → DTCG design tokens (Style Dictionary) → CSS custom properties + data-* axes → Jinja2 templates → atomic components → WeasyPrint → visual-regression tests`.
- **Design tokens:** three-tier (primitives → semantic aliases → component tokens) in the W3C **DTCG `$value`/`$type`** format, compiled by **Style Dictionary v4** into the `:root` CSS vars. Components reference *semantic* tokens only — never client hexes. Per-client = swap the primitive layer; structure untouched.
- **Templating:** **Jinja2** (the standard for WeasyPrint PDFs) replaces f-strings; markup in `.html.jinja`, Python does data prep only. Forbids inline Python → enforces separation.
- **Components:** restructure `patterns/` as atomic design (atoms → molecules → organisms → templates → pages); current `_components.py` builders become Jinja macros with class-based CSS in stylesheets.
- **Axis-driven variants:** axes (`headline_type=serif|sans`, `ground_mode`, `texture`) → `<html data-headline="serif" data-ground="dark">` + CSS `[data-headline="serif"]{--font-heading:var(--font-serif)}`. Logic never branches on client identity.
- **Visual-regression:** rasterize each page (we already do via PyMuPDF) → pixel-diff vs committed baselines (pixelmatch/reg-suit). Quality becomes verifiable, not vibe-checked.

**Incremental migration (low-risk order):** (1) tokenize all literals → semantic CSS vars, snapshot baselines; (2) add Style Dictionary + DTCG source, generate `:root`; (3) convert ONE pattern to Jinja2 keeping the `PageFragment` contract (assembler untouched), verify ~zero pixel-diff, then the rest; (4) reorganize into atomic folders; (5) wire axes → `data-*`, move German strings into a data/i18n file.
**Pollution prevention:** ban hex/font-literals/`if client==` outside the token source (extend the guard tests); primitives never leak into components; the grammar compiles *into* tokens (spec is source, CSS is generated).
Sources: designtokens.org DTCG spec (stable 2025.10), styledictionary.com/info/dtcg, bradfrost.com (themeable design systems + atomic design), Jinja2+WeasyPrint guides, BrowserStack/reg-suit visual-regression.

## Finding 3 — InDesign/IDML + Drive

- **idml-spike (our repo) concluded:** IDML hand-authoring is a structural wireframe only (designer adds 30–50% per page), SimpleIDML manipulates rather than authors, InDesign acceptance was never verified, and it explicitly recommended pivoting to WeasyPrint + designer touch-up.
- **InDesign Server**: $5k/yr (internal) / $13.5k/yr (customer-facing) + Windows/macOS host + queueing/monitoring. **Adobe InDesign API (Firefly)**: new, removes self-hosting but enterprise-priced (~$1k/mo min, print specifics undocumented). **ExtendScript** is legacy (Adobe pushing UXP). At scale, agencies/SaaS (Typefi, Pagination, CHILI) *buy a platform* — that's the cost.
- **Determinism + cost favor HTML/CSS.** Reconsider InDesign only if a print shop mandates spot inks sourced from InDesign PDFs.
- **Drive layer:** user-OAuth2 + stored refresh token; `files.list(q="'<folderId>' in parents and trashed=false")` paged; `files.get_media` streamed; declarative naming→schema map; cache by `md5Checksum`; validate required slots → fail-loud per slot.
Sources: datalogics.com/adobe-indesign-server, developer.adobe.com/firefly-services/docs/indesign-apis, helpx.adobe.com/indesign/using/data-merge, googleapis python client docs, our `research/idml-spike/`.

---

## What this means for our build

- The R2 "blandness" is fixable **within WeasyPrint** by fixing the architecture and actually using rich layout + integrating assets — it was never primarily an engine limit.
- The architecture overhaul (tokens + Jinja2 + atomic components + visual-regression) is **also the permanent fix for the client-pollution problem** that has bitten us — it's the same work.
- Recommended next step: write an **architecture-migration spec** (tokens + Jinja2 + components + visual-regression + grammar-as-token-source), then rebuild the patterns on it grammar-driven, staying on WeasyPrint, with Prince held in reserve.
