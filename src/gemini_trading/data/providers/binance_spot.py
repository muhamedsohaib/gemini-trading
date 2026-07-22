"""Public Binance Spot market-data provider."""

import json
import math
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import cast
from urllib.parse import urlencode

from gemini_trading.data.errors import (
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderSchemaError,
)
from gemini_trading.data.providers.base import (
    HttpResponse,
    HttpTransport,
    ProviderPage,
)
from gemini_trading.data.providers.http import UrllibTransport
from gemini_trading.domain.dataset import RetrievalRequest
from gemini_trading.domain.time import require_utc

_UNIX_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _utc_milliseconds(value: datetime) -> int:
    require_utc(value, "provider timestamp")
    return (value - _UNIX_EPOCH) // timedelta(milliseconds=1)


def _retry_after_seconds(response: HttpResponse) -> float:
    for name, value in response.headers:
        if name.lower() != "retry-after":
            continue
        try:
            parsed = float(value)
        except ValueError:
            return 0.0
        if math.isfinite(parsed) and parsed >= 0:
            return parsed
        return 0.0
    return 0.0


def _classify_response(response: HttpResponse) -> None:
    if 200 <= response.status_code <= 299:
        return
    if response.status_code == 429:
        raise ProviderRateLimitError(_retry_after_seconds(response))
    raise ProviderResponseError(
        status_code=response.status_code,
        retryable=500 <= response.status_code <= 599,
    )


def _parse_server_time(payload: bytes) -> datetime:
    try:
        decoded = cast(object, json.loads(payload.decode("utf-8")))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ProviderSchemaError("Binance server-time payload is invalid") from None

    if not isinstance(decoded, dict):
        raise ProviderSchemaError("Binance server-time payload has an invalid schema")
    values = cast(dict[str, object], decoded)
    server_time = values.get("serverTime")
    if isinstance(server_time, bool) or not isinstance(server_time, int):
        raise ProviderSchemaError("Binance server-time payload has an invalid schema")

    try:
        return _UNIX_EPOCH + timedelta(milliseconds=server_time)
    except (OverflowError, ValueError):
        raise ProviderSchemaError(
            "Binance server-time value is outside the supported range"
        ) from None


class BinanceSpotProvider:
    """Synchronous adapter for Binance Spot public market-data endpoints."""

    def __init__(
        self,
        base_url: str = "https://api.binance.com",
        timeout_seconds: float = 10.0,
        transport: HttpTransport | None = None,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._transport = transport if transport is not None else UrllibTransport()
        self._clock = clock

    def fetch_server_time(self) -> datetime:
        response = self._transport.get(
            f"{self._base_url}/api/v3/time",
            self._timeout_seconds,
        )
        _classify_response(response)
        return _parse_server_time(response.body)

    def fetch_klines(
        self,
        request: RetrievalRequest,
        cursor: datetime,
        limit: int = 1000,
    ) -> ProviderPage:
        parameters = tuple(
            sorted(
                (
                    ("symbol", request.instrument.symbol),
                    ("interval", request.timeframe.value),
                    ("startTime", str(_utc_milliseconds(cursor))),
                    ("endTime", str(_utc_milliseconds(request.end_time) - 1)),
                    ("limit", str(limit)),
                )
            )
        )
        url = f"{self._base_url}/api/v3/klines?{urlencode(parameters)}"
        response = self._transport.get(url, self._timeout_seconds)
        _classify_response(response)
        return ProviderPage(
            request_parameters=parameters,
            response=response,
            retrieved_at=self._clock(),
        )
