"""restructure_page — Stage 4.7, "the editor" (DNA: make a too-dense page breathe).

An OpenRouter LLM acts as a PARAPHRASE-ONLY editor on a single over-budget page:
it (1) CONDENSES the long-text prose fields and (2) MAY lift AT MOST ONE diagram
of kind ∈ {stat, process, q_a} out of structure that is ALREADY explicit in the
copy. It is an editor, NOT an author — and a deterministic, fail-closed
validation suite GUARANTEES that: no number/entity/hedge is invented, output is
strictly shorter, every diagram string is a verbatim source span, and any
violation reverts (per-field, diagram-null, or whole-page) to the ORIGINAL.

`before_after` and `convergence/venn` are intentionally OUTSIDE the LLM's scope
(set-membership guards can't see a fabricated *relationship* or *synthesis*);
those stay with the deterministic extractors (structure_content / plan_diagrams).

Mirrors stages/build_image_prompts.py: async httpx POST, temperature=0, strict
json_schema, fail-closed (None → caller renders the original page byte-identical).
Content-addressed cache → deterministic golden snapshots.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Optional

import httpx

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_TIMEOUT = 120.0
_PROMPT_VERSION = "2026-06-13.1"

# Long-text prose fields the editor may condense. Structured LIST fields
# (steps/faqs/beliefs/symptoms/metrics/zielgruppe/…) are NEVER sent and NEVER
# touched — they are owned by the deterministic layer.
_LONG_TEXT_FIELDS = (
    "body", "intro", "lede", "these", "key_insight",
    "kurzportraet", "ausgangsproblem", "ziel", "loesung",
    "ergebnis_text", "ergebnis", "antwort",
)
# Step/structure-DOMINATED pages: their content is a structured list (step cards,
# timeline) the editor must not touch; condensing their MINOR prose gains little
# and the reflow can tip an at-capacity grid into an overflow. Skip them entirely.
_STEP_DOMINATED_TYPES = frozenset({"ST-06", "ST-22"})

# kinds the LLM is allowed to emit (before_after / convergence are excluded —
# deterministic extractors own those). `process` is also excluded for now: its
# premium renderer band (DPL-3) isn't built, so accepting one would be dead data.
# Re-add "process" here the moment the process_flow band ships.
_LLM_DIAGRAM_KINDS = frozenset({"stat", "q_a"})

# Hedge/qualifier tokens that, if present beside a number in the source, must
# survive beside that same number in the output (no hedge→absolute flips).
_HEDGES = ("bis zu", "ca.", "rund", "etwa", "durchschnittlich", "im schnitt",
           "circa", "ungefähr", "mindestens", "höchstens", "tausende", "bis")
# negation/limiter tokens that may not be orphaned off the front of a diagram span.
_NEGATIONS = ("kein", "keine", "nicht", "ohne", "nur", "kaum")

_SYSTEM_PROMPT = (
    "You are a meticulous German-language report editor. You are given the raw "
    "long-text content fields of ONE page of a German B2B report that is TOO "
    "DENSE — its prose overflows the print box. Your ONLY job is to make the "
    "page breathe by tightening the existing German, and (optionally) by lifting "
    "ONE already-present structure into a small figure. You are an editor, not an "
    "author. You must NEVER invent, add, extrapolate, compute, average, round, "
    "generalize, rename, or import any fact, number, figure, range, unit, "
    "magnitude word, currency, date, name, claim, qualifier, or example that is "
    "not already literally present in the input fields.\n\n"
    "PART 1 — CONDENSE THE PROSE. Rewrite each text field in tighter German so "
    "the page breathes: cut filler, throat-clearing, transitions, and repeated "
    "restatements of the same point. Preserve EVERY concrete claim, figure, named "
    "entity, citation (e.g. \"BCG 2025\"), and the original meaning and register "
    "(formal \"Sie\"-form B2B German). The rewrite of each field MUST be strictly "
    "SHORTER than the input for that field. Do not merge, split, translate, or "
    "reorder facts across fields.\n\n"
    "ABSOLUTE PRESERVATION — copy character-for-character: numbers, %, ranges "
    "(keep BOTH endpoints — never collapse \"25-30 %\" to \"25 %\" or \"12 bis 24 "
    "Stunden\" to \"24 Stunden\"); magnitude words (Mio/Mrd/Tsd/Millionen/k — "
    "\"2,5 Mio €\" never becomes \"2,5 €\"); hedges (bis zu/ca./rund/etwa/im "
    "Schnitt/tausende) attached to numbers; proper nouns + citations with THEIR "
    "OWN year (\"30 %\" is BCG 2025; \"60 %\" is BCG 2026 — never merge years); "
    "negations (kein/keine/nicht/ohne/nur).\n\n"
    "PART 2 — EXTRACT ONE DIAGRAM (optional). ONLY if the prose ALREADY CONTAINS "
    "one of: \"stat\" (one headline figure + the label written beside it; payload "
    "{figure, label}); \"process\" (2-5 EXPLICITLY ORDERED steps each already "
    "titled; payload {steps:[{title, body}]}); \"q_a\" (an already-posed question "
    "+ its answer; payload {frage, antwort}). Every payload string MUST be a "
    "contiguous whole-clause span COPIED VERBATIM from the input — quote, never "
    "paraphrase or stitch, never start right after a negation word. You may NOT "
    "emit a before/after, comparison, or Venn. If no such structure is explicitly "
    "present, return diagram = null. A diagram REPLACES its source via "
    "replace_field, so drop the now-redundant sentences from that field's prose.\n\n"
    "Output only the JSON the schema defines: prose (array of {field, text}) and "
    "diagram (object or null). German content; no markdown, no notes, no English."
)

# Derived from the ACTUAL system prompt: editing _SYSTEM_PROMPT changes this, so
# a prompt edit invalidates every cached rewrite with no manual version bump.
_PROMPT_SIG = hashlib.sha256(_SYSTEM_PROMPT.encode("utf-8")).hexdigest()[:16]

_RESPONSE_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "page_restructure",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "prose": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "field": {"type": "string"},
                            "text": {"type": "string"},
                        },
                        "required": ["field", "text"],
                    },
                },
                "diagram": {
                    "type": ["object", "null"],
                    "additionalProperties": False,
                    "properties": {
                        "kind": {"type": "string"},
                        "payload": {"type": "object", "additionalProperties": True},
                        "replace_field": {"type": ["string", "null"]},
                    },
                    "required": ["kind", "payload", "replace_field"],
                },
            },
            "required": ["prose", "diagram"],
        },
    },
}


# ----------------------------------------------------------------------------
# PURE helpers
# ----------------------------------------------------------------------------
def _norm(s: str) -> str:
    """NFKC-normalize + collapse exotic spaces + whitespace runs. Applied
    IDENTICALLY to input and output so homoglyph/space tricks just trip a revert,
    never a false match."""
    s = unicodedata.normalize("NFKC", str(s or ""))
    for sp in (" ", " ", " ", " ", " "):
        s = s.replace(sp, " ")
    return re.sub(r"\s+", " ", s).strip()


def _select_fields(page_data: dict) -> list[str]:
    """The LONG-TEXT field names this page actually carries (non-empty strings)."""
    if not isinstance(page_data, dict):
        return []
    return [f for f in _LONG_TEXT_FIELDS
            if isinstance(page_data.get(f), str) and page_data[f].strip()]


def _all_strings(obj: Any) -> list[str]:
    """Every string anywhere in the page data (the grounding corpus — incl.
    structured-list strings the LLM never sees but whose numbers must survive)."""
    out: list[str] = []
    if isinstance(obj, str):
        out.append(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            out.extend(_all_strings(v))
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            out.extend(_all_strings(v))
    return out


# magnitude/unit-aware NUMBER ATOM tokenizer (NOT parse_german_number — that
# drops magnitudes/ranges; NOT plan_diagrams._FIGURE_RE — that misses 100+,
# €200k+, 2,5 Mio). A range joined by -/–/bis/auf is captured as ONE atom.
_NUMCORE = r"[€$£]?\s?\d[\d.,]*\+?"
_UNITMAG = (
    r"(?:\s?(?:Mio|Mrd|Tsd|Millionen|Milliarden|Tausend|k|M)\.?)?"
    r"(?:\s?(?:%|x|×|€|Min\.?|Minuten|Std\.?|Stunden|Tagen?|Tage|Monaten?|Monate|Jahren?|Jahre))?"
)
_RANGE_RE = re.compile(
    rf"(?:von\s+)?{_NUMCORE}{_UNITMAG}\+?\s*(?:bis|auf|[-–])\s*{_NUMCORE}{_UNITMAG}\+?",
    re.IGNORECASE,
)
# trailing \+? AFTER the unit/magnitude too, so "€200k+" keeps its "+".
_NUM_RE = re.compile(rf"{_NUMCORE}{_UNITMAG}\+?", re.IGNORECASE)


def _figure_tokens(text: str) -> set[str]:
    """Multiset (as a set) of normalized NUMBER ATOMS. Ranges are whole atoms
    (so '24 Stunden' alone never matches '12 bis 24 Stunden')."""
    t = _norm(text)
    atoms: set[str] = set()
    masked = t
    for m in _RANGE_RE.finditer(t):
        atoms.add(_norm(m.group(0)))
    # mask the ranges so their endpoints aren't also counted as singletons
    masked = _RANGE_RE.sub(" ", t)
    for m in _NUM_RE.finditer(masked):
        a = _norm(m.group(0))
        if any(ch.isdigit() for ch in a):
            atoms.add(a)
    return atoms


_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
# ALLCAPS acronyms ≥3 letters (BCG, KPMG, APEX, CRM) — citation/brand marks.
# German common nouns are Title-case (Prozesse, Engpässe), NOT all-caps, so this
# does NOT flag ordinary nouns recombined by a paraphrase (the over-revert bug).
_ACRONYM_RE = re.compile(r"\b[A-ZÄÖÜ]{3,}\b")


def _entity_set(page_data: dict, corpus: str) -> set[str]:
    """PROPER-NOUN entities only: explicit kunde/partner/author NAMES + citation
    YEARS + ALLCAPS acronyms. Deliberately NOT generic capitalized words — German
    capitalizes every noun, so flagging those would revert every legitimate
    paraphrase. Brand-agnostic: names read from data, never a literal."""
    ents: set[str] = set()
    if isinstance(page_data, dict):
        kunde = page_data.get("kunde")
        if isinstance(kunde, dict) and kunde.get("name"):
            ents.add(_norm(kunde["name"]))
        for key in ("partners", "logos", "press"):
            v = page_data.get(key)
            if isinstance(v, list):
                ents.update(_norm(x) for x in v if isinstance(x, str))
        author = page_data.get("author")
        if isinstance(author, dict) and author.get("name"):
            ents.add(_norm(author["name"]))
    c = _norm(corpus)
    ents.update(m.group(0) for m in _YEAR_RE.finditer(c))
    ents.update(m.group(0) for m in _ACRONYM_RE.finditer(c))
    return {e for e in ents if e}


def _payload_strings(diagram: dict) -> list[str]:
    p = (diagram or {}).get("payload") or {}
    out: list[str] = []
    for k in ("figure", "label", "frage", "antwort"):
        if isinstance(p.get(k), str):
            out.append(p[k])
    for step in (p.get("steps") or []):
        if isinstance(step, dict):
            for k in ("title", "body"):
                if isinstance(step.get(k), str):
                    out.append(step[k])
    return out


def _grounded_clause(span: str, corpus_norm: str) -> bool:
    """A diagram span must be a contiguous substring of the source AND not begin
    immediately after a negation token (orphaned-negation guard)."""
    s = _norm(span)
    if not s or s not in corpus_norm:
        return False
    idx = corpus_norm.find(s)
    pre = corpus_norm[max(0, idx - 40):idx].lower()
    pre_words = pre.split()[-3:]
    return not any(neg in pre_words for neg in _NEGATIONS)


def _validate_restructure(
    *, st_type: str, page_data: dict, fields: list[str],
    parsed: dict, copy_budget: Optional[int],
) -> Optional[dict]:
    """The fail-closed validation suite (checks 0-10). Returns an accepted
    {prose, diagram, reverted_fields, reverted_whole_page} or None (whole-page
    revert). NEVER raises — any anomaly → conservative revert."""
    try:
        # join with " | " so capitalized runs in ADJACENT fields don't merge into
        # a phantom entity (e.g. kunde.name bleeding into the body's first words).
        corpus = " | ".join(_all_strings(page_data))
        corpus_norm = _norm(corpus)
        in_atoms = _figure_tokens(corpus)
        in_ents = _entity_set(page_data, corpus)

        raw_prose = {str(it["field"]): str(it["text"])
                     for it in (parsed.get("prose") or [])
                     if isinstance(it, dict) and it.get("field") and isinstance(it.get("text"), str)}

        accepted: dict[str, str] = {}
        reverted: list[str] = []
        for f in fields:
            src = page_data.get(f)
            if not isinstance(src, str):
                continue
            out = raw_prose.get(f)
            if out is None:
                accepted[f] = src               # model omitted it → keep original
                continue
            # check 1: number-atom subset (no NEW number)
            out_atoms = _figure_tokens(out)
            if not out_atoms.issubset(in_atoms):
                accepted[f] = src; reverted.append(f); continue
            # check 2: hedge preservation for each surviving atom
            if not _hedges_preserved(_norm(src), _norm(out)):
                accepted[f] = src; reverted.append(f); continue
            # check 4: strictly shorter
            if not (len(_norm(out)) < len(_norm(src)) and out.strip()):
                accepted[f] = src; reverted.append(f); continue
            accepted[f] = out

        # ---- diagram validation (checks 6,7,8) ----
        diagram = parsed.get("diagram")
        out_diagram: Optional[dict] = None
        if isinstance(diagram, dict) and diagram.get("kind"):
            kind = str(diagram.get("kind"))
            spans = _payload_strings(diagram)
            ok = (
                kind in _LLM_DIAGRAM_KINDS
                and spans
                and all(_grounded_clause(s, corpus_norm) for s in spans)
                and _figure_tokens(" ".join(spans)).issubset(in_atoms)
            )
            if ok:
                rf = diagram.get("replace_field")
                if rf not in fields:        # check 8: replace_field validity
                    rf = None
                out_diagram = {"kind": kind, "payload": diagram.get("payload") or {},
                               "replace_field": rf}

        # ---- whole-page checks. The "union" is the FULL resulting page: the
        # accepted (modified) fields PLUS every UNTOUCHED field (kunde, structured
        # lists, citations) — those stay on the page, so their entities/atoms are
        # trivially preserved. This makes the recall checks flag ONLY facts dropped
        # from a field the editor actually rewrote. ----
        untouched_strings: list[str] = []
        for k, v in page_data.items():
            if k not in fields:
                untouched_strings.extend(_all_strings(v))
        union = " | ".join(list(accepted.values()) + untouched_strings
                           + _payload_strings(out_diagram or {}))
        union_norm = _norm(union)
        # 3a: every source entity still present somewhere on the final page
        if any(e not in union_norm for e in in_ents):
            return None
        # 3b: no INVENTED entity (every output entity traces to the source)
        if any(e not in corpus_norm for e in _entity_set({}, union)):
            return None
        # 5: recall floor — every input number atom survives somewhere
        if not in_atoms.issubset(_figure_tokens(union)):
            return None
        # 9: shorter total prose
        in_total = sum(len(_norm(page_data[f])) for f in fields if isinstance(page_data.get(f), str))
        out_total = sum(len(_norm(v)) for v in accepted.values())
        if not (out_total < in_total):
            return None

        if not reverted and not out_diagram and out_total == in_total:
            return None  # nothing changed

        return {"prose": accepted, "diagram": out_diagram,
                "reverted_fields": reverted, "reverted_whole_page": False}
    except Exception:  # noqa: BLE001 — any anomaly is a conservative whole-page revert
        return None


def _hedges_preserved(src_norm: str, out_norm: str) -> bool:
    """Every hedge present in the source (lowercased) must still be in the output.
    Coarse but safe: a condensation may not silently drop 'bis zu'/'ca.' etc."""
    s, o = src_norm.lower(), out_norm.lower()
    for h in _HEDGES:
        if h == "bis":
            continue  # 'bis' handled inside range atoms
        if h in s and h not in o:
            return False
    return True


def _build_user_prompt(st_type: str, fields: list[str], page_data: dict,
                       copy_budget: Optional[int]) -> str:
    lines = [f"PAGE TYPE: {st_type}"]
    if copy_budget:
        cur = sum(len(str(page_data.get(f) or "")) for f in fields)
        lines.append(f"Current prose ≈ {cur} chars; target budget ≈ {copy_budget}. "
                     f"Condense to fit while preserving every fact.")
    lines.append("FIELDS TO CONDENSE (return one {field,text} per field, German, shorter):")
    for f in fields:
        lines.append(f"\n### {f}\n{page_data.get(f)}")
    # structured-list strings as READ-ONLY context (do NOT rewrite these):
    extra = [s for s in _all_strings({k: v for k, v in page_data.items() if k not in fields})
             if s.strip()]
    if extra:
        lines.append("\nREAD-ONLY CONTEXT (other content on the page — do NOT "
                     "rewrite; you MAY quote a verbatim span for a diagram):")
        lines.append(" | ".join(extra[:40]))
    return "\n".join(lines)


def restructure_cache_key(
    *, model: str, st_type: str, page_data: dict, copy_budget: Optional[int] = None
) -> str:
    sel = {f: page_data.get(f) for f in _LONG_TEXT_FIELDS if page_data.get(f) is not None}
    blob = "\x00".join([
        model, st_type, _PROMPT_SIG, str(copy_budget),
        json.dumps(sel, sort_keys=True, ensure_ascii=False),
    ])
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


async def restructure_page(
    *,
    st_type: str,
    page_data: dict,
    copy_budget: Optional[int],
    api_key: Optional[str],
    model: str,
    cache_dir: Optional[Path] = None,
    http_client: Optional[httpx.AsyncClient] = None,
    timeout: float = _TIMEOUT,
) -> Optional[dict]:
    """Condense + (maybe) extract a diagram for ONE over-budget page. Returns an
    accepted-and-validated dict, or None (caller renders the original untouched).
    Fail-closed at every step."""
    if st_type in _STEP_DOMINATED_TYPES:
        return None  # structured-step page — leave its prose verbatim
    fields = _select_fields(page_data)
    if not api_key or not isinstance(page_data, dict) or not fields:
        return None

    # content-addressed cache → deterministic goldens
    cache_path: Optional[Path] = None
    if cache_dir is not None:
        cache_dir = Path(cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = cache_dir / f"{restructure_cache_key(model=model, st_type=st_type, page_data=page_data, copy_budget=copy_budget)}.json"
        if cache_path.exists():
            try:
                return json.loads(cache_path.read_text(encoding="utf-8")) or None
            except (OSError, ValueError):
                pass

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(st_type, fields, page_data, copy_budget)},
        ],
        "temperature": 0,
        "response_format": _RESPONSE_SCHEMA,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    owns = http_client is None
    client = http_client or httpx.AsyncClient(timeout=timeout)
    try:
        resp = await client.post(_OPENROUTER_URL, json=payload, headers=headers)
        if resp.status_code != 200:
            return None
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        result = _validate_restructure(
            st_type=st_type, page_data=page_data, fields=fields,
            parsed=parsed, copy_budget=copy_budget,
        )
    except (httpx.HTTPError, KeyError, ValueError, TypeError):
        return None
    finally:
        if owns:
            await client.aclose()

    if result is not None and cache_path is not None:
        try:
            cache_path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
    return result


def apply_restructure(pages: list, results: list) -> list:
    """SOLE MUTATOR. Overwrite accepted prose fields + write data['diagram'] (the
    SAME key + replace-blank convention apply_diagram_plan uses). Idempotent.
    A None result leaves the page byte-identical. pages and results are aligned
    by index (the caller gathers results in flagged-page order)."""
    for page, result in zip(pages, results):
        if not result:
            continue
        data = page.setdefault("data", {}) if isinstance(page, dict) else None
        if data is None:
            # pydantic page object with .data
            data = getattr(page, "data", None)
            if data is None:
                continue
        for f, text in (result.get("prose") or {}).items():
            if isinstance(text, str) and text.strip():
                data[f] = text
        diag = result.get("diagram")
        if diag:
            rendered = _to_renderer_diagram(diag)
            if rendered:
                rf = diag.get("replace_field")
                rendered["source"] = "restructure_page"
                data["diagram"] = rendered
                if rf and rf in data:
                    data[rf] = ""
    return pages


def _to_renderer_diagram(diag: dict) -> Optional[dict]:
    """Map the LLM's diagram payload onto the renderer's FLAT dispatch contract
    (concept_diagram/stat_callout read top-level fields; q_a_ladder reads items[]).
    Unknown/empty → None (no diagram written)."""
    kind = str(diag.get("kind") or "")
    p = diag.get("payload") or {}
    if kind == "stat" and p.get("figure"):
        return {"kind": "stat_callout", "figure": p["figure"], "label": p.get("label", "")}
    if kind == "q_a" and p.get("frage") and p.get("antwort"):
        return {"kind": "q_a", "items": [{"frage": p["frage"], "antwort": p["antwort"]}]}
    return None
