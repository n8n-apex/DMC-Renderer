# Fixture Validation Issues — Apex / Jousef Payload

Validated `dmc-renderer/fixtures/apex_consulting_payload.json` against the 11 ST schemas in the brief. The Writer Pipeline produces content that violates the brief's character budgets in 7 places, omits an optional field in 3 case studies, and over-counts `symptoms` by 1.

These are **Writer-Pipeline issues, not renderer issues** — but the renderer must handle them gracefully (degrade, never crash). Listing here so Richard can route the fixes upstream.

## 1 · Character-budget violations (7)

| Slot | ST | Field | Actual | Budget | Direction |
|---|---|---|---|---|---|
| 1 | ST-01 | `intro_body` | 860 | 300–500 | over by 360 |
| 2 | ST-02 | `body` | 1321 | 700–1100 | over by 221 |
| 3 | ST-05 | `body` | 1579 | 400–700 | over by 879 (≈2.3× max) |
| 4 | ST-09 | `body` | 504 | 700–1200 | **under** by 196 |
| 5 | ST-14 | `intro` | 188 | 200–400 | under by 12 |
| 15 | ST-FAZIT | `body` | 1029 | 500–800 | over by 229 |
| 15 | ST-FAZIT | `bold_thesis` | 125 | 40–100 | over by 25 |

**Renderer mitigation:** templates use CSS `.shrink-fit` class (10pt → 9.5pt body) on overflowing pages; if still overset, fail with structured warning. No crash.

## 2 · Empty `wendepunkt` field (3 / 5 case studies)

`wendepunkt` is marked optional in the brief schema. Cases 2, 3, 4 have empty strings; cases 1 and 5 have it.

**Renderer behavior:** when `wendepunkt` is empty, the entire "WENDEPUNKT" sub-heading + block is skipped (no orphan label). Already handled by template conditional.

## 3 · Symptom count exceeds schema range

ST-09 schema says `symptoms[3-5]`. Fixture has **6 symptoms**.

**Renderer behavior:** template's symptoms grid is `repeat(auto-fill, minmax(...))` so 3, 4, 5, or 6 all flow correctly. Confirmed working in all 4 reference reports (some show 6, some 7, some 8 — actual usage exceeds spec).

## 4 · Mechanism step count exceeds schema range

ST-06 schema says `steps[3-5]`. Fixture has **6 steps**.

**Renderer behavior:** linear list flows N steps regardless. No issue.

## 5 · Page-number metadata is stale (overlaps and skips)

See `0-reference-analysis.md` §5 — slots 11–15 have overlapping/skipping `page_numbers`. Renderer uses `slot` order as canonical and recomputes page numbers.

## 6 · Markdown in body fields

`key_insight` (ST-07B) and `bold_thesis` (ST-FAZIT) contain `**bold**` markdown. Example: `**Operative Engpässe...**`.

**Renderer behavior:** the renderer's text preprocessor must support a light markdown subset:
- `**text**` → `<strong>` (always render bold)
- `*text*` → `<em>` (render italic)
- Newlines preserve as `<br>` or paragraph breaks (depending on context)
- Nothing else (no headings, no lists — those come from structured fields)

## 7 · Page-count total: 22 vs 20 target

With the visual layout in `0-reference-analysis.md` §5, the fixture's 17 slots produce ~22 physical pages (because ST-05 spreads, ST-06 spreads, etc.). Target was 20.

**Options** (need Richard's input):
- **A**: renderer auto-shrinks: ST-05 to 1 page, ST-FAZIT to 1 page → 20 pages
- **B**: Writer Pipeline regenerates with tighter content → 20 pages
- **C**: target relaxed to 20–24 → ship 22 as-is

Currently leaning **A** (renderer adapts) for MVP because it removes a Writer-Pipeline round-trip.

---

**Status:** these are advisory findings, not blockers. Renderer can ship with all 7 violations present. Tracking for Writer-Pipeline cleanup.
