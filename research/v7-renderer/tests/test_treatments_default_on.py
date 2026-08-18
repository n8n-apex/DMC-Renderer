"""Treatments must be ON BY DEFAULT — the system's core layout engine.

The treatment system (editorial spreads, side rails, stat walls, dark
dividers) is a PRIMARY component: every report the system ingests must render
through it. OFF was the legacy rollback; the default is now ON.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

import assembler  # noqa: E402
import render as render_mod  # noqa: E402


def test_render_package_treatments_default_on() -> None:
    """render_package defaults to treatments=True (no flag needed)."""
    import inspect

    sig = inspect.signature(assembler.render_package)
    assert sig.parameters["treatments"].default is True, (
        "render_package must default treatments ON"
    )


def test_cli_flag_defaults_treatments_on() -> None:
    """The CLI has no --treatments required; the default is ON, with an
    explicit --no-treatments escape hatch."""
    src = (ROOT / "render.py").read_text(encoding="utf-8")
    assert "--no-treatments" in src, "must expose --no-treatments"
    assert '"--treatments", action="store_true"' not in src.replace(
        '"--no-treatments", action="store_true"', ""
    ), "the old opt-in flag must be replaced by opt-out"


def test_stylist_runs_in_default_path() -> None:
    """The default render path (no flags) invokes the stylist."""
    src = (ROOT / "assembler.py").read_text(encoding="utf-8")
    assert "assign(pkg.pages, ctx)" in src
    # the call is no longer gated on an OFF default
    assert "if treatments:" in src
