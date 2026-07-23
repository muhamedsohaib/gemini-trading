import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from gemini_trading.data.ingestion.service import IngestionService
from gemini_trading.data.providers.binance_spot import BinanceSpotProvider
from gemini_trading.data.storage.local_immutable import LocalImmutableStore
from gemini_trading.data.verification.service import VerificationService
from gemini_trading.domain.dataset import RetrievalRequest
from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.timeframe import Timeframe


@pytest.mark.live_api
@pytest.mark.skipif(
    os.environ.get("GEMINI_TRADING_RUN_LIVE_API_TESTS") != "1",
    reason="set GEMINI_TRADING_RUN_LIVE_API_TESTS=1 to run bounded public API smoke test",
)
def test_binance_spot_public_smoke_uses_no_credentials_and_only_tmp_path(tmp_path: Path) -> None:
    request = RetrievalRequest(
        instrument=Instrument("ETHUSDT", "ETH", "USDT"),
        timeframe=Timeframe.H4,
        start_time=datetime(2025, 1, 1, tzinfo=UTC),
        end_time=datetime(2025, 1, 1, 8, tzinfo=UTC),
    )
    store = LocalImmutableStore(tmp_path)

    result = IngestionService(
        provider=BinanceSpotProvider(),
        raw_store=store,
        canonical_store=store,
        run_id_factory=lambda: "live-smoke-run",
    ).ingest(request)

    assert result.raw_page_count >= 1
    assert result.candle_count == 2
    assert all(path.is_relative_to(tmp_path) for _name, path in result.paths)
    verification = VerificationService(raw_store=store, canonical_store=store).verify(
        result.dataset_id,
        result.run_id,
    )
    assert verification.candle_count == result.candle_count
