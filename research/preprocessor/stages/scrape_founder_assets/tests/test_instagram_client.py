"""Tests for InstagramClient — best-effort, GRACEFUL collection of founder
imagery from public IG profiles.

Network-free: a FAKE loader records every call and returns scripted data. The
hard requirements under test:
  * profile pic -> avatar candidate; recent image posts -> post candidates;
  * VIDEO posts (reels) are skipped for v1;
  * username parsed from a variety of IG URL shapes;
  * a blocked / 429 / login-redirect error NEVER raises -> status "blocked";
  * any other unexpected error NEVER raises -> status "error";
  * one failing post download does not sink the others.

Brand-agnostic: shapes + behaviour only, no client value.
"""
from __future__ import annotations

from typing import List, Tuple

import pytest

from stages.scrape_founder_assets.clients_instagram import (
    InstagramBlocked,
    InstagramClient,
    _username_from_url,
)
from stages.scrape_founder_assets.models import ScrapeResult


# --------------------------------------------------------------------------
# Fake loader — records every external call; returns scripted data.
# --------------------------------------------------------------------------
class FakeLoader:
    def __init__(
        self,
        *,
        pic=("avatar.jpg", 320, 320),
        posts=None,
        pic_raises: BaseException | None = None,
        posts_raises: BaseException | None = None,
        bad_post_indices: tuple[int, ...] = (),
    ):
        self._pic = pic
        self._posts = posts if posts is not None else []
        self._pic_raises = pic_raises
        self._posts_raises = posts_raises
        self._bad_post_indices = set(bad_post_indices)
        # call log: each entry is (method, *args)
        self.calls: List[Tuple] = []

    def profile_pic(self, username: str, dest: str):
        self.calls.append(("profile_pic", username, dest))
        if self._pic_raises is not None:
            raise self._pic_raises
        return self._pic

    def recent_image_posts(self, username: str, dest_dir: str, limit: int):
        self.calls.append(("recent_image_posts", username, dest_dir, limit))
        if self._posts_raises is not None:
            raise self._posts_raises
        # Model a loader that swallows per-post download failures internally:
        # bad indices simply never make it into the returned list, while the
        # good ones still come through.
        out = []
        for i, post in enumerate(self._posts):
            if i in self._bad_post_indices:
                continue  # this post's download failed, loader skipped it
            out.append(post)
        return out


def _make(tmp_path, **kw):
    loader = FakeLoader(**kw)
    client = InstagramClient(loader=loader, scratch_dir=str(tmp_path))
    return client, loader


# --------------------------------------------------------------------------
# 1. avatar + image posts collected, video posts skipped
# --------------------------------------------------------------------------
def test_collects_avatar_and_image_posts_skips_video(tmp_path):
    posts = [
        ("p0.jpg", 1080, 1080, False),  # image
        ("p1.mp4", 1080, 1920, True),   # video -> skipped
        ("p2.jpg", 1080, 1350, False),  # image
    ]
    client, loader = _make(tmp_path, posts=posts)
    result = client.fetch_candidates("https://instagram.com/foo/", limit=12)

    assert isinstance(result, ScrapeResult)
    assert result.source == "instagram"
    assert result.status == "ok"

    kinds = [c.kind for c in result.candidates]
    assert kinds.count("avatar") == 1
    assert kinds.count("post") == 2  # video skipped

    post_paths = [c.local_path for c in result.candidates if c.kind == "post"]
    assert "p0.jpg" in post_paths
    assert "p2.jpg" in post_paths
    assert "p1.mp4" not in post_paths  # the video was skipped

    # calls were recorded against the loader
    methods = [c[0] for c in loader.calls]
    assert "profile_pic" in methods
    assert "recent_image_posts" in methods
    # username was parsed and passed through
    assert all(c[1] == "foo" for c in loader.calls)


# --------------------------------------------------------------------------
# 2. username parsing from various URL shapes
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "url",
    [
        "https://www.instagram.com/foo/",
        "instagram.com/foo",
        "https://instagram.com/foo/?hl=en",
        "https://www.instagram.com/foo",
        "http://instagram.com/foo/",
    ],
)
def test_username_parsed_from_url(url):
    assert _username_from_url(url) == "foo"


# --------------------------------------------------------------------------
# 3. blocked / 429 / login-redirect is graceful -> status "blocked"
# --------------------------------------------------------------------------
def test_blocked_is_graceful(tmp_path):
    client, loader = _make(tmp_path, pic_raises=InstagramBlocked("login required"))

    result = client.fetch_candidates("https://instagram.com/foo/")

    assert isinstance(result, ScrapeResult)
    assert result.source == "instagram"
    assert result.status == "blocked"
    assert result.reason  # some reason set
    assert result.candidates == []


def test_blocked_by_message_substring_is_graceful(tmp_path):
    # An arbitrary exception whose message looks like a block / rate limit.
    client, loader = _make(tmp_path, pic_raises=RuntimeError("HTTP 429 Too Many Requests"))

    result = client.fetch_candidates("https://instagram.com/foo/")
    assert result.status == "blocked"
    assert result.candidates == []


# --------------------------------------------------------------------------
# 4. unexpected error is graceful -> status "error"
# --------------------------------------------------------------------------
def test_unexpected_error_is_graceful(tmp_path):
    client, loader = _make(tmp_path, pic_raises=ValueError("something weird"))

    result = client.fetch_candidates("https://instagram.com/foo/")

    assert isinstance(result, ScrapeResult)
    assert result.status == "error"
    assert result.reason
    assert result.candidates == []


# --------------------------------------------------------------------------
# 5. a per-post failure does not sink the others
# --------------------------------------------------------------------------
def test_per_post_failure_does_not_sink_others(tmp_path):
    posts = [
        ("p0.jpg", 1080, 1080, False),
        ("p1.jpg", 1080, 1080, False),  # this one blows up
        ("p2.jpg", 1080, 1080, False),
    ]
    client, loader = _make(tmp_path, posts=posts, bad_post_indices=(1,))

    result = client.fetch_candidates("https://instagram.com/foo/")

    assert result.status == "ok"
    post_paths = [c.local_path for c in result.candidates if c.kind == "post"]
    # the good ones survived
    assert "p0.jpg" in post_paths
    assert "p2.jpg" in post_paths
    # avatar still collected too
    assert any(c.kind == "avatar" for c in result.candidates)


# --------------------------------------------------------------------------
# 6. empty profile (no pic, no posts) -> empty
# --------------------------------------------------------------------------
def test_empty_profile_is_empty(tmp_path):
    client, loader = _make(tmp_path, pic=None, posts=[])

    result = client.fetch_candidates("https://instagram.com/foo/")
    assert result.status == "empty"
    assert result.candidates == []
