"""Sealed expanding-window chronological splits for Candidate v0.1."""

from bisect import bisect_left
from calendar import monthrange
from dataclasses import dataclass
from datetime import datetime, timedelta

from gemini_trading.domain.candle import Candle
from gemini_trading.strategy.contracts import IndexWindow
from gemini_trading.strategy.errors import (
    FinalTestSealError,
    InsufficientHistoryError,
    SplitBoundaryError,
)
from gemini_trading.strategy.policy import CandidatePolicy

_LABEL_EXIT_OFFSET = 4


@dataclass(frozen=True, slots=True)
class WalkForwardFold:
    """One immutable expanding training/calibration/development-test fold."""

    fold_number: int
    training: IndexWindow
    calibration: IndexWindow
    development_test: IndexWindow
    training_indices: tuple[int, ...]
    calibration_indices: tuple[int, ...]
    development_test_indices: tuple[int, ...]
    purge_candles: int
    embargo_candles: int

    def __post_init__(self) -> None:
        if isinstance(self.fold_number, bool) or self.fold_number < 1:
            raise ValueError("fold_number must be positive")
        if self.training.end_exclusive > self.calibration.start_inclusive:
            raise SplitBoundaryError("training and calibration windows overlap")
        if self.calibration.end_exclusive > self.development_test.start_inclusive:
            raise SplitBoundaryError("calibration and development-test windows overlap")
        if self.purge_candles < 0 or self.embargo_candles < 0:
            raise SplitBoundaryError("purge and embargo must be non-negative")
        for indexes, window, field_name in (
            (self.training_indices, self.training, "training_indices"),
            (self.calibration_indices, self.calibration, "calibration_indices"),
            (
                self.development_test_indices,
                self.development_test,
                "development_test_indices",
            ),
        ):
            if indexes != tuple(sorted(indexes)) or len(indexes) != len(set(indexes)):
                raise SplitBoundaryError(f"{field_name} must be unique and ordered")
            if any(
                not window.contains(index) or not window.contains(index + _LABEL_EXIT_OFFSET)
                for index in indexes
            ):
                raise SplitBoundaryError(f"{field_name} contains a boundary-crossing label")


@dataclass(frozen=True, slots=True)
class ChronologicalSplitPlan:
    """One final-test-sealed chronological evaluation plan."""

    schema_version: str
    dataset_start_time: datetime
    dataset_end_exclusive: datetime
    final_test_start_time: datetime
    final_test_boundary_index: int
    final_test: IndexWindow
    final_test_indices: tuple[int, ...]
    folds: tuple[WalkForwardFold, ...]
    boundary_indices: tuple[int, ...]
    used_label_indices: tuple[int, ...]
    purge_candles: int
    embargo_candles: int
    label_exit_offset: int

    def __post_init__(self) -> None:
        if not self.schema_version.strip():
            raise ValueError("split plan schema_version must not be empty")
        if not self.dataset_start_time < self.final_test_start_time < self.dataset_end_exclusive:
            raise FinalTestSealError("final-test timestamps must be strictly inside the dataset")
        if self.final_test_boundary_index < 0:
            raise FinalTestSealError("final_test_boundary_index must be non-negative")
        if self.boundary_indices != tuple(sorted(set(self.boundary_indices))):
            raise SplitBoundaryError("boundary_indices must be unique and ordered")
        if self.used_label_indices != tuple(sorted(set(self.used_label_indices))):
            raise SplitBoundaryError("used_label_indices must be unique and ordered")
        if self.final_test_indices != tuple(sorted(set(self.final_test_indices))):
            raise SplitBoundaryError("final_test_indices must be unique and ordered")
        if any(
            not self.final_test.contains(index)
            or not self.final_test.contains(index + self.label_exit_offset)
            for index in self.final_test_indices
        ):
            raise FinalTestSealError("final-test label crosses the sealed window")
        if any(
            _crosses_boundary(index, boundary, self.label_exit_offset)
            or _inside_guard_zone(
                index,
                boundary,
                purge=self.purge_candles,
                embargo=self.embargo_candles,
            )
            for index in self.used_label_indices
            for boundary in self.boundary_indices
        ):
            raise SplitBoundaryError("used label crosses a protected boundary")

    @classmethod
    def build(
        cls,
        candles: tuple[Candle, ...],
        eligible_indices: tuple[int, ...],
        policy: CandidatePolicy,
    ) -> "ChronologicalSplitPlan":
        """Build the locked expanding-window and untouched-final-test plan."""

        dataset_start, dataset_end = _validate_candles(candles)
        if _add_years(dataset_start, policy.minimum_history_years) > dataset_end:
            raise InsufficientHistoryError(
                f"candidate study requires {policy.minimum_history_years} years of history"
            )
        eligible = _validate_eligible_indices(eligible_indices, len(candles))
        if not eligible:
            raise InsufficientHistoryError("candidate study has no eligible observations")
        open_times = tuple(candle.open_time for candle in candles)
        final_test_start = _add_months(dataset_end, -policy.final_test_months)
        final_boundary = bisect_left(open_times, final_test_start)
        if final_boundary <= eligible[0] or final_boundary >= len(candles):
            raise FinalTestSealError("final-test boundary is outside eligible history")

        raw_fold_boundaries: list[tuple[int, int, int]] = []
        step = 0
        while True:
            calibration_start_time = _add_months(
                dataset_start,
                policy.initial_training_months + step * policy.walk_forward_step_months,
            )
            calibration_end_time = _add_months(
                calibration_start_time,
                policy.calibration_months,
            )
            development_test_end_time = _add_months(
                calibration_end_time,
                policy.development_test_months,
            )
            if development_test_end_time > final_test_start:
                break
            calibration_start = bisect_left(open_times, calibration_start_time)
            calibration_end = bisect_left(open_times, calibration_end_time)
            development_test_end = bisect_left(open_times, development_test_end_time)
            raw_fold_boundaries.append(
                (calibration_start, calibration_end, development_test_end)
            )
            step += 1
        if len(raw_fold_boundaries) < policy.minimum_development_folds:
            raise InsufficientHistoryError(
                "candidate study does not contain the required walk-forward folds"
            )

        boundaries = tuple(
            sorted(
                {
                    final_boundary,
                    *(
                        boundary
                        for fold_boundaries in raw_fold_boundaries
                        for boundary in fold_boundaries
                    ),
                }
            )
        )
        eligible_set = set(eligible)
        first_eligible = eligible[0]
        folds: list[WalkForwardFold] = []
        all_used: set[int] = set()
        for fold_number, (
            calibration_start,
            calibration_end,
            development_test_end,
        ) in enumerate(raw_fold_boundaries, start=1):
            training = _window(
                first_eligible,
                calibration_start - policy.purge_candles,
                "training",
            )
            calibration = _window(
                calibration_start + policy.embargo_candles,
                calibration_end - policy.purge_candles,
                "calibration",
            )
            development_test = _window(
                calibration_end + policy.embargo_candles,
                development_test_end - policy.purge_candles,
                "development_test",
            )
            training_indices = _safe_indices(
                training,
                eligible_set,
                boundaries,
                policy,
            )
            calibration_indices = _safe_indices(
                calibration,
                eligible_set,
                boundaries,
                policy,
            )
            development_test_indices = _safe_indices(
                development_test,
                eligible_set,
                boundaries,
                policy,
            )
            if not training_indices or not calibration_indices or not development_test_indices:
                raise InsufficientHistoryError("walk-forward fold contains an empty protected window")
            all_used.update(training_indices)
            all_used.update(calibration_indices)
            all_used.update(development_test_indices)
            folds.append(
                WalkForwardFold(
                    fold_number=fold_number,
                    training=training,
                    calibration=calibration,
                    development_test=development_test,
                    training_indices=training_indices,
                    calibration_indices=calibration_indices,
                    development_test_indices=development_test_indices,
                    purge_candles=policy.purge_candles,
                    embargo_candles=policy.embargo_candles,
                )
            )

        final_test = _window(
            final_boundary + policy.embargo_candles,
            len(candles) - _LABEL_EXIT_OFFSET,
            "final_test",
        )
        final_indices = _safe_indices(
            final_test,
            eligible_set,
            boundaries,
            policy,
        )
        if not final_indices:
            raise InsufficientHistoryError("untouched final test has no protected observations")
        all_used.update(final_indices)
        return cls(
            schema_version="candidate-chronological-split-plan-v1",
            dataset_start_time=dataset_start,
            dataset_end_exclusive=dataset_end,
            final_test_start_time=final_test_start,
            final_test_boundary_index=final_boundary,
            final_test=final_test,
            final_test_indices=final_indices,
            folds=tuple(folds),
            boundary_indices=boundaries,
            used_label_indices=tuple(sorted(all_used)),
            purge_candles=policy.purge_candles,
            embargo_candles=policy.embargo_candles,
            label_exit_offset=_LABEL_EXIT_OFFSET,
        )


def _validate_candles(candles: tuple[Candle, ...]) -> tuple[datetime, datetime]:
    if not candles:
        raise InsufficientHistoryError("chronological split plan requires candles")
    first = candles[0]
    prior = None
    interval = None
    for candle in candles:
        if not candle.completed:
            raise SplitBoundaryError("split plan requires completed candles")
        if candle.instrument != first.instrument or candle.timeframe != first.timeframe:
            raise SplitBoundaryError("split candles must share instrument and timeframe")
        if prior is not None:
            current_interval = candle.open_time - prior.open_time
            if interval is None:
                interval = current_interval
            if current_interval != interval:
                raise SplitBoundaryError("split candles must be exactly continuous")
            if candle.open_time != prior.close_time + timedelta(milliseconds=1):
                raise SplitBoundaryError("split candle boundaries must be contiguous")
        prior = candle
    dataset_end = candles[-1].close_time + timedelta(milliseconds=1)
    return candles[0].open_time, dataset_end


def _validate_eligible_indices(
    eligible_indices: tuple[int, ...],
    candle_count: int,
) -> tuple[int, ...]:
    if any(isinstance(index, bool) or index < 0 for index in eligible_indices):
        raise SplitBoundaryError("eligible indexes must be non-negative integers")
    if len(eligible_indices) != len(set(eligible_indices)):
        raise SplitBoundaryError("eligible indexes must be unique")
    ordered = tuple(sorted(eligible_indices))
    if any(index + _LABEL_EXIT_OFFSET >= candle_count for index in ordered):
        raise SplitBoundaryError("eligible index has an unresolved label outcome")
    return ordered


def _safe_indices(
    window: IndexWindow,
    eligible: set[int],
    boundaries: tuple[int, ...],
    policy: CandidatePolicy,
) -> tuple[int, ...]:
    return tuple(
        index
        for index in range(window.start_inclusive, window.end_exclusive)
        if index in eligible
        and window.contains(index + _LABEL_EXIT_OFFSET)
        and all(
            not _crosses_boundary(index, boundary, _LABEL_EXIT_OFFSET)
            and not _inside_guard_zone(
                index,
                boundary,
                purge=policy.purge_candles,
                embargo=policy.embargo_candles,
            )
            for boundary in boundaries
        )
    )


def _crosses_boundary(index: int, boundary: int, exit_offset: int) -> bool:
    return index < boundary <= index + exit_offset


def _inside_guard_zone(
    index: int,
    boundary: int,
    *,
    purge: int,
    embargo: int,
) -> bool:
    return boundary - purge <= index < boundary + embargo


def _window(start: int, end: int, name: str) -> IndexWindow:
    if end <= start:
        raise SplitBoundaryError(f"{name} window is empty after purge and embargo")
    return IndexWindow(start_inclusive=start, end_exclusive=end)


def _add_years(value: datetime, years: int) -> datetime:
    try:
        return value.replace(year=value.year + years)
    except ValueError:
        return value.replace(year=value.year + years, day=28)


def _add_months(value: datetime, months: int) -> datetime:
    zero_based_month = value.month - 1 + months
    year = value.year + zero_based_month // 12
    month = zero_based_month % 12 + 1
    day = min(value.day, monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)
