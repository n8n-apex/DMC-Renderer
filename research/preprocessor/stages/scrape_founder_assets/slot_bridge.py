"""Bridge the scraper's slot taxonomy to the renderer's drive-key convention.

The scraper fills its OWN slots (``founder`` / ``about_portrait`` / ``team`` /
``scene``) and stores files as ``<slot>__<n>.<ext>``. The slot RESOLVER
(``stages/resolve_slots.py``), however, matches client-asset files to page
``drive_key``s by an EXACT normalized stem for single slots and a ``<stem>-``
prefix for many slots (``stages/slot_registry.py``):

  * ``founder_hero`` (ST-01 cover, ST-FAZIT)  <- drive_key ``founder``  (single)
  * ``team``         (ST-05 about portrait)   <- drive_key ``team``     (single)
  * ``proof``        (ST-05 credibility gallery) <- drive_key ``proof-*`` (many)

``founder__0.jpg`` normalizes to ``founder-0`` which does NOT equal ``founder``,
so the scraper's native filenames never resolve. This module copies each FILLED
scraper slot into the resolver's client-assets dir under a filename whose
normalized stem the resolver WILL match.

Mapping rationale (founder imagery only — never client faces, never generated
scene; those stay flagged / generated elsewhere):
  founder / cover_hero -> ``founder``      (the hero portrait)
  about_portrait / team -> ``team``        (the About-page portrait/group shot)
  scene                -> ``proof-<i>``    (clean candid photos -> proof gallery)

Pure + brand-agnostic: copies local files only, no network, no client literals.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import List, Optional, Union

from .models import RoutedElement

# scraper slot -> resolver drive_key base (the filename stem the resolver matches)
SCRAPER_SLOT_TO_DRIVE_KEY: dict[str, str] = {
    "founder": "founder",
    "cover_hero": "founder",
    "about_portrait": "team",
    "team": "team",
    "scene": "proof",
}
# drive_keys that are "many" (gallery) -> emit indexed ``<key>-1``, ``<key>-2`` ...
_MANY_DRIVE_KEYS = {"proof"}

# router report ELEMENT -> resolver drive_key base. Mirrors
# ``SCRAPER_SLOT_TO_DRIVE_KEY`` for the generalized routing pipeline (Task 5):
#   cover_hero            -> founder   (the hero portrait, single)
#   team                  -> team      (the About-page portrait/group, single)
#   scene / proof / content_card -> proof  (clean photos + designed cards, gallery)
#   logo                  -> logo      (logo/wordmark, single)
#   device_mockup         -> None      (NOT a drive file — a composite element
#                                        emitted as an AssetResult in the
#                                        orchestrator, never copied here)
ELEMENT_TO_DRIVE_KEY: dict[str, Optional[str]] = {
    "cover_hero": "founder",
    "team": "team",
    "scene": "proof",
    "proof": "proof",
    "content_card": "proof",
    "logo": "logo",
    "device_mockup": None,
}


def _copy_to_drive_filename(
    src: str,
    drive_key: str,
    dest_dir: Path,
    many_counter: dict[str, int],
    written_single: set[str],
) -> Optional[str]:
    """Copy ``src`` into ``dest_dir`` under the resolver filename for ``drive_key``.

    - Many drive_keys (proof) get ``<key>-<n><ext>``, numbered per drive_key so
      multiple sources don't clash.
    - Single drive_keys (founder/team/logo) get ``<key><ext>`` — written ONCE;
      a second source for the same single drive_key is SKIPPED (returns None) so
      the first FILLED claimant is never overwritten.
    """
    ext = os.path.splitext(src)[1] or ".jpg"
    if drive_key in _MANY_DRIVE_KEYS:
        n = many_counter.get(drive_key, 0) + 1
        many_counter[drive_key] = n
        filename = f"{drive_key}-{n}{ext}"
    else:
        if drive_key in written_single:
            return None  # single slot already claimed — don't overwrite
        written_single.add(drive_key)
        filename = f"{drive_key}{ext}"
    dest = dest_dir / filename
    shutil.copyfile(src, dest)
    return str(dest)


def place_for_resolver(result, client_assets_dir: Union[str, Path]) -> dict[str, str]:
    """Copy each FILLED scraper slot into ``client_assets_dir`` under a filename
    the slot resolver will match by drive_key. Returns ``{slot: dest_path}``.

    - Single drive_keys (founder/team) get ``<key><ext>`` (e.g. ``founder.jpg``).
    - Many drive_keys (proof) get ``<key>-<n><ext>`` (e.g. ``proof-1.jpg``),
      numbered per drive_key so multiple slots mapping to ``proof`` don't clash.
    - Flagged / unmapped slots are skipped (never fabricated).
    """
    dest_dir = Path(client_assets_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    placed: dict[str, str] = {}
    many_counter: dict[str, int] = {}
    written_single: set[str] = set()

    for slot, outcome in result.slots.items():
        if getattr(outcome, "status", None) != "filled" or not getattr(outcome, "path", None):
            continue
        drive_key = SCRAPER_SLOT_TO_DRIVE_KEY.get(slot)
        if not drive_key:
            continue  # slot has no renderer home (e.g. an unmapped category)
        dest = _copy_to_drive_filename(
            outcome.path, drive_key, dest_dir, many_counter, written_single
        )
        if dest is not None:
            placed[slot] = dest

    return placed


def place_routed(
    routed: List[RoutedElement], client_assets_dir: Union[str, Path]
) -> dict[str, str]:
    """Copy each FILLED routed report element to its resolver drive-key filename.

    Returns ``{element: dest_path}`` for the elements that wrote a file. Mirrors
    ``place_for_resolver`` but keys off the router's report ELEMENT taxonomy via
    ``ELEMENT_TO_DRIVE_KEY``:

    - Single drive_keys (founder/team/logo) get ``<key><ext>`` and are written
      ONCE — the FIRST FILLED element claiming that drive_key wins, so a
      ``founder_portrait`` that fell back to ``team`` and a real ``team`` group
      shot (both -> ``team``) never overwrite.
    - Many drive_keys (proof) get ``<key>-<n><ext>``, numbered per drive_key, so
      ``scene`` + ``proof`` + ``content_card`` all fan into the proof gallery.
    - Elements with drive_key ``None`` (device_mockup) are SKIPPED here — the
      device composite is emitted as an ``AssetResult`` by the orchestrator.
    - Flagged elements are SKIPPED (never fabricated).
    """
    dest_dir = Path(client_assets_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    placed: dict[str, str] = {}
    many_counter: dict[str, int] = {}
    written_single: set[str] = set()

    for el in routed:
        if getattr(el, "status", None) != "filled" or not getattr(el, "path", None):
            continue
        drive_key = ELEMENT_TO_DRIVE_KEY.get(el.element)
        if not drive_key:
            continue  # device_mockup (None) or an unmapped element -> no drive file
        dest = _copy_to_drive_filename(
            el.path, drive_key, dest_dir, many_counter, written_single
        )
        if dest is not None:
            placed[el.element] = dest

    return placed
