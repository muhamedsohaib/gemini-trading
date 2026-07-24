"""Concrete provider-free Candidate v0.1 study evaluation pipeline."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path
from typing import cast

from gemini_trading.research.config import SimulationConfig, serialize_simulation_config
from gemini_trading.research.dataset_reader import VerifiedDataset
from gemini_trading.research.serialization import canonical_json_bytes
from gemini_trading.strategy.artifacts import (
    LocalStrategyStudyStore,
    StrategyStudyArtifacts,
    build_study_artifacts,
)
from gemini_trading.strategy.baselines import build_baseline_schedules
from gemini_trading.strategy.errors import StudyArtifactError
from gemini_trading.strategy.features import FeatureRegistry
from gemini_trading.strategy.labels import LabelPolicy
from gemini_trading.strategy.policy import CandidatePolicy, serialize_candidate_policy
from gemini_trading.strategy.study import (
    REQUIRED_FINAL_CASE_IDS,
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
from gemini_trading.strategy.study_plans import build_split_plan, prepare_phase
from gemini_trading.strategy.study_predictions import PredictionBundle, fit_prediction_bundle
from gemini_trading.strategy.study_strategy import (
    ReplayableStudyStrategy,
    reconstruct_study_strategy,
)


def _canonical_mapping(raw: bytes) -> dict[str, object]:
    loaded: object = json.loads(raw)
    if not isinstance(loaded, dict):
        raise StudyArtifactError("internal canonical mapping is invalid")
    mapping = cast(dict[object, object], loaded)
    if not all(isinstance(key, str) for key in mapping):
        raise StudyArtifactError("internal canonical mapping keys are invalid")
    return cast(dict[str, object], mapping)


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
    split_plan, history_requirement_met = build_split_plan(dataset.candles, eligible, policy)

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
        prepare_phase(
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
    prepare_phase(
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
            plans.items(),
            key=lambda item: (item[0][0].value, item[0][1] or 9999, item[0][2]),
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
        study_evidence,
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
