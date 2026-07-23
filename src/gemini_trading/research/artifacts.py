"""Canonical immutable artifacts and result identity for deterministic backtests."""

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from gemini_trading.data.errors import RawStorageConflictError
from gemini_trading.data.storage.local_immutable import write_immutable
from gemini_trading.domain.account import AccountSnapshot, LedgerEntry
from gemini_trading.domain.experiment import LimitFillPolicy, TimingPolicy
from gemini_trading.domain.fill import Fill
from gemini_trading.domain.order import OrderIntent, SimulatedOrder
from gemini_trading.research.contracts import StrategyDecision
from gemini_trading.research.engine import BacktestEvidence
from gemini_trading.research.errors import ArtifactConflictError
from gemini_trading.research.identity import experiment_id, serialize_experiment_manifest
from gemini_trading.research.metrics import (
    BacktestMetrics,
    CompletedTrade,
    calculate_metrics,
    completed_trades,
)
from gemini_trading.research.serialization import canonical_json_bytes, canonical_jsonl_bytes

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_RESULT_SCHEMA_VERSION = "research-result-v1"
_VERIFICATION_SCHEMA_VERSION = "research-verification-v1"


def _intent_payload(intent: OrderIntent) -> dict[str, object]:
    return {
        "side": intent.side.value,
        "order_type": intent.order_type.value,
        "quantity": intent.quantity,
        "limit_price": intent.limit_price,
        "time_in_force": intent.time_in_force.value,
    }


def _decision_payload(decision: StrategyDecision) -> dict[str, object]:
    return {
        "decision_sequence": decision.decision_sequence,
        "candle_index": decision.candle_index,
        "candle_open_time": decision.candle_open_time,
        "intents": [_intent_payload(intent) for intent in decision.intents],
    }


def _order_payload(order: SimulatedOrder) -> dict[str, object]:
    return {
        "order_id": order.order_id,
        "decision_sequence": order.decision_sequence,
        "intent_sequence": order.intent_sequence,
        "created_candle_index": order.created_candle_index,
        "eligible_candle_index": order.eligible_candle_index,
        "expires_after_candle_index": order.expires_after_candle_index,
        "side": order.side.value,
        "order_type": order.order_type.value,
        "requested_quantity": order.requested_quantity,
        "filled_quantity": order.filled_quantity,
        "remaining_quantity": order.remaining_quantity,
        "limit_price": order.limit_price,
        "time_in_force": order.time_in_force.value,
        "status": order.status.value,
    }


def _fill_payload(fill: Fill) -> dict[str, object]:
    return {
        "fill_id": fill.fill_id,
        "order_id": fill.order_id,
        "candle_index": fill.candle_index,
        "candle_open_time": fill.candle_open_time,
        "quantity": fill.quantity,
        "reference_price": fill.reference_price,
        "fill_price": fill.fill_price,
        "notional": fill.notional,
        "fee": fill.fee,
        "spread_cost": fill.spread_cost,
        "slippage_cost": fill.slippage_cost,
        "price_was_rounded": fill.price_was_rounded,
        "quantity_was_rounded": fill.quantity_was_rounded,
    }


def _ledger_payload(entry: LedgerEntry) -> dict[str, object]:
    return {
        "sequence": entry.sequence,
        "event_type": entry.event_type,
        "order_id": entry.order_id,
        "fill_id": entry.fill_id,
        "cash_delta": entry.cash_delta,
        "position_delta": entry.position_delta,
        "fee_delta": entry.fee_delta,
        "resulting_cash": entry.resulting_cash,
        "resulting_position": entry.resulting_position,
    }


def _account_payload(sequence: int, account: AccountSnapshot) -> dict[str, object]:
    return {
        "sequence": sequence,
        "cash": account.cash,
        "reserved_cash": account.reserved_cash,
        "position_quantity": account.position_quantity,
        "average_entry_price": account.average_entry_price,
        "position_cost_basis": account.position_cost_basis,
        "realized_pnl": account.realized_pnl,
        "cumulative_fees": account.cumulative_fees,
        "cumulative_execution_costs": account.cumulative_execution_costs,
        "marked_equity": account.marked_equity,
        "peak_equity": account.peak_equity,
        "drawdown": account.drawdown,
    }


def _trade_payload(trade: CompletedTrade) -> dict[str, object]:
    return {
        "sequence": trade.sequence,
        "entry_fill_ids": list(trade.entry_fill_ids),
        "exit_fill_ids": list(trade.exit_fill_ids),
        "entry_cost": trade.entry_cost,
        "exit_proceeds": trade.exit_proceeds,
        "realized_pnl": trade.realized_pnl,
        "winning": trade.winning,
    }


def _metrics_payload(metrics: BacktestMetrics) -> dict[str, object]:
    return {
        "starting_equity": metrics.starting_equity,
        "ending_equity": metrics.ending_equity,
        "gross_return": metrics.gross_return,
        "net_return": metrics.net_return,
        "realized_pnl": metrics.realized_pnl,
        "unrealized_pnl": metrics.unrealized_pnl,
        "total_fees": metrics.total_fees,
        "total_execution_costs": metrics.total_execution_costs,
        "maximum_drawdown": metrics.maximum_drawdown,
        "exposure_fraction": metrics.exposure_fraction,
        "order_count": metrics.order_count,
        "rejection_count": metrics.rejection_count,
        "fill_count": metrics.fill_count,
        "partial_fill_count": metrics.partial_fill_count,
        "trade_count": metrics.trade_count,
        "win_rate": metrics.win_rate,
    }


def _is_promotable(evidence: BacktestEvidence) -> bool:
    manifest = evidence.experiment_manifest
    return (
        manifest.timing_policy is TimingPolicy.NEXT_CANDLE
        and manifest.limit_fill_policy is LimitFillPolicy.CONSERVATIVE
    )


@dataclass(frozen=True, slots=True)
class ResearchArtifacts:
    """Complete deterministic artifact bytes for one successful experiment."""

    experiment_id: str
    result_id: str
    terminal_status: str
    promotable: bool
    files: tuple[tuple[str, bytes], ...]

    def __post_init__(self) -> None:
        if _SHA256_PATTERN.fullmatch(self.experiment_id) is None:
            raise ValueError("experiment_id must be a lowercase SHA-256 digest")
        if _SHA256_PATTERN.fullmatch(self.result_id) is None:
            raise ValueError("result_id must be a lowercase SHA-256 digest")
        if self.terminal_status != "completed":
            raise ValueError("successful research artifacts require completed status")
        names = tuple(name for name, _ in self.files)
        if names != tuple(sorted(names)) or len(names) != len(set(names)):
            raise ValueError("artifact files must be uniquely sorted by name")
        if "result-manifest.json" not in names:
            raise ValueError("result-manifest.json is required")

    def artifact_bytes(self, name: str) -> bytes:
        """Return exact stored bytes for one required artifact name."""

        for artifact_name, content in self.files:
            if artifact_name == name:
                return content
        raise KeyError(name)


def build_artifacts(evidence: BacktestEvidence) -> ResearchArtifacts:
    """Build byte-identical canonical evidence and a content-derived result identity."""

    current_experiment_id = experiment_id(evidence.experiment_manifest)
    metrics = calculate_metrics(evidence)
    trades = completed_trades(evidence)
    promotable = _is_promotable(evidence)
    core_files: dict[str, bytes] = {
        "experiment-manifest.json": serialize_experiment_manifest(
            evidence.experiment_manifest
        ),
        "decisions.jsonl": canonical_jsonl_bytes(
            _decision_payload(decision) for decision in evidence.decisions
        ),
        "orders.jsonl": canonical_jsonl_bytes(
            _order_payload(order) for order in evidence.orders
        ),
        "rejections.jsonl": canonical_jsonl_bytes(evidence.rejection_records),
        "fills.jsonl": canonical_jsonl_bytes(_fill_payload(fill) for fill in evidence.fills),
        "cash-ledger.jsonl": canonical_jsonl_bytes(
            _ledger_payload(entry) for entry in evidence.ledger
        ),
        "account-series.jsonl": canonical_jsonl_bytes(
            _account_payload(sequence, account)
            for sequence, account in enumerate(evidence.account_series, start=1)
        ),
        "trades.jsonl": canonical_jsonl_bytes(_trade_payload(trade) for trade in trades),
        "metrics.json": canonical_json_bytes(_metrics_payload(metrics)),
        "verification.json": canonical_json_bytes(
            {
                "schema_version": _VERIFICATION_SCHEMA_VERSION,
                "experiment_id": current_experiment_id,
                "status": "completed",
                "promotable": promotable,
                "checks": [
                    "accounting_reconciled",
                    "canonical_artifacts_built",
                    "completed_candle_chronology",
                ],
            }
        ),
    }
    artifact_hashes = tuple(
        sorted(
            (name, hashlib.sha256(content).hexdigest())
            for name, content in core_files.items()
        )
    )
    result_identity_payload: dict[str, object] = {
        "schema_version": _RESULT_SCHEMA_VERSION,
        "experiment_id": current_experiment_id,
        "artifacts": [list(item) for item in artifact_hashes],
        "terminal_status": "completed",
        "promotable": promotable,
    }
    result_id = hashlib.sha256(canonical_json_bytes(result_identity_payload)).hexdigest()
    result_manifest = canonical_json_bytes(
        {**result_identity_payload, "result_id": result_id}
    )
    files = tuple(sorted((*core_files.items(), ("result-manifest.json", result_manifest))))
    return ResearchArtifacts(
        experiment_id=current_experiment_id,
        result_id=result_id,
        terminal_status="completed",
        promotable=promotable,
        files=files,
    )


@dataclass(frozen=True, slots=True)
class LocalResearchStore:
    """Immutable local store rooted beneath one explicit output directory."""

    root: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "root", Path(self.root))

    def _experiment_directory(self, experiment_id_value: str) -> Path:
        if _SHA256_PATTERN.fullmatch(experiment_id_value) is None:
            raise ValueError("invalid research experiment identity")
        return self.root / "data" / "research" / experiment_id_value

    def write(self, artifacts: ResearchArtifacts) -> tuple[tuple[str, Path], ...]:
        """Publish every artifact once; accept only byte-identical reruns."""

        directory = self._experiment_directory(artifacts.experiment_id)
        paths: list[tuple[str, Path]] = []
        for name, content in artifacts.files:
            path = directory / name
            try:
                write_immutable(path, content)
            except RawStorageConflictError:
                raise ArtifactConflictError(f"immutable research artifact conflicts: {name}") from None
            paths.append((name, path))
        return tuple(paths)
