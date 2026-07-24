"""Tests for deterministic backtest metrics and completed-trade derivation."""

import hashlib
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from gemini_trading.domain.account import AccountSnapshot, LedgerEntry
from gemini_trading.domain.experiment import ExperimentManifest, LimitFillPolicy, TimingPolicy
from gemini_trading.domain.fill import Fill
from gemini_trading.domain.order import (
    OrderSide,
    OrderStatus,
    OrderType,
    SimulatedOrder,
    TimeInForce,
)
from gemini_trading.research.config import SimulationConfig, serialize_simulation_config
from gemini_trading.research.engine import BacktestEvidence
from gemini_trading.research.metrics import calculate_metrics, completed_trades


def known_config() -> SimulationConfig:
    return SimulationConfig.official(
        maker_fee_rate=Decimal("0.001"),
        taker_fee_rate=Decimal("0.001"),
        half_spread_bps=Decimal("5"),
        slippage_bps=Decimal("10"),
        latency_bars=0,
        price_tick=Decimal("0.01"),
        quantity_step=Decimal("0.0001"),
        min_quantity=Decimal("0.0001"),
        min_notional=Decimal("1"),
        max_volume_participation=Decimal("0.25"),
    )


def _manifest() -> ExperimentManifest:
    config = known_config()
    return ExperimentManifest(
        schema_version="research-experiment-v1",
        dataset_id="a" * 64,
        canonical_sha256="b" * 64,
        code_commit="1" * 40,
        engine_version="research-engine-v1",
        strategy_id="fixture.scripted.v1",
        strategy_config=(("script", "[]"),),
        initial_cash=Decimal("1000"),
        timing_policy=TimingPolicy.NEXT_CANDLE,
        limit_fill_policy=LimitFillPolicy.CONSERVATIVE,
        default_time_in_force=TimeInForce.BAR,
        max_active_candles=3,
        random_seed=0,
        simulation_config_sha256=hashlib.sha256(serialize_simulation_config(config)).hexdigest(),
    )


def _order(order_id: str, side: OrderSide) -> SimulatedOrder:
    return SimulatedOrder(
        order_id=order_id,
        decision_sequence=1 if side is OrderSide.BUY else 2,
        intent_sequence=1,
        created_candle_index=0 if side is OrderSide.BUY else 2,
        eligible_candle_index=1 if side is OrderSide.BUY else 3,
        expires_after_candle_index=1 if side is OrderSide.BUY else 3,
        side=side,
        order_type=OrderType.MARKET,
        requested_quantity=Decimal("2"),
        filled_quantity=Decimal("2"),
        limit_price=None,
        time_in_force=TimeInForce.BAR,
        status=OrderStatus.FILLED,
    )


def _fill(
    fill_id: str,
    order_id: str,
    candle_index: int,
    price: Decimal,
    fee: Decimal,
) -> Fill:
    return Fill(
        fill_id=fill_id,
        order_id=order_id,
        candle_index=candle_index,
        candle_open_time=datetime(2025, 1, candle_index + 1, tzinfo=UTC),
        quantity=Decimal("2"),
        reference_price=price,
        fill_price=price,
        notional=price * Decimal("2"),
        fee=fee,
        spread_cost=Decimal("0.50"),
        slippage_cost=Decimal("0.50"),
        price_was_rounded=False,
        quantity_was_rounded=False,
    )


def known_evidence() -> BacktestEvidence:
    buy_order = _order("buy-order", OrderSide.BUY)
    sell_order = _order("sell-order", OrderSide.SELL_TO_CLOSE)
    buy_fill = _fill("buy-fill", buy_order.order_id, 1, Decimal("100"), Decimal("1.00"))
    sell_fill = _fill("sell-fill", sell_order.order_id, 3, Decimal("110"), Decimal("1.20"))
    after_buy = AccountSnapshot(
        cash=Decimal("799.00"),
        reserved_cash=Decimal("0"),
        position_quantity=Decimal("2"),
        average_entry_price=Decimal("100.50"),
        realized_pnl=Decimal("0"),
        cumulative_fees=Decimal("1.00"),
        cumulative_execution_costs=Decimal("1.00"),
        marked_equity=Decimal("999.00"),
        peak_equity=Decimal("1000.00"),
        drawdown=Decimal("0.001"),
        position_cost_basis=Decimal("201.00"),
    )
    terminal = AccountSnapshot(
        cash=Decimal("1017.80"),
        reserved_cash=Decimal("0"),
        position_quantity=Decimal("0"),
        average_entry_price=Decimal("0"),
        realized_pnl=Decimal("17.80"),
        cumulative_fees=Decimal("2.20"),
        cumulative_execution_costs=Decimal("2.00"),
        marked_equity=Decimal("1017.80"),
        peak_equity=Decimal("1017.80"),
        drawdown=Decimal("0"),
        position_cost_basis=Decimal("0"),
    )
    ledger = (
        LedgerEntry(
            sequence=1,
            event_type="fill.buy",
            order_id=buy_order.order_id,
            fill_id=buy_fill.fill_id,
            cash_delta=Decimal("-201.00"),
            position_delta=Decimal("2"),
            fee_delta=Decimal("1.00"),
            resulting_cash=Decimal("799.00"),
            resulting_position=Decimal("2"),
        ),
        LedgerEntry(
            sequence=2,
            event_type="fill.sell_to_close",
            order_id=sell_order.order_id,
            fill_id=sell_fill.fill_id,
            cash_delta=Decimal("218.80"),
            position_delta=Decimal("-2"),
            fee_delta=Decimal("1.20"),
            resulting_cash=Decimal("1017.80"),
            resulting_position=Decimal("0"),
        ),
    )
    return BacktestEvidence(
        experiment_manifest=_manifest(),
        decisions=(),
        orders=(buy_order, sell_order),
        fills=(buy_fill, sell_fill),
        ledger=ledger,
        account_series=(after_buy, terminal),
        rejection_records=(),
        terminal_account=terminal,
    )


def test_metrics_report_gross_net_costs_drawdown_and_counts() -> None:
    metrics = calculate_metrics(known_evidence())

    assert metrics.starting_equity == Decimal("1000")
    assert metrics.ending_equity == Decimal("1017.80")
    assert metrics.gross_return == Decimal("0.022")
    assert metrics.net_return == Decimal("0.0178")
    assert metrics.realized_pnl == Decimal("17.80")
    assert metrics.unrealized_pnl == Decimal("0")
    assert metrics.total_fees == Decimal("2.20")
    assert metrics.total_execution_costs == Decimal("2.00")
    assert metrics.maximum_drawdown == Decimal("0.001")
    assert metrics.exposure_fraction == Decimal("0.5")
    assert metrics.order_count == 2
    assert metrics.rejection_count == 0
    assert metrics.fill_count == 2
    assert metrics.partial_fill_count == 0
    assert metrics.trade_count == 1
    assert metrics.win_rate == Decimal("1")


def test_expanded_metrics_use_the_locked_four_hour_formulas() -> None:
    metrics = calculate_metrics(known_evidence())

    assert metrics.observed_periods == 2
    assert float(metrics.annualized_geometric_return) == pytest.approx(245685177.96318755)
    assert float(metrics.annualized_volatility) == pytest.approx(0.46373495092219325)
    assert float(metrics.downside_deviation) == pytest.approx(0.0330907842155486)
    assert metrics.sortino_ratio is not None
    assert float(metrics.sortino_ratio) == pytest.approx(7424580099.487208)
    assert metrics.return_to_drawdown is not None
    assert float(metrics.return_to_drawdown) == pytest.approx(245685177963.18753)
    assert float(metrics.turnover) == pytest.approx(0.41650138833796113)
    assert metrics.exposure_adjusted_return == Decimal("0.0356")
    assert metrics.profit_factor is None


def test_undefined_expanded_metric_denominators_return_none() -> None:
    evidence = known_evidence()
    flat = AccountSnapshot.initial(Decimal("1000"))
    no_activity = replace(
        evidence,
        orders=(),
        fills=(),
        ledger=(),
        account_series=(flat, flat),
        terminal_account=flat,
    )

    metrics = calculate_metrics(no_activity)

    assert metrics.sortino_ratio is None
    assert metrics.return_to_drawdown is None
    assert metrics.exposure_adjusted_return is None
    assert metrics.profit_factor is None
    assert metrics.turnover == Decimal("0")


def test_completed_trade_reconciles_entry_cost_and_exit_proceeds() -> None:
    trades = completed_trades(known_evidence())

    assert len(trades) == 1
    assert trades[0].entry_candle_index == 1
    assert trades[0].exit_candle_index == 3
    assert trades[0].hold_candles == 2
    assert trades[0].entry_cost == Decimal("201.00")
    assert trades[0].exit_proceeds == Decimal("218.80")
    assert trades[0].gross_return == Decimal("0.1")
    assert trades[0].net_return == Decimal("0.088557213930348258706467661691542")
    assert trades[0].realized_pnl == Decimal("17.80")
    assert trades[0].winning is True
