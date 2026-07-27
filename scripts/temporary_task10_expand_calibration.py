"""Expand the integration-only calibration sample without changing production rules."""

from pathlib import Path


path = Path("tests/integration/test_sealed_historical_validation.py")
text = path.read_text(encoding="utf-8")
old = "_MAX_CALIBRATION_ROWS = 500\n"
new = "_MAX_CALIBRATION_ROWS = 1_000\n"
if text.count(old) != 1:
    raise SystemExit("unexpected Task 10 calibration bound")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
