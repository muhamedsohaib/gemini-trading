"""Provider-free execution and promotion evidence for Candidate strategy studies."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
from typing import cast

from gemini_trading.research.artifacts import LocalResearchStore, build_artifacts
from gemini_trading.research.config import SimulationConfig
from gemini_trading.research.dataset_reader import VerifiedDataset
from gemini_trading.research.engine import BacktestEvidence, run_backtest
from gemini_trading.research.identity import build_experiment_manifest
from gemini_trading.research.metrics import calculate_metrics, completed_trades
from gemini_trading.strategy.calibration import serialize_platt_artifact
from gemini_trading.strategy.contracts import RegimeState
from gemini_trading.strategy.errors import StudyArtifactError
from gemini_trading.strategy.evaluation import (
    BootstrapResult,
    CostStressEvaluation,
    FinalEvaluation,
    FoldEvaluation,
    NeighborEvaluation,
    PromotionClassification,
    PromotionEvidence,
    PromotionReport,
    RegimeMetrics,
    deterministic_moving_block_bootstrap,
    evaluate_promotion,
)
from gemini_trading.strategy.models import serialize_model_artifact
from gemini_trading.strategy.study import (
    REQUIRED_FINAL_CASE_IDS,
    StudyCaseEvidence,
    StudyPhase,
)
from gemini_trading.strategy.study_predictions import PredictionBundle
from gemini_trading.strategy.study_strategy import ReplayableStudyStrategy

_ZERO = Decimal("0")
_ONE = Decimal("1")


@dataclass(frozen=True, slots=True)
class CasePlan:
    """One prepared simulator strategy and its exact cost configuration."""

    strategy: ReplayableStudyStrategy
    simulation: SimulationConfig


@dataclass(slots=True)
class StudyExecutor:
    """Execute prepared study cases through the deterministic research engine."""

    dataset: VerifiedDataset
    output_root: Path
    code_commit: str
    initial_cash: Decimal
    plans: dict[tuple[StudyPhase, int | None, str], CasePlan]
    evidence: dict[tuple[StudyPhase, int | None, str], BacktestEvidence]

    def run_case(
        self,
        *,
        phase: StudyPhase,
        fold_number: int | None,
        case_id: str,
        decision_indices: tuple[int, ...],
    ) -> StudyCaseEvidence:
        del decision_indices
        key = (phase, fold_number, case_id)
        try:
            plan = self.plans[key]
        except KeyError:
            raise StudyArtifactError(f"missing prepared study case: {case_id}") from None
        seed_payload = f"{phase.value}:{fold_number}:{case_id}"
        seed = int(hashlib.sha256(seed_payload.encode()).hexdigest()[:8], 16)
        manifest = build_experiment_manifest(
            dataset=self.dataset,
            config=plan.simulation,
            code_commit=self.code_commit,
            strategy_id=plan.strategy.strategy_id,
            strategy_config=plan.strategy.configuration(),
            initial_cash=self.initial_cash,
            random_seed=seed,
        )
        backtest = run_backtest(self.dataset, manifest, plan.simulation, plan.strategy)
        artifacts = build_artifacts(backtest, plan.simulation)
        LocalResearchStore(self.output_root).write(artifacts)
        self.evidence[key] = backtest
        return StudyCaseEvidence(
            case_id=case_id,
            phase=phase,
            fold_number=fold_number,
            terminal_status="completed",
            experiment_id=artifacts.experiment_id,
            evidence_sha256=artifacts.result_id,
        )


def _period_returns(evidence: BacktestEvidence) -> tuple[Decimal, ...]:
    previous = evidence.experiment_manifest.initial_cash
    values: list[Decimal] = []
    for snapshot in evidence.account_series:
        values.append(snapshot.marked_equity / previous - _ONE)
        previous = snapshot.marked_equity
    return tuple(values)


def _positive_profit(evidence: BacktestEvidence) -> Decimal:
    return sum(
        (trade.realized_pnl for trade in completed_trades(evidence) if trade.realized_pnl > 0),
        _ZERO,
    )


def _largest_profit_fraction(evidence: BacktestEvidence) -> Decimal | None:
    profits = tuple(
        trade.realized_pnl for trade in completed_trades(evidence) if trade.realized_pnl > 0
    )
    total = sum(profits, _ZERO)
    return None if total == 0 else max(profits) / total


def _regime_metrics(
    evidence: BacktestEvidence,
    bundle: PredictionBundle,
) -> tuple[RegimeMetrics, ...]:
    state_by_index = {item.candle_index: item.regime.state for item in bundle.predictions}
    counts = {state: 0 for state in RegimeState}
    exposed = {state: 0 for state in RegimeState}
    returns = {state: _ZERO for state in RegimeState}
    drawdowns = {state: _ZERO for state in RegimeState}
    trades = {state: 0 for state in RegimeState}
    previous = evidence.experiment_manifest.initial_cash
    for index, snapshot in enumerate(evidence.account_series):
        state = state_by_index.get(index, RegimeState.INDETERMINATE)
        counts[state] += 1
        exposed[state] += int(snapshot.position_quantity > 0)
        returns[state] += (
            snapshot.marked_equity - previous
        ) / evidence.experiment_manifest.initial_cash
        drawdowns[state] = max(drawdowns[state], snapshot.drawdown)
        previous = snapshot.marked_equity
    for trade in completed_trades(evidence):
        state = state_by_index.get(trade.exit_candle_index, RegimeState.INDETERMINATE)
        trades[state] += 1
    return tuple(
        RegimeMetrics(
            state=state,
            period_count=counts[state],
            net_return=returns[state],
            maximum_drawdown=drawdowns[state],
            exposure_fraction=(
                _ZERO if counts[state] == 0 else Decimal(exposed[state]) / Decimal(counts[state])
            ),
            completed_trade_count=trades[state],
        )
        for state in RegimeState
    )


def build_promotion_report(
    executor: StudyExecutor,
    bundles: dict[tuple[StudyPhase, int | None], PredictionBundle],
    history_requirement_met: bool,
) -> tuple[PromotionReport, BootstrapResult]:
    """Evaluate all predeclared promotion gates from completed study evidence."""

    folds: list[FoldEvaluation] = []
    development_keys = sorted(
        (key for key in bundles if key[0] is StudyPhase.DEVELOPMENT),
        key=lambda item: cast(int, item[1]),
    )
    for phase, fold_number in development_keys:
        candidate = executor.evidence[(phase, fold_number, "candidate.multi_model.v0_1")]
        candidate_metrics = calculate_metrics(candidate)
        baseline_metrics = tuple(
            calculate_metrics(executor.evidence[(phase, fold_number, case_id)])
            for case_id in (
                "buy_hold.v1",
                "ema_20_50.v1",
                "donchian_20_10.v1",
                "mean_reversion_z24.v1",
            )
        )
        defined = tuple(
            metric.return_to_drawdown
            for metric in baseline_metrics
            if metric.return_to_drawdown is not None
        )
        folds.append(
            FoldEvaluation(
                candidate_net_return=candidate_metrics.net_return,
                candidate_return_to_drawdown=candidate_metrics.return_to_drawdown,
                strongest_active_baseline_return_to_drawdown=max(defined) if defined else None,
                positive_profit=_positive_profit(candidate),
                completed_trades=candidate_metrics.trade_count,
            )
        )

    final_key = (StudyPhase.FINAL, None)
    candidate = executor.evidence[(*final_key, "candidate.multi_model.v0_1")]
    candidate_metrics = calculate_metrics(candidate)
    buy_hold = calculate_metrics(executor.evidence[(*final_key, "buy_hold.v1")])
    simple_ids = (
        "buy_hold.v1",
        "ema_20_50.v1",
        "donchian_20_10.v1",
        "mean_reversion_z24.v1",
    )
    simple_metrics = tuple(
        calculate_metrics(executor.evidence[(*final_key, case_id)]) for case_id in simple_ids
    )
    specialist_metrics = tuple(
        calculate_metrics(executor.evidence[(*final_key, case_id)])
        for case_id in ("trend.specialist.v1", "mean_reversion.specialist.v1")
    )
    simple_rtd = tuple(
        item.return_to_drawdown for item in simple_metrics if item.return_to_drawdown is not None
    )
    specialist_rtd = tuple(
        item.return_to_drawdown
        for item in specialist_metrics
        if item.return_to_drawdown is not None
    )
    final = FinalEvaluation(
        candidate_net_return=candidate_metrics.net_return,
        candidate_maximum_drawdown=candidate_metrics.maximum_drawdown,
        buy_hold_maximum_drawdown=buy_hold.maximum_drawdown,
        candidate_return_to_drawdown=candidate_metrics.return_to_drawdown,
        strongest_active_simple_return_to_drawdown=max(simple_rtd) if simple_rtd else None,
        strongest_specialist_return_to_drawdown=max(specialist_rtd) if specialist_rtd else None,
        strongest_active_simple_net_return=max(item.net_return for item in simple_metrics),
        completed_trades=candidate_metrics.trade_count,
        largest_positive_trade_fraction=_largest_profit_fraction(candidate),
        aggregate_positive_profit=_positive_profit(candidate),
        regime_metrics=_regime_metrics(candidate, bundles[final_key]),
    )
    cost_1_5 = calculate_metrics(executor.evidence[(*final_key, "cost.1_5x")])
    cost_2 = calculate_metrics(executor.evidence[(*final_key, "cost.2x")])
    neighbors = tuple(
        NeighborEvaluation(
            net_return=calculate_metrics(executor.evidence[(*final_key, case_id)]).net_return,
            maximum_drawdown=calculate_metrics(
                executor.evidence[(*final_key, case_id)]
            ).maximum_drawdown,
        )
        for case_id in REQUIRED_FINAL_CASE_IDS
        if case_id.startswith("sensitivity.")
    )
    strongest_baseline = max(
        simple_metrics,
        key=lambda item: item.return_to_drawdown or Decimal("-999999"),
    )
    strongest_case = simple_ids[simple_metrics.index(strongest_baseline)]
    bootstrap = deterministic_moving_block_bootstrap(
        _period_returns(candidate),
        _period_returns(executor.evidence[(*final_key, strongest_case)]),
        block_length=min(42, len(candidate.account_series)),
    )
    delayed = calculate_metrics(executor.evidence[(*final_key, "control.delayed_features.final")])
    promotion_evidence = PromotionEvidence(
        development_folds=tuple(folds),
        final=final,
        cost_1_5x=CostStressEvaluation(
            multiplier=Decimal("1.5"),
            net_return=cost_1_5.net_return,
            maximum_drawdown=cost_1_5.maximum_drawdown,
        ),
        cost_2x=CostStressEvaluation(
            multiplier=Decimal("2"),
            net_return=cost_2.net_return,
            maximum_drawdown=cost_2.maximum_drawdown,
        ),
        neighbors=neighbors,
        bootstrap=bootstrap,
        shuffled_labels_economic_gates_passed=False,
        delayed_feature_return_to_drawdown=delayed.return_to_drawdown,
        no_disagreement_component_value=False,
        no_volume_component_value=False,
        no_protection_component_value=False,
    )
    report = evaluate_promotion(promotion_evidence)
    if not history_requirement_met:
        report = PromotionReport(
            classification=PromotionClassification.INCONCLUSIVE,
            gates=report.gates,
        )
    return report, bootstrap


def _mapping_bytes(raw: bytes) -> dict[str, object]:
    loaded: object = json.loads(raw)
    if not isinstance(loaded, dict):
        raise StudyArtifactError("internal canonical mapping is invalid")
    return cast(dict[str, object], loaded)


def bundle_payloads(
    bundles: Mapping[tuple[StudyPhase, int | None], PredictionBundle],
) -> tuple[
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
]:
    """Serialize model, calibration, prediction, and regime study evidence."""

    models: list[dict[str, object]] = []
    calibration: list[dict[str, object]] = []
    predictions: list[dict[str, object]] = []
    regimes: list[dict[str, object]] = []
    ordered = sorted(bundles.items(), key=lambda item: (item[0][0].value, item[0][1] or 9999))
    for (phase, fold_number), bundle in ordered:
        for specialist, model in (
            ("trend", bundle.trend_model),
            ("mean_reversion", bundle.mean_reversion_model),
        ):
            models.append(
                {
                    "phase": phase.value,
                    "fold_number": fold_number,
                    "specialist": specialist,
                    "artifact": _mapping_bytes(serialize_model_artifact(model)),
                }
            )
        for specialist, platt, return_map in (
            ("trend", bundle.trend_platt, bundle.trend_return_map),
            ("mean_reversion", bundle.mean_reversion_platt, bundle.mean_reversion_return_map),
        ):
            calibration.append(
                {
                    "phase": phase.value,
                    "fold_number": fold_number,
                    "specialist": specialist,
                    "platt": _mapping_bytes(serialize_platt_artifact(platt)),
                    "expected_return": asdict(return_map),
                }
            )
        for item in bundle.predictions:
            predictions.append(
                {
                    "phase": phase.value,
                    "fold_number": fold_number,
                    "candle_index": item.candle_index,
                    "trend_raw_hex": float(item.trend_raw).hex(),
                    "mean_reversion_raw_hex": float(item.mean_reversion_raw).hex(),
                    "trend_probability": item.trend_probability,
                    "mean_reversion_probability": item.mean_reversion_probability,
                    "trend_expected_return": item.trend_expected_return,
                    "mean_reversion_expected_return": item.mean_reversion_expected_return,
                }
            )
            regimes.append(
                {
                    "phase": phase.value,
                    "fold_number": fold_number,
                    **asdict(item.regime),
                }
            )
    return models, calibration, predictions, regimes


__all__ = [
    "CasePlan",
    "StudyExecutor",
    "build_promotion_report",
    "bundle_payloads",
]
