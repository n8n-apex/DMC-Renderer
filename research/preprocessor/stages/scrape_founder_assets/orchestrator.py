"""Founder-asset scraper orchestrator — compose the full pipeline.

This is the conductor that wires together the already-built pieces:

  channels (YouTube + Instagram)  -> candidates
        |  (run IN PARALLEL, each wrapped so one failing never sinks the other)
        v
  selector.score_candidate + select_for_slots  -> per-slot ranked candidates
        |
        v
  restorer.ensure_print_quality  -> quality_gate.passes_quality
        |  (FIRST gate-passing candidate fills the slot; NEVER fabricate)
        v
  storage.commit  -> final committed paths
        |
  finally: storage.cleanup_scratch  (ALWAYS wipe raw downloads)

Every dependency is injectable; the defaults construct the REAL pieces, so
production code calls ``scrape_founder_assets(...)`` with no doubles while
tests inject fakes (no network).

``maybe_scrape`` is the thin pipeline hook: it runs the stage ONLY when the
client input carries a founder YouTube or Instagram URL, and is otherwise a
no-op (empty result, no crash) — additive to the existing /render pipeline.

Brand-agnostic: no client literals; a slot with no acceptable asset is
flagged, never filled with a fabricated stand-in.
"""
from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from typing import Any, List, Optional

from . import selector as _selector_module
from .clients import ChannelClient
from .models import Candidate, RoutedElement, ScrapeResult
from .quality_gate import RealVisionGate, VisionGateClient, passes_quality
from .restorer import Restorer
from .selector import _FACE_SLOTS, crop_to_face
from .storage import AcceptedAsset, LocalStorage, StorageBackend

# Channel status values surfaced per channel.
#   ok / blocked / empty / error come from the channel itself (or our wrapping);
#   skipped means no URL was supplied for that channel.
_NO_ASSET_REASON = "no acceptable asset from channels"


@dataclass
class SlotOutcome:
    """What happened for a single founder slot."""

    slot: str
    status: str  # "filled" | "flagged"
    path: Optional[str] = None
    reason: Optional[str] = None


@dataclass
class FounderAssetResult:
    """Aggregate outcome of one founder-asset scrape run."""

    slots: dict[str, SlotOutcome] = field(default_factory=dict)
    channel_status: dict[str, str] = field(default_factory=dict)
    flags: List[str] = field(default_factory=list)


class _DefaultSelector:
    """Adapts the selector module functions to the injected-selector shape."""

    score_candidate = staticmethod(_selector_module.score_candidate)
    select_for_slots = staticmethod(_selector_module.select_for_slots)


async def _fetch_channel(
    client: Optional[ChannelClient],
    url: Optional[str],
    *,
    limit: int,
) -> tuple[str, ScrapeResult]:
    """Fetch one channel off the event loop, never raising.

    Returns ``(status, ScrapeResult)``. A raised client becomes status
    ``"error"`` with empty candidates so a single channel failure cannot sink
    the other. A ``None`` url short-circuits to ``"skipped"``.
    """
    if url is None or client is None:
        return "skipped", ScrapeResult(source="", status="empty", candidates=[])

    try:
        # fetch_candidates is sync (network/IO); run it in a worker thread so
        # the two channels still progress concurrently under asyncio.gather.
        result = await asyncio.to_thread(client.fetch_candidates, url, limit=limit)
        return result.status, result
    except Exception as exc:  # one channel failing must never sink the other
        return "error", ScrapeResult(
            source="", status="error", candidates=[], reason=str(exc)
        )


def _select(
    selector: Any,
    candidates: List[Candidate],
    slots: List[str],
) -> dict[str, list[Candidate]]:
    """Score every candidate and rank into slots (skipping unreadable ones)."""
    scored: list[tuple[Candidate, Any]] = []
    for cand in candidates:
        try:
            score = selector.score_candidate(cand.local_path)
        except Exception:
            # An unreadable / un-scorable candidate is simply dropped, never
            # promoted into a slot.
            continue
        # Stash the detected face box so a portrait slot can be face-cropped
        # (head + shoulders) at fill time. Safe for fake selectors lacking box.
        box = getattr(score, "box", None)
        if box:
            cand.meta["face_box"] = [int(v) for v in box]
        scored.append((cand, score))
    return selector.select_for_slots(scored, slots)


def _prepare_path(cand: Candidate, slot: str) -> str:
    """The path to restore+gate for ``cand`` in ``slot``.

    For a PORTRAIT slot with a known face box, return a generous head-and-
    shoulders face-crop (tightens framing + drops any peripheral graphics);
    otherwise the raw download path. A crop failure falls back to the raw path
    (never sinks the candidate).
    """
    if slot in _FACE_SLOTS:
        box = cand.meta.get("face_box")
        if box:
            dest = f"{cand.local_path}.face.jpg"
            try:
                return crop_to_face(cand.local_path, tuple(box), dest)
            except Exception:
                return cand.local_path
    return cand.local_path


def _fill_slots(
    ranked: dict[str, list[Candidate]],
    slots: List[str],
    *,
    restorer: Restorer,
    gate: VisionGateClient,
    target_long_edge_px: int,
) -> tuple[list[AcceptedAsset], dict[str, SlotOutcome]]:
    """Fill each slot with a gate-passing candidate; de-dup across slots.

    For each slot we prefer the first gate-passing candidate whose source image
    is NOT already used by another slot (so e.g. ``team`` and ``scene`` don't get
    the identical photo). If every passing candidate is already used, we fall
    back to reusing one rather than leaving the slot empty. Restore + gate
    verdicts are cached so de-dup re-walks never re-pay the API/CPU cost. A slot
    with no acceptable asset is flagged with a reason — NEVER fabricated.
    """
    accepted: list[AcceptedAsset] = []
    outcomes: dict[str, SlotOutcome] = {}

    used_sources: set[str] = set()  # raw cand.local_path already committed
    restore_cache: dict[str, Any] = {}  # prepared path -> RestoreResult
    gate_cache: dict[str, tuple[bool, str]] = {}  # restored path -> (ok, reason)

    def _evaluate(cand: Candidate, slot: str) -> tuple[bool, str, Optional[str]]:
        """(ok, reason, restored_path) for one candidate, via the caches."""
        prepared = _prepare_path(cand, slot)
        restored = restore_cache.get(prepared)
        if restored is None:
            restored = restorer.ensure_print_quality(prepared, target_long_edge_px)
            restore_cache[prepared] = restored
        verdict = gate_cache.get(restored.path)
        if verdict is None:
            verdict = passes_quality(restored.path, gate)
            gate_cache[restored.path] = verdict
        return verdict[0], verdict[1], restored.path

    for slot in slots:
        fresh: Optional[tuple[Candidate, str]] = None  # passing + unused source
        reuse: Optional[tuple[Candidate, str]] = None  # passing but used source
        last_reason: Optional[str] = None

        for cand in ranked.get(slot, []):
            try:
                ok, reason, restored_path = _evaluate(cand, slot)
            except Exception as exc:
                last_reason = f"restore failed: {exc}"
                continue
            if not ok:
                last_reason = reason
                continue
            # passing candidate
            if cand.local_path not in used_sources:
                fresh = (cand, restored_path)
                break  # best possible for this slot — a distinct image
            if reuse is None:
                reuse = (cand, restored_path)  # remember as fallback, keep looking

        choice = fresh or reuse
        if choice is not None:
            cand, restored_path = choice
            # Point the accepted candidate at the print-ready bytes so storage
            # commits the restored asset, not the raw download. Give the copy its
            # OWN meta dict (model_copy is shallow) so the committed candidate
            # never aliases the raw candidate's mutable meta.
            chosen = cand.model_copy(
                update={"local_path": restored_path, "meta": dict(cand.meta)}
            )
            accepted.append(AcceptedAsset(slot=slot, candidate=chosen))
            outcomes[slot] = SlotOutcome(slot=slot, status="filled")
            used_sources.add(cand.local_path)
        else:
            reason = last_reason or _NO_ASSET_REASON
            if not ranked.get(slot):
                reason = _NO_ASSET_REASON
            outcomes[slot] = SlotOutcome(slot=slot, status="flagged", reason=reason)

    return accepted, outcomes


def _build_flags(
    outcomes: dict[str, SlotOutcome],
    channel_status: dict[str, str],
    reasons: dict[str, Optional[str]],
) -> List[str]:
    """Human-readable flags for each flagged slot + each non-ok channel."""
    flags: List[str] = []
    for channel, status in channel_status.items():
        if status in ("ok", "skipped"):
            continue
        detail = reasons.get(channel)
        msg = f"{channel} {status}"
        if detail:
            msg = f"{msg}: {detail}"
        flags.append(msg)
    for slot, outcome in outcomes.items():
        if outcome.status == "flagged":
            flags.append(f"slot {slot}: {outcome.reason}")
    return flags


async def scrape_founder_assets(
    *,
    youtube_url: Optional[str],
    instagram_url: Optional[str],
    founder_id: str,
    slots: List[str],
    scratch_dir: str,
    dest_root: str,
    youtube_client: Optional[ChannelClient] = None,
    instagram_client: Optional[ChannelClient] = None,
    selector: Any = None,
    restorer: Optional[Restorer] = None,
    gate: Optional[VisionGateClient] = None,
    storage: Optional[StorageBackend] = None,
    limit: int = 12,
    target_long_edge_px: int = 2500,
) -> FounderAssetResult:
    """Run the full founder-asset pipeline and return a `FounderAssetResult`.

    All dependencies default to the REAL pieces when not injected. The two
    channels run in parallel; each is wrapped so a single failure cannot sink
    the other. The first gate-passing candidate fills each slot (never
    fabricating); the download scratch is ALWAYS wiped in ``finally``.
    """
    selector = selector if selector is not None else _DefaultSelector()
    restorer = restorer if restorer is not None else Restorer()
    gate = gate if gate is not None else RealVisionGate()
    storage = storage if storage is not None else LocalStorage(dest_root)

    # Construct real channel clients only when not injected and a URL is given.
    if youtube_client is None and youtube_url is not None:
        from .clients_youtube import YouTubeClient

        youtube_client = YouTubeClient(scratch_dir=scratch_dir)
    if instagram_client is None and instagram_url is not None:
        from .clients_instagram import InstagramClient

        instagram_client = InstagramClient(scratch_dir=scratch_dir)

    try:
        # 1. Run both channels in PARALLEL, each guarded against raising.
        (yt_status, yt_result), (ig_status, ig_result) = await asyncio.gather(
            _fetch_channel(youtube_client, youtube_url, limit=limit),
            _fetch_channel(instagram_client, instagram_url, limit=limit),
        )
        channel_status = {"youtube": yt_status, "instagram": ig_status}
        channel_reasons = {
            "youtube": yt_result.reason,
            "instagram": ig_result.reason,
        }

        candidates: list[Candidate] = []
        candidates.extend(yt_result.candidates)
        candidates.extend(ig_result.candidates)

        # 2. Score + rank into slots.
        ranked = _select(selector, candidates, slots)

        # 3. Fill each slot with the first gate-passing candidate.
        accepted, outcomes = _fill_slots(
            ranked,
            slots,
            restorer=restorer,
            gate=gate,
            target_long_edge_px=target_long_edge_px,
        )

        # 4. Commit accepted assets and stamp final paths onto outcomes.
        if accepted:
            committed = storage.commit(accepted, founder_id)
            for asset in committed:
                outcome = outcomes.get(asset.slot)
                if outcome is not None and outcome.status == "filled":
                    outcome.path = asset.final_path

        # 6. Build flags from flagged slots + non-ok channels.
        flags = _build_flags(outcomes, channel_status, channel_reasons)

        return FounderAssetResult(
            slots=outcomes, channel_status=channel_status, flags=flags
        )
    finally:
        # 5. ALWAYS wipe the scratch (raw downloads), success or failure.
        try:
            storage.cleanup_scratch(scratch_dir)
        except Exception:
            pass


async def maybe_scrape(
    client_input: Any,
    *,
    founder_id: str,
    slots: List[str],
    scratch_dir: str,
    dest_root: str,
    **kwargs: Any,
) -> FounderAssetResult:
    """Pipeline hook: run the scrape stage ONLY when a founder URL is present.

    Reads ``founder_youtube_url`` / ``founder_instagram_url`` off the client
    input. If neither is set, returns an empty no-op result (both channels
    ``skipped``) without touching the network or filesystem — additive to the
    existing pipeline. Extra keyword args pass through to
    ``scrape_founder_assets`` (e.g. injected fakes in tests).
    """
    youtube_url = getattr(client_input, "founder_youtube_url", None)
    instagram_url = getattr(client_input, "founder_instagram_url", None)

    if not youtube_url and not instagram_url:
        return FounderAssetResult(
            slots={},
            channel_status={"youtube": "skipped", "instagram": "skipped"},
            flags=[],
        )

    return await scrape_founder_assets(
        youtube_url=youtube_url,
        instagram_url=instagram_url,
        founder_id=founder_id,
        slots=slots,
        scratch_dir=scratch_dir,
        dest_root=dest_root,
        **kwargs,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Smart understanding + routing pipeline (Tasks 4-5)
#
# Where ``scrape_founder_assets`` fills a FIXED set of named slots, this path
# generalizes to Perception -> Analysis -> Routing: harvest a rich pool, DET-
# score + VIS-classify each asset's role + appeal, then route each to the report
# element where it adds the most appeal. Real "founder-at-device" photos fill the
# ``device_mockup`` element directly (emitted as an AssetResult, no synthetic
# frame); the other (drive) elements are copied to their resolver filenames via
# ``slot_bridge.place_routed``. An element with no suitable real asset is FLAGGED
# — never fabricated. Brand-agnostic: no client literals.
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class RouteRunResult:
    """Aggregate outcome of one understand-and-route run.

    - ``routed``: one ``RoutedElement`` per report element (filled or flagged).
    - ``device_assets``: ``AssetResult``s for any FILLED ``device_mockup``
      composite element (real founder-at-device photo, never synthetic).
    - ``placed``: ``{element: dest_path}`` for drive elements copied to the
      resolver client-assets dir.
    - ``flags``: human-readable notes (non-ok channels + flagged elements).
    """

    routed: List[RoutedElement] = field(default_factory=list)
    device_assets: List[Any] = field(default_factory=list)  # list[AssetResult]
    placed: dict = field(default_factory=dict)
    flags: List[str] = field(default_factory=list)


def _score_and_classify(
    selector: Any,
    classifier: Any,
    candidates: List[Candidate],
):
    """Build ``(Candidate, det_score, AssetJudgement)`` triples for the router.

    Each candidate is DET-scored (unreadable ones are skipped) then VIS-
    classified (fail-closed). Returns the list of triples.
    """
    from .classifier import classify_asset

    triples = []
    for cand in candidates:
        try:
            det = selector.score_candidate(cand.local_path)
        except Exception:
            # unreadable / un-scorable candidate -> never routed
            continue
        judgement = classify_asset(cand.local_path, classifier)
        triples.append((cand, det, judgement))
    return triples


async def understand_and_route(
    *,
    youtube_url: Optional[str],
    instagram_url: Optional[str],
    founder_id: str,
    scratch_dir: str,
    dest_root: str,
    youtube_client: Optional[ChannelClient] = None,
    instagram_client: Optional[ChannelClient] = None,
    classifier: Any = None,
    selector: Any = None,
    storage: Optional[StorageBackend] = None,
    limit: int = 12,
    target_long_edge_px: int = 2500,
) -> RouteRunResult:
    """Scrape a pool -> perceive (DET) -> classify (VIS) -> route -> place.

    Fetches both channels in PARALLEL (each guarded so one failure can't sink
    the other), DET-scores + VIS-classifies every candidate, routes the
    ``(cand, det, judgement)`` triples to report elements, copies the FILLED
    drive elements into ``<dest_root>/<founder_id>/`` (where the slot resolver
    reads ``client_assets/<slug>/``), and emits an ``AssetResult`` for a FILLED
    ``device_mockup``. The download scratch is ALWAYS wiped in ``finally``.

    Defaults: ``classifier`` -> ``RealAssetClassifier()``, ``selector`` -> the
    selector module functions (both lazily, to keep import-time light).
    """
    if classifier is None:
        from .classifier import RealAssetClassifier

        classifier = RealAssetClassifier()
    if selector is None:
        selector = _DefaultSelector()
    if storage is None:
        storage = LocalStorage(dest_root)

    # Construct real channel clients only when not injected and a URL is given.
    if youtube_client is None and youtube_url is not None:
        from .clients_youtube import YouTubeClient

        youtube_client = YouTubeClient(scratch_dir=scratch_dir)
    if instagram_client is None and instagram_url is not None:
        from .clients_instagram import InstagramClient

        instagram_client = InstagramClient(scratch_dir=scratch_dir)

    try:
        # 1. Run both channels in PARALLEL, each guarded against raising.
        (yt_status, yt_result), (ig_status, ig_result) = await asyncio.gather(
            _fetch_channel(youtube_client, youtube_url, limit=limit),
            _fetch_channel(instagram_client, instagram_url, limit=limit),
        )
        channel_status = {"youtube": yt_status, "instagram": ig_status}
        channel_reasons = {
            "youtube": yt_result.reason,
            "instagram": ig_result.reason,
        }

        candidates: list[Candidate] = []
        candidates.extend(yt_result.candidates)
        candidates.extend(ig_result.candidates)

        # 2. DET-score + VIS-classify into routing triples, then 3. route.
        from .router import route_assets

        triples = _score_and_classify(selector, classifier, candidates)
        routed = route_assets(triples)

        # 4. Place FILLED drive elements + emit device_mockup AssetResults.
        from .slot_bridge import ELEMENT_TO_DRIVE_KEY, place_routed

        founder_dir = os.path.join(dest_root, founder_id)
        placed = place_routed(routed, founder_dir)

        device_assets = _build_device_assets(routed)

        # 5. Flags: non-ok channels + flagged elements.
        flags = _build_route_flags(routed, channel_status, channel_reasons)

        return RouteRunResult(
            routed=routed,
            device_assets=device_assets,
            placed=placed,
            flags=flags,
        )
    finally:
        # ALWAYS wipe the scratch (raw downloads), success or failure.
        try:
            storage.cleanup_scratch(scratch_dir)
        except Exception:
            pass


def _build_device_assets(routed: List[RoutedElement]) -> List[Any]:
    """Emit an ``AssetResult`` for each FILLED ``device_mockup`` element.

    The device element is a COMPOSITE (a real founder-at-device photo placed on
    a page), so it is surfaced as an AssetResult (``status="resolved"`` — the
    asset is a real scraped image, not generated) rather than copied to a drive
    filename. Flagged device elements emit nothing (never fabricated).
    """
    from stages.generate_assets import AssetResult

    out: List[Any] = []
    for el in routed:
        if el.element != "device_mockup":
            continue
        if el.status != "filled" or not el.path:
            continue
        out.append(
            AssetResult(
                slot_id="device_mockup",
                status="resolved",
                path=el.path,
                image_type="device",
                message=(
                    f"real founder-at-device photo routed to device_mockup "
                    f"(role={el.role}, appeal={el.appeal})"
                ),
            )
        )
    return out


def _build_route_flags(
    routed: List[RoutedElement],
    channel_status: dict[str, str],
    reasons: dict[str, Optional[str]],
) -> List[str]:
    """Human-readable flags for each non-ok channel + each flagged element."""
    flags: List[str] = []
    for channel, status in channel_status.items():
        if status in ("ok", "skipped"):
            continue
        detail = reasons.get(channel)
        msg = f"{channel} {status}"
        if detail:
            msg = f"{msg}: {detail}"
        flags.append(msg)
    for el in routed:
        if el.status == "flagged":
            flags.append(f"element {el.element}: {el.reason}")
    return flags
