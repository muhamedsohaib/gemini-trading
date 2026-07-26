from datetime import UTC, datetime

import pytest

from gemini_trading.data.errors import CandleGapError
from gemini_trading.data.normalization.binance_klines import normalize_binance_klines
from gemini_trading.data.validation.candles import completed_candles, validate_candle_sequence
from gemini_trading.domain.dataset import RetrievalRequest
from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.timeframe import Timeframe


def test_candle_gap_error_reports_previous_expected_and_actual_boundaries() -> None:
    instrument = Instrument("ETHUSDT", "ETH", "USDT")
    request = RetrievalRequest(
        instrument=instrument,
        timeframe=Timeframe.H4,
        start_time=datetime(2025, 1, 1, tzinfo=UTC),
        end_time=datetime(2025, 1, 2, tzinfo=UTC),
    )
    payload = (
        b'[[1735689600000,"3200","3210","3190","3205","1",1735703999999],'
        b'[1735718400000,"3205","3220","3200","3215","1",1735732799999]]'
    )
    candidates = normalize_binance_klines(payload, instrument, Timeframe.H4)
    candles = completed_candles(candidates, datetime(2025, 1, 2, tzinfo=UTC))

    with pytest.raises(CandleGapError) as exc_info:
        validate_candle_sequence(candles, request)

    assert str(exc_info.value) == (
        "candle sequence contains a timeframe gap: "
        "previous_open_time=2025-01-01T00:00:00+00:00 "
        "expected_open_time=2025-01-01T04:00:00+00:00 "
        "actual_open_time=2025-01-01T08:00:00+00:00"
    )
