"""RED tests for Candidate v0.2 repeated-fit determinism evidence."""

import pytest

from gemini_trading.strategy.determinism import (
    TrendDeterminismReceipt,
    fit_verified_prediction_bundle,
)
from gemini_trading.strategy.errors import ModelDeterminismError
from gemini_trading.strategy.policy import CandidatePolicy
from gemini_trading.strategy.study import StudyPhase
from strategy_fixture_support import deterministic_model_fixture


def test_v0_2_repeated_fit_produces_exact_model_and_prediction_identity() -> None:
    matrix, labels, indices = deterministic_model_fixture(row_count=700)
    training = indices[:350]
    calibration = indices[350:550]
    prediction = indices[550:]

    bundle, receipt = fit_verified_prediction_bundle(
        phase=StudyPhase.DEVELOPMENT,
        fold_number=1,
        matrix=matrix,
        labels=labels,
        policy=CandidatePolicy.locked_v0_2(),
        training_indices=training,
        calibration_indices=calibration,
        prediction_indices=prediction,
    )

    assert bundle.phase is StudyPhase.DEVELOPMENT
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
