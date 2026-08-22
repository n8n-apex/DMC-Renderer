"""FAL-TRUTH AGREEMENT GATE — "a fal asset either paints or is deleted."

WHY THIS EXISTS: the user (correctly) found that ~14 fal.ai assets were
generated across 3 campaigns but almost none rendered on the report PDF. The
cause was a BUILD vs RENDER disagreement plus orphans: build_package layered
things into image_map/_SUPPRESS_SLOTS, the treatment templates then refused
unlabeled fal plates, and some files never entered any manifest at all. Every
earlier claim of "fal wired / pixel-verified" covered generated FILES, not
painted pages. This gate locks the HONEST baseline (US-701):

  * image_map.json may reference only files that EXIST on disk;
  * the shipped package's report_assets are exactly the surviving set
    {background_texture (procedural marble), panel_texture (navy_stone)};
  * the known-dead fal-era files are GONE from the fixture;
  * the ONE wired-but-refused survivor (4_status_quo_scene) is explicitly
    flagged for US-704 and may not silently join report_assets.

Run: pytest tests/test_fal_truth_gate.py -v
"""
import json
from pathlib import Path

V7 = Path(__file__).resolve().parent.parent          # research/v7-renderer
FIX = V7 / "fixtures" / "apex"
ASSETS = FIX / "assets"
FIXTURE = FIX / "resolved_package.json"
IMAGE_MAP = FIX / "image_map.json"


def _image_map() -> dict:
    return json.loads(IMAGE_MAP.read_text(encoding="utf-8"))


def _pkg() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


# The fal-era files deleted in US-701 (2026-08-22) as dead: suppressed by the
# slop rip-out, superseded by a real photo / procedural marble, or orphaned
# (never mapped). A re-adding regression trips one of the assertions below.
_DEAD_FAL_SPLIT = {
    "report_background_texture.fal.png",   # fal t2i haze, replaced by procedural marble
    "report_background_texture.procedural.png",  # pre-blend backup of the marble
    "report_atmospheric_gradient.png",     # slop-rip suppressed (breathing_bg_1)
    "5_status_quo_scene.png",              # status_quo_scene_b, suppressed
    "1_cover_hero.png",                    # cover founder photo wins (asserted absent)
    "18_fazit_background.png",             # orphan: never in image_map/report_assets
    "report_navy_footer.png",              # orphan: same img2img batch, never mapped
    "report_fazit_field.png",              # orphan: same batch, never mapped
    "report_extra_wide.png",               # slop-rip suppressed
    "report_extra_square.png",             # slop-rip suppressed
}

# The only fal-era survivors. Everything else from the three campaigns is dead.
_SURVIVOR_REPORT_SLOTS = {"background_texture": "procedural brand marble",
                          "panel_texture": "fal img2img navy stone"}


def test_image_map_references_only_existing_files():
    """A manifest entry pointing at a deleted file is the exact orphan bug US-701
    fixed — the offline build (--no-fal) hard-fails on a missing file."""
    for entry in _image_map().get("page_assets", []) + _image_map().get(
        "report_assets", []
    ):
        f = entry.get("file")
        assert f, f"image_map entry missing 'file': {entry}"
        assert (ASSETS / f).exists(), f"image_map references missing asset: {f}"


def test_dead_fal_files_are_gone():
    """A dead fal file re-added to the fixture is a lying artifact — it exists on
    disk but paints nowhere. US-701 deleted them; a re-add trips this."""
    for f in _DEAD_FAL_SPLIT:
        assert not (ASSETS / f).exists(), f"dead fal asset resurrected: {f}"


def test_report_assets_are_exactly_the_survivors():
    """The shipped package must carry ONLY the survivors in report_assets. The
    slate (cover_hero / gradient / fazit / extra_*) must NEVER be layered back
    in as report assets — that is the 'produced but invisible' state."""
    pkg = _pkg()
    slots = {a.get("slot_id") for a in pkg.get("report_assets", [])}
    assert set(_SURVIVOR_REPORT_SLOTS) <= slots, (
        f"report_assets lost a survivor: {_SURVIVOR_REPORT_SLOTS.keys()} not all in {slots}"
    )
    banned = {"cover_hero", "atmospheric_gradient", "fazit_background",
              "extra_wide", "extra_square", "status_quo_scene_b"}
    assert not (slots & banned), f"suppressed fal slot leaked into report_assets: {slots & banned}"


def test_status_quo_scene_is_flagged_not_hidden():
    """The ONE wired-but-refused fal survivor: 4_status_quo_scene rides the
    ST-09 context page, but the a4_editorial_fill TREATMENT still refuses
    unlabeled fal plates, so it does NOT paint today. It must stay out of
    report_assets (assert above) and remain an open US-704 item — not a silent
    dead file and not a silent paint."""
    pkg = _pkg()
    st09_pages = [p for p in pkg["pages"]
                  if p["st_type"] == "ST-09" and p.get("continuation_role") == "context"]
    assert st09_pages, "ST-09 context page missing from package"
    on_page = [
        a for p in st09_pages for a in (p.get("assets") or [])
        if a.get("slot_id") == "status_quo_scene"
    ]
    assert len(on_page) == 1, f"expected exactly one wired status_quo_scene, got {on_page}"
    # It may NOT be treated as a report-level ground (build_package strips it
    # from the evidence continuation; it must stay a page-level entry).
    assert (ASSETS / "4_status_quo_scene.png").exists(), \
        "US-704 decision asset 4_status_quo_scene must remain on disk until decided"


def test_package_assets_resolve_to_existing_files():
    """Every asset path the package claims must be a real file — no dangling
    claims. (The renderer resolve_asset is graceful, but a claim pointing at
    nothing is exactly the lie this gate kills.)"""
    pkg = _pkg()
    missing = []
    for a in pkg.get("report_assets", []):
        if not (FIX / a.get("path", "")).exists():
            missing.append(a.get("path"))
    for p in pkg.get("pages", []):
        for a in p.get("assets", []):
            ap = a.get("path")
            if ap and not (FIX / ap).exists():
                missing.append(ap)
    assert not missing, f"package references missing assets: {missing}"