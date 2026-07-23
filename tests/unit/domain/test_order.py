"""Tests for immutable simulated-order contracts."""

from dataclasses import FrozenInstanceError, replace
from decimal import Decimal

import pytest

from gemini_trading.domain.order import (
    OrderIntent,
    OrderSide,
    OrderStatus,
    OrderType,
    SimulatedOrder,
    TimeInForce,
)


def _order() -> SimulatedOrder:
    return SimulatedOrder(
        order_id="order-1",
        decision_sequence=1,
        intent_sequence=1,
        created_candle_index=3,
        eligible_candle_index=4,
        expires_after_candle_index=4,
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        requested_quantity=Decimal("2"),
        filled_quantity=Decimal("0.5"),
        limit_price=Decimal("100"),
        time_in_force=TimeInForce.BAR,
        status=OrderStatus.PARTIALLY_FILLED,
    )


def test_limit_order_requires_price_and_market_order_forbids_it() -> None:
    with pytest.raises(ValueError, match="limit_price"):
        OrderIntent(OrderSide.BUY, OrderType.LIMIT, Decimal("1"), None, TimeInForce.GTC)
    with pytest.raises(ValueError, match="limit_price"):
        OrderIntent(
            OrderSide.BUY,
            OrderType.MARKET,
            Decimal("1"),
            Decimal("100"),
            TimeInForce.IOC,
        )


def test_sell_to_close_is_explicit_not_short_side() -> None:
    assert OrderSide.SELL_TO_CLOSE.value == "sell_to_close"


def test_order_quantity_and_lifecycle_are_validated() -> None:
    order = _order()

    assert order.remaining_quantity == Decimal("1.5")
    with pytest.raises(ValueError, match="quantity"):
        replace(order, requested_quantity=Decimal("0"))
    with pytest.raises(ValueError, match="filled_quantity"):
        replace(order, filled_quantity=Decimal("3"))
    with pytest.raises(ValueError, match="eligible_candle_index"):
        replace(order, eligible_candle_index=2)
    with pytest.raises(FrozenInstanceError):
        order.status = OrderStatus.FILLED  # type: ignore[misc]


def test_terminal_status_must_match_filled_quantity() -> None:
    order = _order()

    with pytest.raises(ValueError, match="FILLED"):
        replace(order, status=OrderStatus.FILLED)
    with pytest.raises(ValueError, match="PARTIALLY_FILLED"):
        replace(order, filled_quantity=Decimal("0"), status=OrderStatus.PARTIALLY_FILLED)
