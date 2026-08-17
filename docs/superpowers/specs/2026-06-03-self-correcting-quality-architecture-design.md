# Self-Correcting Quality Architecture — Design Spec (the "Brain / Conductor / Interceptor" loop)

**Status:** Authoritative design — the master architecture for closing the output-quality gap. Approved in design dialogue 2026-06-03. Build resumes against THIS doc after compaction.
**Date:** 2026-06-03
**Components:** spans all three layers — `research/preprocessor/` (Layer 1), `research/v7-renderer/` (Layer 2), the future post-processor (Layer 3) — plus a NEW top-level orchestration layer and a Supabase data layer.
**Author intent (verbatim framing to preserve):** "This is a coding architecture, this is NOT a vibe-coded architecture." Everything below must be deterministic where it can be, probabilistic only where judgment is genuinely required, and **brand-agnostic** throughout.

---

## 0. How to read this doc + the dependency graph (READ FIRST on resume)

This spec is the hub. It **references** these docs and they **reference back** to it (links wired bidirectionally per the build instruction — do not let any go stale):

**This spec DEPENDS ON (read these for detail; cited inline as [DNA], [PRD], [4b], [4a], [CTX], [GRAMMAR]):**
- **[DNA]** `docs/superpowers/specs/2026-05-30-richard-design-dna.md` — the 6-deck visual schema. **§C = the source of the POSITIVE rubric table; §E = the source of the NEGATIVE rubric table; §D = the per-page recipes; §B = the axes.** The rubric in §6 below is derived from it; do not re-derive design rules elsewhere.
- **[GRAMMAR]** `richard-grammar-v2.md` (+ `01_DMC_Master_System_v1.md`, `08_DMC_Design_System_v2.md`) — the universal DMC design grammar = the schema source of truth. The DNA operationalizes it.
- **[PRD]** `docs/superpowers/specs/2026-05-30-preprocessor-PRD.md` — the pre-processor's single source of truth. The package (`ResolvedPackageManifest` v2.0) it produces is the **fix surface** this loop edits.
- **[4a]** `docs/superpowers/plans/2026-05-30-preprocessor-phase-4a-v2-wiring.md` — the v2.0 package wiring (DONE + verified). The loop builds on the package this produced.
- **[4b]** `docs/superpowers/specs/2026-06-02-renderer-phase-4b-v2-consumption-design.md` — the renderer expansion. **This spec SUBSUMES 4b as its "Phase A" (the theme-lock + capability-widening pass).** 4b's §3 component table = the renderer-capability flags the rubric is clamped to (§5.5).
- **[CTX]** `context.md` — the project journey, the cardinal brand-agnostic rule, the hard-won lessons, ops gotchas. The single resume doc; it points here as the active architecture.

**Docs that REFERENCE this spec (back-links added in the same change):** `context.md` (docs index + immediate-next-action), `[4b]` (header note: now Phase A of this architecture), `[PRD]` (see-also forward pointer), `[DNA]` (see-also: it is the rubric source for §6).

**Self-sufficiency promise:** this doc is written to be buildable cold after compaction — the architecture, the two rubric tables, the loop, the perception stack, the Supabase schema, the build roadmap, the risks, and the citations are all inline. Read [DNA]§C/§E and [PRD]§5 alongside it; everything else is here.

---

## 1. Why this exists (the problem, honestly stated)

The pipeline today is **open-loop**: pre-processor builds a package → renderer renders a PDF → **stop**. It has no eyes (never sees its output), no judgment (no rubric for "is this good?"), and no correction (no way to fix and re-render). A human designer works in a closed loop — design, step back, critique, fix, repeat — and that loop is the difference between our APEX render and the agency's hand-designed reference decks (see [CTX] "the Richard situation"; the references are Adobe-InDesign hand-designs — verified via PDF metadata — not pipeline output, and the gap to them is real).

**The fix is a closed loop:** generate → perceive → score-against-references → fix → re-render, **per page, until each page clears a bar.** This is a known, researched pattern (evaluator–optimizer / actor–critic; see §11 citations).

**The honest caveat that governs the whole design (do not lose this):** a scoring loop **raises consistency to the bar the renderer can express — it does NOT raise the bar itself.** If the renderer can't draw a device or the brand font isn't wired, the loop scores those pages low *forever* and burns budget oscillating. Therefore: (a) the rubric is **clamped to current renderer capabilities** (§5.5), and (b) we **widen the renderer + fix the font/theme FIRST** (Phase A), then wrap the loop around it. The loop is the *guarantor of consistency*, not magic. Diagnosis grounding this: the gap is ~80–85% closable in WeasyPrint+templates; the residual ~15–20% is real assets + the licensed font + bespoke art-direction (see §8).

---

## 2. Cardinal rule (non-negotiable, inherited from [CTX] + [DNA])

**Brand-agnostic everywhere.** No client name / hex / font / literal in logic. Per-client = DATA (brand tokens, [DNA]§B axes, content, assets). This is "the rule that nearly killed the project."

**Applied to THIS architecture (the new failure modes to guard):**
- **References ground COMPOSITION, never brand values.** The critic compares device-presence / hierarchy / composition against reference exemplars and is **explicitly told to ignore the reference's colors, fonts, and specific content** — those come from the client. Otherwise the loop would penalize every client for not being navy+orange like Niklas (= pollution in disguise). Reference = the *composition/quality* exemplar; client brand = the *values* that fill it.
- **No raw-PDF copying.** We never select a client's finished deck and copy its layout per-client (the explicit cardinal sin). The **[DNA] recipes already are the proven layouts, abstracted across all 6 decks**; references add the *visual ground-truth to score against*, not a template to clone.
- **Guard test extended:** `test_no_client_name_in_logic` (pre-processor) + `test_no_literals_in_architecture` / `test_no_coral_in_chassis_logic` (renderer) must scan all new modules (orchestrator, conductor, interceptor, perception, scoring). No client-specific literal may leak from a reference into logic.

---

## 3. Architecture (the topology, as the author defined it)

```
                         BRAIN  — master orchestrator (runs the whole software; owns ship / loop / stop)
                           │   drives the full cycle + the per-page convergence loop + the doc-coherence pass
        ┌──────────────────┼──────────────────────────────────┐
        ▼                  ▼                                   ▼
  PRE-PROCESSOR ────────► RENDERER ────────► POST-PROCESSOR (Layer 3, later)
   (builds package)        │ PDF + per-page PNGs (already emitted by render.py)
        │                  │
        │           rendered page(s)
        ▼                  ▼
   CONDUCTOR  ◄────────────┘     sub-orchestrator; BRIDGE between pre-processor and the interceptors;
        │  ▲                     talks BOTH ways (sends pages out, relays verdict + localized fixes back)
        │  │ verdict + fixes
        ▼  │
   INTERCEPTORS   (QA subsystem branching off the pre-processor)
        ├── PERCEPTION  — deterministic checks (DOM/PDF/pixels) + cheap VLM rows read the rendered page → structured facts
        └── ANALYSIS    — the positive + negative rubric tables → per-page REWARD score, judged AGAINST matched reference exemplars
                              ▲
                              └── REFERENCE LIBRARY (Supabase) — reference pages indexed by {st_type, axes, devices}
```

**Component responsibilities (precise):**
- **Brain** = master orchestrator. Runs pre-processor → renderer → (post-processor), owns the per-page convergence loop (§5), the iteration budget, the "keep best" memory, and the final document-coherence pass. In production, n8n still calls `/render` once; the Brain wraps the existing pipeline (it may adopt the async `/render → 202 + webhook` variant the [PRD]§10 already contemplates).
- **Conductor** = a *sub*-orchestrator that bridges the pre-processor and the interceptor subsystem. Sends the package + rendered page(s) to the interceptors; relays the verdict + localized fixes back. Talks both ways. (Implementation: a module the Brain invokes per page.)
- **Interceptors** = the QA subsystem with two organs:
  - **Perception** — turns the rendered page into structured facts (§7): mostly deterministic (computed styles, WCAG contrast/luminance, box geometry, PDF font-embedding, pixel-variance for empty-box), plus a small number of cheap VLM judgments.
  - **Analysis** — applies the rubric (§6) → a per-page **reward** score, **judged against the matched reference exemplars** (§4), and localizes each defect to one fix + its owning layer.
- **Reference Library** = a resource Analysis queries (§4), living in Supabase (§9).

**Deterministic ↔ probabilistic split (the author's "code + AI"):** code owns the rubric, the scoring math, the loop control, the renderer, the reference retrieval, and ALL data correctness (numbers, contrast, slot-resolution, font-embedding). AI owns ONLY perception's visual-judgment rows, the critique, and the fix-*proposal*. **The AI proposes; deterministic code disposes and records.** Numbers are never "AI-corrected."

**Fix routing = (b) route-to-the-owning-layer** (settled by the per-page loop, since a "remake" is sometimes a CSS/template knob (renderer), sometimes package data/axes (pre-processor), sometimes an image regeneration (fal → Pillow re-composite)). The conductor reads each fix's `knob_class` and routes it to its owner.

---

## 4. Reference-grounding (the "answer key")

The architecture is hollow without references. Abstract rules ("dark panels are good") are a weak signal; "here is the reference page this should resemble" is a strong one. So Analysis judges **against matched reference exemplars**, and the fix-proposer points at them ("the reference puts a dark stat-panel here; yours is a pale tint").

- **Library:** the 6 reference decks rasterized per page (the `_renders/*.png` set already exists), each page a row in Supabase `references` tagged `{deck, page_no, st_type, axes, devices[]}`.
- **Retrieval (NOT random):** to score a client page of type T with axes A, retrieve the K reference pages of type T whose axes are **closest** to A (axis-similarity) — apples to apples (a serif+navy case-study vs serif+navy case-study references), never random and never cross-type.
- **Reference-grounded critic:** the VLM judge receives `{rendered page, K matched reference exemplars, the rubric}` and scores **compositional/device fidelity** to the exemplars — **explicitly instructed to ignore the reference's color/font/specific content** (the brand-agnostic safeguard from §2).
- **Reference-grounded fix-proposal:** fixes can cite the exemplar.

---

## 5. The per-page convergence loop (the author's core mechanism, made rigorous)

**The model:** the Brain watches each page as it is made; if it is not right, it is remade; it keeps going until that page clears the bar, **then** moves to the next page.

```
make page N  →  render page N (just that page) → PERCEIVE (deterministic checks + cheap-VLM rows)
            →  ANALYSIS scores vs matched reference exemplars  →  reward_N
            →  reward_N ≥ threshold  AND  zero hard-fails ?
                   YES → lock page N, advance to N+1
                   NO  → brain localizes ONE defect + proposes a fix with its knob_class:
                            • renderer   (CSS token / template / macro)
                            • preprocessor (package data / axis / asset choice)
                            • asset-gen  (fal regenerate → Pillow re-composite)   ← AI for what code can't draw (§8)
                         → conductor routes the fix to its owning layer
                         → REMAKE page N → re-score → repeat
```

### 5.1 The gate ("cleared")
A page clears iff `reward_N ≥ threshold` (a high % of the page-type's achievable max) **AND** zero **hard-fail** rows fired (§6.2). Hard-fails latch — they cannot be out-earned by piling on positives.

### 5.2 The three convergence guards (MANDATORY — without these the loop is a footgun)
1. **Per-page iteration cap (~3–4).** Some targets hit the renderer's genuine ceiling (§8). On cap: **ship the best-scored version of that page + flag it for human review**, and advance. The loop must NEVER stall the whole report on one un-perfectable page. (This amends the author's "keep going until it's right" → *until it clears OR hits the cap, then best-effort + flag.*)
2. **Monotone improvement.** Never accept a remake that scored worse; retain best-so-far (greedy, per CITL §11).
3. **Oscillation detector.** If the same defect set recurs, switch fix strategy instead of reapplying the failed one.

### 5.3 Theme-lock first (the shared-state refinement)
Font, palette, panel-darkness, type scale are **shared across all pages**. A per-page fix to a shared token would silently thrash the other 19 pages. So there is a one-time **theme pass up front** (this is essentially Phase A, §10) that locks the shared tokens; the per-page loop then only touches **page-local** composition + assets. Otherwise the loop never converges.

### 5.4 Document-coherence pass (the cross-page safety net)
Per-page convergence yields 20 individually-good pages — not necessarily a coherent *deck*. After all pages clear, one whole-deck pass checks family-resemblance + dark/light rhythm + tonal consistency across the arc, and may kick a specific page back. **Per-page loop, then a coherence sweep.**

### 5.5 Rubric clamped to renderer capability (the anti-infinite-loop rule)
Every rubric row carries a **capability flag** tied to [4b]§3's component table. A row is **active only if the renderer can currently satisfy it.** A `device_mockup` or `donut_chart` row stays inactive until that macro exists — so "the renderer can't do it yet" becomes a clean backlog item surfaced to a human, NOT an infinite oscillation. Widening capabilities (Phase A / 4b-2) *activates* more rows.

---

## 6. The rubric — the two tables (Analysis), derived from [DNA]§C/§E

The rubric is the **constitution** (code/config, versioned, brand-agnostic). The **running scores** are data (Supabase `page_scores`). Two detection modes per row: **DET** = deterministic check (code: computed style / WCAG / geometry / PDF font table / pixel stats — cheap, exact, gates the loop, never reward-hacks). **VIS** = a bounded vision-model judgment of the rendered PNG (small integer + rationale). On the highest-value/most-fakeable rows, **DET gates VIS** (both must agree).

### 6.1 POSITIVE TABLE (rewards; from [DNA]§C) — abbreviated; full detection notes live with the implementation
| id | rewards | detect | wt |
|---|---|---|---|
| P01 founder-as-hero | founder is the dominant human anchor (cover/about) | DET (slot resolved + box ≥35% area) ∧ VIS | +10 |
| P02 two-tone headline | neutral run + bold-CAPS accent word on covers/openers | DET (macro/accent-span present) | +5 |
| P03 dark authority panel | solid dark (navy/ink/primary) panels, not pale tint | DET (panel bg luminance < 0.18, sourced from `--color-primary`/`--color-ink`) | +8 |
| P04 readable on-panel | text on dark panels = luminance-derived on-color, contrast ≥4.5:1 | DET (computed contrast) | +6 |
| P05 named client photo / case study | each Fallstudie has a framed named portrait (~24–40% col) | DET (slot resolved + box + name/role/url siblings) ∧ VIS | +10 |
| P06 big-number stat devices | 3-up / before→after / grids / cost-math, oversized numerals | DET (component present + numeral ≥2× body) | +7 |
| P07 social-proof apparatus | press wall + rating cards + review grid + client-logo wall | DET (≥3 of 4 families) ∧ VIS | +9 |
| P08 running-header furniture | wordmark + booking tagline + URL + rule + folio | DET (header element fields non-empty) | +4 |
| P09 serif/sans pairing, fonts loaded | display vs body distinct families, embedded (not fallback) | DET (PDF font table; computed families differ) | +4 |
| P10 decorative glyphs | oversized ghost numeral + big quote glyph | DET (element present, ≥6×/≥3× body) ∧ VIS | +3 |
| P11 real charts | before/after / line / donut / money / cost-math, bound to data | DET (chart component + non-empty series) ∧ VIS | +7 |
| P12 magazine density | dense editorial interiors, multi-column | VIS (0–3) + DET (coverage floor) | +5 |
| P13 per-client texture | axis-driven atmosphere where the recipe wants it | DET (texture asset applied) ∧ VIS | +4 |
| P14 full-bleed photo, treated | cover/back/breathing bleed + scrim so text reads | DET (@page bleed + scrim layer) ∧ VIS | +4 |
| P15 numbered pills / labels | white-on-dark numbered pills + uppercase eyebrows | DET (element + index + casing) | +3 |
| P16 device/product mockup | phone/laptop/book mockup on case-study/mechanism | DET (composited asset) ∧ VIS | +3 |

*Front-loaded on the four [DNA]§E ★★★ levers: founder-as-hero (P01), client photos (P05), dark panels (P03/P04), social-proof (P07). Positive cap normalizes to 100; the per-page reward in §6.3 scales this to the author's "up to ~1,000,000".*

### 6.2 NEGATIVE TABLE (penalties; from [DNA]§E + observed render defects) — **HARD-FAIL** rows latch the page below ship regardless of total
| id | penalizes | detect | wt |
|---|---|---|---|
| N01 empty required photo box | required slot renders blank/placeholder | DET (slot unresolved / flat-fill) ∧ VIS | HARD-FAIL |
| N02 pale tint not dark panel | authority panel bg luminance > 0.5 / from accent-tint | DET | −12 |
| N03 font fallback / wrong family | brand font not embedded; display==body | DET (PDF font table) | HARD-FAIL |
| N04 overflow / clipping | content exceeds the page box | DET (existing `check_overflow`) | HARD-FAIL |
| N05 low text contrast | text vs bg < 4.5:1 (incl. over photos) | DET | −10 (HARD-FAIL on headline/URL) |
| N06 oversized QR | QR area > 12% page / > portrait area / qr_enabled false | DET | −8 |
| N07 generic-stock imagery | hero/scene looks generic vs specific-to-business | VIS | −10 |
| N08 dead whitespace | sparse, purposeless empty regions | VIS (0–3) + DET coverage | −6 |
| N09 missing header furniture | interior page lacks header band / folio | DET | −5 |
| N10 untreated full-bleed photo | text on busy photo, no scrim; or inset gaps | DET ∧ VIS | −8 (HARD-FAIL if unreadable) |
| N11 missing recipe-required device | page-type recipe device absent ([DNA]§D) | DET | −6 each |
| N12 accent over-budget | accent sprayed beyond budget / hue-noise | DET (`accent_budget` seam) | −5 |
| N13 empty/stub chart | chart present but no data | DET | −6 (HARD-FAIL if sole proof device) |
| N14 placeholder/lorem/"could not render" leakage | fallback text reaches the PDF | DET (text scan + render warnings) | HARD-FAIL |

### 6.3 Reward scoring scheme (the author's "score per page, up to a million")
- `raw_p = Σ(earned positive weights) − Σ(penalty weights)`, clamped to `[0, page_type_max]`, then normalized to a per-page reward on the author's scale (e.g. `page_reward = 1_000_000 × page_pct` where `page_pct = raw_p / page_type_max`). The absolute scale is cosmetic (the "reward feel"); the work is done by **relative weights + the threshold + the hard-fail latches**.
- **Per-page gate (ship the page):** `page_reward ≥ threshold` (e.g. 95% of max) AND no hard-fail latched.
- **Per-document gate (ship the report):** all content pages cleared, AND `dna_lever_coverage == 4/4` (founder-hero, client-photos, dark-panels, social-proof each present ≥ once), AND the coherence pass (§5.4) passed.
- **Anti-reward-hacking (from §11 research):** caps on every positive row (repeating a device earns nothing past the cap); hard-fails dominate totals (a blank box can't be bought back); DET-gates-VIS on the fakeable rows (P01/P05/P07/P11); recipe-required devices live in the NEGATIVE table (N11/N13) so the optimizer can't skip hard devices to protect a clean total; page-type normalization + lever-coverage force breadth not show-off pages.

---

## 7. Perception stack (scoped for Railway — see §9 hosting)

- **Deterministic core (no model — ~70% of the rubric):** computed CSS, WCAG luminance/contrast, element box geometry, PDF font-embedding, pixel-variance (empty-box), and text-correctness read straight from the rendered DOM + the PDF's own text layer (PyMuPDF — exact, free). This is the bulk of perception.
- **Visual-judgment rows (the handful of VIS rows):** a **cheap, swappable vision API** — default **Gemini Flash via OpenRouter** (cheaper than Sonnet, plenty for coarse holistic judgments; ~single-digit $/mo at this volume). Model slug stays in config (`OPENROUTER_VISION_MODEL`). Pin the model snapshot + `temperature: 0` for reproducibility; log raw outputs. The one genuinely-hard row ("real photography vs generic stock", N07) may be routed to a stronger model if it proves noisy.
- **OCR: NOT in v1.** We render the PDF, so we already have the exact text (DOM + PDF text layer); font-fallback is caught deterministically (N03). OCR (Tesseract `deu`) is a thin optional layer to add ONLY if rendered pixels are ever found not matching intended text.
- **Local OSS VLM: deferred (Railway has no GPU).** Researched + scoped: Railway offers no GPU and caps Hobby images at 4 GB; a resident 2B VLM costs ~$50–70/mo to keep warm, fights the image cap + cold-start 502s, and is *worse* on the hard N07 row — so the vision API wins at this scale. Revisit a local Apache-2.0 model (Qwen2-VL-2B / Moondream2) ONLY with a GPU host (Modal/RunPod/Replicate for just the model service) OR a hard offline/data-residency requirement. **Open question to confirm at build time:** is fully-offline a hard requirement? (Default assumed: no → API.)

---

## 8. The renderer ceiling + asset/font reality (diagnosis grounding Phase A & C)

From this session's investigations (grounded in code + the reference PNGs):
- **Most of the gap is NOT a WeasyPrint wall (~80–85% reachable).** Dominant fixable causes: (1) **the brand font silently falls back to Playfair** — `compile_tokens` ignores `brand.font_heading` entirely AND the real font was never supplied (this is the #1 "generic" tell — a wiring bug + a missing asset); (2) **pale theme** — authority panels fill with a mid-luminance primary instead of dark ink; (3) **timid type scale** (caps ~24–34pt); (4) **starved inputs** — 4/5 case-study photos missing, logos absent (components exist, unfed); (5) **content-blind AI imagery** — generated scenes have `prompt: null`, generic abstract-3D; (6) **one composition per page-type, replayed.**
- **Genuine hard ceilings (→ the fal + Pillow handoff):** no CSS `mix-blend-mode`/duotone (bake duotone upstream in Pillow/fal), no photoreal 3D isometric money-infographics (generate as art, composite via Pillow), true physical-sheet bleed (Layer-3 post-processor). **This is exactly the code-vs-AI split applied to assets: code draws what it can; fal generates what it can't; Pillow re-takes control for alignment/compositing.** The Brain's critic drives better generation prompts (fixing the content-blind-imagery defect, N07).
- **Human-supplied (cannot be synthesized):** the licensed brand font file (else bundle a top-tier OSS editorial face — Fraunces / Bricolage Grotesque / Instrument Serif / a Didone OFL — and wire `brand.font_heading` end-to-end with a loud warning on miss), and the missing real client photos (the author is supplying more — see the asset request in [CTX]/the Richard message).

---

## 9. Data layer — Supabase (decided)

Supabase is the system's data layer (justified beyond references because the closed loop needs persistent state):
- **Storage buckets:** `references/` (per-page reference images + source PDFs), `client-assets/` (real photos Richard supplies), `generated-assets/` (fal outputs), `outputs/` (final PDFs + per-page PNGs).
- **Postgres tables:** `references` (`deck, page_no, st_type, axes, devices[]` — powers retrieval by type+axis, §4); `runs` + `page_scores` (per-page reward + every iteration's score — the author's "score per page, correctly maintained" made durable + auditable); `clients`/`brands` registry.
- **Connection:** `supabase-py` + a service-key env var. Supabase is external/hosted (Postgres + Storage) → clean on Railway, no compute concern. The pre-processor "calls and selects" references **by page-type + closest axes** at render time (not random).
- **Note:** for references *alone* Supabase would be overkill (they're static + tiny, already in `_renders/`); it earns its place as the home for scores + assets + outputs too.

---

## 10. Build roadmap (phases — per-phase writing-plans docs authored at build time)

**Phase A — Renderer + font + theme + capability widening (the theme-lock; subsumes [4b]).** No loop yet; these are the cheap, huge wins. Wire the real/OSS brand font end-to-end + loud warning on miss (fixes the #1 tell); darken authority panels off `--color-ink`; bump the type scale + add a hero tier; add missing devices (ghost-numerals, rating/review cards, more chart kinds via inline SVG) + per-page layout variants; wire the `density` axis. **Locks the shared theme (§5.3) and activates more rubric rows (§5.5).** *This alone closes most of the visible gap.*

**Phase B — The closed loop (Brain / Conductor / Interceptor).** Build the orchestrator + conductor + interceptor (perception §7 + analysis/rubric §6) + reference-grounding §4 + the per-page convergence loop §5 + the guards + the coherence pass; rubric clamped to Phase-A capabilities. Wire Supabase `runs`/`page_scores`. **Locks in consistency every run.**

**Phase C — Assets + reference library + generation art-direction.** Real-asset sourcing (Drive/n8n → `client-assets/`); the reference library populated in Supabase (`references/` + table); art-directed fal prompts (kill `prompt: null`) + Pillow compositing for the ceiling items (§8); flag the human-supplied gaps (font file, missing case-study photos).

**Layer 3 (later):** post-processor (Ghostscript RGB→CMYK, PDF/X-4, true bleed).

---

## 11. Determinism, non-regression, testing, risks

**Determinism:** the DET core is pure code; the vision model is pinned + `temperature:0`; reference retrieval is deterministic (sorted by axis-distance); the renderer + package are golden-tested; fal is content-addressed-cached. The brand-agnostic guard extends to every new module.

**Non-regression:** Phase A is visual-regression-gated (re-baseline per approved page, the proven method); the pre-processor golden (v2.0) stays green; the loop is additive (a new top-level layer, not a rewrite of the existing services).

**Risks + mitigations (from the research):**
- **Convergence / oscillation** → the three guards (§5.2): hard cap, monotone, oscillation detector.
- **Reward-hacking** → §6.3 defenses (caps, hard-fail dominance, DET-gates-VIS, low iteration cap, required-devices-as-penalties).
- **Judge unreliability** (VLM position/verbosity bias, non-determinism, weak on fine-grained charts) → temp-0 + fixed ID-based rubric + reference-grounding; scope the VLM to layout/visual presence, NEVER to verifying chart *numbers* (deterministic); human is the final reviewer (the loop feeds the existing review gate, doesn't replace it).
- **The renderer ceiling** → §5.5 capability-clamp + §8 fal/Pillow handoff; surfaced to human, never looped on.
- **Cost** → mostly-deterministic perception + a few cheap Gemini-vision calls + re-score-only-changed-pages + budget ledger (fal already cap+cache-gated).

**Research citations (the closed-loop pattern is established):** Self-Refine (arxiv 2303.17651); Reflexion (arxiv 2303.11366); LLM/VLM-as-judge incl. Prometheus-Vision (arxiv 2401.06591) + bias literature (2506.22316, 2505.08468); Constitutional AI (arxiv 2212.08073); the directly-analogous render-critique-refine line — UI2Code/CITL (arxiv 2604.05839), ReLook, Web2Code/Design2Code; "LLMs can't self-correct reasoning — localization is the bottleneck" (arxiv 2310.01798); reward over-optimization scaling laws (Gao et al. PMLR v202); agentic loop dynamics + the three mandatory exits.

---

## 12. Out of scope / dependencies
- **Human-supplied assets (the current request to Richard):** the licensed brand font file (else the OSS face, §8); the **4 missing case-study client photos** (`case-study-1/-2/-4/-5`); a **team/duo photo**; **press logos** ("Bekannt aus") + **client logos**; optionally an **environmental founder shot** (founder in their real workspace — more cinematic than the studio crop). **Photo-distribution principle (from the photo-botch correction — apply in Phase A):** founder recurs as the anchor (cover hero + small beside pull-quotes); proof/credibility photos are DISTRIBUTED as individual credibility moments, NOT crammed into one row (4b-1's first cut crammed proof-1/2/3); each case-study photo runs large on its own Fallstudie.
- GPU host (only if a local VLM is ever required; Railway has none).
- Layer-3 post-processor (CMYK/PDF-X/bleed) — later.
- n8n Drive bridge for production asset sourcing (already decided; [CTX]).

## 13. Self-review (per brainstorming)
- **Placeholders:** none — every component names a concrete module seam, the rubric rows name their detection, the loop names its guards.
- **Consistency:** topology (§3) ↔ loop (§5) ↔ rubric (§6) ↔ perception (§7) all reference the same components; the rubric ids in §6 match [DNA]§C/§E and the renderer capabilities in [4b]§3.
- **Brand-agnostic:** §2 reaffirms it + adds the reference-grounding safeguard + the guard-test extension; every rubric row scores a device/relationship, never a client value.
- **Honesty (no overselling):** §1 + §5.5 + §8 state the renderer ceiling plainly; the loop "raises consistency to the bar, not the bar"; reachable ~80–85% + the residual named.
- **Scope:** one coherent architecture across the 3 layers + the new orchestration/data layers; per-phase implementation plans written at build time (writing-plans).
- **Resume-ready:** self-sufficient inline; the dependency graph (§0) is bidirectional; build resumes at Phase A.
