"""Property tests for deterministic accounting conservation and replay."""

from datetime import UTC, datetime
from decimal import Decimal

from hypothesis import given, strategies as st

from gemini_trading.domain.account import AccountSnapshot
from gemini_trading.domain.fill import Fill
from gemini_trading.domain.order import (
    OrderSide,
    OrderStatus,
    OrderType,
    SimulatedOrder,
    TimeInForce,
)
from gemini_trading.research.accounting import apply_fill, verify_reconciliation


def _order(order_id: str, side: OrderSide, quantity: Decimal) -> SimulatedOrder:
    return SimulatedOrder(
        order_id=order_id,
        decision_sequence=1,
        intent_sequence=1,
        created_candle_index=0,
        eligible_candle_index=1,
        expires_after_candle_index=3,
        side=side,
        order_type=OrderType.MARKET,
        requested_quantity=quantity,
        filled_quantity=Decimal("0"),
        limit_price=None,
        time_in_force=TimeInForce.BAR,
        status=OrderStatus.ACCEPTED,
    )


def _fill(
    order_id: str,
    fill_id: str,
    quantity: Decimal,
    price: Decimal,
    fee: Decimal,
) -> Fill:
    return Fill(
        fill_id=fill_id,
        order_id=order_id,
        candle_index=1,
        candle_open_time=datetime(2025, 1, 1, tzinfo=UTC),
        quantity=quantity,
        reference_price=price,
        fill_price=price,
        notional=quantity * price,
        fee=fee,
        spread_cost=Decimal("0"),
        slippage_cost=Decimal("0"),
        price_was_rounded=False,
        quantity_was_rounded=False,
    )


@given(
    quantity_value=st.integers(min_value=1, max_value=20),
    buy_price_value=st.integers(min_value=10, max_value=500),
    sell_price_value=st.integers(min_value=10, max_value=500),
    buy_fee_cents=st.integers(min_value=0, max_value=500),
    sell_fee_cents=st.integers(min_value=0, max_value=500),
)
def test_round_trip_conserves_cash_and_is_deterministic(
    quantity_value: int,
    buy_price_value: int,
    sell_price_value: int,
    buy_fee_cents: int,
    sell_fee_cents: int,
) -> None:
    quantity = Decimal(quantity_value)
    buy_price = Decimal(buy_price_value)
    sell_price = Decimal(sell_price_value)
    buy_fee = Decimal(buy_fee_cents) / Decimal("100")
    sell_fee = Decimal(sell_fee_cents) / Decimal("100")
    initial_cash = quantity * buy_price + buy_fee + Decimal("100")

    initial = AccountSnapshot.initial(initial_cash)
    buy_order = _order("buy", OrderSide.BUY, quantity)
    buy_fill = _fill("buy", "fill-buy", quantity, buy_price, buy_fee)
    sell_order = _order("sell", OrderSide.SELL_TO_CLOSE, quantity)
    sell_fill = _fill("sell", "fill-sell", quantity, sell_price, sell_fee)

    after_buy, buy_entry = apply_fill(initial, buy_order, buy_fill, 1)
    final, sell_entry = apply_fill(after_buy, sell_order, sell_fill, 2)

    replay_after_buy, replay_buy_entry = apply_fill(initial, buy_order, buy_fill, 1)
    replay_final, replay_sell_entry = apply_fill(
        replay_after_buy,
        sell_order,
        sell_fill,
        2,
    )

    ledger = (buy_entry, sell_entry)
    verify_reconciliation(initial_cash, final, ledger)

    assert final.cash >= 0
    assert final.position_quantity == 0
    assert final.cash == initial_cash + final.realized_pnl
    assert replay_after_buy == after_buy
    assert replay_final == final
    assert (replay_buy_entry, replay_sell_entry) == ledger
