"""Pytest setup — extends sys.path so tests can do flat imports.

`from models import ...` and `from stages.X import ...` resolve
regardless of the test runner's cwd.
"""

from __future__ import annotations

import sys
from pathlib import Path

# preprocessor root = parent of tests/
_PREPROCESSOR_ROOT = Path(__file__).resolve().parent.parent
if str(_PREPROCESSOR_ROOT) not in sys.path:
    sys.path.insert(0, str(_PREPROCESSOR_ROOT))

# Shared v3 packages such as composition_registry live one level above the
# preprocessor package. Keep that dependency explicit in the test environment.
_RESEARCH_ROOT = _PREPROCESSOR_ROOT.parent
if str(_RESEARCH_ROOT) not in sys.path:
    sys.path.insert(0, str(_RESEARCH_ROOT))
