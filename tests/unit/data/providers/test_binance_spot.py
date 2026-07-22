import inspect
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qsl, urlsplit

import pytest

from gemini_trading.data.errors import (
    ProviderConnectionError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderSchemaError,
)
from gemini_trading.data.providers.base import HttpResponse
from gemini_trading.data.providers.binance_spot import BinanceSpotProvider
from gemini_trading.domain.dataset import RetrievalRequest
from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.timeframe import Timeframe

_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
_INSTRUMENT = Instrument("ETHUSDT", "ETH", "USDT")
_START = datetime(2025, 1, 1, tzinfo=UTC)
_END = _START + timedelta(days=2)
_RETRIEVED_AT = datetime(2025, 2, 1, 12, 30, tzinfo=UTC)


class _FakeTransport:
    def __init__(self, outcomes: list[HttpResponse | BaseException]) -> None:
        self._outcomes = outcomes
        self.calls: list[tuple[str, float]] = []

    def get(self, url: str, timeout_seconds: float) -> HttpResponse:
        self.calls.append((url, timeout_seconds))
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def _response(
    status_code: int = 200,
    body: bytes = b"[]",
    headers: tuple[tuple[str, str], ...] = (),
) -> HttpResponse:
    return HttpResponse(status_code=status_code, headers=headers, body=body)


def _request() -> RetrievalRequest:
    return RetrievalRequest(
        instrument=_INSTRUMENT,
        timeframe=Timeframe.H4,
        start_time=_START,
        end_time=_END,
    )


def _milliseconds(value: datetime) -> int:
    return (value - _EPOCH) // timedelta(milliseconds=1)


def test_fetch_server_time_uses_exact_public_endpoint_and_integer_milliseconds() -> None:
    server_ms = 1_735_689_600_123
    transport = _FakeTransport([_response(body=b'{"serverTime":1735689600123}')])
    provider = BinanceSpotProvider(
        base_url="https://example.test/",
        timeout_seconds=4.25,
        transport=transport,
        clock=lambda: _RETRIEVED_AT,
    )

    result = provider.fetch_server_time()

    assert transport.calls == [("https://example.test/api/v3/time", 4.25)]
    assert result == _EPOCH + timedelta(milliseconds=server_ms)


def test_fetch_klines_uses_exact_sorted_bounded_query_and_preserves_bytes() -> None:
    body = b'[[1735689600000,"100","110","90","105","1",1735703999999]]\n'
    transport = _FakeTransport([_response(body=body)])
    provider = BinanceSpotProvider(
        base_url="https://example.test",
        timeout_seconds=7.0,
        transport=transport,
        clock=lambda: _RETRIEVED_AT,
    )
    cursor = _START + Timeframe.H4.duration

    page = provider.fetch_klines(_request(), cursor)

    assert len(transport.calls) == 1
    url, timeout = transport.calls[0]
    parsed = urlsplit(url)
    expected_parameters = (
        ("endTime", str(_milliseconds(_END) - 1)),
        ("interval", "4h"),
        ("limit", "1000"),
        ("startTime", str(_milliseconds(cursor))),
        ("symbol", "ETHUSDT"),
    )
    assert parsed.scheme == "https"
    assert parsed.netloc == "example.test"
    assert parsed.path == "/api/v3/klines"
    assert tuple(parse_qsl(parsed.query, keep_blank_values=True)) == expected_parameters
    assert timeout == 7.0
    assert page.request_parameters == expected_parameters
    assert page.response.body == body
    assert page.retrieved_at == _RETRIEVED_AT


def test_binance_provider_constructor_has_no_credential_surface() -> None:
    forbidden = ("api_key", "apikey", "secret", "signature", "authorization", "credential")
    parameters = inspect.signature(BinanceSpotProvider.__init__).parameters

    assert not any(token in name.lower() for name in parameters for token in forbidden)


def test_rate_limit_maps_retry_after_without_leaking_body() -> None:
    transport = _FakeTransport(
        [
            _response(
                status_code=429,
                headers=(("retry-after", "2.5"),),
                body=b"PRIVATE-RATE-LIMIT-BODY",
            )
        ]
    )
    provider = BinanceSpotProvider(transport=transport, clock=lambda: _RETRIEVED_AT)

    with pytest.raises(ProviderRateLimitError) as exc_info:
        provider.fetch_klines(_request(), _START)

    assert exc_info.value.retry_after_seconds == 2.5
    assert "PRIVATE-RATE-LIMIT-BODY" not in str(exc_info.value)


@pytest.mark.parametrize(
    ("status_code", "retryable"),
    [(500, True), (503, True), (400, False), (404, False)],
)
def test_http_failures_are_classified_without_leaking_body(
    status_code: int,
    retryable: bool,
) -> None:
    transport = _FakeTransport(
        [_response(status_code=status_code, body=b"PRIVATE-PROVIDER-BODY")]
    )
    provider = BinanceSpotProvider(transport=transport, clock=lambda: _RETRIEVED_AT)

    with pytest.raises(ProviderResponseError) as exc_info:
        provider.fetch_klines(_request(), _START)

    assert exc_info.value.status_code == status_code
    assert exc_info.value.retryable is retryable
    assert "PRIVATE-PROVIDER-BODY" not in str(exc_info.value)


def test_connection_error_is_preserved_without_network_fallback() -> None:
    expected = ProviderConnectionError("public provider connection failed")
    transport = _FakeTransport([expected])
    provider = BinanceSpotProvider(transport=transport, clock=lambda: _RETRIEVED_AT)

    with pytest.raises(ProviderConnectionError) as exc_info:
        provider.fetch_server_time()

    assert exc_info.value is expected
    assert len(transport.calls) == 1


@pytest.mark.parametrize(
    "body",
    [
        b"not-json",
        b"[]",
        b"{}",
        b'{"serverTime":true}',
        b'{"serverTime":"1735689600000"}',
        b'{"serverTime":1735689600000.0}',
    ],
)
def test_malformed_server_time_schema_is_rejected_safely(body: bytes) -> None:
    transport = _FakeTransport([_response(body=body)])
    provider = BinanceSpotProvider(transport=transport, clock=lambda: _RETRIEVED_AT)

    with pytest.raises(ProviderSchemaError) as exc_info:
        provider.fetch_server_time()

    assert body.decode("utf-8", errors="ignore") not in str(exc_info.value)
