"""Fold-local regime-owned predictions for Candidate v0.4 research."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from gemini_trading.strategy.calibration import (
    ExpectedReturnMap,
    PlattArtifact,
    apply_expected_return,
    apply_platt,
    fit_expected_return_map,
    fit_platt_calibrator,
)
from gemini_trading.strategy.contracts import (
    RegimeState,
    SpecialistKind,
)
from gemini_trading.strategy.entry_selectivity import (
    V04EntryThresholdArtifact,
    build_v0_4_entry_threshold_artifact,
)
from gemini_trading.strategy.errors import StudyArtifactError
from gemini_trading.strategy.features import (
    FeatureMatrix,
    FeatureRow,
)
from gemini_trading.strategy.labels import (
    LabelObservation,
    LabelVector,
)
from gemini_trading.strategy.models import (
    MeanReversionSpecialistTrainer,
    ModelArtifact,
    TrendSpecialistTrainer,
    predict_raw,
)
from gemini_trading.strategy.policy import CandidatePolicy
from gemini_trading.strategy.regimes import (
    RegimeClassifier,
    RegimeObservation,
)
from gemini_trading.strategy.v0_4_context import ContextObservation
from gemini_trading.strategy.v0_4_features import V04FeatureRegistry
from gemini_trading.strategy.v0_4_policy import V04MultiTimeframePolicy

_ZERO = Decimal("0")
_ONE = Decimal("1")


@dataclass(frozen=True, slots=True)
class V04Prediction:
    """One point-in-time Candidate v0.4 specialist prediction row."""

    candle_index: int
    tactical_open_time: datetime
    context_sha256: str
    context_close_time: datetime
    regime: RegimeObservation
    trend_raw: float
    mean_reversion_raw: float
    trend_probability: Decimal
    mean_reversion_probability: Decimal
    trend_expected_return: Decimal
    mean_reversion_expected_return: Decimal
    eligible_specialist: SpecialistKind | None

    def __post_init__(self) -> None:
        if isinstance(self.candle_index, bool) or self.candle_index < 0:
            raise ValueError("Candidate v0.4 prediction candle_index must be non-negative")

        if self.tactical_open_time.tzinfo is None or self.tactical_open_time.utcoffset() is None:
            raise ValueError("Candidate v0.4 tactical timestamp must be timezone-aware")

        if self.context_close_time.tzinfo is None or self.context_close_time.utcoffset() is None:
            raise ValueError("Candidate v0.4 context timestamp must be timezone-aware")

        if self.context_close_time > self.tactical_open_time:
            raise ValueError("Candidate v0.4 prediction contains future context")

        if len(self.context_sha256) != 64:
            raise ValueError("Candidate v0.4 context identity must be SHA-256")

        for value in (
            self.trend_raw,
            self.mean_reversion_raw,
        ):
            if not math.isfinite(value):
                raise ValueError("Candidate v0.4 raw model scores must be finite")

        for value in (
            self.trend_probability,
            self.mean_reversion_probability,
        ):
            if not value.is_finite() or value < _ZERO or value > _ONE:
                raise ValueError("Candidate v0.4 probabilities must be within [0, 1]")

        for value in (
            self.trend_expected_return,
            self.mean_reversion_expected_return,
        ):
            if not value.is_finite():
                raise ValueError("Candidate v0.4 expected returns must be finite")

        if (
            self.eligible_specialist is SpecialistKind.TREND
            and self.regime.state is not RegimeState.TRENDING
        ):
            raise ValueError("trend ownership requires TRENDING context")

        if (
            self.eligible_specialist is SpecialistKind.MEAN_REVERSION
            and self.regime.state is not RegimeState.RANGING
        ):
            raise ValueError("mean-reversion ownership requires RANGING context")


@dataclass(frozen=True, slots=True)
class V04PredictionContext:
    """One complete fold-local v0.4 learned prediction context."""

    fold_number: int

    trend_model: ModelArtifact
    mean_reversion_model: ModelArtifact

    trend_platt: PlattArtifact
    mean_reversion_platt: PlattArtifact

    trend_return_map: ExpectedReturnMap
    mean_reversion_return_map: ExpectedReturnMap

    trend_training_indices: tuple[int, ...]
    mean_reversion_training_indices: tuple[int, ...]

    trend_calibration_indices: tuple[int, ...]
    mean_reversion_calibration_indices: tuple[int, ...]

    primary_thresholds: Mapping[
        SpecialistKind,
        V04EntryThresholdArtifact,
    ]
    sensitivity_thresholds: Mapping[
        tuple[SpecialistKind, Decimal],
        V04EntryThresholdArtifact,
    ]

    predictions: tuple[V04Prediction, ...]

    def __post_init__(self) -> None:
        if isinstance(self.fold_number, bool) or self.fold_number < 1:
            raise ValueError("Candidate v0.4 prediction fold_number must be positive")

        if self.trend_model.specialist is not SpecialistKind.TREND:
            raise ValueError("Candidate v0.4 trend model specialist changed")

        if self.mean_reversion_model.specialist is not SpecialistKind.MEAN_REVERSION:
            raise ValueError("Candidate v0.4 mean-reversion model specialist changed")

        for indices in (
            self.trend_training_indices,
            self.mean_reversion_training_indices,
            self.trend_calibration_indices,
            self.mean_reversion_calibration_indices,
        ):
            if not indices:
                raise ValueError("Candidate v0.4 specialist domains must not be empty")
            if indices != tuple(sorted(set(indices))):
                raise ValueError("Candidate v0.4 specialist domains must be ordered and unique")

        required_specialists = {
            SpecialistKind.TREND,
            SpecialistKind.MEAN_REVERSION,
        }

        if set(self.primary_thresholds) != required_specialists:
            raise ValueError("Candidate v0.4 primary threshold inventory changed")

        adjunct = V04MultiTimeframePolicy.locked()
        expected_sensitivity = {
            (specialist, percentile)
            for specialist in required_specialists
            for percentile in adjunct.sensitivity_percentiles
        }

        if set(self.sensitivity_thresholds) != expected_sensitivity:
            raise ValueError("Candidate v0.4 sensitivity threshold inventory changed")

        all_thresholds = (
            *self.primary_thresholds.values(),
            *self.sensitivity_thresholds.values(),
        )

        if any(artifact.fold_number != self.fold_number for artifact in all_thresholds):
            raise ValueError("Candidate v0.4 threshold fold identity changed")

        prediction_indices = tuple(item.candle_index for item in self.predictions)

        if prediction_indices != tuple(sorted(set(prediction_indices))):
            raise ValueError("Candidate v0.4 predictions must be ordered and unique")


@dataclass(frozen=True, slots=True)
class _MatrixAccess:
    rows: Mapping[int, FeatureRow]
    columns: Mapping[str, int]

    @classmethod
    def build(
        cls,
        matrix: FeatureMatrix,
    ) -> _MatrixAccess:
        return cls(
            rows={row.candle_index: row for row in matrix.rows},
            columns={name: column for column, name in enumerate(matrix.feature_names)},
        )

    def row(self, index: int) -> FeatureRow:
        try:
            return self.rows[index]
        except KeyError:
            raise StudyArtifactError(
                f"Candidate v0.4 feature row is unavailable: {index}"
            ) from None

    def value(
        self,
        index: int,
        name: str,
    ) -> Decimal:
        row = self.row(index)

        try:
            column = self.columns[name]
        except KeyError:
            raise StudyArtifactError(f"Candidate v0.4 feature is unavailable: {name}") from None

        return row.values[column]


def _validate_v0_4_policy(
    policy: CandidatePolicy,
) -> None:
    if policy != CandidatePolicy.locked_v0_4():
        raise StudyArtifactError("v0.4 prediction context requires exact Candidate v0.4 policy")


def _validate_partition(
    *,
    name: str,
    indices: tuple[int, ...],
    access: _MatrixAccess,
    labels: Mapping[int, LabelObservation],
    context_join: tuple[ContextObservation | None, ...],
) -> None:
    if not indices:
        raise StudyArtifactError(f"Candidate v0.4 {name} partition must not be empty")

    if indices != tuple(sorted(set(indices))):
        raise StudyArtifactError(f"Candidate v0.4 {name} indices must be ordered and unique")

    for index in indices:
        if isinstance(index, bool) or index < 0:
            raise StudyArtifactError(f"Candidate v0.4 {name} indices must be non-negative integers")

        access.row(index)

        if index not in labels:
            raise StudyArtifactError(f"Candidate v0.4 label is unavailable: {index}")

        _context_for(
            index=index,
            access=access,
            context_join=context_join,
        )


def _context_for(
    *,
    index: int,
    access: _MatrixAccess,
    context_join: tuple[ContextObservation | None, ...],
) -> ContextObservation:
    if index >= len(context_join):
        raise StudyArtifactError(f"Candidate v0.4 context join is unavailable: {index}")

    observation = context_join[index]

    if observation is None:
        raise StudyArtifactError(f"Candidate v0.4 completed context is unavailable: {index}")

    row = access.row(index)

    if observation.candle.close_time > row.candle_open_time:
        raise StudyArtifactError("Candidate v0.4 context join contains future evidence")

    if observation.constituent_indices[-1] >= index:
        raise StudyArtifactError("Candidate v0.4 context contains future hourly constituents")

    return observation


def _classify_context(
    *,
    index: int,
    access: _MatrixAccess,
    policy: CandidatePolicy,
    sign_streak: int,
) -> RegimeObservation:
    context_names = V04MultiTimeframePolicy.locked().context_feature_names

    signed_spread = access.value(
        index,
        context_names[0],
    )
    volatility_ratio = access.value(
        index,
        context_names[1],
    )
    true_range_ratio = access.value(
        index,
        context_names[2],
    )

    return RegimeClassifier(policy).classify(
        candle_index=index,
        trend_strength=signed_spread,
        volatility_ratio=volatility_ratio,
        true_range_ratio=true_range_ratio,
        sign_streak=sign_streak,
    )


def _stretch_active(
    *,
    index: int,
    access: _MatrixAccess,
) -> bool:
    return access.value(
        index,
        "close_zscore_24",
    ) <= Decimal("-0.75") or access.value(
        index,
        "drawdown_from_high_24",
    ) >= Decimal("0.02")


def _context_sign(
    value: Decimal,
) -> int:
    if value > _ZERO:
        return 1

    if value < _ZERO:
        return -1

    return 0


def _context_sign_streaks(
    *,
    access: _MatrixAccess,
    context_join: tuple[ContextObservation | None, ...],
) -> dict[int, int]:
    """Derive EMA-spread streaks once per distinct completed 4h context."""

    signed_spread_name = V04MultiTimeframePolicy.locked().context_feature_names[0]

    result: dict[int, int] = {}

    digest_spreads: dict[str, Decimal] = {}
    digest_streaks: dict[str, int] = {}

    previous_digest: str | None = None
    previous_open_time: datetime | None = None
    previous_sign = 0
    previous_streak = 0

    for index in sorted(access.rows):
        observation = _context_for(
            index=index,
            access=access,
            context_join=context_join,
        )

        digest = observation.constituent_sha256
        spread = access.value(
            index,
            signed_spread_name,
        )

        if digest in digest_spreads:
            if digest != previous_digest:
                raise StudyArtifactError(
                    "Candidate v0.4 context identity reappeared out of chronological order"
                )

            if digest_spreads[digest] != spread:
                raise StudyArtifactError(
                    "Candidate v0.4 repeated context has inconsistent signed EMA spread"
                )

            result[index] = digest_streaks[digest]
            continue

        current_open_time = observation.candle.open_time

        if previous_open_time is not None and current_open_time <= previous_open_time:
            raise StudyArtifactError(
                "Candidate v0.4 distinct contexts must be strictly chronological"
            )

        sign = _context_sign(spread)

        contiguous = (
            previous_open_time is not None
            and current_open_time == previous_open_time + timedelta(hours=4)
        )

        if sign == 0:
            streak = 0
        elif contiguous and sign == previous_sign:
            streak = previous_streak + 1
        else:
            # Sign changes and non-contiguous context evidence
            # both reset the streak to the current context.
            streak = 1

        digest_spreads[digest] = spread
        digest_streaks[digest] = streak
        result[index] = streak

        previous_digest = digest
        previous_open_time = current_open_time
        previous_sign = sign
        previous_streak = streak

    return result


def _specialist_domains(
    *,
    indices: tuple[int, ...],
    access: _MatrixAccess,
    policy: CandidatePolicy,
    sign_streaks: Mapping[int, int],
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    trend: list[int] = []
    mean_reversion: list[int] = []

    for index in indices:
        regime = _classify_context(
            index=index,
            access=access,
            policy=policy,
            sign_streak=sign_streaks[index],
        )

        if regime.state is RegimeState.TRENDING:
            trend.append(index)

        elif regime.state is RegimeState.RANGING and _stretch_active(
            index=index,
            access=access,
        ):
            mean_reversion.append(index)

    return tuple(trend), tuple(mean_reversion)


def _model_values(
    *,
    access: _MatrixAccess,
    index: int,
    model: ModelArtifact,
) -> dict[str, Decimal]:
    return {
        name: access.value(
            index,
            name,
        )
        for name in model.feature_names
    }


def _raw_scores(
    *,
    access: _MatrixAccess,
    indices: Sequence[int],
    model: ModelArtifact,
) -> tuple[float, ...]:
    return tuple(
        predict_raw(
            model,
            _model_values(
                access=access,
                index=index,
                model=model,
            ),
        )
        for index in indices
    )


def _fit_calibrator(
    *,
    scores: tuple[float, ...],
    indices: tuple[int, ...],
    labels: Mapping[int, LabelObservation],
    policy: CandidatePolicy,
) -> PlattArtifact:
    return fit_platt_calibrator(
        scores,
        tuple(labels[index].positive for index in indices),
        minimum_observations=(policy.calibration_minimum_observations),
        minimum_positive=(policy.calibration_minimum_positive),
        minimum_negative=(policy.calibration_minimum_negative),
    )


def _probability_map(
    *,
    indices: tuple[int, ...],
    scores: tuple[float, ...],
    platt: PlattArtifact,
) -> dict[int, Decimal]:
    return {
        index: apply_platt(
            platt,
            score,
        )
        for index, score in zip(
            indices,
            scores,
            strict=True,
        )
    }


def _fit_return_map(
    *,
    indices: tuple[int, ...],
    probabilities: Mapping[int, Decimal],
    labels: Mapping[int, LabelObservation],
) -> ExpectedReturnMap:
    return fit_expected_return_map(
        tuple(probabilities[index] for index in indices),
        tuple(labels[index].gross_return for index in indices),
    )


def _thresholds(
    *,
    fold_number: int,
    policy: CandidatePolicy,
    trend_indices: tuple[int, ...],
    mean_indices: tuple[int, ...],
    trend_probabilities: Mapping[int, Decimal],
    mean_probabilities: Mapping[int, Decimal],
) -> tuple[
    dict[SpecialistKind, V04EntryThresholdArtifact],
    dict[
        tuple[SpecialistKind, Decimal],
        V04EntryThresholdArtifact,
    ],
]:
    adjunct = V04MultiTimeframePolicy.locked()

    domains = (
        (
            SpecialistKind.TREND,
            trend_indices,
            trend_probabilities,
        ),
        (
            SpecialistKind.MEAN_REVERSION,
            mean_indices,
            mean_probabilities,
        ),
    )

    primary: dict[
        SpecialistKind,
        V04EntryThresholdArtifact,
    ] = {}

    sensitivity: dict[
        tuple[SpecialistKind, Decimal],
        V04EntryThresholdArtifact,
    ] = {}

    for specialist, indices, probabilities in domains:
        primary[specialist] = build_v0_4_entry_threshold_artifact(
            fold_number=fold_number,
            specialist=specialist,
            percentile=adjunct.entry_percentile,
            eligible_indices=indices,
            calibrated_probabilities=probabilities,
            policy=policy,
        )

        for percentile in adjunct.sensitivity_percentiles:
            sensitivity[(specialist, percentile)] = build_v0_4_entry_threshold_artifact(
                fold_number=fold_number,
                specialist=specialist,
                percentile=percentile,
                eligible_indices=indices,
                calibrated_probabilities=probabilities,
                policy=policy,
            )

    return primary, sensitivity


def fit_v0_4_prediction_context(
    *,
    fold_number: int,
    matrix: FeatureMatrix,
    labels: LabelVector,
    context_join: tuple[ContextObservation | None, ...],
    policy: CandidatePolicy,
    training_indices: tuple[int, ...],
    calibration_indices: tuple[int, ...],
    prediction_indices: tuple[int, ...],
) -> V04PredictionContext:
    """Fit one fold using only its preregistered regime-owned evidence."""

    _validate_v0_4_policy(policy)

    if isinstance(fold_number, bool) or fold_number < 1:
        raise StudyArtifactError("v0.4 prediction context requires a positive fold_number")

    access = _MatrixAccess.build(matrix)

    label_by_index = {
        observation.decision_candle_index: observation for observation in labels.observations
    }

    for name, indices in (
        ("training", training_indices),
        ("calibration", calibration_indices),
        ("prediction", prediction_indices),
    ):
        _validate_partition(
            name=name,
            indices=indices,
            access=access,
            labels=label_by_index,
            context_join=context_join,
        )

    if (
        set(training_indices) & set(calibration_indices)
        or set(training_indices) & set(prediction_indices)
        or set(calibration_indices) & set(prediction_indices)
    ):
        raise StudyArtifactError("Candidate v0.4 fold partitions must not overlap")

    if max(training_indices) >= min(calibration_indices) or max(calibration_indices) >= min(
        prediction_indices
    ):
        raise StudyArtifactError("Candidate v0.4 fold chronology is invalid")

    context_sign_streaks = _context_sign_streaks(
        access=access,
        context_join=context_join,
    )

    trend_training, mean_training = _specialist_domains(
        indices=training_indices,
        access=access,
        policy=policy,
        sign_streaks=context_sign_streaks,
    )

    trend_calibration, mean_calibration = _specialist_domains(
        indices=calibration_indices,
        access=access,
        policy=policy,
        sign_streaks=context_sign_streaks,
    )

    if not trend_training or not mean_training:
        raise StudyArtifactError("Candidate v0.4 training lacks one specialist regime domain")

    if not trend_calibration or not mean_calibration:
        raise StudyArtifactError("Candidate v0.4 calibration lacks one specialist regime domain")

    registry = V04FeatureRegistry.locked()

    trend_model = TrendSpecialistTrainer(policy).fit(
        matrix,
        labels,
        training_indices,
        feature_names=registry.trend_feature_names,
        eligible_indices=trend_training,
    )

    mean_model = MeanReversionSpecialistTrainer(policy).fit(
        matrix,
        labels,
        training_indices,
        feature_names=(registry.mean_reversion_feature_names),
        eligible_indices=mean_training,
    )

    trend_scores = _raw_scores(
        access=access,
        indices=trend_calibration,
        model=trend_model,
    )

    mean_scores = _raw_scores(
        access=access,
        indices=mean_calibration,
        model=mean_model,
    )

    trend_platt = _fit_calibrator(
        scores=trend_scores,
        indices=trend_calibration,
        labels=label_by_index,
        policy=policy,
    )

    mean_platt = _fit_calibrator(
        scores=mean_scores,
        indices=mean_calibration,
        labels=label_by_index,
        policy=policy,
    )

    trend_probabilities = _probability_map(
        indices=trend_calibration,
        scores=trend_scores,
        platt=trend_platt,
    )

    mean_probabilities = _probability_map(
        indices=mean_calibration,
        scores=mean_scores,
        platt=mean_platt,
    )

    trend_return_map = _fit_return_map(
        indices=trend_calibration,
        probabilities=trend_probabilities,
        labels=label_by_index,
    )

    mean_return_map = _fit_return_map(
        indices=mean_calibration,
        probabilities=mean_probabilities,
        labels=label_by_index,
    )

    (
        primary_thresholds,
        sensitivity_thresholds,
    ) = _thresholds(
        fold_number=fold_number,
        policy=policy,
        trend_indices=trend_calibration,
        mean_indices=mean_calibration,
        trend_probabilities=trend_probabilities,
        mean_probabilities=mean_probabilities,
    )

    predictions: list[V04Prediction] = []

    for index in prediction_indices:
        observation = _context_for(
            index=index,
            access=access,
            context_join=context_join,
        )

        regime = _classify_context(
            index=index,
            access=access,
            policy=policy,
            sign_streak=context_sign_streaks[index],
        )

        trend_raw = predict_raw(
            trend_model,
            _model_values(
                access=access,
                index=index,
                model=trend_model,
            ),
        )

        mean_raw = predict_raw(
            mean_model,
            _model_values(
                access=access,
                index=index,
                model=mean_model,
            ),
        )

        trend_probability = apply_platt(
            trend_platt,
            trend_raw,
        )

        mean_probability = apply_platt(
            mean_platt,
            mean_raw,
        )

        if regime.state is RegimeState.TRENDING:
            eligible_specialist: SpecialistKind | None = SpecialistKind.TREND

        elif regime.state is RegimeState.RANGING and _stretch_active(
            index=index,
            access=access,
        ):
            eligible_specialist = SpecialistKind.MEAN_REVERSION

        else:
            eligible_specialist = None

        predictions.append(
            V04Prediction(
                candle_index=index,
                tactical_open_time=(access.row(index).candle_open_time),
                context_sha256=(observation.constituent_sha256),
                context_close_time=(observation.candle.close_time),
                regime=regime,
                trend_raw=trend_raw,
                mean_reversion_raw=mean_raw,
                trend_probability=trend_probability,
                mean_reversion_probability=(mean_probability),
                trend_expected_return=(
                    apply_expected_return(
                        trend_return_map,
                        trend_probability,
                    )
                ),
                mean_reversion_expected_return=(
                    apply_expected_return(
                        mean_return_map,
                        mean_probability,
                    )
                ),
                eligible_specialist=eligible_specialist,
            )
        )

    return V04PredictionContext(
        fold_number=fold_number,
        trend_model=trend_model,
        mean_reversion_model=mean_model,
        trend_platt=trend_platt,
        mean_reversion_platt=mean_platt,
        trend_return_map=trend_return_map,
        mean_reversion_return_map=mean_return_map,
        trend_training_indices=trend_training,
        mean_reversion_training_indices=mean_training,
        trend_calibration_indices=trend_calibration,
        mean_reversion_calibration_indices=mean_calibration,
        primary_thresholds=primary_thresholds,
        sensitivity_thresholds=sensitivity_thresholds,
        predictions=tuple(predictions),
    )


__all__ = [
    "V04Prediction",
    "V04PredictionContext",
    "fit_v0_4_prediction_context",
]
