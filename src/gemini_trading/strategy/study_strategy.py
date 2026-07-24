"""Replayable simulation-only strategies for Candidate study experiments."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import cast

from gemini_trading.domain.experiment import ExperimentManifest
from gemini_trading.domain.order import OrderIntent, OrderSide, OrderType, TimeInForce
from gemini_trading.execution.simulator.precision import round_quantity_down
from gemini_trading.research.contracts import StrategyContext
from gemini_trading.research.errors import ReplayMismatchError
from gemini_trading.research.serialization import canonical_json_bytes
from gemini_trading.strategy.replay import validate_replay_strategy_id


class ScheduledAction(StrEnum):
    """Closed long-or-cash actions used by deterministic research schedules."""

    ENTER_LONG = "enter_long"
    EXIT_TO_CASH = "exit_to_cash"


@dataclass(frozen=True, slots=True)
class ReplayableStudyStrategy:
    """Manifest-serializable schedule for the local research simulator only."""

    strategy_id_value: str
    case_id: str
    events: tuple[tuple[int, ScheduledAction], ...]
    quantity_step: Decimal
    minimum_quantity: Decimal
    minimum_notional: Decimal
    production_eligible: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        validate_replay_strategy_id(self.strategy_id_value)
        if not self.case_id.strip():
            raise ValueError("case_id must not be empty")
        indexes = tuple(index for index, _ in self.events)
        if indexes != tuple(sorted(indexes)) or len(indexes) != len(set(indexes)):
            raise ValueError("scheduled strategy events must be unique and ordered")
        for value, field_name in (
            (self.quantity_step, "quantity_step"),
            (self.minimum_quantity, "minimum_quantity"),
            (self.minimum_notional, "minimum_notional"),
        ):
            if not value.is_finite() or value <= 0:
                raise ValueError(f"{field_name} must be finite and positive")

    @property
    def strategy_id(self) -> str:
        return self.strategy_id_value

    def configuration(self) -> tuple[tuple[str, str], ...]:
        """Return canonical non-executable reconstruction evidence."""

        event_payload = canonical_json_bytes(
            {"events": [[index, action.value] for index, action in self.events]}
        ).decode("utf-8").strip()
        return (
            ("case_id", self.case_id),
            ("events", event_payload),
            ("minimum_notional", format(self.minimum_notional, "f")),
            ("minimum_quantity", format(self.minimum_quantity, "f")),
            ("production_eligible", "false"),
            ("quantity_step", format(self.quantity_step, "f")),
            ("timing", "next_candle_via_research_engine"),
        )

    def on_candle(self, context: StrategyContext) -> tuple[OrderIntent, ...]:
        """Return at most one simulated long-or-cash intent for the current candle."""

        if context.active_orders:
            return ()
        action = dict(self.events).get(context.candle_index)
        if action is ScheduledAction.ENTER_LONG:
            if context.account.position_quantity > 0:
                return ()
            cash = context.account.cash - context.account.reserved_cash
            if cash <= 0:
                return ()
            quantity = round_quantity_down(cash / context.candle.close, self.quantity_step)
            if quantity < self.minimum_quantity:
                return ()
            if quantity * context.candle.close < self.minimum_notional:
                return ()
            return (
                OrderIntent(
                    side=OrderSide.BUY,
                    order_type=OrderType.MARKET,
                    quantity=quantity,
                    limit_price=None,
                    time_in_force=TimeInForce.BAR,
                ),
            )
        if action is ScheduledAction.EXIT_TO_CASH:
            quantity = context.account.position_quantity
            if quantity <= 0:
                return ()
            return (
                OrderIntent(
                    side=OrderSide.SELL_TO_CLOSE,
                    order_type=OrderType.MARKET,
                    quantity=quantity,
                    limit_price=None,
                    time_in_force=TimeInForce.BAR,
                ),
            )
        return ()


def reconstruct_study_strategy(manifest: ExperimentManifest) -> ReplayableStudyStrategy:
    """Reconstruct one closed-registry strategy from immutable manifest evidence."""

    validate_replay_strategy_id(manifest.strategy_id)
    configuration = dict(manifest.strategy_config)
    expected = {
        "case_id",
        "events",
        "minimum_notional",
        "minimum_quantity",
        "production_eligible",
        "quantity_step",
        "timing",
    }
    if set(configuration) != expected:
        raise ReplayMismatchError("strategy study experiment configuration does not match schema")
    if configuration["production_eligible"] != "false":
        raise ReplayMismatchError("strategy study experiment cannot be production eligible")
    if configuration["timing"] != "next_candle_via_research_engine":
        raise ReplayMismatchError("strategy study experiment timing is invalid")
    try:
        loaded: object = json.loads(configuration["events"])
        if not isinstance(loaded, dict) or set(loaded) != {"events"}:
            raise ValueError
        raw_events = loaded["events"]
        if not isinstance(raw_events, list):
            raise ValueError
        events: list[tuple[int, ScheduledAction]] = []
        for raw in cast(list[object], raw_events):
            if not isinstance(raw, list) or len(raw) != 2:
                raise ValueError
            index, action = raw
            if isinstance(index, bool) or not isinstance(index, int) or not isinstance(action, str):
                raise ValueError
            events.append((index, ScheduledAction(action)))
        strategy = ReplayableStudyStrategy(
            strategy_id_value=manifest.strategy_id,
            case_id=configuration["case_id"],
            events=tuple(events),
            quantity_step=Decimal(configuration["quantity_step"]),
            minimum_quantity=Decimal(configuration["minimum_quantity"]),
            minimum_notional=Decimal(configuration["minimum_notional"]),
        )
    except (KeyError, ValueError, ArithmeticError):
        raise ReplayMismatchError("strategy study experiment reconstruction failed") from None
    if strategy.configuration() != manifest.strategy_config:
        raise ReplayMismatchError("strategy study experiment configuration is not canonical")
    return strategy


__all__ = ["ReplayableStudyStrategy", "ScheduledAction", "reconstruct_study_strategy"]
