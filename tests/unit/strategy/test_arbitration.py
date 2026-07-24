"""RED tests for deterministic Candidate v0.1 arbitration."""

from dataclasses import replace
from decimal import Decimal

from gemini_trading.strategy.arbitration import ArbitrationInput, MultiModelArbiter
from gemini_trading.strategy.contracts import RegimeState, SpecialistKind, StrategyAction
from gemini_trading.strategy.policy import CandidatePolicy


def flat_input(**changes: object) -> ArbitrationInput:
    base = ArbitrationInput(
        candle_index=42,
        regime=RegimeState.TRENDING,
        trend_probability=Decimal("0.62"),
        trend_expected_gross_return=Decimal("0.0071"),
        mean_reversion_probability=Decimal("0.45"),
        mean_reversion_expected_gross_return=Decimal("0.001"),
        currently_long=False,
        active_specialist=None,
        hold_age=0,
        cooldown_remaining=0,
        indeterminate_streak=0,
        entry_price=None,
        highest_close_since_entry=None,
        current_close=Decimal("100"),
        current_low=Decimal("99"),
        atr24=Decimal("2"),
        current_stop=None,
        stretch_active=False,
        base_hurdle_bps=Decimal("60"),
    )
    return replace(base, **changes)


def long_input(**changes: object) -> ArbitrationInput:
    base = flat_input(
        currently_long=True,
        active_specialist=SpecialistKind.TREND,
        hold_age=2,
        entry_price=Decimal("100"),
        highest_close_since_entry=Decimal("110"),
        current_close=Decimal("108"),
        current_low=Decimal("107"),
        current_stop=Decimal("100"),
        trend_probability=Decimal("0.50"),
    )
    return replace(base, **changes)


def arbiter() -> MultiModelArbiter:
    return MultiModelArbiter(CandidatePolicy.locked_v0_1())


def test_trending_entry_passes_at_locked_boundary() -> None:
    decision = arbiter().decide(flat_input())

    assert decision.action is StrategyAction.ENTER_LONG
    assert decision.active_specialist is SpecialistKind.TREND
    assert decision.initial_stop == Decimal("95.0")
    assert decision.trailing_stop == Decimal("95.0")
    assert decision.cooldown_remaining == 0


def test_ranging_entry_requires_active_stretch() -> None:
    rejected = arbiter().decide(
        flat_input(
            regime=RegimeState.RANGING,
            trend_probability=Decimal("0.45"),
            mean_reversion_probability=Decimal("0.62"),
            mean_reversion_expected_gross_return=Decimal("0.0071"),
        )
    )
    accepted = arbiter().decide(replace(rejected.source, stretch_active=True))

    assert rejected.action is StrategyAction.REMAIN_IN_CASH
    assert accepted.action is StrategyAction.ENTER_LONG
    assert accepted.active_specialist is SpecialistKind.MEAN_REVERSION


def test_unstable_or_conflicting_evidence_abstains() -> None:
    unstable = arbiter().decide(flat_input(regime=RegimeState.UNSTABLE))
    conflicting = arbiter().decide(
        flat_input(
            trend_probability=Decimal("0.80"),
            mean_reversion_probability=Decimal("0.40"),
        )
    )

    assert unstable.action is StrategyAction.REMAIN_IN_CASH
    assert conflicting.action is StrategyAction.REMAIN_IN_CASH


def test_expected_gross_must_strictly_exceed_seventy_basis_points() -> None:
    decision = arbiter().decide(flat_input(trend_expected_gross_return=Decimal("0.0070")))

    assert decision.action is StrategyAction.REMAIN_IN_CASH
    assert "expected_edge_below_entry_hurdle" in decision.reasons


def test_hold_and_exit_probability_boundaries_are_hysteretic() -> None:
    hold = arbiter().decide(long_input(trend_probability=Decimal("0.50")))
    exit_decision = arbiter().decide(long_input(trend_probability=Decimal("0.45")))

    assert hold.action is StrategyAction.REMAIN_LONG
    assert exit_decision.action is StrategyAction.EXIT_TO_CASH
    assert exit_decision.cooldown_remaining == 2


def test_minimum_hold_blocks_probability_exit_but_not_stop_or_instability() -> None:
    probability = arbiter().decide(long_input(hold_age=1, trend_probability=Decimal("0.30")))
    stopped = arbiter().decide(long_input(hold_age=1, current_low=Decimal("99")))
    unstable = arbiter().decide(long_input(hold_age=1, regime=RegimeState.UNSTABLE))

    assert probability.action is StrategyAction.REMAIN_LONG
    assert stopped.action is StrategyAction.EXIT_TO_CASH
    assert unstable.action is StrategyAction.EXIT_TO_CASH


def test_indeterminate_hysteresis_tolerates_one_candle_only() -> None:
    first = arbiter().decide(long_input(regime=RegimeState.INDETERMINATE, indeterminate_streak=0))
    second = arbiter().decide(long_input(regime=RegimeState.INDETERMINATE, indeterminate_streak=1))

    assert first.action is StrategyAction.REMAIN_LONG
    assert first.indeterminate_streak == 1
    assert second.action is StrategyAction.EXIT_TO_CASH


def test_trailing_stop_never_decreases_and_maximum_hold_exits() -> None:
    raised = arbiter().decide(long_input(current_stop=Decimal("100")))
    unchanged = arbiter().decide(long_input(current_stop=Decimal("105")))
    expired = arbiter().decide(long_input(hold_age=18))

    assert raised.trailing_stop == Decimal("104.0")
    assert unchanged.trailing_stop == Decimal("105")
    assert expired.action is StrategyAction.EXIT_TO_CASH
