"""P0: build the REAL preprocessor package from an n8n envelope, in-process.

Runs the same stage sequence as `research/preprocessor/main.py:/render`
(stages 1->8.5), OFFLINE (no keys), then hands the package dir to the caller
to render with the Chromium engine. This replaces the hollow stub manifest in
service.py's build_manifest.

Runs under the RENDERER venv (the dependency superset that can import both the
preprocessor stages and the v7 engine). See docs/REBUILD-LOG.md.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import synthesize_visuals
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import brand_fallbacks as _fallbacks  # noqa: E402

log = logging.getLogger("dmc.build_live")

# Env-overridable so the SAME code runs locally (default: this checkout) and in
# the container (Dockerfile sets DMC_PREPROC_ROOT=/app/research/preprocessor).
PREPROC = Path(os.environ.get(
    "DMC_PREPROC_ROOT", "/Users/utkarsh/Projects/richard/research/preprocessor"))
if str(PREPROC) not in sys.path:
    sys.path.insert(0, str(PREPROC))

# preprocessor stage imports (verified importable under the renderer venv)
from models import (  # type: ignore
    BrandProfile, ClientInput, ImageManifest, ImageManifestItem,
    RenderRequest, ReportJson, ReportMeta, ReportPage,
)
from stages.assemble_package import assemble_package  # type: ignore
from stages.generate_assets import generate_assets  # type: ignore
from stages.generate_components import generate_components_for_report  # type: ignore
from stages.local_assets import client_assets_dir, list_client_assets  # type: ignore
from stages.plan_layout import plan_layout  # type: ignore
from stages.resolve_axes import resolve_axes  # type: ignore
from stages.resolve_fonts import resolve_fonts  # type: ignore
from stages.resolve_slots import normalize_name, resolve_slots  # type: ignore
from stages.structure_content import structure_content  # type: ignore
from stages.validate_copy import validate_copy  # type: ignore
from stages.validate_copyfit import validate_copyfit  # type: ignore
from stages.validate_cover import validate_cover  # type: ignore
from stages.validate_input import validate_and_resolve_brand_tokens  # type: ignore
from stages.route_package import route_package  # type: ignore
from contracts_v3.build_manifest import BuildManifestV3, BuildVersions  # type: ignore
from contracts_v3.report_plan import load_product_profile  # type: ignore
from pipeline_v3 import build_precomposition_bundle_v3  # type: ignore
from stages.plan_editorial_v3 import legacy_report_to_editorial_brief  # type: ignore

from adapter_v3 import adapt_envelope_v3

import httpx  # type: ignore

# slot_name -> (page ST type it belongs on, image_type)
SLOT_TO_ST = {
    "cover_hero": ("ST-01", "background"),
    "cover_author": ("ST-01", "portrait"),
    "about_logo": ("ST-05", "logo"),
    "status_quo_scene": ("ST-09", "scene"),
    # fazit_background removed (G7): ST-FAZIT grounds on the panel_texture
    # report asset + founder avatar + CTA; a per-page background had no reader.
}

WORKFLOW_BUILD_VERSION_FIELDS_V3 = {
    "workflow_contract_version": "workflow_contract",
    "writer_prompt_version": "writer_prompt",
    "schema_resolver_version": "schema_resolver",
    "writer_gate_version": "writer_gate",
    "source_ledger_version": "source_ledger",
    "claim_gate_version": "claim_gate",
}

def selected_contract_version() -> str:
    version = os.environ.get("DMC_CONTRACT_VERSION", "v2").strip().lower()
    if version not in {"v2", "v3"}:
        raise ValueError("DMC_CONTRACT_VERSION must be 'v2' or 'v3'")
    return version


def _env_or_dotenv(name: str):
    """Owner-gated keys: process env first, then the preprocessor's own .env
    (the canonical main.py loads it via pydantic_settings; this bridge skipped
    it, so every render ran "offline" while the keys sat on disk). Values are
    never logged. Unset in both places -> fully offline with zero spend."""
    v = os.environ.get(name)
    if v:
        return v
    try:
        for line in (PREPROC / ".env").read_text().splitlines():
            line = line.strip()
            if line.startswith(f"{name}="):
                return line.split("=", 1)[1].strip().strip('"').strip("'") or None
    except OSError:
        pass
    return None


# writer copy sometimes arrives ASCII-transliterated (ue/oe/ae for umlauts).
# Curated whole-word + word-initial-prefix restorations only; never inside a
# word, so genuine 'ue' sequences (Steuer, Dauer) stay untouched.
_UMLAUT_WORDS = {
    "ueber": "über", "Ueber": "Über",
    "loest": "löst",
    "fuer": "für", "Fuer": "Für",
    "koennen": "können", "Koennen": "Können",
    "moeglich": "möglich",
    "groesser": "größer",
    "naechste": "nächste", "Naechste": "Nächste",
    "spaeter": "später",
    "taeglich": "täglich",
    "waehrend": "während", "Waehrend": "Während",
}
_UMLAUT_WORD_RX = re.compile(
    r"\b(" + "|".join(sorted(_UMLAUT_WORDS, key=len, reverse=True)) + r")\b")
_UMLAUT_PREFIX_RX = re.compile(r"\b(ueber|Ueber)(?=[a-zA-ZäöüßÄÖÜ])")


def _fix_umlauts(text: str) -> str:
    t = _UMLAUT_WORD_RX.sub(lambda m: _UMLAUT_WORDS[m.group(1)], text)
    return _UMLAUT_PREFIX_RX.sub(
        lambda m: "über" if m.group(1) == "ueber" else "Über", t)


# German abbreviations that end a token with a period WITHOUT ending the
# sentence ("z. B.", "ca.", "bzw.", "Dr.", "u. a.", "ggf.", "inkl.").
_DE_ABBREV = {
    "z", "b", "ca", "bzw", "u", "a", "dr", "nr", "ggf", "inkl", "evtl",
    "std", "min", "max", "tel", "str", "bspw", "sog", "vgl", "etc",
}
# candidate boundary: sentence punctuation, whitespace, then an uppercase
# letter (a lowercase continuation is never a sentence start in German prose).
_SENT_BOUNDARY_RX = re.compile(r"(?<=[.!?])\s+(?=[A-ZÄÖÜ])")
# the token (letters/digits) immediately before a terminal period.
_TOKEN_BEFORE_DOT_RX = re.compile(r"([^\W_]+)\.$")


def _split_sentences_de(text: str) -> list[str]:
    """Split German prose into sentences, guarding ordinals and abbreviations.

    A naive split on [.!?]+whitespace breaks "Im 2. Schritt" and "z. B."
    into confetti. Here a split point requires [.!?] followed by whitespace
    AND an uppercase letter, and the token before a period must NOT be
    (a) a single letter ("z. B.", "u. a."), (b) a bare 1-2 digit run (an
    ordinal, "Im 2. Schritt"), or (c) a known abbreviation ("ca.", "bzw.").

    NOTE: validate_copy carries a sibling naive splitter that should
    eventually share this guarded one.
    """
    text = str(text or "").strip()
    if not text:
        return []
    out: list[str] = []
    start = 0
    for m in _SENT_BOUNDARY_RX.finditer(text):
        head = text[start:m.start()]
        if head.endswith("."):
            tok_m = _TOKEN_BEFORE_DOT_RX.search(head)
            tok = tok_m.group(1) if tok_m else ""
            if ((len(tok) == 1 and tok.isalpha())
                    or (tok.isdigit() and len(tok) <= 2)
                    or tok.lower() in _DE_ABBREV):
                continue
        out.append(head.strip())
        start = m.end()
    tail = text[start:].strip()
    if tail:
        out.append(tail)
    return [s for s in out if s]


def _fix_umlauts_deep(node, key=None):
    """Apply the umlaut restoration to COPY string values only. Dict keys are
    schema identifiers and stay byte-exact; URL-bearing values must too. G22:
    IDENTITY fields (author.name/role, kunde.name/company_url) are exempt —
    a curated name like "Waehrend" must never be rewritten to "Während"."""
    if isinstance(node, str):
        if "://" in node or (isinstance(key, str) and (key == "url" or key.endswith("_url"))):
            return node
        if isinstance(key, str) and key in ("name", "role", "funktion", "company"):
            return node
        return _fix_umlauts(node)
    if isinstance(node, dict):
        return {k: _fix_umlauts_deep(v, k) for k, v in node.items()}
    if isinstance(node, list):
        return [_fix_umlauts_deep(v, key) for v in node]
    return node


def _normalize_page_data(st_type: str, data: dict) -> dict:
    """Normalize the WRITER's field names to the CANONICAL render-layer schema.

    The n8n writer emits `headline` (+ per-type shapes like beliefs[].belief/
    reality) while the entire render layer (legacy patterns + treatment adapters)
    speaks the frozen-fixture schema (`title`, beliefs[].irrglaube/realitaet,
    ST-05 `stats`, ST-FAZIT `these`). Unnormalized, those pages fit no treatment,
    fall to legacy patterns reading absent keys, and PRINT raw dicts / literal
    "None" (the 2026-07-04 full-deck defects D1/D2). This is the single boundary
    where the two schemas meet, so the mapping lives here.

    GROUNDED: only renames/derives from values present in the writer data; never
    invents content. Original keys are preserved alongside the canonical ones.
    """
    d = dict(data or {})

    def _join(*parts):
        return "\n\n".join(str(p).strip() for p in parts if p and str(p).strip()) or None

    def _present(v):
        # explicit None/empty check, NOT truthiness: a legitimate 0 value
        # ("von 0 auf 12") must not silently drop the device.
        return v is not None and str(v).strip() != ""

    # G15: every alias application is logged (WARNING) so silent schema drift
    # surfaces in the render log instead of hiding. A writer key mapped to the
    # canonical render-layer name is recorded; keys that map to nothing are
    # logged at the end of the function.
    def _alias(source: str, target: str, value) -> None:
        log.warning("alias: %s.%s -> %s (value %r)", st_type, source, target, value)

    # canonical page title: the writer's `headline` (never overwrite a real title).
    if not d.get("title") and d.get("headline"):
        d["title"] = d["headline"]
        _alias("headline", "title", d["headline"])

    # --- christoph-winter DIALECT -> canonical --------------------------------
    # This writer emits titel/untertitel/einleitung/schmerzpunkte/irrtuemer/
    # schritte/wert/ablauf_text/kicker/vertrauenspunkte etc. Fold each into the
    # field the pattern or treatment actually reads (see docs/API_CONTRACT + the
    # patterns' data.get keys). Grounded renames only; nothing invented.
    if d.get("titel") and not d.get("title"):
        d["title"] = d["titel"]
        _alias("titel", "title", d["titel"])
    if d.get("untertitel") and not d.get("subtitle"):
        d["subtitle"] = d["untertitel"]
        _alias("untertitel", "subtitle", d["untertitel"])

    if st_type == "ST-01" and d.get("kicker") and not d.get("audience"):
        d["audience"] = d["kicker"]
        _alias("kicker", "audience", d["kicker"])
    elif st_type == "ST-02":
        # G13: ausblick_punkte are the reader's TAKEAWAYS, not the target
        # audience. They were renamed to `zielgruppe` and labelled "Zielgruppe
        # des Reports" (semantically wrong); they now map to `takeaways` and
        # render under "Was Sie mitnehmen". A real `zielgruppe` (if the writer
        # ever emits one) stays distinct.
        d["body"] = _join(d.get("body"), d.get("einleitung"), d.get("abschluss"))
        if d.get("ausblick_punkte") and not d.get("takeaways"):
            d["takeaways"] = list(d["ausblick_punkte"])
            _alias("ausblick_punkte", "takeaways", d["takeaways"])
    elif st_type == "ST-05":
        d["body"] = _join(d.get("body"), d.get("einleitung"), d.get("angebot_text"))
        if d.get("vertrauenspunkte") and not d.get("credibility_points"):
            d["credibility_points"] = list(d["vertrauenspunkte"])
            _alias("vertrauenspunkte", "credibility_points", d["credibility_points"])
    elif st_type == "ST-09":
        d["body"] = _join(d.get("body"), d.get("einleitung"), d.get("ueberleitung"))
        if d.get("schmerzpunkte") and not d.get("symptoms"):
            # Join titel + beschreibung with a SENTENCE BREAK, never a colon:
            # the client's copy law forbids Doppelpunkte in printed copy
            # ("Wichtig für Copy", 2026-07-16), and this join was printing
            # "Zeitverlust: Fuer jeden Kunden ..." on the status-quo page. A
            # half-filled dict uses whichever side exists, so a literal "None"
            # can never reach the page (mirrors the ST-05 _cred_str guard).
            symptoms = []
            for s in d["schmerzpunkte"]:
                if not isinstance(s, dict):
                    symptoms.append(s)
                    continue
                t, b = s.get("titel"), s.get("beschreibung")
                if _present(t) and _present(b):
                    head = str(t).strip().rstrip(".")
                    symptoms.append(f"{head}. {str(b).strip()}")
                elif _present(t) or _present(b):
                    symptoms.append(str(t if _present(t) else b))
            if symptoms:
                d["symptoms"] = symptoms
    elif st_type == "ST-14":
        d["body"] = _join(d.get("body"), d.get("einleitung"), d.get("abschluss"))
        if d.get("irrtuemer") and not d.get("beliefs"):
            d["beliefs"] = [
                ({"irrglaube": s.get("irrtum"),
                  "realitaet": _join(s.get("realitaet"), s.get("erklaerung")),
                  # carry the per-belief source so the belief's Quelle line renders
                  # (st_14 reads it.get("quelle")); contract audit 2026-07-16
                  **({"quelle": s["quelle"]} if s.get("quelle") else {})}
                 if isinstance(s, dict) else s)
                for s in d["irrtuemer"]
            ]
    elif st_type == "ST-06":
        d["body"] = _join(d.get("body"), d.get("einleitung"))
        if d.get("schritte") and not d.get("steps"):
            d["steps"] = [
                ({"title": s.get("titel"), "body": s.get("beschreibung")}
                 if isinstance(s, dict) else s)
                for s in d["schritte"]
            ]
        if d.get("abschluss") and not d.get("closing_redirect"):
            d["closing_redirect"] = d["abschluss"]
        # the mechanism's closing payoff line: without an `ergebnis` the
        # horizontal_process treatment renders NO result band, so the A3 page's
        # foot sat as a dead band (the 2026-07-13 J2 defect). The abschluss IS
        # the payoff sentence; expose it verbatim as ergebnis so the curved
        # marble result footer renders it (figure parsing stays graceful: no
        # "%"-figure -> a prominent result line, no gauge).
        if d.get("abschluss") and not d.get("ergebnis"):
            d["ergebnis"] = d["abschluss"]
        # a writer that emits the canonical closing_redirect directly (no
        # abschluss) gets the same payoff footer: map it when both ergebnis
        # and abschluss are absent.
        if d.get("closing_redirect") and not d.get("ergebnis") and not d.get("abschluss"):
            d["ergebnis"] = d["closing_redirect"]
    elif st_type == "ST-07B":
        # the thesis (kernaussage) becomes the key_insight -> the st_07b "fill"
        # variant's big dark-panel statement (fills the page + on-dark contrast,
        # fixing the low-contrast lede-on-navy bug). erklaerung + bezug are the
        # supporting body. layout_variant="fill" is set at the page level.
        if d.get("kernaussage") and not d.get("key_insight"):
            d["key_insight"] = d["kernaussage"]
        d["body"] = _join(d.get("body"), d.get("erklaerung"), d.get("bezug"))
    elif st_type == "ST-FAZIT":
        d["body"] = _join(d.get("body"), d.get("zusammenfassung"))
        if d.get("kernbotschaft") and not d.get("these"):
            d["these"] = d["kernbotschaft"]
    elif st_type == "ST-22":
        # The collaboration page's ablauf_text is SEQUENTIAL prose (first step /
        # then / only after ...). Presenting its sentences as the numbered
        # editorial bands lets the fill treatment own the page middle (the
        # thin-copy void), while the einleitung stays the lede. Verbatim
        # sentences, layout-only: nothing is invented. Only applied when the
        # writer supplied no explicit schritte and the split yields >= 2 steps.
        _ablauf = str(d.get("ablauf_text") or "").strip()
        if _ablauf and not d.get("schritte") and not d.get("steps"):
            _sents = _split_sentences_de(_ablauf)
            if len(_sents) >= 2:
                # plain strings: the engine's step normalizer takes string
                # entries as body-only steps ({"title","body"} dicts here would
                # need those exact keys).
                d["steps"] = _sents
                d["body"] = _join(d.get("body"), d.get("einleitung"))
            else:
                d["body"] = _join(d.get("body"), d.get("einleitung"), d.get("ablauf_text"))
        else:
            d["body"] = _join(d.get("body"), d.get("einleitung"), d.get("ablauf_text"))
    elif st_type == "ST-03":
        d["body"] = _join(d.get("body"), d.get("text"))
        if d.get("button_text") and not d.get("cta_text"):
            d["cta_text"] = d["button_text"]
        if d.get("url") and not d.get("cta_url"):
            d["cta_url"] = d["url"]
    elif st_type == "ST-07A":
        if d.get("kurzportrait") and not d.get("kurzportraet"):
            d["kurzportraet"] = d["kurzportrait"]
        if d.get("wendepunkt") and not d.get("ziel"):
            d["ziel"] = d["wendepunkt"]
        # the a4_case_study treatment REQUIRES a headline; this dialect omits
        # ergebnis_headline, so derive it from the result sentence (grounded: it
        # IS the result). Otherwise the page fits no treatment and renders sparse.
        if not d.get("ergebnis_headline") and d.get("ergebnis_text"):
            # no distinct result headline in this dialect: use the result sentence
            # as the headline, and DROP it as the Ergebnis section so the same
            # sentence is not printed twice (the big-numbers rail carries the
            # outcome, the headline states it).
            d["ergebnis_headline"] = d["ergebnis_text"]
            d["ergebnis_text"] = None
        for m in d.get("ergebnis_metrics") or []:
            if isinstance(m, dict) and _present(m.get("wert")) and not _present(m.get("value")):
                m["value"] = m["wert"]

    if st_type == "ST-14":
        # beliefs[].belief/reality/body -> irrglaube/realitaet (the legacy P-5
        # contract). The per-belief `body` elaboration is appended to realitaet as
        # its own paragraph so the writer's text is not silently dropped.
        beliefs = []
        for it in d.get("beliefs") or []:
            if not isinstance(it, dict):
                # a string belief: the legacy P-5 pattern renders it via its own
                # else-branch, so PRESERVE it. Dropping it deleted real content
                # from mixed lists while all-string lists rendered fine.
                beliefs.append(it)
                continue
            b = dict(it)
            if not b.get("irrglaube") and b.get("belief"):
                b["irrglaube"] = b["belief"]
            if not b.get("realitaet"):
                reality = (b.get("reality") or "").strip()
                body = (b.get("body") or "").strip()
                b["realitaet"] = (reality + ("\n\n" + body if body else "")).strip() or None
            beliefs.append(b)
        if beliefs:
            d["beliefs"] = beliefs

    if st_type == "ST-05":
        # credibility_points arrive as {label, value} dicts: those ARE the stats
        # (the big credibility figures). Expose them as canonical `stats`, and
        # keep credibility_points as display strings for the string-list readers.
        cps = d.get("credibility_points") or []
        if cps and any(isinstance(c, dict) for c in cps):
            def _cred_str(c: dict) -> str:
                # "label: value", but NEVER leak a literal "None" when one side is
                # null (an f-string of c.get(...) printed "Projekte: None").
                # Presence tests, not truthiness, so a real 0 value survives.
                lbl, val = c.get("label"), c.get("value")
                if _present(lbl) and _present(val):
                    return f"{lbl}: {val}"
                return str(lbl if _present(lbl) else val)
            if not d.get("stats"):
                # no stats yet: dict entries BECOME the stats rail (the stringified
                # duplicate is dropped, it double-printed and spilled the page);
                # any non-dict (string) entries can't be stats, so they STAY in
                # credibility_points as display text (not silently dropped).
                d["stats"] = [
                    {"value": str(c["value"]) if _present(c.get("value")) else "",
                     "label": str(c["label"]) if _present(c.get("label")) else ""}
                    for c in cps if isinstance(c, dict)
                ]
                d["credibility_points"] = [c for c in cps if not isinstance(c, dict)]
            else:
                # stats already present: keep EVERY point as display text (dicts as
                # "label: value", strings passed through) so nothing is deleted.
                d["credibility_points"] = [
                    (_cred_str(c) if isinstance(c, dict) else c)
                    for c in cps
                    if (not isinstance(c, dict))
                    or _present(c.get("label")) or _present(c.get("value"))
                ]

    if st_type == "ST-FAZIT":
        # the summary thesis: writer `bold_thesis` -> canonical `these`.
        if not d.get("these") and d.get("bold_thesis"):
            d["these"] = d["bold_thesis"]

    # steps (any ST): writer emits {number, title, description, duration};
    # canonical is {n, title, body, dauer}. Without this the step BODIES are
    # silently dropped and the process/timeline pages render as bare numbered
    # circles in an empty field (the 2026-07-04 "shitty infographics" defect).
    steps = d.get("steps")
    if isinstance(steps, list) and steps:
        norm_steps = []
        for s in steps:
            if not isinstance(s, dict):
                norm_steps.append(s)
                continue
            ns = dict(s)
            if not ns.get("body") and ns.get("description"):
                ns["body"] = ns["description"]
            if not ns.get("dauer") and ns.get("duration"):
                ns["dauer"] = ns["duration"]
            if not ns.get("n") and ns.get("number"):
                ns["n"] = ns["number"]
            norm_steps.append(ns)
        d["steps"] = norm_steps

    if st_type == "ST-06" and not d.get("body") and d.get("mechanism_description"):
        # the mechanism page's intro prose: writer `mechanism_description`.
        d["body"] = d["mechanism_description"]

    # ---- writer-prompt-v4 VISUAL DATA contract (any ST) ---------------------
    # The v4 writer surfaces the page's real figures into structured fields
    # (kennzahlen / vorher_nachher / anteil / kostenrechnung / pullquote+
    # pullquote_attribution / bildwunsch). Map each onto the renderer contract
    # that consumes it (canonical `stats`, the `data.viz` preset specs that
    # viz.jinja dispatches, the pullquote dict treatment_engine._quote_from
    # reads). GROUNDED: every displayed value is copied VERBATIM from the
    # writer's field. The only derived number is the donut's arc angle, a
    # drawing parameter (the printed figure stays the writer's exact string).
    # `bildwunsch` is left untouched on the data (an image INTENT; consumed by
    # the asset/slot layer when client assets are wired).

    # A shared helper set (synthesize_visuals owns the %-figure -> device
    # routing rule so it exists ONCE): donut_spec returns a ring spec only for
    # a drawable 0..100 share (a growth "300 %" is NOT a proportion and comes
    # back None -> route it to the stats rail verbatim instead).

    # digit-keys of figures already carried by this page's viz specs, so the
    # same percentage never renders as two identical rings across fields
    # (kennzahlen + anteil carrying the same figure was double-ringing).
    # Keys come from the shared synthesize_visuals.digit_key so '2,5' and '25'
    # stay distinct everywhere the one-figure-one-device rule is enforced.
    def _viz_keys() -> set:
        keys = set()
        for spec in d.get("viz") or []:
            if not isinstance(spec, dict):
                continue
            for v in (spec.get("figure"),
                      (spec.get("from") or {}).get("value") if isinstance(spec.get("from"), dict) else None,
                      (spec.get("to") or {}).get("value") if isinstance(spec.get("to"), dict) else None):
                if v:
                    keys.add(synthesize_visuals.digit_key(v))
        keys.discard("")
        return keys

    # digit-keys of figures already on the canonical stats rail.
    def _stat_keys() -> set:
        keys = set()
        for s in d.get("stats") or []:
            if isinstance(s, dict):
                keys.add(synthesize_visuals.digit_key(s.get("value")))
        keys.discard("")
        return keys

    # kennzahlen [{wert,label,quelle?}] -> visual devices, split by SHAPE:
    # drawable %-wert -> DONUT ring; anything else -> the canonical stats rail
    # [{value,label,sub?}]. A figure goes to exactly ONE device (never both).
    kz = d.get("kennzahlen")
    if isinstance(kz, list) and kz:
        kz_stats, kz_donuts = [], []
        for k in kz:
            if not (isinstance(k, dict) and _present(k.get("wert"))):
                continue
            wert = str(k["wert"]).strip()
            label = str(k.get("label") or "").strip()
            quelle = str(k.get("quelle") or "").strip() or None
            ring = (synthesize_visuals.donut_spec(wert, label or None, quelle)
                    if "%" in wert or re.search(r"\bprozent\b", wert, re.IGNORECASE)
                    else None)
            if ring is not None:
                kz_donuts.append(ring)
            else:
                s = {"value": wert, "label": label}
                if quelle:
                    s["sub"] = quelle
                kz_stats.append(s)
        if kz_donuts:
            # each ACCEPTED ring claims its digit-key immediately, so two
            # kennzahlen carrying the same figure never double-ring. G12: the
            # dedup must ALSO exclude figures already on the stats rail (a
            # writer-provided stat and a kennzahlen with the same figure must
            # not render as BOTH a ring and a stat).
            existing = _viz_keys() | _stat_keys()
            fresh = []
            for r in kz_donuts:
                if len(fresh) >= 3:
                    # cap like the synthesizer: a proof band, not a donut wall.
                    break
                k = synthesize_visuals.digit_key(r["figure"])
                if k and k in existing:
                    continue
                if k:
                    existing.add(k)
                fresh.append(r)
            if fresh:
                d["viz"] = (d.get("viz") or []) + fresh
        if kz_stats:
            kz_stats = kz_stats[:4]
            seen = set()
            for s in kz_stats:
                k = synthesize_visuals.digit_key(s["value"])
                if k:
                    seen.add(k)
            d["stats"] = kz_stats + [
                s for s in (d.get("stats") or [])
                if isinstance(s, dict)
                and synthesize_visuals.digit_key(s.get("value")) not in seen
            ]

    # vorher_nachher {von,nach,einheit?,label?} -> a transform_arrow viz spec
    # (the A->B card handles prose values like "wenige Wochen" verbatim).
    # Skipped only when BOTH figures already sit on another device (ring or
    # stat); a single fresh number still earns the arrow.
    vn = d.get("vorher_nachher")
    if isinstance(vn, dict) and _present(vn.get("von")) and _present(vn.get("nach")):
        unit = str(vn.get("einheit") or "").strip() or None
        existing = _viz_keys() | _stat_keys()
        # unit-aware keys: a bare-number side ("3") is classified by the
        # einheit so it collides with the same figure carried elsewhere with
        # its unit spelled out; a side with its own unit ("1,5 Jahre") keeps
        # it (digit_key reads the first word after the last digit).
        von_k = synthesize_visuals.digit_key(
            f"{vn['von']} {unit}" if unit else vn["von"])
        nach_k = synthesize_visuals.digit_key(
            f"{vn['nach']} {unit}" if unit else vn["nach"])
        if not (von_k and nach_k and von_k in existing and nach_k in existing):
            d["viz"] = (d.get("viz") or []) + [{
                "preset": "transform_arrow",
                "title": (str(vn.get("label") or "").strip() or None),
                "from": {"value": str(vn["von"]).strip(), "label": unit or "vorher"},
                "to": {"value": str(vn["nach"]).strip(), "label": unit or "nachher"},
            }]

    # anteil {prozent,label} -> a donut via the shared helper (figure verbatim,
    # % symbol ensured, arc = drawing parameter; >100 or numberless -> a stat).
    at = d.get("anteil")
    if isinstance(at, dict) and _present(at.get("prozent")):
        figure = str(at["prozent"]).strip()
        label = str(at.get("label") or "").strip() or None
        ring = synthesize_visuals.donut_spec(figure, label)
        if ring is not None:
            existing = _viz_keys()
            if synthesize_visuals.digit_key(ring["figure"]) not in existing:
                d["viz"] = (d.get("viz") or []) + [ring]
        else:
            # stat fallback (>100 % or numberless): only when no existing stat
            # already carries the same figure. The anteil field is a percent
            # BY CONTRACT, so a bare-number figure is percent-classed for the
            # unit-aware key check even when the marker is not spelled out.
            fig_k = synthesize_visuals.digit_key(
                figure if ("%" in figure
                           or re.search(r"\bprozent\b", figure, re.IGNORECASE))
                else f"{figure} %")
            if not (fig_k and fig_k in _stat_keys()):
                s = {"value": figure, "label": label or ""}
                d["stats"] = (d.get("stats") or []) + [s]

    # kostenrechnung {schritte:[{label,wert}],summe,zeitraum} -> a stat_strip of
    # the worked steps ending on the sum (all values verbatim from the writer).
    kr = d.get("kostenrechnung")
    if isinstance(kr, dict) and _present(kr.get("summe")) and isinstance(kr.get("schritte"), list):
        items = [{"value": str(s["wert"]).strip(),
                  "label": str(s.get("label") or "").strip()}
                 for s in kr["schritte"] if isinstance(s, dict) and _present(s.get("wert"))]
        summe_item = {"value": str(kr["summe"]).strip(),
                      "label": str(kr.get("zeitraum") or "Summe").strip()}
        # one-figure-one-device: drop STEP items already ringed/statted
        # elsewhere on the page; the summe itself is exempt from the filter
        # (a calculation must never print without its total). When the
        # summe's key is already claimed elsewhere, the ENTIRE strip is
        # dropped instead of printing a totalless remainder. A strip below
        # two items is no longer a worked calculation.
        existing = _viz_keys() | _stat_keys()
        summe_k = synthesize_visuals.digit_key(summe_item["value"])
        if not (summe_k and summe_k in existing):
            fresh_items = []
            for it in items:
                k = synthesize_visuals.digit_key(it["value"])
                if k and k in existing:
                    continue
                fresh_items.append(it)
            fresh_items.append(summe_item)
            if len(fresh_items) > 1:
                d["viz"] = (d.get("viz") or []) + [{"preset": "stat_strip", "items": fresh_items}]

    # pullquote (string) + pullquote_attribution -> the {text, attribution}
    # dict shape treatment_engine._quote_from already consumes.
    pq = d.get("pullquote")
    if isinstance(pq, str) and pq.strip():
        d["pullquote"] = {
            "text": pq.strip(),
            "attribution": (str(d.get("pullquote_attribution") or "").strip() or None),
        }

    # ---- THE ROLE -> DEVICE SELECTOR (layer B, docs/ROLE-DEVICE-CONTRACT.md) --
    # Everything above this line is the LEGACY per-FIELD reflex (has "%" -> ring;
    # vorher_nachher -> arrow; kostenrechnung -> strip). It can only ever reach 4
    # of the renderer's 16 devices, which is why every page read the same
    # (docs/DEVICE-VOCABULARY-GAP-2026-07-16.md). The writer-v5 shapes below name
    # the data's RHETORICAL ROLE, so the device follows from what the figure
    # MEANS instead of which key it arrived under.
    #
    # Precedence: an explicit role shape WINS. `kennzahlen` stays the last-resort
    # fallback, so a v4 payload renders exactly as it did before (no regression).
    # Grounded: every figure/label/source is copied verbatim; a shape that is
    # absent or malformed simply yields no device.
    _roles = _role_devices(d, _viz_keys() | _stat_keys())
    if _roles:
        d["viz"] = (d.get("viz") or []) + _roles

    # G15: log keys the renderer has no reader for, so schema drift surfaces.
    _KNOWN_CANONICAL = {
        "title", "subtitle", "body", "takeaways", "zielgruppe", "kicker",
        "audience", "stats", "viz", "diagram", "credibility_points",
        "symptoms", "beliefs", "steps", "headline", "titel", "untertitel",
        "einleitung", "abschluss", "angebot_text", "ausblick_punkte",
        "vertrauenspunkte", "irrtuemer", "schmerzpunkte", "schritte",
        "kennzahlen", "fakten", "verlauf", "rechnung", "kategorien",
        "zusammensetzung", "entitaeten", "vorher_nachher", "anteil",
        "kostenrechnung", "bildwunsch", "kunde", "author", "ergebnis_metrics",
        "ergebnis_text", "ausgangsproblem", "wendepunkt", "loesung",
        "kurzportrait", "pullquote", "pullquote_attribution", "partners",
        "proof_stats", "teaser_items", "kicker_pills", "title_accent",
        "compare", "these", "kernbotschaft", "kosten_des_nichtstuns",
        "zusammenfassung", "faqs", "frage", "antwort", "cta_url", "cta_text",
        "button_text", "url", "ablauf_text", "intro", "erklaerung", "bezug",
        "kernaussage", "quelle", "prozent", "wert", "label", "von", "nach",
    }
    unmapped = sorted(
        k for k in d if k not in _KNOWN_CANONICAL
    )
    if unmapped:
        log.warning("unmapped keys on %s: %s", st_type, ", ".join(unmapped))

    # last: restore ASCII-transliterated umlauts in the writer's copy (values
    # only; keys and URLs stay byte-exact).
    return _fix_umlauts_deep(d)


# The closed icon vocabulary (docs/ROLE-DEVICE-CONTRACT.md). The writer picks a
# SEMANTIC key; the renderer owns the drawing. An unknown key is dropped rather
# than passed through, so a typo can never reach the page as a broken glyph.
_ICON_KEYS = frozenset((
    "zeit", "geld", "person", "team", "dokument", "prozess", "wachstum",
    "warnung", "ziel", "standort", "kalender", "suche", "chart", "check",
    "welt", "schule", "schutz", "idee",
))


def _rows(v, keys=()):
    """A list of dicts that carry at least one of `keys` non-empty; [] otherwise.
    The single shape-guard every role reader uses, so a half-filled writer row
    can never emit a device with holes in it."""
    if not isinstance(v, list):
        return []
    out = []
    for r in v:
        if not isinstance(r, dict):
            continue
        if not keys or any(str(r.get(k) or "").strip() for k in keys):
            out.append(r)
    return out


def _txt(v):
    s = str(v or "").strip()
    return s or None


def _role_devices(d: dict, claimed: set) -> list:
    """Map the writer's ROLE shapes to viz presets. Returns [] when the page
    carries none (every shape is optional).

    `claimed` holds the digit-keys already drawn by the legacy pass, so the
    one-figure-one-device rule still binds across BOTH passes: a figure already
    ringed cannot reappear inside a role device.
    """
    out = []

    # ROLE: sourced market facts -> a ROW of icon-stat cards (the workhorse of
    # Richard's decks; they never float a lone number).
    facts = []
    for f in _rows(d.get("fakten"), ("figur", "label")):
        fig = _txt(f.get("figur"))
        if fig and synthesize_visuals.digit_key(fig) in claimed:
            continue
        icon = str(f.get("icon") or "").strip().lower()
        facts.append({
            "figur": fig,
            "label": _txt(f.get("label")),
            "text": _txt(f.get("text")),
            "quelle": _txt(f.get("quelle")),
            "icon": icon if icon in _ICON_KEYS else None,
        })
    if facts:
        out.append({"preset": "icon_stat_row", "items": facts})

    # ROLE: a development over time -> column chart (values above the bars).
    # G11: figures already drawn elsewhere are filtered out so one-figure-
    # one-device binds across EVERY role, not just `fakten`.
    vl = d.get("verlauf")
    if isinstance(vl, dict):
        pts = [{"label": _txt(p.get("label")), "wert": _txt(p.get("wert"))}
               for p in _rows(vl.get("punkte"), ("wert",))]
        pts = [
            p for p in pts
            if not (p.get("wert") and synthesize_visuals.digit_key(p["wert"]) in claimed)
        ]
        if len(pts) >= 2:
            out.append({
                "preset": "column_chart", "titel": _txt(vl.get("titel")),
                "einheit": _txt(vl.get("einheit")), "quelle": _txt(vl.get("quelle")),
                "punkte": pts, "hervorheben": _txt(vl.get("hervorheben")),
            })

    # ROLE: a derivation -> formula ladder ending in a dark result box.
    rc = d.get("rechnung")
    if isinstance(rc, dict):
        steps = [{"wert": _txt(s.get("wert")), "einheit": _txt(s.get("einheit")),
                  "label": _txt(s.get("label"))}
                 for s in _rows(rc.get("schritte"), ("wert",))]
        steps = [
            s for s in steps
            if not (s.get("wert") and synthesize_visuals.digit_key(s["wert"]) in claimed)
        ]
        erg = rc.get("ergebnis") if isinstance(rc.get("ergebnis"), dict) else {}
        result_value = _txt(erg.get("wert"))
        result_claimed = bool(
            result_value and synthesize_visuals.digit_key(result_value) in claimed
        )
        if steps and result_value and not result_claimed:
            out.append({
                "preset": "formula_ladder", "titel": _txt(rc.get("titel")),
                "schritte": steps,
                "ergebnis": {"wert": result_value, "label": _txt(erg.get("label"))},
            })

    # ROLE: before/after per category -> grouped bars + legend.
    kt = d.get("kategorien")
    if isinstance(kt, dict):
        rows = [{"label": _txt(r.get("label")), "vorher": _txt(r.get("vorher")),
                 "nachher": _txt(r.get("nachher"))}
                for r in _rows(kt.get("zeilen"), ("vorher", "nachher"))]
        rows = [
            r for r in rows
            if not (
                (r.get("vorher") and synthesize_visuals.digit_key(r["vorher"]) in claimed)
                or (r.get("nachher") and synthesize_visuals.digit_key(r["nachher"]) in claimed)
            )
        ]
        if rows:
            out.append({
                "preset": "grouped_bars", "titel": _txt(kt.get("titel")),
                "vorher_label": _txt(kt.get("vorher_label")),
                "nachher_label": _txt(kt.get("nachher_label")),
                "einheit": _txt(kt.get("einheit")), "zeilen": rows,
            })

    # ROLE: the split of a whole (optionally before vs after) -> 100% stacked bar.
    zs = d.get("zusammensetzung")
    if isinstance(zs, dict):
        parts = [{"prozent": _txt(p.get("prozent")), "label": _txt(p.get("label"))}
                 for p in _rows(zs.get("teile"), ("prozent",))]
        parts = [
            p for p in parts
            if not (p.get("prozent") and synthesize_visuals.digit_key(p["prozent"]) in claimed)
        ]
        cmp_parts = [{"prozent": _txt(p.get("prozent")), "label": _txt(p.get("label"))}
                     for p in _rows(zs.get("vergleich_teile"), ("prozent",))]
        cmp_parts = [
            p for p in cmp_parts
            if not (p.get("prozent") and synthesize_visuals.digit_key(p["prozent"]) in claimed)
        ]
        if parts:
            out.append({
                "preset": "stacked_bar_100", "titel": _txt(zs.get("titel")),
                "quelle": _txt(zs.get("quelle")), "teile": parts,
                "vergleich_teile": cmp_parts or None,
                "teile_label": _txt(zs.get("teile_label")),
                "vergleich_label": _txt(zs.get("vergleich_label")),
            })

    # ROLE: several actors on one metric -> entity bars (a mark, never an emoji).
    en = d.get("entitaeten")
    if isinstance(en, dict):
        items = [{"name": _txt(e.get("name")), "wert": _txt(e.get("wert")),
                  "marke": _txt(e.get("marke"))}
                 for e in _rows(en.get("eintraege"), ("name", "wert"))]
        items = [
            i for i in items
            if not (i.get("wert") and synthesize_visuals.digit_key(i["wert"]) in claimed)
        ]
        if items:
            out.append({
                "preset": "entity_bars", "titel": _txt(en.get("titel")),
                "einheit": _txt(en.get("einheit")), "quelle": _txt(en.get("quelle")),
                "eintraege": items,
            })

    return out


def envelope_to_render_request(envelope: dict) -> RenderRequest:
    """Adapt the n8n {payload, images, brand_tokens} envelope to a RenderRequest."""
    payload = envelope["payload"]
    images = envelope.get("images", {}) or {}
    bt = envelope.get("brand_tokens", {}) or {}
    meta = payload.get("meta", {}) or {}

    company = bt.get("company_name_short") or (meta.get("client_slug", "client") or "client").title()
    website = bt.get("qr_target_url") or bt.get("company_url_display") or "https://example.com"
    if "://" not in website:
        website = "https://" + website

    client = ClientInput(
        name=bt.get("founder_full_name") or company,
        company=company,
        website_url=website,
        brand_hex_dark=(
            bt.get("brand_neutral_dark") or bt.get("brand_primary")
            or _fallbacks.FALLBACK_BRAND_HEX_DARK
        ),
        brand_hex_light=bt.get("brand_neutral_light") or _fallbacks.FALLBACK_BRAND_HEX_LIGHT,
        brand_hex_accent=bt.get("brand_accent") or _fallbacks.FALLBACK_BRAND_HEX_ACCENT,
        logo_url=bt.get("logo_dark_url") or bt.get("logo_light_url"),
        brand_profile=BrandProfile(
            brand_primary=bt.get("brand_primary"),
            brand_accent=bt.get("brand_accent"),
            brand_neutral_dark=bt.get("brand_neutral_dark"),
            brand_neutral_mid=bt.get("brand_neutral_mid"),
            brand_neutral_light=bt.get("brand_neutral_light"),
            font_head=bt.get("font_heading"),
            font_body=bt.get("font_body"),
        ),
    )

    # Resolve the LLM key HERE: per-page normalization below runs the visual
    # synthesizer, which executes before _build resolves any keys, so without
    # this the synthesize LLM path never ran (env-only lookup came up empty
    # while the key sat in the preprocessor .env).
    openrouter_key = _env_or_dotenv("OPENROUTER_API_KEY")

    # Build pages, assigning each case study its ordinal fallstudie_number (the
    # dialect omits it; the a4_case_study eyebrow + ghost numeral read it) when the
    # writer did not supply one.
    pages = []
    _case_no = 0
    for p in payload.get("pages", []):
        pd = dict(p.get("data") or {})
        st = p.get("type", "")
        page_extra = {}
        if st == "ST-07A":
            _case_no += 1
            pd.setdefault("fallstudie_number", _case_no)
        if st == "ST-07B":
            # G23: single source of truth for the ST-07B variant. Carry ONLY an
            # explicit writer hint here; the "fill" DEFAULT lives in plan_layout
            # FILL_DEFAULT_TYPES. The old `or "fill"` made build_live a second
            # authority that always injected fill, so an explicit different
            # variant could never win.
            if p.get("layout_variant"):
                page_extra["layout_variant"] = p["layout_variant"]
        norm = _normalize_page_data(st, pd)
        # Synthesize the visual layer: grounded stat callouts / before-after
        # devices from the page's own copy, so prose-only pages get the big-number
        # devices the rich treatments need (only where the page carries no visual
        # data of its own; every figure is verbatim-grounded, see synthesize_visuals).
        norm = synthesize_visuals.synthesize_page_visuals(norm, api_key=openrouter_key)
        # FOUNDER IDENTITY: the writer dialect never emits `author`, so surface the
        # envelope's own founder (brand_tokens.founder_full_name, verbatim) on the
        # pages whose pattern reads it: ST-05 (image-led About hero via
        # founder_identity()), ST-01 (the cover byline), and ST-FAZIT (the signed
        # close). Without this the resolved founder portrait sat unused and the
        # byline/hero never fired. (contract audit 2026-07-16 widened ST-05 -> +01/+FAZIT)
        if (st in ("ST-05", "ST-01", "ST-FAZIT") and not norm.get("author")
                and (bt.get("founder_full_name") or "").strip()):
            # role: ONLY the founder's actual role. A company name is not a
            # role; when the envelope carries none, omit the key and let the
            # template hide the role line.
            norm["author"] = {"name": str(bt["founder_full_name"]).strip()}
            _role = str(bt.get("founder_role") or "").strip()
            if _role:
                norm["author"]["role"] = _role
        # COVER stat rail: the ST-01 pattern reads `proof_stats`, but kennzahlen
        # normalize to `stats` (and ST-01 bypasses the treatment engine, the only
        # other reader of `stats`). Without this the cover's vertical stat rail
        # renders empty on every cover carrying figures. (contract audit 2026-07-16)
        if st == "ST-01" and norm.get("stats") and not norm.get("proof_stats"):
            norm["proof_stats"] = norm["stats"]
        pages.append(ReportPage(**{**p, **page_extra, "data": norm}))

    # page_count_target must be one of the supported sheet counts; snap an
    # off-grid value (e.g. 21) to the nearest so validation does not reject a real
    # writer payload. Coerce first: writers send it as a string ("20"); a value
    # that is not a number at all is ignored (default snapping applies).
    meta = dict(meta)
    # Identity: the n8n envelope computes clientSlug/recordId but never merges
    # them into payload.meta, so a bare meta fails ReportMeta validation.
    # Derive deterministically (same rule as the envelope node + adapter_v3):
    # client_slug from brand_tokens.company_name_short, report_id from the
    # envelope's record id. Explicit payload values always win.
    if not meta.get("client_slug"):
        import re

        name = bt.get("company_name_short") or ""
        meta["client_slug"] = (
            re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", str(name).lower())).strip("-")
            or "client"
        )
    if not meta.get("report_id"):
        meta["report_id"] = str(
            envelope.get("record_id") or f"report-{meta['client_slug']}"
        )
    _pct = meta.get("page_count_target")
    try:
        _pct = int(str(_pct).strip())
    except (TypeError, ValueError):
        _pct = None
    if _pct in (16, 20, 24, 28):
        meta["page_count_target"] = _pct
    else:
        snapped = min((16, 20, 24, 28), key=lambda v: abs(v - (_pct or 20)))
        # G20: the snap is surfaced, not silent - a writer asking for 21 pages
        # is told it was snapped to 20.
        if _pct is not None and _pct != snapped:
            log.warning(
                "page_count_target %s snapped to %s (supported: 16, 20, 24, 28)",
                _pct, snapped,
            )
        meta["page_count_target"] = snapped

    report_json = ReportJson(meta=ReportMeta(**meta), pages=pages)

    # flat images {slot: url} -> ImageManifestItem list, resolving page_slot via st_type
    st_to_slot: dict[str, int] = {}
    for pg in pages:
        st_to_slot.setdefault(pg.type, pg.slot)
    items = []
    for slot_name, url in images.items():
        if not url:
            continue
        st, itype = SLOT_TO_ST.get(slot_name, (None, "image"))
        page_slot = st_to_slot.get(st) if st else None
        if page_slot is None:
            # a provided image the deck cannot place is a real loss: say so
            # instead of dropping it silently.
            reason = ("unmapped slot" if st is None
                      else f"no {st} page in this payload")
            print(f"[build_live] image dropped: {slot_name!r} ({reason})",
                  file=sys.stderr)
            continue
        items.append(ImageManifestItem(
            id=slot_name, page_slot=page_slot, page_st_type=st,
            image_type=itype, url=url, status="provided",
        ))
    image_manifest = ImageManifest(images=items)

    return RenderRequest(
        record_id=meta.get("report_id", "DMC-RENDER"),
        client=client,
        report_json=report_json,
        image_manifest=image_manifest,
    )


def _build_social_manifest(ig_dir):
    """Load the classified social asset manifest for a client's IG pool.

    G3: the social vocabulary (testimonials, breathers, case-study phones,
    profile grid) must run on the LIVE path, not only the fixture. The
    classified manifest is the Phase-2 interceptor's output, persisted as
    ``asset_manifest.json`` inside ``<client>/ig/`` (the fixture builder reads
    the identical shape from ``fixtures/apex/asset_manifest.json``). When no
    manifest is present the client simply has no classified pool yet — return
    None (the social planner stays inert), never a fabricated manifest.
    """
    from models_social import AssetManifest

    manifest_path = Path(ig_dir) / "asset_manifest.json"
    if not manifest_path.is_file():
        return None
    try:
        return AssetManifest(**_load_json(manifest_path))
    except Exception as error:  # noqa: BLE001 - a malformed manifest is a
        # loud warning, not a reason to fabricate social placements.
        print(f"[build_live] social manifest unreadable: {type(error).__name__}: {error}")
        return None


def _load_json(path: Path) -> dict:
    import json as _json

    return _json.loads(Path(path).read_text(encoding="utf-8"))


async def _build(request: RenderRequest, output_dir: Path) -> dict:
    # Lightweight config shim (avoids the preprocessor's pydantic_settings dep,
    # which is not in the renderer venv). Keys unset -> offline.
    from types import SimpleNamespace
    _base = Path(tempfile.gettempdir()) / "dmc_live_cfg"
    # client assets (founder portrait, product shots, logos): prefer the DURABLE
    # repo-local door, fall back to the legacy tempdir door. Overridable via
    # DMC_CLIENT_ASSETS_DIR (the container mounts its own path). A tempdir door
    # was the only door before 2026-07-13 and silently lost files on reboot.
    _repo_assets = Path(__file__).resolve().parent.parent / "client_assets"
    _assets_dir = os.environ.get("DMC_CLIENT_ASSETS_DIR") or (
        str(_repo_assets) if _repo_assets.is_dir() else str(_base / "client_assets"))
    cfg = SimpleNamespace(
        openrouter_prompt_model="anthropic/claude-sonnet-4.6",
        openrouter_restructure_model="anthropic/claude-sonnet-4.6",  # capable + cheaper than opus for copy-fit
        restructure_cache_dir=str(_base / "restructure_cache"),
        fal_image_model="fal-ai/nano-banana-pro",
        fal_image_resolution="2K",
        max_generations_per_report=12,
        asset_cache_dir=str(_base / "asset_cache"),
        client_assets_dir=_assets_dir,
    )
    # Owner-gated keys via the module-level _env_or_dotenv (also used by
    # envelope_to_render_request for the synthesizer's LLM path).
    openrouter_key = _env_or_dotenv("OPENROUTER_API_KEY")
    fal_key = _env_or_dotenv("FAL_KEY")

    brand_tokens, errors, warnings = validate_and_resolve_brand_tokens(request)
    if brand_tokens is None:
        raise RuntimeError(f"Stage 1 failed: {[e.model_dump() for e in errors]}")

    font_config = resolve_fonts(request.client.brand_profile)
    brand_tokens = brand_tokens.model_copy(update={
        "font_heading": font_config.font_heading_name,
        "font_body": font_config.font_body_name,
    })
    axes, axes_provenance = resolve_axes(
        brand_profile=request.client.brand_profile,
        brand_primary=brand_tokens.brand_primary,
        brand_accent=brand_tokens.brand_accent,
    )
    copy_warnings = validate_copy(request.report_json.pages) + validate_copyfit(request.report_json.pages)

    cover_validation = None
    for page in request.report_json.pages:
        if page.slot == 1 or page.type == "ST-01":
            if isinstance(page.data, dict):
                cover_validation = validate_cover(page.data, awareness_level=request.report_json.meta.awareness_level)
            break

    client_dir = client_assets_dir(request.report_json.meta.client_slug, base=Path(cfg.client_assets_dir))
    drive_listing = list_client_assets(client_dir)

    # writer-v4 `bildwunsch` -> REAL product imagery. A page that asked for a
    # device/product visual (art geraet_mockup_* / produkt / proof_galerie)
    # gets the next unused `product-*` file from the client-assets folder as a
    # file:// URI on data["produkt_bild"] (the treatments' device bands render
    # it). The client's product shots arrive PRE-FRAMED (laptop/phone/tablet
    # renders), so no compositor is needed. Deterministic round-robin in page
    # order; graceful: no bildwunsch / no files -> nothing attached, and a page
    # never shows an image that does not exist on disk.
    _product_files = [
        client_dir / f for f in drive_listing
        if f.lower().startswith("product-") or f.lower().startswith("produkt-")
    ]
    _product_i = 0

    def _claim_next_product() -> str | None:
        """The next EXISTING product file as a file URI. The shared cursor
        advances past every candidate it inspects, so a listed-but-missing
        file is skipped (the file is skipped, never the page). Walks at most
        one full cycle (modulo, so exhausted sets restart: a tasteful repeat
        beats a void) and returns None when no listed file exists on disk.
        The ONE claim rule for the hero loop, the bildwunsch router and the
        completion sweep, which previously diverged on bound/modulo."""
        nonlocal _product_i
        for _ in range(len(_product_files)):
            f = _product_files[_product_i % len(_product_files)]
            _product_i += 1
            if f.is_file():
                return f.resolve().as_uri()
        return None

    # HERO placement first (owner-confirmed): the MECHANISM page (ST-06) leads
    # with the product mockup in Richard's reference anatomy (mein_werkzeugkoffer
    # p16), and by folder convention product-1 is the hero-grade shot - so the
    # mechanism page claims the FIRST product file before the bildwunsch router
    # assigns the rest in page order. TAIL-GATED, mirroring the stylist's A3
    # rule (treatment_stylist a3_tail_start = 3*len(pages)//4): only a
    # final-quarter ST-06 is promoted to the product-led hero there; a demoted
    # mid-deck ST-06 renders layouts that never paint the product, so claiming
    # the hero shot for it would bury product-1 in an invisible slot.
    _pages = request.report_json.pages
    for _idx, page in enumerate(_pages):
        if page.type != "ST-06" or _idx < (3 * len(_pages)) // 4:
            continue
        d = page.data if isinstance(page.data, dict) else None
        if not d or d.get("produkt_bild"):
            continue
        uri = _claim_next_product()
        if uri:
            d["produkt_bild"] = uri
    _PRODUCT_ARTS = ("geraet_mockup", "produkt", "proof_galerie")
    for page in request.report_json.pages:
        d = page.data if isinstance(page.data, dict) else None
        if not d or d.get("produkt_bild"):
            continue
        bw = d.get("bildwunsch")
        art = str((bw or {}).get("art") or "").lower() if isinstance(bw, dict) else ""
        if not any(art.startswith(p) for p in _PRODUCT_ARTS):
            continue
        uri = _claim_next_product()
        if uri:
            d["produkt_bild"] = uri

    # DETERMINISTIC DEVICE COMPLETION (owner directive 2026-07-14): a case-study
    # or collaboration page whose device band would otherwise sit EMPTY (no
    # routed product, no drawable viz) claims the next product file in page
    # order - the client's mockup set exists precisely to vary the proof across
    # pages, and an empty left foot is never acceptable. Unclaimed files go
    # first; when all are claimed the cycle restarts (a tasteful repeat beats a
    # void). The bildwunsch router above still has priority: this sweep only
    # fills what the writer left unfilled.
    _DEVICE_COMPLETE_TYPES = ("ST-07A", "ST-22")
    if _product_files:
        for page in request.report_json.pages:
            if page.type not in _DEVICE_COMPLETE_TYPES:
                continue
            d = page.data if isinstance(page.data, dict) else None
            if not d or d.get("produkt_bild") or d.get("viz"):
                continue
            # PAINTABILITY: an ST-22 with 4+ (post-split) steps routes to
            # a4_vertical_timeline (min_counts steps >= 4 in the treatment
            # catalog), which hosts no image band; a product claimed here
            # would never paint and the file is better spent on a page that
            # can show it. Coupled to the timeline's min_counts contract.
            _steps = d.get("steps")
            if (page.type == "ST-22"
                    and isinstance(_steps, list) and len(_steps) >= 4):
                continue
            uri = _claim_next_product()
            if uri:
                d["produkt_bild"] = uri

    # ORDER MATTERS: structure_content SNAPSHOTS each page's data into the typed
    # structured view, and assemble_package PREFERS that snapshot over the live
    # page dict - a key attached after this line never reaches the package
    # (produkt_bild silently vanished until the attach moved above it).
    structured = structure_content(request.report_json.pages)

    page_slots: dict[int, list] = {}
    case_counter = 0
    for page in request.report_json.pages:
        case_index = None
        if page.type == "ST-07A":
            case_counter += 1
            fn = page.data.get("fallstudie_number") if isinstance(page.data, dict) else None
            case_index = int(fn) if (isinstance(fn, int) or (isinstance(fn, str) and str(fn).isdigit())) else case_counter
        page_slots[page.slot] = resolve_slots(page.type, drive_listing, case_index=case_index)

    # generous timeout: this ONE client is injected into every stage, and its
    # DEFAULT (5s) silently killed both the LLM prompt-builder and every fal
    # image generation (ReadTimeout) - the stage's own 180s default only
    # applies when the stage creates its own client. Image jobs take 10-90s.
    # GENERATION GATE: never pay for an asset no consumer can paint.
    # - cover_hero: the founder-first cover uses the generated scene ONLY as
    #   the founder-less fallback; with a founder file on disk it can never
    #   render, so it is not generated.
    # - atmospheric_gradient: no live consumer (the ground + closer both take
    #   background_texture; the gradient was only ever its second-choice
    #   fallback, and both generate in the same run). Resolvers stay graceful.
    _skip_slots = {"atmospheric_gradient"}
    # the founder gate mirrors resolve_slots' truth exactly: the cover's
    # founder slot (drive_key "founder") resolves only on an exact
    # normalized-name match, so a near-miss file must NOT suppress the
    # generated cover scene (a prefix test skipped it while the slot stayed
    # unresolved and the cover rendered with neither).
    if any(normalize_name(f) == "founder" for f in drive_listing):
        _skip_slots.add("cover_hero")

    async with httpx.AsyncClient(timeout=httpx.Timeout(240.0, connect=30.0)) as http_client:
        asset_plan = await generate_assets(
            pages=request.report_json.pages,
            skip_slots=frozenset(_skip_slots),
            image_manifest=request.image_manifest.model_dump(),
            brand_primary=brand_tokens.brand_primary,
            brand_accent=brand_tokens.brand_accent,
            brand_profile=request.client.brand_profile,
            design_brief=request.client.design_brief,
            output_dir=output_dir,
            http_client=http_client,
            openrouter_key=openrouter_key,
            prompt_model=cfg.openrouter_prompt_model,
            fal_key=fal_key,
            fal_model=cfg.fal_image_model,
            fal_resolution=cfg.fal_image_resolution,
            cache_dir=Path(cfg.asset_cache_dir),
            max_generations_per_report=cfg.max_generations_per_report,
        )

    components = generate_components_for_report(
        request.report_json.pages,
        brand_primary=brand_tokens.brand_primary,
        brand_accent=brand_tokens.brand_accent,
        brand_neutral_light=brand_tokens.brand_neutral_light,
        structured=structured,
    )
    plan = plan_layout(
        request.report_json.pages, components=components,
        page_count_target=request.report_json.meta.page_count_target,
    )

    resolved = await assemble_package(
        brand_tokens=brand_tokens.model_dump(),
        font_config=font_config,
        copy_warnings=copy_warnings,
        cover_validation=cover_validation,
        asset_plan=asset_plan,
        components=components,
        layout_plan=plan,
        report_json=request.report_json.model_dump(),
        output_dir=output_dir,
        axes=axes,
        axes_provenance=axes_provenance,
        structured=structured,
        page_slots=page_slots,
        client_dir=client_dir,
    )

    # Stage 8.5 - ST-31 cadence + social routing + diagram proof
    # (restructure is cached/optional; None key). G3: the social manifest now
    # comes from the client's persisted classified IG pool, so testimonials /
    # breathers / case-study phones run on every live render — not just the
    # fixture. A client without a manifest degrades to inert (None).
    pkg_path = Path(resolved.package_path)
    pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
    social_manifest = _build_social_manifest(client_dir / "ig")
    try:
        await route_package(
            pkg, manifest=social_manifest, social_root=client_dir / "ig",
            assets_dir=output_dir / "assets",
            openrouter_key=openrouter_key,
            restructure_model=cfg.openrouter_restructure_model,
            restructure_cache_dir=Path(cfg.restructure_cache_dir),
        )
        pkg_path.write_text(json.dumps(pkg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        # Only "no classified pool" is a benign skip. ANY other exception is a
        # real bug and must surface, not be swallowed as "offline" (it would
        # silently drop the dark-divider cadence + diagram layer too).
        if social_manifest is None:
            print("[build_live] route_package (Stage 8.5): no social manifest; social skipped")
        else:
            raise

    return {
        "package_dir": str(output_dir),
        "package_path": str(pkg_path),
        "page_count": len(pkg.get("pages", [])),
        "component_count": sum(len(p.get("components", [])) for p in pkg.get("pages", [])),
        "report_assets": len(pkg.get("report_assets", [])),
    }


def build_live_package(envelope: dict, output_dir: Path | None = None) -> dict:
    """Sync entry: envelope -> real package dir (with components/assets/cadence)."""
    out = output_dir or Path(tempfile.mkdtemp(prefix="dmc_live_"))
    out.mkdir(parents=True, exist_ok=True)
    if selected_contract_version() == "v3":
        return build_precomposition_package_v3(envelope, out)
    request = envelope_to_render_request(envelope)
    return asyncio.run(_build(request, out))


def _with_workflow_provenance_v3(bundle, envelope: dict):
    version_updates = {
        manifest_field: envelope[envelope_field]
        for envelope_field, manifest_field in WORKFLOW_BUILD_VERSION_FIELDS_V3.items()
        if envelope_field in envelope
    }
    workflow_verification_hash = envelope.get("workflow_verification_bundle_sha256")
    if not version_updates and workflow_verification_hash is None:
        return bundle
    complete_ingress = (
        len(version_updates) == len(WORKFLOW_BUILD_VERSION_FIELDS_V3)
        and workflow_verification_hash is not None
    )
    versions = BuildVersions.model_validate(
        {
            **bundle.manifest.versions.model_dump(mode="python"),
            **version_updates,
            **({"workflow_authority": "verified"} if complete_ingress else {}),
        }
    )
    manifest = BuildManifestV3.model_validate(
        {
            **bundle.manifest.model_dump(mode="python"),
            "versions": versions,
            "artifact_hashes": {
                **bundle.manifest.artifact_hashes,
                **(
                    {"workflow_verification_bundle": workflow_verification_hash}
                    if workflow_verification_hash is not None
                    else {}
                ),
            },
        }
    )
    return bundle.model_copy(update={"manifest": manifest})


def build_precomposition_package_v3(envelope: dict, output_dir: Path) -> dict:
    """Run the v3 adapter and authoritative precomposition gates only."""
    adapted = adapt_envelope_v3(envelope)
    report_json = adapted.report_json.model_dump(mode="json")
    sources = list(adapted.sources)
    claims = list(adapted.claims)
    # Evidence seam (Proof B): a real live writer payload arrives as prose
    # with NO claims array, so precomposition refuses every numeral in it as
    # ungrounded. But the figures ARE in the copy the client approved. Derive
    # them (byte-exact source spans, ``copy_derived`` allowed_uses) exactly
    # like the writer-payload adapter does, so the grounding gate reads the
    # report the way it was written. Explicit envelope claims always win
    # (a hand-authored fixture carries authoritative evidence and must not be
    # overwritten by the derivation).
    if not claims:
        from stages.derive_claims_v3 import derive_evidence  # noqa: PLC0415

        derived = derive_evidence(
            {"report_json": report_json},
            captured_at=datetime.now(timezone.utc),
            language=str(report_json.get("meta", {}).get("lang", "de")),
        )
        sources = list(derived.sources)
        claims = list(derived.claims)
    # Client-asset injection (Proof B): the envelope's ``images`` are the
    # client's Drive-folder refs (the Airtable/Drive flow). When the envelope
    # carries no hand-authored ``assets``, resolve those images into
    # AssetRecords (slot-derived semantics) so the case faces get their real
    # identity asset. FAIL CLOSED: an unreadable/Drive-not-cached ref yields
    # no record and the case face honestly flags an asset_gen gap — never
    # a fabricated person.
    assets = list(adapted.assets)
    if not assets:
        try:
            from stages.resolve_client_assets_v3 import resolve_client_assets_v3  # noqa: PLC0415

            client_root = (
                Path(os.environ.get("DMC_CLIENT_ASSETS_DIR"))
                if os.environ.get("DMC_CLIENT_ASSETS_DIR")
                else Path(__file__).resolve().parent.parent / "client_assets"
            )
            assets = list(
                resolve_client_assets_v3(
                    envelope,
                    client_assets_root=client_root,
                )
            )
        except Exception:
            assets = []  # fail closed: no fabricated record ever
    source_bundle = {
        "sources": tuple(sources),
        "claims": tuple(claims),
        "assets": tuple(assets),
        "report_json": report_json,
        "adapter_failures": tuple(
            failure.model_dump(mode="json") for failure in adapted.adapter_failures
        ),
    }
    profile = load_product_profile(PREPROC / "policies" / "dmc_house_20_face.json")
    editorial_brief = envelope.get("editorial_brief_v3")
    if editorial_brief is None:
        editorial_brief = legacy_report_to_editorial_brief(report_json)
        # Input-driven profile (Proof B): a real client report is its own
        # editorial structure (23 faces / 5 cases / no objections chapter) —
        # the fixed 20-face house specimen is a product template, not the
        # report. Stamp the brief AND derive its matching profile so the plan
        # (product_profile_id) and the validated profile are the same string.
        from stages.plan_editorial_v3 import (  # noqa: PLC0415
            _append_derived_profile_id,
            derive_report_profile,
        )

        _append_derived_profile_id(editorial_brief)
        profile = derive_report_profile(editorial_brief)
    bundle = build_precomposition_bundle_v3(
        source_bundle,
        editorial_brief,
        profile,
    )
    bundle = _with_workflow_provenance_v3(bundle, envelope)
    output_dir.mkdir(parents=True, exist_ok=True)
    bundle_path = output_dir / "precomposition_bundle_v3.json"
    bundle_path.write_text(bundle.to_stable_json() + "\n", encoding="utf-8")
    return {
        "contract_version": "v3",
        "package_dir": str(output_dir),
        "package_path": str(bundle_path),
        "content_hash": bundle.content_hash,
        "face_count": bundle.report_plan.units.face_count,
        "fragment_count": bundle.report_plan.units.fragment_count,
    }


if __name__ == "__main__":
    env = json.load(open("/Users/utkarsh/Projects/richard/dmc-renderer/fixtures/apex_consulting_payload.json"))
    print(json.dumps(build_live_package(env), indent=2))
