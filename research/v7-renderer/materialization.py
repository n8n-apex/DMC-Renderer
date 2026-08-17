"""Probe rendered HTML and emit the v3 MaterializationLedger."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright


HERE = Path(__file__).resolve().parent
RESEARCH_ROOT = HERE.parent
PREPROCESSOR_ROOT = RESEARCH_ROOT / "preprocessor"
for dependency_root in (RESEARCH_ROOT, PREPROCESSOR_ROOT):
    if str(dependency_root) not in sys.path:
        sys.path.insert(0, str(dependency_root))

from contracts_v3.materialization import (  # noqa: E402
    BoundingBoxMm,
    ElementObservation,
    MaterializationLedger,
    MaterializationViolation,
)
from contracts_v3.render_contract import FrozenRenderContractV3  # noqa: E402


class MaterializationFailure(RuntimeError):
    def __init__(self, code: str, ledger: MaterializationLedger) -> None:
        self.owner_stage = "materialization_probe"
        self.code = code
        self.ledger = ledger
        self.face_ids = tuple(
            dict.fromkeys(observation.face_id for observation in ledger.observations)
        )
        self.element_ids = tuple(
            dict.fromkeys(
                element_id
                for violation in ledger.violations
                for element_id in violation.element_ids
            )
        )
        super().__init__(f"{code}: {', '.join(ledger.violation_codes)}")


def reconcile_materialization(
    contract: FrozenRenderContractV3,
    observations: tuple[ElementObservation, ...],
    *,
    fail_on_hard: bool = True,
) -> MaterializationLedger:
    observation_by_id = {item.element_id: item for item in observations}
    if len(observation_by_id) != len(observations):
        raise ValueError("materialization observation IDs must be unique")

    expected_ids = {
        element.element_id
        for fragment in contract.fragments
        for element in fragment.elements
    }
    required_ids = {
        element_id
        for fragment in contract.fragments
        for element_id in fragment.expected_materialization.required_element_ids
    }
    minimum_font_by_id = {
        element_id: minimum
        for fragment in contract.fragments
        for element_id, minimum in fragment.expected_materialization.minimum_font_pt.items()
    }
    missing = tuple(sorted(required_ids - set(observation_by_id)))
    violations: list[MaterializationViolation] = []
    if missing:
        violations.append(
            MaterializationViolation(
                code="required_element_missing",
                element_ids=missing,
                detail="required elements were not found in rendered HTML",
            )
        )

    unexpected = tuple(sorted(set(observation_by_id) - expected_ids))
    if unexpected:
        violations.append(
            MaterializationViolation(
                code="unexpected_element",
                element_ids=unexpected,
                detail="rendered HTML contains elements absent from the frozen contract",
            )
        )

    overlap_pairs: set[tuple[str, str]] = set()
    for item in observations:
        if not item.visible:
            violations.append(
                MaterializationViolation(
                    code="element_hidden",
                    element_ids=(item.element_id,),
                    detail="required semantic element is not visible",
                )
            )
        if item.clipped:
            violations.append(
                MaterializationViolation(
                    code="element_clipped",
                    element_ids=(item.element_id,),
                    detail="element geometry extends outside its owning face",
                )
            )
        if item.overflowed:
            violations.append(
                MaterializationViolation(
                    code="element_overflow",
                    element_ids=(item.element_id,),
                    detail="element scroll geometry exceeds its client geometry",
                )
            )
        minimum_font = minimum_font_by_id.get(item.element_id)
        if (
            minimum_font is not None
            and item.font_size_pt is not None
            and item.font_size_pt + 0.01 < minimum_font
        ):
            violations.append(
                MaterializationViolation(
                    code="font_below_contract_minimum",
                    element_ids=(item.element_id,),
                    detail=f"{item.font_size_pt:.2f}pt is below {minimum_font:.2f}pt",
                )
            )
        for other_id in item.intersecting_element_ids:
            pair = tuple(sorted((item.element_id, other_id)))
            if pair[0] != pair[1]:
                overlap_pairs.add(pair)
    for pair in sorted(overlap_pairs):
        violations.append(
            MaterializationViolation(
                code="element_overlap",
                element_ids=pair,
                detail="semantic element bounding boxes intersect",
            )
        )

    ledger = MaterializationLedger(
        contract_id=contract.contract_id,
        observations=tuple(sorted(observations, key=lambda item: item.element_id)),
        missing_required_element_ids=missing,
        violations=tuple(violations),
    )
    if fail_on_hard and ledger.violations:
        code = (
            "required_element_missing"
            if missing
            else "materialization_gate_failed"
        )
        raise MaterializationFailure(code, ledger)
    return ledger


_BROWSER_PROBE = """() => {
  const PX_PER_MM = 96 / 25.4;
  const nodes = [...document.querySelectorAll('[data-element-id]')];
  const records = nodes.map(node => {
    const rect = node.getBoundingClientRect();
    const face = node.closest('[data-face-id]');
    if (!face) throw new Error(`element ${node.dataset.elementId} has no owning face`);
    const faceRect = face.getBoundingClientRect();
    const region = node.closest('.region');
    const regionRect = region ? region.getBoundingClientRect() : faceRect;
    const style = getComputedStyle(node);
    const lineHeightPx = Number.parseFloat(style.lineHeight);
    const fontSizePx = Number.parseFloat(style.fontSize);
    const visible = style.display !== 'none'
      && style.visibility !== 'hidden'
      && Number.parseFloat(style.opacity) > 0
      && rect.width > 0 && rect.height > 0;
    const clipped = rect.left < faceRect.left - 0.5
      || rect.top < faceRect.top - 0.5
      || rect.right > faceRect.right + 0.5
      || rect.bottom > faceRect.bottom + 0.5
      || rect.left < regionRect.left - 0.5
      || rect.top < regionRect.top - 0.5
      || rect.right > regionRect.right + 0.5
      || rect.bottom > regionRect.bottom + 0.5;
    const overflowed = (style.overflowX !== 'visible'
        && node.scrollWidth > node.clientWidth + 1)
      || (style.overflowY !== 'visible'
        && node.scrollHeight > node.clientHeight + 1);
    return {
      node,
      rect,
      raw: {
        element_id: node.dataset.elementId,
        face_id: face.dataset.faceId,
        region_id: node.dataset.regionId,
        content_ref: node.dataset.contentRef || null,
        claim_id: node.dataset.claimId || null,
        asset_id: node.dataset.assetId || null,
        bounding_box_mm: {
          x: (rect.left - faceRect.left) / PX_PER_MM,
          y: (rect.top - faceRect.top) / PX_PER_MM,
          width: rect.width / PX_PER_MM,
          height: rect.height / PX_PER_MM
        },
        font_size_pt: Number.isFinite(fontSizePx) ? fontSizePx * 72 / 96 : null,
        line_height_pt: Number.isFinite(lineHeightPx) ? lineHeightPx * 72 / 96 : null,
        visible,
        clipped,
        overflowed,
        foreground_color: style.color,
        background_color: style.backgroundColor,
        intersecting_element_ids: []
      }
    };
  });
  for (let i = 0; i < records.length; i += 1) {
    for (let j = i + 1; j < records.length; j += 1) {
      const a = records[i];
      const b = records[j];
      if (a.raw.face_id !== b.raw.face_id) continue;
      const xOverlap = Math.min(a.rect.right, b.rect.right) - Math.max(a.rect.left, b.rect.left);
      const yOverlap = Math.min(a.rect.bottom, b.rect.bottom) - Math.max(a.rect.top, b.rect.top);
      if (xOverlap > 0.5 && yOverlap > 0.5) {
        a.raw.intersecting_element_ids.push(b.raw.element_id);
        b.raw.intersecting_element_ids.push(a.raw.element_id);
      }
    }
  }
  return records.map(record => record.raw);
}"""


def probe_materialization(
    html_path: Path,
    contract: FrozenRenderContractV3,
    *,
    output_path: Path,
    fail_on_hard: bool = True,
) -> MaterializationLedger:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1800, "height": 1200})
        page.goto(html_path.resolve().as_uri(), wait_until="networkidle")
        raw_observations = page.evaluate(_BROWSER_PROBE)
        browser.close()
    observations = tuple(
        ElementObservation.model_validate(item) for item in raw_observations
    )
    ledger = reconcile_materialization(
        contract,
        observations,
        fail_on_hard=False,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            ledger.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    if fail_on_hard and ledger.violations:
        code = (
            "required_element_missing"
            if ledger.missing_required_element_ids
            else "materialization_gate_failed"
        )
        raise MaterializationFailure(code, ledger)
    return ledger
