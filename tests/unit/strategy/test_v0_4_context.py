"""Candidate v0.4 deterministic completed 4h context tests."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from gemini_trading.domain.candle import Candle
from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.timeframe import Timeframe
from gemini_trading.research.serialization import canonical_json_bytes
from gemini_trading.strategy.v0_4_context import (
    ContextObservation,
    DerivedContextBar,
    derive_v0_4_context_bars,
    join_v0_4_context,
)

_INSTRUMENT = Instrument("BTCUSDT", "BTC", "USDT")
_OTHER_INSTRUMENT = Instrument("ETHUSDT", "ETH", "USDT")
_START = datetime(2025, 1, 1, tzinfo=UTC)


def _hour(
    index: int,
    *,
    open_price: str = "100",
    high: str = "110",
    low: str = "90",
    close: str = "105",
    volume: str = "10",
    completed: bool = True,
    instrument: Instrument = _INSTRUMENT,
    timeframe: Timeframe = Timeframe.H1,
) -> Candle:
    open_time = _START + timedelta(hours=index)
    return Candle(
        instrument=instrument,
        timeframe=timeframe,
        open_time=open_time,
        close_time=open_time + timedelta(hours=1) - timedelta(milliseconds=1),
        open=Decimal(open_price),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=Decimal(volume),
        completed=completed,
        source_provider="binance_spot",
    )


def _first_four() -> tuple[Candle, Candle, Candle, Candle]:
    return (
        _hour(
            0,
            open_price="100",
            high="104",
            low="98",
            close="102",
            volume="10",
        ),
        _hour(
            1,
            open_price="102",
            high="106",
            low="101",
            close="105",
            volume="11",
        ),
        _hour(
            2,
            open_price="105",
            high="109",
            low="104",
            close="108",
            volume="12",
        ),
        _hour(
            3,
            open_price="108",
            high="109",
            low="106",
            close="107",
            volume="13",
        ),
    )


def _expected_constituent_sha256(
    candles: tuple[Candle, ...],
    indices: tuple[int, int, int, int],
) -> str:
    payload: dict[str, object] = {
        "constituents": [
            {
                "index": index,
                "open_time": candles[index].open_time,
                "open": candles[index].open,
                "high": candles[index].high,
                "low": candles[index].low,
                "close": candles[index].close,
                "volume": candles[index].volume,
            }
            for index in indices
        ]
    }
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def _context_inventory_bytes(bars: tuple[DerivedContextBar, ...]) -> bytes:
    payload: dict[str, object] = {
        "bars": [
            {
                "open_time": item.candle.open_time,
                "close_time": item.candle.close_time,
                "open": item.candle.open,
                "high": item.candle.high,
                "low": item.candle.low,
                "close": item.candle.close,
                "volume": item.candle.volume,
                "timeframe": item.candle.timeframe.value,
                "constituent_indices": list(item.constituent_indices),
                "constituent_sha256": item.constituent_sha256,
            }
            for item in bars
        ]
    }
    return canonical_json_bytes(payload)


def test_context_bar_uses_exactly_four_completed_hourly_constituents() -> None:
    candles = _first_four()

    bars = derive_v0_4_context_bars(candles, ())

    assert len(bars) == 1
    derived = bars[0]
    assert isinstance(derived, DerivedContextBar)

    bar = derived.candle
    assert bar.instrument == _INSTRUMENT
    assert bar.timeframe is Timeframe.H4
    assert bar.open_time == _START
    assert bar.close_time == _START + timedelta(hours=4) - timedelta(milliseconds=1)
    assert bar.open == Decimal("100")
    assert bar.high == Decimal("109")
    assert bar.low == Decimal("98")
    assert bar.close == Decimal("107")
    assert bar.volume == Decimal("46")
    assert bar.completed is True

    assert derived.constituent_indices == (0, 1, 2, 3)
    assert derived.constituent_sha256 == _expected_constituent_sha256(
        candles,
        (0, 1, 2, 3),
    )


def test_context_is_not_visible_until_the_next_utc_hour_after_context_close() -> None:
    candles = (
        *_first_four(),
        *(_hour(index) for index in range(4, 9)),
    )

    bars = derive_v0_4_context_bars(candles, ())
    joined = join_v0_4_context(candles, bars)

    assert len(bars) == 2

    # [00:00, 04:00) must not be visible to the 03:00 decision row.
    assert joined[2] is None
    assert joined[3] is None

    # It becomes visible to the 04:00 decision row.
    first = joined[4]
    assert isinstance(first, ContextObservation)
    assert first.candle == bars[0].candle
    assert first.constituent_indices == (0, 1, 2, 3)
    assert first.constituent_sha256 == bars[0].constituent_sha256
    assert first.candle.close_time <= candles[4].open_time

    # The future [04:00, 08:00) context is still unavailable at 07:00.
    assert joined[7] == first

    # It becomes visible only at the 08:00 decision row.
    second = joined[8]
    assert isinstance(second, ContextObservation)
    assert second.candle == bars[1].candle
    assert second.constituent_indices == (4, 5, 6, 7)
    assert second.candle.close_time <= candles[8].open_time

    for candle, observation in zip(candles, joined, strict=True):
        if observation is not None:
            assert observation.candle.close_time <= candle.open_time


def test_partial_or_incomplete_four_hour_block_is_not_derived() -> None:
    partial = tuple(_hour(index) for index in range(3))
    assert derive_v0_4_context_bars(partial, ()) == ()

    complete = tuple(_hour(index) for index in range(4))
    incomplete = (
        *complete[:3],
        replace(complete[3], completed=False),
    )
    assert derive_v0_4_context_bars(incomplete, ()) == ()


def test_four_hour_block_must_be_utc_aligned() -> None:
    shifted = tuple(_hour(index) for index in range(1, 5))

    assert derive_v0_4_context_bars(shifted, ()) == ()


def test_context_bar_never_crosses_a_verified_segment_boundary() -> None:
    candles = tuple(_hour(index) for index in range(8))

    bars = derive_v0_4_context_bars(candles, (2,))

    # The aligned 00:00 group crosses boundary index 2 and is invalid.
    # The aligned 04:00 group lies wholly after that boundary and is valid.
    assert len(bars) == 1
    assert bars[0].constituent_indices == (4, 5, 6, 7)
    assert bars[0].candle.open_time == _START + timedelta(hours=4)


def test_context_derivation_rejects_duplicate_or_out_of_order_hours() -> None:
    candles = tuple(_hour(index) for index in range(4))

    duplicate = (
        candles[0],
        candles[1],
        replace(candles[1]),
        candles[3],
    )
    with pytest.raises(ValueError, match="strictly increasing"):
        derive_v0_4_context_bars(duplicate, ())

    reversed_hours = (
        candles[0],
        candles[2],
        candles[1],
        candles[3],
    )
    with pytest.raises(ValueError, match="strictly increasing"):
        derive_v0_4_context_bars(reversed_hours, ())


def test_context_derivation_rejects_mixed_instruments_and_timeframes() -> None:
    candles = tuple(_hour(index) for index in range(4))

    mixed_instrument = (
        candles[0],
        replace(candles[1], instrument=_OTHER_INSTRUMENT),
        candles[2],
        candles[3],
    )
    with pytest.raises(ValueError, match="instrument"):
        derive_v0_4_context_bars(mixed_instrument, ())

    mixed_timeframe = (
        candles[0],
        replace(candles[1], timeframe=Timeframe.H4),
        candles[2],
        candles[3],
    )
    with pytest.raises(ValueError, match="1h"):
        derive_v0_4_context_bars(mixed_timeframe, ())


def test_context_derivation_and_join_are_deterministic() -> None:
    candles = tuple(_hour(index) for index in range(9))
    replayed = tuple(replace(candle) for candle in candles)

    first_bars = derive_v0_4_context_bars(candles, ())
    second_bars = derive_v0_4_context_bars(replayed, ())

    assert first_bars == second_bars
    assert _context_inventory_bytes(first_bars) == _context_inventory_bytes(second_bars)

    first_join = join_v0_4_context(candles, first_bars)
    second_join = join_v0_4_context(replayed, second_bars)

    assert first_join == second_join
