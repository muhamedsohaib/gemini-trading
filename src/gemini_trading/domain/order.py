"""Immutable order intent and simulated-order lifecycle contracts."""

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


def _require_identifier(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


def _require_positive_decimal(value: Decimal, field_name: str) -> None:
    if not value.is_finite() or value <= 0:
        raise ValueError(f"{field_name} must be finite and positive")


class TimeInForce(StrEnum):
    """Supported deterministic order-lifetime policies."""

    IOC = "ioc"
    BAR = "bar"
    GTC = "gtc"


class OrderSide(StrEnum):
    """Long-only spot order sides."""

    BUY = "buy"
    SELL_TO_CLOSE = "sell_to_close"


class OrderType(StrEnum):
    """Supported simulated order types."""

    MARKET = "market"
    LIMIT = "limit"


class OrderStatus(StrEnum):
    """Immutable snapshots of a simulated order lifecycle."""

    ACCEPTED = "accepted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class OrderIntent:
    """One strategy-proposed long-only spot order."""

    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    limit_price: Decimal | None
    time_in_force: TimeInForce

    def __post_init__(self) -> None:
        _require_positive_decimal(self.quantity, "quantity")
        if self.order_type is OrderType.LIMIT:
            if self.limit_price is None:
                raise ValueError("limit_price is required for limit orders")
            _require_positive_decimal(self.limit_price, "limit_price")
        elif self.limit_price is not None:
            raise ValueError("limit_price is forbidden for market orders")


@dataclass(frozen=True, slots=True)
class SimulatedOrder:
    """One deterministic simulated-order state snapshot."""

    order_id: str
    decision_sequence: int
    intent_sequence: int
    created_candle_index: int
    eligible_candle_index: int
    expires_after_candle_index: int
    side: OrderSide
    order_type: OrderType
    requested_quantity: Decimal
    filled_quantity: Decimal
    limit_price: Decimal | None
    time_in_force: TimeInForce
    status: OrderStatus

    def __post_init__(self) -> None:
        object.__setattr__(self, "order_id", _require_identifier(self.order_id, "order_id"))
        if self.decision_sequence < 1:
            raise ValueError("decision_sequence must be positive")
        if self.intent_sequence < 1:
            raise ValueError("intent_sequence must be positive")
        if self.created_candle_index < 0:
            raise ValueError("created_candle_index must be non-negative")
        if self.eligible_candle_index < self.created_candle_index:
            raise ValueError("eligible_candle_index must not precede creation")
        if self.expires_after_candle_index < self.eligible_candle_index:
            raise ValueError("expires_after_candle_index must not precede eligibility")

        _require_positive_decimal(self.requested_quantity, "requested_quantity")
        if not self.filled_quantity.is_finite() or self.filled_quantity < 0:
            raise ValueError("filled_quantity must be finite and non-negative")
        if self.filled_quantity > self.requested_quantity:
            raise ValueError("filled_quantity cannot exceed requested quantity")

        if self.order_type is OrderType.LIMIT:
            if self.limit_price is None:
                raise ValueError("limit_price is required for limit orders")
            _require_positive_decimal(self.limit_price, "limit_price")
        elif self.limit_price is not None:
            raise ValueError("limit_price is forbidden for market orders")

        if self.status is OrderStatus.ACCEPTED and self.filled_quantity != 0:
            raise ValueError("ACCEPTED order cannot contain filled quantity")
        if self.status is OrderStatus.PARTIALLY_FILLED and not (
            Decimal("0") < self.filled_quantity < self.requested_quantity
        ):
            raise ValueError("PARTIALLY_FILLED requires a strict partial quantity")
        if self.status is OrderStatus.FILLED and self.filled_quantity != self.requested_quantity:
            raise ValueError("FILLED requires the requested quantity to be filled")

    @property
    def remaining_quantity(self) -> Decimal:
        """Return the exact unfilled quantity."""

        return self.requested_quantity - self.filled_quantity
