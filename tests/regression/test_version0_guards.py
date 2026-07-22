from decimal import Decimal

import pytest

from gemini_trading.safety.regression_guards import (
    CandleCompletionError,
    DecisionRegistry,
    DuplicateDecisionError,
    OrderValidationError,
    Regime,
    build_future_regime_labels,
    parse_regime,
    require_closed_candle,
    validate_price_geometry,
    validate_sell_to_close,
)


def test_trending_down_identity_is_preserved() -> None:
    assert parse_regime("Trending Down") is Regime.TRENDING_DOWN
    assert parse_regime("Trending Up") is Regime.TRENDING_UP


def test_incomplete_candle_is_rejected() -> None:
    with pytest.raises(CandleCompletionError):
        require_closed_candle("0")


def test_trailing_rows_without_future_outcomes_are_unlabeled() -> None:
    labels = build_future_regime_labels(
        closes=[Decimal("100"), Decimal("101"), Decimal("102"), Decimal("103")],
        horizon=2,
        threshold=Decimal("0.005"),
    )

    assert labels[-2:] == [None, None]


def test_duplicate_decision_key_is_rejected() -> None:
    registry = DecisionRegistry()
    registry.register("BTC-USDT:15m:2026-07-21T08:00:00Z:baseline-v1")

    with pytest.raises(DuplicateDecisionError):
        registry.register("BTC-USDT:15m:2026-07-21T08:00:00Z:baseline-v1")


def test_sell_to_close_requires_an_eligible_position() -> None:
    with pytest.raises(OrderValidationError):
        validate_sell_to_close(
            position_quantity=Decimal("0"),
            requested_quantity=Decimal("0.1"),
        )


def test_long_geometry_requires_stop_below_entry_and_target_above_entry() -> None:
    with pytest.raises(OrderValidationError):
        validate_price_geometry(
            side="long",
            entry=Decimal("100"),
            stop=Decimal("101"),
            target=Decimal("103"),
        )


def test_short_geometry_requires_target_below_entry_and_stop_above_entry() -> None:
    with pytest.raises(OrderValidationError):
        validate_price_geometry(
            side="short",
            entry=Decimal("100"),
            stop=Decimal("99"),
            target=Decimal("97"),
        )
