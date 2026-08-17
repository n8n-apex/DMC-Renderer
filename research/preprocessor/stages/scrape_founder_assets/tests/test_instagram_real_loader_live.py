"""Env-gated LIVE Instagram test — hits the real public web_profile_info API.

Skipped unless ``IG_LIVE_TEST_URL`` is set (a public IG profile URL), so the
default unit suite stays network-free. Proves the root-cause fix: anonymous
``web_profile_info`` returns a real profile pic + image posts where instaloader's
graphql path 403s.

Run:  IG_LIVE_TEST_URL=https://www.instagram.com/<handle>/ \
        python -m pytest stages/scrape_founder_assets/tests/test_instagram_real_loader_live.py -q -s
"""
from __future__ import annotations

import os

import pytest

from stages.scrape_founder_assets.clients_instagram import InstagramClient

_URL = os.environ.get("IG_LIVE_TEST_URL")


@pytest.mark.skipif(not _URL, reason="set IG_LIVE_TEST_URL to run the live IG test")
def test_real_public_profile_yields_candidates(tmp_path):
    client = InstagramClient(scratch_dir=str(tmp_path))
    result = client.fetch_candidates(_URL, limit=12)

    print(f"\nIG live status={result.status} reason={result.reason}")
    for c in result.candidates:
        print(f"  {c.kind:7} {c.width}x{c.height} {c.local_path}")

    # The fix must produce real candidates (never the old false "blocked").
    assert result.status == "ok", f"expected ok, got {result.status}: {result.reason}"
    assert any(c.kind == "avatar" for c in result.candidates), "no profile pic"
    assert any(c.kind == "post" for c in result.candidates), "no image posts"
