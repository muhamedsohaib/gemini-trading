"""Tests for the read-only strategy contract and scripted fixture."""

from dataclasses import fields, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from gemini_trading.domain.account import AccountSnapshot
from gemini_trading.domain.candle import Candle
from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.order import OrderIntent, OrderSide, OrderType, TimeInForce
from gemini_trading.domain.timeframe import Timeframe
from gemini_trading.research.contracts import StrategyContext
from gemini_trading.research.errors import StrategyContractError
from gemini_trading.research.fixture_strategy import ScriptedFixtureStrategy


def _candle(*, completed: bool = True) -> Candle:
    return Candle(
        instrument=Instrument("ETHUSDT", "ETH", "USDT"),
        timeframe=Timeframe.H4,
        open_time=datetime(2025, 1, 1, tzinfo=UTC),
        close_time=datetime(2025, 1, 1, tzinfo=UTC)
        + timedelta(hours=4)
        - timedelta(milliseconds=1),
        open=Decimal("100"),
        high=Decimal("110"),
        low=Decimal("90"),
        close=Decimal("105"),
        volume=Decimal("20"),
        completed=completed,
        source_provider="binance_spot",
    )


def _market_intent(side: OrderSide) -> OrderIntent:
    return OrderIntent(
        side=side,
        order_type=OrderType.MARKET,
        quantity=Decimal("1"),
        limit_price=None,
        time_in_force=TimeInForce.BAR,
    )


def _context(candle_index: int = 0) -> StrategyContext:
    return StrategyContext(
        candle_index=candle_index,
        candle=_candle(),
        account=AccountSnapshot.initial(Decimal("1000")),
        active_orders=(),
    )


def test_context_contains_only_current_completed_state() -> None:
    context = _context()

    assert tuple(field.name for field in fields(StrategyContext)) == (
        "candle_index",
        "candle",
        "account",
        "active_orders",
    )
    assert context.candle.completed is True
    assert not hasattr(context, "future_candles")
    assert not hasattr(context, "provider")


def test_context_rejects_incomplete_candle() -> None:
    with pytest.raises(StrategyContractError, match="completed"):
        replace(_context(), candle=_candle(completed=False))


def test_scripted_fixture_is_deterministic_and_non_production() -> None:
    buy = _market_intent(OrderSide.BUY)
    sell = _market_intent(OrderSide.SELL_TO_CLOSE)
    strategy = ScriptedFixtureStrategy(script=((2, (sell,)), (0, (buy,))))

    first = strategy.on_candle(_context(candle_index=0))
    second = strategy.on_candle(_context(candle_index=0))

    assert first == second == (buy,)
    assert strategy.on_candle(_context(candle_index=1)) == ()
    assert strategy.strategy_id == "fixture.scripted.v1"
    assert strategy.production_eligible is False
    assert strategy.script == ((0, (buy,)), (2, (sell,)))


def test_scripted_fixture_configuration_is_stable_across_input_order() -> None:
    buy = _market_intent(OrderSide.BUY)
    sell = _market_intent(OrderSide.SELL_TO_CLOSE)

    first = ScriptedFixtureStrategy(script=((2, (sell,)), (0, (buy,))))
    second = ScriptedFixtureStrategy(script=((0, (buy,)), (2, (sell,))))

    assert first.configuration() == second.configuration()
    assert first.configuration()[0][0] == "script"


def test_scripted_fixture_rejects_duplicate_or_negative_indexes() -> None:
    buy = _market_intent(OrderSide.BUY)

    with pytest.raises(StrategyContractError, match="duplicate"):
        ScriptedFixtureStrategy(script=((0, (buy,)), (0, (buy,))))
    with pytest.raises(StrategyContractError, match="non-negative"):
        ScriptedFixtureStrategy(script=((-1, (buy,)),))
