"""Chronological deterministic backtesting engine for one long-only spot instrument."""

import hashlib
from dataclasses import dataclass, replace
from decimal import Decimal

from gemini_trading.domain.account import AccountSnapshot, LedgerEntry
from gemini_trading.domain.candle import Candle
from gemini_trading.domain.experiment import ExperimentManifest, TimingPolicy
from gemini_trading.domain.fill import Fill
from gemini_trading.domain.order import (
    OrderIntent,
    OrderSide,
    OrderStatus,
    OrderType,
    SimulatedOrder,
    TimeInForce,
)
from gemini_trading.execution.simulator.fills import evaluate_order
from gemini_trading.research.accounting import apply_fill, mark_to_market, verify_reconciliation
from gemini_trading.research.config import SimulationConfig, serialize_simulation_config
from gemini_trading.research.contracts import Strategy, StrategyContext, StrategyDecision
from gemini_trading.research.dataset_reader import VerifiedDataset
from gemini_trading.research.errors import (
    ChronologyViolationError,
    InvalidExperimentConfigError,
    StrategyContractError,
)
from gemini_trading.research.identity import experiment_id

_ACTIVE_STATUSES = {OrderStatus.ACCEPTED, OrderStatus.PARTIALLY_FILLED}
_ZERO = Decimal("0")


@dataclass(frozen=True, slots=True)
class BacktestEvidence:
    """Immutable in-memory evidence from a deterministic backtest state."""

    experiment_manifest: ExperimentManifest
    decisions: tuple[StrategyDecision, ...]
    orders: tuple[SimulatedOrder, ...]
    fills: tuple[Fill, ...]
    ledger: tuple[LedgerEntry, ...]
    account_series: tuple[AccountSnapshot, ...]
    rejection_records: tuple[dict[str, object], ...]
    terminal_account: AccountSnapshot


class BacktestEngine:
    """Process one verified candle stream in strict chronological order."""

    def __init__(
        self,
        dataset: VerifiedDataset,
        manifest: ExperimentManifest,
        config: SimulationConfig,
        strategy: Strategy,
    ) -> None:
        self._validate_inputs(dataset, manifest, config, strategy)
        self._dataset = dataset
        self._manifest = manifest
        self._config = config
        self._strategy = strategy
        self._experiment_id = experiment_id(manifest)
        self._account = AccountSnapshot.initial(manifest.initial_cash)
        self._decisions: list[StrategyDecision] = []
        self._orders: dict[str, SimulatedOrder] = {}
        self._order_ids: list[str] = []
        self._fills: list[Fill] = []
        self._ledger: list[LedgerEntry] = []
        self._account_series: list[AccountSnapshot] = []
        self._rejections: list[dict[str, object]] = []
        self._last_candle_index = -1
        self._last_candle: Candle | None = None
        self._finalized = False

    @staticmethod
    def _validate_inputs(
        dataset: VerifiedDataset,
        manifest: ExperimentManifest,
        config: SimulationConfig,
        strategy: Strategy,
    ) -> None:
        if manifest.dataset_id != dataset.manifest.dataset_id:
            raise InvalidExperimentConfigError("experiment dataset identity mismatch")
        if manifest.canonical_sha256 != dataset.manifest.canonical_sha256:
            raise InvalidExperimentConfigError("experiment canonical hash mismatch")
        if manifest.strategy_id != strategy.strategy_id:
            raise InvalidExperimentConfigError("experiment strategy identity mismatch")
        if tuple(manifest.strategy_config) != tuple(strategy.configuration()):
            raise InvalidExperimentConfigError("experiment strategy configuration mismatch")
        if manifest.timing_policy is not config.timing_policy:
            raise InvalidExperimentConfigError("experiment timing policy mismatch")
        if manifest.limit_fill_policy is not config.limit_fill_policy:
            raise InvalidExperimentConfigError("experiment limit-fill policy mismatch")
        if manifest.default_time_in_force is not config.default_time_in_force:
            raise InvalidExperimentConfigError("experiment time-in-force mismatch")
        if manifest.max_active_candles != config.max_active_candles:
            raise InvalidExperimentConfigError("experiment order-lifetime mismatch")
        config_hash = hashlib.sha256(serialize_simulation_config(config)).hexdigest()
        if manifest.simulation_config_sha256 != config_hash:
            raise InvalidExperimentConfigError("experiment simulation configuration mismatch")

    @property
    def evidence(self) -> BacktestEvidence:
        """Return an immutable snapshot of all evidence accumulated so far."""

        return BacktestEvidence(
            experiment_manifest=self._manifest,
            decisions=tuple(self._decisions),
            orders=tuple(self._orders[order_id] for order_id in self._order_ids),
            fills=tuple(self._fills),
            ledger=tuple(self._ledger),
            account_series=tuple(self._account_series),
            rejection_records=tuple(dict(record) for record in self._rejections),
            terminal_account=self._account,
        )

    def _active_orders(self) -> tuple[SimulatedOrder, ...]:
        return tuple(
            self._orders[order_id]
            for order_id in sorted(self._order_ids)
            if self._orders[order_id].status in _ACTIVE_STATUSES
        )

    def _record_rejection(
        self,
        *,
        candle_index: int,
        decision_sequence: int,
        intent_sequence: int,
        intent: OrderIntent,
        reason: str,
    ) -> None:
        self._rejections.append(
            {
                "candle_index": candle_index,
                "decision_sequence": decision_sequence,
                "intent_sequence": intent_sequence,
                "side": intent.side.value,
                "order_type": intent.order_type.value,
                "reason": reason,
            }
        )

    def _evaluate_orders(
        self,
        order_ids: tuple[str, ...],
        candle_index: int,
        candle: Candle,
        consumed_volume: Decimal,
        *,
        market_reference_price: Decimal | None = None,
    ) -> Decimal:
        for order_id in sorted(order_ids):
            order = self._orders[order_id]
            if order.status not in _ACTIVE_STATUSES:
                continue
            evaluation = evaluate_order(
                order,
                candle,
                self._account,
                self._config,
                candle_index,
                consumed_volume,
                market_reference_price,
            )
            consumed_volume = evaluation.consumed_volume
            updated_order = evaluation.order
            if evaluation.fill is not None:
                self._account, ledger_entry = apply_fill(
                    self._account,
                    order,
                    evaluation.fill,
                    len(self._ledger) + 1,
                )
                self._fills.append(evaluation.fill)
                self._ledger.append(ledger_entry)

            if updated_order.status in _ACTIVE_STATUSES and candle_index >= (
                updated_order.eligible_candle_index
            ):
                if updated_order.time_in_force in {TimeInForce.IOC, TimeInForce.BAR}:
                    updated_order = replace(updated_order, status=OrderStatus.CANCELLED)
                elif candle_index >= updated_order.expires_after_candle_index:
                    updated_order = replace(updated_order, status=OrderStatus.EXPIRED)
            self._orders[order_id] = updated_order
        return consumed_volume

    def _intent_conflict_reason(self, intents: tuple[OrderIntent, ...]) -> str | None:
        buy_count = sum(intent.side is OrderSide.BUY for intent in intents)
        sell_count = sum(intent.side is OrderSide.SELL_TO_CLOSE for intent in intents)
        if buy_count > 1 or sell_count > 1 or (buy_count > 0 and sell_count > 0):
            return "conflicting_intents"
        return None

    def _accept_intents(
        self,
        intents: tuple[OrderIntent, ...],
        candle_index: int,
        decision_sequence: int,
    ) -> tuple[str, ...]:
        conflict_reason = self._intent_conflict_reason(intents)
        if conflict_reason is not None:
            for intent_sequence, intent in enumerate(intents, start=1):
                self._record_rejection(
                    candle_index=candle_index,
                    decision_sequence=decision_sequence,
                    intent_sequence=intent_sequence,
                    intent=intent,
                    reason=conflict_reason,
                )
            return ()

        active_sides = {order.side for order in self._active_orders()}
        accepted_ids: list[str] = []
        for intent_sequence, intent in enumerate(intents, start=1):
            reason: str | None = None
            if intent.side in active_sides:
                reason = "active_order_same_side"
            elif (
                intent.side is OrderSide.SELL_TO_CLOSE
                and intent.quantity > self._account.position_quantity
            ):
                reason = "insufficient_position"
            elif intent.quantity < self._config.min_quantity:
                reason = "below_min_quantity"
            elif intent.order_type is OrderType.LIMIT:
                if intent.limit_price is None or intent.limit_price % self._config.price_tick != 0:
                    reason = "invalid_limit_tick"
                elif intent.limit_price * intent.quantity < self._config.min_notional:
                    reason = "below_min_notional"

            if reason is not None:
                self._record_rejection(
                    candle_index=candle_index,
                    decision_sequence=decision_sequence,
                    intent_sequence=intent_sequence,
                    intent=intent,
                    reason=reason,
                )
                continue

            identity_input = (
                f"{self._experiment_id}:{decision_sequence}:{intent_sequence}"
            ).encode()
            order_id = hashlib.sha256(identity_input).hexdigest()
            if order_id in self._orders:
                raise ChronologyViolationError("duplicate deterministic order identity")
            if self._config.timing_policy is TimingPolicy.SAME_CLOSE_DIAGNOSTIC:
                eligible_index = candle_index + self._config.latency_bars
            else:
                eligible_index = candle_index + 1 + self._config.latency_bars
            expires_after = (
                eligible_index
                if intent.time_in_force in {TimeInForce.IOC, TimeInForce.BAR}
                else eligible_index + self._config.max_active_candles - 1
            )
            order = SimulatedOrder(
                order_id=order_id,
                decision_sequence=decision_sequence,
                intent_sequence=intent_sequence,
                created_candle_index=candle_index,
                eligible_candle_index=eligible_index,
                expires_after_candle_index=expires_after,
                side=intent.side,
                order_type=intent.order_type,
                requested_quantity=intent.quantity,
                filled_quantity=_ZERO,
                limit_price=intent.limit_price,
                time_in_force=intent.time_in_force,
                status=OrderStatus.ACCEPTED,
            )
            self._orders[order_id] = order
            self._order_ids.append(order_id)
            accepted_ids.append(order_id)
            active_sides.add(intent.side)
        return tuple(accepted_ids)

    def process_candle(self, candle_index: int, candle: Candle) -> None:
        """Process exactly one authoritative completed candle once."""

        if self._finalized:
            raise ChronologyViolationError("cannot process candles after finalization")
        if candle_index <= self._last_candle_index:
            reason = "duplicate" if candle_index == self._last_candle_index else "out-of-order"
            raise ChronologyViolationError(f"{reason} candle event")
        if candle_index != self._last_candle_index + 1:
            raise ChronologyViolationError("candle index gap")
        if candle_index >= len(self._dataset.candles):
            raise ChronologyViolationError("candle index exceeds verified dataset")
        if candle != self._dataset.candles[candle_index]:
            raise ChronologyViolationError("candle identity does not match verified dataset")
        if not candle.completed:
            raise ChronologyViolationError("incomplete candle cannot enter research engine")
        if candle.instrument != self._dataset.manifest.instrument:
            raise ChronologyViolationError("candle instrument identity mismatch")
        if candle.timeframe is not self._dataset.manifest.timeframe:
            raise ChronologyViolationError("candle timeframe identity mismatch")

        consumed_volume = self._evaluate_orders(
            tuple(order.order_id for order in self._active_orders()),
            candle_index,
            candle,
            _ZERO,
        )
        self._account = mark_to_market(self._account, candle.close)
        context = StrategyContext(
            candle_index=candle_index,
            candle=candle,
            account=self._account,
            active_orders=self._active_orders(),
        )
        intents = self._strategy.on_candle(context)
        if not isinstance(intents, tuple) or not all(
            isinstance(intent, OrderIntent) for intent in intents
        ):
            raise StrategyContractError("strategy must return a tuple of OrderIntent values")
        decision_sequence = len(self._decisions) + 1
        decision = StrategyDecision(
            decision_sequence=decision_sequence,
            candle_index=candle_index,
            candle_open_time=candle.open_time,
            intents=intents,
        )
        self._decisions.append(decision)
        accepted_ids = self._accept_intents(intents, candle_index, decision_sequence)

        if self._config.timing_policy is TimingPolicy.SAME_CLOSE_DIAGNOSTIC:
            eligible_ids = tuple(
                order_id
                for order_id in accepted_ids
                if self._orders[order_id].eligible_candle_index == candle_index
            )
            consumed_volume = self._evaluate_orders(
                eligible_ids,
                candle_index,
                candle,
                consumed_volume,
                market_reference_price=candle.close,
            )
            self._account = mark_to_market(self._account, candle.close)

        self._account_series.append(self._account)
        self._last_candle_index = candle_index
        self._last_candle = candle

    def finalize(self) -> BacktestEvidence:
        """Cancel remaining orders, reconcile accounting, and freeze terminal evidence."""

        if self._finalized:
            return self.evidence
        for order_id in self._order_ids:
            order = self._orders[order_id]
            if order.status in _ACTIVE_STATUSES:
                self._orders[order_id] = replace(order, status=OrderStatus.CANCELLED)
        if self._last_candle is not None:
            self._account = mark_to_market(self._account, self._last_candle.close)
            if self._account_series:
                self._account_series[-1] = self._account
        verify_reconciliation(self._manifest.initial_cash, self._account, tuple(self._ledger))
        self._finalized = True
        return self.evidence


def run_backtest(
    dataset: VerifiedDataset,
    manifest: ExperimentManifest,
    config: SimulationConfig,
    strategy: Strategy,
) -> BacktestEvidence:
    """Run one verified dataset to deterministic terminal evidence."""

    engine = BacktestEngine(dataset, manifest, config, strategy)
    for candle_index, candle in enumerate(dataset.candles):
        engine.process_candle(candle_index, candle)
    return engine.finalize()
