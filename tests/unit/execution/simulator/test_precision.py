"""Tests for conservative Decimal precision rules."""

from decimal import Decimal

import pytest

from gemini_trading.domain.order import OrderSide
from gemini_trading.execution.simulator.precision import round_fill_price, round_quantity_down


def test_quantity_rounds_down_to_step() -> None:
    assert round_quantity_down(Decimal("1.23456"), Decimal("0.001")) == Decimal("1.234")


def test_buy_price_rounds_up_and_sell_price_rounds_down() -> None:
    assert round_fill_price(Decimal("100.001"), Decimal("0.01"), OrderSide.BUY) == Decimal("100.01")
    assert round_fill_price(
        Decimal("100.009"), Decimal("0.01"), OrderSide.SELL_TO_CLOSE
    ) == Decimal("100.00")


def test_precision_rejects_invalid_values_before_arithmetic() -> None:
    with pytest.raises(ValueError, match="quantity"):
        round_quantity_down(Decimal("0"), Decimal("0.001"))
    with pytest.raises(ValueError, match="step"):
        round_quantity_down(Decimal("1"), Decimal("NaN"))
    with pytest.raises(ValueError, match="price"):
        round_fill_price(Decimal("-1"), Decimal("0.01"), OrderSide.BUY)
