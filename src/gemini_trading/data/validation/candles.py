"""Pure validation for canonical candle candidates and sequences."""

from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime

from gemini_trading.data.errors import (
    CandleGapError,
    CandleValidationError,
    DuplicateCandleError,
    OutOfOrderCandleError,
)
from gemini_trading.domain.candle import Candle
from gemini_trading.domain.dataset import RetrievalRequest


def validate_candle(candle: Candle) -> None:
    """Validate canonical OHLCV geometry without provider or storage concerns."""

    for field_name, value in (
        ("open", candle.open),
        ("high", candle.high),
        ("low", candle.low),
        ("close", candle.close),
    ):
        if value <= 0:
            raise CandleValidationError(f"{field_name} must be positive")

    if candle.volume < 0:
        raise CandleValidationError("volume must be non-negative")
    if not candle.low <= candle.open <= candle.high:
        raise CandleValidationError("open must be within low and high")
    if not candle.low <= candle.close <= candle.high:
        raise CandleValidationError("close must be within low and high")


def completed_candles(
    candles: Sequence[Candle],
    server_time: datetime,
) -> tuple[Candle, ...]:
    """Return only candles strictly closed before the shared server-time snapshot."""

    return tuple(
        replace(candle, completed=True) for candle in candles if candle.close_time < server_time
    )


def validate_candle_sequence(
    candles: Sequence[Candle],
    request: RetrievalRequest,
) -> None:
    """Validate one completed canonical sequence in the required fail-closed order."""

    if not candles:
        raise CandleValidationError("candle sequence must not be empty")

    for candle in candles:
        validate_candle(candle)

    for candle in candles:
        if candle.instrument != request.instrument:
            raise CandleValidationError("candle instrument does not match request")
        if candle.timeframe != request.timeframe:
            raise CandleValidationError("candle timeframe does not match request")

    for candle in candles:
        if not request.start_time <= candle.open_time < request.end_time:
            raise CandleValidationError("candle open_time is outside the request window")

    for candle in candles:
        if not candle.completed:
            raise CandleValidationError("canonical candle must be completed")

    seen_open_times: set[datetime] = set()
    for candle in candles:
        if candle.open_time in seen_open_times:
            raise DuplicateCandleError("duplicate candle open_time")
        seen_open_times.add(candle.open_time)

    previous_open_time = candles[0].open_time
    for candle in candles[1:]:
        if candle.open_time <= previous_open_time:
            raise OutOfOrderCandleError("candle open_time must be strictly increasing")
        previous_open_time = candle.open_time

    previous_open_time = candles[0].open_time
    for candle in candles[1:]:
        expected_open_time = previous_open_time + request.timeframe.duration
        if candle.open_time != expected_open_time:
            raise CandleGapError("candle sequence contains a timeframe gap")
        previous_open_time = candle.open_time
