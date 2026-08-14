"""Release failures derived from observed semantic element geometry."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


HERE = Path(__file__).resolve().parent
PREPROCESSOR_ROOT = HERE.parents[1] / "preprocessor"
if str(PREPROCESSOR_ROOT) not in sys.path:
    sys.path.insert(0, str(PREPROCESSOR_ROOT))

from contracts_v3.materialization import MaterializationLedger  # noqa: E402
from contracts_v3.release import (  # noqa: E402
    FailureOwner,
    FailureSeverity,
    QualityFailure,
)
from contracts_v3.render_contract import FrozenRenderContractV3  # noqa: E402


class MaterializationGatePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    safe_inset_mm: float = Field(default=6, ge=0)
    minimum_contrast_ratio: float = Field(default=4.5, gt=1)
    allowed_overlap_pairs: tuple[tuple[str, str], ...] = ()


_COLOR_RE = re.compile(
    r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)(?:\s*,\s*([\d.]+))?\s*\)"
)
_TEXT_KINDS = {"heading", "body", "quote", "stat", "comparison", "process", "source"}


def _rgb(value: str) -> tuple[int, int, int] | None:
    match = _COLOR_RE.fullmatch(value.strip())
    if match is None:
        return None
    alpha = float(match.group(4)) if match.group(4) is not None else 1.0
    if alpha == 0:
        return None
    return tuple(int(match.group(index)) for index in range(1, 4))


def _luminance(rgb: tuple[int, int, int]) -> float:
    channels = []
    for value in rgb:
        normalized = value / 255
        channels.append(
            normalized / 12.92
            if normalized <= 0.04045
            else ((normalized + 0.055) / 1.055) ** 2.4
        )
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def _contrast_ratio(foreground: str, background: str) -> float | None:
    foreground_rgb = _rgb(foreground)
    background_rgb = _rgb(background)
    if foreground_rgb is None or background_rgb is None:
        return None
    first = _luminance(foreground_rgb)
    second = _luminance(background_rgb)
    light, dark = max(first, second), min(first, second)
    return (light + 0.05) / (dark + 0.05)


def _failure(
    code: str,
    detail: str,
    *,
    face_ids: tuple[str, ...] = (),
    element_ids: tuple[str, ...] = (),
) -> QualityFailure:
    return QualityFailure(
        owner_stage=FailureOwner.MATERIALIZATION,
        code=code,
        severity=FailureSeverity.HARD,
        face_ids=face_ids,
        element_ids=element_ids,
        remediation_class="revise_composition_or_copyfit",
        detail=detail,
    )


def check_materialization_v3(
    contract: FrozenRenderContractV3,
    ledger: MaterializationLedger,
    *,
    policy: MaterializationGatePolicy | None = None,
) -> tuple[QualityFailure, ...]:
    active_policy = policy or MaterializationGatePolicy()
    allowed_pairs = {
        tuple(sorted(pair)) for pair in active_policy.allowed_overlap_pairs
    }
    element_by_id = {
        element.element_id: element
        for fragment in contract.fragments
        for element in fragment.elements
    }
    failures: list[QualityFailure] = []
    for violation in ledger.violations:
        pair = tuple(sorted(violation.element_ids))
        if violation.code == "element_overlap" and pair in allowed_pairs:
            continue
        face_ids = tuple(
            dict.fromkeys(
                ".".join(element_id.split(".", 2)[:2])
                for element_id in violation.element_ids
                if element_id.startswith("face.")
            )
        )
        failures.append(
            _failure(
                violation.code,
                violation.detail,
                face_ids=face_ids,
                element_ids=violation.element_ids,
            )
        )

    for observation in ledger.observations:
        element = element_by_id.get(observation.element_id)
        if element is None or element.kind not in _TEXT_KINDS:
            continue
        box = observation.bounding_box_mm
        inset = active_policy.safe_inset_mm
        outside = (
            box.x < inset
            or box.y < inset
            or box.x + box.width > 210 - inset
            or box.y + box.height > 297 - inset
        )
        if outside:
            failures.append(
                _failure(
                    "content_outside_safe_bounds",
                    f"{observation.element_id} crosses the {inset:.1f} mm safe inset",
                    face_ids=(observation.face_id,),
                    element_ids=(observation.element_id,),
                )
            )
        contrast = _contrast_ratio(
            observation.foreground_color,
            observation.background_color,
        )
        if contrast is not None and contrast < active_policy.minimum_contrast_ratio:
            failures.append(
                _failure(
                    "low_contrast",
                    (
                        f"{observation.element_id} contrast {contrast:.2f} is below "
                        f"{active_policy.minimum_contrast_ratio:.2f}"
                    ),
                    face_ids=(observation.face_id,),
                    element_ids=(observation.element_id,),
                )
            )
    return tuple(failures)
