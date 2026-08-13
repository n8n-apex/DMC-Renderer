"""Render the christoph v5 fixture with a COVER that exercises the 2026-07-16
contract-audit fixes, and rasterize page 1 so the cover can be LOOKED at.

Exercises: proof_stats (from kennzahlen), the founder byline (author injected for
ST-01), kicker_pills, title_accent, teaser_items. Everything on the cover comes
from the fixture's own copy plus brand_tokens; no invented client facts.

Usage: DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib \
       ../research/v7-renderer/.venv/bin/python render_cover_check.py [outdir]
"""
import sys
import json
import re
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "research" / "v7-renderer"))

import build_live  # noqa: E402
import assembler  # noqa: E402

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "_local_out_cover"

payload = json.load(open(HERE / "fixtures" / "christoph_v5_payload.json"))

# Give the COVER the fields the audit just wired, so the render proves them.
# Figures are lifted VERBATIM from this fixture's own ST-09 status-quo copy
# (300.000 EUR verbrannt / 18 Monate) - nothing invented.
for pg in payload["pages"]:
    if pg.get("type") == "ST-01":
        d = pg.setdefault("data", {})
        d["title_accent"] = "stagniert"
        d["kicker_pills"] = ["Report 2026", "Software-Hersteller"]
        d["kennzahlen"] = [
            {"wert": "300.000 €", "label": "in einer gescheiterten Migration verbrannt"},
            {"wert": "18 Monate", "label": "Entwicklung ohne fertiges Produkt"},
        ]
        # SHORT noun phrases: the rail is a narrow 2-column strip at the foot of a
        # band that already carries a 3-line title + 3-line subtitle. Full sentences
        # overflow and are silently clipped by the bleed page (observed 2026-07-16).
        d["teaser_items"] = [
            "Warum Web-Projekte scheitern",
            "Modernisierung ohne Blindflug",
        ]
        break

envelope = {
    "payload": payload, "images": {},
    "brand_tokens": {
        "company_name_short": "Inventory ONE",
        "founder_full_name": "Christoph Winter",
        "founder_role": "Gründer",
        "qr_target_url": "https://inventory-one.com",
        "company_url_display": "inventory-one.com",
        "brand_primary": "#243b53", "brand_neutral_dark": "#243b53",
        "brand_neutral_light": "#efece4", "brand_accent": "#d4622a",
        "brand_neutral_mid": "#5E5E58",
    },
}

pkg = OUT / "pkg"
shutil.rmtree(pkg, ignore_errors=True)
build_live.build_live_package(envelope, output_dir=pkg)

# what actually reached the cover page data
cover = json.loads((pkg / "resolved_package.json").read_text())["pages"][0]
cd = cover.get("data", {})
print("COVER DATA:", {
    "proof_stats": len(cd.get("proof_stats") or []),
    "author": (cd.get("author") or {}).get("name"),
    "author_role": (cd.get("author") or {}).get("role"),
    "kicker_pills": len(cd.get("kicker_pills") or []),
    "teaser_items": len(cd.get("teaser_items") or []),
    "title_accent": cd.get("title_accent"),
})

render_out = OUT / "render"
shutil.rmtree(render_out, ignore_errors=True)
assembler.render_package(pkg, render_out, engine="chromium", treatments=True)

html = (render_out / "report.html").read_text()
# cover-specific markers from patterns/st_01.py + templates/st_01.html.jinja
print("PIXEL(cover markers):", {
    "c-stat-rail": html.count("c-stat-rail"),
    "cv-byline": html.count("cv-byline") + html.count("cv-author"),
    "c-pill": html.count("c-pill"),
    "cv-teaser": html.count("cv-teaser"),
    "cv-hero--portrait": html.count("cv-hero--portrait"),
})

png = OUT / "png"
shutil.rmtree(png, ignore_errors=True)
png.mkdir(parents=True, exist_ok=True)
subprocess.run(
    ["pdftoppm", "-png", "-r", "110", "-f", "1", "-l", "1",
     str(render_out / "report.pdf"), str(png / "cover")],
    check=True,
)
print("pngs ->", png)
