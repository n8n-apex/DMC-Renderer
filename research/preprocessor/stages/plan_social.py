"""Social Layout Planner (Phase 1) — deterministic asset-routing.

Decides WHERE each classified social asset lands in the report, then writes
those decisions onto the package. Two halves, cleanly split:

  * `plan_social(...)` — PURE + deterministic. Reads the classified
    `AssetManifest` + the report's social homes (breather slots, about slot,
    fazit slot, case-study client names) and produces a `SocialPlan`. The
    `asset_exists(path)->bool` predicate is INJECTED so the planner NEVER
    binds a file that is not on disk (missing → recorded in `plan.dropped`).

  * `apply_social_plan(...)` — the ONLY mutator. Stages each bound source file
    into the package `assets/` dir under a deterministic `ig_<basename>` name
    and writes the binding onto the matching package page. Idempotent.

Brand-agnostic by construction: this module contains ZERO client literals.
Every client string (handle, brand_text, client name) arrives via the
manifest DATA or the report content passed by the caller.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Callable, Optional

from models_social import (
    AssetClassification,
    AssetManifest,
    SocialBinding,
    SocialPlan,
)

# Roles that qualify an asset as a "post" (gallery-grade content), per spec §3.1.
# Cards and portraits are deliberately excluded — they are not feed posts.
_POST_ROLES = frozenset({"speaking", "working", "scene", "client_photo", "interview"})
# The narrower set eligible for a full-bleed scene breather, per spec §3.2.
_SCENE_ROLES = frozenset({"scene", "speaking", "working"})

_GRID_GATE = 6   # ≥6 posts → a profile grid fires (spec §3.1)
_GRID_MAX = 9    # a 3×3 profile grid at most
_TESTIMONIAL_MAX = 2  # ST-05 hosts ≤2 testimonial cards (copy-fit, spec §3.3)


def _norm(text: str) -> str:
    """Normalise a brand/client string for containment matching: lowercase,
    collapse internal whitespace, strip. Brand-agnostic — no literals."""
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _ranked(assets: list[AssetClassification]) -> list[AssetClassification]:
    """Appeal-ranked, stable: highest visual_appeal first, ties broken by path
    ascending (deterministic)."""
    return sorted(assets, key=lambda a: (-int(a.visual_appeal or 0), a.path))


def _shoot(path: str) -> str:
    """Deterministic "shoot" key for breather diversification.

    The basename with any trailing `_<index>` and extension stripped. So
    `jousefmrd_DX2kDuvDL40_8.jpg`, `..._9`, `..._10` all share the shoot
    `jousefmrd_DX2kDuvDL40`; the `DYhZxkq` interview carousel is one shoot; each
    `DVOLEK` Goldman frame is its own shoot. Brand-agnostic — derived from the
    path shape only, no client literals."""
    stem = Path(path).stem  # basename, extension stripped
    return re.sub(r"_\d+$", "", stem)


def plan_social(
    manifest: AssetManifest,
    *,
    case_clients: dict[int, str],
    breather_slots: list[int],
    about_slot: Optional[int],
    fazit_slot: Optional[int],
    founder_name: str,
    founder_role: str,
    asset_exists: Callable[[str], bool],
    enable_profile_grid: bool = True,
) -> SocialPlan:
    """Decide social placements deterministically. PURE: no I/O beyond the
    injected `asset_exists` predicate. Never binds a missing file.

    Allocation order is chosen so the SCARCE single-photo homes get distinct
    photos first and the (de-duped) profile grid fills from what remains —
    this lets the grid, the scene breathers AND the case-study post all
    co-exist from a modest pool while every asset is used at most once.
    """
    handle = manifest.handle or ""
    bindings: list[SocialBinding] = []
    dropped: list[str] = []
    used: set[str] = set()

    # Only ever consider files that physically exist (gap-audit #1).
    present = [a for a in manifest.assets if asset_exists(a.path)]
    for a in manifest.assets:
        if not asset_exists(a.path):
            dropped.append(f"{a.path}: source file missing (not bound)")

    posts = [a for a in present if a.role in _POST_ROLES and not a.is_testimonial_card]
    ranked_posts = _ranked(posts)

    def _take(pool: list[AssetClassification]) -> Optional[AssetClassification]:
        for a in pool:
            if a.path not in used:
                return a
        return None

    breathers = list(breather_slots)
    # When the profile grid is disabled (e.g. a client whose follower/engagement
    # numbers don't justify a feed overview), EVERY breather becomes a diversified
    # full-bleed scene photo — no grid home is reserved. Otherwise the LAST
    # breather is the grid's home and the rest are scene breathers.
    if enable_profile_grid:
        grid_slot = breathers[-1] if breathers else None
        scene_slots = [s for s in breathers if s != grid_slot]  # everything but the grid's home
    else:
        grid_slot = None
        scene_slots = list(breathers)

    # ---- (b) scene breathers: DIVERSIFIED by shoot (gap-fix A; reserved BEFORE
    #          the grid). The FIRST breather is the best-appeal SCENE shot
    #          (scene/speaking/working — the stage/atmosphere look that leads a
    #          breather). Each SUBSEQUENT breather draws from the BROADER post
    #          pool and PREFERS a shot whose ROLE and "shoot" both differ from the
    #          already-picked breathers (a DIFFERENT role first, then a different
    #          shoot, then best appeal), falling back to best-remaining only if
    #          nothing diverse is left. This stops the breathers clustering the
    #          same shoot (e.g. two stage frames from one talk). For apex this
    #          gives slot 6 = a stage speaking shot, slot 11 = the Goldman
    #          handshake (a NON-stage client_photo). ---------------------------
    scene_lead_pool = _ranked([a for a in posts if a.role in _SCENE_ROLES])
    # the broader pool for subsequent (diversifying) picks: every post role
    # (cards already excluded from `posts`), appeal-ranked.
    breather_pool = ranked_posts
    picked_roles: set[str] = set()
    picked_shoots: set[str] = set()
    for i, slot in enumerate(scene_slots):
        if i == 0:
            pick = _take(scene_lead_pool)  # lead breather: a SCENE shot
        else:
            pick = _pick_diverse_scene(
                breather_pool, used, picked_roles, picked_shoots
            )
        if pick is None:
            break
        used.add(pick.path)
        picked_roles.add(pick.role)
        picked_shoots.add(_shoot(pick.path))
        bindings.append(SocialBinding(
            target_kind="ST-31", page_slot=slot, element="scene_breather",
            assets=[pick.path], handle=handle,
        ))

    # ---- (d) case-study matched post: for each case study client, a non-card
    #          post whose normalized brand_text is a CONFIDENT SINGLE client
    #          match (reserved BEFORE the grid). --------------------------------
    norm_clients = {slot: _norm(name) for slot, name in (case_clients or {}).items() if _norm(name)}
    for slot in sorted(norm_clients):
        client = norm_clients[slot]
        # candidate posts whose brand_text matches THIS client (either-direction
        # containment) AND no OTHER client → confident, unambiguous.
        candidates: list[AssetClassification] = []
        for a in posts:
            bt = _norm(a.brand_text)
            if not bt:
                continue
            if not (bt in client or client in bt):
                continue
            # ambiguity guard: this brand_text must map to exactly ONE client.
            matched = [
                s for s, cn in norm_clients.items()
                if bt in cn or cn in bt
            ]
            if len(set(matched)) != 1:
                dropped.append(
                    f"case slot {slot}: brand_text {a.brand_text!r} ambiguous "
                    f"(matches {len(set(matched))} clients) — skipped"
                )
                continue
            candidates.append(a)
        pick = _take(_ranked(candidates))
        if pick is None:
            if candidates:
                dropped.append(f"case slot {slot}: all matching posts already used — skipped")
            else:
                dropped.append(f"case slot {slot}: no confident brand_text match — skipped")
            continue
        used.add(pick.path)
        avatar = _founder_avatar(present)
        b = SocialBinding(
            target_kind="ST-07A", page_slot=slot, element="case_study_post",
            assets=[pick.path], handle=handle,
        )
        if avatar:
            b.assets.append(avatar)  # avatar travels as the 2nd asset (header)
        bindings.append(b)

    # ---- (a) profile grid: the FEED OVERVIEW. ≥6 posts → the 9 (≤) best posts
    #          by visual_appeal desc bound to the LAST breather slot.
    #          EXEMPT from the cross-binding de-dup (gap-fix B): the grid is the
    #          feed overview, so it shows the best posts REGARDLESS of whether a
    #          post is also used as a breather or the case-study post. It does
    #          NOT consume `used` either, so it never starves the (already
    #          allocated) single-photo homes. Breathers + case-study still de-dup
    #          among THEMSELVES; only the grid is exempt. ----------------------
    if grid_slot is not None and len(posts) >= _GRID_GATE:
        grid_members = [a.path for a in ranked_posts][:_GRID_MAX]
        if grid_members:
            bindings.append(SocialBinding(
                target_kind="ST-31", page_slot=grid_slot, element="profile_grid",
                assets=grid_members, handle=handle,
            ))
    elif grid_slot is not None and posts:
        # <6 posts but the LAST breather is free → it becomes a scene breather
        # too (so a small pool still livens every breather).
        pick = _take(_ranked([a for a in posts if a.role in _SCENE_ROLES]))
        if pick is not None:
            used.add(pick.path)
            bindings.append(SocialBinding(
                target_kind="ST-31", page_slot=grid_slot, element="scene_breather",
                assets=[pick.path], handle=handle,
            ))

    # ---- (c) about testimonials: ≥1 card → ≤2 best cards bound to about. -----
    if about_slot is not None:
        cards = _ranked([a for a in present if a.is_testimonial_card])
        chosen = [a.path for a in cards if a.path not in used][:_TESTIMONIAL_MAX]
        if chosen:
            for p in chosen:
                used.add(p)
            bindings.append(SocialBinding(
                target_kind="ST-05", page_slot=about_slot, element="testimonials",
                assets=chosen, handle=handle,
            ))

    # ---- (e) fazit author sign-off (no file needed). The author name travels
    #          in `caption`; the role rides the extra `author_role` field. -----
    if fazit_slot is not None and (founder_name or "").strip():
        bindings.append(SocialBinding(
            target_kind="ST-FAZIT", page_slot=fazit_slot, element="fazit_author",
            assets=[], handle=handle, caption=founder_name.strip(),
            author_role=(founder_role or "").strip(),
        ))

    # Sort bindings into a stable, page-order presentation (deterministic
    # output regardless of allocation order above).
    bindings.sort(key=lambda b: (b.page_slot if b.page_slot is not None else 10**9, b.element))
    return SocialPlan(bindings=bindings, dropped=dropped)


def _pick_diverse_scene(
    scene_pool: list[AssetClassification],
    used: set[str],
    picked_roles: set[str],
    picked_shoots: set[str],
) -> Optional[AssetClassification]:
    """Pick the next scene breather, PREFERRING diversity over the already-picked
    breathers. `scene_pool` is appeal-ranked; we scan it in that order and apply
    a tiered preference:

      1. a DIFFERENT role AND a different shoot (most diverse),
      2. else a DIFFERENT role (shoot may repeat),
      3. else a different shoot (role may repeat),
      4. else best-remaining (nothing diverse left — fall back).

    Within each tier the first match wins, so appeal still breaks ties (the pool
    is pre-ranked). Returns None when no unused scene remains.
    """
    candidates = [a for a in scene_pool if a.path not in used]
    if not candidates:
        return None
    # tier 1: new role AND new shoot
    for a in candidates:
        if a.role not in picked_roles and _shoot(a.path) not in picked_shoots:
            return a
    # tier 2: new role (shoot may repeat)
    for a in candidates:
        if a.role not in picked_roles:
            return a
    # tier 3: new shoot (role may repeat)
    for a in candidates:
        if _shoot(a.path) not in picked_shoots:
            return a
    # tier 4: best-remaining
    return candidates[0]


def _founder_avatar(present: list[AssetClassification]) -> str:
    """Best-appeal founder portrait among existing assets, if any."""
    portraits = _ranked([a for a in present if a.role == "founder_portrait"])
    return portraits[0].path if portraits else ""


# ---------------------------------------------------------------------------
# apply_social_plan — the ONLY mutator.
# ---------------------------------------------------------------------------

def _sanitize(basename: str) -> str:
    """Deterministic staged filename component from a source basename."""
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", basename).strip("_")
    return stem or "asset"


def _stage(src_rel: str, *, assets_dir: Path, source_root: Path) -> Optional[str]:
    """Copy `source_root/src_rel` into `assets_dir/ig_<basename>` (idempotent
    overwrite) and return the package-relative path `assets/<name>`. Returns
    None (no crash) when the source file is absent."""
    src = source_root / src_rel
    if not src.exists():
        return None
    name = f"ig_{_sanitize(Path(src_rel).name)}"
    dst = assets_dir / name
    assets_dir.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(src, dst)
    except OSError:
        return None
    return f"assets/{name}"


def _trim_body_to_paras(body, n: int = 2):
    """Trim a body string to its first `n` paragraphs (blank-line separated).
    The copy-fit decision that travels WITH a testimonials binding (gap-audit
    #3 — keeps ST-05 to one page). Non-string bodies are returned unchanged."""
    if not isinstance(body, str):
        return body
    paras = re.split(r"\n\s*\n", body.strip())
    return "\n\n".join(paras[:n])


def apply_social_plan(
    package: dict,
    plan: SocialPlan,
    *,
    assets_dir: Path,
    source_root: Path,
) -> dict:
    """Write the plan onto the package pages. The ONLY mutator. Idempotent:
    applying twice == once (deterministic staged names + overwrite). Never
    binds a missing source file (staging returns None → the page is left at
    its non-social default for that binding)."""
    assets_dir = Path(assets_dir)
    source_root = Path(source_root)
    pages_by_slot = {p.get("slot"): p for p in package.get("pages", [])}

    # US-605: a section may span continuation pages (ST-06/ST-FAZIT). A
    # slot-keyed binding (e.g. fazit_author) belongs to the section's LEAD
    # page (continuation_index 1 / the first page) — the later continuations
    # are the section's own slices, not independent pages.
    for slot in {p.get("slot") for p in package.get("pages", [])}:
        candidates = [p for p in package.get("pages", []) if p.get("slot") == slot]
        if not candidates:
            continue
        lead = candidates[0]
        for c in candidates:
            if c.get("continuation_index") == 1:
                lead = c
                break
        pages_by_slot[slot] = lead

    def stage(rel: str) -> Optional[str]:
        return _stage(rel, assets_dir=assets_dir, source_root=source_root)

    for b in plan.bindings:
        page = pages_by_slot.get(b.page_slot)
        if page is None:
            continue
        data = page.setdefault("data", {})

        if b.element == "profile_grid":
            grid = [s for s in (stage(a) for a in b.assets) if s]
            if not grid:
                continue
            sp = {"handle": b.handle, "grid": grid}
            avatar = stage(_first_avatar(plan)) if _first_avatar(plan) else None
            if avatar:
                sp["avatar"] = avatar
            data["social_post"] = sp

        elif b.element == "scene_breather":
            staged = stage(b.assets[0]) if b.assets else None
            if not staged:
                continue
            # Repoint the page's breathing_bg* asset to the staged scene photo
            # so ST-31 renders the full-bleed photo breather (image_type=scene).
            assets = page.setdefault("assets", [])
            bg = next(
                (a for a in assets if str(a.get("slot_id", "")).startswith("breathing_bg")),
                None,
            )
            if bg is None and assets:
                bg = assets[0]
            if bg is None:
                bg = {"slot_id": "breathing_bg", "status": "resolved"}
                assets.append(bg)
            bg["path"] = staged
            bg["image_type"] = "scene"
            bg["status"] = "resolved"

        elif b.element == "testimonials":
            staged = [s for s in (stage(a) for a in b.assets) if s]
            if not staged:
                continue
            data["testimonials"] = staged
            # The copy-fit that travels WITH the binding (gap-audit #3): trim
            # the About body to its first 2 paragraphs so ST-05 stays 1 page.
            if "body" in data:
                data["body"] = _trim_body_to_paras(data["body"], 2)

        elif b.element == "case_study_post":
            staged = stage(b.assets[0]) if b.assets else None
            if not staged:
                continue
            sp = {"photo": staged, "handle": b.handle}
            # optional founder avatar (2nd bound asset) as the post header.
            if len(b.assets) > 1:
                av = stage(b.assets[1])
                if av:
                    sp["avatar"] = av
            data["social_post"] = sp

        elif b.element == "fazit_author":
            name = (b.caption or "").strip()
            if name:
                role = str(getattr(b, "author_role", "") or "")
                data["author"] = {"name": name, "role": role}

    return package


def _first_avatar(plan: SocialPlan) -> str:
    """The founder avatar path the planner attached to a case-study binding (if
    any) — reused as the profile-grid header avatar for visual consistency."""
    for b in plan.bindings:
        if b.element == "case_study_post" and len(b.assets) > 1:
            return b.assets[1]
    return ""


# ---------------------------------------------------------------------------
# LIVE-PATH MANIFEST DERIVATION (US-307) — deterministic fallback when no
# hand-authored classification exists (a real n8n client has only the IG
# folder). Filename-pattern roles, client-name containment for brand_text,
# testimonial/card markers. NEVER fabricates: an unclassifiable file gets a
# generic role and appeal 0; the planner's own guards still decide homes.
# ---------------------------------------------------------------------------

_ROLE_KEYWORDS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("avatar", "profil", "portrait", "portraet", "face"), "founder_portrait"),
    (("stage", "buehne", "bu+hne", "talk", "speech", "konferenz", "keynote"), "speaking"),
    (("office", "buero", "bu+ro", "desk", "working", "work", "laptop", "arbeiten"), "working"),
    (("interview", "podcast", "gespraech", "studio"), "interview"),
    (("scene", "szene", "setting", "ambiente", "location"), "scene"),
)

_TESTIMONIAL_MARKERS = ("testimonial", "quote", "zitat", "card", "karte", "review")
_CLIENT_PHOTO_HINTS = ("client", "kunde", "partner", "kunden")

_DEFAULT_APPEAL = 0  # never invented; the planner ranks by appeal only among equals


def _classify_filename(stem: str) -> AssetClassification:
    """One deterministic classification from a filename stem."""
    lower = stem.lower()
    role = "content_card"
    for keywords, candidate_role in _ROLE_KEYWORDS:
        if any(keyword in lower for keyword in keywords):
            role = candidate_role
            break
    if role == "content_card" and any(k in lower for k in _CLIENT_PHOTO_HINTS):
        role = "client_photo"

    is_testimonial = any(k in lower for k in _TESTIMONIAL_MARKERS)
    # brand_text: the longest client-like token (letters/digits) that is NOT a
    # generic word. Conservative: only tokens ≥ 4 chars, no common noise.
    tokens = re.findall(r"[a-z0-9äöüß]{4,}", lower)
    noise = {"handle", "ig", "post", "photo", "bild", "foto", "image", "img"}
    brand_text = next((t for t in tokens if t not in noise), "")
    return AssetClassification(
        path="",
        role=role,
        is_testimonial_card=is_testimonial,
        brand_text=brand_text,
        visual_appeal=_DEFAULT_APPEAL,
    )


def build_manifest_from_folder(folder: Path, handle: str) -> AssetManifest:
    """Build an AssetManifest from a client's IG folder (filenames only).

    Deterministic, no network, no LLM: role/flag/brand_text all derive from
    the filename. Files are listed in sorted order so the manifest is stable
    across runs. A folder with no readable image files yields an empty
    manifest (the planner then produces zero bindings — honest, never
    fabricated placements).
    """
    if not folder.is_dir():
        return AssetManifest(handle=handle)
    assets: list[AssetClassification] = []
    for path in sorted(folder.iterdir()):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
            continue
        classification = _classify_filename(path.stem)
        classification.path = path.name
        assets.append(classification)
    return AssetManifest(handle=handle, assets=assets)
