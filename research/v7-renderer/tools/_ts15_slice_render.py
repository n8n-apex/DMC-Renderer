"""TS-1.5 dev helper: render a PERSISTENT 3-page mixed-format treatment slice.

Mirrors tests/test_treatment_slice.py but writes into a REAL output dir
(output/ts15_slice/) instead of a pytest tmp dir, so the controller can eyeball
the rendered PNGs against the mockups:
  output/ts15_slice/report-p1.png  -> page 0 (bypass ST-01 cover, A4)
  output/ts15_slice/report-p2.png  -> page 2 (ST-05 About, editorial, A3-land)
  output/ts15_slice/report-p3.png  -> page 15 (ST-06, horizontal_process, A3-land)

The slice reuses the real apex package assets (copied into a temp pkg dir) so the
About page's founder-identity portrait resolves, then sets pages = [0, 2, 15] and
renders the real Chromium path via assembler.render_package.

Run (from the repo root, venv active, DYLD set):
  python tools/_ts15_slice_render.py
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from assembler import render_package  # noqa: E402

OUT_DIR = ROOT / "output" / "ts15_slice"
SLICE_INDICES = [0, 2, 15]  # bypass cover, ST-05 About (editorial), ST-06 (process)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="ts15_slice_") as tmp:
        tmp_path = Path(tmp)
        pkg_dir = tmp_path / "pkg"
        shutil.copytree(ROOT / "fixtures" / "apex", pkg_dir)

        manifest_path = pkg_dir / "resolved_package.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["pages"] = [manifest["pages"][i] for i in SLICE_INDICES]
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        res = render_package(pkg_dir, OUT_DIR, engine="chromium", treatments=True)

    print(f"page_count: {res.page_count}")
    print(f"warnings:   {res.warnings}")
    print(f"overflow:   {getattr(res, 'overflow', None)}")
    print("PNGs:")
    for png in sorted(OUT_DIR.glob("report-p*.png")):
        print(f"  {png}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
