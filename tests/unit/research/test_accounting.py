"""Tests for deterministic long-only account transitions and reconciliation."""

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from gemini_trading.domain.account import AccountSnapshot
from gemini_trading.domain.fill import Fill
from gemini_trading.domain.order import (
    OrderSide,
    OrderStatus,
    OrderType,
    SimulatedOrder,
    TimeInForce,
)
from gemini_trading.research.accounting import apply_fill, mark_to_market, verify_reconciliation
from gemini_trading.research.errors import AccountingInvariantError


def _order(
    order_id: str,
    side: OrderSide,
    quantity: Decimal = Decimal("2"),
) -> SimulatedOrder:
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
    *,
    spread_cost: Decimal = Decimal("0"),
    slippage_cost: Decimal = Decimal("0"),
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
        spread_cost=spread_cost,
        slippage_cost=slippage_cost,
        price_was_rounded=False,
        quantity_was_rounded=False,
    )


def test_round_trip_reconciles_cash_position_fees_and_realized_pnl() -> None:
    initial = AccountSnapshot.initial(Decimal("1000"))
    buy_order = _order("buy-1", OrderSide.BUY)
    buy_fill = _fill(
        "buy-1",
        "fill-buy-1",
        Decimal("2"),
        Decimal("100"),
        Decimal("1.00"),
        spread_cost=Decimal("0.50"),
        slippage_cost=Decimal("0.50"),
    )
    after_buy, buy_entry = apply_fill(initial, buy_order, buy_fill, 1)

    sell_order = _order("sell-1", OrderSide.SELL_TO_CLOSE)
    sell_fill = _fill(
        "sell-1",
        "fill-sell-1",
        Decimal("2"),
        Decimal("110"),
        Decimal("1.20"),
        spread_cost=Decimal("0.50"),
        slippage_cost=Decimal("0.50"),
    )
    after_sell, sell_entry = apply_fill(after_buy, sell_order, sell_fill, 2)

    verify_reconciliation(Decimal("1000"), after_sell, (buy_entry, sell_entry))
    assert after_buy.average_entry_price == Decimal("100.50")
    assert after_sell.position_quantity == Decimal("0")
    assert after_sell.average_entry_price == Decimal("0")
    assert after_sell.cash == Decimal("1017.80")
    assert after_sell.realized_pnl == Decimal("17.80")
    assert after_sell.cumulative_fees == Decimal("2.20")
    assert after_sell.cumulative_execution_costs == Decimal("2.00")


def test_sell_above_owned_position_fails_closed() -> None:
    account = AccountSnapshot(
        cash=Decimal("900"),
        reserved_cash=Decimal("0"),
        position_quantity=Decimal("1"),
        average_entry_price=Decimal("100"),
        realized_pnl=Decimal("0"),
        cumulative_fees=Decimal("0"),
        cumulative_execution_costs=Decimal("0"),
        marked_equity=Decimal("1000"),
        peak_equity=Decimal("1000"),
        drawdown=Decimal("0"),
    )

    with pytest.raises(AccountingInvariantError, match="owned position"):
        apply_fill(
            account,
            _order("sell-too-large", OrderSide.SELL_TO_CLOSE),
            _fill(
                "sell-too-large",
                "fill-too-large",
                Decimal("2"),
                Decimal("110"),
                Decimal("0"),
            ),
            1,
        )


def test_mismatched_order_and_fill_identity_fails_closed() -> None:
    with pytest.raises(AccountingInvariantError, match="order identity"):
        apply_fill(
            AccountSnapshot.initial(Decimal("1000")),
            _order("buy-1", OrderSide.BUY),
            _fill("different-order", "fill-1", Decimal("1"), Decimal("100"), Decimal("0")),
            1,
        )


def test_mark_to_market_preserves_peak_and_calculates_drawdown() -> None:
    initial = AccountSnapshot.initial(Decimal("1000"))
    account, _ = apply_fill(
        initial,
        _order("buy-1", OrderSide.BUY, Decimal("1")),
        _fill("buy-1", "fill-1", Decimal("1"), Decimal("100"), Decimal("0")),
        1,
    )

    at_peak = mark_to_market(account, Decimal("120"))
    below_peak = mark_to_market(at_peak, Decimal("90"))

    assert at_peak.marked_equity == Decimal("1020")
    assert at_peak.peak_equity == Decimal("1020")
    assert at_peak.drawdown == Decimal("0")
    assert below_peak.marked_equity == Decimal("990")
    assert below_peak.peak_equity == Decimal("1020")
    assert below_peak.drawdown == Decimal("30") / Decimal("1020")


def test_reconciliation_rejects_duplicate_fill_identity() -> None:
    initial = AccountSnapshot.initial(Decimal("1000"))
    order = _order("buy-1", OrderSide.BUY, Decimal("1"))
    fill = _fill("buy-1", "fill-1", Decimal("1"), Decimal("100"), Decimal("0"))
    account, entry = apply_fill(initial, order, fill, 1)

    with pytest.raises(AccountingInvariantError, match="duplicate fill"):
        verify_reconciliation(
            Decimal("1000"),
            account,
            (entry, replace(entry, sequence=2)),
        )
