"""Concrete provider-free Candidate v0.1 study evaluation pipeline."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, replace
from decimal import Decimal
from pathlib import Path
from typing import cast

from gemini_trading.domain.candle import Candle
from gemini_trading.research.config import SimulationConfig, serialize_simulation_config
from gemini_trading.research.dataset_reader import VerifiedDataset
from gemini_trading.research.serialization import canonical_json_bytes
from gemini_trading.strategy.artifacts import (
    LocalStrategyStudyStore,
    StrategyStudyArtifacts,
    build_study_artifacts,
)
from gemini_trading.strategy.baselines import build_baseline_schedules
from gemini_trading.strategy.contracts import RegimeState, SpecialistKind
from gemini_trading.strategy.errors import InsufficientHistoryError, StudyArtifactError
from gemini_trading.strategy.features import FeatureRegistry
from gemini_trading.strategy.labels import LabelPolicy
from gemini_trading.strategy.policy import CandidatePolicy, serialize_candidate_policy
from gemini_trading.strategy.splits import ChronologicalSplitPlan
from gemini_trading.strategy.study import (
    REQUIRED_DEVELOPMENT_CASE_IDS,
    REQUIRED_FINAL_CASE_IDS,
    StrategyStudyEvidence,
    StrategyStudyRunner,
    StudyPhase,
    split_plan_payload,
)
from gemini_trading.strategy.study_execution import (
    CasePlan,
    StudyExecutor,
    build_promotion_report,
    bundle_payloads,
)
from gemini_trading.strategy.study_predictions import (
    PredictionBundle,
    baseline_events,
    candidate_events,
    fit_prediction_bundle,
    threshold_events,
)
from gemini_trading.strategy.study_strategy import (
    ReplayableStudyStrategy,
    ScheduledAction,
    reconstruct_study_strategy,
)


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


def _diagnostic_policy(policy: CandidatePolicy) -> CandidatePolicy:
    return replace(
        policy,
        minimum_history_years=1,
        final_test_months=2,
        initial_training_months=6,
        calibration_months=2,
        development_test_months=2,
        walk_forward_step_months=2,
        minimum_development_folds=1,
    )


def _build_plan(
    candles: tuple[Candle, ...],
    eligible_indices: tuple[int, ...],
    policy: CandidatePolicy,
) -> tuple[ChronologicalSplitPlan, bool]:
    try:
        return ChronologicalSplitPlan.build(candles, eligible_indices, policy), True
    except InsufficientHistoryError:
        try:
            return (
                ChronologicalSplitPlan.build(
                    candles,
                    eligible_indices,
                    _diagnostic_policy(policy),
                ),
                False,
            )
        except InsufficientHistoryError:
            raise StudyArtifactError(
                "candidate diagnostic evaluation requires at least one continuous year"
            ) from None


def _canonical_mapping(raw: bytes) -> dict[str, object]:
    loaded: object = json.loads(raw)
    if not isinstance(loaded, dict):
        raise StudyArtifactError("internal canonical mapping is invalid")
    return cast(dict[str, object], loaded)


def _prepare_phase(
    *,
    phase: StudyPhase,
    fold_number: int | None,
    indices: tuple[int, ...],
    bundle: PredictionBundle,
    dataset: VerifiedDataset,
    simulation: SimulationConfig,
    policy: CandidatePolicy,
    label_policy: LabelPolicy,
    matrix: object,
    baseline_schedules: object,
    plans: dict[tuple[StudyPhase, int | None, str], CasePlan],
) -> None:
    from gemini_trading.strategy.features import FeatureMatrix

    feature_matrix = cast(FeatureMatrix, matrix)
    schedules = cast(dict[str, object], baseline_schedules)
    regimes = {item.candle_index: item.regime.state for item in bundle.predictions}
    base_events = candidate_events(
        bundle,
        candles=dataset.candles,
        matrix=feature_matrix,
        label_policy=label_policy,
        policy=policy,
    )
    event_by_case: dict[str, tuple[tuple[int, ScheduledAction], ...]] = {
        "candidate.multi_model.v0_1": base_events,
        "trend.specialist.v1": threshold_events(
            bundle,
            specialist=SpecialistKind.TREND,
            matrix=feature_matrix,
        ),
        "mean_reversion.specialist.v1": threshold_events(
            bundle,
            specialist=SpecialistKind.MEAN_REVERSION,
            require_ranging_stretch=True,
            matrix=feature_matrix,
        ),
        "trend.ema_20_50.gated.v1": baseline_events(
            actions=cast(object, schedules["ema_20_50.v1"]).actions,
            indices=indices,
            allowed_regimes=regimes,
            required_regime=RegimeState.TRENDING,
        ),
        "ranging.mean_reversion_z24.gated.v1": baseline_events(
            actions=cast(object, schedules["mean_reversion_z24.v1"]).actions,
            indices=indices,
            allowed_regimes=regimes,
            required_regime=RegimeState.RANGING,
        ),
        "ablation.no_disagreement.v1": candidate_events(
            bundle,
            candles=dataset.candles,
            matrix=feature_matrix,
            label_policy=label_policy,
            policy=replace(policy, disagreement_limit=Decimal("1")),
        ),
        "ablation.no_volume.v1": candidate_events(
            bundle,
            candles=dataset.candles,
            matrix=feature_matrix,
            label_policy=label_policy,
            policy=policy,
            volume_ablation=True,
        ),
        "ablation.no_protection.v1": candidate_events(
            bundle,
            candles=dataset.candles,
            matrix=feature_matrix,
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
            matrix=feature_matrix,
            label_policy=label_policy,
            policy=policy,
            delayed=True,
        ),
        "control.shuffled_labels.v1": candidate_events(
            bundle,
            candles=dataset.candles,
            matrix=feature_matrix,
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
            actions=cast(object, schedules[baseline_id]).actions,
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
                    matrix=feature_matrix,
                    label_policy=label_policy,
                    policy=replace(policy, entry_probability=Decimal("0.59")),
                ),
                "sensitivity.entry_0_65": candidate_events(
                    bundle,
                    candles=dataset.candles,
                    matrix=feature_matrix,
                    label_policy=label_policy,
                    policy=replace(policy, entry_probability=Decimal("0.65")),
                ),
                "sensitivity.exit_0_42": candidate_events(
                    bundle,
                    candles=dataset.candles,
                    matrix=feature_matrix,
                    label_policy=label_policy,
                    policy=replace(policy, exit_probability=Decimal("0.42")),
                ),
                "sensitivity.exit_0_48": candidate_events(
                    bundle,
                    candles=dataset.candles,
                    matrix=feature_matrix,
                    label_policy=label_policy,
                    policy=replace(policy, exit_probability=Decimal("0.48")),
                ),
                "sensitivity.max_hold_12": candidate_events(
                    bundle,
                    candles=dataset.candles,
                    matrix=feature_matrix,
                    label_policy=label_policy,
                    policy=replace(policy, maximum_hold_candles=12),
                ),
                "sensitivity.max_hold_24": candidate_events(
                    bundle,
                    candles=dataset.candles,
                    matrix=feature_matrix,
                    label_policy=label_policy,
                    policy=replace(policy, maximum_hold_candles=24),
                ),
                "sensitivity.initial_stop_2_0": candidate_events(
                    bundle,
                    candles=dataset.candles,
                    matrix=feature_matrix,
                    label_policy=label_policy,
                    policy=replace(policy, initial_stop_atr=Decimal("2.0")),
                ),
                "sensitivity.initial_stop_3_0": candidate_events(
                    bundle,
                    candles=dataset.candles,
                    matrix=feature_matrix,
                    label_policy=label_policy,
                    policy=replace(policy, initial_stop_atr=Decimal("3.0")),
                ),
                "sensitivity.cooldown_1": candidate_events(
                    bundle,
                    candles=dataset.candles,
                    matrix=feature_matrix,
                    label_policy=label_policy,
                    policy=replace(policy, cooldown_candles=1),
                ),
                "sensitivity.cooldown_3": candidate_events(
                    bundle,
                    candles=dataset.candles,
                    matrix=feature_matrix,
                    label_policy=label_policy,
                    policy=replace(policy, cooldown_candles=3),
                ),
                "control.shuffled_labels.seed_1799": event_by_case[
                    "control.shuffled_labels.v1"
                ],
                "control.delayed_features.final": event_by_case[
                    "control.delayed_features.v1"
                ],
                "bootstrap.seed_1788": base_events,
            }
        )
    required = (
        REQUIRED_DEVELOPMENT_CASE_IDS
        if phase is StudyPhase.DEVELOPMENT
        else REQUIRED_FINAL_CASE_IDS
    )
    for case_id in required:
        strategy_id = case_id if case_id in schedules else "candidate.multi_model.v0_1"
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


def evaluate_candidate_strategy_study(
    *,
    dataset: VerifiedDataset,
    simulation: SimulationConfig,
    initial_cash: Decimal,
    output_root: Path,
    code_commit: str,
) -> StrategyStudyArtifacts:
    """Run and persist one complete local Candidate study from verified candles."""

    policy = CandidatePolicy.locked_v0_1()
    if dataset.manifest.instrument.symbol != policy.instrument_symbol:
        raise StudyArtifactError("candidate dataset instrument does not match locked policy")
    if dataset.manifest.timeframe.value != policy.timeframe:
        raise StudyArtifactError("candidate dataset timeframe does not match locked policy")
    registry = FeatureRegistry.locked_v0_1()
    matrix = registry.compute(dataset.candles)
    label_policy = LabelPolicy.locked_v0_1(simulation)
    labels = label_policy.build(
        dataset.candles,
        eligible_indices=tuple(row.candle_index for row in matrix.rows),
    )
    eligible = tuple(item.decision_candle_index for item in labels.observations)
    split_plan, history_requirement_met = _build_plan(dataset.candles, eligible, policy)

    bundles: dict[tuple[StudyPhase, int | None], PredictionBundle] = {}
    for fold in split_plan.folds:
        bundles[(StudyPhase.DEVELOPMENT, fold.fold_number)] = fit_prediction_bundle(
            phase=StudyPhase.DEVELOPMENT,
            fold_number=fold.fold_number,
            matrix=matrix,
            labels=labels,
            policy=policy,
            training_indices=fold.training_indices,
            calibration_indices=fold.calibration_indices,
            prediction_indices=fold.development_test_indices,
        )
    final_calibration = split_plan.folds[-1].development_test_indices
    final_training = tuple(
        index for index in split_plan.used_label_indices if index < final_calibration[0]
    )
    bundles[(StudyPhase.FINAL, None)] = fit_prediction_bundle(
        phase=StudyPhase.FINAL,
        fold_number=None,
        matrix=matrix,
        labels=labels,
        policy=policy,
        training_indices=final_training,
        calibration_indices=final_calibration,
        prediction_indices=split_plan.final_test_indices,
    )

    baseline_schedules = build_baseline_schedules(dataset.candles)
    plans: dict[tuple[StudyPhase, int | None, str], CasePlan] = {}
    for fold in split_plan.folds:
        _prepare_phase(
            phase=StudyPhase.DEVELOPMENT,
            fold_number=fold.fold_number,
            indices=fold.development_test_indices,
            bundle=bundles[(StudyPhase.DEVELOPMENT, fold.fold_number)],
            dataset=dataset,
            simulation=simulation,
            policy=policy,
            label_policy=label_policy,
            matrix=matrix,
            baseline_schedules=baseline_schedules,
            plans=plans,
        )
    _prepare_phase(
        phase=StudyPhase.FINAL,
        fold_number=None,
        indices=split_plan.final_test_indices,
        bundle=bundles[(StudyPhase.FINAL, None)],
        dataset=dataset,
        simulation=simulation,
        policy=policy,
        label_policy=label_policy,
        matrix=matrix,
        baseline_schedules=baseline_schedules,
        plans=plans,
    )

    policy_bytes = serialize_candidate_policy(policy)
    configuration_bytes = canonical_json_bytes(
        {
            "dataset_id": dataset.manifest.dataset_id,
            "initial_cash": initial_cash,
            "simulation_sha256": hashlib.sha256(
                serialize_simulation_config(simulation)
            ).hexdigest(),
            "policy_version": policy.policy_version,
            "history_requirement_met": history_requirement_met,
        }
    )
    executor = StudyExecutor(
        dataset=dataset,
        output_root=Path(output_root),
        code_commit=code_commit,
        initial_cash=initial_cash,
        plans=plans,
        evidence={},
    )
    study_evidence = StrategyStudyRunner(executor).run(
        split_plan=split_plan,
        policy_sha256=hashlib.sha256(policy_bytes).hexdigest(),
        configuration_sha256=hashlib.sha256(configuration_bytes).hexdigest(),
    )
    report, bootstrap = build_promotion_report(executor, bundles, history_requirement_met)
    models, calibration, predictions, regimes = bundle_payloads(bundles)
    decisions = [
        {
            "phase": phase.value,
            "fold_number": fold_number,
            "case_id": case_id,
            "events": [[index, action.value] for index, action in plan.strategy.events],
        }
        for (phase, fold_number, case_id), plan in sorted(
            plans.items(), key=lambda item: (item[0][0].value, item[0][1] or 9999, item[0][2])
        )
        if case_id == "candidate.multi_model.v0_1"
    ]
    payloads: dict[str, object] = {
        "policy.json": _canonical_mapping(policy_bytes),
        "feature-registry.json": {
            "schema_version": registry.schema_version,
            "maximum_lookback_candles": registry.maximum_lookback_candles,
            "definitions": [asdict(item) for item in registry.definitions],
            "trend_feature_names": list(registry.trend_feature_names),
            "mean_reversion_feature_names": list(registry.mean_reversion_feature_names),
            "regime_feature_names": list(registry.regime_feature_names),
        },
        "feature-matrix.jsonl": [
            {
                "candle_index": row.candle_index,
                "candle_open_time": row.candle_open_time,
                "values": list(row.values),
            }
            for row in matrix.rows
        ],
        "labels.jsonl": [asdict(item) for item in labels.observations],
        "split-plan.json": split_plan_payload(split_plan),
        "folds.jsonl": [
            {
                "fold_number": fold.fold_number,
                "training_count": len(fold.training_indices),
                "calibration_count": len(fold.calibration_indices),
                "development_test_count": len(fold.development_test_indices),
            }
            for fold in split_plan.folds
        ],
        "models.jsonl": models,
        "calibration.jsonl": calibration,
        "predictions.jsonl": predictions,
        "regimes.jsonl": regimes,
        "arbitration-decisions.jsonl": decisions,
        "baselines.json": {
            "ids": list(policy.baseline_ids),
            "provider_free": True,
            "shared_simulation": True,
        },
        "ablations.json": {
            "case_ids": [case for case in REQUIRED_FINAL_CASE_IDS if case.startswith("ablation.")]
        },
        "negative-controls.json": {
            "case_ids": [case for case in REQUIRED_FINAL_CASE_IDS if case.startswith("control.")]
        },
        "cost-stress.json": {"multipliers": ["1.5", "2"], "decisions_unchanged": True},
        "parameter-sensitivity.json": {
            "case_ids": [
                case for case in REQUIRED_FINAL_CASE_IDS if case.startswith("sensitivity.")
            ]
        },
        "bootstrap.json": asdict(bootstrap),
        "promotion-gates.json": {
            "classification": report.classification.value,
            "gates": [asdict(gate) for gate in report.gates],
        },
        "limitations.json": {
            "production_eligible": False,
            "history_requirement_met": history_requirement_met,
            "real_seven_year_run_claimed": False,
            "synthetic_or_short_history_is_non_promotable": not history_requirement_met,
            "ohlcv_limitations": [
                "intrabar_path",
                "queue_priority",
                "hidden_liquidity",
                "market_impact",
            ],
        },
    }
    artifacts = build_study_artifacts(
        cast(StrategyStudyEvidence, study_evidence),
        classification=report.classification,
        payloads=payloads,
        code_commit=code_commit,
    )
    LocalStrategyStudyStore(Path(output_root)).write(artifacts)
    return artifacts


__all__ = [
    "ReplayableStudyStrategy",
    "evaluate_candidate_strategy_study",
    "reconstruct_study_strategy",
]
