from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone

import pytest
from gemini_trading.domain.dataset import RetrievalRequest
from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.timeframe import Timeframe


def test_retrieval_request_uses_bounded_utc_window() -> None:
    request = RetrievalRequest(
        instrument=Instrument("ETHUSDT", "ETH", "USDT"),
        timeframe=Timeframe.H4,
        start_time=datetime(2025, 1, 1, tzinfo=UTC),
        end_time=datetime(2025, 1, 2, tzinfo=UTC),
    )

    assert request.start_time == datetime(2025, 1, 1, tzinfo=UTC)
    assert request.end_time == datetime(2025, 1, 2, tzinfo=UTC)


def test_retrieval_request_rejects_naive_or_non_utc_window() -> None:
    instrument = Instrument("ETHUSDT", "ETH", "USDT")

    with pytest.raises(ValueError, match="UTC-aware"):
        RetrievalRequest(
            instrument,
            Timeframe.H4,
            datetime(2025, 1, 1),
            datetime(2025, 1, 2),
        )

    with pytest.raises(ValueError, match="UTC-aware"):
        RetrievalRequest(
            instrument,
            Timeframe.H4,
            datetime(2025, 1, 1, tzinfo=timezone(timedelta(hours=4))),
            datetime(2025, 1, 2, tzinfo=timezone(timedelta(hours=4))),
        )


def test_retrieval_request_requires_end_after_start() -> None:
    instrument = Instrument("ETHUSDT", "ETH", "USDT")
    instant = datetime(2025, 1, 1, tzinfo=UTC)

    with pytest.raises(ValueError, match="later than"):
        RetrievalRequest(instrument, Timeframe.H4, instant, instant)


def test_retrieval_request_is_immutable() -> None:
    request = RetrievalRequest(
        Instrument("ETHUSDT", "ETH", "USDT"),
        Timeframe.H4,
        datetime(2025, 1, 1, tzinfo=UTC),
        datetime(2025, 1, 2, tzinfo=UTC),
    )

    with pytest.raises(FrozenInstanceError):
        request.end_time = datetime(2025, 1, 3, tzinfo=UTC)  # type: ignore[misc]
