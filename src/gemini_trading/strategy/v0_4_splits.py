"""Immutable hourly development-only chronological splits for Candidate v0.4."""

from __future__ import annotations

from bisect import bisect_left
from calendar import monthrange
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from gemini_trading.data.segments import CandleSegmentManifest
from gemini_trading.domain.candle import Candle
from gemini_trading.domain.timeframe import Timeframe
from gemini_trading.strategy.contracts import IndexWindow
from gemini_trading.strategy.errors import (
    InsufficientHistoryError,
    SplitBoundaryError,
)
from gemini_trading.strategy.labels import label_exit_offset
from gemini_trading.strategy.policy import CandidatePolicy
from gemini_trading.strategy.splits import WalkForwardFold

_V0_4_DEVELOPMENT_START = datetime(2018, 1, 1, tzinfo=UTC)
_V0_4_DEVELOPMENT_END = datetime(2026, 8, 1, tzinfo=UTC)
_V0_4_DEVELOPMENT_FOLD_COUNT = 12
_SCHEMA_VERSION = "candidate-v0.4-development-qualification-plan-v1"


@dataclass(frozen=True, slots=True)
class V04DevelopmentQualificationPlan:
    """Candidate v0.4 twelve-fold hourly development plan."""

    schema_version: str
    dataset_start_time: datetime
    dataset_end_exclusive: datetime
    folds: tuple[WalkForwardFold, ...]
    boundary_indices: tuple[int, ...]
    segment_boundary_indices: tuple[int, ...]
    used_label_indices: tuple[int, ...]
    purge_candles: int
    embargo_candles: int
    label_exit_offset: int

    def __post_init__(self) -> None:
        if self.schema_version != _SCHEMA_VERSION:
            raise ValueError("unsupported v0.4 development qualification plan schema")

        if (
            self.dataset_start_time != _V0_4_DEVELOPMENT_START
            or self.dataset_end_exclusive != _V0_4_DEVELOPMENT_END
        ):
            raise SplitBoundaryError("v0.4 development dataset window changed")

        if len(self.folds) != _V0_4_DEVELOPMENT_FOLD_COUNT:
            raise InsufficientHistoryError("v0.4 development plan requires exactly 12 folds")

        if tuple(fold.fold_number for fold in self.folds) != tuple(
            range(1, _V0_4_DEVELOPMENT_FOLD_COUNT + 1)
        ):
            raise SplitBoundaryError("v0.4 development fold numbering changed")

        if self.boundary_indices != tuple(sorted(set(self.boundary_indices))):
            raise SplitBoundaryError("boundary_indices must be unique and ordered")

        if self.segment_boundary_indices != tuple(sorted(set(self.segment_boundary_indices))):
            raise SplitBoundaryError("segment_boundary_indices must be unique and ordered")

        if not set(self.segment_boundary_indices) <= set(self.boundary_indices):
            raise SplitBoundaryError("segment boundaries must be protected boundaries")

        if self.used_label_indices != tuple(sorted(set(self.used_label_indices))):
            raise SplitBoundaryError("used_label_indices must be unique and ordered")

        expected_offset = label_exit_offset(CandidatePolicy.locked_v0_4())
        if self.label_exit_offset != expected_offset:
            raise SplitBoundaryError("v0.4 label exit offset changed")

        if self.purge_candles != 12 or self.embargo_candles != 12:
            raise SplitBoundaryError("v0.4 purge/embargo contract changed")

        if any(
            _crosses_boundary(
                index,
                boundary,
                self.label_exit_offset,
            )
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
        segment_manifest: CandleSegmentManifest | None = None,
    ) -> V04DevelopmentQualificationPlan:
        """Build every complete preregistered v0.4 development fold."""

        if policy != CandidatePolicy.locked_v0_4():
            raise SplitBoundaryError("development qualification requires exact Candidate v0.4")

        dataset_start, dataset_end = _validate_candles(
            candles,
            segment_manifest,
        )

        if dataset_start != _V0_4_DEVELOPMENT_START or dataset_end != _V0_4_DEVELOPMENT_END:
            raise SplitBoundaryError("v0.4 development dataset window changed")

        exit_offset = label_exit_offset(policy)

        eligible = _validate_eligible_indices(
            eligible_indices,
            len(candles),
            exit_offset,
        )

        if not eligible:
            raise InsufficientHistoryError("candidate study has no eligible observations")

        open_times = tuple(candle.open_time for candle in candles)

        raw_fold_boundaries: list[tuple[int, int, int]] = []

        step = 0
        while True:
            calibration_start_time = _add_months(
                dataset_start,
                (policy.initial_training_months + step * policy.walk_forward_step_months),
            )
            calibration_end_time = _add_months(
                calibration_start_time,
                policy.calibration_months,
            )
            development_test_end_time = _add_months(
                calibration_end_time,
                policy.development_test_months,
            )

            if development_test_end_time > dataset_end:
                break

            raw_fold_boundaries.append(
                (
                    bisect_left(
                        open_times,
                        calibration_start_time,
                    ),
                    bisect_left(
                        open_times,
                        calibration_end_time,
                    ),
                    bisect_left(
                        open_times,
                        development_test_end_time,
                    ),
                )
            )
            step += 1

        if len(raw_fold_boundaries) != _V0_4_DEVELOPMENT_FOLD_COUNT:
            raise InsufficientHistoryError("v0.4 development plan requires exactly 12 folds")

        segment_boundaries = (
            segment_manifest.boundary_indices if segment_manifest is not None else ()
        )

        boundaries = tuple(
            sorted(
                {
                    *segment_boundaries,
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
        ) in enumerate(
            raw_fold_boundaries,
            start=1,
        ):
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
                exit_offset,
            )
            calibration_indices = _safe_indices(
                calibration,
                eligible_set,
                boundaries,
                policy,
                exit_offset,
            )
            development_test_indices = _safe_indices(
                development_test,
                eligible_set,
                boundaries,
                policy,
                exit_offset,
            )

            if not training_indices or not calibration_indices or not development_test_indices:
                raise InsufficientHistoryError(
                    "walk-forward fold contains an empty protected window"
                )

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

        return cls(
            schema_version=_SCHEMA_VERSION,
            dataset_start_time=dataset_start,
            dataset_end_exclusive=dataset_end,
            folds=tuple(folds),
            boundary_indices=boundaries,
            segment_boundary_indices=segment_boundaries,
            used_label_indices=tuple(sorted(all_used)),
            purge_candles=policy.purge_candles,
            embargo_candles=policy.embargo_candles,
            label_exit_offset=exit_offset,
        )


def _validate_candles(
    candles: tuple[Candle, ...],
    segment_manifest: CandleSegmentManifest | None,
) -> tuple[datetime, datetime]:
    if not candles:
        raise InsufficientHistoryError("chronological split plan requires candles")

    first = candles[0]

    if first.timeframe is not Timeframe.H1:
        raise SplitBoundaryError("v0.4 development split requires hourly candles")

    boundaries: set[int] = (
        set(segment_manifest.boundary_indices) if segment_manifest is not None else set()
    )

    if segment_manifest is not None and (
        segment_manifest.segments[0].start_index != 0
        or segment_manifest.segments[-1].end_exclusive != len(candles)
    ):
        raise SplitBoundaryError("split segment evidence does not cover candles")

    prior: Candle | None = None
    interval = Timeframe.H1.duration

    for index, candle in enumerate(candles):
        if not candle.completed:
            raise SplitBoundaryError("split plan requires completed candles")

        if candle.instrument != first.instrument or candle.timeframe is not Timeframe.H1:
            raise SplitBoundaryError("split candles must share instrument and hourly timeframe")

        if prior is not None and index not in boundaries:
            if candle.open_time - prior.open_time != interval:
                raise SplitBoundaryError("split candles must be continuous inside segments")

            if candle.open_time != prior.close_time + timedelta(milliseconds=1):
                raise SplitBoundaryError("split candle boundaries must be contiguous")

        prior = candle

    dataset_end = candles[-1].close_time + timedelta(milliseconds=1)

    return candles[0].open_time, dataset_end


def _validate_eligible_indices(
    eligible_indices: tuple[int, ...],
    candle_count: int,
    exit_offset: int,
) -> tuple[int, ...]:
    if any(isinstance(index, bool) or index < 0 for index in eligible_indices):
        raise SplitBoundaryError("eligible indexes must be non-negative integers")

    if len(eligible_indices) != len(set(eligible_indices)):
        raise SplitBoundaryError("eligible indexes must be unique")

    ordered = tuple(sorted(eligible_indices))

    if any(index + exit_offset >= candle_count for index in ordered):
        raise SplitBoundaryError("eligible index has an unresolved label outcome")

    return ordered


def _safe_indices(
    window: IndexWindow,
    eligible: set[int],
    boundaries: tuple[int, ...],
    policy: CandidatePolicy,
    exit_offset: int,
) -> tuple[int, ...]:
    return tuple(
        index
        for index in range(
            window.start_inclusive,
            window.end_exclusive,
        )
        if index in eligible
        and window.contains(index + exit_offset)
        and all(
            not _crosses_boundary(
                index,
                boundary,
                exit_offset,
            )
            and not _inside_guard_zone(
                index,
                boundary,
                purge=policy.purge_candles,
                embargo=policy.embargo_candles,
            )
            for boundary in boundaries
        )
    )


def _crosses_boundary(
    index: int,
    boundary: int,
    exit_offset: int,
) -> bool:
    return index < boundary <= index + exit_offset


def _inside_guard_zone(
    index: int,
    boundary: int,
    *,
    purge: int,
    embargo: int,
) -> bool:
    return boundary - purge <= index < boundary + embargo


def _window(
    start: int,
    end: int,
    name: str,
) -> IndexWindow:
    if end <= start:
        raise SplitBoundaryError(f"{name} window is empty after purge and embargo")

    return IndexWindow(
        start_inclusive=start,
        end_exclusive=end,
    )


def _add_months(
    value: datetime,
    months: int,
) -> datetime:
    zero_based_month = value.month - 1 + months
    year = value.year + zero_based_month // 12
    month = zero_based_month % 12 + 1
    day = min(
        value.day,
        monthrange(year, month)[1],
    )

    return value.replace(
        year=year,
        month=month,
        day=day,
    )


__all__ = [
    "V04DevelopmentQualificationPlan",
]
