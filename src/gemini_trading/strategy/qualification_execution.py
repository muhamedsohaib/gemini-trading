"""Executable development-only qualification for Candidate v0.2."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from decimal import Decimal, localcontext
from pathlib import Path

from gemini_trading.research.config import SimulationConfig, serialize_simulation_config
from gemini_trading.research.dataset_reader import VerifiedDataset
from gemini_trading.research.metrics import calculate_metrics, completed_trades
from gemini_trading.research.serialization import canonical_json_bytes
from gemini_trading.research.verification import ResearchVerificationService
from gemini_trading.strategy.baselines import build_baseline_schedules
from gemini_trading.strategy.determinism import (
    TrendDeterminismReceipt,
    fit_verified_prediction_bundle,
)
from gemini_trading.strategy.errors import StudyArtifactError
from gemini_trading.strategy.evaluation import (
    BootstrapResult,
    CostStressEvaluation,
    FoldEvaluation,
    NeighborEvaluation,
    deterministic_moving_block_bootstrap,
)
from gemini_trading.strategy.evaluator import reconstruct_study_strategy
from gemini_trading.strategy.features import FeatureRegistry
from gemini_trading.strategy.handoff import DatasetHandoffManifest
from gemini_trading.strategy.labels import LabelPolicy
from gemini_trading.strategy.policy import CandidatePolicy, serialize_candidate_policy
from gemini_trading.strategy.qualification import (
    QualificationEvidence,
    QualificationReport,
    evaluate_development_qualification,
)
from gemini_trading.strategy.splits import DevelopmentQualificationPlan, WalkForwardFold
from gemini_trading.strategy.study import REQUIRED_FINAL_CASE_IDS, StudyCaseEvidence, StudyPhase
from gemini_trading.strategy.study_execution import (
    StudyExecutor,
    component_value_supported,
    shuffled_labels_passes_any_economic_gate,
)
from gemini_trading.strategy.study_plans import prepare_phase
from gemini_trading.strategy.study_predictions import PredictionBundle

_ZERO = Decimal("0")
_ONE = Decimal("1")
_SIMPLE_IDS = (
    "buy_hold.v1",
    "ema_20_50.v1",
    "donchian_20_10.v1",
    "mean_reversion_z24.v1",
)
_SPECIALIST_IDS = ("trend.specialist.v1", "mean_reversion.specialist.v1")


@dataclass(frozen=True, slots=True)
class AggregatePathMetrics:
    """Compounded metrics over concatenated non-overlapping development-test returns."""

    net_return: Decimal
    maximum_drawdown: Decimal
    return_to_drawdown: Decimal | None


@dataclass(frozen=True, slots=True)
class QualificationRun:
    """Complete in-memory receipt for one executed Candidate v0.2 qualification."""

    policy_sha256: str
    configuration_sha256: str
    development_plan_sha256: str
    policy_bytes: bytes
    configuration_bytes: bytes
    development_plan_bytes: bytes
    report: QualificationReport
    bootstrap: BootstrapResult
    determinism_receipts: tuple[TrendDeterminismReceipt, ...]
    case_evidence: tuple[StudyCaseEvidence, ...]


def qualification_case_ids(policy: CandidatePolicy) -> tuple[str, ...]:
    """Return the complete fixed development qualification case set for v0.2."""

    if (
        policy.strategy_id != "candidate.multi_model.v0_2"
        or policy.policy_version != "candidate-multi-model-v0.2"
    ):
        raise StudyArtifactError("qualification requires the exact Candidate v0.2 policy")
    return tuple(
        policy.strategy_id if case_id == "candidate.multi_model.v0_1" else case_id
        for case_id in REQUIRED_FINAL_CASE_IDS
    )


def aggregate_path_metrics(period_returns: tuple[Decimal, ...]) -> AggregatePathMetrics:
    """Compound one ordered OOS return path and recompute drawdown from first principles."""

    if not period_returns:
        raise StudyArtifactError("aggregate development path is empty")
    if any(not value.is_finite() or value <= -_ONE for value in period_returns):
        raise StudyArtifactError("aggregate development returns must be finite and above -1")
    with localcontext() as context:
        context.prec = 34
        wealth = _ONE
        peak = _ONE
        maximum_drawdown = _ZERO
        for period_return in period_returns:
            wealth *= _ONE + period_return
            peak = max(peak, wealth)
            if peak > _ZERO:
                maximum_drawdown = max(maximum_drawdown, (peak - wealth) / peak)
        net_return = wealth - _ONE
        return_to_drawdown = None if maximum_drawdown == _ZERO else net_return / maximum_drawdown
    return AggregatePathMetrics(
        net_return=net_return,
        maximum_drawdown=maximum_drawdown,
        return_to_drawdown=return_to_drawdown,
    )


def _development_plan_bytes(plan: DevelopmentQualificationPlan) -> bytes:
    return canonical_json_bytes(asdict(plan))


def _qualification_configuration_bytes(
    *,
    dataset_id: str,
    initial_cash: Decimal,
    simulation: SimulationConfig,
    policy: CandidatePolicy,
) -> bytes:
    simulation_bytes = serialize_simulation_config(simulation)
    return canonical_json_bytes(
        {
            "schema_version": "candidate-v0.2-qualification-config-v1",
            "dataset_id": dataset_id,
            "initial_cash": initial_cash,
            "simulation_sha256": hashlib.sha256(simulation_bytes).hexdigest(),
            "strategy_id": policy.strategy_id,
            "policy_version": policy.policy_version,
        }
    )


def _validate_inputs(
    *,
    dataset: VerifiedDataset,
    handoff: DatasetHandoffManifest,
    policy: CandidatePolicy,
    code_commit: str,
) -> None:
    qualification_case_ids(policy)
    if handoff.source_commit != code_commit:
        raise StudyArtifactError("qualification source commit does not match Stage 1 handoff")
    if handoff.dataset_id != dataset.manifest.dataset_id:
        raise StudyArtifactError("qualification dataset identity does not match Stage 1 handoff")
    if dataset.manifest.schema_version != "candle-dataset-v4":
        raise StudyArtifactError("qualification requires candle-dataset-v4 evidence")
    if dataset.segment_manifest is None:
        raise StudyArtifactError("qualification requires verified segment evidence")
    if handoff.segment_boundary_indices != dataset.segment_manifest.boundary_indices:
        raise StudyArtifactError("qualification segment boundaries do not match handoff")
    if len(dataset.candles) != handoff.candle_count:
        raise StudyArtifactError("qualification candle count does not match handoff")


def _positive_profit(executor: StudyExecutor, key: tuple[StudyPhase, int | None, str]) -> Decimal:
    return sum(
        (
            trade.realized_pnl
            for trade in completed_trades(executor.evidence[key])
            if trade.realized_pnl > _ZERO
        ),
        _ZERO,
    )


def _fold_oos_returns(
    executor: StudyExecutor,
    fold: WalkForwardFold,
    case_id: str,
) -> tuple[Decimal, ...]:
    key = (StudyPhase.DEVELOPMENT, fold.fold_number, case_id)
    evidence = executor.evidence[key]
    plan = executor.plans[key]
    end_exclusive = plan.strategy.evaluation_end_exclusive
    if end_exclusive is None:
        raise StudyArtifactError("qualification case is missing an evaluation boundary")
    start = fold.development_test.start_inclusive
    if start >= end_exclusive or end_exclusive > len(evidence.account_series):
        raise StudyArtifactError("qualification OOS account path is incomplete")
    previous = (
        evidence.experiment_manifest.initial_cash
        if start == 0
        else evidence.account_series[start - 1].marked_equity
    )
    values: list[Decimal] = []
    for snapshot in evidence.account_series[start:end_exclusive]:
        if previous <= _ZERO:
            raise StudyArtifactError("qualification OOS equity must remain positive")
        values.append(snapshot.marked_equity / previous - _ONE)
        previous = snapshot.marked_equity
    return tuple(values)


def _case_period_returns(
    executor: StudyExecutor,
    plan: DevelopmentQualificationPlan,
    case_id: str,
) -> tuple[Decimal, ...]:
    return tuple(
        value for fold in plan.folds for value in _fold_oos_returns(executor, fold, case_id)
    )


def _aggregate_case(
    executor: StudyExecutor,
    plan: DevelopmentQualificationPlan,
    case_id: str,
) -> AggregatePathMetrics:
    return aggregate_path_metrics(_case_period_returns(executor, plan, case_id))


def _fold_evaluations(
    executor: StudyExecutor,
    plan: DevelopmentQualificationPlan,
    policy: CandidatePolicy,
) -> tuple[FoldEvaluation, ...]:
    folds: list[FoldEvaluation] = []
    for fold in plan.folds:
        key = (StudyPhase.DEVELOPMENT, fold.fold_number, policy.strategy_id)
        candidate = executor.evidence[key]
        candidate_metrics = calculate_metrics(candidate)
        baseline_metrics = tuple(
            calculate_metrics(
                executor.evidence[(StudyPhase.DEVELOPMENT, fold.fold_number, case_id)]
            )
            for case_id in _SIMPLE_IDS
        )
        defined = tuple(
            item.return_to_drawdown
            for item in baseline_metrics
            if item.return_to_drawdown is not None
        )
        folds.append(
            FoldEvaluation(
                candidate_net_return=candidate_metrics.net_return,
                candidate_return_to_drawdown=candidate_metrics.return_to_drawdown,
                strongest_active_baseline_return_to_drawdown=max(defined) if defined else None,
                positive_profit=_positive_profit(executor, key),
                completed_trades=candidate_metrics.trade_count,
            )
        )
    return tuple(folds)


def _strongest_rtd(metrics: tuple[AggregatePathMetrics, ...]) -> Decimal | None:
    values = tuple(
        item.return_to_drawdown for item in metrics if item.return_to_drawdown is not None
    )
    return max(values) if values else None


def _build_qualification_evidence(
    *,
    executor: StudyExecutor,
    plan: DevelopmentQualificationPlan,
    policy: CandidatePolicy,
    receipts: tuple[TrendDeterminismReceipt, ...],
    replay_verified: bool,
    independent_verified: bool,
) -> tuple[QualificationEvidence, BootstrapResult]:
    primary = _aggregate_case(executor, plan, policy.strategy_id)
    simple = tuple(_aggregate_case(executor, plan, case_id) for case_id in _SIMPLE_IDS)
    specialist = tuple(_aggregate_case(executor, plan, case_id) for case_id in _SPECIALIST_IDS)
    strongest_simple_rtd = _strongest_rtd(simple)
    strongest_specialist_rtd = _strongest_rtd(specialist)

    delayed = _aggregate_case(executor, plan, "control.delayed_features.final")
    shuffled = _aggregate_case(executor, plan, "control.shuffled_labels.seed_1799")
    no_disagreement = _aggregate_case(executor, plan, "ablation.no_disagreement.v1")
    no_volume = _aggregate_case(executor, plan, "ablation.no_volume.v1")
    no_protection = _aggregate_case(executor, plan, "ablation.no_protection.v1")
    cost_one_half = _aggregate_case(executor, plan, "cost.1_5x")
    cost_double = _aggregate_case(executor, plan, "cost.2x")

    neighbor_ids = tuple(
        case_id for case_id in qualification_case_ids(policy) if case_id.startswith("sensitivity.")
    )
    neighbors = tuple(
        NeighborEvaluation(
            net_return=(metrics := _aggregate_case(executor, plan, case_id)).net_return,
            maximum_drawdown=metrics.maximum_drawdown,
        )
        for case_id in neighbor_ids
    )

    if simple:
        baseline_index = max(
            range(len(simple)),
            key=lambda index: simple[index].return_to_drawdown or Decimal("-999999"),
        )
        strongest_baseline_case = _SIMPLE_IDS[baseline_index]
    else:
        raise StudyArtifactError("qualification requires active simple baselines")
    primary_returns = _case_period_returns(executor, plan, policy.strategy_id)
    baseline_returns = _case_period_returns(executor, plan, strongest_baseline_case)
    bootstrap = deterministic_moving_block_bootstrap(
        primary_returns,
        baseline_returns,
        seed=policy.bootstrap_seed,
        replicate_count=policy.bootstrap_replicates,
        block_length=min(policy.bootstrap_block_candles, len(primary_returns)),
    )

    evidence = QualificationEvidence(
        integrity_verified=True,
        trend_determinism=receipts,
        calibration_complete=True,
        development_folds=_fold_evaluations(executor, plan, policy),
        shuffled_labels_safe=not shuffled_labels_passes_any_economic_gate(
            net_return=shuffled.net_return,
            return_to_drawdown=shuffled.return_to_drawdown,
            strongest_simple_return_to_drawdown=strongest_simple_rtd,
            strongest_specialist_return_to_drawdown=strongest_specialist_rtd,
        ),
        delayed_features_component_supported=(
            primary.return_to_drawdown is not None
            and delayed.return_to_drawdown is not None
            and delayed.return_to_drawdown <= Decimal("1.05") * primary.return_to_drawdown
        ),
        disagreement_component_supported=component_value_supported(
            primary_return_to_drawdown=primary.return_to_drawdown,
            primary_maximum_drawdown=primary.maximum_drawdown,
            ablation_return_to_drawdown=no_disagreement.return_to_drawdown,
            ablation_maximum_drawdown=no_disagreement.maximum_drawdown,
            require_drawdown_reduction=False,
        ),
        volume_component_supported=component_value_supported(
            primary_return_to_drawdown=primary.return_to_drawdown,
            primary_maximum_drawdown=primary.maximum_drawdown,
            ablation_return_to_drawdown=no_volume.return_to_drawdown,
            ablation_maximum_drawdown=no_volume.maximum_drawdown,
            require_drawdown_reduction=False,
        ),
        protection_component_supported=component_value_supported(
            primary_return_to_drawdown=primary.return_to_drawdown,
            primary_maximum_drawdown=primary.maximum_drawdown,
            ablation_return_to_drawdown=no_protection.return_to_drawdown,
            ablation_maximum_drawdown=no_protection.maximum_drawdown,
            require_drawdown_reduction=True,
        ),
        primary_aggregate_net_return=primary.net_return,
        primary_aggregate_max_drawdown=primary.maximum_drawdown,
        cost_1_5x=CostStressEvaluation(
            multiplier=Decimal("1.5"),
            net_return=cost_one_half.net_return,
            maximum_drawdown=cost_one_half.maximum_drawdown,
        ),
        cost_2x=CostStressEvaluation(
            multiplier=Decimal("2"),
            net_return=cost_double.net_return,
            maximum_drawdown=cost_double.maximum_drawdown,
        ),
        neighbors=neighbors,
        bootstrap=bootstrap,
        replay_verified=replay_verified,
        independent_verified=independent_verified,
    )
    return evidence, bootstrap


def execute_candidate_v0_2_qualification(
    *,
    dataset: VerifiedDataset,
    handoff: DatasetHandoffManifest,
    simulation: SimulationConfig,
    initial_cash: Decimal,
    output_root: Path,
    code_commit: str,
) -> QualificationRun:
    """Execute all 12 development folds and controls without constructing a final test."""

    policy = CandidatePolicy.locked_v0_2()
    _validate_inputs(dataset=dataset, handoff=handoff, policy=policy, code_commit=code_commit)
    if not simulation.promotable:
        raise StudyArtifactError("qualification requires promotable simulation evidence")
    if not initial_cash.is_finite() or initial_cash <= _ZERO:
        raise StudyArtifactError("qualification initial cash must be finite and positive")

    registry = FeatureRegistry.locked_v0_1()
    matrix = registry.compute(dataset.candles, segments=dataset.segment_manifest)
    label_policy = LabelPolicy.locked_v0_1(simulation)
    labels = label_policy.build(
        dataset.candles,
        eligible_indices=tuple(row.candle_index for row in matrix.rows),
        segments=dataset.segment_manifest,
    )
    eligible = tuple(item.decision_candle_index for item in labels.observations)
    development_plan = DevelopmentQualificationPlan.build(
        dataset.candles,
        eligible,
        policy,
        dataset.segment_manifest,
    )
    baselines = build_baseline_schedules(dataset.candles)
    executor = StudyExecutor(
        dataset=dataset,
        output_root=output_root,
        code_commit=code_commit,
        initial_cash=initial_cash,
        plans={},
        evidence={},
    )
    receipts: list[TrendDeterminismReceipt] = []
    bundles: dict[int, PredictionBundle] = {}
    for fold in development_plan.folds:
        bundle, receipt = fit_verified_prediction_bundle(
            phase=StudyPhase.DEVELOPMENT,
            fold_number=fold.fold_number,
            matrix=matrix,
            labels=labels,
            policy=policy,
            training_indices=fold.training_indices,
            calibration_indices=fold.calibration_indices,
            prediction_indices=fold.development_test_indices,
        )
        receipts.append(receipt)
        bundles[fold.fold_number] = bundle
        prepare_phase(
            phase=StudyPhase.DEVELOPMENT,
            fold_number=fold.fold_number,
            indices=fold.development_test_indices,
            bundle=bundle,
            dataset=dataset,
            simulation=simulation,
            policy=policy,
            label_policy=label_policy,
            matrix=matrix,
            baseline_schedules=baselines,
            plans=executor.plans,
            include_qualification_robustness=True,
        )

    records: list[StudyCaseEvidence] = []
    case_ids = qualification_case_ids(policy)
    for fold in development_plan.folds:
        for case_id in case_ids:
            records.append(
                executor.run_case(
                    phase=StudyPhase.DEVELOPMENT,
                    fold_number=fold.fold_number,
                    case_id=case_id,
                    decision_indices=fold.development_test_indices,
                )
            )

    verifier = ResearchVerificationService(
        root=output_root,
        current_commit_resolver=lambda: code_commit,
        strategy_reconstructor=reconstruct_study_strategy,
    )
    for record in records:
        result = verifier.verify(record.experiment_id)
        if result.experiment_id != record.experiment_id or result.terminal_status != "completed":
            raise StudyArtifactError("qualification experiment verification changed identity")
        if result.result_id != record.evidence_sha256:
            raise StudyArtifactError("qualification experiment result identity changed")
    replay_verified = True
    independent_verified = True

    qualification_evidence, bootstrap = _build_qualification_evidence(
        executor=executor,
        plan=development_plan,
        policy=policy,
        receipts=tuple(receipts),
        replay_verified=replay_verified,
        independent_verified=independent_verified,
    )
    report = evaluate_development_qualification(qualification_evidence)
    policy_bytes = serialize_candidate_policy(policy)
    configuration_bytes = _qualification_configuration_bytes(
        dataset_id=dataset.manifest.dataset_id,
        initial_cash=initial_cash,
        simulation=simulation,
        policy=policy,
    )
    development_plan_bytes = _development_plan_bytes(development_plan)
    return QualificationRun(
        policy_sha256=hashlib.sha256(policy_bytes).hexdigest(),
        configuration_sha256=hashlib.sha256(configuration_bytes).hexdigest(),
        development_plan_sha256=hashlib.sha256(development_plan_bytes).hexdigest(),
        policy_bytes=policy_bytes,
        configuration_bytes=configuration_bytes,
        development_plan_bytes=development_plan_bytes,
        report=report,
        bootstrap=bootstrap,
        determinism_receipts=tuple(receipts),
        case_evidence=tuple(records),
    )


__all__ = [
    "AggregatePathMetrics",
    "QualificationRun",
    "aggregate_path_metrics",
    "execute_candidate_v0_2_qualification",
    "qualification_case_ids",
]
