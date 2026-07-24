"""RED tests for fold-local probability and expected-return calibration."""

from decimal import Decimal

import pytest

from gemini_trading.strategy.calibration import (
    apply_expected_return,
    apply_platt,
    brier_score,
    expected_calibration_error,
    fit_expected_return_map,
    fit_platt_calibrator,
    log_loss_score,
    serialize_platt_artifact,
)
from gemini_trading.strategy.errors import InsufficientCalibrationError


def calibration_scores() -> tuple[float, ...]:
    return tuple((index - 120) / 20 for index in range(240))


def calibration_labels() -> tuple[bool, ...]:
    return tuple(index % 5 in {0, 1} for index in range(240))


def test_calibration_requires_minimum_classes() -> None:
    with pytest.raises(InsufficientCalibrationError, match="40 positive"):
        fit_platt_calibrator([0.0] * 200, [False] * 180 + [True] * 20)


def test_platt_fit_is_deterministic_and_probability_is_bounded() -> None:
    first = fit_platt_calibrator(calibration_scores(), calibration_labels())
    second = fit_platt_calibrator(calibration_scores(), calibration_labels())
    values = [apply_platt(first, score) for score in (-1e9, -10.0, 0.0, 10.0, 1e9)]

    assert serialize_platt_artifact(first) == serialize_platt_artifact(second)
    assert all(Decimal("0") <= value <= Decimal("1") for value in values)
    assert first.observation_count == 240
    assert first.positive_count == 96
    assert first.negative_count == 144


def test_expected_return_map_clamps_to_calibration_probability_range() -> None:
    probabilities = tuple(Decimal(index) / Decimal("100") for index in range(10, 90))
    gross_returns = tuple(Decimal("-0.01") + value * Decimal("0.03") for value in probabilities)
    mapping = fit_expected_return_map(probabilities, gross_returns)

    assert apply_expected_return(mapping, Decimal("0")) == apply_expected_return(
        mapping,
        Decimal("0.10"),
    )
    assert apply_expected_return(mapping, Decimal("1")) == apply_expected_return(
        mapping,
        Decimal("0.89"),
    )
    assert apply_expected_return(mapping, Decimal("0.50")) == Decimal("0.005")


def test_calibration_metrics_use_locked_formulas() -> None:
    probabilities = (Decimal("0.1"), Decimal("0.8"), Decimal("0.6"), Decimal("0.2"))
    labels = (False, True, False, True)

    assert brier_score(probabilities, labels) == Decimal("0.2625")
    assert log_loss_score(probabilities, labels) > Decimal("0")
    assert Decimal("0") <= expected_calibration_error(probabilities, labels) <= Decimal("1")
