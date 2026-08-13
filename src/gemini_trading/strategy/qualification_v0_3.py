"""Strict development-only pre-final qualification gates for Candidate v0.3."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from gemini_trading.strategy.contracts import GateResult, SpecialistKind
from gemini_trading.strategy.determinism import TrendDeterminismReceipt
from gemini_trading.strategy.evaluation import (
    BootstrapResult,
    CostStressEvaluation,
    FoldEvaluation,
    NeighborEvaluation,
    cost_returns_are_monotonic,
)
from gemini_trading.strategy.qualification import QualificationClassification
from gemini_trading.strategy.study_execution import component_value_supported

_ZERO = Decimal("0")
_ONE = Decimal("1")
_PRIMARY_PERCENTILE = Decimal("0.75")
_SENSITIVITY_PERCENTILES = (Decimal("0.70"), Decimal("0.80"))

V03_QUALIFICATION_GATE_IDS = (
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


@dataclass(frozen=True, slots=True)
class SelectivityReplayReceipt:
    """Provider-free replay result for one fold/specialist/percentile artifact."""

    fold_number: int
    specialist: SpecialistKind
    percentile: Decimal
    eligible_rows_match: bool
    score_vector_match: bool
    raw_quantile_match: bool
    effective_threshold_match: bool
    canonical_bytes_match: bool

    def __post_init__(self) -> None:
        if isinstance(self.fold_number, bool) or self.fold_number < 1:
            raise ValueError("selectivity replay fold_number must be positive")
        if self.percentile not in {
            Decimal("0.70"),
            Decimal("0.75"),
            Decimal("0.80"),
        }:
            raise ValueError("selectivity replay percentile is not preregistered")

    @property
    def exact_match(self) -> bool:
        return all(
            (
                self.eligible_rows_match,
                self.score_vector_match,
                self.raw_quantile_match,
                self.effective_threshold_match,
                self.canonical_bytes_match,
            )
        )


@dataclass(frozen=True, slots=True)
class V03QualificationEvidence:
    """Complete Candidate v0.3 development evidence consumed by mandatory gates."""

    integrity_verified: bool | None
    trend_determinism: tuple[TrendDeterminismReceipt, ...] | None
    calibration_complete: bool | None
    selectivity_replay: tuple[SelectivityReplayReceipt, ...] | None
    development_folds: tuple[FoldEvaluation, ...]
    shuffled_labels_safe: bool | None
    delayed_features_component_supported: bool | None
    primary_return_to_drawdown: Decimal | None
    primary_aggregate_net_return: Decimal | None
    primary_aggregate_max_drawdown: Decimal | None
    no_percentile_selectivity_return_to_drawdown: Decimal | None
    no_percentile_selectivity_max_drawdown: Decimal | None
    volume_component_supported: bool | None
    protection_component_supported: bool | None
    cost_1_5x: CostStressEvaluation | None
    cost_2x: CostStressEvaluation | None
    neighbors: tuple[NeighborEvaluation, ...] | None
    bootstrap: BootstrapResult | None
    replay_verified: bool | None
    independent_verified: bool | None


@dataclass(frozen=True, slots=True)
class V03QualificationReport:
    """Every mandatory Candidate v0.3 pre-final gate plus fail-closed classification."""

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


def _selectivity_key(receipt: SelectivityReplayReceipt) -> tuple[int, SpecialistKind, Decimal]:
    return receipt.fold_number, receipt.specialist, receipt.percentile


def _expected_selectivity_keys(
    percentiles: tuple[Decimal, ...],
) -> set[tuple[int, SpecialistKind, Decimal]]:
    return {
        (fold_number, specialist, percentile)
        for fold_number in range(1, 13)
        for specialist in (SpecialistKind.TREND, SpecialistKind.MEAN_REVERSION)
        for percentile in percentiles
    }


def _selectivity_replay(
    receipts: tuple[SelectivityReplayReceipt, ...] | None,
) -> GateOutcome:
    if receipts is None:
        return _missing(
            "selectivity.replay",
            "24 exact q75 fold/specialist replay receipts",
            "q75 selectivity replay evidence",
        )
    q75 = tuple(item for item in receipts if item.percentile == _PRIMARY_PERCENTILE)
    keys = tuple(_selectivity_key(item) for item in q75)
    expected = _expected_selectivity_keys((_PRIMARY_PERCENTILE,))
    if len(keys) != len(set(keys)) or set(keys) != expected:
        return _missing(
            "selectivity.replay",
            "24 exact q75 fold/specialist replay receipts",
            "complete q75 selectivity replay inventory",
        )
    return _gate(
        "selectivity.replay",
        all(item.exact_match for item in q75),
        f"q75_receipts={len(q75)}",
        "24/24 exact q75 artifact replays",
        "q75 selectivity artifact replay evaluated",
    )


def _sensitivity_selectivity_complete(
    receipts: tuple[SelectivityReplayReceipt, ...] | None,
) -> bool:
    if receipts is None:
        return False
    sensitivity = tuple(item for item in receipts if item.percentile in _SENSITIVITY_PERCENTILES)
    keys = tuple(_selectivity_key(item) for item in sensitivity)
    expected = _expected_selectivity_keys(_SENSITIVITY_PERCENTILES)
    return (
        len(keys) == len(set(keys))
        and set(keys) == expected
        and all(item.exact_match for item in sensitivity)
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


def _no_percentile_selectivity(evidence: V03QualificationEvidence) -> GateOutcome:
    primary_rtd = evidence.primary_return_to_drawdown
    ablation_rtd = evidence.no_percentile_selectivity_return_to_drawdown
    primary_dd = evidence.primary_aggregate_max_drawdown
    ablation_dd = evidence.no_percentile_selectivity_max_drawdown
    if primary_dd is None or ablation_dd is None:
        return _missing(
            "control.no_percentile_selectivity",
            "component value retained",
            "primary/ablation drawdown evidence",
        )
    supported = component_value_supported(
        primary_return_to_drawdown=primary_rtd,
        primary_maximum_drawdown=primary_dd,
        ablation_return_to_drawdown=ablation_rtd,
        ablation_maximum_drawdown=ablation_dd,
        require_drawdown_reduction=False,
    )
    return _gate(
        "control.no_percentile_selectivity",
        supported,
        f"primary_rtd={primary_rtd};ablation_rtd={ablation_rtd};primary_dd={primary_dd};ablation_dd={ablation_dd}",
        "0.50 ablation must not improve RTD >=10% with drawdown no higher",
        "percentile-selectivity component evaluated; undefined RTD fails closed",
    )


def _cost_outcomes(evidence: V03QualificationEvidence) -> list[GateOutcome]:
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
        outcomes.append(_missing("cost.monotonicity", "base>=1.5x>=2x", "cost monotonicity"))
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


def _missing_sensitivity() -> list[GateOutcome]:
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


def _sensitivity_outcomes(evidence: V03QualificationEvidence) -> list[GateOutcome]:
    if not _sensitivity_selectivity_complete(evidence.selectivity_replay):
        return _missing_sensitivity()
    neighbors = evidence.neighbors
    if neighbors is None:
        return _missing_sensitivity()
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


def evaluate_v0_3_development_qualification(
    evidence: V03QualificationEvidence,
) -> V03QualificationReport:
    """Apply every preregistered Candidate v0.3 pre-final gate and fail closed."""

    outcomes: list[GateOutcome] = [
        _boolean("integrity.verified", evidence.integrity_verified, "integrity verification"),
        _trend_determinism(evidence.trend_determinism),
        _boolean("calibration.complete", evidence.calibration_complete, "calibration evidence"),
        _selectivity_replay(evidence.selectivity_replay),
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
            _no_percentile_selectivity(evidence),
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
    if tuple(item.gate_id for item in gates) != V03_QUALIFICATION_GATE_IDS:
        raise RuntimeError("mandatory v0.3 qualification gate order is incomplete")
    explicit_failure = any(not gate.passed and not missing for gate, missing in outcomes)
    missing_evidence = any(missing for _, missing in outcomes)
    if explicit_failure:
        classification = QualificationClassification.REJECTED
    elif missing_evidence:
        classification = QualificationClassification.INCONCLUSIVE
    else:
        classification = QualificationClassification.QUALIFIED
    return V03QualificationReport(classification=classification, gates=gates)


__all__ = [
    "V03_QUALIFICATION_GATE_IDS",
    "SelectivityReplayReceipt",
    "V03QualificationEvidence",
    "V03QualificationReport",
    "evaluate_v0_3_development_qualification",
]
