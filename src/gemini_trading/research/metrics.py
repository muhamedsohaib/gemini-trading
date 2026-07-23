"""Deterministic performance metrics and completed long-only trade attribution."""

from dataclasses import dataclass
from decimal import Decimal

from gemini_trading.domain.order import OrderSide
from gemini_trading.research.engine import BacktestEvidence
from gemini_trading.research.errors import AccountingInvariantError

_ZERO = Decimal("0")


@dataclass(frozen=True, slots=True)
class CompletedTrade:
    """One exact flat-to-flat long-only round trip derived from recorded fills."""

    sequence: int
    entry_fill_ids: tuple[str, ...]
    exit_fill_ids: tuple[str, ...]
    entry_cost: Decimal
    exit_proceeds: Decimal
    realized_pnl: Decimal
    winning: bool


@dataclass(frozen=True, slots=True)
class BacktestMetrics:
    """Deterministic summary derived only from immutable backtest evidence."""

    starting_equity: Decimal
    ending_equity: Decimal
    gross_return: Decimal
    net_return: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    total_fees: Decimal
    total_execution_costs: Decimal
    maximum_drawdown: Decimal
    exposure_fraction: Decimal
    order_count: int
    rejection_count: int
    fill_count: int
    partial_fill_count: int
    trade_count: int
    win_rate: Decimal | None


def completed_trades(evidence: BacktestEvidence) -> tuple[CompletedTrade, ...]:
    """Derive exact completed flat-to-flat trades in fill chronology."""

    orders = {order.order_id: order for order in evidence.orders}
    position_quantity = _ZERO
    entry_cost = _ZERO
    exit_proceeds = _ZERO
    entry_fill_ids: list[str] = []
    exit_fill_ids: list[str] = []
    trades: list[CompletedTrade] = []

    for fill in evidence.fills:
        order = orders.get(fill.order_id)
        if order is None:
            raise AccountingInvariantError("fill references an unknown order")
        if order.side is OrderSide.BUY:
            if position_quantity == 0:
                entry_cost = _ZERO
                exit_proceeds = _ZERO
                entry_fill_ids = []
                exit_fill_ids = []
            position_quantity += fill.quantity
            entry_cost += fill.notional + fill.fee
            entry_fill_ids.append(fill.fill_id)
            continue

        if fill.quantity > position_quantity:
            raise AccountingInvariantError("sell fill exceeds derived trade position")
        position_quantity -= fill.quantity
        exit_proceeds += fill.notional - fill.fee
        exit_fill_ids.append(fill.fill_id)
        if position_quantity == 0:
            realized_pnl = exit_proceeds - entry_cost
            trades.append(
                CompletedTrade(
                    sequence=len(trades) + 1,
                    entry_fill_ids=tuple(entry_fill_ids),
                    exit_fill_ids=tuple(exit_fill_ids),
                    entry_cost=entry_cost,
                    exit_proceeds=exit_proceeds,
                    realized_pnl=realized_pnl,
                    winning=realized_pnl > 0,
                )
            )
            entry_cost = _ZERO
            exit_proceeds = _ZERO
            entry_fill_ids = []
            exit_fill_ids = []

    return tuple(trades)


def calculate_metrics(evidence: BacktestEvidence) -> BacktestMetrics:
    """Calculate exact metrics without clocks, randomness, or external data."""

    starting_equity = evidence.experiment_manifest.initial_cash
    ending_equity = evidence.terminal_account.marked_equity
    total_fees = evidence.terminal_account.cumulative_fees
    total_execution_costs = evidence.terminal_account.cumulative_execution_costs
    net_return = (ending_equity - starting_equity) / starting_equity
    gross_return = (
        ending_equity + total_fees + total_execution_costs - starting_equity
    ) / starting_equity
    unrealized_pnl = (
        ending_equity
        - evidence.terminal_account.cash
        - evidence.terminal_account.position_cost_basis
    )
    snapshots = (*evidence.account_series, evidence.terminal_account)
    maximum_drawdown = max((snapshot.drawdown for snapshot in snapshots), default=_ZERO)
    exposure_fraction = (
        _ZERO
        if not evidence.account_series
        else Decimal(
            sum(snapshot.position_quantity > 0 for snapshot in evidence.account_series)
        )
        / Decimal(len(evidence.account_series))
    )
    partial_fill_count = sum(
        _ZERO < order.filled_quantity < order.requested_quantity for order in evidence.orders
    )
    trades = completed_trades(evidence)
    win_rate = (
        None
        if not trades
        else Decimal(sum(trade.winning for trade in trades)) / Decimal(len(trades))
    )
    return BacktestMetrics(
        starting_equity=starting_equity,
        ending_equity=ending_equity,
        gross_return=gross_return,
        net_return=net_return,
        realized_pnl=evidence.terminal_account.realized_pnl,
        unrealized_pnl=unrealized_pnl,
        total_fees=total_fees,
        total_execution_costs=total_execution_costs,
        maximum_drawdown=maximum_drawdown,
        exposure_fraction=exposure_fraction,
        order_count=len(evidence.orders),
        rejection_count=len(evidence.rejection_records),
        fill_count=len(evidence.fills),
        partial_fill_count=partial_fill_count,
        trade_count=len(trades),
        win_rate=win_rate,
    )
