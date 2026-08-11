"""RED tests for Candidate v0.2 strict development qualification gates."""

from dataclasses import replace
from decimal import Decimal

from gemini_trading.strategy.determinism import TrendDeterminismReceipt
from gemini_trading.strategy.evaluation import (
    BootstrapResult,
    CostStressEvaluation,
    FoldEvaluation,
    NeighborEvaluation,
)
from gemini_trading.strategy.qualification import (
    QUALIFICATION_GATE_IDS,
    QualificationClassification,
    QualificationEvidence,
    evaluate_development_qualification,
)


def _receipt(fold_number: int) -> TrendDeterminismReceipt:
    digest = f"{fold_number:064x}"
    bundle_digest = f"{fold_number + 100:064x}"
    return TrendDeterminismReceipt(
        schema_version="candidate-v0.2-trend-determinism-v1",
        fold_number=fold_number,
        iteration_count=1000 + fold_number,
        first_model_sha256=digest,
        second_model_sha256=digest,
        first_bundle_sha256=bundle_digest,
        second_bundle_sha256=bundle_digest,
        exact_match=True,
    )


def _passing_evidence() -> QualificationEvidence:
    folds = tuple(
        FoldEvaluation(
            candidate_net_return=Decimal("0.02"),
            candidate_return_to_drawdown=Decimal("0.8"),
            strongest_active_baseline_return_to_drawdown=Decimal("0.5"),
            positive_profit=Decimal("1"),
            completed_trades=5,
        )
        for _ in range(12)
    )
    neighbors = tuple(
        NeighborEvaluation(net_return=Decimal("0.05"), maximum_drawdown=Decimal("0.15"))
        for _ in range(10)
    )
    bootstrap = BootstrapResult(
        seed=1788,
        replicate_count=1000,
        block_length=42,
        sampled_start_matrix_sha256="a" * 64,
        net_return_difference_median=Decimal("0.03"),
        net_return_difference_p05=Decimal("-0.01"),
        net_return_difference_p95=Decimal("0.08"),
        drawdown_difference_median=Decimal("-0.01"),
        drawdown_difference_p05=Decimal("-0.04"),
        drawdown_difference_p95=Decimal("0.02"),
        return_to_drawdown_difference_median=Decimal("0.2"),
        return_to_drawdown_difference_p05=Decimal("-0.01"),
        return_to_drawdown_difference_p95=Decimal("0.5"),
    )
    return QualificationEvidence(
        integrity_verified=True,
        trend_determinism=tuple(_receipt(number) for number in range(1, 13)),
        calibration_complete=True,
        development_folds=folds,
        shuffled_labels_safe=True,
        delayed_features_component_supported=True,
        disagreement_component_supported=True,
        volume_component_supported=True,
        protection_component_supported=True,
        primary_aggregate_net_return=Decimal("0.10"),
        primary_aggregate_max_drawdown=Decimal("0.15"),
        cost_1_5x=CostStressEvaluation(
            multiplier=Decimal("1.5"),
            net_return=Decimal("0.07"),
            maximum_drawdown=Decimal("0.18"),
        ),
        cost_2x=CostStressEvaluation(
            multiplier=Decimal("2"),
            net_return=Decimal("0.03"),
            maximum_drawdown=Decimal("0.22"),
        ),
        neighbors=neighbors,
        bootstrap=bootstrap,
        replay_verified=True,
        independent_verified=True,
    )


def test_complete_passing_development_evidence_is_qualified() -> None:
    report = evaluate_development_qualification(_passing_evidence())

    assert report.classification is QualificationClassification.QUALIFIED
    assert tuple(gate.gate_id for gate in report.gates) == QUALIFICATION_GATE_IDS
    assert all(gate.passed for gate in report.gates)


def test_explicit_mandatory_failure_is_rejected() -> None:
    evidence = replace(_passing_evidence(), integrity_verified=False)

    report = evaluate_development_qualification(evidence)

    assert report.classification is QualificationClassification.REJECTED


def test_missing_evidence_without_explicit_failure_is_inconclusive() -> None:
    evidence = replace(_passing_evidence(), bootstrap=None)

    report = evaluate_development_qualification(evidence)

    assert report.classification is QualificationClassification.INCONCLUSIVE
