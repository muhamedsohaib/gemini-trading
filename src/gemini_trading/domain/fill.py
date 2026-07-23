"""Immutable simulated fill contracts."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from gemini_trading.domain.time import require_utc


def _require_identifier(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


def _require_positive(value: Decimal, field_name: str) -> None:
    if not value.is_finite() or value <= 0:
        raise ValueError(f"{field_name} must be finite and positive")


def _require_non_negative(value: Decimal, field_name: str) -> None:
    if not value.is_finite() or value < 0:
        raise ValueError(f"{field_name} must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class Fill:
    """One deterministic partial or complete simulated fill."""

    fill_id: str
    order_id: str
    candle_index: int
    candle_open_time: datetime
    quantity: Decimal
    reference_price: Decimal
    fill_price: Decimal
    notional: Decimal
    fee: Decimal
    spread_cost: Decimal
    slippage_cost: Decimal
    price_was_rounded: bool
    quantity_was_rounded: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "fill_id", _require_identifier(self.fill_id, "fill_id"))
        object.__setattr__(self, "order_id", _require_identifier(self.order_id, "order_id"))
        if self.candle_index < 0:
            raise ValueError("candle_index must be non-negative")
        require_utc(self.candle_open_time, "candle_open_time")
        _require_positive(self.quantity, "quantity")
        _require_positive(self.reference_price, "reference_price")
        _require_positive(self.fill_price, "fill_price")
        _require_positive(self.notional, "notional")
        _require_non_negative(self.fee, "fee")
        _require_non_negative(self.spread_cost, "spread_cost")
        _require_non_negative(self.slippage_cost, "slippage_cost")
        if self.notional != self.quantity * self.fill_price:
            raise ValueError("notional must equal quantity multiplied by fill_price")
