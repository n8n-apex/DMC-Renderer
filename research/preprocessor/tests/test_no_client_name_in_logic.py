"""Regression guard mirroring the chassis's `test_no_coral_in_chassis_logic`.

Scans the pre-processor's production LOGIC (main.py, models*.py, stages/) for
client names that the user explicitly forbade in logic:

    APEX, GEVA, Conesso, NMR, Ärztepartner, Buchagentur, Boss

…plus literal accent-colour names that prior frames used as chassis
concepts ("coral").

What "logic" means here (and why this scan is token-aware, not line-based):
the rule forbids a client literal as a DATA VALUE or IDENTIFIER in executable
code (e.g. `if client == "APEX"`, `APEX_PROFILE = {...}`). It does NOT forbid
mentioning the pilot fixture in an explanatory COMMENT or DOCSTRING, nor a
legitimate `fixtures/<client>/` path. So the scanner tokenizes each file and:
  - skips COMMENT tokens entirely,
  - skips module/class/function DOCSTRINGS (detected via ast),
  - still scans NAME + value-STRING tokens (a real literal in logic is caught).

Allowed contexts (exempted):
  - tests/ and test fixtures (fixtures CAN name a client — that's data
    identifying whose data was transcribed, not logic),
  - .venv / 3rd-party packages (PIL/pymupdf ship "coral" as a CSS color name),
  - __pycache__,
  - tools/ — operational/one-off SCRIPTS (e.g. the pilot decorative-asset
    generator), which are not part of the brand-agnostic PIPELINE logic and
    legitimately reference the pilot fixture + its `fixtures/<client>/` path.
    (This matches the guard's documented scope: main.py, models.py, stages/.)
  - comments + docstrings within in-scope files (explanatory prose, not logic).

This test is the structural lock: future contributors who reintroduce a client
name into pre-processor logic (a value or identifier) fail the suite immediately.
"""

from __future__ import annotations

import ast
import io
import pathlib
import re
import tokenize


_FORBIDDEN_LITERALS = (
    "APEX", "GEVA", "Conesso", "NMR", "Ärztepartner", "Buchagentur",
    "Boss",
    "coral",  # GEVA's prior-frame accent name; chassis decontamination removed it
)

# Directories whose .py files are NOT brand-agnostic pipeline logic.
_SKIP_TOP_DIRS = {"tests", ".venv", "__pycache__", "tools"}


def _docstring_line_spans(tree: ast.AST) -> set[int]:
    """Line numbers occupied by module/class/function docstrings (the first
    statement of each body when it is a bare string constant)."""
    spans: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            body = getattr(node, "body", None)
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                const = body[0].value
                end = const.end_lineno or const.lineno
                for ln in range(const.lineno, end + 1):
                    spans.add(ln)
    return spans


def _matches(text: str) -> list[str]:
    return [
        lit for lit in _FORBIDDEN_LITERALS
        if re.search(rf"\b{re.escape(lit)}\b", text, re.IGNORECASE)
    ]


def _scan_source(src: str) -> list[tuple[int, str, str]]:
    """Return (lineno, literal, snippet) for forbidden literals in CODE only:
    comments and docstrings are excluded; NAME + value-STRING tokens are scanned
    (so a genuine client literal in logic is still caught). Falls back to a raw
    line scan if the file cannot be tokenized (never silently passes)."""
    hits: list[tuple[int, str, str]] = []
    try:
        tree = ast.parse(src)
        doc_lines = _docstring_line_spans(tree)
        tokens = list(tokenize.generate_tokens(io.StringIO(src).readline))
    except (SyntaxError, tokenize.TokenError, IndentationError):
        for lineno, line in enumerate(src.splitlines(), 1):
            for lit in _matches(line):
                hits.append((lineno, lit, line.strip()))
        return hits

    for tok in tokens:
        if tok.type == tokenize.COMMENT:
            continue
        if tok.type == tokenize.STRING and tok.start[0] in doc_lines:
            continue  # docstring prose, not logic
        if tok.type not in (tokenize.NAME, tokenize.STRING):
            continue
        for lit in _matches(tok.string):
            hits.append((tok.start[0], lit, tok.string.strip()[:80]))
    return hits


def test_no_client_name_in_preprocessor_logic() -> None:
    """Regression guard: forbidden literals must not appear in active
    pre-processor LOGIC (main.py, models*.py, stages/*.py) as a value or
    identifier. Comments, docstrings, tests, fixtures, tools/, and .venv are
    exempt (see module docstring)."""
    pp_root = pathlib.Path(__file__).resolve().parent.parent
    violations: list[str] = []

    for py_file in pp_root.rglob("*.py"):
        rel = py_file.relative_to(pp_root)
        parts = rel.parts
        if parts[0] in _SKIP_TOP_DIRS or "__pycache__" in parts:
            continue
        for lineno, literal, snippet in _scan_source(py_file.read_text()):
            violations.append(f"{rel}:{lineno}: [{literal}] {snippet}")

    assert not violations, (
        f"forbidden client/colour literal(s) found in pre-processor "
        f"logic ({len(violations)} hits):\n" + "\n".join(violations)
    )


def test_scanner_still_catches_real_literals() -> None:
    """Proves the token-aware scan did NOT go soft: a client literal used as a
    value or identifier in CODE is still caught; only comments/docstrings pass.
    """
    # value-string literal in logic -> CAUGHT
    assert any(lit == "APEX" for _, lit, _ in _scan_source('x = "APEX"\n')), \
        "a value-string client literal in code must be caught"
    # bare identifier literal -> CAUGHT
    assert _scan_source("coral = 1\n"), "a client/colour identifier must be caught"
    # comment -> NOT caught
    assert _scan_source("y = 1  # apex pilot fixture\n") == []
    # module docstring -> NOT caught
    assert _scan_source('"""About the apex fixture."""\nz = 1\n') == []
