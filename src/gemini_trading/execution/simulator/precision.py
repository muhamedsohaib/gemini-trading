"""Conservative Decimal-only price and quantity precision rules."""

from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal

from gemini_trading.domain.order import OrderSide


def _positive(value: Decimal, field_name: str) -> None:
    if not value.is_finite() or value <= 0:
        raise ValueError(f"{field_name} must be finite and positive")


def round_quantity_down(quantity: Decimal, step: Decimal) -> Decimal:
    """Round quantity toward zero to the configured exchange step."""

    _positive(quantity, "quantity")
    _positive(step, "step")
    units = (quantity / step).to_integral_value(rounding=ROUND_FLOOR)
    return units * step


def round_fill_price(price: Decimal, tick: Decimal, side: OrderSide) -> Decimal:
    """Round simulated fills adversely for the long-only order side."""

    _positive(price, "price")
    _positive(tick, "tick")
    rounding = ROUND_CEILING if side is OrderSide.BUY else ROUND_FLOOR
    units = (price / tick).to_integral_value(rounding=rounding)
    rounded = units * tick
    if rounded <= 0:
        raise ValueError("rounded fill price must be positive")
    return rounded
