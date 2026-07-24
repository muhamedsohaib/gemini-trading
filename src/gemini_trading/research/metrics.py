"""Deterministic performance metrics and completed long-only trade attribution."""

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext

from gemini_trading.domain.order import OrderSide
from gemini_trading.research.engine import BacktestEvidence
from gemini_trading.research.errors import AccountingInvariantError

_ZERO = Decimal("0")
_ONE = Decimal("1")
_PERIODS_PER_YEAR = Decimal("2190")
_CONTEXT = Context(prec=34, rounding=ROUND_HALF_EVEN)


@dataclass(frozen=True, slots=True)
class CompletedTrade:
    """One exact flat-to-flat long-only round trip derived from recorded fills."""

    sequence: int
    entry_fill_ids: tuple[str, ...]
    exit_fill_ids: tuple[str, ...]
    entry_candle_index: int
    exit_candle_index: int
    hold_candles: int
    entry_cost: Decimal
    exit_proceeds: Decimal
    gross_return: Decimal
    net_return: Decimal
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
    observed_periods: int
    annualized_geometric_return: Decimal
    annualized_volatility: Decimal
    downside_deviation: Decimal
    sortino_ratio: Decimal | None
    return_to_drawdown: Decimal | None
    turnover: Decimal
    exposure_adjusted_return: Decimal | None
    profit_factor: Decimal | None
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
    entry_notional = _ZERO
    exit_proceeds = _ZERO
    exit_notional = _ZERO
    entry_candle_index: int | None = None
    entry_fill_ids: list[str] = []
    exit_fill_ids: list[str] = []
    trades: list[CompletedTrade] = []

    with localcontext(_CONTEXT):
        for fill in evidence.fills:
            order = orders.get(fill.order_id)
            if order is None:
                raise AccountingInvariantError("fill references an unknown order")
            if order.side is OrderSide.BUY:
                if position_quantity == 0:
                    entry_cost = _ZERO
                    entry_notional = _ZERO
                    exit_proceeds = _ZERO
                    exit_notional = _ZERO
                    entry_candle_index = fill.candle_index
                    entry_fill_ids = []
                    exit_fill_ids = []
                position_quantity += fill.quantity
                entry_cost += fill.notional + fill.fee
                entry_notional += fill.notional
                entry_fill_ids.append(fill.fill_id)
                continue

            if fill.quantity > position_quantity:
                raise AccountingInvariantError("sell fill exceeds derived trade position")
            position_quantity -= fill.quantity
            exit_proceeds += fill.notional - fill.fee
            exit_notional += fill.notional
            exit_fill_ids.append(fill.fill_id)
            if position_quantity == 0:
                if entry_candle_index is None or entry_cost <= 0 or entry_notional <= 0:
                    raise AccountingInvariantError("completed trade is missing entry attribution")
                realized_pnl = exit_proceeds - entry_cost
                gross_return = exit_notional / entry_notional - _ONE
                net_return = realized_pnl / entry_cost
                trades.append(
                    CompletedTrade(
                        sequence=len(trades) + 1,
                        entry_fill_ids=tuple(entry_fill_ids),
                        exit_fill_ids=tuple(exit_fill_ids),
                        entry_candle_index=entry_candle_index,
                        exit_candle_index=fill.candle_index,
                        hold_candles=fill.candle_index - entry_candle_index,
                        entry_cost=entry_cost,
                        exit_proceeds=exit_proceeds,
                        gross_return=gross_return,
                        net_return=net_return,
                        realized_pnl=realized_pnl,
                        winning=realized_pnl > 0,
                    )
                )
                entry_cost = _ZERO
                entry_notional = _ZERO
                exit_proceeds = _ZERO
                exit_notional = _ZERO
                entry_candle_index = None
                entry_fill_ids = []
                exit_fill_ids = []

    return tuple(trades)


def _period_returns(evidence: BacktestEvidence, starting_equity: Decimal) -> tuple[Decimal, ...]:
    previous_equity = starting_equity
    returns: list[Decimal] = []
    with localcontext(_CONTEXT):
        for snapshot in evidence.account_series:
            if previous_equity <= 0:
                raise AccountingInvariantError("period return requires positive prior equity")
            returns.append(snapshot.marked_equity / previous_equity - _ONE)
            previous_equity = snapshot.marked_equity
    return tuple(returns)


def _population_standard_deviation(values: tuple[Decimal, ...]) -> Decimal:
    if not values:
        return _ZERO
    with localcontext(_CONTEXT):
        mean = sum(values, _ZERO) / Decimal(len(values))
        variance = sum(((value - mean) ** 2 for value in values), _ZERO) / Decimal(len(values))
        return variance.sqrt()


def calculate_metrics(evidence: BacktestEvidence) -> BacktestMetrics:
    """Calculate exact metrics without clocks, randomness, or external data."""

    starting_equity = evidence.experiment_manifest.initial_cash
    ending_equity = evidence.terminal_account.marked_equity
    total_fees = evidence.terminal_account.cumulative_fees
    total_execution_costs = evidence.terminal_account.cumulative_execution_costs
    with localcontext(_CONTEXT):
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
        period_returns = _period_returns(evidence, starting_equity)
        observed_periods = len(period_returns)
        annualized_geometric_return = (
            _ZERO
            if observed_periods == 0
            else (ending_equity / starting_equity)
            ** (int(_PERIODS_PER_YEAR) // observed_periods)
            - _ONE
        )
        annualization_scale = _PERIODS_PER_YEAR.sqrt()
        annualized_volatility = _population_standard_deviation(period_returns) * annualization_scale
        downside_deviation = (
            _ZERO
            if not period_returns
            else (
                sum((min(value, _ZERO) ** 2 for value in period_returns), _ZERO)
                / Decimal(observed_periods)
            ).sqrt()
            * annualization_scale
        )
        sortino_ratio = (
            None
            if downside_deviation == 0
            else annualized_geometric_return / downside_deviation
        )
        return_to_drawdown = (
            None
            if maximum_drawdown == 0
            else annualized_geometric_return / maximum_drawdown
        )
        mean_equity = (
            _ZERO
            if not evidence.account_series
            else sum(
                (snapshot.marked_equity for snapshot in evidence.account_series),
                _ZERO,
            )
            / Decimal(len(evidence.account_series))
        )
        total_fill_notional = sum((fill.notional for fill in evidence.fills), _ZERO)
        turnover = _ZERO if mean_equity == 0 else total_fill_notional / mean_equity
        exposure_adjusted_return = (
            None if exposure_fraction == 0 else net_return / exposure_fraction
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
    positive_pnl = sum((trade.realized_pnl for trade in trades if trade.realized_pnl > 0), _ZERO)
    negative_pnl = sum((trade.realized_pnl for trade in trades if trade.realized_pnl < 0), _ZERO)
    profit_factor = None if negative_pnl == 0 else positive_pnl / abs(negative_pnl)
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
        observed_periods=observed_periods,
        annualized_geometric_return=annualized_geometric_return,
        annualized_volatility=annualized_volatility,
        downside_deviation=downside_deviation,
        sortino_ratio=sortino_ratio,
        return_to_drawdown=return_to_drawdown,
        turnover=turnover,
        exposure_adjusted_return=exposure_adjusted_return,
        profit_factor=profit_factor,
        order_count=len(evidence.orders),
        rejection_count=len(evidence.rejection_records),
        fill_count=len(evidence.fills),
        partial_fill_count=partial_fill_count,
        trade_count=len(trades),
        win_rate=win_rate,
    )
