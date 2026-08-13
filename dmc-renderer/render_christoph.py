"""Render the christoph-winter v4 fixture end-to-end and rasterize per-page
PNGs. The standing local verification harness (lives in the REPO so a wiped
scratchpad cannot lose it again).

Usage: DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib \
       ../research/v7-renderer/.venv/bin/python render_christoph.py [outdir]
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

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "_local_out"

payload = json.load(open(HERE / "fixtures" / "christoph_v4_payload.json"))
envelope = {
    "payload": payload, "images": {},
    "brand_tokens": {
        "company_name_short": "Inventory ONE", "founder_full_name": "Christoph Winter",
        "qr_target_url": "https://inventory-one.com", "company_url_display": "inventory-one.com",
        "brand_primary": "#243b53", "brand_neutral_dark": "#243b53",
        "brand_neutral_light": "#efece4", "brand_accent": "#d4622a",
        "brand_neutral_mid": "#5E5E58",
    },
}
pkg = OUT / "pkg"
shutil.rmtree(pkg, ignore_errors=True)
build_live.build_live_package(envelope, output_dir=pkg)
render_out = OUT / "render"
shutil.rmtree(render_out, ignore_errors=True)
assembler.render_package(pkg, render_out, engine="chromium", treatments=True)

html = (render_out / "report.html").read_text()
print("PIXEL:", {
    "viz_figures": len(re.findall(r'<figure class="c-viz', html)),
    "product_imgs": html.count('<img class="cs4-product"') + html.count('<img class="ef-product"'),
    "portraits": html.count("ef-portrait-photo") + html.count("cs4-portrait"),
})
png = OUT / "png"
shutil.rmtree(png, ignore_errors=True)
png.mkdir(parents=True, exist_ok=True)
subprocess.run(
    ["pdftoppm", "-png", "-r", "90", str(render_out / "report.pdf"), str(png / "p")],
    check=True,
)
print("pngs ->", png)
