"""Deterministic candle-volume participation limits."""

from decimal import Decimal


def _non_negative(value: Decimal, field_name: str) -> None:
    if not value.is_finite() or value < 0:
        raise ValueError(f"{field_name} must be finite and non-negative")


def available_quantity(
    *,
    candle_volume: Decimal,
    participation: Decimal,
    already_consumed: Decimal,
) -> Decimal:
    """Return remaining deterministic quantity available from one candle."""

    _non_negative(candle_volume, "candle_volume")
    _non_negative(already_consumed, "already_consumed")
    if not participation.is_finite() or not Decimal("0") < participation <= Decimal("1"):
        raise ValueError("participation must be greater than zero and no greater than one")
    cap = candle_volume * participation
    return max(Decimal("0"), cap - already_consumed)
