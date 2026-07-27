"""Rename the autouse integration fixture for strict Pyright."""

from pathlib import Path


path = Path("tests/integration/test_sealed_historical_validation.py")
text = path.read_text(encoding="utf-8")
old = "def _bound_integration_training(monkeypatch: pytest.MonkeyPatch) -> None:"
new = "def bound_integration_training(monkeypatch: pytest.MonkeyPatch) -> None:"
if text.count(old) != 1:
    raise SystemExit("unexpected bounded integration fixture structure")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
