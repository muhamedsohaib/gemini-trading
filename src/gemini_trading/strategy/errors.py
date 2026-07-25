"""Strategy-study error exports kept inside the strategy package."""

from gemini_trading.research.errors import (
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


class HistoricalValidationError(StrategyStudyError):
    """Base error for sealed historical-validation evidence."""


class DatasetHandoffError(HistoricalValidationError):
    """Raised when a dataset handoff is missing, mismatched, or tampered."""


class FinalAccessError(HistoricalValidationError):
    """Raised when final-test access or exact resume is not authorized."""


class PreFinalArtifactError(HistoricalValidationError):
    """Raised when pre-final evidence is incomplete or inconsistent."""


__all__ = [
    "DatasetHandoffError",
    "FinalAccessError",
    "FinalTestSealError",
    "HistoricalValidationError",
    "InsufficientCalibrationError",
    "InsufficientHistoryError",
    "LabelLeakageError",
    "ModelDeterminismError",
    "PointInTimeViolationError",
    "PreFinalArtifactError",
    "ProbabilityRangeError",
    "SplitBoundaryError",
    "StrategyStudyError",
    "StudyArtifactError",
    "StudyReplayMismatchError",
    "StudyVerificationError",
]
