"""Verification harness for the renderer-contract-audit fixes (2026-07-16).

Encodes the EXPECTED post-fix adapter behaviour for the gaps found in
`docs/renderer-contract-audit-2026-07-16.md`. Stubs the one network call
(synthesize_page_visuals) so it runs offline with no API key.

Lives in the REPO, not the scratchpad: the scratchpad IS wiped (this file was
lost once already), and `render_christoph.py` carries the same warning.

Expected: 10/10 passed. If a check fails, the corresponding fix in
`build_live.py` (founder-identity gate / proof_stats / belief quelle) or the
pass-through key in `docs/resolve-schema-node-v5.js` has regressed.

Usage: DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib \
       ../research/v7-renderer/.venv/bin/python verify_contract_fixes.py
"""
import sys, os
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ.setdefault("OPENROUTER_API_KEY", "")  # unused; synth is stubbed

import build_live
# no network: the visual synthesizer is not what we're testing
build_live.synthesize_visuals.synthesize_page_visuals = lambda norm, **kw: norm

BT = {
    "company_name_short": "ACME",
    "founder_full_name": "Max Muster",
    "founder_role": "Gründer",
    "brand_primary": "#1a1a2e", "brand_accent": "#e94560",
    "brand_neutral_dark": "#1a1a2e", "brand_neutral_light": "#f5f5f7",
    "qr_target_url": "https://acme.example",
}

envelope = {
    "brand_tokens": BT,
    "images": {},
    "payload": {
        "meta": {"report_id": "acme-test", "client_slug": "acme", "page_count_target": "20"},
        "pages": [
            {"type": "ST-01", "slot": 1, "data": {
                "title": "Warum Excel zum Risiko wird",
                "kicker": "Für Agenturen",
                "kennzahlen": [{"wert": "13.160 €", "label": "pro Monat für Koordination"}],
                # pass-through keys (schema-node adds them; adapter must not strip):
                "title_accent": "zum Risiko",
                "kicker_pills": ["Report", "2026"],
                "teaser_items": ["Der Montags-Stau", "Die doppelte Pflege"],
            }},
            {"type": "ST-05", "slot": 5, "data": {
                "titel": "Wer wir sind", "einleitung": "x", "angebot_text": "y",
                "partners": ["Cordes Consulting", "Frese Recruiting"],  # pass-through
            }},
            {"type": "ST-14", "slot": 14, "data": {
                "titel": "Irrtümer", "einleitung": "x",
                "irrtuemer": [{"irrtum": "Zu teuer", "realitaet": "Nein",
                               "erklaerung": "weil", "quelle": "(Destatis, 2018)"}],
            }},
            {"type": "ST-07B", "slot": 8, "data": {
                "titel": "Das Prinzip", "kernaussage": "x", "erklaerung": "y",
                "compare": {"ohne": ["chaos"], "mit": ["struktur"]},  # pass-through
            }},
            {"type": "ST-07A", "slot": 12, "data": {
                "titel": "Fallstudie", "ausgangsproblem": "x", "loesung": "y",
                "kunde": {  # schema-node emits name/company_url (G5)
                    "name": "GoldmanTax", "company_url": "goldmantax.example",
                    "funktion": "Steuerberatung",
                },
            }},
            {"type": "ST-FAZIT", "slot": 20, "data": {
                "titel": "Fazit", "zusammenfassung": "x",
                "kernbotschaft": "Struktur schlägt Talent",
            }},
        ],
    },
}

req = build_live.envelope_to_render_request(envelope)
by = {p.type: p.data for p in req.report_json.pages}

checks = []
def check(name, cond):
    checks.append((name, bool(cond)))

d01 = by["ST-01"]
check("ST-01 proof_stats filled (from stats)", bool(d01.get("proof_stats")))
check("ST-01 author.name filled (founder)", (d01.get("author") or {}).get("name") == "Max Muster")
check("ST-01 title_accent passthrough", d01.get("title_accent") == "zum Risiko")
check("ST-01 kicker_pills passthrough", d01.get("kicker_pills") == ["Report", "2026"])
check("ST-01 teaser_items passthrough", bool(d01.get("teaser_items")))

d05 = by["ST-05"]
check("ST-05 partners passthrough", d05.get("partners") == ["Cordes Consulting", "Frese Recruiting"])
check("ST-05 author still filled", bool((d05.get("author") or {}).get("name")))

d14 = by["ST-14"]
bel = (d14.get("beliefs") or [{}])[0]
check("ST-14 belief carries quelle", bel.get("quelle") == "(Destatis, 2018)")

d07b = by["ST-07B"]
check("ST-07B compare passthrough", (d07b.get("compare") or {}).get("ohne") == ["chaos"])

d07a = by["ST-07A"]
check("ST-07A kunde.name passthrough", (d07a.get("kunde") or {}).get("name") == "GoldmanTax")
check("ST-07A kunde.company_url passthrough", (d07a.get("kunde") or {}).get("company_url") == "goldmantax.example")

dfz = by["ST-FAZIT"]
check("ST-FAZIT author.name filled (founder)", (dfz.get("author") or {}).get("name") == "Max Muster")

print("=" * 60)
npass = sum(1 for _, ok in checks if ok)
for name, ok in checks:
    print(("PASS " if ok else "FAIL ") + name)
print("=" * 60)
print(f"{npass}/{len(checks)} passed")
sys.exit(0 if npass == len(checks) else 1)
