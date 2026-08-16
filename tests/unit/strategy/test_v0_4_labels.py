"""Candidate v0.4 hourly label-contract tests."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from gemini_trading.data.segments import CandleSegment, CandleSegmentManifest
from gemini_trading.domain.candle import Candle
from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.timeframe import Timeframe
from gemini_trading.strategy.labels import build_labels, label_exit_offset
from gemini_trading.strategy.policy import CandidatePolicy
from strategy_fixture_support import base_simulation

_INSTRUMENT = Instrument("BTCUSDT", "BTC", "USDT")
_START = datetime(2025, 1, 1, tzinfo=UTC)


def _hour(index: int) -> Candle:
    opened = _START + timedelta(hours=index)
    opening = Decimal("10000") + Decimal(index * 25)
    close = opening + Decimal("5") + Decimal(index % 3)

    return Candle(
        instrument=_INSTRUMENT,
        timeframe=Timeframe.H1,
        open_time=opened,
        close_time=opened + timedelta(hours=1) - timedelta(milliseconds=1),
        open=opening,
        high=close + Decimal("10"),
        low=opening - Decimal("10"),
        close=close,
        volume=Decimal("1000") + Decimal(index * 7),
        completed=True,
        source_provider="binance_spot",
    )


def _candles(count: int = 90) -> tuple[Candle, ...]:
    return tuple(_hour(index) for index in range(count))


def _two_segments(
    candles: tuple[Candle, ...],
    split: int,
) -> CandleSegmentManifest:
    return CandleSegmentManifest(
        schema_version="candle-segment-manifest-v1",
        segments=(
            CandleSegment(
                segment_number=1,
                start_index=0,
                end_exclusive=split,
                first_open_time=candles[0].open_time,
                last_open_time=candles[split - 1].open_time,
                candle_count=split,
                preceding_closure_id=None,
            ),
            CandleSegment(
                segment_number=2,
                start_index=split,
                end_exclusive=len(candles),
                first_open_time=candles[split].open_time,
                last_open_time=candles[-1].open_time,
                candle_count=len(candles) - split,
                preceding_closure_id="test-closure",
            ),
        ),
    )


def test_v0_4_positive_label_uses_next_hour_entry_and_twelve_hour_horizon() -> None:
    candles = _candles()
    simulation = base_simulation()
    policy = CandidatePolicy.locked_v0_4()

    labels = build_labels(
        candles,
        simulation,
        policy,
        eligible_indices=(50,),
    )
    label = labels.for_index(50)

    round_trip_market_cost_bps = (
        simulation.taker_fee_rate * Decimal("10000")
        + simulation.half_spread_bps
        + simulation.slippage_bps
    ) * Decimal("2")

    assert labels.horizon_candles == 12
    assert label.decision_candle_index == 50
    assert label.entry_candle_index == 51
    assert label.exit_candle_index == 63
    assert label.entry_reference_price == candles[51].open
    assert label.exit_reference_price == candles[63].open
    assert label.hurdle_bps == (round_trip_market_cost_bps + policy.cost_hurdle_extra_bps)
    assert label.positive


def test_v0_4_label_exit_offset_is_derived_from_next_candle_plus_horizon() -> None:
    assert label_exit_offset(CandidatePolicy.locked_v0_3()) == 4
    assert label_exit_offset(CandidatePolicy.locked_v0_4()) == 13


def test_v0_4_candles_after_exit_cannot_change_prior_label() -> None:
    candles = _candles()
    simulation = base_simulation()
    policy = CandidatePolicy.locked_v0_4()

    original = build_labels(
        candles,
        simulation,
        policy,
        eligible_indices=(50,),
    ).for_index(50)

    final = candles[-1]
    changed = (
        *candles[:-1],
        replace(
            final,
            open=Decimal("500000"),
            high=Decimal("500100"),
            low=Decimal("499900"),
            close=Decimal("500050"),
        ),
    )

    replayed = build_labels(
        changed,
        simulation,
        policy,
        eligible_indices=(50,),
    ).for_index(50)

    assert replayed == original


def test_v0_4_label_path_cannot_cross_verified_segment_boundary() -> None:
    candles = _candles()
    simulation = base_simulation()
    policy = CandidatePolicy.locked_v0_4()
    segments = _two_segments(candles, 60)

    labels = build_labels(
        candles,
        simulation,
        policy,
        eligible_indices=(50, 64),
        segments=segments,
    )

    # Decision 50 enters at 51 and exits at 63, crossing the boundary at 60.
    # Decision 64 enters/exits wholly inside segment 2.
    assert tuple(item.decision_candle_index for item in labels.observations) == (64,)


def test_candidate_label_builder_preserves_v0_3_three_candle_timing() -> None:
    candles = _candles()
    policy = CandidatePolicy.locked_v0_3()

    labels = build_labels(
        candles,
        base_simulation(),
        policy,
        eligible_indices=(50,),
    )
    label = labels.for_index(50)

    assert labels.horizon_candles == 3
    assert label.entry_candle_index == 51
    assert label.exit_candle_index == 54
