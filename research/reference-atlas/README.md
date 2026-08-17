# Richard reference atlas

## Status

Phase 0A is a measured reference-corpus map. It does not change the renderer, preprocessor, postprocessor, schema, prompts, or tests.

The unit of analysis is one physical A4 face. Four source files store interior pages as A3 landscape spreads, so each landscape PDF object is split into a left and right face before it is counted or classified.

The atlas contains:

- 6 source reports
- 84 PDF objects
- 120 physical A4 faces
- 120 unique face annotations
- 120 normalized thumbnails
- 6 contact sheets
- measured word capacity per face
- embedded font inventories where the PDF exposes fonts
- page role, anatomy, visual mechanism, evidence assets, cadence function, confidence, and uncertainty per face

The machine-readable source is [`reference-atlas.json`](reference-atlas.json). The compact human index is [`PAGE-BY-PAGE.md`](PAGE-BY-PAGE.md). The annotations are in [`atlas_annotations.tsv`](atlas_annotations.tsv). The build is reproducible with [`build_atlas.py`](build_atlas.py).

## Evidence labels

The atlas separates three levels of certainty:

- `high`: directly visible, counted, extracted, or repeated in the corpus.
- `inferred`: a likely design rationale or grid interpretation, not an authored rule supplied by Richard.
- `unknown`: impossible to establish from flattened PDFs alone.

Word counts are capacity measurements, not copy-quality scores. Embedded text is used when available. Direct high-resolution OCR is used for Apex and as a fallback when a face has an incomplete text layer. Review screenshots and charts can still produce imperfect OCR, so the per-role bands are better evidence than any single low-level word count.

## Corpus manifest

| Report | PDF objects | Physical faces | Measured words | Mean per face | Source form |
|---|---:|---:|---:|---:|---|
| Apex | 20 | 20 | 6,754 | 337.7 | 20 portrait objects, no extractable text or font layer |
| Buchagentur | 11 | 20 | 6,900 | 345.0 | cover, 9 A3 spreads, back page |
| Alexander Boss | 11 | 20 | 6,363 | 318.1 | cover, 9 A3 spreads, back page |
| Mein Werkzeugkoffer | 11 | 20 | 4,977 | 248.8 | cover, 9 A3 spreads, back page |
| Niklas Niemeyer | 20 | 20 | 5,134 | 256.7 | 20 portrait objects |
| Ärztepartner | 11 | 20 | 5,422 | 271.1 | cover, 9 A3 spreads, back page |
| **Corpus** | **84** | **120** | **35,550** | **296.2** | normalized to physical faces |

The corpus median is 304 words per face. Regular content faces, excluding covers, CTAs, trust walls, and the Apex brand breather, average 319.5 words and have a median of 313 words.

## Corrections to the existing project analysis

This pass does not simply endorse the old pattern-spike documents. It corrects several material errors.

### 1. The old corpus count is wrong

`research/pattern-spike/page-catalog.md` says the five non-Apex reports contain 101 pages. Their PDFs contain exactly 100 physical faces. With Apex, the total is exactly 120.

The error came from treating object pages and physical faces inconsistently. The atlas derives the count from live PDF geometry.

### 2. There is no universal font pairing

The older design grammar describes a universal sans-display and serif-body system. The embedded PDF fonts disprove that.

| Report | Measured embedded families | Observed typographic direction |
|---|---|---|
| Apex | Not extractable | Visually a serif-led editorial display with compact sans support, but exact fonts are unknown |
| Buchagentur | Instrument Sans, Merriweather 120pt, Inter | Serif display with sans body and interface support |
| Alexander Boss | Source Sans 3, Bebas Neue, Montserrat | Primarily all-sans, with condensed and heavy display accents |
| Mein Werkzeugkoffer | Elza, Lato | All-sans brand system with strong weight contrast |
| Niklas Niemeyer | Azo Sans, Minion Pro, Source Sans Pro, Rockwell Condensed, Acumin | Sans display with serif body and several controlled accent faces |
| Ärztepartner | Lato, Merriweather 120pt, Bebas Neue Pro, Source Sans 3 | Serif display with sans body and condensed display support |

What is stable is not a specific pairing. The stable rule is role separation: display, reading text, labels, and numeric accents remain legible and deliberately contrasted. The family choice is a brand axis.

### 3. The current report does not look text-heavy because Richard uses less text

The reference corpus is text-rich. Outlook faces have a median of 446 words, false-belief faces 418, summaries 366, theory faces 351, and objections 321.

The previously rendered Christopher report had about 1,942 OCR words across 17 faces, roughly 114 words per face. The reference corpus averages about 296 words per face. The reference reports therefore carry roughly 2.6 times as many words per face.

The real failure is not global text quantity. It is insufficient editorial transformation:

- too much copy remains one undifferentiated body mass
- too few claims are converted into numbered structures, comparisons, charts, timelines, or evidence rails
- weak composition makes even a smaller amount of text feel heavier
- visuals are added after the page decision instead of helping determine the page decision
- page capacity is not assigned by semantic role

Reducing copy indiscriminately would move the system further from the references. The required change is to structure, compress, and visualize the right parts while preserving enough substantive evidence.

### 4. Cadence is not mainly dark-page alternation

The corpus is predominantly light:

- Apex: 18 light faces, 2 dark faces
- Buchagentur: 18 light, 1 photo-led cover, 1 dark close
- Alexander Boss: 18 light, 2 photo-led bookends
- Mein Werkzeugkoffer: 18 light, 2 photo-led bookends
- Niklas Niemeyer: 14 light, 4 dark, 2 photo-led
- Ärztepartner: 20 light

Only Niklas uses frequent dark resets. The shared cadence is created by role, density, composition, proof, and mechanism changes. A global rule such as “insert a dark page every N faces” would be unsupported.

### 5. The dedicated trust page is not universal

Dedicated review or logo-wall faces appear in four of the six reports. Trust evidence is universal, but it can be embedded in About, case studies, client metrics, partner logos, or the close. The system needs a trust-proof capability, not a mandatory trust-proof page.

### 6. Apex is not a separate dark visual world

Apex is visually distinct, but only its cover and primary CTA are dark. Most interior faces are light with blue gradient punctuation. Its real difference is a cleaner modern-tech surface, blue data graphics, more gradient geometry, and a different case-study construction. Calling it a dark report obscures the actual system.

## The stable report grammar

All six reports contain exactly 20 physical faces and exactly three case studies. Their sequence is not identical, but the narrative contract is highly stable.

```text
Hook
  Cover

Frame and authority
  Outlook
  About

Diagnosis
  Status quo
  False beliefs

Evidence and explanation
  Case 1 -> theory
  Case 2 -> theory
  Case 3 -> theory

Method and conversion
  Mechanism or synthesis
  Summary
  Objections
  Collaboration
  Trust evidence
  Final CTA
```

The exact role counts across the 120 faces are:

| Role | Faces | Corpus behavior |
|---|---:|---|
| Cover | 6 | one per report |
| Outlook | 6 | one per report |
| About | 6 | one per report |
| Status quo | 11 | one to four per report |
| False beliefs | 10 | one or two per report |
| Case study | 18 | exactly three per report |
| Theory | 22 | two to four per report |
| Mechanism | 9 | present in all five Richard-editorial reports, not explicit in Apex |
| Summary | 6 | one per report |
| Objections | 6 | one per report |
| Collaboration | 7 | one per report, Apex uses two faces |
| Dedicated trust proof | 5 | zero to two per report |
| CTA | 7 | one final close per report, Apex has an additional CTA poster |
| Brand breather | 1 | Apex-only interstitial |

The strongest system-level invariants are:

1. 20 physical faces.
2. One cover, outlook, about, summary, objection section, collaboration section, and final CTA.
3. Exactly three case studies.
4. A case is followed or paired with a page that explains why the result generalizes.
5. Trust evidence appears somewhere, even when it does not receive its own page.
6. The close becomes progressively easier to scan and more action-oriented.
7. Each face has one dominant reading mechanism.

## Page-family atlas

### Cover

Observed variants:

- full-bleed contextual photo with overlaid promise
- professional portrait on a light editorial field
- portrait plus a compact data and contents rail

Required anatomy:

- audience or category signal
- report promise
- identity anchor
- one supporting proof or content preview

The cover is not a miniature body page. It compresses the report's value into one visual claim.

### Outlook

Outlook is the densest reliable prose family. Five reports use an editorial essay; Niklas uses a photo-backed essay. It frames the reader's situation and establishes stakes before credentials.

The page accepts 354 to 529 measured words in this corpus. It works because the body is divided into short sections, the headline has enough authority, and one secondary anchor breaks the reading field.

### About and authority

Every About face combines at least three of these:

- founder or team image
- company proposition
- credentials or history
- numeric proof
- rating
- known-client or media logos

About is not a biography template. It is an authority composition. The evidence mix varies by client.

### Diagnosis

The diagnosis act uses three composition families:

- recognition list or card grid
- economic magnitude model
- system-gap diagram or conceptual metaphor

Werkzeug expands diagnosis to four faces because its argument requires a spread-level labor-cost equation. That is a useful exception: page count follows argument complexity, not a fixed ST slot count.

### False beliefs

False-belief faces are the densest recurring family. They hold a median of 418 words and often contain five to eight items.

Variants include:

- navy cards with white text
- large coral numbers or circles
- plain numbered editorial rows
- a conceptual preface followed by the numbered page

The invariant is not card styling. It is repeated objection anatomy with fast entry points and concise rebuttals.

### Case study

There are exactly 18 case-study faces. Each report repeats one internal case geometry across all three cases.

Observed geometries:

- left evidence rail with photo, quote, QR, and URL
- right portrait or result rail
- embedded evidence without a full rail
- Apex evidence rail with blue stat accents

The universal proof bundle is:

- named or identifiable client
- specific starting condition
- intervention
- outcome
- human or product evidence
- quote or result metrics

QR and URL are common but not universal. A case page without a credible evidence bundle is structurally incomplete even if the CSS is attractive.

### Theory and mechanism

Theory pages explain why a case generalizes. They are not generic filler after case studies.

Observed mechanisms include:

- numbered insight stack
- before-after comparison
- bar or line chart
- process flow
- two-by-two matrix
- Venn diagram
- circular consequence loop
- conceptual illustration
- interface screenshot plus evaluation

Mechanism pages explain the offer's distinct delivery logic, usually in three to six ordered stages. The five Richard-editorial reports contain explicit mechanism pages. Apex distributes mechanism explanation across its theory and collaboration faces.

### Summary and objections

Summary is often text-rich. It can use a portrait, comparison chart, economic dashboard, or dark chapter reset. The following objection page narrows attention to four to eight blockers and gives each one a direct response.

These are different jobs. Summary consolidates belief. Objections remove friction.

### Collaboration

Collaboration uses five or six stages in every report. The stable anatomy is:

- ordered step
- step name
- concise outcome or commitment
- clear final result

Apex uses two faces because it gives each stage more explanatory copy. The other reports compress the same job into one face.

### Trust proof

Observed trust mechanisms:

- Trustpilot or rating header
- review screenshot wall
- client logo wall
- known-client strip
- partner and media logos
- case-study metrics and quotes

The proof mechanism must match the evidence actually available. A logo wall cannot be generated from generic marks, and a review wall cannot be synthesized from prose.

### CTA and breather

Final CTAs are materially lighter than content pages, with a median of 76 measured words. Observed closes use:

- full-bleed contextual photo
- solid brand-dark field
- light editorial statement with a dark URL bar
- light gradient field with a large URL

Apex alone inserts a near-empty brand breather before its last closing page. This is a one-off, not a required page type.

## Capacity map

The following bands are measured from the six references. Q1 and Q3 describe the middle 50 percent of observed faces.

| Role | Faces | Q1 | Median | Q3 | Observed range |
|---|---:|---:|---:|---:|---:|
| Cover | 6 | 129 | 140 | 151 | 127 to 170 |
| Outlook | 6 | 379 | 446 | 498 | 354 to 529 |
| About | 6 | 171 | 186 | 228 | 168 to 303 |
| Status quo | 11 | 250 | 319 | 410 | 172 to 521 |
| False beliefs | 10 | 328 | 418 | 453 | 218 to 547 |
| Case study | 18 | 252 | 283 | 300 | 211 to 380 |
| Theory | 22 | 268 | 351 | 408 | 45 to 464 |
| Mechanism | 9 | 206 | 265 | 314 | 194 to 368 |
| Summary | 6 | 241 | 366 | 423 | 224 to 450 |
| Objections | 6 | 275 | 321 | 352 | 179 to 370 |
| Collaboration | 7 | 258 | 305 | 349 | 239 to 388 |
| Trust proof | 5 | 86 | 383 | 626 | 63 to 645 |
| CTA | 7 | 46 | 76 | 102 | 35 to 209 |

Theory's low outlier is a chart-led face. Trust-proof OCR includes the words inside review screenshots, so its word count is evidence volume rather than reading-body volume.

Capacity must therefore be role-specific and composition-specific. A single “maximum words per page” is not a valid contract.

## Grid and spatial grammar

### Measured facts

- All reports resolve to A4 portrait faces.
- Four reports use A3 landscape objects for the nine interior spreads.
- Physical-face widths range from about 595 to 612 PDF points before spread splitting.
- Outer bleed and crop differences account for most size variation.
- Full-bleed imagery is concentrated at covers and closes.
- Interior pages reserve visible header and footer bands even when they do not carry running CTAs.

### High-confidence recurring geometry

- outer page margins are visually consistent inside each report
- cases use an asymmetrical narrative and evidence split
- numbered-card pages use repeated equal-width or equal-height modules
- charts occupy a deliberately reserved region instead of being inserted into leftover space
- spread designs coordinate facing pages, especially setup and result sequences
- display headlines can cross multiple text-column widths but do not collide with evidence rails

### Inferred ranges

The existing visual analysis estimates outer margins around 14 to 18 mm, inner spread gutters around 10 to 15 mm, and a case-study narrative-to-evidence split near two-thirds to one-third. One detailed Ärztepartner case face was estimated around 110 mm narrative, 5 to 7 mm gutter, and 65 mm evidence rail.

These values are useful hypotheses, not universal measurements. Exact per-page grids are not recoverable as named InDesign grids from flattened PDFs. They can be measured as object geometry, but that still does not reveal Richard's authored master-page logic.

## Cadence model

The common rhythm is semantic and compositional:

1. High-impact cover.
2. Dense framing essay.
3. Authority dashboard.
4. Recognition and diagnosis.
5. Dense belief correction.
6. Repeating proof and explanation pairs.
7. Ordered method.
8. Dense synthesis.
9. Objection removal.
10. Ordered collaboration.
11. Proof or brand pause.
12. Light final action.

Within the evidence act, the rhythm is especially stable:

```text
human proof -> explanatory mechanism -> human proof -> explanatory mechanism -> human proof -> explanatory mechanism
```

This alternates the kind of cognitive work the reader performs. It does not require alternating background colors.

## Asset evidence map

The reference corpus implies an asset bank with separate evidence classes.

### Identity assets

- primary and alternate logos
- brand colors
- actual brand fonts or licensed substitutes
- recurring brand ornaments
- paper, marble, or gradient surfaces where appropriate

### Human proof assets

- founder portraits
- team imagery
- case-client portraits or group photos
- professional contextual portraits

### Outcome proof assets

- client quotes
- result metrics
- product or book covers
- interface screenshots
- review screenshots
- client and partner logos
- source URLs and QR destinations

### Context assets

- worksite, clinic, office, product, or industry scenes
- diagrams that explain a real mechanism
- charts backed by report data

### Safe generated assets

- abstract backgrounds
- textures
- non-evidentiary conceptual illustrations
- decorative brand-compatible motifs

Generated imagery must never impersonate customer proof, credentials, reviews, product screenshots, or measured results.

The asset selector therefore needs two different behaviors:

- deterministic selection for proof and identity, where provenance and role are authoritative
- judgmental selection for contextual and decorative assets, where several valid compositions may exist

## What can now be authoritative

The evidence supports authoritative contracts for:

- 20-face report length as the default reference form
- three case studies
- narrative act ordering
- semantic page roles
- proof bundle requirements
- role-specific capacity bands
- final CTA lightness
- trust-evidence provenance
- within-report consistency of case-study geometry
- one dominant visual mechanism per face

The evidence does not support one authoritative visual skin, one font pairing, one case rail, one dark-page cadence, or one chart style.

## What remains unmapped

This atlas closes the page-count, page-role, composition-family, capacity, font-inventory, evidence, and cadence gaps for the six surviving PDFs. It does not manufacture information that the sources cannot provide.

Still unresolved:

- exact original master grids and baseline-grid settings
- exact point sizes, tracking values, and paragraph styles for every report
- original InDesign, Illustrator, and Affinity source files
- source-image provenance and licenses
- the decision logic Richard used when selecting one valid composition over another
- the lost copy-law Word document
- the missing Luka Martic and Frese reference PDFs
- the live deployed n8n workflow and prompt state
- behavior on several genuinely different new client packages
- an automated scorer calibrated against Richard's own judgment
- whether every current repository test expresses a current requirement

These are not all prerequisites for defining Phase 0B. The correct boundary is:

- treat measured semantic, evidence, and capacity rules as authoritative
- treat composition selection as constrained among observed families
- label typography and grid values as report-specific tokens or inferred ranges
- keep unknown provenance and live-workflow behavior blocked until the missing sources are recovered

## Inputs for Phase 0B

No system redesign should begin until Phase 0B uses this atlas to audit the current runtime against four explicit questions:

1. Can the schema express every observed page role and proof bundle?
2. Can the preprocessor choose a composition from semantics, capacity, evidence, and cadence?
3. Can the renderer execute every validated family without inventing missing proof?
4. Can the postprocessor detect overflow, weak hierarchy, missing evidence, broken cadence, and unsupported claims?

The atlas makes those questions testable. It does not answer them by assumption.

## Rebuild command

```bash
research/v7-renderer/.venv/bin/python research/reference-atlas/build_atlas.py
```

The build fails if any source PDF is missing, object counts change, annotations reference an unknown face, the corpus does not resolve to 120 faces, or a report does not resolve to 20 faces.
