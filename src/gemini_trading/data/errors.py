"""Safe market-data error taxonomy."""

import math


class MarketDataError(Exception):
    """Base class for safe market-data failures."""


class ProviderConnectionError(MarketDataError):
    """Raised when the public provider cannot be reached."""


class ProviderRateLimitError(MarketDataError):
    """Raised when the provider requests a bounded retry delay."""

    retry_after_seconds: float

    def __init__(self, retry_after_seconds: float) -> None:
        if not math.isfinite(retry_after_seconds) or retry_after_seconds < 0:
            raise ValueError("retry_after_seconds must be finite and non-negative")
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"Provider rate limit reached; retry after {retry_after_seconds} seconds")


class ProviderResponseError(MarketDataError):
    """Raised for a classified non-success HTTP response."""

    status_code: int
    retryable: bool

    def __init__(self, status_code: int, retryable: bool) -> None:
        if not 100 <= status_code <= 599:
            raise ValueError("status_code must be a valid HTTP status")
        self.status_code = status_code
        self.retryable = retryable
        super().__init__(f"Provider returned HTTP status {status_code}")


class ProviderSchemaError(MarketDataError):
    """Raised when a provider response violates its public schema."""


class InvalidRetrievalWindowError(MarketDataError):
    """Raised when a retrieval window cannot be executed safely."""


class CandleValidationError(MarketDataError):
    """Raised when a candle violates canonical validation rules."""


class DuplicateCandleError(CandleValidationError):
    """Raised when a sequence repeats a candle identity."""


class OutOfOrderCandleError(CandleValidationError):
    """Raised when candle order is not strictly increasing."""


class CandleGapError(CandleValidationError):
    """Raised when a completed sequence has a continuity gap."""


class IncompleteWindowError(MarketDataError):
    """Raised when a provider cannot supply the full completed window."""


class RawStorageConflictError(MarketDataError):
    """Raised when immutable raw evidence conflicts with existing bytes."""


class CanonicalDatasetWriteError(MarketDataError):
    """Raised when canonical publication cannot complete atomically."""
