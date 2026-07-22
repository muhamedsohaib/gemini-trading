from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from gemini_trading.data.errors import CandleGapError, DuplicateCandleError, OutOfOrderCandleError
from gemini_trading.data.validation.candles import validate_candle_sequence
from gemini_trading.domain.candle import Candle
from gemini_trading.domain.dataset import RetrievalRequest
from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.timeframe import Timeframe

_INSTRUMENT = Instrument("ETHUSDT", "ETH", "USDT")
_START = datetime(2025, 1, 1, tzinfo=UTC)


def _sequence(count: int) -> tuple[Candle, ...]:
    return tuple(
        Candle(
            instrument=_INSTRUMENT,
            timeframe=Timeframe.H4,
            open_time=_START + index * Timeframe.H4.duration,
            close_time=_START + (index + 1) * Timeframe.H4.duration - timedelta(milliseconds=1),
            open=Decimal("100"),
            high=Decimal("110"),
            low=Decimal("90"),
            close=Decimal("105"),
            volume=Decimal("1"),
            completed=True,
            source_provider="binance_spot",
        )
        for index in range(count)
    )


def _request(count: int) -> RetrievalRequest:
    return RetrievalRequest(
        instrument=_INSTRUMENT,
        timeframe=Timeframe.H4,
        start_time=_START,
        end_time=_START + count * Timeframe.H4.duration,
    )


@given(
    count=st.integers(min_value=2, max_value=20),
    raw_index=st.integers(min_value=0, max_value=100),
)
def test_duplicate_mutation_always_raises_duplicate_error(count: int, raw_index: int) -> None:
    candles = list(_sequence(count))
    index = raw_index % count
    candles.insert(index, candles[index])

    with pytest.raises(DuplicateCandleError):
        validate_candle_sequence(candles, _request(count))


@given(
    count=st.integers(min_value=2, max_value=20),
    raw_index=st.integers(min_value=0, max_value=100),
)
def test_reversal_mutation_always_raises_out_of_order_error(count: int, raw_index: int) -> None:
    candles = list(_sequence(count))
    left = raw_index % (count - 1)
    candles[left], candles[left + 1] = candles[left + 1], candles[left]

    with pytest.raises(OutOfOrderCandleError):
        validate_candle_sequence(candles, _request(count))


@given(
    count=st.integers(min_value=3, max_value=20),
    raw_index=st.integers(min_value=0, max_value=100),
)
def test_gap_mutation_always_raises_gap_error(count: int, raw_index: int) -> None:
    candles = list(_sequence(count))
    internal_index = 1 + raw_index % (count - 2)
    del candles[internal_index]

    with pytest.raises(CandleGapError):
        validate_candle_sequence(candles, _request(count))
