"""Layer-B brand profile: the per-client treatment axes.

`richard-grammar-v2.md` §4 defines sixteen axes that decide how a client's
report LOOKS: ground mode, texture, headline construction, belief-card
treatment, image modes, case geometry. It states one hard rule:

    "A client profile MUST supply every axis below. RULE [HARD]: a profile
     that omits any axis is REJECTED loud at config-time - never defaulted."

`render_v3.py` called `compile_tokens(brand, BrandAxes())` with no
arguments, so every client got the same defaults and every report looked
identical. That is the whole reason the output reads as boxes with text.

This module is the fix at the type level: every axis is required, so a
profile that omits one cannot be constructed. There is no default
BrandProfile and there must never be one.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


AccentMechanic = Literal["contrasting_hue", "tonal_same_hue"]
GroundMode = Literal[
    "cream_textured",
    "cool_light",
    "role_split",
    "tri",
    "saturated_dark_light",
]
Texture = Literal["marble_paper", "crumpled_paper", "smooth", "photo"]
HeadlineType = Literal["serif", "sans", "sans_allcaps"]
HeadlineConstruction = Literal[
    "single_colour", "accent_word", "two_tone_two_weight", "tonal_accent_word"
]
ImageMode = Literal[
    "full_bleed_photo",
    "cutout_figure",
    "cutout_bleed",
    "framed_rect",
    "3d_render",
    "device_mockup",
    "duotone",
    "product_shot",
    "round_portrait",
]
PageUnit = Literal["spread", "single_page"]
CaseGeometry = Literal["RRW", "LRP", "NR", "BAND"]
BeliefTreatment = Literal[
    "dark_box", "ghost_numeral", "connector_spine", "plain_numbered"
]

# §4.0: body text colour is the chassis default for ALL profiles, never a
# per-client value. DMC_InDesign_Spec_v1.md L243.
BODY_INK = "#333333"


class AccentRoles(BaseModel):
    """Which accent each role takes. §4.0 axis A."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    cover: str
    cta: str
    body_editorial: str
    data_emphasis: str
    icons: str
    url: str
    kicker: str


class BrandProfile(BaseModel):
    """One client's complete Layer-B profile. No axis has a default.

    Constructing this with a missing axis raises, which is the grammar's
    hard rule expressed as a type rather than as a comment nobody reads.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    profile_id: str = Field(min_length=1)
    client_name: str = Field(min_length=1)

    primary_dark: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")   # P
    accents: AccentRoles                                       # A
    accent_mechanic: AccentMechanic                            # M
    ground_mode: GroundMode                                    # G
    texture: Texture                                           # X
    headline_type: HeadlineType                                # H
    headline_construction: HeadlineConstruction                # HC
    image_modes: tuple[ImageMode, ...] = Field(min_length=1)   # I
    page_unit: PageUnit                                        # S
    case_geometry: CaseGeometry                                # CG
    belief_treatment: BeliefTreatment                          # N
    rating_widget: str = Field(min_length=1)                   # RW
    font_head: str = Field(min_length=1)
    font_body: str = Field(min_length=1)
    motif: str | None = None                                   # optional by spec

    def to_axes_kwargs(self) -> dict[str, str]:
        """The subset of axes the token compiler already understands.

        Its `ground_mode` vocabulary is coarser than the grammar's, so the
        five specified grounds fold onto light/dark by whether the profile
        puts type on a saturated field.
        """
        dark_grounds = {"role_split", "tri", "saturated_dark_light"}
        return {
            "headline_type": self.headline_type,
            "ground_mode": "dark" if self.ground_mode in dark_grounds else "light",
            "texture": self.texture,
            "accent_mechanic": self.accent_mechanic,
        }

    def data_attributes(self) -> dict[str, str]:
        """The axes as DOM attributes, so CSS can key on the treatment.

        Axes N, HC, G and X had no route to the stylesheet at all. This is
        that route: one attribute per axis on the fragment element.
        """
        return {
            "data-accent-mechanic": self.accent_mechanic,
            "data-ground-mode": self.ground_mode,
            "data-texture": self.texture,
            "data-headline-type": self.headline_type,
            "data-headline-construction": self.headline_construction,
            "data-case-geometry": self.case_geometry,
            "data-belief-treatment": self.belief_treatment,
            "data-page-unit": self.page_unit,
            "data-image-modes": " ".join(self.image_modes),
            "data-motif": self.motif_kind(),
        }

    def motif_kind(self) -> str:
        """The drawn device this profile's motif prose names.

        The grammar writes motifs as description ("flowing gold ribbon
        footer", "rotated side-label + blue corner tab", "thin wing/swoosh
        + faint dot-arc"). They are drawn in CSS rather than imported, so a
        missing asset can never drop a client's signature.
        """
        text = (self.motif or "").lower()
        if "ribbon" in text:
            return "ribbon"
        if "corner tab" in text or "corner-tab" in text:
            return "corner_tab"
        if "swoosh" in text or "wing" in text:
            return "swoosh"
        return "none"


class ProfileMissing(ValueError):
    """No profile exists for this client, and defaulting one is forbidden."""

    def __init__(self, profile_id: str, available: tuple[str, ...]) -> None:
        self.profile_id = profile_id
        super().__init__(
            f"no brand profile for {profile_id!r}; the grammar forbids "
            f"defaulting one. Available: {', '.join(available) or 'none'}"
        )


PROFILES_PATH = Path(__file__).resolve().parent / "brand-profiles.json"


def load_profiles(path: Path | None = None) -> dict[str, BrandProfile]:
    raw = json.loads((path or PROFILES_PATH).read_text(encoding="utf-8"))
    return {
        item["profile_id"]: BrandProfile.model_validate(item)
        for item in raw["profiles"]
    }


def profile_for(profile_id: str, path: Path | None = None) -> BrandProfile:
    """The client's profile, or a loud refusal. Never a default."""
    profiles = load_profiles(path)
    if profile_id not in profiles:
        raise ProfileMissing(profile_id, tuple(sorted(profiles)))
    return profiles[profile_id]
