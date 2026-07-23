"""Deterministic long-only spot accounting transitions and reconciliation."""

from dataclasses import replace
from decimal import Decimal

from gemini_trading.domain.account import AccountSnapshot, LedgerEntry
from gemini_trading.domain.fill import Fill
from gemini_trading.domain.order import OrderSide, OrderStatus, SimulatedOrder
from gemini_trading.research.errors import AccountingInvariantError

_ACTIVE_ORDER_STATUSES = {OrderStatus.ACCEPTED, OrderStatus.PARTIALLY_FILLED}
_ZERO = Decimal("0")


def _drawdown(marked_equity: Decimal, peak_equity: Decimal) -> Decimal:
    if peak_equity == 0:
        return _ZERO
    return (peak_equity - marked_equity) / peak_equity


def _validate_fill_application(
    account: AccountSnapshot,
    order: SimulatedOrder,
    fill: Fill,
    sequence: int,
) -> None:
    if sequence < 1:
        raise AccountingInvariantError("ledger sequence must be positive")
    if account.reserved_cash != 0:
        raise AccountingInvariantError("reserved cash is unsupported in this accounting slice")
    if fill.order_id != order.order_id:
        raise AccountingInvariantError("fill and order identity do not match")
    if order.status not in _ACTIVE_ORDER_STATUSES:
        raise AccountingInvariantError("fill requires an active order")
    if fill.quantity > order.remaining_quantity:
        raise AccountingInvariantError("fill quantity exceeds the order remainder")


def apply_fill(
    account: AccountSnapshot,
    order: SimulatedOrder,
    fill: Fill,
    sequence: int,
) -> tuple[AccountSnapshot, LedgerEntry]:
    """Apply one valid fill and return the new immutable account and ledger delta."""

    _validate_fill_application(account, order, fill, sequence)

    if order.side is OrderSide.BUY:
        cash_delta = -(fill.notional + fill.fee)
        if -cash_delta > account.cash:
            raise AccountingInvariantError("buy fill exceeds available cash")
        position_delta = fill.quantity
        resulting_position = account.position_quantity + position_delta
        position_cost_basis = account.position_cost_basis + fill.notional + fill.fee
        average_entry_price = position_cost_basis / resulting_position
        realized_pnl = account.realized_pnl
        event_type = "fill.buy"
    else:
        if fill.quantity > account.position_quantity:
            raise AccountingInvariantError("sell fill exceeds owned position")
        cash_delta = fill.notional - fill.fee
        position_delta = -fill.quantity
        resulting_position = account.position_quantity + position_delta
        if resulting_position == 0:
            cost_basis_released = account.position_cost_basis
            position_cost_basis = _ZERO
            average_entry_price = _ZERO
        else:
            cost_basis_released = (
                account.position_cost_basis * fill.quantity / account.position_quantity
            )
            position_cost_basis = account.position_cost_basis - cost_basis_released
            average_entry_price = position_cost_basis / resulting_position
        realized_pnl = account.realized_pnl + cash_delta - cost_basis_released
        event_type = "fill.sell_to_close"

    resulting_cash = account.cash + cash_delta
    if resulting_cash < 0 or resulting_position < 0:
        raise AccountingInvariantError("fill would create a negative account balance")

    marked_equity = resulting_cash + resulting_position * fill.fill_price
    peak_equity = max(account.peak_equity, marked_equity)
    updated = AccountSnapshot(
        cash=resulting_cash,
        reserved_cash=_ZERO,
        position_quantity=resulting_position,
        average_entry_price=average_entry_price,
        realized_pnl=realized_pnl,
        cumulative_fees=account.cumulative_fees + fill.fee,
        cumulative_execution_costs=(
            account.cumulative_execution_costs + fill.spread_cost + fill.slippage_cost
        ),
        marked_equity=marked_equity,
        peak_equity=peak_equity,
        drawdown=_drawdown(marked_equity, peak_equity),
        position_cost_basis=position_cost_basis,
    )
    ledger_entry = LedgerEntry(
        sequence=sequence,
        event_type=event_type,
        order_id=order.order_id,
        fill_id=fill.fill_id,
        cash_delta=cash_delta,
        position_delta=position_delta,
        fee_delta=fill.fee,
        resulting_cash=resulting_cash,
        resulting_position=resulting_position,
    )
    return updated, ledger_entry


def mark_to_market(account: AccountSnapshot, close_price: Decimal) -> AccountSnapshot:
    """Mark the long-only account at one finite positive completed-candle close."""

    if not close_price.is_finite() or close_price <= 0:
        raise AccountingInvariantError("close price must be finite and positive")
    marked_equity = account.cash + account.position_quantity * close_price
    peak_equity = max(account.peak_equity, marked_equity)
    return replace(
        account,
        marked_equity=marked_equity,
        peak_equity=peak_equity,
        drawdown=_drawdown(marked_equity, peak_equity),
    )


def verify_reconciliation(
    initial_cash: Decimal,
    account: AccountSnapshot,
    ledger: tuple[LedgerEntry, ...],
) -> None:
    """Fail closed unless the ledger exactly reconstructs terminal balances."""

    if not initial_cash.is_finite() or initial_cash <= 0:
        raise AccountingInvariantError("initial cash must be finite and positive")

    fill_ids = tuple(entry.fill_id for entry in ledger if entry.fill_id is not None)
    if len(fill_ids) != len(set(fill_ids)):
        raise AccountingInvariantError("duplicate fill identity in ledger")

    sequences = tuple(entry.sequence for entry in ledger)
    if sequences != tuple(sorted(sequences)) or len(sequences) != len(set(sequences)):
        raise AccountingInvariantError("ledger sequences must be unique and increasing")

    running_cash = initial_cash
    running_position = _ZERO
    fee_total = _ZERO
    for entry in ledger:
        running_cash += entry.cash_delta
        running_position += entry.position_delta
        fee_total += entry.fee_delta
        if running_cash < 0 or running_position < 0:
            raise AccountingInvariantError("ledger reconstructs a negative balance")
        if entry.resulting_cash != running_cash:
            raise AccountingInvariantError("ledger cash balance does not reconcile")
        if entry.resulting_position != running_position:
            raise AccountingInvariantError("ledger position balance does not reconcile")

    if running_cash != account.cash:
        raise AccountingInvariantError("terminal cash does not reconcile")
    if running_position != account.position_quantity:
        raise AccountingInvariantError("terminal position does not reconcile")
    if fee_total != account.cumulative_fees:
        raise AccountingInvariantError("terminal fees do not reconcile")
    if account.position_quantity == 0:
        if account.position_cost_basis != 0:
            raise AccountingInvariantError("flat account retains position cost basis")
        if account.cash != initial_cash + account.realized_pnl:
            raise AccountingInvariantError("flat-account realized profit does not reconcile")
