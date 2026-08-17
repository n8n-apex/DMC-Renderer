"""Tests for the REAL Instagram loader's network-free logic.

Root cause (June 2026): instaloader 4.15.1's ``Profile.from_username`` hits
``https://www.instagram.com/graphql/query`` which returns **403 Forbidden** for
anonymous clients, and instaloader then mis-reports it as "Profile does not
exist." The fix is to fetch Instagram's public ``web_profile_info`` API with an
``X-IG-App-ID`` header, which returns the profile pic + the first 12 timeline
media for any PUBLIC profile, free and login-free.

These tests cover the loader's pure parsing + HTTP-status mapping with NO
network: a fake ``http_get`` returns a scripted ``web_profile_info`` payload and
a fake ``download_image`` records the URLs it was asked to fetch.

Brand-agnostic: the fixture uses example.com URLs and a placeholder handle.
"""
from __future__ import annotations

import json

import pytest

from stages.scrape_founder_assets.clients_instagram import (
    IG_APP_ID,
    InstagramBlocked,
    RealLoader,
    _extract_image_posts,
    _extract_profile_pic_url,
)

# A small, brand-agnostic web_profile_info "user" payload exercising: a plain
# image post, a video post (must be skipped), and a sidecar carousel with one
# image child + one video child + one image child.
SAMPLE_USER = {
    "profile_pic_url": "https://cdn.example/pic_low.jpg",
    "profile_pic_url_hd": "https://cdn.example/pic_hd.jpg",
    "edge_owner_to_timeline_media": {
        "edges": [
            {
                "node": {
                    "__typename": "GraphImage",
                    "shortcode": "AAA",
                    "is_video": False,
                    "display_url": "https://cdn.example/aaa.jpg",
                    "dimensions": {"width": 1080, "height": 1350},
                }
            },
            {
                "node": {
                    "__typename": "GraphVideo",
                    "shortcode": "BBB",
                    "is_video": True,
                    "display_url": "https://cdn.example/bbb.jpg",
                    "dimensions": {"width": 1080, "height": 1920},
                }
            },
            {
                "node": {
                    "__typename": "GraphSidecar",
                    "shortcode": "CCC",
                    "is_video": False,
                    "dimensions": {"width": 1080, "height": 1080},
                    "edge_sidecar_to_children": {
                        "edges": [
                            {
                                "node": {
                                    "is_video": False,
                                    "display_url": "https://cdn.example/ccc_1.jpg",
                                    "dimensions": {"width": 1080, "height": 1080},
                                }
                            },
                            {
                                "node": {
                                    "is_video": True,
                                    "display_url": "https://cdn.example/ccc_2.jpg",
                                    "dimensions": {"width": 1080, "height": 1080},
                                }
                            },
                            {
                                "node": {
                                    "is_video": False,
                                    "display_url": "https://cdn.example/ccc_3.jpg",
                                    "dimensions": {"width": 1080, "height": 1080},
                                }
                            },
                        ]
                    },
                }
            },
        ]
    },
}


def _payload(user=SAMPLE_USER) -> bytes:
    return json.dumps({"data": {"user": user}}).encode("utf-8")


# --------------------------------------------------------------------------
# pure helpers
# --------------------------------------------------------------------------
def test_profile_pic_prefers_hd():
    assert _extract_profile_pic_url(SAMPLE_USER) == "https://cdn.example/pic_hd.jpg"


def test_profile_pic_falls_back_to_standard():
    user = {"profile_pic_url": "https://cdn.example/pic_low.jpg"}
    assert _extract_profile_pic_url(user) == "https://cdn.example/pic_low.jpg"


def test_profile_pic_none_when_absent():
    assert _extract_profile_pic_url({}) is None


def test_extract_image_posts_skips_video_and_expands_sidecar():
    posts = _extract_image_posts(SAMPLE_USER, limit=12)
    urls = [p["display_url"] for p in posts]
    # video post BBB skipped; sidecar CCC expands to its two IMAGE children
    # (the video child ccc_2 is skipped).
    assert urls == [
        "https://cdn.example/aaa.jpg",
        "https://cdn.example/ccc_1.jpg",
        "https://cdn.example/ccc_3.jpg",
    ]
    # dimensions carried through
    assert posts[0]["width"] == 1080 and posts[0]["height"] == 1350


def test_extract_image_posts_respects_limit():
    posts = _extract_image_posts(SAMPLE_USER, limit=1)
    assert [p["display_url"] for p in posts] == ["https://cdn.example/aaa.jpg"]


# --------------------------------------------------------------------------
# RealLoader HTTP-status mapping (network-free via injected http_get)
# --------------------------------------------------------------------------
def _loader(status=200, body=None, downloads=None):
    """Build a RealLoader with a fake http_get + download_image."""
    if body is None:
        body = _payload()
    seen_headers = {}

    def fake_http_get(url, headers):
        seen_headers.update(headers)
        return status, body

    def fake_download(url, local):
        if downloads is not None:
            downloads.append(url)
        return (local, 1080, 1080)

    loader = RealLoader(http_get=fake_http_get, download_image=fake_download)
    loader._seen_headers = seen_headers  # type: ignore[attr-defined]
    return loader


@pytest.mark.parametrize("status", [401, 403, 429])
def test_blocked_statuses_raise_instagram_blocked(status):
    loader = _loader(status=status, body=b"")
    with pytest.raises(InstagramBlocked):
        loader.profile_pic("founder", "/tmp")


def test_null_user_raises_blocked():
    loader = _loader(status=200, body=json.dumps({"data": {"user": None}}).encode())
    with pytest.raises(InstagramBlocked):
        loader.profile_pic("founder", "/tmp")


def test_sends_app_id_header():
    loader = _loader()
    loader.profile_pic("founder", "/tmp")
    assert loader._seen_headers.get("X-IG-App-ID") == IG_APP_ID


def test_profile_pic_downloads_hd(tmp_path):
    downloads: list[str] = []
    loader = _loader(downloads=downloads)
    result = loader.profile_pic("founder", str(tmp_path))
    assert result is not None
    assert downloads == ["https://cdn.example/pic_hd.jpg"]


def test_recent_image_posts_downloads_only_images(tmp_path):
    downloads: list[str] = []
    loader = _loader(downloads=downloads)
    out = loader.recent_image_posts("founder", str(tmp_path), limit=12)
    # all returned items are flagged not-video
    assert all(item[3] is False for item in out)
    assert downloads == [
        "https://cdn.example/aaa.jpg",
        "https://cdn.example/ccc_1.jpg",
        "https://cdn.example/ccc_3.jpg",
    ]


def test_sidecar_children_get_unique_local_paths(tmp_path):
    # ccc_1 and ccc_3 share shortcode "CCC"; their local paths must differ so
    # one carousel child does not overwrite another on disk.
    loader = _loader()  # default fake download returns the local path it is given
    out = loader.recent_image_posts("founder", str(tmp_path), limit=12)
    paths = [item[0] for item in out]
    assert len(paths) == len(set(paths)), f"duplicate local paths: {paths}"


def test_web_profile_info_cached_across_calls(tmp_path):
    calls = {"n": 0}

    def counting_get(url, headers):
        calls["n"] += 1
        return 200, _payload()

    loader = RealLoader(
        http_get=counting_get,
        download_image=lambda url, local: (local, 1080, 1080),
    )
    loader.profile_pic("founder", str(tmp_path))
    loader.recent_image_posts("founder", str(tmp_path), limit=12)
    # one HTTP round-trip serves both — the JSON is cached per username
    assert calls["n"] == 1
