"""Deterministic strategy evaluation, robustness, and promotion gates."""

import hashlib
import math
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext
from enum import StrEnum

import numpy as np

from gemini_trading.research.engine import BacktestEvidence
from gemini_trading.research.metrics import completed_trades
from gemini_trading.research.serialization import canonical_json_bytes
from gemini_trading.strategy.contracts import GateResult, RegimeState
from gemini_trading.strategy.regimes import RegimeObservation

_ZERO = Decimal("0")
_ONE = Decimal("1")
_CONTEXT = Context(prec=34, rounding=ROUND_HALF_EVEN)


@dataclass(frozen=True, slots=True)
class RegimeMetrics:
    """Exact economic attribution for one closed regime state."""

    state: RegimeState
    period_count: int
    net_return: Decimal
    maximum_drawdown: Decimal
    exposure_fraction: Decimal
    completed_trade_count: int


@dataclass(frozen=True, slots=True)
class BootstrapResult:
    """Content-identified deterministic moving-block bootstrap summary."""

    seed: int
    replicate_count: int
    block_length: int
    sampled_start_matrix_sha256: str
    net_return_difference_median: Decimal
    net_return_difference_p05: Decimal
    net_return_difference_p95: Decimal
    drawdown_difference_median: Decimal
    drawdown_difference_p05: Decimal
    drawdown_difference_p95: Decimal
    return_to_drawdown_difference_median: Decimal
    return_to_drawdown_difference_p05: Decimal
    return_to_drawdown_difference_p95: Decimal


@dataclass(frozen=True, slots=True)
class FoldEvaluation:
    """One development-fold promotion summary."""

    candidate_net_return: Decimal
    candidate_return_to_drawdown: Decimal | None
    strongest_active_baseline_return_to_drawdown: Decimal | None
    positive_profit: Decimal
    completed_trades: int


@dataclass(frozen=True, slots=True)
class FinalEvaluation:
    """One sealed final-test promotion summary."""

    candidate_net_return: Decimal
    candidate_maximum_drawdown: Decimal
    buy_hold_maximum_drawdown: Decimal
    candidate_return_to_drawdown: Decimal | None
    strongest_active_simple_return_to_drawdown: Decimal | None
    strongest_specialist_return_to_drawdown: Decimal | None
    strongest_active_simple_net_return: Decimal | None
    completed_trades: int
    largest_positive_trade_fraction: Decimal | None
    aggregate_positive_profit: Decimal
    regime_metrics: tuple[RegimeMetrics, ...]


@dataclass(frozen=True, slots=True)
class CostStressEvaluation:
    """One fixed-decision execution-cost stress result."""

    multiplier: Decimal
    net_return: Decimal
    maximum_drawdown: Decimal


@dataclass(frozen=True, slots=True)
class NeighborEvaluation:
    """One neighboring locked-parameter sensitivity result."""

    net_return: Decimal
    maximum_drawdown: Decimal


@dataclass(frozen=True, slots=True)
class PromotionEvidence:
    """Complete immutable evidence required by every mandatory gate."""

    development_folds: tuple[FoldEvaluation, ...]
    final: FinalEvaluation
    cost_1_5x: CostStressEvaluation
    cost_2x: CostStressEvaluation
    neighbors: tuple[NeighborEvaluation, ...]
    bootstrap: BootstrapResult
    shuffled_labels_economic_gates_passed: bool
    delayed_feature_return_to_drawdown: Decimal | None
    no_disagreement_component_value: bool
    no_volume_component_value: bool
    no_protection_component_value: bool


class PromotionClassification(StrEnum):
    """Closed strategy-study terminal classifications."""

    PASS = "PASS"
    REJECTED = "REJECTED"
    INCONCLUSIVE = "INCONCLUSIVE"


@dataclass(frozen=True, slots=True)
class PromotionReport:
    """Every mandatory gate plus one fail-closed classification."""

    classification: PromotionClassification
    gates: tuple[GateResult, ...]


MANDATORY_GATE_IDS = (
    "development.fold_count",
    "development.positive_return_folds",
    "development.baseline_rtd_folds",
    "development.profit_concentration",
    "development.trade_count",
    "final.net_return",
    "final.trade_count",
    "final.absolute_drawdown",
    "final.relative_drawdown",
    "final.return_to_drawdown",
    "final.simple_baseline_rtd",
    "final.specialist_rtd",
    "final.simple_baseline_net_return",
    "final.trade_concentration",
    "final.regime_nonnegative",
    "final.regime_loss",
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
    "control.shuffled_labels",
    "control.delayed_features",
    "control.no_disagreement",
    "control.no_volume",
    "control.no_protection",
)


def attribute_regime_metrics(
    evidence: BacktestEvidence,
    observations: tuple[RegimeObservation, ...],
) -> tuple[RegimeMetrics, ...]:
    """Attribute account changes and completed trades to stored regime observations."""

    if len(observations) != len(evidence.account_series):
        raise ValueError("regime observations must align one-to-one with account series")
    candle_indices = tuple(item.candle_index for item in observations)
    if len(candle_indices) != len(set(candle_indices)):
        raise ValueError("regime observation candle indices must be unique")

    starting_equity = evidence.experiment_manifest.initial_cash
    previous_equity = starting_equity
    period_counts = {state: 0 for state in RegimeState}
    net_returns = {state: _ZERO for state in RegimeState}
    maximum_drawdowns = {state: _ZERO for state in RegimeState}
    exposed_periods = {state: 0 for state in RegimeState}
    trade_counts = {state: 0 for state in RegimeState}
    state_by_index = {item.candle_index: item.state for item in observations}

    with localcontext(_CONTEXT):
        for observation, snapshot in zip(observations, evidence.account_series, strict=True):
            state = observation.state
            period_counts[state] += 1
            net_returns[state] += (snapshot.marked_equity - previous_equity) / starting_equity
            maximum_drawdowns[state] = max(maximum_drawdowns[state], snapshot.drawdown)
            exposed_periods[state] += int(snapshot.position_quantity > 0)
            previous_equity = snapshot.marked_equity

        for trade in completed_trades(evidence):
            state = state_by_index.get(trade.exit_candle_index)
            if state is None:
                raise ValueError("completed trade exit has no regime observation")
            trade_counts[state] += 1

        return tuple(
            RegimeMetrics(
                state=state,
                period_count=period_counts[state],
                net_return=net_returns[state],
                maximum_drawdown=maximum_drawdowns[state],
                exposure_fraction=(
                    _ZERO
                    if period_counts[state] == 0
                    else Decimal(exposed_periods[state]) / Decimal(period_counts[state])
                ),
                completed_trade_count=trade_counts[state],
            )
            for state in RegimeState
        )


def _path_statistics(period_returns: np.ndarray) -> tuple[float, float, float]:
    wealth = np.cumprod(1.0 + period_returns)
    net_return = float(wealth[-1] - 1.0)
    peaks = np.maximum.accumulate(np.concatenate((np.array([1.0]), wealth)))
    extended = np.concatenate((np.array([1.0]), wealth))
    drawdown = float(np.max((peaks - extended) / peaks))
    return_to_drawdown = 0.0 if drawdown == 0.0 else net_return / drawdown
    return net_return, drawdown, return_to_drawdown


def _percentiles(values: np.ndarray) -> tuple[Decimal, Decimal, Decimal]:
    p05, median, p95 = np.percentile(values, (5, 50, 95))
    return Decimal(str(float(median))), Decimal(str(float(p05))), Decimal(str(float(p95)))


def deterministic_moving_block_bootstrap(
    candidate_period_returns: tuple[Decimal, ...],
    baseline_period_returns: tuple[Decimal, ...],
    *,
    seed: int = 1788,
    replicate_count: int = 1000,
    block_length: int = 42,
) -> BootstrapResult:
    """Bootstrap paired return paths using one locked PCG64 sampled-start matrix."""

    if len(candidate_period_returns) != len(baseline_period_returns):
        raise ValueError("candidate and baseline return series must have equal length")
    if not candidate_period_returns:
        raise ValueError("bootstrap return series must not be empty")
    if block_length <= 0 or block_length > len(candidate_period_returns):
        raise ValueError("bootstrap block length must fit the return series")
    if replicate_count <= 0:
        raise ValueError("bootstrap replicate count must be positive")

    candidate = np.asarray([float(value) for value in candidate_period_returns], dtype=np.float64)
    baseline = np.asarray([float(value) for value in baseline_period_returns], dtype=np.float64)
    block_count = math.ceil(len(candidate) / block_length)
    rng = np.random.Generator(np.random.PCG64(seed))
    starts = rng.integers(
        0,
        len(candidate) - block_length + 1,
        size=(replicate_count, block_count),
        dtype=np.int64,
    )
    matrix_identity = hashlib.sha256(
        canonical_json_bytes(
            {
                "seed": seed,
                "replicate_count": replicate_count,
                "block_length": block_length,
                "starts": starts.tolist(),
            }
        )
    ).hexdigest()
    net_differences = np.empty(replicate_count, dtype=np.float64)
    drawdown_differences = np.empty(replicate_count, dtype=np.float64)
    rtd_differences = np.empty(replicate_count, dtype=np.float64)

    for replicate_index, replicate_starts in enumerate(starts):
        indices = np.concatenate(
            [np.arange(start, start + block_length, dtype=np.int64) for start in replicate_starts]
        )[: len(candidate)]
        candidate_stats = _path_statistics(candidate[indices])
        baseline_stats = _path_statistics(baseline[indices])
        net_differences[replicate_index] = candidate_stats[0] - baseline_stats[0]
        drawdown_differences[replicate_index] = candidate_stats[1] - baseline_stats[1]
        rtd_differences[replicate_index] = candidate_stats[2] - baseline_stats[2]

    net_median, net_p05, net_p95 = _percentiles(net_differences)
    drawdown_median, drawdown_p05, drawdown_p95 = _percentiles(drawdown_differences)
    rtd_median, rtd_p05, rtd_p95 = _percentiles(rtd_differences)
    return BootstrapResult(
        seed=seed,
        replicate_count=replicate_count,
        block_length=block_length,
        sampled_start_matrix_sha256=matrix_identity,
        net_return_difference_median=net_median,
        net_return_difference_p05=net_p05,
        net_return_difference_p95=net_p95,
        drawdown_difference_median=drawdown_median,
        drawdown_difference_p05=drawdown_p05,
        drawdown_difference_p95=drawdown_p95,
        return_to_drawdown_difference_median=rtd_median,
        return_to_drawdown_difference_p05=rtd_p05,
        return_to_drawdown_difference_p95=rtd_p95,
    )


def cost_returns_are_monotonic(
    base_return: Decimal,
    one_half_cost_return: Decimal,
    double_cost_return: Decimal,
) -> bool:
    """Return whether more expensive execution never improves net return."""

    return base_return >= one_half_cost_return >= double_cost_return


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


def _median(values: tuple[Decimal, ...]) -> Decimal:
    ordered = tuple(sorted(values))
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / Decimal("2")


def evaluate_promotion(evidence: PromotionEvidence) -> PromotionReport:
    """Apply every mandatory Candidate v0.1 gate and classify fail closed."""

    outcomes: list[tuple[GateResult, bool]] = []
    folds = evidence.development_folds
    outcomes.append(
        _gate(
            "development.fold_count",
            len(folds) >= 5,
            len(folds),
            ">=5",
            "development fold count evaluated",
        )
    )
    positive_folds = sum(item.candidate_net_return > 0 for item in folds)
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
            item.candidate_return_to_drawdown
            > item.strongest_active_baseline_return_to_drawdown
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
        if total_positive_profit == 0
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

    final = evidence.final
    outcomes.append(
        _gate("final.net_return", final.candidate_net_return > 0, final.candidate_net_return, ">0", "final net return evaluated")
    )
    outcomes.append(
        _gate("final.trade_count", final.completed_trades >= 30, final.completed_trades, ">=30", "final trade count evaluated")
    )
    outcomes.append(
        _gate(
            "final.absolute_drawdown",
            final.candidate_maximum_drawdown <= Decimal("0.25"),
            final.candidate_maximum_drawdown,
            "<=0.25",
            "final absolute drawdown evaluated",
        )
    )
    outcomes.append(
        _gate(
            "final.relative_drawdown",
            final.candidate_maximum_drawdown <= Decimal("0.80") * final.buy_hold_maximum_drawdown,
            final.candidate_maximum_drawdown,
            "<=0.80*buy_hold",
            "final drawdown relative to buy-and-hold evaluated",
        )
    )
    if final.candidate_return_to_drawdown is None:
        outcomes.append(_missing("final.return_to_drawdown", ">=0.50", "candidate return-to-drawdown"))
    else:
        outcomes.append(
            _gate(
                "final.return_to_drawdown",
                final.candidate_return_to_drawdown >= Decimal("0.50"),
                final.candidate_return_to_drawdown,
                ">=0.50",
                "final return-to-drawdown evaluated",
            )
        )
    if final.candidate_return_to_drawdown is None or final.strongest_active_simple_return_to_drawdown is None:
        outcomes.append(_missing("final.simple_baseline_rtd", ">=1.10x", "simple baseline return-to-drawdown comparator"))
    else:
        outcomes.append(
            _gate(
                "final.simple_baseline_rtd",
                final.candidate_return_to_drawdown
                >= Decimal("1.10") * final.strongest_active_simple_return_to_drawdown,
                final.candidate_return_to_drawdown,
                ">=1.10x strongest simple baseline",
                "final simple-baseline return-to-drawdown comparison evaluated",
            )
        )
    if final.candidate_return_to_drawdown is None or final.strongest_specialist_return_to_drawdown is None:
        outcomes.append(_missing("final.specialist_rtd", ">=1.05x", "specialist return-to-drawdown comparator"))
    else:
        outcomes.append(
            _gate(
                "final.specialist_rtd",
                final.candidate_return_to_drawdown
                >= Decimal("1.05") * final.strongest_specialist_return_to_drawdown,
                final.candidate_return_to_drawdown,
                ">=1.05x strongest specialist",
                "final specialist return-to-drawdown comparison evaluated",
            )
        )
    if final.strongest_active_simple_net_return is None:
        outcomes.append(_missing("final.simple_baseline_net_return", ">=baseline-0.02", "simple baseline net-return comparator"))
    else:
        outcomes.append(
            _gate(
                "final.simple_baseline_net_return",
                final.candidate_net_return >= final.strongest_active_simple_net_return - Decimal("0.02"),
                final.candidate_net_return,
                ">=strongest simple baseline-0.02",
                "final simple-baseline net-return comparison evaluated",
            )
        )
    if final.largest_positive_trade_fraction is None:
        outcomes.append(_missing("final.trade_concentration", "<=0.25", "positive-trade concentration"))
    else:
        outcomes.append(
            _gate(
                "final.trade_concentration",
                final.largest_positive_trade_fraction <= Decimal("0.25"),
                final.largest_positive_trade_fraction,
                "<=0.25",
                "final positive-trade concentration evaluated",
            )
        )
    nonnegative_regimes = sum(
        item.period_count > 0 and item.net_return >= 0 for item in final.regime_metrics
    )
    outcomes.append(
        _gate(
            "final.regime_nonnegative",
            nonnegative_regimes >= 2,
            nonnegative_regimes,
            ">=2",
            "non-negative required regimes evaluated",
        )
    )
    if final.aggregate_positive_profit <= 0:
        outcomes.append(_missing("final.regime_loss", ">=-0.25*positive_profit", "aggregate positive profit"))
    else:
        worst_regime = min(
            (item.net_return for item in final.regime_metrics if item.period_count > 0),
            default=_ZERO,
        )
        outcomes.append(
            _gate(
                "final.regime_loss",
                worst_regime >= -Decimal("0.25") * final.aggregate_positive_profit,
                worst_regime,
                ">=-0.25*aggregate positive profit",
                "required-regime loss evaluated",
            )
        )

    outcomes.extend(
        (
            _gate("cost.one_half_return", evidence.cost_1_5x.net_return > 0, evidence.cost_1_5x.net_return, ">0", "1.5x cost return evaluated"),
            _gate("cost.one_half_drawdown", evidence.cost_1_5x.maximum_drawdown <= Decimal("0.275"), evidence.cost_1_5x.maximum_drawdown, "<=0.275", "1.5x cost drawdown evaluated"),
            _gate("cost.double_return", evidence.cost_2x.net_return >= Decimal("-0.05"), evidence.cost_2x.net_return, ">=-0.05", "2x cost return evaluated"),
            _gate("cost.double_drawdown", evidence.cost_2x.maximum_drawdown <= Decimal("0.30"), evidence.cost_2x.maximum_drawdown, "<=0.30", "2x cost drawdown evaluated"),
            _gate("cost.monotonicity", cost_returns_are_monotonic(final.candidate_net_return, evidence.cost_1_5x.net_return, evidence.cost_2x.net_return), f"{final.candidate_net_return},{evidence.cost_1_5x.net_return},{evidence.cost_2x.net_return}", "base>=1.5x>=2x", "cost monotonicity evaluated"),
        )
    )

    neighbor_returns = tuple(item.net_return for item in evidence.neighbors)
    positive_neighbors = sum(value > 0 for value in neighbor_returns)
    neighbor_median = _ZERO if not neighbor_returns else _median(neighbor_returns)
    neighbor_max_drawdown = max(
        (item.maximum_drawdown for item in evidence.neighbors), default=Decimal("Infinity")
    )
    outcomes.extend(
        (
            _gate("sensitivity.positive_neighbors", len(evidence.neighbors) >= 10 and positive_neighbors >= 7, positive_neighbors, ">=7/10", "positive neighboring variants evaluated"),
            _gate("sensitivity.median_return", neighbor_median > 0, neighbor_median, ">0", "neighbor median return evaluated"),
            _gate("sensitivity.drawdown", neighbor_max_drawdown <= Decimal("0.35"), neighbor_max_drawdown, "<=0.35", "neighbor drawdown evaluated"),
        )
    )
    stability_passed = True
    if final.candidate_net_return <= Decimal("0.02"):
        stability_passed = all(
            item.net_return <= final.candidate_net_return * Decimal("2")
            for item in evidence.neighbors
        )
    outcomes.append(
        _gate(
            "sensitivity.primary_stability",
            stability_passed,
            final.candidate_net_return,
            "no >100% neighbor improvement when primary<=0.02",
            "primary sensitivity stability evaluated",
        )
    )
    outcomes.extend(
        (
            _gate("uncertainty.bootstrap_median", evidence.bootstrap.net_return_difference_median > 0, evidence.bootstrap.net_return_difference_median, ">0", "bootstrap median return difference evaluated"),
            _gate("uncertainty.bootstrap_lower_bound", evidence.bootstrap.net_return_difference_p05 > Decimal("-0.02"), evidence.bootstrap.net_return_difference_p05, ">-0.02", "bootstrap 90% lower bound evaluated"),
            _gate("control.shuffled_labels", not evidence.shuffled_labels_economic_gates_passed, evidence.shuffled_labels_economic_gates_passed, "false", "shuffled-label economic gates evaluated"),
        )
    )
    if final.candidate_return_to_drawdown is None or evidence.delayed_feature_return_to_drawdown is None:
        outcomes.append(_missing("control.delayed_features", "<=1.05x primary", "delayed-feature comparator"))
    else:
        outcomes.append(
            _gate(
                "control.delayed_features",
                evidence.delayed_feature_return_to_drawdown
                <= Decimal("1.05") * final.candidate_return_to_drawdown,
                evidence.delayed_feature_return_to_drawdown,
                "<=1.05x primary",
                "delayed-feature control evaluated",
            )
        )
    outcomes.extend(
        (
            _gate("control.no_disagreement", evidence.no_disagreement_component_value, evidence.no_disagreement_component_value, "true", "disagreement component value evaluated"),
            _gate("control.no_volume", evidence.no_volume_component_value, evidence.no_volume_component_value, "true", "volume component value evaluated"),
            _gate("control.no_protection", evidence.no_protection_component_value, evidence.no_protection_component_value, "true", "protection component value evaluated"),
        )
    )

    gates = tuple(item for item, _ in outcomes)
    if tuple(item.gate_id for item in gates) != MANDATORY_GATE_IDS:
        raise RuntimeError("mandatory promotion gate order is incomplete")
    explicit_failure = any(not item.passed and not missing for item, missing in outcomes)
    missing_evidence = any(missing for _, missing in outcomes)
    classification = (
        PromotionClassification.REJECTED
        if explicit_failure
        else PromotionClassification.INCONCLUSIVE
        if missing_evidence
        else PromotionClassification.PASS
    )
    return PromotionReport(classification=classification, gates=gates)


__all__ = [
    "MANDATORY_GATE_IDS",
    "BootstrapResult",
    "CostStressEvaluation",
    "FinalEvaluation",
    "FoldEvaluation",
    "NeighborEvaluation",
    "PromotionClassification",
    "PromotionEvidence",
    "PromotionReport",
    "RegimeMetrics",
    "attribute_regime_metrics",
    "cost_returns_are_monotonic",
    "deterministic_moving_block_bootstrap",
    "evaluate_promotion",
]
