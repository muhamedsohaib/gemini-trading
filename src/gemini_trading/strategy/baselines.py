"""Deterministic trailing-only long/cash baselines for Candidate v0.1 studies."""

from dataclasses import dataclass, field
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext
from enum import StrEnum

from gemini_trading.domain.candle import Candle
from gemini_trading.domain.order import OrderIntent, OrderSide, OrderType, TimeInForce
from gemini_trading.execution.simulator.precision import round_quantity_down
from gemini_trading.research.contracts import StrategyContext

_CONTEXT = Context(prec=34, rounding=ROUND_HALF_EVEN)


class BaselineAction(StrEnum):
    """Closed long-or-cash actions emitted by baseline schedules."""

    CASH = "cash"
    ENTER_LONG = "enter_long"
    HOLD_LONG = "hold_long"
    EXIT_TO_CASH = "exit_to_cash"


@dataclass(frozen=True, slots=True)
class BaselineSchedule:
    """One exact-index immutable action schedule."""

    strategy_id: str
    actions: tuple[BaselineAction, ...]

    def __post_init__(self) -> None:
        if not self.strategy_id.strip():
            raise ValueError("strategy_id must not be empty")

    def action_for(self, candle_index: int) -> BaselineAction:
        """Return the action aligned to one exact candle index."""

        if candle_index < 0 or candle_index >= len(self.actions):
            return BaselineAction.CASH
        return self.actions[candle_index]


@dataclass(frozen=True, slots=True)
class _ScheduledBaseline:
    """Convert a precomputed baseline schedule into safe market intents."""

    schedule: BaselineSchedule = field(default_factory=lambda: BaselineSchedule("unset", ()))
    quantity_step: Decimal = Decimal("0.001")
    minimum_quantity: Decimal = Decimal("0.001")
    minimum_notional: Decimal = Decimal("5")
    production_eligible: bool = field(default=False, init=False)

    @property
    def strategy_id(self) -> str:
        """Return the locked baseline identity."""

        return self.schedule.strategy_id

    def configuration(self) -> tuple[tuple[str, str], ...]:
        """Return stable strategy configuration evidence."""

        return (
            ("strategy_id", self.strategy_id),
            ("decision_count", str(len(self.schedule.actions))),
            ("timing", "next_candle_via_research_engine"),
            ("production_eligible", "false"),
        )

    def on_candle(self, context: StrategyContext) -> tuple[OrderIntent, ...]:
        """Return at most one long-only intent for the exact current index."""

        if context.active_orders:
            return ()
        action = self.schedule.action_for(context.candle_index)
        if action is BaselineAction.ENTER_LONG:
            return self._enter(context)
        if action is BaselineAction.EXIT_TO_CASH:
            return self._exit(context)
        return ()

    def _enter(self, context: StrategyContext) -> tuple[OrderIntent, ...]:
        if context.account.position_quantity > 0:
            return ()
        available_cash = context.account.cash - context.account.reserved_cash
        if available_cash <= 0:
            return ()
        quantity = round_quantity_down(available_cash / context.candle.close, self.quantity_step)
        if quantity < self.minimum_quantity or quantity * context.candle.close < self.minimum_notional:
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

    def _exit(self, context: StrategyContext) -> tuple[OrderIntent, ...]:
        if context.account.position_quantity <= 0:
            return ()
        return (
            OrderIntent(
                side=OrderSide.SELL_TO_CLOSE,
                order_type=OrderType.MARKET,
                quantity=context.account.position_quantity,
                limit_price=None,
                time_in_force=TimeInForce.BAR,
            ),
        )


@dataclass(frozen=True, slots=True)
class CashBaseline(_ScheduledBaseline):
    schedule: BaselineSchedule = field(
        default_factory=lambda: BaselineSchedule("cash.v1", ()),
    )


@dataclass(frozen=True, slots=True)
class BuyHoldBaseline(_ScheduledBaseline):
    schedule: BaselineSchedule = field(
        default_factory=lambda: BaselineSchedule("buy_hold.v1", ()),
    )


@dataclass(frozen=True, slots=True)
class Ema2050Baseline(_ScheduledBaseline):
    schedule: BaselineSchedule = field(
        default_factory=lambda: BaselineSchedule("ema_20_50.v1", ()),
    )


@dataclass(frozen=True, slots=True)
class Donchian2010Baseline(_ScheduledBaseline):
    schedule: BaselineSchedule = field(
        default_factory=lambda: BaselineSchedule("donchian_20_10.v1", ()),
    )


@dataclass(frozen=True, slots=True)
class MeanReversionZ24Baseline(_ScheduledBaseline):
    schedule: BaselineSchedule = field(
        default_factory=lambda: BaselineSchedule("mean_reversion_z24.v1", ()),
    )


class BaselineSuite:
    """Factory for the five locked Candidate v0.1 comparison strategies."""

    @staticmethod
    def locked_v0_1() -> tuple[_ScheduledBaseline, ...]:
        """Return baseline prototypes in the approved comparison order."""

        return (
            CashBaseline(),
            BuyHoldBaseline(),
            Ema2050Baseline(),
            Donchian2010Baseline(),
            MeanReversionZ24Baseline(),
        )


def _state_action(currently_long: bool, should_be_long: bool) -> tuple[BaselineAction, bool]:
    if should_be_long and not currently_long:
        return BaselineAction.ENTER_LONG, True
    if not should_be_long and currently_long:
        return BaselineAction.EXIT_TO_CASH, False
    if currently_long:
        return BaselineAction.HOLD_LONG, True
    return BaselineAction.CASH, False


def _ema(values: tuple[Decimal, ...], span: int) -> tuple[Decimal, ...]:
    alpha = Decimal("2") / Decimal(span + 1)
    output: list[Decimal] = []
    with localcontext(_CONTEXT):
        current = values[0]
        output.append(current)
        for value in values[1:]:
            current = alpha * value + (Decimal("1") - alpha) * current
            output.append(current)
    return tuple(output)


def _cash_schedule(count: int) -> BaselineSchedule:
    return BaselineSchedule("cash.v1", (BaselineAction.CASH,) * count)


def _buy_hold_schedule(count: int) -> BaselineSchedule:
    actions = [BaselineAction.CASH] * count
    if count > 50:
        actions[50] = BaselineAction.ENTER_LONG
        actions[51:] = [BaselineAction.HOLD_LONG] * (count - 51)
    return BaselineSchedule("buy_hold.v1", tuple(actions))


def _ema_schedule(candles: tuple[Candle, ...]) -> BaselineSchedule:
    closes = tuple(candle.close for candle in candles)
    fast = _ema(closes, 20)
    slow = _ema(closes, 50)
    actions: list[BaselineAction] = []
    currently_long = False
    for index in range(len(candles)):
        should_be_long = index >= 49 and fast[index] > slow[index]
        action, currently_long = _state_action(currently_long, should_be_long)
        actions.append(action)
    return BaselineSchedule("ema_20_50.v1", tuple(actions))


def _donchian_schedule(candles: tuple[Candle, ...]) -> BaselineSchedule:
    actions: list[BaselineAction] = []
    currently_long = False
    for index, candle in enumerate(candles):
        if index < 20:
            should_be_long = currently_long
        elif currently_long:
            prior_low = min(item.low for item in candles[index - 10 : index])
            should_be_long = not candle.close < prior_low
        else:
            prior_high = max(item.high for item in candles[index - 20 : index])
            should_be_long = candle.close > prior_high
        action, currently_long = _state_action(currently_long, should_be_long)
        actions.append(action)
    return BaselineSchedule("donchian_20_10.v1", tuple(actions))


def _zscore_schedule(candles: tuple[Candle, ...]) -> BaselineSchedule:
    actions: list[BaselineAction] = []
    currently_long = False
    with localcontext(_CONTEXT):
        for index, candle in enumerate(candles):
            if index < 23:
                should_be_long = currently_long
            else:
                window = tuple(item.close for item in candles[index - 23 : index + 1])
                mean = sum(window, Decimal("0")) / Decimal(len(window))
                variance = sum((value - mean) ** 2 for value in window) / Decimal(len(window))
                if variance == 0:
                    should_be_long = currently_long
                else:
                    zscore = (candle.close - mean) / variance.sqrt()
                    should_be_long = zscore < Decimal("0") if currently_long else zscore <= Decimal("-1.5")
            action, currently_long = _state_action(currently_long, should_be_long)
            actions.append(action)
    return BaselineSchedule("mean_reversion_z24.v1", tuple(actions))


def build_baseline_schedules(candles: tuple[Candle, ...]) -> dict[str, BaselineSchedule]:
    """Build all locked baseline schedules from completed candles only."""

    if any(not candle.completed for candle in candles):
        raise ValueError("baseline schedules require completed candles")
    schedules = (
        _cash_schedule(len(candles)),
        _buy_hold_schedule(len(candles)),
        _ema_schedule(candles),
        _donchian_schedule(candles),
        _zscore_schedule(candles),
    )
    return {schedule.strategy_id: schedule for schedule in schedules}
