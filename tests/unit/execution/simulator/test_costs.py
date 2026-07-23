"""Tests for deterministic spread, slippage, and fee costs."""

from decimal import Decimal

import pytest

from gemini_trading.domain.order import OrderSide
from gemini_trading.execution.simulator.costs import market_fill_costs


def test_market_buy_costs_are_adverse_and_exact() -> None:
    result = market_fill_costs(
        reference_price=Decimal("100"),
        quantity=Decimal("2"),
        side=OrderSide.BUY,
        half_spread_bps=Decimal("5"),
        slippage_bps=Decimal("10"),
        fee_rate=Decimal("0.001"),
    )

    assert result.fill_price == Decimal("100.1500")
    assert result.notional == Decimal("200.3000")
    assert result.fee == Decimal("0.2003000")
    assert result.spread_cost == Decimal("0.1000")
    assert result.slippage_cost == Decimal("0.200")


def test_market_sell_costs_are_adverse() -> None:
    result = market_fill_costs(
        reference_price=Decimal("100"),
        quantity=Decimal("2"),
        side=OrderSide.SELL_TO_CLOSE,
        half_spread_bps=Decimal("5"),
        slippage_bps=Decimal("10"),
        fee_rate=Decimal("0.001"),
    )

    assert result.fill_price == Decimal("99.8500")
    assert result.notional == Decimal("199.7000")


def test_market_costs_reject_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="fee_rate"):
        market_fill_costs(
            reference_price=Decimal("100"),
            quantity=Decimal("1"),
            side=OrderSide.BUY,
            half_spread_bps=Decimal("0"),
            slippage_bps=Decimal("0"),
            fee_rate=Decimal("-0.001"),
        )
