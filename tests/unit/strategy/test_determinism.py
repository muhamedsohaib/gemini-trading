"""Tests for Candidate v0.2 repeated-fit determinism evidence."""

from decimal import Decimal

import pytest

import gemini_trading.strategy.determinism as determinism
from gemini_trading.strategy.calibration import ExpectedReturnMap, PlattArtifact
from gemini_trading.strategy.contracts import RegimeState
from gemini_trading.strategy.determinism import (
    TrendDeterminismReceipt,
    fit_verified_prediction_bundle,
)
from gemini_trading.strategy.errors import ModelDeterminismError
from gemini_trading.strategy.models import MeanReversionSpecialistTrainer, TrendSpecialistTrainer
from gemini_trading.strategy.policy import CandidatePolicy
from gemini_trading.strategy.regimes import RegimeObservation
from gemini_trading.strategy.study import StudyPhase
from gemini_trading.strategy.study_predictions import Prediction, PredictionBundle
from strategy_fixture_support import deterministic_model_fixture


def _bundle() -> tuple[PredictionBundle, object, object, tuple[int, ...]]:
    matrix, labels, indices = deterministic_model_fixture()
    policy = CandidatePolicy.locked_v0_2()
    trend = TrendSpecialistTrainer(policy).fit(matrix, labels, indices)
    mean_reversion = MeanReversionSpecialistTrainer(policy).fit(matrix, labels, indices)
    platt = PlattArtifact(
        schema_version="candidate-platt-v1",
        slope_hex=(1.0).hex(),
        intercept_hex=(0.0).hex(),
        minimum_probability_hex=(0.1).hex(),
        maximum_probability_hex=(0.9).hex(),
        observation_count=200,
        positive_count=100,
        negative_count=100,
    )
    expected = ExpectedReturnMap(
        schema_version="candidate-expected-return-map-v1",
        intercept=Decimal("0"),
        slope=Decimal("0.01"),
        minimum_probability=Decimal("0.1"),
        maximum_probability=Decimal("0.9"),
        observation_count=200,
    )
    prediction = Prediction(
        candle_index=indices[-1],
        trend_raw=0.1,
        mean_reversion_raw=0.2,
        trend_probability=Decimal("0.55"),
        mean_reversion_probability=Decimal("0.52"),
        trend_expected_return=Decimal("0.01"),
        mean_reversion_expected_return=Decimal("0.008"),
        regime=RegimeObservation(
            candle_index=indices[-1],
            state=RegimeState.TRENDING,
            trend_strength=Decimal("1.2"),
            volatility_ratio=Decimal("1.1"),
            true_range_ratio=Decimal("1.0"),
            sign_streak=3,
            reason_code="trending_strength_streak",
        ),
    )
    return (
        PredictionBundle(
            phase=StudyPhase.DEVELOPMENT,
            fold_number=1,
            trend_model=trend,
            mean_reversion_model=mean_reversion,
            trend_platt=platt,
            mean_reversion_platt=platt,
            trend_return_map=expected,
            mean_reversion_return_map=expected,
            predictions=(prediction,),
        ),
        matrix,
        labels,
        indices,
    )


def test_v0_2_repeated_fit_produces_exact_model_and_prediction_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle, matrix, labels, indices = _bundle()

    def deterministic_fit(**_kwargs: object) -> PredictionBundle:
        return bundle

    monkeypatch.setattr(determinism, "fit_prediction_bundle", deterministic_fit)
    verified, receipt = fit_verified_prediction_bundle(
        phase=StudyPhase.DEVELOPMENT,
        fold_number=1,
        matrix=matrix,
        labels=labels,
        policy=CandidatePolicy.locked_v0_2(),
        training_indices=indices,
        calibration_indices=indices,
        prediction_indices=indices,
    )

    assert verified == bundle
    assert receipt.schema_version == "candidate-v0.2-trend-determinism-v1"
    assert receipt.fold_number == 1
    assert receipt.iteration_count < 50_000
    assert receipt.first_model_sha256 == receipt.second_model_sha256
    assert receipt.first_bundle_sha256 == receipt.second_bundle_sha256
    assert receipt.exact_match is True


def test_determinism_receipt_rejects_mismatched_model_identity() -> None:
    with pytest.raises(ModelDeterminismError, match="repeated trend model"):
        TrendDeterminismReceipt(
            schema_version="candidate-v0.2-trend-determinism-v1",
            fold_number=1,
            iteration_count=100,
            first_model_sha256="a" * 64,
            second_model_sha256="b" * 64,
            first_bundle_sha256="c" * 64,
            second_bundle_sha256="c" * 64,
            exact_match=False,
        )
