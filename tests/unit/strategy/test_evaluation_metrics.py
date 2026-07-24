"""Tests for deterministic regime attribution and bootstrap evaluation."""

from decimal import Decimal

from test_metrics import known_evidence

from gemini_trading.strategy.contracts import RegimeState
from gemini_trading.strategy.evaluation import (
    attribute_regime_metrics,
    deterministic_moving_block_bootstrap,
)
from gemini_trading.strategy.regimes import RegimeObservation


def _observation(candle_index: int, state: RegimeState) -> RegimeObservation:
    return RegimeObservation(
        candle_index=candle_index,
        state=state,
        trend_strength=Decimal("0"),
        volatility_ratio=Decimal("1"),
        true_range_ratio=Decimal("1"),
        sign_streak=0,
        reason_code=f"fixture_{state.value}",
    )


def test_regime_attribution_returns_all_states_with_exact_contributions() -> None:
    metrics = attribute_regime_metrics(
        known_evidence(),
        (
            _observation(1, RegimeState.TRENDING),
            _observation(3, RegimeState.RANGING),
        ),
    )
    by_state = {item.state: item for item in metrics}

    assert set(by_state) == set(RegimeState)
    assert by_state[RegimeState.TRENDING].net_return == Decimal("-0.001")
    assert by_state[RegimeState.TRENDING].maximum_drawdown == Decimal("0.001")
    assert by_state[RegimeState.TRENDING].exposure_fraction == Decimal("1")
    assert by_state[RegimeState.TRENDING].completed_trade_count == 0
    assert by_state[RegimeState.RANGING].net_return == Decimal("0.0188")
    assert by_state[RegimeState.RANGING].maximum_drawdown == Decimal("0")
    assert by_state[RegimeState.RANGING].exposure_fraction == Decimal("0")
    assert by_state[RegimeState.RANGING].completed_trade_count == 1
    assert by_state[RegimeState.UNSTABLE].period_count == 0
    assert by_state[RegimeState.INDETERMINATE].period_count == 0


def test_moving_block_bootstrap_is_seeded_content_identified_and_ordered() -> None:
    candidate = tuple(
        Decimal(value)
        for value in ("0.01", "-0.004", "0.006", "0.003", "-0.002", "0.008")
        * 14
    )
    baseline = tuple(
        Decimal(value)
        for value in ("0.004", "-0.003", "0.003", "0.001", "-0.001", "0.004")
        * 14
    )

    first = deterministic_moving_block_bootstrap(candidate, baseline)
    second = deterministic_moving_block_bootstrap(candidate, baseline)

    assert first == second
    assert first.seed == 1788
    assert first.replicate_count == 1000
    assert first.block_length == 42
    assert len(first.sampled_start_matrix_sha256) == 64
    assert (
        first.net_return_difference_p05
        <= first.net_return_difference_median
        <= first.net_return_difference_p95
    )
    assert (
        first.drawdown_difference_p05
        <= first.drawdown_difference_median
        <= first.drawdown_difference_p95
    )
