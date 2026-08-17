from __future__ import annotations
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
CHASSIS_ROOT = HERE.parent
sys.path.insert(0, str(CHASSIS_ROOT))

from brand_tokens import parse_brand_tokens  # noqa: E402
from tokens.compile_tokens import compile_tokens, BrandAxes  # noqa: E402

SAMPLE = {
    "brand_primary": "#5a9ab3", "brand_accent": "#85d2ee",
    "brand_neutral_dark": "#0F0F1F", "brand_neutral_mid": "#7A7A8C",
    "brand_neutral_light": "#fdffff", "font_heading": "Gestura Headline",
    "font_body": "Source Sans 3", "qr_target_url": "https://x.de",
    "company_name_short": "X", "company_url_display": "x.de",
}


def _sample_tokens(**overrides) -> dict:
    """A complete 10-key brand-token dict with bundled-font defaults.

    Defaults to font_heading / font_body = "Source Sans 3" (a bundled, loading
    family) and valid hex colours, so a test can override exactly the field it
    exercises without tripping parse_brand_tokens' required-key gate or emitting
    a spurious unbundled-font warning.
    """
    base = {
        "brand_primary": "#5a9ab3",
        "brand_accent": "#85d2ee",
        "brand_neutral_dark": "#0F0F1F",
        "brand_neutral_mid": "#7A7A8C",
        "brand_neutral_light": "#fdffff",
        "font_heading": "Source Sans 3",
        "font_body": "Source Sans 3",
        "qr_target_url": "https://x.de",
        "company_name_short": "X",
        "company_url_display": "x.de",
    }
    base.update(overrides)
    return base

def test_compile_tokens_emits_semantic_and_legacy_vars():
    brand = parse_brand_tokens(SAMPLE)
    css, attrs = compile_tokens(brand, BrandAxes(headline_type="serif"))
    # new semantic vars
    assert "--color-accent: #85d2ee" in css
    assert "--color-primary: #5a9ab3" in css
    assert "--font-display:" in css and "--font-serif:" in css
    assert "--space-4:" in css and "--type-display:" in css
    # legacy aliases (so existing patterns keep working)
    assert "--brand-primary: #5a9ab3" in css
    assert "--brand-accent: #85d2ee" in css
    assert "--brand-neutral-light: #fdffff" in css
    # serif axis -> display family is the serif var
    assert "--font-display: var(--font-serif)" in css
    # data attrs
    assert attrs["data-headline-type"] == "serif"

def test_sans_axis_uses_sans_display():
    brand = parse_brand_tokens(SAMPLE)
    css, attrs = compile_tokens(brand, BrandAxes(headline_type="sans"))
    assert "--font-display: var(--font-sans-head)" in css
    assert attrs["data-headline-type"] == "sans"

def test_font_head_follows_display_so_serif_brand_gets_serif_headings():
    """--font-head must FOLLOW --font-display so a serif-headline brand renders
    serif headings (the editorial signal) and the display serif embeds (clearing
    the N03 font-fallback hard-fail). A sans brand is unchanged. Regression guard
    for the bug where --font-head was pinned to the sans-head stack and serif
    brands silently got sans headlines on an unbundled brand face."""
    brand = parse_brand_tokens(SAMPLE)
    css_serif, _ = compile_tokens(brand, BrandAxes(headline_type="serif"))
    assert "--font-head: var(--font-display)" in css_serif
    assert "--font-display: var(--font-serif)" in css_serif  # transitively serif
    css_sans, _ = compile_tokens(brand, BrandAxes(headline_type="sans"))
    assert "--font-head: var(--font-display)" in css_sans
    assert "--font-display: var(--font-sans-head)" in css_sans

def test_brandaxes_defaults():
    ax = BrandAxes()
    assert ax.headline_type == "serif"  # Phase A default; was trivially `in (…)` before
    assert ax.ground_mode and ax.texture and ax.accent_mechanic

def test_emits_tint_and_ground_roles():
    from tokens.compile_tokens import compile_tokens, BrandAxes
    from brand_tokens import BrandConfig
    brand = BrandConfig(
        brand_primary="#5a9ab3", brand_accent="#85d2ee", brand_neutral_dark="#1a2230",
        brand_neutral_mid="#8a93a0", brand_neutral_light="#fdffff",
        font_heading="Montserrat", font_body="Source Sans 3",
        qr_target_url="https://x", company_name_short="X", company_url_display="x.de")
    css, _ = compile_tokens(brand, BrandAxes(accent_mechanic="tonal_same_hue"))
    assert "--color-accent-tint:" in css
    assert "--color-on-accent:" in css
    assert "--color-ground-wash:" in css


# ── NEW: --color-on-primary token ─────────────────────────────────────────

def test_compile_tokens_emits_color_on_primary():
    """`--color-on-primary` must be present in the :root block."""
    brand = parse_brand_tokens(SAMPLE)
    css, _ = compile_tokens(brand, BrandAxes())
    assert "--color-on-primary:" in css


def test_dark_primary_yields_light_on_primary():
    """A very dark primary (e.g. deep navy #1A2540) → light on-color (not brand_neutral_dark)."""
    from brand_tokens import BrandConfig
    dark_brand = BrandConfig(
        brand_primary="#1A2540",   # deep navy — clearly dark
        brand_accent="#E97E47",
        brand_neutral_dark="#0F0F1F",
        brand_neutral_mid="#7A7A8C",
        brand_neutral_light="#F5EFE3",
        font_heading="Montserrat", font_body="Source Sans 3",
        qr_target_url="https://x", company_name_short="X", company_url_display="x.de",
    )
    css, _ = compile_tokens(dark_brand, BrandAxes())
    # Extract --color-on-primary value from CSS
    for line in css.splitlines():
        if "--color-on-primary:" in line:
            # dark primary → on-color must be the light on-dark value, NOT the dark neutral
            # The dark primary has low luminance, so on-color should NOT be brand_neutral_dark
            assert "#0F0F1F" not in line, (
                f"Dark primary should yield light on-color, got: {line.strip()}"
            )
            break
    else:
        raise AssertionError("--color-on-primary not found in CSS output")


def test_light_primary_yields_dark_on_primary():
    """A light primary → on-color is the dark ink color."""
    from brand_tokens import BrandConfig
    light_brand = BrandConfig(
        brand_primary="#F5EFE3",   # near-white light primary
        brand_accent="#E97E47",
        brand_neutral_dark="#0F0F1F",
        brand_neutral_mid="#7A7A8C",
        brand_neutral_light="#FFFFFF",
        font_heading="Montserrat", font_body="Source Sans 3",
        qr_target_url="https://x", company_name_short="X", company_url_display="x.de",
    )
    css, _ = compile_tokens(light_brand, BrandAxes())
    for line in css.splitlines():
        if "--color-on-primary:" in line:
            # light primary → on-color should be the dark neutral (#0F0F1F)
            assert "#0F0F1F" in line, (
                f"Light primary should yield dark on-color, got: {line.strip()}"
            )
            break
    else:
        raise AssertionError("--color-on-primary not found in CSS output")


# ── T1: brand/OSS heading font wired end-to-end ───────────────────────────

def test_brand_heading_font_is_wired_into_font_stack():
    from brand_tokens import parse_brand_tokens
    from tokens.compile_tokens import compile_tokens, BrandAxes
    brand = parse_brand_tokens(_sample_tokens(font_heading="Acme Grotesk", font_body="Acme Text"))
    css, _ = compile_tokens(brand, BrandAxes(headline_type="sans"))
    assert "Acme Grotesk" in css
    assert "Acme Text" in css


def test_default_serif_is_loading_editorial_face_not_fallback():
    # Root-cause fix (plan 2026-06-03-renderer-phase-A): the bundled display serif
    # must be Source Serif 4 — a face that ACTUALLY LOADS in WeasyPrint+fontconfig
    # (its cmap has a format-12 subtable). Playfair/Fraunces were format-4-only →
    # fontconfig empty-charset → never loaded → headlines fell back to system serif.
    from brand_tokens import parse_brand_tokens
    from tokens.compile_tokens import compile_tokens, BrandAxes
    brand = parse_brand_tokens(_sample_tokens())
    css, _ = compile_tokens(brand, BrandAxes(headline_type="serif"))
    assert "Source Serif 4" in css
    assert "Playfair" not in css
    assert "Fraunces" not in css


def test_unbundled_brand_font_emits_warning(caplog):
    import logging
    from brand_tokens import parse_brand_tokens
    from tokens.compile_tokens import compile_tokens, BrandAxes
    brand = parse_brand_tokens(_sample_tokens(font_heading="Nonexistent Licensed Face"))
    with caplog.at_level(logging.WARNING):
        compile_tokens(brand, BrandAxes())
    assert any("Nonexistent Licensed Face" in r.message for r in caplog.records)


# ── T2: hero display type tier ────────────────────────────────────────────

def test_hero_type_tier_exists_and_is_largest():
    import json, pathlib
    t = json.loads(pathlib.Path("tokens/base.tokens.json").read_text())["type"]
    pt = lambda v: float(v["$value"].replace("pt", ""))
    assert "hero" in t
    assert pt(t["hero"]) >= 44
    assert pt(t["hero"]) > pt(t["display-xl"])


# ── Task 1: Scale-B type ramp ─────────────────────────────────────────────

def test_type_scale_B_values():
    """Scale-B ramp: changed (h3 14, h2 20, display 32) + net-new tokens (source,
    caption, cta, signature, pullquote, stat, stat-xl) are emitted correctly."""
    from brand_tokens import parse_brand_tokens
    from tokens.compile_tokens import compile_tokens, BrandAxes
    brand = parse_brand_tokens(_sample_tokens())
    css, _ = compile_tokens(brand, BrandAxes())
    # changed values
    assert "--type-h2: 20pt" in css
    assert "--type-h3: 14pt" in css
    assert "--type-display: 32pt" in css
    # net-new tokens
    assert "--type-stat-xl: 60pt" in css
    assert "--type-stat: 40pt" in css
    assert "--type-pullquote: 18pt" in css
    assert "--type-signature: 28pt" in css
    assert "--type-cta: 11.5pt" in css
    assert "--type-source: 7.5pt" in css
    assert "--type-caption: 8.5pt" in css


# ── Task 3: new color roles ───────────────────────────────────────────────

def test_panel_role_follows_accent_mechanic():
    """--color-panel uses var(--color-ink) for tonal_same_hue,
    var(--color-primary) for contrasting_hue; both always emit --color-on-panel."""
    from brand_tokens import BrandConfig
    from tokens.compile_tokens import compile_tokens, BrandAxes

    brand = BrandConfig(
        brand_primary="#5a9ab3",
        brand_accent="#85d2ee",
        brand_neutral_dark="#0F0F1F",
        brand_neutral_mid="#7A7A8C",
        brand_neutral_light="#fdffff",
        font_heading="Source Sans 3",
        font_body="Source Sans 3",
        qr_target_url="https://x.de",
        company_name_short="X",
        company_url_display="x.de",
    )

    # tonal_same_hue → panel = ink
    css_tonal, _ = compile_tokens(brand, BrandAxes(accent_mechanic="tonal_same_hue"))
    assert "--color-panel: var(--color-ink)" in css_tonal
    assert "--color-on-panel:" in css_tonal

    # contrasting_hue → panel = primary
    css_contrast, _ = compile_tokens(brand, BrandAxes(accent_mechanic="contrasting_hue"))
    assert "--color-panel: var(--color-primary)" in css_contrast
    assert "--color-on-panel:" in css_contrast


# ── lede type token ──────────────────────────────────────────────────────

def test_type_lede_token():
    """--type-lede (12pt) must be emitted — a tier between body (10.5pt) and h3 (14pt)."""
    from brand_tokens import parse_brand_tokens
    from tokens.compile_tokens import compile_tokens, BrandAxes
    brand = parse_brand_tokens(_sample_tokens())
    css, _ = compile_tokens(brand, BrandAxes())
    assert "--type-lede: 12pt" in css


# ── Task 5: serif display default ────────────────────────────────────────

def test_display_default_is_serif():
    """BrandAxes() (no args) must resolve display family to var(--font-serif).

    This is the Phase A theme-lock: all reports default to the editorial serif
    display face unless an axis explicitly selects sans or sans_allcaps.
    """
    from brand_tokens import parse_brand_tokens
    from tokens.compile_tokens import compile_tokens, BrandAxes
    brand = parse_brand_tokens(_sample_tokens())
    css, _ = compile_tokens(brand, BrandAxes())
    assert "--font-display: var(--font-serif)" in css, (
        "BrandAxes() default must produce a serif display family"
    )


def test_neutral_role_aliases_and_ground():
    """--color-neutral-dark/mid/light and --color-ground are all emitted;
    --color-ground must differ from --color-neutral-light."""
    from brand_tokens import BrandConfig
    from tokens.compile_tokens import compile_tokens, BrandAxes

    brand = BrandConfig(
        brand_primary="#5a9ab3",
        brand_accent="#85d2ee",
        brand_neutral_dark="#0F0F1F",
        brand_neutral_mid="#7A7A8C",
        brand_neutral_light="#fdffff",
        font_heading="Source Sans 3",
        font_body="Source Sans 3",
        qr_target_url="https://x.de",
        company_name_short="X",
        company_url_display="x.de",
    )
    css, _ = compile_tokens(brand, BrandAxes())

    assert "--color-neutral-dark:" in css
    assert "--color-neutral-mid:" in css
    assert "--color-neutral-light:" in css
    assert "--color-ground:" in css

    # extract the emitted values and confirm ground != neutral-light
    ground_val = None
    neutral_light_val = None
    for line in css.splitlines():
        stripped = line.strip()
        if stripped.startswith("--color-ground:"):
            ground_val = stripped.split(":", 1)[1].strip().rstrip(";")
        if stripped.startswith("--color-neutral-light:"):
            neutral_light_val = stripped.split(":", 1)[1].strip().rstrip(";")

    assert ground_val is not None, "--color-ground not found in CSS"
    assert neutral_light_val is not None, "--color-neutral-light not found in CSS"
    assert ground_val != neutral_light_val, (
        f"--color-ground ({ground_val!r}) must differ from "
        f"--color-neutral-light ({neutral_light_val!r})"
    )


# ── Task 5: font preflight faces ─────────────────────────────────────────

def test_required_fonts_are_loaded_faces():
    """_REQUIRED_FONTS in render.py must list the Source family faces that actually
    load via @font-face in WeasyPrint+fontconfig, and NOT Montserrat (format-4-only
    cmap, does not load in fontconfig).
    """
    import importlib.util, sys as _sys
    spec = importlib.util.spec_from_file_location(
        "render_module", CHASSIS_ROOT / "render.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    fonts = mod._REQUIRED_FONTS
    assert any("SourceSans3" in f for f in fonts), (
        "SourceSans3 must be in _REQUIRED_FONTS"
    )
    assert any("SourceSerif4" in f for f in fonts), (
        "SourceSerif4 must be in _REQUIRED_FONTS"
    )
    assert not any("Montserrat" in f for f in fonts), (
        "Montserrat must NOT be in _REQUIRED_FONTS (format-4-only cmap, does not load)"
    )


import re as _re  # noqa: E402

_TYPE_VAR_DEF = _re.compile(r"--(type-[a-z0-9-]+)\s*:")
_TYPE_VAR_REF = _re.compile(r"var\(\s*--(type-[a-z0-9-]+)\s*(,[^)]*)?\)")


def test_css_references_only_defined_type_tokens():
    """Every var(--type-*) in a stylesheet must name a token the compiler emits.

    A reference to an UNDEFINED custom property with no fallback (e.g. the
    non-existent --type-h1) makes the ENTIRE font-size declaration invalid, so the
    element silently inherits body size. That is exactly the bug that shrank the
    editorial-fill hero headline (and the a3 case-study headline, and the
    case-study quote glyph) to body size. This guard fails the build if any CSS
    references a --type-* token that is not defined and carries no fallback.
    """
    brand = parse_brand_tokens(_sample_tokens())
    css, _ = compile_tokens(brand, BrandAxes(headline_type="serif"))
    defined = set(_TYPE_VAR_DEF.findall(css))
    # sanity: the compiler really did emit the canonical ramp
    assert {"type-display", "type-h2", "type-h3", "type-lede"} <= defined

    offenders: list[str] = []
    for path in sorted(CHASSIS_ROOT.glob("styles/**/*.css")):
        text = path.read_text(encoding="utf-8")
        for m in _TYPE_VAR_REF.finditer(text):
            name, fallback = m.group(1), m.group(2)
            if name not in defined and not fallback:
                rel = path.relative_to(CHASSIS_ROOT)
                offenders.append(f"{rel}: var(--{name}) is undefined and has no fallback")
    assert not offenders, (
        "CSS references undefined --type-* tokens (invalid font-size -> silent "
        "inherit):\n  " + "\n  ".join(offenders)
    )
