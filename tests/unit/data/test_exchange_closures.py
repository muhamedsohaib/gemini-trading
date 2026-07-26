from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest

from gemini_trading.data.errors import CandleValidationError
from gemini_trading.data.exchange_closures import (
    load_exchange_closure_manifest,
    load_fixed_btcusdt_closure_manifest,
    serialize_exchange_closure_manifest,
)
from gemini_trading.research.serialization import canonical_json_bytes

_PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _closure(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "closure_id": "binance-spot-system-upgrade-2018-02-08",
        "missing_start": "2018-02-08T04:00:00Z",
        "resumed_open": "2018-02-09T08:00:00Z",
        "missing_candle_count": 7,
        "reason_code": "exchange_system_upgrade",
        "governance_reference": "github-issue-22",
    }
    payload.update(overrides)
    return payload


def _payload(*closures: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": "exchange-closure-manifest-v1",
        "provider": "binance_spot",
        "instrument": {
            "symbol": "BTCUSDT",
            "base_asset": "BTC",
            "quote_asset": "USDT",
        },
        "timeframe": "4h",
        "start_time": "2018-01-01T00:00:00Z",
        "end_time": "2026-07-01T00:00:00Z",
        "closures": list(closures or (_closure(),)),
    }


def _raw(payload: dict[str, object]) -> bytes:
    return canonical_json_bytes(payload)


def test_fixed_manifest_is_canonical_and_exact() -> None:
    manifest, raw = load_fixed_btcusdt_closure_manifest(_PROJECT_ROOT)

    assert serialize_exchange_closure_manifest(manifest) == raw
    assert manifest.closures[0].missing_candle_count == 7
    assert manifest.closures[0].missing_start == datetime(2018, 2, 8, 4, tzinfo=UTC)
    assert manifest.closures[0].resumed_open == datetime(2018, 2, 9, 8, tzinfo=UTC)


def test_manifest_rejects_noncanonical_encoding() -> None:
    raw = _raw(_payload()).rstrip(b"\n")

    with pytest.raises(CandleValidationError, match="canonical"):
        load_exchange_closure_manifest(raw)


def test_manifest_rejects_extra_fields() -> None:
    payload = _payload()
    payload["unexpected"] = True

    with pytest.raises(CandleValidationError, match="fields"):
        load_exchange_closure_manifest(_raw(payload))


def test_manifest_rejects_duplicate_closure_ids() -> None:
    payload = _payload(
        _closure(),
        _closure(
            missing_start="2019-01-01T00:00:00Z",
            resumed_open="2019-01-01T04:00:00Z",
            missing_candle_count=1,
        ),
    )

    with pytest.raises(CandleValidationError, match="duplicate"):
        load_exchange_closure_manifest(_raw(payload))


def test_manifest_rejects_unsorted_closures() -> None:
    later = _closure(
        closure_id="later-closure",
        missing_start="2019-01-01T00:00:00Z",
        resumed_open="2019-01-01T04:00:00Z",
        missing_candle_count=1,
    )
    payload = _payload(later, _closure())

    with pytest.raises(CandleValidationError, match="ordered"):
        load_exchange_closure_manifest(_raw(payload))


@pytest.mark.parametrize(
    ("second_start", "message"),
    [
        ("2018-02-09T04:00:00Z", "overlap"),
        ("2018-02-09T08:00:00Z", "touch"),
    ],
)
def test_manifest_rejects_overlapping_or_touching_closures(
    second_start: str,
    message: str,
) -> None:
    second = _closure(
        closure_id="second-closure",
        missing_start=second_start,
        resumed_open="2018-02-09T12:00:00Z",
        missing_candle_count=1,
    )

    with pytest.raises(CandleValidationError, match=message):
        load_exchange_closure_manifest(_raw(_payload(_closure(), second)))


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
        ("missing_start", "2018-02-08T04:00:00+01:00", "UTC"),
        ("missing_start", "2018-02-08T02:00:00Z", "aligned"),
        ("missing_candle_count", 6, "count"),
        ("missing_start", "2017-12-31T20:00:00Z", "window"),
    ],
)
def test_manifest_rejects_invalid_closure_values(
    field_name: str,
    value: object,
    message: str,
) -> None:
    closure = _closure(**{field_name: value})

    with pytest.raises(CandleValidationError, match=message):
        load_exchange_closure_manifest(_raw(_payload(closure)))


def test_manifest_rejects_wrong_market_identity() -> None:
    payload = deepcopy(_payload())
    instrument = cast(dict[str, object], payload["instrument"])
    instrument["symbol"] = "ETHUSDT"
    instrument["base_asset"] = "ETH"

    with pytest.raises(CandleValidationError, match="market identity"):
        load_exchange_closure_manifest(_raw(payload))
