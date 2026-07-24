"""Deterministic regime-aware arbitration for the Candidate v0.1 strategy."""

from dataclasses import dataclass
from decimal import Decimal

from gemini_trading.strategy.contracts import RegimeState, SpecialistKind, StrategyAction
from gemini_trading.strategy.policy import CandidatePolicy

_BASIS_POINTS = Decimal("10000")


def _finite(value: Decimal, field_name: str) -> None:
    if not value.is_finite():
        raise ValueError(f"{field_name} must be finite")


def _probability(value: Decimal, field_name: str) -> None:
    _finite(value, field_name)
    if not Decimal("0") <= value <= Decimal("1"):
        raise ValueError(f"{field_name} must be within [0, 1]")


def _positive(value: Decimal, field_name: str) -> None:
    _finite(value, field_name)
    if value <= 0:
        raise ValueError(f"{field_name} must be positive")


@dataclass(frozen=True, slots=True)
class ArbitrationInput:
    """Complete immutable state used by one arbitration decision."""

    candle_index: int
    regime: RegimeState
    trend_probability: Decimal
    trend_expected_gross_return: Decimal
    mean_reversion_probability: Decimal
    mean_reversion_expected_gross_return: Decimal
    currently_long: bool
    active_specialist: SpecialistKind | None
    hold_age: int
    cooldown_remaining: int
    indeterminate_streak: int
    entry_price: Decimal | None
    highest_close_since_entry: Decimal | None
    current_close: Decimal
    current_low: Decimal
    atr24: Decimal
    current_stop: Decimal | None
    stretch_active: bool
    base_hurdle_bps: Decimal

    def __post_init__(self) -> None:
        if isinstance(self.candle_index, bool) or self.candle_index < 0:
            raise ValueError("candle_index must be a non-negative integer")
        for field_name in ("hold_age", "cooldown_remaining", "indeterminate_streak"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer")
        _probability(self.trend_probability, "trend_probability")
        _probability(self.mean_reversion_probability, "mean_reversion_probability")
        _finite(self.trend_expected_gross_return, "trend_expected_gross_return")
        _finite(
            self.mean_reversion_expected_gross_return,
            "mean_reversion_expected_gross_return",
        )
        _positive(self.current_close, "current_close")
        _positive(self.current_low, "current_low")
        _positive(self.atr24, "atr24")
        _finite(self.base_hurdle_bps, "base_hurdle_bps")
        if self.base_hurdle_bps < 0:
            raise ValueError("base_hurdle_bps must be non-negative")
        for field_name in (
            "entry_price",
            "highest_close_since_entry",
            "current_stop",
        ):
            value = getattr(self, field_name)
            if value is not None:
                _positive(value, field_name)
        if self.current_low > self.current_close:
            raise ValueError("current_low cannot exceed current_close")
        if self.currently_long:
            if self.active_specialist is None:
                raise ValueError("long state requires an active specialist")
            if (
                self.entry_price is None
                or self.highest_close_since_entry is None
                or self.current_stop is None
            ):
                raise ValueError("long state requires entry, high-water, and stop values")
            if self.highest_close_since_entry < self.entry_price:
                raise ValueError("highest_close_since_entry cannot be below entry_price")
        else:
            if self.active_specialist is not None:
                raise ValueError("cash state cannot have an active specialist")
            if self.hold_age != 0:
                raise ValueError("cash state must have zero hold_age")
            if any(
                value is not None
                for value in (
                    self.entry_price,
                    self.highest_close_since_entry,
                    self.current_stop,
                )
            ):
                raise ValueError("cash state cannot contain position risk values")


@dataclass(frozen=True, slots=True)
class ArbitrationDecision:
    """One auditable long-or-cash decision and its next state."""

    source: ArbitrationInput
    candle_index: int
    action: StrategyAction
    active_specialist: SpecialistKind | None
    regime: RegimeState
    trend_probability: Decimal
    mean_reversion_probability: Decimal
    trend_expected_gross_return: Decimal
    mean_reversion_expected_gross_return: Decimal
    entry_hurdle: Decimal
    hold_age: int
    cooldown_remaining: int
    indeterminate_streak: int
    initial_stop: Decimal | None
    trailing_stop: Decimal | None
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.candle_index != self.source.candle_index:
            raise ValueError("decision candle_index must match source")
        if not self.reasons or any(not reason.strip() for reason in self.reasons):
            raise ValueError("decision reasons must be non-empty")
        if self.action in {StrategyAction.ENTER_LONG, StrategyAction.REMAIN_LONG}:
            if self.active_specialist is None:
                raise ValueError("long decision requires an active specialist")
            if self.initial_stop is None or self.trailing_stop is None:
                raise ValueError("long decision requires stop values")
        if (
            self.action is StrategyAction.REMAIN_IN_CASH
            and self.active_specialist is not None
        ):
            raise ValueError("cash decision cannot retain an active specialist")


@dataclass(frozen=True, slots=True)
class MultiModelArbiter:
    """Apply the approved entry, abstention, hold, exit, and risk rules."""

    policy: CandidatePolicy

    def decide(self, source: ArbitrationInput) -> ArbitrationDecision:
        """Return one deterministic transition from the supplied state."""

        entry_hurdle = (
            source.base_hurdle_bps + self.policy.expected_edge_extra_bps
        ) / _BASIS_POINTS
        if source.currently_long:
            return self._decide_long(source, entry_hurdle)
        return self._decide_cash(source, entry_hurdle)

    def _decide_cash(
        self,
        source: ArbitrationInput,
        entry_hurdle: Decimal,
    ) -> ArbitrationDecision:
        if source.cooldown_remaining > 0:
            return self._cash(
                source,
                entry_hurdle,
                cooldown=max(0, source.cooldown_remaining - 1),
                reasons=("cooldown_active",),
            )
        if source.regime is RegimeState.UNSTABLE:
            return self._cash(
                source,
                entry_hurdle,
                cooldown=0,
                reasons=("unstable_regime",),
            )
        if source.regime is RegimeState.INDETERMINATE:
            return self._cash(
                source,
                entry_hurdle,
                cooldown=0,
                reasons=("indeterminate_regime",),
            )
        if source.regime is RegimeState.TRENDING:
            specialist = SpecialistKind.TREND
            active_probability = source.trend_probability
            companion_probability = source.mean_reversion_probability
            active_expected = source.trend_expected_gross_return
        else:
            if not source.stretch_active:
                return self._cash(
                    source,
                    entry_hurdle,
                    cooldown=0,
                    reasons=("ranging_without_stretch",),
                )
            specialist = SpecialistKind.MEAN_REVERSION
            active_probability = source.mean_reversion_probability
            companion_probability = source.trend_probability
            active_expected = source.mean_reversion_expected_gross_return
        reasons: list[str] = []
        if active_probability < self.policy.entry_probability:
            reasons.append("active_probability_below_entry")
        if companion_probability < self.policy.companion_probability_floor:
            reasons.append("companion_probability_below_floor")
        if (
            abs(source.trend_probability - source.mean_reversion_probability)
            > self.policy.disagreement_limit
        ):
            reasons.append("specialist_disagreement")
        if active_expected <= entry_hurdle:
            reasons.append("expected_edge_below_entry_hurdle")
        if reasons:
            return self._cash(
                source,
                entry_hurdle,
                cooldown=0,
                reasons=tuple(reasons),
            )
        initial_stop = source.current_close - self.policy.initial_stop_atr * source.atr24
        if initial_stop <= 0:
            return self._cash(
                source,
                entry_hurdle,
                cooldown=0,
                reasons=("non_positive_initial_stop",),
            )
        return ArbitrationDecision(
            source=source,
            candle_index=source.candle_index,
            action=StrategyAction.ENTER_LONG,
            active_specialist=specialist,
            regime=source.regime,
            trend_probability=source.trend_probability,
            mean_reversion_probability=source.mean_reversion_probability,
            trend_expected_gross_return=source.trend_expected_gross_return,
            mean_reversion_expected_gross_return=source.mean_reversion_expected_gross_return,
            entry_hurdle=entry_hurdle,
            hold_age=0,
            cooldown_remaining=0,
            indeterminate_streak=0,
            initial_stop=initial_stop,
            trailing_stop=initial_stop,
            reasons=("entry_rules_passed", specialist.value),
        )

    def _decide_long(
        self,
        source: ArbitrationInput,
        entry_hurdle: Decimal,
    ) -> ArbitrationDecision:
        if (
            source.active_specialist is None
            or source.entry_price is None
            or source.highest_close_since_entry is None
            or source.current_stop is None
        ):
            raise ValueError("long arbitration source is incomplete")
        initial_stop = source.entry_price - self.policy.initial_stop_atr * source.atr24
        trailing_candidate = (
            source.highest_close_since_entry - self.policy.trailing_stop_atr * source.atr24
        )
        trailing_stop = max(source.current_stop, trailing_candidate)
        next_hold_age = source.hold_age + 1
        active_probability = (
            source.trend_probability
            if source.active_specialist is SpecialistKind.TREND
            else source.mean_reversion_probability
        )
        if source.current_low <= trailing_stop:
            return self._exit(
                source,
                entry_hurdle,
                initial_stop,
                trailing_stop,
                reasons=("stop_hit",),
            )
        if source.regime is RegimeState.UNSTABLE:
            return self._exit(
                source,
                entry_hurdle,
                initial_stop,
                trailing_stop,
                reasons=("unstable_regime",),
            )
        if source.hold_age >= self.policy.maximum_hold_candles:
            return self._exit(
                source,
                entry_hurdle,
                initial_stop,
                trailing_stop,
                reasons=("maximum_hold_reached",),
            )
        if source.regime is RegimeState.INDETERMINATE:
            next_streak = source.indeterminate_streak + 1
            if next_streak > self.policy.indeterminate_tolerance_candles:
                return self._exit(
                    source,
                    entry_hurdle,
                    initial_stop,
                    trailing_stop,
                    reasons=("indeterminate_tolerance_exceeded",),
                )
            return self._hold(
                source,
                entry_hurdle,
                initial_stop,
                trailing_stop,
                next_hold_age,
                next_streak,
                reasons=("indeterminate_tolerated",),
            )
        if source.hold_age < self.policy.minimum_hold_candles:
            return self._hold(
                source,
                entry_hurdle,
                initial_stop,
                trailing_stop,
                next_hold_age,
                0,
                reasons=("minimum_hold_active",),
            )
        if active_probability <= self.policy.exit_probability:
            return self._exit(
                source,
                entry_hurdle,
                initial_stop,
                trailing_stop,
                reasons=("active_probability_at_or_below_exit",),
            )
        reason = (
            "active_probability_at_or_above_hold"
            if active_probability >= self.policy.hold_probability
            else "probability_hysteresis_band"
        )
        return self._hold(
            source,
            entry_hurdle,
            initial_stop,
            trailing_stop,
            next_hold_age,
            0,
            reasons=(reason,),
        )

    def _cash(
        self,
        source: ArbitrationInput,
        entry_hurdle: Decimal,
        *,
        cooldown: int,
        reasons: tuple[str, ...],
    ) -> ArbitrationDecision:
        return ArbitrationDecision(
            source=source,
            candle_index=source.candle_index,
            action=StrategyAction.REMAIN_IN_CASH,
            active_specialist=None,
            regime=source.regime,
            trend_probability=source.trend_probability,
            mean_reversion_probability=source.mean_reversion_probability,
            trend_expected_gross_return=source.trend_expected_gross_return,
            mean_reversion_expected_gross_return=source.mean_reversion_expected_gross_return,
            entry_hurdle=entry_hurdle,
            hold_age=0,
            cooldown_remaining=cooldown,
            indeterminate_streak=0,
            initial_stop=None,
            trailing_stop=None,
            reasons=reasons,
        )

    def _hold(
        self,
        source: ArbitrationInput,
        entry_hurdle: Decimal,
        initial_stop: Decimal,
        trailing_stop: Decimal,
        hold_age: int,
        indeterminate_streak: int,
        *,
        reasons: tuple[str, ...],
    ) -> ArbitrationDecision:
        return ArbitrationDecision(
            source=source,
            candle_index=source.candle_index,
            action=StrategyAction.REMAIN_LONG,
            active_specialist=source.active_specialist,
            regime=source.regime,
            trend_probability=source.trend_probability,
            mean_reversion_probability=source.mean_reversion_probability,
            trend_expected_gross_return=source.trend_expected_gross_return,
            mean_reversion_expected_gross_return=source.mean_reversion_expected_gross_return,
            entry_hurdle=entry_hurdle,
            hold_age=hold_age,
            cooldown_remaining=0,
            indeterminate_streak=indeterminate_streak,
            initial_stop=initial_stop,
            trailing_stop=trailing_stop,
            reasons=reasons,
        )

    def _exit(
        self,
        source: ArbitrationInput,
        entry_hurdle: Decimal,
        initial_stop: Decimal,
        trailing_stop: Decimal,
        *,
        reasons: tuple[str, ...],
    ) -> ArbitrationDecision:
        return ArbitrationDecision(
            source=source,
            candle_index=source.candle_index,
            action=StrategyAction.EXIT_TO_CASH,
            active_specialist=source.active_specialist,
            regime=source.regime,
            trend_probability=source.trend_probability,
            mean_reversion_probability=source.mean_reversion_probability,
            trend_expected_gross_return=source.trend_expected_gross_return,
            mean_reversion_expected_gross_return=source.mean_reversion_expected_gross_return,
            entry_hurdle=entry_hurdle,
            hold_age=source.hold_age,
            cooldown_remaining=self.policy.cooldown_candles,
            indeterminate_streak=0,
            initial_stop=initial_stop,
            trailing_stop=trailing_stop,
            reasons=reasons,
        )
