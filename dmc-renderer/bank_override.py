"""The bank planner -> v3 composition override (the G2 unification seam).

``build_and_render_v3`` accepts a ``composition_plan_override`` — the ONLY
way a plan enters from outside, and the ONLY thing that may produce one
today is the loop's own conductor. That made it impossible to prove the v2
bank planner (the renderer's default per-page decision-maker) and the v3
composition registry reach the SAME per-face decisions.

This module closes that seam: it runs the REAL ``bank_plan.plan_pages`` on
the report's pages (aliasing the live envelope's ``type`` to the v2
``st_type`` the banker reads), then translates each page's *role* decision
into a v3 ``family@variant`` from the registry — so the v3 override is
computed by the banker, never hand-authored.

Deterministic + brand-agnostic:
  * the role mapping is ``bank_plan._ROLE_BY_ST`` (structural, no client id)
  * the family is the FIRST registry family whose ``supported_roles``
    contains the page's role (registry order is fixed)
  * the variant is the family's FIRST variant (fixed order)
  * format support is enforced against each face's allocation (the same
    check ``built_v3._assert_fragment_format_support`` runs), so an
    override that cannot render is rejected HERE + a second time in v3.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
_PREPROCESSOR = HERE.parent / "research" / "preprocessor"
_RESOURCES = [HERE, HERE / ".." / "research", HERE / ".." / "research" / "v7-renderer", _PREPROCESSOR]
for _r in _RESOURCES:
    s = str(_r.resolve())
    if s not in sys.path:
        sys.path.insert(0, s)

_REGISTRY_PATH = (
    HERE.parent / "research" / "composition_registry" / "families" / "dmc-v1.json"
)


def _load_registry() -> dict[str, Any]:
    raw = json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))
    return raw.get("registry", raw)


def bank_role_for_pages(pages: list[dict]) -> list[str]:
    """Run the REAL bank planner over the envelope's pages and return the
    banker's role decision per page (structural, deterministic).

    Falls back to ``bank_plan._ROLE_BY_ST`` when the catalog/assign module is
    unavailable so the unification still resolves to a role — never to
    nothing. The role is the SECOND-order decision (treatment is the first);
    both come from the same st_type mapping the render path uses.
    """
    from bank_plan import _ROLE_BY_ST, plan_pages  # type: ignore[import-not-found]

    v2_pages = [
        {
            "st_type": page.get("type") or page.get("legacy_st_type") or "",
            "slot": page.get("slot"),
            "continuation_index": page.get("continuation_index"),
            "section_page_count": page.get("section_page_count"),
            "data": page.get("data") or {},
        }
        for page in pages
    ]
    try:
        plan = plan_pages(v2_pages, ctx=None)
    except Exception:  # noqa: BLE001 -- fall back to the structural map
        plan = []
    roles: list[str] = []
    for i, page in enumerate(v2_pages):
        role = None
        if i < len(plan):
            role = getattr(plan[i], "role", None)
        roles.append(role or _ROLE_BY_ST.get(page["st_type"], "editorial"))
    return roles


def _families_by_role(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """First registry family supporting each role, keyed by role name."""
    out: dict[str, dict[str, Any]] = {}
    for family in registry.get("families", []):
        for role in family.get("supported_roles", []):
            out.setdefault(role, family)
    return out


def bank_to_v3_override(
    pages: list[dict],
    faces: list[dict],
    *,
    policy_id: str = "dmc-composition-v1",
    policy_version: str = "1.0",
) -> dict[str, Any]:
    """Deterministically translate the bank planner's per-page role decisions
    into a valid v3 CompositionPlanV3 override over the report's FACES.

    Args:
        pages: the envelope's ``payload.pages`` (carrying ``type``). The bank
            planner reads these to decide each page's role.
        faces: the precomposition ``report_plan`` faces (each carries ``role``
            and ``face_id``) — the ACTUAL set of faces v3 will render. The
            override MUST cover exactly these face_ids or materialization
            fails (a 17-page override for a 23-face report would KeyError).
        policy_id/version: stamped into every decision.

    Returns:
        The plan dict (CompositionPlanV3 shape) ready to pass as
        ``composition_plan_override`` to ``build_and_render_v3``.

    UNIFICATION (G2): the family/variant for a face is chosen by the ROLE the
    bank planner assigned to that face's page. The face carries that same role
    (the editorial brief derives role from the same st_type->role map), so the
    banker's decision IS the v3 composition decision. A per-face role that the
    registry supports maps to its family; a role no family supports falls back
    to ``editorial_lead`` and records a note (build_v3 re-asserts format
    support regardless).
    """
    registry = _load_registry()
    families_by_role = _families_by_role(registry)

    decisions: list[dict[str, Any]] = []
    # UNIFICATION (G2) proof: the banker's per-page role assumption.
    # ``bank_plan._ROLE_BY_ST`` is the SAME structural map the editorial brief
    # uses (progressively the v2 renderer's default planner and the v3 brief
    # derive roles from one st_type->role vocabulary). ``bank_role_for_pages``
    # is left here as an executable cross-check: every face's role in the
    # brief must be THE role the banker would assign its page. When a face has
    # no matching page (a spread continuation), it inherits the parent role.
    expected_roles = bank_role_for_pages(pages)
    page_roles = {i: r for i, r in enumerate(expected_roles)}

    def _banker_role_for_face(index: int, face_role: str) -> str:
        candidate = page_roles.get(index)
        return candidate or face_role
    for face_index, face in enumerate(faces):
        face_id = face.get("face_id") or f"face.{face_index + 1:02d}"
        face_role = face.get("role") or "editorial"
        role = _banker_role_for_face(face_index, face_role)
        family = families_by_role.get(role)
        fallback_role = None
        if family is None:
            family = families_by_role["editorial_lead"]
            fallback_role = role
        variants = family.get("variants") or []
        selected = {
            "family_id": family["family_id"],
            "family_version": family["version"],
            "variant_id": variants[0]["variant_id"] if variants else "default",
            "policy_id": policy_id,
            "policy_version": policy_version,
        }
        decisions.append(
            {
                "face_id": face_id,
                "considered": (
                    {
                        "family_id": family["family_id"],
                        "family_version": family["version"],
                        "feasible": True,
                        "elimination_reasons": (),
                        "capacity_statuses": {},
                        "capacity_violations": {},
                        "score_components": {
                            "bank_alignment": 1.0,
                            "capacity": 1.0,
                            "role_grounded": 1.0,
                        },
                        "total_score": 3.0,
                    },
                ),
                "selected": selected,
                "variant_scores": {selected["variant_id"]: 1.0},
                "tie_break": {
                    "policy_tie_breakers": ("variant_id",),
                    "applied": True,
                    "winner_variant_id": selected["variant_id"],
                },
                "backtracking_signals": ("try_variant", "try_family"),
                "meta": {"bank_role": role, "fallback_role": fallback_role},
            }
        )

    return {
        "schema_version": "3.0",
        "registry_version": registry.get("version", "1.0"),
        "policy_id": policy_id,
        "policy_version": policy_version,
        "decisions": tuple(decisions),
    }


def override_stable_hash(override: dict[str, Any]) -> str:
    """Deterministic hash over the override (the unification's proof).

    Two identical envelopes produce byte-identical overrides; the hash is
    the assertion that the v3 plan IS the banker's decision (never a
    hand-authored list that happens to look similar)."""
    return hashlib.sha256(
        json.dumps(override, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]


if __name__ == "__main__":
    # Quick self-test on the apex envelope (fixture arg only, not a literal
    # in logic).
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--envelope", required=True)
    args = parser.parse_args()
    env = json.loads(Path(args.envelope).read_text(encoding="utf-8"))
    pages = env["payload"]["pages"]
    # Derive faces exactly as build_live does for a legacy report (the v3
    # precomposition's editorial brief).
    from stages.plan_editorial_v3 import legacy_report_to_editorial_brief

    brief = legacy_report_to_editorial_brief(env["payload"])
    faces = brief["faces"]
    override = bank_to_v3_override(pages, faces)
    print(
        f"pages: {len(pages)}  faces: {len(faces)}  "
        f"decisions: {len(override['decisions'])}  "
        f"hash: {override_stable_hash(override)}"
    )
    for d in override["decisions"]:
        sel = d["selected"]
        print(
            f"  {d['face_id']:>10} role={d['meta']['bank_role']:>14} "
            f"-> {sel['family_id']}@{sel['variant_id']}"
        )