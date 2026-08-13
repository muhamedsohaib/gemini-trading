"""Immutable development-only chronological splits for Candidate v0.3."""

from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass
from datetime import UTC, datetime

from gemini_trading.data.segments import CandleSegmentManifest
from gemini_trading.domain.candle import Candle
from gemini_trading.strategy.errors import InsufficientHistoryError, SplitBoundaryError
from gemini_trading.strategy.policy import CandidatePolicy
from gemini_trading.strategy.splits import (
    WalkForwardFold,
    _add_months,
    _crosses_boundary,
    _inside_guard_zone,
    _safe_indices,
    _validate_candles,
    _validate_eligible_indices,
    _window,
)

_LABEL_EXIT_OFFSET = 4
_V0_3_DEVELOPMENT_START = datetime(2018, 1, 1, tzinfo=UTC)
_V0_3_DEVELOPMENT_END = datetime(2026, 8, 1, tzinfo=UTC)
_V0_3_DEVELOPMENT_FOLD_COUNT = 12


@dataclass(frozen=True, slots=True)
class V03DevelopmentQualificationPlan:
    """Candidate v0.3 development folds over the exact preregistered era."""

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
        if self.schema_version != "candidate-v0.3-development-qualification-plan-v1":
            raise ValueError("unsupported v0.3 development qualification plan schema")
        if (
            self.dataset_start_time != _V0_3_DEVELOPMENT_START
            or self.dataset_end_exclusive != _V0_3_DEVELOPMENT_END
        ):
            raise SplitBoundaryError("v0.3 development dataset window changed")
        if len(self.folds) != _V0_3_DEVELOPMENT_FOLD_COUNT:
            raise InsufficientHistoryError("v0.3 development plan requires exactly 12 folds")
        if tuple(fold.fold_number for fold in self.folds) != tuple(
            range(1, _V0_3_DEVELOPMENT_FOLD_COUNT + 1)
        ):
            raise SplitBoundaryError("v0.3 development fold numbering changed")
        if self.boundary_indices != tuple(sorted(set(self.boundary_indices))):
            raise SplitBoundaryError("boundary_indices must be unique and ordered")
        if self.segment_boundary_indices != tuple(sorted(set(self.segment_boundary_indices))):
            raise SplitBoundaryError("segment_boundary_indices must be unique and ordered")
        if not set(self.segment_boundary_indices) <= set(self.boundary_indices):
            raise SplitBoundaryError("segment boundaries must be protected boundaries")
        if self.used_label_indices != tuple(sorted(set(self.used_label_indices))):
            raise SplitBoundaryError("used_label_indices must be unique and ordered")
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
        segment_manifest: CandleSegmentManifest | None = None,
    ) -> V03DevelopmentQualificationPlan:
        """Build every complete v0.3 fold without turning the final month into a partial fold."""

        if (
            policy.strategy_id != "candidate.multi_model.v0_3"
            or policy.policy_version != "candidate-multi-model-v0.3"
            or policy.schema_version != "candidate-strategy-policy-v3"
        ):
            raise SplitBoundaryError("development qualification requires exact Candidate v0.3")
        dataset_start, dataset_end = _validate_candles(candles, segment_manifest)
        if dataset_start != _V0_3_DEVELOPMENT_START or dataset_end != _V0_3_DEVELOPMENT_END:
            raise SplitBoundaryError("v0.3 development dataset window changed")
        eligible = _validate_eligible_indices(eligible_indices, len(candles))
        if not eligible:
            raise InsufficientHistoryError("candidate study has no eligible observations")

        open_times = tuple(candle.open_time for candle in candles)
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
            if development_test_end_time > dataset_end:
                break
            raw_fold_boundaries.append(
                (
                    bisect_left(open_times, calibration_start_time),
                    bisect_left(open_times, calibration_end_time),
                    bisect_left(open_times, development_test_end_time),
                )
            )
            step += 1
        if len(raw_fold_boundaries) != _V0_3_DEVELOPMENT_FOLD_COUNT:
            raise InsufficientHistoryError("v0.3 development plan requires exactly 12 folds")

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
            training_indices = _safe_indices(training, eligible_set, boundaries, policy)
            calibration_indices = _safe_indices(calibration, eligible_set, boundaries, policy)
            development_test_indices = _safe_indices(
                development_test,
                eligible_set,
                boundaries,
                policy,
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
            schema_version="candidate-v0.3-development-qualification-plan-v1",
            dataset_start_time=dataset_start,
            dataset_end_exclusive=dataset_end,
            folds=tuple(folds),
            boundary_indices=boundaries,
            segment_boundary_indices=segment_boundaries,
            used_label_indices=tuple(sorted(all_used)),
            purge_candles=policy.purge_candles,
            embargo_candles=policy.embargo_candles,
            label_exit_offset=_LABEL_EXIT_OFFSET,
        )


__all__ = ["V03DevelopmentQualificationPlan"]
