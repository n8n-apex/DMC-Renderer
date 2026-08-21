================================================================================
GRAMMAR STATUS: DRAFT — NOT RATIFIED. Chassis MUST refuse to load while
                RATIFIED-BY is blank. (R9/F1 trust-boundary gate.)
SOURCE:         (1) 64 reference pages, 5 clients, read byte-by-byte
                2026-05-17; palette pixel-extracted via k-means.
                (2) Richard's own LIVE spec documents (5 files in
                `files from richard/`, see SOURCE-DOCS below) — these
                are PRIMARY where they speak.
LAYER A FROM:   research/pattern-spike/ (structural clustering) +
                Richard's `01_DMC_Master_System_v1.md` (slot plan,
                ST types, sequence rules) — Richard governs where he
                speaks; pattern-spike fills structural gaps he doesn't.
LAYER B FROM:   pixel extraction (work/sweep/colors.txt, accents.txt,
                notes.md) — colour/treatment values, per-client.
                Richard's `08_DMC_Design_System_v2.md` and
                `DMC_InDesign_Spec_v1.md` provide governing rules
                (3-colour cap, font defaults, body color, etc).
SUPERSEDES:     research/idml-spike/skills/richard-design-system/SKILL.md
                — RETIRED in full. Leave on disk, marked DEAD (first
                line); do NOT overwrite. Chassis repointed here as a
                deliberate, reviewed change.
RATIFIED-BY:    Utkarsh 2026-05-23
SOURCE-DOCS:    The 5 LIVE Richard documents this grammar binds to:
                - `01_DMC_Master_System_v1.md`    (Master rules / slot plan)
                - `08_DMC_Design_System_v2.md`    (Design philosophy + v1 corrections)
                - `DMC_InDesign_Spec_v1.md`       (LIVE per GATE-1 ruling:
                                                   only version exists; v2
                                                   cites it as authoritative;
                                                   rule is successor-existence,
                                                   not filename-version match)
                - `04_DMC_Copy_Masterbook_v3.md`  (Copy mechanics — reference)
                - `05_DMC_Intelligence_Layer_v4.md` (Copy intelligence — reference)
                Governance order where two LIVE docs disagree:
                v2 Design System > InDesign Spec (v2 is philosophy doc the
                spec implements). All other pairs subject-matter-disjoint.
                v1/Old* (any doc WITH a successor on disk): DEAD. Cite a
                LIVE-doc line or drop the rule.
MATRIX REF:     docs/superpowers/plans/2026-05-16-grammar-contract-
                reconciliation-matrix.md — 2026-05-18 RICHARD-PRIMARY
                RE-RATIFICATION block reflected throughout this grammar
                (A2/B2/C1/D1/D2 strikes folded in; A1/B3 HELD).
GAP-REPORT REF: 2026-05-17-grammar-gap-report.md (rev.A) — read alongside.
================================================================================


## §0  HOW TO READ THIS GRAMMAR (the one idea that fixes the overfit)

Richard's reports are TWO independent layers. The dead skill fused them
and froze ONE client's instance as universal law; that is why the GEVA
render was weak. This grammar keeps them apart on purpose:

- LAYER A — STRUCTURE. Treatment-free page architectures, the report-
  level narrative, and the slot plan. These recur across ALL five
  clients AND are codified in Richard's Master System. §2, §3.
- LAYER B — BRAND TREATMENT. Palette, accent (per-client value — NOT a
  fixed colour name), mechanic, type, ground, texture, photo mode.
  PER-CLIENT, varies on nearly every axis. §4.

A rendered page = (a Layer-A pattern) × (a client's Layer-B profile).
Neither half is the grammar alone. The renderer composes them.

CRITICAL DECONTAMINATION RULE (Layer-B accent is a VALUE, not a NAME):
  The word "coral" is one literal hex value in ONE client's profile
  (GEVA's `brand_accent`). It is NOT a concept, a validator name, a
  class name, a CSS class, a function name, a config key, or a chassis
  symbol. Renderer logic refers to `accent` (the per-client profile
  field); the hex it resolves to is whatever that profile supplies —
  coral for GEVA, gold for aerz/nikl, tan for alex, tonal-teal for buch.
  See §4 for profiles, §5 for binding, §9 for change discipline.

§0.1  RICHARD'S RULE TIERS (his framework, applied throughout this grammar)

Richard's docs (and his own message) name three tiers:

  HARD       — input gates, FIXED slots, absolute Verbote. Source:
               `01_DMC_Master_System_v1.md` ("HART, keine Ausnahmen",
               "PFLICHT", "WARNUNG", "FIXED"); `08_v2` print-spec H.1.
               The renderer rejects on violation.
  SOFT       — tolerance ranges, derived from content / character
               limits. Source: `08_v2` "Maße ergeben sich aus
               Zeichenlimits" (L15-16); InDesign Spec font-size ranges.
               The renderer warns / allows within range.
  VARIATION  — "designer's eye", per-brand / per-page. Source: `08_v2`
               B.2 customer-font intake; per-client palette; brand-
               variant body section ordering. The renderer reads the
               profile, no global rule.

Each rule below is tagged [HARD] / [SOFT] / [VARIATION].

§0.2  NON-NEGOTIABLE RULES FOR ANYONE EXTENDING THIS FILE
  - Every new claim cites the exact source: a LIVE Richard doc
    (preferred) OR a reference page from the corpus sweep.
  - A claim seen in only one client is tagged [SINGLE-CLIENT:xxx] and
    is NOT promoted to universal until seen in ≥2 clients in bytes OR
    explicitly named in a Richard doc.
  - The Layer-B schema must have a SLOT for every axis the bytes
    exhibit BEFORE a value is recorded. Bigger corpus without this →
    bigger overfit.
  - Hex values from pixel extraction are approximate (JPEG/PNG, screen
    not press). Correct in RELATION and ROLE; press CMYK is a colorist
    task at output commit. Do not treat as final.
  - This grammar is the visual/structural contract. It does NOT
    redefine the API ST contract. Where reality and the contract
    disagree, that is a MATRIX decision, flagged here, not resolved.
  - Coral as a chassis-logic concept is REMOVED. If you find yourself
    writing "coral" anywhere except a literal value in GEVA's profile
    row (§4.1) or a worked example, you are recontaminating. Stop.

§0.3  WHAT WAS READ (auditable; ratifier re-checks against these)
  Visual corpus: GEVA 1–11.jpeg (decoded from
  DMCReport_Mein_Werkzeugkoffer.pdf); aerz p01–p11; nikl p01–p20;
  alex p01–p11; buch p01–p11. = 64 pages, 100%. Palette in
  work/sweep/colors.txt + accents.txt; sweep in work/sweep/notes.md.
  Richard docs: the 5 LIVE files in SOURCE-DOCS, full reads
  (TASK-0 coverage on the matrix's 2026-05-18 block).

§0.4  CORRECTIONS APPLIED TO pattern-spike LAYER A BEFORE ADOPTION
  (pattern-spike structure is sound; these are the byte-grounded fixes.)
  C-A  pattern-spike "always cream + marble texture; pure-black/pure-
       white NEVER" (design-grammar §6 #11/#12) is OVERSTATED. Bytes:
       nikl uses near-black grounds; alex uses light + slate bands;
       buch uses deep-teal full-bleed. Demote to: cream+texture is
       GEVA/aerz default ONLY; ground-mode is a Layer-B axis (§4 G).
  C-B  pattern-spike P-5/P-6 brand-variant LABELS are colour-tainted
       (it has no gold/serif/tonal code). Keep the STRUCTURAL clusters
       (P-1…P-12); Layer B (§4) supplies colour/type.
  C-C  pattern-spike's ST-23 Trust-Proof proposal is byte-supported.
       Documented here as pattern P-11; NOT bound to an ST — that
       contract change is a MATRIX decision (§5).
  C-D  Horizontal/branching process-flow with connector arrows is a
       real recurring system pattern-spike under-names; promoted here
       to first-class P-13.


## §1  THE REPORT (narrative spine — Layer A)

Richard's `01_DMC_Master_System_v1.md` Modul 9.1 defines the canonical
20-page slot plan; the corpus sweep confirms it across 5 clients with
expected per-client substitutions. The order is HARD; the per-act
PATTERN is HARD; the TREATMENT is VARIATION (Layer B).

### §1.1  THE 7-ACT SPINE  [HARD]
  1 HOOK         Cover                       P-1   (aerz cover = P-1a)
  2 FRAME        Outlook                     P-2   (nikl = P-2a)
  3 CREDENTIALS  About                       P-3   (universal, 5/5)
  4 DIAGNOSIS    Status-Quo + False-Belief   P-4 + P-5
  5 EVIDENCE     3× Case-Study + Theory      P-6 (+ P-7 paired)
  6 METHOD       Mechanism                   P-8
  7 CONVERSION   Fazit → Collab → Trust → CTA  P-9 → P-10 → P-11 → P-12

### §1.2  THE 20-PAGE SLOT PLAN  [HARD]
Verbatim from `01_DMC_Master_System_v1.md` Modul 9.1:

  S1   ST-01 — Cover                                       (FIXED)
  S2   ST-02 — Ausblick/Editorial                          (FIXED)
       (ODER: ST-04 Innenklappe auf S2, ST-02 auf S3)
  S3   ST-05 — Autorität/Über-Uns                          (ANCHOR)
  S4   VARIABLE — aus PROBLEM-Gruppe (ST-09 bis ST-13)
  S5   VARIABLE — aus PROBLEM oder DENKFEHLER-Gruppe
  S6   VARIABLE — aus DENKFEHLER-Gruppe (ST-14 bis ST-18)
  S7   VARIABLE — aus DENKFEHLER oder ÜBERGANG-Gruppe
  S8   ST-06 — Mechanismus-Einführung                      (ANCHOR)
  S9   VARIABLE — aus MECHANISMUS-Gruppe (ST-19 bis ST-22)
       (ODER ST-37 Soft-CTA-Zwischenseite)
  S10  ST-07A — Fallstudie #1                              (ANCHOR/PROOF)
  S11  ST-07B — Gegenseite zu FS1                          (PROOF) —
       eigenständige Vertiefung
  S12  ST-07A — Fallstudie #2                              (ANCHOR/PROOF)
  S13  ST-07B — Gegenseite zu FS2 (oder VARIABLE aus PROOF)
  S14  VARIABLE — Fallstudie #3 (ST-07A) ODER
       PROOF-Sonderformat (ST-23–ST-27)
  S15  VARIABLE — Gegenseite zu FS3 ODER PROOF ODER SPECIAL
  S16  VARIABLE — aus PROOF oder TRUST-Gruppe
  S17  ST-05-Variante / ST-31 — Kompetenz & Trust          (ANCHOR)
  S18  ANCHOR — Einladungs-Seite / Zusammenarbeit (ST-22 oder ST-37)
  S19  ST-08 — FAQ / Einwandvorwegnahme                    (ANCHOR)
  S20  ST-03 — Rückseite/Hard-CTA                          (FIXED)

CTA-Kadenz [HARD]: S2 (Soft im Ausblick), S9 (Mid nach Mechanismus),
S18 (Mid Einladung), S20 (Hard).

Page-count [HARD]: 16 / 20 / 24 / 28 only (Druckbögen — divisible by 4).
Citation: `01_DMC_Master_System_v1.md` chunk 2 L856-857; also
`DMC_InDesign_Spec_v1.md` L17.

### §1.3  BUILD ORDER (committed scope = all 37 STs; this phase = ~13)
Decision (user, 2026-05-18): all 37 STs are scope; one full 20-page
GEVA-equivalent rendering strong end-to-end is the phase-1 "done"
target; remaining ~24 are additive on a proven chassis.

Build set for this phase (derived FROM the slot plan above):
  FIXED+ANCHOR (8): ST-01, ST-02, ST-03, ST-05, ST-06, ST-07A, ST-07B,
                    ST-08.
  STRONG VARIABLE picks (5): ST-09 (PROBLEM-Gruppe S4-S5),
                              ST-14 (DENKFEHLER-Gruppe S6-S7),
                              ST-22 (Zusammenarbeit / Prozessablauf),
                              ST-31 (Kompetenz-Cluster at S17),
                              ST-32 (Atemseite, interspersed every 5-7 pp).
  = 13 patterns. The other 24 ST types (ST-04, ST-07C, ST-10–13,
  ST-15–18, ST-19–21, ST-23–28, ST-29–30, ST-33–37) are NOT stubbed
  this phase. Build them after the 13-set produces a strong full report.

NOTE on ST-32: GATE-4 flagged that ST-32 is VARIABLE (not FIXED) per
the slot plan above (it appears as "Atemseite interspersed every 5-7
pages", not assigned to a specific S-number). Treated as VARIABLE in
the count but built in this phase because rhythm-validation needs it.

### §1.4  INVARIANTS verified in bytes (do NOT parameterise away)
  - Exactly THREE case studies per report, every client. (aerz p05-07,
    nikl p08/10/12, alex p05-07, buch p05-07, GEVA 6-8.) Strongest
    structural commitment in the corpus.
  - One cover, one back-cover CTA, one collaboration page, every report.
  - A report picks ONE case-study geometry and uses it for all 3
    (anti-pattern §6 #15). Verified: GEVA LRP×3, aerz RRW×3,
    nikl rail×3, alex band×3, buch NR×3.
  - SPREAD vs SINGLE-PAGE is a Layer-B axis (§4 axis S). aerz/GEVA/
    alex/buch are 2-page spreads; nikl is 20 single pages. Same
    patterns, different page unit.

### §1.5  DOUBLESPREAD COUNT [SOFT] (GATE-4 correction to prior claim)
Prior session claim "5 mandated doublespreads" was WRONG. Bytes:
`08_DMC_Design_System_v2.md` D.3 L202 (verbatim):
  "Zwei Doppelseiten pro 20-Seiten-Report (als Richtwert). Das sind
   keine Fallstudien-Doppelseiten, sondern thematisch zusammengehörende
   Spreads."
AND L209-210 (verbatim):
  "Die Fallstudie steht auf einer Einzelseite. Die gegenüberliegende
   Seite ist eine eigenständige Seite die das Warum des Ergebnisses
   erklärt — ohne Rückbezug auf die Fallstudie."
Real count: ~2 THEMATIC doublespreads per 20-page report (typically
Mechanism+Diagramm, Numbers+Kompetenz). Case studies (ST-07A) stay
SINGLE-PAGE; their facing Gegenseite (ST-07B) is an INDEPENDENT page,
not a design-unit doublespread. The "60% empty GEVA case study" is a
value/grammar problem on the single page, not a missing spread half.


## §2  LAYER-A PATTERN LIBRARY (treatment-free; Layer B fills it)

Each pattern: structural skeleton + byte evidence + Layer-B variation
slots. Strength per pattern-catalog, re-verified this sweep.

P-1  FULL-BLEED PHOTO COVER  — STRONG, 4/5
  Skeleton: photo dominates page; brand wordmark top-corner; large
  display headline; "INKLUSIVE/DU LERNST" info panel or column;
  benefit/teaser list w/ checks; author/founder name; optional cover
  stat block.
  Bytes: GEVA 1.jpeg, nikl p01, alex p01, buch p01.
  Archetypes (Layer-B):
    C-A photo + translucent dark overlay panel (GEVA 1.jpeg)
    C-B photo + text directly on darkened photo + stat block (nikl p01)
    C-C photo + overlaid multi-box info COLUMN (alex p01)
    C-E cutout figure on saturated/solid ground + symmetric 3-zone
        list, no photo bleed (buch p01)
  P-1a PORTRAIT/CUTOUT COVER — [SINGLE-CLIENT:aerz] aerz p01: cutout
       figure on light textured ground + dark learn-box + dark cover-
       FOOTER case-study band (P-14). Restrained archetype.

P-2  BODY OUTLOOK  — STRONG, 4/5
  Skeleton: big display headline; 2–3 body sections; "Zielgruppe des
  Reports" list; quiet, image-light; photo (if any) lives on facing
  About page.
  Bytes: aerz p02L, GEVA 2.jpeg(L), alex p02L, buch p02L.
  P-2a PHOTO-BLEED OUTLOOK — [SINGLE-CLIENT:nikl] nikl p02: full-bleed
       photo ground, white text. Editorial-hook variant.

P-3  AUTHOR BIO + CREDIBILITY STRIP  — UNIVERSAL, 5/5
  Skeleton: founder/team photo (rect or cutout); dark-fill author
  callout box w/ 5–8 ✓ credentials; "Über [brand]" section; credibility
  strip = rating widget AND/OR "Bekannt aus" logo row; optional inline
  stat grid.
  Bytes: aerz p02R, GEVA 2.jpeg(R), alex p02R/p03(widget), buch p02R,
  nikl p03. Rating PROVIDER is Layer B (axis RW).

P-4  NUMBERED SCENARIOS / STATUS-QUO  — STRONG, 5/5
  Skeleton: 5–8 numbered items, each = number + short title + brief
  body; vertical stack or 2-col; intro question headline.
  Bytes: GEVA 3.jpeg, aerz p03L, alex p03L, buch p03L, nikl p04.
  Structural sub-forms (Layer B):
    - separate cards in a grid (nikl p04 6-up alternating fills)
    - one big box containing the numbered list (aerz p03L)
    - timeline w/ vertical connector spine + bleed photo (GEVA 3.jpeg)
    - hero full-bleed-photo + 5UP stat equation (GEVA 4.jpeg variant)
  P-4 and P-5 are the same numbered-list family in two rhetorical
  roles (situations vs misconceptions); visual treatment set is shared.

P-5  NUMBERED BELIEFS / DENKFEHLER  — UNIVERSAL, 5/5
  Skeleton: 5–8 items, each = number + quoted false belief + rebuttal.
  Bytes: aerz p04R/p05R, GEVA 5.jpeg(R), alex p03R, buch p04L,
  nikl p06/p17.
  FOUR structural treatments — selection is Layer B (axis N):
    A dark-fill callout boxes, label inside       (aerz, alex)
    B big numeral + ghost-outline number / glyph  (GEVA 5.jpeg)
    C big numeral + vertical connector-tick spine (nikl p06)
    D plain numbered, no card fill                (buch p04L)
    (nikl p17 = solid-square-number variant of A.)

P-6  CASE STUDY  — UNIVERSAL, 5/5, exactly 3 per report
  Skeleton (treatment-free): case-number/kicker · client name+tagline ·
  Ausgangssituation · Ziel · Lösung · Ergebnis · attribution · founder/
  team photo · QR + URL · pull-quote · (optional) result metric strip.
  Geometry is ONE per report (Layer-B axis CG):
    RRW  right portrait rail + body left   — aerz p05-07, nikl p08/10/12
    LRP  left photo+stamp+pullquote rail, body right — GEVA 6-8
    NR   no rail, photo embedded in flowing body — buch p05-07
    BAND full-width header band + body + framed photo — alex p05-07
    (nikl rail carries a GIANT GHOSTED SECTION NUMBER 01/02/03 —
     VERIFIED nikl p08/p10/p12; the ghost element is P-15.)
  CASE STUDY IS A SINGLE PAGE per `08_v2` L209-210 (§1.5 above).
  Facing Gegenseite (ST-07B) is an INDEPENDENT page, NOT a doublespread
  half. Prior-session "case study is a spread" claim REVERSED. The 60%-
  empty GEVA render is a value/grammar problem on the single page, not
  a missing right half. (Resolves matrix 2026-05-18 §5 flag.)

P-7  THEORY (paired with each case study)  — VARIANT-HEAVY
  Slot, not one shape. Sub-forms (Layer B axis T):
    P-7a numbered insight rows/cards   aerz p05R/p07R, alex p05R/p06R
    P-7b chart/diagram body            buch p05R/p08, alex p04L, GEVA 6R
    P-7c side-by-side / before-after   nikl p09/p11/p13
    P-7d 2-axis matrix                 GEVA 6.jpeg(R) Schaden×Sichtbarkeit
  Theory page faces each case study; in spread-clients it's the
  facing page, in nikl it alternates. Independent of the case page
  content per `08_v2` L209-210 (no Rückbezug — Master System Modul 8
  ST-07B Verbote also forbid this).

P-8  MECHANISM — NUMBERED STAGES  — UNIVERSAL, 5/5
  Skeleton: 3–6 numbered stages, each = numeral + title + body; card
  or connector-spine arrangement; often paired w/ photo or icons; ends
  bridging to CTA.
  Bytes: GEVA 9.jpeg, aerz p07R, alex p04R/p08L, buch p07R/p09L,
  nikl p14-15. Card-count, fill, icon-presence, arrangement = Layer B.
  Mechanism MUST come before first case study (Master System sequence
  rule, also §1.2 slot plan).

P-9  FAZIT  — STRONG, 5/5
  Skeleton: closing-argument body; ONE visual punctuation (chart /
  ✓-bullets / numbered objections / before-after); CTA-adjacent.
  Bytes: GEVA 10.jpeg(L), aerz p09, alex p09L, buch p08R/p09R.
  P-9a DARK CHAPTER-DIVIDER FAZIT — [SINGLE-CLIENT:nikl] nikl p05/p16:
       full-bleed dark photo, two-tone headline, CTA band.

P-10 COLLABORATION — NUMBERED SCHRITT  — UNIVERSAL, 5/5
  Skeleton: "So läuft die Zusammenarbeit (ab)" / "Ablauf der
  Zusammenarbeit" title; 5–6 "Schritt N" units (title + body +
  optional duration); QR + URL CTA.
  Bytes: GEVA 10.jpeg(R), aerz p10L, alex p09R, buch p10L, nikl p18.

P-11 TRUST PROOF — REVIEWS + LOGO WALL  — STRONG, 4/5 dedicated
  Skeleton: rating widget (score + stars + count) AND/OR client logo
  wall; review-card grid.
  Bytes: aerz p10R, alex p10(both), buch p10R, nikl p19(logo wall).
  >>NOT BOUND TO AN ST<< — proposed ST-23 / ST-31 mapping is a MATRIX
  decision (§5). The pattern exists in the bytes; the contract has no
  current ST for it.

P-12 CTA — DARK GROUND + ACCENT URL  — STRONG, 4/5
  Skeleton: dark ground (photo-bleed OR solid); white/near-white short
  headline; the URL is the largest type on the page IN THE ACCENT
  COLOUR (whatever the client's accent is — §4); optional QR; optional
  founder line.
  Bytes: GEVA 11.jpeg(gold url), buch p11(tonal-teal url, solid),
  nikl p20(gold url, solid+QR), alex p11(photo-bleed, slate band).
  P-12a CREAM CTA — [SINGLE-CLIENT:aerz] aerz p11: LIGHT ground,
        serif navy headline, navy band + gold URL.

P-13 PROCESS-FLOW WITH CONNECTORS  — STRONG (cross-client)
  Two structural forms:
    horizontal chain: boxed/pill steps left→right joined by arrows,
      may wrap (buch p05R; aerz p08R curved arrows; alex p04L chevron;
      GEVA 7-ish compare)
    vertical/branching: numbered pills down a curved connector spine,
      branching to outcome pills (alex p05R 1–6; alex p07R Engpass→…→
      Geldverlust w/ branch)
  Appears inside P-7/P-8 slots. Arrow style/colour = Layer B.

P-14 COVER-FOOTER CASE BAND  — [SINGLE-CLIENT:aerz] aerz p01: cover
  ends in a dark band of 2–3 mini case columns w/ rules. Weaker
  analogues elsewhere. Keep as a cover sub-element.

P-15 OVERSIZED GHOST BACKGROUND ELEMENT  — STRONG (multi-client)
  Huge low-opacity tone-on-tone element behind content. Variants:
    NUMBER — nikl case-rail "01/02/03" (p08/10/12) VERIFIED;
             nikl p06 giant ghost "7" in headline band.
    QUOTE-GLYPH — GEVA 2/7.jpeg „ ; nikl p09/11/13 grey „ on dark.
    ICON — nikl p07 ghost shield+check.
  Parametrise as {number|glyph|icon}; tone = Layer B.

REPEATING-SPREAD SKELETON [SINGLE-CLIENT:nikl]: nikl p09/p11/p13 repeat
  [near-black testimonial + ghost glyph + device mockup] → [accent
  transition strip] → [white two-tone headline + 2-col body + data].
  nikl-specific report rhythm.


## §3  LAYER-A COMPOSITION RULES (treatment-free; all clients)

### §3.1  DENSITY VARIES BY ROLE  [SOFT]
Outlook/About/CTA breathe. Status-Quo/Beliefs are dense numbered grids.
Case/Mechanism medium. Fazit medium-dense. Encode per-pattern density,
not one global grid.

### §3.2  BOOKEND GRAVITY  [SOFT]
Cover + closing CTA carry the heaviest visual weight (photo or
saturated ground). Interior body quieter.

### §3.3  ONE PUNCTUATION PER SPREAD/PAGE  [SOFT]
A single bright/contrasting callout interrupts the body rhythm — GEVA's
accent "Fakt ist:" box, aerz's navy box, buch's teal band. EXACTLY ONE
is the norm.

### §3.4  WHITESPACE ≥20% PER PAGE  [HARD]
Citation: `08_DMC_Design_System_v2.md` D.1 L180 (verbatim):
  "Mindestens 20% jeder Seite ist frei — kein Text, kein Bild, keine
   Grafik."
Validator: raster-check empty pixel ratio ≥20% per page.

### §3.5  COLOR DISCIPLINE  [HARD]
Citation: `08_v2` C.2 L156 (verbatim):
  "Pro Report maximal 3 Designfarben plus Neutral-Weiß/Grau."
≤3 distinct design colours across the entire report (primary + accent
+ neutral). Validator: distinct-hue-cluster count ≤3.

### §3.6  ACCENT BUDGET PER PAGE  [HARD] (replaces all "coral" rules)
Citation: `08_v2` C.2 L162 (verbatim):
  "Akzentfarbe → Highlights, Zahlen, Icons, sparsam eingesetzt
   (max. 10% Flächenanteil pro Seite)"
AREA-based: ≤10% page surface in the client's accent colour, per page.
Validator: rasterize each page, compute pixel ratio matching the
client's `brand_accent` (±ΔE 10), assert ≤10% per page.
NOT count-based. NOT named after coral. The validator validates the
client's accent VALUE — coral for GEVA, gold for aerz/nikl, tan for
alex, tonal-teal for buch.

### §3.7  ACCENT FIRING LOCATIONS  [HARD] (allowed-list, hue-agnostic)
The accent (whatever hue per profile) is allowed at these locations
only:
  - kickers / FALLSTUDIE stamp
  - panel fills (CTA panels, callout panels)
  - oversized quote glyphs (P-15)
  - URLs in CTA contexts
  - inline data emphasis (stat numbers, percent change)
  - icons (line-icons, check-circles per client)
  - attribution labels in pullquotes
Validator: classify each accent-pixel cluster's nearest DOM ancestor
against this list; non-allowed → fail.

### §3.8  DISPLAY HEADLINES ARE HAND-POSITIONED  [SOFT — designer judgment]
Display headlines do NOT snap to baseline; body/labels/spacing do. CSS
cannot fully close this gap — the Option-2 premise. Bar: "small human
touch-up", not "pixel-identical".

### §3.9  COPY DISCIPLINE  [HARD] (from Copy Masterbook / Master System)
NOTE: These validators run in the PRE-PROCESSOR, not the renderer.
The renderer does not validate copy. Specific line citations from
`04_DMC_Copy_Masterbook_v3.md` and `05_DMC_Intelligence_Layer_v4.md`
are DEFERRED to the pre-processor validator implementation — each
validator will cite its source line when built. The rules below are
verified real (CC TASK-0 full reads confirmed their existence in the
docs); the grammar records them for completeness but they are not
the renderer's concern.
Validators:
  - "Nicht X, sondern Y" construction max 1× per report
  - Three-word sentence chains max 1× per report
  - Gedankenstriche (em-dashes) max 1× per page
  - Same word max 2× per page (Synonymisierung)
  - "How-to" overkill: max 30% of "Wie" revealed
  - Verbotene Buzzwords: "innovativ", "maßgeschneidert", "ganzheitlich",
    "state-of-the-art" (denylist)
  - Min. 2 Voice-Marker per content page  [SOFT]


## §4  LAYER-B BRAND PROFILE SCHEMA (per-client; the overfit fix)

A client profile MUST supply every axis below. RULE [HARD]: a profile
that omits any axis is REJECTED loud at config-time — never defaulted.
The renderer reads (Layer-A pattern) × (this profile).

### §4.0  AXES (each a required field)

  P            primary dark           hex
  A            accent set + ROLE map  {cover, cta, body_editorial,
                                        box_fill, data_emphasis, icons,
                                        checks, url, kicker, attribution,
                                        stamp_outline} → each maps to a
                                        hex in the accent set
  M            accent MECHANIC        "contrasting_hue" | "tonal_same_hue"
  G            ground mode            "cream_textured" | "cool_light" |
                                        "role_split(photo_dark/light)" |
                                        "tri(dark/saturated/light)" |
                                        "saturated_dark+light"
  X            texture                "marble_paper" | "crumpled_paper" |
                                        "smooth" | "photo"
  H            headline type          "serif" | "sans" | "sans_allcaps"
  HC           headline construction  "single_colour" | "accent_word" |
                                        "two_tone_two_weight" |
                                        "tonal_accent_word"
  I            image modes (set)      any of: full_bleed_photo,
                                        cutout_figure, framed_rect,
                                        3d_render, device_mockup,
                                        duotone, product_shot
  S            page unit              "spread" | "single_page"
  CG           case-study geometry    "RRW" | "LRP" | "NR" | "BAND"
  N            belief-card treatment  "dark_box" | "ghost_numeral" |
                                        "connector_spine" | "plain_numbered"
  RW           rating widget          "trustpilot" | "trustmarkt" |
                                        "agenturmarkt" |
                                        "google_softwareadvice"
  font_head    headline font          customer-font (Priorität 1) OR
                                        Montserrat (default; ExtraBold/
                                        Bold/SemiBold per InDesign Spec
                                        L484-489)
  font_body    body font              customer-font (Priorität 1) OR
                                        Source Sans Pro (default;
                                        Regular/SemiBold/Bold/Italic
                                        per InDesign Spec L484-489)
  motif        optional decorative device

Body text colour [HARD, governed for ALL profiles]: #333333.
Citation: `DMC_InDesign_Spec_v1.md` L243 (verbatim):
  "Farbe:                 #333333 (Dunkelgrau, nicht Schwarz)"
This is NOT a per-client value; it is the chassis default and ALL
profiles inherit it unless they explicitly override (rare).

Body alignment [HARD]: Blocksatz (justified) with auto-hyphenation;
4mm first-line indent on paragraphs AFTER the first (Body_First = no
indent, Body_Text_Einzug = 4mm).
Citation: `DMC_InDesign_Spec_v1.md` L244-246, L262-275.

Hyphenation threshold [HARD]: minimum 5 characters in the word before
hyphenation fires; 2 characters minimum before the break, 2 after
(the "2-2 Minimum" rule). For Pyphen configuration: `left=2, right=2`.
Without this, Pyphen hyphenates short words and body text looks choppy.
Citation: `DMC_InDesign_Spec_v1.md` L246 (verbatim):
  "Silbentrennung:        EIN (mindestens 5 Zeichen, 2-2 Minimum)"

Body leading [HARD]: 14pt FEST (fixed, not automatic). This is the
vertical distance between baselines of consecutive body text lines.
"FEST" means the renderer must set an absolute value, not a relative
`line-height` multiplier — 14pt regardless of font-size variations.
This governs the vertical rhythm of the entire report.
Citation: `DMC_InDesign_Spec_v1.md` L242 (verbatim):
  "Zeilenabstand:         FEST 14 pt"

Baseline grid [HARD]: body text snaps to a baseline grid
(Grundlinienraster: EIN). Every line of body text across the page
aligns to the same invisible vertical grid — this is the "magazine
feel" that distinguishes a typeset report from an HTML page. In CSS
this is approximated by ensuring `line-height`, `margin-top`, and
`padding-top` on all body elements are multiples of the baseline
increment (14pt per the leading rule above).
Citation: `DMC_InDesign_Spec_v1.md` L246 (in the same Absatzformate
  block as Silbentrennung):
  "Grundlinienraster:     EIN"

Body geometry [HARD]: 2-column ~84mm each, 6mm gutter.
Citation: `DMC_InDesign_Spec_v1.md` L53-65 (verbatim):
  "Standard-Raster:       2 Spalten
   Spaltenabstand:        6 mm
   Spaltenbreite:         (Textbreite - 6mm) / 2 = ca. 84 mm"

Section labels — TWO DISTINCT RULES [HARD]:
  H2 (Subheadline) colour: **Primärfarbe** OR Dunkelgrau (#333333).
    The client's primary dark colour (navy for GEVA/aerz, slate-blue
    for alex, bright blue for nikl, deep teal for buch) — OR dark grey.
    Citation: `DMC_InDesign_Spec_v1.md` L206 (verbatim):
      "Farbe:                 Primärfarbe ODER Dunkelgrau (#333333)"
  H3 (Zwischentitel) colour: **Akzentfarbe** OR Dunkelgrau.
    The client's accent colour (coral for GEVA, gold for aerz, amber
    for nikl, tan for alex, lighter teal for buch) — OR dark grey.
    Citation: `DMC_InDesign_Spec_v1.md` L225 (verbatim):
      "Farbe:                 Akzentfarbe ODER Dunkelgrau"
  These are DIFFERENT rules for different heading levels. H2 uses the
  PRIMARY; H3 uses the ACCENT. Do not conflate them. Not navy_bold
  (D1 STRUCK in matrix — neither level mandates a specific colour;
  both offer a choice between the brand colour and dark grey).

Headline size [SOFT]: 28–40pt, default 32pt.
Citation: `DMC_InDesign_Spec_v1.md` L183.

Pullquote size [SOFT]: 17–20pt.
Citation: `DMC_InDesign_Spec_v1.md` L285.

Customer font [VARIATION — Priorität 1]: if client supplies a Hausschrift
(via CD asset upload, NOT upstream JSON), it OVERRIDES both font_head
and font_body. Absent customer font → Priorität 2 fallback (Montserrat
+ Source Sans Pro).
Citation: `08_DMC_Design_System_v2.md` B.2 L90-91.

### §4.1  THE FIVE OBSERVED PROFILES (every cell cited)

Hex from work/sweep/colors.txt + accents.txt. Approximate; role-correct.

GEVA / mein_werkzeugkoffer
  P            navy #1E1D41 (panel #404472)          [colors 2.jpeg]
  A            cover/cta/icons/kicker/data/checks =
                 GOLD #D58D0C..#E09308               [1.jpeg, 11.jpeg]
               body_editorial/quote/url =
                 CORAL #E46F36..#E47E46              [4.jpeg]
               (check-circle varies: green 2.jpeg / gold 5,6,9)
  M            contrasting_hue
  G            role_split(photo_dark/cream)
  X            marble_paper
  H            sans          HC single_colour (gold cover, navy interior)
  I            full_bleed_photo, framed_rect, duotone(p9), cutout_bleed
  S            spread        CG LRP            N ghost_numeral
  RW           google_softwareadvice
  font_head    Montserrat (fallback)
  font_body    Source Sans Pro (fallback)
  NOTE: accent is DUAL BY FUNCTION (gold=structural; coral=editorial).
  CORAL IS A VALUE IN THIS PROFILE — it is not a chassis concept and
  does not appear in any other profile.

aerz / Ärztepartner
  P            navy #222B53 (#1E264F); secondary brighter blue
                 #1F4C82/#0B5392                     [accents p01]
  A            ribbon/connectors/badges/icons/url =
                 GOLD/BRONZE desat #B89B5E/#957C49   [accents p08]
               CORAL = ABSENT (skin tones only; pixel-confirmed)
  M            contrasting_hue       G cool_light    X crumpled_paper
  H            serif         HC accent_word (brighter-blue in navy serif)
  I            cutout_figure, 3d_render, framed_rect (NO full-bleed)
  S            spread        CG RRW            N dark_box
  RW           google-style review cards
  motif        flowing gold ribbon footer every interior
  NOTE: back cover is P-12a (light, no vivid accent).

nikl / NMR
  P            bright BLUE #034A9A/#01499A (vivid royal, NOT navy)
                                                     [accents p07]
  A            stat/url/cta/back-head =
                 GOLD-AMBER #B4831D/#815D18          [accents p18-19]
               headline-emphasis = the bright blue itself
  M            contrasting_hue (2 accents: blue + gold)
  G            tri(near-black #27262A / full-bleed blue / white)
  X            smooth/photo
  H            sans          HC two_tone_two_weight (white/black reg
                                  word + heavy coloured word)
  I            full_bleed_photo, framed_rect, device_mockup
  S            single_page   CG RRW-rail w/ GHOST NUMBER
  N            connector_spine
  RW           trustmarkt
  motif        rotated side-label + blue corner tab every interior

alex / Boss Recruiting
  P            desat SLATE-BLUE #1C2341/#44496B; secondary clinic-blue
                 #2675B9                             [accents p10]
  A            underlines/numerals/rules/box-borders =
                 MUTED TAN-GOLD #CCA770/#BB9A61      [accents p01, p03]
               cta bands = clinic-blue #2675B9
  M            contrasting_hue
  G            saturated_dark+light (slate bands on light)
  X            smooth
  H            sans_allcaps  HC single_colour + tan underline
  I            full_bleed_photo, framed_rect, device_mockup, round_portrait
  S            spread        CG BAND(full-width slate header band)
  N            dark_box(slate)
  RW           trustpilot
  NOTE: structurally aerz's twin (light+blue+gold, spread) on different
  dials — the cleanest proof of Layer-A/B separation.

buch / Buchagentur
  P            deep TEAL/PETROL #073C3E (#042F30)    [colors p01]
  A            ALL roles = LIGHTER TEAL same-hue #389694/#3C9D9A
                                                     [accents p01, p09, p11]
  M            TONAL_SAME_HUE   <-- the structural outlier; un-
                  representable in any contrasting-accent model.
                  This axis is WHY M must exist.
  G            saturated_dark+light (teal bleed / light body)
  X            smooth        H serif    HC tonal_accent_word
  I            cutout_figure, framed_rect, product_shot
  S            spread        CG NR(no rail)    N plain_numbered
  RW           trustpilot + agenturmarkt + bekannt-aus logo row
  motif        thin wing/swoosh + faint dot-arc bottom corner

### §4.2  CROSS-CLIENT FACTS (pixel-proven; kill the old assumptions)
  - "navy+coral universal" (dead skill §1): FALSE. coral absent in
    aerz/nikl/alex; buch one-off (Venn red, not a system); GEVA coral
    is interior-editorial-only and SECONDARY to gold on cover/CTA.
  - accent MECHANIC differs (contrasting ×4, tonal ×1). A colour value
    alone cannot encode this; axis M is mandatory.
  - serif headlines: aerz, buch. sans: GEVA, nikl. sans-allcaps: alex.
    The dead skill assumed sans-only.
  - ground varies (cream/cool-light/tri/teal-bleed/slate-band). "Always
    cream" is false.


## §5  BINDING TO THE API ST CONTRACT

The 11 contract STs map to patterns as follows. This grammar does NOT
alter the contract.

  ST-01 Cover        → P-1 (profile picks archetype; aerz→P-1a)
  ST-02 Outlook      → P-2 (nikl→P-2a)
  ST-05 About        → P-3
  ST-09 Status Quo   → P-4  (P-5 if content is belief-framed)
  ST-14 False Belief → P-5  (treatment by axis N)
  ST-07A Case Study  → P-6  (geometry by axis CG; SINGLE-PAGE per §1.5)
  ST-07B Theory      → P-7  (sub-form by axis T)
  ST-06 Mechanism    → P-8
  ST-FAZIT Summary   → P-9  (nikl→P-9a)
  ST-22 Collaboration→ P-10
  ST-03 CTA          → P-12 (aerz→P-12a)
  + P-13 process-flow is a COMPONENT usable in ST-07B/ST-06.
  + P-15 ghost element is a COMPONENT usable in ST-07A/ST-14.

Richard's Master System defines 37 STs total (Modul 8); the contract
implements 11. The remaining 26 (ST-04 Innenklappe, ST-07C Fallstudie-
Doppelseite, ST-08 FAQ, ST-10–13 PROBLEM, ST-15–18 DENKFEHLER variants,
ST-19–21 MECHANISMUS variants, ST-23–28 PROOF variants, ST-29–31 TRUST
variants, ST-32 Atemseite, ST-33–37 SPECIAL) are committed scope
(decision 2026-05-18) but additive — built after the 13-set produces a
strong full report.

### §5.1  CONTRACT FLAGS (matrix decisions, NOT resolved here)
  - P-11 Trust Proof: 4/5 reports have a dedicated trust page; the
    contract has no ST. Master System defines ST-31 Kompetenz/Trust-
    Cluster. Adopting ST-31 into the contract OR folding trust into
    ST-05 is a CONTRACT decision → MATRIX.
  - ST-32 Atemseite: defined in Master System Modul 8; no contract ST.
    Adoption → MATRIX.


## §6  ANTI-PATTERNS (Layer-A prohibitions; byte-verified; tier-tagged)

### §6.1  UNIVERSAL [HARD] (verified across all relevant clients)

  1   no rounded corners on text containers / panels
      EXCEPTION 1: CTA boxes may have 2–3mm border-radius optionally.
      Citation: `DMC_InDesign_Spec_v1.md` L548-552:
        "Textrahmen_CTA_Box: ... Ecken: Optional leicht abgerundet
         (2–3mm)"
      EXCEPTION 2: Mechanism/process step cards (P-8, P-13) may have
      rounded corners when used as numbered-stage containers.
      Evidence: aerz_p07 (5 navy step cards with clear ~4mm rounding +
      3D gold icons — strong, unambiguous). buch_p07 Freiheits-Kaskade
      Stufe cards show negligible rounding (weak supporting evidence;
      do not rely on as second-client confirmation). Treated as
      VARIATION — per-brand designer choice, not universal law. Not
      cited in InDesign Spec (no Textrahmen_Mechanismus entry found).
  2   no drop shadows on type or panels (flat fills only)
  3   no multi-colour body text within a paragraph
  4   no gradient fills on type
  5   no script/decorative display fonts
  6   no 3D/bevel effects on DIAGRAMS (3D bar/pie/line charts
      forbidden — Master System Modul 6, `08_v2` E.1 "Kein 3D —
      niemals" in diagram context). EXCEPTION: 3D-rendered decorative
      ILLUSTRATIONS adjacent to diagrams are legitimate (aerz_p07
      gold icons: magnifying glass, compass, shield, column,
      handshake; aerz_p08 3D coin stacks; aerz_p04L hourglass).
      The rule prohibits 3D data visualization, not 3D decorative
      objects. Evidence: 2/5 clients use 3D-rendered illustrations
      as design elements while all diagrams remain flat 2D.
  7   no drop caps on body
  8   photos rectangular or soft/oval portrait — no rounded-corner photos
  9   ≤4 distinct hues per page (palette discipline; pairs with §3.5
      report-level ≤3)
  10  no empty body page — every page has ≥1 anchor (number/callout/
      photo/headline/ghost element)
  13  no running per-page footer CTA — CTAs are end-of-chapter/report
  14  page folio small, mid-grey, corner only — never oversized/accent
  15  ONE case-study geometry per report — never mixed
  16  ST-07B forbids direct reference back to ST-07A (Master System;
      v2 L209-210 reinforces — eigenständig, ohne Rückbezug)
  17  Single QR code per report — "Mehr als 1 QR-Code / URL pro Report"
      VERBOTEN (Master System / Intelligence Layer — specific line
      citation deferred; rule verified present in CC TASK-0 full reads
      of both docs; to be pinned at validator build time)
  18  Atemseite (ST-32): every 5–7 pages max one, NIEMALS adjacent

### §6.2  CORRECTED — were asserted universal by pattern-spike; bytes refute
(These are NOT anti-patterns — they are Layer-B options.)
  11  "no pure-black/dark ground" → FALSE: nikl near-black is legitimate.
      Retained as "avoid pure #000000; use the client's dark value".
  12  "always cream + texture" → FALSE: ground-mode is Layer-B (axis G).
      Retained as "ground is never default pure #FFFFFF; it is the
      client's ground-mode value".


## §7  PRINT EXPORT [HARD]

Citation: `08_DMC_Design_System_v2.md` H.1 L365-371 (verbatim):
  Dateiformat:    PDF/X-3 oder PDF/X-4
  Farbprofil:     ISO Coated v2 300% (Euroscale Coated)
  Auflösung:      Min. 300 dpi für Bilder bei Endgröße
  Anschnitt:      3 mm
  Schriften:      Eingebettet oder in Kurven
  Schwarzer Text: K=100 (kein Komposit-Schwarz)
  Seitenanzahl:   Durch 4 teilbar

Bleed [HARD]: 3mm all sides.
Citation: `DMC_InDesign_Spec_v1.md` L26-29.

Margins [SOFT — derive, do NOT hardcode]:
Citation: `08_DMC_Design_System_v2.md` L15-16 (governing; GATE-3 ruling):
  "Falsch: Exakte Randmaße und Spaltenbreiten als harte Vorgaben
   Richtig: Maße ergeben sich aus Zeichenlimits der Copy und Lesbarkeits-
   Anforderungen (siehe Teil B)."
Reference baseline (derived defaults, NOT canonical):
  T16 / O14 / B20 / I18 mm per InDesign Spec L40-43.
These numbers are the OUTPUT of the derive-from-character-limits
process for a 2-col 84mm body — they are an assertion target, NOT a
chassis input. The chassis derives margins from body geometry; the
baseline is for sanity-check.

K=100 black text [HARD per spec; OPEN for chassis]: WeasyPrint does
not natively emit pure-K black. This is a post-process PDF step.
Currently DEFERRED; renderer outputs composite black until a colorist
pass converts at commit. State openly.


## §8  WHAT THIS GRAMMAR DOES AND DOES NOT CLOSE (honest bar-setting)

CLOSES:
  - The grammar gap. Page = (Layer-A pattern) × (Layer-B profile),
    structurally complete, palette-correct, page-filling, brand-true.
  - The coral-as-concept disease. Accent is a per-client profile field;
    the validator checks `accent` (whatever hue) area + location; the
    word "coral" appears in chassis logic zero times. Coral is one
    value in GEVA's profile row, nowhere else.
  - The 2-page-spread misread. Case study is single-page per `08_v2`
    L209-210; the weak GEVA render is a value/grammar problem on the
    single page, not a missing right half.
  - Apex-contamination at the brand-token level. Richard's upstream
    payload is 4 design fields (primaerfarbe_hex, akzentfarbe_hex,
    logo_vorhanden, autorenfoto_vorhanden) per Master System Modul 4.1.
    Everything else is production-curated per `08_v2` C.1.

DOES NOT CLOSE: designer judgment. Hand-kerned headline positioning,
photo focal points, optical balance (§3.8). The Option-2 premise: machine
draft + small human touch-up. Bar: "a designer finishes it in minutes".

REMAINING PRE-RATIFICATION ITEMS (state, don't hide):
  - 64 pages read; 5 Richard docs read (matrix 2026-05-18 TASK-0).
  - [SINGLE-CLIENT] tags (P-1a, P-2a, P-9a, P-12a, P-14, repeating-
    spread) are NOT promoted to universal.
  - Hex is screen-extracted; press-CMYK is a colorist task.
  - Two matrix-flagged contract items (P-11 Trust binding; the 37→11
    ST gap) MUST be resolved via the matrix before a full report
    renders against the real contract.
  - K=100 pure-K black emission is DEFERRED (§7).
  - Customer-font intake path is DEFERRED (production-side asset upload).
  - ATMOSPHERIC / DECORATIVE ELEMENTS not captured as patterns: marble/
    crumpled paper page backgrounds, atmospheric gradient washes (aerz
    sky effect), 3D-rendered decorative icons (aerz gold icons), 3D-
    rendered object illustrations (aerz coin stacks, hourglass). These
    are NOT structural patterns — they are Layer-B brand-treatment
    assets produced by the pre-processor's AI image generation pipeline,
    not by CSS. The grammar's Layer-A patterns are STRUCTURAL; these
    atmospheric elements are the responsibility of the pre-processor
    layer, not the grammar or the renderer.

REMAINING UNGROUNDED ITEMS (BARRED from chassis until cited):
  - §5c "coral micro-header callout grid" — no verbatim Richard
    citation; UNGROUNDED-DEFERRED in matrix; chassis CSS for this
    element STAYS BARRED until cited or a citation refutes its
    existence in the GEVA reference.
  - FALLSTUDIE stamp position in left rail — visual-evidence-only
    (mw_p14); no verbatim citation. UNGROUNDED-DROPPED unless a
    citation surfaces. Treat as observation, not rule.


## §9  PROVENANCE & CHANGE DISCIPLINE (the F1 trust-boundary fix)

- This file supersedes the dead SKILL.md (header). The chassis MUST be
  repointed here AND MUST refuse to load while RATIFIED-BY is blank.
  The loader implements this as a fail-loud check at startup — same
  pattern as the brand_tokens fix.
- Ratification = a human (Utkarsh) reads this file against the
  reference PDFs AND the 5 Richard docs, AND fills RATIFIED-BY. The
  signature IS the audit; an unaudited signature defeats the gate.
- Append-only after ratification, same discipline as the matrix. Any
  new client adds a §4.1 profile (all axes, cited) — does NOT edit
  Layer A. Layer-A change requires re-ratification.
- Where Richard's docs and the corpus sweep disagree, Richard governs.
  Where two LIVE Richard docs disagree, §0 governance order applies
  (v2 Design System > InDesign Spec; other pairs subject-disjoint).
- v1/Old* docs WITH a successor on disk: DEAD. The InDesign Spec is
  LIVE under the successor-existence rule (no v2 exists; cited as
  authoritative by v2 Design System L925).
- Coral as a chassis concept is REMOVED. If a future contributor
  reintroduces the word "coral" anywhere except as a literal hex value
  in GEVA's §4.1 row (or a worked example), they have recontaminated.
================================================================================
