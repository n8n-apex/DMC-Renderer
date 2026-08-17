# Research Task E — CSS Paged Media Feature Matrix for `dmc-renderer`

**Scope.** Concrete evidence on which CSS Paged Media features work in each candidate engine, at what fidelity, and where the landmines are. Phase-1 input for engine pick (Task A) and template authoring decisions. Versions evaluated: WeasyPrint 65–68 (latest stable Feb 2026), Paged.js latest + Chromium 125+, PrinceXML 15/16, Vivliostyle 2.30+, Typst 0.14+.

## 1 — Support matrix

Legend: ✅ full | ⚠️ partial (note caveat) | ❌ not supported | n/a not applicable

| # | Feature | WeasyPrint 68 | Paged.js + Chromium | Prince 15/16 | Vivliostyle 2.30+ | Typst 0.14 |
|---|---|---|---|---|---|---|
| 1 | `@page` rules (size, margins) | ✅ | ✅ | ✅ | ✅ | ✅ (Typst syntax, not CSS) |
| 2 | `@page :first` / `:left` / `:right` / `:blank` | ✅ | ✅ (`:blank` doesn't combine with named pages — workaround needed) | ✅ | ✅ (`:left`/`:right`/`:recto`/`:verso`) | ⚠️ via `set page` + context |
| 3 | Named pages (`page: cover`) | ⚠️ supported, but emits spurious blank page in some cases ([#1944](https://github.com/Kozea/WeasyPrint/issues/1944), [#1076](https://github.com/Kozea/WeasyPrint/issues/1076)); page groups unsupported | ✅ since 2019; `:nth()`+named combo unsupported | ✅ + Prince extensions (`:recto`, `:verso`) | ✅ since v2.7 (2021) | ❌ (no CSS-named-pages concept; emulate with regions) |
| 4 | `page-break-before/after/inside` (legacy) | ✅ | ✅ | ✅ | ✅ | ✅ (`pagebreak()`) |
| 5 | `break-before/after/inside` (modern) | ✅ | ✅ | ✅ | ✅ | n/a |
| 6 | Margin boxes `@top-*`, `@bottom-*`, `@left-*`, `@right-*` | ✅ all 16 boxes | ✅ all 16 boxes | ✅ all 16 boxes + `@prince-overlay` | ✅ | ⚠️ header/footer only via `header:`/`footer:`, no granular 16-box model |
| 7 | `string-set` + `content(string-name)` in margin boxes | ✅ | ✅ (named strings supported, some keywords pending merge) | ✅ | ✅ since v2.4 (2020) | ⚠️ counter/state primitives only; no GCPM-style strings |
| 8 | `target-counter(url(#id), page)` (cross-refs) | ✅ | ⚠️ only the `page` counter works; other counters unsupported per Paged.js docs | ✅ | ✅ in `content` property | ✅ (native page refs via `<ref>`) |
| 9 | `target-text(url(#id))` | ✅ | ⚠️ partial; `target-content` plugin variants exist | ✅ | ✅ | ⚠️ via Typst refs |
| 10 | `counter(page)` / `counter(pages)` | ✅ | ✅ | ✅ | ✅ | ✅ via `counter("page")` |
| 11 | `bookmark-level` / `bookmark-label` / `bookmark-state` (PDF outline) | ✅ (was `-weasy-` prefixed pre-v53; unprefixed now) | ❌ Paged.js renders DOM only — Chromium's PDF printer does NOT honour GCPM bookmarks; outline must be patched in post-process | ✅ + Prince-specific `prince-bookmark-*` extensions | ⚠️ outline auto-generated from `<h1..h6>` and ToC; bookmark-* CSS properties not honoured | ⚠️ auto-bookmarked from headings; `bookmarked: false` to suppress; outline depth has bugs in some PDF readers ([#5615](https://github.com/typst/typst/issues/5615)) |
| 12 | Footnote floats (`float: footnote`, `::footnote-call`, `::footnote-marker`) | ✅ since v54 (commercial-grade since v60) | ⚠️ works but `@footnote` only supports `float: bottom`; counter-reset interactions broken ([gitlab #313, #410](https://gitlab.coko.foundation/pagedjs/pagedjs/-/issues/410)); `footnote-display: compact` unsupported | ✅ richest implementation (custom symbols, sidenotes, multi-ref) | ⚠️ supported via GCPM; footnotes-in-tables historically broken, `footnote-policy` partial | ✅ native `footnote()` function |
| 13 | `hanging-punctuation: first allow-end last` | ❌ not in supported features list | ⚠️ inherits browser support — Chromium added partial support late 2024; Firefox unsupported (n/a here) | ❌ on Prince [roadmap](https://www.princexml.com/roadmap/), not shipped | ⚠️ open issue [#818](https://github.com/vivliostyle/vivliostyle.js/issues) for `allow-end` | n/a (no CSS concept) |
| 14 | `widows` / `orphans` | ✅ | ⚠️ inherited from Chromium; Firefox is buggy but Chromium is fine | ✅ | ✅ (bug fixed for multi-column) | ⚠️ no direct property; `par.linebreaks: "optimized"` is the workaround |
| 15 | `box-decoration-break: clone \| slice` | ⚠️ property accepted; backgrounds don't extend properly with `slice`; `clone` partial ([#771](https://github.com/Kozea/WeasyPrint/issues/771)) | ⚠️ Chromium accepts but page-break interactions are flaky | ✅ Prince 16 changed default from `clone` → `slice` (breaking) | ⚠️ inheritance bug [#603](https://github.com/vivliostyle/vivliostyle.js/issues/603) | n/a |
| 16 | CSS Grid in paged context | ⚠️ Grid layout supported since v62 but **a single grid does not fragment across pages** — column overflow is clipped ([#2076](https://github.com/Kozea/WeasyPrint/issues/2076), [#2397](https://github.com/Kozea/WeasyPrint/issues/2397)); v67 added row-page-breaks | ⚠️ Chromium Grid is full-fidelity for layout; `break-inside` on grid/flex items is ignored or buggy at page borders | ⚠️ Prince 16 added Grid, but **single-page only, no fragmentation** | ⚠️ browser-delegated; same fragmentation issue | n/a |
| 17 | CSS multi-column (`column-count`, `column-fill`) | ✅ + balanced column rules | ✅ Chromium-native | ✅ full | ✅ (widows/orphans bug recently fixed) | ✅ native columns |
| 18 | Inline `<svg>` rendering | ✅ rendered as vector | ✅ (Chromium) | ✅ | ✅ (browser-delegated) | ✅ |
| 19 | `@font-face` with subsetting | ✅ subsets via hb-subset (fast) or fontTools fallback; .ttf/.otf preferred, .woff2 supported | ✅ (subsetting via downstream Puppeteer print path) | ✅ subsets and embeds | ✅ | ✅ subsets natively |
| 20 | `size` (A4, `210mm 297mm`, landscape) | ✅ | ✅ | ✅ | ✅ | ✅ |
| 21 | Bleed (`bleed`, `marks: crop cross`) | ✅ `@page { bleed: 5mm; marks: crop; }` | ✅ via `@page` settings | ✅ rich (crop, registration, bleed boxes) | ✅ bleed + crop marks | ⚠️ via `page(bleed: ...)` syntax |
| 22 | JavaScript during render | ❌ none — pure Python | ✅ runs anything Chromium does (Paged.js itself IS JS-driven; you control DOM before pagination) | ⚠️ ES5 only, no strict mode, no `setInterval`, no `document.write`; events `onClick` never fire; disabled by default | ⚠️ static rendering only; no SPA / client-routing; SSR-rendered output expected | ❌ Typst is its own language, no JS |

## 2 — Per-engine summary

**WeasyPrint 68** (Python, AGPL/free). Cleanest free implementation of GCPM and Paged Media Module 3. Footnotes, bookmarks, target-counter, named pages, margin boxes, multi-column all production-ready. The two real gotchas are (a) CSS Grid does not fragment across pages — fine for cover, dashboard tiles, KPIs; not fine for a 50-row table laid out via Grid; and (b) no `hanging-punctuation`. No JS, so any "dynamic" computation must be done in Python before HTML generation. ([Features](https://doc.courtbouillon.org/weasyprint/stable/api_reference.html))

**Paged.js + headless Chromium** (Apache 2, JS). Polyfill that runs in a real browser, so flexbox/grid/transforms are first-class. But it is a polyfill — bookmarks, hanging-punctuation, target-counter (beyond `page`), and `:nth()`+named-page combos are partial or missing, and the underlying Chromium PDF printer doesn't honour GCPM bookmarks so you must emit the PDF outline post-hoc with `pdf-lib` / pypdf. Footnotes work but counter-reset edge cases bite. ([Supported features](https://pagedjs.org/en/documentation/14-supported-feature-of-the-w3c-specifications/))

**PrinceXML 15/16** (commercial, ~$3,800/server). The reference implementation for CSS print — strongest GCPM support, sidenotes, custom footnote symbols, recto/verso, bookmark-state, ES5 JS. Prince 16 (Feb 2025) added Grid (single-page) and variable fonts. No `hanging-punctuation` (roadmap). License cost is the only reason not to pick this. ([CSS props](https://www.princexml.com/doc/css-props/), [Prince 16 release](https://www.princexml.com/releases/16/))

**Vivliostyle 2.30+** (JS, AGPL/free). Two-layer architecture: GCPM/page logic in JS, layout delegated to Chromium. Strong on Japanese / vertical text, ruby, EPUB Adaptive Layout. Weaker on bookmarks (auto-derived from ToC, not from `bookmark-level`) and on `hanging-punctuation`. Static rendering only — no SPA / on-page JS. ([Supported features](https://docs.vivliostyle.org/supported-css-features.html))

**Typst 0.14** (Rust, MIT). Outstanding rendering quality and speed, but **does not accept HTML/CSS as input** — its HTML feature is an *export* target (experimental, "do not use for production" per [docs](https://typst.app/docs/reference/html/)). NLnet project to bridge HTML in/out has a June 2026 deadline. For this project — where templates are HTML — Typst is effectively disqualified unless we abandon the HTML/CSS authoring model.

## 3 — Critical caveats (gotchas that bite)

- **Bookmarks in Paged.js are a lie.** Paged.js implements `bookmark-level` against the DOM, but Chromium's `printToPDF` doesn't read those declarations — output PDFs have no outline. Every "Paged.js bookmarks work" tutorial silently uses a post-process step. If we go Paged.js, budget time for `pdf-lib`/pypdf outline injection.
- **CSS Grid does not paginate** in WeasyPrint or Prince. A grid that overflows page height is clipped, not fragmented. Use Grid for self-contained UI tiles (cover, KPI strip, info card) but NEVER for long-flowing content (case study list, chapter body). Use multi-column + block flow for those. ([WeasyPrint #2076](https://github.com/Kozea/WeasyPrint/issues/2076), [#2397](https://github.com/Kozea/WeasyPrint/issues/2397))
- **Named pages in WeasyPrint emit spurious blank pages** in some sequences ([#1944](https://github.com/Kozea/WeasyPrint/issues/1944), [#1076](https://github.com/Kozea/WeasyPrint/issues/1076)). Pattern that triggers: a named page set on the first child of a section directly after a `break-before: page`. Workaround: put `break-before` on the section, not the first inner block.
- **`hanging-punctuation` is broadly unsupported.** Only Safari has shipped it; Prince has it on the roadmap; WeasyPrint and Vivliostyle both lack it. If German typographic polish requires it, we have to live without (negligible for B2B reports) or fake the optical margin via a hard `padding-left` adjustment on quoted paragraphs.
- **`box-decoration-break` semantics changed in Prince 16** (default `clone` → `slice`). If we adopt Prince and our templates rely on cloned borders across page breaks, output regresses silently.
- **Paged.js `target-counter` only supports the `page` counter**, not custom counters. "See chapter N for details" cross-refs need either WeasyPrint or Prince.
- **Footnote counter resets are flaky in Paged.js** ([gitlab #313, #410](https://gitlab.coko.foundation/pagedjs/pagedjs/-/issues/410)). Per-page or per-chapter footnote numbering may glitch.
- **Typst HTML export is unidirectional and experimental.** Don't pick Typst unless we redesign authoring around `.typ` files.
- **`:blank` doesn't combine with named pages in Paged.js.** Workaround uses a class-selector trick; not all teams discover it.
- **WeasyPrint has no JavaScript.** Any string interpolation, conditional logic, or computed cross-reference must be done in Python pre-render.
- **Prince JS is ES5 only.** No arrow functions, no destructuring, no `setInterval`. Most modern bundler output won't run.

## 4 — Implications for `dmc-renderer`

**Features we can safely build into templates (free-engine baseline = WeasyPrint):**
- `@page` rules with named pages (`@page cover`, `@page chapter`, `@page case-study`)
- `:first` / `:left` / `:right` / `:blank` pseudo-classes
- Modern `break-before/after/inside`
- All 16 margin boxes for running headers/footers
- `string-set` + `content(name)` for chapter-title-in-header pattern
- `target-counter(... page)` for "siehe Seite N" cross-refs
- `counter(page)` / `counter(pages)` for "Seite N von M"
- `bookmark-level` + `bookmark-label` for PDF outline (Adobe-friendly)
- `float: footnote` for Quellen-Fußnoten
- Multi-column for the case-studies index
- `widows`/`orphans` for body text
- `@font-face` for the brand font (subsetting is automatic)
- `size: A4`, `bleed`, crop marks if print-shop output is needed
- CSS Grid **only inside fixed-height regions** (cover hero, KPI tiles, status box) — never on flowing content

**Features to avoid or work around:**
- `hanging-punctuation` — drop or simulate manually
- CSS Grid for any container that must paginate — use block flow + multi-column instead
- `box-decoration-break: clone` for boxes that cross page breaks — test rendered output, set borders/backgrounds defensively
- Custom `target-counter(... chapter)` — only `page` is portable; use `target-text` or string-set for chapter labels
- JS-driven content adjustments — push all logic to the Python layer
- Named page on a first-child element after `break-before` — move break onto the wrapper

**If we go Paged.js instead** (because of design polish / Chromium parity):
- Plan for a post-process outline-injection step (`pypdf`, `pikepdf`, or `pdf-lib` via Node)
- Avoid custom-named `target-counter`; use the `page` counter only
- Test `:nth()` + named-page combinations defensively
- Accept that footnote counter-resets may need manual workarounds

**If we go Prince** (commercial budget exists):
- Almost everything Just Works; the question is licence cost vs. open-source ergonomics
- Watch the v16 `box-decoration-break` default change when upgrading
- ES5-only JS limits any in-template scripting; do logic Python-side anyway

**Engine drop list (in order of confidence to deprioritise):**
1. **Typst** — wrong input format for this project (HTML templates).
2. **Vivliostyle** — fine engine, but no clear advantage over Paged.js for our use case, weaker bookmarks story, smaller community.
3. **Paged.js** — viable but adds Node + Chromium to the runtime and forces post-process outline work.
4. **Prince** — best fidelity, gated by ~$3,800/server licence.
5. **WeasyPrint** — Phase-1 winner on cost + Paged-Media coverage + Python-native fit.

## 5 — Three-sentence summary

(a) **PrinceXML wins on raw Paged-Media support** (richest GCPM implementation, custom footnote symbols, sidenotes, recto/verso, ES5 JS), with **WeasyPrint 68 a very close second** for any free / Python-native stack — the gap matters only if we need hanging-punctuation, sidenotes, or grid that paginates. (b) **The biggest gotcha across all engines is CSS Grid in paginated content**: it works for fixed-height tiles but is silently clipped (Prince, WeasyPrint) or breaks at page boundaries (Paged.js) when content overflows — never use Grid for flowing content, only multi-column + block flow. (c) **If we go free-engine (WeasyPrint), we must drop `hanging-punctuation` and any JavaScript-in-template logic**, and we must keep CSS Grid out of the body-flowing chapter content (Grid is fine for the cover and KPI tiles only).

## Sources

- [WeasyPrint 68.1 API Reference & supported features](https://doc.courtbouillon.org/weasyprint/stable/api_reference.html)
- [WeasyPrint changelog](https://doc.courtbouillon.org/weasyprint/stable/changelog.html)
- [WeasyPrint issue #771 — box-decoration-break](https://github.com/Kozea/WeasyPrint/issues/771)
- [WeasyPrint issue #1944 — named pages force page break](https://github.com/Kozea/WeasyPrint/issues/1944)
- [WeasyPrint issue #2076 — page breaks on grid/flex items](https://github.com/Kozea/WeasyPrint/issues/2076)
- [WeasyPrint issue #2397 — allow fragmentation in grid rows](https://github.com/Kozea/WeasyPrint/issues/2397)
- [Paged.js — Supported features of W3C specifications](https://pagedjs.org/en/documentation/14-supported-feature-of-the-w3c-specifications/)
- [Paged.js — Named pages](https://pagedjs.org/en/documentation/8-named-page/)
- [Paged.js — Cross References](https://pagedjs.org/en/documentation/-cross-references/)
- [Paged.js footnotes issue #410 (counter reset)](https://gitlab.coko.foundation/pagedjs/pagedjs/-/issues/410)
- [PrinceXML CSS properties](https://www.princexml.com/doc/css-props/)
- [PrinceXML Paged Media](https://www.princexml.com/doc/paged/)
- [PrinceXML 15 cookbook](https://www.princexml.com/doc/15/cookbook/)
- [PrinceXML 16 release notes](https://www.princexml.com/releases/16/)
- [PrinceXML roadmap (hanging-punctuation pending)](https://www.princexml.com/roadmap/)
- [Vivliostyle supported CSS features](https://docs.vivliostyle.org/supported-css-features.html)
- [Vivliostyle.js CHANGELOG](https://github.com/vivliostyle/vivliostyle.js/blob/master/CHANGELOG.md)
- [Vivliostyle issue #603 — box-decoration-break inheritance](https://github.com/vivliostyle/vivliostyle.js/issues/603)
- [Typst HTML export documentation](https://typst.app/docs/reference/html/)
- [Typst bookmark depth issue #5615](https://github.com/typst/typst/issues/5615)
- [NLnet Typst-HTML project (due June 2026)](https://nlnet.nl/project/Typst-HTML/)
- [print-css.rocks tools index](https://print-css.rocks/tools)
- [PrintCSS footnotes article](https://printcss.net/articles/footnotes)
- [W3C CSS Generated Content for Paged Media Module](https://www.w3.org/TR/css-gcpm-3/)
- [W3C CSS Paged Media Module Level 3](https://www.w3.org/TR/css-page-3/)
