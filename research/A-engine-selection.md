# Research Task A — PDF Rendering Engine Selection

**Service:** `dmc-renderer` (FastAPI, A4-portrait PDF, German B2B 16-28pp lead-magnet reports)
**Target quality:** "indistinguishable from InDesign to a layperson"
**Constraints:** Digital-only PDF 1.7 / sRGB, hosted on Railway, free strongly preferred; PrinceXML self-hosted is the only acceptable paid option ($3,800 one-time + ~$2,500/yr support); DocRaptor is excluded.

---

## 1. Per-engine findings

### 1.1 WeasyPrint 68.1 (Feb 2025 stable, Python-native)
- Mature, actively maintained by CourtBouillon. v67 (Dec 2024) added CMYK + PDF/A variants + CSS Layers + `::first-line`; v68 added font-face for SVG, CVE-2025-68616 fix, language-specific `text-transform`. No 2026 release yet on GitHub.
- Implements the entire CSS Paged Media L3 module: `@page`, named pages, all margin boxes (`@top-left`, `@bottom-right`, etc.), `:left/:right/:first/:blank/:nth()`.
- Full CSS GCPM L3: `bookmark-level`, `bookmark-label`, `bookmark-state` (PDF outline); `string-set` + `content(string)`; `target-counter()`, `target-text()`; `float: footnote` + `::footnote-call` + `::footnote-marker`.
- Font stack = Pango + HarfBuzz; OpenType features via `font-feature-settings`, `font-variant-*`, `font-kerning`. Kerning + standard ligatures (ff/fi/fl) work; ä/ö/ü/ß flawless (UTF-8 + Pango).
- Hyphenation via `pyphen` — solid German `de-DE` dictionaries (Liang patterns), `hyphens: auto`, `hyphenate-limit-chars` controls.
- **NOT supported**: `hanging-punctuation` (officially listed as unsupported in CSS Text L3 features); OpenType `lfbd`/`rtbd` optical margin alignment is not natively implemented (you can pass them via `font-feature-settings` but the engine itself does not produce optical bleed at the margin).
- sRGB ICC: yes — `--srgb` CLI flag / `srgb=True` in API embeds the standard sRGB profile and tags it as the default for device-dependent RGB. PDF/A-2u/3u supported.
- Speed: ~335 ms/page single page; scales linearly. For 20 pages of A4 with images, expect ~1–3 s typical. (speedata 2026 benchmark.)
- Deploy: pure Python (CFFI bindings to system libs). Docker base needs `libpango`, `libcairo`, `libgdk-pixbuf`, `fontconfig`. Min ~2 GB RAM; final image typically 400–700 MB on `python:3.12-slim`. Trivial on Railway.

### 1.2 Paged.js + headless Chromium (Playwright)
- Polyfill for CSS Paged Media + GCPM that runs inside Chromium and uses Chrome's "print to PDF" backend. Maintained by Coko Foundation (used in Ketty, Kotahi, Louvre's catalogue raisonné).
- Implements `@page`, margin boxes, `string-set`/`content(string)`, `target-counter()`, `target-text()`, footnotes via `float: footnote` — **but** footnotes have multiple open issues (specificity bug on `float: none`; unsuppressible `::footnote-call`; counter-reset can hang the renderer). Known buggy for complex docs.
- Typography quality inherits Chromium's HarfBuzz pipeline — kerning, ligatures, OpenType `font-feature-settings` all work well (ä/ö/ü/ß flawless).
- Hyphenation: depends on the Chrome version's bundled dictionaries; German hyphenation works in Chromium but quality is "browser-grade" not "publishing-grade" (less tuned than TeX/Prince).
- `hanging-punctuation`: Chromium does **not** ship this property (only Safari has partial support).
- `bookmark-level`/`bookmark-label`: not native to Chrome print; Paged.js has limited bookmark support via plugin; quality is below WeasyPrint/Prince.
- sRGB ICC: Chrome embeds sRGB by default; explicit ICC tagging is fragile.
- Speed: 1–3 s engine cold-start (browser spin-up) + paginate time; ~2–4 s end-to-end for 20 pages.
- Deploy: heavy. Playwright + Chromium = ~350 MB Chromium binary alone; image ~1.2–1.8 GB; needs 1.5–2 GB RAM. **FastAPI integration is fragile**: `sync_playwright` blocks the event loop, `asyncio` subprocess loop quirks (documented FastAPI issue #5446, playwright-python #2097). Workable but needs careful worker management.

### 1.3 PrinceXML self-hosted (16.2, Jan 2026)
- The reference standard for HTML-to-PDF typography. Used by The Economist, Springer, Wiley.
- Prince 16 (Feb 2025) added CSS Grid (single-page), variable fonts, CFF2 outlines. **Prince 16.1 (Jul 2025) → 16.2 (Jan 2026)** are the current releases. The roadmap (last updated 2026-03-10) shows `font-feature-settings` and `font-variant-alternates` / `@font-feature-values` were marked **Done 2026-03-10** — i.e. they are in pre-release builds and shipping any day.
- CSS Paged Media: gold-standard. Named pages, full margin boxes, `string-set`, `content(string)`, `target-counter()`, `target-text()`, `bookmark-level`/`bookmark-label` (vendor-prefixed `-prince-bookmark-*`), `float: footnote` + `prince-column-footnote` / `prince-column-inline-footnote`.
- Typography: best-in-class kerning, ligature, OpenType handling — supports OpenType GPOS, GSUB, kern table fallback when GPOS absent; `font-variant: prince-opentype()` exposes arbitrary OT features. German ä/ö/ü/ß flawless, ligatures perfect, kerning tables fully honoured.
- Hyphenation: Prince ships hand-curated dictionaries for German (including ß-aware) with quality on par with InDesign.
- **`hanging-punctuation`: NOT supported** (Prince's own docs say: "Prince does not recognize `line-break`, `text-align-all` and `hanging-punctuation`"). It is on the roadmap as "Support optical alignment and hanging punctuation for neater margins" — undated.
- OpenType `lfbd`/`rtbd` optical margin alignment: not exposed directly, but Prince's `text-align: justify` paragraph layout is closer to InDesign than any other engine.
- sRGB ICC: full ICC embed support, PDF/A-1a/2a/2b/3a/3b, PDF/X-1a/X-4. The most production-ready color story.
- Speed: ~0.3–0.5 s for 20 pages typical; very fast.
- Deploy: closed-source C++ binary. Single static binary, ~50 MB. Trivial Docker image (debian + libc deps). Memory <200 MB for a 20-page doc. Python integration = subprocess call. Community Docker image exists (`michaelperrin/prince`). Railway hosting trivial.
- License: $3,800 one-time + $2,500/yr after year 1 for upgrades & support.

### 1.4 Vivliostyle (Core 2.x / CLI v10.5, Apr 2026)
- Actively maintained (CLI v10.5.0 dated 2026-04-12; CLI v10 dropped Dec 2025; CLI v10.1 added cross-OS automatic hyphenation Jan 2026).
- Engine = TypeScript inside headless Chromium (similar architectural model to Paged.js but with a more complete CSS Paged Media implementation maintained by the Vivliostyle Foundation in Japan).
- CSS Paged Media + GCPM support is broader than Paged.js: `string-set`, `target-counter`, `target-text`, named pages, running headers, footnotes via `float: footnote`, leaders. The 3renderers benchmark suite groups WeasyPrint, Paged.js, and Vivliostyle as the three serious open-source contenders.
- Typography: also Chromium + HarfBuzz; kerning + ligatures = browser-grade (same level as Paged.js, below Prince).
- `hanging-punctuation`: not supported (Chromium limitation).
- Hyphenation: as of v10.1 (Jan 2026) automatic hyphenation works on Linux for the first time → previously a deployment blocker. Quality is good for German.
- Output: PDF/X-1a press-ready option. sRGB ICC reliable.
- Speed: similar to Paged.js (~2–4 s for 20 pages incl. browser warmup).
- Deploy: Node.js v20+ + bundled Chromium via Playwright. Image ~1.2 GB. **No Python binding** — subprocess to the `vivliostyle` CLI from FastAPI. Workable, slightly clunkier than WeasyPrint.

### 1.5 Typst (0.14.2, Dec 2025)
- Rust-based modern typesetting system, Apache-2.0. Active and fast-moving (0.14.0 Oct 2025, 0.14.1 Dec 2025, 0.14.2 Dec 2025). Has its own DSL, **not HTML/CSS**.
- HTML export was added in 0.14 (Oct 2025) — but it's **experimental and produces HTML *output***. There is no general "HTML → Typst → PDF" path. To use Typst with the existing JSON-to-HTML pipeline assumed by `dmc-renderer`, we would have to either (a) translate the JSON to Typst markup, or (b) rely on Pandoc's HTML-to-Typst conversion (lossy for fine CSS).
- Typography: HarfBuzz-based, with TeX-class line-breaking, character-level justification (new in 0.14), kerning, ligatures, OpenType features via the `text` function. Quality is genuinely in the TeX class — better than WeasyPrint/Paged.js/Vivliostyle for paragraph composition; in some respects (optical character-level justification) approaches InDesign.
- German hyphenation: native, language-aware, 34+ languages including German (de). Liang patterns + their own optical penalty tuning ("hyphens close to word edges discouraged" — 0.12).
- No `hanging-punctuation` CSS, but Typst's own justification model achieves equivalent visual balance via character-level micro-adjustment.
- Cross-refs (`ref`, `counter`), running headers, bookmarks/PDF outlines (auto for headings), footnotes: all native and stable.
- PDF: PDF/A (all variants), accessibility tagged by default in 0.14, sRGB default with ICC embed possible. Tagged PDF + character-level justification + speed combo is unmatched in this list.
- Speed: ~106 ms single page, **8.7 s for 500 pages — 28× faster than WeasyPrint**. Probably ~0.2 s for 20 pages.
- Deploy: single Rust binary, ~30 MB. Python integration: `typst` PyPI package (Rust binding, no subprocess); `typst-py`; `pypst` (high-level wrapper). Docker image <200 MB, RAM <200 MB. Cheapest deploy of all options.
- **Risk:** the input format change. If the JSON-to-HTML mapping is half-built we'd be rewriting the templating layer in Typst's DSL. Cost = full re-author of template system.

---

## 2. Comparison table

Score legend: ★★★★★ excellent · ★★★★ good · ★★★ acceptable · ★★ weak · ★ missing/broken

| Criterion | WeasyPrint 68 | Paged.js + Chromium | PrinceXML 16.2 | Vivliostyle 10 | Typst 0.14 |
|---|---|---|---|---|---|
| German ä/ö/ü/ß | ★★★★★ Pango/HB | ★★★★★ Chromium/HB | ★★★★★ native | ★★★★★ Chromium/HB | ★★★★★ HB |
| German hyphenation quality | ★★★★ pyphen/Liang | ★★★ browser dict | ★★★★★ hand-tuned dicts | ★★★★ since v10.1 cross-OS | ★★★★ Liang + edge penalty |
| Ligatures (ff/fi/fl) | ★★★★ `font-variant-ligatures` | ★★★★ via CSS | ★★★★★ best-in-class GSUB | ★★★★ via CSS | ★★★★★ native |
| Kerning quality | ★★★★ HarfBuzz | ★★★★ HarfBuzz | ★★★★★ + kern fallback table | ★★★★ HarfBuzz | ★★★★★ HB + tuned model |
| `hanging-punctuation` | ★ unsupported | ★ Chromium lacks it | ★ roadmap only | ★ Chromium lacks it | ★ no CSS, but justification model compensates |
| OT `lfbd`/`rtbd` optical margin | ★★ via `font-feature-settings` only | ★★ via `font-feature-settings` | ★★★ exposed via `prince-opentype()` (now full `font-feature-settings` per 2026-03-10 roadmap) | ★★ via `font-feature-settings` | ★★★★ via `text(features: ...)` |
| `@page` + named pages + margin boxes | ★★★★★ | ★★★★ (some bugs) | ★★★★★ | ★★★★★ | ★★★★ different syntax |
| `string-set` / `content(string)` | ★★★★★ | ★★★★ | ★★★★★ | ★★★★★ | n/a (own counter system, equivalent) |
| `target-counter()` / `target-text()` | ★★★★★ | ★★★★ known bug w/ string in `content` | ★★★★★ | ★★★★ | ★★★★★ via `ref` |
| `counter(page)` / `counter(pages)` | ★★★★★ | ★★★★★ | ★★★★★ | ★★★★★ | ★★★★★ |
| `bookmark-level` + `bookmark-label` (PDF outline) | ★★★★★ UA stylesheet auto | ★★★ plugin only, partial | ★★★★★ `-prince-bookmark-*` | ★★★★ | ★★★★★ auto for headings |
| Footnote floats (`float: footnote`) | ★★★★★ stable | ★★ multiple open bugs in 2024-25 | ★★★★★ + column footnotes | ★★★★ | ★★★★★ native |
| SVG embed (inline + linked) | ★★★★★ | ★★★★★ | ★★★★★ + foreignObject (Prince 16.2) | ★★★★ | ★★★★ |
| sRGB ICC profile embed | ★★★★★ `srgb=True` | ★★★ Chromium-controlled | ★★★★★ full ICC + PDF/X | ★★★★ PDF/X-1a | ★★★★ default sRGB; explicit ICC flag in flight |
| Speed for 20 pp A4 | ★★★★ ~1-3 s | ★★ ~2-4 s (browser cold start) | ★★★★★ ~0.3-0.5 s | ★★ ~2-4 s | ★★★★★ ~0.2 s |
| Memory footprint | ★★★★ ~300-600 MB | ★★ 1.5-2 GB (Chromium) | ★★★★★ <200 MB | ★★ 1.5-2 GB | ★★★★★ <200 MB |
| Docker image size | ★★★★ 400-700 MB | ★★ 1.2-1.8 GB | ★★★★★ ~100 MB | ★★ ~1.2 GB | ★★★★★ ~150 MB |
| Python ergonomics | ★★★★★ native library | ★★★ async/sync gotchas in FastAPI | ★★★★ subprocess | ★★★ subprocess (Node CLI) | ★★★★★ `typst` PyPI binding |
| 2026 maintenance state | ★★★★★ active | ★★★★ active (Coko) | ★★★★★ commercial, just shipped 16.2 | ★★★★★ very active (v10.5 Apr 2026) | ★★★★★ very active |
| License cost | Free (BSD-3) | Free (MIT) | $3,800 + $2,500/yr | Free (AGPL-3 for core, but CLI usage as black-box is fine) | Free (Apache-2.0) |

---

## 3. Recommendation

**Use WeasyPrint 68.1 as the primary engine. Build a Prince-compatible CSS path so PrinceXML self-hosted can be swapped in later if quality testing requires it.**

### Why WeasyPrint over the alternatives

- **Among the four free options**, WeasyPrint is the only one that is (a) Python-native (no subprocess, no Node, no Chromium), (b) implements the full CSS Paged Media + GCPM spec the JSON-to-HTML pipeline assumes, and (c) has the smallest, fastest Railway footprint that doesn't need a 1.5-GB Chromium image.
- **Paged.js + Chromium** matches CSS coverage but has documented footnote bugs, Playwright-in-FastAPI event-loop pain, and 3-4× the container size and memory.
- **Vivliostyle** is technically excellent (the v10.1 cross-OS hyphenation fix in Jan 2026 finally unblocks Linux deployments) but adds a Node.js + Chromium dependency for marginal quality gain over WeasyPrint and significantly more deploy surface.
- **Typst** would produce the highest absolute typography quality of the free options — but the input is its own DSL, not HTML/CSS. Adopting it requires rebuilding the template layer (which the existing PRD assumes is HTML/CSS). If we were greenfielding the templating, Typst would be the recommendation; given a JSON→HTML→PDF pipeline is implied by the design system docs, the switch cost is prohibitive for Phase 1.

### Why not PrinceXML out of the gate

- The single concrete typography feature Prince offers that WeasyPrint does not have ready today (`font-feature-settings`) just shipped on Prince's roadmap (2026-03-10) and is also in WeasyPrint via `font-feature-settings`. The actual residual quality delta is: hand-tuned German hyphenation dictionaries, better paragraph composition for justified text, and slightly better kerning fallback. Real but not categorically out of reach for WeasyPrint on B2B lead-magnet reports at A4 portrait.
- **`hanging-punctuation` is missing from every engine in this list** including PrinceXML. So upgrading to Prince does not buy this capability. It can only be approximated via CSS tricks (negative margins on opening glyphs) and that trick works equally in WeasyPrint.
- $3,800 + $2,500/yr is non-trivial. Spec the system with WeasyPrint, ship Phase 1, then run a side-by-side render of `aerztepartner.pdf` / `buchagentur.pdf` etc. against WeasyPrint. If a layperson can distinguish the WeasyPrint version from InDesign, then Prince is justified. If they can't, save the money.
- The CSS we author for WeasyPrint is ~95% portable to Prince (both implement GCPM), so the swap path is short.

### Concrete plan
1. Phase 1 ships on **WeasyPrint 68.1** with `srgb=True`, PDF/A-3u optional, `hyphens: auto` + `lang="de"`, full `font-variant-ligatures: common-ligatures discretionary-ligatures`, `font-kerning: normal`.
2. After Phase 1 build, render the 4 reference PDFs (aerztepartner / buchagentur / alexander_boss / niklas_niemeyer) with WeasyPrint and have a layperson + the user compare against the InDesign originals.
3. If a visible quality gap remains → buy PrinceXML 16.2. The CSS swap is ~1 day of work.

---

## 4. Cost implication

| Plan | One-time | Recurring |
|---|---|---|
| **Recommended (WeasyPrint)** | **$0** | **$0** (Railway compute only) |
| Fallback (PrinceXML self-hosted if WeasyPrint quality insufficient) | $3,800 | $2,500/yr after year 1 |
| (excluded) DocRaptor | n/a | n/a |

Railway compute for WeasyPrint: ~1 GB RAM, 1 vCPU, ~$5-10/mo at expected volume.

---

## 5. Risks & known gotchas (WeasyPrint)

1. **`hanging-punctuation` unsupported.** If the reference InDesign PDFs use hanging quotes at paragraph starts, we have to fake it with `text-indent` negative offsets on `:first-letter` when the first character is a quote/punct. Hack but workable.
2. **No native optical margin alignment (`lfbd`/`rtbd`).** Same workaround required if reference docs use it. Most B2B lead-magnet reports don't — they use slab/sans body and rely on tight margins, not optical hanging.
3. **Pyphen German hyphenation is good but not as tuned as Prince's.** Mitigation: tune `hyphenate-limit-chars: 8 4 4`, `hyphenate-limit-lines: 2`, `widows: 2`, `orphans: 2` aggressively per the design system in `08_DMC_Design_System_v2.md`.
4. **System fonts on Railway**: WeasyPrint reads fonts via fontconfig. The Docker image must bundle the chosen DMC body/display fonts as `/usr/share/fonts/...` and run `fc-cache -f` in the build step.
5. **Memory spikes on long documents.** Issue #671 documents 1000+ page docs hitting 3 GB. Not relevant for 16-28 pp reports, but the rendering pipeline should `gc.collect()` and stream to disk per request.
6. **`hyphens: auto` requires `lang="de"` on the html element.** Easy to forget; add a renderer assertion.
7. **CMYK / PDF/X-4 transparency-group bug (issue #2723) is open.** Not a problem for sRGB digital-only delivery as specced.
8. **Two-pass layout limit:** WeasyPrint single-pass means complex flowing TOC + back-reference page numbers may need a render-twice pattern. WeasyPrint supports this via `target-counter()`, but the test harness should verify the TOC pages are accurate after a single render of all reference PDFs.

---

## 6. Evidence

- WeasyPrint stable docs & feature list: https://doc.courtbouillon.org/weasyprint/stable/features.html
- WeasyPrint 68 release: https://github.com/Kozea/WeasyPrint/releases
- WeasyPrint color management blog: https://www.courtbouillon.org/blog/00052-more-colors-in-weasyprint/
- WeasyPrint Docker / memory guidance: https://github.com/SchweizerischeBundesbahnen/weasyprint-service
- PrinceXML 16.2 release: https://www.princexml.com/releases/
- PrinceXML 16 release notes: https://www.princexml.com/releases/16/
- PrinceXML CSS support reference: https://www.princexml.com/doc/css-props/
- PrinceXML roadmap (hanging-punctuation on roadmap, `font-feature-settings` done 2026-03-10): https://www.princexml.com/roadmap/
- PrinceXML purchase / licensing: https://www.princexml.com/purchase/
- PrinceXML footnotes guide: https://www.princexml.com/howcome/2022/guides/footnotes/
- PrinceXML hanging-punctuation forum confirmation it's not yet supported: https://www.princexml.com/forum/topic/1492/hanging-punctuation
- PrinceXML optical margin forum confirmation roadmap: https://www.princexml.com/forum/topic/894/optical-margin
- Paged.js docs (running headers, cross-refs): https://pagedjs.org/en/documentation/7-generated-content-in-margin-boxes/ and https://pagedjs.org/en/documentation/-cross-references/
- Paged.js footnote bugs: https://github.com/pagedjs/pagedjs/issues/224, https://github.com/pagedjs/pagedjs/issues/292
- Paged.js production usage (Coko / Ketty / Kotahi / Louvre): https://coko.foundation/blog/, https://www.infodocket.com/2023/05/22/cokos-open-source-publishing-tools-flax-and-paged-js-power-the-creation-of-the-louvres-newest-catalogue-raisonne/
- Playwright in FastAPI gotchas: https://github.com/fastapi/fastapi/issues/5446, https://github.com/microsoft/playwright-python/issues/2097
- Vivliostyle CLI v10.1 / v10.5 (Apr 2026): https://github.com/vivliostyle/vivliostyle-cli and https://vivliostyle.org/blog/2025/12/21/vivliostyle-cli-v10.1.0-released-integrated-create-command/
- Typst 0.14 release "Now accessible" (Oct 2025): https://typst.app/blog/2025/typst-0.14/
- Typst automated PDF generation: https://typst.app/blog/2025/automated-generation/
- Typst Python binding: https://pypi.org/project/typst/ and https://github.com/messense/typst-py
- Typst color profile (sRGB default, ICC roadmap): https://github.com/typst/typst/issues/3143
- Typesetting engine benchmark (speedata 2026-02-10): https://news.speedata.de/2026/02/10/typesetting-benchmark/
- WeasyPrint vs Prince comparison: https://www.saashub.com/compare-weasyprint-vs-prince-xml, https://docraptor.com/prince-alternatives
- CSS Paged Media three-renderer comparison harness: https://github.com/CSS-Paged-Media/3renderers
