"""Tests for the fail-closed strategy-study error taxonomy."""

import pytest

from gemini_trading.research.errors import ResearchError
from gemini_trading.strategy.errors import (
    FinalTestSealError,
    InsufficientCalibrationError,
    InsufficientHistoryError,
    LabelLeakageError,
    ModelDeterminismError,
    PointInTimeViolationError,
    ProbabilityRangeError,
    SplitBoundaryError,
    StrategyStudyError,
    StudyArtifactError,
    StudyReplayMismatchError,
    StudyVerificationError,
)


@pytest.mark.parametrize(
    "error_type",
    [
        InsufficientHistoryError,
        PointInTimeViolationError,
        SplitBoundaryError,
        LabelLeakageError,
        InsufficientCalibrationError,
        ModelDeterminismError,
        ProbabilityRangeError,
        FinalTestSealError,
        StudyArtifactError,
        StudyReplayMismatchError,
        StudyVerificationError,
    ],
)
def test_strategy_failures_share_safe_research_base(
    error_type: type[StrategyStudyError],
) -> None:
    error = error_type("safe classified failure")

    assert isinstance(error, StrategyStudyError)
    assert isinstance(error, ResearchError)
    assert str(error) == "safe classified failure"
