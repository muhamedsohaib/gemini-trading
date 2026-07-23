"""Tests for deterministic market and limit fill evaluation."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from gemini_trading.domain.account import AccountSnapshot
from gemini_trading.domain.candle import Candle
from gemini_trading.domain.experiment import LimitFillPolicy
from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.order import (
    OrderSide,
    OrderStatus,
    OrderType,
    SimulatedOrder,
    TimeInForce,
)
from gemini_trading.domain.timeframe import Timeframe
from gemini_trading.execution.simulator.fills import evaluate_order
from gemini_trading.research.config import SimulationConfig


def _config(**overrides: object) -> SimulationConfig:
    values: dict[str, object] = {
        "maker_fee_rate": Decimal("0.001"),
        "taker_fee_rate": Decimal("0.001"),
        "half_spread_bps": Decimal("5"),
        "slippage_bps": Decimal("10"),
        "latency_bars": 0,
        "price_tick": Decimal("0.01"),
        "quantity_step": Decimal("0.0001"),
        "min_quantity": Decimal("0.0001"),
        "min_notional": Decimal("5"),
        "max_volume_participation": Decimal("0.25"),
    }
    values.update(overrides)
    return SimulationConfig.official(**values)  # type: ignore[arg-type]


def _candle(**overrides: Decimal) -> Candle:
    values = {
        "open": Decimal("100"),
        "high": Decimal("110"),
        "low": Decimal("90"),
        "close": Decimal("105"),
        "volume": Decimal("20"),
    }
    values.update(overrides)
    return Candle(
        instrument=Instrument("ETHUSDT", "ETH", "USDT"),
        timeframe=Timeframe.H4,
        open_time=datetime(2025, 1, 1, tzinfo=UTC),
        close_time=datetime(2025, 1, 1, tzinfo=UTC) + timedelta(hours=4) - timedelta(milliseconds=1),
        completed=True,
        source_provider="binance_spot",
        **values,
    )


def _order(
    *,
    side: OrderSide = OrderSide.BUY,
    order_type: OrderType = OrderType.LIMIT,
    quantity: Decimal = Decimal("1"),
    limit_price: Decimal | None = Decimal("100"),
) -> SimulatedOrder:
    return SimulatedOrder(
        order_id="order-1",
        decision_sequence=1,
        intent_sequence=1,
        created_candle_index=0,
        eligible_candle_index=0,
        expires_after_candle_index=3,
        side=side,
        order_type=order_type,
        requested_quantity=quantity,
        filled_quantity=Decimal("0"),
        limit_price=limit_price,
        time_in_force=TimeInForce.BAR,
        status=OrderStatus.ACCEPTED,
    )


def _account(cash: Decimal = Decimal("1000"), position: Decimal = Decimal("0")) -> AccountSnapshot:
    if position == 0:
        return AccountSnapshot.initial(cash)
    return AccountSnapshot(
        cash=cash,
        reserved_cash=Decimal("0"),
        position_quantity=position,
        average_entry_price=Decimal("95"),
        realized_pnl=Decimal("0"),
        cumulative_fees=Decimal("0"),
        cumulative_execution_costs=Decimal("0"),
        marked_equity=cash + position * Decimal("100"),
        peak_equity=cash + position * Decimal("100"),
        drawdown=Decimal("0"),
    )


def test_conservative_buy_limit_requires_strict_cross() -> None:
    result = evaluate_order(
        _order(),
        _candle(low=Decimal("100")),
        _account(),
        _config(),
        0,
        Decimal("0"),
    )

    assert result.fill is None
    assert result.reason == "limit_not_strictly_crossed"


def test_optimistic_touch_policy_fills_touch_but_is_non_promotable() -> None:
    config = replace(
        _config(),
        limit_fill_policy=LimitFillPolicy.OPTIMISTIC_TOUCH_DIAGNOSTIC,
        promotable=False,
    )

    result = evaluate_order(
        _order(),
        _candle(low=Decimal("100")),
        _account(),
        config,
        0,
        Decimal("0"),
    )

    assert config.promotable is False
    assert result.fill is not None
    assert result.fill.fill_price == Decimal("100")


def test_partial_fill_is_capped_by_volume_participation_and_cash() -> None:
    result = evaluate_order(
        _order(order_type=OrderType.MARKET, quantity=Decimal("10"), limit_price=None),
        _candle(),
        _account(cash=Decimal("350")),
        _config(),
        0,
        Decimal("0"),
    )

    assert result.fill is not None
    assert Decimal("0") < result.fill.quantity <= Decimal("3.5")
    assert result.order.status is OrderStatus.PARTIALLY_FILLED
    assert result.reason == "partial_fill"


def test_sell_quantity_is_capped_by_owned_position() -> None:
    result = evaluate_order(
        _order(
            side=OrderSide.SELL_TO_CLOSE,
            order_type=OrderType.MARKET,
            quantity=Decimal("5"),
            limit_price=None,
        ),
        _candle(),
        _account(position=Decimal("1.25")),
        _config(),
        0,
        Decimal("0"),
    )

    assert result.fill is not None
    assert result.fill.quantity == Decimal("1.25")
    assert result.reason == "partial_fill"


def test_order_eligibility_and_expiry_are_enforced() -> None:
    order = replace(_order(), eligible_candle_index=2, expires_after_candle_index=3)

    assert evaluate_order(order, _candle(), _account(), _config(), 1, Decimal("0")).reason == (
        "not_yet_eligible"
    )
    assert evaluate_order(order, _candle(), _account(), _config(), 4, Decimal("0")).reason == (
        "expired"
    )
