from dataclasses import FrozenInstanceError

import pytest
from gemini_trading.domain.instrument import Instrument


def test_instrument_normalizes_uppercase_identity() -> None:
    instrument = Instrument(symbol=" ethusdt ", base_asset=" eth ", quote_asset=" usdt ")

    assert instrument.symbol == "ETHUSDT"
    assert instrument.base_asset == "ETH"
    assert instrument.quote_asset == "USDT"


def test_instrument_requires_symbol_to_match_assets() -> None:
    with pytest.raises(ValueError, match=r"must equal base_asset \+ quote_asset"):
        Instrument(symbol="BTCUSDT", base_asset="ETH", quote_asset="USDT")


@pytest.mark.parametrize(
    ("symbol", "base_asset", "quote_asset"),
    [
        ("", "ETH", "USDT"),
        ("EUSDT", "E", "USDT"),
        ("ETH-USDT", "ETH-", "USDT"),
        ("A" * 31 + "USDT", "A" * 31, "USDT"),
    ],
)
def test_instrument_rejects_malformed_identifiers(
    symbol: str, base_asset: str, quote_asset: str
) -> None:
    with pytest.raises(ValueError, match="identifier"):
        Instrument(symbol=symbol, base_asset=base_asset, quote_asset=quote_asset)


def test_instrument_is_immutable() -> None:
    instrument = Instrument("ETHUSDT", "ETH", "USDT")

    with pytest.raises(FrozenInstanceError):
        instrument.symbol = "BTCUSDT"  # type: ignore[misc]
