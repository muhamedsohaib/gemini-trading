"""Property tests for point-in-time feature isolation."""

from dataclasses import replace
from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from gemini_trading.strategy.features import FeatureRegistry
from strategy_fixture_support import rising_candles


@given(
    count=st.integers(min_value=50, max_value=80),
    shock=st.integers(min_value=100_000, max_value=1_000_000),
)
def test_future_candle_changes_cannot_alter_prior_rows(count: int, shock: int) -> None:
    candles = rising_candles(count)
    registry = FeatureRegistry.locked_v0_1()
    original = registry.compute(candles)
    final = candles[-1]
    changed = registry.compute(
        (
            *candles[:-1],
            replace(
                final,
                high=Decimal(shock + 10),
                close=Decimal(shock),
                volume=Decimal(shock * 100),
            ),
        )
    )

    prior_index = count - 2
    assert original.row_for(prior_index) == changed.row_for(prior_index)
