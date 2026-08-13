"""Candidate v0.3 qualification-case inventory and non-gating diagnostics."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from decimal import Decimal

from gemini_trading.research.serialization import canonical_json_bytes
from gemini_trading.strategy.contracts import RegimeState
from gemini_trading.strategy.errors import StudyArtifactError
from gemini_trading.strategy.study_predictions import PredictionBundle

V03_QUALIFICATION_CASE_IDS = (
    "candidate.multi_model.v0_3",
    "cash.v1",
    "buy_hold.v1",
    "ema_20_50.v1",
    "donchian_20_10.v1",
    "mean_reversion_z24.v1",
    "trend.specialist.v1",
    "mean_reversion.specialist.v1",
    "trend.ema_20_50.gated.v1",
    "ranging.mean_reversion_z24.gated.v1",
    "ablation.no_percentile_selectivity.v1",
    "ablation.no_volume.v1",
    "ablation.no_protection.v1",
    "control.delayed_features.v1",
    "control.shuffled_labels.v1",
    "cost.1_5x",
    "cost.2x",
    "sensitivity.entry_percentile_0_70",
    "sensitivity.entry_percentile_0_80",
    "sensitivity.exit_0_42",
    "sensitivity.exit_0_48",
    "sensitivity.max_hold_12",
    "sensitivity.max_hold_24",
    "sensitivity.initial_stop_2_0",
    "sensitivity.initial_stop_3_0",
    "sensitivity.cooldown_1",
    "sensitivity.cooldown_3",
    "control.shuffled_labels.seed_1799",
    "control.delayed_features.final",
    "bootstrap.seed_1788",
)


@dataclass(frozen=True, slots=True)
class V03FoldDiagnostics:
    """Persisted v0.3 companion/disagreement distributions; never a gate input."""

    schema_version: str
    fold_number: int
    decision_indices: tuple[int, ...]
    companion_indices: tuple[int, ...]
    companion_probabilities: tuple[Decimal, ...]
    disagreement_indices: tuple[int, ...]
    absolute_disagreements: tuple[Decimal, ...]
    companion_distribution_sha256: str
    disagreement_distribution_sha256: str

    def __post_init__(self) -> None:
        if self.schema_version != "candidate-v0.3-fold-diagnostics-v1":
            raise ValueError("unsupported v0.3 fold diagnostics schema")
        if isinstance(self.fold_number, bool) or self.fold_number < 1:
            raise ValueError("fold_number must be positive")
        for indices, values, field_name in (
            (self.companion_indices, self.companion_probabilities, "companion"),
            (self.disagreement_indices, self.absolute_disagreements, "disagreement"),
        ):
            if indices != tuple(sorted(set(indices))):
                raise ValueError(f"{field_name} indices must be unique and ordered")
            if len(indices) != len(values):
                raise ValueError(f"{field_name} diagnostics must remain aligned")
            if any(not value.is_finite() for value in values):
                raise ValueError(f"{field_name} diagnostics must be finite")
        if self.decision_indices != tuple(sorted(set(self.decision_indices))):
            raise ValueError("decision_indices must be unique and ordered")
        if not set(self.companion_indices) <= set(self.decision_indices):
            raise ValueError("companion diagnostics must come from development decision rows")
        if self.disagreement_indices != self.decision_indices:
            raise ValueError("disagreement diagnostics must cover every development decision row")
        if (
            len(self.companion_distribution_sha256) != 64
            or len(self.disagreement_distribution_sha256) != 64
        ):
            raise ValueError("diagnostic distributions must have SHA-256 identities")


def _sha256(payload: dict[str, object]) -> str:
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def build_v0_3_fold_diagnostics(
    *,
    fold_number: int,
    indices: tuple[int, ...],
    bundle: PredictionBundle,
) -> V03FoldDiagnostics:
    """Build deterministic diagnostic-only probability distributions for one fold."""

    if isinstance(fold_number, bool) or fold_number < 1:
        raise StudyArtifactError("v0.3 diagnostics require a positive fold number")
    if indices != tuple(sorted(set(indices))) or not indices:
        raise StudyArtifactError("v0.3 diagnostic indices must be non-empty, unique, and ordered")
    by_index = {item.candle_index: item for item in bundle.predictions}
    if len(by_index) != len(bundle.predictions):
        raise StudyArtifactError("v0.3 prediction bundle contains duplicate decision rows")
    if not set(indices) <= set(by_index):
        raise StudyArtifactError("v0.3 diagnostics require every development decision prediction")

    companion_indices: list[int] = []
    companion_probabilities: list[Decimal] = []
    disagreement_indices: list[int] = []
    absolute_disagreements: list[Decimal] = []
    for index in indices:
        item = by_index[index]
        trend = item.trend_probability
        mean = item.mean_reversion_probability
        if not trend.is_finite() or not mean.is_finite():
            raise StudyArtifactError("v0.3 diagnostics require finite calibrated probabilities")
        disagreement_indices.append(index)
        absolute_disagreements.append(abs(trend - mean))
        if item.regime.state is RegimeState.TRENDING:
            companion_indices.append(index)
            companion_probabilities.append(mean)
        elif item.regime.state is RegimeState.RANGING:
            companion_indices.append(index)
            companion_probabilities.append(trend)

    companion_index_tuple = tuple(companion_indices)
    companion_probability_tuple = tuple(companion_probabilities)
    disagreement_index_tuple = tuple(disagreement_indices)
    disagreement_tuple = tuple(absolute_disagreements)
    companion_sha = _sha256(
        {
            "schema_version": "candidate-v0.3-companion-distribution-v1",
            "fold_number": fold_number,
            "indices": companion_index_tuple,
            "probabilities": companion_probability_tuple,
        }
    )
    disagreement_sha = _sha256(
        {
            "schema_version": "candidate-v0.3-disagreement-distribution-v1",
            "fold_number": fold_number,
            "indices": disagreement_index_tuple,
            "absolute_disagreements": disagreement_tuple,
        }
    )
    return V03FoldDiagnostics(
        schema_version="candidate-v0.3-fold-diagnostics-v1",
        fold_number=fold_number,
        decision_indices=indices,
        companion_indices=companion_index_tuple,
        companion_probabilities=companion_probability_tuple,
        disagreement_indices=disagreement_index_tuple,
        absolute_disagreements=disagreement_tuple,
        companion_distribution_sha256=companion_sha,
        disagreement_distribution_sha256=disagreement_sha,
    )


def serialize_v0_3_fold_diagnostics(diagnostics: V03FoldDiagnostics) -> bytes:
    """Return canonical bytes for non-gating v0.3 diagnostic evidence."""

    return canonical_json_bytes(asdict(diagnostics))


__all__ = [
    "V03_QUALIFICATION_CASE_IDS",
    "V03FoldDiagnostics",
    "build_v0_3_fold_diagnostics",
    "serialize_v0_3_fold_diagnostics",
]
