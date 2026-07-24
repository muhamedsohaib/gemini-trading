"""Regression tests for repeated deterministic specialist fitting."""

from gemini_trading.strategy.models import (
    MeanReversionSpecialistTrainer,
    TrendSpecialistTrainer,
    serialize_model_artifact,
)
from gemini_trading.strategy.policy import CandidatePolicy
from strategy_fixture_support import deterministic_model_fixture


def test_repeated_specialist_fits_are_byte_identical() -> None:
    matrix, labels, indices = deterministic_model_fixture()
    policy = CandidatePolicy.locked_v0_1()

    first_trend = serialize_model_artifact(TrendSpecialistTrainer(policy).fit(matrix, labels, indices))
    second_trend = serialize_model_artifact(TrendSpecialistTrainer(policy).fit(matrix, labels, indices))
    first_mean_reversion = serialize_model_artifact(
        MeanReversionSpecialistTrainer(policy).fit(matrix, labels, indices)
    )
    second_mean_reversion = serialize_model_artifact(
        MeanReversionSpecialistTrainer(policy).fit(matrix, labels, indices)
    )

    assert first_trend == second_trend
    assert first_mean_reversion == second_mean_reversion
