"""Candidate v0.4 hierarchical feature-contract tests."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext

from gemini_trading.data.segments import CandleSegment, CandleSegmentManifest
from gemini_trading.domain.candle import Candle
from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.timeframe import Timeframe
from gemini_trading.strategy.features import FeatureRegistry
from gemini_trading.strategy.v0_4_context import (
    derive_v0_4_context_bars,
    join_v0_4_context,
)
from gemini_trading.strategy.v0_4_features import (
    V04FeatureRegistry,
    build_v0_4_feature_matrix,
)
from gemini_trading.strategy.v0_4_policy import V04MultiTimeframePolicy

_INSTRUMENT = Instrument("BTCUSDT", "BTC", "USDT")
_START = datetime(2025, 1, 1, tzinfo=UTC)


def _hour(index: int) -> Candle:
    opened = _START + timedelta(hours=index)
    close = Decimal("10000") + Decimal(index * 3) + Decimal((index % 7) - 3) * Decimal("0.7")
    opening = close - Decimal("1.5") + Decimal(index % 3) * Decimal("0.25")
    high = max(opening, close) + Decimal("2") + Decimal(index % 5) * Decimal("0.1")
    low = min(opening, close) - Decimal("2") - Decimal(index % 4) * Decimal("0.1")

    return Candle(
        instrument=_INSTRUMENT,
        timeframe=Timeframe.H1,
        open_time=opened,
        close_time=opened + timedelta(hours=1) - timedelta(milliseconds=1),
        open=opening,
        high=high,
        low=low,
        close=close,
        volume=Decimal("1000") + Decimal(index * 11) + Decimal(index % 9),
        completed=True,
        source_provider="binance_spot",
    )


def _hourly_candles(count: int = 220) -> tuple[Candle, ...]:
    return tuple(_hour(index) for index in range(count))


def _segments(candles: tuple[Candle, ...]) -> CandleSegmentManifest:
    return CandleSegmentManifest(
        schema_version="candle-segment-manifest-v1",
        segments=(
            CandleSegment(
                segment_number=1,
                start_index=0,
                end_exclusive=len(candles),
                first_open_time=candles[0].open_time,
                last_open_time=candles[-1].open_time,
                candle_count=len(candles),
                preceding_closure_id=None,
            ),
        ),
    )


def _matrix(candles: tuple[Candle, ...]):
    context_bars = derive_v0_4_context_bars(candles, ())
    context_join = join_v0_4_context(candles, context_bars)
    return build_v0_4_feature_matrix(
        candles,
        _segments(candles),
        context_join,
    )


def test_v0_4_registry_has_exactly_six_context_features_per_specialist() -> None:
    registry = V04FeatureRegistry.locked()
    context = V04MultiTimeframePolicy.locked().context_feature_names

    assert registry.context_feature_names == context
    assert (
        tuple(name for name in registry.trend_feature_names if name.startswith("ctx4h_")) == context
    )
    assert (
        tuple(name for name in registry.mean_reversion_feature_names if name.startswith("ctx4h_"))
        == context
    )


def test_v0_4_retains_exact_v0_1_tactical_specialist_inputs() -> None:
    legacy = FeatureRegistry.locked_v0_1()
    registry = V04FeatureRegistry.locked()
    context = registry.context_feature_names

    assert registry.trend_feature_names == (
        *legacy.trend_feature_names,
        *context,
    )
    assert registry.mean_reversion_feature_names == (
        *legacy.mean_reversion_feature_names,
        *context,
    )


def test_v0_4_tactical_dependency_remains_exactly_42_hours() -> None:
    legacy = FeatureRegistry.locked_v0_1()
    registry = V04FeatureRegistry.locked()

    # The v0.4 tactical portion is the unchanged v0.1 registry evaluated on H1.
    assert legacy.maximum_lookback_candles == 42
    assert registry.trend_feature_names[: -len(registry.context_feature_names)] == (
        legacy.trend_feature_names
    )
    assert (
        registry.mean_reversion_feature_names[: -len(registry.context_feature_names)]
        == legacy.mean_reversion_feature_names
    )


def test_v0_4_specialist_inputs_do_not_contain_categorical_regime_feature() -> None:
    registry = V04FeatureRegistry.locked()

    all_specialist_names = (
        *registry.trend_feature_names,
        *registry.mean_reversion_feature_names,
    )

    assert "regime" not in all_specialist_names
    assert "regime_class" not in all_specialist_names
    assert "regime_label" not in all_specialist_names


def test_v0_4_matrix_appends_only_the_six_context_columns() -> None:
    candles = _hourly_candles()
    matrix = _matrix(candles)

    legacy = FeatureRegistry.locked_v0_1()
    context = V04MultiTimeframePolicy.locked().context_feature_names

    assert matrix.feature_names == (
        *legacy.feature_names,
        *context,
    )


def test_future_hourly_mutation_cannot_change_any_earlier_v0_4_feature_row() -> None:
    candles = _hourly_candles()
    first = _matrix(candles)

    final = candles[-1]
    changed = (
        *candles[:-1],
        replace(
            final,
            open=final.open + Decimal("500"),
            high=final.high + Decimal("1000"),
            low=final.low - Decimal("500"),
            close=final.close + Decimal("750"),
            volume=final.volume + Decimal("999999"),
        ),
    )
    second = _matrix(changed)

    # Candle 219 itself may change its tactical feature vector.
    # No earlier decision row may change.
    assert first.row_for(218) == second.row_for(218)
    assert first.row_for(219) != second.row_for(219)


def test_v0_4_feature_matrix_is_deterministic() -> None:
    candles = _hourly_candles()

    first = _matrix(candles)
    second = _matrix(tuple(replace(candle) for candle in candles))

    assert first == second


def _flat_context_hour(index: int) -> Candle:
    """Keep completed 4h closes flat while preserving non-degenerate hourly motion."""

    closes = (
        Decimal("10002"),
        Decimal("9998"),
        Decimal("10001"),
        Decimal("10000"),
    )
    close = closes[index % 4]
    base = _hour(index)
    return replace(
        base,
        open=close - Decimal("1"),
        high=close + Decimal("3"),
        low=close - Decimal("3"),
        close=close,
        volume=Decimal("1500") + Decimal(index * 13),
    )


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


def test_v0_4_context_values_match_exact_completed_4h_formulas() -> None:
    candles = _hourly_candles()
    context_bars = derive_v0_4_context_bars(candles, ())
    context_join = join_v0_4_context(candles, context_bars)

    matrix = build_v0_4_feature_matrix(
        candles,
        _segments(candles),
        context_join,
    )

    decision_index = 200
    observation = context_join[decision_index]
    assert observation is not None

    context_index = next(
        index
        for index, item in enumerate(context_bars)
        if item.constituent_sha256 == observation.constituent_sha256
    )

    context_matrix = FeatureRegistry.locked_v0_1().compute(
        tuple(item.candle for item in context_bars)
    )

    atr24 = context_matrix.value_for(context_index, "atr_24")
    ema_spread_close = context_matrix.value_for(
        context_index,
        "ema_spread_12_42",
    )
    trend_strength = context_matrix.value_for(
        context_index,
        "trend_strength_12_42_atr24",
    )

    if ema_spread_close > 0:
        signed_spread = trend_strength
    elif ema_spread_close < 0:
        signed_spread = -trend_strength
    else:
        signed_spread = Decimal("0")

    with localcontext(Context(prec=34, rounding=ROUND_HALF_EVEN)):
        ema12_slope = (
            context_matrix.value_for(context_index, "ema_slope_12_3")
            * observation.candle.close
            / atr24
        )

    expected = (
        signed_spread,
        context_matrix.value_for(
            context_index,
            "volatility_ratio_6_42",
        ),
        context_matrix.value_for(
            context_index,
            "true_range_ratio_24",
        ),
        context_matrix.value_for(
            context_index,
            "rolling_close_location_24",
        ),
        context_matrix.value_for(
            context_index,
            "median_atr_distance_24",
        ),
        ema12_slope,
    )

    names = V04MultiTimeframePolicy.locked().context_feature_names
    actual = tuple(matrix.value_for(decision_index, name) for name in names)

    assert actual == expected


def test_v0_4_insufficient_completed_4h_history_makes_rows_ineligible() -> None:
    candles = _hourly_candles(160)

    tactical = FeatureRegistry.locked_v0_1().compute(
        candles,
        segments=_segments(candles),
    )
    assert tactical.rows

    matrix = _matrix(candles)

    # 160 completed hours provide only 40 completed 4h bars.
    # Context requires the locked 42-bar history and must not be imputed.
    assert matrix.rows == ()


def test_v0_4_zero_context_denominator_is_not_imputed() -> None:
    candles = tuple(_flat_context_hour(index) for index in range(220))

    tactical = FeatureRegistry.locked_v0_1().compute(
        candles,
        segments=_segments(candles),
    )
    assert tactical.rows

    context_bars = derive_v0_4_context_bars(candles, ())
    assert len(context_bars) == 55
    assert len({item.candle.close for item in context_bars}) == 1

    matrix = build_v0_4_feature_matrix(
        candles,
        _segments(candles),
        join_v0_4_context(candles, context_bars),
    )

    # Flat completed 4h closes make rv42 zero. No context value is imputed.
    assert matrix.rows == ()


def test_v0_4_context_warmup_restarts_after_verified_segment_boundary() -> None:
    candles = _hourly_candles(400)
    split = 200
    segments = _two_segments(candles, split)

    context_bars = derive_v0_4_context_bars(
        candles,
        segments.boundary_indices,
    )
    context_join = join_v0_4_context(candles, context_bars)

    matrix = build_v0_4_feature_matrix(
        candles,
        segments,
        context_join,
    )

    second_segment_rows = tuple(
        row.candle_index for row in matrix.rows if row.candle_index >= split
    )

    # Segment 2 starts at hour 200. The first independently warmed
    # 42-history context bar is [368,372), visible to the 372 decision.
    assert second_segment_rows
    assert min(second_segment_rows) == 372


def _constant_context_volume_hour(index: int) -> Candle:
    """Vary 1h volume while making every derived 4h volume identical."""

    base = _hour(index)
    volumes = (
        Decimal("100"),
        Decimal("200"),
        Decimal("300"),
        Decimal("400"),
    )
    return replace(
        base,
        volume=volumes[index % 4],
    )


def test_v0_4_context_eligibility_ignores_unrelated_constant_volume() -> None:
    candles = tuple(_constant_context_volume_hour(index) for index in range(220))

    # Tactical 1h volume remains non-degenerate.
    tactical = FeatureRegistry.locked_v0_1().compute(
        candles,
        segments=_segments(candles),
    )
    assert tactical.rows

    context_bars = derive_v0_4_context_bars(candles, ())

    # Every completed 4h context bar has identical aggregate volume.
    assert context_bars
    assert {item.candle.volume for item in context_bars} == {Decimal("1000")}

    matrix = build_v0_4_feature_matrix(
        candles,
        _segments(candles),
        join_v0_4_context(candles, context_bars),
    )

    # Volume is not one of the six v0.4 context features.
    # Constant context volume must therefore not invalidate otherwise
    # eligible context observations.
    assert matrix.rows
    assert 200 in tuple(row.candle_index for row in matrix.rows)
