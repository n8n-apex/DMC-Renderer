# Grammar ↔ Contract Reconciliation Matrix — Redefined STEP 0

STATUS: BLOCKING. 18 reconciliation rows (A1,A2,B1-B5,C1-C3,D1,D2,E1-E6)
+ F1-F3 acknowledgements. No coral edit, no Chassis Phase 0, no STEP 2
GEVA build begins until every non-blocked row is RATIFIED by Utkarsh.
[AUTHOR-ERROR-1 CORRECTED: prior header said "13"; true enumerated count
is 18, confirmed by CC verification log.]

ROOT FAULT: API_CONTRACT.md / ARCHITECTURE.md / BRAND_TOKENS.md /
FONT_LOADING.md / CACHE_STRATEGY.md = the Apex Phase-2 contract. pattern-
spike/* + design-findings.md + idml-spike skills + richard-pattern-
confirmation.md = Richard's extracted grammar. Built at different times,
never reconciled. apex_consulting_payload.json conforms to the contract;
fixture_mw_geva.json conforms to the grammar; no mapping exists between
them. Every row below is one instance of that fault line.

RATIFICATION STATES (per row): UNRATIFIED → (user ruling) → RATIFIED.
Rows marked BLOCKED-ON-RICHARD cannot be ratified by anyone until
Richard answers richard-pattern-confirmation.md; they are NOT CC's to
decide and NOT to be guessed. Verdict tags: DATA-DECIDED (bytes already
settle it, source named) / USER-RULES (needs Utkarsh decision) /
PENDING-FILE (needs an unseen file). Each DATA-DECIDED row carries a
CC-VERIFY line naming the exact file:field CC must open and confirm.

RATIFY IN THIS ORDER (dependencies): A1 first (keystone), then A2,
Section B, Section C, D, E. F = acknowledge only.

================================================================
SECTION A — THE STRUCTURAL SEAM (A1 is the keystone)
================================================================

A1 — design_preferences ingestion seam
CLAIM: fixture_mw_geva.json brand_tokens.design_preferences is a nested
object {case_study_geometry, fallstudie_kicker_style, pullquote_treatment,
page_background, section_label_style, coral_budget_per_page,
callout_row_color}. BRAND_TOKENS.md states verbatim "No nested merging
(no key in brand_tokens is currently an object, so this isn't a concern)".
apex_consulting_payload.json has no such key (flat 14-key brand_tokens).
VERDICT: DATA-DECIDED — grammar wins. Renderer must grow a
design_preferences ingestion path (this is architecture-v2's
BrandLayout/BrandStyle seam located in real data). BRAND_TOKENS.md
"no nested merge" sentence struck, replaced with design_preferences
sub-schema.
USER-RULES: does design_preferences stay inside brand_tokens (as GEVA
sends it) or get promoted to a 4th top-level request key? RECOMMEND:
keep inside brand_tokens (API_CONTRACT.md authoring rule: the fixture
IS the contract).
CC-VERIFY: fixture_mw_geva.json → brand_tokens.design_preferences exists
and is an object; BRAND_TOKENS.md → the literal "no nested merging"
sentence; apex_consulting_payload.json → brand_tokens has no
design_preferences key.
RATIFICATION: UNRATIFIED

A2 — Apex has no design_preferences; needs default-resolution rule
CLAIM: apex_consulting_payload.json brand_tokens has no design_preferences.
If renderer keys variant behavior off that object, Apex must resolve to a
default profile.
VERDICT: USER-RULES. RECOMMEND: absence → documented "apex" default
profile (RRW geometry, initials block, 3-up metrics, coral count-budget
{ST-01:3,ST-03:3,_default:2}, single-page). Absence is NOT a 400.
CC-VERIFY: apex_consulting_payload.json → confirm no design_preferences
anywhere in brand_tokens.
RATIFICATION: UNRATIFIED

================================================================
SECTION B — ST-07A SCHEMA SPLIT (blocks STEP 2)
================================================================

B1 — ergebnis_metrics cardinality
CLAIM: API_CONTRACT.md ST-07A: ergebnis_metrics required, "3 items
expected … Apex template applies coral to the first metric".
apex_consulting_payload.json: every case study has exactly 3.
fixture_mw_geva.json: ergebnis_metrics is [] (empty).
VERDICT: DATA-DECIDED — split ST-07A by geometry. LRP (P-6b/GEVA):
ergebnis_metrics optional, may be [], no 3-up block, no coral-first rule.
RRW/Apex: required, 3 items, coral-first. ST-07A becomes a geometry-
discriminated union keyed off design_preferences.case_study_geometry.
API_CONTRACT.md ST-07A flagged "Apex/RRW variant; LRP defined separately".
CC-VERIFY: API_CONTRACT.md → ST-07A ergebnis_metrics row text;
apex_consulting_payload.json → slots 6/8/10/12/13 ergebnis_metrics length;
fixture_mw_geva.json → data.ergebnis_metrics is [].
RATIFICATION: UNRATIFIED

B2 — wendepunkt type collision (RENDER-CORRUPTING — highest danger)
CLAIM: API_CONTRACT.md: wendepunkt = markdown-preprocessed prose, ""
valid. ARCHITECTURE.md §6 lists wendepunkt among preprocessed fields
(\n→<br/>). apex: prose or "". fixture_mw_geva.json: wendepunkt =
"Mehr Übersicht bei Planung | Prüftermine sicher im Griff\nWerkzeuge
sauber verwaltet | Strukturiert statt manuell" — a 2x2 pipe/newline
callout grid. Running §6's preprocessor turns \n into <br/>, pipes stay
literal: the P-6b callout row renders as one broken text line. Passes
every structural gate (present, non-empty string); corrupts at render.
VERDICT: DATA-DECIDED — LRP needs a distinct structured field.
RECOMMEND: LRP schema renames to callout_row typed [{text}] (parsed, NOT
preprocessed); remove wendepunkt from §6 preprocess list for LRP; re-
transcribe GEVA fixture to an array. STEP 2 cannot build until this
field's type is fixed.
CC-VERIFY: ARCHITECTURE.md §6 → wendepunkt present in preprocess table;
fixture_mw_geva.json → exact data.wendepunkt string incl. the literal \n
and pipes.
RATIFICATION: UNRATIFIED

B3 — ziel field missing from contract
CLAIM: fixture_mw_geva.json has data.ziel. apex: no ziel anywhere.
API_CONTRACT.md ST-07A: no ziel field. design-findings.md §1: render_v7
iter 12 renders Ausgangssituation/Ziel/Lösung/Ergebnis. richard-design-
system §4: aerztepartner sequence Unternehmen→Ausgangssituation→Ziel→
Lösung→Ergebnis.
VERDICT: DATA-DECIDED — grammar wins. LRP schema adds ziel (required,
preprocessed prose). RRW/Apex omits it. Contract ST-07A must document the
LRP body field set.
CC-VERIFY: fixture_mw_geva.json → data.ziel exists; API_CONTRACT.md →
ST-07A field table has no ziel row; apex_consulting_payload.json → grep
ziel returns nothing in any ST-07A.
RATIFICATION: UNRATIFIED

B4 — kunde.initials vs photo
CLAIM: API_CONTRACT.md: kunde.initials required, "InitialsBlock when no
portrait". apex: all initials populated, no portraits. fixture_mw_geva:
initials "GE" present BUT images.geva_team is a real photo file AND
richard-design-system §2 Variant B′ (confirmed P-6b) is photo-at-top-of-
rail, not initials. design-findings.md §7 lists the initials-block ref
(assembly-st07a-conesso-v6.pdf) under "Worth abandoning — wrong sidebar".
VERDICT: DATA-DECIDED — split. LRP: photo rail, initials ignored when an
image slot is present (kept in schema for forward-compat). RRW/Apex:
initials block when no portrait. STEP 2 renders the GEVA photo, not "GE".
PARTIAL BLOCKED-ON-RICHARD: Richard's Q6/Q7 (geometry per brand) could
alter whether LRP is fixed-per-brand. The photo-vs-initials split itself
is DATA-DECIDED; the per-brand binding is BLOCKED-ON-RICHARD.
CC-VERIFY: API_CONTRACT.md → kunde.initials row; fixture_mw_geva.json →
images.geva_team value AND data.kunde.initials value; design-findings.md
§7 → the "Worth abandoning" section, bullet "The v6 prototype (built on
wrong sidebar pattern)". [AUTHOR-ERROR-2 CORRECTED: prior CC-VERIFY cited
the filename "assembly-st07a-conesso-v6.pdf" as appearing in design-
findings.md §7; that filename does NOT appear in §7. The substance of B4
— LRP uses a photo rail, not the initials block; the v6 sidebar pattern
is abandoned — is unchanged and supported by the §7 bullet above. Only
the evidence pointer was wrong.]
RATIFICATION: UNRATIFIED (split: DATA portion ratifiable; per-brand
binding BLOCKED-ON-RICHARD)

B5 — case-study image slot + file:// fetch
CLAIM: API_CONTRACT.md images slots are usage-named; Apex ST-07A uses no
image. fixture_mw_geva.json images: {"geva_team":"file:///…/geva-team-
placeholder.png"}. CACHE_STRATEGY.md fetcher uses urllib.request.urlopen
(HTTP) and slot regex ^[a-z][a-z0-9_]{1,30}$. geva_team matches regex but
file:/// is not urlopen-fetchable like Drive uc?id= URLs, and the contract
has no case-study image slot.
VERDICT: DATA-DECIDED — LRP needs a case-study image slot AND fetcher must
accept file:// (test) + https:// (prod). Flag: production GEVA-style needs
a real fetchable URL, not file://.
CC-VERIFY: CACHE_STRATEGY.md → fetch_images uses urllib.request.urlopen;
fixture_mw_geva.json → images.geva_team value; API_CONTRACT.md → images
slot table has no case-study slot.
[AUTHOR-ERROR-6 CORRECTED: B5's reasoning that "file:/// is not
urlopen-fetchable" is FALSE — urllib.request.urlopen natively supports
file:// URLs. B5's VERDICT is UNCHANGED and still holds: the LRP case
study needs an image slot AND the contract defines no case-study image
slot — that fact alone, independent of the file:// reasoning, is the
basis for B5. Only the file:// rationale is struck.]
RATIFICATION: UNRATIFIED

================================================================
SECTION C — CORAL (blocks STEP 0 coral edit; three-way)
================================================================

C1 — coral rule is three-way
CLAIM: ARCHITECTURE.md §7: hardcoded CORAL_BUDGET={"ST-01":3,"ST-03":3,
"_default":2}, raster validator, 422 on >2. API_CONTRACT.md: public error
"coral_budget_exceeded"+fires[], n8n branches on it. BRAND_TOKENS.md
asserts ≤2 in FOUR places (brand_accent row; "does NOT control" list;
"Adding a new brand" step 4; merge-defaults comment). fixture_mw_geva.json
design_preferences.coral_budget_per_page: 5. richard-design-system §1
REVISED: coral fires multiple times per page in mw "with intention", 7
legitimate locations, "≤1 per page … DOES NOT apply to mein_werkzeugkoffer".
VERDICT: USER-RULES, model clear. Per-brand-overridable budget from
design_preferences.coral_budget_per_page, default = contract count when
absent. Apex → count {ST-01:3,ST-03:3,_default:2}. GEVA → budget 5,
validated by LOCATION LEGITIMACY (richard-design-system §1's firing
locations) not raw count.
CC-VERIFY: ARCHITECTURE.md §7 → the CORAL_BUDGET dict literal;
BRAND_TOKENS.md → the brand_accent-row ≤2 assertion AND the "does NOT
control" ≤2 assertion AND the "Adding a new brand" step 4 "1 fire/page"
assertion (quote all three with line context; confirm the 1-vs-2 self-
conflict); fixture_mw_geva.json → design_preferences.coral_budget_per_page
value; richard-design-system §1 → the "DOES NOT apply to
mein_werkzeugkoffer" sentence + the firing-locations list.

[AUTHOR-ERROR-3 CORRECTED: prior text claimed BRAND_TOKENS.md asserts ≤2
in FOUR places. Byte-verified: TWO literal ≤2 assertions (brand_accent
row; "does NOT control" list), both matching ARCHITECTURE.md §7's coded
CORAL_BUDGET dict. A THIRD location ("Adding a new brand" step 4) asserts
"1 fire/page is the discipline regardless of client". This is NOT a
fourth coral rule to reconcile — it is the v6 aerztepartner-extracted
discipline that richard-design-system §1 EXPLICITLY invalidated for
mein_werkzeugkoffer ("the earlier '≤1 per page' rule was extracted from
aerztepartner and DOES NOT apply to mein_werkzeugkoffer"). DISPOSITION:
on C1 ratification this line is STRUCK, not reconciled — the grammar
already adjudicated it. A FOURTH cited location is only a "# coral"
comment, no rule. C1 STEP-0 SCOPE: (a) the two ≤2 prose assertions; (b)
strike the fossilized "1 fire/page" line; (c) convert ARCHITECTURE.md §7
CORAL_BUDGET from a hardcoded constant to a design_preferences-sourced
lookup; (d) verify the §7 CODED path currently matches a stated rule at
all — the doc self-contradiction is a tell that the code-vs-rule match
is unaudited; (e) preserve the C3 n8n "coral_budget_exceeded" branch
across (c). The doc inconsistency is cosmetic; (c)+(d) are the real work.]
RATIFICATION: UNRATIFIED

C2 — raster validator cannot enforce a location rule
CLAIM: ARCHITECTURE.md §7 raster mode (downsample, count connected coral
regions) has NO DOM. A location rule needs DOM-ancestor classification.
§7 source-mode (HTML scan) is explicitly fail-soft non-authoritative. The
authoritative validator structurally cannot evaluate the rule C1 needs.
VERDICT: USER-RULES — architectural. RECOMMEND (c): location-rule brands
validated DOM-side, count-rule brands (Apex) raster-side, selected by
design_preferences presence (mirrors A2's two-path split, keeps Apex's
proven raster path untouched). CC task 1.f must be re-scoped to this.
CC-VERIFY: ARCHITECTURE.md §7 → confirm raster mode description has no DOM
concept AND source-mode is labeled fail-soft/non-authoritative.
RATIFICATION: UNRATIFIED

C3 — coral_budget_exceeded error code is n8n-coupled
CLAIM: API_CONTRACT.md error table + ARCHITECTURE.md §8: coral_budget_
exceeded is stable kebab-case, "n8n branches on it". A different code from
the location-rule validator silently breaks the n8n catch.
VERDICT: USER-RULES. RECOMMEND: keep the code coral_budget_exceeded
regardless of internal rule; details string carries the rule-specific
explanation. If the code must change it is a PIPELINE EDIT flagged in
STEP 0 (n8n Workflow 3 error branch changes in lockstep), not renderer-
only.
CC-VERIFY: API_CONTRACT.md → the coral_budget_exceeded error code row AND
the literal phrase "(n8n branches on it)"; ARCHITECTURE.md §8 → the error
table (note: §8 describes the error table but does NOT contain the
"n8n branches on it" phrase). [AUTHOR-ERROR-4 CORRECTED: prior CC-VERIFY
attributed "n8n branches on it" to ARCHITECTURE.md §8; the phrase lives in
API_CONTRACT.md. C3's substance — the error code is n8n-coupled, changing
it is a pipeline edit not a renderer-only change — is unchanged.]
RATIFICATION: UNRATIFIED

================================================================
SECTION D — COLOR & LABEL MODEL
================================================================

D1 — brand_neutral_mid / section-label color
CLAIM: BRAND_TOKENS.md: brand_neutral_mid "faintly pink … use #3d3d4a …
handled at template level". apex: brand_neutral_mid "#7a7a8c".
design-grammar.md §2 + richard-design-system §10 type table: section
labels NAVY bold #1A2540, not gray. fixture_mw_geva.json
design_preferences.section_label_style: "navy_bold".
VERDICT: DATA-DECIDED — grammar wins via design_preferences. Section-
label color driven by design_preferences.section_label_style. brand_
neutral_mid used only for folio/URL/caption (richard-design-system §10).
render_v7.py's NEUTRAL_MID-for-labels is a confirmed grammar violation
(one of the original "6 violations").
KNOWN EDGE: design-grammar.md §2 wording is cited from prior transcript,
not bytes verified this run — CC must verify §2 directly.
CC-VERIFY: BRAND_TOKENS.md → brand_neutral_mid "faintly pink" note;
fixture_mw_geva.json → design_preferences.section_label_style value;
richard-design-system §10 → section-label row color; design-grammar.md §2
→ the navy-bold-not-gray statement (THIS ONE IS THE FLAGGED UNVERIFIED
CITATION — report CONFIRMED/REFUTED/UNVERIFIABLE precisely).
RATIFICATION: UNRATIFIED

D2 — sixth color slot (brand_secondary_panel)
CLAIM: BRAND_TOKENS.md "Adding a new brand" step 1: ">5 colors, pick 5;
no sixth slot". apex: 5 color slots. fixture_mw_geva.json:
brand_secondary_panel "#1F3D6D" — a sixth. richard-design-system §1: the
two navys (#1A2540 display, #1F3D6D panel) "deliberately at different
tonal positions … treating them as the same navy … would collapse this
distinction"; §3 pullquote = white on panel navy #1F3D6D.
VERDICT: DATA-DECIDED — grammar wins. Add brand_secondary_panel as a 6th
optional slot, defaults to brand_primary when absent (Apex collapses
harmlessly). BRAND_TOKENS.md "no sixth slot" sentence struck.
CC-VERIFY: BRAND_TOKENS.md → the "doesn't have a sixth slot" sentence;
fixture_mw_geva.json → brand_tokens.brand_secondary_panel value;
richard-design-system §1 → the two-navys "would collapse this
distinction" sentence.
RATIFICATION: UNRATIFIED

================================================================
SECTION E — PAGE MODEL & FONTS
================================================================

E1 — case-study spread vs single
CLAIM: API_CONTRACT.md + ARCHITECTURE.md §5: ST-07A single pages. apex:
all single, export_mode "single-page". fixture_mw_geva.json: single "14",
one-page fragment (page_count_target 20, one slot). pattern-spike P-6a /
page-catalog: Richard's real case studies are LEFT page of a 2-page
spread, theory facing right.
VERDICT: DATA-DECIDED for STEP 2 (single-page correct for both fixtures
as sent); USER-RULES for production. STEP 2 single-page build unblocked.
FLAG LOUDLY: production P-6 may be spread-grammar; build STEP 2 so spread
mode is an additive variant, not a rebuild.
CC-VERIFY: apex_consulting_payload.json → ST-07A page_numbers all single;
fixture_mw_geva.json → meta.export_mode + the single page_numbers + one-
slot pages array.
RATIFICATION: UNRATIFIED

E2 — ST-23 Trust Proof: grammar/plan has it, contract doesn't
CLAIM: pattern-spike P-11 / st-pattern-mapping / design-findings.md §2
12-pattern table / richard-pattern-confirmation.md Q12 all carry ST-23.
API_CONTRACT.md: exactly 11 ST types, no ST-23. ARCHITECTURE.md §13: 11
templates, no st-23.j2. Neither fixture exercises ST-23.
VERDICT: USER-RULES, deferrable (no fixture uses it, not STEP0/STEP2
blocking). RECOMMEND: add to API_CONTRACT.md + §13 now as documented-but-
not-implemented so later phases don't hit an undocumented type.
PARTIAL BLOCKED-ON-RICHARD: Q12 (is Trust Proof per-client optional, mw
the exception) affects whether ST-23 is mandatory.
CC-VERIFY: API_CONTRACT.md → count ST types, confirm no ST-23;
ARCHITECTURE.md §13 → template list, confirm no st-23; design-findings.md
§2 → ST-23 in the 12-pattern table.
RATIFICATION: UNRATIFIED (deferrable; partial BLOCKED-ON-RICHARD)

E3 — export_mode field collision
CLAIM: API_CONTRACT.md: meta.export_mode ∈ {single-page,spread} (layout,
spread reserved v1.1). architecture-v2 §8 + print-pivot + prompt
deliverable (i): export_mode ∈ {print,screen} (print-compliance trigger).
Richard's print spec needs THREE intents (offset/digital/online). Both
fixtures send "single-page".
VERDICT: DATA-DECIDED — collision real, needs separate field. export_mode
keeps API_CONTRACT.md meaning (layout). Print intent moves to NEW field
meta.print_profile ∈ {offset,digital,online,none}, default none.
architecture-v2 §8's export_mode=="print" reading renamed to
print_profile. Must be fixed before the print pipeline wires to
export_mode.
CC-VERIFY: API_CONTRACT.md → export_mode enum + "Reserved for spread";
both fixtures → meta.export_mode value.
RATIFICATION: UNRATIFIED

E4 — Inter weight 400 not bundled; folio/URL render at 700
CLAIM: FONT_LOADING.md @font-face declares Inter 400 → Inter-Regular.ttf;
"Pending" section: Inter-Regular.ttf NOT bundled, Inter-700.ttf the
placeholder, deprioritized because "current Apex templates use Serif for
body and Inter only for labels/headlines (all 700+)". richard-design-
system §10: Folio + URL/meta = Inter Regular (400). So P-6b folio/URL
must be Inter 400 but no Inter 400 face exists → falls back to 700, too
heavy, every page, silent. The "deprioritized" rationale is Apex-only;
the grammar contradicts it.
VERDICT: DATA-DECIDED — grammar wins. Inter-Regular must be bundled
BEFORE STEP 2 (moves from "Pending/low" to STEP 2 prerequisite). Network
config allows github.com so FONT_LOADING.md's own fetch procedure is
feasible in-container.
CC-VERIFY: FONT_LOADING.md → @font-face Inter 400 line AND the "Pending"
Inter-Regular-not-bundled paragraph AND the Apex-only rationale sentence;
richard-design-system §10 → Folio + URL rows show Inter Regular/400.
RATIFICATION: UNRATIFIED

E5 — [WITHDRAWN] kunde.company_url markdown-link markup
STATUS: WITHDRAWN. Premise false against on-disk fixture bytes.
ORIGINAL CLAIM (void): that fixture_mw_geva.json kunde.company_url and
company_url_display contained markdown-link markup "[text](url)" that
would render as literal brackets, requiring a re-transcription + a link-
flatten guard.
WHY WITHDRAWN: CC byte-verified the on-disk fixture this run. On disk,
kunde.company_url = "www.gevagmbh.de" and company_url_display =
"www.meinwerkzeugkoffer.de" — plain strings, NO "[...](...)" markup. The
markup appeared only in a chat-pasted copy of the fixture, not in the file
the renderer ingests. Disk is authoritative for what the renderer reads.
ACTION: NONE. Do not re-transcribe the fixture. Do not add a link-flatten
guard on the basis of this row. If a link-flatten guard is desired as
general defensive hygiene, that is a separate, independently-justified
decision — it is NOT mandated by E5 and must not be smuggled in under it.
[AUTHOR-ERROR-5 CORRECTED: E5's entire diagnostic premise was false; the
row is withdrawn, not amended. This is the canonical case for why on-disk
byte verification overrides author confidence.]
RATIFICATION: WITHDRAWN — not subject to ratification.

E6 — Apex canonical fixture violates ARCHITECTURE.md §5 monotonic rule
CLAIM: apex_consulting_payload.json page_numbers by slot: …slot13="18",
slot14="15-16", slot15="17-18". slot14 goes backwards vs slot13; slot15
overlaps both. ARCHITECTURE.md §5 assert_monotonic warns when
lo<=last_hi → fires on the CANONICAL reference fixture, multiple times.
§5 says renderer does not abort, renders what given → total_pages double-
counts pages 15,16,18; the S.N/TOTAL strip is wrong for the canonical
fixture. ARCHITECTURE.md §13 test_render_apex.py asserts "full 20-page
PDF renders" against a fixture that doesn't cleanly produce 20 monotonic
pages.
VERDICT: DATA-DECIDED — the canonical Apex fixture is internally
inconsistent; cannot be trusted as page-count parity reference. STEP 0
must re-transcribe apex_consulting_payload.json to monotonic page_numbers
OR explicitly mark it "page-numbers known-broken; content-shape reference
only". Highest-severity contract-internal defect found. Re-check Chapter
Plan Generator v2 against this — this fixture predates or escaped that fix.
CC-VERIFY: apex_consulting_payload.json → list page_numbers for slots
13,14,15 verbatim; ARCHITECTURE.md §5 → assert_monotonic + total_pages
code; §13 → test_render_apex.py "20-page" assertion text.
RATIFICATION: UNRATIFIED

================================================================
SECTION F — RESOLVED / NO-ACTION (recorded so not re-litigated)
================================================================

F1 — font alias chain works. apex font_body "Source Serif Pro" →
FONT_ALIASES → "Source Serif 4" (bundled). GEVA font_body "Source Serif
4" → direct (bundled). Both resolve. The defect is E4 (Inter 400), not
the serif chain. ACK ONLY.

F2 — export_mode "single-page" correct for both fixtures for STEP 2
(resolved under E1/E3). STEP 2 single-page unblocked. ACK ONLY.

F3 — same-family serif bold. FONT_LOADING.md v6.1: SourceSerif4-Bold.ttf
bundled, weight700→bold binary. richard-design-system §10 requires
exactly this. Aligned. STEP 2 must NOT regress (no Inter-800 cross-family
workaround). ACK ONLY.

================================================================
COMPLETION GATE FOR STEP 0
================================================================
STEP 0 is not complete until: every A/B/C/D/E row carries Utkarsh's
ruling (or is marked BLOCKED-ON-RICHARD and parked); the five contract
docs are edited to record each DATA-DECIDED verdict (so the next agent
cannot re-derive the conflict); the n8n Workflow 3 coral error branch is
confirmed against C3; the two fixtures are re-transcribed or quarantined
per B2, E5, E6. Only then: STEP 0 coral edit → Chassis Phase 0 → STEP 2.

BLOCKED-ON-RICHARD INDEX: Contradiction-1 (anti-pattern override —
tracked outside this matrix, in the open CC corrections), B4 per-brand
binding, E2 Q12. These wait for richard-pattern-confirmation.md answers.

================================================================
## CC VERIFICATION LOG

Verification adversary pass against fixed matrix above. Byte-fresh reads
this run. No row ratified. No row content above this section modified.

### AUTHOR-ERRORS-OBSERVED

(Surfaced for Utkarsh to correct in the matrix source, not silently
absorbed. Consistent with surface-don't-embed standing rule.)

1. Matrix header / role-prompt framing claims "13 reconciliation rows".
   Actual enumeration: A1, A2, B1–B5, C1–C3, D1, D2, E1–E6 = 18 rows
   (plus F1–F3 acknowledgements). Authoritative count is 18. No row's
   CONTENT is affected; only the header count is wrong.

2. B4 target 3 cites a specific filename inside `design-findings.md §7`
   that does not appear there. The §7 "Worth abandoning" bullet says
   `"The v6 prototype (built on wrong sidebar pattern)"` — it does NOT
   say `assembly-st07a-conesso-v6.pdf`. The conceptual claim survives;
   the filename citation is fabricated/misremembered.

3. C1 target 2 claims `BRAND_TOKENS.md` asserts `≤2 per page` in FOUR
   places. Byte-verified count: TWO. The other two locations the matrix
   names contain (a) a `1 fire/page` assertion (different rule, stricter)
   and (b) just the comment `# coral` with no budget rule at all.

4. C3 target 2 attributes the phrase `"n8n branches on it"` to
   `ARCHITECTURE.md §8`. The phrase actually lives in `API_CONTRACT.md`
   (already C3 target 1). `ARCHITECTURE.md §8` does not contain that
   phrase.

5. E5 target 1 claims `fixture_mw_geva.json` `kunde.company_url` =
   `"[www.gevagmbh.de](https://www.gevagmbh.de)"` and
   `brand_tokens.company_url_display` similarly. The actual bytes show
   PLAIN strings with no markdown-link markup. E5's entire diagnostic
   premise (that GEVA fixture would render literal `[...](...)`
   brackets unless fixed) is FALSE against the current fixture bytes.

### PATH-RESOLUTION-NOTE

User-asserted path `research/idml-spike/richard-design-system/SKILL.md`
does not exist on disk this run. `ls research/idml-spike/` showed no
`richard-design-system/` subdirectory at that level. Per user rule
"mark UNVERIFIABLE with the exact missing path, do not search around
for a substitute," I did NOT enumerate alternative subdirectories.
Targets dependent on `richard-design-system` are UNVERIFIABLE this
run: C1 target 4, D1 target 3, D2 target 3, E4 target 2.

### PER-ROW VERIFICATION

ROW A1
- `research/v7-test/fixture_mw_geva.json` → `brand_tokens.design_preferences` exists as object → CONFIRMED → literal bytes (lines 57–65):
  `"design_preferences": { "case_study_geometry": "LRP", "fallstudie_kicker_style": "coral_outlined_stamp", "pullquote_treatment": "navy_panel_with_oversized_quote_glyph", "page_background": "marble_cream", "section_label_style": "navy_bold", "coral_budget_per_page": 5, "callout_row_color": "coral" }`
- `dmc-renderer/docs/BRAND_TOKENS.md` → literal "no nested merging" sentence → CONFIRMED → literal bytes (line 69):
  `"**Top-level shallow merge.** Per-client tokens override defaults; missing keys fall back. No nested merging (no key in `brand_tokens` is currently an object, so this isn't a concern). No deep diff or schema-driven merge — keep it boring."`
- `dmc-renderer/fixtures/apex_consulting_payload.json` → `brand_tokens` has no `design_preferences` key → CONFIRMED → literal bytes (lines 494–509): 14 flat keys present (`brand_primary`, `brand_accent`, `brand_neutral_dark`, `brand_neutral_mid`, `brand_neutral_light`, `font_heading`, `font_body`, `logo_dark_url`, `logo_light_url`, `qr_target_url`, `founder_full_name`, `founder_role`, `company_name_short`, `company_url_display`); no `design_preferences`.
- ROW A1 NET: matrix-claim-holds.

ROW A2
- `dmc-renderer/fixtures/apex_consulting_payload.json` → no `design_preferences` anywhere in `brand_tokens` → CONFIRMED → see A1 target 3; the entire `brand_tokens` object contains zero occurrences of the substring `design_preferences`.
- ROW A2 NET: matrix-claim-holds.

ROW B1
- `dmc-renderer/docs/API_CONTRACT.md` → ST-07A `ergebnis_metrics` row text → CONFIRMED → literal bytes (line 238):
  `| `ergebnis_metrics` | array of `{label, value}` | yes | no | 3 items expected — renders as the stat_block in the bottom-right of the right column. The Apex template applies coral to the first (most impactful) metric. |`
- `dmc-renderer/fixtures/apex_consulting_payload.json` → slots 6/8/10/12/13 `ergebnis_metrics` length → CONFIRMED → all FIVE ST-07A slots carry exactly 3 items:
  - slot 6 (lines 150–163): 3 items (`Support-Reaktionszeit`, `Jährliche Support-Kosteneinsparung`, `Automatisierte Kernprozesse`)
  - slot 8 (lines 201–214): 3 items (`Automatisierte Kernprozesse`, `Kapazitätslimit`, `Tool-Migrationen notwendig`)
  - slot 10 (lines 252–265): 3 items (`Reaktionszeit`, `Bewältigte Konversationen`, `Zusätzlicher Headcount`)
  - slot 12 (lines 303–316): 3 items (`Onboarding-Zeit`, `Copywriting pro Asset`, `Operative Engpässe`)
  - slot 13 (lines 342–355): 3 items (`Manuelle Koordinationsschritte`, `Lead-Priorisierung`, `Operative Kapazität`)
- `research/v7-test/fixture_mw_geva.json` → `data.ergebnis_metrics` is `[]` → CONFIRMED → literal bytes (line 27): `"ergebnis_metrics": [],`
- ROW B1 NET: matrix-claim-holds.

ROW B2
- `dmc-renderer/docs/ARCHITECTURE.md` §6 → `wendepunkt` present in preprocess table → CONFIRMED → literal bytes (line 158):
  `| ST-07A | `kurzportraet`, `ausgangsproblem`, `wendepunkt`, `loesung`, `ergebnis_text`, `pullquote.text` |`
- `research/v7-test/fixture_mw_geva.json` → exact `data.wendepunkt` string → CONFIRMED → literal bytes (line 23):
  `"wendepunkt": "Mehr Übersicht bei Planung | Prüftermine sicher im Griff\nWerkzeuge sauber verwaltet | Strukturiert statt manuell",`
- ROW B2 NET: matrix-claim-holds.

ROW B3
- `research/v7-test/fixture_mw_geva.json` → `data.ziel` exists → CONFIRMED → literal bytes (line 24):
  `"ziel": "Das zentrale Ziel war, Prüftermine einfacher zu terminieren, zuverlässig nachzuverfolgen und den Überblick über fällige Prüfungen dauerhaft zu behalten. Gesucht wurde eine praxistaugliche Lösung, die zu den Abläufen eines technischen Fachbetriebs passt.",`
- `dmc-renderer/docs/API_CONTRACT.md` → ST-07A field table has no `ziel` row → CONFIRMED → ST-07A field table (lines 228–241) enumerates `fallstudie_number`, `ergebnis_headline`, `kurzportraet`, `ausgangsproblem`, `wendepunkt`, `loesung`, `ergebnis_text`, `ergebnis_metrics`, `kunde`, `pullquote` — no `ziel` row.
- `dmc-renderer/fixtures/apex_consulting_payload.json` → grep `ziel` returns nothing in any ST-07A → CONFIRMED → all five ST-07A slots (6, 8, 10, 12, 13) carry the same field set as the API contract; no `ziel` field in any `data` block.
- ROW B3 NET: matrix-claim-holds.

ROW B4
- `dmc-renderer/docs/API_CONTRACT.md` → `kunde.initials` row → CONFIRMED → literal bytes (line 249):
  `| `initials` | string (1–3 chars) | yes | Used in the big InitialsBlock at the top of the sidebar when no portrait image is provided. |`
- `research/v7-test/fixture_mw_geva.json` → `images.geva_team` value AND `data.kunde.initials` → CONFIRMED → literal bytes:
  line 43: `"geva_team": "file:///Users/utkarsh/Projects/richard/research/v7-test/assets/geva-team-placeholder.png"`
  line 32: `"initials": "GE"`
- `research/v7-test/design-findings.md` §7 → the "Worth abandoning" line naming the conesso-v6 ref → REFUTED → literal bytes of §7 "Worth abandoning" subsection (lines 252–258):
  `"### Worth abandoning`
  `- The v6 prototype (built on wrong sidebar pattern)`
  `- The IDML spike outputs (Option 3 rejected)`
  `- Iterations 1-11 of v7 (only iter 12 + measurements matter)`
  `- The flex-based layouts (replaced by table-layout)`
  `- The "≤1 coral per page" v6 validator (replaced by per-role budget)"`
  The string `assembly-st07a-conesso-v6.pdf` does NOT appear in design-findings.md §7. The conceptual bullet `"The v6 prototype (built on wrong sidebar pattern)"` exists; the matrix's specific filename citation is wrong.
- ROW B4 NET: matrix-claim-broken (conceptual claim survives via the v6-prototype bullet; specific filename citation is fabricated/misremembered).

ROW B5
- `dmc-renderer/docs/CACHE_STRATEGY.md` → `fetch_images` uses `urllib.request.urlopen` → CONFIRMED → literal bytes (lines 65–75):
  `import urllib.request`
  `from pathlib import Path`
  `def fetch_images(images: dict, scratch_dir: Path, timeout_s: int = 30):`
  `    for slot, url in images.items():`
  `        ext = guess_ext(url)             # png/jpg/svg from content-type or URL`
  `        target = scratch_dir / f"{slot}.{ext}"`
  `        with urllib.request.urlopen(url, timeout=timeout_s) as resp:`
  `            target.write_bytes(resp.read())`
- `research/v7-test/fixture_mw_geva.json` → `images.geva_team` value → CONFIRMED → see B4 target 2; value is `file:///Users/utkarsh/Projects/richard/research/v7-test/assets/geva-team-placeholder.png`. Note: `urllib.request.urlopen` DOES accept `file://` URLs in Python's stdlib (so the matrix's "not urlopen-fetchable" sub-claim would itself be byte-questionable — but this is the matrix's REASONING, not a target, and is outside this verification's scope).
- `dmc-renderer/docs/API_CONTRACT.md` → images slot table has no case-study slot → CONFIRMED → literal bytes (lines 396–403): 5 slots enumerated — `cover_hero` (ST-01), `cover_author` (ST-01), `about_logo` (ST-05), `status_quo_scene` (ST-09), `fazit_background` (ST-FAZIT). No case-study slot.
- ROW B5 NET: matrix-claim-holds. (Side note flagged: the matrix's parenthetical "file:/// is not urlopen-fetchable" reasoning is incorrect — `urllib.request.urlopen` natively supports `file://`. Surfaced for Utkarsh; not editing matrix.)

ROW C1
- `dmc-renderer/docs/ARCHITECTURE.md` §7 → `CORAL_BUDGET` dict literal → CONFIRMED → literal bytes (line 216):
  `CORAL_BUDGET = {"ST-01": 3, "ST-03": 3, "_default": 2}`
- `dmc-renderer/docs/BRAND_TOKENS.md` → ALL FOUR `≤2` assertions → REFUTED → byte-verified count is TWO:
  - PRESENT (line 16): `| `brand_accent` | hex color `#rrggbb` | `"#e94560"` | The coral. Fires sparingly. Coral-budget validator enforces ≤2 per page (cover/CTA: ≤3). |`
  - PRESENT (line 141): `- Coral budget rules (≤2 per page, except ST-01 / ST-03)`
  - NOT PRESENT as `≤2` (line 125): `"4. Test render the canonical Apex fixture **with this new brand_tokens** swapped in. Verify the coral budget validator still passes (1 fire/page is the discipline regardless of client)."` — this is `1 fire/page`, not `≤2`. Different (stricter) rule.
  - NOT PRESENT in merge-defaults comment (lines 47–62 DEFAULTS dict): `"brand_accent":        "#e94560",  # coral` — the comment is just `# coral`, contains no budget rule.
- `research/v7-test/fixture_mw_geva.json` → `design_preferences.coral_budget_per_page` value → CONFIRMED → literal bytes (line 63): `"coral_budget_per_page": 5,`
- `richard-design-system` §1 → "DOES NOT apply to mein_werkzeugkoffer" + 7 firing locations → UNVERIFIABLE → file path `research/idml-spike/richard-design-system/SKILL.md` does not exist on disk this run.
- ROW C1 NET: matrix-claim-broken. (The central claim — coral rule is three-way — partly survives via the CONFIRMED ARCHITECTURE.md and fixture targets, but the "FOUR ≤2 assertions in BRAND_TOKENS.md" count is REFUTED, and the richard-design-system corroboration is UNVERIFIABLE.)

ROW C2
- `dmc-renderer/docs/ARCHITECTURE.md` §7 → raster mode has no DOM AND source-mode fail-soft / non-authoritative → CONFIRMED → literal bytes:
  source mode (lines 180–183): `"1. **Source mode** (cheap, in-process): scan the final rendered HTML for hex colors within ΔE76 < 10 of `brand_accent`. Flag any color other than the literal accent itself. Fail-soft (warning), since CSS-level near-coral is usually intentional brand variation."`
  raster mode (lines 185–189): `"2. **Raster mode** (authoritative, runs on rendered PNG of each page): downsample to 800 px max edge, scan all pixels, find connected regions of coral, count regions with ≥ 50 pixels. **If any page has > 2 coral fires, return HTTP 422.**"`
  Raster mode operates on `rendered PNG of each page` (pixels). No DOM concept. Source mode is explicitly `Fail-soft (warning)`.
- ROW C2 NET: matrix-claim-holds.

ROW C3
- `dmc-renderer/docs/API_CONTRACT.md` → `coral_budget_exceeded` error code row → CONFIRMED → literal bytes (line 477):
  `| **422** | Render produced but failed validation | `coral_budget_exceeded`, `page_count_overflow` |`
  Also literal bytes (line 471): `` `error` is a stable kebab-case code (n8n branches on it). ``
- `dmc-renderer/docs/ARCHITECTURE.md` §8 → "n8n branches on it" phrasing → REFUTED → ARCHITECTURE.md §8 (lines 228–242) does NOT contain the phrase `"n8n branches on it"`. The phrase exists at line 471 of `API_CONTRACT.md` (already CONFIRMED in target 1). ARCHITECTURE.md §8 covers error-code semantics in a table plus a closing paragraph about `traceback_id` and the line `"The renderer NEVER returns 200 with a non-PDF body, and NEVER returns a PDF with a 4xx/5xx code."` — no `n8n branches` text.
- ROW C3 NET: matrix-claim-broken. (The substantive concern — that the `coral_budget_exceeded` code is n8n-coupled — survives via the CONFIRMED API_CONTRACT.md target. The matrix's source-attribution to ARCHITECTURE.md §8 is wrong; the phrase lives in API_CONTRACT.md.)

ROW D1
- `dmc-renderer/docs/BRAND_TOKENS.md` → `brand_neutral_mid` "faintly pink" note → CONFIRMED → literal bytes (line 18):
  `| `brand_neutral_mid` | hex color | `"#7a7a8c"` | Labels, captions, secondary text. **Note:** sometimes reads as faintly pink due to slight purple bias; if the brand wants clearly-neutral gray, use `#3d3d4a` or similar in section labels — handled at template level. |`
- `research/v7-test/fixture_mw_geva.json` → `design_preferences.section_label_style` value → CONFIRMED → literal bytes (line 62): `"section_label_style": "navy_bold",`
- `richard-design-system` §10 → section-label row color → UNVERIFIABLE → file path does not exist this run.
- **FLAGGED-WEAK TARGET:** `research/pattern-spike/design-grammar.md` §2 → navy-bold-not-gray statement → **CONFIRMED** → literal bytes (§2 "Navy vs coral rule for headlines" subsection):
  `"### Navy vs coral rule for headlines"`
  `"- **Display headlines on Outlook/About/Body pages:** NAVY default."`
  `"- **Display headlines on Cover/Fazit/Chapter-divider:** sometimes CORAL or MIXED. Brand call."`
  `"- **Section labels (within body):** NAVY bold (NOT cold gray as v6 used)."`
  `"- **Buchagentur exception:** uses DARK TEAL where others use navy."`
  The third bullet `"Section labels (within body): NAVY bold (NOT cold gray as v6 used)"` is the navy-bold-not-gray statement. The prior-transcript citation was correct. The matrix's flag of "most likely place the matrix is wrong" turns out to be unjustified — the §2 citation HOLDS against the bytes.
- ROW D1 NET: matrix-claim-holds. (3 CONFIRMED including the FLAGGED §2 citation; 1 UNVERIFIABLE due to missing richard-design-system path, but the UNVERIFIABLE target is supplementary corroboration — the main claim is established by the other three.)

ROW D2
- `dmc-renderer/docs/BRAND_TOKENS.md` → "doesn't have a sixth slot" sentence → CONFIRMED → literal bytes (line 123):
  `"1. Inspect the client's brand guide. Map their colors to the 5 brand color slots above. If they have more than 5 distinct brand colors, pick the 5 most-used; the renderer doesn't have a sixth slot."`
- `research/v7-test/fixture_mw_geva.json` → `brand_tokens.brand_secondary_panel` value → CONFIRMED → literal bytes (line 47): `"brand_secondary_panel": "#1F3D6D",`
- `richard-design-system` §1 → two-navys "would collapse this distinction" sentence → UNVERIFIABLE → file path does not exist this run.
- ROW D2 NET: matrix-claim-holds. (Verifiable targets CONFIRMED; UNVERIFIABLE target supplementary.)

ROW E1
- `dmc-renderer/fixtures/apex_consulting_payload.json` → ST-07A `page_numbers` all single → CONFIRMED → literal bytes:
  - slot 6: `"page_numbers": "10"`
  - slot 8: `"page_numbers": "12"`
  - slot 10: `"page_numbers": "14"`
  - slot 12: `"page_numbers": "16"`
  - slot 13: `"page_numbers": "18"`
  All single (no hyphen, no range).
- `research/v7-test/fixture_mw_geva.json` → `meta.export_mode` + single `page_numbers` + one-slot `pages` array → CONFIRMED → literal bytes:
  - line 9: `"export_mode": "single-page",`
  - line 17: `"page_numbers": "14",`
  - `payload.pages` (lines 12–40) contains exactly one slot object.
- ROW E1 NET: matrix-claim-holds.

ROW E2
- `dmc-renderer/docs/API_CONTRACT.md` → ST-type count, no ST-23 → CONFIRMED → byte-verified ST schemas (lines 72–378) enumerate exactly: ST-01, ST-02, ST-03, ST-05, ST-06, ST-07A, ST-07B, ST-09, ST-14, ST-22, ST-FAZIT — eleven types. No ST-23.
- `dmc-renderer/docs/ARCHITECTURE.md` §13 → template list, no `st-23` → CONFIRMED → literal bytes (lines 355–365): templates enumerated as `st-01.html.j2`, `st-02.html.j2`, `st-03.html.j2`, `st-05.html.j2`, `st-06.html.j2`, `st-07a.html.j2`, `st-07b.html.j2`, `st-09.html.j2`, `st-14.html.j2`, `st-22.html.j2`, `st-fazit.html.j2`. Eleven templates. No `st-23`.
- `research/v7-test/design-findings.md` §2 → ST-23 in 12-pattern table → CONFIRMED → literal bytes (line 67): `| **P-11** | Trust Proof — Trustpilot + Logos | ST-23 (new) | STRONG (4/5) |`
- ROW E2 NET: matrix-claim-holds.

ROW E3
- `dmc-renderer/docs/API_CONTRACT.md` → `export_mode` enum + "Reserved for spread" → CONFIRMED → literal bytes (line 39):
  `| `export_mode` | string | yes | `"single-page"` | `"single-page"` = each `page_numbers` segment renders as separate sequential A4 pages (current default). Reserved for `"spread"` (true facing-page rendering) in v1.1. |`
- both fixtures → `meta.export_mode` value → CONFIRMED:
  - `apex_consulting_payload.json` line 8: `"export_mode": "single-page",`
  - `fixture_mw_geva.json` line 9: `"export_mode": "single-page",`
- ROW E3 NET: matrix-claim-holds.

ROW E4
- `dmc-renderer/docs/FONT_LOADING.md` → @font-face Inter 400 line + "Pending" Inter-Regular-not-bundled paragraph + Apex-only rationale → CONFIRMED → literal bytes (three parts present):
  - Inter 400 face mapping (line 16): `| Inter | 400 | normal | `Inter-Regular.ttf` *(to bundle — see § Pending below)* | Google Fonts (SIL OFL 1.1) |`
  - @font-face Inter 400 declaration (lines 45–46): `@font-face { font-family: 'Inter'; font-style: normal; font-weight: 400; src: url('file:///app/fonts/Inter-Regular.ttf') format('truetype'); }`
  - Pending paragraph + Apex-only rationale (lines 28–29): `"### Pending (to add before Phase 3 first ST renders)`
    `- `Inter-Regular.ttf` — currently the palette uses `Inter-700.ttf` as a placeholder for weight 400. This means body sans text (when used) is rendered too heavy. Low priority because the current Apex templates use Serif for body and Inter only for labels/headlines (all of which are 700+)."`
- `richard-design-system` §10 → Folio + URL rows show Inter Regular/400 → UNVERIFIABLE → file path does not exist this run.
- ROW E4 NET: unverifiable-as-noted. (FONT_LOADING.md side of the contradiction CONFIRMED in full; the grammar side requires `richard-design-system` §10 to establish that the grammar specifies Inter 400 for folio/URL, and that target is UNVERIFIABLE this run. The contradiction CANNOT be fully established without the grammar-side citation.)

ROW E5
- `research/v7-test/fixture_mw_geva.json` → `kunde.company_url` AND `brand_tokens.company_url_display` exact strings → **REFUTED** → literal bytes:
  - line 31: `"company_url": "www.gevagmbh.de",` ← PLAIN STRING
  - line 56: `"company_url_display": "www.meinwerkzeugkoffer.de",` ← PLAIN STRING
  Neither value contains markdown-link markup `[...](...)`. The matrix's claim `"kunde.company_url = \"[www.gevagmbh.de](https://www.gevagmbh.de)\" and company_url_display similarly"` is FALSE against the current fixture bytes.
- `dmc-renderer/docs/ARCHITECTURE.md` §6 → preprocess table has no markdown-link rule → CONFIRMED → literal bytes (lines 138–146):
  `| Markdown | HTML |`
  `|---|---|`
  `| `**text**` | `<strong>text</strong>` |`
  `| `*text*` | `<em>text</em>` |`
  `| `\n\n` (double newline) | `</p><p>` (paragraph break) |`
  `| `\n` (single newline) | `<br/>` |`
  Four rules: bold, italic, paragraph break, line break. No `[text](url)` → `<a>` rule.
- apex `company_url` = `""` → CONFIRMED → all five ST-07A slots in apex_consulting_payload.json have `"company_url": ""` (lines 167, 218, 269, 320, 361).
- ROW E5 NET: matrix-claim-broken. **E5's diagnostic premise is FALSE.** The fixture does NOT contain markdown-link markup; there is no broken rendering hazard to fix and no two-part action item to take. The matrix is wrong on this row — most clearly of any row in the audit.

ROW E6
- `dmc-renderer/fixtures/apex_consulting_payload.json` → `page_numbers` for slots 13, 14, 15 verbatim → CONFIRMED → literal bytes:
  - slot 13: `"page_numbers": "18"` (line 333)
  - slot 14: `"page_numbers": "15-16"` (line 372)
  - slot 15: `"page_numbers": "17-18"` (line 422)
  slot 14's `lo=15` is less than slot 13's `last_hi=18` → monotonicity violated. slot 15's `lo=17, hi=18` overlaps both prior ranges.
- `dmc-renderer/docs/ARCHITECTURE.md` §5 → `assert_monotonic` + `total_pages` code → CONFIRMED → literal bytes:
  `total_pages` (lines 94–104):
  `def total_pages(payload):`
  `    total = 0`
  `    for page in payload["pages"]:`
  `        pn = page["page_numbers"]   # "1" or "2-3" or "16-17"`
  `        if "-" in pn:`
  `            lo, hi = map(int, pn.split("-"))`
  `            total += hi - lo + 1`
  `        else:`
  `            total += 1`
  `    return total`
  `assert_monotonic` (lines 117–125):
  `def assert_monotonic(payload):`
  `    last_hi = 0`
  `    for page in payload["pages"]:`
  `        pn = page["page_numbers"]`
  `        lo, hi = (int(x) for x in (pn.split("-") if "-" in pn else (pn, pn)))`
  `        if lo <= last_hi:`
  `            warnings.warn(f"page_numbers collision at slot {page['slot']}: {pn} <= prev {last_hi}")`
  `        last_hi = hi`
- `dmc-renderer/docs/ARCHITECTURE.md` §13 → `test_render_apex.py` "20-page" assertion text → CONFIRMED → literal bytes (line 395):
  `"End-to-end test (`test_render_apex.py`) loads the canonical Apex fixture and asserts the full 20-page PDF renders without any validator failures."`
- ROW E6 NET: matrix-claim-holds. (Confirmed: canonical Apex fixture is internally inconsistent on page numbering. `total_pages` would compute slot 14 as `15→16=2 pages` + slot 15 as `17→18=2 pages` on top of slot 13 already declaring `18`, double-counting page 18. `assert_monotonic` would fire at slot 14 (`lo=15 ≤ last_hi=18`) and again at slot 15 (`lo=17 ≤ last_hi=16` — actually `lo=17` vs `last_hi=16` is `lo > last_hi` so slot 15 alone is monotonic; the violation is slot 14 vs slot 13). The matrix's diagnostic is real.)

### F-SECTION ACKNOWLEDGEMENTS

F1, F2, F3 have no CC-VERIFY lines. Spot-verified the underlying claims this run:
- F1: `FONT_ALIASES["Source Serif Pro"] = "Source Serif 4"` referenced in BRAND_TOKENS.md (lines 107–110) and apex fixture sends `"font_body": "Source Serif Pro"` (line 501); GEVA fixture sends `"font_body": "Source Serif 4"` (line 53). Both resolve to `SourceSerif4-Regular.ttf` bundled per FONT_LOADING.md (line 20). Aligned. ACK holds.
- F2: covered by E3 verification.
- F3: FONT_LOADING.md line 22 confirms `SourceSerif4-Bold.ttf` bundled (`**v6.1 addition**`); lines 99–114 describe the v6 → v6.1 fix. ACK holds.

### ADVERSARIAL PASS

**Pass scope (per prompt):** one bounded pass on three explicit checks only. No open investigation.

1. **`richard-pattern-confirmation.md` movement on B4 / E2 / Contradiction-1 anti-pattern override.**
   File present on disk at `research/v7-test/richard-pattern-confirmation.md`. Byte-verified content this run: the file is the QUESTIONNAIRE sent TO Richard (Q1–Q16 + the brand-axis ask). It does NOT contain Richard's ANSWERS. The questions about case-study geometry per brand (Q6, Q7), Trust Proof optionality (Q12), and anti-pattern override / "do you ever break this rule" (Q15) are present, but no responses from Richard have been recorded. **BLOCKED-ON-RICHARD rows remain blocked.** I did not infer Richard's answers. I did not guess geometry-per-brand. Adversarial pass step 1: no movement, by rule.

2. **Hold `design-grammar.md` (full) against D1/D2 once. Fourteenth contradiction of the same class?**
   Scanned design-grammar.md §1–§7 byte-fresh. Looking for a contract-vs-grammar contradiction (contract doc asserts X, grammar doc asserts not-X, both byte-quoted) that is NOT already captured in rows A1–E6.
   Candidates considered and dismissed (each because it's either already captured or not a contradiction):
   - §6 #12 anti-pattern (pure-white bg) — already explicitly acknowledges Apex breaks this; design-grammar.md itself self-flags the exception, so no contradiction with the contract.
   - §6 #13 (running per-page footer CTAs) — contract docs are silent on @page CTAs; no asserted X in contract to contradict.
   - §6 #15 (mixing case-study geometries) — same fault line as A1/B4 (case_study_geometry seam); already captured.
   - §7 axes (page_format spread vs single, photography_intensity, trust_proof_variant, etc.) — same fault line as A1 (design_preferences seam); already captured for the rows in question. Spread-vs-single specifically is E1.
   - §3 "3-3-3 system" — FONT_LOADING.md bundles exactly 3 families (Inter, Source Serif 4, Vollkorn); aligned, no contradiction.
   - §1 "7-act narrative arc" + ST count — design-grammar.md §1 mentions 11 STs map to the 7-act arc; ST-23 is in design-findings.md/pattern-spike but NOT in design-grammar.md §1's claim of 11. Same fault line as E2.
   **Result: no fourteenth contradiction found.** Not manufacturing one. Stopping the pass here.

### FINAL SUMMARY

CC verification complete. Rows holding: 13 (A1, A2, B1, B2, B3, B5, C2, D1, D2, E1, E2, E3, E6). Broken: 4 (B4, C1, C3, E5). Unverifiable: 1 (E4 — grammar side blocked by missing richard-design-system path).

Proposed deltas: none from CC. Five author-errors-observed surfaced above for Utkarsh to correct at the matrix source: (1) "13 rows" count error; (2) B4 fabricated filename citation; (3) C1 "FOUR ≤2 assertions" should be TWO; (4) C3 phrase attributed to wrong doc (lives in API_CONTRACT.md, not ARCHITECTURE.md §8); (5) E5 fixture-content claim REFUTED — fixture has plain strings, not markdown-link markup, so E5's entire diagnostic premise is FALSE.

Path-resolution issue surfaced: `research/idml-spike/richard-design-system/SKILL.md` does not exist; 4 targets across C1, D1, D2, E4 are UNVERIFIABLE this run. Not searched for substitute per user rule.

No rows ratified. BLOCKED-ON-RICHARD rows (Contradiction-1, B4 per-brand binding, E2 Q12) untouched — `richard-pattern-confirmation.md` is the questionnaire, not Richard's answers; the rows wait on Richard.

## PATH-RESOLUTION RE-VERIFICATION (C1/D1/D2/E4 targets)

Re-verification of the four targets that were UNVERIFIABLE in the prior log solely because the asserted path `research/idml-spike/richard-design-system/SKILL.md` was missing the `/skills/` segment. Corrected path resolved this run: `research/idml-spike/skills/richard-design-system/SKILL.md` — file exists, read byte-fresh this run. Authorization scope from BLOCK 2: one directory enumeration + this one file; no substitute search performed.

**C1 TARGET 4** — richard-design-system §1: "≤1 per page" rule extracted from aerztepartner + DOES NOT apply to mein_werkzeugkoffer + firing-locations list → **CONFIRMED** → literal bytes (SKILL.md lines 28–35):

```
- **REVISED:** Coral fires **multiple times per page** in mein_werkzeugkoffer, with intention. The discipline is "use coral where it earns its place" — kicker stamps, callout panels, CTA buttons, URL highlights, attribution labels. The earlier "≤1 per page" rule was extracted from aerztepartner and DOES NOT apply to mein_werkzeugkoffer. For Apex, treat coral as the **primary editorial-system color** with these legitimate firing locations:
  - FALLSTUDIE stamp box (border + text, ~once per case page)
  - Oversized opening quote glyph "
  - Callout panel fills (e.g. "Fakt ist:", "Hast du noch Fragen?")
  - CTA button fills + URL text
  - Editorial-hook display headlines (cover, opener, major chapters — NOT case-study body headlines)
  - Attribution text below pullquote
  - Coral micro-headers on body callout rows ("Mehr Übersicht bei Planung")
```

Both halves of the C1#4 target are present: (a) the "≤1 per page" rule is explicitly named as extracted-from-aerztepartner and stated as "DOES NOT apply to mein_werkzeugkoffer"; (b) a seven-item firing-locations list follows immediately after. Note for the record: this list is SEVEN locations (FALLSTUDIE stamp, opening quote glyph, callout panel fills, CTA button fills + URL text, editorial-hook display headlines, attribution text, coral micro-headers) — the prior matrix language calling it "7 locations" matches the bytes. Note also that §9 (anti-patterns) line 236 still carries the older bullet "No more than one coral moment per page" — this is the aerztepartner-extracted rule §1 explicitly invalidates for mw. Same fossil identified in C1's [AUTHOR-ERROR-3 CORRECTED] disposition; same instruction stands (STRUCK on ratification, not reconciled).

**D1 TARGET 3** — richard-design-system §10: section-label row color (must show display-navy, NOT gray) → **CONFIRMED** → literal bytes (SKILL.md line 245, §10 type system table row):

```
| **Section labels** | Same family | Bold (700) | ~10pt | normal | Display navy `#1A2540` |
```

Color column reads `Display navy `#1A2540`` for the Section labels row. Not gray. Confirms D1's claim that section labels are navy-bold per grammar.

**D2 TARGET 3** — richard-design-system §1: two-navys "would collapse this distinction" sentence → **CONFIRMED** → literal bytes (SKILL.md line 26):

```
- The two navys (`#1A2540` display, `#1F3D6D` panel) are deliberately at different tonal positions. The display navy is darker, close to near-black; the panel navy is mid-value. Putting them at slightly different tonal positions prevents visual competition: body text and pullquote don't fight for primacy, because they read as distinct depths. Treating them as "the same navy" in implementation would collapse this distinction.
```

The phrase `"would collapse this distinction"` appears verbatim in the final sentence. Two distinct hex values (`#1A2540` display, `#1F3D6D` panel) are named with their tonal-position rationale, supporting D2's claim that brand_secondary_panel must exist as a sixth slot independent of brand_primary.

**E4 TARGET 2** — richard-design-system §10: Folio row AND URL/meta row both show Inter Regular / weight 400 → **CONFIRMED** → literal bytes (SKILL.md §10 type system table, lines 251–252):

```
| **Folio** | Same sans | Regular | ~9pt | normal | Mid gray `#8C8C8C` |
| **URL / meta** | Same sans | Regular | ~7pt | normal | Mid gray `#8C8C8C` |
```

Both rows show `Regular` in the Weight column. `Regular` = 400 in the OpenType convention. "Same sans" refers back to the Display headline row (line 244), which names the family as `Source Sans 3 / Inter (HIGH confidence sans-serif geometric grotesque)` — i.e., when the renderer chooses Inter for the sans family, Folio and URL/meta resolve to Inter Regular / 400. E4's claim that the grammar requires Inter 400 for Folio + URL holds against the bytes. This now closes the contradiction E4 originally flagged: FONT_LOADING.md does NOT bundle Inter-Regular.ttf (CONFIRMED prior); grammar §10 DOES specify Regular weight for Folio and URL (CONFIRMED now). Both halves established. E4's diagnostic stands.

### NET CHANGES TO PRIOR LOG SUMMARY

All four previously-UNVERIFIABLE targets now CONFIRMED. Applying these results to the prior NET tallies:

- C1: previously matrix-claim-broken (one REFUTED, one UNVERIFIABLE, two CONFIRMED). The UNVERIFIABLE is now CONFIRMED. The REFUTED ("FOUR ≤2 assertions") was addressed by the BLOCK 1 [AUTHOR-ERROR-3 CORRECTED] revision. Updated NET (this verification run): the C1 row's claims are now fully supported by bytes after the author correction.
- D1: previously matrix-claim-holds (3 of 4 verified, including the FLAGGED §2 target). The UNVERIFIABLE §10 target is now CONFIRMED. D1 NET (this verification run): all four CC-VERIFY targets CONFIRMED.
- D2: previously matrix-claim-holds (2 of 3, 1 UNVERIFIABLE). The UNVERIFIABLE §1 target is now CONFIRMED. D2 NET (this verification run): all three CC-VERIFY targets CONFIRMED.
- E4: previously unverifiable-as-noted (FONT_LOADING.md CONFIRMED, grammar side UNVERIFIABLE). Grammar side now CONFIRMED. E4 NET (this verification run): both targets CONFIRMED; contradiction fully established (FONT_LOADING.md does not bundle Inter-Regular AND grammar requires Inter 400 for Folio + URL).

These updates are recorded here in the append-only log; row NET tallies in the matrix proper are not edited. No rows ratified; the ratification step is the user's, and per the standing rule the verifier does not touch RATIFICATION lines.

================================================================
## STEP 0 RATIFICATION RECORD (Utkarsh, proceeding without Richard)

Transcription of decisions made by Utkarsh. Recorded here per Phase 2 of the STEP 0 close-out plan. No row content above is edited; ratification is recorded in this appended section rather than by editing inline RATIFICATION lines. Verifier holds no decision authority; this is transcription only.

### RATIFIED — proceed now (not dependent on Richard)

A1 — design_preferences stays INSIDE brand_tokens; renderer grows a
     design_preferences ingestion path; BRAND_TOKENS.md "no nested
     merge" sentence to be struck in the contract-doc edit pass.

A2 — absence of design_preferences → documented "apex" default profile
     (RRW geometry, initials block, 3-up metrics, coral count-budget
     {ST-01:3,ST-03:3,_default:2}, single-page). Absence is NOT a 400.

B1 — ST-07A splits by geometry. LRP: ergebnis_metrics optional, may
     be []. RRW/Apex: required, 3 items, coral-first.

B2 — LRP gets NEW structured field `callout_row` = list of {text};
     PARSED, never markdown-preprocessed; wendepunkt removed from §6
     preprocess list for LRP. GEVA fixture re-transcribed to array in
     Phase 4.

B3 — LRP schema adds `ziel` (required, preprocessed prose). RRW/Apex
     omits it.

B5 — LRP gets a case-study image slot; fetcher accepts file:// (test)
     + https:// (prod). file:// reasoning struck per AUTHOR-ERROR-6;
     verdict stands on contract-has-no-slot alone.

C1 — coral budget per-brand-overridable from
     design_preferences.coral_budget_per_page; default = count budget
     when absent. Apex = count. mw/GEVA = budget 5, location-legitimacy
     validated. "1 fire/page" line is the aerztepartner fossil —
     STRUCK, not reconciled.

C2 — two validation paths: count-rule brands (Apex) raster-side;
     location-rule brands (mw) DOM-side; selected by
     design_preferences presence.

C3 — error code stays "coral_budget_exceeded" regardless of internal
     rule (preserve n8n branch). Any code change = flagged pipeline
     edit, not renderer-only.

D1 — section-label color driven by
     design_preferences.section_label_style; brand_neutral_mid is
     folio/URL/caption only.

D2 — add brand_secondary_panel as a 6th optional color slot; defaults
     to brand_primary when absent.

E1 — STEP 2 builds single-page. Spread is a future ADDITIVE variant,
     not a rebuild.

E3 — export_mode keeps layout meaning; print intent → NEW field
     meta.print_profile {offset,digital,online,none}, default none.

E4 — Inter-Regular (weight 400) bundled BEFORE STEP 2 ships; moves
     from "Pending/low" to STEP 2 prerequisite.

E6 — apex_consulting_payload.json marked "page-numbers known-broken;
     content-shape reference only" — NOT re-transcribed (recorded
     defect, out of scope).

### PARKED — explicitly deferred, NOT guessed (Richard / later phase). Build proceeds around these via the chassis toggle.

ANTI-PATTERN OVERRIDE (rounded corners / drop shadows) — PARKED.
  Built as a chassis-level runtime toggle (Phase 3). Default = HARD
  (Richard's observed grammar: none). Richard's eventual answer flips
  the toggle; NO rebuild.

B4 per-brand geometry binding — PARKED. STEP 2 uses LRP for GEVA
  (data-decided); whether LRP is fixed-per-brand waits on Richard.

E2 ST-23 Trust Proof optionality — PARKED. Not exercised by STEP 2.

================================================================
## CONTRACT-DOC EDIT LIST (deferred to post-chassis, recorded so the next agent cannot re-derive the conflict)

This is a RECORDED TODO list of contract-doc edits implied by the RATIFIED rows above. NOT an instruction to edit those docs in this run. The contract-doc edit pass is deferred to a later phase after the chassis is built and approved.

- BRAND_TOKENS.md strike "no nested merge"
- BRAND_TOKENS.md add 6th color slot + design_preferences sub-schema
- API_CONTRACT.md ST-07A split LRP vs RRW + add ziel/callout_row to LRP + add case-study image slot
- API_CONTRACT.md/ARCHITECTURE.md add meta.print_profile
- ARCHITECTURE.md §6 remove wendepunkt-for-LRP from preprocess
- ARCHITECTURE.md §7 CORAL_BUDGET → design_preferences lookup
- FONT_LOADING.md Inter-Regular bundled

================================================================
## RICHARD-PRIMARY RE-RATIFICATION 2026-05-18

Context: user ruling 2026-05-18 — Richard's current spec docs (in `files from richard/` folder) are SOURCE OF TRUTH over the Apex contract, the matrix, the chassis, and SKILL.md. v1/Old*/SKILL.md are DEAD; do not cite. The five live primary docs are:
  - `01_DMC_Master_System_v1.md` (Master rules)
  - `08_DMC_Design_System_v2.md` (Design philosophy + corrections to v1)
  - `DMC_InDesign_Spec_v1.md` (treated as LIVE — only version exists, cited by v2)
  - `04_DMC_Copy_Masterbook_v3.md` (Copy mechanics)
  - `05_DMC_Intelligence_Layer_v4.md` (Copy intelligence)

Re-tier scheme: HARD (input gates, FIXED slots, absolute Verbote), SOFT (tolerance ranges, derived from content/character-limits), VARIATION (per-brand designer's eye).

Append-only: existing rows above are NOT edited. Each row below cites a verbatim line from a current doc (with chunk reference from TASK-0 coverage). A row with NO verbatim citation is marked HELD, not flipped.

---

ROW A1 — design_preferences ingestion
  OLD tier: DATA-DECIDED (matrix-grade hard rule)
  NEW tier: HELD — claimed by prior audit, unverified
  REASON: No upstream pipeline doc shows a `design_preferences` object. The closest upstream is Master System Modul 4.1 `design{primaerfarbe_hex, akzentfarbe_hex, logo_vorhanden, autorenfoto_vorhanden}` (chunk 1 lines 228-233). That is the ENTIRE upstream design surface. The matrix's `design_preferences` object is renderer-side architecture, not grounded.
  CITATION: `01_DMC_Master_System_v1.md` chunk 1 L228-233 (verbatim):
    ```
    "design": {
      "primaerfarbe_hex": "[Hex aus Kunden-CD]",
      "akzentfarbe_hex": "[Hex]",
      "logo_vorhanden": true,
      "autorenfoto_vorhanden": true
    },
    ```
  NEW VALUE: brand_tokens upstream payload exposes ONLY the 4 fields above. Renderer must derive everything else (neutrals, fonts, geometry, panel-navy, etc.) from production-side curation per v2 Design System C.1 ("Die Farbpalette kommt von uns — nicht vom Kunden"). HELD pending user ruling on whether to keep `design_preferences` as a renderer-internal artifact or remove it.

ROW A2 — apex default profile
  OLD tier: USER-RULES
  NEW tier: STRUCK
  REASON: The "apex" default profile carried Apex-contract values (Inter font, Source Serif Pro body, navy_bold section labels). Richard is now primary; the "apex default" is no longer the default. Richard's defaults are: Montserrat/Source Sans Pro fonts, #333333 body color, accent-OR-darkgray section labels.
  CITATION: `DMC_InDesign_Spec_v1.md` L484-489 (verbatim):
    ```
    PRIORITÄT 2 — Empfohlene Systemschriften:
    Headlines:  Montserrat (ExtraBold, Bold, SemiBold)
    Fließtext:  Source Sans Pro (Regular, SemiBold, Bold, Italic)
    ```
  AND L243: `Farbe:                 #333333 (Dunkelgrau, nicht Schwarz)` (body color)
  AND L223 (H2 section labels): `Farbe:                 Primärfarbe ODER Dunkelgrau (#333333)`
  AND L224 (H3 section labels): `Farbe:                 Akzentfarbe ODER Dunkelgrau`
  NEW VALUE: `APEX_DEFAULT_PROFILE` renamed to `RICHARD_DEFAULT_PROFILE` with values from cited lines. Apex tier (if needed) becomes a separate brand-variant override, NOT the default.

ROW B2 — wendepunkt → callout_row
  OLD tier: DATA-DECIDED (LRP gets parsed callout_row)
  NEW tier: STRUCK
  REASON: `wendepunkt` in Richard's schema is a SINGLE-SENTENCE narrative pivot ("DER eine Moment der alles veränderte"), not a 2×2 callout grid. The grid interpretation was a GEVA-fixture-specific reading of pipe/newline shorthand; not in Richard's spec.
  CITATION: `01_DMC_Master_System_v1.md` chunk 1 L184-189 (Briefing schema):
    ```
    "wendepunkt": "[DER eine Moment der alles veränderte]",
    ```
  AND `05_DMC_Intelligence_Layer_v4.md` chunk 2 L517-520 (Fallstudien-Vorlage):
    ```
    WENDEPUNKT (1-2 Sätze):
    Der eine Moment oder die eine Entscheidung die alles verändert hat.
    → Dieser Satz ist das Herz der Fallstudie. Konkret und unvergesslich.
    ```
  NEW VALUE: `wendepunkt` is preprocessed prose (1-2 sentences), NOT a structured grid. The 2×2 callout-row concept is removed from the schema. The mid-body callout-row visual element seen on mw_p14 is the §5c Coral micro-header callout — driven by DIFFERENT content, not by wendepunkt. preprocess.parse_callout_row() function is dead code.

ROW B3 — ziel required for LRP
  OLD tier: DATA-DECIDED
  NEW tier: HELD — claimed by prior audit, unverified
  REASON: Master System Briefing schema (chunk 1 L179-193) lists Fallstudien fields as `name_pseudonym, kurzportraet, ausgangsproblem, wendepunkt, loesung_skizze, ergebnis_vorher, ergebnis_nachher, zeitraum`. No explicit `ziel` field. Intelligence Layer Fallstudien-Vorlage shows body sections: Kurzporträt → PROBLEM → WENDEPUNKT → LÖSUNG → ERGEBNIS — no ziel section. Aerztepartner brand-variant in v2 Design System uses Ausgangslage → Ziel → Lösung → Ergebnis but that's a brand-specific composition.
  CITATION: `01_DMC_Master_System_v1.md` chunk 1 L179-193 (verbatim schema, no `ziel` field).
  NEW VALUE: HELD. ziel is not a Pflicht-field in Richard's master schema. It MAY be a brand-variant body section header (aerztepartner uses it) but is not universal. Drop B3's "required" status; ziel becomes optional brand-variant text.

ROW C1 — coral budget per-brand override (count-based)
  OLD tier: USER-RULES (count-rule + location-rule two paths)
  NEW tier: STRUCK
  REASON: Richard's actual coral rule is AREA-based + LOCATION-based, never count-based. The count-cap is an Apex/n8n artifact with no source-of-truth grounding.
  CITATION: `08_DMC_Design_System_v2.md` L162 (verbatim):
    ```
    Akzentfarbe → Highlights, Zahlen, Icons, sparsam eingesetzt (max. 10% Flächenanteil pro Seite)
    ```
  AND `01_DMC_Master_System_v1.md` Modul 6 / §1 firing-locations list (chunks 1-2): coral fires at specific named locations (kickers, panel fills, oversized quote glyphs, URLs, CTA fills, attribution labels, stamp boxes, callout-row micro-headers).
  NEW VALUE: Coral validator = AREA (≤10% of page surface) + LOCATION (allowed places only). Drop `coral_budget_per_page` from design_preferences. Drop `APEX_CORAL_COUNT_BUDGET` dict. Drop the two-path selection seam — there's only one rule. Error code stays `coral_budget_exceeded` for n8n compatibility but its meaning becomes "area-or-location violation."

ROW D1 — section labels navy bold
  OLD tier: DATA-DECIDED
  NEW tier: STRUCK
  REASON: Richard's InDesign Spec H3 and H2 explicitly state Akzentfarbe OR Dunkelgrau (#333333). Navy is permitted but NOT mandated.
  CITATION: `DMC_InDesign_Spec_v1.md` L224 (H3_Zwischentitel, verbatim):
    ```
    Farbe:                 Akzentfarbe ODER Dunkelgrau
    ```
  AND L206 (H2_Subheadline):
    ```
    Farbe:                 Primärfarbe ODER Dunkelgrau (#333333)
    ```
  NEW VALUE: Section labels are H2/H3 Inter-style bold (Montserrat SemiBold per Richard) at the sizes cited, with color = Akzentfarbe OR Dunkelgrau. Drop the `section_label_style: "navy_bold"` design_preferences field. The renderer picks accent or #333333 based on per-page composition / hierarchy; not a global brand_tokens decision.

ROW D2 — brand_secondary_panel (6th color slot)
  OLD tier: DATA-DECIDED
  NEW tier: STRUCK
  REASON: Richard's color model is THREE colors max: Primärfarbe + Akzentfarbe + Neutral. No "panel navy" / second navy as a separate token. The two-navys distinction (#1A2540 display, #1F3D6D panel) was a renderer-side fabrication from one specific GEVA-page observation.
  CITATION: `08_DMC_Design_System_v2.md` C.2 L156-163 (verbatim):
    ```
    ## C.2 Drei-Farben-Regel

    Pro Report maximal 3 Designfarben plus Neutral-Weiß/Grau.

    **Warum:** Mehr Farben wirken billig, unentschlossen und überladen. Luxus entsteht durch Zurückhaltung.

    **Die Drei:**
    - Primärfarbe → dominante Farbe, Headlines, CTA-Elemente, Akzentflächen
    - Akzentfarbe → Highlights, Zahlen, Icons, sparsam eingesetzt (max. 10% Flächenanteil pro Seite)
    - Neutral → Fließtext-Farbe, Hintergrundflächen, Trennelemente
  ```
  AND `01_DMC_Master_System_v1.md` chunk 1 L228-233 (Briefing design schema has ONLY primaerfarbe_hex + akzentfarbe_hex — no second-color slot).
  NEW VALUE: Drop `brand_secondary_panel` from BrandConfig and APEX_DEFAULT_PROFILE. Pullquote panel fill = primärfarbe (or a TINT of primärfarbe if extra depth needed — derived, not a separate token).

ROW [NEW] BLEED — page bleed
  NEW tier: HARD
  REASON: Print bleed is a print-spec hard rule across all Richard docs.
  CITATION: `DMC_InDesign_Spec_v1.md` L26-29 (verbatim):
    ```
    Anschnitt oben:        3 mm
    Anschnitt unten:       3 mm
    Anschnitt innen:       3 mm
    Anschnitt außen:       3 mm
    ```
  NEW VALUE: @page rules must declare `bleed: 3mm` (or size A4 with explicit 3mm bleed margins). Currently `patterns/st_07a.py` L297 has `margin: 10mm 10mm 10mm 10mm` and NO bleed declaration. Structural fix required.

ROW [NEW] MARGINS — page margins
  NEW tier: SOFT (Richard explicitly downgraded these from HARD in v2)
  REASON: v2 explicitly says margins emerge from character limits, not hard mm values.
  CITATION: `08_DMC_Design_System_v2.md` L15-16 (verbatim):
    ```
    **Falsch:** Exakte Randmaße und Spaltenbreiten als harte Vorgaben
    **Richtig:** Maße ergeben sich aus Zeichenlimits der Copy und Lesbarkeits-Anforderungen (siehe Teil B).
    ```
  REFERENCE BASELINE (from InDesign Spec L40-43, treated as SOFT defaults not HARD requirements):
    ```
    Oben (Top):            16 mm
    Unten (Bottom):        20 mm
    Innen (Inside/Bund):   18 mm
    Außen (Outside):       14 mm
    ```
  NEW VALUE: Chassis @page uses asymmetric margins ~16/20/18/14 as starting point, adjustable per character-density needs. The current 10mm symmetric is wrong on both axes.

ROW [NEW] BODY-COLOR — body text color
  NEW tier: HARD
  CITATION: `DMC_InDesign_Spec_v1.md` L243 (verbatim, in Body_Text style):
    ```
    Farbe:                 #333333 (Dunkelgrau, nicht Schwarz)
    ```
  NEW VALUE: body text color = `#333333`. NOT `var(--brand-primary)` (display navy). Section labels are separate and per ROW D1 use Akzentfarbe OR Dunkelgrau.

ROW [NEW] BODY-FONT — body font family
  NEW tier: VARIATION (customer-font priority 1) with HARD fallback
  CITATION: `DMC_InDesign_Spec_v1.md` L479-489 (verbatim):
    ```
    PRIORITÄT 1 — Kunden-eigene Schrift:
    Wenn vorhanden: Diese verwenden für Headlines UND Fließtext.

    PRIORITÄT 2 — Empfohlene Systemschriften:
    Headlines:  Montserrat (ExtraBold, Bold, SemiBold)
    Fließtext:  Source Sans Pro (Regular, SemiBold, Bold, Italic)
    ```
  NEW VALUE: Body fallback = Source Sans Pro Regular. Headlines fallback = Montserrat (ExtraBold/Bold/SemiBold). Inter + Source Serif 4 are NOT Richard's defaults. Customer-font, when present, overrides.

ROW [NEW] BODY-LAYOUT — column count + alignment + indent
  NEW tier: HARD (column count + alignment) / SOFT (column-width mm)
  CITATION: `DMC_InDesign_Spec_v1.md` L53-65 (verbatim):
    ```
    Standard-Raster:       2 Spalten
    Spaltenabstand:        6 mm
    Spaltenbreite:         (Textbreite - 6mm) / 2 = ca. 84 mm
    ```
  AND L244 (Body_Text alignment):
    ```
    Ausrichtung:           Blocksatz mit Silbentrennung (Standard)
    ```
  AND L246: `Silbentrennung:        EIN (mindestens 5 Zeichen, 2-2 Minimum)`
  AND L273 (Body_Text_Einzug after first paragraph):
    ```
    Einzug erste Zeile:    4 mm
    ```
  NEW VALUE: Body uses 2-column layout (~84mm each, 6mm gutter), Blocksatz (justified) with auto-hyphenation, 4mm first-line indent on paragraphs after the first (Body_First for first paragraph = no indent, Body_Text_Einzug for subsequent = 4mm). Currently the chassis renders single-column left-aligned no-indent body. **Structural — flagged.**

ROW [NEW] PULLQUOTE-SIZE — pullquote font size
  NEW tier: SOFT (tolerance range)
  CITATION: `DMC_InDesign_Spec_v1.md` L285 (verbatim, Pullquote style):
    ```
    Größe:                 17–20 pt
    ```
  NEW VALUE: Pullquote = 17–20pt. Currently chassis has `font-size: 10pt` (L395 of st_07a.py) — that's ~half Richard's spec.

ROW [NEW] HEADLINE-SIZE — H1 page headline
  NEW tier: SOFT (tolerance range)
  CITATION: `DMC_InDesign_Spec_v1.md` L183 (verbatim, H1_Seitenheadline):
    ```
    Größe:                 28–40 pt (je nach Textmenge, Standard: 32 pt)
    ```
  NEW VALUE: Headline 28–40pt, default 32pt. Currently 24pt — below range.

ROW [NEW] PAGE-COUNT — pages divisible by 4
  NEW tier: HARD
  CITATION: `01_DMC_Master_System_v1.md` chunk 2 L856-857 (verbatim, slot plan rules):
    ```
    - Regel: NUR 16/20/24/28 — immer 4er-Schritte (Druckbögen)
    ```
  AND `DMC_InDesign_Spec_v1.md` L17: `Seiten:                20 (Standard) | 16 | 24 | 28`
  NEW VALUE: Renderer must validate page_count ∈ {16, 20, 24, 28}.

ROW [NEW] CTA-CADENCE — soft/mid/hard CTA positions
  NEW tier: HARD
  CITATION: `01_DMC_Master_System_v1.md` chunk 2 L818 (verbatim):
    ```
    **CTA-Kadenz:** S2 (Soft im Ausblick), S9 (Mid nach Mechanismus), S18 (Mid Einladung), S20 (Hard)
    ```
  NEW VALUE: Renderer validates that ST-02 carries soft-CTA hint, ST-06's facing page (S9) carries mid-CTA, ST-08 Einladung (S18) carries mid-CTA, ST-03 (S20) carries hard-CTA. Chassis doesn't enforce this yet.

ROW [NEW] ATEMSEITE-RHYTHM — breathing-page cadence
  NEW tier: HARD (rhythm constraint) + SOFT (exact placement)
  CITATION: `01_DMC_Master_System_v1.md` chunk 2 L745 (verbatim, ST-32):
    ```
    **Einsatz:** Alle 5–7 Seiten maximal eine. **NIEMALS** direkt nach einer anderen Atemseite.
    ```
  NEW VALUE: Atemseite (ST-32) placed every 5-7 pages, max 15 words. Renderer cannot place two Atemseiten adjacent.

ROW [NEW] DOPPELSEITEN-COUNT — doublespread budget per report
  NEW tier: SOFT (target ~2 per 20-page report)
  REASON: Replaces my prior-audit's wrong claim of "5 mandated doublespreads". Real number is ~2 thematic doublespreads; case studies stay single-page.
  CITATION: `08_DMC_Design_System_v2.md` D.3 L201-202 (verbatim):
    ```
    **Zwei Doppelseiten pro 20-Seiten-Report** (als Richtwert). Das sind keine Fallstudien-Doppelseiten, sondern thematisch zusammengehörende Spreads.
    ```
  AND L209-210:
    ```
    Fallstudien-Logik im Spread:
    Die Fallstudie steht auf einer Einzelseite. Die gegenüberliegende Seite ist eine eigenständige Seite die das Warum des Ergebnisses erklärt — ohne Rückbezug auf die Fallstudie.
    ```
  NEW VALUE: 2 thematic doublespreads per 20-page report (Mechanism+Diagramm, Numbers+Kompetenz typical). Case studies (ST-07A) remain single-page; their facing Gegenseite (ST-07B) is an INDEPENDENT page, not a design-unit doublespread.

ROW [NEW] BODY-BOLD-FAMILY — same-family bold
  NEW tier: HARD
  CITATION: `DMC_InDesign_Spec_v1.md` L407 (verbatim, Character Style Fett_Hervorhebung):
    ```
    Schrift:   Fette Variante des laufenden Fonts
    ```
  NEW VALUE: Body bold = bold variant of body font family. If body is Source Sans Pro Regular, body bold is Source Sans Pro Bold. NO cross-family substitution (no Inter-Bold inside Source-Serif body, no Source-Serif-Bold inside Source-Sans body). Confirms F3.

ROW [NEW] WHITESPACE — minimum white-space per page
  NEW tier: HARD
  CITATION: `08_DMC_Design_System_v2.md` D.1 L180 (verbatim):
    ```
    Mindestens 20% jeder Seite ist frei — kein Text, kein Bild, keine Grafik.
    ```
  NEW VALUE: Renderer must validate ≥20% empty pixel ratio per page (post-rasterization check).

ROW [NEW] COLOR-COUNT — max 3 design colors per report
  NEW tier: HARD
  CITATION: `08_DMC_Design_System_v2.md` C.2 L156 (verbatim):
    ```
    Pro Report maximal 3 Designfarben plus Neutral-Weiß/Grau.
    ```
  NEW VALUE: Across the entire report, design colors used ≤ 3 (primary + accent + neutral). Validator: distinct-hue-cluster count ≤3 across all pages.

ROW [NEW] PDFX-CMYK — print export profile
  NEW tier: HARD
  CITATION: `08_DMC_Design_System_v2.md` H.1 L365-371 (verbatim):
    ```
    **Dateiformat:** PDF/X-3 oder PDF/X-4
    **Farbprofil:** ISO Coated v2 300% (Euroscale Coated)
    **Auflösung:** Min. 300 dpi für Bilder bei Endgröße
    **Anschnitt:** 3 mm
    **Schriften:** Eingebettet oder in Kurven
    **Schwarzer Text:** K=100 (kein Komposit-Schwarz)
    **Seitenanzahl:** Durch 4 teilbar
    ```
  NEW VALUE: Print export = PDF/X-3 or PDF/X-4, ISO Coated v2 300% (FOGRA39), 300 dpi images, 3mm bleed, embedded fonts, K=100 black text.

ROW [NEW] NO-ROUNDED-EXCEPT-CTA — anti-pattern #1 narrowed
  NEW tier: HARD (with one named exception)
  REASON: My prior-audit "no rounded corners anywhere" was over-extrapolated. v2 Design System is silent on rounded corners; InDesign Spec explicitly permits 2–3mm on CTA boxes only.
  CITATION: `DMC_InDesign_Spec_v1.md` L549-552 (verbatim, Textrahmen_CTA_Box):
    ```
    Textrahmen_CTA_Box:
      Einzüge:      6 mm alle Seiten
      Hintergrund:  Primärfarbe
      Textfarbe:    Weiß
      Ecken:        Optional leicht abgerundet (2–3mm)
    ```
  NEW VALUE: Default = no rounded corners on any text container. EXCEPTION: CTA boxes (.cta-box class) may have 2–3mm border-radius optionally. Drop the ANTIPATTERN_MODE BRAND_PREF toggle — it was solving the wrong problem (per-brand override). The right answer is per-element-class.

ROW [NEW] FONT-INTAKE — customer-font is priority 1
  NEW tier: VARIATION (per-brand intake)
  CITATION: `08_DMC_Design_System_v2.md` B.2 L91-92 (verbatim):
    ```
    **Priorität 1 — Kundenspezifische Schrift:**
    Wenn der Kunde eine Hausschrift hat (im CD definiert): Diese verwenden.
    ```
  AND `09_DMC_VA_SOP.docx` Teil 5 asset list (extracted): client supplies "Hex-Codes Haupt- und Akzentfarbe, Firmenlogo EPS oder PNG mit Transparenz" — does NOT supply fonts. Customer-fonts come from CD asset upload.
  NEW VALUE: Renderer accepts a customer-font upload path (mounted from production-side asset gathering, NOT from upstream JSON). When customer-font absent, falls back to Montserrat+Source Sans Pro (the Priorität-2 system fonts), NOT to Inter+Source Serif 4.

---

End of RICHARD-PRIMARY RE-RATIFICATION 2026-05-18.

Rows ratified above (new + flipped + struck + held): A1 (HELD), A2 (STRUCK), B2 (STRUCK), B3 (HELD), C1 (STRUCK), D1 (STRUCK), D2 (STRUCK), plus 13 new rows: BLEED, MARGINS, BODY-COLOR, BODY-FONT, BODY-LAYOUT, PULLQUOTE-SIZE, HEADLINE-SIZE, PAGE-COUNT, CTA-CADENCE, ATEMSEITE-RHYTHM, DOPPELSEITEN-COUNT, BODY-BOLD-FAMILY, WHITESPACE, COLOR-COUNT, PDFX-CMYK, NO-ROUNDED-EXCEPT-CTA, FONT-INTAKE.

Existing matrix rows above this block are not edited. No new .md file created.

---

## 2026-05-23 MOVE 1

Context: chassis decontamination Move 1 (grammar usable by chassis). Two appends in this block:
  (a) ROW C1 textual correction — the 2026-05-18 block's C1 NEW VALUE re-encoded the contamination it was supposed to remove ("Coral validator = AREA + LOCATION").
  (b) Move-1 chassis status note (informational; no new ratification).

Append-only: existing rows above are NOT edited; the 2026-05-18 block above is NOT edited; this is a successor block.

---

ROW C1 — coral budget per-brand override (count-based)
  TIER STATUS: STRUCK (unchanged from 2026-05-18 block; this is a textual
               correction to NEW VALUE only, not a re-tier).
  TEXT CORRECTION (2026-05-23): the 2026-05-18 block's NEW VALUE said
  "Coral validator = AREA + LOCATION". That phrasing re-encodes the
  contamination the strike was supposed to remove — naming the
  validator after the literal hex value of one client's accent.

  CORRECTED NEW VALUE: The validator is "accent ≤10% area + firing-
  location whitelist" — the word "coral" does NOT appear in the rule,
  the validator name, or the error code identifier. The accent is a
  per-client profile value (coral for GEVA, gold for aerz, amber for
  nikl, tan for alex, tonal-teal for buch — every value cited in
  richard-grammar-v2.md §4.1). The validator checks the `accent` field
  from the brand profile, hue-agnostic.

  AUTHORIZED RENAMES (user, 2026-05-19 / 2026-05-23):
    - `CORAL_BUDGET_EXCEEDED` error code → `ACCENT_BUDGET_EXCEEDED`
      (n8n side will be updated to match — coupled change).
    - validators/coral.py → accent-named file (e.g.,
      validators/accent_budget.py or validators/accent.py).
    - `CoralValidator` class → accent-named (e.g., `AccentBudgetValidator`).
    - all chassis docstrings/comments that name "coral" as a chassis
      concept (the chassis-logic-coral hits enumerated in the
      Move-0 damage report).
  Renames are MOVE 2 work; this matrix entry authorizes them.

  REASON unchanged: Richard's actual rule is area-based + location-
  based, per `08_DMC_Design_System_v2.md` L162 ("max. 10% Flächenanteil
  pro Seite") + `01_DMC_Master_System_v1.md` Modul 6 / §1 firing-
  locations list. The count-cap was an Apex artifact.

---

ROW C2 — coral path-selection seam (design_preferences_present)
  OLD tier: RATIFIED (path = location if design_preferences present,
            else count; selection at validator __init__ time, fixed
            per render).
  NEW tier: STRUCK.
  REASON: ROW C1's CORRECTED NEW VALUE (this same 2026-05-23 block,
  above) collapses validation into a single "accent ≤10% area +
  firing-location whitelist" rule, hue-agnostic, fired by the brand's
  `accent` field. There is no count path. There is no location path.
  There is no path selection. C2's two-path seam dies with C1.
  CITATION: cross-reference 2026-05-23 ROW C1 CORRECTED NEW VALUE in
  this same block (above). No independent Richard-doc citation is
  required because C2's death is the structural consequence of C1's
  rule shape, not a rule grounded elsewhere.
  NEW VALUE: in Move 2:
    - Delete `CoralValidator.path: str` attribute (validators/coral.py
      L94).
    - Delete `path: str` field from `CoralValidationResult` dataclass
      (validators/coral.py L73).
    - Delete the `if self.path == "count": ... else: ...` branch in
      `validate()` (validators/coral.py L107-109).
    - Delete the entire `_validate_count()` method (L111-132).
    - Rewrite `_validate_location()` as the single validate path,
      renamed to reflect its single-path nature (e.g.,
      `_validate_accent_budget()`).
    - Delete render.py L203-208 `if validator.path != "location":
      raise RuntimeError(...)` block.
    - Delete render.py L201-202 path-printing log line.
    - Delete tests asserting validator.path == "count" or "location"
      (tests/test_chassis_contract.py L319-330, L333-353 — see
      inventory).
  CONSEQUENCE: when paired with ROW C1's corrected New Value + the
  authorized renames, validators/coral.py becomes single-path,
  treatment-free, accent-budget-named. The brand profile field that
  drives it is `brand_accent` (whatever hex the client supplies).

---

ROW E4 — Inter-Regular.ttf required bundle
  OLD tier: RATIFIED (Inter-Regular.ttf MUST be bundled before render;
            FAIL LOUD if missing, per render.py:_preflight_fonts).
  NEW tier: STRUCK.
  REASON: ROW BODY-FONT in the 2026-05-18 RICHARD-PRIMARY block
  established Montserrat (headlines) + Source Sans Pro (body) as the
  Priorität-2 system-font fallback. Inter is not in any LIVE Richard
  doc; the Inter-bundle requirement is an Apex-era artifact predating
  the Richard-primary frame.
  CITATION: `DMC_InDesign_Spec_v1.md` L484-489 (verbatim, Modul 7.1
  Font-Hierarchie):
    ```
    PRIORITÄT 2 — Empfohlene Systemschriften:
    Headlines:  Montserrat (ExtraBold, Bold, SemiBold)
    Fließtext:  Source Sans Pro (Regular, SemiBold, Bold, Italic)
    ```
  Note on the "Source Sans Pro" naming: Adobe renamed the family to
  "Source Sans 3" in 2021 (last legacy Pro release was 3.046). Google
  Fonts now serves the v3 family. Same typeface in continuity; Richard
  literally writes "Source Sans Pro" in the spec doc; the chassis
  fetches v3 because it is the maintained current release.
  NEW VALUE: Move-2 fetches the new font bundle into
  research/v7-renderer/fonts/ and rewrites render.py:_preflight_fonts
  + patterns/st_07a.py @font-face blocks to reference the new files.
  The choice between variable-axis and static-cut downloads is a
  user ruling pending (one option must be picked before Move 2):

    OPTION A — Variable fonts (Google Fonts canonical, simpler):
      - Montserrat[wght].ttf            (weight axis 100-900)
      - Montserrat-Italic[wght].ttf     (italic, weight axis)
      - SourceSans3[wght].ttf           (weight axis 200-900)
      - SourceSans3-Italic[wght].ttf    (italic, weight axis)
      Source: https://github.com/google/fonts/tree/main/ofl/montserrat
              https://github.com/google/fonts/tree/main/ofl/sourcesans3
      4 files. CSS @font-face uses `font-weight: 700` etc. and the
      variable file resolves the weight via its axis. WeasyPrint v54+
      supports variable fonts. Smallest disk footprint.

    OPTION B — Static cuts (legacy distribution; per-weight files):
      Montserrat (from Google Fonts ofl/montserrat — static subdir
      not at the expected path; fetch from JulietaUla/Montserrat repo
      or fontsource npm package instead):
        - Montserrat-Regular.ttf
        - Montserrat-SemiBold.ttf
        - Montserrat-Bold.ttf
        - Montserrat-ExtraBold.ttf
        - Montserrat-Italic.ttf (if italic-heading needed)
      Source Sans 3 (from adobe-fonts/source-sans release/TTF/):
        - SourceSans3-Regular.ttf
        - SourceSans3-Semibold.ttf    (note: lowercase 'b' per Adobe)
        - SourceSans3-Bold.ttf
        - SourceSans3-It.ttf          (note: 'It' not 'Italic')
        - SourceSans3-SemiboldIt.ttf
        - SourceSans3-BoldIt.ttf
      Source: https://github.com/adobe-fonts/source-sans/tree/release/TTF
      ~9 files. CSS @font-face has one entry per weight. Verified
      filenames from upstream listings, not guesses.

    OPTION C — Adobe legacy "Source Sans Pro" 3.046R:
      Direct text-match to Richard's literal "Source Sans Pro" wording.
      Source: https://github.com/adobe-fonts/source-sans/releases/tag/3.046R
      Filenames at that tag are SourceSansPro-Regular.otf etc. Drift
      from the maintained current release; no future updates. Only
      pick if exact-literal-name match matters more than current
      maintenance.

  RECOMMENDATION (CC, not ratified): OPTION A (variable). Smallest
  bundle, current upstream, axis-driven weight in CSS aligns naturally
  with Richard's "ExtraBold / Bold / SemiBold" + "Regular / SemiBold /
  Bold / Italic" enumeration. User picks before Move 2.

  PREFLIGHT REWRITE: render.py:_preflight_fonts hardcodes Inter-* and
  SourceSerif4-* filenames (L84-92). Move 2 swaps the required list
  to the chosen option's filenames. The font-missing FileNotFoundError
  message also names "Inter-Regular.ttf" specifically — that string
  needs updating too.

---

ROW B1 — LRP/RRW renderer-internal labels
  OLD tier: RATIFIED (LRP = left page of facing-pair; RRW = right page
            rail variant).
  NEW tier: HELD with clarification.
  REASON: LRP and RRW are renderer-internal naming conventions
  adopted earlier in chassis design. They do not appear in any LIVE
  Richard doc. v2 D.3 explicitly states case study + Gegenseite are
  TWO independent single pages, NOT a doublespread design unit. The
  labels may persist as internal vocabulary BUT must NOT be interpreted
  as implying a doublespread.
  CITATION: `08_DMC_Design_System_v2.md` D.3 L209-210 (verbatim):
    ```
    Die Fallstudie steht auf einer Einzelseite. Die gegenüberliegende
    Seite ist eine eigenständige Seite die das Warum des Ergebnisses
    erklärt — ohne Rückbezug auf die Fallstudie.
    ```
  AND `01_DMC_Master_System_v1.md` L487 (verbatim, ST-07B section
  header): `## ST-07B | FALLSTUDIEN-GEGENSEITE (EIGENSTÄNDIGE
  VERTIEFUNG)` — the parenthetical "EIGENSTÄNDIGE VERTIEFUNG"
  ("independent deep-dive") reinforces v2's independence rule.
  NEW VALUE: the label "LRP" may persist as renderer-internal vocabulary
  for the file `patterns/st_07a.py` since the case study has a logical
  facing partner. The docstring of `patterns/st_07a.py` must explicitly
  state, in plain text, in the header docstring: "Single page; facing
  Gegenseite (ST-07B) is rendered independently per v2 L209-210; no
  doublespread design unit exists." patterns/st_07b.py (when created
  in a future move) must be a self-contained pattern, NOT
  architecturally dependent on st_07a. The chassis NEVER renders a
  case-study + Gegenseite as a single design unit; they are two
  independent page renders that happen to face each other in the
  final assembled PDF.

---

ROW [NEW] SLOT-PLAN — verbatim Modul 9.1 Standard 20-Seiten plan
  NEW tier: HARD (FIXED + ANCHOR slot assignments); SOFT (VARIABLE
            slot selection within named groups).
  CITATION: `01_DMC_Master_System_v1.md` L793-815 (verbatim, Modul 9.1
  Standard 20-Seiten-Report), reproduced from the slot-plan block
  bytes:

    S1:  ST-01 — Cover (FIXED)
    S2:  ST-02 — Ausblick/Editorial (FIXED)
         ODER: ST-04 Innenklappe auf S2, ST-02 auf S3
    S3:  ST-05 — Autorität/Über-Uns (ANCHOR)
         ODER S2/S3 Ausblick + S4 Autorität (je nach Ausblick-Variante)
    S4:  VARIABLE — aus PROBLEM-Gruppe (ST-09 bis ST-13)
    S5:  VARIABLE — aus PROBLEM oder DENKFEHLER-Gruppe
    S6:  VARIABLE — aus DENKFEHLER-Gruppe (ST-14 bis ST-18)
    S7:  VARIABLE — aus DENKFEHLER oder ÜBERGANG-Gruppe
    S8:  ST-06 — Mechanismus-Einführung (ANCHOR)
    S9:  VARIABLE — aus MECHANISMUS-Gruppe (ST-19 bis ST-22)
         ODER ST-37 Soft-CTA-Zwischenseite
    S10: ST-07A — Fallstudie #1 (ANCHOR/PROOF)
    S11: ST-07B — Gegenseite zu FS1 (PROOF) — eigenständige Vertiefung
    S12: ST-07A — Fallstudie #2 (ANCHOR/PROOF)
    S13: ST-07B — Gegenseite zu FS2 (PROOF) — oder VARIABLE aus PROOF-Gruppe
    S14: VARIABLE — Fallstudie #3 (ST-07A) ODER PROOF-Sonderformat (ST-23–ST-27)
    S15: VARIABLE — Gegenseite zu FS3 ODER PROOF-Gruppe ODER SPECIAL
    S16: VARIABLE — aus PROOF oder TRUST-Gruppe
    S17: ST-05-Variante / ST-31 — Kompetenz & Trust gebündelt (ANCHOR)
    S18: ANCHOR — Einladungs-Seite / Zusammenarbeit (ST-22 oder ST-37)
    S19: ST-08 — FAQ / Einwandvorwegnahme (ANCHOR)
    S20: ST-03 — Rückseite/Hard-CTA (FIXED)

  AND `01_DMC_Master_System_v1.md` L818 (CTA-Kadenz, verbatim):
    **CTA-Kadenz:** S2 (Soft im Ausblick), S9 (Mid nach Mechanismus),
    S18 (Mid Einladung), S20 (Hard)

  AND `01_DMC_Master_System_v1.md` L842 (Atemseite combination
  prohibition, verbatim from Modul 10.1 Kombinationsverbote):
    - ST-32 (Atemseite) direkt nach ST-32 → verboten

  DERIVED BUILD SUBSET (13 patterns, derived FROM the pasted bytes
  above — not asserted): the smallest pattern set that can fill every
  slot of the Standard 20-Seiten plan, one primary choice per slot:

    FIXED (always-required): ST-01 (S1), ST-02 (S2), ST-03 (S20)        → 3
    ANCHOR (named in plan):  ST-05 (S3), ST-06 (S8), ST-07A (S10+S12),
                              ST-07B (S11), ST-08 (S19)                  → 5
    ANCHOR alt at S17:       ST-31 (or ST-05-Variante; pick ST-31)       → 1
    VARIABLE PROBLEM (S4/S5):     ST-09 (group leader, ST-09 to ST-13)   → 1
    VARIABLE DENKFEHLER (S6/S7):  ST-14 (group leader, ST-14 to ST-18)   → 1
    VARIABLE MECHANISMUS (S9):    ST-22 (group, ST-19 to ST-22; also
                                   serves as S18 Einladung alt)          → 1
    Atemseite (cadence insert,    ST-32 (VARIABLE, not in S1-S20 slots;
    every 5–7 pages):              inserted by rhythm constraint per
                                   ROW ATEMSEITE-RHYTHM)                 → 1
    TOTAL                                                                = 13

  RECONCILES the GATE-4 self-flag from the prior session ("ST-32 is
  VARIABLE not FIXED"): confirmed against verbatim bytes. ST-32 does
  not appear in S1-S20; it is a VARIABLE insert governed by the 5-7
  page cadence in ROW ATEMSEITE-RHYTHM. The build set includes it
  because the renderer needs the pattern code to emit Atemseiten
  during composition, not because it is slot-mapped.

  NEW VALUE: 13 ST-types in scope for this phase: ST-01, ST-02, ST-03,
  ST-05, ST-06, ST-07A, ST-07B, ST-08, ST-09, ST-14, ST-22, ST-31,
  ST-32. NOT in scope this phase (committed for additive future work
  per user 2026-05-18): ST-04, ST-07C, ST-10-ST-13, ST-15-ST-18,
  ST-19-ST-21, ST-23-ST-30, ST-33-ST-37.

  AND `01_DMC_Master_System_v1.md` L820-833 (24/16/28 variants,
  verbatim, for record):
    ## 9.2 24-Seiten-Report
      +4 Slots zwischen S13 und S14 (aus VARIABLE-Gruppen wählen).
    ## 9.3 16-Seiten-Report
      Streiche: S5, S7, S14, S15. Behalte alle FIXED und ANCHOR
      Pflichttypen. Nur 2 Fallstudien (ST-07A) ohne Gegenseiten.
    ## 9.4 28-Seiten-Report
      +8 Slots. Hier können ST-07C (Doppelseiten-Fallstudien) sinnvoll
      eingesetzt werden.

  NOTE: SLOT-PLAN is HARD because the plan itself is "PFLICHT" /
  "FIXED" / "ANCHOR" per Master System Modul 9.1; the VARIABLE-slot
  picking is SOFT (designer/copy choice within named groups).

---

MOVE 1 CHASSIS STATUS NOTE (informational; not a matrix ratification)

  Grammar loader repointed at richard-grammar-v2.md (Move 0).
  Grammar ratified (`RATIFIED-BY: Utkarsh 2026-05-23`).
  Parser regex updated to handle the new `## §N  TITLE` / `### §N.M
  TITLE` heading format. Parser now reads §0 through §9 plus
  subnumbers from the live grammar.
  get_section() call sites in patterns/st_07a.py remapped from OLD
  SKILL.md numbering to NEW grammar numbering (full remap table in
  patterns/st_07a.py STEP 1 comment block).
  Pyphen installed in chassis venv (Blocksatz hyphenation now active
  per §4.0 / InDesign Spec L246).
  pango + glib already installed on host (verified via brew).
  Move-2 work still pending: validator rename (per ROW C1 above);
  A1 design_preferences deletion; chassis "coral"-named symbols
  cleanup; font swap to Montserrat + Source Sans Pro; rewriting
  patterns/st_07a.py _extract_type_system to read §4.0's format
  (or replacing it with direct grammar-citation hardcodes); removal
  of BARRED §5c micro-header callout-grid CSS; deletion of
  render.py L168-184 path-selection raise.

---

End of MOVE 1 block 2026-05-23.
