import asyncio
import json
from pathlib import Path

from stages.route_package import route_package
from models_social import AssetManifest

FIX = Path(__file__).resolve().parents[2] / "v7-renderer" / "fixtures" / "apex"
IG = Path(__file__).resolve().parents[1] / "client_assets" / "apex" / "ig"


def _load(n):
    return json.loads((FIX / n).read_text(encoding="utf-8"))


def test_route_package_applies_social_and_diagram_bindings(tmp_path):
    pkg = _load("resolved_package.json")
    for p in pkg["pages"]:
        (p.get("data") or {}).pop("social_post", None)
        (p.get("data") or {}).pop("diagram", None)
        p.pop("page_mode", None)
    manifest = AssetManifest(**_load("asset_manifest.json"))
    report = asyncio.run(route_package(
        pkg, manifest=manifest, social_root=IG, assets_dir=tmp_path,
        enable_profile_grid=False, openrouter_key="",
    ))
    assert any(p.get("page_mode") == "dark_divider"
               for p in pkg["pages"] if p["st_type"] == "ST-07B")
    case_posts = [p for p in pkg["pages"]
                  if p["st_type"] == "ST-07A" and (p.get("data") or {}).get("social_post")]
    assert len(case_posts) == 1
    st31 = [p for p in pkg["pages"] if p["st_type"] == "ST-31"]
    assert all(any(a.get("image_type") == "scene" for a in (p.get("assets") or []))
               for p in st31)
    assert report.bindings
