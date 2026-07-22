import pytest
from gemini_trading.data.errors import (
    CandleGapError,
    CandleValidationError,
    CanonicalDatasetWriteError,
    DuplicateCandleError,
    IncompleteWindowError,
    InvalidRetrievalWindowError,
    MarketDataError,
    OutOfOrderCandleError,
    ProviderConnectionError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderSchemaError,
    RawStorageConflictError,
)


@pytest.mark.parametrize(
    "error_type",
    [
        ProviderConnectionError,
        ProviderSchemaError,
        InvalidRetrievalWindowError,
        CandleValidationError,
        DuplicateCandleError,
        OutOfOrderCandleError,
        CandleGapError,
        IncompleteWindowError,
        RawStorageConflictError,
        CanonicalDatasetWriteError,
    ],
)
def test_market_data_errors_share_one_safe_base(error_type: type[MarketDataError]) -> None:
    error = error_type("safe diagnostic")

    assert isinstance(error, MarketDataError)
    assert str(error) == "safe diagnostic"
    assert not hasattr(error, "body")
    assert not hasattr(error, "response_bytes")


def test_rate_limit_error_exposes_only_retry_guidance() -> None:
    error = ProviderRateLimitError(retry_after_seconds=2.5)

    assert error.retry_after_seconds == 2.5
    assert "rate limit" in str(error).lower()
    assert not hasattr(error, "body")


def test_provider_response_error_exposes_status_and_retryability() -> None:
    error = ProviderResponseError(status_code=503, retryable=True)

    assert error.status_code == 503
    assert error.retryable is True
    assert "503" in str(error)
    assert not hasattr(error, "body")


def test_provider_error_metadata_is_validated() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        ProviderRateLimitError(retry_after_seconds=-1)

    with pytest.raises(ValueError, match="HTTP status"):
        ProviderResponseError(status_code=99, retryable=False)
