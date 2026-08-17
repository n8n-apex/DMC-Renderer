"""Shared dataclasses for the founder-asset scraper contract.

Every channel client returns a `ScrapeResult` carrying zero or more
`Candidate` images plus a `ChannelStatus` describing how the fetch went
(ok / blocked / empty / error). Downstream selection + gating reads only
these shapes — never the network.

Pydantic v2 BaseModel to match repo style (models_charts.py /
models_pagedata.py). Brand-agnostic: shapes only, no client value.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# Permissive: preserve unexpected scraper metadata rather than reject it.
_Permissive = ConfigDict(extra="allow")

# How a single channel fetch turned out.
ChannelStatus = Literal["ok", "blocked", "empty", "error"]


class Candidate(BaseModel):
    """One downloaded image considered for a founder slot."""

    model_config = _Permissive

    source: str  # "youtube" | "instagram"
    kind: str  # "avatar" | "banner" | "thumbnail" | "frame" | "post"
    local_path: str
    width: int
    height: int
    meta: dict = Field(default_factory=dict)


class ScrapeResult(BaseModel):
    """Outcome of fetching candidates from one channel."""

    model_config = _Permissive

    source: str
    status: ChannelStatus
    candidates: list[Candidate] = Field(default_factory=list)
    reason: Optional[str] = None


# --- asset understanding + routing (Task 1) ---------------------------------
#
# Per the design (docs/.../2026-06-04-founder-social-mockup-design.md §4.2-4.3):
# the VIS layer judges WHAT each asset depicts (its role) + whether it carries
# overlaid graphic text + how visually appealing it is (0-3); the router then
# places each into the report element where it adds the most appeal, flagging
# (never fabricating) any element with no suitable real asset.

# The closed role vocabulary — what an asset DEPICTS (brand-agnostic).
ASSET_ROLES = (
    "founder_portrait",
    "founder_working",
    "founder_speaking",
    "group_team",
    "lifestyle",
    "content_card",
    "logo",
    "other",
)
AssetRole = Literal[
    "founder_portrait",
    "founder_working",
    "founder_speaking",
    "group_team",
    "lifestyle",
    "content_card",
    "logo",
    "other",
]


class AssetJudgement(BaseModel):
    """The VIS verdict for one asset: role + overlaid-text + appeal (0-3)."""

    model_config = _Permissive

    role: AssetRole
    has_overlaid_text: bool = False
    visual_appeal: int = 0  # 0-3
    notes: str = ""


class RoutedElement(BaseModel):
    """A report element's routing outcome: filled with a real asset, or flagged.

    ``flagged`` (with a ``reason``) is the honest "no suitable real asset"
    outcome — never a fabricated/placeholder fill.
    """

    model_config = _Permissive

    element: str
    status: Literal["filled", "flagged"]
    path: Optional[str] = None
    role: Optional[str] = None
    appeal: Optional[int] = None
    reason: Optional[str] = None
