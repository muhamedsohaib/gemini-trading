"""RED tests for deterministic Candidate v0.1 regime classification."""

from decimal import Decimal

import pytest

from gemini_trading.strategy.contracts import RegimeState
from gemini_trading.strategy.policy import CandidatePolicy
from gemini_trading.strategy.regimes import RegimeClassifier


def classify_values(
    strength: str,
    volatility_ratio: str,
    true_range_ratio: str,
    streak: int,
):
    return RegimeClassifier(CandidatePolicy.locked_v0_1()).classify(
        candle_index=42,
        trend_strength=Decimal(strength),
        volatility_ratio=Decimal(volatility_ratio),
        true_range_ratio=Decimal(true_range_ratio),
        sign_streak=streak,
    )


@pytest.mark.parametrize(
    ("strength", "volatility_ratio", "true_range_ratio", "streak", "expected"),
    [
        ("2.0", "1.75", "1.0", 4, RegimeState.UNSTABLE),
        ("1.0", "1.49", "1.0", 3, RegimeState.TRENDING),
        ("0.5", "1.25", "1.0", 0, RegimeState.RANGING),
        ("0.8", "1.30", "1.0", 2, RegimeState.INDETERMINATE),
    ],
)
def test_regime_rule_order(
    strength: str,
    volatility_ratio: str,
    true_range_ratio: str,
    streak: int,
    expected: RegimeState,
) -> None:
    observation = classify_values(
        strength,
        volatility_ratio,
        true_range_ratio,
        streak,
    )

    assert observation.state is expected
    assert observation.candle_index == 42
    assert observation.trend_strength == Decimal(strength)
    assert observation.volatility_ratio == Decimal(volatility_ratio)
    assert observation.true_range_ratio == Decimal(true_range_ratio)
    assert observation.sign_streak == streak
    assert observation.reason_code


def test_true_range_instability_precedes_trending() -> None:
    observation = classify_values("3.0", "1.0", "2.5", 8)

    assert observation.state is RegimeState.UNSTABLE
    assert observation.reason_code == "unstable_true_range"
