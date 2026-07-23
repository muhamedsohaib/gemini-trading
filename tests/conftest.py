"""Repository-wide pytest import support for shared test fixtures."""

import sys
from pathlib import Path

_TESTS_ROOT = Path(__file__).resolve().parent
_TESTS_ROOT_TEXT = str(_TESTS_ROOT)
if _TESTS_ROOT_TEXT not in sys.path:
    sys.path.insert(0, _TESTS_ROOT_TEXT)
