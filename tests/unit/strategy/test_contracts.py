"""Tests for immutable candidate-strategy contracts."""

from decimal import Decimal

import pytest

from gemini_trading.strategy.contracts import (
    GateResult,
    IndexWindow,
    SpecialistKind,
    SpecialistPrediction,
)


def test_index_window_is_strict_and_half_open() -> None:
    window = IndexWindow(start_inclusive=3, end_exclusive=7)

    assert window.contains(3) is True
    assert window.contains(6) is True
    assert window.contains(7) is False


@pytest.mark.parametrize(
    ("start", "end"),
    [(-1, 1), (0, 0), (2, 1), (False, 1), (0, True)],
)
def test_index_window_rejects_invalid_bounds(start: int, end: int) -> None:
    with pytest.raises(ValueError):
        IndexWindow(start_inclusive=start, end_exclusive=end)


def test_specialist_prediction_validates_probability_and_raw_score() -> None:
    prediction = SpecialistPrediction(
        candle_index=42,
        specialist=SpecialistKind.TREND,
        raw_score_hex=(1.25).hex(),
        probability=Decimal("0.62"),
        expected_gross_return=Decimal("0.0071"),
    )

    assert prediction.raw_score_hex == "0x1.4000000000000p+0"

    with pytest.raises(ValueError, match="probability"):
        SpecialistPrediction(
            candle_index=42,
            specialist=SpecialistKind.TREND,
            raw_score_hex=(1.25).hex(),
            probability=Decimal("1.01"),
            expected_gross_return=Decimal("0.0071"),
        )
    with pytest.raises(ValueError, match="raw_score_hex"):
        SpecialistPrediction(
            candle_index=42,
            specialist=SpecialistKind.TREND,
            raw_score_hex="not-a-float",
            probability=Decimal("0.62"),
            expected_gross_return=Decimal("0.0071"),
        )


def test_gate_result_requires_explicit_evidence() -> None:
    gate = GateResult(
        gate_id="final.net_return.positive",
        passed=True,
        observed="0.04",
        required="> 0",
        reason="base-cost final-test return is positive",
    )

    assert gate.passed is True
    with pytest.raises(ValueError, match="reason"):
        GateResult(
            gate_id="final.net_return.positive",
            passed=False,
            observed="-0.01",
            required="> 0",
            reason=" ",
        )
