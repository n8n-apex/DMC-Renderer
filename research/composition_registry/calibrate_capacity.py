"""Write browser-backed capacity calibration measurements.

This command records observations. It never rewrites the approved composition
registry, so measurement changes cannot silently alter production policy.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Any


Measurement = Mapping[str, int | float | str | bool | None]
Measurer = Callable[[Mapping[str, Any]], Measurement]


def _playwright_measure(sample: Mapping[str, Any]) -> Measurement:
    """Measure a single HTML specimen in Chromium."""

    from playwright.sync_api import sync_playwright

    html = str(sample.get("html", ""))
    selector = str(sample.get("selector", "#capacity-target"))
    viewport_width = int(sample.get("viewport_width", 1200))
    viewport_height = int(sample.get("viewport_height", 900))

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(
            viewport={"width": viewport_width, "height": viewport_height}
        )
        page.set_content(html)
        element = page.locator(selector)
        if element.count() != 1:
            browser.close()
            raise ValueError(
                f"Expected exactly one calibration element for {selector!r}"
            )
        result = element.evaluate(
            """node => {
                const style = getComputedStyle(node);
                const rect = node.getBoundingClientRect();
                const lineHeight = Number.parseFloat(style.lineHeight);
                return {
                    width_px: rect.width,
                    height_px: rect.height,
                    line_height_px: Number.isFinite(lineHeight) ? lineHeight : null,
                    wrapped_line_count: Number.isFinite(lineHeight) && lineHeight > 0
                        ? Math.round(rect.height / lineHeight)
                        : null,
                    scroll_height_px: node.scrollHeight,
                    overflowed: node.scrollHeight > node.clientHeight + 0.5
                };
            }"""
        )
        browser.close()
    return result


def write_calibration_report(
    samples: Iterable[Mapping[str, Any]],
    output_path: Path,
    *,
    measurer: Measurer | None = None,
) -> dict[str, Any]:
    """Measure samples and write a deterministic, separate report artifact."""

    measurement_function = measurer or _playwright_measure
    measurements: list[dict[str, Any]] = []
    for sample in samples:
        sample_id = str(sample["sample_id"])
        measurement = dict(measurement_function(sample))
        measurements.append({"sample_id": sample_id, **measurement})

    report = {
        "schema_version": "1.0",
        "measurements": measurements,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    payload = json.loads(args.samples.read_text(encoding="utf-8"))
    samples = payload["samples"] if isinstance(payload, dict) else payload
    write_calibration_report(samples, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
