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
_FIXED_RELATIVE_PATH = Path("config/market-data/sealed-btcusdt-4h-exchange-closures.json")
_APPROVED_ROW_SHA256 = "6d0ed02c75960a3acf11073a2b7276e0bdc04f217fc99a488b15a5ff68e70775"


def _fixed_mapping() -> dict[str, object]:
    loaded: object = json.loads((PROJECT_ROOT / _FIXED_RELATIVE_PATH).read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return cast(dict[str, object], loaded)


def _closures(mapping: dict[str, object]) -> list[dict[str, object]]:
    value = mapping["closures"]
    assert isinstance(value, list)
    raw_items = cast(list[object], value)
    assert all(isinstance(item, dict) for item in raw_items)
    return cast(list[dict[str, object]], raw_items)


def _partial(closure: dict[str, object]) -> dict[str, object]:
    value = closure["partial_candle"]
    assert isinstance(value, dict)
    return cast(dict[str, object], value)


def _canonical(mapping: dict[str, object]) -> bytes:
    return (json.dumps(mapping, ensure_ascii=False, separators=(",", ":")) + "\n").encode()


def _write_fixed_candidate(root: Path, mapping: dict[str, object]) -> None:
    path = root / _FIXED_RELATIVE_PATH
    path.parent.mkdir(parents=True)
    path.write_bytes(_canonical(mapping))


def test_fixed_manifest_is_canonical_and_exact_v2() -> None:
    manifest, raw = load_fixed_btcusdt_closure_manifest(PROJECT_ROOT)
    assert serialize_exchange_closure_manifest(manifest) == raw
    assert manifest.schema_version == "exchange-closure-manifest-v2"
    assert manifest.provider == "binance_spot"
    assert manifest.instrument.symbol == "BTCUSDT"
    assert manifest.timeframe.value == "4h"
    assert len(manifest.closures) == 1

    closure = manifest.closures[0]
    assert closure.closure_id == "binance-spot-system-upgrade-2018-02-08"
    assert closure.canonical_gap_start.isoformat() == "2018-02-08T00:00:00+00:00"
    assert closure.resumed_open.isoformat() == "2018-02-09T08:00:00+00:00"
    assert closure.unavailable_candle_count == 8
    assert closure.fully_missing_start.isoformat() == "2018-02-08T04:00:00+00:00"
    assert closure.fully_missing_candle_count == 7
    assert closure.reason_code == "exchange_system_upgrade"
    assert closure.governance_reference == "github-issue-22"

    partial = closure.partial_candle
    assert partial.open_time.isoformat() == "2018-02-08T00:00:00+00:00"
    assert partial.actual_close_time.isoformat() == "2018-02-08T00:28:14.788000+00:00"
    assert partial.expected_close_time.isoformat() == "2018-02-08T03:59:59.999000+00:00"
    assert partial.provider_row_sha256 == _APPROVED_ROW_SHA256
    assert partial.exclusion_reason == "exchange_closed_mid_candle"


def test_manifest_rejects_v1_schema() -> None:
    mapping = _fixed_mapping()
    mapping["schema_version"] = "exchange-closure-manifest-v1"
    with pytest.raises(CandleValidationError, match="schema"):
        load_exchange_closure_manifest(_canonical(mapping))


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
        canonical_gap_start="2018-03-01T00:00:00Z",
        resumed_open="2018-03-01T04:00:00Z",
        unavailable_candle_count=1,
        fully_missing_start="2018-03-01T00:00:00Z",
        fully_missing_candle_count=1,
        partial_candle=None,
    )
    closures.append(second)
    with pytest.raises(CandleValidationError, match="duplicate"):
        load_exchange_closure_manifest(_canonical(mapping))


def test_manifest_rejects_non_utc_partial_timestamp() -> None:
    mapping = _fixed_mapping()
    partial = _partial(_closures(mapping)[0])
    partial["actual_close_time"] = "2018-02-08T04:28:14.788+04:00"
    with pytest.raises(CandleValidationError, match="UTC"):
        load_exchange_closure_manifest(_canonical(mapping))


def test_manifest_rejects_partial_expected_close_mismatch() -> None:
    mapping = _fixed_mapping()
    partial = _partial(_closures(mapping)[0])
    partial["expected_close_time"] = "2018-02-08T03:59:59.998Z"
    with pytest.raises(CandleValidationError, match="expected close"):
        load_exchange_closure_manifest(_canonical(mapping))


def test_manifest_rejects_partial_close_not_strictly_inside_slot() -> None:
    mapping = _fixed_mapping()
    partial = _partial(_closures(mapping)[0])
    partial["actual_close_time"] = partial["expected_close_time"]
    with pytest.raises(CandleValidationError, match="partial candle"):
        load_exchange_closure_manifest(_canonical(mapping))


def test_manifest_rejects_invalid_provider_row_sha256() -> None:
    mapping = _fixed_mapping()
    partial = _partial(_closures(mapping)[0])
    partial["provider_row_sha256"] = "abc"
    with pytest.raises(CandleValidationError, match="SHA-256"):
        load_exchange_closure_manifest(_canonical(mapping))


def test_manifest_rejects_wrong_unavailable_count() -> None:
    mapping = _fixed_mapping()
    _closures(mapping)[0]["unavailable_candle_count"] = 7
    with pytest.raises(CandleValidationError, match="count"):
        load_exchange_closure_manifest(_canonical(mapping))


def test_manifest_rejects_wrong_fully_missing_count() -> None:
    mapping = _fixed_mapping()
    _closures(mapping)[0]["fully_missing_candle_count"] = 6
    with pytest.raises(CandleValidationError, match="count"):
        load_exchange_closure_manifest(_canonical(mapping))


def test_manifest_rejects_partial_open_not_equal_to_gap_start() -> None:
    mapping = _fixed_mapping()
    partial = _partial(_closures(mapping)[0])
    partial["open_time"] = "2018-02-08T04:00:00Z"
    with pytest.raises(CandleValidationError, match="gap start"):
        load_exchange_closure_manifest(_canonical(mapping))


def test_manifest_rejects_fully_missing_start_not_next_slot() -> None:
    mapping = _fixed_mapping()
    _closures(mapping)[0]["fully_missing_start"] = "2018-02-08T08:00:00Z"
    with pytest.raises(CandleValidationError, match="fully missing"):
        load_exchange_closure_manifest(_canonical(mapping))


def test_fixed_loader_rejects_wrong_market_identity(tmp_path: Path) -> None:
    mapping = _fixed_mapping()
    instrument = mapping["instrument"]
    assert isinstance(instrument, dict)
    instrument["symbol"] = "ETHUSDT"
    instrument["base_asset"] = "ETH"
    _write_fixed_candidate(tmp_path, mapping)

    with pytest.raises(CandleValidationError, match="identity"):
        load_fixed_btcusdt_closure_manifest(tmp_path)


def test_manifest_rejects_closure_outside_request_window() -> None:
    mapping = _fixed_mapping()
    closure = _closures(mapping)[0]
    closure.update(
        canonical_gap_start="2017-12-31T20:00:00Z",
        resumed_open="2018-01-01T00:00:00Z",
        unavailable_candle_count=1,
        fully_missing_start="2017-12-31T20:00:00Z",
        fully_missing_candle_count=1,
        partial_candle=None,
    )
    with pytest.raises(CandleValidationError, match="window"):
        load_exchange_closure_manifest(_canonical(mapping))
