"""RED tests for the Candidate v0.1 long/cash strategy adapter."""

from decimal import Decimal

from gemini_trading.domain.account import AccountSnapshot
from gemini_trading.domain.order import OrderSide, OrderType, TimeInForce
from gemini_trading.research.contracts import StrategyContext
from gemini_trading.strategy.arbitration import (
    ArbitrationDecision,
    ArbitrationInput,
    MultiModelArbiter,
)
from gemini_trading.strategy.candidate import CandidateDecisionSchedule, CandidateMultiModelStrategy
from gemini_trading.strategy.contracts import RegimeState, SpecialistKind
from gemini_trading.strategy.policy import CandidatePolicy
from strategy_fixture_support import btc_candle


def account_with_position(
    quantity: Decimal,
    *,
    cash: Decimal = Decimal("1000"),
    entry_price: Decimal = Decimal("100"),
    mark_price: Decimal = Decimal("100"),
) -> AccountSnapshot:
    equity = cash + quantity * mark_price
    return AccountSnapshot(
        cash=cash,
        reserved_cash=Decimal("0"),
        position_quantity=quantity,
        average_entry_price=entry_price if quantity > 0 else Decimal("0"),
        realized_pnl=Decimal("0"),
        cumulative_fees=Decimal("0"),
        cumulative_execution_costs=Decimal("0"),
        marked_equity=equity,
        peak_equity=equity,
        drawdown=Decimal("0"),
    )


def entry_decision(candle_index: int = 42) -> ArbitrationDecision:
    return MultiModelArbiter(CandidatePolicy.locked_v0_1()).decide(
        ArbitrationInput(
            candle_index=candle_index,
            regime=RegimeState.TRENDING,
            trend_probability=Decimal("0.62"),
            trend_expected_gross_return=Decimal("0.0071"),
            mean_reversion_probability=Decimal("0.45"),
            mean_reversion_expected_gross_return=Decimal("0"),
            currently_long=False,
            active_specialist=None,
            hold_age=0,
            cooldown_remaining=0,
            indeterminate_streak=0,
            entry_price=None,
            highest_close_since_entry=None,
            current_close=Decimal("100"),
            current_low=Decimal("99"),
            atr24=Decimal("2"),
            current_stop=None,
            stretch_active=False,
            base_hurdle_bps=Decimal("60"),
        )
    )


def exit_decision(candle_index: int = 42) -> ArbitrationDecision:
    return MultiModelArbiter(CandidatePolicy.locked_v0_1()).decide(
        ArbitrationInput(
            candle_index=candle_index,
            regime=RegimeState.TRENDING,
            trend_probability=Decimal("0.45"),
            trend_expected_gross_return=Decimal("0"),
            mean_reversion_probability=Decimal("0.50"),
            mean_reversion_expected_gross_return=Decimal("0"),
            currently_long=True,
            active_specialist=SpecialistKind.TREND,
            hold_age=2,
            cooldown_remaining=0,
            indeterminate_streak=0,
            entry_price=Decimal("100"),
            highest_close_since_entry=Decimal("102"),
            current_close=Decimal("100"),
            current_low=Decimal("99"),
            atr24=Decimal("2"),
            current_stop=Decimal("90"),
            stretch_active=False,
            base_hurdle_bps=Decimal("60"),
        )
    )


def strategy_for(*decisions: ArbitrationDecision) -> CandidateMultiModelStrategy:
    return CandidateMultiModelStrategy(
        schedule=CandidateDecisionSchedule(decisions),
        quantity_step=Decimal("0.001"),
        minimum_quantity=Decimal("0.001"),
        minimum_notional=Decimal("5"),
    )


def test_enter_long_returns_one_market_buy_sized_from_available_cash() -> None:
    strategy = strategy_for(entry_decision())
    context = StrategyContext(
        candle_index=42,
        candle=btc_candle(42, close=Decimal("100")),
        account=AccountSnapshot.initial(Decimal("10000")),
        active_orders=(),
    )

    intents = strategy.on_candle(context)

    assert len(intents) == 1
    assert intents[0].side is OrderSide.BUY
    assert intents[0].order_type is OrderType.MARKET
    assert intents[0].time_in_force is TimeInForce.BAR
    assert intents[0].quantity == Decimal("100.000")
    assert strategy.strategy_id == "candidate.multi_model.v0_1"
    assert strategy.production_eligible is False


def test_exit_to_cash_never_sells_above_the_current_position() -> None:
    strategy = strategy_for(exit_decision())
    context = StrategyContext(
        candle_index=42,
        candle=btc_candle(42, close=Decimal("100")),
        account=account_with_position(Decimal("1.234")),
        active_orders=(),
    )

    intents = strategy.on_candle(context)

    assert len(intents) == 1
    assert intents[0].side is OrderSide.SELL_TO_CLOSE
    assert intents[0].quantity == Decimal("1.234")


def test_adapter_refuses_pyramiding_and_empty_position_sells() -> None:
    candle = btc_candle(42, close=Decimal("100"))
    buy_strategy = strategy_for(entry_decision())
    sell_strategy = strategy_for(exit_decision())

    buy_intents = buy_strategy.on_candle(
        StrategyContext(
            candle_index=42,
            candle=candle,
            account=account_with_position(Decimal("1")),
            active_orders=(),
        )
    )
    sell_intents = sell_strategy.on_candle(
        StrategyContext(
            candle_index=42,
            candle=candle,
            account=AccountSnapshot.initial(Decimal("10000")),
            active_orders=(),
        )
    )

    assert buy_intents == ()
    assert sell_intents == ()


def test_below_minimum_order_remains_in_cash() -> None:
    strategy = strategy_for(entry_decision())
    context = StrategyContext(
        candle_index=42,
        candle=btc_candle(42, close=Decimal("10000")),
        account=AccountSnapshot.initial(Decimal("1")),
        active_orders=(),
    )

    assert strategy.on_candle(context) == ()
