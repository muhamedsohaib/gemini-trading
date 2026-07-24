"""Deterministic completed-candle regime classification."""

from dataclasses import dataclass
from decimal import Decimal

from gemini_trading.strategy.contracts import RegimeState
from gemini_trading.strategy.policy import CandidatePolicy


def _finite(value: Decimal, field_name: str) -> None:
    if not value.is_finite():
        raise ValueError(f"{field_name} must be finite")


@dataclass(frozen=True, slots=True)
class RegimeObservation:
    """One immutable regime state and its complete rule inputs."""

    candle_index: int
    state: RegimeState
    trend_strength: Decimal
    volatility_ratio: Decimal
    true_range_ratio: Decimal
    sign_streak: int
    reason_code: str

    def __post_init__(self) -> None:
        if isinstance(self.candle_index, bool) or self.candle_index < 0:
            raise ValueError("candle_index must be a non-negative integer")
        for field_name in (
            "trend_strength",
            "volatility_ratio",
            "true_range_ratio",
        ):
            _finite(getattr(self, field_name), field_name)
        if self.volatility_ratio < 0 or self.true_range_ratio < 0:
            raise ValueError("regime ratios must be non-negative")
        if isinstance(self.sign_streak, bool):
            raise ValueError("sign_streak must be an integer")
        if not self.reason_code.strip():
            raise ValueError("reason_code must not be empty")


@dataclass(frozen=True, slots=True)
class RegimeClassifier:
    """Apply the approved ordered Candidate v0.1 regime rules."""

    policy: CandidatePolicy

    def classify(
        self,
        *,
        candle_index: int,
        trend_strength: Decimal,
        volatility_ratio: Decimal,
        true_range_ratio: Decimal,
        sign_streak: int,
    ) -> RegimeObservation:
        """Classify one completed candle, evaluating unstable rules first."""

        values = RegimeObservation(
            candle_index=candle_index,
            state=RegimeState.INDETERMINATE,
            trend_strength=trend_strength,
            volatility_ratio=volatility_ratio,
            true_range_ratio=true_range_ratio,
            sign_streak=sign_streak,
            reason_code="pending",
        )
        if volatility_ratio >= self.policy.unstable_volatility_ratio:
            state = RegimeState.UNSTABLE
            reason = "unstable_volatility"
        elif true_range_ratio >= self.policy.unstable_true_range_ratio:
            state = RegimeState.UNSTABLE
            reason = "unstable_true_range"
        elif (
            abs(trend_strength) >= self.policy.trending_strength_floor
            and volatility_ratio < self.policy.trending_volatility_ceiling
            and abs(sign_streak) >= self.policy.trending_sign_streak
        ):
            state = RegimeState.TRENDING
            reason = "trending_strength_streak"
        elif (
            abs(trend_strength) <= self.policy.ranging_strength_ceiling
            and volatility_ratio <= self.policy.ranging_volatility_ceiling
        ):
            state = RegimeState.RANGING
            reason = "ranging_low_strength"
        else:
            state = RegimeState.INDETERMINATE
            reason = "indeterminate_rules"
        return RegimeObservation(
            candle_index=values.candle_index,
            state=state,
            trend_strength=values.trend_strength,
            volatility_ratio=values.volatility_ratio,
            true_range_ratio=values.true_range_ratio,
            sign_streak=values.sign_streak,
            reason_code=reason,
        )
