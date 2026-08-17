"""Phase 2 (ship-build-path): render.py must accept --package-dir so the renderer
can rasterize ANY built package (a fresh /render output, a regenerated fixture),
not only the frozen apex fixture. Defaults to the apex fixture for back-compat.
"""
from pathlib import Path

import render


def test_package_dir_defaults_to_apex_fixture():
    ns = render._build_parser().parse_args([])
    assert Path(ns.package_dir).resolve() == render.FIXTURES_APEX_DIR


def test_package_dir_can_be_overridden():
    ns = render._build_parser().parse_args(["--package-dir", "/tmp/somepkg"])
    assert ns.package_dir == "/tmp/somepkg"


def test_existing_flags_survive_the_refactor():
    ns = render._build_parser().parse_args(["--engine", "weasyprint", "--fast"])
    assert ns.engine == "weasyprint" and ns.fast is True


def test_output_dir_defaults_and_overrides():
    # Per-job output isolation: the orchestrator points each job at its own dir
    # so concurrent renders never collide on the shared output/ folder.
    ns = render._build_parser().parse_args([])
    assert Path(ns.output_dir).resolve() == render.OUTPUT_DIR
    ns2 = render._build_parser().parse_args(["--output-dir", "/tmp/job1"])
    assert ns2.output_dir == "/tmp/job1"
