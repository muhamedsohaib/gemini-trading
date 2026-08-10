"""RED tests for the locked Candidate Multi-Model Strategy policies."""

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
    assert policy.trend_max_iterations == 10000
    assert policy.trend_tolerance == Decimal("0.00000001")
    assert serialize_candidate_policy(policy) == serialize_candidate_policy(
        CandidatePolicy.locked_v0_1()
    )


def test_locked_v0_2_changes_only_approved_identity_and_convergence() -> None:
    old = CandidatePolicy.locked_v0_1()
    new = CandidatePolicy.locked_v0_2()

    assert new.strategy_id == "candidate.multi_model.v0_2"
    assert new.policy_version == "candidate-multi-model-v0.2"
    assert new.schema_version == "candidate-strategy-policy-v2"
    assert (new.instrument_symbol, new.timeframe) == ("BTCUSDT", "4h")
    assert new.trend_max_iterations == 50_000
    assert new.trend_tolerance == Decimal("0.0000001")
    differing = {
        name for name in old.__dataclass_fields__ if getattr(old, name) != getattr(new, name)
    }
    assert differing == {
        "schema_version",
        "strategy_id",
        "policy_version",
        "trend_max_iterations",
        "trend_tolerance",
    }
    assert serialize_candidate_policy(new) == serialize_candidate_policy(
        CandidatePolicy.locked_v0_2()
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
