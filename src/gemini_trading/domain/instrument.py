"""Instrument identity for market-data retrieval."""

import re
from dataclasses import dataclass

_IDENTIFIER_PATTERN = re.compile(r"^[A-Z0-9]{2,30}$")


def _normalize_identifier(value: str, field_name: str) -> str:
    normalized = value.strip().upper()
    if _IDENTIFIER_PATTERN.fullmatch(normalized) is None:
        raise ValueError(f"{field_name} must be a valid identifier")
    return normalized


@dataclass(frozen=True, slots=True)
class Instrument:
    """Explicit venue symbol identity without implicit asset inference."""

    symbol: str
    base_asset: str
    quote_asset: str

    def __post_init__(self) -> None:
        symbol = _normalize_identifier(self.symbol, "symbol")
        base_asset = _normalize_identifier(self.base_asset, "base_asset")
        quote_asset = _normalize_identifier(self.quote_asset, "quote_asset")

        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "base_asset", base_asset)
        object.__setattr__(self, "quote_asset", quote_asset)

        if symbol != f"{base_asset}{quote_asset}":
            raise ValueError("symbol must equal base_asset + quote_asset")
