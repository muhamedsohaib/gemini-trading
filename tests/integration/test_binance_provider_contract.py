from datetime import UTC, datetime, timedelta

from gemini_trading.data.providers.base import (
    HttpResponse,
    HttpTransport,
    MarketDataProvider,
)
from gemini_trading.data.providers.binance_spot import BinanceSpotProvider
from gemini_trading.domain.dataset import RetrievalRequest
from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.timeframe import Timeframe


class _ContractTransport:
    def __init__(self) -> None:
        self.urls: list[str] = []

    def get(self, url: str, timeout_seconds: float) -> HttpResponse:
        assert timeout_seconds == 6.0
        self.urls.append(url)
        if url.endswith("/api/v3/time"):
            return HttpResponse(200, (), b'{"serverTime":1735689600123}')
        return HttpResponse(200, (("Content-Type", "application/json"),), b"[]")


def _as_transport(value: HttpTransport) -> HttpTransport:
    return value


def _as_provider(value: MarketDataProvider) -> MarketDataProvider:
    return value


def test_binance_provider_satisfies_public_provider_contract_without_network() -> None:
    transport = _ContractTransport()
    provider = _as_provider(
        BinanceSpotProvider(
            base_url="https://example.test",
            timeout_seconds=6.0,
            transport=_as_transport(transport),
            clock=lambda: datetime(2025, 2, 1, tzinfo=UTC),
        )
    )
    request = RetrievalRequest(
        instrument=Instrument("ETHUSDT", "ETH", "USDT"),
        timeframe=Timeframe.H4,
        start_time=datetime(2025, 1, 1, tzinfo=UTC),
        end_time=datetime(2025, 1, 2, tzinfo=UTC),
    )

    server_time = provider.fetch_server_time()
    page = provider.fetch_klines(request, request.start_time, limit=250)

    assert server_time == datetime(1970, 1, 1, tzinfo=UTC) + timedelta(
        milliseconds=1_735_689_600_123
    )
    assert page.response.body == b"[]"
    assert transport.urls[0] == "https://example.test/api/v3/time"
    assert transport.urls[1].startswith("https://example.test/api/v3/klines?")
    assert "limit=250" in transport.urls[1]
