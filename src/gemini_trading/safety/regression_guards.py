"""Pure guards that prevent known Version 0 failure modes."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Literal


class Regime(StrEnum):
    RANGING = "Ranging"
    TRENDING_UP = "Trending Up"
    TRENDING_DOWN = "Trending Down"


class CandleCompletionError(ValueError):
    """Raised when a closed-candle workflow receives an incomplete candle."""


class DuplicateDecisionError(ValueError):
    """Raised when a deterministic decision identity is reused."""


class OrderValidationError(ValueError):
    """Raised when an order request violates a safety invariant."""


def parse_regime(value: str) -> Regime:
    normalized = " ".join(value.strip().split())
    try:
        return Regime(normalized)
    except ValueError as exc:
        raise ValueError(f"Unsupported regime: {value!r}") from exc


def require_closed_candle(confirm: str) -> None:
    if confirm != "1":
        raise CandleCompletionError("Closed-candle workflows require confirm='1'.")


def build_future_regime_labels(
    closes: list[Decimal],
    horizon: int,
    threshold: Decimal,
) -> list[Regime | None]:
    if horizon <= 0:
        raise ValueError("horizon must be positive")
    if threshold <= 0:
        raise ValueError("threshold must be positive")

    labels: list[Regime | None] = []
    for index, close in enumerate(closes):
        future_index = index + horizon
        if future_index >= len(closes):
            labels.append(None)
            continue
        if close <= 0:
            raise ValueError("close prices must be positive")

        future_return = closes[future_index] / close - Decimal("1")
        if future_return > threshold:
            labels.append(Regime.TRENDING_UP)
        elif future_return < -threshold:
            labels.append(Regime.TRENDING_DOWN)
        else:
            labels.append(Regime.RANGING)
    return labels


class DecisionRegistry:
    def __init__(self) -> None:
        self._keys: set[str] = set()

    def register(self, decision_key: str) -> None:
        if not decision_key.strip():
            raise ValueError("decision_key must not be empty")
        if decision_key in self._keys:
            raise DuplicateDecisionError(decision_key)
        self._keys.add(decision_key)


def validate_sell_to_close(
    position_quantity: Decimal,
    requested_quantity: Decimal,
) -> None:
    if requested_quantity <= 0:
        raise OrderValidationError("requested quantity must be positive")
    if position_quantity <= 0:
        raise OrderValidationError("sell-to-close requires an eligible long position")
    if requested_quantity > position_quantity:
        raise OrderValidationError("sell-to-close quantity exceeds the open position")


def validate_price_geometry(
    side: Literal["long", "short"],
    entry: Decimal,
    stop: Decimal,
    target: Decimal,
) -> None:
    if min(entry, stop, target) <= 0:
        raise OrderValidationError("entry, stop, and target must be positive")
    if side == "long" and not stop < entry < target:
        raise OrderValidationError("long geometry requires stop < entry < target")
    if side == "short" and not target < entry < stop:
        raise OrderValidationError("short geometry requires target < entry < stop")
