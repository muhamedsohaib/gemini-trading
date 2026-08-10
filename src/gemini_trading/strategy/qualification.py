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


type GateOutcome = tuple[GateResult, bool]


def _gate(
    gate_id: str,
    passed: bool,
    observed: object,
    required: str,
    reason: str,
) -> GateOutcome:
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


def _missing(gate_id: str, required: str, reason: str) -> GateOutcome:
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


def _boolean(gate_id: str, value: bool | None, reason: str) -> GateOutcome:
    if value is None:
        return _missing(gate_id, "true", reason)
    return _gate(gate_id, value, value, "true", f"{reason} evaluated")


def _median(values: tuple[Decimal, ...]) -> Decimal:
    ordered = tuple(sorted(values))
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / Decimal("2")


def _trend_determinism(
    receipts: tuple[TrendDeterminismReceipt, ...] | None,
) -> GateOutcome:
    if receipts is None:
        return _missing(
            "convergence.trend_determinism",
            "12 exact deterministic fold receipts",
            "trend determinism evidence",
        )
    fold_numbers = tuple(item.fold_number for item in receipts)
    passed = fold_numbers == tuple(range(1, 13)) and all(
        item.exact_match and item.iteration_count < 50_000 for item in receipts
    )
    return _gate(
        "convergence.trend_determinism",
        passed,
        f"folds={fold_numbers}",
        "folds=1..12; exact; iterations<50000",
        "trend repeated-fit determinism evaluated",
    )


def _development_outcomes(folds: tuple[FoldEvaluation, ...]) -> list[GateOutcome]:
    outcomes = [
        _gate(
            "development.fold_count",
            len(folds) == 12,
            len(folds),
            "=12",
            "complete fixed development-fold count evaluated",
        )
    ]
    positive_count = sum(item.candidate_net_return > _ZERO for item in folds)
    positive_fraction = _ZERO if not folds else Decimal(positive_count) / Decimal(len(folds))
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
    total_profit = sum((max(item.positive_profit, _ZERO) for item in folds), _ZERO)
    concentration = (
        _ONE
        if total_profit == _ZERO
        else max((item.positive_profit for item in folds), default=_ZERO) / total_profit
    )
    outcomes.extend(
        (
            _gate(
                "development.profit_concentration",
                concentration <= Decimal("0.50"),
                concentration,
                "<=0.50",
                "development profit concentration evaluated",
            ),
            _gate(
                "development.trade_count",
                sum(item.completed_trades for item in folds) >= 60,
                sum(item.completed_trades for item in folds),
                ">=60",
                "development completed-trade count evaluated",
            ),
        )
    )
    return outcomes


def _cost_outcomes(evidence: QualificationEvidence) -> list[GateOutcome]:
    one_half = evidence.cost_1_5x
    double = evidence.cost_2x
    outcomes: list[GateOutcome] = []
    if one_half is None:
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
                    one_half.net_return > _ZERO,
                    one_half.net_return,
                    ">0",
                    "1.5x-cost aggregate development return evaluated",
                ),
                _gate(
                    "cost.one_half_drawdown",
                    one_half.maximum_drawdown <= Decimal("0.275"),
                    one_half.maximum_drawdown,
                    "<=0.275",
                    "1.5x-cost aggregate development drawdown evaluated",
                ),
            )
        )
    if double is None:
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
                    double.net_return >= Decimal("-0.05"),
                    double.net_return,
                    ">=-0.05",
                    "2x-cost aggregate development return evaluated",
                ),
                _gate(
                    "cost.double_drawdown",
                    double.maximum_drawdown <= Decimal("0.30"),
                    double.maximum_drawdown,
                    "<=0.30",
                    "2x-cost aggregate development drawdown evaluated",
                ),
            )
        )
    primary = evidence.primary_aggregate_net_return
    if primary is None or one_half is None or double is None:
        outcomes.append(
            _missing("cost.monotonicity", "base>=1.5x>=2x", "cost monotonicity")
        )
    else:
        outcomes.append(
            _gate(
                "cost.monotonicity",
                cost_returns_are_monotonic(primary, one_half.net_return, double.net_return),
                f"{primary},{one_half.net_return},{double.net_return}",
                "base>=1.5x>=2x",
                "aggregate development cost monotonicity evaluated",
            )
        )
    return outcomes


def _sensitivity_outcomes(evidence: QualificationEvidence) -> list[GateOutcome]:
    neighbors = evidence.neighbors
    if neighbors is None:
        return [
            _missing("sensitivity.positive_neighbors", ">=7/10", "sensitivity variants"),
            _missing("sensitivity.median_return", ">0", "sensitivity median return"),
            _missing("sensitivity.drawdown", "<=0.35", "sensitivity drawdown"),
            _missing(
                "sensitivity.primary_stability",
                "no >100% neighbor improvement when primary<=0.02",
                "primary sensitivity stability",
            ),
        ]
    returns = tuple(item.net_return for item in neighbors)
    positive_count = sum(value > _ZERO for value in returns)
    maximum_drawdown = max(
        (item.maximum_drawdown for item in neighbors),
        default=Decimal("Infinity"),
    )
    outcomes = [
        _gate(
            "sensitivity.positive_neighbors",
            len(neighbors) == 10 and positive_count >= 7,
            positive_count,
            ">=7/10 with exactly 10 variants",
            "positive sensitivity variants evaluated",
        ),
        _gate(
            "sensitivity.median_return",
            bool(returns) and _median(returns) > _ZERO,
            _ZERO if not returns else _median(returns),
            ">0",
            "sensitivity median aggregate return evaluated",
        ),
        _gate(
            "sensitivity.drawdown",
            maximum_drawdown <= Decimal("0.35"),
            maximum_drawdown,
            "<=0.35",
            "sensitivity maximum aggregate drawdown evaluated",
        ),
    ]
    primary = evidence.primary_aggregate_net_return
    if primary is None:
        outcomes.append(
            _missing(
                "sensitivity.primary_stability",
                "no >100% neighbor improvement when primary<=0.02",
                "primary aggregate development return",
            )
        )
    else:
        stable = primary > Decimal("0.02") or all(
            item.net_return <= primary * Decimal("2") for item in neighbors
        )
        outcomes.append(
            _gate(
                "sensitivity.primary_stability",
                stable,
                primary,
                "no >100% neighbor improvement when primary<=0.02",
                "primary development sensitivity stability evaluated",
            )
        )
    return outcomes


def _bootstrap_outcomes(bootstrap: BootstrapResult | None) -> list[GateOutcome]:
    if bootstrap is None:
        return [
            _missing("uncertainty.bootstrap_median", ">0", "bootstrap median"),
            _missing("uncertainty.bootstrap_lower_bound", ">-0.02", "bootstrap lower bound"),
        ]
    return [
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
    ]


def evaluate_development_qualification(evidence: QualificationEvidence) -> QualificationReport:
    """Apply every preregistered Candidate v0.2 development gate and fail closed."""

    outcomes: list[GateOutcome] = [
        _boolean("integrity.verified", evidence.integrity_verified, "integrity verification"),
        _trend_determinism(evidence.trend_determinism),
        _boolean("calibration.complete", evidence.calibration_complete, "calibration evidence"),
    ]
    outcomes.extend(_development_outcomes(evidence.development_folds))
    outcomes.extend(
        (
            _boolean(
                "control.shuffled_labels",
                evidence.shuffled_labels_safe,
                "shuffled-label negative control",
            ),
            _boolean(
                "control.delayed_features",
                evidence.delayed_features_component_supported,
                "delayed-feature control",
            ),
            _boolean(
                "control.no_disagreement",
                evidence.disagreement_component_supported,
                "disagreement-abstention component",
            ),
            _boolean("control.no_volume", evidence.volume_component_supported, "volume component"),
            _boolean(
                "control.no_protection",
                evidence.protection_component_supported,
                "protection component",
            ),
        )
    )
    outcomes.extend(_cost_outcomes(evidence))
    outcomes.extend(_sensitivity_outcomes(evidence))
    outcomes.extend(_bootstrap_outcomes(evidence.bootstrap))
    outcomes.extend(
        (
            _boolean("replay.verified", evidence.replay_verified, "provider-free replay"),
            _boolean(
                "independent.verified",
                evidence.independent_verified,
                "independent verification",
            ),
        )
    )

    gates = tuple(item for item, _ in outcomes)
    if tuple(item.gate_id for item in gates) != QUALIFICATION_GATE_IDS:
        raise RuntimeError("mandatory qualification gate order is incomplete")
    explicit_failure = any(not gate.passed and not missing for gate, missing in outcomes)
    missing_evidence = any(missing for _, missing in outcomes)
    if explicit_failure:
        classification = QualificationClassification.REJECTED
    elif missing_evidence:
        classification = QualificationClassification.INCONCLUSIVE
    else:
        classification = QualificationClassification.QUALIFIED
    return QualificationReport(classification=classification, gates=gates)


__all__ = [
    "QUALIFICATION_GATE_IDS",
    "QualificationClassification",
    "QualificationEvidence",
    "QualificationReport",
    "evaluate_development_qualification",
]
