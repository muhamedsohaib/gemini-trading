"""Safe deterministic-research failure taxonomy."""


class ResearchError(Exception):
    """Base class for safe research and backtesting failures."""


class InvalidExperimentConfigError(ResearchError):
    """Experiment configuration is incomplete or contradictory."""


class DatasetVerificationError(ResearchError):
    """Canonical dataset evidence cannot be trusted."""


class ChronologyViolationError(ResearchError):
    """Candle chronology or completion rules were violated."""


class StrategyContractError(ResearchError):
    """A strategy returned an invalid or non-deterministic decision."""


class InvalidOrderTransitionError(ResearchError):
    """An order lifecycle transition is not permitted."""


class AccountingInvariantError(ResearchError):
    """Cash, position, equity, or ledger invariants failed."""


class ArtifactConflictError(ResearchError):
    """Immutable research evidence conflicts with stored bytes."""


class ReplayMismatchError(ResearchError):
    """Replay did not reproduce the recorded artifacts."""


class NonDeterministicResultError(ResearchError):
    """Equivalent trusted inputs produced different core evidence."""


class StrategyStudyError(ResearchError):
    """Base class for safe candidate-strategy study failures."""


class InsufficientHistoryError(StrategyStudyError):
    """Verified history cannot satisfy the locked evaluation protocol."""


class PointInTimeViolationError(StrategyStudyError):
    """A feature or observation used information unavailable at decision time."""


class SplitBoundaryError(StrategyStudyError):
    """Chronological train, calibration, or test boundaries are invalid."""


class LabelLeakageError(StrategyStudyError):
    """A target or label window leaked across a protected boundary."""


class InsufficientCalibrationError(StrategyStudyError):
    """A calibration segment lacks required observations or classes."""


class ModelDeterminismError(StrategyStudyError):
    """Equivalent trusted model inputs produced different outputs."""


class ProbabilityRangeError(StrategyStudyError):
    """A specialist emitted a non-finite or out-of-range probability."""


class FinalTestSealError(StrategyStudyError):
    """The untouched final test was accessed or changed outside its gate."""


class StudyArtifactError(StrategyStudyError):
    """Immutable strategy-study evidence is incomplete or conflicting."""


class StudyReplayMismatchError(StrategyStudyError):
    """Provider-free strategy-study replay did not reproduce evidence."""


class StudyVerificationError(StrategyStudyError):
    """Independent strategy-study verification failed closed."""
