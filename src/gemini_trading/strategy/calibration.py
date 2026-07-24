"""Fold-local deterministic calibration and expected-return mapping."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext

from gemini_trading.research.serialization import canonical_json_bytes
from gemini_trading.strategy.errors import (
    InsufficientCalibrationError,
    ModelDeterminismError,
    ProbabilityRangeError,
)

_CONTEXT = Context(prec=34, rounding=ROUND_HALF_EVEN)
_STABILIZER = 1e-12
_PARAMETER_TOLERANCE = 1e-12
_MAX_ITERATIONS = 100
_LOG_LOSS_FLOOR = 1e-15


def _validate_hex(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    try:
        decoded = float.fromhex(normalized)
    except ValueError:
        raise ValueError(f"{field_name} must contain a hexadecimal float") from None
    if not math.isfinite(decoded):
        raise ValueError(f"{field_name} must contain a finite hexadecimal float")
    return normalized


def _decimal(value: float) -> Decimal:
    if not math.isfinite(value):
        raise ProbabilityRangeError("calibration output must be finite")
    return Decimal(repr(value))


@dataclass(frozen=True, slots=True)
class PlattArtifact:
    """Portable two-parameter Platt probability calibration artifact."""

    schema_version: str
    slope_hex: str
    intercept_hex: str
    minimum_probability_hex: str
    maximum_probability_hex: str
    observation_count: int
    positive_count: int
    negative_count: int

    def __post_init__(self) -> None:
        if not self.schema_version.strip():
            raise ValueError("schema_version must not be empty")
        for field_name in (
            "slope_hex",
            "intercept_hex",
            "minimum_probability_hex",
            "maximum_probability_hex",
        ):
            object.__setattr__(self, field_name, _validate_hex(getattr(self, field_name), field_name))
        minimum = float.fromhex(self.minimum_probability_hex)
        maximum = float.fromhex(self.maximum_probability_hex)
        if not 0 <= minimum <= maximum <= 1:
            raise ValueError("calibration probability range must be within [0, 1]")
        for field_name in ("observation_count", "positive_count", "negative_count"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or value < 0:
                raise ValueError(f"{field_name} must be non-negative")
        if self.positive_count + self.negative_count != self.observation_count:
            raise ValueError("calibration class counts must sum to observation_count")


@dataclass(frozen=True, slots=True)
class ExpectedReturnMap:
    """Fold-local linear expected-gross-return map over calibrated probability."""

    schema_version: str
    intercept: Decimal
    slope: Decimal
    minimum_probability: Decimal
    maximum_probability: Decimal
    observation_count: int

    def __post_init__(self) -> None:
        if not self.schema_version.strip():
            raise ValueError("schema_version must not be empty")
        for field_name in ("intercept", "slope", "minimum_probability", "maximum_probability"):
            if not getattr(self, field_name).is_finite():
                raise ValueError(f"{field_name} must be finite")
        if not Decimal("0") <= self.minimum_probability <= self.maximum_probability <= Decimal("1"):
            raise ValueError("expected-return probability range must be within [0, 1]")
        if isinstance(self.observation_count, bool) or self.observation_count < 2:
            raise ValueError("observation_count must be at least two")


def _sigmoid(value: float) -> float:
    if value >= 0:
        negative_exponential = math.exp(-value)
        return 1 / (1 + negative_exponential)
    exponential = math.exp(value)
    return exponential / (1 + exponential)


def fit_platt_calibrator(
    raw_scores: Sequence[float],
    labels: Sequence[bool],
    *,
    minimum_observations: int = 200,
    minimum_positive: int = 40,
    minimum_negative: int = 40,
) -> PlattArtifact:
    """Fit one deterministic fold-local Platt calibrator with Newton-Raphson."""

    scores = tuple(float(value) for value in raw_scores)
    targets = tuple(bool(value) for value in labels)
    if len(scores) != len(targets):
        raise ValueError("calibration scores and labels must have equal length")
    if len(scores) < minimum_observations:
        raise InsufficientCalibrationError(
            f"calibration requires at least {minimum_observations} observations"
        )
    if any(not math.isfinite(value) for value in scores):
        raise ValueError("calibration scores must be finite")
    positive = sum(targets)
    negative = len(targets) - positive
    if positive < minimum_positive:
        raise InsufficientCalibrationError(
            f"calibration requires at least {minimum_positive} positive labels"
        )
    if negative < minimum_negative:
        raise InsufficientCalibrationError(
            f"calibration requires at least {minimum_negative} negative labels"
        )
    slope = 0.0
    intercept = math.log(positive / negative)
    converged = False
    for _ in range(_MAX_ITERATIONS):
        gradient_slope = 0.0
        gradient_intercept = 0.0
        hessian_slope = _STABILIZER
        hessian_cross = 0.0
        hessian_intercept = _STABILIZER
        for score, target in zip(scores, targets, strict=True):
            probability = _sigmoid(slope * score + intercept)
            residual = probability - (1.0 if target else 0.0)
            weight = probability * (1 - probability)
            gradient_slope += residual * score
            gradient_intercept += residual
            hessian_slope += weight * score * score
            hessian_cross += weight * score
            hessian_intercept += weight
        determinant = hessian_slope * hessian_intercept - hessian_cross * hessian_cross
        if not math.isfinite(determinant) or abs(determinant) <= _STABILIZER:
            raise ModelDeterminismError("Platt calibration Hessian is singular")
        delta_slope = (
            gradient_slope * hessian_intercept - gradient_intercept * hessian_cross
        ) / determinant
        delta_intercept = (
            gradient_intercept * hessian_slope - gradient_slope * hessian_cross
        ) / determinant
        slope -= delta_slope
        intercept -= delta_intercept
        if not math.isfinite(slope) or not math.isfinite(intercept):
            raise ModelDeterminismError("Platt calibration produced non-finite parameters")
        if max(abs(delta_slope), abs(delta_intercept)) <= _PARAMETER_TOLERANCE:
            converged = True
            break
    if not converged:
        raise ModelDeterminismError("Platt calibration did not converge")
    probabilities = tuple(_sigmoid(slope * score + intercept) for score in scores)
    return PlattArtifact(
        schema_version="candidate-platt-v1",
        slope_hex=slope.hex(),
        intercept_hex=intercept.hex(),
        minimum_probability_hex=min(probabilities).hex(),
        maximum_probability_hex=max(probabilities).hex(),
        observation_count=len(scores),
        positive_count=positive,
        negative_count=negative,
    )


def apply_platt(artifact: PlattArtifact, raw_score: float) -> Decimal:
    """Apply stable bounded Platt inference to one finite raw score."""

    score = float(raw_score)
    if not math.isfinite(score):
        raise ProbabilityRangeError("raw calibration score must be finite")
    probability = _sigmoid(
        float.fromhex(artifact.slope_hex) * score + float.fromhex(artifact.intercept_hex)
    )
    if not 0 <= probability <= 1:
        raise ProbabilityRangeError("calibrated probability must be within [0, 1]")
    return _decimal(probability)


def serialize_platt_artifact(artifact: PlattArtifact) -> bytes:
    """Return canonical portable Platt artifact bytes."""

    return canonical_json_bytes(
        {
            "schema_version": artifact.schema_version,
            "slope_hex": artifact.slope_hex,
            "intercept_hex": artifact.intercept_hex,
            "minimum_probability_hex": artifact.minimum_probability_hex,
            "maximum_probability_hex": artifact.maximum_probability_hex,
            "observation_count": artifact.observation_count,
            "positive_count": artifact.positive_count,
            "negative_count": artifact.negative_count,
        }
    )


def fit_expected_return_map(
    probabilities: Sequence[Decimal],
    gross_returns: Sequence[Decimal],
) -> ExpectedReturnMap:
    """Fit exact Decimal OLS from calibrated probability to gross return."""

    probability_values = tuple(probabilities)
    return_values = tuple(gross_returns)
    if len(probability_values) != len(return_values):
        raise ValueError("probabilities and gross returns must have equal length")
    if len(probability_values) < 2:
        raise InsufficientCalibrationError("expected-return map requires at least two observations")
    if any(
        not value.is_finite() or not Decimal("0") <= value <= Decimal("1")
        for value in probability_values
    ):
        raise ProbabilityRangeError("expected-return probabilities must be finite within [0, 1]")
    if any(not value.is_finite() for value in return_values):
        raise ValueError("expected-return gross returns must be finite")
    with localcontext(_CONTEXT):
        count = Decimal(len(probability_values))
        mean_probability = sum(probability_values, Decimal("0")) / count
        mean_return = sum(return_values, Decimal("0")) / count
        variance = sum((value - mean_probability) ** 2 for value in probability_values)
        if variance == 0:
            raise InsufficientCalibrationError("expected-return probability variance must be positive")
        covariance = sum(
            (probability - mean_probability) * (gross_return - mean_return)
            for probability, gross_return in zip(
                probability_values,
                return_values,
                strict=True,
            )
        )
        slope = covariance / variance
        intercept = mean_return - slope * mean_probability
    return ExpectedReturnMap(
        schema_version="candidate-expected-return-map-v1",
        intercept=intercept,
        slope=slope,
        minimum_probability=min(probability_values),
        maximum_probability=max(probability_values),
        observation_count=len(probability_values),
    )


def apply_expected_return(mapping: ExpectedReturnMap, probability: Decimal) -> Decimal:
    """Apply the OLS map after clamping to the fold-local calibration range."""

    if not probability.is_finite() or not Decimal("0") <= probability <= Decimal("1"):
        raise ProbabilityRangeError("expected-return probability must be finite within [0, 1]")
    clamped = min(max(probability, mapping.minimum_probability), mapping.maximum_probability)
    with localcontext(_CONTEXT):
        return mapping.intercept + mapping.slope * clamped


def brier_score(probabilities: Sequence[Decimal], labels: Sequence[bool]) -> Decimal:
    """Return exact mean squared probability error."""

    probability_values, targets = _metric_inputs(probabilities, labels)
    with localcontext(_CONTEXT):
        return sum(
            (probability - (Decimal("1") if target else Decimal("0"))) ** 2
            for probability, target in zip(probability_values, targets, strict=True)
        ) / Decimal(len(probability_values))


def log_loss_score(probabilities: Sequence[Decimal], labels: Sequence[bool]) -> Decimal:
    """Return binary log loss with the locked clipping interval."""

    probability_values, targets = _metric_inputs(probabilities, labels)
    losses: list[float] = []
    for probability, target in zip(probability_values, targets, strict=True):
        value = min(max(float(probability), _LOG_LOSS_FLOOR), 1 - _LOG_LOSS_FLOOR)
        losses.append(-math.log(value if target else 1 - value))
    return _decimal(math.fsum(losses) / len(losses))


def expected_calibration_error(
    probabilities: Sequence[Decimal],
    labels: Sequence[bool],
) -> Decimal:
    """Return ten-bin expected calibration error."""

    probability_values, targets = _metric_inputs(probabilities, labels)
    total = Decimal(len(probability_values))
    result = Decimal("0")
    with localcontext(_CONTEXT):
        for bin_index in range(10):
            lower = Decimal(bin_index) / Decimal("10")
            upper = Decimal(bin_index + 1) / Decimal("10")
            members = tuple(
                index
                for index, probability in enumerate(probability_values)
                if lower <= probability < upper or (bin_index == 9 and probability == Decimal("1"))
            )
            if not members:
                continue
            mean_probability = sum(
                (probability_values[index] for index in members),
                Decimal("0"),
            ) / Decimal(len(members))
            positive_fraction = sum(
                (Decimal("1") if targets[index] else Decimal("0") for index in members),
                Decimal("0"),
            ) / Decimal(len(members))
            result += Decimal(len(members)) / total * abs(mean_probability - positive_fraction)
    return result


def _metric_inputs(
    probabilities: Sequence[Decimal],
    labels: Sequence[bool],
) -> tuple[tuple[Decimal, ...], tuple[bool, ...]]:
    probability_values = tuple(probabilities)
    targets = tuple(bool(value) for value in labels)
    if not probability_values or len(probability_values) != len(targets):
        raise ValueError("metric probabilities and labels must be non-empty and equal length")
    if any(
        not value.is_finite() or not Decimal("0") <= value <= Decimal("1")
        for value in probability_values
    ):
        raise ProbabilityRangeError("metric probabilities must be finite within [0, 1]")
    return probability_values, targets
