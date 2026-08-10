"""Repeated-fit determinism evidence for Candidate v0.2 development qualification."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from typing import cast

from gemini_trading.research.serialization import canonical_json_bytes
from gemini_trading.strategy.calibration import serialize_platt_artifact
from gemini_trading.strategy.errors import ModelDeterminismError
from gemini_trading.strategy.features import FeatureMatrix
from gemini_trading.strategy.labels import LabelVector
from gemini_trading.strategy.models import LinearModelArtifact, serialize_model_artifact
from gemini_trading.strategy.policy import CandidatePolicy
from gemini_trading.strategy.study import StudyPhase
from gemini_trading.strategy.study_predictions import (
    PredictionBundle,
    fit_prediction_bundle,
)

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _canonical_mapping(raw: bytes) -> dict[str, object]:
    loaded: object = json.loads(raw)
    if not isinstance(loaded, dict):
        raise ModelDeterminismError("serialized deterministic artifact is not a mapping")
    return cast(dict[str, object], loaded)


def prediction_bundle_sha256(bundle: PredictionBundle) -> str:
    """Return a content identity for one complete non-executable prediction bundle."""

    payload: dict[str, object] = {
        "phase": bundle.phase.value,
        "fold_number": bundle.fold_number,
        "trend_model": _canonical_mapping(serialize_model_artifact(bundle.trend_model)),
        "mean_reversion_model": _canonical_mapping(
            serialize_model_artifact(bundle.mean_reversion_model)
        ),
        "trend_platt": _canonical_mapping(serialize_platt_artifact(bundle.trend_platt)),
        "mean_reversion_platt": _canonical_mapping(
            serialize_platt_artifact(bundle.mean_reversion_platt)
        ),
        "trend_return_map": asdict(bundle.trend_return_map),
        "mean_reversion_return_map": asdict(bundle.mean_reversion_return_map),
        "predictions": [
            {
                "candle_index": item.candle_index,
                "trend_raw_hex": float(item.trend_raw).hex(),
                "mean_reversion_raw_hex": float(item.mean_reversion_raw).hex(),
                "trend_probability": item.trend_probability,
                "mean_reversion_probability": item.mean_reversion_probability,
                "trend_expected_return": item.trend_expected_return,
                "mean_reversion_expected_return": item.mean_reversion_expected_return,
                "regime": asdict(item.regime),
            }
            for item in bundle.predictions
        ],
    }
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


@dataclass(frozen=True, slots=True)
class TrendDeterminismReceipt:
    """Immutable proof that identical v0.2 fold inputs produced byte-identical evidence."""

    schema_version: str
    fold_number: int
    iteration_count: int
    first_model_sha256: str
    second_model_sha256: str
    first_bundle_sha256: str
    second_bundle_sha256: str
    exact_match: bool

    def __post_init__(self) -> None:
        if self.schema_version != "candidate-v0.2-trend-determinism-v1":
            raise ValueError("unsupported trend determinism receipt schema")
        if isinstance(self.fold_number, bool) or self.fold_number < 1:
            raise ValueError("fold_number must be positive")
        if isinstance(self.iteration_count, bool) or self.iteration_count < 1:
            raise ValueError("iteration_count must be positive")
        for field_name in (
            "first_model_sha256",
            "second_model_sha256",
            "first_bundle_sha256",
            "second_bundle_sha256",
        ):
            if _SHA256_PATTERN.fullmatch(getattr(self, field_name)) is None:
                raise ValueError(f"{field_name} must be a lowercase SHA-256 digest")
        if self.first_model_sha256 != self.second_model_sha256:
            raise ModelDeterminismError("repeated trend model identity changed")
        if self.first_bundle_sha256 != self.second_bundle_sha256:
            raise ModelDeterminismError("repeated prediction bundle identity changed")
        if not self.exact_match:
            raise ModelDeterminismError("repeated Candidate v0.2 fit did not exactly match")


def fit_verified_prediction_bundle(
    *,
    phase: StudyPhase,
    fold_number: int | None,
    matrix: FeatureMatrix,
    labels: LabelVector,
    policy: CandidatePolicy,
    training_indices: tuple[int, ...],
    calibration_indices: tuple[int, ...],
    prediction_indices: tuple[int, ...],
) -> tuple[PredictionBundle, TrendDeterminismReceipt]:
    """Fit an identical v0.2 development bundle twice and require exact identities."""

    if phase is not StudyPhase.DEVELOPMENT or fold_number is None:
        raise ModelDeterminismError("v0.2 determinism receipt requires a development fold")
    if (
        policy.strategy_id != "candidate.multi_model.v0_2"
        or policy.policy_version != "candidate-multi-model-v0.2"
    ):
        raise ModelDeterminismError("v0.2 determinism receipt requires Candidate v0.2 policy")

    arguments = {
        "phase": phase,
        "fold_number": fold_number,
        "matrix": matrix,
        "labels": labels,
        "policy": policy,
        "training_indices": training_indices,
        "calibration_indices": calibration_indices,
        "prediction_indices": prediction_indices,
    }
    first = fit_prediction_bundle(**arguments)
    second = fit_prediction_bundle(**arguments)
    if not isinstance(first.trend_model, LinearModelArtifact) or not isinstance(
        second.trend_model, LinearModelArtifact
    ):
        raise ModelDeterminismError("trend specialist did not produce a linear model artifact")
    if first.trend_model.iteration_count >= policy.trend_max_iterations:
        raise ModelDeterminismError("trend specialist did not converge before max_iter")
    first_model = hashlib.sha256(serialize_model_artifact(first.trend_model)).hexdigest()
    second_model = hashlib.sha256(serialize_model_artifact(second.trend_model)).hexdigest()
    first_bundle = prediction_bundle_sha256(first)
    second_bundle = prediction_bundle_sha256(second)
    receipt = TrendDeterminismReceipt(
        schema_version="candidate-v0.2-trend-determinism-v1",
        fold_number=fold_number,
        iteration_count=first.trend_model.iteration_count,
        first_model_sha256=first_model,
        second_model_sha256=second_model,
        first_bundle_sha256=first_bundle,
        second_bundle_sha256=second_bundle,
        exact_match=first_model == second_model and first_bundle == second_bundle,
    )
    return first, receipt


__all__ = [
    "TrendDeterminismReceipt",
    "fit_verified_prediction_bundle",
    "prediction_bundle_sha256",
]
