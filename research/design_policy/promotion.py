"""Design-policy promotion uses the same immutable evidence record."""

from __future__ import annotations

from composition_registry.promotion import PromotionRecord, promote


def promote_policy(record: PromotionRecord):
    if record.artifact_kind != "design_policy":
        raise ValueError("design-policy promotion requires artifact_kind design_policy")
    return promote(record)
