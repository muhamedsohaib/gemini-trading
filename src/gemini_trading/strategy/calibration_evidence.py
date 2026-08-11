"""Persisted fold-local calibration evidence for Candidate v0.2 qualification."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import cast

from gemini_trading.research.serialization import canonical_json_bytes
from gemini_trading.strategy.calibration import (
    ExpectedReturnMap,
    PlattArtifact,
    apply_platt,
    brier_score,
    expected_calibration_error,
    log_loss_score,
)
from gemini_trading.strategy.errors import StudyArtifactError
from gemini_trading.strategy.features import FeatureMatrix
from gemini_trading.strategy.labels import LabelVector
from gemini_trading.strategy.models import ModelArtifact, predict_raw
from gemini_trading.strategy.policy import CandidatePolicy
from gemini_trading.strategy.study_predictions import PredictionBundle

_SCHEMA = "candidate-v0.2-calibration-diagnostic-v1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SPECIALISTS = ("trend", "mean_reversion")
_DECIMAL_FIELDS = (
    "return_map_intercept",
    "return_map_slope",
    "return_map_minimum_probability",
    "return_map_maximum_probability",
    "brier_score",
    "log_loss",
    "expected_calibration_error",
)


@dataclass(frozen=True, slots=True)
class CalibrationDiagnostic:
    """One complete fold/specialist calibration artifact and diagnostic receipt."""

    schema_version: str
    fold_number: int
    specialist: str
    calibration_rows_sha256: str
    platt_schema_version: str
    platt_slope_hex: str
    platt_intercept_hex: str
    platt_minimum_probability_hex: str
    platt_maximum_probability_hex: str
    observation_count: int
    positive_count: int
    negative_count: int
    return_map_schema_version: str
    return_map_intercept: Decimal
    return_map_slope: Decimal
    return_map_minimum_probability: Decimal
    return_map_maximum_probability: Decimal
    return_map_observation_count: int
    brier_score: Decimal
    log_loss: Decimal
    expected_calibration_error: Decimal

    def __post_init__(self) -> None:
        if self.schema_version != _SCHEMA:
            raise StudyArtifactError("unsupported v0.2 calibration diagnostic schema")
        if isinstance(self.fold_number, bool) or not 1 <= self.fold_number <= 12:
            raise StudyArtifactError("invalid v0.2 calibration fold number")
        if self.specialist not in _SPECIALISTS:
            raise StudyArtifactError("invalid v0.2 calibration specialist")
        if _SHA256.fullmatch(self.calibration_rows_sha256) is None:
            raise StudyArtifactError("invalid v0.2 calibration row identity")
        if not self.platt_schema_version or not self.return_map_schema_version:
            raise StudyArtifactError("invalid v0.2 calibration artifact schema")
        for value in (
            self.platt_slope_hex,
            self.platt_intercept_hex,
            self.platt_minimum_probability_hex,
            self.platt_maximum_probability_hex,
        ):
            try:
                decoded = float.fromhex(value)
            except ValueError:
                raise StudyArtifactError("invalid v0.2 calibration hexadecimal value") from None
            if not math.isfinite(decoded):
                raise StudyArtifactError("non-finite v0.2 calibration hexadecimal value")
        if (
            isinstance(self.observation_count, bool)
            or self.observation_count < 1
            or isinstance(self.positive_count, bool)
            or self.positive_count < 0
            or isinstance(self.negative_count, bool)
            or self.negative_count < 0
            or self.positive_count + self.negative_count != self.observation_count
        ):
            raise StudyArtifactError("invalid v0.2 calibration class counts")
        if (
            isinstance(self.return_map_observation_count, bool)
            or self.return_map_observation_count != self.observation_count
        ):
            raise StudyArtifactError("v0.2 calibration return-map population changed")
        for field_name in _DECIMAL_FIELDS:
            if not getattr(self, field_name).is_finite():
                raise StudyArtifactError(f"non-finite v0.2 calibration field: {field_name}")
        if not (
            Decimal("0")
            <= self.return_map_minimum_probability
            <= self.return_map_maximum_probability
            <= Decimal("1")
        ):
            raise StudyArtifactError("invalid v0.2 return-map probability range")
        if not Decimal("0") <= self.brier_score <= Decimal("1"):
            raise StudyArtifactError("invalid v0.2 Brier score")
        if self.log_loss < Decimal("0"):
            raise StudyArtifactError("invalid v0.2 log loss")
        if not Decimal("0") <= self.expected_calibration_error <= Decimal("1"):
            raise StudyArtifactError("invalid v0.2 expected calibration error")


def _scores(
    model: ModelArtifact,
    matrix: FeatureMatrix,
    calibration_indices: tuple[int, ...],
) -> tuple[float, ...]:
    return tuple(
        predict_raw(
            model,
            {name: matrix.value_for(index, name) for name in model.feature_names},
        )
        for index in calibration_indices
    )


def _diagnostic(
    *,
    fold_number: int,
    specialist: str,
    model: ModelArtifact,
    platt: PlattArtifact,
    return_map: ExpectedReturnMap,
    matrix: FeatureMatrix,
    labels: LabelVector,
    calibration_indices: tuple[int, ...],
) -> CalibrationDiagnostic:
    scores = _scores(model, matrix, calibration_indices)
    probabilities = tuple(apply_platt(platt, score) for score in scores)
    targets = tuple(labels.for_index(index).positive for index in calibration_indices)
    positive = sum(targets)
    negative = len(targets) - positive
    if (
        platt.observation_count != len(calibration_indices)
        or platt.positive_count != positive
        or platt.negative_count != negative
        or return_map.observation_count != len(calibration_indices)
    ):
        raise StudyArtifactError("v0.2 calibration artifact population changed")
    rows_identity = hashlib.sha256(
        canonical_json_bytes(
            {
                "rows": [
                    {
                        "candle_index": index,
                        "probability": probability,
                        "positive": target,
                    }
                    for index, probability, target in zip(
                        calibration_indices,
                        probabilities,
                        targets,
                        strict=True,
                    )
                ]
            }
        )
    ).hexdigest()
    return CalibrationDiagnostic(
        schema_version=_SCHEMA,
        fold_number=fold_number,
        specialist=specialist,
        calibration_rows_sha256=rows_identity,
        platt_schema_version=platt.schema_version,
        platt_slope_hex=platt.slope_hex,
        platt_intercept_hex=platt.intercept_hex,
        platt_minimum_probability_hex=platt.minimum_probability_hex,
        platt_maximum_probability_hex=platt.maximum_probability_hex,
        observation_count=platt.observation_count,
        positive_count=platt.positive_count,
        negative_count=platt.negative_count,
        return_map_schema_version=return_map.schema_version,
        return_map_intercept=return_map.intercept,
        return_map_slope=return_map.slope,
        return_map_minimum_probability=return_map.minimum_probability,
        return_map_maximum_probability=return_map.maximum_probability,
        return_map_observation_count=return_map.observation_count,
        brier_score=brier_score(probabilities, targets),
        log_loss=log_loss_score(probabilities, targets),
        expected_calibration_error=expected_calibration_error(probabilities, targets),
    )


def build_calibration_diagnostics(
    *,
    fold_number: int,
    bundle: PredictionBundle,
    matrix: FeatureMatrix,
    labels: LabelVector,
    calibration_indices: tuple[int, ...],
) -> tuple[CalibrationDiagnostic, ...]:
    """Build the two complete calibration receipts for one v0.2 development fold."""

    return (
        _diagnostic(
            fold_number=fold_number,
            specialist="trend",
            model=bundle.trend_model,
            platt=bundle.trend_platt,
            return_map=bundle.trend_return_map,
            matrix=matrix,
            labels=labels,
            calibration_indices=calibration_indices,
        ),
        _diagnostic(
            fold_number=fold_number,
            specialist="mean_reversion",
            model=bundle.mean_reversion_model,
            platt=bundle.mean_reversion_platt,
            return_map=bundle.mean_reversion_return_map,
            matrix=matrix,
            labels=labels,
            calibration_indices=calibration_indices,
        ),
    )


def calibration_evidence_complete(
    diagnostics: tuple[CalibrationDiagnostic, ...],
    policy: CandidatePolicy,
) -> bool:
    """Require both specialists and approved minimum calibration populations for all 12 folds."""

    expected = {(fold, specialist) for fold in range(1, 13) for specialist in _SPECIALISTS}
    observed = {(item.fold_number, item.specialist) for item in diagnostics}
    return (
        len(diagnostics) == len(expected)
        and observed == expected
        and all(
            item.observation_count >= policy.calibration_minimum_observations
            and item.positive_count >= policy.calibration_minimum_positive
            and item.negative_count >= policy.calibration_minimum_negative
            and item.return_map_observation_count == item.observation_count
            for item in diagnostics
        )
    )


def parse_calibration_diagnostics(raw: bytes) -> tuple[CalibrationDiagnostic, ...]:
    """Parse canonical diagnostic rows and reject schema/type drift."""

    expected_keys = set(CalibrationDiagnostic.__dataclass_fields__)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise StudyArtifactError("v0.2 calibration diagnostics are not UTF-8") from None
    diagnostics: list[CalibrationDiagnostic] = []
    for line in text.splitlines():
        try:
            loaded: object = json.loads(line)
        except json.JSONDecodeError:
            raise StudyArtifactError("invalid v0.2 calibration diagnostic JSON") from None
        if not isinstance(loaded, dict):
            raise StudyArtifactError("invalid v0.2 calibration diagnostic row")
        mapping = cast(dict[str, object], loaded)
        if set(mapping) != expected_keys:
            raise StudyArtifactError("v0.2 calibration diagnostic fields changed")
        try:
            decimal_values = {
                field_name: Decimal(cast(str, mapping[field_name]))
                for field_name in _DECIMAL_FIELDS
            }
        except (InvalidOperation, TypeError):
            raise StudyArtifactError("invalid v0.2 calibration decimal value") from None
        try:
            diagnostics.append(
                CalibrationDiagnostic(
                    schema_version=cast(str, mapping["schema_version"]),
                    fold_number=cast(int, mapping["fold_number"]),
                    specialist=cast(str, mapping["specialist"]),
                    calibration_rows_sha256=cast(str, mapping["calibration_rows_sha256"]),
                    platt_schema_version=cast(str, mapping["platt_schema_version"]),
                    platt_slope_hex=cast(str, mapping["platt_slope_hex"]),
                    platt_intercept_hex=cast(str, mapping["platt_intercept_hex"]),
                    platt_minimum_probability_hex=cast(
                        str, mapping["platt_minimum_probability_hex"]
                    ),
                    platt_maximum_probability_hex=cast(
                        str, mapping["platt_maximum_probability_hex"]
                    ),
                    observation_count=cast(int, mapping["observation_count"]),
                    positive_count=cast(int, mapping["positive_count"]),
                    negative_count=cast(int, mapping["negative_count"]),
                    return_map_schema_version=cast(str, mapping["return_map_schema_version"]),
                    return_map_intercept=decimal_values["return_map_intercept"],
                    return_map_slope=decimal_values["return_map_slope"],
                    return_map_minimum_probability=decimal_values["return_map_minimum_probability"],
                    return_map_maximum_probability=decimal_values["return_map_maximum_probability"],
                    return_map_observation_count=cast(int, mapping["return_map_observation_count"]),
                    brier_score=decimal_values["brier_score"],
                    log_loss=decimal_values["log_loss"],
                    expected_calibration_error=decimal_values["expected_calibration_error"],
                )
            )
        except (KeyError, ValueError, TypeError):
            raise StudyArtifactError("invalid v0.2 calibration diagnostic metadata") from None
    return tuple(diagnostics)


__all__ = [
    "CalibrationDiagnostic",
    "build_calibration_diagnostics",
    "calibration_evidence_complete",
    "parse_calibration_diagnostics",
]
