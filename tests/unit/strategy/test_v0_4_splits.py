"""Candidate v0.4 hourly development split-contract tests."""

from __future__ import annotations

from calendar import monthrange
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from gemini_trading.data.segments import CandleSegment, CandleSegmentManifest
from gemini_trading.domain.candle import Candle
from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.timeframe import Timeframe
from gemini_trading.strategy.errors import SplitBoundaryError
from gemini_trading.strategy.labels import label_exit_offset
from gemini_trading.strategy.policy import CandidatePolicy
from gemini_trading.strategy.v0_4_splits import V04DevelopmentQualificationPlan

_START = datetime(2018, 1, 1, tzinfo=UTC)
_END = datetime(2026, 8, 1, tzinfo=UTC)
_INSTRUMENT = Instrument("BTCUSDT", "BTC", "USDT")


def _add_months(value: datetime, months: int) -> datetime:
    zero_based_month = value.month - 1 + months
    year = value.year + zero_based_month // 12
    month = zero_based_month % 12 + 1
    day = min(value.day, monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def _hourly_calendar_candles(
    *,
    start: datetime = _START,
    end_exclusive: datetime = _END,
) -> tuple[Candle, ...]:
    duration = end_exclusive - start
    count = int(duration.total_seconds() // 3600)

    if start + timedelta(hours=count) != end_exclusive:
        raise ValueError("fixture range must contain whole one-hour candles")

    candles: list[Candle] = []
    for index in range(count):
        opened = start + timedelta(hours=index)
        price = Decimal("10000") + Decimal(index % 1000)

        candles.append(
            Candle(
                instrument=_INSTRUMENT,
                timeframe=Timeframe.H1,
                open_time=opened,
                close_time=(opened + timedelta(hours=1) - timedelta(milliseconds=1)),
                open=price,
                high=price + Decimal("2"),
                low=price - Decimal("2"),
                close=price + Decimal("1"),
                volume=Decimal("1000") + Decimal(index % 100),
                completed=True,
                source_provider="binance_spot",
            )
        )

    return tuple(candles)


@pytest.fixture(scope="module")
def hourly_candles() -> tuple[Candle, ...]:
    return _hourly_calendar_candles()


def _eligible(candle_count: int) -> tuple[int, ...]:
    # 42-hour tactical warmup.
    # A decision at N needs its exact v0.4 exit at N + 13.
    return tuple(range(42, candle_count - 13))


def _segments(
    candles: tuple[Candle, ...],
    split: int,
) -> CandleSegmentManifest:
    return CandleSegmentManifest(
        schema_version="candle-segment-manifest-v1",
        segments=(
            CandleSegment(
                segment_number=1,
                start_index=0,
                end_exclusive=split,
                first_open_time=candles[0].open_time,
                last_open_time=candles[split - 1].open_time,
                candle_count=split,
                preceding_closure_id=None,
            ),
            CandleSegment(
                segment_number=2,
                start_index=split,
                end_exclusive=len(candles),
                first_open_time=candles[split].open_time,
                last_open_time=candles[-1].open_time,
                candle_count=len(candles) - split,
                preceding_closure_id="test-closure",
            ),
        ),
    )


def test_v0_4_plan_has_twelve_complete_development_folds(
    hourly_candles: tuple[Candle, ...],
) -> None:
    policy = CandidatePolicy.locked_v0_4()

    plan = V04DevelopmentQualificationPlan.build(
        hourly_candles,
        _eligible(len(hourly_candles)),
        policy,
    )

    assert plan.schema_version == "candidate-v0.4-development-qualification-plan-v1"
    assert plan.dataset_start_time == _START
    assert plan.dataset_end_exclusive == _END
    assert tuple(fold.fold_number for fold in plan.folds) == tuple(range(1, 13))
    assert len(plan.folds) == 12
    assert plan.purge_candles == 12
    assert plan.embargo_candles == 12
    assert plan.label_exit_offset == 13
    assert plan.label_exit_offset == label_exit_offset(policy)
    assert not hasattr(plan, "final_test")


def test_v0_4_fold_calendar_is_exact_24m_6m_6m_with_6m_step(
    hourly_candles: tuple[Candle, ...],
) -> None:
    policy = CandidatePolicy.locked_v0_4()

    plan = V04DevelopmentQualificationPlan.build(
        hourly_candles,
        _eligible(len(hourly_candles)),
        policy,
    )

    assert policy.initial_training_months == 24
    assert policy.calibration_months == 6
    assert policy.development_test_months == 6
    assert policy.walk_forward_step_months == 6

    for offset, fold in enumerate(plan.folds):
        calibration_start = _add_months(
            _START,
            24 + offset * 6,
        )
        calibration_end = _add_months(
            calibration_start,
            6,
        )
        development_test_end = _add_months(
            calibration_end,
            6,
        )

        # Undo the exact purge/embargo guards to recover
        # the raw preregistered calendar boundaries.
        training_boundary = fold.training.end_exclusive + policy.purge_candles
        calibration_start_boundary = fold.calibration.start_inclusive - policy.embargo_candles
        calibration_end_boundary = fold.calibration.end_exclusive + policy.purge_candles
        development_start_boundary = fold.development_test.start_inclusive - policy.embargo_candles
        development_end_boundary = fold.development_test.end_exclusive + policy.purge_candles

        assert fold.training.start_inclusive == 42

        assert hourly_candles[training_boundary].open_time == calibration_start
        assert hourly_candles[calibration_start_boundary].open_time == calibration_start
        assert hourly_candles[calibration_end_boundary].open_time == calibration_end
        assert hourly_candles[development_start_boundary].open_time == calibration_end
        assert hourly_candles[development_end_boundary].open_time == development_test_end

    # Fold 12 is the final complete fold.
    final_raw_end = plan.folds[-1].development_test.end_exclusive + policy.purge_candles
    assert hourly_candles[final_raw_end].open_time == datetime(2026, 7, 1, tzinfo=UTC)
    assert plan.dataset_end_exclusive == datetime(
        2026,
        8,
        1,
        tzinfo=UTC,
    )


def test_v0_4_used_labels_never_cross_fold_or_segment_boundaries(
    hourly_candles: tuple[Candle, ...],
) -> None:
    policy = CandidatePolicy.locked_v0_4()
    split = 5000

    plan = V04DevelopmentQualificationPlan.build(
        hourly_candles,
        _eligible(len(hourly_candles)),
        policy,
        _segments(hourly_candles, split),
    )

    assert plan.segment_boundary_indices == (split,)
    assert split in plan.boundary_indices

    exit_offset = label_exit_offset(policy)

    for boundary in plan.boundary_indices:
        assert all(
            not (decision_index < boundary <= decision_index + exit_offset)
            for decision_index in plan.used_label_indices
        )

        assert all(
            not (
                boundary - policy.purge_candles
                <= decision_index
                < boundary + policy.embargo_candles
            )
            for decision_index in plan.used_label_indices
        )

    for fold in plan.folds:
        for window, indices in (
            (fold.training, fold.training_indices),
            (fold.calibration, fold.calibration_indices),
            (
                fold.development_test,
                fold.development_test_indices,
            ),
        ):
            assert indices
            assert all(
                window.contains(index) and window.contains(index + exit_offset) for index in indices
            )


def test_v0_4_plan_rejects_wrong_cutoff_or_nonexact_policy(
    hourly_candles: tuple[Candle, ...],
) -> None:
    changed = _hourly_calendar_candles(
        end_exclusive=datetime(2026, 7, 1, tzinfo=UTC),
    )

    with pytest.raises(
        SplitBoundaryError,
        match=r"v0\.4 development dataset window",
    ):
        V04DevelopmentQualificationPlan.build(
            changed,
            _eligible(len(changed)),
            CandidatePolicy.locked_v0_4(),
        )

    with pytest.raises(
        SplitBoundaryError,
        match=r"exact Candidate v0\.4",
    ):
        V04DevelopmentQualificationPlan.build(
            hourly_candles,
            _eligible(len(hourly_candles)),
            CandidatePolicy.locked_v0_3(),
        )

    mutated = replace(
        CandidatePolicy.locked_v0_4(),
        purge_candles=11,
    )

    with pytest.raises(
        SplitBoundaryError,
        match=r"exact Candidate v0\.4",
    ):
        V04DevelopmentQualificationPlan.build(
            hourly_candles,
            _eligible(len(hourly_candles)),
            mutated,
        )


def test_v0_4_plan_rejects_unresolved_label_index(
    hourly_candles: tuple[Candle, ...],
) -> None:
    bad_index = len(hourly_candles) - 13

    with pytest.raises(
        SplitBoundaryError,
        match="unresolved label outcome",
    ):
        V04DevelopmentQualificationPlan.build(
            hourly_candles,
            (
                *_eligible(len(hourly_candles)),
                bad_index,
            ),
            CandidatePolicy.locked_v0_4(),
        )
