"""Property tests for chronological label-window isolation."""

from datetime import UTC, datetime

from hypothesis import given, settings
from hypothesis import strategies as st

from gemini_trading.strategy.policy import CandidatePolicy
from gemini_trading.strategy.splits import ChronologicalSplitPlan
from strategy_fixture_support import calendar_candles


@settings(max_examples=4, deadline=None)
@given(end_year=st.integers(min_value=2025, max_value=2028))
def test_every_used_label_is_contained_inside_its_assigned_window(end_year: int) -> None:
    candles = calendar_candles(
        start=datetime(2017, 1, 1, tzinfo=UTC),
        end_exclusive=datetime(end_year, 1, 1, tzinfo=UTC),
    )
    plan = ChronologicalSplitPlan.build(
        candles,
        tuple(range(42, len(candles) - 4)),
        CandidatePolicy.locked_v0_1(),
    )

    assigned_windows = (
        *(
            window
            for fold in plan.folds
            for window in (fold.training, fold.calibration, fold.development_test)
        ),
        plan.final_test,
    )
    for decision_index in plan.used_label_indices:
        containing = tuple(window for window in assigned_windows if window.contains(decision_index))
        assert containing
        assert any(window.contains(decision_index + 4) for window in containing)
