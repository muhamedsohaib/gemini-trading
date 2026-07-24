"""RED tests for the locked point-in-time feature registry."""

from dataclasses import replace
from decimal import Decimal

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
