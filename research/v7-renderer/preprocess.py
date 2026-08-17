"""Markdown preprocessor — body field transforms (markdown → HTML).

Transforms applied to body fields by `preprocess_body()`:
  - **bold**   → <strong>bold</strong>
  - *italic*   → <em>italic</em>
  - \\n\\n      → </p><p>   (paragraph break)
  - \\n        → <br/>     (line break)

Scope: regex-only transforms. No nested-markdown semantics. No
markdown-link rule (matrix E5: no link rule exists in §6's table, and
one is NOT added defensively here). German hyphenation runs via Pyphen
+ WeasyPrint's `hyphens: auto` (active per InDesign Spec L246 — min 5
chars, 2-2 minimum).

History note: an earlier `parse_callout_row()` function lived here to
parse `wendepunkt` as a 2×2 pipe/newline grid. REMOVED in M2b
(UNGROUNDED per grammar §8; matrix B2 STRUCK wendepunkt-as-grid).
wendepunkt is now prose per Master System schema L184-189 — single-
sentence narrative pivot, processed by preprocess_body() like any other
body field (or by the future pre-processor layer).
"""

from __future__ import annotations

import re


# Match **bold** non-greedy across single lines.
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
# Match *italic* non-greedy, but NOT inside **bold** (we run bold first).
_ITALIC_RE = re.compile(r"\*(.+?)\*")


def preprocess_body(text: str) -> str:
    """Convert markdown-like body text into HTML fragments.

    Input is one body field (already a string, already utf-8). Output is
    HTML wrapped in <p>...</p> per paragraph. Single newlines become
    <br/>; double newlines split paragraphs.
    """
    if not text:
        return ""

    # Strip surrounding whitespace, then split on blank-line boundaries.
    text = text.strip()
    paragraphs = [p.strip() for p in re.split(r"\n\n+", text) if p.strip()]

    out_parts: list[str] = []
    for para in paragraphs:
        # Bold first, then italic, so **bold** does not get partially-italic-matched.
        para = _BOLD_RE.sub(r"<strong>\1</strong>", para)
        para = _ITALIC_RE.sub(r"<em>\1</em>", para)
        # Single newlines inside the paragraph become <br/>.
        para = para.replace("\n", "<br/>\n")
        out_parts.append(f"<p>{para}</p>")

    return "\n".join(out_parts)
