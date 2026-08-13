# DMC Renderer — API Contract

**Endpoint:** `POST /render`
**Canonical reference fixture:** [`fixtures/apex_consulting_payload.json`](../fixtures/apex_consulting_payload.json)
**Authoring rule:** This document is grounded in the actual fixture on disk. Every documented field appears in or is intentionally absent from that fixture. A regression test (`tests/test_contract_matches_fixture.py`, Phase 3) asserts the fixture conforms to this schema.

---

## Request envelope

```json
{
  "payload":      { "meta": {...}, "pages": [...] },
  "images":       { "<slot_key>": "<url>", ... },
  "brand_tokens": { ... }
}
```

Three top-level keys. All three **required**. Any other top-level key is ignored (forward-compatible — but logged at debug level so we can spot upstream drift).

| Key | Type | Required | Purpose |
|---|---|---|---|
| `payload` | object | yes | Report content. Contains `meta` + `pages`. |
| `images` | object | yes (may be empty `{}` if no images referenced) | Map of named image slots → publicly fetchable URLs. The renderer resolves these to local files in `/tmp/render-{report_id}/`. |
| `brand_tokens` | object | yes | Per-client styling tokens. Merged into the Jinja template context. Missing keys fall back to defaults — see [BRAND_TOKENS.md](BRAND_TOKENS.md). |

Top-level validation failures (missing keys, non-object types) return **400** with `error: "malformed_request"`.

---

## `payload.meta`

| Field | Type | Required | Example | Notes |
|---|---|---|---|---|
| `client_slug` | string | yes | `"jousef"` | Lowercased, used as a stable client identifier. Currently informational only (logged + used to seed deterministic timestamps). |
| `report_id` | string | yes | `"CL-20260508-092136-MCE"` | Globally unique report identifier. Used as the scratch directory name (`/tmp/render-{report_id}/`) AND as the seed for the PDF creation timestamp (determinism). Must match `^[A-Za-z0-9_-]{1,64}$` (we use it as a filesystem path). |
| `lang` | string | yes | `"de"` | BCP-47 language tag. Drives hyphenation dictionary selection (Pyphen). Currently only `de` and `en` are supported; other tags fall back to `en` with a warning. |
| `page_format` | string | yes | `"A4"` | Currently only `"A4"` is supported. `"Letter"` will be added when a client needs it. Anything else → 400. |
| `export_mode` | string | yes | `"single-page"` | `"single-page"` = each `page_numbers` segment renders as separate sequential A4 pages (current default). Reserved for `"spread"` (true facing-page rendering) in v1.1. |
| `page_count_target` | integer | yes | `20` | The Writer's *target* page count. The renderer reports the actual page count via `X-Page-Count` response header. The Writer may overshoot this — the locked decision (`research/SUMMARY.md`) is that the renderer never auto-shrinks to fit. |

Validation: all 6 fields required. Missing field → 400 with `details: "payload.meta.<field> is required"`. Type mismatch → 400. Unknown extra keys in `meta` → ignored (debug-logged).

---

## `payload.pages[]`

An array, in display order. Each entry has the same envelope:

```json
{
  "slot": <integer>,
  "type": "<ST-XX>",
  "chapter_type_original": "<string>",
  "page_numbers": "<string>",
  "data": { ... }   // type-specific, see § per-ST schemas below
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `slot` | integer | yes | 1-indexed position in the array. The renderer asserts `pages[i].slot == i + 1` and 400s on mismatch. (Defensive check — upstream should never emit a hole.) |
| `type` | string | yes | One of the 11 ST identifiers documented below. Unknown type → 400. |
| `chapter_type_original` | string | yes | Free-form label from the upstream chapter planner (e.g. `"Case Study 4"`). Informational only — the renderer logs it but does not consume it. |
| `page_numbers` | string | yes | Either `"N"` (single page) or `"N-M"` (range, M ≥ N+1). The renderer counts page total from these — see [ARCHITECTURE.md § Page count](ARCHITECTURE.md#5-page-count-computation). The `S. N / TOTAL` header strip is computed by the renderer, never by upstream. |
| `data` | object | yes | Schema depends on `type` — see below. |

---

## Per-ST `data` schemas

### ST-01 — Cover

Single page (`page_numbers: "1"`). Hero with title, subtitle, intro, and teaser bullets.

```json
{
  "title": "Dein Wachstum frisst dich selbst auf",
  "subtitle": "Wie manuelle Prozesse und fehlendes Automatisierungssystem ...",
  "intro_body": "Dein Unternehmen wächst. Neue Kunden kommen rein, ...",
  "teaser_bullets": [
    "Warum 60% aller AI-Investitionen ...",
    "Wie B2B-Firmen Umsatz skalieren ...",
    "Welche 5 Prozesse in deinem Unternehmen ..."
  ]
}
```

| Field | Type | Required | Markdown? | Notes |
|---|---|---|---|---|
| `title` | string | yes | no | Main cover headline (Inter 900 display). |
| `subtitle` | string | yes | no | Secondary headline. |
| `intro_body` | string | yes | **yes** | Long-form intro paragraph(s). Preprocessed for `**bold**`, `*italic*`, and `\n\n` paragraph breaks. |
| `teaser_bullets` | array of strings | yes | no | 3–5 items expected; renderer accepts any non-empty array. |

Image references: uses `images.cover_hero` (background hero illustration) and `images.cover_author` (founder portrait, top-right). Both must be present in `images` map.

### ST-02 — Outlook

Two-page spread (`page_numbers: "2-3"`). Asymmetric opener + body.

```json
{
  "headline": "Dein Wachstum scheitert nicht am Markt",
  "asymmetrie_opener": "Dein Unternehmen läuft. ...",
  "body": "Manuelle Prozesse fressen in B2B-Unternehmen bis zu 30 % ..."
}
```

| Field | Type | Required | Markdown? | Notes |
|---|---|---|---|---|
| `headline` | string | yes | no | Display headline. |
| `asymmetrie_opener` | string | yes | no | Short paragraph (1–3 sentences) — the editorial "hook". Rendered in italic Source Serif at the top of the right page of the spread. |
| `body` | string | yes | **yes** | Multi-paragraph body. Use `\n\n` between paragraphs in the JSON source — preprocessor converts to paragraph breaks. |

### ST-03 — CTA

Single page (`page_numbers: "20"` typically). Closing call-to-action.

```json
{
  "headline": "Buche jetzt dein kostenloses Erstgespräch mit APEX",
  "body": "Dein Team verbrennt täglich Stunden ...",
  "cta_text": "Jetzt Erstgespräch buchen",
  "cta_url": "https://apex-consulting.ai/"
}
```

| Field | Type | Required | Markdown? | Notes |
|---|---|---|---|---|
| `headline` | string | yes | no | |
| `body` | string | yes | **yes** | |
| `cta_text` | string | yes | no | Button label. |
| `cta_url` | string | yes | no | URL the QR code encodes AND the button links to. Must be `http(s)://`. |

ST-03 has a slightly higher coral budget (3 fires) — it legitimately uses coral on the headline accent + CTA button + the QR target frame.

### ST-05 — About

Two-page spread (`page_numbers: "4-5"`). Founder bio + credibility grid.

```json
{
  "headline": "Über 100 AI-Projekte. Ein Ergebnis: Betrieb ohne Flaschenhals.",
  "intro": "APEX Consulting hat über 100 B2B-Unternehmen ...",
  "body": "Jousef gründete APEX Consulting mit einer präzisen These: ...",
  "credibility_points": [
    { "label": "Abgeschlossene AI-Projekte", "value": "100+" },
    { "label": "Betriebskosteneinsparung", "value": "30–50 %" },
    ...
  ]
}
```

| Field | Type | Required | Markdown? | Notes |
|---|---|---|---|---|
| `headline` | string | yes | no | |
| `intro` | string | yes | no | Italic lede paragraph below the headline. |
| `body` | string | yes | **yes** | Multi-paragraph founder bio. |
| `credibility_points` | array of `{label, value}` | yes | no | 3–6 items recommended; renders as a stat grid. `label` is sans-serif gray small caps, `value` is sans-serif navy big number. |

Image: uses `images.about_logo` (small wordmark, top-left of left page).

### ST-06 — Mechanism

Two-page spread (`page_numbers: "15-16"`). The signature methodology.

```json
{
  "headline": "Das Done-For-You AI Automation Framework",
  "mechanism_name": "Done-For-You AI Automation Framework",
  "mechanism_description": "Die meisten Unternehmen automatisieren falsch: ...",
  "steps": [
    {
      "number": 1,
      "title": "Workflow-Audit und Engpass-Diagnose",
      "description": "Bevor eine einzige Zeile Code geschrieben wird, ...",
      "reveal_level": "full"
    },
    ...
  ],
  "closing_redirect": "Wie genau APEX deine spezifischen Engpässe diagnostiziert ..."
}
```

| Field | Type | Required | Markdown? | Notes |
|---|---|---|---|---|
| `headline` | string | yes | no | |
| `mechanism_name` | string | yes | no | Often duplicates the headline. The template uses this in the process_flow diagram label. |
| `mechanism_description` | string | yes | **yes** | Paragraphs explaining the mechanism. |
| `steps` | array of `{number, title, description, reveal_level}` | yes | description: **yes** | Always 6 steps for Apex (the framework count is fixed); other clients may vary 4–8. The renderer treats `len(steps)` as canonical, not a hardcoded 6. |
| `closing_redirect` | string | yes | **yes** | Sentence redirecting reader to the CTA (preprocessed for bold/italic). |

`steps[].reveal_level` takes one of `"full"` or `"gesture"`. `"full"` renders the entire description body. `"gesture"` renders only the title + a 1-line hint (the description is still in the JSON for the writer's reference but isn't fully shown). This is the "tease vs explain" pattern.

The Apex 6-step framework is fundamentally a process, so this template always uses the `process_flow` component (not `hub_and_spoke`).

### ST-07A — Case Study

Single page (`page_numbers: "10"`, `"12"`, `"14"`, `"16"`, `"18"`). Reference: research/decoration-samples/assembly-st07a-conesso-v6.pdf.

```json
{
  "fallstudie_number": 4,
  "ergebnis_headline": "Onboarding von 30 Minuten auf 2 Minuten",
  "kurzportraet": "Conesso GmbH ist eine Performance-Agentur, ...",
  "ausgangsproblem": "Jeder neue Kunde bedeutete mehr manuelle Arbeit: ...",
  "wendepunkt": "",
  "loesung": "APEX implementierte AI-gesteuerte Automationen ...",
  "ergebnis_text": "Nach der Implementierung sank die Onboarding-Zeit ...",
  "ergebnis_metrics": [
    { "label": "Onboarding-Zeit", "value": "von 30 auf 2 Minuten" },
    { "label": "Copywriting pro Asset", "value": "von 60 auf 5 Minuten" },
    { "label": "Operative Engpässe", "value": "3 kritische Workflows eliminiert" }
  ],
  "kunde": {
    "name": "Conesso GmbH",
    "funktion": "Performance-Agentur",
    "company_url": "",
    "initials": "CG"
  },
  "pullquote": {
    "text": "„Onboarding, das früher 30 Minuten dauerte, braucht jetzt nur noch 2 ...",
    "attribution": "Conesso GmbH"
  }
}
```

| Field | Type | Required | Markdown? | Notes |
|---|---|---|---|---|
| `fallstudie_number` | integer | yes | no | Display number ("FALLSTUDIE · 04"). Zero-padded by the template. |
| `ergebnis_headline` | string | yes | no | The Big Headline (Inter 900). |
| `kurzportraet` | string | yes | **yes** | Italic Serif lede paragraph. |
| `ausgangsproblem` | string | yes | **yes** | "AUSGANGSSITUATION" body. |
| `wendepunkt` | string (may be empty `""`) | yes | **yes** | Optional pivot moment. **Empty string is valid** and skipped in render — observed in case 2, 3, 4 of the Apex fixture. |
| `loesung` | string | yes | **yes** | "DIE LÖSUNG" body. |
| `ergebnis_text` | string | yes | **yes** | "DAS ERGEBNIS" body. |
| `ergebnis_metrics` | array of `{label, value}` | yes | no | 3 items expected — renders as the stat_block in the bottom-right of the right column. The Apex template applies coral to the first (most impactful) metric. |
| `kunde` | object — see below | yes | no | Customer info. |
| `pullquote` | object — see below | yes | no | Sidebar pullquote. |

`kunde` shape:

| Sub-field | Type | Required | Notes |
|---|---|---|---|
| `name` | string | yes | Customer company name (Inter 800 white in sidebar). |
| `funktion` | string | yes | Role / category (e.g. "Performance-Agentur"). Italic Source Serif. |
| `company_url` | string | yes (may be `""`) | If non-empty, becomes a small URL line in the sidebar. **Empty is valid** (observed in all 5 Apex cases). |
| `initials` | string (1–3 chars) | yes | Used in the big InitialsBlock at the top of the sidebar when no portrait image is provided. |

`pullquote` shape:

| Sub-field | Type | Required | Markdown? | Notes |
|---|---|---|---|---|
| `text` | string | yes | **yes** | The quote text. May start with a "„" German opening quote — template handles either. |
| `attribution` | string | yes | no | Renders as "— ATTRIBUTION" small-caps under the quote. |

### ST-07B — Theory

Single page (`page_numbers: "11"`, `"13"`, `"15"`). Companion to ST-07A — extracts the principle from the preceding case study.

```json
{
  "headline": "Wachstum entsteht nicht durch mehr Köpfe",
  "subheadline": "Wer skaliert, ohne Prozesse zu automatisieren, kauft sich Overhead — kein Wachstum.",
  "body": "Das Muster ist immer dasselbe. Ein Unternehmen wächst. ...",
  "key_insight": "**Operative Engpässe durch manuelle Prozesse deckelten die Kapazität — nicht fehlende Nachfrage oder fehlendes Personal.**"
}
```

| Field | Type | Required | Markdown? | Notes |
|---|---|---|---|---|
| `headline` | string | yes | no | |
| `subheadline` | string | yes | no | Italic Source Serif under the headline. |
| `body` | string | yes | **yes** | Long-form body — typically the longest of the report's prose passages. |
| `key_insight` | string | yes | **yes** | Pull-out callout, rendered in a tinted box or boxed-out style. **Already contains `**bold**` markers** — preprocessor converts. |

### ST-09 — Status Quo

Two-page spread (`page_numbers: "6-7"`). The diagnostic / status-quo chapter with symptoms.

```json
{
  "headline": "Dein Unternehmen wächst. Deine Prozesse nicht.",
  "asymmetrie_opener": "Du hast Kunden. Du hast ein Team. ...",
  "body": "Das ist kein Disziplinproblem. ...",
  "symptoms": [
    { "title": "Montagmorgen kostet drei Stunden Überblick", "description": "Du öffnest fünf verschiedene Tools, ..." },
    ...
  ],
  "closing": "Diese Symptome sind kein Zufall. Sie haben eine gemeinsame Ursache, ..."
}
```

| Field | Type | Required | Markdown? | Notes |
|---|---|---|---|---|
| `headline` | string | yes | no | |
| `asymmetrie_opener` | string | yes | no | Editorial hook, italic. |
| `body` | string | yes | **yes** | |
| `symptoms` | array of `{title, description}` | yes | description: **yes** | 6 items in the Apex fixture; template handles 4–8. Layout is a 3×2 grid on a 2-page spread. |
| `closing` | string | yes | **yes** | Bridge to the next chapter. |

Image: uses `images.status_quo_scene` (scene illustration on the left page).

### ST-14 — False Beliefs

Two-page spread (`page_numbers: "8-9"`). 3 beliefs × {belief, reality, body} structure.

```json
{
  "headline": "Drei Lügen, die dein Wachstum blockieren",
  "intro": "Du glaubst, du brauchst mehr Leute. ...",
  "beliefs": [
    {
      "belief": "„Mehr Mitarbeiter einstellen ist der einzige Weg, ...",
      "reality": "Skalierung entsteht durch Systeme, nicht durch Köpfe.",
      "body": "77 % der HR-Verantwortlichen planen 2026 ..."
    },
    ...
  ]
}
```

| Field | Type | Required | Markdown? | Notes |
|---|---|---|---|---|
| `headline` | string | yes | no | |
| `intro` | string | yes | **yes** | |
| `beliefs` | array of `{belief, reality, body}` | yes | body: **yes** | Always 3 items in current usage. `belief` is quoted in italic; `reality` is the bold rebuttal; `body` is the evidence. |

### ST-22 — Collaboration / Process

Single page (`page_numbers: "19"`). The "how we work" timeline.

```json
{
  "headline": "Von Erstgespräch zu laufendem AI-System in Wochen",
  "intro": "Kein monatelanges IT-Projekt. ...",
  "steps": [
    {
      "number": 1,
      "title": "Strategiegespräch & Fit-Check",
      "description": "In 45 Minuten analysieren wir gemeinsam ...",
      "duration": "1 Tag"
    },
    ...
  ]
}
```

| Field | Type | Required | Markdown? | Notes |
|---|---|---|---|---|
| `headline` | string | yes | no | |
| `intro` | string | yes | **yes** | |
| `steps` | array of `{number, title, description, duration}` | yes | description: **yes** | 5 items in Apex fixture. Note `duration` field present here but **not** in ST-06's `steps[]`. |

### ST-FAZIT — Summary

Two-page spread (`page_numbers: "17-18"`). Closing argument before the CTA.

```json
{
  "headline": "Dein Wachstum wartet nicht auf deine Entscheidung",
  "body": "Du hast jetzt gesehen, was manuelle Prozesse kosten: ...",
  "bold_thesis": "Das ist kein Ressourcenproblem – es ist ein Systemfehler, ...",
  "cost_of_inaction": "Jeder Monat ohne Automatisierung bedeutet: ...",
  "closing_question": "Wie viele weitere Monate kannst du dir leisten, der Flaschenhals deines eigenen Unternehmens zu sein?"
}
```

| Field | Type | Required | Markdown? | Notes |
|---|---|---|---|---|
| `headline` | string | yes | no | |
| `body` | string | yes | **yes** | Multi-paragraph closing argument. |
| `bold_thesis` | string | yes | **yes** | Pull-out callout — rendered in large display Serif Bold. |
| `cost_of_inaction` | string | yes | **yes** | Secondary callout — italic. |
| `closing_question` | string | yes | no | The final rhetorical question, rendered solo. |

Image: uses `images.fazit_background` (background illustration, typically muted/textured).

---

## `images`

```json
{
  "cover_hero":       "https://drive.google.com/uc?id=...",
  "cover_author":     "https://drive.google.com/uc?id=...",
  "about_logo":       "https://drive.google.com/uc?id=...",
  "status_quo_scene": "https://drive.google.com/uc?id=...",
  "fazit_background": "https://drive.google.com/uc?id=..."
}
```

Image slots are **named by usage location**, not by ST type. The current set of named slots:

| Slot | Used by ST | Required if that ST is present? |
|---|---|---|
| `cover_hero` | ST-01 | yes |
| `cover_author` | ST-01 | yes |
| `about_logo` | ST-05 | yes |
| `status_quo_scene` | ST-09 | yes |
| `fazit_background` | ST-FAZIT | recommended; template falls back to plain background if missing |

Additional client-specific slots can be added as new ST templates need them. Slot names must match `^[a-z][a-z0-9_]{1,30}$`.

URL must be publicly fetchable. Currently Drive `uc?id=...` URLs verified working. The renderer fetches each into `/tmp/render-{report_id}/<slot_name>.<ext>` via `urllib.request.urlopen`, 30-second per-image timeout. Fetch failure → 500 (operator decides whether to retry; the renderer never serves degraded output).

For details on no-caching policy, see [CACHE_STRATEGY.md](CACHE_STRATEGY.md).

---

## `brand_tokens`

```json
{
  "brand_primary":        "#1a1a2e",
  "brand_accent":         "#e94560",
  "brand_neutral_dark":   "#0f0f1f",
  "brand_neutral_mid":    "#7a7a8c",
  "brand_neutral_light":  "#f5f5f7",
  "font_heading":         "Inter",
  "font_body":            "Source Serif Pro",
  "logo_dark_url":        "https://drive.google.com/uc?id=...",
  "logo_light_url":       "https://drive.google.com/uc?id=...",
  "qr_target_url":        "https://apex-consulting.ai/",
  "founder_full_name":    "",
  "founder_role":         "",
  "company_name_short":   "Jousef",
  "company_url_display":  "apex-consulting.ai"
}
```

Required vs optional keys, fallback defaults, merge semantics — all documented in [BRAND_TOKENS.md](BRAND_TOKENS.md).

---

## Response

### Success — `200 OK`

```
Content-Type: application/pdf
Content-Length: 487213
X-Renderer-Version: a4b8c1d (git short SHA)
X-Api-Version: v1
X-Page-Count: 20
X-Report-Id: CL-20260508-092136-MCE
```

Body is the PDF binary.

### Failure — JSON error envelope

```http
HTTP/1.1 422 Unprocessable Entity
Content-Type: application/json
```

```json
{
  "error": "coral_budget_exceeded",
  "details": "page 3 (slot 8, type ST-07A): 4 coral fires detected — max 2",
  "fixture_path": "payload.pages[7]",
  "fires": [
    { "page": 3, "bbox": [264, 609, 13, 17], "pixels": 112 },
    { "page": 3, "bbox": [278, 609, 14, 17], "pixels": 134 }
  ]
}
```

`error` is a stable kebab-case code (n8n branches on it). `details` is a human-readable explanation. `fixture_path` (when applicable) is a JSON-pointer-ish string that points into the request body to help upstream debugging. Additional error-specific fields (like `fires` above) may appear.

| Code | When | `error` examples |
|---|---|---|
| **400** | Malformed JSON, missing required field, wrong type, invalid `meta.page_format`, unknown `ST type` | `malformed_request`, `missing_field`, `invalid_field_type`, `unsupported_st_type`, `invalid_page_numbers` |
| **401** | Bad / missing Authorization header | `unauthorized` |
| **422** | Render produced but failed validation | `coral_budget_exceeded`, `page_count_overflow` |
| **500** | Internal failure | `render_failed`, `image_fetch_failed`, `font_missing`, `template_render_error` |

---

## Worked example — what n8n sends

```http
POST /render HTTP/1.1
Host: dmc-renderer.up.railway.app
Authorization: Bearer s3cr3t
Content-Type: application/json
Content-Length: 38219

{
  "payload": { ... see fixtures/apex_consulting_payload.json ... },
  "images": { "cover_hero": "...", ... },
  "brand_tokens": { "brand_primary": "#1a1a2e", ... }
}
```

The full canonical request body is the JSON at [`fixtures/apex_consulting_payload.json`](../fixtures/apex_consulting_payload.json). That file IS the contract — when this doc and the fixture disagree, **the fixture wins** and this doc is the bug.

---

## Versioning

This is `v1` of the contract. Breaking changes (new required field, removed field, changed semantics) increment to `v2` — served at `POST /v2/render` alongside `v1`. Additive changes (new optional fields, new ST types) stay in `v1`. n8n sets `X-Api-Version: v1` (informational; the path is the binding choice).

Reserved for `v2`: spread-rendering mode (`export_mode: "spread"`), async render handle (`POST /render?mode=async` → 202 + job id), explicit page-break hints.
