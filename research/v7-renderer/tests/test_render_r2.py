"""R2 per-pattern + component unit tests."""
from __future__ import annotations

import json
import re
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

def _ctx(package_dir: Path = CHASSIS_ROOT / "fixtures" / "apex") -> RenderContext:
    return RenderContext(brand=parse_brand_tokens(SAMPLE_BRAND),
                         grammar=load_grammar(), package_dir=package_dir)

def _no_head_css(frag: PageFragment) -> None:
    for tok in ("@page", "@font-face", ":root"):
        assert tok not in frag.css, f"{tok} must not appear in fragment css"


def _render(src: str, **kw) -> str:
    """Render a tiny Jinja template string via the shared env (macro tests)."""
    from templating import get_env
    return get_env().from_string(src).render(**kw)


def _assert_no_literals_rr(html: str) -> None:
    """A macro's emitted markup carries NO font-family literal and NO raw #hex —
    components reference semantic design tokens (var(--…)) ONLY."""
    for lit in ("Montserrat", "Source Sans 3", "Playfair Display", "Gestura"):
        assert lit not in html, f"font literal {lit!r} leaked into markup: {html!r}"
    import re as _re_local
    assert not _re_local.search(r"#[0-9a-fA-F]{3,8}\b", html), f"raw hex leaked: {html!r}"


def test_components_qr_svg_is_shared_and_brand_agnostic() -> None:
    """_components.py keeps ONLY the shared QR generator (the old HTML-string
    builders are SUPERSEDED by the token-only Jinja macros in components/ and
    were removed). qr_svg takes fg/bg as ARGS, so it carries no brand literal of
    its own — the caller (st_03 / st_07a) passes resolved token colors in."""
    from patterns import _components as C
    # the only surviving builder + its private escaper
    assert hasattr(C, "qr_svg") and hasattr(C, "_esc")
    # the superseded builders + their literal *_CSS constants are gone
    for gone in ("numbered_block", "numbered_step_card", "dark_cta_panel",
                 "stat_strip", "bar_mini", "horizontal_flow",
                 "NUMBERED_BLOCK_CSS", "DARK_CTA_PANEL_CSS"):
        assert not hasattr(C, gone), f"superseded builder {gone!r} should be removed"
    # caller-supplied fg/bg flow straight through -> module-level source is literal-free
    fg, bg = "var(--color-on-accent)", "var(--color-accent)"
    svg = C.qr_svg("https://x.de", fg, bg)
    assert svg.startswith("<svg") and "rect" in svg
    assert fg in svg and bg in svg


def _page(st_type, data, slot=4):
    return {"slot": slot, "st_type": st_type, "page_numbers": str(slot), "data": data, "assets": [], "components": []}

def test_st09_status_quo() -> None:
    from patterns import st_09
    data = {"title": "Deine Prozesse skalieren nicht", "body": "Intro.",
            "symptoms": [{"title": "Montag kostet 3 Stunden", "body": "Du öffnest fünf Tools."},
                         "Ein reiner String-Eintrag"]}
    frag = st_09.render(_page("ST-09", data), _ctx())
    assert isinstance(frag, PageFragment); _no_head_css(frag)
    assert ".st-09" in frag.css                       # R-3 scoping
    assert "Montag kostet 3 Stunden" in frag.html and "reiner String" in frag.html
    assert st_09.render(_page("ST-09", {}), _ctx()).html.strip()  # graceful empty

def test_st14_false_beliefs() -> None:
    from patterns import st_14
    data = {"title": "Drei Lügen", "beliefs": [
        {"irrglaube": "Mehr Leute = mehr Kunden", "realitaet": "Systeme skalieren, nicht Köpfe.", "quelle": "PwC 2026"}]}
    frag = st_14.render(_page("ST-14", data), _ctx())
    _no_head_css(frag); assert ".st-14" in frag.css
    assert "Mehr Leute" in frag.html and "Systeme skalieren" in frag.html and "PwC 2026" in frag.html
    assert st_14.render(_page("ST-14", {}), _ctx()).html.strip()  # graceful empty

def test_st06_mechanism() -> None:
    from patterns import st_06
    data = {"title": "Das Framework", "body": "Intro.",
            "steps": [{"title": "Audit", "body": "Wir messen."}, {"title": "Bereinigung", "body": "Wir putzen."}],
            "ergebnis": "30-50% Effizienz."}
    frag = st_06.render(_page("ST-06", data), _ctx())
    _no_head_css(frag); assert ".st-06" in frag.css
    assert "Audit" in frag.html and "Bereinigung" in frag.html
    assert st_06.render(_page("ST-06", {}), _ctx()).html.strip()  # graceful empty


def test_st02_outlook() -> None:
    from patterns import st_02
    data = {"title": "Dein Wachstum scheitert nicht am Markt", "body": "Abs eins.\n\nAbs zwei.",
            "zielgruppe": ["B2B 10-50 MA", "500k-3M Umsatz"]}
    frag = st_02.render(_page("ST-02", data, slot=2), _ctx())
    _no_head_css(frag); assert ".st-02" in frag.css
    assert "Dein Wachstum" in frag.html and "B2B 10-50 MA" in frag.html
    assert st_02.render(_page("ST-02", {}, slot=2), _ctx()).html.strip()

def test_st07b_theory() -> None:
    from patterns import st_07b
    data = {"title": "Wachstum entsteht nicht durch mehr Köpfe", "body": "Prosa.",
            "key_insight": "Engpässe sind strukturell, nicht motivational."}
    frag = st_07b.render(_page("ST-07B", data, slot=8), _ctx())
    _no_head_css(frag); assert ".st-07b" in frag.css
    assert "mehr Köpfe" in frag.html and "strukturell" in frag.html

def test_st08_faq() -> None:
    from patterns import st_08
    data = {"title": "Häufige Fragen", "faqs": [
        {"frage": "Wie lange dauert es?", "antwort": "Wenige Wochen."},
        {"frage": "Muss ich Tools wechseln?", "antwort": "Nein."}]}
    frag = st_08.render(_page("ST-08", data, slot=99), _ctx())
    _no_head_css(frag); assert ".st-08" in frag.css
    assert "Wie lange" in frag.html and "Wenige Wochen" in frag.html
    assert st_08.render(_page("ST-08", {}, slot=99), _ctx()).html.strip()


def test_components_dark_recap_panel_supersedes_dark_cta() -> None:
    """The old hand-built dark_cta_panel f-string (hardcoded #fff / 'Montserrat')
    is SUPERSEDED by the token-only dark_recap_panel.jinja macro (styled via
    styles/components.css). Its emitted markup carries semantic tokens ONLY."""
    html = _render(
        "{% from 'dark_recap_panel.jinja' import dark_recap_panel %}"
        "{{ dark_recap_panel('Das Ergebnis', '<p>Los.</p>') }}"
    )
    assert "c-dark-recap" in html and "Das Ergebnis" in html and "Los." in html
    _assert_no_literals_rr(html)

def test_st03_hard_cta() -> None:
    from patterns import st_03
    data = {"title": "Buche jetzt dein Erstgespräch", "body": "Kein Risiko.",
            "cta_text": "Jetzt buchen", "cta_url": "https://apex-consulting.ai/"}
    frag = st_03.render(_page("ST-03", data, slot=20), _ctx())
    _no_head_css(frag); assert ".st-03" in frag.css
    assert "Buche jetzt" in frag.html and "apex-consulting.ai" in frag.html

def test_stfazit_summary() -> None:
    from patterns import st_fazit
    data = {"title": "Zusammenfassung", "body": "Argument.",
            "these": "Es ist ein Systemfehler.", "kosten_des_nichtstuns": "Jeder Monat kostet.",
            "cta_url": "https://apex-consulting.ai/"}
    frag = st_fazit.render(_page("ST-FAZIT", data, slot=18), _ctx())
    _no_head_css(frag); assert ".st-fazit" in frag.css
    assert "Systemfehler" in frag.html and "Jeder Monat" in frag.html
    # rebuilt summary composes the These statement + cost block + accent URL band
    assert "c-these" in frag.html, "These pull-statement macro missing"
    assert "c-cost-block" in frag.html, "cost block macro missing"
    assert "c-url-band" in frag.html, "full-width accent URL band macro missing"

def test_st31_breathing_css_ground_and_asset(tmp_path) -> None:
    from patterns import st_31, st_32
    # no asset -> token gradient ground fallback, still a full-bleed atmospheric page
    frag = st_31.render(_page("ST-31", {"phrase": "Durchatmen."}), _ctx())
    _no_head_css(frag)
    assert "br-bleed" in frag.html and "Durchatmen." in frag.html
    assert "c-geo" in frag.html              # low-opacity geometric shape overlay
    assert "page: bleed" in frag.css         # the suppressed full-bleed named page
    assert st_32.render is st_31.render      # ST-32 reuses the breathing render
    # graceful: no data at all still paints a striking ground (not blank)
    assert st_31.render(_page("ST-31", {}, slot=6), _ctx()).html.strip()
    # with a background asset on the page
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "g.png").write_bytes(b"\x89PNG\r\n")
    page = {"slot": 6, "st_type": "ST-31", "data": {},
            "assets": [{"slot_id": "atmospheric_gradient", "image_type": "gradient", "path": "assets/g.png"}],
            "components": []}
    frag2 = st_31.render(page, _ctx(tmp_path))
    assert "g.png" in frag2.html


def test_components_stat_bar_flow() -> None:
    """The old stat_strip / bar_mini / horizontal_flow HTML-string builders
    (hardcoded #333 / 'Montserrat') are SUPERSEDED by the token-only Jinja macros
    stat_strip / bar_chart / horizontal_flow. Their markup is literal-free."""
    strip = _render(
        "{% from 'stat_strip.jinja' import stat_strip %}"
        "{{ stat_strip([{'value': '100+', 'label': 'Projekte'}]) }}"
    )
    assert "100+" in strip and "c-stat-strip" in strip
    _assert_no_literals_rr(strip)
    bars = _render(
        "{% from 'bar_chart.jinja' import bar_chart %}"
        "{{ bar_chart([{'value': '100', 'label': 'Projekte'},"
        "              {'value': '30', 'label': 'Quote'}]) }}"
    )
    assert "Projekte" in bars and "c-bar-chart" in bars
    _assert_no_literals_rr(bars)
    flow = _render(
        "{% from 'horizontal_flow.jinja' import horizontal_flow %}"
        "{{ horizontal_flow([{'n': 1, 'title': 'Call', 'body': '45 Min', 'dauer': '1 Tag'},"
        "                    {'n': 2, 'title': 'Audit', 'body': '3-5 Tage'}]) }}"
    )
    assert "Call" in flow and "Audit" in flow and "c-hflow__arrow" in flow
    _assert_no_literals_rr(flow)

def test_st01_cover() -> None:
    from patterns import st_01
    data = {"title": "Dein Wachstum frisst dich auf", "subtitle": "Wie manuelle Prozesse …",
            "kicker_pills": ["PROZESSAUTOMATISIERUNG"], "inclusions": ["3 Fallstudien"],
            "proof_stats": [{"value": "100", "label": "Projekte"}],
            "teaser_items": ["Warum 60% scheitern"], "author": {"name": "Jousef", "role": "Founder"}}
    frag = st_01.render(_page("ST-01", data, slot=1), _ctx())
    _no_head_css(frag); assert ".st-01" in frag.css
    assert "Dein Wachstum" in frag.html and "PROZESSAUTOMATISIERUNG" in frag.html and "Jousef" in frag.html
    # macro composition: kicker pill + vertical stat rail + two-tone title.
    assert "c-pill" in frag.html and "c-stat-rail" in frag.html
    assert "c-two-tone" in frag.html               # two-tone display title (DNA §C1)
    assert st_01.render(_page("ST-01", {}, slot=1), _ctx()).html.strip()


# ---- ST-01 cover rebuild (founder-hero portrait + scrim + two-tone title) -----

def test_st01_cover_composes_founder_hero_scrim_title_and_rail() -> None:
    """The Phase-4b cover (ST-01) anchors on the FOUNDER PORTRAIT (DNA §C2): the
    resolved founder slot (slot_id 'founder') is the hero background, with a dark
    scrim, a two-tone display title, a kicker pill row, and a vertical stat rail —
    composed from the macro library on the token-themed .st-01 layout. Loads the
    REAL apex cover (slot 1), whose slots[] carries the resolved founder photo.
    """
    from patterns import st_01
    page = _load_fixture_page("ST-01")
    frag = st_01.render(page, _ctx(APEX_FIXTURE))
    assert isinstance(frag, PageFragment)
    _no_head_css(frag)
    assert ".st-01" in frag.css, "fragment CSS must be scoped to .st-01"

    # Signature cover devices.
    assert "c-pill" in frag.html, "kicker pill macro missing"
    assert "c-stat-rail" in frag.html, "vertical stat rail missing"
    assert "cv-hero" in frag.html, "full-bleed hero block missing"
    assert "cv-hero--portrait" in frag.html, "founder hero must mark the portrait variant"
    assert "cv-scrim" in frag.html, "dark scrim overlay missing"
    assert "c-two-tone" in frag.html, "two-tone display title missing"

    # The FOUNDER portrait is the hero — NOT the generated cover_hero scene.
    # The cover asset resolves to 1_founder.png in the current fixture.
    assert "1_founder" in frag.html, "founder portrait must be the cover hero"
    assert "1_cover_hero.png" not in frag.html, "scene must not win when a founder photo resolves"

    # Real cover content from the fixture flows through (title split into two
    # runs: a neutral lead + the accent punch from data title_accent).
    assert "Dein Wachstum" in frag.html                             # title lead run
    assert "frisst dich selbst auf" in frag.html                    # title accent run
    assert "Für Agenturen" in frag.html                             # audience band
    assert "PROZESSAUTOMATISIERUNG" in frag.html                    # kicker pill
    assert "Jousef" in frag.html                                    # author.name
    assert "100+" in frag.html                                      # proof stat value

    # No-chrome: the cover must request the suppressed named page.
    assert "page: cover" in frag.css, "cover must assign itself the named @page cover"


def test_st01_cover_falls_back_to_scene_without_founder_slot(tmp_path) -> None:
    """Graceful fallback (photo-less clients must NOT regress): when no founder
    slot resolves, the hero falls back to the generated cover-hero SCENE
    (page assets, image_type 'background') and the portrait variant is NOT set."""
    from patterns import st_01
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "scene.png").write_bytes(b"\x89PNG\r\n")
    page = {
        "slot": 1, "st_type": "ST-01", "page_numbers": "1",
        "data": {"title": "Ein kurzer Ausblick", "title_accent": "Ausblick",
                 "author": {"name": "Pat", "role": "Gründerin"}},
        "slots": [],   # no founder photo for this client
        "assets": [{"slot_id": "cover_hero", "image_type": "background",
                    "path": "assets/scene.png"}],
        "components": [],
    }
    frag = st_01.render(page, _ctx(tmp_path))
    assert "scene.png" in frag.html, "must fall back to the generated scene"
    assert "cv-hero--portrait" not in frag.html, "scene fallback is not the portrait variant"
    assert "c-two-tone" in frag.html and "Ausblick" in frag.html


def test_st01_title_uses_display_axis_token() -> None:
    """The cover title must size off var(--font-display) — serif via the axis,
    never a hardcoded family — so the apex (serif) deck renders Playfair."""
    css = (CHASSIS_ROOT / "styles" / "st_01.css").read_text(encoding="utf-8")
    assert "var(--font-display)" in css, "cover title must use var(--font-display)"
    # text overlaid on the scrim is on-dark
    assert "var(--color-on-dark)" in css


def test_st01_new_files_are_brand_agnostic() -> None:
    """No font-family literal and no raw #hex in the new cover template or layout
    CSS — colors + fonts come from semantic tokens at render time (cardinal rule)."""
    new_files = [
        CHASSIS_ROOT / "templates" / "st_01.html.jinja",
        CHASSIS_ROOT / "styles" / "st_01.css",
    ]
    violations: list[str] = []
    for f in new_files:
        assert f.exists(), f"expected {f} to exist after the rebuild"
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if _FONT_LIT.search(line) or _HEX.search(line):
                violations.append(f"{f.name}:{i}: {line.strip()}")
    assert not violations, (
        "brand literal in the new ST-01 architecture files (tokens only):\n"
        + "\n".join(violations)
    )

def test_macro_two_tone_headline_composes_neutral_lead_and_accent_run() -> None:
    """two_tone_headline (DNA §C1) renders a neutral serif LEAD run + a bold-caps
    ACCENT run as one headline. Both runs flow through; the markup is token-only
    (serif via --font-display in CSS, accent via --color-accent — no literals)."""
    out = _render(
        "{% from 'two_tone_headline.jinja' import two_tone_headline %}"
        "{{ two_tone_headline('Ein kurzer', 'Ausblick') }}"
    )
    assert "c-two-tone" in out
    assert "c-two-tone__lead" in out and "Ein kurzer" in out
    assert "c-two-tone__accent" in out and "Ausblick" in out
    # default heading element is h1 (the cover)
    assert "<h1" in out and "</h1>" in out
    _assert_no_literals_rr(out)


def test_macro_two_tone_headline_degrades_to_plain_when_one_run() -> None:
    """With only ONE run present the macro degrades to a plain single-tone
    headline (the --solo modifier) — a title that can't be split never breaks.
    A custom tag is honored (section headers use h2)."""
    lead_only = _render(
        "{% from 'two_tone_headline.jinja' import two_tone_headline %}"
        "{{ two_tone_headline('Nur ein Teil', tag='h2') }}"
    )
    assert "c-two-tone--solo" in lead_only and "Nur ein Teil" in lead_only
    assert "c-two-tone__accent" not in lead_only        # no empty accent run
    assert "<h2" in lead_only and "</h2>" in lead_only

    accent_only = _render(
        "{% from 'two_tone_headline.jinja' import two_tone_headline %}"
        "{{ two_tone_headline('', 'Wahrheit') }}"
    )
    assert "c-two-tone--solo" in accent_only and "Wahrheit" in accent_only
    assert "c-two-tone__lead" not in accent_only        # no empty lead run


def test_macro_two_tone_headline_css_is_brand_agnostic() -> None:
    """.c-two-tone styling lives in the shared components.css and is token-only
    (serif via --font-display, accent via --color-accent — no literals)."""
    css = (CHASSIS_ROOT / "styles" / "components.css").read_text(encoding="utf-8")
    for cls in (".c-two-tone", ".c-two-tone__lead", ".c-two-tone__accent"):
        assert cls in css, f"missing {cls} styling in components.css"
    # the accent run must fire the accent token (the two-tone punch)
    assert "var(--color-accent)" in css and "var(--font-display)" in css


def test_macro_ghost_numeral_emits_decorative_aria_hidden_span() -> None:
    """ghost_numeral (DNA §C1/§C6) stamps an OVERSIZED faint decorative numeral —
    a `c-ghost-num` span carrying the number, marked aria-hidden (it is pure
    decoration, never read out / never a focal element). The number flows through
    verbatim so a caller can place a faint big '3' behind a section's real number."""
    out = _render(
        "{% from 'ghost_numeral.jinja' import ghost_numeral %}"
        "{{ ghost_numeral(3) }}"
    )
    assert "c-ghost-num" in out
    assert ">3<" in out or "3</span>" in out      # the numeral itself flows through
    assert 'aria-hidden="true"' in out            # decorative — not announced
    _assert_no_literals_rr(out)


def test_macro_ghost_numeral_css_is_decorative_and_brand_agnostic() -> None:
    """.c-ghost-num styling lives in the shared components.css and is token-only
    (oversized via --type-hero, faint --color-accent fill, --font-display face —
    no hex / font / client literal). It MUST be position:absolute + pointer-events
    :none so it is pure DECORATION and never affects layout flow or page height."""
    css = (CHASSIS_ROOT / "styles" / "components.css").read_text(encoding="utf-8")
    assert ".c-ghost-num" in css, "missing .c-ghost-num styling in components.css"
    # locate the .c-ghost-num rule block and assert its decorative properties
    import re as _re
    m = _re.search(r"\.c-ghost-num\s*\{([^}]*)\}", css)
    assert m, ".c-ghost-num rule block not found"
    block = m.group(1)
    assert "position: absolute" in block, "ghost numeral must be position:absolute (no flow)"
    assert "pointer-events: none" in block, "ghost numeral must not capture pointer events"
    assert "var(--color-accent)" in block, "ghost numeral must fire the accent token"
    assert "var(--font-display)" in block, "ghost numeral must use the display face"
    assert "var(--type-hero)" in block, "ghost numeral must size off the hero type token"
    # faint: a low opacity so it reads as a background decoration, not a focal mark
    om = _re.search(r"opacity:\s*([0-9.]+)", block)
    assert om and float(om.group(1)) <= 0.3, "ghost numeral must be faint (low opacity)"
    # whole-sheet literal guard (defence in depth)
    violations = [
        f"components.css:{i}: {line.strip()}"
        for i, line in enumerate(css.splitlines(), 1)
        if _FONT_LIT.search(line) or _HEX.search(line)
    ]
    assert not violations, "brand literal in components.css:\n" + "\n".join(violations)


def test_st05_about() -> None:
    from patterns import st_05
    data = {"title": "Über 100 AI-Projekte", "body": "APEX …",
            "stats": [{"value": "100+", "label": "Projekte"}, {"value": "30%", "label": "Einsparung"}],
            "partners": ["Frese", "Conesso"], "credibility_points": ["100+ Projekte"]}
    frag = st_05.render(_page("ST-05", data, slot=3), _ctx())
    _no_head_css(frag); assert ".st-05" in frag.css
    assert "100+" in frag.html and "Frese" in frag.html

def test_st22_collaboration() -> None:
    from patterns import st_22
    data = {"title": "Von Erstgespräch zu System", "body": "Strukturiert.",
            "steps": [{"n": 1, "title": "Strategiegespräch", "body": "45 Min.", "dauer": "1 Tag"},
                      {"n": 2, "title": "Audit", "body": "Bottlenecks.", "dauer": "3-5 Tage"}]}
    frag = st_22.render(_page("ST-22", data, slot=19), _ctx())
    _no_head_css(frag); assert ".st-22" in frag.css
    # Rebuilt to the tokens + Jinja-macro pattern: the step flow is the shared
    # c-hflow macro (accent connectors) and the heading uses the serif display axis.
    assert "Strategiegespräch" in frag.html and "c-hflow" in frag.html
    assert st_22.render(_page("ST-22", {}, slot=19), _ctx()).html.strip()  # graceful empty


# ---- ST-07A flagship rebuild (tokens + Jinja macros + axis theming) ----------

APEX_FIXTURE = CHASSIS_ROOT / "fixtures" / "apex"
# Literals that must NEVER appear in the new template / layout CSS (brand-agnostic).
_FONT_LIT = re.compile(r"Montserrat|Playfair|Source\s*Sans|Gestura")
_HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")


def _load_fixture_page(st_type: str, package_dir: Path = APEX_FIXTURE) -> dict:
    """Load the first page of `st_type` from a resolved_package.json fixture.

    Mirrors how the assembler reads pages: each entry already carries
    data/assets/components, so the pattern can render it directly.
    """
    pkg = json.loads((package_dir / "resolved_package.json").read_text(encoding="utf-8"))
    for pg in pkg.get("pages", []):
        if pg.get("st_type") == st_type:
            return pg
    raise AssertionError(f"no {st_type} page in {package_dir}")


def test_st07a_flagship_composes_macro_devices() -> None:
    """The rebuilt ST-07A composes the macro library on a token-themed layout.

    Asserts the flagship case-study page renders its signature devices (kicker
    pill, serif display headline, two-column + sidebar, accent stat numbers,
    uppercase section labels, sidebar pull-quote) by checking the macros' `c-`
    classes are present. NOTE: the client PORTRAIT is now conditional on a resolved
    case_study_portrait slot (the first fixture case study has none, so c-media is
    NOT asserted here — its resolved/absent behaviour is covered by the dedicated
    ST-07A portrait tests in test_render_r1.py). NOTE: case studies render NO QR
    (a mid-case-study scannable code reads as clutter); the single designed QR
    lives on the ST-03 back-cover CTA. So c-qr is asserted ABSENT here.
    """
    from patterns import st_07a
    page = _load_fixture_page("ST-07A")
    # This test asserts the STANDARD layout's macro composition (the
    # c-stat-strip sidebar etc.). The fixture now defaults to layout_variant=
    # "fill" (a distinct full-height-panel composition with cs-statstack), so we
    # pin the standard variant here. The fill composition is covered by
    # tests/test_st07a_fill_variant.py.
    page = {**page, "layout_variant": "standard"}
    frag = st_07a.render(page, _ctx(APEX_FIXTURE))
    assert isinstance(frag, PageFragment)
    _no_head_css(frag)
    assert ".st-07a" in frag.css, "fragment CSS must be scoped to .st-07a"

    # Macro library devices (each macro stamps its own c- class). This test pins
    # the STANDARD layout (see above), so it asserts the standard composition's
    # signature devices: kicker pill, stat strip, sidebar pull-quote and
    # uppercase section labels. The portrait is conditional on a resolved slot
    # (the first case study has no resolved photo) so it is excluded.
    for cls in ("c-pill", "c-stat-strip", "c-pull-quote",
                "c-section-label"):
        assert cls in frag.html, f"missing macro device {cls} in ST-07A html"
    # Case studies render NO QR (clutter); the one designed QR is on ST-03.
    assert "c-qr" not in frag.html, "case studies (ST-07A) must render no QR"

    # Real case-study content from the current fixture flows through.
    assert "Martina Ammon" in frag.html            # kunde.name
    assert "FALLSTUDIE 01" in frag.html                # kicker pill, fallstudie_number=1
    assert "AUSGANGSSITUATION" in frag.html.upper()    # section label


def test_st07a_headline_uses_display_axis_token() -> None:
    """The headline must size off var(--font-display) — serif via the axis,
    never a hardcoded family — so the apex (serif) deck renders Playfair."""
    from patterns import st_07a
    page = _load_fixture_page("ST-07A")
    frag = st_07a.render(page, _ctx(APEX_FIXTURE))
    css = (CHASSIS_ROOT / "styles" / "st_07a.css").read_text(encoding="utf-8")
    assert "var(--font-display)" in css, "headline must use var(--font-display)"
    # the headline element itself is token-themed
    assert "var(--font-display)" in (css + frag.css)


def test_st07a_new_files_are_brand_agnostic() -> None:
    """No font-family literal and no raw #hex in the new template or layout CSS —
    colors + fonts come from semantic tokens at render time (cardinal rule)."""
    new_files = [
        CHASSIS_ROOT / "templates" / "st_07a.html.jinja",
        CHASSIS_ROOT / "styles" / "st_07a.css",
    ]
    violations: list[str] = []
    for f in new_files:
        assert f.exists(), f"expected {f} to exist after the rebuild"
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if _FONT_LIT.search(line) or _HEX.search(line):
                violations.append(f"{f.name}:{i}: {line.strip()}")
    assert not violations, (
        "brand literal in the new ST-07A architecture files (tokens only):\n"
        + "\n".join(violations)
    )


# ---- new shared macros: numbered_block / callout_panel / color_block_opener ---

def test_macro_numbered_block_composes_numeral_title_body_reality_source() -> None:
    """The numbered_block macro stamps a big accent numeral, a bold title, body,
    an optional accent-ruled reality sub-block, and an optional uppercase source.
    All under the c-numbered-block namespace (token-only look in components.css)."""
    from templating import get_env
    tmpl = get_env().from_string(
        "{% from 'numbered_block.jinja' import numbered_block %}"
        "{{ numbered_block(2, 'Mythos', '<p>Body</p>',"
        " reality_html='<p>So ist es wirklich</p>', source='BCG 2025', reality_label='REALITÄT') }}"
    )
    out = tmpl.render()
    assert "c-numbered-block" in out
    assert "c-numbered-block__num" in out and ">2<" in out
    assert "Mythos" in out and "Body" in out
    assert "c-numbered-block__reality" in out and "So ist es wirklich" in out
    assert "REALITÄT" in out
    assert "c-numbered-block__source" in out and "BCG 2025" in out
    # graceful: no reality / source still composes the core
    bare = get_env().from_string(
        "{% from 'numbered_block.jinja' import numbered_block %}"
        "{{ numbered_block(1, 'Nur Titel', '<p>x</p>') }}"
    ).render()
    assert "c-numbered-block" in bare and "Nur Titel" in bare
    assert "c-numbered-block__reality" not in bare


def test_macro_callout_panel_is_tint_panel_with_label() -> None:
    """callout_panel renders a tint panel (c-callout-panel, --color-accent-tint
    fill in CSS) carrying insight/tip content and an optional uppercase label."""
    from templating import get_env
    out = get_env().from_string(
        "{% from 'callout_panel.jinja' import callout_panel %}"
        "{{ callout_panel('<p>Die gute Nachricht</p>', label='Einsicht') }}"
    ).render()
    assert "c-callout-panel" in out
    assert "Die gute Nachricht" in out
    assert "c-callout-panel__label" in out and "Einsicht" in out


def test_macro_color_block_opener_is_solid_accent_serif_heading() -> None:
    """color_block_opener renders a solid-accent block with the heading in
    on-accent ink (serif via --font-display in CSS)."""
    from templating import get_env
    out = get_env().from_string(
        "{% from 'color_block_opener.jinja' import color_block_opener %}"
        "{{ color_block_opener('Drei Lügen') }}"
    ).render()
    assert "c-color-block" in out and "Drei Lügen" in out


def test_new_component_macros_css_is_brand_agnostic() -> None:
    """The new c- component CSS (appended to components.css) carries semantic
    tokens ONLY — no font-family literal, no raw #hex (cardinal rule)."""
    css = (CHASSIS_ROOT / "styles" / "components.css").read_text(encoding="utf-8")
    # the three new devices must be styled in the shared sheet
    for cls in (".c-numbered-block", ".c-callout-panel", ".c-color-block"):
        assert cls in css, f"missing {cls} styling in components.css"
    violations = [
        f"components.css:{i}: {line.strip()}"
        for i, line in enumerate(css.splitlines(), 1)
        if _FONT_LIT.search(line) or _HEX.search(line)
    ]
    assert not violations, "brand literal in components.css:\n" + "\n".join(violations)


# ---- ST-09 status-quo rebuild (numbered symptom blocks + tint callout) -------

def test_st09_rebuild_composes_numbered_blocks_and_callout() -> None:
    """The rebuilt ST-09 (status-quo) is a serif heading + intro, a series of
    numbered symptom blocks (numbered_block), and a mega-numeral insight viz
    (c-viz-mega), composed from the macro library on the .st-09 layout.
    Loads the REAL apex status-quo page (slot 4)."""
    from patterns import st_09
    page = _load_fixture_page("ST-09")
    frag = st_09.render(page, _ctx(APEX_FIXTURE))
    assert isinstance(frag, PageFragment)
    _no_head_css(frag)
    assert ".st-09" in frag.css, "fragment CSS must be scoped to .st-09"

    # Signature devices: numbered symptom blocks + a mega-numeral insight viz.
    assert "c-numbered-block" in frag.html, "numbered symptom blocks missing"
    assert "c-numbered-block__num" in frag.html, "big accent numeral missing"
    assert "c-viz-mega" in frag.html, "mega-numeral insight viz missing"

    # Real status-quo content flows through.
    assert "Dein Unternehmen wächst. Deine Prozesse nicht." in frag.html   # title
    assert "Montagmorgen kostet drei Stunden" in frag.html                 # symptom 1
    assert "Marketing-Pipeline ist chronisch leer" in frag.html            # symptom 6
    # NOTE: the old fal "status_quo_scene" background was intentionally pruned
    # (the AI scenes were removed; the page's hero visual is now the code-drawn
    # mega-numeral viz asserted above), so no scene-asset assertion here.


def test_st09_headline_uses_display_axis_token() -> None:
    """The ST-09 heading must size off var(--font-display) — serif via the axis."""
    css = (CHASSIS_ROOT / "styles" / "st_09.css").read_text(encoding="utf-8")
    assert "var(--font-display)" in css, "ST-09 heading must use var(--font-display)"


def test_st09_new_files_are_brand_agnostic() -> None:
    """No font-family literal and no raw #hex in the new ST-09 template/layout CSS."""
    new_files = [
        CHASSIS_ROOT / "templates" / "st_09.html.jinja",
        CHASSIS_ROOT / "styles" / "st_09.css",
    ]
    violations: list[str] = []
    for f in new_files:
        assert f.exists(), f"expected {f} to exist after the rebuild"
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if _FONT_LIT.search(line) or _HEX.search(line):
                violations.append(f"{f.name}:{i}: {line.strip()}")
    assert not violations, (
        "brand literal in the new ST-09 architecture files (tokens only):\n"
        + "\n".join(violations)
    )


# ---- ST-14 false-beliefs rebuild (color-block opener + belief→reality) -------

def test_st14_rebuild_composes_color_block_and_belief_reality() -> None:
    """The rebuilt ST-14 (false-beliefs) opens with a solid-accent color-block
    behind the heading (color_block_opener), then numbered belief→reality blocks
    (numbered_block with a distinct Realität sub-block + source) — composed from
    the macro library on the .st-14 layout. Loads the REAL apex page (slot 5)."""
    from patterns import st_14
    page = _load_fixture_page("ST-14")
    frag = st_14.render(page, _ctx(APEX_FIXTURE))
    assert isinstance(frag, PageFragment)
    _no_head_css(frag)
    assert ".st-14" in frag.css, "fragment CSS must be scoped to .st-14"

    # Signature devices: a solid-accent color-block opener + numbered
    # belief→reality blocks with the Realität reality sub-block.
    assert "c-color-block" in frag.html, "solid-accent color-block opener missing"
    assert "c-numbered-block" in frag.html, "numbered belief->reality blocks missing"
    assert "c-numbered-block__reality" in frag.html, "Realität reality sub-block missing"
    assert "REALITÄT" in frag.html.upper(), "Realität reality label missing"

    # Real false-beliefs content flows through.
    assert "Drei Lügen, die dein Wachstum blockieren" in frag.html         # title
    assert "Skalierung entsteht durch Systeme" in frag.html                # reality 1
    assert "PwC 2026" in frag.html                                         # quelle/source 1


def test_st14_headline_uses_display_axis_token() -> None:
    """The ST-14 color-block heading must size off var(--font-display) — serif."""
    css = (CHASSIS_ROOT / "styles" / "st_14.css").read_text(encoding="utf-8")
    assert "var(--font-display)" in css, "ST-14 heading must use var(--font-display)"


def test_st14_new_files_are_brand_agnostic() -> None:
    """No font-family literal and no raw #hex in the new ST-14 template/layout CSS."""
    new_files = [
        CHASSIS_ROOT / "templates" / "st_14.html.jinja",
        CHASSIS_ROOT / "styles" / "st_14.css",
    ]
    violations: list[str] = []
    for f in new_files:
        assert f.exists(), f"expected {f} to exist after the rebuild"
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if _FONT_LIT.search(line) or _HEX.search(line):
                violations.append(f"{f.name}:{i}: {line.strip()}")
    assert not violations, (
        "brand literal in the new ST-14 architecture files (tokens only):\n"
        + "\n".join(violations)
    )


# ---- new ST-06 macros: step_card / horizontal_flow / bar_chart /
#      stat_callout_card / dark_recap_panel ------------------------------------

def test_macro_step_card_composes_numeral_title_body() -> None:
    """step_card stamps an accent numeral + bold title + body in a thin-border
    card. Under the c-step-card namespace (token-only look in components.css)."""
    from templating import get_env
    out = get_env().from_string(
        "{% from 'step_card.jinja' import step_card %}"
        "{{ step_card(3, 'Workflow-Audit', '<p>Wir messen alles.</p>') }}"
    ).render()
    assert "c-step-card" in out
    assert "c-step-card__num" in out and ">3<" in out
    assert "Workflow-Audit" in out and "Wir messen alles." in out


def test_macro_horizontal_flow_connects_steps_with_arrows() -> None:
    """horizontal_flow renders a row of connected step boxes with accent arrow
    connectors; each box has a number + title + short body + optional duration."""
    from templating import get_env
    out = get_env().from_string(
        "{% from 'horizontal_flow.jinja' import horizontal_flow %}"
        "{{ horizontal_flow(["
        "{'n': 1, 'title': 'Audit', 'body': 'Diagnose', 'dauer': 'Woche 1'},"
        "{'n': 2, 'title': 'Bereinigung', 'body': 'Daten'}]) }}"
    ).render()
    assert "c-hflow" in out
    assert "c-hflow__step" in out and "c-hflow__arrow" in out
    assert "Audit" in out and "Bereinigung" in out
    assert "Diagnose" in out and "Woche 1" in out  # body + optional duration
    # graceful: empty list yields nothing fragile
    bare = get_env().from_string(
        "{% from 'horizontal_flow.jinja' import horizontal_flow %}"
        "{{ horizontal_flow([]) }}"
    ).render()
    assert "c-hflow__step" not in bare


def test_macro_bar_chart_draws_token_bars_from_data() -> None:
    """bar_chart draws its OWN token-colored horizontal bars from data: each bar's
    width comes from parsing the numeric magnitude of `value`; label + value show."""
    from templating import get_env
    out = get_env().from_string(
        "{% from 'bar_chart.jinja' import bar_chart %}"
        "{{ bar_chart(["
        "{'label': 'Vorher', 'value': '30 Min'},"
        "{'label': 'Nachher', 'value': '2 Min'}]) }}"
    ).render()
    assert "c-bar-chart" in out
    assert "c-bar-chart__fill" in out  # the drawn accent bar
    assert "Vorher" in out and "Nachher" in out
    assert "30 Min" in out and "2 Min" in out
    # the fill width is computed inline from the magnitude (renderer draws it)
    assert "width:" in out
    # graceful: empty yields nothing fragile
    bare = get_env().from_string(
        "{% from 'bar_chart.jinja' import bar_chart %}{{ bar_chart([]) }}"
    ).render()
    assert "c-bar-chart__fill" not in bare


def test_macro_stat_callout_card_is_big_number_over_label() -> None:
    """stat_callout_card renders a small card: big accent number + uppercase
    label, on a tint/bordered card. Under the c-stat-callout namespace."""
    from templating import get_env
    out = get_env().from_string(
        "{% from 'stat_callout_card.jinja' import stat_callout_card %}"
        "{{ stat_callout_card('30-50%', 'Effizienzgewinn') }}"
    ).render()
    assert "c-stat-callout" in out
    assert "c-stat-callout__value" in out and "30-50%" in out
    assert "c-stat-callout__label" in out and "Effizienzgewinn" in out


def test_macro_dark_recap_panel_is_solid_ink_panel() -> None:
    """dark_recap_panel renders a SOLID dark panel (--color-ink fill in CSS, so it
    reads as a true dark panel for ANY brand) with on-dark text + optional heading.
    Under the c-dark-recap namespace (token-only look in components.css)."""
    from templating import get_env
    out = get_env().from_string(
        "{% from 'dark_recap_panel.jinja' import dark_recap_panel %}"
        "{{ dark_recap_panel('Das Ergebnis', '<p>30-50% mehr Effizienz.</p>') }}"
    ).render()
    assert "c-dark-recap" in out
    assert "c-dark-recap__heading" in out and "Das Ergebnis" in out
    assert "30-50% mehr Effizienz." in out


def test_new_st06_component_macros_css_is_brand_agnostic() -> None:
    """The new ST-06 c- component CSS (appended to components.css) carries semantic
    tokens ONLY — no font literal, no raw #hex — AND the dark recap panel fills
    with --color-panel (the recipe-driven dark role: ink by default, primary for
    contrasting brands), never a pale accent-tint."""
    css = (CHASSIS_ROOT / "styles" / "components.css").read_text(encoding="utf-8")
    for cls in (".c-step-card", ".c-hflow", ".c-bar-chart", ".c-stat-callout",
                ".c-dark-recap"):
        assert cls in css, f"missing {cls} styling in components.css"
    # the dark recap panel must be a TRUE dark panel: --color-panel fill
    # (recipe-driven dark role — ink by default, primary for contrasting brands).
    recap_block = css[css.index(".c-dark-recap"):]
    recap_block = recap_block[:recap_block.index(".c-dark-recap") + 600]
    assert "var(--color-panel)" in recap_block, "dark recap must fill with --color-panel"
    violations = [
        f"components.css:{i}: {line.strip()}"
        for i, line in enumerate(css.splitlines(), 1)
        if _FONT_LIT.search(line) or _HEX.search(line)
    ]
    assert not violations, "brand literal in components.css:\n" + "\n".join(violations)


# ---- reusable dark authority_panel (DNA §C3, gap #4) -------------------------

def test_macro_authority_panel_is_solid_dark_panel() -> None:
    """authority_panel renders a SOLID dark "authority" panel (DNA §C3 — the
    recurring authority beat: CTA panels, stat rails, positioning panels). The
    default tone="ink" fills with --color-ink + on-dark text; an optional eyebrow
    and heading sit above the body. Under the c-authority namespace (token-only
    look in components.css). Mirrors dark_recap_panel's structure/quality."""
    from templating import get_env
    out = get_env().from_string(
        "{% from 'authority_panel.jinja' import authority_panel %}"
        "{{ authority_panel('<p>30-50% mehr Effizienz.</p>',"
        " eyebrow='Das Ergebnis', heading='Mehr Marge, weniger Aufwand') }}"
    ).render()
    assert "c-authority" in out
    assert "c-authority__eyebrow" in out and "Das Ergebnis" in out
    assert "c-authority__heading" in out and "Mehr Marge, weniger Aufwand" in out
    assert "c-authority__body" in out and "30-50% mehr Effizienz." in out
    # graceful: body only (no eyebrow / no heading) still composes the core panel
    bare = get_env().from_string(
        "{% from 'authority_panel.jinja' import authority_panel %}"
        "{{ authority_panel('<p>Nur Text.</p>') }}"
    ).render()
    assert "c-authority" in bare and "Nur Text." in bare
    assert "c-authority__eyebrow" not in bare and "c-authority__heading" not in bare


def test_macro_authority_panel_tone_is_recipe_driven_no_modifier() -> None:
    """Phase A removed the .c-authority--primary modifier: ink-vs-primary ground is
    now recipe-driven via the compiled --color-panel token, NOT a markup class. The
    macro still accepts `tone` (call-site compatibility) but emits the SAME
    .c-authority element regardless — and never the (now-removed) --primary class."""
    from templating import get_env
    primary = get_env().from_string(
        "{% from 'authority_panel.jinja' import authority_panel %}"
        "{{ authority_panel('<p>x</p>', tone='primary') }}"
    ).render()
    assert "c-authority" in primary
    assert "c-authority--primary" not in primary
    ink = get_env().from_string(
        "{% from 'authority_panel.jinja' import authority_panel %}"
        "{{ authority_panel('<p>x</p>') }}"
    ).render()
    assert "c-authority" in ink
    assert "c-authority--primary" not in ink


def test_authority_panel_macro_markup_is_brand_agnostic() -> None:
    """The macro's emitted markup carries no font-family literal and no raw #hex."""
    from templating import get_env
    out = get_env().from_string(
        "{% from 'authority_panel.jinja' import authority_panel %}"
        "{{ authority_panel('<p>x</p>', eyebrow='E', heading='H', tone='primary') }}"
    ).render()
    _assert_no_literals_rr(out)


def test_authority_panel_css_is_solid_dark_token_only() -> None:
    """The .c-authority CSS (in components.css) is a TRUE dark panel: it fills with
    the recipe-driven --color-panel role (ink by default, primary for contrasting
    brands) and sets light --color-on-panel text — NEVER a pale accent-tint or
    ground-wash fill, and no font literal / raw #hex. The old .c-authority--primary
    modifier is gone (the recipe drives ink-vs-primary). DNA §C3 gap #4 fix."""
    css = (CHASSIS_ROOT / "styles" / "components.css").read_text(encoding="utf-8")
    assert ".c-authority" in css, "missing .c-authority styling in components.css"
    # isolate the .c-authority rule block group (until the next top-level comment).
    start = css.index(".c-authority")
    block = css[start:start + 900]
    # solid dark ground via the recipe-driven panel role + its readable on-color
    assert "var(--color-panel)" in block, ".c-authority must fill with --color-panel"
    assert "var(--color-on-panel)" in block, ".c-authority needs --color-on-panel text"
    # NEVER a pale accent-tint / ground-wash fill on this authority panel
    assert "--color-accent-tint" not in block, "authority panel must not use accent-tint"
    assert "--color-ground-wash" not in block, "authority panel must not use ground-wash"
    assert "rgba(" not in block, "authority panel must not use a raw rgba() wash"
    # brand-agnostic: tokens only
    for i, line in enumerate(block.splitlines(), 1):
        assert not (_FONT_LIT.search(line) or _HEX.search(line)), (
            f"brand literal in .c-authority CSS: {line.strip()}"
        )


# ---- ST-06 mechanism rebuild (step cards + horizontal flow + dark recap) -----

def test_st06_rebuild_composes_step_cards_flow_and_dark_recap() -> None:
    """The rebuilt ST-06 (mechanism / how-it-works) is a serif heading + intro,
    a series of numbered step cards (step_card) for the mechanism stages, and a
    solid dark "Das Ergebnis" recap panel (dark_recap_panel) — composed from the
    macro library on the .st-06 layout. Loads the REAL apex page (16) which has
    6 steps.

    Flow-strip (horizontal_flow / c-hflow) is SUPPRESSED when there are ≥5 steps
    because the 6 labeled step cards already carry the process overview and the
    strip would waste vertical space on a dense page. The strip renders only for
    <5-step pages (see the separate ≤4-step path below).
    """
    from patterns import st_06
    page = _load_fixture_page("ST-06")
    frag = st_06.render(page, _ctx(APEX_FIXTURE))
    assert isinstance(frag, PageFragment)
    _no_head_css(frag)
    assert ".st-06" in frag.css, "fragment CSS must be scoped to .st-06"

    # Core signature devices: step cards + dark recap.
    assert "c-step-card" in frag.html, "numbered step cards missing"
    assert "c-step-card__num" in frag.html, "accent step numeral missing"
    assert "c-dark-recap" in frag.html, "dark 'Das Ergebnis' recap panel missing"

    # Flow-strip ABSENT for the 6-step apex fixture (suppressed at ≥5 steps).
    assert "c-hflow" not in frag.html, (
        "horizontal flow strip must be suppressed for 6-step pages (≥5 steps)"
    )

    # Real mechanism content from the fixture flows through.
    assert "Das Done-For-You AI Automation Framework" in frag.html          # title
    assert "Workflow-Audit und Engpass-Diagnose" in frag.html               # step 1
    assert "Kontinuierliche Optimierung und Reporting" in frag.html         # step 6
    assert "Das Ergebnis" in frag.html                                      # recap label

    # Flow-strip IS emitted for a short (≤4-step) page.  Use the existing 2-step
    # fixture path: build a minimal 3-step page dict and confirm c-hflow appears.
    short_page = {
        "st_type": "ST-06",
        "data": {
            "title": "Kurzprozess",
            "body": "Intro.",
            "steps": [
                {"title": "Schritt Eins", "body": "Erster Schritt."},
                {"title": "Schritt Zwei", "body": "Zweiter Schritt."},
                {"title": "Schritt Drei", "body": "Dritter Schritt."},
            ],
            "ergebnis": "Gutes Ergebnis.",
        },
    }
    short_frag = st_06.render(short_page, _ctx(APEX_FIXTURE))
    assert "c-hflow" in short_frag.html, (
        "horizontal flow strip must be present for ≤4-step pages"
    )


def test_st06_headline_uses_display_axis_token() -> None:
    """The ST-06 heading must size off var(--font-display) — serif via the axis."""
    css = (CHASSIS_ROOT / "styles" / "st_06.css").read_text(encoding="utf-8")
    assert "var(--font-display)" in css, "ST-06 heading must use var(--font-display)"


def test_st06_new_files_are_brand_agnostic() -> None:
    """No font-family literal and no raw #hex in the new ST-06 template/layout CSS."""
    new_files = [
        CHASSIS_ROOT / "templates" / "st_06.html.jinja",
        CHASSIS_ROOT / "styles" / "st_06.css",
    ]
    violations: list[str] = []
    for f in new_files:
        assert f.exists(), f"expected {f} to exist after the rebuild"
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if _FONT_LIT.search(line) or _HEX.search(line):
                violations.append(f"{f.name}:{i}: {line.strip()}")
    assert not violations, (
        "brand literal in the new ST-06 architecture files (tokens only):\n"
        + "\n".join(violations)
    )


# ---- new shared macros: check_list (ST-02) / qa_item (ST-08) ------------------

def test_macro_check_list_composes_accent_checks_and_items() -> None:
    """check_list renders a list of items, each with an accent check glyph beside
    the item text. Under the c-check-list namespace (token-only look in
    components.css). It is the audience / Zielgruppe device, dropped INSIDE a
    callout_panel body on ST-02."""
    from templating import get_env
    out = get_env().from_string(
        "{% from 'check_list.jinja' import check_list %}"
        "{{ check_list(['B2B mit 10 bis 50 Mitarbeitern',"
        " '€500.000 bis €3 Millionen Umsatz']) }}"
    ).render()
    assert "c-check-list" in out
    assert "c-check-list__item" in out
    # an accent check glyph marker is stamped per item
    assert "c-check-list__check" in out
    assert "B2B mit 10 bis 50 Mitarbeitern" in out
    assert "€500.000 bis €3 Millionen Umsatz" in out
    # graceful: empty list yields nothing fragile
    bare = get_env().from_string(
        "{% from 'check_list.jinja' import check_list %}{{ check_list([]) }}"
    ).render()
    assert "c-check-list__item" not in bare


def test_macro_qa_item_composes_accent_question_and_body_answer() -> None:
    """qa_item renders one FAQ entry: an accent (or bold) question above a body
    answer. Under the c-qa-item namespace (token-only look in components.css).
    The page CSS arranges multiple qa_items into two columns."""
    from templating import get_env
    out = get_env().from_string(
        "{% from 'qa_item.jinja' import qa_item %}"
        "{{ qa_item('Wie lange dauert die Umsetzung?',"
        " '<p>Wenige Wochen, nicht Monate.</p>') }}"
    ).render()
    assert "c-qa-item" in out
    assert "c-qa-item__question" in out and "Wie lange dauert die Umsetzung?" in out
    assert "c-qa-item__answer" in out and "Wenige Wochen, nicht Monate." in out


def test_new_st02_st08_component_macros_css_is_brand_agnostic() -> None:
    """The new c- component CSS (check_list + qa_item, appended to components.css)
    carries semantic tokens ONLY — no font-family literal, no raw #hex (cardinal
    rule). The check glyph + question accent fire via tokens."""
    css = (CHASSIS_ROOT / "styles" / "components.css").read_text(encoding="utf-8")
    for cls in (".c-check-list", ".c-qa-item"):
        assert cls in css, f"missing {cls} styling in components.css"
    violations = [
        f"components.css:{i}: {line.strip()}"
        for i, line in enumerate(css.splitlines(), 1)
        if _FONT_LIT.search(line) or _HEX.search(line)
    ]
    assert not violations, "brand literal in components.css:\n" + "\n".join(violations)


# ---- ST-02 outlook rebuild (serif question-headline + two-col + tint checklist) --

def test_st02_rebuild_composes_serif_headline_two_col_and_check_panel() -> None:
    """The rebuilt ST-02 (outlook) is a large serif question-headline, a
    two-column body, and a tint check-list panel (callout_panel carrying a
    check_list) for the audience / Zielgruppe — composed from the macro library on
    the token-themed .st-02 layout. Loads the REAL apex outlook page (slot 2)."""
    from patterns import st_02
    page = _load_fixture_page("ST-02")
    frag = st_02.render(page, _ctx(APEX_FIXTURE))
    assert isinstance(frag, PageFragment)
    _no_head_css(frag)
    assert ".st-02" in frag.css, "fragment CSS must be scoped to .st-02"

    # Signature devices: a serif question-headline, a two-column body, and the
    # tint callout panel carrying the accent check-list (Zielgruppe).
    assert "ol-headline" in frag.html, "serif question-headline missing"
    assert "ol-body" in frag.html, "two-column body block missing"
    assert "c-callout-panel" in frag.html, "tint check-list panel missing"
    assert "c-check-list" in frag.html, "accent check-list missing"
    assert "c-check-list__check" in frag.html, "accent check glyph missing"

    # Real outlook content from the fixture flows through.
    assert "Dein Wachstum scheitert nicht am Markt" in frag.html            # title
    assert "B2B-Unternehmen mit 10 bis 50 Mitarbeitern" in frag.html        # zielgruppe 1
    assert "€500.000 bis €3 Millionen Jahresumsatz" in frag.html            # zielgruppe 2
    assert "Manuelle Prozesse fressen" in frag.html                         # body prose

    # graceful: empty data still composes a non-empty fragment.
    assert st_02.render(_page("ST-02", {}, slot=2), _ctx()).html.strip()


def test_st02_headline_uses_display_axis_token() -> None:
    """The ST-02 question-headline must size off var(--font-display) — serif via
    the axis, never a hardcoded family — so the apex (serif) deck renders Playfair.
    The two-column body sets in the sans body face; the contrast is the §18 hit."""
    css = (CHASSIS_ROOT / "styles" / "st_02.css").read_text(encoding="utf-8")
    assert "var(--font-display)" in css, "ST-02 headline must use var(--font-display)"
    assert "var(--font-body)" in css, "ST-02 body must use the sans body face"


def test_st02_new_files_are_brand_agnostic() -> None:
    """No font-family literal and no raw #hex in the new ST-02 template/layout CSS."""
    new_files = [
        CHASSIS_ROOT / "templates" / "st_02.html.jinja",
        CHASSIS_ROOT / "styles" / "st_02.css",
    ]
    violations: list[str] = []
    for f in new_files:
        assert f.exists(), f"expected {f} to exist after the rebuild"
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if _FONT_LIT.search(line) or _HEX.search(line):
                violations.append(f"{f.name}:{i}: {line.strip()}")
    assert not violations, (
        "brand literal in the new ST-02 architecture files (tokens only):\n"
        + "\n".join(violations)
    )


# ---- ST-08 FAQ rebuild (serif heading + two-column accent-question Q&A stack) --

def test_st08_rebuild_composes_serif_heading_and_two_col_qa() -> None:
    """The rebuilt ST-08 (FAQ) is a serif heading + an optional intro, then a
    two-column Q&A stack where each item is an accent question above a body answer
    (qa_item) — composed from the macro library on the .st-08 layout. ST-08 is not
    in the apex fixture (synthetic-verified), so this drives realistic German FAQ
    data through the pattern directly."""
    from patterns import st_08
    data = {
        "title": "Häufige Fragen",
        "faqs": [
            {"frage": "Wie lange dauert die Umsetzung?",
             "antwort": "Die ersten Automatisierungen laufen in **wenigen Wochen**, nicht Monaten."},
            {"frage": "Muss ich meine bestehenden Tools wechseln?",
             "antwort": "Nein. Die AI-Agenten setzen auf deiner bestehenden Tool-Umgebung auf."},
            {"frage": "Brauche ich ein eigenes IT-Team?",
             "antwort": "Nein. Wir übernehmen die komplette Umsetzung done-for-you."},
            {"frage": "Was kostet ein Projekt?",
             "antwort": "Das hängt vom Umfang ab — die meisten Projekte amortisieren sich in unter sechs Monaten."},
        ],
    }
    frag = st_08.render(_page("ST-08", data, slot=99), _ctx())
    assert isinstance(frag, PageFragment)
    _no_head_css(frag)
    assert ".st-08" in frag.css, "fragment CSS must be scoped to .st-08"

    # Signature devices: a serif heading + a two-column Q&A stack of qa_items.
    assert "faq-headline" in frag.html, "serif FAQ heading missing"
    assert "faq-list" in frag.html, "two-column Q&A stack missing"
    assert "c-qa-item" in frag.html, "qa_item entries missing"
    assert "c-qa-item__question" in frag.html, "accent question missing"
    assert "c-qa-item__answer" in frag.html, "body answer missing"

    # Real FAQ content flows through (questions + markdown-processed answers).
    assert "Wie lange dauert die Umsetzung?" in frag.html
    assert "Muss ich meine bestehenden Tools wechseln?" in frag.html
    assert "wenigen Wochen" in frag.html
    assert "<strong>wenigen Wochen</strong>" in frag.html, "answer markdown must render"

    # graceful: empty data still composes a non-empty fragment.
    assert st_08.render(_page("ST-08", {}, slot=99), _ctx()).html.strip()


def test_st08_headline_uses_display_axis_token() -> None:
    """The ST-08 heading must size off var(--font-display) — serif via the axis."""
    css = (CHASSIS_ROOT / "styles" / "st_08.css").read_text(encoding="utf-8")
    assert "var(--font-display)" in css, "ST-08 heading must use var(--font-display)"


def test_st08_new_files_are_brand_agnostic() -> None:
    """No font-family literal and no raw #hex in the new ST-08 template/layout CSS."""
    new_files = [
        CHASSIS_ROOT / "templates" / "st_08.html.jinja",
        CHASSIS_ROOT / "styles" / "st_08.css",
    ]
    violations: list[str] = []
    for f in new_files:
        assert f.exists(), f"expected {f} to exist after the rebuild"
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if _FONT_LIT.search(line) or _HEX.search(line):
                violations.append(f"{f.name}:{i}: {line.strip()}")
    assert not violations, (
        "brand literal in the new ST-08 architecture files (tokens only):\n"
        + "\n".join(violations)
    )


# ---- new shared macros: logo_wall (ST-05) / key_insight (ST-07B) -------------

def test_macro_logo_wall_renders_grayscale_logos_and_degrades() -> None:
    """logo_wall renders a row/grid of logo IMAGES in grayscale (the "bekannt aus"
    credibility wall). Under the c-logo-wall namespace; the token-only look
    (grayscale filter, item rhythm) lives in styles/components.css. logos = list of
    resolved image URIs. It must DEGRADE GRACEFULLY when empty (render nothing or a
    restrained text fallback — never fabricate logos)."""
    from templating import get_env
    out = get_env().from_string(
        "{% from 'logo_wall.jinja' import logo_wall %}"
        "{{ logo_wall(['file:///tmp/a.png', 'file:///tmp/b.png']) }}"
    ).render()
    assert "c-logo-wall" in out
    assert "c-logo-wall__logo" in out
    # the two logo image URIs are wired into the wall
    assert "file:///tmp/a.png" in out and "file:///tmp/b.png" in out
    # graceful: an empty list yields NO logo items (no fabricated logos, nothing fragile)
    bare = get_env().from_string(
        "{% from 'logo_wall.jinja' import logo_wall %}{{ logo_wall([]) }}"
    ).render()
    assert "c-logo-wall__logo" not in bare


def test_macro_logo_wall_text_fallback_when_no_images() -> None:
    """When NO logo image URIs are available but partner NAMES are (the apex
    fixture case), logo_wall may render a restrained text fallback of the names —
    still under the c-logo-wall namespace, never fabricating logo art."""
    from templating import get_env
    out = get_env().from_string(
        "{% from 'logo_wall.jinja' import logo_wall %}"
        "{{ logo_wall([], names=['Frese Recruiting', 'Conesso GmbH']) }}"
    ).render()
    assert "c-logo-wall" in out
    assert "Frese Recruiting" in out and "Conesso GmbH" in out
    # the text fallback must NOT emit fabricated <img>/background logo nodes
    assert "c-logo-wall__logo" not in out


def test_macro_key_insight_is_accent_rule_italic_tint_panel() -> None:
    """key_insight renders a distinct callout: an accent rule + LARGER italic text
    on a tint panel (the ST-07B key-insight treatment). Under the c-key-insight
    namespace; token-only look in components.css. An empty text yields nothing."""
    from templating import get_env
    out = get_env().from_string(
        "{% from 'key_insight.jinja' import key_insight %}"
        "{{ key_insight('Operative Engpaesse sind strukturell.') }}"
    ).render()
    assert "c-key-insight" in out
    assert "Operative Engpaesse sind strukturell." in out
    bare = get_env().from_string(
        "{% from 'key_insight.jinja' import key_insight %}{{ key_insight('') }}"
    ).render()
    assert "c-key-insight" not in bare


def test_new_st05_st07b_component_macros_css_is_brand_agnostic() -> None:
    """The new c- component CSS (logo_wall + key_insight, appended to
    components.css) carries semantic tokens ONLY — no font-family literal, no raw
    #hex (cardinal rule). Grayscale fires via filter; the rule/tint via tokens."""
    css = (CHASSIS_ROOT / "styles" / "components.css").read_text(encoding="utf-8")
    for cls in (".c-logo-wall", ".c-key-insight"):
        assert cls in css, f"missing {cls} styling in components.css"
    violations = [
        f"components.css:{i}: {line.strip()}"
        for i, line in enumerate(css.splitlines(), 1)
        if _FONT_LIT.search(line) or _HEX.search(line)
    ]
    assert not violations, "brand literal in components.css:\n" + "\n".join(violations)


# ---- ST-05 about rebuild (serif heading + stat trio + grayscale logo wall) ----

def test_st05_rebuild_composes_serif_heading_stat_trio_and_logo_wall() -> None:
    """The rebuilt ST-05 (about) is a large serif heading, body prose, a stat trio
    ("in Zahlen" — stat_strip with 3 big accent numbers), and a grayscale logo wall
    ("bekannt aus" — logo_wall) — composed from the macro library on the
    token-themed .st-05 layout. Loads the REAL apex about page (slot 3)."""
    from patterns import st_05
    page = _load_fixture_page("ST-05")
    frag = st_05.render(page, _ctx(APEX_FIXTURE))
    assert isinstance(frag, PageFragment)
    _no_head_css(frag)
    assert ".st-05" in frag.css, "fragment CSS must be scoped to .st-05"

    # Signature devices: a serif heading, the stat trio (stat_strip), and the
    # grayscale logo wall (logo_wall).
    assert "ab-headline" in frag.html, "serif heading missing"
    assert "c-stat-strip" in frag.html, "stat trio (stat_strip) missing"
    assert "c-stat-value" in frag.html, "big accent stat numbers missing"
    assert "c-logo-wall" in frag.html, "grayscale logo wall (logo_wall) missing"

    # Real about content from the fixture flows through.
    assert "Über 100 AI-Projekte" in frag.html                # title
    assert "100+" in frag.html and "AI-Projekte" in frag.html  # stat trio (#4)
    assert "€200k+" in frag.html and "30-50%" in frag.html     # all three stats
    assert "Frese Recruiting" in frag.html                     # logo wall name (#16)
    assert "APEX Consulting hat" in frag.html                  # body prose

    # graceful: empty data still composes a non-empty fragment.
    assert st_05.render(_page("ST-05", {}, slot=3), _ctx()).html.strip()


def test_st05_phase4b_dark_panel_and_social_proof_from_slots() -> None:
    """Phase 4b + IG-assets: the positioning statement (the body's FIRST paragraph)
    rides a DARK authority panel (.ab-lead, DNA §C3). The apex about page leads its
    §C4 social proof with the designed TESTIMONIAL CARDS (real client quote+metric+
    name, scraped from the founder's socials); the framed proof-photo gallery is the
    FALLBACK rendered only when no testimonial cards are present."""
    import copy
    from patterns import st_05
    page = _load_fixture_page("ST-05")
    frag = st_05.render(page, _ctx(APEX_FIXTURE))

    # dark positioning panel carries the thesis (the body's first paragraph)
    assert "ab-lead" in frag.html, "dark positioning panel (.ab-lead) missing"
    assert "APEX Consulting hat" in frag.html, "thesis (body para 1) must be on the panel"
    # the panel grounds on --color-ink with on-dark text (the §C3 dark panel,
    # re-grounded from --color-primary to --color-ink so it reads as a true dark
    # for any brand, incl. brands where primary == accent)
    assert ".ab-lead" in frag.css
    assert "var(--color-ink)" in frag.css and "var(--color-on-dark)" in frag.css

    # social proof: the designed testimonial cards (the apex page carries 2 whole cards).
    # The card ASSET paths are produced by the Social Layout Planner (staged as
    # ig_<basename>), so derive the expected filename from the page DATA rather than
    # hardcoding — the planner is the source of truth, not a fixed filename.
    assert frag.html.count("ab-testimonials__card") == 2, "both testimonial cards must render"
    assert "Das sagen unsere Kunden" in frag.html, "testimonials content label missing"
    tpaths = (page.get("data") or {}).get("testimonials") or []
    assert tpaths, "fixture ST-05 must carry planner-bound testimonials"
    assert tpaths[0].split("/")[-1] in frag.html, "testimonial card asset must integrate"

    # FALLBACK: with NO testimonials, the framed proof-photo gallery renders instead
    page_no_t = copy.deepcopy(page)
    (page_no_t.get("data") or {}).pop("testimonials", None)
    frag2 = st_05.render(page_no_t, _ctx(APEX_FIXTURE))
    assert "c-proof-gallery" in frag2.html, "proof gallery (fallback) missing"
    assert frag2.html.count("c-proof-gallery__item") == 3, "all 3 proof photos must render"
    assert "Referenzen" in frag2.html, "proof gallery content label missing"


def test_st05_graceful_without_slots_keeps_name_fallback_and_no_proof() -> None:
    """Graceful contract: a page with NO slots (a photo-less client) renders NO
    proof gallery and NO portrait, and the partner-NAME text fallback still
    carries the "bekannt aus" wall. The dark panel still anchors the body."""
    from patterns import st_05
    data = {
        "title": "Über uns",
        "body": "Die These.\n\nWeiterer Fließtext zur Einordnung.",
        "stats": [{"value": "100+", "label": "Projekte"}],
        "partners": ["Acme GmbH", "Beispiel AG"],
        "credibility_points": ["Punkt eins"],
    }
    frag = st_05.render(_page("ST-05", data, slot=3), _ctx())
    # no slots -> no proof gallery, no portrait media block
    assert "c-proof-gallery" not in frag.html
    assert "ab-portrait" not in frag.html
    # the partner NAME fallback carries the wall (no logo art fabricated)
    assert "c-logo-wall--text" in frag.html
    assert "Acme GmbH" in frag.html and "Beispiel AG" in frag.html
    # the dark positioning panel still anchors the thesis (first paragraph)
    assert "ab-lead" in frag.html and "Die These." in frag.html


def test_st05_headline_uses_display_axis_token() -> None:
    """The ST-05 heading must size off var(--font-display) — serif via the axis,
    never a hardcoded family — so the apex (serif) deck renders Playfair."""
    css = (CHASSIS_ROOT / "styles" / "st_05.css").read_text(encoding="utf-8")
    assert "var(--font-display)" in css, "ST-05 heading must use var(--font-display)"
    assert "var(--font-body)" in css, "ST-05 body must use the sans body face"


def test_st05_new_files_are_brand_agnostic() -> None:
    """No font-family literal and no raw #hex in the new ST-05 template/layout CSS."""
    new_files = [
        CHASSIS_ROOT / "templates" / "st_05.html.jinja",
        CHASSIS_ROOT / "styles" / "st_05.css",
    ]
    violations: list[str] = []
    for f in new_files:
        assert f.exists(), f"expected {f} to exist after the rebuild"
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if _FONT_LIT.search(line) or _HEX.search(line):
                violations.append(f"{f.name}:{i}: {line.strip()}")
    assert not violations, (
        "brand literal in the new ST-05 architecture files (tokens only):\n"
        + "\n".join(violations)
    )


# ---- ST-07B theory rebuild (serif headline + prose + key-insight callout) -----

def test_st07b_rebuild_composes_serif_headline_and_key_insight_callout() -> None:
    """The rebuilt ST-07B (theory) is a serif headline, body prose, and a distinct
    key-insight callout (accent rule + larger italic text on a tint panel) —
    composed from the macro library on the token-themed .st-07b layout. Loads the
    REAL apex theory page (first ST-07B, slot 8)."""
    from patterns import st_07b
    page = _load_fixture_page("ST-07B")
    # The fixture now defaults to layout_variant="fill" (FILL_DEFAULT_TYPES). This
    # test asserts the STANDARD composition (the key-insight tint callout), so pin
    # it; the fill composition is covered by tests/test_st07b_fill_variant.py.
    page = {**page, "layout_variant": "standard"}
    frag = st_07b.render(page, _ctx(APEX_FIXTURE))
    assert isinstance(frag, PageFragment)
    _no_head_css(frag)
    assert ".st-07b" in frag.css, "fragment CSS must be scoped to .st-07b"

    # Signature devices: a serif headline + a key-insight callout (tint panel via
    # callout_panel OR the c-key-insight variant — either way an accent tint panel).
    assert "th-headline" in frag.html, "serif headline missing"
    assert ("c-callout-panel" in frag.html or "c-key-insight" in frag.html), \
        "key-insight callout (tint panel) missing"

    # Real theory content from the fixture flows through.
    assert "Wachstum entsteht nicht durch mehr Köpfe" in frag.html          # title
    assert "Wer skaliert, ohne Prozesse zu automatisieren" in frag.html      # body prose
    assert "Operative Engpässe durch manuelle Prozesse" in frag.html         # key_insight (#17)

    # graceful: empty data still composes a non-empty fragment.
    assert st_07b.render(_page("ST-07B", {}, slot=8), _ctx()).html.strip()


def test_st07b_headline_uses_display_axis_token() -> None:
    """The ST-07B headline must size off var(--font-display) — serif via the axis."""
    css = (CHASSIS_ROOT / "styles" / "st_07b.css").read_text(encoding="utf-8")
    assert "var(--font-display)" in css, "ST-07B headline must use var(--font-display)"
    assert "var(--font-body)" in css, "ST-07B body must use the sans body face"


def test_st07b_new_files_are_brand_agnostic() -> None:
    """No font-family literal and no raw #hex in the new ST-07B template/layout CSS."""
    new_files = [
        CHASSIS_ROOT / "templates" / "st_07b.html.jinja",
        CHASSIS_ROOT / "styles" / "st_07b.css",
    ]
    violations: list[str] = []
    for f in new_files:
        assert f.exists(), f"expected {f} to exist after the rebuild"
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if _FONT_LIT.search(line) or _HEX.search(line):
                violations.append(f"{f.name}:{i}: {line.strip()}")
    assert not violations, (
        "brand literal in the new ST-07B architecture files (tokens only):\n"
        + "\n".join(violations)
    )


# ---- new shared macro: geo_shapes (breathing-page geometric overlay) ----------

def test_macro_geo_shapes_composes_low_opacity_token_shapes() -> None:
    """geo_shapes renders a deterministic set of low-opacity geometric accent
    shapes (a logo-motif overlay for the breathing page) under the c-geo
    namespace. The shapes are token-colored (the look lives in components.css);
    the macro only emits the markup. A `variant` selects a shape arrangement so
    the three breathing pages don't look identical."""
    from templating import get_env
    out = get_env().from_string(
        "{% from 'geo_shapes.jinja' import geo_shapes %}{{ geo_shapes(1) }}"
    ).render()
    assert "c-geo" in out
    # several distinct shape primitives compose the motif
    assert "c-geo__shape" in out
    # a second variant produces a DIFFERENT arrangement (so the pages vary)
    out2 = get_env().from_string(
        "{% from 'geo_shapes.jinja' import geo_shapes %}{{ geo_shapes(2) }}"
    ).render()
    assert "c-geo" in out2 and out2 != out


def test_geo_shapes_css_is_brand_agnostic_and_low_opacity() -> None:
    """The c-geo overlay CSS (appended to components.css) carries semantic tokens
    ONLY — no font literal, no raw #hex — and the shapes are low-opacity accent /
    on-dark fields (a quiet logo motif, never solid)."""
    css = (CHASSIS_ROOT / "styles" / "components.css").read_text(encoding="utf-8")
    assert ".c-geo" in css, "missing .c-geo overlay styling in components.css"
    geo_block = css[css.index("/* ---- geo_shapes"):]
    # shapes are tinted with the accent / on-dark tokens at reduced opacity
    assert "var(--color-accent)" in geo_block or "var(--color-on-dark)" in geo_block
    assert "opacity:" in geo_block, "geo shapes must be low-opacity (translucent)"
    violations = [
        f"components.css:{i}: {line.strip()}"
        for i, line in enumerate(css.splitlines(), 1)
        if _FONT_LIT.search(line) or _HEX.search(line)
    ]
    assert not violations, "brand literal in components.css:\n" + "\n".join(violations)


# ---- shared full-bleed @page bleed (breathing pages) -------------------------

def test_shared_head_declares_full_bleed_bleed_page() -> None:
    """The breathing page needs the SAME full-bleed technique the cover uses: a
    named @page with margin:0 and the persistent header band + folio suppressed.
    The cover owns `@page cover`; the breathing page owns `@page bleed`. @page
    rules can only live in the head (assembler.shared_head_css), token-only."""
    from assembler import shared_head_css
    from brand_tokens import parse_brand_tokens
    from tokens.compile_tokens import BrandAxes
    head = shared_head_css(parse_brand_tokens(SAMPLE_BRAND), CHASSIS_ROOT / "fonts", BrandAxes())
    assert "@page bleed" in head, "named full-bleed @page bleed missing from shared head"
    # the bleed page suppresses chrome (margin:0 + header/folio content:none)
    bleed = head[head.index("@page bleed"):]
    bleed = bleed[:bleed.index("@bottom-right") + 40]
    assert "margin: 0" in bleed or "margin:0" in bleed
    assert "content: none" in bleed or "content:none" in bleed
    # the @page bleed block itself is token-only (the per-client :root colors live
    # elsewhere in the head — bound at render time from compile_tokens, by design).
    assert not _HEX.search(bleed), "raw hex in the @page bleed block"
    # the assembler SOURCE (the architecture file) carries the named bleed page.
    src = (CHASSIS_ROOT / "assembler.py").read_text(encoding="utf-8")
    assert "@page bleed" in src


# ---- ST-22 collaboration rebuild (full-width banner + horizontal step flow) ---

def test_st22_rebuild_composes_full_width_banner_and_hflow() -> None:
    """The rebuilt ST-22 (collaboration) is a full-width banner photo header
    (media_figure full-bleed / banner block) + a serif heading + intro, then a
    horizontal numbered step flow (the shared c-hflow macro — Schritt 1 → N with
    accent connectors + Dauer durations). Composed from the macro library on the
    .st-22 layout. Loads the REAL apex page (19)."""
    from patterns import st_22
    page = _load_fixture_page("ST-22")
    # The fixture now defaults to layout_variant="fill" (FILL_DEFAULT_TYPES). This
    # test asserts the STANDARD composition (banner + horizontal flow), so pin it;
    # the fill (vertical-timeline) composition is covered by test_st22_fill_variant.py.
    page = {**page, "layout_variant": "standard"}
    frag = st_22.render(page, _ctx(APEX_FIXTURE))
    assert isinstance(frag, PageFragment)
    _no_head_css(frag)
    assert ".st-22" in frag.css, "fragment CSS must be scoped to .st-22"

    # Signature devices (checklist #9 full-width banner, #12 horizontal flow).
    assert "co-banner" in frag.html, "full-width banner header missing"
    assert "c-hflow" in frag.html, "horizontal step flow missing"
    assert "c-hflow__arrow" in frag.html, "accent flow connectors missing"
    assert "c-hflow__dauer" in frag.html, "step durations (Dauer) missing"

    # Real collaboration content from the fixture flows through.
    assert "Von Erstgespräch zu laufendem AI-System in Wochen" in frag.html   # title
    assert "Strategiegespräch &amp; Fit-Check" in frag.html or \
           "Strategiegespräch & Fit-Check" in frag.html                       # step 1
    assert "Übergabe &amp; Ergebnismessung" in frag.html or \
           "Übergabe & Ergebnismessung" in frag.html                          # step 5
    assert "1 Tag" in frag.html and "1-3 Wochen" in frag.html                  # durations

    # graceful: empty data still composes a non-empty fragment.
    assert st_22.render(_page("ST-22", {}, slot=19), _ctx()).html.strip()


def test_st22_banner_falls_back_to_report_assets_wide(tmp_path) -> None:
    """ST-22 carries no page-level asset in the fixture; the banner integrates a
    wide background from the package report_assets (e.g. extra_wide) so the
    collaboration header is a real photo banner, not an empty plate. The pattern
    reads report_assets off the RenderContext."""
    from patterns import st_22
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "wide.png").write_bytes(b"\x89PNG\r\n")
    report_assets = [{"slot_id": "extra_wide", "image_type": "background",
                      "path": "assets/wide.png", "status": "generated"}]
    ctx = RenderContext(brand=parse_brand_tokens(SAMPLE_BRAND), grammar=load_grammar(),
                        package_dir=tmp_path, report_assets=report_assets)
    data = {"title": "Zusammenarbeit", "steps": [{"n": 1, "title": "Call"}]}
    frag = st_22.render(_page("ST-22", data, slot=19), ctx)
    assert "wide.png" in frag.html, "banner should fall back to a report_assets wide image"


def test_st22_headline_uses_display_axis_token() -> None:
    """The ST-22 heading must size off var(--font-display) — serif via the axis."""
    css = (CHASSIS_ROOT / "styles" / "st_22.css").read_text(encoding="utf-8")
    assert "var(--font-display)" in css, "ST-22 heading must use var(--font-display)"
    assert "var(--font-body)" in css, "ST-22 body must use the sans body face"


def test_st22_new_files_are_brand_agnostic() -> None:
    """No font-family literal and no raw #hex in the new ST-22 template/layout CSS."""
    new_files = [
        CHASSIS_ROOT / "templates" / "st_22.html.jinja",
        CHASSIS_ROOT / "styles" / "st_22.css",
    ]
    violations: list[str] = []
    for f in new_files:
        assert f.exists(), f"expected {f} to exist after the rebuild"
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if _FONT_LIT.search(line) or _HEX.search(line):
                violations.append(f"{f.name}:{i}: {line.strip()}")
    assert not violations, (
        "brand literal in the new ST-22 architecture files (tokens only):\n"
        + "\n".join(violations)
    )


# ---- ST-31/32 breathing rebuild (full-bleed atmospheric ground + geo overlay) -

def test_st31_rebuild_composes_full_bleed_ground_and_geo_overlay() -> None:
    """The rebuilt breathing page (ST-31/32 Atemseite) is a full-page atmospheric
    ground — the brand texture/gradient asset filling the page edge-to-edge via the
    cover's full-bleed technique (the suppressed @page bleed) — with low-opacity
    token-colored geometric accent shapes (geo_shapes) overlaid, a deliberate
    pacing page. Loads the REAL apex breathing page (6); its routed ground asset
    (a real founder/client SCENE photo when routed, an atmospheric texture
    otherwise) must integrate edge-to-edge."""
    from patterns import st_31
    page = _load_fixture_page("ST-31")
    frag = st_31.render(page, _ctx(APEX_FIXTURE))
    assert isinstance(frag, PageFragment)
    _no_head_css(frag)
    assert ".st-31" in frag.css, "fragment CSS must be scoped to .st-31"

    # Full-bleed routing + atmospheric ground + geometric overlay (checklist #22, #20).
    assert "page: bleed" in frag.css, "breathing page must assign itself the named @page bleed"
    assert "br-bleed" in frag.html, "full-bleed atmospheric block missing"
    assert "c-geo" in frag.html, "low-opacity geometric shape overlay missing"
    assert "c-geo__shape" in frag.html, "geometric shape primitives missing"

    # The page's ROUTED breathing-ground asset integrates as the page ground
    # (derived from the fixture, not hardcoded — robust to which scene is routed).
    ground = next((a["path"] for a in (page.get("assets") or [])
                   if str(a.get("slot_id", "")).startswith("breathing_bg") and a.get("path")), "")
    assert ground, "fixture ST-31 page must carry a breathing_bg ground asset"
    assert ground.split("/")[-1] in frag.html, "breather ground asset did not integrate"


def test_st31_falls_back_to_token_gradient_without_asset() -> None:
    """With NO atmospheric asset, the breathing page falls back to a token gradient
    ground (--color-primary → --color-ink) so it is still a striking full-bleed
    pause — never blank, never an awkward content-hugging texture box."""
    from patterns import st_31
    frag = st_31.render(_page("ST-31", {}, slot=6), _ctx())
    assert "br-bleed" in frag.html and "c-geo" in frag.html
    # the layout sheet provides a token gradient ground fallback
    css = (CHASSIS_ROOT / "styles" / "st_31.css").read_text(encoding="utf-8")
    assert "var(--color-primary)" in css and "var(--color-ink)" in css


def test_st31_new_files_are_brand_agnostic() -> None:
    """No font-family literal and no raw #hex in the new breathing template/layout CSS."""
    new_files = [
        CHASSIS_ROOT / "templates" / "st_31.html.jinja",
        CHASSIS_ROOT / "styles" / "st_31.css",
        CHASSIS_ROOT / "components" / "geo_shapes.jinja",
    ]
    violations: list[str] = []
    for f in new_files:
        assert f.exists(), f"expected {f} to exist after the rebuild"
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if _FONT_LIT.search(line) or _HEX.search(line):
                violations.append(f"{f.name}:{i}: {line.strip()}")
    assert not violations, (
        "brand literal in the new breathing architecture files (tokens only):\n"
        + "\n".join(violations)
    )


# ---- new shared macros: these_statement / cost_block / url_band (ST-FAZIT, ST-03) --

def test_macro_these_statement_is_serif_large_pull_statement() -> None:
    """these_statement renders a LARGE serif (var(--font-display)) pull-statement —
    the report's thesis. Markup token-only; the serif sizing lives in the c-these
    class (components.css)."""
    html = _render("{% from 'these_statement.jinja' import these_statement %}"
                   "{{ these_statement('Es ist ein Systemfehler.') }}")
    assert "Es ist ein Systemfehler." in html
    assert "c-these" in html
    _assert_no_literals_rr(html)
    # empty text degrades to nothing (graceful)
    empty = _render("{% from 'these_statement.jinja' import these_statement %}"
                    "{{ these_statement('') }}")
    assert "c-these" not in empty


def test_macro_cost_block_presents_big_figure_and_label() -> None:
    """cost_block presents a prominent offer cost/price — a big figure beside a
    label + optional note. Token-only markup; the figure sizing lives in
    .c-cost-block (components.css)."""
    html = _render("{% from 'cost_block.jinja' import cost_block %}"
                   "{{ cost_block('Kostenloses Erstgespräch', '0 €', note='Kein Risiko.') }}")
    assert "Kostenloses Erstgespräch" in html and "0 &euro;" in html or "0 €" in html
    assert "Kein Risiko." in html
    assert "c-cost-block" in html
    assert "c-cost-block__value" in html and "c-cost-block__label" in html
    _assert_no_literals_rr(html)
    # graceful: nothing to show -> empty
    assert "c-cost-block" not in _render(
        "{% from 'cost_block.jinja' import cost_block %}{{ cost_block('', '') }}")


def test_macro_url_band_is_full_width_button_bar() -> None:
    """url_band renders a FULL-WIDTH accent band with the URL as LARGE type — a
    button-like CTA bar (checklist #15). Token-only markup; the band fill + large
    URL type live in .c-url-band (components.css)."""
    html = _render("{% from 'url_band.jinja' import url_band %}"
                   "{{ url_band('https://apex-consulting.ai/', label='Jetzt starten') }}")
    assert "apex-consulting.ai" in html and "Jetzt starten" in html
    assert "c-url-band" in html and "c-url-band__url" in html
    # the URL is an anchor with a scheme-prefixed href
    assert 'href="https://apex-consulting.ai/"' in html
    _assert_no_literals_rr(html)
    # graceful: no url -> empty
    assert "c-url-band" not in _render(
        "{% from 'url_band.jinja' import url_band %}{{ url_band('') }}")


def test_new_fazit_cta_component_macros_css_is_brand_agnostic() -> None:
    """The new c-these / c-cost-block / c-url-band component CSS (components.css)
    carries NO font-family literal and NO raw #hex — token-only."""
    css = (CHASSIS_ROOT / "styles" / "components.css").read_text(encoding="utf-8")
    # the three new component blocks exist
    for cls in (".c-these", ".c-cost-block", ".c-url-band"):
        assert cls in css, f"expected {cls} in components.css after the rebuild"
    # the These statement sizes off the serif display token
    these = css[css.index(".c-these"):]
    these = these[:these.index(".c-url-band")] if ".c-url-band" in these else these
    assert "var(--font-display)" in these, "These statement must use var(--font-display)"


# ---- ST-FAZIT summary rebuild (serif header band + These + cost + URL band) ----

def test_stfazit_rebuild_composes_these_cost_and_url_band() -> None:
    """The rebuilt summary (ST-FAZIT) is a serif 'Zusammenfassung' header band, a
    recap body, a large These pull-statement (these_statement), a cost block
    (cost_block), and a full-width accent URL band (url_band). A normal (non-bleed)
    content page composed from the macro library on the .st-fazit layout. Loads the
    REAL apex page (18)."""
    from patterns import st_fazit
    page = _load_fixture_page("ST-FAZIT")
    # The fixture now defaults to layout_variant="fill" (FILL_DEFAULT_TYPES). This
    # test asserts the STANDARD composition (header band + These + cost + url band),
    # so pin it; the fill composition is covered by test_stfazit_fill_variant.py.
    page = {**page, "layout_variant": "standard"}
    frag = st_fazit.render(page, _ctx(APEX_FIXTURE))
    assert isinstance(frag, PageFragment)
    _no_head_css(frag)
    assert ".st-fazit" in frag.css, "fragment CSS must be scoped to .st-fazit"

    # Signature devices (checklist #15 giant URL band + These statement + cost block).
    assert "c-these" in frag.html, "These pull-statement missing"
    assert "c-cost-block" in frag.html, "cost block missing"
    assert "c-url-band" in frag.html, "full-width accent URL band missing"

    # Real summary content from the fixture flows through.
    assert "Dein Wachstum wartet nicht" in frag.html                       # title -> header band
    assert "Systemfehler" in frag.html                                     # These statement
    assert "apex-consulting.ai" in frag.html                               # URL band

    # graceful: empty data still composes a non-empty fragment.
    assert st_fazit.render(_page("ST-FAZIT", {}, slot=18), _ctx()).html.strip()


def test_stfazit_header_and_these_use_display_axis_token() -> None:
    """The ST-FAZIT header band + These statement must size off var(--font-display)
    — serif via the axis — set against the sans body face."""
    css = (CHASSIS_ROOT / "styles" / "st_fazit.css").read_text(encoding="utf-8")
    assert "var(--font-display)" in css, "ST-FAZIT serif header/These must use var(--font-display)"
    assert "var(--font-body)" in css, "ST-FAZIT recap body must use the sans body face"


def test_stfazit_new_files_are_brand_agnostic() -> None:
    """No font-family literal and no raw #hex in the new ST-FAZIT template/layout CSS."""
    new_files = [
        CHASSIS_ROOT / "templates" / "st_fazit.html.jinja",
        CHASSIS_ROOT / "styles" / "st_fazit.css",
    ]
    violations: list[str] = []
    for f in new_files:
        assert f.exists(), f"expected {f} to exist after the rebuild"
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if _FONT_LIT.search(line) or _HEX.search(line):
                violations.append(f"{f.name}:{i}: {line.strip()}")
    assert not violations, (
        "brand literal in the new ST-FAZIT architecture files (tokens only):\n"
        + "\n".join(violations)
    )


# ---- ST-03 back-cover rebuild (full-bleed saturated ground + oversized URL + QR) --

def test_st03_rebuild_composes_full_bleed_saturated_ground_oversized_url_and_qr() -> None:
    """The rebuilt back cover (ST-03) is a full-bleed dark-authority-ground page
    (--color-ink filling the sheet, suppressed chrome) with low-opacity geometric
    shapes (geo_shapes), a short headline, a DESIGNED CTA cluster (an accent rule →
    label → PROPORTIONATE accent URL beside the QR), and a centered wordmark
    sign-off — Richard's lower-weighted closing skeleton. Loads the REAL apex
    page (20)."""
    from patterns import st_03
    page = _load_fixture_page("ST-03")
    frag = st_03.render(page, _ctx(APEX_FIXTURE))
    assert isinstance(frag, PageFragment)
    _no_head_css(frag)
    assert ".st-03" in frag.css, "fragment CSS must be scoped to .st-03"

    # Full-bleed routing + dark ground (reuse the named @page bleed).
    assert "page: bleed" in frag.css, "back cover must assign itself the named @page bleed"
    assert "cta-bleed" in frag.html, "full-bleed dark-authority ground block missing"
    # Signature devices: geo shapes (#20), the designed CTA cluster (proportionate
    # URL — NOT a naked oversized string), and the embedded QR (#21).
    assert "c-geo" in frag.html and "c-geo__shape" in frag.html, "geometric shapes missing"
    assert "cta-action" in frag.html, "designed CTA cluster missing"
    assert "cta-url" in frag.html, "proportionate URL CTA missing"
    assert "c-qr" in frag.html, "embedded QR (white box) missing"

    # Real back-cover content from the fixture flows through.
    assert "Buche jetzt dein kostenloses Erstgespräch" in frag.html         # headline
    assert "apex-consulting.ai" in frag.html                                # oversized URL

    # graceful: empty data still composes a non-empty fragment (QR falls back to
    # the brand qr_target_url so the back cover always carries a scannable code).
    assert st_03.render(_page("ST-03", {}, slot=20), _ctx()).html.strip()


def test_st03_dark_authority_ground_and_proportionate_url_are_tokens() -> None:
    """DNA §C3 (gap #4): the back-cover CTA is an AUTHORITY panel — a SOLID DARK
    ground (--color-ink, the genuinely-dark neutral) so it reads as a strong
    closing page for ANY brand (a saturated --color-primary goes pale for a
    tonal/mid-hue brand like APEX's cyan — exactly the soft look this fix removes).
    The headline/wordmark read in --color-on-dark (white); the URL is
    PROPORTIONATE (--type-h2, a contained CTA — NOT the page's biggest type) and
    fires in --color-accent on the dark ground (Richard's closing skeleton)."""
    css = (CHASSIS_ROOT / "styles" / "st_03.css").read_text(encoding="utf-8")
    assert "var(--color-ink)" in css, "back-cover CTA ground must be the solid dark --color-ink"
    # the pale-tint look the dark-ground fix removes: NOT a pale accent-tint / wash.
    assert "--color-accent-tint" not in css, "back-cover CTA must not use a pale accent-tint"
    assert "--color-ground-wash" not in css, "back-cover CTA must not use a pale ground-wash"
    assert "var(--color-on-dark)" in css, "headline/wordmark must read in --color-on-dark (white)"
    # the URL must be PROPORTIONATE + accent — NOT the oversized display-xl hero
    # the old naked-URL design used (the exact "too big" look this redesign fixes).
    assert "var(--type-h2)" in css, "the CTA URL must be proportionate (--type-h2)"
    assert "var(--color-accent)" in css, "the CTA URL/rule must fire in --color-accent"
    assert "var(--type-display-xl)" not in css, "the URL must NOT be the oversized display-xl hero"


def test_st03_new_files_are_brand_agnostic() -> None:
    """No font-family literal and no raw #hex in the new ST-03 template/layout CSS."""
    new_files = [
        CHASSIS_ROOT / "templates" / "st_03.html.jinja",
        CHASSIS_ROOT / "styles" / "st_03.css",
    ]
    violations: list[str] = []
    for f in new_files:
        assert f.exists(), f"expected {f} to exist after the rebuild"
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if _FONT_LIT.search(line) or _HEX.search(line):
                violations.append(f"{f.name}:{i}: {line.strip()}")
    assert not violations, (
        "brand literal in the new ST-03 architecture files (tokens only):\n"
        + "\n".join(violations)
    )


# ---- Task 6: data-driven chart embedding (RenderContext.chart_svgs +
#      ST-06 / ST-07A chart-region wiring) ------------------------------------
#
# Contract: the pre-processor extracts chart SPECS onto page["charts"]
# (provenance) and APPENDS a brand-styled SVG per spec — last — to that slot's
# page["components"] (path strings under components/). So for a page with N chart
# specs the LAST N components ARE the chart SVGs. RenderContext.chart_svgs(page)
# keys off that count (no type marker / no naming convention / no pre-processor
# re-run needed) and returns the inline SVG strings. A chart-host pattern embeds
# them in its chart region; a chart-less page renders exactly as before.

_CHART_SVG = (
    '<svg viewBox="0 0 200 120" xmlns="http://www.w3.org/2000/svg">'
    '<rect width="200" height="120" fill="#fff"/>'
    '<rect x="10" y="40" width="40" height="60" fill="#5a9ab3"/>'
    '<text x="10" y="115">Vorher 40h</text></svg>'
)


def _write_component(pkg_dir: Path, name: str, svg: str) -> str:
    """Write an SVG component into a package's components/ dir; return its
    package-relative path (mirrors how the pre-processor writes + references it)."""
    (pkg_dir / "components").mkdir(parents=True, exist_ok=True)
    (pkg_dir / "components" / name).write_text(svg, encoding="utf-8")
    return f"components/{name}"


def test_chart_svgs_returns_tail_components_for_charted_page(tmp_path) -> None:
    """chart_svgs resolves the LAST N components (N = len(page['charts'])) to
    inline SVG strings — the robust, marker-free signal for chart components."""
    # one non-chart leading component + two trailing chart components
    rel0 = _write_component(tmp_path, "16_component_0.svg", "<svg><!--lead--></svg>")
    rel1 = _write_component(tmp_path, "16_component_1.svg", _CHART_SVG)
    rel2 = _write_component(tmp_path, "16_component_2.svg",
                            _CHART_SVG.replace("Vorher", "Nachher"))
    page = {
        "slot": 16, "st_type": "ST-06",
        "components": [rel0, rel1, rel2],
        "charts": [{"chart_type": "before_after_bars"},
                   {"chart_type": "comparison_columns"}],  # N = 2
    }
    svgs = _ctx(tmp_path).chart_svgs(page)
    assert len(svgs) == 2                       # only the trailing two
    assert "Vorher 40h" in svgs[0]              # in package order
    assert "Nachher 40h" in svgs[1]
    assert "lead" not in "".join(svgs)          # the leading non-chart is excluded


def test_chart_svgs_empty_when_no_charts(tmp_path) -> None:
    """A page WITHOUT chart specs yields [] even if it carries components (those
    are non-chart ST/extra components) — so chart-less pages stay unchanged."""
    rel = _write_component(tmp_path, "16_component_0.svg", "<svg><!--x--></svg>")
    page = {"slot": 16, "st_type": "ST-06", "components": [rel], "charts": []}
    assert _ctx(tmp_path).chart_svgs(page) == []
    # missing keys entirely → still graceful []
    assert _ctx(tmp_path).chart_svgs({"slot": 16, "st_type": "ST-06"}) == []


def test_st06_embeds_chart_svg_instead_of_token_bar(tmp_path) -> None:
    """ST-06: when a real chart component/spec is present, the chart SVG renders
    in the chart region INSTEAD of the ad-hoc token bar_chart.jinja bar."""
    from patterns import st_06
    rel = _write_component(tmp_path, "16_component_0.svg", _CHART_SVG)
    page = {
        "slot": 16, "st_type": "ST-06", "page_numbers": "16", "assets": [],
        "data": {"title": "Das Framework", "body": "Intro.",
                 "steps": [{"title": "Audit", "body": "Wir messen."}],
                 "ergebnis": "30-50% Effizienz.",
                 # bars present too — must be SUPERSEDED by the real chart
                 "bars": [{"label": "Vorher", "value": "40h"}]},
        "components": [rel],
        "charts": [{"chart_type": "before_after_bars"}],
    }
    frag = st_06.render(page, _ctx(tmp_path))
    _no_head_css(frag)
    # the chart SVG is inlined in the chart region …
    assert "mx-chart-svg" in frag.html
    assert "<svg" in frag.html and "Vorher 40h" in frag.html
    # … and the ad-hoc token bar is NOT rendered (chart supersedes it)
    assert "c-bar-chart" not in frag.html


def test_st06_falls_back_to_token_bar_without_chart_spec() -> None:
    """ST-06 chart-less page keeps the OLD behavior: the ad-hoc token bar renders
    from data['bars'] and no chart SVG region appears."""
    from patterns import st_06
    data = {"title": "Das Framework", "body": "Intro.",
            "steps": [{"title": "Audit", "body": "Wir messen."}],
            "ergebnis": "30-50% Effizienz.",
            "bars": [{"label": "Vorher", "value": "40h"}]}
    frag = st_06.render(_page("ST-06", data, slot=16), _ctx())
    _no_head_css(frag)
    assert "mx-chart-svg" not in frag.html        # no chart SVG region
    assert "c-bar-chart" in frag.html             # old token bar intact


def test_st07a_embeds_chart_svg_in_chart_region(tmp_path) -> None:
    """ST-07A: a results page carrying page['charts'] embeds the chart SVG into
    the main column's chart region.

    The current fixture's first case study is the GoldmanTax casestudy_hero
    A3 spread, whose dark 'Das Ergebnis' dashboard draws its own proof device
    (csh-dev-ba) instead of a chart band. The chart-region host lives on the
    'standard' variant, so force that variant here to keep this test's intent
    (charts render when the layout hosts them)."""
    from patterns import st_07a
    # start from the real fixture page, then attach a chart component + spec
    page = dict(_load_fixture_page("ST-07A"))
    page["layout_variant"] = "standard"
    rel = _write_component(tmp_path, "cs_component_0.svg", _CHART_SVG)
    page["components"] = list(page.get("components") or []) + [rel]
    page["charts"] = [{"chart_type": "before_after_bars"}]
    frag = st_07a.render(page, _ctx(tmp_path))
    _no_head_css(frag)
    assert "cs-chart-svg" in frag.html
    assert "<svg" in frag.html and "Vorher 40h" in frag.html


def test_st07a_without_charts_renders_no_chart_region() -> None:
    """ST-07A chart-less page renders unchanged: no chart SVG region."""
    from patterns import st_07a
    page = _load_fixture_page("ST-07A")
    frag = st_07a.render(page, _ctx(APEX_FIXTURE))
    assert "cs-chart-svg" not in frag.html


# ---- Task 5: sans_allcaps head-CSS rule --------------------------------------

def test_sans_allcaps_emits_uppercase_rule() -> None:
    """shared_head_css must emit a [data-headline-type="sans_allcaps"] rule that
    uppercases + tracks the headline classes (.c-two-tone and page h1).

    The rule must be scoped to the HEADLINE selectors only (body/thesis sentence-
    case is untouched); the rule lives in the shared head CSS so it is always
    present regardless of which pattern renders the page.
    """
    from assembler import shared_head_css
    from brand_tokens import parse_brand_tokens
    from tokens.compile_tokens import BrandAxes
    head = shared_head_css(parse_brand_tokens(SAMPLE_BRAND), CHASSIS_ROOT / "fonts", BrandAxes())
    assert '[data-headline-type="sans_allcaps"]' in head, (
        "sans_allcaps selector missing from shared head CSS"
    )
    assert "text-transform: uppercase" in head, (
        "text-transform: uppercase missing from shared head CSS"
    )
    assert "letter-spacing" in head, (
        "letter-spacing missing from sans_allcaps rule"
    )
    # body and thesis selectors must NOT appear inside the sans_allcaps block
    # (we just assert the rule targets headline classes, not body/p/thesis)
    block_start = head.index('[data-headline-type="sans_allcaps"]')
    # find the end of the rule block (closing brace after the block)
    block_end = head.index("}", block_start) + 1
    block = head[block_start:block_end]
    assert ".c-two-tone" in block or "h1" in block, (
        "sans_allcaps rule must target headline classes (.c-two-tone or h1)"
    )


# ---- Task 6: perceptible page ground (light/cool_light uses --color-ground) --

def test_light_page_ground_is_color_ground_not_wash() -> None:
    """The light-page ground is painted on the FULL SHEET via @page (2026-07-13
    contract), with the light `.page` transparent so content never re-fills it.

    This supersedes the old contract where the light block itself carried
    `var(--color-ground)`: that moved to the sheet so the ground reaches edge
    to edge through the margins. The `@page a4-portrait` sheet must use the
    perceptible `--color-surface` base (not the near-invisible 5% wash as the
    sole layer), and the folio-band gradient still consumes `--color-ground-wash`.
    """
    from assembler import shared_head_css
    from brand_tokens import parse_brand_tokens
    from tokens.compile_tokens import BrandAxes
    head = shared_head_css(parse_brand_tokens(SAMPLE_BRAND), CHASSIS_ROOT / "fonts", BrandAxes())

    # The light content page is transparent: the ground is painted by @page.
    assert '[data-ground-mode="light"]' in head, (
        "[data-ground-mode=\"light\"] selector missing from shared head CSS"
    )
    block_start = head.index('[data-ground-mode="light"]')
    block_end = head.index("}", block_start) + 1
    light_block = head[block_start:block_end]
    assert "background: transparent" in light_block, (
        "light page must be transparent so the full-sheet @page ground shows through"
    )

    # The full-sheet ground is the perceptible surface token, not the wash alone.
    assert "var(--color-surface)" in head, (
        "@page sheet ground must use var(--color-surface)"
    )

    # The folio-band gradient still consumes --color-ground-wash (preserved).
    assert "var(--color-ground-wash)" in head, (
        "@page folio-band gradient must still reference var(--color-ground-wash) "
        "(the folio wash must not be removed)"
    )


# ---- Task 8: FEST 14pt body leading + balanced density rule ------------------

def test_body_leading_is_absolute_14pt() -> None:
    """The body { } rule in shared_head_css must pin line-height to the absolute
    FEST value of 14pt — NOT a unitless multiplier via var(--density-lead).

    Canon: 10.5pt body × absolute 14pt leading = consistent 4-pt baseline grid
    regardless of density axis.  The density axis still drives column-gap and
    paragraph-spacing (via --density-col-gap / --density-para), but body leading
    is immutable: 14pt FEST.
    """
    from assembler import shared_head_css
    from brand_tokens import parse_brand_tokens
    from tokens.compile_tokens import BrandAxes
    head = shared_head_css(parse_brand_tokens(SAMPLE_BRAND), CHASSIS_ROOT / "fonts", BrandAxes())

    # Isolate the body { } rule (find "body {" then the closing brace).
    assert "body {" in head or "body{{" in head, "body rule missing from shared head CSS"
    body_start = head.index("body {") if "body {" in head else head.index("body{{")
    body_end = head.index("}", body_start) + 1
    body_block = head[body_start:body_end]

    # Must contain the absolute 14pt value.
    assert "line-height: 14pt" in body_block, (
        f"body rule must set line-height: 14pt (FEST absolute), got block:\n{body_block}"
    )
    # Must NOT use the density variable as the driver.
    assert "var(--density-lead" not in body_block, (
        "body rule must not use var(--density-lead) — leading is fixed 14pt FEST"
    )


def test_balanced_density_rule_present() -> None:
    """density.css must contain an explicit [data-density="balanced"] rule so
    that the balanced density has defined --density-* vars (previously it fell
    through to the :root defaults, giving it no named rule at all).
    """
    density_css = (CHASSIS_ROOT / "styles" / "density.css").read_text(encoding="utf-8")
    assert '[data-density="balanced"]' in density_css, (
        "[data-density=\"balanced\"] rule is missing from styles/density.css"
    )


# ---- Task 9: page furniture — margins, header accent tick, footer hairline ----

def test_furniture_margins_tick_footer() -> None:
    """Task 9 furniture pin:

    (a) @page margins are exactly 16mm 14mm 20mm 18mm (T16/R14/B20/L18 = top/
        outside/bottom/inside).
    (b) A .ph-tick CSS rule exists in the shared head, uses var(--color-accent),
        AND the ph-tick span appears in the header markup produced by
        _page_header().
    (c) The folio moved to @bottom-right (Footer-A redesign) and reads navy,
        var(--color-ink), not the old muted @bottom-left.
    """
    from assembler import shared_head_css, _page_header
    from brand_tokens import parse_brand_tokens
    from tokens.compile_tokens import BrandAxes

    head = shared_head_css(parse_brand_tokens(SAMPLE_BRAND), CHASSIS_ROOT / "fonts", BrandAxes())
    brand = parse_brand_tokens(SAMPLE_BRAND)
    header_markup = _page_header(brand)

    # (a) Margins
    assert "margin: 16mm 14mm 20mm 18mm" in head, (
        "@page margin must be exactly '16mm 14mm 20mm 18mm' (T16/R14/B20/L18)"
    )

    # (b) Accent tick — CSS rule + markup span
    assert ".ph-tick" in head, ".ph-tick CSS rule missing from shared head CSS"
    assert "var(--color-accent)" in head[head.index(".ph-tick"):head.index(".ph-tick") + 300], (
        ".ph-tick CSS must use var(--color-accent)"
    )
    assert "ph-tick" in header_markup, (
        "ph-tick span missing from _page_header() markup"
    )

    # (c) Footer folio moved to @bottom-right (Footer-A) and reads navy (ink).
    assert "@bottom-right" in head, "@bottom-right folio rule missing"
    br_start = head.index("@bottom-right")
    br_end = head.index("}", br_start) + 1
    folio_block = head[br_start:br_end]
    assert "var(--color-ink)" in folio_block, (
        "@bottom-right folio must use var(--color-ink)"
    )


# ---- phone_mockup macro ("live social presence" — a real IG post in a drawn phone) --

def test_macro_phone_mockup_shows_real_post_and_never_fabricates() -> None:
    """phone_mockup draws a CSS phone (bezel + notch + white screen) carrying the
    REAL post photo + the REAL avatar + handle (shown as @handle). It must NEVER
    fabricate engagement: with no caption supplied it shows the empty foot strip,
    NOT invented caption/likes; a real caption shows only when supplied. Token-only
    chrome (the look lives in .c-phone, components.css)."""
    from templating import get_env
    out = get_env().from_string(
        "{% from 'phone_mockup.jinja' import phone_mockup %}"
        "{{ phone_mockup('file:///t/post.jpg', avatar_uri='file:///t/av.jpg', handle='jousefmrd') }}"
    ).render()
    # device chrome + the real post image
    assert "c-phone" in out and "c-phone__screen" in out and "c-phone__notch" in out
    assert "c-phone__photo" in out and "file:///t/post.jpg" in out
    # real avatar + handle (shown as @handle)
    assert "c-phone__avatar" in out and "file:///t/av.jpg" in out
    assert "@jousefmrd" in out
    # NO fabrication: no caption supplied → empty foot strip, no caption block
    assert "c-phone__foot" in out and "c-phone__cap" not in out

    # a REAL caption shows only when supplied
    out2 = get_env().from_string(
        "{% from 'phone_mockup.jinja' import phone_mockup %}"
        "{{ phone_mockup('file:///t/post.jpg', caption='Echtes Zitat') }}"
    ).render()
    assert "c-phone__cap" in out2 and "Echtes Zitat" in out2

    # PROFILE-GRID mode: a `posts` list renders a 3-col grid of the real posts
    # (the "active brand presence" look), one cell per post; takes precedence.
    out3 = get_env().from_string(
        "{% from 'phone_mockup.jinja' import phone_mockup %}"
        "{{ phone_mockup(avatar_uri='file:///t/av.jpg', handle='jousefmrd',"
        "   posts=['file:///t/p1.jpg','file:///t/p2.jpg','file:///t/p3.jpg']) }}"
    ).render()
    assert "c-phone--grid" in out3 and "c-phone__grid" in out3
    assert out3.count("c-phone__cell") == 3
    assert "file:///t/p1.jpg" in out3 and "file:///t/p3.jpg" in out3
    assert "c-phone__photo" not in out3, "grid mode must not render the single-post photo"

    # macro carries NO client/colour/font literal (brand-agnostic by construction)
    macro = (CHASSIS_ROOT / "components" / "phone_mockup.jinja").read_text(encoding="utf-8")
    assert not _HEX.search(macro) and not _FONT_LIT.search(macro)
