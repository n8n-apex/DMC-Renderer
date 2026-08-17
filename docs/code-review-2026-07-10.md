# Code review: DMC rebuild (2026-07-10)  [ALL 15 FIXED 2026-07-10, Path B]

STATUS: all 15 findings fixed. C1-C4 + D1 resolved by the Path B rewrite of
service.py (render the real Chromium+treatments deck once, grade THOSE bytes,
ship them, cleanup in finally, no inline auto-redo). H1-H4/M1-M2/L1-L4 fixed
mechanically. Verified: regex/logic unit checks vs the review's exact failure
inputs (all pass), H1/H2 data-preservation asserts, treatment+guard suite (26
pass), live Path-B render (17=17, overflow 0, content 0, honest data-QC 12/17:
5 need photos, 13 prose-stats), case-study page LOOKED (rail bleeds to sheet
foot, initials/numbering correct). See the fix note under each item.

DISCOVERY during the fix: the perception/rubric VISUAL grader is
WeasyPrint-calibrated and cannot read a Chromium PDF's font table (PyMuPDF
returns no fonts) -> run on the ship path it reports a clean deck as 0-cleared.
So the inline grade uses ONLY the engine-agnostic DATA checks (N01 missing
slots, N15 prose-stats); the full visual grade stays an offline design-QA tool.
Recalibrating the visual grader for Chromium is logged as FOLLOWUP.


Max-effort multi-agent review of everything built or changed in the rebuild
(service, build_live normalizer, treatment stylist/engine/catalog, the A4
case-study treatment, assembler QC + font changes, quality_loop compose, the
writer gate, Docker). 10 independent finder angles produced 88 candidates; each
survivor was checked by an adversarial verifier that read the actual code and
tried to refute it. **15 findings survived, every one CONFIRMED with a quoted
guilty line.** Ranked below by severity.

Legend: each finding gives the location, what is wrong, a concrete trigger, and
the fix.

---

# CRITICAL: the QC-and-ship pipeline grades one deck and ships another

These four are one architectural fault in the auto-redo flow added over the last
several turns. The grading and the shipping look at different bytes.

## C1. Reference-QC grades WeasyPrint / treatments-OFF renders, never the deck that ships
`dmc-renderer/service.py:49` (root cause spans `quality_loop/brain.py:278-302`, `conductor.py:262`, `stage_converge.py:121-145`)

- **Wrong:** `_grade_deck` injects `render_fn` (Chromium, treatments=True), but
  `run_stage` only uses it in the *compose* step. The actual per-page grading
  (`converge_deck` -> `converge_page`) never receives it and falls back to
  `assembler.render_package`'s defaults: `engine="weasyprint", treatments=False`
  (`assembler.py:687-688`). WeasyPrint is the engine this file's own docstring
  says "spilled" with wrong pagination, and treatments=False means case studies
  render in their legacy form, not the shipped A4 treatment.
- **Fails:** every graded request. `X-QC-Cleared`, `X-QC-Hard-Fails`, and the
  reference-QC strict gate describe an artifact that is never shipped. A deck
  clean under Chromium can show phantom overflow flags from the WeasyPrint grade.
- **Fix:** decided by the Path A / Path B choice below. Either thread
  `engine="chromium", treatments=True` through `converge_page`/`conductor`, or
  stop grading via the converge loop and grade the real shipped render directly.

## C2. The shipped composed PDF is never QC'd; all response fields come from the discarded raw render
`dmc-renderer/service.py:98`

- **Wrong:** the endpoint ships `qc["composed_pdf"]` (`service.py:98`, read at
  :153), but `overflow`, `content_defects`, `page_count`, `physical_pages`, the
  strict 422, and every `X-*` header are computed from the *raw* `result` bound
  at :93. `stage_converge.py:145` calls `render_fn(merged_dir, composed_out...)`
  and throws away its `RenderResult` (which carries the composed deck's own
  overflow + warnings), keeping only the path string.
- **Fails, direction 1:** compose flips a page's `layout_variant`, the composed
  re-render spills a sheet or prints a literal `None` -> it ships with
  `X-Overflow: 0`, `X-Content-Defects: 0`, strict passing.
- **Fails, direction 2:** the raw render overflows but the winning variant fixed
  it -> strict still 422s "overflow" and the page-count headers describe the
  wrong PDF.
- **Fix:** compute every QC field from the exact bytes that ship. If a composed
  deck is shipped, re-run the deterministic checks (overflow + content scan) on
  *it* and derive headers/gate from that.

## C3. A grader crash is swallowed, so strict mode ships an ungraded deck as HTTP 200
`dmc-renderer/service.py:74`

- **Wrong:** `_grade_deck`'s `except` returns `{"error": ..., "hard_fails": []}`.
  `render_endpoint` reads `hard_fails=[]`, so the reference-QC leg of the strict
  gate passes vacuously and the error string appears nowhere in the response.
- **Fails:** quality_loop import/dependency breaks in a deployment (or
  stage_converge raises every run). A client that set `_strict` specifically to
  refuse an un-QC'd deck receives the raw PDF, 200 OK, no signal anything failed.
- **Fix:** a grader error must fail closed under strict mode (422 with the error)
  and surface in a header/body field otherwise, never be treated as "passed".

## C4. `_engine` is ignored by compose: the shipped engine differs from the requested one, headers describe neither
`dmc-renderer/service.py:133`

- **Wrong:** `_engine` controls only the raw render; the compose re-render is
  pinned to Chromium. On a successful compose the Chromium PDF silently replaces
  the requested engine's output, while headers/gate still reflect the
  requested-engine raw render.
- **Fails:** `POST _engine="weasyprint", _grade=true` -> raw WeasyPrint render
  spills, strict 422s on overflow regardless of the shipped deck; non-strict
  ships a Chromium PDF the caller never asked for.
- **Fix:** one engine per request, used for render + grade + ship + headers.

---

# HIGH: content silently deleted or printed wrong

## H1. ST-05 credibility points silently deleted when the page already has stats
`dmc-renderer/build_live.py:116`

- **Wrong:** the `credibility_points = []` line sits *outside* the
  `if not d.get("stats")` guard that converts dict credibility points into
  stats. So when stats already exist, the conversion is skipped but the emptying
  still runs: the writer's credibility content is copied nowhere and deleted.
- **Fails:** ST-05 data with both `stats` and dict `credibility_points` -> the
  About page renders with no credibility points, no warning.
- **Fix:** only empty `credibility_points` in the same branch that actually moved
  its content into stats.

## H2. ST-14 string beliefs dropped (but only in a mixed list)
`dmc-renderer/build_live.py:90`

- **Wrong:** the belief normalizer `continue`s past non-dict items, then
  overwrites the whole list whenever at least one dict survived. String beliefs
  (which the legacy P-5 pattern renders via its else-branch) vanish. An
  all-strings list is left untouched, so the same input shape is handled two
  different ways.
- **Fails:** `beliefs = ["Kaltakquise ist tot", {belief,reality}]` -> the string
  myth disappears from the page; alone in an all-string list it would have
  rendered fine.
- **Fix:** preserve non-dict beliefs (pass them through unchanged) instead of
  dropping them.

## H3. German percentages render as a truncated wrong number in the big result KPI
`research/v7-renderer/treatment_engine.py:241`

- **Wrong:** `_PERCENT_FIGURE_RE` does not cross a German decimal comma or a
  thousands dot, so it grabs only the fragment after the separator. Verified by
  running the regex: `"12,5 %"` -> `"5 %"`, `"3,5%"` -> `"5%"`, `"1.200 %"` ->
  `"200 %"`. `_result_from` feeds that to `horizontal_process` as the >=40pt
  gauge figure.
- **Fails:** an ST-06 mechanism deck ships with a prominently wrong headline
  number.
- **Fix:** the figure pattern must include `[.,]` inside the digit run
  (`\d[\d.,]*`), then normalize.

## H4. Any trailing parenthetical is rendered as a study citation
`research/v7-renderer/treatment_engine.py:244`

- **Wrong:** `_SOURCE_RE` treats any sentence-final `(...)` as the source
  caption. Ordinary German asides land in the citation slot.
- **Fails:** `"Antwortquote steigt um 35 % (im Schnitt)."` -> "im Schnitt"
  printed under the KPI as if it were the figure's source.
- **Fix:** only treat a parenthetical as a citation when it matches a
  source shape (contains a year, or `Name, Year`), else leave it in the text.

---

# MEDIUM: the content-QC gate is wrong in both directions

## M1. The literal-None scan false-positives on the English word "None" -> permanent 422
`research/v7-renderer/assembler.py:767`

- **Wrong:** `(?<![\w])None(?![\w])` matches the ordinary word None in real
  copy, not just a leaked Python `None`.
- **Fails:** a quote or English deck with "None of the agencies delivered this"
  -> content_defect -> strict 422 on every loop iteration; the copy is
  legitimate, so the loop can never clear it.
- **Fix:** detect leaked nulls structurally (a field that stringified `None`),
  not by scanning rendered prose for the word.

## M2. The dict-repr leak detector misses lists and numeric-key dicts
`research/v7-renderer/assembler.py:772`

- **Wrong:** the regex `\{\s*['"]` only matches dicts with quoted string keys.
  Leaked list/tuple reprs and numeric-key dicts pass silently.
- **Fails:** a template prints `"['Ausgangssituation', 'Ziel']"` or `"{0: ...}"`
  -> no warning, `X-Content-Defects: 0`, and a PDF with visible Python reprs
  ships (the exact defect class this gate exists to catch).
- **Fix:** broaden the structural detector to list/tuple/any-key dict reprs, or
  better, prevent reprs at the source (adapters/templates never stringify a
  container).

---

# LOW: cosmetic and edge cases

## L1. Legacy fallback re-stamped as A3 -> A4 content on an A3 sheet
`research/v7-renderer/assembler.py:784`

- **Wrong:** `used_f or page.get("page_format")` re-applies a package-declared
  `page_format="a3"` even when the treatment fell back to the legacy A4 pattern,
  contradicting `_render_one_page`'s explicit "not mis-sized to A3" guarantee.
- **Fails:** an ST-07A page carries the ST-07C `page_format:"a3"` signal but
  `a3_case_study` misfits/raises -> the A4 legacy fragment is stamped
  `format-a3` and laid on the wide sheet.
- **Fix:** when a page renders legacy (treatment None), do not honor a treatment
  page_format signal; keep it A4.

## L2. A 4mm cream strip under the "full-bleed" dark rail on every case study
`research/v7-renderer/styles/treatments/a4_case_study.css:22`

- **Wrong:** grid height 257mm + rail `bottom:-20mm` = 293mm on a 297mm sheet
  (16mm top margin + 257 + 20). The rail ends 4mm above the sheet foot.
- **Fails:** a constant light band at the bottom-right below the dark rail,
  contradicting the file's own bleed claim.
- **Fix:** extend the rail bleed to reach the sheet foot (bottom:-24mm, or a
  grid height that accounts for the full 261mm content box).

## L3. German honorifics produce the wrong initials avatar
`research/v7-renderer/templates/treatments/a4_case_study.html.jinja:28`

- **Wrong:** initials come from the first two whitespace tokens of `kunde.name`.
- **Fails:** "Dr. Anna Berger" -> "DA" not "AB"; "Prof. Dr. Weber" -> "PD".
- **Fix:** strip leading honorifics (Dr., Prof., etc.) before taking initials,
  or prefer the explicit `kunde.initials` and only derive as last resort.

## L4. Double-digit case numbers render malformed
`research/v7-renderer/treatment_engine.py:342`

- **Wrong:** the eyebrow is built `f"{_KICKER_BASE} 0{number}"` with a hard-coded
  leading zero. The A4 ghost numeral (eyebrow's last token) inherits it.
- **Fails:** a 28+ page report (the ST-07C tier this change supports) with
  `fallstudie_number=10` -> "FALLSTUDIE 010" and a giant "010" ghost numeral; a
  pre-padded string "03" -> "003".
- **Fix:** zero-pad only single-digit ints (`f"{int(number):02d}"`), pass
  through already-formatted strings.

---

# DISK: the leak fix is incomplete

## D1. Cleanup runs only on success, not in a finally; the temp package is never reclaimed
`dmc-renderer/service.py:64`

- **Wrong:** the `rmtree` of `converge/pages` + `converge/merged` runs only on
  the success path. Any exception from `run_stage` (compose copytree or the
  composed re-render, including the ENOSPC case this hygiene was added for)
  skips it. Separately, the `dmc_live_*` tempdir from `build_live_package`
  (full package + raw render PNGs + composed output) is never removed on any
  path, success or failure.
- **Fails:** a Chromium crash or disk-pressure mid-request leaves the GB-scale
  per-page iteration renders (the documented 2026-07-04 disk-filler) on disk;
  every request leaks its `dmc_live_*` dir regardless.
- **Fix:** move cleanup into a `finally`, and give the temp package dir a
  cleanup policy (delete after the response is written, or a TTL sweeper).

---

## The one decision (blocks C1/C2/C3/C4)

The auto-redo-inline-in-the-render-request design is broken (grades wrong
artifact), slow (full deck + up to 3 re-renders per page + a full recompose),
and a disk bomb. Two ways forward:

- **Path A (keep inline auto-redo, fix it):** thread Chromium+treatments through
  `converge_page`/`conductor`, and re-QC the composed deck. Faithful to the
  requested flow; real work inside fragile quality_loop internals.
- **Path B (recommended):** `/render` renders the real Chromium+treatments deck
  once, QCs those exact bytes, and ships them. The auto-redo becomes a separate,
  deliberate offline pass. Fixes C1-C4 + D1 in one move; fast and honest.

The other 11 findings (H1-H4, M1-M2, L1-L4, and the temp-dir half of D1) are
mechanical and get fixed regardless of A/B.
