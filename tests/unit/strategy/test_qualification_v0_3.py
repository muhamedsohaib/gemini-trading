"""Candidate v0.3 strict development qualification gate tests."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from gemini_trading.strategy.contracts import SpecialistKind
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
)
from gemini_trading.strategy.qualification_v0_3 import (
    V03_QUALIFICATION_GATE_IDS,
    SelectivityReplayReceipt,
    V03QualificationEvidence,
    evaluate_v0_3_development_qualification,
)

_EXPECTED_GATE_IDS = (
    "integrity.verified",
    "convergence.trend_determinism",
    "calibration.complete",
    "selectivity.replay",
    "development.fold_count",
    "development.positive_return_folds",
    "development.baseline_rtd_folds",
    "development.profit_concentration",
    "development.trade_count",
    "control.shuffled_labels",
    "control.delayed_features",
    "control.no_percentile_selectivity",
    "control.no_volume",
    "control.no_protection",
    "cost.one_half_return",
    "cost.one_half_drawdown",
    "cost.double_return",
    "cost.double_drawdown",
    "cost.monotonicity",
    "sensitivity.positive_neighbors",
    "sensitivity.median_return",
    "sensitivity.drawdown",
    "sensitivity.primary_stability",
    "uncertainty.bootstrap_median",
    "uncertainty.bootstrap_lower_bound",
    "replay.verified",
    "independent.verified",
)


def _determinism_receipt(fold_number: int) -> TrendDeterminismReceipt:
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


def _selectivity_receipts() -> tuple[SelectivityReplayReceipt, ...]:
    return tuple(
        SelectivityReplayReceipt(
            fold_number=fold_number,
            specialist=specialist,
            percentile=percentile,
            eligible_rows_match=True,
            score_vector_match=True,
            raw_quantile_match=True,
            effective_threshold_match=True,
            canonical_bytes_match=True,
        )
        for fold_number in range(1, 13)
        for specialist in (SpecialistKind.TREND, SpecialistKind.MEAN_REVERSION)
        for percentile in (Decimal("0.70"), Decimal("0.75"), Decimal("0.80"))
    )


def _passing_evidence() -> V03QualificationEvidence:
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
    return V03QualificationEvidence(
        integrity_verified=True,
        trend_determinism=tuple(_determinism_receipt(number) for number in range(1, 13)),
        calibration_complete=True,
        selectivity_replay=_selectivity_receipts(),
        development_folds=folds,
        shuffled_labels_safe=True,
        delayed_features_component_supported=True,
        primary_return_to_drawdown=Decimal("0.80"),
        primary_aggregate_net_return=Decimal("0.10"),
        primary_aggregate_max_drawdown=Decimal("0.15"),
        no_percentile_selectivity_return_to_drawdown=Decimal("0.75"),
        no_percentile_selectivity_max_drawdown=Decimal("0.15"),
        volume_component_supported=True,
        protection_component_supported=True,
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


def test_complete_passing_v0_3_evidence_is_qualified_in_fixed_gate_order() -> None:
    report = evaluate_v0_3_development_qualification(_passing_evidence())

    assert V03_QUALIFICATION_GATE_IDS == _EXPECTED_GATE_IDS
    assert tuple(gate.gate_id for gate in report.gates) == _EXPECTED_GATE_IDS
    assert report.classification is QualificationClassification.QUALIFIED
    assert all(gate.passed for gate in report.gates)


def test_explicit_v0_3_mandatory_failure_is_rejected() -> None:
    report = evaluate_v0_3_development_qualification(
        replace(_passing_evidence(), integrity_verified=False)
    )
    assert report.classification is QualificationClassification.REJECTED


def test_missing_v0_3_evidence_without_explicit_failure_is_inconclusive() -> None:
    report = evaluate_v0_3_development_qualification(
        replace(_passing_evidence(), bootstrap=None)
    )
    assert report.classification is QualificationClassification.INCONCLUSIVE


def test_no_percentile_selectivity_gate_rejects_ten_percent_rtd_improvement() -> None:
    evidence = replace(
        _passing_evidence(),
        no_percentile_selectivity_return_to_drawdown=Decimal("0.88"),
        no_percentile_selectivity_max_drawdown=Decimal("0.15"),
    )
    report = evaluate_v0_3_development_qualification(evidence)
    gate = next(
        item for item in report.gates if item.gate_id == "control.no_percentile_selectivity"
    )

    assert gate.passed is False
    assert report.classification is QualificationClassification.REJECTED


def test_no_percentile_selectivity_gate_accepts_sub_ten_percent_improvement() -> None:
    evidence = replace(
        _passing_evidence(),
        no_percentile_selectivity_return_to_drawdown=Decimal("0.879"),
        no_percentile_selectivity_max_drawdown=Decimal("0.15"),
    )
    report = evaluate_v0_3_development_qualification(evidence)
    gate = next(
        item for item in report.gates if item.gate_id == "control.no_percentile_selectivity"
    )
    assert gate.passed is True


def test_undefined_no_percentile_selectivity_ratio_fails_closed() -> None:
    evidence = replace(
        _passing_evidence(),
        no_percentile_selectivity_return_to_drawdown=None,
    )
    report = evaluate_v0_3_development_qualification(evidence)
    gate = next(
        item for item in report.gates if item.gate_id == "control.no_percentile_selectivity"
    )

    assert gate.passed is False
    assert report.classification is QualificationClassification.REJECTED


def test_q75_selectivity_replay_mismatch_is_rejected() -> None:
    receipts = list(_selectivity_receipts())
    q75_index = next(
        index
        for index, item in enumerate(receipts)
        if item.fold_number == 1
        and item.specialist is SpecialistKind.TREND
        and item.percentile == Decimal("0.75")
    )
    receipts[q75_index] = replace(receipts[q75_index], canonical_bytes_match=False)

    report = evaluate_v0_3_development_qualification(
        replace(_passing_evidence(), selectivity_replay=tuple(receipts))
    )
    gate = next(item for item in report.gates if item.gate_id == "selectivity.replay")

    assert gate.passed is False
    assert report.classification is QualificationClassification.REJECTED


def test_missing_q70_or_q80_artifact_makes_sensitivity_evidence_inconclusive() -> None:
    receipts = tuple(
        item
        for item in _selectivity_receipts()
        if not (
            item.fold_number == 1
            and item.specialist is SpecialistKind.TREND
            and item.percentile == Decimal("0.70")
        )
    )
    report = evaluate_v0_3_development_qualification(
        replace(_passing_evidence(), selectivity_replay=receipts)
    )

    assert next(item for item in report.gates if item.gate_id == "selectivity.replay").passed
    sensitivity_gates = tuple(
        item for item in report.gates if item.gate_id.startswith("sensitivity.")
    )
    assert sensitivity_gates
    assert all(item.passed is False and item.observed == "missing" for item in sensitivity_gates)
    assert report.classification is QualificationClassification.INCONCLUSIVE


def test_v0_2_gate_registry_remains_unchanged() -> None:
    assert "control.no_disagreement" in QUALIFICATION_GATE_IDS
    assert "control.no_percentile_selectivity" not in QUALIFICATION_GATE_IDS
    assert "selectivity.replay" not in QUALIFICATION_GATE_IDS
