"""Property tests for monotonic Candidate cost-stress results."""

from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from gemini_trading.strategy.evaluation import cost_returns_are_monotonic

_DECIMALS = st.decimals(
    min_value=Decimal("-1"),
    max_value=Decimal("1"),
    allow_nan=False,
    allow_infinity=False,
    places=6,
)
_NON_NEGATIVE = st.decimals(
    min_value=Decimal("0"),
    max_value=Decimal("1"),
    allow_nan=False,
    allow_infinity=False,
    places=6,
)


@given(base=_DECIMALS, first_drag=_NON_NEGATIVE, second_drag=_NON_NEGATIVE)
def test_ordered_cost_stress_returns_are_monotonic(
    base: Decimal,
    first_drag: Decimal,
    second_drag: Decimal,
) -> None:
    one_half = base - first_drag
    double = one_half - second_drag

    assert cost_returns_are_monotonic(base, one_half, double)


def test_cost_improvement_under_more_expensive_execution_is_not_monotonic() -> None:
    assert not cost_returns_are_monotonic(
        Decimal("0.03"),
        Decimal("0.04"),
        Decimal("0.02"),
    )
