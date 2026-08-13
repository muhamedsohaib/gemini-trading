"""Case-plan construction for Candidate v0.3 development qualification."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from gemini_trading.domain.candle import Candle
from gemini_trading.research.config import SimulationConfig
from gemini_trading.research.dataset_reader import VerifiedDataset
from gemini_trading.strategy.baselines import BaselineSchedule
from gemini_trading.strategy.contracts import RegimeState, SpecialistKind
from gemini_trading.strategy.errors import StudyArtifactError
from gemini_trading.strategy.features import FeatureMatrix
from gemini_trading.strategy.labels import LabelPolicy
from gemini_trading.strategy.policy import CandidatePolicy
from gemini_trading.strategy.study import StudyPhase
from gemini_trading.strategy.study_execution import CasePlan
from gemini_trading.strategy.study_predictions import (
    baseline_events,
    candidate_events,
    threshold_events,
)
from gemini_trading.strategy.study_strategy import ReplayableStudyStrategy, ScheduledAction
from gemini_trading.strategy.v0_3_cases import V03_QUALIFICATION_CASE_IDS
from gemini_trading.strategy.v0_3_predictions import V03PredictionContext

_HALF_THRESHOLDS = {
    SpecialistKind.TREND: Decimal("0.50"),
    SpecialistKind.MEAN_REVERSION: Decimal("0.50"),
}


def _validate_policy(policy: CandidatePolicy) -> None:
    if (
        policy.strategy_id != "candidate.multi_model.v0_3"
        or policy.policy_version != "candidate-multi-model-v0.3"
        or policy.schema_version != "candidate-strategy-policy-v3"
    ):
        raise StudyArtifactError("v0.3 phase preparation requires exact Candidate v0.3")


def _strategy(
    strategy_id: str,
    case_id: str,
    events: tuple[tuple[int, ScheduledAction], ...],
    simulation: SimulationConfig,
    evaluation_end_exclusive: int,
) -> ReplayableStudyStrategy:
    return ReplayableStudyStrategy(
        strategy_id_value=strategy_id,
        case_id=case_id,
        events=events,
        quantity_step=simulation.quantity_step,
        minimum_quantity=simulation.min_quantity,
        minimum_notional=simulation.min_notional,
        evaluation_end_exclusive=evaluation_end_exclusive,
    )


def _cost_config(config: SimulationConfig, multiplier: Decimal) -> SimulationConfig:
    return replace(
        config,
        maker_fee_rate=config.maker_fee_rate * multiplier,
        taker_fee_rate=config.taker_fee_rate * multiplier,
        half_spread_bps=config.half_spread_bps * multiplier,
        slippage_bps=config.slippage_bps * multiplier,
    )


def _candidate(
    context: V03PredictionContext,
    *,
    percentile: Decimal | None,
    candles: tuple[Candle, ...],
    matrix: FeatureMatrix,
    label_policy: LabelPolicy,
    policy: CandidatePolicy,
    delayed: bool = False,
    invert_probabilities: bool = False,
    volume_ablation: bool = False,
) -> tuple[tuple[int, ScheduledAction], ...]:
    thresholds = (
        _HALF_THRESHOLDS
        if percentile is None
        else context.effective_thresholds(percentile)
    )
    return candidate_events(
        context.bundle,
        candles=candles,
        matrix=matrix,
        label_policy=label_policy,
        policy=policy,
        delayed=delayed,
        invert_probabilities=invert_probabilities,
        volume_ablation=volume_ablation,
        entry_thresholds=thresholds,
        companion_disagreement_diagnostic_only=True,
    )


def prepare_v0_3_phase(
    *,
    phase: StudyPhase,
    fold_number: int | None,
    indices: tuple[int, ...],
    context: V03PredictionContext,
    dataset: VerifiedDataset,
    simulation: SimulationConfig,
    policy: CandidatePolicy,
    label_policy: LabelPolicy,
    matrix: FeatureMatrix,
    baseline_schedules: dict[str, BaselineSchedule],
    plans: dict[tuple[StudyPhase, int | None, str], CasePlan],
) -> None:
    """Prepare every preregistered v0.3 development qualification case."""

    _validate_policy(policy)
    if phase is not StudyPhase.DEVELOPMENT or fold_number is None or fold_number < 1:
        raise StudyArtifactError("v0.3 qualification case preparation is development-fold only")
    if not indices or indices != tuple(sorted(set(indices))):
        raise StudyArtifactError("v0.3 qualification requires ordered unique decision indices")
    expected_baselines = {
        "cash.v1",
        "buy_hold.v1",
        "ema_20_50.v1",
        "donchian_20_10.v1",
        "mean_reversion_z24.v1",
    }
    if set(baseline_schedules) != expected_baselines:
        raise StudyArtifactError("v0.3 qualification baseline inventory changed")

    evaluation_end_exclusive = min(
        len(dataset.candles),
        indices[-1] + 2 + simulation.latency_bars,
    )
    q70 = Decimal("0.70")
    q75 = Decimal("0.75")
    q80 = Decimal("0.80")
    base_events = _candidate(
        context,
        percentile=q75,
        candles=dataset.candles,
        matrix=matrix,
        label_policy=label_policy,
        policy=policy,
    )
    regimes = {item.candle_index: item.regime.state for item in context.bundle.predictions}
    event_by_case: dict[str, tuple[tuple[int, ScheduledAction], ...]] = {
        policy.strategy_id: base_events,
        "trend.specialist.v1": threshold_events(
            context.bundle,
            specialist=SpecialistKind.TREND,
            matrix=matrix,
        ),
        "mean_reversion.specialist.v1": threshold_events(
            context.bundle,
            specialist=SpecialistKind.MEAN_REVERSION,
            require_ranging_stretch=True,
            matrix=matrix,
        ),
        "trend.ema_20_50.gated.v1": baseline_events(
            actions=baseline_schedules["ema_20_50.v1"].actions,
            indices=indices,
            allowed_regimes=regimes,
            required_regime=RegimeState.TRENDING,
        ),
        "ranging.mean_reversion_z24.gated.v1": baseline_events(
            actions=baseline_schedules["mean_reversion_z24.v1"].actions,
            indices=indices,
            allowed_regimes=regimes,
            required_regime=RegimeState.RANGING,
        ),
        "ablation.no_percentile_selectivity.v1": _candidate(
            context,
            percentile=None,
            candles=dataset.candles,
            matrix=matrix,
            label_policy=label_policy,
            policy=policy,
        ),
        "ablation.no_volume.v1": _candidate(
            context,
            percentile=q75,
            candles=dataset.candles,
            matrix=matrix,
            label_policy=label_policy,
            policy=policy,
            volume_ablation=True,
        ),
        "ablation.no_protection.v1": _candidate(
            context,
            percentile=q75,
            candles=dataset.candles,
            matrix=matrix,
            label_policy=label_policy,
            policy=replace(
                policy,
                initial_stop_atr=Decimal("100"),
                trailing_stop_atr=Decimal("100"),
            ),
        ),
        "control.delayed_features.v1": _candidate(
            context,
            percentile=q75,
            candles=dataset.candles,
            matrix=matrix,
            label_policy=label_policy,
            policy=policy,
            delayed=True,
        ),
        "control.shuffled_labels.v1": _candidate(
            context,
            percentile=q75,
            candles=dataset.candles,
            matrix=matrix,
            label_policy=label_policy,
            policy=policy,
            invert_probabilities=True,
        ),
        "cost.1_5x": base_events,
        "cost.2x": base_events,
        "sensitivity.entry_percentile_0_70": _candidate(
            context,
            percentile=q70,
            candles=dataset.candles,
            matrix=matrix,
            label_policy=label_policy,
            policy=policy,
        ),
        "sensitivity.entry_percentile_0_80": _candidate(
            context,
            percentile=q80,
            candles=dataset.candles,
            matrix=matrix,
            label_policy=label_policy,
            policy=policy,
        ),
        "sensitivity.exit_0_42": _candidate(
            context,
            percentile=q75,
            candles=dataset.candles,
            matrix=matrix,
            label_policy=label_policy,
            policy=replace(policy, exit_probability=Decimal("0.42")),
        ),
        "sensitivity.exit_0_48": _candidate(
            context,
            percentile=q75,
            candles=dataset.candles,
            matrix=matrix,
            label_policy=label_policy,
            policy=replace(policy, exit_probability=Decimal("0.48")),
        ),
        "sensitivity.max_hold_12": _candidate(
            context,
            percentile=q75,
            candles=dataset.candles,
            matrix=matrix,
            label_policy=label_policy,
            policy=replace(policy, maximum_hold_candles=12),
        ),
        "sensitivity.max_hold_24": _candidate(
            context,
            percentile=q75,
            candles=dataset.candles,
            matrix=matrix,
            label_policy=label_policy,
            policy=replace(policy, maximum_hold_candles=24),
        ),
        "sensitivity.initial_stop_2_0": _candidate(
            context,
            percentile=q75,
            candles=dataset.candles,
            matrix=matrix,
            label_policy=label_policy,
            policy=replace(policy, initial_stop_atr=Decimal("2.0")),
        ),
        "sensitivity.initial_stop_3_0": _candidate(
            context,
            percentile=q75,
            candles=dataset.candles,
            matrix=matrix,
            label_policy=label_policy,
            policy=replace(policy, initial_stop_atr=Decimal("3.0")),
        ),
        "sensitivity.cooldown_1": _candidate(
            context,
            percentile=q75,
            candles=dataset.candles,
            matrix=matrix,
            label_policy=label_policy,
            policy=replace(policy, cooldown_candles=1),
        ),
        "sensitivity.cooldown_3": _candidate(
            context,
            percentile=q75,
            candles=dataset.candles,
            matrix=matrix,
            label_policy=label_policy,
            policy=replace(policy, cooldown_candles=3),
        ),
    }
    event_by_case["control.shuffled_labels.seed_1799"] = event_by_case[
        "control.shuffled_labels.v1"
    ]
    event_by_case["control.delayed_features.final"] = event_by_case[
        "control.delayed_features.v1"
    ]
    event_by_case["bootstrap.seed_1788"] = base_events
    for baseline_id in expected_baselines:
        event_by_case[baseline_id] = baseline_events(
            actions=baseline_schedules[baseline_id].actions,
            indices=indices,
        )

    if set(event_by_case) != set(V03_QUALIFICATION_CASE_IDS):
        raise StudyArtifactError("v0.3 qualification case construction is incomplete")
    for case_id in V03_QUALIFICATION_CASE_IDS:
        case_simulation = simulation
        if case_id == "cost.1_5x":
            case_simulation = _cost_config(simulation, Decimal("1.5"))
        elif case_id == "cost.2x":
            case_simulation = _cost_config(simulation, Decimal("2"))
        strategy_id = case_id if case_id in baseline_schedules else policy.strategy_id
        plans[(phase, fold_number, case_id)] = CasePlan(
            strategy=_strategy(
                strategy_id,
                case_id,
                event_by_case[case_id],
                case_simulation,
                evaluation_end_exclusive,
            ),
            simulation=case_simulation,
        )


__all__ = ["prepare_v0_3_phase"]
