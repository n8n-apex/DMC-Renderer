# Phase-1 Research Task F — German Typography for `dmc-renderer`

Audience: native-German B2B decision-makers. Output must read as editorial-quality German. Pipeline hardcodes `lang="de"` for MVP. Primary engine: Python (WeasyPrint assumed; PrinceXML noted as alternative). Optional Node sidecar.

---

## 1. Hyphenation dictionaries

| Pattern set | Source | Notes |
|---|---|---|
| `hyph-de-1996` | CTAN `hyph-utf8` | Patterns for new-orthography German (1996 reform). |
| `hyph-de-2006` | CTAN `hyph-utf8` (a.k.a. `dehyphn-x`) | Refined patterns reflecting the 2006 council amendments — current de-facto standard for Germany & Austria. |
| `hyph-de-ch-1901` | CTAN `hyph-utf8` | Swiss High German, traditional orthography (1901 rules). Used only when targeting CH audiences. |

**Recommendation:** `hyph-de-2006`. This is what LibreOffice's "frami" dictionary ships and what current Duden-style hyphenation expects. `hyph-de-1996` is an older snapshot; `hyph-de-ch-1901` is wrong locale.

**Integration paths:**

- **WeasyPrint (Python primary):** WeasyPrint relies on **Pyphen** internally. Pyphen ships LibreOffice-derived Hunspell `.dic` files for `de_DE`, `de_AT`, `de_CH` (post-2006). Activating it is a single CSS line + `lang="de"` on `<html>`. No download or shimming needed — the dictionary is bundled with `pip install pyphen`.
- **PrinceXML (if selected later):** Prince ships German patterns from CTAN. Activated via `:lang(de) { prince-hyphenate-patterns: "hyph-de-2006.pat" }` only if you want to override default. Default is fine for our purposes.
- **Node sidecar (only if frontend preview needed):** `hyphenopoly` on npm — server-side mode uses `hyphenopoly.module.js` with WASM patterns. Required only if we render in headless Chromium where browser-default hyphenation is patchy on some platforms.

**Decision for our stack:** Pyphen via WeasyPrint. No sidecar. If we ever switch to PrinceXML, Prince's bundled de patterns are equivalent quality.

---

## 2. Long compound words

German pain point: `Politikverdrossenheit`, `Donaudampfschifffahrtsgesellschaft`, `Mitarbeiterentwicklungsgespräch`. Without hyphenation, these blow narrow columns.

**Rules:**

- `hyphens: auto` + `lang="de"` — **always on** for body, captions, table cells with prose.
- `overflow-wrap: break-word` — **fallback only**, for URLs / e-mail / model numbers / SKUs that the dictionary won't break. Allows mid-word break only when the line would otherwise overflow.
- `word-break: break-all` — **never use**. It breaks at arbitrary characters, ignores German morphology, produces ugly typography.
- `word-break: keep-all` — irrelevant (East-Asian use case).
- Hyphenation should be **disabled** on headlines >= H2 (`hyphens: manual`) — a hyphenated headline looks cheap.
- Set `hyphenate-limit-chars: 6 3 3` (min word length 6, min before/after break 3) to avoid stubby breaks like `ein-er`.

CSS in §11 below encodes this.

---

## 3. German quotation marks

Correct: `„Wort"` — low-9 opening (U+201E `„`), high-9 closing (U+201C `"`). Inner: `‚Wort'` — low-9 single (U+201A), high-9 single (U+2018).

Alternate (less common, more typographic, used in Switzerland and high-end editorial): Guillemets `»Wort«` with points facing inward (note: opposite of French `«Wort»`). Inner: `›Wort‹`.

**Wrong (English-default curlies):** `"Wort"` (U+201C…U+201D). The opening glyph sits at the top instead of bottom-left.

**Verify Hyphenopoly/CSS doesn't break this:** Hyphenopoly only inserts soft hyphens (U+00AD); it does not touch quote glyphs. CSS `hyphens: auto` likewise leaves quote characters alone. Risk only arises if the *AI writer* emits straight `"`/`'` — the preprocessor below normalises before render.

**Preprocessor regex** — see §12.A. Handles:
- Outer straight `"…"` → `„…"`
- Inner straight `'…'` → `‚…'`
- Heuristic: opening quote is preceded by start-of-string/whitespace/opening bracket/dash; closing quote is preceded by a word/digit/punctuation.
- Skip code/math regions if present (marked by classes; for MVP we have no such regions).

Use **»…«** style only when configured at the report-level (e.g. Swiss audience). Default = `„…"`.

---

## 4. Ligatures

Standard ligatures (`liga`, on by default): `ff`, `fi`, `fl`, `ffi`, `ffl`, `ft`, `tt`. These are safe in German body text **except** at morpheme boundaries inside compound words — e.g. `Schaff`+`Liste` should not ligate `ffl`. High-quality German fonts (Adobe Garamond Pro German, FF Meta, Tisa, etc.) handle this via the `dlig`/`ccmp` shaping table or by simply not defining problematic ligatures.

**Recommendation for body:**

```css
font-feature-settings: "liga" 1, "calt" 1, "kern" 1;
font-variant-ligatures: common-ligatures no-discretionary-ligatures contextual;
```

- `liga` ON — standard ligatures.
- `dlig` OFF — discretionary ligatures (`ct`, `st`, `sp` swashes) look out of place in B2B reports.
- `hlig` OFF — historical ligatures.
- `calt` ON — contextual alternates (small visual smoothing).
- `kern` ON — pair kerning, essential.

**Headlines** can keep `dlig` ON if the brand font has well-designed display ligatures; default OFF.

**Sources note:** German typographic tradition (Bringhurst summarising Tschichold) recommends *suppressing* the `f`-ligatures across morpheme joins. We rely on the font's GSUB table to handle this; we do **not** try to insert ZWJ/ZWNJ in the preprocessor (too brittle for MVP).

---

## 5. No-break-space rules

German typography requires a non-breaking space between several token pairs. DIN 5008:2020-03 prescribes **U+202F NARROW NO-BREAK SPACE (NNBSP)** as the preferred glyph; **U+00A0 NO-BREAK SPACE (NBSP)** is a widely-supported fallback. NNBSP is visually thinner and reads more correctly in tight German body text.

**Pragmatic choice for MVP:** use **U+00A0** everywhere. NNBSP support in some fonts (especially older DTP-era licences) is patchy and can render as `.notdef` (□) in PDFs. NBSP is rock-solid across every font.

**Required contexts:**

| Pattern | Example | Notes |
|---|---|---|
| Number + unit | `100 €`, `48 Minuten`, `30 %`, `15 Mitarbeiter`, `12 kg`, `5 m²` | Includes currency, percent, SI units, common nouns acting as units. |
| Number + currency code | `100 EUR`, `2 500 USD` | |
| Multi-part abbrev | `z. B.`, `d. h.`, `u. a.`, `s. o.`, `s. u.`, `u. U.`, `i. d. R.`, `n. Chr.`, `v. Chr.` | Inner space is NBSP. |
| Title/honorific + name | `Dr. Müller`, `Prof. Schmidt`, `Frau Bauer`, `Herrn Müller`, `St. Pauli` | Single NBSP. |
| Initial(s) + surname | `H. Müller`, `J. F. Kennedy` | NBSP between each. |
| Page/section ref | `S. 12`, `Abs. 3`, `Art. 4`, `Bd. 2`, `Nr. 5`, `Abb. 7`, `Tab. 3`, `Kap. 4` | NBSP before number. |
| Date day + month | `11. Mai 2026` | NBSP between `11.` and `Mai` (Babel does NOT insert this — see §13). |

See §12.B for preprocessor.

---

## 6. Date formatting

German long date: `11. Mai 2026` (day with period, full month name, year, no comma).
Short numeric: `11.05.2026` (DIN 5008 compliant, dots, two-digit day/month).

**Recommendation:** `babel.dates.format_date(d, format='long', locale='de_DE')` → `11. Mai 2026`.

- `format='short'` → `11.05.26`
- `format='medium'` → `11.05.2026`
- `format='long'` → `11. Mai 2026`  ← report body
- `format='full'` → `Montag, 11. Mai 2026` ← report cover only

Note: Babel emits a regular space between `11.` and `Mai`. Post-process to NBSP (§12.B catches this via the abbreviation rule).

Python `datetime.strftime('%d. %B %Y')` with `locale.setlocale(LC_TIME, 'de_DE.UTF-8')` works but is global and not thread-safe in a multi-tenant renderer. **Use Babel, not `locale`.**

---

## 7. Number formatting

`babel.numbers.format_decimal(n, locale='de_DE')`:

- `1000` → `1.000`
- `1000000` → `1.000.000`
- `1234.56` → `1.234,56`
- `0.0875` → `0,0875`

`babel.numbers.format_currency(1234.5, 'EUR', locale='de_DE')` → `1.234,50 €` (note: trailing currency, space before symbol — German convention).

`babel.numbers.format_percent(0.30, locale='de_DE')` → `30 %`.

After Babel formatting, run §12.B to convert the regular space to NBSP between number and unit/symbol.

---

## 8. Capitalisation

German rule: every noun is capitalised, including inside compounds at clause heads. Verbs, adjectives, articles are lowercase (except sentence-initial). Nominalised verbs/adjectives are capitalised (`das Lesen`, `im Allgemeinen`).

**This is the AI writer's job.** The renderer cannot reliably re-case input — capitalisation is grammar, not typography. Flag for upstream: include a content-validation check in the writer prompt and/or a post-generation linter (e.g. via LanguageTool API) that flags suspect lowercase nouns.

**Risk flag:** an LLM trained predominantly on English may under-capitalise German nouns mid-sentence. Worth a spot-check on the first 10 reports.

---

## 9. Hyphen vs en-dash vs em-dash

- `-` U+002D HYPHEN-MINUS: only inside compound words and at end-of-line hyphenation. Examples: `Software-Update`, `E-Mail`, `EU-weit`.
- `–` U+2013 EN DASH (`Halbgeviertstrich`, `Gedankenstrich`): parenthetical break, number ranges, "bis" replacement, "gegen" in sport scores. Surrounded by spaces when parenthetical (`Der Bericht – ein Meilenstein – wurde veröffentlicht`). **No spaces** in ranges (`Seiten 12–14`, `9–17 Uhr`, `Bayern–Dortmund`).
- `—` U+2014 EM DASH (`Geviertstrich`): **not used in German prose typography.** Reserve for tabular lines / structural fillers only.

**Preprocessor rule (§12.C):** convert ` -- ` and ` — ` to ` – `; leave intra-word `-` alone; leave numeric ranges with regular hyphen alone (we keep them as en-dash if they're already en-dashed; we do not aggressively convert `12-14` → `12–14` because some IDs/SKUs use hyphens).

---

## 10. OpenType feature interactions

| Feature | German body | Reason |
|---|---|---|
| `liga` (standard) | ON | Safe. |
| `dlig` (discretionary) | **OFF** | Decorative `ct`/`st`/`sp` ligatures fight German compound morphology and read as precious. |
| `hlig` (historical) | OFF | Same. |
| `calt` (contextual alts) | ON | Subtle glyph smoothing. |
| `kern` | ON | Required. |
| `smcp` (small caps) | only on demand | German all-caps headlines need `Versalsatz` — apply `letter-spacing: 0.05em` for legibility (DIN tradition). |
| `lnum` / `tnum` (lining/tabular figures) | `tnum` ON in tables | Numbers align. Body uses default (often old-style or proportional lining). |
| `frac` | OFF | German uses `1/2` written-out or decimal. |
| `ss01`+ stylistic sets | font-specific | Test per-font; some Latin fonts ship a "German `ß`" stylistic set replacing capital `ẞ` (U+1E9E). |
| `case` | ON when uppercasing | Adjusts punctuation height for caps. |

**Known misbehaviour:** `dlig` enabling `ct`/`st` will produce decorative ligatures inside common German words like `Verschwöru**ng**` or names — looks costume-y. Keep OFF for body. Some old-style fonts ligate `ch`/`ck` via `dlig`; never enable in B2B body.

---

## 11. Paste-ready CSS

```css
/* === German typography baseline for dmc-renderer ===
   Apply with: <html lang="de"> + WeasyPrint (Pyphen bundled). */

:root {
  --de-hyphen-char: "\2010"; /* explicit hyphen U+2010, not minus */
}

html { lang: de; }            /* belt-and-braces; HTML attribute is canonical */

html, body {
  font-family: "Source Serif Pro", "Adobe Garamond Pro", "Liberation Serif", Georgia, serif;
  font-size: 10.5pt;
  line-height: 1.45;

  /* Hyphenation — German requires this for long compounds */
  -webkit-hyphens: auto;
  -ms-hyphens: auto;
  hyphens: auto;
  hyphenate-limit-chars: 6 3 3;     /* min word=6, min-before=3, min-after=3 */
  hyphenate-limit-lines: 2;          /* no more than 2 consecutive hyphenated lines */
  hyphenate-limit-zone: 8%;          /* avoid hyphenating when ragged edge is close */
  hyphenate-character: "\2010";

  /* Overflow fallback for un-dictionaried strings (URLs, SKUs) */
  overflow-wrap: break-word;
  word-break: normal;                /* NEVER break-all */

  /* Typography quality */
  font-feature-settings: "kern" 1, "liga" 1, "calt" 1;
  font-variant-ligatures: common-ligatures no-discretionary-ligatures contextual;
  font-kerning: normal;
  text-rendering: optimizeLegibility;

  /* Quote-character mapping for any CSS-generated quotes (q { quotes: ... }) */
  quotes: "\201E" "\201C" "\201A" "\2018";  /* „ "  ‚ ' */
}

/* Body paragraphs */
p {
  text-align: justify;
  text-justify: inter-word;
  orphans: 2; widows: 2;
}

/* Headlines — no hyphenation, no auto-justify */
h1, h2, h3, h4 {
  hyphens: manual;
  text-align: left;
  font-feature-settings: "kern" 1, "liga" 1, "calt" 1;
  /* dlig stays off; if brand font has nice display ligatures, opt-in per-class */
}

/* Tables: tabular figures, no hyphens in narrow cells */
table {
  font-feature-settings: "kern" 1, "liga" 1, "tnum" 1, "lnum" 1;
  font-variant-numeric: tabular-nums lining-nums;
  hyphens: manual;
}

/* CSS-generated <q> elements get correct German marks */
q::before { content: "\201E"; }     /* „ */
q::after  { content: "\201C"; }     /* " */
q q::before { content: "\201A"; }   /* ‚ */
q q::after  { content: "\2018"; }   /* ' */

/* Class hooks for content the writer marks up */
.no-hyphens     { hyphens: manual; }
.allow-break    { overflow-wrap: anywhere; word-break: break-word; }
.tabular-nums   { font-variant-numeric: tabular-nums lining-nums; }
.uppercase-de   { text-transform: uppercase; letter-spacing: 0.05em;
                  font-feature-settings: "case" 1, "kern" 1; }
```

---

## 12. Python preprocessor sketches

Apply in this order: **A (quotes) → B (NBSP) → C (dashes)**. Each operates on the AI-writer's plain prose before HTML serialisation. Keep idempotent.

### 12.A — Quotation mark normalisation

```python
import re

# German „outer" + ‚inner' (Duden default). Switch to »…«/›…‹ via STYLE.
_QUOTE_STYLES = {
    "duden": ("„", "“", "‚", "‘"),  # „ " ‚ '
    "swiss": ("»", "«", "›", "‹"),  # » « › ‹  (German Swiss)
}

def normalise_quotes_de(text: str, style: str = "duden") -> str:
    o2, c2, o1, c1 = _QUOTE_STYLES[style]

    # Step 1: pre-existing English curlies → German equivalents
    text = text.replace("“", o2).replace("”", c2)  # " " → „ "
    text = text.replace("‘", o1).replace("’", c1)  # ' ' → ‚ '  (RISK: apostrophes)

    # Step 1b: protect apostrophes inside words (Müller's, geht's) - undo overzealous step 1
    text = re.sub(r"(\w)" + re.escape(c1) + r"(\w)", r"\1’\2", text)

    # Step 2: straight " - alternate open/close by depth tracking
    out, depth = [], 0
    prev = " "
    for ch in text:
        if ch == '"':
            opening = prev.isspace() or prev in "([{—–-„‚"
            out.append(o2 if opening else c2)
            depth += 1 if opening else -1
        elif ch == "'" and (prev.isspace() or prev in "([{—–-„"):
            out.append(o1)
        elif ch == "'" and (out and out[-1] not in " \t\n"):
            # word-internal apostrophe → typographic right single
            out.append("’")
        else:
            out.append(ch)
        prev = ch
    return "".join(out)
```

### 12.B — Non-breaking-space insertion

```python
import re
NBSP = " "   # U+00A0; switch to " " if font support is verified

# Pre-compile patterns once.
_NUM_UNIT = re.compile(
    r"(?<=\d)[ ]"
    r"(?=(?:€|EUR|USD|CHF|GBP|\$|%|‰|kg|g|mg|t|km|m|cm|mm|µm|"
    r"l|ml|h|min|s|ms|Stk\.?|Mio\.?|Mrd\.?|"
    r"Mitarbeiter|Mitarbeiterinnen|Personen|Kunden|Tage|Wochen|"
    r"Monate|Jahre|Stunden|Minuten|Sekunden|Prozent)\b)"
)
_ABBREV = re.compile(
    r"\b(z|d|u|s|i|n|v|o|e)\.\s+(B|h|a|o|u|d|Chr|V|R|A)\."
)
_INITIAL = re.compile(r"\b([A-ZÄÖÜ])\.\s+(?=[A-ZÄÖÜ])")
_TITLE = re.compile(
    r"\b(Dr|Prof|Hr|Fr|Frau|Herrn?|Sr|Jr|St|Sankt|Mag|Dipl|Ing|"
    r"Bd|Nr|Abs|Art|Abb|Tab|Kap|S|Vgl|cf|p|pp|ca|vgl)\.\s+(?=\S)"
)
_DATE_DAY_MONTH = re.compile(
    r"\b(\d{1,2})\.\s+(?=(?:Januar|Februar|März|April|Mai|Juni|"
    r"Juli|August|September|Oktober|November|Dezember)\b)"
)

def insert_nbsp_de(text: str) -> str:
    text = _NUM_UNIT.sub(NBSP, text)
    # Abbreviations: replace the inner space; loop for chains like "v. l. n. r."
    prev = None
    while prev != text:
        prev = text
        text = _ABBREV.sub(lambda m: f"{m.group(1)}.{NBSP}{m.group(2)}.", text)
    text = _INITIAL.sub(lambda m: f"{m.group(1)}.{NBSP}", text)
    text = _TITLE.sub(lambda m: f"{m.group(1)}.{NBSP}", text)
    text = _DATE_DAY_MONTH.sub(lambda m: f"{m.group(1)}.{NBSP}", text)
    return text
```

### 12.C — Hyphen / en-dash / em-dash

```python
import re
EN_DASH = "–"
EM_DASH = "—"

_DOUBLE_HYPHEN = re.compile(r"(?<=\s)--(?=\s)")        # ` -- ` → ` – `
_EM_TO_EN      = re.compile(r"(?<=\s)—(?=\s)")    # ` — ` → ` – `  (German prefers en-dash)
_PARENTHETICAL = re.compile(r" - ")                    # ` - ` (space-hyphen-space) → ` – `
_RANGE         = re.compile(r"(?<=\d)\s*-\s*(?=\d)")   # `12-14`/`12 - 14` → `12–14` (no spaces)

def normalise_dashes_de(text: str) -> str:
    text = _DOUBLE_HYPHEN.sub(EN_DASH, text)
    text = _EM_TO_EN.sub(EN_DASH, text)
    text = _PARENTHETICAL.sub(f" {EN_DASH} ", text)
    text = _RANGE.sub(EN_DASH, text)
    # Intra-word hyphens (Software-Update, E-Mail) are left untouched: no surrounding spaces.
    return text
```

### Driver

```python
def german_typo_pass(text: str) -> str:
    text = normalise_quotes_de(text, style="duden")
    text = normalise_dashes_de(text)
    text = insert_nbsp_de(text)
    return text
```

Apply once per text-bearing field after the writer emits and before HTML serialisation. HTML-escape *after* this pass (`html.escape`) so the special characters survive.

---

## 13. Date / number helper

```python
from datetime import date
from babel.dates import format_date
from babel.numbers import format_decimal, format_currency, format_percent

NBSP = " "
LOC = "de_DE"

def de_date(d: date, fmt: str = "long") -> str:
    # 'long' → "11. Mai 2026"
    s = format_date(d, format=fmt, locale=LOC)
    # Babel emits regular space — convert "11. Mai" → "11. Mai"
    return s.replace(". ", f".{NBSP}", 1) if fmt in ("long", "full") else s

def de_num(n) -> str:
    return format_decimal(n, locale=LOC)           # 1.234,56

def de_currency(n, code: str = "EUR") -> str:
    s = format_currency(n, code, locale=LOC)       # "1.234,50 €"
    return s.replace(" ", NBSP)                    # tie number+symbol

def de_percent(frac: float) -> str:
    s = format_percent(frac, locale=LOC)           # "30 %"
    return s.replace(" ", NBSP)
```

Dependency: `babel >= 2.14` (CLDR 44+, current German formats).

---

## 14. Hyphenation dictionary — final recommendation

| Question | Answer |
|---|---|
| Which dictionary? | **hyph-de-2006** (post-reform, current Duden alignment). |
| Where to obtain? | Bundled with **Pyphen** (`pip install pyphen`) as `de_DE.dic`. Source upstream: LibreOffice `dictionaries/de` (Björn Jacke / Franz Michael Baumann, "frami"). For PrinceXML: CTAN `hyph-utf8/tex/generic/hyph-utf8/patterns/tex/hyph-de-2006.tex`. |
| How to integrate? | Set `<html lang="de">` and `hyphens: auto` in CSS. WeasyPrint picks Pyphen automatically. No code, no config. |
| Override per element? | `lang="de-CH"` on a `<section>` if a quoted Swiss passage needs Swiss conventions; otherwise leave `de`. |
| Fallback for Node sidecar (if added later)? | `hyphenopoly` npm package, configured with `require: { "de": "Silbentrennungsmuster" }`. Server-side module: `hyphenopoly.module.js`. |

---

## 15. Sources

- [Pyphen — Hyphenation in pure Python](https://pyphen.org/) (German `de_DE`/`de_AT`/`de_CH` dictionaries; API).
- [WeasyPrint API reference — hyphenation](https://doc.courtbouillon.org/weasyprint/stable/api_reference.html) (uses Pyphen; needs `lang` attribute).
- [CTAN: `hyph-utf8` patterns](https://ctan.org/pkg/hyph-utf8) and [`hyph-de-2006.tex`](https://github.com/hyphenation/tex-hyphen/blob/master/hyph-utf8/tex/generic/hyph-utf8/patterns/tex/hyph-de-1996.tex) (pattern provenance).
- [PrinceXML Hyphenation docs](https://www.princexml.com/doc/11/hyphenation/) (`prince-hyphenate-patterns`).
- [Hyphenopoly](https://github.com/mnater/Hyphenopoly) (server-side Node + browser polyfill).
- [MDN: `hyphens` CSS property](https://developer.mozilla.org/en-US/docs/Web/CSS/hyphens) and [Can I Use: CSS Hyphenation](https://caniuse.com/css-hyphens).
- [Wikipedia: Non-breaking space — German conventions](https://en.wikipedia.org/wiki/Non-breaking_space) (multi-part abbreviations).
- [DIN 5008:2020-03 summary on NNBSP / U+202F](https://unicode-explorer.com/c/202F) (narrow no-break space for German abbrev/thousands).
- [Duden — Anführungszeichen](https://www.duden.de/sprachwissen/rechtschreibregeln/anfuehrungszeichen) (quote rules; Rule 12 for nested marks).
- [Wikipedia: German orthography reform of 1996](https://en.wikipedia.org/wiki/German_orthography_reform_of_1996) and [2006 amendments](https://en.wikipedia.org/wiki/German_orthography) (hyphenation changes).
- [Typefacts — Binde- und Gedankenstrich](https://typefacts.com/en/articles/binde-und-gedankenstrich) (hyphen vs en-dash vs em-dash in German).
- [CSSWG drafts issue #3927 — capitalised words & `hyphens: auto`](https://github.com/w3c/csswg-drafts/issues/3927) (German is the explicit exception that *requires* hyphenating capitalised words).
- [MDN: `font-variant-ligatures`](https://developer.mozilla.org/en-US/docs/Web/CSS/font-variant-ligatures) and [Type Network: Standard Ligatures](https://typenetwork.com/articles/opentype-at-work-standard-ligatures) (liga vs dlig).
- [Babel — Number Formatting](https://babel.pocoo.org/en/latest/numbers.html) and [Date & Time](https://babel.pocoo.org/en/latest/dates.html) (German locale formatters).
- [LibreOffice de "frami" dictionary README](https://cgit.freedesktop.org/libreoffice/dictionaries/tree/de/README_hyph_de.txt) (post-2006 word list provenance).
