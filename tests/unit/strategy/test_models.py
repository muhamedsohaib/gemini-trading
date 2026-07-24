"""RED tests for deterministic Candidate v0.1 specialist models."""

from decimal import Decimal

import pytest

from gemini_trading.strategy.contracts import SpecialistKind
from gemini_trading.strategy.features import FeatureMatrix
from gemini_trading.strategy.models import (
    BoostedTreeArtifact,
    LinearModelArtifact,
    MeanReversionSpecialistTrainer,
    TrendSpecialistTrainer,
    parse_model_artifact,
    predict_raw,
    serialize_model_artifact,
)
from gemini_trading.strategy.policy import CandidatePolicy
from strategy_fixture_support import deterministic_model_fixture


def _row_values(matrix: FeatureMatrix, candle_index: int) -> dict[str, Decimal]:
    row = matrix.row_for(candle_index)
    return dict(zip(matrix.feature_names, row.values, strict=True))


def test_trend_fit_is_byte_deterministic() -> None:
    matrix, labels, indices = deterministic_model_fixture()
    trainer = TrendSpecialistTrainer(CandidatePolicy.locked_v0_1())

    first = trainer.fit(matrix, labels, indices)
    second = trainer.fit(matrix, labels, indices)

    assert isinstance(first, LinearModelArtifact)
    assert first.specialist is SpecialistKind.TREND
    assert first.iteration_count < CandidatePolicy.locked_v0_1().trend_max_iterations
    assert serialize_model_artifact(first) == serialize_model_artifact(second)
    assert parse_model_artifact(serialize_model_artifact(first)) == first


def test_mean_reversion_shape_is_locked() -> None:
    matrix, labels, indices = deterministic_model_fixture()
    model = MeanReversionSpecialistTrainer(CandidatePolicy.locked_v0_1()).fit(
        matrix,
        labels,
        indices,
    )

    assert isinstance(model, BoostedTreeArtifact)
    assert model.specialist is SpecialistKind.MEAN_REVERSION
    assert model.estimator_count == 150
    assert model.max_depth == 2
    assert model.minimum_leaf == 100
    assert model.learning_rate_hex == (0.03).hex()
    assert len(model.trees) == 150
    assert parse_model_artifact(serialize_model_artifact(model)) == model


@pytest.mark.parametrize("specialist", [SpecialistKind.TREND, SpecialistKind.MEAN_REVERSION])
def test_custom_raw_prediction_is_finite(specialist: SpecialistKind) -> None:
    matrix, labels, indices = deterministic_model_fixture()
    policy = CandidatePolicy.locked_v0_1()
    model = (
        TrendSpecialistTrainer(policy).fit(matrix, labels, indices)
        if specialist is SpecialistKind.TREND
        else MeanReversionSpecialistTrainer(policy).fit(matrix, labels, indices)
    )

    score = predict_raw(model, _row_values(matrix, indices[-1]))

    assert float("-inf") < score < float("inf")


def test_training_selection_rejects_unknown_index() -> None:
    matrix, labels, indices = deterministic_model_fixture()

    with pytest.raises(KeyError, match="training index"):
        TrendSpecialistTrainer(CandidatePolicy.locked_v0_1()).fit(
            matrix,
            labels,
            (*indices, indices[-1] + 1),
        )
