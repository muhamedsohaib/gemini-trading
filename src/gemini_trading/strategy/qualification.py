"""Strict development-only qualification gates for Candidate v0.2."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from gemini_trading.strategy.contracts import GateResult
from gemini_trading.strategy.determinism import TrendDeterminismReceipt
from gemini_trading.strategy.evaluation import (
    BootstrapResult,
    CostStressEvaluation,
    FoldEvaluation,
    NeighborEvaluation,
    cost_returns_are_monotonic,
)

_ZERO = Decimal("0")
_ONE = Decimal("1")

QUALIFICATION_GATE_IDS = (
    "integrity.verified",
    "convergence.trend_determinism",
    "calibration.complete",
    "development.fold_count",
    "development.positive_return_folds",
    "development.baseline_rtd_folds",
    "development.profit_concentration",
    "development.trade_count",
    "control.shuffled_labels",
    "control.delayed_features",
    "control.no_disagreement",
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


class QualificationClassification(StrEnum):
    """Closed Candidate v0.2 pre-final qualification classifications."""

    QUALIFIED = "QUALIFIED"
    REJECTED = "REJECTED"
    INCONCLUSIVE = "INCONCLUSIVE"


@dataclass(frozen=True, slots=True)
class QualificationEvidence:
    """Complete development-only evidence consumed by the v0.2 qualification gates."""

    integrity_verified: bool | None
    trend_determinism: tuple[TrendDeterminismReceipt, ...] | None
    calibration_complete: bool | None
    development_folds: tuple[FoldEvaluation, ...]
    shuffled_labels_safe: bool | None
    delayed_features_component_supported: bool | None
    disagreement_component_supported: bool | None
    volume_component_supported: bool | None
    protection_component_supported: bool | None
    primary_aggregate_net_return: Decimal | None
    primary_aggregate_max_drawdown: Decimal | None
    cost_1_5x: CostStressEvaluation | None
    cost_2x: CostStressEvaluation | None
    neighbors: tuple[NeighborEvaluation, ...] | None
    bootstrap: BootstrapResult | None
    replay_verified: bool | None
    independent_verified: bool | None


@dataclass(frozen=True, slots=True)
class QualificationReport:
    """Every mandatory v0.2 pre-final gate plus one fail-closed classification."""

    classification: QualificationClassification
    gates: tuple[GateResult, ...]


def _gate(
    gate_id: str,
    passed: bool,
    observed: object,
    required: str,
    reason: str,
) -> tuple[GateResult, bool]:
    return (
        GateResult(
            gate_id=gate_id,
            passed=passed,
            observed=str(observed),
            required=required,
            reason=reason,
        ),
        False,
    )


def _missing(gate_id: str, required: str, reason: str) -> tuple[GateResult, bool]:
    return (
        GateResult(
            gate_id=gate_id,
            passed=False,
            observed="missing",
            required=required,
            reason=f"missing {reason}",
        ),
        True,
    )


def _optional_boolean(
    gate_id: str,
    value: bool | None,
    *,
    reason: str,
) -> tuple[GateResult, bool]:
    if value is None:
        return _missing(gate_id, "true", reason)
    return _gate(gate_id, value, value, "true", f"{reason} evaluated")


def _median(values: tuple[Decimal, ...]) -> Decimal:
    ordered = tuple(sorted(values))
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / Decimal("2")


def evaluate_development_qualification(evidence: QualificationEvidence) -> QualificationReport:
    """Apply every preregistered Candidate v0.2 development gate and fail closed."""

    outcomes: list[tuple[GateResult, bool]] = []
    outcomes.append(
        _optional_boolean(
            "integrity.verified",
            evidence.integrity_verified,
            reason="development integrity verification",
        )
    )

    receipts = evidence.trend_determinism
    if receipts is None:
        outcomes.append(
            _missing(
                "convergence.trend_determinism",
                "12 exact deterministic fold receipts",
                "trend determinism evidence",
            )
        )
    else:
        fold_numbers = tuple(item.fold_number for item in receipts)
        deterministic = (
            fold_numbers == tuple(range(1, 13))
            and all(item.exact_match and item.iteration_count < 50_000 for item in receipts)
        )
        outcomes.append(
            _gate(
                "convergence.trend_determinism",
                deterministic,
                f"folds={fold_numbers}",
                "folds=1..12; exact; iterations<50000",
                "trend repeated-fit determinism evaluated",
            )
        )
    outcomes.append(
        _optional_boolean(
            "calibration.complete",
            evidence.calibration_complete,
            reason="calibration minimums and artifacts",
        )
    )

    folds = evidence.development_folds
    outcomes.append(
        _gate(
            "development.fold_count",
            len(folds) == 12,
            len(folds),
            "=12",
            "complete fixed development-fold count evaluated",
        )
    )
    positive_folds = sum(item.candidate_net_return > _ZERO for item in folds)
    positive_fraction = _ZERO if not folds else Decimal(positive_folds) / Decimal(len(folds))
    outcomes.append(
        _gate(
            "development.positive_return_folds",
            positive_fraction >= Decimal("0.60"),
            positive_fraction,
            ">=0.60",
            "positive-return development-fold fraction evaluated",
        )
    )
    if any(
        item.candidate_return_to_drawdown is None
        or item.strongest_active_baseline_return_to_drawdown is None
        for item in folds
    ):
        outcomes.append(
            _missing(
                "development.baseline_rtd_folds",
                ">=0.60",
                "development return-to-drawdown comparator",
            )
        )
    else:
        beat_count = sum(
            item.candidate_return_to_drawdown > item.strongest_active_baseline_return_to_drawdown
            for item in folds
            if item.candidate_return_to_drawdown is not None
            and item.strongest_active_baseline_return_to_drawdown is not None
        )
        beat_fraction = _ZERO if not folds else Decimal(beat_count) / Decimal(len(folds))
        outcomes.append(
            _gate(
                "development.baseline_rtd_folds",
                beat_fraction >= Decimal("0.60"),
                beat_fraction,
                ">=0.60",
                "development baseline return-to-drawdown wins evaluated",
            )
        )
    total_positive_profit = sum((max(item.positive_profit, _ZERO) for item in folds), _ZERO)
    concentration = (
        _ONE
        if total_positive_profit == _ZERO
        else max((item.positive_profit for item in folds), default=_ZERO) / total_positive_profit
    )
    outcomes.append(
        _gate(
            "development.profit_concentration",
            concentration <= Decimal("0.50"),
            concentration,
            "<=0.50",
            "development profit concentration evaluated",
        )
    )
    development_trades = sum(item.completed_trades for item in folds)
    outcomes.append(
        _gate(
            "development.trade_count",
            development_trades >= 60,
            development_trades,
            ">=60",
            "development completed-trade count evaluated",
        )
    )

    outcomes.extend(
        (
            _optional_boolean(
                "control.shuffled_labels",
                evidence.shuffled_labels_safe,
                reason="shuffled-label negative control",
            ),
            _optional_boolean(
                "control.delayed_features",
                evidence.delayed_features_component_supported,
                reason="delayed-feature control",
            ),
            _optional_boolean(
                "control.no_disagreement",
                evidence.disagreement_component_supported,
                reason="disagreement-abstention component value",
            ),
            _optional_boolean(
                "control.no_volume",
                evidence.volume_component_supported,
                reason="volume component value",
            ),
            _optional_boolean(
                "control.no_protection",
                evidence.protection_component_supported,
                reason="protection component value",
            ),
        )
    )

    cost_1_5x = evidence.cost_1_5x
    if cost_1_5x is None:
        outcomes.extend(
            (
                _missing("cost.one_half_return", ">0", "1.5x-cost return"),
                _missing("cost.one_half_drawdown", "<=0.275", "1.5x-cost drawdown"),
            )
        )
    else:
        outcomes.extend(
            (
                _gate(
                    "cost.one_half_return",
                    cost_1_5x.net_return > _ZERO,
                    cost_1_5x.net_return,
                    ">0",
                    "1.5x-cost aggregate development return evaluated",
                ),
                _gate(
                    "cost.one_half_drawdown",
                    cost_1_5x.maximum_drawdown <= Decimal("0.275"),
                    cost_1_5x.maximum_drawdown,
                    "<=0.275",
                    "1.5x-cost aggregate development drawdown evaluated",
                ),
            )
        )
    cost_2x = evidence.cost_2x
    if cost_2x is None:
        outcomes.extend(
            (
                _missing("cost.double_return", ">=-0.05", "2x-cost return"),
                _missing("cost.double_drawdown", "<=0.30", "2x-cost drawdown"),
            )
        )
    else:
        outcomes.extend(
            (
                _gate(
                    "cost.double_return",
                    cost_2x.net_return >= Decimal("-0.05"),
                    cost_2x.net_return,
                    ">=-0.05",
                    "2x-cost aggregate development return evaluated",
                ),
                _gate(
                    "cost.double_drawdown",
                    cost_2x.maximum_drawdown <= Decimal("0.30"),
                    cost_2x.maximum_drawdown,
                    "<=0.30",
                    "2x-cost aggregate development drawdown evaluated",
                ),
            )
        )
    if (
        evidence.primary_aggregate_net_return is None
        or cost_1_5x is None
        or cost_2x is None
    ):
        outcomes.append(
            _missing(
                "cost.monotonicity",
                "base>=1.5x>=2x",
                "aggregate development cost monotonicity",
            )
        )
    else:
        outcomes.append(
            _gate(
                "cost.monotonicity",
                cost_returns_are_monotonic(
                    evidence.primary_aggregate_net_return,
                    cost_1_5x.net_return,
                    cost_2x.net_return,
                ),
                (
                    f"{evidence.primary_aggregate_net_return},"
                    f"{cost_1_5x.net_return},{cost_2x.net_return}"
                ),
                "base>=1.5x>=2x",
                "aggregate development cost monotonicity evaluated",
            )
        )

    neighbors = evidence.neighbors
    if neighbors is None:
        outcomes.extend(
            (
                _missing("sensitivity.positive_neighbors", ">=7/10", "sensitivity variants"),
                _missing("sensitivity.median_return", ">0", "sensitivity median return"),
                _missing("sensitivity.drawdown", "<=0.35", "sensitivity drawdown"),
                _missing(
                    "sensitivity.primary_stability",
                    "no >100% neighbor improvement when primary<=0.02",
                    "primary sensitivity stability",
                ),
            )
        )
    else:
        neighbor_returns = tuple(item.net_return for item in neighbors)
        positive_neighbors = sum(value > _ZERO for value in neighbor_returns)
        neighbor_median = _ZERO if not neighbor_returns else _median(neighbor_returns)
        neighbor_max_drawdown = max(
            (item.maximum_drawdown for item in neighbors),
            default=Decimal("Infinity"),
        )
        outcomes.extend(
            (
                _gate(
                    "sensitivity.positive_neighbors",
                    len(neighbors) == 10 and positive_neighbors >= 7,
                    positive_neighbors,
                    ">=7/10 with exactly 10 variants",
                    "positive sensitivity variants evaluated",
                ),
                _gate(
                    "sensitivity.median_return",
                    neighbor_median > _ZERO,
                    neighbor_median,
                    ">0",
                    "sensitivity median aggregate return evaluated",
                ),
                _gate(
                    "sensitivity.drawdown",
                    neighbor_max_drawdown <= Decimal("0.35"),
                    neighbor_max_drawdown,
                    "<=0.35",
                    "sensitivity maximum aggregate drawdown evaluated",
                ),
            )
        )
        if evidence.primary_aggregate_net_return is None:
            outcomes.append(
                _missing(
                    "sensitivity.primary_stability",
                    "no >100% neighbor improvement when primary<=0.02",
                    "primary aggregate development return",
                )
            )
        else:
            stable = True
            if evidence.primary_aggregate_net_return <= Decimal("0.02"):
                stable = all(
                    item.net_return <= evidence.primary_aggregate_net_return * Decimal("2")
                    for item in neighbors
                )
            outcomes.append(
                _gate(
                    "sensitivity.primary_stability",
                    stable,
                    evidence.primary_aggregate_net_return,
                    "no >100% neighbor improvement when primary<=0.02",
                    "primary development sensitivity stability evaluated",
                )
            )

    bootstrap = evidence.bootstrap
    if bootstrap is None:
        outcomes.extend(
            (
                _missing(
                    "uncertainty.bootstrap_median",
                    ">0",
                    "development bootstrap median return difference",
                ),
                _missing(
                    "uncertainty.bootstrap_lower_bound",
                    ">-0.02",
                    "development bootstrap lower bound",
                ),
            )
        )
    else:
        outcomes.extend(
            (
                _gate(
                    "uncertainty.bootstrap_median",
                    bootstrap.net_return_difference_median > _ZERO,
                    bootstrap.net_return_difference_median,
                    ">0",
                    "development bootstrap median return difference evaluated",
                ),
                _gate(
                    "uncertainty.bootstrap_lower_bound",
                    bootstrap.net_return_difference_p05 > Decimal("-0.02"),
                    bootstrap.net_return_difference_p05,
                    ">-0.02",
                    "development bootstrap 90% lower bound evaluated",
                ),
            )
        )

    outcomes.extend(
        (
            _optional_boolean(
                "replay.verified",
                evidence.replay_verified,
                reason="provider-free qualification replay",
            ),
            _optional_boolean(
                "independent.verified",
                evidence.independent_verified,
                reason="independent qualification verification",
            ),
        )
    )

    gates = tuple(item for item, _ in outcomes)
    if tuple(item.gate_id for item in gates) != QUALIFICATION_GATE_IDS:
        raise RuntimeError("mandatory qualification gate order is incomplete")
    explicit_failure = any(not item.passed and not missing for item, missing in outcomes)
    missing_evidence = any(missing for _, missing in outcomes)
    classification = (
        QualificationClassification.REJECTED
        if explicit_failure
        else QualificationClassification.INCONCLUSIVE
        if missing_evidence
        else QualificationClassification.QUALIFIED
    )
    return QualificationReport(classification=classification, gates=gates)


__all__ = [
    "QUALIFICATION_GATE_IDS",
    "QualificationClassification",
    "QualificationEvidence",
    "QualificationReport",
    "evaluate_development_qualification",
]
