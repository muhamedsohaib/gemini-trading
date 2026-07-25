"""Two-phase operational Candidate evaluation for sealed historical validation."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
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
from gemini_trading.strategy.errors import (
    FinalAccessError,
    PreFinalArtifactError,
    StudyArtifactError,
)
from gemini_trading.strategy.evaluation import PromotionReport
from gemini_trading.strategy.features import FeatureMatrix, FeatureRegistry
from gemini_trading.strategy.final_access import DurableFinalAccessReceipt, FinalAccessIdentity
from gemini_trading.strategy.handoff import DatasetHandoffManifest
from gemini_trading.strategy.labels import LabelPolicy, LabelVector
from gemini_trading.strategy.policy import CandidatePolicy, serialize_candidate_policy
from gemini_trading.strategy.pre_final import (
    LocalPreFinalStore,
    PreFinalArtifacts,
    build_pre_final_artifacts,
    verify_pre_final_artifacts,
)
from gemini_trading.strategy.splits import ChronologicalSplitPlan
from gemini_trading.strategy.study import (
    REQUIRED_DEVELOPMENT_CASE_IDS,
    REQUIRED_FINAL_CASE_IDS,
    FinalTestReceipt,
    StrategyStudyEvidence,
    StudyCaseEvidence,
    StudyPhase,
    split_plan_payload,
    split_plan_sha256,
)
from gemini_trading.strategy.study_execution import (
    CasePlan,
    StudyExecutor,
    build_promotion_report,
    bundle_payloads,
)
from gemini_trading.strategy.study_plans import build_split_plan, prepare_phase
from gemini_trading.strategy.study_predictions import PredictionBundle, fit_prediction_bundle


@dataclass(frozen=True, slots=True)
class CandidatePreparation:
    """Deterministic preparation state with an explicit final-phase boundary."""

    policy: CandidatePolicy
    registry: FeatureRegistry
    matrix: FeatureMatrix
    labels: LabelVector
    split_plan: ChronologicalSplitPlan
    bundles: Mapping[tuple[StudyPhase, int | None], PredictionBundle]
    plans: Mapping[tuple[StudyPhase, int | None, str], CasePlan]
    policy_bytes: bytes
    configuration_bytes: bytes
    split_plan_bytes: bytes
    policy_sha256: str
    configuration_sha256: str
    split_plan_sha256: str
    history_requirement_met: bool


def _canonical_mapping(raw: bytes) -> dict[str, object]:
    loaded: object = json.loads(raw)
    if not isinstance(loaded, dict):
        raise StudyArtifactError("internal canonical mapping is invalid")
    mapping = cast(dict[object, object], loaded)
    if not all(isinstance(key, str) for key in mapping):
        raise StudyArtifactError("internal canonical mapping keys are invalid")
    return cast(dict[str, object], mapping)


def _validate_dataset(dataset: VerifiedDataset, policy: CandidatePolicy) -> None:
    if dataset.manifest.instrument.symbol != policy.instrument_symbol:
        raise StudyArtifactError("candidate dataset instrument does not match locked policy")
    if dataset.manifest.timeframe.value != policy.timeframe:
        raise StudyArtifactError("candidate dataset timeframe does not match locked policy")


def build_candidate_preparation(
    *,
    dataset: VerifiedDataset,
    simulation: SimulationConfig,
    initial_cash: Decimal,
    include_final: bool,
) -> CandidatePreparation:
    policy = CandidatePolicy.locked_v0_1()
    _validate_dataset(dataset, policy)
    registry = FeatureRegistry.locked_v0_1()
    label_policy = LabelPolicy.locked_v0_1(simulation)
    structural_eligible = tuple(
        range(
            registry.maximum_lookback_candles,
            len(dataset.candles) - label_policy.horizon_candles - 1,
        )
    )
    split_plan, history_requirement_met = build_split_plan(
        dataset.candles,
        structural_eligible,
        policy,
    )
    preparation_candles = (
        dataset.candles
        if include_final
        else dataset.candles[: split_plan.final_test_boundary_index]
    )
    preparation_dataset = VerifiedDataset(
        manifest=dataset.manifest,
        candles=preparation_candles,
        canonical_bytes=dataset.canonical_bytes,
    )
    matrix = registry.compute(preparation_candles)
    labels = label_policy.build(
        preparation_candles,
        eligible_indices=tuple(row.candle_index for row in matrix.rows),
    )

    bundles: dict[tuple[StudyPhase, int | None], PredictionBundle] = {}
    plans: dict[tuple[StudyPhase, int | None, str], CasePlan] = {}
    baseline_schedules = build_baseline_schedules(preparation_candles)
    for fold in split_plan.folds:
        key = (StudyPhase.DEVELOPMENT, fold.fold_number)
        bundle = fit_prediction_bundle(
            phase=StudyPhase.DEVELOPMENT,
            fold_number=fold.fold_number,
            matrix=matrix,
            labels=labels,
            policy=policy,
            training_indices=fold.training_indices,
            calibration_indices=fold.calibration_indices,
            prediction_indices=fold.development_test_indices,
        )
        bundles[key] = bundle
        prepare_phase(
            phase=StudyPhase.DEVELOPMENT,
            fold_number=fold.fold_number,
            indices=fold.development_test_indices,
            bundle=bundle,
            dataset=preparation_dataset,
            simulation=simulation,
            policy=policy,
            label_policy=label_policy,
            matrix=matrix,
            baseline_schedules=baseline_schedules,
            plans=plans,
        )

    if include_final:
        final_calibration = split_plan.folds[-1].development_test_indices
        final_training = tuple(
            index for index in split_plan.used_label_indices if index < final_calibration[0]
        )
        final_bundle = fit_prediction_bundle(
            phase=StudyPhase.FINAL,
            fold_number=None,
            matrix=matrix,
            labels=labels,
            policy=policy,
            training_indices=final_training,
            calibration_indices=final_calibration,
            prediction_indices=split_plan.final_test_indices,
        )
        bundles[(StudyPhase.FINAL, None)] = final_bundle
        prepare_phase(
            phase=StudyPhase.FINAL,
            fold_number=None,
            indices=split_plan.final_test_indices,
            bundle=final_bundle,
            dataset=preparation_dataset,
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
    split_bytes = canonical_json_bytes(split_plan_payload(split_plan))
    return CandidatePreparation(
        policy=policy,
        registry=registry,
        matrix=matrix,
        labels=labels,
        split_plan=split_plan,
        bundles=bundles,
        plans=plans,
        policy_bytes=policy_bytes,
        configuration_bytes=configuration_bytes,
        split_plan_bytes=split_bytes,
        policy_sha256=hashlib.sha256(policy_bytes).hexdigest(),
        configuration_sha256=hashlib.sha256(configuration_bytes).hexdigest(),
        split_plan_sha256=split_plan_sha256(split_plan),
        history_requirement_met=history_requirement_met,
    )


def _executor(
    *,
    preparation: CandidatePreparation,
    dataset: VerifiedDataset,
    output_root: Path,
    code_commit: str,
    initial_cash: Decimal,
) -> StudyExecutor:
    return StudyExecutor(
        dataset=dataset,
        output_root=Path(output_root),
        code_commit=code_commit,
        initial_cash=initial_cash,
        plans=dict(preparation.plans),
        evidence={},
    )


def _execute_development(
    executor: StudyExecutor,
    preparation: CandidatePreparation,
) -> tuple[StudyCaseEvidence, ...]:
    records: list[StudyCaseEvidence] = []
    for fold in preparation.split_plan.folds:
        for case_id in REQUIRED_DEVELOPMENT_CASE_IDS:
            records.append(
                executor.run_case(
                    phase=StudyPhase.DEVELOPMENT,
                    fold_number=fold.fold_number,
                    case_id=case_id,
                    decision_indices=fold.development_test_indices,
                )
            )
    return tuple(records)


def _pre_final_records(pre_final: PreFinalArtifacts) -> tuple[StudyCaseEvidence, ...]:
    records: list[StudyCaseEvidence] = []
    raw = pre_final.artifact_bytes("development-experiments.jsonl")
    for line in raw.splitlines():
        loaded: object = json.loads(line)
        if not isinstance(loaded, dict):
            raise PreFinalArtifactError("invalid development experiment JSON")
        row = cast(dict[str, object], loaded)
        fold_number = row.get("fold_number")
        if isinstance(fold_number, bool) or not isinstance(fold_number, int):
            raise PreFinalArtifactError("invalid development experiment fold")
        try:
            phase = StudyPhase(cast(str, row["phase"]))
            record = StudyCaseEvidence(
                case_id=cast(str, row["case_id"]),
                phase=phase,
                fold_number=fold_number,
                terminal_status=cast(str, row["terminal_status"]),
                experiment_id=cast(str, row["experiment_id"]),
                evidence_sha256=cast(str, row["evidence_sha256"]),
            )
        except (KeyError, TypeError, ValueError):
            raise PreFinalArtifactError("invalid development experiment evidence") from None
        records.append(record)
    return tuple(records)


def prepare_candidate_strategy_study(
    *,
    dataset: VerifiedDataset,
    simulation: SimulationConfig,
    initial_cash: Decimal,
    output_root: Path,
    code_commit: str,
    handoff: DatasetHandoffManifest,
) -> PreFinalArtifacts:
    """Complete all development work without fitting or executing the final phase."""

    if handoff.dataset_id != dataset.manifest.dataset_id:
        raise PreFinalArtifactError("pre-final dataset handoff identity mismatch")
    if handoff.source_commit != code_commit:
        raise PreFinalArtifactError("pre-final source commit mismatch")
    preparation = build_candidate_preparation(
        dataset=dataset,
        simulation=simulation,
        initial_cash=initial_cash,
        include_final=False,
    )
    executor = _executor(
        preparation=preparation,
        dataset=dataset,
        output_root=output_root,
        code_commit=code_commit,
        initial_cash=initial_cash,
    )
    records = _execute_development(executor, preparation)
    artifacts = build_pre_final_artifacts(
        dataset_id=dataset.manifest.dataset_id,
        handoff=handoff,
        code_commit=code_commit,
        policy_bytes=preparation.policy_bytes,
        configuration_bytes=preparation.configuration_bytes,
        split_plan_bytes=preparation.split_plan_bytes,
        split_plan_sha256=preparation.split_plan_sha256,
        development_records=records,
    )
    LocalPreFinalStore(Path(output_root)).write(artifacts)
    return artifacts


def final_access_identity(
    *,
    pre_final: PreFinalArtifacts,
    handoff: DatasetHandoffManifest,
    preparation: CandidatePreparation,
    code_commit: str,
    workflow_run_id: int,
    workflow_run_attempt: int,
) -> FinalAccessIdentity:
    """Build the exact identity authorized before final rows are materialized."""

    return FinalAccessIdentity(
        code_commit=code_commit,
        dataset_id=handoff.dataset_id,
        configuration_sha256=preparation.configuration_sha256,
        policy_sha256=preparation.policy_sha256,
        split_plan_sha256=preparation.split_plan_sha256,
        pre_final_id=pre_final.pre_final_id,
        workflow_run_id=workflow_run_id,
        workflow_run_attempt=workflow_run_attempt,
    )


def _study_evidence(
    *,
    preparation: CandidatePreparation,
    development_records: tuple[StudyCaseEvidence, ...],
    final_records: tuple[StudyCaseEvidence, ...],
    receipt: DurableFinalAccessReceipt,
) -> StrategyStudyEvidence:
    identity_payload: dict[str, object] = {
        "schema_version": "strategy-study-v1",
        "split_plan_sha256": preparation.split_plan_sha256,
        "policy_sha256": preparation.policy_sha256,
        "configuration_sha256": preparation.configuration_sha256,
        "development_cases": list(REQUIRED_DEVELOPMENT_CASE_IDS),
        "final_cases": list(REQUIRED_FINAL_CASE_IDS),
    }
    return StrategyStudyEvidence(
        study_id=hashlib.sha256(canonical_json_bytes(identity_payload)).hexdigest(),
        split_plan_sha256=preparation.split_plan_sha256,
        policy_sha256=preparation.policy_sha256,
        configuration_sha256=preparation.configuration_sha256,
        fold_records=development_records,
        final_records=final_records,
        final_test_receipt=FinalTestReceipt(
            evaluation_count=1,
            final_test=preparation.split_plan.final_test,
            split_plan_sha256=preparation.split_plan_sha256,
            policy_sha256=preparation.policy_sha256,
            configuration_sha256=preparation.configuration_sha256,
            receipt_id=receipt.receipt_id,
        ),
    )


def _payloads(
    preparation: CandidatePreparation,
    executor: StudyExecutor,
) -> tuple[dict[str, object], PromotionReport]:
    report, bootstrap = build_promotion_report(
        executor,
        dict(preparation.bundles),
        preparation.history_requirement_met,
    )
    models, calibration, predictions, regimes = bundle_payloads(preparation.bundles)
    decisions = [
        {
            "phase": phase.value,
            "fold_number": fold_number,
            "case_id": case_id,
            "events": [[index, action.value] for index, action in plan.strategy.events],
        }
        for (phase, fold_number, case_id), plan in sorted(
            preparation.plans.items(),
            key=lambda item: (item[0][0].value, item[0][1] or 9999, item[0][2]),
        )
        if case_id == "candidate.multi_model.v0_1"
    ]
    payloads: dict[str, object] = {
        "policy.json": _canonical_mapping(preparation.policy_bytes),
        "feature-registry.json": {
            "schema_version": preparation.registry.schema_version,
            "maximum_lookback_candles": preparation.registry.maximum_lookback_candles,
            "definitions": [asdict(item) for item in preparation.registry.definitions],
            "trend_feature_names": list(preparation.registry.trend_feature_names),
            "mean_reversion_feature_names": list(preparation.registry.mean_reversion_feature_names),
            "regime_feature_names": list(preparation.registry.regime_feature_names),
        },
        "feature-matrix.jsonl": [
            {
                "candle_index": row.candle_index,
                "candle_open_time": row.candle_open_time,
                "values": list(row.values),
            }
            for row in preparation.matrix.rows
        ],
        "labels.jsonl": [asdict(item) for item in preparation.labels.observations],
        "split-plan.json": split_plan_payload(preparation.split_plan),
        "folds.jsonl": [
            {
                "fold_number": fold.fold_number,
                "training_count": len(fold.training_indices),
                "calibration_count": len(fold.calibration_indices),
                "development_test_count": len(fold.development_test_indices),
            }
            for fold in preparation.split_plan.folds
        ],
        "models.jsonl": models,
        "calibration.jsonl": calibration,
        "predictions.jsonl": predictions,
        "regimes.jsonl": regimes,
        "arbitration-decisions.jsonl": decisions,
        "baselines.json": {
            "ids": list(preparation.policy.baseline_ids),
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
            "history_requirement_met": preparation.history_requirement_met,
            "real_seven_year_run_claimed": preparation.history_requirement_met,
            "synthetic_or_short_history_is_non_promotable": not preparation.history_requirement_met,
            "ohlcv_limitations": [
                "intrabar_path",
                "queue_priority",
                "hidden_liquidity",
                "market_impact",
            ],
        },
    }
    return payloads, report


def _extend_manifest(
    artifacts: StrategyStudyArtifacts,
    *,
    evidence: StrategyStudyEvidence,
    code_commit: str,
    pre_final: PreFinalArtifacts,
    handoff: DatasetHandoffManifest,
    receipt: DurableFinalAccessReceipt,
) -> StrategyStudyArtifacts:
    files = dict(artifacts.files)
    files["study-manifest.json"] = canonical_json_bytes(
        {
            "schema_version": "strategy-study-v1",
            "study_id": evidence.study_id,
            "split_plan_sha256": evidence.split_plan_sha256,
            "policy_sha256": evidence.policy_sha256,
            "configuration_sha256": evidence.configuration_sha256,
            "code_commit": code_commit,
            "final_test_receipt_id": evidence.final_test_receipt.receipt_id,
            "final_evaluation_count": 1,
            "pre_final_id": pre_final.pre_final_id,
            "dataset_handoff_inventory_root": handoff.inventory_root_sha256,
            "durable_final_access_receipt_id": receipt.receipt_id,
        }
    )
    core = tuple(
        sorted(
            (name, content)
            for name, content in files.items()
            if name != "study-result-manifest.json"
        )
    )
    hashes = tuple((name, hashlib.sha256(content).hexdigest()) for name, content in core)
    identity: dict[str, object] = {
        "schema_version": "strategy-study-result-v1",
        "study_id": evidence.study_id,
        "artifacts": [list(item) for item in hashes],
        "classification": artifacts.classification.value,
    }
    result_id = hashlib.sha256(canonical_json_bytes(identity)).hexdigest()
    result = canonical_json_bytes({**identity, "study_result_id": result_id})
    return StrategyStudyArtifacts(
        study_id=evidence.study_id,
        study_result_id=result_id,
        classification=artifacts.classification,
        files=tuple(sorted((*core, ("study-result-manifest.json", result)))),
    )


def complete_candidate_strategy_study(
    *,
    pre_final: PreFinalArtifacts,
    receipt: DurableFinalAccessReceipt,
    handoff: DatasetHandoffManifest,
    dataset: VerifiedDataset,
    simulation: SimulationConfig,
    initial_cash: Decimal,
    output_root: Path,
    code_commit: str,
) -> StrategyStudyArtifacts:
    """Verify the durable boundary, then execute and persist the final phase once."""

    verify_pre_final_artifacts(
        pre_final,
        expected_handoff=handoff,
        expected_code_commit=code_commit,
        expected_dataset_id=dataset.manifest.dataset_id,
    )
    development = build_candidate_preparation(
        dataset=dataset,
        simulation=simulation,
        initial_cash=initial_cash,
        include_final=False,
    )
    expected_identity = final_access_identity(
        pre_final=pre_final,
        handoff=handoff,
        preparation=development,
        code_commit=code_commit,
        workflow_run_id=receipt.identity.workflow_run_id,
        workflow_run_attempt=receipt.identity.workflow_run_attempt,
    )
    if receipt.identity != expected_identity:
        raise FinalAccessError("final-test access identity mismatch")

    preparation = build_candidate_preparation(
        dataset=dataset,
        simulation=simulation,
        initial_cash=initial_cash,
        include_final=True,
    )
    executor = _executor(
        preparation=preparation,
        dataset=dataset,
        output_root=output_root,
        code_commit=code_commit,
        initial_cash=initial_cash,
    )
    development_records = _execute_development(executor, preparation)
    if development_records != _pre_final_records(pre_final):
        raise PreFinalArtifactError("reconstructed development evidence does not match pre-final")
    final_records = tuple(
        executor.run_case(
            phase=StudyPhase.FINAL,
            fold_number=None,
            case_id=case_id,
            decision_indices=preparation.split_plan.final_test_indices,
        )
        for case_id in REQUIRED_FINAL_CASE_IDS
    )
    evidence = _study_evidence(
        preparation=preparation,
        development_records=development_records,
        final_records=final_records,
        receipt=receipt,
    )
    payloads, report = _payloads(preparation, executor)
    base = build_study_artifacts(
        evidence,
        classification=report.classification,
        payloads=payloads,
        code_commit=code_commit,
    )
    artifacts = _extend_manifest(
        base,
        evidence=evidence,
        code_commit=code_commit,
        pre_final=pre_final,
        handoff=handoff,
        receipt=receipt,
    )
    LocalStrategyStudyStore(Path(output_root)).write(artifacts)
    return artifacts


__all__ = [
    "CandidatePreparation",
    "build_candidate_preparation",
    "complete_candidate_strategy_study",
    "final_access_identity",
    "prepare_candidate_strategy_study",
]
