"""Tests for the deterministic Social Layout Planner (Phase 1).

`plan_social` is PURE (injected `asset_exists`): given a classified asset
manifest + the report's social homes (breather slots, about slot, fazit
slot, case-study client names), it decides bindings deterministically.
`apply_social_plan` is the ONLY mutator: it stages the bound files and
writes them onto the package pages (idempotently).

Brand-agnostic: every client string lives in the manifest DATA here (test
fixtures may name clients — that is data, not logic).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from models_social import AssetClassification, AssetManifest
from stages.plan_social import apply_social_plan, plan_social


# --------------------------------------------------------------------------
# Fixtures: an apex-shaped pool (mirrors fixtures/apex/asset_manifest.json).
# --------------------------------------------------------------------------

def _apex_assets() -> list[AssetClassification]:
    return [
        AssetClassification(path="ig/avatar.jpg", role="founder_portrait", visual_appeal=3),
        AssetClassification(path="ig/dvolek_0.jpg", role="client_photo", brand_text="Goldman Tax", visual_appeal=2),
        AssetClassification(path="ig/dvolek_1.jpg", role="client_photo", brand_text="Goldman Tax", visual_appeal=3),
        AssetClassification(path="ig/card_2.jpg", role="content_card", is_testimonial_card=True, brand_text="Bildungsfabrik", has_overlaid_text=True, visual_appeal=3),
        AssetClassification(path="ig/card_3.jpg", role="content_card", is_testimonial_card=True, brand_text="Aramaz Digital", has_overlaid_text=True, visual_appeal=3),
        AssetClassification(path="ig/dyil_4.jpg", role="client_photo", brand_text="Frese Recruiting", visual_appeal=3),
        AssetClassification(path="ig/dyhz_5.jpg", role="interview", brand_text="Frese Recruiting", visual_appeal=3),
        AssetClassification(path="ig/dyhz_6.jpg", role="interview", brand_text="Frese Recruiting", visual_appeal=2),
        AssetClassification(path="ig/dyhz_7.jpg", role="interview", brand_text="Frese Recruiting", visual_appeal=2),
        AssetClassification(path="ig/dx2k_8.jpg", role="speaking", visual_appeal=3),
        AssetClassification(path="ig/dx2k_9.jpg", role="speaking", visual_appeal=2),
        AssetClassification(path="ig/dx2k_10.jpg", role="speaking", visual_appeal=2),
        AssetClassification(path="ig/dx2k_11.jpg", role="speaking", visual_appeal=2),
    ]


def _apex_manifest() -> AssetManifest:
    return AssetManifest(handle="jousefmrd", assets=_apex_assets())


_APEX_CASE_CLIENTS = {7: "Martina Ammon", 9: "Cordes Consulting", 12: "Frese Recruiting", 14: "Conesso GmbH", 15: "Hanisch & Klein"}
_APEX_BREATHERS = [6, 11, 17]
_APEX_ABOUT = 3
_APEX_FAZIT = 18


def _always(_p: str) -> bool:
    return True


def _plan_apex(**over):
    kw = dict(
        case_clients=_APEX_CASE_CLIENTS,
        breather_slots=_APEX_BREATHERS,
        about_slot=_APEX_ABOUT,
        fazit_slot=_APEX_FAZIT,
        founder_name="Jousef",
        founder_role="Gründer",
        asset_exists=_always,
    )
    kw.update(over)
    return plan_social(_apex_manifest(), **kw)


def _by_element(plan):
    out: dict[str, list] = {}
    for b in plan.bindings:
        out.setdefault(b.element, []).append(b)
    return out


# --------------------------------------------------------------------------
# (a) full apex pool — the headline expected layout (§6a)
# --------------------------------------------------------------------------

def test_full_pool_produces_grid_scenes_testimonials_case_fazit() -> None:
    plan = _plan_apex()
    el = _by_element(plan)

    # profile_grid → the LAST breather slot. The grid is the FEED OVERVIEW, so it
    # shows the 9 best posts by appeal (gap-fix B) — exactly 9 when ≥9 posts exist
    # (apex has 10 posts). EXEMPT from cross-binding de-dup (it may include posts
    # also used as breathers/case-study), but never duplicated WITHIN itself.
    assert len(el["profile_grid"]) == 1
    grid = el["profile_grid"][0]
    assert grid.target_kind == "ST-31"
    assert grid.page_slot == 17  # LAST breather
    assert grid.handle == "jousefmrd"
    assert len(grid.assets) == 9  # exactly 9 (apex has 10 posts ≥ 9)
    assert len(grid.assets) == len(set(grid.assets))  # no dupes within grid

    # scene breathers → the OTHER breather slots, ascending
    scenes = el["scene_breather"]
    assert [b.page_slot for b in scenes] == [6, 11]
    for b in scenes:
        assert b.target_kind == "ST-31"
        assert len(b.assets) == 1

    # testimonials → about slot, ≤2 cards, appeal-ranked
    tcards = el["testimonials"]
    assert len(tcards) == 1
    tb = tcards[0]
    assert tb.page_slot == _APEX_ABOUT
    assert tb.target_kind == "ST-05"
    assert len(tb.assets) == 2

    # case_study_post → the Frese case study slot (12), confident single client
    cs = el["case_study_post"]
    assert len(cs) == 1
    assert cs[0].page_slot == 12
    assert cs[0].target_kind == "ST-07A"
    # the matched post is the primary asset; an optional founder avatar may ride
    # along as a 2nd asset (the IG-post header), per spec `{photo, avatar?, handle}`.
    assert 1 <= len(cs[0].assets) <= 2

    # fazit_author → no page binding needed beyond element + name
    fa = el["fazit_author"]
    assert len(fa) == 1
    assert fa[0].page_slot == _APEX_FAZIT


def test_full_pool_lead_breather_is_a_scene_shot() -> None:
    """The FIRST (lead) breather is always a SCENE shot (scene/speaking/working
    — the stage/atmosphere look). Subsequent breathers may diversify to other
    post roles (gap-fix A)."""
    plan = _plan_apex()
    scenes = _by_element(plan)["scene_breather"]
    by_path = {a.path: a for a in _apex_assets()}
    lead = by_path[scenes[0].assets[0]]
    assert lead.role in {"scene", "speaking", "working"}


def test_full_pool_breathers_diversify_by_shoot_and_role() -> None:
    """Gap-fix A: the two apex breathers must NOT cluster the same shoot/role.
    slot 6 is a stage `speaking` shot; slot 11 is a NON-stage shot (the Goldman
    handshake client_photo) — a different role AND a different shoot."""
    from stages.plan_social import _shoot

    plan = _plan_apex()
    scenes = {b.page_slot: b for b in _by_element(plan)["scene_breather"]}
    by_path = {a.path: a for a in _apex_assets()}

    slot6 = by_path[scenes[6].assets[0]]
    slot11 = by_path[scenes[11].assets[0]]

    # slot 6 = a stage speaking shot (the lead scene)
    assert slot6.role == "speaking"
    assert slot6.path == "ig/dx2k_8.jpg"

    # slot 11 = a NON-stage shot: the Goldman handshake client_photo (appeal 3)
    assert slot11.role == "client_photo"
    assert slot11.path == "ig/dvolek_1.jpg"

    # the two breathers differ in BOTH role and shoot (no clustering)
    assert slot6.role != slot11.role
    assert _shoot(slot6.path) != _shoot(slot11.path)


def test_full_pool_case_post_is_frese_branded() -> None:
    plan = _plan_apex()
    cs = _by_element(plan)["case_study_post"][0]
    by_path = {a.path: a for a in _apex_assets()}
    bound = by_path[cs.assets[0]]
    # normalized brand_text must be a containment match with the client name
    assert "frese" in bound.brand_text.lower()
    assert not bound.is_testimonial_card


def test_profile_grid_disabled_makes_every_breather_a_scene() -> None:
    """enable_profile_grid=False (a client whose reach doesn't justify a feed
    overview) → NO profile_grid binding; EVERY breather (incl. the last) becomes a
    diversified full-bleed scene photo. Other bindings (testimonials/case/fazit)
    are unaffected."""
    plan = _plan_apex(enable_profile_grid=False)
    el = _by_element(plan)

    assert "profile_grid" not in el                      # the grid is gone
    scenes = el["scene_breather"]
    assert [b.page_slot for b in scenes] == [6, 11, 17]   # ALL breathers, ascending
    for b in scenes:
        assert b.target_kind == "ST-31"
        assert len(b.assets) == 1
    # the 3 scene photos are distinct (no breather reuses another's shot)
    paths = [b.assets[0] for b in scenes]
    assert len(paths) == len(set(paths))
    # the other homes still fill
    assert len(el["testimonials"]) == 1
    assert len(el["case_study_post"]) == 1
    assert len(el["fazit_author"]) == 1


# --------------------------------------------------------------------------
# (b) empty / absent pool → zero bindings, graceful
# --------------------------------------------------------------------------

def test_empty_manifest_zero_bindings() -> None:
    plan = plan_social(
        AssetManifest(),
        case_clients=_APEX_CASE_CLIENTS, breather_slots=_APEX_BREATHERS,
        about_slot=_APEX_ABOUT, fazit_slot=None, founder_name="", founder_role="",
        asset_exists=_always,
    )
    assert plan.bindings == []


def test_no_homes_no_bindings() -> None:
    plan = plan_social(
        _apex_manifest(), case_clients={}, breather_slots=[], about_slot=None,
        fazit_slot=None, founder_name="", founder_role="", asset_exists=_always,
    )
    # no breathers, no about, no cases, no fazit → nothing to bind
    assert plan.bindings == []


# --------------------------------------------------------------------------
# (d) <6 posts → no grid (scenes only)
# --------------------------------------------------------------------------

def test_under_six_posts_no_grid_but_scenes() -> None:
    assets = [
        AssetClassification(path="p/a.jpg", role="speaking", visual_appeal=3),
        AssetClassification(path="p/b.jpg", role="speaking", visual_appeal=2),
        AssetClassification(path="p/c.jpg", role="scene", visual_appeal=1),
    ]
    plan = plan_social(
        AssetManifest(handle="h", assets=assets), case_clients={},
        breather_slots=[6, 11, 17], about_slot=None, fazit_slot=None,
        founder_name="", founder_role="", asset_exists=_always,
    )
    el = _by_element(plan)
    assert "profile_grid" not in el  # <6 posts → no grid
    # all breather slots become scene breathers (filled in slot order)
    assert [b.page_slot for b in el["scene_breather"]] == [6, 11, 17]


# --------------------------------------------------------------------------
# (c) client-match — positive and negative
# --------------------------------------------------------------------------

def test_client_match_negative_no_matching_case_study() -> None:
    assets = [
        AssetClassification(path="p/a.jpg", role="client_photo", brand_text="Totally Unrelated GmbH", visual_appeal=3),
    ]
    plan = plan_social(
        AssetManifest(assets=assets),
        case_clients={7: "Martina Ammon", 9: "Cordes Consulting"},
        breather_slots=[], about_slot=None, fazit_slot=None,
        founder_name="", founder_role="", asset_exists=_always,
    )
    assert "case_study_post" not in _by_element(plan)
    assert any("Totally Unrelated" in d or "case" in d.lower() for d in plan.dropped)


def test_client_match_positive_single_confident() -> None:
    assets = [
        AssetClassification(path="p/match.jpg", role="client_photo", brand_text="Frese", visual_appeal=3),
    ]
    plan = plan_social(
        AssetManifest(assets=assets),
        case_clients={12: "Frese Recruiting"},
        breather_slots=[], about_slot=None, fazit_slot=None,
        founder_name="", founder_role="", asset_exists=_always,
    )
    cs = _by_element(plan)["case_study_post"]
    assert len(cs) == 1
    assert cs[0].page_slot == 12
    assert cs[0].assets == ["p/match.jpg"]


def test_client_match_ambiguous_two_clients_skipped() -> None:
    # one brand_text contained in TWO different client names → ambiguous → skip
    assets = [
        AssetClassification(path="p/amb.jpg", role="client_photo", brand_text="Consulting", visual_appeal=3),
    ]
    plan = plan_social(
        AssetManifest(assets=assets),
        case_clients={9: "Cordes Consulting", 15: "Hanisch Consulting"},
        breather_slots=[], about_slot=None, fazit_slot=None,
        founder_name="", founder_role="", asset_exists=_always,
    )
    assert "case_study_post" not in _by_element(plan)


# --------------------------------------------------------------------------
# (e) de-dup — no asset bound to two homes
# --------------------------------------------------------------------------

def test_dedup_no_asset_in_two_bindings_grid_exempt() -> None:
    """De-dup holds among the SINGLE-PHOTO homes (breathers + case-study +
    testimonials): no asset is bound to two of those. The profile GRID is the
    FEED OVERVIEW and is EXEMPT (gap-fix B) — it shows the best posts regardless
    of whether they are also a breather/case-study, so it is excluded here."""
    plan = _plan_apex()
    seen: list[str] = []
    for b in plan.bindings:
        if b.element == "profile_grid":
            continue  # grid is exempt from cross-binding de-dup
        seen.extend(b.assets)
    assert len(seen) == len(set(seen)), f"asset bound twice (non-grid): {seen}"


def test_grid_is_exempt_from_dedup_and_may_share_breather_case_assets() -> None:
    """The grid (feed overview) MAY include posts also used as a breather or the
    case-study post — that overlap is intentional (gap-fix B). Assert at least
    one grid member is also bound elsewhere, proving the exemption is real (the
    apex pool is small, so the 9-best grid overlaps the single-photo homes)."""
    plan = _plan_apex()
    el = _by_element(plan)
    grid = set(el["profile_grid"][0].assets)
    others: set[str] = set()
    for elem in ("scene_breather", "case_study_post"):
        for b in el.get(elem, []):
            others.update(b.assets)
    assert grid & others, "grid should overlap a breather/case post (exempt de-dup)"


# --------------------------------------------------------------------------
# (f) asset_exists=False → dropped, not bound
# --------------------------------------------------------------------------

def test_missing_files_are_dropped_not_bound() -> None:
    plan = _plan_apex(asset_exists=lambda _p: False)
    # nothing physically exists → no file-backed bindings
    for b in plan.bindings:
        assert b.element == "fazit_author", b  # author needs no file
    assert plan.dropped, "missing files should be recorded as dropped"


def test_partial_missing_files_only_existing_bound() -> None:
    # only the cards exist; posts all missing → testimonials bind, grid/scenes/case skip
    existing = {"ig/card_2.jpg", "ig/card_3.jpg"}
    plan = _plan_apex(asset_exists=lambda p: p in existing)
    el = _by_element(plan)
    assert "profile_grid" not in el
    assert "scene_breather" not in el
    assert "case_study_post" not in el
    assert len(el["testimonials"]) == 1
    assert set(el["testimonials"][0].assets) == existing


# --------------------------------------------------------------------------
# determinism
# --------------------------------------------------------------------------

def test_plan_is_deterministic() -> None:
    a = _plan_apex().model_dump()
    b = _plan_apex().model_dump()
    assert a == b


# --------------------------------------------------------------------------
# apply_social_plan — the mutator
# --------------------------------------------------------------------------

def _fake_package() -> dict:
    return {
        "pages": [
            {"slot": 3, "st_type": "ST-05", "data": {
                "body": "P1.\n\nP2.\n\nP3.\n\nP4.",
                "credibility_points": ["c1", "c2"],
            }, "assets": []},
            {"slot": 6, "st_type": "ST-31", "data": {"phrase": "x"}, "assets": [
                {"slot_id": "breathing_bg_1", "image_type": "gradient", "path": "assets/grad.png", "status": "generated"}
            ]},
            {"slot": 11, "st_type": "ST-31", "data": {"phrase": "y"}, "assets": [
                {"slot_id": "breathing_bg_2", "image_type": "texture", "path": "assets/tex.png", "status": "generated"}
            ]},
            {"slot": 12, "st_type": "ST-07A", "data": {"kunde": {"name": "Frese Recruiting"}}, "assets": []},
            {"slot": 17, "st_type": "ST-31", "data": {"phrase": "z"}, "assets": [
                {"slot_id": "breathing_bg_3", "image_type": "background", "path": "assets/bg.png", "status": "generated"}
            ]},
            {"slot": 18, "st_type": "ST-FAZIT", "data": {"body": "..."}, "assets": []},
        ]
    }


def _make_source(tmp_path: Path) -> Path:
    """Create source files matching the apex manifest paths under a root."""
    root = tmp_path / "src"
    for a in _apex_assets():
        f = root / a.path
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"fakejpg")
    return root


def _page(pkg: dict, slot: int) -> dict:
    return next(p for p in pkg["pages"] if p["slot"] == slot)


def test_apply_lands_bindings_and_stages_files(tmp_path: Path) -> None:
    source_root = _make_source(tmp_path)
    assets_dir = tmp_path / "pkg" / "assets"
    plan = _plan_apex(asset_exists=lambda p: (source_root / p).exists())
    pkg = _fake_package()
    out = apply_social_plan(pkg, plan, assets_dir=assets_dir, source_root=source_root)

    # grid landed on slot 17
    grid_page = _page(out, 17)
    sp = grid_page["data"]["social_post"]
    assert sp["handle"] == "jousefmrd"
    assert isinstance(sp["grid"], list) and len(sp["grid"]) >= 6
    assert all(g.startswith("assets/ig_") for g in sp["grid"])

    # scene breathers repointed (breathing_bg → staged scene, image_type scene)
    for slot in (6, 11):
        p = _page(out, slot)
        bg = p["assets"][0]
        assert bg["image_type"] == "scene"
        assert bg["path"].startswith("assets/ig_")

    # testimonials on about + body trimmed to 2 paras
    about = _page(out, 3)
    assert len(about["data"]["testimonials"]) == 2
    assert all(t.startswith("assets/ig_") for t in about["data"]["testimonials"])
    assert about["data"]["body"].count("\n\n") == 1  # 2 paragraphs

    # case study post on slot 12
    case = _page(out, 12)
    assert "social_post" in case["data"]
    assert case["data"]["social_post"]["photo"].startswith("assets/ig_")

    # fazit author
    fazit = _page(out, 18)
    assert fazit["data"]["author"] == {"name": "Jousef", "role": "Gründer"}

    # files physically staged
    staged = list(assets_dir.glob("ig_*"))
    assert staged, "no files staged"


def test_apply_trims_about_body_only_when_testimonials_bound(tmp_path: Path) -> None:
    source_root = _make_source(tmp_path)
    assets_dir = tmp_path / "pkg" / "assets"
    # a plan with NO testimonials binding
    plan = plan_social(
        AssetManifest(assets=[AssetClassification(path="ig/dx2k_8.jpg", role="speaking", visual_appeal=3)]),
        case_clients={}, breather_slots=[6], about_slot=3, fazit_slot=None,
        founder_name="", founder_role="", asset_exists=lambda p: (source_root / p).exists(),
    )
    pkg = _fake_package()
    out = apply_social_plan(pkg, plan, assets_dir=assets_dir, source_root=source_root)
    about = _page(out, 3)
    # no testimonials bound → body untouched (still 4 paras)
    assert "testimonials" not in about["data"] or not about["data"].get("testimonials")
    assert about["data"]["body"].count("\n\n") == 3


def test_apply_is_idempotent(tmp_path: Path) -> None:
    source_root = _make_source(tmp_path)
    assets_dir = tmp_path / "pkg" / "assets"
    plan = _plan_apex(asset_exists=lambda p: (source_root / p).exists())
    pkg = _fake_package()
    once = apply_social_plan(_fake_package(), plan, assets_dir=assets_dir, source_root=source_root)
    twice = apply_social_plan(json.loads(json.dumps(once)), plan, assets_dir=assets_dir, source_root=source_root)
    assert once == twice


def test_apply_never_binds_missing_source_file(tmp_path: Path) -> None:
    # source root is empty → apply must not crash, must not stage anything
    source_root = tmp_path / "empty"
    source_root.mkdir()
    assets_dir = tmp_path / "pkg" / "assets"
    plan = _plan_apex(asset_exists=lambda _p: True)  # planner thinks they exist
    pkg = _fake_package()
    out = apply_social_plan(pkg, plan, assets_dir=assets_dir, source_root=source_root)
    # author still lands (no file needed)
    assert _page(out, 18)["data"].get("author")


# ---------------------------------------------------------------------------
# LIVE-PATH manifest derivation (US-307): a deterministic fallback manifest
# built from the client's IG folder when no hand-authored classification
# exists. Filename-pattern roles; client-name containment for brand_text;
# testimonial/card markers; never fabricates an appeal score.
# ---------------------------------------------------------------------------

def _mk_ig_folder(tmp_path, files: list[str]) -> Path:
    folder = tmp_path / "ig"
    folder.mkdir(parents=True, exist_ok=True)
    for name in files:
        (folder / name).touch()
    return folder


def test_folder_manifest_classifies_roles_and_clients(tmp_path) -> None:
    from stages.plan_social import build_manifest_from_folder

    folder = _mk_ig_folder(tmp_path, [
        "handle_avatar.jpg",              # founder portrait (avatar marker)
        "handle_stage_1.jpg",             # speaking (stage keyword)
        "handle_office_2.jpg",            # working (office keyword)
        "handle_goldman_3.jpg",           # client_photo (client name in file)
        "handle_testimonial_frese_4.jpg", # testimonial card (marker)
        "handle_random_5.jpg",            # generic post
    ])
    manifest = build_manifest_from_folder(folder, handle="handle")
    by_path = {a.path: a for a in manifest.assets}
    assert by_path["handle_avatar.jpg"].role == "founder_portrait"
    assert by_path["handle_stage_1.jpg"].role == "speaking"
    assert by_path["handle_office_2.jpg"].role == "working"
    assert by_path["handle_goldman_3.jpg"].role in ("client_photo", "content_card")
    assert by_path["handle_testimonial_frese_4.jpg"].is_testimonial_card is True
    assert by_path["handle_goldman_3.jpg"].brand_text.lower() == "goldman"
    assert manifest.handle == "handle"


def test_folder_manifest_empty_folder_is_empty_manifest(tmp_path) -> None:
    from stages.plan_social import build_manifest_from_folder

    folder = _mk_ig_folder(tmp_path, [])
    manifest = build_manifest_from_folder(folder, handle="x")
    assert manifest.assets == []


def test_folder_manifest_plans_social_placements(tmp_path) -> None:
    """The derived manifest feeds plan_social end-to-end: a client folder
    with a stage shot + office shot + a Goldman photo produces real
    bindings (scene breather + case-study post), not zero."""
    from stages.plan_social import build_manifest_from_folder, plan_social

    folder = _mk_ig_folder(tmp_path, [
        "jf_avatar.jpg",
        "jf_stage_1.jpg",
        "jf_office_2.jpg",
        "jf_goldman_3.jpg",
        "jf_testimonial_4.jpg",
    ])
    manifest = build_manifest_from_folder(folder, handle="jf")
    plan = plan_social(
        manifest,
        case_clients={7: "Goldman Tax", 9: "Cordes Consulting"},
        breather_slots=[6, 11, 17],
        about_slot=3, fazit_slot=18,
        founder_name="Jousef", founder_role="Gründer",
        asset_exists=lambda rel: (folder / rel).exists(),
        enable_profile_grid=False,
    )
    assert plan.bindings, "derived manifest must produce placements"
    kinds = {b.element for b in plan.bindings}
    assert "scene_breather" in kinds
