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
