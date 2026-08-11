"""RED tests for executable Candidate v0.2 development qualification helpers."""

from decimal import Decimal

from gemini_trading.strategy.policy import CandidatePolicy
from gemini_trading.strategy.qualification_execution import (
    aggregate_path_metrics,
    qualification_case_ids,
)
from gemini_trading.strategy.study import REQUIRED_FINAL_CASE_IDS


def test_v0_2_qualification_case_ids_preserve_full_robustness_suite() -> None:
    policy = CandidatePolicy.locked_v0_2()

    case_ids = qualification_case_ids(policy)

    expected = tuple(
        policy.strategy_id if case_id == "candidate.multi_model.v0_1" else case_id
        for case_id in REQUIRED_FINAL_CASE_IDS
    )
    assert case_ids == expected
    assert case_ids[0] == "candidate.multi_model.v0_2"
    assert "bootstrap.seed_1788" in case_ids


def test_aggregate_path_metrics_recompute_compounded_return_and_drawdown() -> None:
    metrics = aggregate_path_metrics(
        (
            Decimal("0.10"),
            Decimal("-0.10"),
            Decimal("0.05"),
        )
    )

    assert metrics.net_return == Decimal("0.0395")
    assert metrics.maximum_drawdown == Decimal("0.10")
    assert metrics.return_to_drawdown == Decimal("0.395")


def test_aggregate_path_metrics_leave_undefined_ratio_when_drawdown_is_zero() -> None:
    metrics = aggregate_path_metrics((Decimal("0.01"), Decimal("0.02")))

    assert metrics.net_return == Decimal("0.0302")
    assert metrics.maximum_drawdown == Decimal("0")
    assert metrics.return_to_drawdown is None
