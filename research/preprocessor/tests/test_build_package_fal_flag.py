"""OFFLINE wiring test for build_package's --fal flag (Phase 3).

NO network / fal / LLM calls and NO fixture regeneration: this only exercises
the arg-parser + flag plumbing of the apex fixture builder. It imports the
build_package module the same way build_package imports the preprocessor (by
adding the v7-renderer apex fixtures dir to sys.path), then asserts:

  * `_parse_args([])`        → fal is OFF by default (offline reproducible path)
  * `_parse_args(["--fal"])` → fal is ON (real generate_assets path)
  * the module still exposes `_build_asset_plan` (the offline fallback is kept)
    and references `generate_assets` (the real fal path is wired in)
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

# preprocessor root = parent of tests/  → research/preprocessor
_PREPROCESSOR_ROOT = Path(__file__).resolve().parent.parent
_BUILD_PACKAGE = (
    _PREPROCESSOR_ROOT.parent
    / "v7-renderer" / "fixtures" / "apex" / "build_package.py"
)


def _load_build_package():
    """Import build_package.py by path.

    build_package itself does `sys.path.insert(0, PREPROCESSOR)` at import time
    so its `from models import ...` / `from stages.X import ...` resolve; the
    conftest already put the preprocessor root on sys.path, so this is a no-op
    duplicate that stays offline (no stage code runs at import).
    """
    if str(_PREPROCESSOR_ROOT) not in sys.path:
        sys.path.insert(0, str(_PREPROCESSOR_ROOT))
    spec = importlib.util.spec_from_file_location(
        "apex_build_package", _BUILD_PACKAGE
    )
    assert spec and spec.loader, f"could not load {_BUILD_PACKAGE}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_default_is_offline_no_fal():
    bp = _load_build_package()
    args = bp._parse_args([])
    assert args.fal is False, "default build must stay offline (fal OFF)"


def test_fal_flag_recognized():
    bp = _load_build_package()
    args = bp._parse_args(["--fal"])
    assert args.fal is True, "--fal must switch on the real generate_assets path"


def test_offline_fallback_helper_intact():
    """The offline `_build_asset_plan` path must still exist (it is the
    no-keys reproducible default), AND the real fal generator must be wired in."""
    bp = _load_build_package()
    assert hasattr(bp, "_build_asset_plan"), "offline _build_asset_plan removed"
    assert hasattr(bp, "generate_assets"), "real generate_assets not imported"


def test_no_fal_marker_written_by_import_or_parse():
    """Importing the module and parsing args must NEVER write the .fal_active
    marker — only a completed --fal build does (and that is not run here)."""
    bp = _load_build_package()
    bp._parse_args(["--fal"])
    marker = (
        _PREPROCESSOR_ROOT.parent
        / "v7-renderer" / "fixtures" / "apex" / ".fal_active"
    )
    assert not marker.exists(), (
        "parsing --fal must not create .fal_active; only a real build does"
    )
