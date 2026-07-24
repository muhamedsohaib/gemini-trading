"""RED tests for the locked Candidate Multi-Model Strategy v0.1 policy."""

from decimal import Decimal

from gemini_trading.strategy.contracts import RegimeState, SpecialistKind, StrategyAction
from gemini_trading.strategy.policy import CandidatePolicy, serialize_candidate_policy


def test_locked_policy_matches_approved_spec() -> None:
    policy = CandidatePolicy.locked_v0_1()

    assert policy.strategy_id == "candidate.multi_model.v0_1"
    assert (policy.instrument_symbol, policy.timeframe) == ("BTCUSDT", "4h")
    assert policy.minimum_history_years == 7
    assert policy.final_test_months == 18
    assert policy.label_horizon_candles == 3
    assert policy.entry_probability == Decimal("0.62")
    assert policy.hold_probability == Decimal("0.50")
    assert policy.exit_probability == Decimal("0.45")
    assert policy.disagreement_limit == Decimal("0.25")
    assert policy.minimum_hold_candles == 2
    assert policy.maximum_hold_candles == 18
    assert policy.cooldown_candles == 2
    assert policy.initial_stop_atr == Decimal("2.5")
    assert policy.trailing_stop_atr == Decimal("3.0")
    assert serialize_candidate_policy(policy) == serialize_candidate_policy(
        CandidatePolicy.locked_v0_1()
    )


def test_closed_enums_are_stable() -> None:
    assert tuple(item.value for item in RegimeState) == (
        "unstable",
        "trending",
        "ranging",
        "indeterminate",
    )
    assert tuple(item.value for item in SpecialistKind) == (
        "trend",
        "mean_reversion",
    )
    assert tuple(item.value for item in StrategyAction) == (
        "enter_long",
        "remain_long",
        "exit_to_cash",
        "remain_in_cash",
    )
