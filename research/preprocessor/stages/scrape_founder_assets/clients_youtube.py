"""YouTube channel client — collects real founder imagery via yt-dlp + ffmpeg
WITHOUT ever downloading long videos.

The whole point of this module is the *FILTER*: a founder's channel may hold
hour-long talks. We must never download those. We harvest cheap imagery
(avatar, banner, thumbnails) for everything, and only ever fetch the actual
video bytes for SHORT clips bounded by ``MAX_SHORT_SECONDS`` and capped at
``MAX_SHORTS``. Long / over-length videos contribute only their thumbnail.

Network access is abstracted behind a ``runner`` so tests are network-free:

    runner.channel_info(url) -> dict
        {"avatar_url", "banner_url",
         "videos": [{"id","title","duration_sec","is_short","thumbnail_url"}]}
    runner.download_image(image_url, dest) -> (path, w, h)
    runner.download_short(video_id, dest) -> path        # ONLY for eligible shorts
    runner.sample_frames(video_path, dest_dir, every_sec=2) -> [(path, w, h)]

The real runner (``RealRunner``) lazy-imports yt_dlp and shells out to ffmpeg;
it is only exercised by an env-gated real test. Unit tests inject a fake.

Brand-agnostic: shapes + behaviour only, no client value.
"""
from __future__ import annotations

import os
from typing import List, Optional, Protocol, Tuple, runtime_checkable

from .models import Candidate, ScrapeResult

# --- The FILTER: the hard data-bounding contract. -------------------------
MAX_SHORT_SECONDS = 90  # only fetch video bytes for clips this short or shorter
MAX_SHORTS = 4  # never download more than this many shorts
MAX_THUMBNAILS = 12  # never collect more than this many video thumbnails

_SOURCE = "youtube"


@runtime_checkable
class YouTubeRunner(Protocol):
    """External-tool boundary for the YouTube client (injectable for tests)."""

    def channel_info(self, url: str) -> dict:
        ...

    def download_image(self, image_url: str, dest: str) -> Tuple[str, int, int]:
        ...

    def download_short(self, video_id: str, dest: str) -> str:
        ...

    def sample_frames(
        self, video_path: str, dest_dir: str, every_sec: int = 2
    ) -> List[Tuple[str, int, int]]:
        ...


def _is_eligible_short(video: dict) -> bool:
    """A short we are allowed to DOWNLOAD: flagged as a short AND not a KNOWN
    over-length clip.

    The flat channel listing frequently omits per-video duration (returns
    ``None``); excluding those would mean downloading nothing at all. Since a
    video flagged via the ``/shorts`` tab is inherently short (YouTube caps
    Shorts at ~3 min), we TRUST that flag when the duration is unknown — the
    "never ffmpeg a long video" rule is still honoured (a /shorts entry cannot
    be an hour-long talk). Only a clip with a KNOWN duration over
    ``MAX_SHORT_SECONDS`` is disqualified (thumbnail only).
    """
    if not video.get("is_short"):
        return False
    duration = video.get("duration_sec")
    return duration is None or duration <= MAX_SHORT_SECONDS


class YouTubeClient:
    """Fetches founder-asset candidates from a YouTube channel URL.

    Implements the ``ChannelClient`` protocol (``fetch_candidates``). All
    external work goes through the injected ``runner``; failures are caught and
    surfaced as a ``ScrapeResult`` with status "error"/"empty" rather than
    raising.
    """

    def __init__(self, runner: Optional[YouTubeRunner] = None, *, scratch_dir: str = "/tmp"):
        self.runner: YouTubeRunner = runner if runner is not None else RealRunner()
        self.scratch_dir = scratch_dir

    # -- public API --------------------------------------------------------
    def fetch_candidates(self, url: str, *, limit: int = 12) -> ScrapeResult:
        try:
            info = self.runner.channel_info(url)
        except Exception as exc:  # graceful: never crash the pipeline
            return ScrapeResult(
                source=_SOURCE,
                status="error",
                candidates=[],
                reason=f"channel_info failed: {exc}",
            )

        videos = list(info.get("videos") or [])
        if not videos:
            return ScrapeResult(
                source=_SOURCE,
                status="empty",
                candidates=[],
                reason="no videos found on channel",
            )

        candidates: List[Candidate] = []

        # 1) avatar + banner — cheap images, never any video download.
        for kind, key in (("avatar", "avatar_url"), ("banner", "banner_url")):
            image_url = info.get(key)
            if image_url:
                cand = self._image_candidate(kind, image_url, meta={})
                if cand is not None:
                    candidates.append(cand)

        # 2) thumbnails for recent videos (bounded), still no video download.
        thumb_budget = min(limit, MAX_THUMBNAILS)
        for video in videos[:thumb_budget]:
            thumb_url = video.get("thumbnail_url")
            if not thumb_url:
                continue
            cand = self._image_candidate(
                "thumbnail", thumb_url, meta={"video_id": video.get("id")}
            )
            if cand is not None:
                candidates.append(cand)

        # 3) ONLY eligible shorts (<= MAX_SHORT_SECONDS), capped at MAX_SHORTS,
        #    get their bytes downloaded + frame-sampled. Long / over-length
        #    videos are deliberately skipped here — thumbnail only.
        downloaded = 0
        for video in videos:
            if downloaded >= MAX_SHORTS:
                break
            if not _is_eligible_short(video):
                continue
            video_id = video.get("id")
            if not video_id:
                continue
            frames = self._frame_candidates(video_id, video)
            candidates.extend(frames)
            downloaded += 1

        return ScrapeResult(source=_SOURCE, status="ok", candidates=candidates)

    # -- helpers -----------------------------------------------------------
    def _image_candidate(self, kind: str, image_url: str, *, meta: dict) -> Optional[Candidate]:
        try:
            path, width, height = self.runner.download_image(image_url, self.scratch_dir)
        except Exception:
            return None  # one bad image must not sink the whole fetch
        full_meta = {"source_url": image_url}
        full_meta.update({k: v for k, v in meta.items() if v is not None})
        return Candidate(
            source=_SOURCE,
            kind=kind,
            local_path=path,
            width=width,
            height=height,
            meta=full_meta,
        )

    def _frame_candidates(self, video_id: str, video: dict) -> List[Candidate]:
        try:
            video_path = self.runner.download_short(video_id, self.scratch_dir)
            frames = self.runner.sample_frames(video_path, self.scratch_dir)
        except Exception:
            return []  # a failed short must not sink the whole fetch
        out: List[Candidate] = []
        for path, width, height in frames:
            out.append(
                Candidate(
                    source=_SOURCE,
                    kind="frame",
                    local_path=path,
                    width=width,
                    height=height,
                    meta={"video_id": video_id, "title": video.get("title")},
                )
            )
        return out


class RealRunner:
    """Real external-tool runner: yt-dlp metadata + image fetch + ffmpeg frames.

    Lazy-imports / shells out so that ``import clients_youtube`` works even
    where yt_dlp / ffmpeg are absent (CI). Only used by an env-gated real test.
    """

    def channel_info(self, url: str) -> dict:
        import yt_dlp  # lazy: optional dependency

        # A channel ROOT url (e.g. .../@Handle) extracts to the channel's TABS,
        # not its videos — so we must hit the /videos and /shorts tabs directly
        # to get real video entries. Strip any existing tab suffix first.
        base = url.rstrip("/")
        for suf in ("/videos", "/shorts", "/streams", "/featured"):
            if base.endswith(suf):
                base = base[: -len(suf)]
                break

        opts = {
            "quiet": True,
            "skip_download": True,
            "extract_flat": "in_playlist",
            "playlistend": MAX_THUMBNAILS + MAX_SHORTS + 4,  # bound the listing
        }
        avatar_url = banner_url = None
        videos: list[dict] = []
        for tab, is_short_tab in (("/videos", False), ("/shorts", True)):
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    data = ydl.extract_info(base + tab, download=False)
            except Exception:  # noqa: BLE001 — one tab failing must not sink the other
                continue
            if avatar_url is None:
                avatar_url = _channel_image(data, "avatar_uncropped") or _channel_image(data, "avatar")
            if banner_url is None:
                banner_url = _channel_image(data, "banner_uncropped") or _channel_image(data, "banner")
            for entry in data.get("entries") or []:
                # an entry may itself be a nested playlist — flatten one level.
                items = entry.get("entries") or [entry]
                for it in items:
                    vid = it.get("id")
                    if not vid:
                        continue
                    duration = it.get("duration")
                    # flat extraction often omits per-video thumbnails — derive
                    # the canonical thumbnail URL from the video id as a fallback.
                    thumb = it.get("thumbnail") or f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
                    videos.append(
                        {
                            "id": vid,
                            "title": it.get("title"),
                            "duration_sec": int(duration) if duration is not None else None,
                            "is_short": is_short_tab or _looks_like_short(it),
                            "thumbnail_url": thumb,
                        }
                    )
        return {"avatar_url": avatar_url, "banner_url": banner_url, "videos": videos}

    def download_image(self, image_url: str, dest: str) -> Tuple[str, int, int]:
        import urllib.request

        from PIL import Image  # lazy: optional dependency

        os.makedirs(dest, exist_ok=True)
        local = os.path.join(dest, _local_name_for_url(image_url))
        urllib.request.urlretrieve(image_url, local)
        with Image.open(local) as img:
            width, height = img.size
        return (local, width, height)

    def download_short(self, video_id: str, dest: str) -> str:
        import yt_dlp  # lazy

        os.makedirs(dest, exist_ok=True)
        out_tmpl = os.path.join(dest, f"{video_id}.%(ext)s")
        opts = {"quiet": True, "outtmpl": out_tmpl, "format": "mp4/best"}
        url = f"https://www.youtube.com/watch?v={video_id}"
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        # yt-dlp may emit any container (.mp4/.webm/.mkv/.m4v/.mov/...). Glob for
        # whatever actually landed rather than guessing a fixed extension, so we
        # never hand sample_frames a path that isn't on disk.
        import glob

        matches = sorted(glob.glob(os.path.join(dest, f"{video_id}.*")))
        # Prefer a video container if several files share the stem (e.g. a
        # leftover thumbnail); fall back to the first match, else the mp4 name.
        for ext in ("mp4", "webm", "mkv", "m4v", "mov"):
            preferred = os.path.join(dest, f"{video_id}.{ext}")
            if preferred in matches:
                return preferred
        if matches:
            return matches[0]
        return os.path.join(dest, f"{video_id}.mp4")

    def sample_frames(
        self, video_path: str, dest_dir: str, every_sec: int = 2
    ) -> List[Tuple[str, int, int]]:
        import glob
        import subprocess

        from PIL import Image  # lazy

        os.makedirs(dest_dir, exist_ok=True)
        base = os.path.splitext(os.path.basename(video_path))[0]
        pattern = os.path.join(dest_dir, f"{base}_frame_%03d.png")
        subprocess.run(
            [
                "ffmpeg",
                "-i",
                video_path,
                "-vf",
                f"fps=1/{every_sec}",
                pattern,
            ],
            check=True,
            capture_output=True,
        )
        out: List[Tuple[str, int, int]] = []
        for path in sorted(glob.glob(os.path.join(dest_dir, f"{base}_frame_*.png"))):
            with Image.open(path) as img:
                width, height = img.size
            out.append((path, width, height))
        return out


def _local_name_for_url(image_url: str) -> str:
    """A unique local filename for an image URL.

    YouTube thumbnail URLs are all ``.../vi/<video_id>/hqdefault.jpg`` — their
    basenames collide (every video -> ``hqdefault.jpg``), so naming a download by
    its basename alone makes each thumbnail overwrite the last. Prefix a short
    hash of the FULL url to guarantee uniqueness while keeping a readable suffix.
    """
    import hashlib

    base = os.path.basename(image_url.split("?")[0]) or "image"
    digest = hashlib.md5(image_url.encode("utf-8")).hexdigest()[:10]
    return f"{digest}_{base}"


def _channel_image(data: dict, image_id: str) -> Optional[str]:
    for thumb in data.get("thumbnails") or []:
        if thumb.get("id") == image_id:
            return thumb.get("url")
    return None


def _looks_like_short(entry: dict) -> bool:
    url = (entry.get("url") or entry.get("webpage_url") or "")
    if "/shorts/" in url:
        return True
    duration = entry.get("duration")
    return duration is not None and duration <= MAX_SHORT_SECONDS
