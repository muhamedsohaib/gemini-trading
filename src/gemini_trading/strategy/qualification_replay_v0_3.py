"""Provider-free recomputation of Candidate v0.3 qualification evidence."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import cast

from gemini_trading.data.storage.local_immutable import LocalImmutableStore
from gemini_trading.domain.experiment import LimitFillPolicy, TimingPolicy
from gemini_trading.domain.order import TimeInForce
from gemini_trading.research.artifacts import LocalResearchStore
from gemini_trading.research.config import SimulationConfig
from gemini_trading.research.dataset_reader import load_verified_dataset
from gemini_trading.research.serialization import canonical_json_bytes, canonical_jsonl_bytes
from gemini_trading.strategy.calibration_evidence import (
    calibration_evidence_complete,
    parse_calibration_diagnostics,
)
from gemini_trading.strategy.determinism import TrendDeterminismReceipt
from gemini_trading.strategy.errors import ModelDeterminismError, StudyArtifactError
from gemini_trading.strategy.evaluation import (
    BootstrapResult,
    CostStressEvaluation,
    FoldEvaluation,
    NeighborEvaluation,
    deterministic_moving_block_bootstrap,
)
from gemini_trading.strategy.features import FeatureRegistry
from gemini_trading.strategy.labels import LabelPolicy
from gemini_trading.strategy.policy import CandidatePolicy
from gemini_trading.strategy.qualification_execution import (
    AggregatePathMetrics,
    aggregate_path_metrics,
)
from gemini_trading.strategy.qualification_execution_v0_3 import qualification_case_ids
from gemini_trading.strategy.qualification_v0_3 import (
    SelectivityReplayReceipt,
    V03QualificationEvidence,
    V03QualificationReport,
    evaluate_v0_3_development_qualification,
)
from gemini_trading.strategy.splits import WalkForwardFold
from gemini_trading.strategy.study import StudyCaseEvidence
from gemini_trading.strategy.study_execution import (
    component_value_supported,
    shuffled_labels_passes_any_economic_gate,
)
from gemini_trading.strategy.v0_3_splits import V03DevelopmentQualificationPlan

_ZERO = Decimal("0")
_SIMPLE_IDS = (
    "buy_hold.v1",
    "ema_20_50.v1",
    "donchian_20_10.v1",
    "mean_reversion_z24.v1",
)
_SPECIALIST_IDS = ("trend.specialist.v1", "mean_reversion.specialist.v1")


@dataclass(frozen=True, slots=True)
class V03QualificationReplay:
    """Independently recomputed split, bootstrap, and report identities."""

    development_plan_bytes: bytes
    bootstrap: BootstrapResult
    report: V03QualificationReport


@dataclass(frozen=True, slots=True)
class _StoredMetrics:
    starting_equity: Decimal
    net_return: Decimal
    maximum_drawdown: Decimal
    return_to_drawdown: Decimal | None
    trade_count: int


def _mapping(raw: bytes, description: str) -> dict[str, object]:
    try:
        loaded: object = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise StudyArtifactError(f"invalid v0.3 replay {description} JSON") from None
    if not isinstance(loaded, dict):
        raise StudyArtifactError(f"invalid v0.3 replay {description} JSON")
    return cast(dict[str, object], loaded)


def _rows(raw: bytes, description: str) -> tuple[dict[str, object], ...]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise StudyArtifactError(f"invalid v0.3 replay {description} UTF-8") from None
    values: list[dict[str, object]] = []
    for line in text.splitlines():
        try:
            loaded: object = json.loads(line)
        except json.JSONDecodeError:
            raise StudyArtifactError(f"invalid v0.3 replay {description} JSONL") from None
        if not isinstance(loaded, dict):
            raise StudyArtifactError(f"invalid v0.3 replay {description} row")
        values.append(cast(dict[str, object], loaded))
    return tuple(values)


def _decimal(mapping: dict[str, object], key: str, description: str) -> Decimal:
    value = mapping.get(key)
    if not isinstance(value, str):
        raise StudyArtifactError(f"invalid v0.3 replay {description}: {key}")
    try:
        result = Decimal(value)
    except InvalidOperation:
        raise StudyArtifactError(f"invalid v0.3 replay {description}: {key}") from None
    if not result.is_finite():
        raise StudyArtifactError(f"non-finite v0.3 replay {description}: {key}")
    return result


def _optional_decimal(mapping: dict[str, object], key: str, description: str) -> Decimal | None:
    value = mapping.get(key)
    if value is None:
        return None
    return _decimal(mapping, key, description)


def _integer(mapping: dict[str, object], key: str, description: str) -> int:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise StudyArtifactError(f"invalid v0.3 replay {description}: {key}")
    return value


def parse_simulation_config(raw: bytes) -> SimulationConfig:
    """Parse one exact canonical simulation config used by a verified experiment."""

    mapping = _mapping(raw, "simulation config")
    expected = set(SimulationConfig.__dataclass_fields__)
    if set(mapping) != expected:
        raise StudyArtifactError("v0.3 replay simulation fields changed")
    max_active_raw = mapping.get("max_active_candles")
    max_active = (
        None
        if max_active_raw is None
        else _integer(mapping, "max_active_candles", "simulation config")
    )
    latency = _integer(mapping, "latency_bars", "simulation config")
    promotable = mapping.get("promotable")
    if not isinstance(promotable, bool):
        raise StudyArtifactError("invalid v0.3 replay simulation config: promotable")
    try:
        return SimulationConfig(
            maker_fee_rate=_decimal(mapping, "maker_fee_rate", "simulation config"),
            taker_fee_rate=_decimal(mapping, "taker_fee_rate", "simulation config"),
            half_spread_bps=_decimal(mapping, "half_spread_bps", "simulation config"),
            slippage_bps=_decimal(mapping, "slippage_bps", "simulation config"),
            latency_bars=latency,
            price_tick=_decimal(mapping, "price_tick", "simulation config"),
            quantity_step=_decimal(mapping, "quantity_step", "simulation config"),
            min_quantity=_decimal(mapping, "min_quantity", "simulation config"),
            min_notional=_decimal(mapping, "min_notional", "simulation config"),
            max_volume_participation=_decimal(
                mapping, "max_volume_participation", "simulation config"
            ),
            max_active_candles=max_active,
            timing_policy=TimingPolicy(cast(str, mapping["timing_policy"])),
            limit_fill_policy=LimitFillPolicy(cast(str, mapping["limit_fill_policy"])),
            default_time_in_force=TimeInForce(cast(str, mapping["default_time_in_force"])),
            promotable=promotable,
        )
    except (KeyError, ValueError, TypeError):
        raise StudyArtifactError("invalid v0.3 replay simulation config") from None


def _determinism_receipts(raw: bytes) -> tuple[TrendDeterminismReceipt, ...]:
    receipts: list[TrendDeterminismReceipt] = []
    for mapping in _rows(raw, "determinism receipts"):
        try:
            receipts.append(
                TrendDeterminismReceipt(
                    schema_version=cast(str, mapping["schema_version"]),
                    fold_number=cast(int, mapping["fold_number"]),
                    iteration_count=cast(int, mapping["iteration_count"]),
                    first_model_sha256=cast(str, mapping["first_model_sha256"]),
                    second_model_sha256=cast(str, mapping["second_model_sha256"]),
                    first_bundle_sha256=cast(str, mapping["first_bundle_sha256"]),
                    second_bundle_sha256=cast(str, mapping["second_bundle_sha256"]),
                    exact_match=cast(bool, mapping["exact_match"]),
                )
            )
        except (KeyError, TypeError, ValueError, ModelDeterminismError):
            raise StudyArtifactError("invalid v0.3 replay determinism receipt") from None
    if canonical_jsonl_bytes(asdict(item) for item in receipts) != raw:
        raise StudyArtifactError("v0.3 replay determinism receipt encoding changed")
    return tuple(receipts)


def _record_map(records: tuple[StudyCaseEvidence, ...]) -> dict[tuple[int, str], StudyCaseEvidence]:
    mapped: dict[tuple[int, str], StudyCaseEvidence] = {}
    for record in records:
        if record.fold_number is None:
            raise StudyArtifactError("v0.3 replay case is missing a fold number")
        key = (record.fold_number, record.case_id)
        if key in mapped:
            raise StudyArtifactError("duplicate v0.3 replay case evidence")
        mapped[key] = record
    return mapped


def _case_directory(store: LocalResearchStore, record: StudyCaseEvidence) -> Path:
    return store.directory(record.experiment_id)


def _metrics(store: LocalResearchStore, record: StudyCaseEvidence) -> _StoredMetrics:
    try:
        mapping = _mapping(
            (_case_directory(store, record) / "metrics.json").read_bytes(), "metrics"
        )
    except OSError:
        raise StudyArtifactError("v0.3 replay metrics artifact is missing") from None
    return _StoredMetrics(
        starting_equity=_decimal(mapping, "starting_equity", "metrics"),
        net_return=_decimal(mapping, "net_return", "metrics"),
        maximum_drawdown=_decimal(mapping, "maximum_drawdown", "metrics"),
        return_to_drawdown=_optional_decimal(mapping, "return_to_drawdown", "metrics"),
        trade_count=_integer(mapping, "trade_count", "metrics"),
    )


def _positive_profit(store: LocalResearchStore, record: StudyCaseEvidence) -> Decimal:
    try:
        rows = _rows((_case_directory(store, record) / "trades.jsonl").read_bytes(), "trades")
    except OSError:
        raise StudyArtifactError("v0.3 replay trades artifact is missing") from None
    total = _ZERO
    for mapping in rows:
        realized = _decimal(mapping, "realized_pnl", "trade")
        if realized > _ZERO:
            total += realized
    return total


def _equity_series(store: LocalResearchStore, record: StudyCaseEvidence) -> tuple[Decimal, ...]:
    try:
        rows = _rows(
            (_case_directory(store, record) / "account-series.jsonl").read_bytes(),
            "account series",
        )
    except OSError:
        raise StudyArtifactError("v0.3 replay account-series artifact is missing") from None
    return tuple(_decimal(mapping, "marked_equity", "account snapshot") for mapping in rows)


def _fold_oos_returns(
    *,
    store: LocalResearchStore,
    record: StudyCaseEvidence,
    fold: WalkForwardFold,
    simulation: SimulationConfig,
    candle_count: int,
) -> tuple[Decimal, ...]:
    development_test = fold.development_test
    development_test_indices = fold.development_test_indices
    if not isinstance(development_test_indices, tuple) or not development_test_indices:
        raise StudyArtifactError("v0.3 replay fold development-test indices are invalid")
    start = development_test.start_inclusive
    if isinstance(start, bool) or not isinstance(start, int):
        raise StudyArtifactError("v0.3 replay fold start is invalid")
    last_index = development_test_indices[-1]
    if isinstance(last_index, bool) or not isinstance(last_index, int):
        raise StudyArtifactError("v0.3 replay fold end is invalid")
    end_exclusive = min(candle_count, last_index + 2 + simulation.latency_bars)
    equities = _equity_series(store, record)
    metrics = _metrics(store, record)
    if start >= end_exclusive or end_exclusive > len(equities):
        raise StudyArtifactError("v0.3 replay OOS account path is incomplete")
    previous = metrics.starting_equity if start == 0 else equities[start - 1]
    values: list[Decimal] = []
    for equity in equities[start:end_exclusive]:
        if previous <= _ZERO:
            raise StudyArtifactError("v0.3 replay OOS prior equity must remain positive")
        values.append(equity / previous - Decimal("1"))
        previous = equity
    return tuple(values)


def _case_period_returns(
    *,
    store: LocalResearchStore,
    records: dict[tuple[int, str], StudyCaseEvidence],
    plan: V03DevelopmentQualificationPlan,
    simulation: SimulationConfig,
    candle_count: int,
    case_id: str,
) -> tuple[Decimal, ...]:
    values: list[Decimal] = []
    for fold in plan.folds:
        record = records.get((fold.fold_number, case_id))
        if record is None:
            raise StudyArtifactError(f"v0.3 replay case evidence is missing: {case_id}")
        values.extend(
            _fold_oos_returns(
                store=store,
                record=record,
                fold=fold,
                simulation=simulation,
                candle_count=candle_count,
            )
        )
    return tuple(values)


def _aggregate_case(
    *,
    store: LocalResearchStore,
    records: dict[tuple[int, str], StudyCaseEvidence],
    plan: V03DevelopmentQualificationPlan,
    simulation: SimulationConfig,
    candle_count: int,
    case_id: str,
) -> AggregatePathMetrics:
    return aggregate_path_metrics(
        _case_period_returns(
            store=store,
            records=records,
            plan=plan,
            simulation=simulation,
            candle_count=candle_count,
            case_id=case_id,
        )
    )


def _strongest_rtd(metrics: tuple[AggregatePathMetrics, ...]) -> Decimal | None:
    values = tuple(
        item.return_to_drawdown for item in metrics if item.return_to_drawdown is not None
    )
    return max(values) if values else None


def _fold_evaluations(
    *,
    store: LocalResearchStore,
    records: dict[tuple[int, str], StudyCaseEvidence],
    plan: V03DevelopmentQualificationPlan,
    policy: CandidatePolicy,
) -> tuple[FoldEvaluation, ...]:
    values: list[FoldEvaluation] = []
    for fold in plan.folds:
        candidate_record = records[(fold.fold_number, policy.strategy_id)]
        candidate = _metrics(store, candidate_record)
        baseline = tuple(
            _metrics(store, records[(fold.fold_number, case_id)]) for case_id in _SIMPLE_IDS
        )
        defined = tuple(
            item.return_to_drawdown for item in baseline if item.return_to_drawdown is not None
        )
        values.append(
            FoldEvaluation(
                candidate_net_return=candidate.net_return,
                candidate_return_to_drawdown=candidate.return_to_drawdown,
                strongest_active_baseline_return_to_drawdown=max(defined) if defined else None,
                positive_profit=_positive_profit(store, candidate_record),
                completed_trades=candidate.trade_count,
            )
        )
    return tuple(values)


def replay_candidate_v0_3_qualification(
    *,
    root: Path,
    dataset_id: str,
    records: tuple[StudyCaseEvidence, ...],
    threshold_receipts: tuple[SelectivityReplayReceipt, ...],
    artifact_files: dict[str, bytes],
) -> V03QualificationReplay:
    """Recompute v0.3 split, bootstrap, and every pre-final gate from portable evidence."""

    policy = CandidatePolicy.locked_v0_3()
    mapped = _record_map(records)
    store = LocalResearchStore(root)
    primary_record = mapped.get((1, policy.strategy_id))
    if primary_record is None:
        raise StudyArtifactError("v0.3 replay primary fold-one case is missing")
    try:
        simulation_raw = (
            _case_directory(store, primary_record) / "simulation-config.json"
        ).read_bytes()
    except OSError:
        raise StudyArtifactError("v0.3 replay simulation artifact is missing") from None
    simulation = parse_simulation_config(simulation_raw)

    dataset = load_verified_dataset(LocalImmutableStore(root), dataset_id)
    if dataset.segment_manifest is None:
        raise StudyArtifactError("v0.3 replay segment evidence is missing")
    matrix = FeatureRegistry.locked_v0_1().compute(
        dataset.candles,
        segments=dataset.segment_manifest,
    )
    labels = LabelPolicy.locked_v0_1(simulation).build(
        dataset.candles,
        eligible_indices=tuple(row.candle_index for row in matrix.rows),
        segments=dataset.segment_manifest,
    )
    eligible = tuple(item.decision_candle_index for item in labels.observations)
    plan = V03DevelopmentQualificationPlan.build(
        dataset.candles,
        eligible,
        policy,
        dataset.segment_manifest,
    )
    development_plan_bytes = canonical_json_bytes(asdict(plan))

    simple = tuple(
        _aggregate_case(
            store=store,
            records=mapped,
            plan=plan,
            simulation=simulation,
            candle_count=len(dataset.candles),
            case_id=case_id,
        )
        for case_id in _SIMPLE_IDS
    )
    specialist = tuple(
        _aggregate_case(
            store=store,
            records=mapped,
            plan=plan,
            simulation=simulation,
            candle_count=len(dataset.candles),
            case_id=case_id,
        )
        for case_id in _SPECIALIST_IDS
    )
    strongest_simple_rtd = _strongest_rtd(simple)
    strongest_specialist_rtd = _strongest_rtd(specialist)

    def aggregate(case_id: str) -> AggregatePathMetrics:
        return _aggregate_case(
            store=store,
            records=mapped,
            plan=plan,
            simulation=simulation,
            candle_count=len(dataset.candles),
            case_id=case_id,
        )

    primary = aggregate(policy.strategy_id)
    delayed = aggregate("control.delayed_features.final")
    shuffled = aggregate("control.shuffled_labels.seed_1799")
    no_selectivity = aggregate("ablation.no_percentile_selectivity.v1")
    no_volume = aggregate("ablation.no_volume.v1")
    no_protection = aggregate("ablation.no_protection.v1")
    cost_one_half = aggregate("cost.1_5x")
    cost_double = aggregate("cost.2x")

    neighbor_ids = tuple(
        case_id for case_id in qualification_case_ids(policy) if case_id.startswith("sensitivity.")
    )
    neighbors = tuple(
        NeighborEvaluation(
            net_return=(metrics := aggregate(case_id)).net_return,
            maximum_drawdown=metrics.maximum_drawdown,
        )
        for case_id in neighbor_ids
    )
    if len(neighbors) != 10:
        raise StudyArtifactError("v0.3 replay sensitivity inventory changed")

    baseline_index = max(
        range(len(simple)),
        key=lambda index: simple[index].return_to_drawdown or Decimal("-999999"),
    )
    strongest_baseline_case = _SIMPLE_IDS[baseline_index]
    primary_returns = _case_period_returns(
        store=store,
        records=mapped,
        plan=plan,
        simulation=simulation,
        candle_count=len(dataset.candles),
        case_id=policy.strategy_id,
    )
    baseline_returns = _case_period_returns(
        store=store,
        records=mapped,
        plan=plan,
        simulation=simulation,
        candle_count=len(dataset.candles),
        case_id=strongest_baseline_case,
    )
    if not primary_returns:
        raise StudyArtifactError("v0.3 replay bootstrap path is empty")
    bootstrap = deterministic_moving_block_bootstrap(
        primary_returns,
        baseline_returns,
        seed=policy.bootstrap_seed,
        replicate_count=policy.bootstrap_replicates,
        block_length=min(policy.bootstrap_block_candles, len(primary_returns)),
    )

    determinism = _determinism_receipts(artifact_files["determinism-receipts.jsonl"])
    diagnostics = parse_calibration_diagnostics(artifact_files["calibration-diagnostics.jsonl"])
    evidence = V03QualificationEvidence(
        integrity_verified=True,
        trend_determinism=determinism,
        calibration_complete=calibration_evidence_complete(diagnostics, policy),
        selectivity_replay=threshold_receipts,
        development_folds=_fold_evaluations(
            store=store,
            records=mapped,
            plan=plan,
            policy=policy,
        ),
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
        primary_return_to_drawdown=primary.return_to_drawdown,
        primary_aggregate_net_return=primary.net_return,
        primary_aggregate_max_drawdown=primary.maximum_drawdown,
        no_percentile_selectivity_return_to_drawdown=no_selectivity.return_to_drawdown,
        no_percentile_selectivity_max_drawdown=no_selectivity.maximum_drawdown,
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
        replay_verified=True,
        independent_verified=True,
    )
    report = evaluate_v0_3_development_qualification(evidence)
    return V03QualificationReplay(
        development_plan_bytes=development_plan_bytes,
        bootstrap=bootstrap,
        report=report,
    )


__all__ = [
    "V03QualificationReplay",
    "parse_simulation_config",
    "replay_candidate_v0_3_qualification",
]
