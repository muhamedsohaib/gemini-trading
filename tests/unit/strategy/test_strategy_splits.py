"""RED tests for sealed chronological Candidate v0.1 splits."""

from datetime import UTC, datetime

from gemini_trading.domain.candle import Candle
from gemini_trading.strategy.policy import CandidatePolicy
from gemini_trading.strategy.splits import ChronologicalSplitPlan
from strategy_fixture_support import calendar_candles


def _eight_year_candles() -> tuple[Candle, ...]:
    return calendar_candles(
        start=datetime(2018, 1, 1, tzinfo=UTC),
        end_exclusive=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_split_plan_locks_calendar_windows_and_final_test() -> None:
    candles = _eight_year_candles()
    eligible = tuple(range(42, len(candles) - 4))
    plan = ChronologicalSplitPlan.build(
        candles,
        eligible,
        CandidatePolicy.locked_v0_1(),
    )

    assert plan.dataset_start_time == datetime(2018, 1, 1, tzinfo=UTC)
    assert plan.dataset_end_exclusive == datetime(2026, 1, 1, tzinfo=UTC)
    assert plan.final_test_start_time == datetime(2024, 7, 1, tzinfo=UTC)
    assert len(plan.folds) == 8
    assert all(fold.purge_candles == 3 for fold in plan.folds)
    assert all(fold.embargo_candles == 3 for fold in plan.folds)
    assert plan.final_test.start_inclusive >= plan.final_test_boundary_index + 3
    assert plan.final_test.end_exclusive <= len(candles) - 4


def test_no_used_label_window_crosses_any_protected_boundary() -> None:
    candles = _eight_year_candles()
    eligible = tuple(range(42, len(candles) - 4))
    plan = ChronologicalSplitPlan.build(
        candles,
        eligible,
        CandidatePolicy.locked_v0_1(),
    )

    for boundary in plan.boundary_indices:
        assert all(
            not (decision_index < boundary <= decision_index + 4)
            for decision_index in plan.used_label_indices
        )


def test_fold_windows_are_ordered_disjoint_and_expanding() -> None:
    candles = _eight_year_candles()
    plan = ChronologicalSplitPlan.build(
        candles,
        tuple(range(42, len(candles) - 4)),
        CandidatePolicy.locked_v0_1(),
    )

    prior_training_end = 0
    for fold in plan.folds:
        assert fold.training.end_exclusive > prior_training_end
        assert fold.training.end_exclusive <= fold.calibration.start_inclusive
        assert fold.calibration.end_exclusive <= fold.development_test.start_inclusive
        assert fold.development_test.end_exclusive <= plan.final_test_boundary_index
        prior_training_end = fold.training.end_exclusive
