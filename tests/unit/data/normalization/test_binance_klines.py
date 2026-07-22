import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from gemini_trading.data.errors import ProviderSchemaError
from gemini_trading.data.normalization.binance_klines import normalize_binance_klines
from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.timeframe import Timeframe

_FIXTURE_DIR = Path(__file__).parents[3] / "fixtures" / "binance_spot"
_INSTRUMENT = Instrument("ETHUSDT", "ETH", "USDT")
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
_OPEN_MS = 1_735_689_600_000
_CLOSE_MS = 1_735_703_999_999


def _row(
    *,
    open_time: object = _OPEN_MS,
    close_time: object = _CLOSE_MS,
) -> list[object]:
    return [
        open_time,
        "100.1200",
        "110.000",
        "90.5000",
        "105.3400",
        "12.500",
        close_time,
    ]


def _payload(row: list[object]) -> bytes:
    return json.dumps([row], separators=(",", ":")).encode("utf-8")


def test_normalize_binance_klines_maps_valid_fixture_exactly() -> None:
    candles = normalize_binance_klines(
        (_FIXTURE_DIR / "klines_valid_single_page.json").read_bytes(),
        _INSTRUMENT,
        Timeframe.H4,
    )

    assert len(candles) == 2
    first = candles[0]
    assert first.instrument == _INSTRUMENT
    assert first.timeframe is Timeframe.H4
    assert first.open_time == _EPOCH + timedelta(milliseconds=_OPEN_MS)
    assert first.close_time == _EPOCH + timedelta(milliseconds=_CLOSE_MS)
    assert first.open == Decimal("100.1200")
    assert first.open.as_tuple().exponent == -4
    assert first.high == Decimal("110.000")
    assert first.low == Decimal("90.5000")
    assert first.close == Decimal("105.3400")
    assert first.volume == Decimal("12.500")
    assert first.volume.as_tuple().exponent == -3
    assert first.completed is False
    assert first.source_provider == "binance_spot"


def test_normalize_binance_klines_rejects_short_row_fixture() -> None:
    with pytest.raises(ProviderSchemaError, match="row"):
        normalize_binance_klines(
            (_FIXTURE_DIR / "klines_malformed_shape.json").read_bytes(),
            _INSTRUMENT,
            Timeframe.H4,
        )


def test_normalize_binance_klines_rejects_invalid_decimal_without_leaking_payload() -> None:
    with pytest.raises(ProviderSchemaError, match="decimal") as exc_info:
        normalize_binance_klines(
            (_FIXTURE_DIR / "klines_invalid_decimal.json").read_bytes(),
            _INSTRUMENT,
            Timeframe.H4,
        )

    assert "PRIVATE-DECIMAL-MARKER" not in str(exc_info.value)


def test_normalize_binance_klines_rejects_invalid_utf8_without_leaking_payload() -> None:
    payload = b"\xffPRIVATE-UTF8-MARKER"

    with pytest.raises(ProviderSchemaError, match="UTF-8") as exc_info:
        normalize_binance_klines(payload, _INSTRUMENT, Timeframe.H4)

    assert "PRIVATE-UTF8-MARKER" not in str(exc_info.value)


def test_normalize_binance_klines_rejects_invalid_json_without_leaking_payload() -> None:
    payload = b'["PRIVATE-JSON-MARKER"'

    with pytest.raises(ProviderSchemaError, match="JSON") as exc_info:
        normalize_binance_klines(payload, _INSTRUMENT, Timeframe.H4)

    assert "PRIVATE-JSON-MARKER" not in str(exc_info.value)


def test_normalize_binance_klines_rejects_non_list_root_without_leaking_payload() -> None:
    payload = b'{"data":"PRIVATE-ROOT-MARKER"}'

    with pytest.raises(ProviderSchemaError, match="root") as exc_info:
        normalize_binance_klines(payload, _INSTRUMENT, Timeframe.H4)

    assert "PRIVATE-ROOT-MARKER" not in str(exc_info.value)


def test_normalize_binance_klines_rejects_non_list_row() -> None:
    with pytest.raises(ProviderSchemaError, match="row"):
        normalize_binance_klines(b'[{"not":"a-row"}]', _INSTRUMENT, Timeframe.H4)


@pytest.mark.parametrize("timestamp_index", [0, 6])
@pytest.mark.parametrize("timestamp_value", ["1735689600000", 1735689600000.0, True, None])
def test_normalize_binance_klines_rejects_non_integer_milliseconds(
    timestamp_index: int,
    timestamp_value: object,
) -> None:
    row = _row()
    row[timestamp_index] = timestamp_value

    with pytest.raises(ProviderSchemaError, match="milliseconds"):
        normalize_binance_klines(_payload(row), _INSTRUMENT, Timeframe.H4)


@pytest.mark.parametrize("field_index", range(1, 6))
@pytest.mark.parametrize("invalid_value", ["NaN", "Infinity", "-Infinity"])
def test_normalize_binance_klines_rejects_non_finite_decimals(
    field_index: int,
    invalid_value: str,
) -> None:
    row = _row()
    row[field_index] = invalid_value

    with pytest.raises(ProviderSchemaError, match="finite decimal"):
        normalize_binance_klines(_payload(row), _INSTRUMENT, Timeframe.H4)


def test_normalize_binance_klines_converts_large_integer_milliseconds_exactly() -> None:
    open_ms = 253_402_300_000_001
    close_ms = open_ms + 1

    candle = normalize_binance_klines(
        _payload(_row(open_time=open_ms, close_time=close_ms)),
        _INSTRUMENT,
        Timeframe.H4,
    )[0]

    assert candle.open_time == _EPOCH + timedelta(milliseconds=open_ms)
    assert candle.close_time == _EPOCH + timedelta(milliseconds=close_ms)
    assert candle.open_time.microsecond == 1_000
