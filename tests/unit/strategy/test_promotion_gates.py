"""Tests for exact Candidate v0.1 promotion-gate classification."""

from dataclasses import replace
from decimal import Decimal

from gemini_trading.strategy.contracts import RegimeState
from gemini_trading.strategy.evaluation import (
    MANDATORY_GATE_IDS,
    BootstrapResult,
    CostStressEvaluation,
    FinalEvaluation,
    FoldEvaluation,
    NeighborEvaluation,
    PromotionClassification,
    PromotionEvidence,
    RegimeMetrics,
    evaluate_promotion,
)


def _passing_bootstrap() -> BootstrapResult:
    return BootstrapResult(
        seed=1788,
        replicate_count=1000,
        block_length=42,
        sampled_start_matrix_sha256="a" * 64,
        net_return_difference_median=Decimal("0.01"),
        net_return_difference_p05=Decimal("-0.01"),
        net_return_difference_p95=Decimal("0.03"),
        drawdown_difference_median=Decimal("-0.02"),
        drawdown_difference_p05=Decimal("-0.04"),
        drawdown_difference_p95=Decimal("0.01"),
        return_to_drawdown_difference_median=Decimal("0.08"),
        return_to_drawdown_difference_p05=Decimal("-0.01"),
        return_to_drawdown_difference_p95=Decimal("0.15"),
    )


def _passing_evidence() -> PromotionEvidence:
    folds = tuple(
        FoldEvaluation(
            candidate_net_return=Decimal("0.02") if index < 3 else Decimal("-0.005"),
            candidate_return_to_drawdown=Decimal("0.70") if index < 3 else Decimal("0.40"),
            strongest_active_baseline_return_to_drawdown=Decimal("0.60"),
            positive_profit=Decimal("10"),
            completed_trades=12,
        )
        for index in range(5)
    )
    regimes = (
        RegimeMetrics(RegimeState.TRENDING, 20, Decimal("0.03"), Decimal("0.10"), Decimal("0.7"), 12),
        RegimeMetrics(RegimeState.RANGING, 20, Decimal("0.02"), Decimal("0.08"), Decimal("0.4"), 10),
        RegimeMetrics(RegimeState.INDETERMINATE, 10, Decimal("0"), Decimal("0.03"), Decimal("0.1"), 4),
        RegimeMetrics(RegimeState.UNSTABLE, 10, Decimal("-0.005"), Decimal("0.04"), Decimal("0.1"), 4),
    )
    final = FinalEvaluation(
        candidate_net_return=Decimal("0.05"),
        candidate_maximum_drawdown=Decimal("0.20"),
        buy_hold_maximum_drawdown=Decimal("0.30"),
        candidate_return_to_drawdown=Decimal("0.60"),
        strongest_active_simple_return_to_drawdown=Decimal("0.54"),
        strongest_specialist_return_to_drawdown=Decimal("0.57"),
        strongest_active_simple_net_return=Decimal("0.06"),
        completed_trades=30,
        largest_positive_trade_fraction=Decimal("0.20"),
        aggregate_positive_profit=Decimal("0.05"),
        regime_metrics=regimes,
    )
    neighbors = tuple(
        NeighborEvaluation(
            net_return=Decimal("0.01") if index < 7 else Decimal("-0.002"),
            maximum_drawdown=Decimal("0.25"),
        )
        for index in range(10)
    )
    return PromotionEvidence(
        development_folds=folds,
        final=final,
        cost_1_5x=CostStressEvaluation(Decimal("1.5"), Decimal("0.02"), Decimal("0.24")),
        cost_2x=CostStressEvaluation(Decimal("2"), Decimal("-0.02"), Decimal("0.28")),
        neighbors=neighbors,
        bootstrap=_passing_bootstrap(),
        shuffled_labels_economic_gates_passed=False,
        delayed_feature_return_to_drawdown=Decimal("0.61"),
        no_disagreement_component_value=True,
        no_volume_component_value=True,
        no_protection_component_value=True,
    )


def test_every_mandatory_gate_passes_only_for_complete_passing_evidence() -> None:
    report = evaluate_promotion(_passing_evidence())

    assert report.classification is PromotionClassification.PASS
    assert tuple(item.gate_id for item in report.gates) == MANDATORY_GATE_IDS
    assert all(item.passed for item in report.gates)


def test_one_failed_mandatory_gate_rejects_the_candidate() -> None:
    evidence = _passing_evidence()
    rejected = replace(
        evidence,
        cost_2x=replace(evidence.cost_2x, net_return=Decimal("-0.06")),
    )

    report = evaluate_promotion(rejected)

    assert report.classification is PromotionClassification.REJECTED
    gate = next(item for item in report.gates if item.gate_id == "cost.double_return")
    assert gate.passed is False


def test_missing_required_comparator_is_inconclusive_not_pass() -> None:
    evidence = _passing_evidence()
    inconclusive = replace(
        evidence,
        final=replace(evidence.final, strongest_active_simple_return_to_drawdown=None),
    )

    report = evaluate_promotion(inconclusive)

    assert report.classification is PromotionClassification.INCONCLUSIVE
    gate = next(item for item in report.gates if item.gate_id == "final.simple_baseline_rtd")
    assert gate.passed is False
    assert "missing" in gate.reason
