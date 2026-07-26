"""Small authentic-shaped BTCUSDT 4-hour fixture around the approved closure."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from gemini_trading.domain.candle import Candle
from gemini_trading.domain.dataset import RetrievalRequest
from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.timeframe import Timeframe

INSTRUMENT = Instrument("BTCUSDT", "BTC", "USDT")
TIMEFRAME = Timeframe.H4
REQUEST = RetrievalRequest(
    instrument=INSTRUMENT,
    timeframe=TIMEFRAME,
    start_time=datetime(2018, 1, 1, tzinfo=UTC),
    end_time=datetime(2026, 7, 1, tzinfo=UTC),
)


def _candle(open_time: datetime, value: str) -> Candle:
    price = Decimal(value)
    return Candle(
        instrument=INSTRUMENT,
        timeframe=TIMEFRAME,
        open_time=open_time,
        close_time=open_time + timedelta(hours=4) - timedelta(milliseconds=1),
        open=price,
        high=price + Decimal("10"),
        low=price - Decimal("10"),
        close=price + Decimal("2"),
        volume=Decimal("100"),
        completed=True,
        source_provider="binance_spot",
    )


CANDLES = (
    _candle(datetime(2018, 2, 7, 16, tzinfo=UTC), "8000"),
    _candle(datetime(2018, 2, 7, 20, tzinfo=UTC), "8050"),
    _candle(datetime(2018, 2, 8, 0, tzinfo=UTC), "8100"),
    _candle(datetime(2018, 2, 9, 8, tzinfo=UTC), "8200"),
    _candle(datetime(2018, 2, 9, 12, tzinfo=UTC), "8250"),
    _candle(datetime(2018, 2, 9, 16, tzinfo=UTC), "8300"),
)
