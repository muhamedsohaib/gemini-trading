"""Candidate v0.3 immutable development-only split contract tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from gemini_trading.data.segments import CandleSegment, CandleSegmentManifest
from gemini_trading.domain.candle import Candle
from gemini_trading.strategy.errors import SplitBoundaryError
from gemini_trading.strategy.policy import CandidatePolicy
from gemini_trading.strategy.splits import DevelopmentQualificationPlan
from gemini_trading.strategy.v0_3_splits import V03DevelopmentQualificationPlan
from strategy_fixture_support import calendar_candles

_START = datetime(2018, 1, 1, tzinfo=UTC)
_END = datetime(2026, 8, 1, tzinfo=UTC)


def _eligible(candle_count: int) -> tuple[int, ...]:
    return tuple(range(42, candle_count - 4))


def _segments(candles: tuple[Candle, ...], split: int) -> CandleSegmentManifest:
    return CandleSegmentManifest(
        schema_version="candle-segment-manifest-v1",
        segments=(
            CandleSegment(
                1,
                0,
                split,
                candles[0].open_time,
                candles[split - 1].open_time,
                split,
                None,
            ),
            CandleSegment(
                2,
                split,
                len(candles),
                candles[split].open_time,
                candles[-1].open_time,
                len(candles) - split,
                "test-closure",
            ),
        ),
    )


def test_v0_3_plan_locks_cutoff_and_all_twelve_complete_folds() -> None:
    candles = calendar_candles(start=_START, end_exclusive=_END)
    policy = CandidatePolicy.locked_v0_3()
    plan = V03DevelopmentQualificationPlan.build(
        candles,
        _eligible(len(candles)),
        policy,
    )

    assert plan.schema_version == "candidate-v0.3-development-qualification-plan-v1"
    assert plan.dataset_start_time == _START
    assert plan.dataset_end_exclusive == _END
    assert tuple(fold.fold_number for fold in plan.folds) == tuple(range(1, 13))
    assert len(plan.folds) == 12
    assert plan.used_label_indices == tuple(sorted(set(plan.used_label_indices)))
    assert not hasattr(plan, "final_test")

    last_complete_boundary: int = (
        plan.folds[-1].development_test.end_exclusive + policy.purge_candles
    )
    assert candles[last_complete_boundary].open_time == datetime(2026, 7, 1, tzinfo=UTC)
    assert plan.dataset_end_exclusive == datetime(2026, 8, 1, tzinfo=UTC)


def test_v0_3_plan_protects_segment_and_fold_boundaries() -> None:
    candles = calendar_candles(start=_START, end_exclusive=_END)
    split = 500
    plan = V03DevelopmentQualificationPlan.build(
        candles,
        _eligible(len(candles)),
        CandidatePolicy.locked_v0_3(),
        _segments(candles, split),
    )

    assert plan.segment_boundary_indices == (split,)
    assert split in plan.boundary_indices
    for boundary in plan.boundary_indices:
        assert all(
            not (decision_index < boundary <= decision_index + 4)
            for decision_index in plan.used_label_indices
        )
        assert all(
            not (
                boundary - plan.purge_candles
                <= decision_index
                < boundary + plan.embargo_candles
            )
            for decision_index in plan.used_label_indices
        )


def test_v0_3_fold_windows_are_ordered_disjoint_and_expanding() -> None:
    candles = calendar_candles(start=_START, end_exclusive=_END)
    plan = V03DevelopmentQualificationPlan.build(
        candles,
        _eligible(len(candles)),
        CandidatePolicy.locked_v0_3(),
    )

    prior_training_end = 0
    for fold in plan.folds:
        assert fold.training.end_exclusive > prior_training_end
        assert fold.training.end_exclusive <= fold.calibration.start_inclusive
        assert fold.calibration.end_exclusive <= fold.development_test.start_inclusive
        prior_training_end = fold.training.end_exclusive


def test_v0_3_plan_rejects_changed_cutoff_and_old_candidate_identity() -> None:
    changed = calendar_candles(
        start=_START,
        end_exclusive=datetime(2026, 7, 1, tzinfo=UTC),
    )
    with pytest.raises(SplitBoundaryError, match=r"v0\.3 development dataset window"):
        V03DevelopmentQualificationPlan.build(
            changed,
            _eligible(len(changed)),
            CandidatePolicy.locked_v0_3(),
        )

    candles = calendar_candles(start=_START, end_exclusive=_END)
    with pytest.raises(SplitBoundaryError, match=r"Candidate v0\.3"):
        V03DevelopmentQualificationPlan.build(
            candles,
            _eligible(len(candles)),
            CandidatePolicy.locked_v0_2(),
        )


def test_existing_v0_2_plan_remains_unchanged() -> None:
    end = datetime(2026, 7, 1, tzinfo=UTC)
    candles = calendar_candles(start=_START, end_exclusive=end)
    plan = DevelopmentQualificationPlan.build(
        candles,
        _eligible(len(candles)),
        CandidatePolicy.locked_v0_2(),
    )

    assert plan.schema_version == "candidate-development-qualification-plan-v1"
    assert plan.dataset_end_exclusive == end
    assert tuple(fold.fold_number for fold in plan.folds) == tuple(range(1, 13))
