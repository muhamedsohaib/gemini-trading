"""Exact Binance partial-row exclusion contracts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest

from gemini_trading.data.errors import CandleValidationError
from gemini_trading.data.exchange_closures import (
    ExchangeClosure,
    ExchangeClosureManifest,
    PartialCandleDeclaration,
)
from gemini_trading.data.exclusions import (
    canonical_binance_row_bytes,
    load_candle_exclusion_manifest,
    match_and_exclude_partial_candles,
    serialize_candle_exclusion_manifest,
)
from gemini_trading.data.normalization.binance_klines import normalize_binance_klines
from gemini_trading.domain.dataset import RawPage
from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.timeframe import Timeframe

_INSTRUMENT = Instrument(symbol="BTCUSDT", base_asset="BTC", quote_asset="USDT")
_TIMEFRAME = Timeframe.H4
_START = datetime(2020, 1, 1, tzinfo=UTC)
_PARTIAL_OPEN = _START + timedelta(hours=4)
_MISSING_OPEN = _START + timedelta(hours=8)
_RESUMED_OPEN = _START + timedelta(hours=12)
_END = _START + timedelta(hours=24)
_SERVER_TIME = _END + timedelta(days=1)


def _milliseconds(value: datetime) -> int:
    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    return (value - epoch) // timedelta(milliseconds=1)


def _full_row(open_time: datetime, seed: int) -> list[object]:
    return [
        _milliseconds(open_time),
        str(100 + seed),
        str(110 + seed),
        str(90 + seed),
        str(105 + seed),
        str(10 + seed),
        _milliseconds(open_time + _TIMEFRAME.duration) - 1,
    ]


def _partial_row() -> list[object]:
    return [
        _milliseconds(_PARTIAL_OPEN),
        "7599.00000000",
        "7844.00000000",
        "7572.09000000",
        "7784.02000000",
        "1521.53731800",
        _milliseconds(_PARTIAL_OPEN + timedelta(minutes=28, seconds=14, milliseconds=788)),
        "11770168.04386595",
        12417,
        "844.25881300",
        "6532638.63751892",
        "0",
    ]


def _manifest(partial_row: list[object] | None = None) -> ExchangeClosureManifest:
    row = _partial_row() if partial_row is None else partial_row
    actual_close = _PARTIAL_OPEN + timedelta(minutes=28, seconds=14, milliseconds=788)
    return ExchangeClosureManifest(
        schema_version="exchange-closure-manifest-v2",
        provider="binance_spot",
        instrument=_INSTRUMENT,
        timeframe=_TIMEFRAME,
        start_time=_START,
        end_time=_END,
        closures=(
            ExchangeClosure(
                closure_id="test-system-upgrade",
                canonical_gap_start=_PARTIAL_OPEN,
                resumed_open=_RESUMED_OPEN,
                unavailable_candle_count=2,
                fully_missing_start=_MISSING_OPEN,
                fully_missing_candle_count=1,
                reason_code="exchange_system_upgrade",
                governance_reference="test-governance",
                partial_candle=PartialCandleDeclaration(
                    open_time=_PARTIAL_OPEN,
                    actual_close_time=actual_close,
                    expected_close_time=_PARTIAL_OPEN
                    + _TIMEFRAME.duration
                    - timedelta(milliseconds=1),
                    provider_row_sha256=hashlib.sha256(
                        canonical_binance_row_bytes(row)
                    ).hexdigest(),
                    exclusion_reason="exchange_closed_mid_candle",
                ),
            ),
        ),
    )


def _raw_page(rows: list[list[object]], *, response_hash: str | None = None) -> RawPage:
    body = (json.dumps(rows, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
    return RawPage(
        run_id="test-run",
        sequence=1,
        request_parameters=(
            ("endTime", str(_milliseconds(_END) - 1)),
            ("interval", _TIMEFRAME.value),
            ("limit", "1000"),
            ("startTime", str(_milliseconds(_START))),
            ("symbol", _INSTRUMENT.symbol),
        ),
        retrieved_at=datetime(2026, 7, 26, tzinfo=UTC),
        server_time_snapshot=_SERVER_TIME,
        http_status=200,
        response_bytes=body,
        response_sha256=(
            hashlib.sha256(body).hexdigest() if response_hash is None else response_hash
        ),
    )


def _rows() -> list[list[object]]:
    return [
        _full_row(_START, 0),
        _partial_row(),
        _full_row(_RESUMED_OPEN, 1),
        _full_row(_START + timedelta(hours=16), 2),
    ]


def _match(
    rows: list[list[object]],
    *,
    manifest: ExchangeClosureManifest | None = None,
    page: RawPage | None = None,
):
    raw_page = _raw_page(rows) if page is None else page
    normalized = normalize_binance_klines(raw_page.response_bytes, _INSTRUMENT, _TIMEFRAME)
    return match_and_exclude_partial_candles(
        (raw_page,),
        (normalized,),
        _manifest() if manifest is None else manifest,
        server_time=_SERVER_TIME,
    )


def test_canonical_provider_row_digest_matches_approved_evidence() -> None:
    row = [
        1518048000000,
        "7599.00000000",
        "7844.00000000",
        "7572.09000000",
        "7784.02000000",
        "1521.53731800",
        1518049694788,
        "11770168.04386595",
        12417,
        "844.25881300",
        "6532638.63751892",
        "0",
    ]
    assert (
        hashlib.sha256(canonical_binance_row_bytes(row)).hexdigest()
        == "6d0ed02c75960a3acf11073a2b7276e0bdc04f217fc99a488b15a5ff68e70775"
    )


def test_exact_partial_row_is_excluded_once_without_changing_raw_bytes() -> None:
    rows = _rows()
    page = _raw_page(rows)
    original_bytes = page.response_bytes

    result = _match(rows, page=page)

    assert page.response_bytes == original_bytes
    assert tuple(candle.open_time for candle in result.candles) == (
        _START,
        _RESUMED_OPEN,
        _START + timedelta(hours=16),
    )
    assert all(candle.completed for candle in result.candles)
    assert len(result.manifest.exclusions) == 1
    exclusion = result.manifest.exclusions[0]
    assert exclusion.closure_id == "test-system-upgrade"
    assert exclusion.raw_page_sequence == 1
    assert exclusion.raw_page_sha256 == page.response_sha256
    assert exclusion.row_index == 1
    assert exclusion.open_time == _PARTIAL_OPEN
    assert exclusion.canonical_index_before_removal == 1
    assert exclusion.provider_row_sha256 == _manifest().closures[0].partial_candle.provider_row_sha256


def test_exclusion_manifest_round_trips_only_canonical_bytes() -> None:
    manifest = _match(_rows()).manifest
    raw = serialize_candle_exclusion_manifest(manifest)
    assert load_candle_exclusion_manifest(raw) == manifest
    assert raw.endswith(b"\n")

    mapping = cast(dict[str, object], json.loads(raw))
    with pytest.raises(CandleValidationError, match="canonical"):
        load_candle_exclusion_manifest(json.dumps(mapping, indent=2).encode())
    mapping["unexpected"] = True
    with pytest.raises(CandleValidationError, match="fields"):
        load_candle_exclusion_manifest(
            (json.dumps(mapping, separators=(",", ":")) + "\n").encode()
        )


def test_manifest_rejects_invalid_provider_row_hash() -> None:
    manifest = _match(_rows()).manifest
    with pytest.raises(CandleValidationError, match="SHA-256"):
        replace(manifest.exclusions[0], provider_row_sha256="abc")


def test_matching_rejects_altered_partial_row_value() -> None:
    rows = _rows()
    rows[1][4] = "7784.03000000"
    with pytest.raises(CandleValidationError, match="provider-row SHA-256"):
        _match(rows)


def test_matching_rejects_missing_partial_row() -> None:
    rows = [_full_row(_START, 0), _full_row(_RESUMED_OPEN, 1)]
    with pytest.raises(CandleValidationError, match="missing"):
        _match(rows)


def test_matching_rejects_duplicate_partial_row() -> None:
    rows = _rows()
    rows.insert(2, _partial_row())
    with pytest.raises(CandleValidationError, match="duplicate"):
        _match(rows)


def test_matching_rejects_additional_undeclared_partial_row() -> None:
    rows = _rows()
    extra = _full_row(_START + timedelta(hours=16), 2)
    extra[6] = _milliseconds(_START + timedelta(hours=16, minutes=30))
    rows[-1] = extra
    with pytest.raises(CandleValidationError, match="undeclared partial"):
        _match(rows)


def test_matching_rejects_candle_inside_fully_missing_interval() -> None:
    rows = _rows()
    rows.insert(2, _full_row(_MISSING_OPEN, 3))
    with pytest.raises(CandleValidationError, match="fully missing"):
        _match(rows)


def test_matching_rejects_missing_resumed_candle() -> None:
    rows = [_full_row(_START, 0), _partial_row(), _full_row(_START + timedelta(hours=16), 2)]
    with pytest.raises(CandleValidationError, match="resumed"):
        _match(rows)


def test_matching_rejects_reordered_rows() -> None:
    rows = _rows()
    rows[2], rows[3] = rows[3], rows[2]
    with pytest.raises(CandleValidationError, match="out of order"):
        _match(rows)


def test_matching_rejects_normalized_rows_not_derived_from_raw_page() -> None:
    rows = _rows()
    page = _raw_page(rows)
    normalized = list(normalize_binance_klines(page.response_bytes, _INSTRUMENT, _TIMEFRAME))
    normalized[0] = replace(normalized[0], close=normalized[0].close + 1)
    with pytest.raises(CandleValidationError, match="normalized candles"):
        match_and_exclude_partial_candles(
            (page,),
            (tuple(normalized),),
            _manifest(),
            server_time=_SERVER_TIME,
        )


def test_matching_rejects_raw_page_hash_mismatch() -> None:
    rows = _rows()
    page = _raw_page(rows, response_hash="0" * 64)
    with pytest.raises(CandleValidationError, match="raw page SHA-256"):
        _match(rows, page=page)
