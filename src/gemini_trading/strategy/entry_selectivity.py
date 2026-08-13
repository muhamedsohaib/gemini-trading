"""Calibration-only entry selectivity for Candidate v0.3 research."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from gemini_trading.research.serialization import canonical_json_bytes
from gemini_trading.strategy.contracts import RegimeState, SpecialistKind
from gemini_trading.strategy.errors import StudyArtifactError
from gemini_trading.strategy.features import FeatureMatrix
from gemini_trading.strategy.policy import CandidatePolicy
from gemini_trading.strategy.regimes import RegimeClassifier

_ZERO = Decimal("0")
_ONE = Decimal("1")


@dataclass(frozen=True, slots=True)
class EntrySelectivityPolicy:
    """Frozen Candidate v0.3 calibration-selectivity constants."""

    schema_version: str
    primary_percentile: Decimal
    threshold_floor: Decimal
    minimum_eligible_scores: int
    sensitivity_percentiles: tuple[Decimal, Decimal]

    def __post_init__(self) -> None:
        if not self.schema_version.strip():
            raise ValueError("entry selectivity schema_version must not be empty")
        for value in (
            self.primary_percentile,
            self.threshold_floor,
            *self.sensitivity_percentiles,
        ):
            if not value.is_finite():
                raise ValueError("entry selectivity probabilities must be finite")
            if value < _ZERO or value > _ONE:
                raise ValueError("entry selectivity probabilities must be within [0, 1]")
        if isinstance(self.minimum_eligible_scores, bool) or self.minimum_eligible_scores < 1:
            raise ValueError("minimum eligible scores must be positive")

    @classmethod
    def locked_v0_3(cls) -> EntrySelectivityPolicy:
        """Return the preregistered Candidate v0.3 entry-selectivity contract."""

        return cls(
            schema_version="candidate-v0.3-entry-selectivity-v1",
            primary_percentile=Decimal("0.75"),
            threshold_floor=Decimal("0.50"),
            minimum_eligible_scores=40,
            sensitivity_percentiles=(Decimal("0.70"), Decimal("0.80")),
        )


@dataclass(frozen=True, slots=True)
class EntryThresholdArtifact:
    """Immutable fold/specialist calibration threshold evidence."""

    schema_version: str
    fold_number: int
    specialist: SpecialistKind
    percentile: Decimal
    eligible_indices: tuple[int, ...]
    eligible_scores: tuple[Decimal, ...]
    eligible_rows_sha256: str
    score_vector_sha256: str
    raw_quantile: Decimal
    effective_threshold: Decimal
    quantile_method: str

    def __post_init__(self) -> None:
        if self.schema_version != "candidate-v0.3-entry-threshold-v1":
            raise ValueError("unsupported entry threshold artifact schema")
        if isinstance(self.fold_number, bool) or self.fold_number < 1:
            raise ValueError("fold_number must be positive")
        if self.eligible_indices != tuple(sorted(set(self.eligible_indices))):
            raise ValueError("eligible_indices must be unique and ordered")
        if len(self.eligible_indices) != len(self.eligible_scores):
            raise ValueError("eligible score alignment changed")
        if any(not value.is_finite() for value in self.eligible_scores):
            raise ValueError("eligible scores must be finite")
        if not self.raw_quantile.is_finite() or not self.effective_threshold.is_finite():
            raise ValueError("entry thresholds must be finite")
        if len(self.eligible_rows_sha256) != 64 or len(self.score_vector_sha256) != 64:
            raise ValueError("entry threshold identities must be SHA-256 digests")
        if self.quantile_method != "linear_n_minus_one":
            raise ValueError("entry threshold quantile method changed")


def linear_quantile(values: tuple[Decimal, ...], percentile: Decimal) -> Decimal:
    """Return a deterministic empirical quantile using `(n - 1) * p` interpolation."""

    if not percentile.is_finite() or percentile < _ZERO or percentile > _ONE:
        raise ValueError("percentile must be finite and within [0, 1]")
    if not values:
        raise ValueError("scores must not be empty")
    if any(not value.is_finite() for value in values):
        raise ValueError("scores must be finite")
    ordered = tuple(sorted(values))
    if len(ordered) == 1:
        return ordered[0]
    position = Decimal(len(ordered) - 1) * percentile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - Decimal(lower)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _sha256(payload: Mapping[str, object]) -> str:
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def _validate_v0_3_policy(policy: CandidatePolicy) -> None:
    if (
        policy.strategy_id != "candidate.multi_model.v0_3"
        or policy.policy_version != "candidate-multi-model-v0.3"
        or policy.schema_version != "candidate-strategy-policy-v3"
    ):
        raise StudyArtifactError("entry selectivity requires exact Candidate v0.3 policy")


def _regime_eligible(
    *,
    specialist: SpecialistKind,
    index: int,
    matrix: FeatureMatrix,
    classifier: RegimeClassifier,
) -> bool:
    regime = classifier.classify(
        candle_index=index,
        trend_strength=matrix.value_for(index, "trend_strength_12_42_atr24"),
        volatility_ratio=matrix.value_for(index, "volatility_ratio_6_42"),
        true_range_ratio=matrix.value_for(index, "true_range_ratio_24"),
        sign_streak=int(matrix.value_for(index, "ema_12_42_sign_streak")),
    )
    if specialist is SpecialistKind.TREND:
        return regime.state is RegimeState.TRENDING
    if specialist is SpecialistKind.MEAN_REVERSION:
        if regime.state is not RegimeState.RANGING:
            return False
        return matrix.value_for(index, "close_zscore_24") <= Decimal("-0.75") or matrix.value_for(
            index, "drawdown_from_high_24"
        ) >= Decimal("0.02")
    raise StudyArtifactError("unsupported specialist for entry selectivity")


def build_entry_threshold_artifact(
    *,
    fold_number: int,
    specialist: SpecialistKind,
    percentile: Decimal,
    calibration_indices: tuple[int, ...],
    calibrated_probabilities: Mapping[int, Decimal],
    matrix: FeatureMatrix,
    policy: CandidatePolicy,
) -> EntryThresholdArtifact:
    """Build one threshold strictly from the supplied fold calibration partition."""

    _validate_v0_3_policy(policy)
    if isinstance(fold_number, bool) or fold_number < 1:
        raise StudyArtifactError("entry threshold fold_number must be positive")
    if calibration_indices != tuple(sorted(set(calibration_indices))):
        raise StudyArtifactError("calibration indices must be unique and ordered")
    if set(calibrated_probabilities) != set(calibration_indices):
        raise StudyArtifactError("probability keys must match calibration indices exactly")

    selectivity = EntrySelectivityPolicy.locked_v0_3()
    allowed_percentiles = {
        selectivity.primary_percentile,
        *selectivity.sensitivity_percentiles,
    }
    if percentile not in allowed_percentiles:
        raise StudyArtifactError("entry percentile is not preregistered for Candidate v0.3")

    probabilities: dict[int, Decimal] = {}
    for index in calibration_indices:
        value = calibrated_probabilities[index]
        if not value.is_finite() or value < _ZERO or value > _ONE:
            raise StudyArtifactError("calibrated probabilities must be finite and within [0, 1]")
        probabilities[index] = value

    classifier = RegimeClassifier(policy)
    eligible_indices = tuple(
        index
        for index in calibration_indices
        if _regime_eligible(
            specialist=specialist,
            index=index,
            matrix=matrix,
            classifier=classifier,
        )
    )
    if len(eligible_indices) < selectivity.minimum_eligible_scores:
        raise StudyArtifactError(
            "entry selectivity requires at least 40 eligible calibration scores"
        )
    eligible_scores = tuple(probabilities[index] for index in eligible_indices)
    raw_quantile = linear_quantile(eligible_scores, percentile)
    effective_threshold = max(raw_quantile, selectivity.threshold_floor)

    eligible_rows_sha256 = _sha256(
        {
            "schema_version": "candidate-v0.3-entry-eligible-rows-v1",
            "fold_number": fold_number,
            "specialist": specialist.value,
            "eligible_indices": eligible_indices,
        }
    )
    score_vector_sha256 = _sha256(
        {
            "schema_version": "candidate-v0.3-entry-score-vector-v1",
            "fold_number": fold_number,
            "specialist": specialist.value,
            "eligible_indices": eligible_indices,
            "eligible_scores": eligible_scores,
        }
    )
    return EntryThresholdArtifact(
        schema_version="candidate-v0.3-entry-threshold-v1",
        fold_number=fold_number,
        specialist=specialist,
        percentile=percentile,
        eligible_indices=eligible_indices,
        eligible_scores=eligible_scores,
        eligible_rows_sha256=eligible_rows_sha256,
        score_vector_sha256=score_vector_sha256,
        raw_quantile=raw_quantile,
        effective_threshold=effective_threshold,
        quantile_method="linear_n_minus_one",
    )


__all__ = [
    "EntrySelectivityPolicy",
    "EntryThresholdArtifact",
    "build_entry_threshold_artifact",
    "linear_quantile",
]
