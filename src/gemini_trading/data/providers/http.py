"""Standard-library HTTP transport for public provider requests."""

import urllib.request
from email.message import Message
from urllib.error import HTTPError, URLError

from gemini_trading.data.errors import ProviderConnectionError
from gemini_trading.data.providers.base import HttpResponse


def _header_items(headers: Message | None) -> tuple[tuple[str, str], ...]:
    if headers is None:
        return ()
    return tuple((name, value) for name, value in headers.items())


class UrllibTransport:
    """Perform one bounded public HTTP GET and retain exact response bytes."""

    def get(self, url: str, timeout_seconds: float) -> HttpResponse:
        request = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(request, timeout_seconds) as response:
                return HttpResponse(
                    status_code=response.status,
                    headers=_header_items(response.headers),
                    body=response.read(),
                )
        except HTTPError as error:
            return HttpResponse(
                status_code=error.code,
                headers=_header_items(error.headers),
                body=error.read(),
            )
        except (URLError, TimeoutError, OSError):
            raise ProviderConnectionError("public provider connection failed") from None
