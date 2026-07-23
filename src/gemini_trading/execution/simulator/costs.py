"""Deterministic adverse spread, slippage, and fee calculations."""

from dataclasses import dataclass
from decimal import Decimal

from gemini_trading.domain.order import OrderSide

_BASIS_POINTS = Decimal("10000")


def _positive(value: Decimal, field_name: str) -> None:
    if not value.is_finite() or value <= 0:
        raise ValueError(f"{field_name} must be finite and positive")


def _non_negative(value: Decimal, field_name: str) -> None:
    if not value.is_finite() or value < 0:
        raise ValueError(f"{field_name} must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class FillCosts:
    """Exact cost components for one unrounded market fill."""

    reference_price: Decimal
    fill_price: Decimal
    notional: Decimal
    fee: Decimal
    spread_cost: Decimal
    slippage_cost: Decimal



def market_fill_costs(
    *,
    reference_price: Decimal,
    quantity: Decimal,
    side: OrderSide,
    half_spread_bps: Decimal,
    slippage_bps: Decimal,
    fee_rate: Decimal,
) -> FillCosts:
    """Apply adverse market execution costs without binary floating point."""

    _positive(reference_price, "reference_price")
    _positive(quantity, "quantity")
    _non_negative(half_spread_bps, "half_spread_bps")
    _non_negative(slippage_bps, "slippage_bps")
    _non_negative(fee_rate, "fee_rate")

    direction = Decimal("1") if side is OrderSide.BUY else Decimal("-1")
    spread = reference_price * half_spread_bps / _BASIS_POINTS
    slippage = reference_price * slippage_bps / _BASIS_POINTS
    fill_price = reference_price + direction * (spread + slippage)
    if fill_price <= 0:
        raise ValueError("fill_price must remain positive after execution costs")
    notional = fill_price * quantity
    return FillCosts(
        reference_price=reference_price,
        fill_price=fill_price,
        notional=notional,
        fee=notional * fee_rate,
        spread_cost=spread * quantity,
        slippage_cost=slippage * quantity,
    )
