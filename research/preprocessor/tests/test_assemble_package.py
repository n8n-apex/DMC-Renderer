"""Tests for Stage 8 — assemble_package (resolved_package.json + dirs)."""

from __future__ import annotations

import asyncio
import json
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Optional

import pytest

from models import CopyWarning, CoverValidation, FontConfig, ScoreDetail
from models_package import ResolvedPackageManifest
from stages.assemble_package import (
    PACKAGE_SCHEMA_VERSION,
    ResolvedPackage,
    assemble_package,
)
from stages.generate_assets import AssetPlan, AssetResult
from stages.plan_layout import LayoutPlan, PlannedPage
from stages.resolve_axes import ResolvedAxes
from stages.structure_content import StructuredContent


def _axes() -> ResolvedAxes:
    """A fully-specified 7-field ResolvedAxes for assembly tests."""
    return ResolvedAxes(
        headline_type="serif", palette="mono_tonal",
        accent_mechanic="tonal_same_hue", texture="smooth",
        qr_enabled=False, density="balanced", ground_mode="light",
    )


def _v2(out_dir: Path, *, structured=None, page_slots=None) -> dict:
    """The Phase-4a v2.0 kwargs every assemble_package call now needs.
    Defaults are hermetic: empty structured / no drive slots / client_dir
    under the package (never touched when page_slots is empty)."""
    return {
        "axes": _axes(),
        "axes_provenance": {},
        "structured": structured if structured is not None else StructuredContent(pages=[]),
        "page_slots": page_slots if page_slots is not None else {},
        "client_dir": out_dir.parent / "client_assets_none",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Fixture builders
# ─────────────────────────────────────────────────────────────────────────────


def _font_config(
    heading_path: Optional[str] = None,
    body_path: Optional[str] = None,
) -> FontConfig:
    return FontConfig(
        font_heading_name="Montserrat",
        font_body_name="Source Sans 3",
        font_heading_path=heading_path,
        font_body_path=body_path,
        source="chassis_default",
    )


def _layout_plan(pages_spec: list[tuple[int, str, bool]]) -> LayoutPlan:
    """Build a LayoutPlan from `(slot, st_type, has_cta)` tuples."""
    pages = [
        PlannedPage(
            slot=slot, st_type=st_type,
            css_template={"ST-01": "cover", "ST-02": "outlook",
                          "ST-03": "cta_hard"}.get(st_type, "generic"),
            components=[], has_cta=has_cta, data={"_marker": slot},
        )
        for slot, st_type, has_cta in pages_spec
    ]
    return LayoutPlan(
        pages=pages,
        page_count=len(pages),
        page_count_target=len(pages),
        warnings=[],
        cta_positions=[s for s, _, has in pages_spec if has],
        breathing_positions=[],
    )


def _asset_plan(out: Path, assets: list[AssetResult]) -> AssetPlan:
    return AssetPlan(
        assets=assets,
        output_dir=out,
        total_required=len(assets),
        total_downloaded=sum(1 for a in assets if a.status == "downloaded"),
        total_stubbed=sum(1 for a in assets if a.status == "stub_not_generated"),
        total_client_upload_needed=sum(
            1 for a in assets if a.status == "client_upload_needed"
        ),
        total_failed=sum(1 for a in assets if a.status == "failed"),
        total_generated=sum(1 for a in assets if a.status == "generated"),
    )


def _cover_validation() -> CoverValidation:
    return CoverValidation(
        headline_type="Typ B — Diagnose",
        headline_size_class="long",
        awareness_level=2,
        h_score=14,
        h_scores_detail=[
            ScoreDetail(criterion="H1", score=2, reason="audience present"),
        ],
        s_score=9,
        s_scores_detail=[
            ScoreDetail(criterion="S1", score=2, reason="one job"),
        ],
        b_score=8,
        b_scores_detail=[
            ScoreDetail(criterion="B1", score=1, reason="some curiosity"),
        ],
        disqualifications=[],
        warnings=[],
        overall="pass",
    )


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture
def out_dir() -> Path:
    with tempfile.TemporaryDirectory() as td:
        yield Path(td) / "pkg"


# ─────────────────────────────────────────────────────────────────────────────
# The 12 spec test cases
# ─────────────────────────────────────────────────────────────────────────────


def test_1_full_assembly_creates_valid_json(out_dir: Path) -> None:
    """Full assembly with mock data → directory + valid resolved_package.json."""
    rp = _run(assemble_package(
        brand_tokens={"brand_primary": "#1A2540", "brand_accent": "#E97E47"},
        font_config=_font_config(),
        copy_warnings=[],
        cover_validation=None,
        asset_plan=_asset_plan(out_dir, []),
        components={},
        layout_plan=_layout_plan([(1, "ST-01", False), (2, "ST-03", True)]),
        report_json={"meta": {"report_id": "test"}, "pages": [
            {"slot": 1, "type": "ST-01", "data": {}},
            {"slot": 2, "type": "ST-03", "data": {}},
        ]},
        output_dir=out_dir,
        **_v2(out_dir),
    ))
    assert rp.package_path.exists()
    data = json.loads(rp.package_path.read_text())
    assert data["version"] == PACKAGE_SCHEMA_VERSION
    # Directory tree
    assert (out_dir / "assets").is_dir()
    assert (out_dir / "components").is_dir()
    assert (out_dir / "fonts").is_dir()


def test_2_brand_tokens_in_manifest(out_dir: Path) -> None:
    """The 10-field brand_tokens dict from Stage 1 appears verbatim
    under `brand` in the manifest.
    """
    tokens = {
        "brand_primary": "#1A2540",
        "brand_accent": "#E97E47",
        "brand_neutral_dark": "#0F0F1F",
        "brand_neutral_mid": "#7A7A8C",
        "brand_neutral_light": "#F5EFE3",
        "font_heading": "Montserrat",
        "font_body": "Source Sans 3",
        "qr_target_url": "https://example.com",
        "company_name_short": "Example GmbH",
        "company_url_display": "example.com",
    }
    rp = _run(assemble_package(
        brand_tokens=tokens,
        font_config=_font_config(),
        copy_warnings=[],
        cover_validation=None,
        asset_plan=_asset_plan(out_dir, []),
        components={},
        layout_plan=_layout_plan([(1, "ST-01", False)]),
        report_json={"meta": {"report_id": "x"}, "pages": [
            {"slot": 1, "type": "ST-01", "data": {}},
        ]},
        output_dir=out_dir,
        **_v2(out_dir),
    ))
    data = json.loads(rp.package_path.read_text())
    assert data["brand"] == tokens


def test_3_pages_array_length_matches_input(out_dir: Path) -> None:
    """If LayoutPlan has 20 pages, manifest has 20 pages."""
    pages_spec = [(i, "ST-01" if i == 1 else "ST-03" if i == 20 else "ST-02",
                   i in {2, 9, 18, 20}) for i in range(1, 21)]
    rp = _run(assemble_package(
        brand_tokens={"brand_primary": "#1A2540"},
        font_config=_font_config(),
        copy_warnings=[],
        cover_validation=None,
        asset_plan=_asset_plan(out_dir, []),
        components={},
        layout_plan=_layout_plan(pages_spec),
        report_json={"meta": {"report_id": "x"}, "pages": [
            {"slot": s, "type": st, "data": {}} for s, st, _ in pages_spec
        ]},
        output_dir=out_dir,
        **_v2(out_dir),
    ))
    data = json.loads(rp.package_path.read_text())
    assert len(data["pages"]) == 20
    assert rp.page_count == 20


def test_4_every_page_has_css_template(out_dir: Path) -> None:
    """No page in the manifest has css_template == None."""
    rp = _run(assemble_package(
        brand_tokens={"brand_primary": "#1A2540"},
        font_config=_font_config(),
        copy_warnings=[],
        cover_validation=None,
        asset_plan=_asset_plan(out_dir, []),
        components={},
        layout_plan=_layout_plan([(1, "ST-01", False), (2, "ST-99", False)]),
        report_json={"meta": {}, "pages": []},
        output_dir=out_dir,
        **_v2(out_dir),
    ))
    data = json.loads(rp.package_path.read_text())
    for page in data["pages"]:
        assert page["css_template"], f"slot {page['slot']} has empty css_template"


def test_5_svg_components_written_as_files(out_dir: Path) -> None:
    """Components written to `components/` with the expected names and
    content matching the inputs.
    """
    components = {
        3: ["<svg>SLOT3_A</svg>", "<svg>SLOT3_B</svg>"],
        7: ["<svg>SLOT7</svg>"],
    }
    rp = _run(assemble_package(
        brand_tokens={"brand_primary": "#1A2540"},
        font_config=_font_config(),
        copy_warnings=[],
        cover_validation=None,
        asset_plan=_asset_plan(out_dir, []),
        components=components,
        layout_plan=_layout_plan([
            (3, "ST-02", False), (7, "ST-02", False),
        ]),
        report_json={"meta": {}, "pages": []},
        output_dir=out_dir,
        **_v2(out_dir),
    ))
    # Files exist
    assert (out_dir / "components" / "3_component_0.svg").read_text() == \
        "<svg>SLOT3_A</svg>"
    assert (out_dir / "components" / "3_component_1.svg").read_text() == \
        "<svg>SLOT3_B</svg>"
    assert (out_dir / "components" / "7_component_0.svg").read_text() == \
        "<svg>SLOT7</svg>"
    # Manifest references them
    data = json.loads(rp.package_path.read_text())
    slot3 = next(p for p in data["pages"] if p["slot"] == 3)
    assert slot3["components"] == [
        "components/3_component_0.svg",
        "components/3_component_1.svg",
    ]


def test_6_font_files_copied_when_paths_provided(out_dir: Path) -> None:
    """If font_config has paths to existing files, they're copied into
    `fonts/` and the manifest references them by basename.
    """
    # Create fake font files in a temp source dir
    src_dir = out_dir.parent / "src_fonts"
    src_dir.mkdir()
    heading_src = src_dir / "FakeMontserrat.ttf"
    heading_src.write_bytes(b"FAKE_HEAD")
    body_src = src_dir / "FakeBody.ttf"
    body_src.write_bytes(b"FAKE_BODY")

    rp = _run(assemble_package(
        brand_tokens={"brand_primary": "#1A2540"},
        font_config=_font_config(str(heading_src), str(body_src)),
        copy_warnings=[],
        cover_validation=None,
        asset_plan=_asset_plan(out_dir, []),
        components={},
        layout_plan=_layout_plan([(1, "ST-01", False)]),
        report_json={"meta": {}, "pages": []},
        output_dir=out_dir,
        **_v2(out_dir),
    ))
    assert (out_dir / "fonts" / "FakeMontserrat.ttf").read_bytes() == b"FAKE_HEAD"
    assert (out_dir / "fonts" / "FakeBody.ttf").read_bytes() == b"FAKE_BODY"
    data = json.loads(rp.package_path.read_text())
    assert data["fonts"]["heading"]["path"] == "fonts/FakeMontserrat.ttf"
    assert data["fonts"]["body"]["path"] == "fonts/FakeBody.ttf"


def test_7_cover_page_has_cover_validation_block(out_dir: Path) -> None:
    """The ST-01 page gets a cover_validation block with H/S/B scores."""
    rp = _run(assemble_package(
        brand_tokens={"brand_primary": "#1A2540"},
        font_config=_font_config(),
        copy_warnings=[],
        cover_validation=_cover_validation(),
        asset_plan=_asset_plan(out_dir, []),
        components={},
        layout_plan=_layout_plan([(1, "ST-01", False), (2, "ST-02", True)]),
        report_json={"meta": {}, "pages": []},
        output_dir=out_dir,
        **_v2(out_dir),
    ))
    data = json.loads(rp.package_path.read_text())
    cover = next(p for p in data["pages"] if p["slot"] == 1)
    assert cover["cover_validation"] is not None
    cv = cover["cover_validation"]
    assert cv["h_score"] == 14
    assert cv["s_score"] == 9
    assert cv["b_score"] == 8
    assert cv["overall"] == "pass"


def test_8_non_cover_page_has_cover_validation_null(out_dir: Path) -> None:
    """Non-ST-01 pages have cover_validation == null."""
    rp = _run(assemble_package(
        brand_tokens={"brand_primary": "#1A2540"},
        font_config=_font_config(),
        copy_warnings=[],
        cover_validation=_cover_validation(),
        asset_plan=_asset_plan(out_dir, []),
        components={},
        layout_plan=_layout_plan([(1, "ST-01", False), (2, "ST-02", True)]),
        report_json={"meta": {}, "pages": []},
        output_dir=out_dir,
        **_v2(out_dir),
    ))
    data = json.loads(rp.package_path.read_text())
    non_cover = next(p for p in data["pages"] if p["slot"] == 2)
    assert non_cover["cover_validation"] is None


def test_9_stubbed_assets_appear_with_path_null(out_dir: Path) -> None:
    """Stubbed assets appear in pages[].assets[] with path=None and the
    correct status.
    """
    assets = [
        AssetResult(
            slot_id="cover_hero", status="stub_not_generated",
            path=None, message="stubbed", page_slot=1, image_type="background",
            prompt="STYLE-DNA Subject: cover. Aspect ratio 3:4.",
            negative_prompt="warm tones",
        ),
    ]
    rp = _run(assemble_package(
        brand_tokens={"brand_primary": "#1A2540"},
        font_config=_font_config(),
        copy_warnings=[],
        cover_validation=None,
        asset_plan=_asset_plan(out_dir, assets),
        components={},
        layout_plan=_layout_plan([(1, "ST-01", False)]),
        report_json={"meta": {}, "pages": []},
        output_dir=out_dir,
        **_v2(out_dir),
    ))
    data = json.loads(rp.package_path.read_text())
    cover = next(p for p in data["pages"] if p["slot"] == 1)
    assert len(cover["assets"]) == 1
    asset = cover["assets"][0]
    assert asset["slot_id"] == "cover_hero"
    assert asset["status"] == "stub_not_generated"
    assert asset["path"] is None
    # Brief-driven prompt fields flow into the manifest entry.
    assert "prompt" in asset and "negative_prompt" in asset
    assert asset["prompt"] == "STYLE-DNA Subject: cover. Aspect ratio 3:4."
    assert asset["negative_prompt"] == "warm tones"


def test_10_validation_aggregates_copy_and_layout_warnings(out_dir: Path) -> None:
    """`validation.total_warnings` = len(copy_warnings) + len(layout_warnings)."""
    cw = [
        CopyWarning(
            page_slot=4, page_type="ST-09", field_name="body",
            rule="buzzword_denylist", detail="Found 'innovativ'",
        ),
        CopyWarning(
            page_slot=8, page_type="ST-14", field_name="intro",
            rule="konjunktiv", detail="könnte found",
        ),
    ]
    plan = _layout_plan([(1, "ST-01", False)])
    plan.warnings.extend([
        "no CTA detected between S3 and S9",
        "page count mismatch",
    ])
    rp = _run(assemble_package(
        brand_tokens={"brand_primary": "#1A2540"},
        font_config=_font_config(),
        copy_warnings=cw,
        cover_validation=None,
        asset_plan=_asset_plan(out_dir, []),
        components={},
        layout_plan=plan,
        report_json={"meta": {}, "pages": []},
        output_dir=out_dir,
        **_v2(out_dir),
    ))
    data = json.loads(rp.package_path.read_text())
    val = data["validation"]
    assert len(val["copy_warnings"]) == 2
    assert len(val["layout_warnings"]) == 2
    assert val["total_warnings"] == 4
    assert rp.total_warnings == 4


def test_11_no_absolute_paths_in_json(out_dir: Path) -> None:
    """No absolute /Users/ paths leak into the JSON — all paths inside
    resolved_package.json must be relative.
    """
    # Create a fake font file so the font copy path triggers
    src_dir = out_dir.parent / "src_fonts"
    src_dir.mkdir()
    f = src_dir / "FontX.ttf"
    f.write_bytes(b"x")

    rp = _run(assemble_package(
        brand_tokens={"brand_primary": "#1A2540"},
        font_config=_font_config(str(f), str(f)),
        copy_warnings=[],
        cover_validation=None,
        asset_plan=_asset_plan(out_dir, [
            AssetResult(slot_id="x", status="stub_not_generated", path=None,
                        page_slot=1, image_type="background"),
        ]),
        components={1: ["<svg/>"]},
        layout_plan=_layout_plan([(1, "ST-01", False)]),
        report_json={"meta": {}, "pages": []},
        output_dir=out_dir,
        **_v2(out_dir),
    ))
    raw = rp.package_path.read_text()
    assert "/Users/" not in raw, (
        "absolute /Users/ path leaked into JSON — paths must be "
        "relative to output_dir"
    )
    # Also no absolute /tmp/ paths
    assert "/var/folders/" not in raw
    assert "/tmp/" not in raw


def test_12_package_can_be_read_back(out_dir: Path) -> None:
    """The JSON is well-formed and has all the documented top-level keys."""
    rp = _run(assemble_package(
        brand_tokens={"brand_primary": "#1A2540"},
        font_config=_font_config(),
        copy_warnings=[],
        cover_validation=None,
        asset_plan=_asset_plan(out_dir, []),
        components={},
        layout_plan=_layout_plan([(1, "ST-01", False)]),
        report_json={"meta": {"report_id": "RID"}, "pages": []},
        output_dir=out_dir,
        **_v2(out_dir),
    ))
    raw = rp.package_path.read_text()
    data = json.loads(raw)  # raises on malformed JSON
    expected_keys = {
        "version", "generated_at", "record_id", "brand", "fonts",
        "pages", "validation", "asset_summary", "asset_warnings",
    }
    assert set(data.keys()) >= expected_keys, (
        f"missing top-level keys: {expected_keys - set(data.keys())}"
    )
    assert data["record_id"] == "RID"


def test_generated_at_is_deterministic_per_record_id() -> None:
    """G10: the package manifest timestamp must be stable per record id, so
    identical inputs produce identical bytes (it no longer claims wall-clock
    time; it is a deterministic build identity derived from the record id)."""
    from stages.assemble_package import _stable_generated_at

    first = _stable_generated_at("RID-1")
    second = _stable_generated_at("RID-1")
    assert first == second
    other = _stable_generated_at("RID-2")
    assert first != other
    assert first.endswith("Z")
    assert first.startswith("20")


# ─────────────────────────────────────────────────────────────────────────────
# Additional coverage
# ─────────────────────────────────────────────────────────────────────────────


def test_asset_summary_in_manifest_matches_plan(out_dir: Path) -> None:
    """`asset_summary` in the JSON matches the AssetPlan counts, including
    the additive `total_generated` field.
    """
    assets = [
        AssetResult(slot_id="a1", status="downloaded",
                    path=out_dir / "assets" / "f.png",
                    page_slot=1, image_type="background"),
        AssetResult(slot_id="a2", status="stub_not_generated",
                    page_slot=1, image_type="background"),
        AssetResult(slot_id="a3", status="client_upload_needed",
                    page_slot=2, image_type="logo"),
        AssetResult(slot_id="a4", status="generated",
                    path=out_dir / "assets" / "4_a4.png",
                    page_slot=4, image_type="scene",
                    prompt="PB", negative_prompt="NEG"),
    ]
    rp = _run(assemble_package(
        brand_tokens={"brand_primary": "#1A2540"},
        font_config=_font_config(),
        copy_warnings=[],
        cover_validation=None,
        asset_plan=_asset_plan(out_dir, assets),
        components={},
        layout_plan=_layout_plan([(1, "ST-01", False), (2, "ST-05", False)]),
        report_json={"meta": {}, "pages": []},
        output_dir=out_dir,
        **_v2(out_dir),
    ))
    data = json.loads(rp.package_path.read_text())
    summary = data["asset_summary"]
    assert summary["total_required"] == 4
    assert summary["total_downloaded"] == 1
    assert summary["total_stubbed"] == 1
    assert summary["total_client_upload_needed"] == 1
    assert summary["total_generated"] == 1
    # The additive field is present (default 0) for every assembled package.
    assert "total_generated" in summary


def test_report_level_assets_appear_in_report_assets(out_dir: Path) -> None:
    """Report-level assets (page_slot=None — texture/gradient) must NOT be
    dropped: they land in the top-level `report_assets` array (with their
    brief-driven prompts), never under any page.
    """
    assets = [
        AssetResult(slot_id="cover_hero", status="stub_not_generated",
                    page_slot=1, image_type="background",
                    prompt="STYLE Subject: cover.", negative_prompt="warm"),
        AssetResult(slot_id="background_texture", status="stub_not_generated",
                    page_slot=None, image_type="texture",
                    prompt="STYLE Subject: a seamless texture.",
                    negative_prompt="warm tones"),
        AssetResult(slot_id="atmospheric_gradient", status="stub_not_generated",
                    page_slot=None, image_type="gradient",
                    prompt="STYLE Subject: a gradient wash.",
                    negative_prompt="warm tones"),
    ]
    rp = _run(assemble_package(
        brand_tokens={"brand_primary": "#1A2540"},
        font_config=_font_config(),
        copy_warnings=[],
        cover_validation=None,
        asset_plan=_asset_plan(out_dir, assets),
        components={},
        layout_plan=_layout_plan([(1, "ST-01", False)]),
        report_json={"meta": {}, "pages": []},
        output_dir=out_dir,
        **_v2(out_dir),
    ))
    data = json.loads(rp.package_path.read_text())

    # The two report-level assets are present at the top level, with prompts.
    report = data["report_assets"]
    report_ids = {a["slot_id"] for a in report}
    assert report_ids == {"background_texture", "atmospheric_gradient"}
    for a in report:
        assert a["prompt"].startswith("STYLE Subject:")
        assert a["negative_prompt"] == "warm tones"

    # And they did NOT leak into any page's assets; the page keeps cover_hero.
    cover = next(p for p in data["pages"] if p["slot"] == 1)
    assert {a["slot_id"] for a in cover["assets"]} == {"cover_hero"}


def test_manifest_page_carries_page_numbers(tmp_path) -> None:
    """Each manifest page entry includes the page_numbers field from PlannedPage."""
    import asyncio
    from stages.plan_layout import LayoutPlan, PlannedPage
    from stages.generate_assets import AssetPlan
    from models import FontConfig

    planned = [
        PlannedPage(slot=1, st_type="ST-01", css_template="cover",
                    components=[], has_cta=False, data={}, page_numbers="1"),
        PlannedPage(slot=2, st_type="ST-02", css_template="outlook",
                    components=[], has_cta=False, data={}, page_numbers="2-3"),
    ]
    layout_plan = LayoutPlan(pages=planned, page_count=2, page_count_target=20)
    asset_plan = AssetPlan(assets=[])
    font_config = FontConfig(
        font_heading_name="Montserrat", font_body_name="Source Sans 3",
        font_heading_path=None, font_body_path=None, source="chassis_default",
    )
    resolved = asyncio.run(assemble_package(
        brand_tokens={
            "brand_primary": "#111", "brand_accent": "#222",
            "brand_neutral_dark": "#333", "brand_neutral_mid": "#444",
            "brand_neutral_light": "#555", "font_heading": "Montserrat",
            "font_body": "Source Sans 3", "qr_target_url": "https://x.de",
            "company_name_short": "X", "company_url_display": "x.de",
        },
        font_config=font_config, copy_warnings=[], cover_validation=None,
        asset_plan=asset_plan, components={}, layout_plan=layout_plan,
        report_json={"meta": {"report_id": "T"}, "pages": []},
        output_dir=tmp_path,
        **_v2(tmp_path),
    ))
    import json
    manifest = json.loads((resolved.output_dir / "resolved_package.json").read_text())
    pn = {p["slot"]: p.get("page_numbers") for p in manifest["pages"]}
    assert pn == {1: "1", 2: "2-3"}


def test_manifest_carries_derived_brand_axes(tmp_path) -> None:
    """The transitional 4-field `brand_axes` is DERIVED from the canonical
    7-field `axes` (no longer passed in): the four keys mirror `axes`."""
    import asyncio, json
    from stages.plan_layout import LayoutPlan, PlannedPage
    from stages.generate_assets import AssetPlan
    from models import FontConfig
    planned = [PlannedPage(slot=1, st_type="ST-01", css_template="cover",
                           components=[], has_cta=False, data={}, page_numbers="1")]
    axes = ResolvedAxes(
        headline_type="serif", palette="dual_contrasting",
        accent_mechanic="contrasting_hue", texture="marble_paper",
        qr_enabled=True, density="packed", ground_mode="dark",
    )
    resolved = asyncio.run(assemble_package(
        brand_tokens={"brand_primary": "#111", "brand_accent": "#222",
            "brand_neutral_dark": "#333", "brand_neutral_mid": "#444",
            "brand_neutral_light": "#555", "font_heading": "M", "font_body": "S",
            "qr_target_url": "https://x.de", "company_name_short": "X",
            "company_url_display": "x.de"},
        font_config=FontConfig(font_heading_name="M", font_body_name="S",
            font_heading_path=None, font_body_path=None, source="chassis_default"),
        copy_warnings=[], cover_validation=None, asset_plan=AssetPlan(assets=[]),
        components={}, layout_plan=LayoutPlan(pages=planned, page_count=1, page_count_target=20),
        report_json={"meta": {"report_id": "T"}, "pages": []}, output_dir=tmp_path,
        axes=axes, axes_provenance={"headline_type": "brand_profile"},
        structured=StructuredContent(pages=[]), page_slots={},
        client_dir=tmp_path.parent / "none",
    ))
    manifest = json.loads((resolved.output_dir / "resolved_package.json").read_text())
    assert manifest["brand_axes"] == {
        "headline_type": "serif", "ground_mode": "dark",
        "texture": "marble_paper", "accent_mechanic": "contrasting_hue",
    }
    # The 4-field block is exactly the renderer-facing subset of `axes`.
    assert set(manifest["brand_axes"]) == {
        "headline_type", "ground_mode", "texture", "accent_mechanic"
    }


def test_manifest_v2_shape_and_validates(tmp_path) -> None:
    """v2.0 top-level: axes(7) / brand_axes(4) / provenance / slot_summary;
    a page carries data / charts / social_proof / slots; and the whole
    manifest validates against ResolvedPackageManifest."""
    import asyncio, json
    from stages.plan_layout import LayoutPlan, PlannedPage
    from stages.generate_assets import AssetPlan
    from models import FontConfig
    from stages.structure_content import structure_content

    pages_in = [
        {"slot": 1, "type": "ST-01", "data": {"title": "Cover"}},
        {"slot": 2, "type": "ST-09", "data": {
            "title": "Status quo",
            "social_proof": {"quote": "Sehr gut", "attribution": "Ein Kunde"},
        }},
    ]
    planned = [
        PlannedPage(slot=1, st_type="ST-01", css_template="cover",
                    components=[], has_cta=False, data={}, page_numbers="1"),
        PlannedPage(slot=2, st_type="ST-09", css_template="generic",
                    components=[], has_cta=False, data={}, page_numbers="2"),
    ]
    structured = structure_content(pages_in)
    axes = _axes()
    resolved = asyncio.run(assemble_package(
        brand_tokens={"brand_primary": "#111", "brand_accent": "#222",
            "brand_neutral_dark": "#333", "brand_neutral_mid": "#444",
            "brand_neutral_light": "#555", "font_heading": "M", "font_body": "S",
            "qr_target_url": "https://x.de", "company_name_short": "X",
            "company_url_display": "x.de"},
        font_config=FontConfig(font_heading_name="M", font_body_name="S",
            font_heading_path=None, font_body_path=None, source="chassis_default"),
        copy_warnings=[], cover_validation=None, asset_plan=AssetPlan(assets=[]),
        components={}, layout_plan=LayoutPlan(pages=planned, page_count=2, page_count_target=20),
        report_json={"meta": {"report_id": "T"}, "pages": pages_in},
        output_dir=tmp_path,
        axes=axes, axes_provenance={"headline_type": "default", "palette": "derived"},
        structured=structured, page_slots={},
        client_dir=tmp_path.parent / "none",
    ))
    manifest = json.loads((resolved.output_dir / "resolved_package.json").read_text())

    assert manifest["version"] == "2.0"
    # Top-level v2 blocks.
    assert set(manifest["axes"]) == {
        "headline_type", "palette", "accent_mechanic", "texture",
        "qr_enabled", "density", "ground_mode",
    }
    assert set(manifest["brand_axes"]) == {
        "headline_type", "ground_mode", "texture", "accent_mechanic"
    }
    assert manifest["provenance"] == {"headline_type": "default", "palette": "derived"}
    assert set(manifest["slot_summary"]) >= {
        "resolved", "missing_required", "absent", "total", "missing"
    }
    # A page carries the typed v2 per-page blocks.
    for p in manifest["pages"]:
        assert "data" in p and "charts" in p and "social_proof" in p and "slots" in p
    page2 = next(p for p in manifest["pages"] if p["slot"] == 2)
    assert page2["social_proof"] is not None  # structure_content parsed it

    # The written manifest round-trips through the contract model.
    ResolvedPackageManifest.model_validate(manifest)


def test_chart_svg_component_written_into_package(out_dir: Path) -> None:
    """A chart SVG rendered for a page (Task 5) flows into the package: the
    component file is written and the page's `components` references it, while
    the chart spec stays under `charts` for provenance.
    """
    from stages.generate_components import generate_components_for_report
    from stages.structure_content import structure_content

    pages_in = [
        {"slot": 5, "type": "ST-05", "data": {
            "ohne": ["Excel-Chaos"], "mit": ["Live-Dashboard"],
        }},
    ]
    structured = structure_content(pages_in)
    components = generate_components_for_report(
        pages_in, brand_primary="#1A2540", brand_accent="#E97E47",
        brand_neutral_light="#F5EFE3", structured=structured,
    )
    assert 5 in components and components[5]

    rp = _run(assemble_package(
        brand_tokens={"brand_primary": "#1A2540", "brand_accent": "#E97E47"},
        font_config=_font_config(),
        copy_warnings=[],
        cover_validation=None,
        asset_plan=_asset_plan(out_dir, []),
        components=components,
        layout_plan=_layout_plan([(5, "ST-05", False)]),
        report_json={"meta": {"report_id": "t"}, "pages": pages_in},
        output_dir=out_dir,
        **_v2(out_dir, structured=structured),
    ))
    data = json.loads(rp.package_path.read_text())
    page5 = next(p for p in data["pages"] if p["slot"] == 5)
    # Component file(s) referenced and written, with a chart SVG inside.
    assert page5["components"], "page should reference its components"
    found_chart = False
    for rel in page5["components"]:
        svg = (out_dir / rel).read_text()
        # The ComparisonColumns renderer emits the data bullets + brand accent.
        if "<svg" in svg and "Live-Dashboard" in svg and "#E97E47" in svg:
            found_chart = True
    assert found_chart, "a chart SVG component should be written into the package"
    # The chart spec remains for provenance.
    assert page5["charts"], "the chart spec must remain under charts"
    assert page5["charts"][0]["kind"] == "comparison_columns"


def test_resolved_drive_slot_is_copied_into_package(tmp_path) -> None:
    """A `resolved` drive slot → its file is COPIED into the package under
    `assets/` and the emitted `slots[]` entry's `path` is package-relative.
    A `missing_required` drive slot → `path=None` + the status preserved,
    and it shows up in `slot_summary.missing` named."""
    import asyncio, json
    from stages.plan_layout import LayoutPlan, PlannedPage
    from stages.generate_assets import AssetPlan
    from models import FontConfig
    from stages.resolve_slots import ResolvedSlot

    # A real source file the assembler will copy in.
    client_dir = tmp_path / "client"
    client_dir.mkdir()
    (client_dir / "founder.png").write_bytes(b"\x89PNG\r\n\x1a\nFOUNDER")

    page_slots = {
        1: [
            ResolvedSlot(
                slot_kind="founder_hero", source="drive", status="resolved",
                path="founder.png", drive_key="founder", slot_id="founder",
                image_type="portrait", aspect_ratio="3x4",
            ),
        ],
        2: [
            ResolvedSlot(
                slot_kind="client_portrait", source="drive",
                status="missing_required", drive_key="case-study-2",
                expected="case-study-2", index=2,
                slot_id="case_study_portrait", image_type="portrait",
                aspect_ratio="1x1",
            ),
            # A generate-source slot must NOT appear in slots[] (it belongs
            # in assets[]); only drive slots are emitted here.
            ResolvedSlot(
                slot_kind="scene", source="generate", status="absent",
                slot_id="scene", image_type="scene", aspect_ratio="3x4",
            ),
        ],
    }
    planned = [
        PlannedPage(slot=1, st_type="ST-01", css_template="cover",
                    components=[], has_cta=False, data={}, page_numbers="1"),
        PlannedPage(slot=2, st_type="ST-07A", css_template="generic",
                    components=[], has_cta=False, data={}, page_numbers="2"),
    ]
    resolved = asyncio.run(assemble_package(
        brand_tokens={"brand_primary": "#111"},
        font_config=FontConfig(font_heading_name="M", font_body_name="S",
            font_heading_path=None, font_body_path=None, source="chassis_default"),
        copy_warnings=[], cover_validation=None, asset_plan=AssetPlan(assets=[]),
        components={}, layout_plan=LayoutPlan(pages=planned, page_count=2, page_count_target=20),
        report_json={"meta": {"report_id": "T"}, "pages": []},
        output_dir=tmp_path / "pkg",
        axes=_axes(), axes_provenance={}, structured=StructuredContent(pages=[]),
        page_slots=page_slots, client_dir=client_dir,
    ))
    manifest = json.loads((resolved.output_dir / "resolved_package.json").read_text())

    page1 = next(p for p in manifest["pages"] if p["slot"] == 1)
    assert len(page1["slots"]) == 1
    founder = page1["slots"][0]
    assert founder["slot_id"] == "founder"
    assert founder["status"] == "resolved"
    assert founder["path"] == "assets/1_founder.png"
    # The file was actually copied into the package.
    copied = resolved.output_dir / "assets" / "1_founder.png"
    assert copied.exists()
    assert copied.read_bytes().startswith(b"\x89PNG")

    page2 = next(p for p in manifest["pages"] if p["slot"] == 2)
    # generate-source slot excluded; only the drive portrait remains.
    assert len(page2["slots"]) == 1
    portrait = page2["slots"][0]
    assert portrait["slot_id"] == "case_study_portrait"
    assert portrait["status"] == "missing_required"
    assert portrait["path"] is None
    assert portrait["expected"] == "case-study-2"

    summary = manifest["slot_summary"]
    assert summary["resolved"] == 1
    assert summary["missing_required"] == 1
    assert summary["total"] == 2
    assert summary["missing"] == [
        {"page_slot": 2, "slot_id": "case_study_portrait", "expected": "case-study-2"}
    ]


# ─────────────────────────────────────────────────────────────────────────────
# layout_variant plumbing (Stage 7 PlannedPage.layout_variant → package page)
# ─────────────────────────────────────────────────────────────────────────────


def _layout_plan_with_variants(
    pages_spec: list[tuple[int, str, Optional[str]]],
) -> LayoutPlan:
    """Build a LayoutPlan from `(slot, st_type, layout_variant)` tuples."""
    pages = [
        PlannedPage(
            slot=slot, st_type=st_type,
            css_template={"ST-01": "cover", "ST-03": "cta_hard",
                          "ST-07A": "case_study"}.get(st_type, "generic"),
            components=[], has_cta=False, data={"_marker": slot},
            layout_variant=variant,
        )
        for slot, st_type, variant in pages_spec
    ]
    return LayoutPlan(
        pages=pages, page_count=len(pages), page_count_target=len(pages),
        warnings=[], cta_positions=[], breathing_positions=[],
    )


def _report_json(pages_spec) -> dict:
    return {"meta": {"report_id": "test"}, "pages": [
        {"slot": slot, "type": st_type, "data": {}}
        for slot, st_type, _ in pages_spec
    ]}


def test_layout_variant_written_into_package_page(out_dir: Path) -> None:
    """A PlannedPage carrying layout_variant='fill' (the ST-07A default Stage 7
    resolves) surfaces as page['layout_variant'] in resolved_package.json."""
    spec = [(1, "ST-01", None), (2, "ST-07A", "fill"), (3, "ST-03", None)]
    rp = _run(assemble_package(
        brand_tokens={"brand_primary": "#1A2540", "brand_accent": "#E97E47"},
        font_config=_font_config(), copy_warnings=[], cover_validation=None,
        asset_plan=_asset_plan(out_dir, []), components={},
        layout_plan=_layout_plan_with_variants(spec),
        report_json=_report_json(spec), output_dir=out_dir, **_v2(out_dir),
    ))
    data = json.loads(rp.package_path.read_text())
    by_slot = {p["slot"]: p for p in data["pages"]}
    assert by_slot[2]["layout_variant"] == "fill"


def test_explicit_standard_variant_written_into_package_page(out_dir: Path) -> None:
    """An explicit per-page override ('standard') is written through verbatim."""
    spec = [(1, "ST-01", None), (2, "ST-07A", "standard"), (3, "ST-03", None)]
    rp = _run(assemble_package(
        brand_tokens={"brand_primary": "#1A2540", "brand_accent": "#E97E47"},
        font_config=_font_config(), copy_warnings=[], cover_validation=None,
        asset_plan=_asset_plan(out_dir, []), components={},
        layout_plan=_layout_plan_with_variants(spec),
        report_json=_report_json(spec), output_dir=out_dir, **_v2(out_dir),
    ))
    data = json.loads(rp.package_path.read_text())
    by_slot = {p["slot"]: p for p in data["pages"]}
    assert by_slot[2]["layout_variant"] == "standard"


def test_no_layout_variant_key_when_none(out_dir: Path) -> None:
    """A page whose PlannedPage.layout_variant is None (e.g. a non-ST-07A page
    with no explicit hint) does NOT get a layout_variant key — back-compat: the
    renderer keeps its own default for that ST type."""
    spec = [(1, "ST-01", None), (2, "ST-09", None), (3, "ST-03", None)]
    rp = _run(assemble_package(
        brand_tokens={"brand_primary": "#1A2540", "brand_accent": "#E97E47"},
        font_config=_font_config(), copy_warnings=[], cover_validation=None,
        asset_plan=_asset_plan(out_dir, []), components={},
        layout_plan=_layout_plan_with_variants(spec),
        report_json=_report_json(spec), output_dir=out_dir, **_v2(out_dir),
    ))
    data = json.loads(rp.package_path.read_text())
    by_slot = {p["slot"]: p for p in data["pages"]}
    assert "layout_variant" not in by_slot[2], by_slot[2]


def test_st07a_default_fill_end_to_end_via_plan_layout(out_dir: Path) -> None:
    """End-to-end through the REAL plan_layout: an ST-07A page with no hint
    lands as layout_variant='fill' in the package; a sibling ST-09 page gets no
    key at all."""
    from stages.plan_layout import plan_layout

    pages = [
        {"slot": 1, "type": "ST-01", "data": {}},
        {"slot": 2, "type": "ST-09", "data": {}},
        {"slot": 3, "type": "ST-07A", "data": {}},
        {"slot": 4, "type": "ST-03", "data": {}},
    ]
    plan = plan_layout(pages, components={}, page_count_target=20)
    rp = _run(assemble_package(
        brand_tokens={"brand_primary": "#1A2540", "brand_accent": "#E97E47"},
        font_config=_font_config(), copy_warnings=[], cover_validation=None,
        asset_plan=_asset_plan(out_dir, []), components={},
        layout_plan=plan,
        report_json={"meta": {"report_id": "test"}, "pages": pages},
        output_dir=out_dir, **_v2(out_dir),
    ))
    data = json.loads(rp.package_path.read_text())
    by_slot = {p["slot"]: p for p in data["pages"]}
    assert by_slot[3]["layout_variant"] == "fill"   # ST-07A default
    assert "layout_variant" not in by_slot[2]         # ST-09 untouched
