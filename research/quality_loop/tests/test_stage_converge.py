"""Tests for Stage 9 (``stage_converge``).

ALL OFFLINE: ``build_report`` is a pure function over a hand-built ``DeckResult``;
``run_stage`` is driven with an injected fake ``converge_deck`` so the wiring is
proven with no render and no network.
"""
from __future__ import annotations

import json

from brain import DeckResult, PageResult
from conductor import Fix
from stage_converge import build_report, run_stage


def _page(idx, st, cleared, reward, fixes, flags):
    return PageResult(
        page_index=idx,
        st_type=st,
        cleared=cleared,
        best_reward=reward,
        best_iteration=0,
        iterations=[],
        fixes_applied=fixes,
        flags=flags,
        shipped_best=True,
        best_artifacts=None,
    )


def _deck():
    p0 = _page(0, "ST-01", True, 42.0, [], [])
    p1 = _page(
        1,
        "ST-07A",
        False,
        18.0,
        [Fix("N08", "renderer", "density", "balanced", "density compact->balanced")],
        [
            "N01 missing client photo -> asset_gen",
            "N08 residual after density exhausted -> renderer capability gap",
        ],
    )
    deck_flags = [
        {"page_index": 1, "st_type": "ST-07A",
         "flag": "N01 missing client photo -> asset_gen"},
        {"page_index": 1, "st_type": "ST-07A",
         "flag": "N08 residual after density exhausted -> renderer capability gap"},
    ]
    return DeckResult(pages=[p0, p1], deck_flags=deck_flags, cleared_count=1, total=2)


def test_build_report_structure():
    r = build_report(_deck())
    assert r["total"] == 2 and r["cleared_count"] == 1
    assert r["deck_cleared"] is False
    assert r["deck_reward"] == 60.0

    p1 = r["pages"][1]
    assert p1["st_type"] == "ST-07A" and p1["cleared"] is False
    assert p1["fixes_applied"][0]["defect_id"] == "N08"
    assert p1["fixes_applied"][0]["knob"] == "density"
    # N01 routes to asset_gen; the residual N08 to renderer.
    assert p1["residual_by_owner"]["asset_gen"]
    assert p1["residual_by_owner"]["renderer"]
    assert not p1["residual_by_owner"]["preprocessor"]
    # deck-level flag ledger grouped by owner.
    assert r["flags_by_owner"]["asset_gen"][0]["page_index"] == 1
    assert r["flags_by_owner"]["renderer"][0]["st_type"] == "ST-07A"


def test_run_stage_writes_report(tmp_path):
    calls = {}

    def fake_converge_deck(
        package_dir, *, out_root, max_iterations, vis_client, page_indices, **kw
    ):
        calls["out_root"] = out_root
        calls["vis_client"] = vis_client
        calls["page_indices"] = page_indices
        calls["max_iterations"] = max_iterations
        return _deck()

    out = tmp_path / "out"
    report = run_stage(
        "/nonexistent/pkg",
        out,
        use_vis=False,
        max_iterations=2,
        page_indices=[0, 1],
        converge_deck_fn=fake_converge_deck,
    )

    written = json.loads((out / "convergence_report.json").read_text())
    assert written == report
    assert (out / "convergence_report.txt").exists()
    # use_vis=False -> no client constructed or passed through.
    assert calls["vis_client"] is None
    assert calls["page_indices"] == [0, 1]
    assert calls["max_iterations"] == 2
