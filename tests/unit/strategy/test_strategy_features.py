"""RED tests for the locked point-in-time feature registry."""

from dataclasses import replace
from decimal import Decimal

from gemini_trading.data.segments import CandleSegment, CandleSegmentManifest
from gemini_trading.domain.candle import Candle
from gemini_trading.strategy.features import FeatureRegistry
from strategy_fixture_support import rising_candles


def test_first_eligible_feature_row_is_index_42() -> None:
    matrix = FeatureRegistry.locked_v0_1().compute(rising_candles(50))

    assert matrix.rows[0].candle_index == 42
    assert matrix.rows[-1].candle_index == 49
    assert len(matrix.rows) == 8
    assert matrix.feature_names == tuple(definition.name for definition in matrix.definitions)
    assert all(value.is_finite() for row in matrix.rows for value in row.values)


def test_future_mutation_cannot_change_prior_feature_row() -> None:
    candles = rising_candles(60)
    registry = FeatureRegistry.locked_v0_1()
    first = registry.compute(candles)
    final = candles[-1]
    changed = (
        *candles[:-1],
        replace(
            final,
            high=Decimal("999999"),
            close=Decimal("999990"),
            volume=Decimal("99999999"),
        ),
    )
    second = registry.compute(changed)

    assert first.row_for(58) == second.row_for(58)
    assert first.row_for(59) != second.row_for(59)


def test_specialist_feature_sets_are_closed_registry_subsets() -> None:
    registry = FeatureRegistry.locked_v0_1()
    registered = set(registry.feature_names)

    assert registry.maximum_lookback_candles == 42
    assert set(registry.trend_feature_names) < registered
    assert set(registry.mean_reversion_feature_names) < registered
    assert set(registry.regime_feature_names) < registered
    assert len(registry.feature_names) == len(registered)


def _two_segments(candles: tuple[Candle, ...]) -> CandleSegmentManifest:
    split = len(candles) // 2
    return CandleSegmentManifest(
        schema_version="candle-segment-manifest-v1",
        segments=(
            CandleSegment(
                1, 0, split, candles[0].open_time, candles[split - 1].open_time, split, None
            ),
            CandleSegment(
                2,
                split,
                len(candles),
                candles[split].open_time,
                candles[-1].open_time,
                len(candles) - split,
                "test-closure",
            ),
        ),
    )


def test_feature_warmup_restarts_after_segment_boundary() -> None:
    candles = rising_candles(100)
    segments = _two_segments(candles)
    matrix = FeatureRegistry.locked_v0_1().compute(candles, segments=segments)

    second_start = segments.segments[1].start_index
    assert min(row.candle_index for row in matrix.rows if row.candle_index >= second_start) == 92


def test_prior_segment_mutation_cannot_change_later_segment_features() -> None:
    candles = rising_candles(100)
    segments = _two_segments(candles)
    registry = FeatureRegistry.locked_v0_1()
    original = registry.compute(candles, segments=segments)
    changed = (
        replace(candles[0], volume=Decimal("999999")),
        *candles[1:],
    )

    assert original.row_for(95) == registry.compute(changed, segments=segments).row_for(95)
