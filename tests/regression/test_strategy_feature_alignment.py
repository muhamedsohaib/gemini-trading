"""Regression tests for feature/candle index alignment."""

from decimal import Context, ROUND_HALF_EVEN, localcontext

from gemini_trading.strategy.features import FeatureRegistry
from strategy_fixture_support import rising_candles


def test_one_candle_return_is_aligned_to_current_completed_candle() -> None:
    candles = rising_candles(50)
    matrix = FeatureRegistry.locked_v0_1().compute(candles)
    row = matrix.row_for(42)

    with localcontext(Context(prec=34, rounding=ROUND_HALF_EVEN)):
        expected = (candles[42].close / candles[41].close).ln()

    assert row.candle_open_time == candles[42].open_time
    assert matrix.value_for(42, "log_return_1") == expected
    assert matrix.value_for(42, "close_location_current") == (
        (candles[42].close - candles[42].low) / (candles[42].high - candles[42].low)
    )
