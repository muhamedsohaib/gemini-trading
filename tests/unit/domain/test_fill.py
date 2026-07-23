"""Tests for immutable fill contracts."""

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from gemini_trading.domain.fill import Fill


def _fill() -> Fill:
    return Fill(
        fill_id="fill-1",
        order_id="order-1",
        candle_index=4,
        candle_open_time=datetime(2025, 1, 1, tzinfo=UTC),
        quantity=Decimal("1.25"),
        reference_price=Decimal("100"),
        fill_price=Decimal("100.20"),
        notional=Decimal("125.250"),
        fee=Decimal("0.12525"),
        spread_cost=Decimal("0.125"),
        slippage_cost=Decimal("0.125"),
        price_was_rounded=False,
        quantity_was_rounded=False,
    )


def test_fill_is_immutable_and_requires_utc_time() -> None:
    fill = _fill()

    with pytest.raises(FrozenInstanceError):
        fill.quantity = Decimal("1")  # type: ignore[misc]
    with pytest.raises(ValueError, match="UTC-aware"):
        replace(fill, candle_open_time=datetime(2025, 1, 1))


def test_fill_requires_positive_finite_trade_values() -> None:
    fill = _fill()

    for field_name in ("quantity", "reference_price", "fill_price", "notional"):
        with pytest.raises(ValueError, match=field_name):
            replace(fill, **{field_name: Decimal("0")})
    with pytest.raises(ValueError, match="fee"):
        replace(fill, fee=Decimal("-1"))
    with pytest.raises(ValueError, match="finite"):
        replace(fill, fill_price=Decimal("NaN"))


def test_fill_notional_matches_quantity_times_fill_price() -> None:
    with pytest.raises(ValueError, match="notional"):
        replace(_fill(), notional=Decimal("999"))
