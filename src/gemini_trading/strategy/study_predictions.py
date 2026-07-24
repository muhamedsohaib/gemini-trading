"""Deterministic Candidate prediction bundles and simulated action schedules."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import cast

from gemini_trading.domain.candle import Candle
from gemini_trading.strategy.arbitration import ArbitrationInput, MultiModelArbiter
from gemini_trading.strategy.baselines import BaselineAction
from gemini_trading.strategy.calibration import (
    ExpectedReturnMap,
    PlattArtifact,
    apply_expected_return,
    apply_platt,
    fit_expected_return_map,
    fit_platt_calibrator,
)
from gemini_trading.strategy.contracts import RegimeState, SpecialistKind, StrategyAction
from gemini_trading.strategy.features import FeatureMatrix
from gemini_trading.strategy.labels import LabelPolicy, LabelVector
from gemini_trading.strategy.models import (
    MeanReversionSpecialistTrainer,
    ModelArtifact,
    TrendSpecialistTrainer,
    predict_raw,
)
from gemini_trading.strategy.policy import CandidatePolicy
from gemini_trading.strategy.regimes import RegimeClassifier, RegimeObservation
from gemini_trading.strategy.study import StudyPhase
from gemini_trading.strategy.study_strategy import ScheduledAction

_ONE = Decimal("1")


@dataclass(frozen=True, slots=True)
class Prediction:
    """One immutable specialist and regime prediction row."""

    candle_index: int
    trend_raw: float
    mean_reversion_raw: float
    trend_probability: Decimal
    mean_reversion_probability: Decimal
    trend_expected_return: Decimal
    mean_reversion_expected_return: Decimal
    regime: RegimeObservation


@dataclass(frozen=True, slots=True)
class PredictionBundle:
    """Models, calibration evidence, and predictions for one study window."""

    phase: StudyPhase
    fold_number: int | None
    trend_model: ModelArtifact
    mean_reversion_model: ModelArtifact
    trend_platt: PlattArtifact
    mean_reversion_platt: PlattArtifact
    trend_return_map: ExpectedReturnMap
    mean_reversion_return_map: ExpectedReturnMap
    predictions: tuple[Prediction, ...]


def _values(matrix: FeatureMatrix, index: int, names: Sequence[str]) -> dict[str, Decimal]:
    return {name: matrix.value_for(index, name) for name in names}


def fit_prediction_bundle(
    *,
    phase: StudyPhase,
    fold_number: int | None,
    matrix: FeatureMatrix,
    labels: LabelVector,
    policy: CandidatePolicy,
    training_indices: tuple[int, ...],
    calibration_indices: tuple[int, ...],
    prediction_indices: tuple[int, ...],
) -> PredictionBundle:
    """Fit deterministic specialists and build calibrated prediction rows."""

    trend_model = TrendSpecialistTrainer(policy).fit(matrix, labels, training_indices)
    mean_model = MeanReversionSpecialistTrainer(policy).fit(matrix, labels, training_indices)
    trend_scores = tuple(
        predict_raw(trend_model, _values(matrix, index, trend_model.feature_names))
        for index in calibration_indices
    )
    mean_scores = tuple(
        predict_raw(mean_model, _values(matrix, index, mean_model.feature_names))
        for index in calibration_indices
    )
    calibration_labels = tuple(labels.for_index(index).positive for index in calibration_indices)
    trend_platt = fit_platt_calibrator(
        trend_scores,
        calibration_labels,
        minimum_observations=policy.calibration_minimum_observations,
        minimum_positive=policy.calibration_minimum_positive,
        minimum_negative=policy.calibration_minimum_negative,
    )
    mean_platt = fit_platt_calibrator(
        mean_scores,
        calibration_labels,
        minimum_observations=policy.calibration_minimum_observations,
        minimum_positive=policy.calibration_minimum_positive,
        minimum_negative=policy.calibration_minimum_negative,
    )
    trend_probabilities = tuple(apply_platt(trend_platt, score) for score in trend_scores)
    mean_probabilities = tuple(apply_platt(mean_platt, score) for score in mean_scores)
    gross_returns = tuple(labels.for_index(index).gross_return for index in calibration_indices)
    trend_return_map = fit_expected_return_map(trend_probabilities, gross_returns)
    mean_return_map = fit_expected_return_map(mean_probabilities, gross_returns)

    classifier = RegimeClassifier(policy)
    predictions: list[Prediction] = []
    for index in prediction_indices:
        trend_raw = predict_raw(trend_model, _values(matrix, index, trend_model.feature_names))
        mean_raw = predict_raw(mean_model, _values(matrix, index, mean_model.feature_names))
        trend_probability = apply_platt(trend_platt, trend_raw)
        mean_probability = apply_platt(mean_platt, mean_raw)
        regime = classifier.classify(
            candle_index=index,
            trend_strength=matrix.value_for(index, "trend_strength_12_42_atr24"),
            volatility_ratio=matrix.value_for(index, "volatility_ratio_6_42"),
            true_range_ratio=matrix.value_for(index, "true_range_ratio_24"),
            sign_streak=int(matrix.value_for(index, "ema_12_42_sign_streak")),
        )
        predictions.append(
            Prediction(
                candle_index=index,
                trend_raw=trend_raw,
                mean_reversion_raw=mean_raw,
                trend_probability=trend_probability,
                mean_reversion_probability=mean_probability,
                trend_expected_return=apply_expected_return(trend_return_map, trend_probability),
                mean_reversion_expected_return=apply_expected_return(
                    mean_return_map, mean_probability
                ),
                regime=regime,
            )
        )
    return PredictionBundle(
        phase=phase,
        fold_number=fold_number,
        trend_model=trend_model,
        mean_reversion_model=mean_model,
        trend_platt=trend_platt,
        mean_reversion_platt=mean_platt,
        trend_return_map=trend_return_map,
        mean_reversion_return_map=mean_return_map,
        predictions=tuple(predictions),
    )


def candidate_events(
    bundle: PredictionBundle,
    *,
    candles: tuple[Candle, ...],
    matrix: FeatureMatrix,
    label_policy: LabelPolicy,
    policy: CandidatePolicy,
    delayed: bool = False,
    invert_probabilities: bool = False,
    volume_ablation: bool = False,
) -> tuple[tuple[int, ScheduledAction], ...]:
    """Convert calibrated predictions into a deterministic long-or-cash schedule."""

    arbiter = MultiModelArbiter(policy)
    currently_long = False
    active_specialist: SpecialistKind | None = None
    hold_age = 0
    cooldown = 0
    indeterminate_streak = 0
    entry_price: Decimal | None = None
    highest_close: Decimal | None = None
    current_stop: Decimal | None = None
    events: list[tuple[int, ScheduledAction]] = []

    for position, item in enumerate(bundle.predictions):
        source_item = bundle.predictions[position - 1] if delayed and position > 0 else item
        trend_probability = source_item.trend_probability
        mean_probability = source_item.mean_reversion_probability
        trend_expected = source_item.trend_expected_return
        mean_expected = source_item.mean_reversion_expected_return
        if invert_probabilities:
            trend_probability = _ONE - trend_probability
            mean_probability = _ONE - mean_probability
            trend_expected = -trend_expected
            mean_expected = -mean_expected
        if volume_ablation:
            trend_probability = (trend_probability + Decimal("0.5")) / Decimal("2")
            mean_probability = (mean_probability + Decimal("0.5")) / Decimal("2")
        index = item.candle_index
        candle = candles[index]
        stretch_active = (
            matrix.value_for(index, "close_zscore_24") <= Decimal("-0.75")
            or matrix.value_for(index, "drawdown_from_high_24") >= Decimal("0.02")
        )
        decision = arbiter.decide(
            ArbitrationInput(
                candle_index=index,
                regime=source_item.regime.state,
                trend_probability=trend_probability,
                trend_expected_gross_return=trend_expected,
                mean_reversion_probability=mean_probability,
                mean_reversion_expected_gross_return=mean_expected,
                currently_long=currently_long,
                active_specialist=active_specialist,
                hold_age=hold_age,
                cooldown_remaining=cooldown,
                indeterminate_streak=indeterminate_streak,
                entry_price=entry_price,
                highest_close_since_entry=highest_close,
                current_close=candle.close,
                current_low=candle.low,
                atr24=matrix.value_for(index, "atr_24"),
                current_stop=current_stop,
                stretch_active=stretch_active,
                base_hurdle_bps=label_policy.hurdle_bps,
            )
        )
        if decision.action is StrategyAction.ENTER_LONG:
            events.append((index, ScheduledAction.ENTER_LONG))
            currently_long = True
            active_specialist = decision.active_specialist
            hold_age = decision.hold_age
            cooldown = 0
            indeterminate_streak = 0
            entry_price = candle.close
            highest_close = candle.close
            current_stop = decision.trailing_stop
        elif decision.action is StrategyAction.REMAIN_LONG:
            hold_age = decision.hold_age
            indeterminate_streak = decision.indeterminate_streak
            highest_close = max(cast(Decimal, highest_close), candle.close)
            current_stop = decision.trailing_stop
        elif decision.action is StrategyAction.EXIT_TO_CASH:
            events.append((index, ScheduledAction.EXIT_TO_CASH))
            currently_long = False
            active_specialist = None
            hold_age = 0
            cooldown = decision.cooldown_remaining
            indeterminate_streak = 0
            entry_price = None
            highest_close = None
            current_stop = None
        else:
            cooldown = decision.cooldown_remaining
    if currently_long and bundle.predictions:
        last = bundle.predictions[-1].candle_index
        events = [event for event in events if event[0] != last]
        events.append((last, ScheduledAction.EXIT_TO_CASH))
    return tuple(sorted(events))


def threshold_events(
    bundle: PredictionBundle,
    *,
    specialist: SpecialistKind,
    require_ranging_stretch: bool = False,
    matrix: FeatureMatrix,
) -> tuple[tuple[int, ScheduledAction], ...]:
    """Build one deterministic specialist-only comparison schedule."""

    long = False
    events: list[tuple[int, ScheduledAction]] = []
    for item in bundle.predictions:
        probability = (
            item.trend_probability
            if specialist is SpecialistKind.TREND
            else item.mean_reversion_probability
        )
        allowed = item.regime.state is (
            RegimeState.TRENDING if specialist is SpecialistKind.TREND else RegimeState.RANGING
        )
        if require_ranging_stretch:
            allowed = allowed and (
                matrix.value_for(item.candle_index, "close_zscore_24") <= Decimal("-0.75")
                or matrix.value_for(item.candle_index, "drawdown_from_high_24") >= Decimal("0.02")
            )
        if not long and allowed and probability >= Decimal("0.62"):
            events.append((item.candle_index, ScheduledAction.ENTER_LONG))
            long = True
        elif long and (not allowed or probability <= Decimal("0.45")):
            events.append((item.candle_index, ScheduledAction.EXIT_TO_CASH))
            long = False
    if long and bundle.predictions:
        events.append((bundle.predictions[-1].candle_index, ScheduledAction.EXIT_TO_CASH))
    return tuple(sorted(dict(events).items()))


def baseline_events(
    *,
    actions: tuple[BaselineAction, ...],
    indices: tuple[int, ...],
    allowed_regimes: Mapping[int, RegimeState] | None = None,
    required_regime: RegimeState | None = None,
) -> tuple[tuple[int, ScheduledAction], ...]:
    """Convert a provider-free baseline action series into a simulation schedule."""

    events: list[tuple[int, ScheduledAction]] = []
    long = False
    for index in indices:
        action = actions[index]
        allowed = (
            True
            if required_regime is None
            else allowed_regimes is not None and allowed_regimes.get(index) is required_regime
        )
        if action is BaselineAction.ENTER_LONG and allowed and not long:
            events.append((index, ScheduledAction.ENTER_LONG))
            long = True
        elif (action is BaselineAction.EXIT_TO_CASH or not allowed) and long:
            events.append((index, ScheduledAction.EXIT_TO_CASH))
            long = False
    if long and indices:
        events.append((indices[-1], ScheduledAction.EXIT_TO_CASH))
    return tuple(sorted(dict(events).items()))


__all__ = [
    "Prediction",
    "PredictionBundle",
    "baseline_events",
    "candidate_events",
    "fit_prediction_bundle",
    "threshold_events",
]
