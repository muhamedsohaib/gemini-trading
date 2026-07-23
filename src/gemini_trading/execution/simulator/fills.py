"""Deterministic candle-based market and limit fill evaluation."""

import hashlib
from dataclasses import dataclass, replace
from decimal import Decimal

from gemini_trading.domain.account import AccountSnapshot
from gemini_trading.domain.candle import Candle
from gemini_trading.domain.experiment import LimitFillPolicy
from gemini_trading.domain.fill import Fill
from gemini_trading.domain.order import OrderSide, OrderStatus, OrderType, SimulatedOrder
from gemini_trading.execution.simulator.costs import FillCosts, market_fill_costs
from gemini_trading.execution.simulator.liquidity import available_quantity
from gemini_trading.execution.simulator.precision import round_fill_price, round_quantity_down
from gemini_trading.research.config import SimulationConfig


@dataclass(frozen=True, slots=True)
class FillEvaluation:
    """One immutable evaluation of an order against a completed candle."""

    order: SimulatedOrder
    fill: Fill | None
    reason: str
    consumed_volume: Decimal


def _no_fill(order: SimulatedOrder, reason: str, consumed_volume: Decimal) -> FillEvaluation:
    return FillEvaluation(order=order, fill=None, reason=reason, consumed_volume=consumed_volume)


def _strictly_crossed(order: SimulatedOrder, candle: Candle, config: SimulationConfig) -> bool:
    limit_price = order.limit_price
    if limit_price is None:
        return False
    optimistic = config.limit_fill_policy is LimitFillPolicy.OPTIMISTIC_TOUCH_DIAGNOSTIC
    if order.side is OrderSide.BUY:
        return candle.low <= limit_price if optimistic else candle.low < limit_price
    return candle.high >= limit_price if optimistic else candle.high > limit_price


def _market_price(
    order: SimulatedOrder,
    reference_price: Decimal,
    config: SimulationConfig,
) -> tuple[Decimal, FillCosts]:
    costs = market_fill_costs(
        reference_price=reference_price,
        quantity=Decimal("1"),
        side=order.side,
        half_spread_bps=config.half_spread_bps,
        slippage_bps=config.slippage_bps,
        fee_rate=config.taker_fee_rate,
    )
    return round_fill_price(costs.fill_price, config.price_tick, order.side), costs


def _candidate_quantity(
    order: SimulatedOrder,
    candle: Candle,
    account: AccountSnapshot,
    config: SimulationConfig,
    consumed_volume: Decimal,
    fill_price: Decimal,
    fee_rate: Decimal,
) -> Decimal:
    liquidity_quantity = available_quantity(
        candle_volume=candle.volume,
        participation=config.max_volume_participation,
        already_consumed=consumed_volume,
    )
    candidate = min(order.remaining_quantity, liquidity_quantity)
    if order.side is OrderSide.BUY:
        affordability = account.cash / (fill_price * (Decimal("1") + fee_rate))
        candidate = min(candidate, affordability)
    else:
        candidate = min(candidate, account.position_quantity)
    return candidate


def _fill_id(order: SimulatedOrder, candle_index: int, quantity: Decimal, price: Decimal) -> str:
    identity = (
        f"{order.order_id}:{candle_index}:{format(quantity, 'f')}:{format(price, 'f')}"
    ).encode()
    return hashlib.sha256(identity).hexdigest()


def evaluate_order(
    order: SimulatedOrder,
    candle: Candle,
    account: AccountSnapshot,
    config: SimulationConfig,
    candle_index: int,
    consumed_volume: Decimal,
    market_reference_price: Decimal | None = None,
) -> FillEvaluation:
    """Evaluate one active order without reading clocks, networks, or random state."""

    if not consumed_volume.is_finite() or consumed_volume < 0:
        raise ValueError("consumed_volume must be finite and non-negative")
    if candle_index < order.eligible_candle_index:
        return _no_fill(order, "not_yet_eligible", consumed_volume)
    if candle_index > order.expires_after_candle_index:
        return _no_fill(order, "expired", consumed_volume)
    if order.status not in {OrderStatus.ACCEPTED, OrderStatus.PARTIALLY_FILLED}:
        return _no_fill(order, "order_not_active", consumed_volume)

    if order.order_type is OrderType.LIMIT:
        if order.limit_price is None or order.limit_price % config.price_tick != 0:
            return _no_fill(order, "invalid_limit_tick", consumed_volume)
        if not _strictly_crossed(order, candle, config):
            return _no_fill(order, "limit_not_strictly_crossed", consumed_volume)
        fill_price = order.limit_price
        fee_rate = config.maker_fee_rate
        raw_market_costs: FillCosts | None = None
    else:
        reference_price = candle.open if market_reference_price is None else market_reference_price
        fill_price, raw_market_costs = _market_price(order, reference_price, config)
        fee_rate = config.taker_fee_rate

    if not candle.low <= fill_price <= candle.high:
        return _no_fill(order, "fill_price_outside_candle", consumed_volume)

    candidate = _candidate_quantity(
        order,
        candle,
        account,
        config,
        consumed_volume,
        fill_price,
        fee_rate,
    )
    if candidate <= 0:
        if (
            available_quantity(
                candle_volume=candle.volume,
                participation=config.max_volume_participation,
                already_consumed=consumed_volume,
            )
            <= 0
        ):
            return _no_fill(order, "no_liquidity", consumed_volume)
        reason = "insufficient_cash" if order.side is OrderSide.BUY else "insufficient_position"
        return _no_fill(order, reason, consumed_volume)

    filled_quantity = round_quantity_down(candidate, config.quantity_step)
    if filled_quantity < config.min_quantity or filled_quantity == 0:
        return _no_fill(order, "below_min_quantity", consumed_volume)
    notional = fill_price * filled_quantity
    if notional < config.min_notional:
        return _no_fill(order, "below_min_notional", consumed_volume)

    if raw_market_costs is None:
        spread_cost = Decimal("0")
        slippage_cost = Decimal("0")
        reference_price = fill_price
        price_was_rounded = False
    else:
        exact_costs = market_fill_costs(
            reference_price=raw_market_costs.reference_price,
            quantity=filled_quantity,
            side=order.side,
            half_spread_bps=config.half_spread_bps,
            slippage_bps=config.slippage_bps,
            fee_rate=fee_rate,
        )
        spread_cost = exact_costs.spread_cost
        slippage_cost = exact_costs.slippage_cost
        reference_price = exact_costs.reference_price
        price_was_rounded = fill_price != exact_costs.fill_price

    fee = notional * fee_rate
    fill = Fill(
        fill_id=_fill_id(order, candle_index, filled_quantity, fill_price),
        order_id=order.order_id,
        candle_index=candle_index,
        candle_open_time=candle.open_time,
        quantity=filled_quantity,
        reference_price=reference_price,
        fill_price=fill_price,
        notional=notional,
        fee=fee,
        spread_cost=spread_cost,
        slippage_cost=slippage_cost,
        price_was_rounded=price_was_rounded,
        quantity_was_rounded=filled_quantity != candidate,
    )
    total_filled = order.filled_quantity + filled_quantity
    status = (
        OrderStatus.FILLED
        if total_filled == order.requested_quantity
        else OrderStatus.PARTIALLY_FILLED
    )
    updated_order = replace(order, filled_quantity=total_filled, status=status)
    reason = "filled" if status is OrderStatus.FILLED else "partial_fill"
    return FillEvaluation(
        order=updated_order,
        fill=fill,
        reason=reason,
        consumed_volume=consumed_volume + filled_quantity,
    )
