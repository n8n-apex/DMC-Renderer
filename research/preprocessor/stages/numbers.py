"""parse_german_number — turn a German-formatted numeric string into a float.

German convention: '.' = thousands separator, ',' = decimal separator.
Strips surrounding currency/percent/words and parses the first number-like
token. Pure + deterministic + brand-agnostic. Built for the chart lane
(only a detector regex existed before).
"""
from __future__ import annotations

import re
from typing import Optional

_TOKEN = re.compile(r"-?\d[\d.,]*")


def parse_german_number(text: Optional[str]) -> Optional[float]:
    if text is None:
        return None
    m = _TOKEN.search(str(text))
    if not m:
        return None
    tok = m.group(0)
    if "," in tok:
        tok = tok.replace(".", "").replace(",", ".")
    elif tok.count(".") == 1 and len(tok.split(".")[1]) != 3:
        pass
    else:
        tok = tok.replace(".", "")
    try:
        return float(tok)
    except ValueError:
        return None
