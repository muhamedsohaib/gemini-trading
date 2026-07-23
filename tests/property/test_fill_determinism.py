"""Properties for deterministic fill evaluation."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from gemini_trading.domain.account import AccountSnapshot
from gemini_trading.domain.candle import Candle
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

_QUANTITIES = st.decimals(
    min_value=Decimal("0.0001"),
    max_value=Decimal("100"),
    places=4,
    allow_nan=False,
    allow_infinity=False,
)


def _config() -> SimulationConfig:
    return SimulationConfig.official(
        maker_fee_rate=Decimal("0.001"),
        taker_fee_rate=Decimal("0.001"),
        half_spread_bps=Decimal("5"),
        slippage_bps=Decimal("10"),
        latency_bars=0,
        price_tick=Decimal("0.01"),
        quantity_step=Decimal("0.0001"),
        min_quantity=Decimal("0.0001"),
        min_notional=Decimal("5"),
        max_volume_participation=Decimal("0.25"),
    )


def _candle() -> Candle:
    open_time = datetime(2025, 1, 1, tzinfo=UTC)
    return Candle(
        instrument=Instrument("ETHUSDT", "ETH", "USDT"),
        timeframe=Timeframe.H4,
        open_time=open_time,
        close_time=open_time + timedelta(hours=4) - timedelta(milliseconds=1),
        open=Decimal("100"),
        high=Decimal("110"),
        low=Decimal("90"),
        close=Decimal("105"),
        volume=Decimal("20"),
        completed=True,
        source_provider="binance_spot",
    )


@given(quantity=_QUANTITIES)
def test_repeated_market_evaluation_is_identical(quantity: Decimal) -> None:
    order = SimulatedOrder(
        order_id="order-property",
        decision_sequence=1,
        intent_sequence=1,
        created_candle_index=0,
        eligible_candle_index=0,
        expires_after_candle_index=3,
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        requested_quantity=quantity,
        filled_quantity=Decimal("0"),
        limit_price=None,
        time_in_force=TimeInForce.BAR,
        status=OrderStatus.ACCEPTED,
    )
    account = AccountSnapshot.initial(Decimal("10000"))

    first = evaluate_order(order, _candle(), account, _config(), 0, Decimal("0"))
    second = evaluate_order(order, _candle(), account, _config(), 0, Decimal("0"))

    assert first == second
    assert first.consumed_volume >= 0
