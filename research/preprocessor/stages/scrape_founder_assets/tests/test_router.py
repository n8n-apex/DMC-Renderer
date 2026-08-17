"""Tests for router.py — pure role -> report-element routing (Task 3).

The router takes ``(Candidate, det_score, AssetJudgement)`` triples and places
each asset into the report element where it adds the most appeal, with DET
cross-checks (a face element must actually have a frontal print-capable face),
best-appeal-first ordering, source de-dup, and flag-on-empty (never fabricated).

Pure: no I/O, no network. ``det_score`` is a stand-in here; in production it is
``selector.CandidateScore`` — the router accesses it via getattr to stay robust
to both shapes.
"""
from __future__ import annotations

from stages.scrape_founder_assets.models import AssetJudgement, Candidate
from stages.scrape_founder_assets.router import (
    ELEMENT_PRIORITY,
    ROLE_TO_ELEMENTS,
    route_assets,
)


def _c(p, src="instagram"):
    return Candidate(source=src, kind="post", local_path=p, width=1080, height=1350)


class _Det:  # stand-in DET score
    def __init__(self, frontal=True, pc=True, faces=1):
        self.frontal = frontal
        self.print_capable = pc
        self.faces = faces


def test_routes_by_role_best_appeal_first_with_dedup():
    items = [
        (_c("/p1.jpg", src="a"), _Det(), AssetJudgement(role="founder_portrait", visual_appeal=3)),
        (_c("/p2.jpg", src="b"), _Det(), AssetJudgement(role="founder_portrait", visual_appeal=2)),
        (_c("/w1.jpg", src="c"), _Det(), AssetJudgement(role="founder_working", visual_appeal=3)),
    ]
    out = route_assets(items)
    by_el = {r.element: r for r in out}
    assert by_el["cover_hero"].path == "/p1.jpg"  # best-appeal portrait
    assert by_el["team"].path == "/p2.jpg"  # de-dup -> 2nd portrait falls back to team
    assert by_el["device_mockup"].path == "/w1.jpg"  # working photo -> device/working role
    assert by_el["cover_hero"].path != by_el["team"].path


def test_face_element_requires_a_frontal_face():
    # VIS says portrait but DET says NO frontal face -> NOT placed into a face slot
    items = [
        (
            _c("/x.jpg"),
            _Det(frontal=False, pc=False, faces=0),
            AssetJudgement(role="founder_portrait", visual_appeal=3),
        )
    ]
    out = {r.element: r for r in route_assets(items)}
    assert out["cover_hero"].status == "flagged"


def test_frontal_subprint_portrait_still_fills_hero():
    # A frontal portrait that is slightly sub-print (e.g. a 990px studio avatar)
    # MUST still fill the hero (print-capability is a ranking preference, not a
    # hard gate) — the restorer upscales it. Regression guard for the router
    # over-flagging the founder hero.
    c = Candidate(source="youtube", kind="avatar", local_path="/a990.jpg", width=990, height=990)
    items = [(c, _Det(frontal=True, pc=False, faces=1),
              AssetJudgement(role="founder_portrait", visual_appeal=3))]
    out = {r.element: r for r in route_assets(items)}
    assert out["cover_hero"].status == "filled" and out["cover_hero"].path == "/a990.jpg"


def test_empty_pool_flags_never_fabricates():
    out = route_assets([])
    assert all(r.status == "flagged" and r.path is None for r in out)
    # one outcome per element in priority order
    assert [r.element for r in out] == list(ELEMENT_PRIORITY)


def test_role_to_elements_map_per_spec():
    assert ROLE_TO_ELEMENTS["founder_portrait"] == ["cover_hero", "team"]
    assert ROLE_TO_ELEMENTS["founder_working"] == ["device_mockup"]
    assert ROLE_TO_ELEMENTS["founder_speaking"] == ["scene"]
    assert ROLE_TO_ELEMENTS["group_team"] == ["team"]
    assert ROLE_TO_ELEMENTS["lifestyle"] == ["scene"]
    assert ROLE_TO_ELEMENTS["content_card"] == ["proof"]
    assert ROLE_TO_ELEMENTS["logo"] == ["logo"]


def test_low_appeal_is_not_placed():
    # appeal below the minimum (2) is rejected even with a good DET face.
    items = [
        (_c("/lo.jpg"), _Det(), AssetJudgement(role="founder_portrait", visual_appeal=1))
    ]
    out = {r.element: r for r in route_assets(items)}
    assert out["cover_hero"].status == "flagged"


def test_works_with_real_candidatescore_shape():
    # The real selector.CandidateScore has has_face/frontal/face_area_frac/
    # width/height but NO .print_capable or .faces — the router must cope.
    from stages.scrape_founder_assets.selector import CandidateScore

    big = CandidateScore(
        has_face=True, frontal=True, face_area_frac=0.2, sharpness=500.0,
        width=2000, height=2500,
    )
    items = [(_c("/real.jpg"), big, AssetJudgement(role="founder_portrait", visual_appeal=3))]
    out = {r.element: r for r in route_assets(items)}
    assert out["cover_hero"].status == "filled" and out["cover_hero"].path == "/real.jpg"

    # A sub-print real score (long edge < 1000) is STILL eligible for a face
    # element (print-capability is a ranking preference, not a hard gate); the
    # restorer upscales it. It must be FILLED, not flagged.
    small = CandidateScore(
        has_face=True, frontal=True, face_area_frac=0.2, sharpness=500.0,
        width=320, height=320,
    )
    cs = Candidate(source="instagram", kind="avatar", local_path="/small.jpg", width=320, height=320)
    items2 = [(cs, small, AssetJudgement(role="founder_portrait", visual_appeal=3))]
    out2 = {r.element: r for r in route_assets(items2)}
    assert out2["cover_hero"].status == "filled" and out2["cover_hero"].path == "/small.jpg"


def test_hero_prefers_higher_resolution_portrait(tmp_path):
    # Two frontal portraits, both sub-print; the hero must take the
    # higher-resolution one (990 > 320), and the 2nd portrait falls back to team
    # (team has no frontal gate, so a solo portrait is fine when no group exists).
    big = Candidate(source="youtube", kind="avatar", local_path="/big990.jpg", width=990, height=990)
    small = Candidate(source="instagram", kind="avatar", local_path="/small320.jpg", width=320, height=320)
    items = [
        (small, _Det(frontal=True, pc=False, faces=1), AssetJudgement(role="founder_portrait", visual_appeal=3)),
        (big, _Det(frontal=True, pc=False, faces=1), AssetJudgement(role="founder_portrait", visual_appeal=3)),
    ]
    out = {r.element: r for r in route_assets(items)}
    assert out["cover_hero"].path == "/big990.jpg"      # higher-res to the hero
    assert out["team"].path == "/small320.jpg"  # de-dup -> 2nd portrait to team


def test_group_team_photo_beats_fallback_avatar_for_team(tmp_path):
    # THE BUG REGRESSION GUARD: a 990 frontal portrait, a 320 frontal portrait,
    # AND a 1080 group_team photo. cover_hero must take the 990 portrait; team
    # must take the GROUP photo (1080, print-capable beats the sub-print 320 on
    # the rank key, even though group has no frontal gate); the 320 avatar goes
    # UNUSED (no element left to claim it). This is the correct renderer model:
    # the soft 320 founder avatar must NOT claim team.jpg over the real group.
    portrait990 = Candidate(source="youtube", kind="avatar", local_path="/p990.jpg", width=990, height=990)
    portrait320 = Candidate(source="instagram", kind="avatar", local_path="/p320.jpg", width=320, height=320)
    group1080 = Candidate(source="instagram", kind="post", local_path="/group1080.jpg", width=1080, height=1080)
    items = [
        (portrait990, _Det(frontal=True, pc=False, faces=1), AssetJudgement(role="founder_portrait", visual_appeal=3)),
        (portrait320, _Det(frontal=True, pc=False, faces=1), AssetJudgement(role="founder_portrait", visual_appeal=3)),
        (group1080, _Det(frontal=False, pc=True, faces=3), AssetJudgement(role="group_team", visual_appeal=3)),
    ]
    routed = route_assets(items)
    out = {r.element: r for r in routed}
    assert out["cover_hero"].path == "/p990.jpg"   # best frontal portrait -> hero
    assert out["team"].path == "/group1080.jpg"    # the GROUP photo wins team, not the 320 avatar
    # the 320 avatar is unused — no path in any element points to it
    used = {r.path for r in routed if r.path}
    assert "/p320.jpg" not in used


def test_team_prefers_two_or_more_faces():
    items = [
        (_c("/solo.jpg", src="a"), _Det(faces=1), AssetJudgement(role="group_team", visual_appeal=2)),
        (_c("/group.jpg", src="b"), _Det(faces=3), AssetJudgement(role="group_team", visual_appeal=2)),
    ]
    out = {r.element: r for r in route_assets(items)}
    assert out["team"].path == "/group.jpg"
