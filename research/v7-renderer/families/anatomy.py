"""Family anatomy: per-family semantic structure over the generic region loop.

Each family declares which anatomy role every region plays. The renderer tags
fragments, regions, and load-bearing elements with those roles so family CSS
can lay out visibly different pages while the frozen contract keeps owning
every element reference.
"""

from __future__ import annotations


# region_id -> anatomy role, per family. Roles are family vocabulary, not
# decoration: CSS grid areas and element treatments key off them.
FAMILY_REGION_ANATOMY: dict[str, dict[str, str]] = {
    "editorial_lead": {
        "headline": "verdict",
        "narrative": "argument",
        "anchor": "proof_anchor",
    },
    "false_belief_stack": {
        "opening": "verdict",
        "beliefs": "objection_ladder",
    },
    "case_narrative": {
        "case_story": "case_story",
        "evidence_rail": "evidence_rail",
    },
    "theory_interpretation": {
        "principle": "argument",
        "mechanism": "mechanism_field",
    },
    "mechanism_spread": {
        "method_frame": "verdict",
        "steps": "process_path",
    },
    "summary_synthesis": {
        "synthesis": "verdict",
        "payoff": "result_band",
    },
    "objection_response": {
        "objection_frame": "verdict",
        "responses": "objection_ladder",
    },
    "collaboration_pathway": {
        "commitment": "result_band",
        "pathway": "process_path",
    },
    "evidence_wall": {
        "trust_header": "verdict",
        "proof_wall": "proof_wall",
    },
    "closing_cta": {
        "closing_statement": "verdict",
        "identity_close": "result_band",
    },
}


def anatomy_role(family_id: str, region_id: str) -> str:
    return FAMILY_REGION_ANATOMY.get(family_id, {}).get(region_id, "supporting")


def element_anatomy_class(family_id: str, element) -> str:
    """Element-level anatomy for the load-bearing devices of a family."""
    kind = element.kind
    if family_id == "case_narrative":
        if kind == "heading":
            return "anatomy-identity"
        if kind == "comparison":
            return "anatomy-before-after"
        if kind in {"quote", "image"}:
            return "anatomy-proof"
        if kind == "stat":
            return "anatomy-result"
    if kind == "stat":
        return "anatomy-figure"
    if kind == "quote":
        return "anatomy-voice"
    return ""
