"""Package loader — reads the pre-processor's resolved_package.json.

Turns a package directory into a typed LoadedPackage the assembler
consumes. FAIL LOUD when the manifest is missing or the brand block is
incomplete (parse_brand_tokens raises ValueError naming the missing
field) — the renderer must not render against a half-resolved package.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Allow flat imports from the chassis package.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from brand_tokens import BrandConfig, parse_brand_tokens  # noqa: E402
from tokens.compile_tokens import BrandAxes  # noqa: E402


@dataclass
class LoadedPackage:
    brand: BrandConfig
    pages: list[dict]            # package pages verbatim (incl. page_numbers)
    report_assets: list[dict]
    fonts: dict
    package_dir: Path
    axes: BrandAxes = field(default_factory=BrandAxes)


def load_package(package_dir: Path) -> LoadedPackage:
    package_dir = Path(package_dir).resolve()
    manifest_path = package_dir / "resolved_package.json"
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"resolved_package.json not found in {package_dir}. The renderer "
            f"consumes a pre-processor package; point it at a directory that "
            f"contains resolved_package.json."
        )

    pkg = json.loads(manifest_path.read_text(encoding="utf-8"))

    # FAIL LOUD on incomplete brand (reuses the chassis's 10-field gate).
    brand = parse_brand_tokens(pkg.get("brand", {}))

    pages = pkg.get("pages", [])
    if not isinstance(pages, list):
        raise ValueError(
            f"resolved_package.json 'pages' must be a list; got {type(pages)}."
        )

    # v2.0 contract: prefer the 7-field top-level `axes`. The legacy 4-field
    # `brand_axes` is a TRANSITIONAL v1 duplicate. A v1 (brand_axes-only) package
    # still LOADS for back-compat, but the missing palette/qr_enabled/density would
    # otherwise default SILENTLY and change the render -- so warn loudly (addition
    # B: make the default non-silent rather than breaking intentional back-compat).
    _ax = pkg.get("axes")
    if _ax is None:
        _ax = pkg.get("brand_axes")
        if _ax:
            import warnings
            warnings.warn(
                "resolved_package.json carries legacy 'brand_axes' (4 fields) but "
                "no v2.0 'axes' (7 fields): palette/qr_enabled/density are "
                "defaulting and may not match the brand. Re-build so the package "
                "emits top-level 'axes'.",
                stacklevel=2,
            )
        else:
            _ax = {}
    _known = frozenset(
        ("headline_type", "ground_mode", "texture", "accent_mechanic",
         "palette", "qr_enabled", "density")
    )
    axes = BrandAxes(**{k: v for k, v in _ax.items() if k in _known})

    return LoadedPackage(
        brand=brand,
        pages=pages,
        report_assets=pkg.get("report_assets", []) or [],
        fonts=pkg.get("fonts", {}) or {},
        package_dir=package_dir,
        axes=axes,
    )
