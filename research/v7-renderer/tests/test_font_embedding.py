"""Regression test for the font-loading root cause (plan 2026-06-03-renderer-phase-A).

THE BUG this guards against: WeasyPrint 68.1 + fontconfig 2.18 compute an EMPTY
charset for fonts whose cmap has only format-4 subtables (Montserrat, Playfair,
Fraunces) -> "No match" -> every headline silently fell back to a system serif
(PT-Serif) / Hiragino in ALL prior phases. Only fonts with a format-12 cmap
subtable (the Adobe Source family) load. So this asserts the DISPLAY SERIF and
BODY SANS actually EMBED in the rendered PDF (the spec's N03 deterministic
perception check), not that they merely appear in CSS.

Rendered in a FRESH SUBPROCESS on purpose: WeasyPrint/fontconfig leaks font
state across multiple write_pdf calls in one process, which makes an in-process
assertion order-dependent and flaky. One render per process is exactly how
production (render.py) runs, and is the only reliable probe.
"""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path

import fitz  # PyMuPDF
import pytest

HERE = Path(__file__).resolve().parent
CHASSIS_ROOT = HERE.parent

# Static script: builds the head via the REAL shared_head_css @font-face contract,
# renders a serif headline + body paragraph, writes the PDF. Paths via argv (no
# interpolation), HTML uses single-quoted attrs (no escaping needed).
_RENDER_SCRIPT = """
import sys
CHASSIS_ROOT, OUT = sys.argv[1], sys.argv[2]
sys.path.insert(0, CHASSIS_ROOT)
from brand_tokens import BrandConfig
from tokens.compile_tokens import BrandAxes
from assembler import shared_head_css, FONT_DIR
import weasyprint
from weasyprint.text.fonts import FontConfiguration

brand = BrandConfig(
    brand_primary='#1A2540', brand_accent='#E97E47', brand_neutral_dark='#0F0F1F',
    brand_neutral_mid='#7A7A8C', brand_neutral_light='#FFFFFF',
    font_heading='Source Serif 4', font_body='Source Sans 3',
    qr_target_url='https://x', company_name_short='X', company_url_display='x.de')
head = shared_head_css(brand, FONT_DIR, BrandAxes(headline_type='serif'))
html = ('<style>' + head + '</style>'
        "<h1 style='font-family:var(--font-display);font-weight:700'>Ueberschrift Bold</h1>"
        "<p style='font-family:var(--font-body)'>Fliesstext probe text.</p>")
weasyprint.HTML(string=html, base_url=CHASSIS_ROOT).write_pdf(OUT, font_config=FontConfiguration())
"""


def _embedded_fonts(tmp_path) -> list[str]:
    out = tmp_path / "probe.pdf"
    script = tmp_path / "render_probe.py"
    script.write_text(_RENDER_SCRIPT)
    proc = subprocess.run(
        [sys.executable, str(script), str(CHASSIS_ROOT), str(out)],
        cwd=str(CHASSIS_ROOT), capture_output=True, text=True,
    )
    assert proc.returncode == 0, f"render subprocess failed:\n{proc.stderr}"
    doc = fitz.open(out)
    return [f[3] for pno in range(len(doc)) for f in doc.get_page_fonts(pno)]


def test_display_serif_and_body_actually_embed(tmp_path):
    fonts = _embedded_fonts(tmp_path)
    blob = " ".join(fonts)
    assert "Source-Serif-4" in blob, f"display serif did NOT embed (fell back): {fonts}"
    assert "Source-Sans-3" in blob, f"body sans did NOT embed (fell back): {fonts}"


def test_no_system_font_fallback_for_headlines(tmp_path):
    fonts = _embedded_fonts(tmp_path)
    blob = " ".join(fonts)
    # The exact symptom of the bug: headline -> PT-Serif, sans -> Hiragino.
    assert "PT-Serif" not in blob, f"headline fell back to system PT-Serif: {fonts}"
    assert "Hiragino" not in blob, f"text fell back to system Hiragino: {fonts}"
