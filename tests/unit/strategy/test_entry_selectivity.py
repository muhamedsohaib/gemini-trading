"""Contract tests for Candidate v0.3 calibration-only entry selectivity."""

from __future__ import annotations

import importlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest

from gemini_trading.strategy.contracts import SpecialistKind
from gemini_trading.strategy.errors import StudyArtifactError
from gemini_trading.strategy.features import (
    FeatureDefinition,
    FeatureGroup,
    FeatureMatrix,
    FeatureRow,
)
from gemini_trading.strategy.policy import CandidatePolicy

_FEATURE_NAMES = (
    "trend_strength_12_42_atr24",
    "volatility_ratio_6_42",
    "true_range_ratio_24",
    "ema_12_42_sign_streak",
    "close_zscore_24",
    "drawdown_from_high_24",
)


def _api(name: str) -> Any:
    module = importlib.import_module("gemini_trading.strategy.entry_selectivity")
    value = getattr(module, name, None)
    assert value is not None, f"entry_selectivity must define {name}"
    return value


def _matrix(
    count: int,
    *,
    regime: str = "trending",
    stretched: bool = True,
) -> FeatureMatrix:
    definitions = tuple(
        FeatureDefinition(
            name=name,
            version="v1",
            group=FeatureGroup.REGIME,
            lookback_candles=1,
        )
        for name in _FEATURE_NAMES
    )
    rows: list[FeatureRow] = []
    start = datetime(2024, 1, 1, tzinfo=UTC)
    for index in range(count):
        if regime == "trending":
            values = (
                Decimal("1.2"),
                Decimal("1.0"),
                Decimal("1.0"),
                Decimal("3"),
                Decimal("0"),
                Decimal("0"),
            )
        else:
            values = (
                Decimal("0.2"),
                Decimal("1.0"),
                Decimal("1.0"),
                Decimal("0"),
                Decimal("-1.0") if stretched else Decimal("0"),
                Decimal("0.03") if stretched else Decimal("0"),
            )
        rows.append(
            FeatureRow(
                candle_index=index,
                candle_open_time=start + timedelta(hours=4 * index),
                values=values,
            )
        )
    return FeatureMatrix(
        schema_version="entry-selectivity-test-v1",
        definitions=definitions,
        rows=tuple(rows),
    )


def _probabilities(count: int, *, start: str = "0.40") -> dict[int, Decimal]:
    base = Decimal(start)
    return {index: base + Decimal(index) / Decimal("100") for index in range(count)}


def _artifact(
    *,
    matrix: FeatureMatrix,
    probabilities: dict[int, Decimal],
    specialist: SpecialistKind = SpecialistKind.TREND,
    percentile: Decimal = Decimal("0.75"),
):
    builder = _api("build_entry_threshold_artifact")
    return builder(
        fold_number=1,
        specialist=specialist,
        percentile=percentile,
        calibration_indices=tuple(range(len(matrix.rows))),
        calibrated_probabilities=probabilities,
        matrix=matrix,
        policy=CandidatePolicy.locked_v0_3(),
    )


def test_locked_selectivity_policy_matches_approved_v0_3_contract() -> None:
    policy_type = _api("EntrySelectivityPolicy")
    policy = policy_type.locked_v0_3()

    assert policy.schema_version == "candidate-v0.3-entry-selectivity-v1"
    assert policy.primary_percentile == Decimal("0.75")
    assert policy.threshold_floor == Decimal("0.50")
    assert policy.minimum_eligible_scores == 40
    assert policy.sensitivity_percentiles == (Decimal("0.70"), Decimal("0.80"))


def test_linear_quantile_uses_deterministic_n_minus_one_interpolation() -> None:
    quantile = _api("linear_quantile")

    values = tuple(Decimal(value) for value in ("0.9", "0.3", "0.1", "0.8", "0.2"))
    assert quantile(values, Decimal("0.75")) == Decimal("0.8")
    assert quantile(
        tuple(Decimal(value) for value in ("0.4", "0.1", "0.3", "0.2")),
        Decimal("0.50"),
    ) == Decimal("0.25")
    assert quantile(
        tuple(Decimal(value) for value in ("0.2", "0.2", "0.2", "0.8")),
        Decimal("0.50"),
    ) == Decimal("0.2")


@pytest.mark.parametrize("percentile", (Decimal("-0.01"), Decimal("1.01")))
def test_linear_quantile_rejects_out_of_range_percentiles(percentile: Decimal) -> None:
    quantile = _api("linear_quantile")
    with pytest.raises(ValueError, match="percentile"):
        quantile((Decimal("0.5"),), percentile)


def test_linear_quantile_rejects_empty_or_nonfinite_scores() -> None:
    quantile = _api("linear_quantile")
    with pytest.raises(ValueError, match="scores"):
        quantile((), Decimal("0.75"))
    with pytest.raises(ValueError, match="finite"):
        quantile((Decimal("NaN"),), Decimal("0.75"))


def test_threshold_artifact_uses_calibration_only_q75_and_preserves_row_alignment() -> None:
    matrix = _matrix(40)
    probabilities = _probabilities(40)
    artifact = _artifact(matrix=matrix, probabilities=probabilities)

    assert artifact.schema_version == "candidate-v0.3-entry-threshold-v1"
    assert artifact.fold_number == 1
    assert artifact.specialist is SpecialistKind.TREND
    assert artifact.percentile == Decimal("0.75")
    assert artifact.eligible_indices == tuple(range(40))
    assert artifact.eligible_scores == tuple(probabilities[index] for index in range(40))
    assert artifact.raw_quantile == Decimal("0.6925")
    assert artifact.effective_threshold == Decimal("0.6925")
    assert artifact.quantile_method == "linear_n_minus_one"
    assert len(artifact.eligible_rows_sha256) == 64
    assert len(artifact.score_vector_sha256) == 64


def test_threshold_artifact_applies_the_locked_half_probability_floor() -> None:
    matrix = _matrix(40)
    artifact = _artifact(
        matrix=matrix,
        probabilities={index: Decimal("0.20") for index in range(40)},
    )

    assert artifact.raw_quantile == Decimal("0.20")
    assert artifact.effective_threshold == Decimal("0.50")


def test_threshold_artifact_is_invariant_to_probability_mapping_insertion_order() -> None:
    matrix = _matrix(40)
    ordered = _probabilities(40)
    reversed_mapping = dict(reversed(tuple(ordered.items())))

    first = _artifact(matrix=matrix, probabilities=ordered)
    second = _artifact(matrix=matrix, probabilities=reversed_mapping)

    assert first == second
    assert first.eligible_rows_sha256 == second.eligible_rows_sha256
    assert first.score_vector_sha256 == second.score_vector_sha256


def test_mean_reversion_requires_ranging_stretch_for_calibration_eligibility() -> None:
    stretched = _matrix(40, regime="ranging", stretched=True)
    artifact = _artifact(
        matrix=stretched,
        probabilities=_probabilities(40),
        specialist=SpecialistKind.MEAN_REVERSION,
    )
    assert len(artifact.eligible_indices) == 40

    not_stretched = _matrix(40, regime="ranging", stretched=False)
    with pytest.raises(StudyArtifactError, match="40 eligible calibration scores"):
        _artifact(
            matrix=not_stretched,
            probabilities=_probabilities(40),
            specialist=SpecialistKind.MEAN_REVERSION,
        )


def test_threshold_artifact_fails_closed_below_40_eligible_rows() -> None:
    with pytest.raises(StudyArtifactError, match="40 eligible calibration scores"):
        _artifact(matrix=_matrix(39), probabilities=_probabilities(39))


def test_threshold_artifact_rejects_non_calibration_probability_keys() -> None:
    matrix = _matrix(40)
    probabilities = _probabilities(40)
    probabilities[99] = Decimal("0.99")

    with pytest.raises(StudyArtifactError, match="calibration indices"):
        _artifact(matrix=matrix, probabilities=probabilities)


def test_threshold_artifact_allows_only_preregistered_percentiles() -> None:
    matrix = _matrix(40)
    probabilities = _probabilities(40)

    for allowed in (Decimal("0.70"), Decimal("0.75"), Decimal("0.80")):
        assert (
            _artifact(
                matrix=matrix,
                probabilities=probabilities,
                percentile=allowed,
            ).percentile
            == allowed
        )

    with pytest.raises(StudyArtifactError, match="preregistered"):
        _artifact(
            matrix=matrix,
            probabilities=probabilities,
            percentile=Decimal("0.72"),
        )


def test_threshold_artifact_rejects_old_candidate_identity() -> None:
    builder = _api("build_entry_threshold_artifact")
    matrix = _matrix(40)
    with pytest.raises(StudyArtifactError, match=r"Candidate v0\.3"):
        builder(
            fold_number=1,
            specialist=SpecialistKind.TREND,
            percentile=Decimal("0.75"),
            calibration_indices=tuple(range(40)),
            calibrated_probabilities=_probabilities(40),
            matrix=matrix,
            policy=CandidatePolicy.locked_v0_2(),
        )


def _v0_4_probabilities(
    count: int,
    *,
    start: str = "0.40",
) -> dict[int, Decimal]:
    base = Decimal(start)
    return {index: base + Decimal(index) / Decimal("1000") for index in range(count)}


def _v0_4_artifact(
    *,
    count: int = 160,
    percentile: Decimal = Decimal("0.75"),
    start: str = "0.40",
    specialist: SpecialistKind = SpecialistKind.TREND,
):
    builder = _api("build_v0_4_entry_threshold_artifact")
    indices = tuple(range(1000, 1000 + count))
    probabilities = {
        index: probability
        for index, probability in zip(
            indices,
            _v0_4_probabilities(
                count,
                start=start,
            ).values(),
            strict=True,
        )
    }
    return builder(
        fold_number=3,
        specialist=specialist,
        percentile=percentile,
        eligible_indices=indices,
        calibrated_probabilities=probabilities,
        policy=CandidatePolicy.locked_v0_4(),
    )


def test_v0_4_threshold_artifact_uses_explicit_regime_matched_q75_domain() -> None:
    artifact = _v0_4_artifact()

    assert artifact.schema_version == "candidate-v0.4-entry-threshold-v1"
    assert artifact.fold_number == 3
    assert artifact.specialist is SpecialistKind.TREND
    assert artifact.percentile == Decimal("0.75")
    assert artifact.eligible_indices == tuple(range(1000, 1160))
    assert len(artifact.eligible_scores) == 160

    # n=160 -> q75 position is
    # (160 - 1) * 0.75 = 119.25
    # scores run 0.400 .. 0.559.
    assert artifact.raw_quantile == Decimal("0.51925")
    assert artifact.effective_threshold == Decimal("0.51925")

    assert len(artifact.eligible_rows_sha256) == 64
    assert len(artifact.score_vector_sha256) == 64


@pytest.mark.parametrize(
    "percentile",
    (
        Decimal("0.70"),
        Decimal("0.75"),
        Decimal("0.80"),
    ),
)
def test_v0_4_threshold_artifact_allows_only_locked_percentiles(
    percentile: Decimal,
) -> None:
    artifact = _v0_4_artifact(
        percentile=percentile,
    )
    assert artifact.percentile == percentile


def test_v0_4_threshold_artifact_rejects_nonregistered_percentile() -> None:
    with pytest.raises(
        StudyArtifactError,
        match="preregistered",
    ):
        _v0_4_artifact(
            percentile=Decimal("0.72"),
        )


def test_v0_4_threshold_artifact_requires_160_regime_matched_scores() -> None:
    with pytest.raises(
        StudyArtifactError,
        match="160 eligible calibration scores",
    ):
        _v0_4_artifact(count=159)


def test_v0_4_threshold_artifact_applies_half_probability_floor() -> None:
    artifact = _v0_4_artifact(
        start="0.10",
    )

    assert artifact.raw_quantile == Decimal("0.21925")
    assert artifact.effective_threshold == Decimal("0.50")


def test_v0_4_threshold_artifact_is_mapping_order_deterministic() -> None:
    builder = _api("build_v0_4_entry_threshold_artifact")

    indices = tuple(range(1000, 1160))
    ordered = {
        index: Decimal("0.40") + Decimal(offset) / Decimal("1000")
        for offset, index in enumerate(indices)
    }
    reversed_mapping = dict(reversed(tuple(ordered.items())))

    first = builder(
        fold_number=3,
        specialist=SpecialistKind.TREND,
        percentile=Decimal("0.75"),
        eligible_indices=indices,
        calibrated_probabilities=ordered,
        policy=CandidatePolicy.locked_v0_4(),
    )
    second = builder(
        fold_number=3,
        specialist=SpecialistKind.TREND,
        percentile=Decimal("0.75"),
        eligible_indices=indices,
        calibrated_probabilities=reversed_mapping,
        policy=CandidatePolicy.locked_v0_4(),
    )

    assert first == second
    assert first.eligible_rows_sha256 == second.eligible_rows_sha256
    assert first.score_vector_sha256 == second.score_vector_sha256


def test_v0_4_threshold_artifact_rejects_non_v0_4_policy() -> None:
    builder = _api("build_v0_4_entry_threshold_artifact")

    indices = tuple(range(160))
    probabilities = _v0_4_probabilities(160)

    with pytest.raises(
        StudyArtifactError,
        match=r"Candidate v0\.4",
    ):
        builder(
            fold_number=1,
            specialist=SpecialistKind.TREND,
            percentile=Decimal("0.75"),
            eligible_indices=indices,
            calibrated_probabilities=probabilities,
            policy=CandidatePolicy.locked_v0_3(),
        )
