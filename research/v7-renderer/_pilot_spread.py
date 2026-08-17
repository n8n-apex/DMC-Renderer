"""PILOT (temporary): render ONE case study (Conesso, fallstudie 4) as a
breathing two-page spread through the real renderer, to verify on pixels before
rolling the layout system out. Builds a 2-page package (spread_story +
spread_proof) and renders it via the real Chromium path. Not wired into the deck.
"""
import sys, json, shutil, copy
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from assembler import render_package  # noqa: E402

APEX = HERE / "fixtures" / "apex"
TMP = Path("/tmp/pilot_pkg")
OUT = Path("/tmp/pilot_out")
if TMP.exists():
    shutil.rmtree(TMP)
shutil.copytree(APEX, TMP)

pkgf = TMP / "resolved_package.json"
pkg = json.loads(pkgf.read_text(encoding="utf-8"))
conesso = next(
    p for p in pkg["pages"]
    if p.get("st_type") == "ST-07A"
    and str((p.get("data") or {}).get("fallstudie_number")) == "4"
)
print("viz on Conesso:", [s.get("preset") for s in (conesso.get("data") or {}).get("viz") or []])
mag = copy.deepcopy(conesso)
mag["layout_variant"] = "magazine"
# MAGAZINE modular interlock: one integrated layout (1-2 pages) where each copy
# block pairs with the visual that proves it. viz[0] (ba_bars) pairs with
# Ausgangssituation; viz[1] (the 3-workflow flow, verbatim from Lösung) pairs
# with Lösung; Ergebnis pairs with the stat + quote.
mag["data"]["viz"] = [
    {"preset": "ba_bars", "unit": "Min", "pairs": [
        {"label": "Onboarding pro Kunde", "before": {"value": "30"}, "after": {"value": "2"}, "delta": "−93 %"},
        {"label": "Copywriting pro Asset", "before": {"value": "60"}, "after": {"value": "5"}, "delta": "−92 %"}]},
    {"preset": "step_cascade", "title": "Drei automatisierte Workflows", "steps": [
        {"title": "Kunden-Onboarding"},
        {"title": "Copy-Generierung"},
        {"title": "Check-in-Vorbereitung"}]},
]
pkg["pages"] = [mag]
pkgf.write_text(json.dumps(pkg, ensure_ascii=False, indent=2), encoding="utf-8")

res = render_package(TMP, OUT, engine="chromium")
print("warnings:", getattr(res, "warnings", res))
print("PNGs:", sorted(str(p.name) for p in OUT.glob("report-p*.png")))
