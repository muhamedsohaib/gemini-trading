"""Chronological split and case-plan construction for Candidate studies."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from gemini_trading.domain.candle import Candle
from gemini_trading.research.config import SimulationConfig
from gemini_trading.research.dataset_reader import VerifiedDataset
from gemini_trading.strategy.baselines import BaselineSchedule
from gemini_trading.strategy.contracts import RegimeState, SpecialistKind
from gemini_trading.strategy.errors import InsufficientHistoryError, StudyArtifactError
from gemini_trading.strategy.features import FeatureMatrix
from gemini_trading.strategy.labels import LabelPolicy
from gemini_trading.strategy.policy import CandidatePolicy
from gemini_trading.strategy.splits import ChronologicalSplitPlan
from gemini_trading.strategy.study import (
    REQUIRED_DEVELOPMENT_CASE_IDS,
    REQUIRED_FINAL_CASE_IDS,
    StudyPhase,
)
from gemini_trading.strategy.study_execution import CasePlan
from gemini_trading.strategy.study_predictions import (
    PredictionBundle,
    baseline_events,
    candidate_events,
    threshold_events,
)
from gemini_trading.strategy.study_strategy import ReplayableStudyStrategy, ScheduledAction


def build_split_plan(
    candles: tuple[Candle, ...],
    eligible_indices: tuple[int, ...],
    policy: CandidatePolicy,
) -> tuple[ChronologicalSplitPlan, bool]:
    """Build the locked plan, falling back only to non-promotable diagnostic history."""

    try:
        return ChronologicalSplitPlan.build(candles, eligible_indices, policy), True
    except InsufficientHistoryError:
        diagnostic_policy = replace(
            policy,
            minimum_history_years=1,
            final_test_months=2,
            initial_training_months=6,
            calibration_months=2,
            development_test_months=2,
            walk_forward_step_months=2,
            minimum_development_folds=1,
        )
        try:
            return ChronologicalSplitPlan.build(
                candles,
                eligible_indices,
                diagnostic_policy,
            ), False
        except InsufficientHistoryError:
            raise StudyArtifactError(
                "candidate diagnostic evaluation requires at least one continuous year"
            ) from None


def _strategy(
    strategy_id: str,
    case_id: str,
    events: tuple[tuple[int, ScheduledAction], ...],
    simulation: SimulationConfig,
) -> ReplayableStudyStrategy:
    return ReplayableStudyStrategy(
        strategy_id_value=strategy_id,
        case_id=case_id,
        events=events,
        quantity_step=simulation.quantity_step,
        minimum_quantity=simulation.min_quantity,
        minimum_notional=simulation.min_notional,
    )


def _cost_config(config: SimulationConfig, multiplier: Decimal) -> SimulationConfig:
    return replace(
        config,
        maker_fee_rate=config.maker_fee_rate * multiplier,
        taker_fee_rate=config.taker_fee_rate * multiplier,
        half_spread_bps=config.half_spread_bps * multiplier,
        slippage_bps=config.slippage_bps * multiplier,
    )


def prepare_phase(
    *,
    phase: StudyPhase,
    fold_number: int | None,
    indices: tuple[int, ...],
    bundle: PredictionBundle,
    dataset: VerifiedDataset,
    simulation: SimulationConfig,
    policy: CandidatePolicy,
    label_policy: LabelPolicy,
    matrix: FeatureMatrix,
    baseline_schedules: dict[str, BaselineSchedule],
    plans: dict[tuple[StudyPhase, int | None, str], CasePlan],
) -> None:
    """Prepare every required comparator, control, stress, and sensitivity case."""

    regimes = {item.candle_index: item.regime.state for item in bundle.predictions}
    base_events = candidate_events(
        bundle,
        candles=dataset.candles,
        matrix=matrix,
        label_policy=label_policy,
        policy=policy,
    )
    event_by_case: dict[str, tuple[tuple[int, ScheduledAction], ...]] = {
        "candidate.multi_model.v0_1": base_events,
        "trend.specialist.v1": threshold_events(
            bundle,
            specialist=SpecialistKind.TREND,
            matrix=matrix,
        ),
        "mean_reversion.specialist.v1": threshold_events(
            bundle,
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
        "ablation.no_disagreement.v1": candidate_events(
            bundle,
            candles=dataset.candles,
            matrix=matrix,
            label_policy=label_policy,
            policy=replace(policy, disagreement_limit=Decimal("1")),
        ),
        "ablation.no_volume.v1": candidate_events(
            bundle,
            candles=dataset.candles,
            matrix=matrix,
            label_policy=label_policy,
            policy=policy,
            volume_ablation=True,
        ),
        "ablation.no_protection.v1": candidate_events(
            bundle,
            candles=dataset.candles,
            matrix=matrix,
            label_policy=label_policy,
            policy=replace(
                policy,
                initial_stop_atr=Decimal("100"),
                trailing_stop_atr=Decimal("100"),
            ),
        ),
        "control.delayed_features.v1": candidate_events(
            bundle,
            candles=dataset.candles,
            matrix=matrix,
            label_policy=label_policy,
            policy=policy,
            delayed=True,
        ),
        "control.shuffled_labels.v1": candidate_events(
            bundle,
            candles=dataset.candles,
            matrix=matrix,
            label_policy=label_policy,
            policy=policy,
            invert_probabilities=True,
        ),
    }
    for baseline_id in (
        "cash.v1",
        "buy_hold.v1",
        "ema_20_50.v1",
        "donchian_20_10.v1",
        "mean_reversion_z24.v1",
    ):
        event_by_case[baseline_id] = baseline_events(
            actions=baseline_schedules[baseline_id].actions,
            indices=indices,
        )
    if phase is StudyPhase.FINAL:
        event_by_case.update(
            {
                "cost.1_5x": base_events,
                "cost.2x": base_events,
                "sensitivity.entry_0_59": candidate_events(
                    bundle,
                    candles=dataset.candles,
                    matrix=matrix,
                    label_policy=label_policy,
                    policy=replace(policy, entry_probability=Decimal("0.59")),
                ),
                "sensitivity.entry_0_65": candidate_events(
                    bundle,
                    candles=dataset.candles,
                    matrix=matrix,
                    label_policy=label_policy,
                    policy=replace(policy, entry_probability=Decimal("0.65")),
                ),
                "sensitivity.exit_0_42": candidate_events(
                    bundle,
                    candles=dataset.candles,
                    matrix=matrix,
                    label_policy=label_policy,
                    policy=replace(policy, exit_probability=Decimal("0.42")),
                ),
                "sensitivity.exit_0_48": candidate_events(
                    bundle,
                    candles=dataset.candles,
                    matrix=matrix,
                    label_policy=label_policy,
                    policy=replace(policy, exit_probability=Decimal("0.48")),
                ),
                "sensitivity.max_hold_12": candidate_events(
                    bundle,
                    candles=dataset.candles,
                    matrix=matrix,
                    label_policy=label_policy,
                    policy=replace(policy, maximum_hold_candles=12),
                ),
                "sensitivity.max_hold_24": candidate_events(
                    bundle,
                    candles=dataset.candles,
                    matrix=matrix,
                    label_policy=label_policy,
                    policy=replace(policy, maximum_hold_candles=24),
                ),
                "sensitivity.initial_stop_2_0": candidate_events(
                    bundle,
                    candles=dataset.candles,
                    matrix=matrix,
                    label_policy=label_policy,
                    policy=replace(policy, initial_stop_atr=Decimal("2.0")),
                ),
                "sensitivity.initial_stop_3_0": candidate_events(
                    bundle,
                    candles=dataset.candles,
                    matrix=matrix,
                    label_policy=label_policy,
                    policy=replace(policy, initial_stop_atr=Decimal("3.0")),
                ),
                "sensitivity.cooldown_1": candidate_events(
                    bundle,
                    candles=dataset.candles,
                    matrix=matrix,
                    label_policy=label_policy,
                    policy=replace(policy, cooldown_candles=1),
                ),
                "sensitivity.cooldown_3": candidate_events(
                    bundle,
                    candles=dataset.candles,
                    matrix=matrix,
                    label_policy=label_policy,
                    policy=replace(policy, cooldown_candles=3),
                ),
                "control.shuffled_labels.seed_1799": event_by_case["control.shuffled_labels.v1"],
                "control.delayed_features.final": event_by_case["control.delayed_features.v1"],
                "bootstrap.seed_1788": base_events,
            }
        )
    required = (
        REQUIRED_DEVELOPMENT_CASE_IDS
        if phase is StudyPhase.DEVELOPMENT
        else REQUIRED_FINAL_CASE_IDS
    )
    for case_id in required:
        strategy_id = case_id if case_id in baseline_schedules else "candidate.multi_model.v0_1"
        case_simulation = simulation
        if case_id == "cost.1_5x":
            case_simulation = _cost_config(simulation, Decimal("1.5"))
        elif case_id == "cost.2x":
            case_simulation = _cost_config(simulation, Decimal("2"))
        plans[(phase, fold_number, case_id)] = CasePlan(
            strategy=_strategy(
                strategy_id,
                case_id,
                event_by_case[case_id],
                case_simulation,
            ),
            simulation=case_simulation,
        )


__all__ = ["build_split_plan", "prepare_phase"]
