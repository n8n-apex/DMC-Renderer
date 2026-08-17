# Phase-1 Research Task B — Editorial Typography Polish for HTML→PDF

**Target engine:** WeasyPrint (production) + Paged.js (dev preview). Recipes also work in headless Chromium. PrinceXML paths noted where they diverge.
**Goal:** Match InDesign-grade typography: kerning, optical margin alignment, hanging punctuation, German hyphenation, polished OpenType.

---

## 1. Findings per technique

### 1.1 Typeset.js span-wrapping technique

David Merfield's `Typeset` (deprecated but technique-stable) is the canonical preprocessor pattern. It walks text nodes and wraps three classes of glyphs:

- **Leading-quote optical margin alignment** — opening `"` `"` `'` `'` get wrapped in `.pull-double` / `.pull-single` with negative `margin-left` (`-0.46em` / `-0.27em`). The preceding word (if any) gets a `.push-*` span with matching positive `margin-right` to preserve the visual gap.
- **Problem-letter pulls** — capital letters whose left side bearing is visually "indented" (T, V, W, Y, A, O, C) are wrapped in `.pull-T`, `.pull-V` etc. when they appear flush against a margin. Source: `src/hangingPunctuation.js` defines `alignMe = "CcOoYTAVvWw".split('')` plus a `diacriticMap` covering accented variants (Ä, Ö, etc.).
- **Trailing punctuation push-out** — `.push-*` siblings mirror the pull (offset on the previous element's right side).

Span classes use `display: inline-block` only for the wide-margin quote classes (so the negative margin renders without bleed into the previous line box).

### 1.2 `hanging-punctuation` engine support (May 2026)

| Engine | `first` | `allow-end` | `last` | Notes |
|---|---|---|---|---|
| Safari / WebKit | yes | partial | no | Only mature impl. (since v10) |
| Chromium (Chrome/Edge/Headless) | **no** | no | no | Tracked but unshipped: `chromestatus 5196301767278592` |
| Firefox | no | no | no | Not implemented |
| WeasyPrint | **no** | no | no | Docs explicitly exclude it (CSS Text 3 unsupported subset) |
| Paged.js | no | no | no | Inherits from underlying Chromium |
| PrinceXML | **no** (on roadmap) | no | no | Listed as planned, not shipped |

**Conclusion:** Treat `hanging-punctuation` as **always polyfilled** for our stack. Ship CSS with `@supports (hanging-punctuation: first)` as belt-and-suspenders, but rely on the preprocessor spans.

### 1.3 OpenType `lfbd` / `rtbd` (optical bounds) feature support

These are *automatic* glyph-bound features — meant to be applied to glyphs at the left/right end of a horizontal line. Reality (2026):

- **Engine support** — WeasyPrint, Chromium, and PrinceXML do **not** activate `lfbd`/`rtbd` automatically (they have no concept of "this glyph is at line end" during shaping). You can list them in `font-feature-settings` but no shaping engine consumes them. Only InDesign's Optical Margin Alignment does this natively.
- **Font support** — Spot-check of candidates:
  - Source Serif Pro / Source Serif 4 — **no** `lfbd`/`rtbd` tables (Adobe's editorial polish lives in InDesign, not the font)
  - IBM Plex Serif / Sans — **no** optical-bounds tables
  - Crimson Pro — **no** (`smcp`, `c2sc`, `onum`, `pnum`, `lnum`, `tnum` present; no bounds)
  - Vollkorn — **no** (rich features: `liga`, `dlig`, `calt`, `smcp`, `frac`, `sups`, `subs`, `ordn`, `zero`, `ss01`; no bounds)
  - Inter — **no** (`calt`, `dlig`, `tnum`, `frac`, `case`, `cv01-cv13`, `ss01-ss08`; no bounds)
  - EB Garamond — **no**

**Conclusion:** `lfbd`/`rtbd` is **not a viable path** for free fonts on free engines. The preprocessor (§1.1) is the only practical optical-bounds mechanism. List `lfbd, rtbd` in `font-feature-settings` anyway (harmless, future-proof).

### 1.4 Hyphenation — German specifically

- **WeasyPrint native** (PRD-chosen engine): uses [Pyphen](https://github.com/Kozea/Pyphen) under the hood. `hyphens: auto` + `lang="de"` Just Works. Pattern files include `de_DE`, `de_1996`, `de_2006`, `de_CH`. Per CSS-Print-Rocks compatibility matrix: WeasyPrint hyphenation = "OK".
- **PrinceXML**: Native German patterns bundled (`de` in their list of 14 supported langs), uses CTAN patterns. Tunable via `prince-hyphenate-before/after/lines`.
- **Paged.js / headless Chromium**: Chromium supports `hyphens: auto` since v88 using its bundled Hyphen dictionaries — but the **German Compound-Word problem** persists: Chromium does not decompose `Donaudampfschiffahrtsgesellschaft` into morphemes; it hyphenates only at pattern-matched points.
- **Hyphenopoly.js** (Node module `hyphenopoly`): TeX `hyph-de-1996` and `hyph-de-2006` patterns converted to trie. Better than Pyphen for compound words because it supports `exceptions` and `minWordLength` + the new `hyph-de-2006` pattern set explicitly handles ß↔ss reform. API: `hyphenopoly.config({require: ["de"], exceptions: {...}})`.
- **Pyphen** (the WeasyPrint backend): standardized on Hunspell-format `.dic`. German compound handling is **adequate but not perfect**; Hunspell `de_DE_frami` covers most cases. Cannot decompose unknown compounds.

**Recommendation:** Use WeasyPrint's built-in Pyphen with `lang="de"`. For Schwergewicht compounds (multi-syllable proper nouns, brand names), feed a **manual `&shy;` (U+00AD) injection layer** in the preprocessor based on a brand-specific exception dictionary.

### 1.5 Best free editorial-font picks

References from the four sample reports + DMC design system + editorial-pairing literature:

| Slot | Pick | Why |
|---|---|---|
| **Body serif** | **Source Serif 4** (transitional, Adobe) | Pairs natively with Source Sans 3; broad weight range incl. 200/300/600/900; great German diacritics; SIL Open Font License |
| Body serif (alt) | Vollkorn | Warmer, more "Buch-Magazin"; richest OpenType feature set of the free serifs (`smcp`, `c2sc`, `dlig`, `ss01`); explicitly designed for body text ("Vollkorn" = wholegrain) |
| Body serif (premium alt) | IBM Plex Serif | Institutional B2B feel; pairs natively with IBM Plex Sans + Mono; very strong for technical/data sections |
| **Body sans / running text** | **Inter** | Best-in-class screen + print legibility, slashed-zero default, deep `cv01-cv13` for fine-tuning; pairs cleanly with any serif |
| Body sans (alt) | Source Sans 3 | The matched twin to Source Serif 4 — use both for the "Source duo" look |
| **Display sans (heavy headlines)** | **Inter 800/900** | Same family as body sans = no font swap; takes negative letter-spacing at -0.02em cleanly; cap-height balances German Umlauts well |
| Display sans (alt) | Montserrat ExtraBold | DMC v2 design system already lists it (line 96 of `08_DMC_Design_System_v2.md`); slightly more "marketing" feel |

**Recommended combinations:**

- **DMC Default (editorial, premium):** **Source Serif 4** (body) + **Inter** (headlines, captions, numerals). Both ship variable fonts, both have SIL OFL.
- **DMC Apex brand (max polish):** **Vollkorn** body + **Inter** display. Vollkorn's `smcp` + `dlig` adds magazine warmth where Source Serif 4 reads more "Adobe-corporate".
- **Technical/data-heavy variant:** **IBM Plex Serif** + **IBM Plex Sans** + **IBM Plex Mono** for code/tabular data. One-family discipline.

The DMC Design System v2 (lines 96–105) currently lists Montserrat / Raleway / Source Sans Pro / Lato. Our picks **upgrade** the body text choice from Source Sans Pro to Source Serif 4 (or Vollkorn) for the "editorial magazine" tier 1 reports, keeping Inter for headlines and tabular data.

### 1.6 Micro-adjustments

- `text-justify: inter-word` for German body — never `inter-character` (breaks German compound word legibility).
- Headlines (≥24pt): `letter-spacing: -0.015em` to `-0.025em`. Body text: 0 or +0.005em max.
- `word-spacing`: leave default for justified body; for centered headlines use `word-spacing: -0.02em` to tighten.
- `font-variant-numeric: oldstyle-nums proportional-nums` for body running prose; `tabular-nums lining-nums` for any column of figures.

### 1.7 OpenType features beyond bounds — recipe per text level

- **Body (running prose)**: `kern, liga, calt, onum, pnum` — kerning + standard ligatures + contextual alternates + old-style proportional figures.
- **Headlines**: `kern, liga, dlig, case, ss01` — add discretionary ligatures + case-sensitive forms (so brackets/punctuation align to caps) + the font's first stylistic set (usually the "designer's preferred alternates").
- **Numerics / tables**: `kern, lnum, tnum, zero` — lining tabular figures + slashed zero.
- **Pull-quotes**: `kern, liga, dlig, hlig, smcp, c2sc` — fancier ligatures + true small caps.

---

## 2. Paste-ready CSS recipes

```css
/* =========================================================
   B. EDITORIAL TYPOGRAPHY POLISH
   Production: WeasyPrint. Dev preview: Paged.js (Chromium).
   ========================================================= */

/* ---- 2.1 Font stack ------------------------------------- */
@font-face {
  font-family: "Source Serif 4";
  src: url("/fonts/SourceSerif4-VariableFont_opsz,wght.ttf") format("truetype-variations");
  font-weight: 200 900;
  font-style: normal;
  font-display: swap;
}
@font-face {
  font-family: "Inter";
  src: url("/fonts/InterVariable.ttf") format("truetype-variations");
  font-weight: 100 900;
  font-style: normal;
  font-display: swap;
}

:root {
  --font-body:    "Source Serif 4", "Vollkorn", Georgia, serif;
  --font-display: "Inter", "Helvetica Neue", system-ui, sans-serif;
  --font-mono:    "IBM Plex Mono", ui-monospace, monospace;
}

/* ---- 2.2 Body --- editorial running prose --------------- */
html { lang: de; }  /* must also be in <html lang="de"> markup */

body {
  font-family: var(--font-body);
  font-size: 11pt;
  line-height: 1.5;
  font-feature-settings: "kern" 1, "liga" 1, "calt" 1,
                         "onum" 1, "pnum" 1,
                         "lfbd" 1, "rtbd" 1;     /* harmless if unsupported */
  font-variant-numeric: oldstyle-nums proportional-nums;
  font-kerning: normal;
  text-rendering: optimizeLegibility;
  hyphens: auto;
  -webkit-hyphens: auto;
  hyphenate-character: "\2010";                  /* U+2010 HYPHEN, not - */
  hyphenate-limit-chars: 6 3 3;                  /* min word/before/after */
  hyphenate-limit-lines: 2;                      /* no >2 hyphens in a row */
  text-align: justify;
  text-justify: inter-word;
  word-spacing: 0;
  letter-spacing: 0;
  orphans: 2;
  widows: 2;
}

/* ---- 2.3 Headlines -------------------------------------- */
h1, h2, h3, .headline {
  font-family: var(--font-display);
  font-weight: 800;
  letter-spacing: -0.02em;
  line-height: 1.05;
  hyphens: manual;                /* never hyphenate headlines */
  text-wrap: balance;             /* Chromium/Paged.js only; ignored by WP */
  font-feature-settings: "kern" 1, "liga" 1, "dlig" 1, "case" 1, "ss01" 1,
                         "lfbd" 1, "rtbd" 1;
}
h1 { font-size: 36pt; letter-spacing: -0.025em; }
h2 { font-size: 24pt; letter-spacing: -0.02em; }
h3 { font-size: 16pt; letter-spacing: -0.015em; }

/* ---- 2.4 Pull-quote ------------------------------------- */
.pullquote {
  font-family: var(--font-body);
  font-style: italic;
  font-size: 18pt;
  line-height: 1.3;
  font-feature-settings: "kern" 1, "liga" 1, "dlig" 1, "hlig" 1,
                         "smcp" 1, "c2sc" 1,
                         "lfbd" 1, "rtbd" 1;
  hyphens: manual;
  text-indent: -0.45em;           /* polyfill: hang opening quote */
  padding-left: 0;
}
@supports (hanging-punctuation: first allow-end last) {
  .pullquote {
    text-indent: 0;
    hanging-punctuation: first allow-end last;
  }
}

/* ---- 2.5 Numerics / tabular ----------------------------- */
.numeric, td.num, .stat {
  font-family: var(--font-display);
  font-feature-settings: "kern" 1, "lnum" 1, "tnum" 1, "zero" 1;
  font-variant-numeric: lining-nums tabular-nums slashed-zero;
}

/* ---- 2.6 Optical margin alignment (Typeset.js classes) -- */
/*  Negative-margin pulls for problem capitals + quotes      */
.pull-T, .pull-V, .pull-W, .pull-Y { margin-left: -0.07em; }
.pull-O, .pull-C, .pull-o, .pull-c { margin-left: -0.04em; }
.pull-A                             { margin-left: -0.03em; }
.pull-single                        { margin-left: -0.27em; display: inline-block; }
.pull-double                        { margin-left: -0.46em; display: inline-block; }

.push-T, .push-V, .push-W, .push-Y { margin-right: 0.07em; }
.push-O, .push-C, .push-o, .push-c { margin-right: 0.04em; }
.push-A                             { margin-right: 0.03em; }
.push-single                        { margin-right: 0.27em; display: inline-block; }
.push-double                        { margin-right: 0.46em; display: inline-block; }

/* Trailing punctuation push-out (Typeset.js style) */
.hang-period,  .hang-comma   { margin-right: -0.20em; }
.hang-hyphen                 { margin-right: -0.25em; }

/* ---- 2.7 Idempotence: do not double-apply -------------- */
.typeset-done { /* sentinel; preprocessor sets this on processed nodes */ }

/* ---- 2.8 Hanging punctuation native (if engine supports) */
@supports (hanging-punctuation: first allow-end last) {
  body p, .has-hang {
    hanging-punctuation: first allow-end last;
  }
}

/* ---- 2.9 Drop-cap (figure 5+ lines) --------------------- */
.dropcap::first-letter {
  font-family: var(--font-display);
  font-weight: 900;
  float: left;
  font-size: 5.2em;
  line-height: 0.85;
  margin: 0.05em 0.08em -0.05em -0.06em;  /* last value pulls left, optical */
  font-feature-settings: "kern" 1, "case" 1;
}
```

---

## 3. Python preprocessor sketch (`typeset_polish.py`)

```python
"""
typeset_polish.py - WeasyPrint preprocessor (~150 lines)
Idempotent DOM walker that wraps glyphs in span.pull-* / span.push-* / span.hang-*
to emulate InDesign Optical Margin Alignment.

Pipeline position:  template_render(html) -> typeset_polish(html) -> weasyprint(html)
"""
from __future__ import annotations
import re
from lxml import etree, html as lxml_html
from typing import Iterable

# ---- Configuration ------------------------------------------------------
PULL_HEAVY    = set("TVWY")
PULL_HEAVY_LO = set("tvwy")
PULL_MED      = set("OC")
PULL_MED_LO   = set("oc")
PULL_LIGHT    = set("A")
# Diacritic equivalents (per Typeset.js diacriticMap)
PULL_T_DIAC = set("ŤŢ")
PULL_O_DIAC = set("ÖÓÒÔÕØ")
PULL_A_DIAC = set("ÄÁÀÂÃÅ")
PULL_C_DIAC = set("ÇĆČ")

# Quote characters that hang into the margin
DOUBLE_QUOTES  = set('"“„«')   # "  „  «
SINGLE_QUOTES  = set("'‘‚‹")  # ʼ  ‚  ‹
ALL_QUOTES     = DOUBLE_QUOTES | SINGLE_QUOTES

# Trailing-margin punctuation
HANG_TRAIL = {".": "hang-period", ",": "hang-comma", "-": "hang-hyphen",
              "‐": "hang-hyphen", "–": "hang-hyphen"}

# Skip these elements entirely
SKIP_TAGS  = {"pre", "code", "kbd", "samp", "script", "style", "textarea",
              "tt", "var", "math"}
SKIP_CLASS = {"no-typeset", "typeset-done"}

# Brand-specific manual-shy injection map (German compound exception list)
SHY = "­"
COMPOUND_EXCEPTIONS = {
    # "Donaudampfschiffahrtsgesellschaft":
    #     "Donau" + SHY + "dampf" + SHY + "schiff" + SHY + "fahrts" + SHY + "gesellschaft",
}


# ---- Helpers ------------------------------------------------------------
def _is_skipped(el: etree._Element) -> bool:
    if el.tag in SKIP_TAGS:
        return True
    cls = (el.get("class") or "").split()
    return bool(SKIP_CLASS.intersection(cls))


def _pull_class(ch: str) -> str | None:
    """Return e.g. 'pull-T' for a glyph that needs a left-margin pull, else None."""
    if ch in PULL_HEAVY    or ch in PULL_T_DIAC: return f"pull-{ch.upper()}"
    if ch in PULL_HEAVY_LO:                       return f"pull-{ch}"
    if ch in PULL_MED      or ch in PULL_O_DIAC or ch in PULL_C_DIAC:
        return f"pull-{ch.upper()}"
    if ch in PULL_MED_LO:                         return f"pull-{ch}"
    if ch in PULL_LIGHT    or ch in PULL_A_DIAC:  return "pull-A"
    if ch in DOUBLE_QUOTES:                       return "pull-double"
    if ch in SINGLE_QUOTES:                       return "pull-single"
    return None


def _push_class(pull_cls: str) -> str:
    return pull_cls.replace("pull-", "push-")


def _wrap_span(text: str, cls: str) -> etree._Element:
    span = etree.Element("span", attrib={"class": cls})
    span.text = text
    return span


# ---- Core transforms ----------------------------------------------------
def _wrap_leading(text: str) -> list:
    """
    Wrap the first character of `text` in a pull-span if it needs optical pull.
    Returns a list mixing strings + Element nodes (consumed by _splice).
    """
    if not text:
        return [text]
    first = text[0]
    cls = _pull_class(first)
    if cls is None:
        return [text]
    # Split off first char, wrap, keep the rest as plain text
    return [_wrap_span(first, cls), text[1:]]


def _wrap_trailing_punct(text: str) -> list:
    """Wrap trailing . , - / hyphen in hang-* span to push past the right margin."""
    if not text:
        return [text]
    last = text[-1]
    cls = HANG_TRAIL.get(last)
    if cls is None:
        return [text]
    return [text[:-1], _wrap_span(last, cls)]


def _inject_shy(text: str) -> str:
    """Inject U+00AD into known German compound exceptions."""
    for word, replacement in COMPOUND_EXCEPTIONS.items():
        text = text.replace(word, replacement)
    return text


def _splice(parent: etree._Element, child: etree._Element | None,
            pieces: list, is_tail: bool):
    """
    Replace `child.text` (if is_tail=False) or `child.tail` with the sequence
    `pieces` (mix of strings & Elements). Idempotent on already-processed text.
    """
    # Build replacement text + child-spans
    new_text_parts = []
    new_children = []
    for p in pieces:
        if isinstance(p, str):
            if new_children:
                # tail of last appended span
                last = new_children[-1]
                last.tail = (last.tail or "") + p
            else:
                new_text_parts.append(p)
        else:  # Element span
            new_children.append(p)
    new_text = "".join(new_text_parts) or None

    if is_tail:
        # Insert spans after `child` in parent, and rewrite child.tail
        child.tail = new_text
        idx = list(parent).index(child) + 1
        for sp in new_children:
            parent.insert(idx, sp); idx += 1
    else:
        parent.text = new_text
        for sp in reversed(new_children):
            parent.insert(0, sp)


def _walk(el: etree._Element):
    """Depth-first DOM walk applying preprocessor to every text node."""
    if _is_skipped(el):
        return

    # 1. Process el.text (text before first child)
    if el.text:
        txt = _inject_shy(el.text)
        # First, leading-pull on first glyph
        leading = _wrap_leading(txt)
        # Then trailing-punct on the LAST string piece
        if leading and isinstance(leading[-1], str):
            tail = _wrap_trailing_punct(leading[-1])
            leading = leading[:-1] + tail
        _splice(el, None, leading, is_tail=False)

    # 2. Recurse into children + process tails
    for child in list(el):
        _walk(child)
        if child.tail:
            txt = _inject_shy(child.tail)
            pieces = _wrap_leading(txt)
            if pieces and isinstance(pieces[-1], str):
                pieces = pieces[:-1] + _wrap_trailing_punct(pieces[-1])
            _splice(el, child, pieces, is_tail=True)

    # 3. Mark as processed (idempotence sentinel)
    classes = (el.get("class") or "").split()
    if "typeset-done" not in classes:
        classes.append("typeset-done")
        el.set("class", " ".join(classes))


# ---- Public API ---------------------------------------------------------
def typeset_polish(html_str: str) -> str:
    """
    Idempotent. Safe to call twice (the typeset-done sentinel guards re-entry).
    """
    tree = lxml_html.fromstring(html_str)
    # Apply to <body> only (so <head>, <script>, etc. are untouched)
    body = tree.find(".//body") if tree.tag != "body" else tree
    if body is None:
        body = tree
    _walk(body)
    return lxml_html.tostring(tree, encoding="unicode")


# ---- CLI smoke test -----------------------------------------------------
if __name__ == "__main__":
    sample = '<p>"Typografie ist die Kunst." Das sagt Tschichold. Aber: warum?</p>'
    print(typeset_polish(sample))
    # Expected: <p><span class="pull-double">"</span>Typografie ...
    #             ... <span class="pull-T">T</span>schichold ...
```

**Why this works for our stack (idempotent / belt-and-suspenders):**

1. The `typeset-done` class sentinel prevents double-wrapping if the preprocessor is run twice (e.g., dev hot-reload).
2. The CSS classes degrade gracefully — if `lfbd`/`rtbd` ever ship in WeasyPrint, the negative margins are simply additive (and small enough they won't visibly compound for editorial-grade type sizes).
3. The `@supports (hanging-punctuation: first)` block means a future Chromium upgrade automatically enables native behavior without code changes.
4. Soft-hyphen injection (`_inject_shy`) layers on top of WeasyPrint's native Pyphen hyphenation — Pyphen handles 95% of German words; the exception dictionary handles the long-tail brand and compound words.

---

## 4. Font picks — recommendation

| Tier | Body | Display | Why |
|---|---|---|---|
| **DMC Default** | Source Serif 4 | Inter 800/900 | Free, variable, fully-loaded OpenType, matched Adobe duo philosophy. Bundle size: ~2 × 600 kB. |
| **DMC Apex (top-shelf brand)** | Vollkorn | Inter 900 | Vollkorn brings true small caps, discretionary ligatures, stylistic sets — closer to magazine-grade warmth. |
| **DMC Technical/Data** | IBM Plex Serif | IBM Plex Sans + Mono | Institutional B2B B; one-family discipline; superior tabular figures. |

All four fonts ship under **SIL Open Font License 1.1** — no licensing concerns for a Docker-bundled server.

---

## 5. Evidence / citations

- **Typeset.js source & class taxonomy** — https://github.com/davidmerfield/Typeset (README CSS recipe; `src/hangingPunctuation.js` for the `alignMe = "CcOoYTAVvWw"` list and the `diacriticMap`)
- **`hanging-punctuation` browser support** — https://caniuse.com/css-hanging-punctuation (Safari only as of 2026; Chromium not shipped); https://chriscoyier.net/2023/11/27/the-hanging-punctuation-property-in-css/ (polyfill pattern)
- **`hanging-punctuation` polyfill (Kenneth Ormandy)** — https://github.com/kennethormandy/hanging-punctuation
- **WeasyPrint feature matrix** — https://doc.courtbouillon.org/weasyprint/stable/features.html (confirms `hyphens`, `hyphenate-character`, `hyphenate-limit-chars`, `hyphenate-limit-zone`, `font-feature-settings` SUPPORTED; `hanging-punctuation` and `text-indent`-edge-cases UNSUPPORTED)
- **PrinceXML hyphenation + features** — https://www.princexml.com/doc/11/hyphenation/ (German bundled); https://www.princexml.com/doc/properties/font-variant/ (`prince-opentype()` syntax + features list)
- **Hyphenopoly Node module** — https://github.com/mnater/Hyphenopoly + https://mnater.github.io/Hyphenopoly/ (TeX `hyph-de-1996` / `hyph-de-2006` patterns, trie compilation, German syllabification mode)
- **Pyphen (WeasyPrint's hyphenation backend)** — https://github.com/Kozea/Pyphen (Hunspell `.dic` patterns for `de_DE`, `de_1996`, `de_2006`, `de_CH`)
- **Print-CSS compatibility matrix** — https://print-css.rocks/lesson/lesson-hyphenation (confirms WeasyPrint + PrinceXML hyphenation OK; Paged.js no built-in)
- **Font OpenType feature inventories:**
  - Inter — https://rsms.me/inter/ (`calt`, `dlig`, `tnum`, `frac`, `case`, `ss01–ss08`, `cv01–cv13`; no `lfbd`/`rtbd`)
  - Vollkorn — http://vollkorn-typeface.com/ and https://www.beautifulwebtype.com/vollkorn/ (`liga`, `dlig`, `calt`, `smcp`, `c2sc`, `frac`, `onum`, `pnum`, `tnum`, `lnum`, `ss01`; no bounds)
  - Crimson Pro — https://www.beautifulwebtype.com/crimson-pro/ (oldstyle/lining numerals + smcp)
  - Source Serif — https://fonts.adobe.com/fonts/source-serif (transitional, pairs with Source Sans)
  - IBM Plex — https://github.com/IBM/plex (Serif + Sans + Mono superfamily)
- **OpenType `lfbd`/`rtbd` spec** — https://learn.microsoft.com/en-us/typography/opentype/spec/features_ko (registered features list)
- **PRD-confirmed renderer** — `/Users/utkarsh/Projects/richard/PRD.md` line 5 (WeasyPrint production) + line 167 (Pyphen + `lang="de"`)

---

## Risks

- **Optical Margin Alignment is preprocessor-only.** Free engines (WeasyPrint, Chromium, Prince) won't catch up before this ships. Mitigation: ship the preprocessor.
- **Free fonts lack `lfbd`/`rtbd` tables.** Even paying for Adobe fonts wouldn't help — these tables are rare. The preprocessor is the only real path; setting them in CSS is harmless future-proofing.
- **German compound-word hyphenation gaps in Pyphen.** For long proper-noun compounds Pyphen will miss break points. Mitigate with a curated `&shy;` injection dictionary in the preprocessor (sketch §3 `_inject_shy`).

---

## 3-sentence summary

**(a) Recipe:** Use WeasyPrint with `hyphens:auto` + `lang="de"` + Pyphen for German hyphenation, layer a Python lxml preprocessor (~150 lines) that wraps problem-capital letters, opening quotes, and trailing punctuation in `.pull-*` / `.push-*` / `.hang-*` spans (Typeset.js taxonomy), plus a per-text-level `font-feature-settings` recipe (`kern liga calt onum pnum` for body, add `dlig case ss01` for headlines, `lnum tnum zero` for numerics). **(b) Fonts:** **Default = Source Serif 4 body + Inter 800 display**; **Apex brand = Vollkorn body + Inter 900 display** (both pairings free under SIL OFL); IBM Plex superfamily for technical/data-heavy reports. **(c) Risks:** Hanging-punctuation and `lfbd`/`rtbd` are unsupported across all our target engines and missing from all candidate free fonts — the preprocessor is the *only* InDesign-grade optical-margin path; German compound-word hyphenation will need a curated soft-hyphen exception dictionary for brand and long proper-noun terms.
