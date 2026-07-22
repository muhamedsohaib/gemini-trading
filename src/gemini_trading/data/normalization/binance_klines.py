"""Strict normalization for public Binance Spot kline payloads."""

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import NoReturn, cast

from gemini_trading.data.errors import ProviderSchemaError
from gemini_trading.domain.candle import Candle
from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.timeframe import Timeframe

_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
_MINIMUM_ROW_FIELDS = 7
_SOURCE_PROVIDER = "binance_spot"


def _reject_json_constant(_value: str) -> NoReturn:
    raise ValueError("non-standard JSON constant")


def _decode_payload(payload: bytes) -> object:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        raise ProviderSchemaError("Binance kline payload is not valid UTF-8") from None

    try:
        return cast(
            object,
            json.loads(
                text,
                parse_float=str,
                parse_constant=_reject_json_constant,
            ),
        )
    except (json.JSONDecodeError, ValueError):
        raise ProviderSchemaError("Binance kline payload is not valid JSON") from None


def _milliseconds_to_datetime(value: object) -> datetime:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ProviderSchemaError("Binance kline timestamps must be integer milliseconds")

    try:
        return _EPOCH + timedelta(milliseconds=value)
    except (OverflowError, ValueError):
        raise ProviderSchemaError(
            "Binance kline timestamp is outside the supported range"
        ) from None


def _finite_decimal(value: object) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ProviderSchemaError("Binance kline numeric fields must be finite decimals")

    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ProviderSchemaError("Binance kline numeric fields must be finite decimals") from None

    if not decimal_value.is_finite():
        raise ProviderSchemaError("Binance kline numeric fields must be finite decimals")
    return decimal_value


def normalize_binance_klines(
    payload: bytes,
    instrument: Instrument,
    timeframe: Timeframe,
) -> tuple[Candle, ...]:
    """Normalize exact Binance response bytes into immutable candle candidates."""

    decoded = _decode_payload(payload)
    if not isinstance(decoded, list):
        raise ProviderSchemaError("Binance kline payload root must be a list")

    rows = cast(list[object], decoded)
    candles: list[Candle] = []
    for item in rows:
        if not isinstance(item, list) or len(item) < _MINIMUM_ROW_FIELDS:
            raise ProviderSchemaError("Binance kline row must contain at least 7 fields")
        row = cast(list[object], item)

        try:
            candle = Candle(
                instrument=instrument,
                timeframe=timeframe,
                open_time=_milliseconds_to_datetime(row[0]),
                close_time=_milliseconds_to_datetime(row[6]),
                open=_finite_decimal(row[1]),
                high=_finite_decimal(row[2]),
                low=_finite_decimal(row[3]),
                close=_finite_decimal(row[4]),
                volume=_finite_decimal(row[5]),
                completed=False,
                source_provider=_SOURCE_PROVIDER,
            )
        except ValueError:
            raise ProviderSchemaError("Binance kline row violates the candle schema") from None
        candles.append(candle)

    return tuple(candles)
