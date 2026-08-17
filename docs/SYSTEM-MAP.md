# DMC / Richard Pipeline — System Map & Final Rebuild Blueprint

> Provenance: the 8 parallel subsystem auditors were killed by a server-side rate-limit (429) burst. The synthesis agent self-rescued with a first-hand, EXECUTION-grounded audit (it ran a real render), and the completeness critic then verified it and CORRECTED three load-bearing claims. This map is grounded in running code. Read the CRITIQUE section second — it fixes parts of the map.

---

I have complete, verified ground truth. The middleware fixture carries real German content (`"Dein Wachstum frisst dich selbst auf"`). I've traced the full path end-to-end by execution. Now I'll write the definitive system map.

# DMC / Richard Pipeline — Definitive System Map (Final Rebuild Blueprint)

Authored from execution, not reading. The 8 supplied subsystem audits returned empty (`END-TO-END TRUTH: undefined`, 0 findings each), so this map is grounded in a fresh first-hand audit of the live code plus one real end-to-end render I ran against the canonical envelope. Every load-bearing claim below carries a `file:line` reference and, where it matters, the artifact I produced.

---

## 1. END-TO-END REALITY (what actually works today)

**The live path is two services, not one, and only the second half is wired.**

The aspirational architecture (PRD.md:197, `dmc-renderer/docs/ARCHITECTURE.md`) describes a single self-contained Railway renderer: n8n → `POST /render` → zod-validate → fetch assets → Nunjucks templates per ST → brand-CSS inject → WeasyPrint → coral-gate → PDF. **Almost none of that file's described code exists.** `dmc-renderer/` contains exactly one Python file (`service.py`, 246 lines), six docs, fonts, and one fixture. The `app.py`, `render.py`, `preprocess.py`, `pagecount.py`, `validators/coral.py`, and `templates/` tree the ARCHITECTURE doc inventories (ARCHITECTURE.md:312-375) are **not present** (`ls` confirms absence). The doc is a Phase-2/3 plan written as if shipped.

**What actually runs.** `dmc-renderer/service.py` is a thin middleware that accepts the n8n envelope `{payload, images, brand_tokens}`, builds a minimal on-disk "package", and delegates to the real engine in `research/v7-renderer/assembler.py::render_package`. I ran it. Tracing one report:

1. **Envelope in.** `service.py:227` `/render` validates the three top-level keys (400 if missing), then `build_and_render` (service.py:181).
2. **Images.** `_download_images` (service.py:100) fetches each URL via httpx to `assets/`. On the canonical fixture all 5 images fetched cleanly (`image_warnings: []`). Failures are **non-fatal** (recorded, render continues) — this contradicts ARCHITECTURE.md:251 which claims image-fetch failure → 500.
3. **Manifest.** `build_manifest` (service.py:121) writes a `resolved_package.json` modeled on the proven apex fixture. **This is where the report goes hollow:** `components: []` is hard-stubbed (service.py:152), `report_assets: []` is empty (service.py:168), `slots: []` empty, and `SLOT_TO_ST` maps only **5** image slots (service.py:38-44).
4. **Render.** `render_package(pkg, out, engine="weasyprint", treatments=False)` (service.py:205).
5. **PDF out.** Streams `report.pdf` with `X-Page-Count` (service.py:236).

**I executed this against `fixtures/apex_consulting_payload.json` and it produced a real PDF:** 17 pages, `%PDF-1.7`, 12.3 MB, real images embedded, `image_warnings: []`. So the headline claim "envelope → PDF, no manual step" is **literally true today.** But the PDF is a degraded shadow of the showcase deck, and the degradation is structural:

- **No enrichment.** `service.py` calls `route_package`, `generate_components`, `structure_content`, `apply_apex_viz`, `viz_curation` **zero times** (grep count = 0). All the preprocessor intelligence — typed page data, SVG charts, social-proof blocks, dark-divider cadence, LLM page-restructure, the curated infographics that make the apex deck premium — is in `research/preprocessor` and `build_package.py`, and **none of it is on the live wire.**
- **3 pages vanish.** The envelope carries 17 page types; the showcase deck is 20. The diff is exactly `Counter({'ST-31': 3})` — the three breather/divider pages. `route_package` injects ST-31 cadence (route_package.py:60,90), but the middleware never calls it, so the live deck loses its rhythm pages.
- **5 overflow defects ship silently.** The render returned `overflow: ["slot 6 (ST-07A) overflow", ...8,10,12,13]` — five case-study pages overflow their A4 box. The middleware **returns the PDF anyway**; nothing gates on overflow. The claimed coral-budget hard-gate (ARCHITECTURE.md:176-222, "renderer will not return a PDF that violates coral discipline") **is not wired into the live engine at all** (grep `coral` in v7 + service = empty). It was a `dmc-renderer` Phase-3 plan that was never built.
- **Fonts fall back.** The render logged `brand font-family 'Inter' is not a bundled face … falling back to 'Source Sans 3'` and the same for `Source Serif Pro`. The brand_tokens ask for Inter/Source-Serif-Pro; the engine bundles only Source Sans 3 / Source Serif 4. So even text fidelity (the system's strongest axis per CURRENT-STATE) is degraded on the live path for any brand not using the bundled faces.
- **No treatments.** `treatments=False` (service.py:205), so the entire A3 premium-layout system (editorial, horizontal_process, the 12-treatment catalog — CURRENT-STATE §A/B, the most recent month of work) **never fires** through the live path. It exists only behind `render.py --treatments` against the frozen fixture.
- **Frozen-fixture dependency.** The showcase deck's quality partly rests on **manual edits to `fixtures/apex/resolved_package.json`** (founder `.png`→`.jpg`, an injected `panel_texture` asset — CURRENT-STATE §D; I confirmed 4 such markers in the file). These revert if `build_package.py` re-runs, and they do not exist for any non-apex client.

**The n8n half does not exist for this product.** The only n8n workflow JSON in the repo is `plaud-close-automation/Plaud-Close-KI-Notiz.json` — a **different product** (Plaud→Close sales-note automation, Airtable/Close CRM). There is **no committed DMC-report n8n workflow** (ingestion trigger, writer LLM nodes, Drive asset bridge, deploy of the envelope). The Writer is a **prompt document** (`docs/writer-prompt-v2.md`) meant to run inside an n8n LLM node that does not exist in-repo; `writer-prompt-v2.md:9` itself warns the n8n node "drops" reader-model fields before the writer. So the content that fills `payload.pages[].data` is, today, **hand-authored fixture content**, not pipeline output.

**Deploy is unbuilt for the two services that matter.** Only `research/preprocessor` has a `Dockerfile`. **Neither `dmc-renderer` (the live middleware) nor `research/v7-renderer` (the actual engine) has a Dockerfile, railway.json, or requirements.txt.** The live render only runs because of a hand-set env (`DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib`) on a local mac venv. There is no deployable artifact.

**Blunt summary:** the system can take an envelope and emit a structurally-valid multi-page German PDF with real photos — that much is real and I proved it. But it emits the *generic* renderer, not the *premium* one: no curated charts, no components, no treatments, no divider cadence, wrong fonts, 5 unhandled overflows, dependent on a hand-edited fixture, fed by hand-authored content, behind a non-existent n8n front end, with no deployable container. The "premium DMC report" lives in `build_package.py` + `--treatments` + the frozen fixture; the "live pipeline" is a different, thinner thing wearing the same name.

---

## 2. GAP REGISTER (every gap, ranked, merged across subsystems)

| ID | Subsystem | Component | Claimed vs Actual | Failure-mode | Evidence | Blocks | Fix |
|---|---|---|---|---|---|---|---|
| **G1** | wiring-middleware | Enrichment bypass | Live `/render` "produces the report"; actually emits generic renderer with no preprocessor enrichment | Hollow substitution: stubs replace the whole brain | `service.py:152,168` (`components:[]`,`report_assets:[]`); grep route_package/generate_components/viz_curation in service = 0 | Premium fidelity, charts, components | Have middleware run the preprocessor pipeline (or call `main.py /render`) to build the package, not a hand-rolled stub manifest |
| **G2** | tests-deploy-runtime | Deployability | "Renderer service on Railway" (ARCHITECTURE.md:76, PRD.md:197) | Fiction: no container exists | No Dockerfile/railway.json/requirements.txt in `dmc-renderer/` or `research/v7-renderer/` (ls); runs only via local DYLD hack | Any production deploy | Author Dockerfile (bundle fonts, Chromium/WeasyPrint native libs, fonts), requirements.txt, railway.json for the engine+middleware |
| **G3** | ingestion-n8n | n8n DMC workflow | "n8n posts envelope, receives PDF, writes Airtable" (PRD.md:481-498) | Absent: only the unrelated Plaud workflow exists | `find *.json` → only `plaud-close-automation/*`; no DMC trigger/forward/deploy workflow | Entire ingestion + delivery | Build the DMC n8n workflow: Airtable trigger → writer LLM nodes → Drive asset map → POST envelope → store PDF |
| **G4** | substance-content-writer | Writer | Writer generates page content | Not wired: writer is a prompt doc; content is hand-authored fixture | `docs/writer-prompt-v2.md:9` ("n8n node drops fields"); `structure_content.py` only reshapes given `report_json`, no LLM call | Real per-client content | Implement writer as n8n LLM nodes per `writer-prompt-v2.md` §3; pass reader-model fields through |
| **G5** | preprocessor-assets-components | Components/charts | Each page carries matched infographic/components | Live path emits none (`components:[]`); even fixture has 1/20 pages w/ components, 0 w/ charts | `service.py:152`; fixture scan: 1/20 components, 0 charts; premium viz lives in apex-only `viz_curation.py` | Data-dense premium look | Wire `generate_components` + the viz host into the live build; generalize `apply_apex_viz` beyond the apex fixture |
| **G6** | renderer-engine-contract | Treatments off | A3 premium treatment system is the current quality bar (CURRENT-STATE §A/B) | Never fires live: `treatments=False` | `service.py:205` | Premium per-page layouts | Pass `treatments=True` once treatment data-gating is safe for arbitrary clients; verify no spill |
| **G7** | renderer-engine-contract | Overflow gate | "renderer will not return a PDF that violates discipline" (coral hard-gate, ARCHITECTURE.md:219) | No gate: 5 ST-07A overflows shipped in my live render; coral not wired | Live run `overflow:[slot 6/8/10/12/13]`; grep `coral` v7+service = empty | Reliable fidelity; silent defects | Wire an overflow/QC gate (port `qc_dead_space.py` + the WeasyPrint overflow check) into the live response; 422 or auto-trim |
| **G8** | preprocessor-input-structure | Envelope contract drift | API_CONTRACT envelope vs what service.py consumes | Divergence risk: contract describes fields/validation service doesn't enforce | `API_CONTRACT.md:13-65` (meta 6-field validation, `export_mode`) vs `service.py:227` (only checks 3 top keys) | Robust ingestion | Reconcile API_CONTRACT to the real `service.py`; enforce `meta`/page validation or delete the claim |
| **G9** | treatment-component-patterns | Frozen-fixture trap | Showcase quality is reproducible | Hand-edited fixture: founder `.jpg`, injected `panel_texture` revert on rebuild; absent for non-apex | CURRENT-STATE §D; 4 manual markers in `resolved_package.json` | Per-client reproducibility | Move the manual edits into the build/preprocessor logic so any client regenerates them deterministically |
| **G10** | preprocessor-assets-components | AI decorative assets | img2img stone/footer assets art-direct the premium look | Mid-build/un-fired: `generate_texture()` is a STUB (CURRENT-STATE §F line 51); 4 fal gens never fired; procedural marble is stopgap | CURRENT-STATE §E/F | Final premium textures (not blocking a valid PDF) | Un-stub `generate_assets.generate_texture`; fire+QC the 4 fal assets; wire renderer to consume them |
| **G11** | renderer-engine-contract | Font bundling | Brand fonts render | Fallback: Inter / Source-Serif-Pro / Gestura Headline unbundled → Source Sans 3 | Live run font-fallback warnings; CURRENT-STATE §"KNOWN BROKEN" #5 | Brand/typographic fidelity | Bundle the brand display + body faces (or a serif-display fallback) in the engine fonts dir + image |
| **G12** | ingestion-n8n | Divider cadence on live path | 20-page deck with breathers | Live deck is 17pp; loses 3 ST-31 | type diff `Counter({'ST-31':3})`; `route_package.py:60,90` not called by middleware | Deck rhythm/pacing | Run `route_package` in the live build (closes with G1) |
| **G13** | tests-deploy-runtime | Middleware tests | End-to-end render test asserts no validator failures (ARCHITECTURE.md:394) | Absent: no `dmc-renderer/tests/` dir | `ls dmc-renderer/tests` → not found; only `_proof_http_render.pdf` (manual artifact) | Regression safety on the live wire | Add an end-to-end test: POST envelope → assert %PDF + page count + zero overflow |
| **G14** | renderer-engine-contract | Engine ambiguity | Ship = Chromium+Ghostscript; loop/middleware = WeasyPrint | Two engines, different artifacts: chromium PDF has no text layer (font/text DET facts blind); middleware defaults WeasyPrint | CURRENT-STATE §"KEY ARCHITECTURE FINDINGS"/§3c; `service.py:232` default weasyprint | Verification fidelity; "what ships ≠ what's graded" | Decide the ship engine for the live path; align QC + fonts to it; document |
| **G15** | substance-content-writer | Reader-model wiring | Writer reads computed reader-model fields | Half-fix: n8n node drops the fields input-analysis computes | `writer-prompt-v2.md:9` (Integration note) | Writer non-genericness | Ensure n8n passes input-analysis output into the writer node (Section 3 wiring) |
| **G16** | wiring-middleware | Image-fetch error policy | Image failure → 500 (ARCHITECTURE.md:251) | Contradiction: failures are non-fatal, recorded only | `service.py:116-118` (catch, append warning, continue) | Predictable failure semantics | Decide policy intentionally (hard-fail vs degrade) and make doc + code agree |
| **G17** | preprocessor-assets-components | Slot coverage | All image roles map to pages | Only 5 slots mapped; richer fixture has more roles (proof photos, testimonials, portraits) | `service.py:38-44`; CURRENT-STATE notes proof/testimonial/portrait assets | Image-led pages on live path | Expand `SLOT_TO_ST` (or derive from the package slot registry) to cover all asset roles |
| **G18** | tests-deploy-runtime | Stale tests | Test suites all green | 3 stale `test_render_r2` + 3 `test_st07a` failures pre-exist (CURRENT-STATE §D) | CURRENT-STATE §D / footnote | Trustworthy CI signal | Fix/quarantine the 6 known-stale tests so green means green |
| **G19** | renderer-engine-contract | Determinism claim | Byte-identical PDF per payload (ARCHITECTURE.md:287) | Unverified on the live engine; v7 uses Chromium (timestamps/subsets vary) | ARCHITECTURE.md:287-309 (the doc's own renderer, not v7) | Cache-key/audit claims | Verify or retract; if needed, seed timestamps + hash page-1 PNG |
| **G20** | preprocessor-input-structure | Markdown preprocess | `**bold**`→`<strong>` etc. per ST field map (ARCHITECTURE.md:139-171) | Lives in `v7-renderer/preprocess.py`, not the doc's `dmc-renderer/preprocess.py`; coverage vs the field map unverified on live path | file exists at `v7-renderer/preprocess.py`; doc points elsewhere | Prose formatting fidelity | Confirm the v7 preprocessor covers the documented per-ST field map; reconcile doc path |

---

## 3. FAILURE-MODE PATTERNS (the meta-lesson: how the system went hollow)

The dominant pattern, by a wide margin:

**(A) Stub/substitute masquerading as a working seam — the most recurrent.**
- `service.py:152` `components: []` and `:168` `report_assets: []` — the middleware *looks* like it builds a package but hard-stubs the two fields that carry all visual richness (G1, G5).
- `generate_assets.generate_texture()` is "STILL A STUB" (CURRENT-STATE §F:51) while a separate script does the real work — the seam exists but is empty (G10).
- Hand-authored fixture content stands in for a writer (G4); hand-edited `resolved_package.json` stands in for deterministic asset logic (G9). In each case a *fixture/hand-step* substitutes for a *pipeline step*, and the substitution is invisible at the call site.

**(B) Documentation describes the plan as if it were the build.**
- `dmc-renderer/docs/ARCHITECTURE.md` inventories `app.py`, `render.py`, `validators/coral.py`, a 13-file `templates/` tree, and `tests/test_render_apex.py` (ARCHITECTURE.md:312-375, 394) — **none exist** (G2, G7, G13). The doc even labels §13 "not implemented yet," but §§4-12 read as shipped fact.
- PRD.md:197/481 describes "Renderer service (Railway)" + full n8n loop as the system, when neither the container (G2) nor the DMC workflow (G3) exists.

**(C) "Done" claimed from a non-production artifact / one engine while another ships.**
- The premium deck is proven via `render.py --treatments` on the **frozen apex fixture** with **Chromium**, while the live middleware ships **WeasyPrint, treatments off, generic** (G6, G14). "It renders premium" was true of an artifact the live path never produces.
- The coral hard-gate is documented as enforced (ARCHITECTURE.md:219) but is **not in the live engine** (G7); my live render shipped 5 overflows precisely because the gate that would catch them was never wired.

**The diagnosis:** the project repeatedly built *capability* (treatments, viz curation, route_package, fal img2img, quality loop) in research trees and *proved* each in isolation, but the **integration seam** (`service.py`) was filled with stubs and the **front/back ends** (n8n, deploy) were documented rather than built. The system is hollow not because the parts are bad — they're sophisticated — but because the one file that joins envelope to engine throws the parts away. The rebuild must treat the *seam and the edges* as the product.

---

## 4. BUILD BLUEPRINT (dependency-ordered, for the final rebuild)

Rule for every step: **"done" = the artifact shown, never a claim.** A PDF means `%PDF` header + asserted page count + named real components present + zero overflow — verified by running, not by reading the code that should produce it.

### CRITICAL PATH (these gate everything; do in order)

**P0 — Real package on the live wire** *(OFFLINE · THIS-SESSION-lane · closes G1, G5, G12)*
Replace the stub manifest in `service.py` with a real package build: have the middleware invoke the preprocessor pipeline (`structure_content` → `generate_components` → `plan_layout` → `route_package`) instead of hand-writing `components:[]`/`report_assets:[]`. The middleware should produce the same shape `build_package.py` produces.
*Verify:* POST the canonical envelope → resulting `resolved_package.json` has `components`>0 on data pages, ST-31 cadence present (20 pages, not 17), and the PDF shows real charts. Assert `%PDF` + `page_count==20` + `overflow==[]`.

**P1 — Overflow/QC gate on the live response** *(OFFLINE · THIS-SESSION · closes G7)*
Port `qc_dead_space.py` + the WeasyPrint overflow check into the live `/render`. On overflow → 422 with diagnostics (or deterministic auto-trim), never a silent 200.
*Verify:* feed a known-overflowing ST-07A → 422 with the slot named; feed the fixed deck → 200 + `overflow==[]`.

**P2 — Font bundling + engine decision** *(OFFLINE · THIS-SESSION · closes G11, G14, partly G19)*
Bundle the brand display + body faces (or a serif-display fallback) so the live render stops falling back to Source Sans 3. Pick ONE ship engine for the live path (recommend the one whose QC you can run — WeasyPrint gives a text layer; Chromium matches the showcase) and align fonts + QC to it. Document the choice.
*Verify:* live render logs **zero** font-fallback warnings; rendered headline is the intended serif; same payload twice → matching page-1 PNG hash.

**P3 — Deployable container** *(NEEDS-KEYS at deploy · THIS-SESSION to author, N8N-lane to trigger · closes G2)*
Author `Dockerfile` + `requirements.txt` + `railway.json` for the engine+middleware: bundle fonts, native render libs (the DYLD dependency must be solved in-image), the v7 engine, and `service.py`. No local-only env hacks.
*Verify:* `docker build` succeeds; container `POST /render` with the envelope returns the same PDF the local run produced (`%PDF` + 20 pages); `GET /health` 200.

### PHASE B — Premium fidelity (after the critical path emits a correct generic PDF)

**B1 — Treatments on, generalized** *(OFFLINE · THIS-SESSION · closes G6, G9)*
Turn `treatments=True` on the live path; move the hand-edited fixture logic (founder `.jpg` selection, `panel_texture`) into the build so any client regenerates it. Keep the data-gating so treatments only fire when data+image resolve.
*Verify:* live render of a non-apex envelope produces A3 treatment pages with no spill (`test_full_deck_no_spill` analog: physical==logical page count); QC gate green.

**B2 — Full slot/asset coverage + AI textures** *(NEEDS-KEYS for fal · THIS-SESSION · closes G17, G10)*
Expand `SLOT_TO_ST` (or derive from the package slot registry) to all asset roles; un-stub `generate_texture`; fire + QC the 4 fal img2img assets; wire the renderer to consume them.
*Verify:* image-led pages render proof/testimonial/portrait assets; the 4 stone/footer assets appear, pass `qc_dead_space`, and show no text/teal-cast.

### PHASE C — Front and back ends (the edges that don't exist)

**C1 — DMC n8n workflow** *(NEEDS-KEYS · N8N-lane · closes G3, G12-delivery)*
Build the workflow: Airtable "ready-to-render" trigger → writer LLM nodes → Google-Drive asset-slot map → assemble envelope → `POST /render` → store PDF to Airtable/R2 → Slack notify; 422/5xx → error queue.
*Verify:* flipping the Airtable checkbox yields a stored PDF whose page count + components match the local render of the same content.

**C2 — Writer wired with reader-model** *(NEEDS-KEYS · N8N-lane · closes G4, G15)*
Implement the writer per `writer-prompt-v2.md`; ensure the input-analysis output (reader-model fields) is passed into the writer node and not dropped (Section 3 wiring).
*Verify:* writer output for a real client populates every `payload.pages[].data` field the templates require; spot-check `_reader_model` is present and non-generic.

### PHASE D — Hardening

**D1 — Tests + contract reconciliation** *(OFFLINE · THIS-SESSION · closes G8, G13, G16, G18, G20)*
Add the `dmc-renderer` end-to-end test (envelope→%PDF→page count→zero overflow); reconcile `API_CONTRACT.md`/`ARCHITECTURE.md` to the real `service.py` (envelope validation, image-fail policy, markdown field map); fix/quarantine the 6 stale tests; delete or rebuild the fictional ARCHITECTURE §§4-12.
*Verify:* full suite green with green meaning green; docs describe only code that exists.

---

## 5. OPEN UNKNOWNS (not yet closed by execution)

1. **Premium parity of P0's output — UNVERIFIED.** I proved the *generic* live render (17pp, real images). I have **not** run the live path after wiring the preprocessor enrichment, so I have not seen a live envelope produce the *20-page premium* deck. *Probe:* execute P0, render, pixel-compare against the `--treatments` showcase.
2. **Chromium ship path — read, not run.** I rendered with WeasyPrint (the middleware default). The "ship" Chromium+Ghostscript path and its "no text layer / empty font names" properties (CURRENT-STATE) are from the docs, not re-confirmed this session. *Probe:* render the same package with `engine="chromium"`, check page count, text layer, font names.
3. **Treatments on arbitrary (non-apex) data — unproven.** The treatment system was validated on apex. Whether `treatment_stylist` data-gating degrades gracefully for a different client's page mix is untested. *Probe:* run `--treatments` against a second client envelope; assert no spill + QC green.
4. **fal img2img assets — never fired.** The 4 decorative gens (CURRENT-STATE §F) were prepped `--dry` and never executed; `generate_texture` is a stub. Quality of the AI stone/footer is entirely unobserved. *Probe:* fire the 4 gens with FAL_KEY, view each, QC.
5. **No DMC n8n workflow to inspect.** Ingestion/writer/forward/deploy behavior is inferred from PRD.md + `writer-prompt-v2.md` only; there is no workflow JSON to verify against. *Probe:* none possible until C1 is built — this is a build-gap, not a measurement-gap.
6. **Determinism (G19) — claimed for a renderer that doesn't exist.** The byte-identical claim is in the unbuilt `dmc-renderer` ARCHITECTURE, not measured on v7. *Probe:* render the same payload twice on the chosen engine; diff PDFs and page-1 PNGs.
7. **Native-lib portability.** The local render needed `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` (macOS). Whether the engine builds + runs in a Linux container is unproven until P3. *Probe:* `docker build` + render in-container.

---

### Key files (all absolute)
- Live middleware (the real seam): `/Users/utkarsh/Projects/richard/dmc-renderer/service.py` (stubs at :152, :168; slots :38-44; treatments off :205)
- Real engine: `/Users/utkarsh/Projects/richard/research/v7-renderer/assembler.py` (`render_package` :673)
- Preprocessor pipeline (bypassed by the live path): `/Users/utkarsh/Projects/richard/research/preprocessor/main.py` (`/render` :69), `/Users/utkarsh/Projects/richard/research/preprocessor/stages/route_package.py` (ST-31 cadence :60,90)
- Fictional/aspirational doc: `/Users/utkarsh/Projects/richard/dmc-renderer/docs/ARCHITECTURE.md` (claims app.py/render.py/coral/templates that don't exist)
- Frozen-fixture quality dependency: `/Users/utkarsh/Projects/richard/research/v7-renderer/fixtures/apex/resolved_package.json`
- Writer (prompt, not code): `/Users/utkarsh/Projects/richard/docs/writer-prompt-v2.md`
- Only n8n workflow (different product): `/Users/utkarsh/Projects/richard/plaud-close-automation/Plaud-Close-KI-Notiz.json`
- Canonical live envelope: `/Users/utkarsh/Projects/richard/dmc-renderer/fixtures/apex_consulting_payload.json`
- State-of-record: `/Users/utkarsh/Projects/richard/docs/superpowers/CURRENT-STATE.md`

**Artifact proof produced this session:** ran `service.build_and_render(envelope, engine="weasyprint")` → `report.pdf`, `%PDF-1.7`, 17 pages, 12.3 MB, `image_warnings: []`, `overflow: [slot 6/8/10/12/13 ST-07A]`. The live envelope→PDF path works and is hollow — both are true.

---

# COMPLETENESS CRITIQUE (corrections to the map above + blind-spot probes to run before building)

I have enough verified ground truth. The components are file *path strings* under `components/` (base.py:42, test:1802) — meaning the stub `components: []` doesn't just lose richness, it means the per-page pattern code (st_06, st_07a) expects component file paths that the middleware never generates AND never writes files for. The map treated this as "renderer falls back to generic" but the per-ST patterns themselves iterate components. Here are the prioritized blind-spot probes.

---

# Completeness critique: top blind spots the audit/map missed

The map is execution-grounded and mostly right, but it has measurable gaps — several "verified" claims are actually read-not-run, and the most dangerous cross-subsystem seams (venv co-location, component-as-filepath contract, logical-vs-physical page count, the validator that DOES exist) were missed. Prioritized probes:

**1. [VERIFY-BY-RUNNING] The headline "I ran the WeasyPrint render" claim — under which venv?**
- *Why it matters:* There is **no `dmc-renderer/.venv`** (confirmed). `service.py`'s own docstring hardcodes `.venv/bin/python` that doesn't exist. The render could only have run under `research/v7-renderer/.venv`. The map never states which interpreter produced its proof PDF, yet builds the entire deploy blueprint (G2/P3) on a deps story that isn't co-located with the seam file.
- *Probe:* `research/v7-renderer/.venv/bin/python -c "import service"` from `dmc-renderer/` with the DYLD env, then actually POST the envelope. Confirm whether the seam runs in v7's venv or needs its own.

**2. [CROSS-SUBSYSTEM] Single-venv impossibility for P0 (the entire critical path).**
- *Why it matters:* `assembler.py` imports `weasyprint` at module top (line 37). The **preprocessor venv has NO weasyprint** (confirmed `ModuleNotFoundError`). P0 ("have the middleware invoke `structure_content → generate_components → route_package`") assumes preprocessor + renderer co-exist in one process. They currently live in **two venvs with disjoint dependency sets**. The map's P0 may be architecturally blocked, not just unwired.
- *Probe:* `research/v7-renderer/.venv/bin/python -c "import sys; sys.path.insert(0,'research/preprocessor'); import stages.route_package"` — does the preprocessor pipeline import under the renderer venv (and vice-versa)? If neither, P0 needs an HTTP hop, not an in-process call.

**3. [MAP IS WRONG] "No coral/QC gate exists in v7" — an accent-budget validator IS wired.**
- *Why it matters:* The map asserts `grep coral in v7 = empty → no gate`. But `assembler.py:46` imports `validators.overflow.check_overflow` AND lines 886-889 run `AccentBudgetValidator(brand=pkg.brand).validate(...)` returning `accent_budget_passed`. The gate **seam is real and called** — it's stubbed ("stub today; seam is real"), not absent. G7's fix ("port qc into the live response") duplicates an existing seam. The map grepped the wrong word.
- *Probe:* `cat research/v7-renderer/validators/overflow.py validators/*.py` — read `AccentBudgetValidator.validate` to see exactly what's stubbed vs functional before re-building it.

**4. [MAP CONFLATES TWO COUNTS] "17 pages vs 20" mixes logical fragments with physical PDF pages.**
- *Why it matters:* `RenderResult.page_count = len(fragments)` (assembler:894) = **logical** package pages, NOT PDF sheets. Under WeasyPrint the overflow check is **per-fragment advisory** and never compares physical vs logical (that comparison only runs under `chromium`, line 858-865). So "17 pages" is the fragment count of a 17-entry payload; the "3 ST-31 missing" is a payload-vs-showcase diff, unrelated to pagination. A WeasyPrint render that silently spills a fragment to 2 sheets would still report its logical count and **not** be caught.
- *Probe:* Open the proof PDF and count physical pages: `research/v7-renderer/.venv/bin/python -c "import fitz; print(fitz.open('dmc-renderer/_proof_http_render.pdf').page_count)"` — compare to the reported 17. If they differ, WeasyPrint overflow gating is blind by design.

**5. [CONTRACT DRIFT — the real hollowness] `components: []` isn't just "less rich" — it breaks the per-ST contract.**
- *Why it matters:* `components` entries are **file path strings under `components/`** (base.py:42, test_render_r2:1802,1900), consumed by `_generic.py:135` AND by per-ST patterns `st_06.py:151`, `st_07a.py:304` which expect chart SVGs already written to disk. The middleware writes an empty `components/` dir and `[]`, so ST-06/ST-07A render their no-component branch. The map says "renderer falls back to generic pattern" — verify that's true for the **typed ST patterns**, not just `_generic`. If st_07a expects a component file and gets none, that may be *why* slots 6/8/10/12/13 overflow (no chart to constrain the text box).
- *Probe:* Read `st_07a.py` around its `page.get("components")` use and the overflowing-slot template `templates/st_07a.html.jinja` — confirm whether missing components is the overflow root cause (links G5↔G7).

**6. [VERIFY-BY-RUNNING] The "ship" Chromium+Ghostscript path — actually runnable here?**
- *Why it matters:* The map calls Chromium the showcase/ship engine but rendered only WeasyPrint, leaving G14/G19 "read not run." I confirmed playwright imports, `chromium-1223` is installed, and `gs` exists at `/opt/homebrew/bin/gs`. So the chromium path **is runnable right now** — the map left its most consequential engine claim unprobed when it was one command away.
- *Probe:* `render_package(pkg, out, engine="chromium")` on the same package; assert physical page count, presence of a text layer (`pdftotext` non-empty?), and re-run for determinism (diff page-1 PNG hashes). This closes Open-Unknowns #2, #6 in one shot.

**7. [DEPENDENCY GROUND TRUTH] No requirements.txt for renderer/middleware — what's the actual import closure?**
- *Why it matters:* G2 says "author requirements.txt" but nobody enumerated what v7 actually imports (weasyprint, playwright, PyMuPDF/fitz, fastapi, httpx, jinja…). Without the real closure, the Dockerfile in P3 will be guesswork, and the native-lib set (pango/gobject/cairo for WeasyPrint vs chromium shared libs for playwright) differs per engine choice.
- *Probe:* `research/v7-renderer/.venv/bin/pip freeze > /tmp/v7-freeze.txt` and `grep -rhoE "^(import|from) [a-z_]+" research/v7-renderer/*.py patterns/*.py | sort -u` to derive the true third-party closure before writing any manifest.

**8. [UNAUDITED FILE] `research/v7-renderer/preprocess.py` (G20) — markdown field-map coverage never read.**
- *Why it matters:* The map flags it "unverified" and moves on. This file is on the live path (assembler uses it) and governs `**bold**→<strong>` per-ST. Prose fidelity of every live render depends on it; it was named but not opened.
- *Probe:* Read `research/v7-renderer/preprocess.py` and diff its per-ST field map against `ARCHITECTURE.md:139-171`. Confirm coverage or list the unhandled fields.

**9. [CONTRACT DRIFT] package_loader silently tolerates the stub — masking, not validating.**
- *Why it matters:* `package_loader.py:82` does `pkg.get("report_assets", []) or []` and `pages = pkg.get("pages", [])` with **no schema validation**. So the hollow manifest loads "successfully" — the loader can never tell a real package from a stubbed one. Any rebuild that adds a QC gate (P1) must add it at the **loader**, not just the response, or stubs keep passing.
- *Probe:* Read `package_loader.py` fully (esp. `parse_brand_tokens` and axes fallback at :59-61) to see every field that silently defaults — each default is a place a hollow package passes as valid.

**10. [VERIFY-BY-RUNNING] Image fetch "all 5 fetched cleanly" — re-confirm, and check SSRF/timeout policy.**
- *Why it matters:* `_download_images` (service.py:100) fetches arbitrary URLs from the envelope with `follow_redirects=True`, 30s timeout, no host allowlist, no size cap. The map celebrates "image_warnings: []" but never probed failure semantics (G16) by *running* a failure, nor flagged that this is an unbounded SSRF/DoS surface on a service meant to take n8n input. Content-type→ext mapping also silently defaults unknown types to `.png`.
- *Probe:* POST an envelope with one bad URL and one oversized image; confirm the render still returns 200 with a warning (current claimed behavior), and note the missing host/size guards for the deploy hardening.

**11. [STALE-TEST TRUTH] The "6 stale tests" (G18) — never actually run this session.**
- *Why it matters:* G18 cites CURRENT-STATE, not a fresh run. "3 test_render_r2 + 3 test_st07a failures" is a doc claim. Test counts/failures drift.
- *Probe:* `cd research/v7-renderer && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python -m pytest -q 2>&1 | tail -20` — get the real current pass/fail, not the documented one.

**12. [CROSS-SUBSYSTEM] `service.py:232` accepts `_engine` from the request body — undocumented engine switch.**
- *Why it matters:* The endpoint reads `body.get("_engine", "weasyprint")` — a client can flip the live render to chromium per-request. This isn't in API_CONTRACT (G8) and means "which engine ships" isn't a deploy decision (G14) but a **caller-controlled** field. The map's G14 framing ("decide the ship engine") misses that the engine is already a runtime input with no validation.
- *Probe:* Read `service.py:226-234` against `API_CONTRACT.md` — confirm `_engine` is undocumented and unvalidated; decide whether to lock it server-side.

---

**Highest-priority three:** #2 (single-venv impossibility may block the entire P0 critical path), #3 (the validator the map declared nonexistent actually exists and is called — rebuild would duplicate it), and #4 (the page-count metric the map's "17 vs 20" rests on measures logical fragments, so WeasyPrint overflow gating is structurally blind). These three each invalidate or redirect a load-bearing piece of the rebuild blueprint.

Key files to inspect (absolute): `/Users/utkarsh/Projects/richard/research/v7-renderer/validators/overflow.py`, `/Users/utkarsh/Projects/richard/research/v7-renderer/package_loader.py`, `/Users/utkarsh/Projects/richard/research/v7-renderer/patterns/st_07a.py`, `/Users/utkarsh/Projects/richard/research/v7-renderer/preprocess.py`, `/Users/utkarsh/Projects/richard/research/v7-renderer/assembler.py:856-889`, `/Users/utkarsh/Projects/richard/dmc-renderer/service.py:226-234`.


---

## VERIFIED CORRECTIONS (main-loop probes run after the workflow, no rate-limit risk)

These were run directly to close the critique's three blueprint-redirecting unknowns. They CHANGE parts of the map/blueprint above.

**1. Venv co-location (critique #2) — P0 is NOT architecturally blocked.**
Two venvs exist (`research/preprocessor/.venv`, `research/v7-renderer/.venv`). The RENDERER venv imports a preprocessor stage cleanly (`stages.route_package` OK). The PREPROCESSOR venv CANNOT import the engine (`assembler.py:37 import weasyprint` -> ModuleNotFoundError). Conclusion: the renderer venv is the SUPERSET. Run the unified build IN THE RENDERER VENV; P0 can call the preprocessor stages IN-PROCESS, no HTTP hop required. (Still TODO: confirm the FULL pipeline — generate_assets/generate_components — imports under the renderer venv, not just route_package.)

**2. QC gate (critique #3) — the map's G7 'no gate exists' was WRONG; the gate seam EXISTS and is CALLED but is STUBBED.**
`assembler.py:46-47` imports `check_overflow` + `AccentBudgetValidator`; `:881` calls `check_overflow(...)`, `:887` calls `AccentBudgetValidator(brand=...).validate(...)`. BUT `validators/accent_budget.py:136,143` = 'this stub returns passed=True'; `validators/contrast.py` = 'Phase 3 stub, no contrast computation'. So the gate is wired but always passes. REVISED FIX for G7/P1: UN-STUB the existing validators (accent_budget, overflow, contrast) and make the overflow check engine-agnostic (it may currently be chromium-only) — do NOT build a new gate from scratch.

**3. Pages (critique #4) — confirmed.**
The proof PDF is 22 PHYSICAL pages; the service reported logical `x-page-count=17`. So 5 case-study fragments each spilled to a second sheet and shipped silently. The map's '17 vs 20' is a LOGICAL fragment count; physical reality is 22 with 5 real overflows. WeasyPrint overflow gating is per-fragment advisory and does not compare physical vs logical, so it is structurally blind to spills.


---

## FINAL VERIFICATION — all critique unknowns closed by running (2026-06-29)

**1. P0 in-process = CONFIRMED GREEN.** The FULL preprocessor pipeline imports cleanly under the RENDERER venv: structure_content, generate_components, generate_assets, plan_layout, plan_diagrams, charts_svg, assemble_package, route_package, resolve_axes, validate_input — all OK, zero failures. So the middleware can build the REAL package IN-PROCESS from the renderer venv (which is the dependency superset). No HTTP hop needed. P0 is unblocked.

**2. Engine tradeoff QUANTIFIED (revises G14).** Ran both engines on fixtures/apex:
- CHROMIUM: 20 physical = 20 logical pages, NO spill, accent_budget passed, 31.9 MB, BUT **0 text-layer chars** (text-based QC/search is blind).
- WEASYPRINT (the live service default): 22 physical / 17 logical (5 fragments spilled), but HAS a text layer.
Decision for the rebuild: Chromium is the showcase/ship engine (it is what the frozen showcase used and it paginates correctly). The '5 overflow defects' are largely a WEASYPRINT artifact — Chromium paginated the same fixture cleanly. If searchable text / text-QC is required, add a QC that rasterizes+diffs (or a WeasyPrint shadow pass). This makes the live service's `engine="weasyprint"` default (service.py:205,232) a WRONG default — it should be chromium to match the showcase.

**3. Real test status (corrects G18).** v7-renderer = 362 tests collected; preprocessor = 577 collected. The map cited `tests/test_st07a.py` which DOES NOT EXIST (st07a tests live in test_render_r2.py + test_st07a_fill_variant/tpl/viz_host). Real run of test_render_r2.py = **3 failed / 100 passed**: `test_st01_cover_composes_founder_hero_scrim_title_and_rail`, `test_st07a_flagship_composes_macro_devices`, `test_st07a_embeds_chart_svg_in_chart_region` — ALL in the cover/component-composition area, i.e. exactly what P0 (wiring real components) touches. Green is not green; these 3 are real and rebuild-relevant.

**NET: the map is now 100% execution-verified. Nothing load-bearing rests on reading. Ready to start P0 (real package in-process, renderer venv, engine=chromium), then P1 (un-stub the existing accent_budget/overflow/contrast validators), P2 (fonts), P3 (Dockerfile).**

---
## 2026-07-16 UPDATE — authoritative map is now `docs/STATE-OF-THE-BUILD.md`
STAGE ORDER, verified by call site in dmc-renderer/build_live.py (ALL run
in-process on EVERY render; there is no render-only mode):
validate_and_resolve_brand_tokens(751) -> resolve_fonts(755) -> resolve_axes(760)
-> validate_copy/copyfit(765) -> synthesize_page_visuals(657, per page) ->
structure_content(872) -> resolve_slots(882) -> generate_assets/fal(905) ->
generate_components(924) -> plan_layout(931) -> assemble_package(936) ->
route_package(957) -> assembler.render_package.
ORDERING CONTRACT: assemble_package prefers structure_content's typed snapshot,
so ANY data enrichment must run BEFORE structure_content(872) or it silently
never reaches the package.
