"""Bounded retry policy for public market-data retrieval."""

import math
from dataclasses import dataclass

from gemini_trading.data.errors import ProviderRateLimitError


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Validated exponential backoff with optional provider delay floor."""

    max_attempts: int = 3
    base_delay_seconds: float = 0.5

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        if not math.isfinite(self.base_delay_seconds) or self.base_delay_seconds < 0:
            raise ValueError("base_delay_seconds must be finite and non-negative")

    def delay_for(
        self,
        attempt: int,
        error: ProviderRateLimitError | None = None,
    ) -> float:
        """Return the delay after one failed attempt."""

        if attempt < 1:
            raise ValueError("attempt must be positive")
        delay = self.base_delay_seconds * (2 ** (attempt - 1))
        if error is not None:
            delay = max(delay, error.retry_after_seconds)
        return delay
