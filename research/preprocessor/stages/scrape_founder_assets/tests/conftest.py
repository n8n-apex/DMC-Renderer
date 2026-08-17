"""Pytest setup — extends sys.path so these tests resolve `stages.*`
imports regardless of the runner's cwd (mirrors tests/conftest.py).
"""
from __future__ import annotations

import sys
from pathlib import Path

# preprocessor root = stages/scrape_founder_assets/tests -> up 3
_PREPROCESSOR_ROOT = Path(__file__).resolve().parents[3]
if str(_PREPROCESSOR_ROOT) not in sys.path:
    sys.path.insert(0, str(_PREPROCESSOR_ROOT))
