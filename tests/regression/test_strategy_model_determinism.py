"""Regression tests for repeated deterministic specialist fitting."""

from gemini_trading.strategy.features import FeatureRegistry
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

    first_trend = serialize_model_artifact(
        TrendSpecialistTrainer(policy).fit(matrix, labels, indices)
    )
    second_trend = serialize_model_artifact(
        TrendSpecialistTrainer(policy).fit(matrix, labels, indices)
    )
    first_mean_reversion = serialize_model_artifact(
        MeanReversionSpecialistTrainer(policy).fit(matrix, labels, indices)
    )
    second_mean_reversion = serialize_model_artifact(
        MeanReversionSpecialistTrainer(policy).fit(matrix, labels, indices)
    )

    assert first_trend == second_trend
    assert first_mean_reversion == second_mean_reversion


def test_v0_4_explicit_domain_specialist_fits_are_byte_identical() -> None:
    matrix, labels, indices = deterministic_model_fixture()

    policy = CandidatePolicy.locked_v0_4()
    registry = FeatureRegistry.locked_v0_1()

    # Exercise the Task 6 explicit-domain interface rather than
    # either specialist's historical default row-selection path.
    trend_domain = indices[::2]
    # Step by three so the deterministic fixture spans every
    # close_zscore_24 modulo-4 state rather than selecting only
    # the constant -1.00 rows.
    mean_reversion_domain = indices[::3]

    first_trend = serialize_model_artifact(
        TrendSpecialistTrainer(policy).fit(
            matrix,
            labels,
            indices,
            feature_names=registry.trend_feature_names,
            eligible_indices=trend_domain,
        )
    )
    second_trend = serialize_model_artifact(
        TrendSpecialistTrainer(policy).fit(
            matrix,
            labels,
            indices,
            feature_names=registry.trend_feature_names,
            eligible_indices=trend_domain,
        )
    )

    first_mean_reversion = serialize_model_artifact(
        MeanReversionSpecialistTrainer(policy).fit(
            matrix,
            labels,
            indices,
            feature_names=registry.mean_reversion_feature_names,
            eligible_indices=mean_reversion_domain,
        )
    )
    second_mean_reversion = serialize_model_artifact(
        MeanReversionSpecialistTrainer(policy).fit(
            matrix,
            labels,
            indices,
            feature_names=registry.mean_reversion_feature_names,
            eligible_indices=mean_reversion_domain,
        )
    )

    assert first_trend == second_trend
    assert first_mean_reversion == second_mean_reversion
