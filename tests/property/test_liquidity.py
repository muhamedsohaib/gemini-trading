"""Properties for deterministic candle-volume participation."""

from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from gemini_trading.execution.simulator.liquidity import available_quantity

_DECIMALS = st.decimals(
    min_value=Decimal("0"),
    max_value=Decimal("100000"),
    places=4,
    allow_nan=False,
    allow_infinity=False,
)
_PARTICIPATION = st.decimals(
    min_value=Decimal("0.0001"),
    max_value=Decimal("1"),
    places=4,
    allow_nan=False,
    allow_infinity=False,
)


@given(candle_volume=_DECIMALS, participation=_PARTICIPATION, consumed=_DECIMALS)
def test_available_quantity_is_bounded_and_deterministic(
    candle_volume: Decimal,
    participation: Decimal,
    consumed: Decimal,
) -> None:
    first = available_quantity(
        candle_volume=candle_volume,
        participation=participation,
        already_consumed=consumed,
    )
    second = available_quantity(
        candle_volume=candle_volume,
        participation=participation,
        already_consumed=consumed,
    )

    assert first == second
    assert first >= 0
    assert first <= candle_volume * participation
    assert first == max(Decimal("0"), candle_volume * participation - consumed)


def test_available_quantity_rejects_invalid_participation() -> None:
    with pytest.raises(ValueError, match="participation"):
        available_quantity(
            candle_volume=Decimal("10"),
            participation=Decimal("1.1"),
            already_consumed=Decimal("0"),
        )
