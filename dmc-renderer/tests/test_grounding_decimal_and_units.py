"""G17: the grounding gate must not collapse decimals or ignore units."""
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from synthesize_visuals import _digit_tokens, _ground_device  # noqa: E402


def test_decimal_comma_is_not_collapsed() -> None:
    """'12,5' must NOT ground '125': a decimal comma is significant."""
    source = _digit_tokens("Die Zeit sank auf 12,5 Stunden.")
    assert "125" not in source
    assert "12,5" in source


def test_thousands_dot_is_a_separator() -> None:
    """'1.200' must NOT ground '1200' as a decimal; it is a thousands sep."""
    source = _digit_tokens("Der Umsatz betrug 1.200 €.")
    assert "1200" in source or "1.200" in source


def test_label_swap_is_rejected() -> None:
    """A device that attaches a correct digit to a wrong label must fail."""
    text = "2 Stunden Bearbeitung."
    source = _digit_tokens(text)
    device = {"stats": [{"value": "2 h", "label": "Bearbeitung"}]}
    assert _ground_device(device, source, source_text=text) is False


def test_matching_label_and_digit_passes() -> None:
    text = "2 Stunden Bearbeitung."
    source = _digit_tokens(text)
    device = {"stats": [{"value": "2", "label": "Stunden Bearbeitung"}]}
    assert _ground_device(device, source, source_text=text) is True
