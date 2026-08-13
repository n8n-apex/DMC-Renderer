"""Grounded visual-device synthesis.

Turns a page's PROSE into the skimmable visual layer premium DMC pages need
(big-number stat callouts, before/after devices, comparisons) so the rich
treatments (a4_metric_column, a4_bi_dashboard, ...) have something to bind to.
Without this every prose-only page falls to a thin text treatment (the christoph
deck: 0 viz, 0 images, stats on 3 of 15 pages) and reads cramped with dead space.

THE ACCURACY GUARANTEE (why it cannot "synthesize wrong"): whatever proposes a
device (the LLM structurer OR the deterministic fallback), EVERY numeric token it
displays must appear VERBATIM in that page's own source text, or the device is
DROPPED. `_ground_device` is the gate. A stat can never show a number the copy
did not state, a label can never attach a figure to the wrong thing without the
figure being present, and nothing is computed. Grounding is checked on the raw
digit runs (whitespace / thousands-dot / decimal-comma insensitive), so
"2 Std -> 20 Min" grounds against "von 2 Stunden auf 20 Minuten" (2 and 20 both
present) but a fabricated "45 %" grounds against nothing and is rejected.

LLM vs deterministic: with OPENROUTER_API_KEY set, an LLM (temperature 0) reads
the page and proposes well-labelled devices, then the gate validates them.
Without a key, a conservative deterministic pass extracts the unambiguous devices
(before/after phrases, currency/percent callouts). Either way the gate runs, so
the output is grounded by construction.
"""
from __future__ import annotations

import json
import os
import re
import sys
from typing import Any, Optional

# --- grounding primitives ----------------------------------------------------
# every maximal digit run in a text, thousands-dot / decimal-comma collapsed so
# "1.200" -> "1200", "12,5" -> "125" match how the same value is written anywhere.
_DIGITS = re.compile(r"\d[\d.,]*")


def _digit_tokens(text: str) -> set[str]:
    out: set[str] = set()
    for m in _DIGITS.finditer(text or ""):
        out.add(re.sub(r"[.,\s]", "", m.group(0)))
    return out


def _numbers_in(value: str) -> list[str]:
    return [re.sub(r"[.,\s]", "", m.group(0)) for m in _DIGITS.finditer(str(value or ""))]


# thousands-separated shape: groups of 3 after dots, optional decimal comma.
_THOUSANDS_DE = re.compile(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?")


def _parse_number_de(token: str) -> float:
    """Parse a figure token with German separators: dot-groups-of-3 are
    thousands separators, comma is the decimal mark ('1.200' -> 1200.0,
    '2,5' -> 2.5, '12.5' -> 12.5)."""
    t = str(token or "").strip().strip(".,")
    if _THOUSANDS_DE.fullmatch(t):
        t = t.replace(".", "")
    return float(t.replace(",", "."))


def digit_key(value: Any) -> str:
    """Canonical dedup key for the one-figure-one-device rule (dedup ONLY;
    grounding stays separator-insensitive on purpose). Thousands-dots and
    whitespace are stripped, a decimal comma becomes a dot, so '1.200' and
    '1200' collide while '2,5' and '25' stay distinct. The key carries a
    UNIT CLASS after a '|' so the same number with different units stays
    distinct ('40 %' vs '40 Stunden' vs '40 Mitarbeiter') while spelling
    variants collide ('30 %' == '30%' == '30 Prozent'): '%' when the figure
    contains a percent sign or the word Prozent, else the first alphabetic
    word after the last digit (lowercased, trailing dot trimmed, empty when
    none)."""
    s = str(value if value is not None else "")
    toks: list[str] = []
    last_end = 0
    for m in _DIGITS.finditer(s):
        tok = m.group(0).strip(".,")
        if _THOUSANDS_DE.fullmatch(tok):
            tok = tok.replace(".", "")
        toks.append(tok.replace(",", "."))
        last_end = m.end()
    if not toks:
        return ""
    if "%" in s or re.search(r"\bprozent\b", s, re.IGNORECASE):
        unit = "%"
    else:
        w = re.search(r"[^\W\d_]+", s[last_end:])
        unit = w.group(0).lower().rstrip(".") if w else ""
    return " ".join(toks) + "|" + unit


def _ground_device(device: dict, source_tokens: set[str]) -> bool:
    """True iff EVERY numeric token shown by the device is present in the source.

    A device with no numbers at all (e.g. a pure label) is NOT grounded here (we
    only synthesize NUMERIC devices; a text-only 'device' is just copy). This is
    the gate that makes fabrication impossible. Non-dict entries (a malformed
    LLM item) are skipped, never crashed on."""
    shown: list[str] = []
    for stat in device.get("stats", []) or []:
        if not isinstance(stat, dict):
            continue
        shown += _numbers_in(stat.get("value", ""))
    for pair in device.get("pairs", []) or []:
        if not isinstance(pair, dict):
            continue
        shown += _numbers_in(pair.get("before", ""))
        shown += _numbers_in(pair.get("after", ""))
    for ring in device.get("donuts", []) or []:
        if not isinstance(ring, dict):
            continue
        # the ring's DISPLAYED figure must ground; `percent` (the arc angle) is a
        # drawing parameter derived from that same figure, never shown as text.
        shown += _numbers_in(ring.get("figure", ""))
    if not shown:
        return False
    return all(tok in source_tokens for tok in shown)


# --- source text of a page ---------------------------------------------------
_TEXT_KEYS = (
    "title", "titel", "subtitle", "untertitel", "body", "einleitung",
    "angebot_text", "abschluss", "ueberleitung", "zusammenfassung",
    "kernaussage", "erklaerung", "bezug", "ergebnis_text", "text", "ablauf_text",
)


def _page_source_text(data: dict) -> str:
    """All human-readable strings on the page, concatenated, for grounding +
    (LLM) context. Walks nested lists/dicts so schmerzpunkte / irrtuemer /
    schritte / vertrauenspunkte / ausblick_punkte text is included."""
    parts: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, str):
            parts.append(node)
        elif isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(data)
    return "\n".join(parts)


# --- shared percent/donut helpers (the ONE owner of the %-figure -> device
# routing rule; build_live's writer-v4 adapter calls these too) ---------------
_PERCENT_NUM = re.compile(r"\d+(?:[.,]\d+)?")


def percent_arc(figure: str) -> Optional[float]:
    """The donut arc angle for a %-figure, or None when the figure is NOT a
    drawable share of a whole: no parseable number, a value over 100 (a
    growth/delta percentage like "300 %" drawn as a ring would assert a false
    100% share), or a RANGE ("70 % to 75 %", "70-75 %", "70 bis 75") - a range
    has no single arc, and the long string shrinks illegibly inside the ring
    (the 2026-07-13 "shitty infographic" middle donut). Non-ring figures belong
    in a stat callout."""
    s = str(figure or "")
    if re.search(r"\d\s*(?:%|prozent)?\s*(?:to|bis|-|–|—)\s*\d", s, re.IGNORECASE):
        return None
    m = _PERCENT_NUM.search(s)
    if not m:
        return None
    # German separators BEFORE the 0..100 gate: '1.200 %' is 1200, not 1.2,
    # so it is rejected here and routed to a stat instead of a false ring.
    pct = _parse_number_de(m.group(0))
    if pct < 0.0 or pct > 100.0:
        return None
    return pct


def donut_spec(figure: Any, label: Optional[str] = None,
               source: Optional[str] = None) -> Optional[dict]:
    """A donut viz spec for a %-shaped figure, or None when it is not
    ring-drawable (route it to a stat instead). The displayed figure keeps the
    writer's exact number; a missing % symbol is appended (unit presentation
    for a value the writer declared as a percentage, not a value change)."""
    fig = str(figure or "").strip()
    if not fig:
        return None
    pct = percent_arc(fig)
    if pct is None:
        return None
    # phrase figures ('30 Prozent weniger Aufwand') are NOT ring-drawable: the
    # prose belongs in a label, so route them to a stat. Only a clean
    # number(+unit) figure gets the ring.
    m = _PERCENT_NUM.search(fig)
    leftover = fig[:m.start()] + " " + fig[m.end():]
    leftover = leftover.replace("%", " ", 1)
    leftover = re.sub(r"\bprozent\b", " ", leftover, count=1, flags=re.IGNORECASE)
    if re.search(r"[^\W\d_]", leftover):
        return None
    if "%" not in fig:
        fig = re.sub(r"\s*prozent\s*$", "", fig, flags=re.IGNORECASE).strip() + " %"
    spec: dict = {"preset": "donut", "figure": fig, "percent": pct}
    if label:
        spec["label"] = label
    if source:
        spec["source"] = source
    return spec


# --- deterministic extraction (no key) --------------------------------------
# A before/after phrase: "von X auf Y", "X -> Y" (arrow), "X auf Y". Captures the
# two number+unit spans verbatim.
_BEFORE_AFTER = re.compile(
    r"von\s+(\d[\d.,]*\s*\w+)\s+auf\s+(\d[\d.,]*\s*\w+)", re.IGNORECASE)
_ARROW = re.compile(r"(\d[\d.,]*\s*\w*)\s*(?:->|→|➔)\s*(\d[\d.,]*\s*\w+)")

# words a captured pair value may legitimately end on (units and their common
# declensions); any other trailing word is regex overshoot ("2026 stieg").
_PAIR_UNIT_WORDS = {
    "euro", "eur", "prozent", "min", "minuten", "std", "stunde", "stunden",
    "tag", "tage", "tagen", "woche", "wochen", "monat", "monate", "monaten",
    "jahr", "jahre", "jahren",
}
_TRAILING_WORD = re.compile(r"\s([^\W\d_]+\.?)$")


def _clean_after_value(value: str, before: str = "") -> Optional[str]:
    """Strip a trailing non-unit word the pair regex absorbed (a verb after a
    bare year, e.g. '2026 stieg'); None when no digit survives. A trailing
    word the BEFORE value also ends with (case-insensitive) is a shared
    count noun ('von 20 Kunden auf 50 Kunden') and is KEPT, so both sides
    stay symmetric; the year-span rejection still fires downstream because a
    verb after a bare year ('2026 stieg') never matches the before side."""
    v = re.sub(r"\s+", " ", str(value or "")).strip()
    m = _TRAILING_WORD.search(v)
    if m:
        word = m.group(1).lower().rstrip(".")
        bm = _TRAILING_WORD.search(re.sub(r"\s+", " ", str(before or "")).strip())
        before_word = bm.group(1).lower().rstrip(".") if bm else None
        if word not in _PAIR_UNIT_WORDS and word != before_word:
            v = v[:m.start()].strip()
    return v if re.search(r"\d", v) else None


def _is_bare_year(value: str) -> bool:
    s = str(value or "").strip()
    return bool(re.fullmatch(r"\d{4}", s)) and 1900 <= int(s) <= 2100

# A stat-worthy figure: a number carrying a unit that makes it a headline metric.
_FIGURE = re.compile(
    r"(?:über|ueber|rund|ca\.?|bis zu)?\s*"
    r"(\d[\d.,]*(?:\s*(?:bis|to)\s*\d[\d.,]*)?)\s*"
    r"(%|€|EUR|Euro|Prozent|Minuten|Min\.?|Stunden|Std\.?|Tage|Tagen|Wochen|"
    r"Monate|Monaten|Jahre|Jahren|Unternehmen|Nutzer|Mitarbeiter|Fahrzeuge|"
    r"Fahrzeugen|Immobilien|Gewerbeimmobilien|Assets|Geräte|Geraete)\b",
    re.IGNORECASE)


def _deterministic_devices(text: str) -> list[dict]:
    """The conservative no-key pass: before/after devices + figure callouts, all
    with verbatim values. Labels are kept short and generic (the LLM path yields
    better labels); a device with no clean label still carries its grounded
    figure, which is the point. `text` is the page source text, computed ONCE by
    the caller (it was being re-walked here and in the LLM path)."""
    devices: list[dict] = []

    # before/after (strongest, most recognizable device)
    pairs: list[dict] = []
    for rx in (_BEFORE_AFTER, _ARROW):
        for m in rx.finditer(text):
            before = m.group(1).strip()
            after = _clean_after_value(m.group(2), before)
            if not before or not after:
                continue
            if _is_bare_year(before) and _is_bare_year(after):
                # a date range ("von 2019 auf 2026"), not a magnitude change.
                continue
            if (before, after) not in [(p["before"], p["after"]) for p in pairs]:
                pairs.append({"before": before, "after": after, "label": ""})
    if pairs:
        devices.append({"kind": "before_after", "pairs": pairs[:3]})

    # figure callouts. Split the number from its unit so the callout has a real
    # LABEL (the unit noun) with no LLM: "250 Unternehmen" -> value "250", label
    # "Unternehmen". Currency stays WITH the number (a bare "83" is meaningless).
    # PERCENT figures that are a drawable share (0..100) become DONUT rings
    # (figure verbatim; the arc angle is a drawing parameter from the same
    # figure via donut_spec); a percent OVER 100 (growth/delta) is NOT a
    # proportion and stays a flat stat. A figure goes to exactly ONE device
    # class, never two: `seen` is seeded with the before/after pair numbers
    # above so a paired figure is not re-emitted as a stat or ring. Cap so a
    # page is not all stats.
    _UNIT_IN_VALUE = {"€", "eur", "euro"}
    _UNIT_PERCENT = {"%", "prozent"}
    stats: list[dict] = []
    donuts: list[dict] = []
    seen: set[str] = set()
    # pair seeds also claim their bare DIGIT part: a pair side captured
    # without its unit ('von 40 auf 20') must still block a '40 %' callout,
    # because it is the same occurrence in the text (unit-blind on purpose;
    # figure-vs-figure dedup below stays unit-aware via the full key).
    paired_digits: set[str] = set()
    for p in pairs:
        for side in ("before", "after"):
            k = digit_key(p.get(side, ""))
            if k:
                seen.add(k)
                paired_digits.add(k.split("|", 1)[0])
    for m in _FIGURE.finditer(text):
        number = re.sub(r"\s+", " ", m.group(1)).strip()
        unit = m.group(2).strip()
        # key over the FULL match (number + unit) so the unit-aware key lines
        # up with the pair-seeded keys above ('20 Minuten' on both sides).
        key = digit_key(m.group(0))
        if not key or key in seen or key.split("|", 1)[0] in paired_digits:
            continue
        seen.add(key)
        if unit.lower() in _UNIT_PERCENT:
            ring = donut_spec(f"{number} %")
            if ring is not None:
                donuts.append({"figure": ring["figure"], "percent": ring["percent"]})
            else:
                # not ring-drawable (e.g. a 300 % growth figure): a flat stat.
                stats.append({"value": f"{number} %", "label": ""})
        elif unit.lower() in _UNIT_IN_VALUE:
            stats.append({"value": f"{number} {unit}".strip(), "label": ""})
        else:
            stats.append({"value": number, "label": unit})
    if donuts:
        devices.append({"kind": "donuts", "donuts": donuts[:3]})
    if stats:
        devices.append({"kind": "stats", "stats": stats[:4]})

    return devices


# --- LLM structuring (env-gated) --------------------------------------------
_LLM_MODEL = "anthropic/claude-sonnet-4.6"
_LLM_PROMPT = (
    "You extract the numeric PROOF from one report page and return it as visual "
    "devices. STRICT RULES: use ONLY numbers that appear in the page text, copied "
    "verbatim; never compute, round, or invent a number; if a number is not in "
    "the text it does not exist. Give each figure a SHORT German label (2-5 words) "
    "naming what it measures, taken from the surrounding sentence. Return JSON: "
    '{"stats":[{"value":"<number+unit verbatim>","label":"<kurzes Label>"}],'
    '"pairs":[{"before":"<verbatim>","after":"<verbatim>","label":"<Label>"}]}. '
    "Prefer 2-4 of the most meaningful figures. Omit a key if empty. JSON only."
)


def _llm_devices(text: str, api_key: str) -> list[dict]:
    """Ask the LLM to structure the page's figures into labelled devices. The
    caller applies the grounding gate to whatever comes back, so a hallucinated
    number is rejected downstream. Returns [] on any error (best-effort)."""
    try:
        import httpx  # type: ignore
        resp = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": _LLM_MODEL,
                "temperature": 0,
                "messages": [
                    {"role": "system", "content": _LLM_PROMPT},
                    {"role": "user", "content": text},
                ],
            },
            timeout=40,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        content = re.sub(r"^```(?:json)?|```$", "", content.strip()).strip()
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            return []
        # shape gate: keep only well-formed entries so a malformed LLM item
        # (string instead of dict, empty values) never reaches the renderer.
        pairs = [p for p in (parsed.get("pairs") or [])
                 if isinstance(p, dict)
                 and isinstance(p.get("before"), str) and p["before"].strip()
                 and isinstance(p.get("after"), str) and p["after"].strip()]
        stats = [s for s in (parsed.get("stats") or [])
                 if isinstance(s, dict)
                 and s.get("value") is not None and str(s["value"]).strip()]
        donuts = [r for r in (parsed.get("donuts") or [])
                  if isinstance(r, dict)
                  and r.get("figure") is not None and str(r["figure"]).strip()]
        devices: list[dict] = []
        if pairs:
            devices.append({"kind": "before_after", "pairs": pairs})
        if stats:
            devices.append({"kind": "stats", "stats": stats})
        if donuts:
            devices.append({"kind": "donuts", "donuts": donuts})
        return devices
    except Exception:  # noqa: BLE001 - best-effort; deterministic pass still runs
        return []


# --- public entry ------------------------------------------------------------
def synthesize_page_visuals(data: dict, api_key: Optional[str] = None) -> dict:
    """Return the page `data` with grounded `stats` and/or `viz` MERGED in when
    the page carries no structured visual data of its own. Never overwrites data
    the writer already provided. Never adds an ungrounded figure. Pure w.r.t. the
    input dict (returns a shallow copy). `api_key` gates the LLM path (falls
    back to the process env when None); synthesis is ADDITIVE, so any unexpected
    failure degrades to the unchanged page, never sinks the render."""
    d = dict(data or {})
    try:
        return _synthesize(d, api_key)
    except Exception as e:  # noqa: BLE001 - additive layer; the page must survive
        print(f"[synthesize_visuals] synthesis skipped: {type(e).__name__}: {e}",
              file=sys.stderr)
        return d


def _synthesize(d: dict, api_key: Optional[str]) -> dict:
    # a page that already carries its own visual data (case-study metrics, an
    # authored viz) is left ALONE - we only fill the prose-only gaps.
    if d.get("viz") or d.get("stats") or d.get("ergebnis_metrics"):
        return d

    text = _page_source_text(d)
    source_tokens = _digit_tokens(text)
    if not source_tokens:
        return d  # no numbers on the page -> nothing to visualize

    key = api_key or os.environ.get("OPENROUTER_API_KEY")
    proposed = _llm_devices(text, key) if key else []
    if not proposed:
        proposed = _deterministic_devices(text)

    # THE GATE: keep only devices whose every number is grounded in this page.
    grounded = [dev for dev in proposed if _ground_device(dev, source_tokens)]
    if not grounded:
        return d

    stats: list[dict] = []
    viz: list[dict] = []
    for dev in grounded:
        if dev["kind"] == "stats":
            stats += dev["stats"]
        elif dev["kind"] == "before_after":
            viz.append({"preset": "bar_compare", "pairs": [
                {"label": p.get("label") or "", "before": {"value": p["before"]},
                 "after": {"value": p["after"]}} for p in dev["pairs"]]})
        elif dev["kind"] == "donuts":
            for ring in dev["donuts"]:
                # an LLM-supplied `percent` is NEVER trusted: the arc is
                # always re-derived from the displayed figure via donut_spec
                # (0..100 gate, German separators, phrase rejection, and the
                # % display append). A figure the spec rejects is still a
                # grounded number, so it survives as a flat stat.
                spec = donut_spec(ring.get("figure"), ring.get("label") or None)
                if spec is not None:
                    viz.append(spec)
                    continue
                fig = str(ring.get("figure") or "").strip()
                if fig:
                    stats.append({"value": fig, "label": ring.get("label") or ""})
    if stats:
        d["stats"] = stats
    if viz:
        d["viz"] = viz
    return d
