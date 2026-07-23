"""Immutable long-only spot account and ledger contracts."""

from dataclasses import dataclass
from decimal import Decimal


def _require_finite(value: Decimal, field_name: str) -> None:
    if not value.is_finite():
        raise ValueError(f"{field_name} must be finite")


def _require_non_negative(value: Decimal, field_name: str) -> None:
    _require_finite(value, field_name)
    if value < 0:
        raise ValueError(f"{field_name} must be non-negative")


def _require_optional_identifier(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty when provided")
    return normalized


@dataclass(frozen=True, slots=True)
class AccountSnapshot:
    """Authoritative immutable account state after one accepted event."""

    cash: Decimal
    reserved_cash: Decimal
    position_quantity: Decimal
    average_entry_price: Decimal
    realized_pnl: Decimal
    cumulative_fees: Decimal
    cumulative_execution_costs: Decimal
    marked_equity: Decimal
    peak_equity: Decimal
    drawdown: Decimal
    position_cost_basis: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        _require_non_negative(self.cash, "cash")
        _require_non_negative(self.reserved_cash, "reserved_cash")
        _require_non_negative(self.position_quantity, "position_quantity")
        _require_non_negative(self.average_entry_price, "average_entry_price")
        _require_finite(self.realized_pnl, "realized_pnl")
        _require_non_negative(self.cumulative_fees, "cumulative_fees")
        _require_non_negative(self.cumulative_execution_costs, "cumulative_execution_costs")
        _require_non_negative(self.marked_equity, "marked_equity")
        _require_non_negative(self.peak_equity, "peak_equity")
        _require_non_negative(self.drawdown, "drawdown")
        _require_non_negative(self.position_cost_basis, "position_cost_basis")

        if self.reserved_cash > self.cash:
            raise ValueError("reserved_cash cannot exceed cash")
        if self.position_quantity == 0:
            if self.average_entry_price != 0:
                raise ValueError("average_entry_price must be zero without a position")
            if self.position_cost_basis != 0:
                raise ValueError("position_cost_basis must be zero without a position")
        else:
            if self.average_entry_price <= 0:
                raise ValueError("average_entry_price must be positive with a position")
            if self.position_cost_basis == 0:
                inferred_cost_basis = self.average_entry_price * self.position_quantity
                if inferred_cost_basis <= 0:
                    raise ValueError("position_cost_basis must be positive with a position")
                object.__setattr__(self, "position_cost_basis", inferred_cost_basis)
        if self.drawdown > 1:
            raise ValueError("drawdown must be between zero and one")
        if self.peak_equity < self.marked_equity:
            raise ValueError("peak_equity cannot be below marked_equity")

    @classmethod
    def initial(cls, cash: Decimal) -> "AccountSnapshot":
        """Create a cash-only account with no position or costs."""

        if not cash.is_finite() or cash <= 0:
            raise ValueError("cash must be finite and positive")
        zero = Decimal("0")
        return cls(cash, zero, zero, zero, zero, zero, zero, cash, cash, zero, zero)


@dataclass(frozen=True, slots=True)
class LedgerEntry:
    """One immutable accounting delta and resulting balances."""

    sequence: int
    event_type: str
    order_id: str | None
    fill_id: str | None
    cash_delta: Decimal
    position_delta: Decimal
    fee_delta: Decimal
    resulting_cash: Decimal
    resulting_position: Decimal

    def __post_init__(self) -> None:
        if self.sequence < 1:
            raise ValueError("sequence must be positive")
        normalized_event = self.event_type.strip()
        if not normalized_event:
            raise ValueError("event_type must not be empty")
        object.__setattr__(self, "event_type", normalized_event)
        object.__setattr__(
            self,
            "order_id",
            _require_optional_identifier(self.order_id, "order_id"),
        )
        object.__setattr__(
            self,
            "fill_id",
            _require_optional_identifier(self.fill_id, "fill_id"),
        )
        _require_finite(self.cash_delta, "cash_delta")
        _require_finite(self.position_delta, "position_delta")
        _require_non_negative(self.fee_delta, "fee_delta")
        _require_non_negative(self.resulting_cash, "resulting_cash")
        _require_non_negative(self.resulting_position, "resulting_position")
