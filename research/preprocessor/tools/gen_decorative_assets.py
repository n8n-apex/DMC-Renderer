"""Generate APEX decorative MATERIAL assets via fal Nano Banana Pro IMAGE-TO-IMAGE.

Why img2img (edit) and not text-to-image: we seed each call with a clean,
brand-correct canvas (navy #2E3E50 with the soft glow already placed, or warm
cream #F6F3ED), so the model only has to ELEVATE the seed into premium photoreal
material. It cannot wander into text / objects / wrong colors. That is the
anti-slop mechanism (text-to-image is a blank slate; this is "refine THIS").

Endpoint: fal-ai/nano-banana-pro/edit  (image_urls accepts base64 data URIs).
fal has no negative_prompt field, so the bans are folded into the prompt text.

Run:
  cd research/preprocessor
  set -a; . ./.env >/dev/null 2>&1; set +a      # loads FAL_KEY without echoing
  .venv/bin/python tools/gen_decorative_assets.py --dry     # print prompts only
  .venv/bin/python tools/gen_decorative_assets.py           # FIRE (writes assets)

This script makes NO call in --dry mode. It NEVER prints the key.
"""
from __future__ import annotations

import argparse
import base64
import os
import sys
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
SEEDS = Path("/tmp/seeds")
OUT_DIR = (HERE / ".." / ".." / "v7-renderer" / "fixtures" / "apex" / "assets").resolve()
ENDPOINT = "https://fal.run/fal-ai/nano-banana-pro/edit"
RESOLUTION = "2K"

# The hard anti-slop ban list (folded into every prompt; teal is renderer trim
# only, so it is banned inside generated materials). No text is THE failure mode.
BANS = (
    "no text, no letters, no words, no numbers, no logos, no watermarks, no icons, "
    "no charts, no graphs, no data, no UI, no objects, no people, no faces, "
    "no marble veining, no stone slab edges, no cracks, no gold, no metallic, no foil, "
    "no gloss, no bevel, no lens flare, no spotlight, no rays, no particles, no banding, "
    "no hard vignette ring, no seams, no teal, no cyan, no blue, no purple, no green color cast"
)

# Each asset: seed canvas + an EDIT instruction (keep palette+glow, add real material).
ASSETS = [
    {
        "name": "report_navy_stone",
        "seed": "seed_navy_field.png",
        "aspect_ratio": "1:1",
        "prompt": (
            "Transform this image into a premium photorealistic matte dark navy STONE "
            "surface. Keep the exact deep desaturated navy color and keep the single soft "
            "off-center light glow exactly where it already is. Add fine realistic fine-grain "
            "stone / honed-concrete micro-texture and a very subtle low-frequency tonal depth. "
            "Matte, no shine, low overall contrast so light text could sit on top and stay "
            "readable. Keep it a calm abstract material field. " + BANS + "."
        ),
    },
    {
        "name": "report_navy_footer",
        "seed": "seed_footer_band.png",
        "aspect_ratio": "auto",
        "prompt": (
            "Transform this image into a premium photorealistic matte dark navy STONE band. "
            "Keep the exact deep navy color and the soft central glow exactly as placed; keep "
            "the upper area cleaner and calmer for content. Add fine realistic honed-stone "
            "micro-texture and gentle material depth, matte, low contrast. Abstract material "
            "only. " + BANS + "."
        ),
    },
    {
        "name": "report_fazit_field",
        "seed": "seed_fazit.png",
        "aspect_ratio": "3:4",
        "prompt": (
            "Transform this image into a premium photorealistic full-bleed matte navy SLATE "
            "stone field for a closing page. Keep the exact deep navy color, keep the soft glow "
            "rising from the lower-center, and keep the generous calm empty space in the middle. "
            "Add fine realistic slate micro-texture and smooth tonal depth, matte, low contrast. "
            + BANS + "."
        ),
    },
    {
        "name": "report_cream_paper",
        "seed": "seed_cream.png",
        "aspect_ratio": "1:1",
        "prompt": (
            "Transform this image into a premium uncoated fine-art CREAM PAPER surface. Keep the "
            "exact warm cream color, do not shift the hue. Add a subtle realistic paper fiber and "
            "laid tooth texture, completely matte, flat even diffuse light, extremely low contrast "
            "(the texture should be felt only up close), seamless. Abstract paper material only. "
            + BANS + "."
        ),
    },
]


def _data_uri(p: Path) -> str:
    b = p.read_bytes()
    return "data:image/png;base64," + base64.b64encode(b).decode("ascii")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="print the prompts/plan; make NO fal call")
    ap.add_argument("--only", default="", help="comma-separated asset names to generate")
    args = ap.parse_args()

    only = {s.strip() for s in args.only.split(",") if s.strip()}
    assets = [a for a in ASSETS if not only or a["name"] in only]

    print(f"endpoint: {ENDPOINT}")
    print(f"resolution: {RESOLUTION}   out_dir: {OUT_DIR}")
    for a in assets:
        seed = SEEDS / a["seed"]
        print("\n" + "=" * 78)
        print(f"ASSET: {a['name']}   seed: {seed}  ({'exists' if seed.exists() else 'MISSING'})  aspect: {a['aspect_ratio']}")
        print(f"PROMPT:\n{a['prompt']}")

    if args.dry:
        print("\n[--dry] no fal call made.")
        return 0

    key = os.environ.get("FAL_KEY")
    if not key:
        print("\nFAL_KEY not in environment. Load it first: set -a; . ./.env >/dev/null 2>&1; set +a", file=sys.stderr)
        return 2

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    headers = {"Authorization": f"Key {key}", "Content-Type": "application/json"}
    results = []
    with httpx.Client(timeout=httpx.Timeout(300.0), follow_redirects=True) as client:
        for a in assets:
            seed = SEEDS / a["seed"]
            if not seed.exists():
                print(f"[skip] {a['name']}: seed missing {seed}")
                results.append((a["name"], "seed_missing"))
                continue
            body = {
                "prompt": a["prompt"],
                "image_urls": [_data_uri(seed)],
                "num_images": 1,
                "output_format": "png",
                "resolution": RESOLUTION,
            }
            if a["aspect_ratio"] != "auto":
                body["aspect_ratio"] = a["aspect_ratio"]
            try:
                r = client.post(ENDPOINT, json=body, headers=headers)
                if r.status_code != 200:
                    print(f"[fail] {a['name']}: HTTP {r.status_code} {r.text[:200]}")
                    results.append((a["name"], f"http_{r.status_code}"))
                    continue
                url = r.json()["images"][0]["url"]
                img = client.get(url)
                out = OUT_DIR / f"{a['name']}.png"
                out.write_bytes(img.content)
                print(f"[ok]   {a['name']} -> {out} ({len(img.content):,} bytes)")
                results.append((a["name"], "generated"))
            except Exception as exc:  # noqa: BLE001 - never raise; record + continue
                print(f"[fail] {a['name']}: {exc!r}")
                results.append((a["name"], "error"))
    print("\nSUMMARY:", results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
