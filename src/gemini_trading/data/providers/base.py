"""Provider and HTTP transport contracts."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from gemini_trading.domain.dataset import RetrievalRequest


@dataclass(frozen=True, slots=True)
class HttpResponse:
    """Exact HTTP response bytes and safe metadata."""

    status_code: int
    headers: tuple[tuple[str, str], ...]
    body: bytes


class HttpTransport(Protocol):
    """Synchronous HTTP GET transport."""

    def get(self, url: str, timeout_seconds: float) -> HttpResponse: ...


@dataclass(frozen=True, slots=True)
class ProviderPage:
    """One provider page with stable request parameters and retrieval time."""

    request_parameters: tuple[tuple[str, str], ...]
    response: HttpResponse
    retrieved_at: datetime


class MarketDataProvider(Protocol):
    """Public market-data retrieval contract."""

    def fetch_server_time(self) -> datetime: ...

    def fetch_klines(
        self,
        request: RetrievalRequest,
        cursor: datetime,
        limit: int = 1000,
    ) -> ProviderPage: ...
