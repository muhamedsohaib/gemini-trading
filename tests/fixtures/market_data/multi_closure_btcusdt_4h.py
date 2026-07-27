"""Generated BTCUSDT 4-hour candles around all approved closure boundaries."""

from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from gemini_trading.data.exchange_closures import load_fixed_btcusdt_closure_manifest
from gemini_trading.domain.candle import Candle
from gemini_trading.domain.dataset import RetrievalRequest

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
MANIFEST, MANIFEST_BYTES = load_fixed_btcusdt_closure_manifest(_PROJECT_ROOT)
REQUEST = RetrievalRequest(
    instrument=MANIFEST.instrument,
    timeframe=MANIFEST.timeframe,
    start_time=MANIFEST.start_time,
    end_time=MANIFEST.end_time,
)
EXPECTED_BOUNDARIES = (
    18,
    227,
    1047,
    1092,
    1733,
    1887,
    2593,
    2975,
    3524,
    4062,
    4133,
    4650,
    5042,
    5425,
    6483,
    6791,
    7198,
    7228,
    7886,
    8168,
)
EXPECTED_CANDLE_COUNT = 18_582


def candle(open_time: datetime, seed: int = 0) -> Candle:
    """Build one deterministic full-timeframe completed candle."""

    price = Decimal(10_000 + seed % 100)
    return Candle(
        instrument=MANIFEST.instrument,
        timeframe=MANIFEST.timeframe,
        open_time=open_time,
        close_time=open_time + MANIFEST.timeframe.duration - timedelta(milliseconds=1),
        open=price,
        high=price + Decimal("10"),
        low=price - Decimal("10"),
        close=price + Decimal("2"),
        volume=Decimal("100"),
        completed=True,
        source_provider=MANIFEST.provider,
    )


def unavailable_opens() -> frozenset[datetime]:
    """Return every exact canonical open removed by the approved declarations."""

    return frozenset(
        closure.canonical_gap_start + offset * MANIFEST.timeframe.duration
        for closure in MANIFEST.closures
        for offset in range(closure.unavailable_candle_count)
    )


def _build_candles() -> tuple[Candle, ...]:
    unavailable = unavailable_opens()
    values: list[Candle] = []
    open_time = MANIFEST.start_time
    seed = 0
    while open_time < MANIFEST.end_time:
        if open_time not in unavailable:
            values.append(candle(open_time, seed))
            seed += 1
        open_time += MANIFEST.timeframe.duration
    return tuple(values)


CANDLES = _build_candles()
