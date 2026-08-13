"""Candidate v0.3 prediction context and calibration-only entry thresholds."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from gemini_trading.strategy.calibration import apply_platt
from gemini_trading.strategy.contracts import SpecialistKind
from gemini_trading.strategy.determinism import (
    TrendDeterminismReceipt,
    fit_verified_prediction_bundle,
)
from gemini_trading.strategy.entry_selectivity import (
    EntrySelectivityPolicy,
    EntryThresholdArtifact,
    build_entry_threshold_artifact,
)
from gemini_trading.strategy.errors import StudyArtifactError
from gemini_trading.strategy.features import FeatureMatrix
from gemini_trading.strategy.labels import LabelVector
from gemini_trading.strategy.models import ModelArtifact, predict_raw
from gemini_trading.strategy.policy import CandidatePolicy
from gemini_trading.strategy.study import StudyPhase
from gemini_trading.strategy.study_predictions import PredictionBundle


@dataclass(frozen=True, slots=True)
class V03PredictionContext:
    """One deterministic v0.3 fold bundle plus its calibration thresholds."""

    bundle: PredictionBundle
    determinism_receipt: TrendDeterminismReceipt
    threshold_artifacts: tuple[EntryThresholdArtifact, ...]

    def __post_init__(self) -> None:
        selectivity = EntrySelectivityPolicy.locked_v0_3()
        expected = tuple(
            (specialist, percentile)
            for specialist in (SpecialistKind.TREND, SpecialistKind.MEAN_REVERSION)
            for percentile in (
                *selectivity.sensitivity_percentiles[:1],
                selectivity.primary_percentile,
                *selectivity.sensitivity_percentiles[1:],
            )
        )
        observed = tuple(
            (artifact.specialist, artifact.percentile)
            for artifact in self.threshold_artifacts
        )
        if observed != expected:
            raise ValueError("v0.3 threshold artifact inventory or order changed")
        if any(
            artifact.fold_number != self.determinism_receipt.fold_number
            for artifact in self.threshold_artifacts
        ):
            raise ValueError("v0.3 threshold artifact fold identity changed")

    def threshold_artifact(
        self,
        specialist: SpecialistKind,
        percentile: Decimal,
    ) -> EntryThresholdArtifact:
        """Return one preregistered threshold artifact."""

        for artifact in self.threshold_artifacts:
            if artifact.specialist is specialist and artifact.percentile == percentile:
                return artifact
        raise KeyError((specialist, percentile))

    def effective_thresholds(self, percentile: Decimal) -> dict[SpecialistKind, Decimal]:
        """Return effective entry thresholds for both specialists at one percentile."""

        return {
            specialist: self.threshold_artifact(
                specialist,
                percentile,
            ).effective_threshold
            for specialist in (SpecialistKind.TREND, SpecialistKind.MEAN_REVERSION)
        }


def _validate_v0_3_policy(policy: CandidatePolicy) -> None:
    if (
        policy.strategy_id != "candidate.multi_model.v0_3"
        or policy.policy_version != "candidate-multi-model-v0.3"
        or policy.schema_version != "candidate-strategy-policy-v3"
    ):
        raise StudyArtifactError("v0.3 prediction context requires exact Candidate v0.3 policy")


def _values(
    matrix: FeatureMatrix,
    index: int,
    model: ModelArtifact,
) -> dict[str, Decimal]:
    return {name: matrix.value_for(index, name) for name in model.feature_names}


def _calibrated_probabilities(
    *,
    matrix: FeatureMatrix,
    calibration_indices: tuple[int, ...],
    model: ModelArtifact,
    platt: object,
) -> dict[int, Decimal]:
    return {
        index: apply_platt(
            platt,  # type: ignore[arg-type]
            predict_raw(model, _values(matrix, index, model)),
        )
        for index in calibration_indices
    }


def fit_v0_3_prediction_context(
    *,
    phase: StudyPhase,
    fold_number: int | None,
    matrix: FeatureMatrix,
    labels: LabelVector,
    policy: CandidatePolicy,
    training_indices: tuple[int, ...],
    calibration_indices: tuple[int, ...],
    prediction_indices: tuple[int, ...],
) -> V03PredictionContext:
    """Fit the unchanged v0.2 specialist bundle and add v0.3 calibration thresholds."""

    _validate_v0_3_policy(policy)
    model_policy = CandidatePolicy.locked_v0_2()
    bundle, receipt = fit_verified_prediction_bundle(
        phase=phase,
        fold_number=fold_number,
        matrix=matrix,
        labels=labels,
        policy=model_policy,
        training_indices=training_indices,
        calibration_indices=calibration_indices,
        prediction_indices=prediction_indices,
    )

    trend_probabilities = _calibrated_probabilities(
        matrix=matrix,
        calibration_indices=calibration_indices,
        model=bundle.trend_model,
        platt=bundle.trend_platt,
    )
    mean_probabilities = _calibrated_probabilities(
        matrix=matrix,
        calibration_indices=calibration_indices,
        model=bundle.mean_reversion_model,
        platt=bundle.mean_reversion_platt,
    )
    if fold_number is None:
        raise StudyArtifactError("v0.3 prediction context requires a development fold")

    selectivity = EntrySelectivityPolicy.locked_v0_3()
    percentiles = (
        selectivity.sensitivity_percentiles[0],
        selectivity.primary_percentile,
        selectivity.sensitivity_percentiles[1],
    )
    artifacts: list[EntryThresholdArtifact] = []
    for specialist, probabilities in (
        (SpecialistKind.TREND, trend_probabilities),
        (SpecialistKind.MEAN_REVERSION, mean_probabilities),
    ):
        for percentile in percentiles:
            artifacts.append(
                build_entry_threshold_artifact(
                    fold_number=fold_number,
                    specialist=specialist,
                    percentile=percentile,
                    calibration_indices=calibration_indices,
                    calibrated_probabilities=probabilities,
                    matrix=matrix,
                    policy=policy,
                )
            )
    return V03PredictionContext(
        bundle=bundle,
        determinism_receipt=receipt,
        threshold_artifacts=tuple(artifacts),
    )


__all__ = ["V03PredictionContext", "fit_v0_3_prediction_context"]
