"""RED tests for Candidate v0.2 development-only chronological qualification splits."""

from datetime import UTC, datetime

import pytest

from gemini_trading.strategy.errors import SplitBoundaryError
from gemini_trading.strategy.policy import CandidatePolicy
from gemini_trading.strategy.splits import DevelopmentQualificationPlan
from strategy_fixture_support import calendar_candles

_START = datetime(2018, 1, 1, tzinfo=UTC)
_END = datetime(2026, 7, 1, tzinfo=UTC)


def _eligible(candle_count: int) -> tuple[int, ...]:
    return tuple(range(42, candle_count - 4))


def test_v0_2_development_plan_uses_all_twelve_complete_forward_folds() -> None:
    candles = calendar_candles(start=_START, end_exclusive=_END)

    plan = DevelopmentQualificationPlan.build(
        candles,
        _eligible(len(candles)),
        CandidatePolicy.locked_v0_2(),
    )

    assert plan.schema_version == "candidate-development-qualification-plan-v1"
    assert plan.dataset_start_time == _START
    assert plan.dataset_end_exclusive == _END
    assert len(plan.folds) == 12
    assert tuple(fold.fold_number for fold in plan.folds) == tuple(range(1, 13))
    assert plan.used_label_indices == tuple(sorted(set(plan.used_label_indices)))
    assert plan.folds[-1].development_test.end_exclusive <= len(candles)
    assert not hasattr(plan, "final_test")


def test_v0_2_development_plan_rejects_changed_dataset_cutoff() -> None:
    candles = calendar_candles(
        start=_START,
        end_exclusive=datetime(2026, 6, 1, tzinfo=UTC),
    )

    with pytest.raises(SplitBoundaryError, match="v0.2 development dataset window"):
        DevelopmentQualificationPlan.build(
            candles,
            _eligible(len(candles)),
            CandidatePolicy.locked_v0_2(),
        )
