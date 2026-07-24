"""RED tests for conservative cost-aware Candidate v0.1 labels."""

from dataclasses import replace
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext

from gemini_trading.domain.candle import Candle
from gemini_trading.domain.order import OrderSide
from gemini_trading.execution.simulator.costs import market_fill_costs
from gemini_trading.execution.simulator.precision import round_fill_price
from gemini_trading.strategy.labels import LabelPolicy
from strategy_fixture_support import base_simulation, rising_candles


def _label_fixture() -> tuple[Candle, ...]:
    candles = list(rising_candles(50))
    entry = candles[43]
    exit_candle = candles[46]
    candles[43] = replace(
        entry,
        open=Decimal("10000"),
        high=Decimal("10020"),
        low=Decimal("9980"),
        close=Decimal("10010"),
    )
    candles[46] = replace(
        exit_candle,
        open=Decimal("10150"),
        high=Decimal("10170"),
        low=Decimal("10120"),
        close=Decimal("10160"),
    )
    return tuple(candles)


def test_label_uses_next_open_and_exit_after_three_held_candles() -> None:
    config = base_simulation()
    labels = LabelPolicy.locked_v0_1(config).build(
        _label_fixture(),
        eligible_indices=(42,),
    )
    observation = labels.for_index(42)

    buy_costs = market_fill_costs(
        reference_price=Decimal("10000"),
        quantity=Decimal("1"),
        side=OrderSide.BUY,
        half_spread_bps=config.half_spread_bps,
        slippage_bps=config.slippage_bps,
        fee_rate=config.taker_fee_rate,
    )
    sell_costs = market_fill_costs(
        reference_price=Decimal("10150"),
        quantity=Decimal("1"),
        side=OrderSide.SELL_TO_CLOSE,
        half_spread_bps=config.half_spread_bps,
        slippage_bps=config.slippage_bps,
        fee_rate=config.taker_fee_rate,
    )
    expected_buy = round_fill_price(buy_costs.fill_price, config.price_tick, OrderSide.BUY)
    expected_sell = round_fill_price(
        sell_costs.fill_price,
        config.price_tick,
        OrderSide.SELL_TO_CLOSE,
    )
    with localcontext(Context(prec=34, rounding=ROUND_HALF_EVEN)):
        buy_notional = expected_buy
        sell_notional = expected_sell
        buy_fee = buy_notional * config.taker_fee_rate
        sell_fee = sell_notional * config.taker_fee_rate
        expected_gross = expected_sell / expected_buy - Decimal("1")
        expected_net = (sell_notional - sell_fee - buy_notional - buy_fee) / (
            buy_notional + buy_fee
        )

    assert observation.decision_candle_index == 42
    assert observation.entry_candle_index == 43
    assert observation.exit_candle_index == 46
    assert observation.entry_fill_price == expected_buy
    assert observation.exit_fill_price == expected_sell
    assert observation.gross_return == expected_gross
    assert observation.net_return == expected_net
    assert observation.hurdle_bps == Decimal("60")
    assert observation.positive is (expected_net > Decimal("0.006"))


def test_label_vector_is_ordered_and_omits_unresolved_outcomes() -> None:
    candles = rising_candles(50)
    labels = LabelPolicy.locked_v0_1(base_simulation()).build(
        candles,
        eligible_indices=(44, 42, 49, 43),
    )

    assert tuple(item.decision_candle_index for item in labels.observations) == (
        42,
        43,
        44,
    )
    assert labels.horizon_candles == 3


def test_candles_after_the_exit_cannot_change_a_prior_label() -> None:
    candles = _label_fixture()
    policy = LabelPolicy.locked_v0_1(base_simulation())
    original = policy.build(candles, eligible_indices=(42,)).for_index(42)
    changed = (
        *candles[:-1],
        replace(
            candles[-1],
            open=Decimal("500000"),
            high=Decimal("500100"),
            low=Decimal("499900"),
            close=Decimal("500050"),
        ),
    )

    assert policy.build(changed, eligible_indices=(42,)).for_index(42) == original
