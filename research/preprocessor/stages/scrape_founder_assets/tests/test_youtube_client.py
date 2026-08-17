"""Tests for YouTubeClient — the data-bounding FILTER that collects founder
imagery WITHOUT ever downloading long videos.

Network-free: a FAKE runner records every call (channel_info / download_image
/ download_short / sample_frames) and returns scripted data. The hard
requirement under test is the filter: only shorts with duration <= 90s, and
at most MAX_SHORTS of them, are ever passed to download_short/sample_frames;
long videos contribute only their thumbnail.

Brand-agnostic: shapes + behaviour only, no client value.
"""
from __future__ import annotations

from typing import List, Tuple

import pytest

from stages.scrape_founder_assets.clients_youtube import (
    MAX_SHORTS,
    MAX_SHORT_SECONDS,
    MAX_THUMBNAILS,
    YouTubeClient,
    _local_name_for_url,
)
from stages.scrape_founder_assets.models import ScrapeResult


def test_thumbnail_urls_get_unique_local_names():
    """Regression: every YouTube thumbnail is ``.../vi/<id>/hqdefault.jpg`` so
    basenames collide — naming by basename made each thumbnail overwrite the
    last. The unique-name helper must disambiguate same-basename URLs."""
    a = _local_name_for_url("https://i.ytimg.com/vi/AAA/hqdefault.jpg")
    b = _local_name_for_url("https://i.ytimg.com/vi/BBB/hqdefault.jpg")
    assert a != b
    assert a.endswith("hqdefault.jpg") and b.endswith("hqdefault.jpg")
    # stable for the same url
    assert a == _local_name_for_url("https://i.ytimg.com/vi/AAA/hqdefault.jpg")


# --------------------------------------------------------------------------
# Fake runner — records every external call; returns scripted data.
# --------------------------------------------------------------------------
class FakeRunner:
    def __init__(self, info: dict | None = None, *, info_raises: BaseException | None = None):
        self._info = info or {}
        self._info_raises = info_raises
        # call logs
        self.channel_info_calls: List[str] = []
        self.download_image_calls: List[Tuple[str, str]] = []
        self.download_short_calls: List[str] = []  # video_id
        self.sample_frames_calls: List[str] = []  # video_path

    def channel_info(self, url: str) -> dict:
        self.channel_info_calls.append(url)
        if self._info_raises is not None:
            raise self._info_raises
        return self._info

    def download_image(self, image_url: str, dest: str):
        self.download_image_calls.append((image_url, dest))
        # scripted stub file + dims
        return (dest, 640, 360)

    def download_short(self, video_id: str, dest: str):
        self.download_short_calls.append(video_id)
        return f"{dest}/{video_id}.mp4"

    def sample_frames(self, video_path: str, dest_dir: str, every_sec: int = 2):
        self.sample_frames_calls.append(video_path)
        return [
            (f"{dest_dir}/frame_0.png", 1080, 1920),
            (f"{dest_dir}/frame_1.png", 1080, 1920),
        ]


def _scripted_info() -> dict:
    return {
        "avatar_url": "https://img/avatar.png",
        "banner_url": "https://img/banner.png",
        "videos": [
            {"id": "s30", "title": "short 30", "duration_sec": 30, "is_short": True, "thumbnail_url": "https://img/s30.jpg"},
            {"id": "s75", "title": "short 75", "duration_sec": 75, "is_short": True, "thumbnail_url": "https://img/s75.jpg"},
            {"id": "s120", "title": "over filter", "duration_sec": 120, "is_short": True, "thumbnail_url": "https://img/s120.jpg"},
            {"id": "long600", "title": "long talk", "duration_sec": 600, "is_short": False, "thumbnail_url": "https://img/long600.jpg"},
        ],
    }


def _make(tmp_path, info=None, **kw):
    runner = FakeRunner(info if info is not None else _scripted_info(), **kw)
    client = YouTubeClient(runner=runner, scratch_dir=str(tmp_path))
    return client, runner


# --------------------------------------------------------------------------
# 1. avatar + banner + thumbnails, no video download for any thumbnail
# --------------------------------------------------------------------------
def test_collects_avatar_banner_thumbnails_without_video_download(tmp_path):
    client, runner = _make(tmp_path)
    result = client.fetch_candidates("https://youtube/c/x", limit=12)

    assert isinstance(result, ScrapeResult)
    assert result.source == "youtube"
    assert result.status == "ok"

    kinds = [c.kind for c in result.candidates]
    assert "avatar" in kinds
    assert "banner" in kinds
    # one thumbnail per video (4 videos)
    assert kinds.count("thumbnail") == 4

    # download_image used for avatar + banner + every thumbnail
    assert len(runner.download_image_calls) == 2 + 4

    # The thumbnail/avatar/banner collection NEVER touches video tooling for
    # videos that are not eligible shorts.
    # (download_short only for the eligible shorts — asserted fully in test 2)
    assert runner.sample_frames_calls != []  # frames produced for eligible shorts
    # but sample_frames is only ever called on downloaded shorts:
    assert len(runner.sample_frames_calls) == len(runner.download_short_calls)


# --------------------------------------------------------------------------
# 2. download_short ONLY for shorts within the duration filter (<=90s)
# --------------------------------------------------------------------------
def test_downloads_only_shorts_within_duration_filter(tmp_path):
    client, runner = _make(tmp_path)
    result = client.fetch_candidates("https://youtube/c/x")

    # exactly the 30s and 75s shorts — not 120s, not 600s
    assert set(runner.download_short_calls) == {"s30", "s75"}
    assert "s120" not in runner.download_short_calls
    assert "long600" not in runner.download_short_calls

    # never more than the cap
    assert len(runner.download_short_calls) <= MAX_SHORTS

    # every downloaded short was within the duration filter
    by_id = {v["id"]: v for v in _scripted_info()["videos"]}
    for vid in runner.download_short_calls:
        assert by_id[vid]["duration_sec"] <= MAX_SHORT_SECONDS

    # frame candidates produced for those shorts
    frame_cands = [c for c in result.candidates if c.kind == "frame"]
    assert frame_cands  # at least some frames
    assert result.status == "ok"


def test_shorts_with_unknown_duration_are_eligible(tmp_path):
    """The flat channel listing often omits duration (None). A /shorts-tab clip
    with unknown duration must still be downloaded (trust the shorts flag);
    only a KNOWN over-length clip is excluded."""
    info = {
        "avatar_url": None,
        "banner_url": None,
        "videos": [
            {"id": "snone", "title": "no-dur short", "duration_sec": None, "is_short": True, "thumbnail_url": "https://img/snone.jpg"},
            {"id": "s200", "title": "known over-length", "duration_sec": 200, "is_short": True, "thumbnail_url": "https://img/s200.jpg"},
        ],
    }
    client, runner = _make(tmp_path, info=info)
    client.fetch_candidates("https://youtube/c/x")
    assert "snone" in runner.download_short_calls       # unknown duration -> trusted
    assert "s200" not in runner.download_short_calls     # known over-length -> excluded


# --------------------------------------------------------------------------
# 3. long video -> thumbnail only, never download_short/sample_frames
# --------------------------------------------------------------------------
def test_long_video_thumbnail_only(tmp_path):
    client, runner = _make(tmp_path)
    result = client.fetch_candidates("https://youtube/c/x")

    # the 600s long video contributed a thumbnail candidate
    thumb_metas = [c.meta.get("video_id") for c in result.candidates if c.kind == "thumbnail"]
    assert "long600" in thumb_metas

    # but no short download / frame sampling referencing it
    assert "long600" not in runner.download_short_calls
    # sample_frames is called with a video_path derived from download_short;
    # since long600 was never downloaded, no frame path can reference it.
    assert all("long600" not in vp for vp in runner.sample_frames_calls)
    # also the 120s "short" (over filter) is treated as not-a-short for download
    assert "s120" not in runner.download_short_calls


# --------------------------------------------------------------------------
# 4. channel_info failure is graceful -> status "error", no exception
# --------------------------------------------------------------------------
def test_channel_info_failure_is_graceful(tmp_path):
    client, runner = _make(tmp_path, info_raises=RuntimeError("yt-dlp exploded"))

    # must NOT propagate
    result = client.fetch_candidates("https://youtube/c/x")

    assert isinstance(result, ScrapeResult)
    assert result.source == "youtube"
    assert result.status == "error"
    assert result.reason  # some reason set
    assert result.candidates == []
    # no downstream tooling touched
    assert runner.download_image_calls == []
    assert runner.download_short_calls == []
    assert runner.sample_frames_calls == []


# --------------------------------------------------------------------------
# 5. no videos -> empty (graceful)
# --------------------------------------------------------------------------
def test_no_videos_is_empty(tmp_path):
    info = {"avatar_url": None, "banner_url": None, "videos": []}
    client, runner = _make(tmp_path, info=info)

    result = client.fetch_candidates("https://youtube/c/x")
    assert result.status == "empty"
    assert result.candidates == []
    assert runner.download_short_calls == []


# --------------------------------------------------------------------------
# 6. constants sanity
# --------------------------------------------------------------------------
def test_filter_constants():
    assert MAX_SHORT_SECONDS == 90
    assert MAX_SHORTS == 4
    assert MAX_THUMBNAILS == 12
