from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from gemini_trading.data.errors import (
    CandleGapError,
    CandleValidationError,
    DuplicateCandleError,
    OutOfOrderCandleError,
)
from gemini_trading.data.validation.candles import (
    completed_candles,
    validate_candle,
    validate_candle_sequence,
)
from gemini_trading.domain.candle import Candle
from gemini_trading.domain.dataset import RetrievalRequest
from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.timeframe import Timeframe

_INSTRUMENT = Instrument("ETHUSDT", "ETH", "USDT")
_START = datetime(2025, 1, 1, tzinfo=UTC)


def _candle(
    index: int = 0,
    *,
    instrument: Instrument = _INSTRUMENT,
    timeframe: Timeframe = Timeframe.H4,
    completed: bool = True,
) -> Candle:
    open_time = _START + index * timeframe.duration
    return Candle(
        instrument=instrument,
        timeframe=timeframe,
        open_time=open_time,
        close_time=open_time + timeframe.duration - timedelta(milliseconds=1),
        open=Decimal("100"),
        high=Decimal("110"),
        low=Decimal("90"),
        close=Decimal("105"),
        volume=Decimal("12.5"),
        completed=completed,
        source_provider="binance_spot",
    )


def _request(*, candle_count: int = 3) -> RetrievalRequest:
    return RetrievalRequest(
        instrument=_INSTRUMENT,
        timeframe=Timeframe.H4,
        start_time=_START,
        end_time=_START + candle_count * Timeframe.H4.duration,
    )


def _replace_price(candle: Candle, field_name: str, value: Decimal) -> Candle:
    match field_name:
        case "open":
            return replace(candle, open=value)
        case "high":
            return replace(candle, high=value)
        case "low":
            return replace(candle, low=value)
        case "close":
            return replace(candle, close=value)
        case _:
            raise AssertionError(f"unsupported price field: {field_name}")


@pytest.mark.parametrize("field_name", ["open", "high", "low", "close"])
@pytest.mark.parametrize("invalid_value", [Decimal("0"), Decimal("-0.01")])
def test_validate_candle_rejects_non_positive_ohlc(
    field_name: str, invalid_value: Decimal
) -> None:
    with pytest.raises(CandleValidationError, match=field_name):
        validate_candle(_replace_price(_candle(), field_name, invalid_value))


def test_validate_candle_rejects_negative_volume_but_accepts_zero() -> None:
    with pytest.raises(CandleValidationError, match="volume"):
        validate_candle(replace(_candle(), volume=Decimal("-0.01")))

    validate_candle(replace(_candle(), volume=Decimal("0")))


def test_validate_candle_requires_open_within_low_high_range() -> None:
    with pytest.raises(CandleValidationError, match="open"):
        validate_candle(replace(_candle(), open=Decimal("89")))


def test_validate_candle_requires_close_within_low_high_range() -> None:
    with pytest.raises(CandleValidationError, match="close"):
        validate_candle(replace(_candle(), close=Decimal("111")))


def test_completed_candles_marks_only_strictly_closed_rows_complete() -> None:
    candidates = tuple(_candle(index, completed=False) for index in range(3))
    server_time = candidates[1].close_time

    result = completed_candles(candidates, server_time)

    assert result == (replace(candidates[0], completed=True),)
    assert all(candle.completed for candle in result)
    assert all(not candle.completed for candle in candidates)


def test_validate_candle_sequence_accepts_exact_completed_window() -> None:
    candles = tuple(_candle(index) for index in range(3))

    validate_candle_sequence(candles, _request())


def test_validate_candle_sequence_rejects_empty_sequence() -> None:
    with pytest.raises(CandleValidationError, match="empty"):
        validate_candle_sequence((), _request())


def test_validate_candle_sequence_rejects_mixed_instrument() -> None:
    other = Instrument("BTCUSDT", "BTC", "USDT")
    candles = (_candle(0), _candle(1, instrument=other))

    with pytest.raises(CandleValidationError, match="instrument"):
        validate_candle_sequence(candles, _request(candle_count=2))


def test_validate_candle_sequence_rejects_mixed_timeframe() -> None:
    candles = (_candle(0), _candle(4, timeframe=Timeframe.H1))

    with pytest.raises(CandleValidationError, match="timeframe"):
        validate_candle_sequence(candles, _request(candle_count=2))


@pytest.mark.parametrize(
    "outside_open_time",
    [_START - Timeframe.H4.duration, _START + 2 * Timeframe.H4.duration],
)
def test_validate_candle_sequence_rejects_open_times_outside_window(
    outside_open_time: datetime,
) -> None:
    candle = replace(
        _candle(),
        open_time=outside_open_time,
        close_time=outside_open_time + Timeframe.H4.duration - timedelta(milliseconds=1),
    )

    with pytest.raises(CandleValidationError, match="window"):
        validate_candle_sequence((candle,), _request(candle_count=2))


def test_validate_candle_sequence_rejects_incomplete_canonical_candle() -> None:
    with pytest.raises(CandleValidationError, match="completed"):
        validate_candle_sequence((_candle(completed=False),), _request(candle_count=1))


def test_validate_candle_sequence_rejects_duplicate_open_time() -> None:
    first = _candle(0)

    with pytest.raises(DuplicateCandleError):
        validate_candle_sequence((first, replace(first)), _request(candle_count=2))


def test_validate_candle_sequence_rejects_reversal() -> None:
    with pytest.raises(OutOfOrderCandleError):
        validate_candle_sequence((_candle(1), _candle(0)), _request(candle_count=2))


def test_validate_candle_sequence_rejects_gap() -> None:
    with pytest.raises(CandleGapError):
        validate_candle_sequence((_candle(0), _candle(2)), _request())
