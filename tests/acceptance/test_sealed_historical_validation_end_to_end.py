"""Synthetic acceptance for the complete sealed historical-validation path."""

from pathlib import Path

import pytest

from gemini_trading.data.providers.binance_spot import BinanceSpotProvider
from integration.test_sealed_historical_validation import (
    test_complete_requires_matching_durable_receipt as _run_complete_sealed_path,
)


def test_complete_sealed_path_is_provider_free_and_non_promotional(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def deny_provider(
        self: object,
        *args: object,
        **kwargs: object,
    ) -> None:
        del self, args, kwargs
        raise AssertionError("sealed historical validation constructed a market-data provider")

    monkeypatch.setattr(BinanceSpotProvider, "__init__", deny_provider)

    _run_complete_sealed_path(tmp_path)

    study_root = tmp_path / "data" / "strategy-studies"
    study_directories = tuple(path for path in study_root.iterdir() if path.is_dir())
    assert len(study_directories) == 1
    limitations = (study_directories[0] / "limitations.json").read_text(encoding="utf-8")
    assert '"production_eligible":false' in limitations
    assert '"real_seven_year_run_claimed":false' in limitations
