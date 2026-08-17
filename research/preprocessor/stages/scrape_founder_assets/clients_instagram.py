"""Instagram channel client — best-effort collection of real founder imagery
from PUBLIC IG profiles via instaloader. IG posts are already images (no
ffmpeg needed), so this client is image-only.

IG scraping is fragile: public access is frequently met with login-redirects
and 429 rate-limit blocks. The hard requirement of this module is therefore
GRACEFUL FAILURE — it must NEVER crash the pipeline. Block/login/429-type
failures surface as ``status="blocked"``; anything else unexpected surfaces as
``status="error"``; an empty profile is ``status="empty"``. A failure fetching
ONE post is swallowed so the rest still come through.

Network access is abstracted behind a ``loader`` so tests are network-free:

    loader.profile_pic(username, dest) -> (path, w, h) | None
        download the profile picture.
    loader.recent_image_posts(username, dest_dir, limit)
        -> list[(path, w, h, is_video)]
        download recent posts' images; each item flags ``is_video``.

The real loader (``RealLoader``) fetches Instagram's public ``web_profile_info``
API anonymously (no login, no proxy) with an ``X-IG-App-ID`` header — the
anonymous path that still works in 2026 (instaloader's ``graphql/query`` path
is 403-gated for anonymous clients). It is only exercised end-to-end by an
env-gated real test; unit tests inject a fake.

Brand-agnostic: shapes + behaviour only, no client value.
"""
from __future__ import annotations

import os
from typing import List, Optional, Protocol, Tuple, runtime_checkable
from urllib.parse import urlparse

from .models import Candidate, ScrapeResult

_SOURCE = "instagram"

# Substrings that mark an exception as a "blocked"/login/rate-limit condition
# rather than a generic error. Lower-cased before matching.
_BLOCKED_MARKERS = ("429", "login", "redirect", "rate limit", "rate-limit", "blocked")

# Instagram's public web_profile_info API. For any PUBLIC profile this returns
# the profile pic + the first ~12 timeline media WITHOUT login, given the web
# app id header below. This is the anonymous-access path that still works in
# 2026; instaloader's graphql/query path is 403-gated for anonymous clients.
WEB_PROFILE_INFO_URL = (
    "https://i.instagram.com/api/v1/users/web_profile_info/?username={username}"
)
# The public Instagram web App ID. Not a secret/credential — it is the same
# constant the instagram.com web client sends on every anonymous request; the
# API rejects the call without it. (No client identity here — brand-agnostic.)
IG_APP_ID = "936619743392459"
# A realistic mobile UA reduces the chance of an anti-bot challenge.
_DEFAULT_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 "
    "Instagram 309.0.0.0 (iPhone15,2; iOS 17_0; en_US; en-US; scale=3.00)"
)
# HTTP statuses that mean "Instagram refused anonymous access" (vs a real error).
_BLOCKED_STATUSES = (401, 403, 429)


def _extract_profile_pic_url(user: dict) -> Optional[str]:
    """The best available profile-pic URL (HD preferred), or None."""
    if not user:
        return None
    return user.get("profile_pic_url_hd") or user.get("profile_pic_url")


def _extract_image_posts(user: dict, limit: int) -> List[dict]:
    """Flatten ``web_profile_info`` timeline media into image-post descriptors.

    Returns up to ``limit`` ``{shortcode, display_url, width, height}`` dicts.
    Video posts (reels) are skipped. A sidecar carousel is expanded into its
    individual IMAGE children (video children skipped) so a single free API
    call yields as much real imagery as possible.
    """
    if not user:
        return []
    edges = ((user.get("edge_owner_to_timeline_media") or {}).get("edges")) or []
    out: List[dict] = []
    for edge in edges:
        if len(out) >= limit:
            break
        node = edge.get("node") or {}
        sidecar = node.get("edge_sidecar_to_children")
        if sidecar:
            child_nodes = [c.get("node") or {} for c in (sidecar.get("edges") or [])]
        else:
            child_nodes = [node]
        for child in child_nodes:
            if len(out) >= limit:
                break
            if child.get("is_video"):
                continue
            url = child.get("display_url")
            if not url:
                continue
            dims = child.get("dimensions") or {}
            out.append(
                {
                    "shortcode": node.get("shortcode"),
                    "display_url": url,
                    "width": int(dims.get("width") or 0),
                    "height": int(dims.get("height") or 0),
                }
            )
    return out


class InstagramBlocked(Exception):
    """Raised by a loader when IG refuses public access (login / 429 / block).

    Surfaced by the client as ``status="blocked"`` — never propagated.
    """


@runtime_checkable
class InstagramLoader(Protocol):
    """External-tool boundary for the Instagram client (injectable for tests)."""

    def profile_pic(self, username: str, dest: str) -> Optional[Tuple[str, int, int]]:
        ...

    def recent_image_posts(
        self, username: str, dest_dir: str, limit: int
    ) -> List[Tuple[str, int, int, bool]]:
        ...


def _username_from_url(url: str) -> Optional[str]:
    """Parse the IG username from a profile URL.

    Handles ``https://www.instagram.com/foo/``, ``instagram.com/foo``,
    ``https://instagram.com/foo/?hl=en`` etc. Returns the first non-empty path
    segment, or ``None`` if none can be found.
    """
    if not url:
        return None
    candidate = url.strip()
    # urlparse needs a scheme to populate .path correctly; add one if missing.
    if "://" not in candidate:
        candidate = "//" + candidate
    parsed = urlparse(candidate)
    path = parsed.path or ""
    for segment in path.split("/"):
        if segment:
            return segment
    return None


def _is_blocked_error(exc: BaseException) -> bool:
    if isinstance(exc, InstagramBlocked):
        return True
    message = str(exc).lower()
    return any(marker in message for marker in _BLOCKED_MARKERS)


class InstagramClient:
    """Fetches founder-asset candidates from a public Instagram profile URL.

    Implements the ``ChannelClient`` protocol (``fetch_candidates``). All
    external work goes through the injected ``loader``; failures are caught and
    surfaced as a ``ScrapeResult`` (blocked / error / empty) rather than
    raising.
    """

    def __init__(
        self, loader: Optional[InstagramLoader] = None, *, scratch_dir: str = "/tmp"
    ):
        self.loader: InstagramLoader = loader if loader is not None else RealLoader()
        self.scratch_dir = scratch_dir

    # -- public API --------------------------------------------------------
    def fetch_candidates(self, url: str, *, limit: int = 12) -> ScrapeResult:
        username = _username_from_url(url)
        if not username:
            return ScrapeResult(
                source=_SOURCE,
                status="error",
                candidates=[],
                reason=f"could not parse username from url: {url!r}",
            )

        candidates: List[Candidate] = []

        # 1) profile picture -> avatar candidate.
        try:
            pic = self.loader.profile_pic(username, self.scratch_dir)
        except Exception as exc:  # graceful: never crash the pipeline
            return self._failure(exc, "profile_pic")
        if pic is not None:
            path, width, height = pic
            candidates.append(
                Candidate(
                    source=_SOURCE,
                    kind="avatar",
                    local_path=path,
                    width=width,
                    height=height,
                    meta={"username": username},
                )
            )

        # 2) recent posts -> post candidates (images only; videos skipped).
        try:
            posts = self.loader.recent_image_posts(username, self.scratch_dir, limit)
        except Exception as exc:  # graceful: never crash the pipeline
            # If we already have an avatar, keep it as a partial result rather
            # than discarding everything.
            return self._failure(exc, "recent_image_posts", partial=candidates)

        for post in posts or []:
            try:
                path, width, height, is_video = post
            except Exception:
                continue  # a malformed item must not sink the others
            if is_video:
                continue  # reels / videos are out for v1
            candidates.append(
                Candidate(
                    source=_SOURCE,
                    kind="post",
                    local_path=path,
                    width=width,
                    height=height,
                    meta={"username": username},
                )
            )

        if not candidates:
            return ScrapeResult(
                source=_SOURCE,
                status="empty",
                candidates=[],
                reason="no profile pic or image posts found",
            )

        return ScrapeResult(source=_SOURCE, status="ok", candidates=candidates)

    # -- helpers -----------------------------------------------------------
    def _failure(
        self,
        exc: BaseException,
        where: str,
        *,
        partial: Optional[List[Candidate]] = None,
    ) -> ScrapeResult:
        status = "blocked" if _is_blocked_error(exc) else "error"
        # A blocked condition means the source is unusable; drop any partial.
        candidates: List[Candidate] = [] if status == "blocked" else list(partial or [])
        return ScrapeResult(
            source=_SOURCE,
            status=status,
            candidates=candidates,
            reason=f"{where} failed: {exc}",
        )


class RealLoader:
    """Real public-IG loader via the anonymous ``web_profile_info`` API.

    No login, no proxy, no instaloader GraphQL. One HTTP round-trip per username
    (cached) returns the profile pic + the first ~12 timeline media for any
    PUBLIC profile. ``http_get`` and ``download_image`` are injectable so the
    loader is fully testable without network; the defaults use urllib + Pillow.

    Blocked / refused conditions (HTTP 401/403/429, or a null user payload)
    raise ``InstagramBlocked`` so the client maps them to ``status="blocked"``.
    Only exercised end-to-end by an env-gated real test.
    """

    def __init__(
        self,
        http_get=None,
        download_image=None,
        *,
        user_agent: str = _DEFAULT_UA,
    ) -> None:
        self._http_get = http_get or _urllib_get
        self._download_image = download_image or _urllib_download_image
        self._user_agent = user_agent
        self._cache: dict[str, dict] = {}

    def _headers(self) -> dict:
        return {
            "User-Agent": self._user_agent,
            "X-IG-App-ID": IG_APP_ID,
            "Accept": "*/*",
        }

    def _web_profile_info(self, username: str) -> dict:
        """Fetch + cache the ``web_profile_info`` ``user`` payload for a handle."""
        if username in self._cache:
            return self._cache[username]

        url = WEB_PROFILE_INFO_URL.format(username=username)
        status, body = self._http_get(url, self._headers())

        if status in _BLOCKED_STATUSES:
            raise InstagramBlocked(
                f"web_profile_info HTTP {status} for {username!r} (anonymous access refused)"
            )
        if status == 404:
            # A wrong/removed handle. Surface as a block so the pipeline flags
            # the channel and falls back to other sources, never crashing.
            raise InstagramBlocked(
                f"web_profile_info HTTP 404 for {username!r} (profile not found)"
            )
        if status != 200:
            raise RuntimeError(f"web_profile_info HTTP {status} for {username!r}")

        try:
            import json

            payload = json.loads(body)
            user = payload["data"]["user"]
        except Exception as exc:  # malformed / unexpected body
            raise RuntimeError(
                f"web_profile_info returned unparseable body for {username!r}: {exc}"
            ) from exc

        if not user:
            raise InstagramBlocked(
                f"web_profile_info returned an empty user for {username!r}"
            )

        self._cache[username] = user
        return user

    def profile_pic(self, username: str, dest: str) -> Optional[Tuple[str, int, int]]:
        user = self._web_profile_info(username)
        pic_url = _extract_profile_pic_url(user)
        if not pic_url:
            return None
        os.makedirs(dest, exist_ok=True)
        local = os.path.join(dest, f"{username}_avatar.jpg")
        return self._download_image(pic_url, local)

    def recent_image_posts(
        self, username: str, dest_dir: str, limit: int
    ) -> List[Tuple[str, int, int, bool]]:
        user = self._web_profile_info(username)
        posts = _extract_image_posts(user, limit)
        os.makedirs(dest_dir, exist_ok=True)
        out: List[Tuple[str, int, int, bool]] = []
        for i, post in enumerate(posts):
            # Sidecar carousel children share one shortcode, so the shortcode
            # alone is NOT a unique filename — index it or children overwrite
            # each other on disk.
            shortcode = post.get("shortcode") or "post"
            local = os.path.join(dest_dir, f"{username}_{shortcode}_{i}.jpg")
            try:
                downloaded = self._download_image(post["display_url"], local)
            except Exception:
                continue  # per-post failure must not sink the others
            if downloaded is None:
                continue
            path, width, height = downloaded
            out.append((path, width, height, False))
        return out


def _urllib_get(url: str, headers: dict) -> Tuple[int, bytes]:
    """Default ``http_get``: a plain urllib GET returning ``(status, body)``.

    Never raises on an HTTP error status — returns the status so the caller maps
    it (403 -> blocked, etc.). Only genuine transport failures propagate.
    """
    import urllib.error
    import urllib.request

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.getcode(), resp.read()
    except urllib.error.HTTPError as exc:  # 4xx/5xx: hand the status back
        return exc.code, exc.read() if hasattr(exc, "read") else b""


def _urllib_download_image(url: str, local: str) -> Optional[Tuple[str, int, int]]:
    """Default ``download_image``: fetch to ``local``, return ``(path, w, h)``."""
    import urllib.request

    from PIL import Image  # lazy: optional dependency

    urllib.request.urlretrieve(url, local)
    with Image.open(local) as img:
        width, height = img.size
    return (local, width, height)
