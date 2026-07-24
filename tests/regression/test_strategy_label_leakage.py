"""Regression tests for strategy label and split leakage."""

from datetime import UTC, datetime

from gemini_trading.strategy.policy import CandidatePolicy
from gemini_trading.strategy.splits import ChronologicalSplitPlan
from strategy_fixture_support import calendar_candles


def test_purge_and_embargo_remove_boundary_adjacent_observations() -> None:
    candles = calendar_candles(
        start=datetime(2018, 1, 1, tzinfo=UTC),
        end_exclusive=datetime(2026, 1, 1, tzinfo=UTC),
    )
    plan = ChronologicalSplitPlan.build(
        candles,
        tuple(range(42, len(candles) - 4)),
        CandidatePolicy.locked_v0_1(),
    )

    used = set(plan.used_label_indices)
    for boundary in plan.boundary_indices:
        for decision_index in range(boundary - 3, boundary + 3):
            assert decision_index not in used
        for decision_index in range(boundary - 4, boundary):
            assert decision_index + 4 < boundary or decision_index not in used
