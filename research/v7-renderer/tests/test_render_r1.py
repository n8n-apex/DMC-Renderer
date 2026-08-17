"""R1 renderer tests — loader / interface / registry / overflow / assembler / integration."""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHASSIS_ROOT = HERE.parent
sys.path.insert(0, str(CHASSIS_ROOT))

import pytest  # noqa: E402

from brand_tokens import parse_brand_tokens  # noqa: E402
from grammar_loader import load_grammar  # noqa: E402
from patterns.base import PageFragment, RenderContext  # noqa: E402


SAMPLE_BRAND = {
    "brand_primary": "#5a9ab3", "brand_accent": "#85d2ee",
    "brand_neutral_dark": "#0F0F1F", "brand_neutral_mid": "#7A7A8C",
    "brand_neutral_light": "#fdffff", "font_heading": "Montserrat",
    "font_body": "Source Sans 3", "qr_target_url": "https://example.de",
    "company_name_short": "Example", "company_url_display": "example.de",
}


def _ctx(package_dir: Path) -> RenderContext:
    return RenderContext(
        brand=parse_brand_tokens(SAMPLE_BRAND),
        grammar=load_grammar(),
        package_dir=package_dir,
    )


def test_pagefragment_is_frozen_dataclass() -> None:
    frag = PageFragment(html="<p>hi</p>", css=".x{}")
    assert frag.html == "<p>hi</p>" and frag.css == ".x{}"
    with pytest.raises(Exception):
        frag.html = "mutated"  # frozen


def test_rendercontext_resolves_existing_and_missing(tmp_path) -> None:
    (tmp_path / "assets").mkdir()
    img = tmp_path / "assets" / "a.png"
    img.write_bytes(b"\x89PNG\r\n")
    svg = tmp_path / "c.svg"
    svg.write_text("<svg/>", encoding="utf-8")

    ctx = _ctx(tmp_path)
    assert ctx.resolve_asset("assets/a.png") == img.resolve()
    assert ctx.resolve_asset("assets/missing.png") is None
    assert ctx.resolve_asset(None) is None
    assert ctx.resolve_component("c.svg") == "<svg/>"
    assert ctx.resolve_component("missing.svg") is None
    assert ctx.resolve_component(None) is None


def test_rendercontext_slot_uri_resolves_resolved_slot(tmp_path) -> None:
    """ctx.slot_uri(page, slot_id) — the v2.0 photo-slot primitive. A resolved
    slot whose file exists resolves to a file:// URI; absent / unresolved /
    missing-file / no-slots all degrade to None (the graceful contract every
    photo pattern relies on)."""
    (tmp_path / "assets").mkdir()
    founder = tmp_path / "assets" / "1_founder.png"
    founder.write_bytes(b"\x89PNG\r\n")
    ctx = _ctx(tmp_path)

    # 1) resolved slot whose file exists -> a file:// URI pointing at the asset
    page = {
        "slots": [
            {"slot_id": "founder", "status": "resolved", "path": "assets/1_founder.png"},
        ]
    }
    uri = ctx.slot_uri(page, "founder")
    assert uri == founder.resolve().as_uri()
    assert uri is not None and uri.startswith("file://") and uri.endswith("1_founder.png")

    # 2) a DIFFERENT slot_id on the same page -> None (no match)
    assert ctx.slot_uri(page, "team") is None

    # 3) slot present but NOT resolved (absent / missing_required) -> None
    page_absent = {"slots": [{"slot_id": "founder", "status": "absent", "path": None}]}
    assert ctx.slot_uri(page_absent, "founder") is None
    page_missing = {
        "slots": [{"slot_id": "founder", "status": "missing_required", "path": None}]
    }
    assert ctx.slot_uri(page_missing, "founder") is None

    # 4) resolved but the file does not exist on disk -> None (never a broken img)
    page_gone = {
        "slots": [{"slot_id": "founder", "status": "resolved", "path": "assets/nope.png"}]
    }
    assert ctx.slot_uri(page_gone, "founder") is None

    # 5) page carries no slots at all -> None
    assert ctx.slot_uri({}, "founder") is None
    assert ctx.slot_uri({"slots": []}, "founder") is None


def test_rendercontext_slot_uris_returns_all_resolved_in_order(tmp_path) -> None:
    """ctx.slot_uris(page, slot_id) — the MANY-slots primitive (proof gallery /
    logo walls). Returns the file:// URIs of EVERY resolved slot with that
    slot_id, in package order; absent / unresolved / missing-file / no-match all
    drop out, and no slots at all yields []."""
    (tmp_path / "assets").mkdir()
    for n in (0, 1, 2):
        (tmp_path / "assets" / f"3_proof_{n}.png").write_bytes(b"\x89PNG\r\n")
    ctx = _ctx(tmp_path)

    # 1) three resolved `proof` slots -> three URIs, in package order
    page = {
        "slots": [
            {"slot_id": "proof", "status": "resolved", "path": "assets/3_proof_0.png"},
            {"slot_id": "proof", "status": "resolved", "path": "assets/3_proof_1.png"},
            {"slot_id": "proof", "status": "resolved", "path": "assets/3_proof_2.png"},
        ]
    }
    uris = ctx.slot_uris(page, "proof")
    assert uris == [
        (tmp_path / "assets" / f"3_proof_{n}.png").resolve().as_uri() for n in (0, 1, 2)
    ]
    assert all(u.startswith("file://") for u in uris)

    # 2) a slot_id with no entries on the page -> [] (graceful empty)
    assert ctx.slot_uris(page, "press_logo") == []

    # 3) unresolved / missing-file entries are skipped; only resolved+present kept
    mixed = {
        "slots": [
            {"slot_id": "proof", "status": "resolved", "path": "assets/3_proof_0.png"},
            {"slot_id": "proof", "status": "absent", "path": None},
            {"slot_id": "proof", "status": "missing_required", "path": None},
            {"slot_id": "proof", "status": "resolved", "path": "assets/gone.png"},
            {"slot_id": "proof", "status": "resolved", "path": "assets/3_proof_2.png"},
        ]
    }
    assert ctx.slot_uris(mixed, "proof") == [
        (tmp_path / "assets" / "3_proof_0.png").resolve().as_uri(),
        (tmp_path / "assets" / "3_proof_2.png").resolve().as_uri(),
    ]

    # 4) no slots at all -> [] (never None, never a crash)
    assert ctx.slot_uris({}, "proof") == []
    assert ctx.slot_uris({"slots": []}, "proof") == []


def test_generic_renders_full_data(tmp_path) -> None:
    from patterns import _generic
    page = {
        "slot": 3, "st_type": "ST-05",
        "data": {
            "title": "Über uns",
            "subtitle": "Ein Satz Untertitel.",
            "body": "Absatz eins.\n\nAbsatz zwei mit **fett**.",
            "credibility_points": ["100+ Projekte", "30-50% Einsparung"],
        },
        "assets": [], "components": [],
    }
    frag = _generic.render(page, _ctx(tmp_path))
    assert isinstance(frag, PageFragment)
    assert "Über uns" in frag.html
    assert "Absatz eins" in frag.html
    assert "100+ Projekte" in frag.html
    assert frag.css.strip()  # non-empty scoped css
    # never leaks head-level rules
    assert "@page" not in frag.css and "@font-face" not in frag.css


def test_generic_handles_empty_data(tmp_path) -> None:
    from patterns import _generic
    page = {"slot": 9, "st_type": "ST-31", "data": {}, "assets": [], "components": []}
    frag = _generic.render(page, _ctx(tmp_path))
    assert isinstance(frag, PageFragment)
    assert "st-generic" in frag.html  # valid container, even if near-empty


def test_generic_renders_background_asset(tmp_path) -> None:
    from patterns import _generic
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "bg.png").write_bytes(b"\x89PNG\r\n")
    page = {
        "slot": 1, "st_type": "ST-01", "data": {"title": "Cover"},
        "assets": [{"slot_id": "cover_hero", "image_type": "background",
                    "path": "assets/bg.png", "status": "generated"}],
        "components": [],
    }
    frag = _generic.render(page, _ctx(tmp_path))
    # Background is painted directly on the .st-generic block via an inline
    # style (an abspos inset:0 child does not paint in WeasyPrint).
    assert 'class="st-generic" style="background-image:' in frag.html
    assert "bg.png" in frag.html


FIXTURES_APEX = CHASSIS_ROOT / "fixtures" / "apex"


def test_load_package_returns_typed_package() -> None:
    from package_loader import load_package, LoadedPackage
    from brand_tokens import BrandConfig
    pkg = load_package(FIXTURES_APEX)
    assert isinstance(pkg, LoadedPackage)
    assert isinstance(pkg.brand, BrandConfig)
    assert pkg.brand.brand_primary.startswith("#")
    assert len(pkg.pages) >= 1
    assert all(isinstance(p, dict) and "st_type" in p for p in pkg.pages)
    assert pkg.package_dir == FIXTURES_APEX.resolve()
    assert isinstance(pkg.report_assets, list)
    assert isinstance(pkg.fonts, dict)


def test_load_package_missing_manifest_raises(tmp_path) -> None:
    from package_loader import load_package
    with pytest.raises(FileNotFoundError):
        load_package(tmp_path)  # empty dir, no resolved_package.json


def test_load_package_incomplete_brand_raises(tmp_path) -> None:
    import json
    from package_loader import load_package
    (tmp_path / "resolved_package.json").write_text(
        json.dumps({"brand": {"brand_primary": "#111"}, "pages": []}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError):  # parse_brand_tokens: missing required keys
        load_package(tmp_path)


def _doc(body: str) -> str:
    return (
        "<html><head><style>"
        "@page { size: A4; margin: 15mm; } "
        "body { font-family: sans-serif; font-size: 12pt; }"
        "</style></head><body>" + body + "</body></html>"
    )


def test_overflow_false_for_fitting_content() -> None:
    from validators.overflow import check_overflow
    assert check_overflow(_doc("<p>A short paragraph that fits one page.</p>")) is False


def test_overflow_true_for_too_much_content() -> None:
    from validators.overflow import check_overflow
    huge = "<p>" + ("Wort " * 6000) + "</p>"
    assert check_overflow(_doc(huge)) is True


def _apex_case_study_page() -> dict:
    return {
        "slot": 7, "st_type": "ST-07A", "page_numbers": "10",
        "data": {
            "fallstudie_number": 1,
            "ergebnis_headline": "Von operativem Chaos zu skalierbarer KI-Infrastruktur",
            "kurzportraet": "Martina Ammon führt zwei Unternehmen parallel.",
            "ausgangsproblem": "Rapides Wachstum bedeutete täglich manuelle Anfragen.",
            "ziel": "Ohne automatisierte Betriebsebene frisst Kapazität sich selbst.",
            "loesung": "APEX implementierte Custom AI-Agenten in die bestehende Umgebung.",
            "ergebnis_text": "Anfragen in Minuten statt Stunden; Onboarding automatisch.",
            "ergebnis_metrics": [
                {"label": "Support-Reaktionszeit", "value": "24 Std. → Minuten"},
                {"label": "Support-Einsparung / Jahr", "value": "> 200.000 €"},
                {"label": "Automatisierte Kernprozesse", "value": "4"},
            ],
            "pullquote": {"text": "APEX hat unsere Antwortzeiten drastisch reduziert.",
                          "attribution": "Martina Ammon"},
            "kunde": {"name": "Martina Ammon", "funktion": "Gründerin",
                      "company_url": "example.de"},
        },
        "assets": [], "components": [],
    }


def test_st07a_returns_fragment_with_metrics(tmp_path) -> None:
    from patterns import st_07a
    frag = st_07a.render(_apex_case_study_page(), _ctx(tmp_path))
    assert isinstance(frag, PageFragment)
    assert frag.html.strip() and frag.css.strip()
    # head-level rules must NOT be in the fragment css
    assert "@page" not in frag.css
    assert "@font-face" not in frag.css
    assert ":root" not in frag.css
    # Plan B rebuild: the page-scoped two-column grid (was .lrp-grid -> .cs-grid),
    # scoped under the assembler's .st-07a section (not the bare .page container).
    assert ".st-07a" in frag.css
    assert "cs-grid" in frag.css
    # case content present
    assert "Von operativem Chaos" in frag.html
    assert "FALLSTUDIE" in frag.html
    # ergebnis_metrics render via the stat_strip macro (c-stat-strip class).
    assert "c-stat-strip" in frag.html
    assert "200.000" in frag.html
    assert "Support-Reaktionszeit" in frag.html


def test_st07a_omits_portrait_box_entirely_when_absent(tmp_path) -> None:
    """Owner decision (DNA §C2/§3): a case study with NO resolved
    case_study_portrait slot renders NO photo AND NO empty placeholder box — the
    sidebar reflows to the name/role/url + QR/quote panel. Never an empty grey
    plate."""
    from patterns import st_07a
    frag = st_07a.render(_apex_case_study_page(), _ctx(tmp_path))
    # no portrait wrapper at all (not merely an empty media figure)
    assert "cs-portrait" not in frag.html, "no portrait block should render when absent"
    # and specifically NO empty media placeholder (the old ugly grey box)
    assert "c-media--empty" not in frag.html
    assert "c-media-img--placeholder" not in frag.html
    # the sidebar still carries the named client block + the QR/quote panel
    assert "cs-kunde" in frag.html and "Martina Ammon" in frag.html
    assert "cs-panel" in frag.html


def test_st07a_renders_large_framed_portrait_when_slot_resolved(tmp_path) -> None:
    """When the case_study_portrait slot RESOLVES, a LARGE framed portrait renders
    in the sidebar (DNA §C2) — sourced from the v2.0 slots[] via ctx.slot_uri,
    NOT page['assets']. The resolved file URI flows into a c-media background."""
    from patterns import st_07a
    (tmp_path / "assets").mkdir()
    portrait = tmp_path / "assets" / "12_case_study_portrait_3.png"
    portrait.write_bytes(b"\x89PNG\r\n")
    page = _apex_case_study_page()
    page["slots"] = [
        {"slot_id": "case_study_portrait", "status": "resolved",
         "path": "assets/12_case_study_portrait_3.png"},
    ]
    frag = st_07a.render(page, _ctx(tmp_path))
    # the portrait block renders, framed, with the resolved file URI as a bg image
    assert "cs-portrait" in frag.html
    assert "c-media--frame" in frag.html
    assert "c-media--empty" not in frag.html       # a real photo, not a placeholder
    assert portrait.resolve().as_uri() in frag.html
    # the page-local CSS gives it a concrete (large) height (DNA §C2: never tiny)
    assert ".cs-portrait .c-media-img" in frag.css and "mm" in frag.css


def test_registry_dispatch() -> None:
    from patterns import get_renderer
    from patterns import st_07a, st_01, _generic
    assert get_renderer("ST-07A") is st_07a.render
    assert get_renderer("ST-99") is _generic.render  # truly-unknown type -> generic fallback
    assert get_renderer("ST-01") is st_01.render  # implemented in R2 Batch 4


def test_shared_head_has_page_fonts_and_folio() -> None:
    from assembler import shared_head_css
    css = shared_head_css(parse_brand_tokens(SAMPLE_BRAND), CHASSIS_ROOT / "fonts")
    assert "@page" in css
    assert "@font-face" in css
    assert "--brand-primary" in css
    assert "string(pagefolio)" in css  # per-page folio mechanism


def test_render_package_apex(tmp_path) -> None:
    """Integration: the regenerated apex package renders to a 24-page PDF."""
    from assembler import render_package, RenderResult
    result = render_package(FIXTURES_APEX, tmp_path)
    assert isinstance(result, RenderResult)
    assert result.pdf_path.exists()
    assert result.pdf_path.stat().st_size > 5000
    # US-604/605: ST-02 (2) + ST-05 (2) + ST-06 (2) + FAZIT (2) continuations
    # expand the deck to 24 pages.
    assert result.page_count == 24
    assert len(result.png_paths) >= 20        # physical pages rasterized
    assert isinstance(result.overflow, list)
    assert isinstance(result.warnings, list)
