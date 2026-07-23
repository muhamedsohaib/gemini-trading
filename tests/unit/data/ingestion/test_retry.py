import math

import pytest

from gemini_trading.data.errors import ProviderRateLimitError
from gemini_trading.data.ingestion.retry import RetryPolicy


@pytest.mark.parametrize(
    ("max_attempts", "base_delay_seconds", "message"),
    [
        (0, 0.5, "max_attempts must be positive"),
        (3, -0.1, "base_delay_seconds must be finite and non-negative"),
        (3, math.inf, "base_delay_seconds must be finite and non-negative"),
        (3, math.nan, "base_delay_seconds must be finite and non-negative"),
    ],
)
def test_retry_policy_rejects_invalid_configuration(
    max_attempts: int,
    base_delay_seconds: float,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        RetryPolicy(
            max_attempts=max_attempts,
            base_delay_seconds=base_delay_seconds,
        )


def test_retry_policy_uses_exponential_delay() -> None:
    policy = RetryPolicy(max_attempts=4, base_delay_seconds=0.5)

    assert policy.delay_for(1) == 0.5
    assert policy.delay_for(2) == 1.0
    assert policy.delay_for(3) == 2.0


def test_retry_policy_honors_larger_retry_after_delay() -> None:
    policy = RetryPolicy(max_attempts=3, base_delay_seconds=0.5)
    error = ProviderRateLimitError(retry_after_seconds=3.25)

    assert policy.delay_for(1, error) == 3.25
    assert policy.delay_for(4, error) == 4.0


@pytest.mark.parametrize("attempt", [0, -1])
def test_retry_policy_rejects_non_positive_attempt(attempt: int) -> None:
    with pytest.raises(ValueError, match="attempt must be positive"):
        RetryPolicy().delay_for(attempt)
