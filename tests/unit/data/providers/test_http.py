from email.message import Message
from io import BytesIO
from types import TracebackType
from typing import Self
from urllib.error import HTTPError, URLError
from urllib.request import Request

import pytest

from gemini_trading.data.errors import ProviderConnectionError
from gemini_trading.data.providers.http import UrllibTransport


class _Response:
    def __init__(self, body: bytes, status: int, headers: Message) -> None:
        self._body = body
        self.status = status
        self.headers = headers

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None


def test_urllib_transport_returns_exact_success_bytes_and_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = b'{"exact":"bytes"}\n'
    headers = Message()
    headers["Content-Type"] = "application/json"
    captured: dict[str, object] = {}

    def fake_urlopen(request: Request, timeout: float) -> _Response:
        captured["request"] = request
        captured["timeout"] = timeout
        return _Response(body, 200, headers)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    response = UrllibTransport().get("https://example.test/path", 3.5)

    request = captured["request"]
    assert isinstance(request, Request)
    assert request.method == "GET"
    assert request.full_url == "https://example.test/path"
    assert captured["timeout"] == 3.5
    assert response.status_code == 200
    assert response.headers == (("Content-Type", "application/json"),)
    assert response.body == body


def test_urllib_transport_returns_http_error_status_headers_and_exact_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = b"RATE-LIMIT-BODY"
    headers = Message()
    headers["Retry-After"] = "2.5"

    def fake_urlopen(_request: Request, timeout: float) -> _Response:
        del timeout
        raise HTTPError(
            "https://example.test/path",
            429,
            "Too Many Requests",
            headers,
            BytesIO(body),
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    response = UrllibTransport().get("https://example.test/path", 3.5)

    assert response.status_code == 429
    assert response.headers == (("Retry-After", "2.5"),)
    assert response.body == body


@pytest.mark.parametrize(
    "failure",
    [URLError("offline"), TimeoutError("slow"), OSError("socket")],
)
def test_urllib_transport_maps_connection_failures_without_leaking_details(
    monkeypatch: pytest.MonkeyPatch,
    failure: BaseException,
) -> None:
    def fake_urlopen(_request: Request, timeout: float) -> _Response:
        del timeout
        raise failure

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    with pytest.raises(ProviderConnectionError) as exc_info:
        UrllibTransport().get("https://example.test/PRIVATE-URL", 3.5)

    assert "PRIVATE-URL" not in str(exc_info.value)
    assert "offline" not in str(exc_info.value)
    assert "slow" not in str(exc_info.value)
    assert "socket" not in str(exc_info.value)
