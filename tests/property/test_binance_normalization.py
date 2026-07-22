import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from gemini_trading.data.errors import ProviderSchemaError
from gemini_trading.data.normalization.binance_klines import normalize_binance_klines
from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.timeframe import Timeframe

_INSTRUMENT = Instrument("ETHUSDT", "ETH", "USDT")
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
_DECIMAL_TEXT = st.from_regex(r"[1-9][0-9]{0,8}\.[0-9]{1,8}", fullmatch=True)
_INVALID_MILLISECONDS = st.one_of(
    st.none(),
    st.booleans(),
    st.floats(allow_nan=False, allow_infinity=False),
    st.text(max_size=30),
)


def _payload(
    open_time: object,
    close_time: object,
    decimal_text: str = "100.00",
) -> bytes:
    row = [
        open_time,
        decimal_text,
        decimal_text,
        decimal_text,
        decimal_text,
        decimal_text,
        close_time,
    ]
    return json.dumps([row], separators=(",", ":")).encode("utf-8")


@given(open_ms=st.integers(min_value=0, max_value=253_402_300_799_998))
def test_integer_milliseconds_round_trip_without_float_precision_loss(open_ms: int) -> None:
    close_ms = open_ms + 1

    candle = normalize_binance_klines(
        _payload(open_ms, close_ms),
        _INSTRUMENT,
        Timeframe.H4,
    )[0]

    assert candle.open_time == _EPOCH + timedelta(milliseconds=open_ms)
    assert candle.close_time == _EPOCH + timedelta(milliseconds=close_ms)


@given(decimal_text=_DECIMAL_TEXT)
def test_decimal_text_preserves_exact_value_and_exponent(decimal_text: str) -> None:
    candle = normalize_binance_klines(
        _payload(1_735_689_600_000, 1_735_703_999_999, decimal_text),
        _INSTRUMENT,
        Timeframe.H4,
    )[0]
    expected = Decimal(decimal_text)

    assert candle.open == expected
    assert candle.open.as_tuple().exponent == expected.as_tuple().exponent
    assert candle.volume == expected
    assert candle.volume.as_tuple().exponent == expected.as_tuple().exponent


@given(invalid_timestamp=_INVALID_MILLISECONDS)
def test_non_integer_open_milliseconds_always_raise_schema_error(
    invalid_timestamp: object,
) -> None:
    with pytest.raises(ProviderSchemaError):
        normalize_binance_klines(
            _payload(invalid_timestamp, 1_735_703_999_999),
            _INSTRUMENT,
            Timeframe.H4,
        )
