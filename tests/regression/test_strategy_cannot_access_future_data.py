"""Regression guards preventing future-data access through the strategy boundary."""

from dataclasses import fields
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from gemini_trading.domain.account import AccountSnapshot
from gemini_trading.domain.candle import Candle
from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.timeframe import Timeframe
from gemini_trading.research.contracts import StrategyContext
from gemini_trading.research.errors import StrategyContractError


def _candle(completed: bool) -> Candle:
    return Candle(
        instrument=Instrument("ETHUSDT", "ETH", "USDT"),
        timeframe=Timeframe.H4,
        open_time=datetime(2025, 1, 1, tzinfo=UTC),
        close_time=datetime(2025, 1, 1, tzinfo=UTC)
        + timedelta(hours=4)
        - timedelta(milliseconds=1),
        open=Decimal("100"),
        high=Decimal("110"),
        low=Decimal("90"),
        close=Decimal("105"),
        volume=Decimal("20"),
        completed=completed,
        source_provider="binance_spot",
    )


def test_strategy_context_has_no_forward_access_capability() -> None:
    context = StrategyContext(
        candle_index=0,
        candle=_candle(completed=True),
        account=AccountSnapshot.initial(Decimal("1000")),
        active_orders=(),
    )

    assert {field.name for field in fields(context)} == {
        "candle_index",
        "candle",
        "account",
        "active_orders",
    }
    with pytest.raises(AttributeError):
        _ = context.future_candles  # type: ignore[attr-defined]
    with pytest.raises(AttributeError):
        _ = context.provider  # type: ignore[attr-defined]


def test_incomplete_candle_cannot_cross_strategy_boundary() -> None:
    with pytest.raises(StrategyContractError, match="completed"):
        StrategyContext(
            candle_index=0,
            candle=_candle(completed=False),
            account=AccountSnapshot.initial(Decimal("1000")),
            active_orders=(),
        )
