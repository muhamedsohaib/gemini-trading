from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from gemini_trading.domain.candle import Candle
from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.timeframe import Timeframe


def _valid_candle() -> Candle:
    return Candle(
        instrument=Instrument("ETHUSDT", "ETH", "USDT"),
        timeframe=Timeframe.H4,
        open_time=datetime(2025, 1, 1, tzinfo=UTC),
        close_time=datetime(2025, 1, 1, 3, 59, 59, 999000, tzinfo=UTC),
        open=Decimal("100.00"),
        high=Decimal("110.00"),
        low=Decimal("90.00"),
        close=Decimal("105.00"),
        volume=Decimal("12.5000"),
        completed=True,
        source_provider="binance_spot",
    )


def test_candle_is_immutable() -> None:
    candle = _valid_candle()

    with pytest.raises(FrozenInstanceError):
        candle.close = Decimal("1")  # type: ignore[misc]


def test_candle_rejects_naive_or_non_utc_timestamps() -> None:
    candle = _valid_candle()

    with pytest.raises(ValueError, match="UTC-aware"):
        replace(candle, open_time=datetime(2025, 1, 1))

    with pytest.raises(ValueError, match="UTC-aware"):
        replace(
            candle,
            open_time=datetime(2025, 1, 1, tzinfo=timezone(timedelta(hours=4))),
        )


def test_candle_requires_increasing_millisecond_aligned_times() -> None:
    candle = _valid_candle()

    with pytest.raises(ValueError, match="later than"):
        replace(candle, close_time=candle.open_time)

    with pytest.raises(ValueError, match="millisecond-aligned"):
        replace(candle, open_time=candle.open_time.replace(microsecond=1))


def test_candle_rejects_non_finite_decimals() -> None:
    candle = _valid_candle()

    with pytest.raises(ValueError, match="finite"):
        replace(candle, close=Decimal("NaN"))


def test_candle_requires_non_empty_provider() -> None:
    candle = _valid_candle()

    with pytest.raises(ValueError, match="source_provider"):
        replace(candle, source_provider="   ")
