"""Contracts for the fixed sealed BTCUSDT exchange-closure manifest."""

import json
from pathlib import Path
from typing import cast

import pytest

from gemini_trading.data.errors import CandleValidationError
from gemini_trading.data.exchange_closures import (
    load_exchange_closure_manifest,
    load_fixed_btcusdt_closure_manifest,
    serialize_exchange_closure_manifest,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _fixed_mapping() -> dict[str, object]:
    path = PROJECT_ROOT / "config/market-data/sealed-btcusdt-4h-exchange-closures.json"
    loaded: object = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return cast(dict[str, object], loaded)


def _closures(mapping: dict[str, object]) -> list[dict[str, object]]:
    value = mapping["closures"]
    assert isinstance(value, list)
    raw_items = cast(list[object], value)
    assert all(isinstance(item, dict) for item in raw_items)
    return cast(list[dict[str, object]], raw_items)


def _canonical(mapping: dict[str, object]) -> bytes:
    return (json.dumps(mapping, ensure_ascii=False, separators=(",", ":")) + "\n").encode()


def test_fixed_manifest_is_canonical_and_exact() -> None:
    manifest, raw = load_fixed_btcusdt_closure_manifest(PROJECT_ROOT)
    assert serialize_exchange_closure_manifest(manifest) == raw
    assert manifest.provider == "binance_spot"
    assert manifest.instrument.symbol == "BTCUSDT"
    assert manifest.timeframe.value == "4h"
    assert len(manifest.closures) == 1
    closure = manifest.closures[0]
    assert closure.closure_id == "binance-spot-system-upgrade-2018-02-08"
    assert closure.missing_candle_count == 7
    assert closure.missing_start.isoformat() == "2018-02-08T04:00:00+00:00"
    assert closure.resumed_open.isoformat() == "2018-02-09T08:00:00+00:00"
    assert closure.reason_code == "exchange_system_upgrade"
    assert closure.governance_reference == "github-issue-22"


def test_manifest_rejects_extra_fields() -> None:
    mapping = _fixed_mapping()
    mapping["unexpected"] = True
    with pytest.raises(CandleValidationError, match="fields"):
        load_exchange_closure_manifest(_canonical(mapping))


def test_manifest_rejects_noncanonical_whitespace() -> None:
    mapping = _fixed_mapping()
    with pytest.raises(CandleValidationError, match="canonical"):
        load_exchange_closure_manifest(json.dumps(mapping, indent=2).encode())


def test_manifest_rejects_duplicate_closure_ids() -> None:
    mapping = _fixed_mapping()
    closures = _closures(mapping)
    second = dict(closures[0])
    second.update(
        missing_start="2018-03-01T00:00:00Z",
        resumed_open="2018-03-01T04:00:00Z",
        missing_candle_count=1,
    )
    closures.append(second)
    with pytest.raises(CandleValidationError, match="duplicate"):
        load_exchange_closure_manifest(_canonical(mapping))


def test_manifest_rejects_unsorted_entries() -> None:
    mapping = _fixed_mapping()
    first = dict(_closures(mapping)[0])
    later = dict(first)
    later.update(
        closure_id="later",
        missing_start="2018-03-01T00:00:00Z",
        resumed_open="2018-03-01T04:00:00Z",
        missing_candle_count=1,
    )
    mapping["closures"] = [later, first]
    with pytest.raises(CandleValidationError, match="ordered"):
        load_exchange_closure_manifest(_canonical(mapping))


def test_manifest_rejects_overlapping_entries() -> None:
    mapping = _fixed_mapping()
    first = dict(_closures(mapping)[0])
    overlap = dict(first)
    overlap.update(
        closure_id="overlap",
        missing_start="2018-02-09T04:00:00Z",
        resumed_open="2018-02-09T12:00:00Z",
        missing_candle_count=2,
    )
    mapping["closures"] = [first, overlap]
    with pytest.raises(CandleValidationError, match="overlap"):
        load_exchange_closure_manifest(_canonical(mapping))


def test_manifest_rejects_touching_entries() -> None:
    mapping = _fixed_mapping()
    first = dict(_closures(mapping)[0])
    touching = dict(first)
    touching.update(
        closure_id="touching",
        missing_start=first["resumed_open"],
        resumed_open="2018-02-09T12:00:00Z",
        missing_candle_count=1,
    )
    mapping["closures"] = [first, touching]
    with pytest.raises(CandleValidationError, match="overlap"):
        load_exchange_closure_manifest(_canonical(mapping))


def test_manifest_rejects_non_utc_timestamp() -> None:
    mapping = _fixed_mapping()
    closure = _closures(mapping)[0]
    closure["missing_start"] = "2018-02-08T08:00:00+04:00"
    with pytest.raises(CandleValidationError, match="UTC"):
        load_exchange_closure_manifest(_canonical(mapping))


def test_manifest_rejects_timeframe_misalignment() -> None:
    mapping = _fixed_mapping()
    closure = _closures(mapping)[0]
    closure["missing_start"] = "2018-02-08T05:00:00Z"
    with pytest.raises(CandleValidationError, match="aligned"):
        load_exchange_closure_manifest(_canonical(mapping))


def test_manifest_rejects_wrong_missing_count() -> None:
    mapping = _fixed_mapping()
    _closures(mapping)[0]["missing_candle_count"] = 6
    with pytest.raises(CandleValidationError, match="count"):
        load_exchange_closure_manifest(_canonical(mapping))


def test_manifest_rejects_wrong_market_identity() -> None:
    mapping = _fixed_mapping()
    instrument = mapping["instrument"]
    assert isinstance(instrument, dict)
    instrument["symbol"] = "ETHUSDT"
    instrument["base_asset"] = "ETH"
    with pytest.raises(CandleValidationError, match="market"):
        load_exchange_closure_manifest(_canonical(mapping))


def test_manifest_rejects_closure_outside_request_window() -> None:
    mapping = _fixed_mapping()
    closure = _closures(mapping)[0]
    closure.update(
        missing_start="2017-12-31T20:00:00Z",
        resumed_open="2018-01-01T00:00:00Z",
        missing_candle_count=1,
    )
    with pytest.raises(CandleValidationError, match="window"):
        load_exchange_closure_manifest(_canonical(mapping))
