"""UTF-8 serialization contract for canonical candle datasets."""

from datetime import UTC, datetime
from decimal import Decimal

from gemini_trading.data.datasets.canonical_writer import serialize_candles
from gemini_trading.domain.candle import Candle
from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.timeframe import Timeframe


def test_canonical_json_preserves_utf8_text_without_ascii_escaping() -> None:
    candle = Candle(
        instrument=Instrument("ETHUSDT", "ETH", "USDT"),
        timeframe=Timeframe.H4,
        open_time=datetime(2025, 1, 1, tzinfo=UTC),
        close_time=datetime(2025, 1, 1, 3, 59, 59, 999000, tzinfo=UTC),
        open=Decimal("100.00"),
        high=Decimal("110.00"),
        low=Decimal("90.00"),
        close=Decimal("105.00"),
        volume=Decimal("12.3400"),
        completed=True,
        source_provider="binancé",
    )

    canonical = serialize_candles((candle,))

    assert b'"source_provider":"binanc\xc3\xa9"' in canonical
    assert b"\\u00e9" not in canonical
