"""Thin long-or-cash strategy adapter for precomputed Candidate decisions."""

from dataclasses import dataclass, field
from decimal import Decimal

from gemini_trading.domain.order import OrderIntent, OrderSide, OrderType, TimeInForce
from gemini_trading.execution.simulator.precision import round_quantity_down
from gemini_trading.research.contracts import StrategyContext
from gemini_trading.strategy.arbitration import ArbitrationDecision
from gemini_trading.strategy.contracts import StrategyAction


def _positive(value: Decimal, field_name: str) -> None:
    if not value.is_finite() or value <= 0:
        raise ValueError(f"{field_name} must be finite and positive")


@dataclass(frozen=True, slots=True)
class CandidateDecisionSchedule:
    """Immutable exact-index lookup schedule for precomputed decisions."""

    decisions: tuple[ArbitrationDecision, ...]

    def __post_init__(self) -> None:
        indexes = tuple(decision.candle_index for decision in self.decisions)
        if indexes != tuple(sorted(indexes)) or len(indexes) != len(set(indexes)):
            raise ValueError("candidate decisions must have unique ordered candle indexes")

    def decision_for(self, candle_index: int) -> ArbitrationDecision | None:
        """Return only the decision aligned to the exact current candle index."""

        for decision in self.decisions:
            if decision.candle_index == candle_index:
                return decision
            if decision.candle_index > candle_index:
                break
        return None


@dataclass(frozen=True, slots=True)
class CandidateMultiModelStrategy:
    """Convert immutable Candidate decisions into safe simulated order intents."""

    schedule: CandidateDecisionSchedule
    quantity_step: Decimal
    minimum_quantity: Decimal
    minimum_notional: Decimal
    strategy_id: str = field(default="candidate.multi_model.v0_1", init=False)
    production_eligible: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        _positive(self.quantity_step, "quantity_step")
        _positive(self.minimum_quantity, "minimum_quantity")
        _positive(self.minimum_notional, "minimum_notional")

    def configuration(self) -> tuple[tuple[str, str], ...]:
        """Return stable non-executable strategy configuration evidence."""

        return (
            ("decision_count", str(len(self.schedule.decisions))),
            ("quantity_step", format(self.quantity_step, "f")),
            ("minimum_quantity", format(self.minimum_quantity, "f")),
            ("minimum_notional", format(self.minimum_notional, "f")),
            ("timing", "next_candle_via_research_engine"),
            ("production_eligible", "false"),
        )

    def on_candle(self, context: StrategyContext) -> tuple[OrderIntent, ...]:
        """Return at most one long-only intent from the exact schedule row."""

        if context.active_orders:
            return ()
        decision = self.schedule.decision_for(context.candle_index)
        if decision is None:
            return ()
        if decision.action is StrategyAction.ENTER_LONG:
            return self._buy_intent(context)
        if decision.action is StrategyAction.EXIT_TO_CASH:
            return self._sell_intent(context)
        return ()

    def _buy_intent(self, context: StrategyContext) -> tuple[OrderIntent, ...]:
        if context.account.position_quantity > 0:
            return ()
        available_cash = context.account.cash - context.account.reserved_cash
        if available_cash <= 0:
            return ()
        quantity = round_quantity_down(
            available_cash / context.candle.close,
            self.quantity_step,
        )
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

    def _sell_intent(self, context: StrategyContext) -> tuple[OrderIntent, ...]:
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
