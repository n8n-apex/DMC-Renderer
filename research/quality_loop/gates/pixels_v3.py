"""Raster-backed, multi-feature pixel gate for selected composition families.

Every feature is measured deterministically from the per-face raster with PIL
only, recorded per face in the gate output, and bounded by the family pixel
policy. The accent-budget check that used to be the whole gate is now one
feature among several:

- ``accent_fraction``      fraction of pixels within ``color_tolerance`` of the
                           brand accent (the original check, kept verbatim).
- ``ink_occupancy``        fraction of pixels whose ITU-R 601-2 luminance is at
                           or below ``ink_luminance_max`` (clearly darker than
                           paper): how much of the face carries ink.
- ``vertical_hierarchy``   the top band's share of ink density:
                           ``top / (top + body)`` in [0, 1] (0.0 when the
                           face has no ink at all). Headline-led families
                           score high; anchor-led families score low. A share
                           is used instead of a raw ratio because the ratio
                           explodes unboundedly when body ink approaches
                           zero, which makes bounds meaningless.
- ``whitespace_fraction``  fraction of pixels at or above
                           ``whitespace_luminance_min`` (paper-bright).
- ``type_rhythm_bands``    count of distinct horizontal ink bands: maximal
                           runs of rows whose row ink fraction is at least
                           ``row_ink_fraction_min`` and whose height is at
                           least ``min_band_row_fraction`` of the face.
- ``proof_visibility``     accent fraction measured inside the family's proof
                           band (a vertical slice of the face), so a promised
                           proof marker is visibly present.
- ``image_coverage``       fraction of mid-tone pixels (neither ink nor
                           whitespace): photographic or tinted area.

All bounds live in the family pixel policy as explicit values with a written
rationale; a ``null`` bound means the feature is recorded but not enforced
for that family.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Literal

from PIL import Image
from pydantic import BaseModel, ConfigDict, Field, model_validator


HERE = Path(__file__).resolve().parent
PREPROCESSOR_ROOT = HERE.parents[1] / "preprocessor"
if str(PREPROCESSOR_ROOT) not in sys.path:
    sys.path.insert(0, str(PREPROCESSOR_ROOT))

from contracts_v3.release import (  # noqa: E402
    FailureOwner,
    FailureSeverity,
    QualityFailure,
)


class MeasurementSpec(BaseModel):
    """The exact measurement procedure, recorded in the policy for audit."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ink_luminance_max: int = Field(ge=0, le=255)
    whitespace_luminance_min: int = Field(ge=0, le=255)
    top_band_fraction: float = Field(gt=0, lt=1)
    row_ink_fraction_min: float = Field(gt=0, lt=1)
    min_band_row_fraction: float = Field(gt=0, lt=1)

    @model_validator(mode="after")
    def validate_luminance_zones(self) -> "MeasurementSpec":
        if self.ink_luminance_max >= self.whitespace_luminance_min:
            raise ValueError(
                "ink and whitespace luminance zones must not overlap"
            )
        return self


class FeatureBounds(BaseModel):
    """Enforced bounds for one measured feature; null means record-only."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    min_value: float | None = None
    max_value: float | None = None
    rationale: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_order(self) -> "FeatureBounds":
        if (
            self.min_value is not None
            and self.max_value is not None
            and self.min_value > self.max_value
        ):
            raise ValueError("feature bounds must be ordered")
        return self

    def violation(self, value: float) -> str | None:
        if self.min_value is not None and value < self.min_value:
            return f"{value:.4f} is below the minimum {self.min_value:.4f}"
        if self.max_value is not None and value > self.max_value:
            return f"{value:.4f} is above the maximum {self.max_value:.4f}"
        return None


class FamilyPixelPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    # Accent budget: the original single-feature check, kept as one feature.
    min_accent_fraction: float = Field(ge=0, le=1)
    max_accent_fraction: float = Field(ge=0, le=1)
    color_tolerance: int = Field(default=18, ge=0, le=255)
    accent_budget_opt_out: bool = False
    accent_rationale: str = Field(min_length=1)

    # Measured features.
    ink_occupancy: FeatureBounds
    vertical_hierarchy: FeatureBounds
    whitespace_fraction: FeatureBounds
    type_rhythm_bands: FeatureBounds
    proof_visibility: FeatureBounds
    image_coverage: FeatureBounds

    # Vertical extent of the proof band as fractions of face height.
    proof_band: tuple[float, float] = (0.6, 1.0)

    @model_validator(mode="after")
    def validate_ranges(self) -> "FamilyPixelPolicy":
        if self.min_accent_fraction > self.max_accent_fraction:
            raise ValueError("accent fraction bounds must be ordered")
        top, bottom = self.proof_band
        if not (0.0 <= top < bottom <= 1.0):
            raise ValueError("proof band must be an ordered slice of the face")
        return self


class PixelPolicyV2(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["2.0"] = "2.0"
    policy_id: str
    version: str
    notes: str | None = None
    measurement: MeasurementSpec
    families: dict[str, FamilyPixelPolicy]


class PixelSample(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    face_id: str
    family_id: str
    image_path: str
    accent_rgb: tuple[int, int, int]


class FacePixelFeatures(BaseModel):
    """Every measured feature for one face raster, recorded in gate output."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    face_id: str
    family_id: str
    accent_fraction: float
    ink_occupancy: float
    vertical_hierarchy: float
    whitespace_fraction: float
    type_rhythm_bands: int
    proof_visibility: float
    image_coverage: float


class PixelGateReportV3(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    policy_id: str
    policy_version: str
    faces: tuple[FacePixelFeatures, ...]
    failures: tuple[QualityFailure, ...]


def load_pixel_policy(path: Path) -> PixelPolicyV2:
    return PixelPolicyV2.model_validate(json.loads(path.read_text(encoding="utf-8")))


def _accent_fraction(
    image: Image.Image,
    accent_rgb: tuple[int, int, int],
    color_tolerance: int,
) -> float:
    pixels = image.getdata()
    total = image.width * image.height
    accent = sum(
        all(
            abs(pixel[channel] - accent_rgb[channel]) <= color_tolerance
            for channel in range(3)
        )
        for pixel in pixels
    )
    return accent / total if total else 0.0


def _luminance_histogram(luma: Image.Image) -> list[int]:
    return luma.histogram()


def _zone_fractions(
    histogram: list[int],
    measurement: MeasurementSpec,
) -> tuple[float, float, float]:
    total = sum(histogram)
    if not total:
        return 0.0, 0.0, 0.0
    ink = sum(histogram[: measurement.ink_luminance_max + 1]) / total
    whitespace = sum(histogram[measurement.whitespace_luminance_min :]) / total
    midtone = max(0.0, 1.0 - ink - whitespace)
    return ink, whitespace, midtone


def _ink_density(luma: Image.Image, measurement: MeasurementSpec) -> float:
    histogram = luma.histogram()
    total = sum(histogram)
    if not total:
        return 0.0
    return sum(histogram[: measurement.ink_luminance_max + 1]) / total


def _row_ink_fractions(
    luma: Image.Image,
    measurement: MeasurementSpec,
) -> list[float]:
    ink_mask = luma.point(
        lambda value: 255 if value <= measurement.ink_luminance_max else 0
    )
    row_means = ink_mask.resize((1, ink_mask.height), Image.Resampling.BOX)
    return [pixel / 255.0 for pixel in row_means.getdata()]


def _count_type_bands(
    row_fractions: list[float],
    measurement: MeasurementSpec,
) -> int:
    height = len(row_fractions)
    min_rows = max(2, round(measurement.min_band_row_fraction * height))
    bands = 0
    run = 0
    for fraction in row_fractions:
        if fraction >= measurement.row_ink_fraction_min:
            run += 1
        else:
            if run >= min_rows:
                bands += 1
            run = 0
    if run >= min_rows:
        bands += 1
    return bands


def measure_face_pixels(
    sample: PixelSample,
    family_policy: FamilyPixelPolicy,
    measurement: MeasurementSpec,
) -> FacePixelFeatures:
    """Measure every feature for one face raster. Deterministic, PIL only."""
    with Image.open(sample.image_path) as raw:
        image = raw.convert("RGB")

    luma = image.convert("L")
    histogram = luma.histogram()
    ink, whitespace, midtone = _zone_fractions(histogram, measurement)

    top_rows = max(1, round(measurement.top_band_fraction * luma.height))
    top_band = luma.crop((0, 0, luma.width, top_rows))
    body_band = luma.crop((0, top_rows, luma.width, luma.height))
    top_density = _ink_density(top_band, measurement)
    body_density = (
        _ink_density(body_band, measurement) if body_band.height else 0.0
    )
    density_sum = top_density + body_density
    hierarchy = top_density / density_sum if density_sum else 0.0

    bands = _count_type_bands(_row_ink_fractions(luma, measurement), measurement)

    proof_top = round(family_policy.proof_band[0] * image.height)
    proof_bottom = round(family_policy.proof_band[1] * image.height)
    proof_bottom = max(proof_bottom, proof_top + 1)
    proof_crop = image.crop((0, proof_top, image.width, min(proof_bottom, image.height)))
    proof_visibility = _accent_fraction(
        proof_crop, sample.accent_rgb, family_policy.color_tolerance
    )

    return FacePixelFeatures(
        face_id=sample.face_id,
        family_id=sample.family_id,
        accent_fraction=_accent_fraction(
            image, sample.accent_rgb, family_policy.color_tolerance
        ),
        ink_occupancy=ink,
        vertical_hierarchy=hierarchy,
        whitespace_fraction=whitespace,
        type_rhythm_bands=bands,
        proof_visibility=proof_visibility,
        image_coverage=midtone,
    )


def _feature_failure(
    sample: PixelSample,
    code: str,
    remediation_class: str,
    detail: str,
) -> QualityFailure:
    return QualityFailure(
        owner_stage=FailureOwner.PIXELS,
        code=code,
        severity=FailureSeverity.HARD,
        face_ids=(sample.face_id,),
        remediation_class=remediation_class,
        detail=detail,
    )


_FEATURE_CHECKS: tuple[tuple[str, str, str], ...] = (
    # (feature attribute, failure code, remediation class)
    ("ink_occupancy", "ink_occupancy_out_of_bounds", "rebalance_ink_density"),
    (
        "vertical_hierarchy",
        "vertical_hierarchy_out_of_bounds",
        "restore_headline_hierarchy",
    ),
    (
        "whitespace_fraction",
        "whitespace_fraction_out_of_bounds",
        "restore_whitespace_budget",
    ),
    ("type_rhythm_bands", "type_rhythm_out_of_bounds", "restore_type_rhythm"),
    (
        "proof_visibility",
        "proof_visibility_out_of_bounds",
        "restore_proof_band_marker",
    ),
    ("image_coverage", "image_coverage_out_of_bounds", "rebalance_image_area"),
)


def run_pixel_gate_v3(
    samples: tuple[PixelSample, ...],
    policy: PixelPolicyV2,
) -> PixelGateReportV3:
    """Measure every face and enforce the family policy bounds.

    The report records the full per-face measurements even when every check
    passes, so calibration and review always see the numbers the gate saw.
    """
    faces: list[FacePixelFeatures] = []
    failures: list[QualityFailure] = []
    for sample in samples:
        family_policy = policy.families.get(sample.family_id)
        if family_policy is None:
            failures.append(
                QualityFailure(
                    owner_stage=FailureOwner.PIXELS,
                    code="accent_budget_exceeded",
                    severity=FailureSeverity.HARD,
                    face_ids=(sample.face_id,),
                    remediation_class="define_family_pixel_policy",
                    detail=f"no pixel policy exists for {sample.family_id}",
                )
            )
            continue

        features = measure_face_pixels(sample, family_policy, policy.measurement)
        faces.append(features)

        # A deterministic dead-space detector already existed in the repo and
        # nothing ever called it, so empty panels and dead bands were only ever
        # caught by the reader's eye. It runs here, on the same raster the rest
        # of the gate measures.
        for region in _dead_regions(Path(sample.image_path)):
            failures.append(
                _feature_failure(
                    sample,
                    "dead_space_region",
                    "fill_or_shrink_empty_region",
                    region,
                )
            )

        if not family_policy.accent_budget_opt_out and not (
            family_policy.min_accent_fraction
            <= features.accent_fraction
            <= family_policy.max_accent_fraction
        ):
            failures.append(
                _feature_failure(
                    sample,
                    "accent_budget_exceeded",
                    "rebalance_accent_usage",
                    (
                        f"accent fraction {features.accent_fraction:.4f} is outside "
                        f"{family_policy.min_accent_fraction:.4f} to "
                        f"{family_policy.max_accent_fraction:.4f}"
                    ),
                )
            )

        for attribute, code, remediation_class in _FEATURE_CHECKS:
            bounds: FeatureBounds = getattr(family_policy, attribute)
            violation = bounds.violation(float(getattr(features, attribute)))
            if violation is not None:
                failures.append(
                    _feature_failure(
                        sample,
                        code,
                        remediation_class,
                        f"{attribute} {violation}",
                    )
                )

    return PixelGateReportV3(
        policy_id=policy.policy_id,
        policy_version=policy.version,
        faces=tuple(faces),
        failures=tuple(failures),
    )


def check_pixel_gates_v3(
    samples: tuple[PixelSample, ...],
    policy: PixelPolicyV2,
) -> tuple[QualityFailure, ...]:
    """Compatibility wrapper: the failure tuple of :func:`run_pixel_gate_v3`."""
    return run_pixel_gate_v3(samples, policy).failures


def _dead_regions(image_path: Path) -> tuple[str, ...]:
    """Describe every dead panel or band on one face, or nothing."""
    try:
        from tools.qc_dead_space import find_dead_regions
    except ImportError:  # pragma: no cover - the tool ships with the renderer
        import sys

        renderer_tools = (
            Path(__file__).resolve().parents[3] / "research" / "v7-renderer"
        )
        if str(renderer_tools) not in sys.path:
            sys.path.insert(0, str(renderer_tools))
        try:
            from tools.qc_dead_space import find_dead_regions
        except ImportError:
            return ()
    try:
        return tuple(region.describe() for region in find_dead_regions(image_path))
    except Exception:
        # A detector that cannot read a raster must not mask the other checks.
        return ()
