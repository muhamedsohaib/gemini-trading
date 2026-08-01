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
    CandleExclusionResult,
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
_APPROVED_ROW_SHA256 = (
    "6d0ed02c75960a3acf11073a2b7276e0bdc04f217fc99a488b15a5ff68e70775"  # pragma: allowlist secret
)
_START = datetime(2020, 1, 1, tzinfo=UTC)
_ZERO_PARTIAL_OPEN = _START + timedelta(hours=4)
_ZERO_RESUMED_OPEN = _START + timedelta(hours=8)
_SECOND_PARTIAL_OPEN = _START + timedelta(hours=16)
_SECOND_MISSING_OPEN = _START + timedelta(hours=20)
_SECOND_RESUMED_OPEN = _START + timedelta(hours=24)
_END = _START + timedelta(hours=36)
_SERVER_TIME = _END + timedelta(days=1)


def _milliseconds(value: datetime) -> int:
    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    return (value - epoch) // timedelta(milliseconds=1)


def _datetime_from_milliseconds(value: object) -> datetime:
    assert isinstance(value, int)
    return datetime.fromtimestamp(value / 1000, tz=UTC)


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


def _partial_row(open_time: datetime, actual_close: datetime, seed: int) -> list[object]:
    return [
        _milliseconds(open_time),
        f"{100 + seed}.00000000",
        f"{110 + seed}.00000000",
        f"{90 + seed}.00000000",
        f"{105 + seed}.00000000",
        f"{10 + seed}.00000000",
        _milliseconds(actual_close),
        f"{1000 + seed}.00000000",
        100 + seed,
        f"{5 + seed}.00000000",
        f"{500 + seed}.00000000",
        "0",
    ]


def _approved_partial_row() -> list[object]:
    return [
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


def _page_rows() -> tuple[list[list[object]], list[list[object]]]:
    first_page = [
        _full_row(_START, 0),
        _partial_row(
            _ZERO_PARTIAL_OPEN,
            _ZERO_PARTIAL_OPEN + timedelta(hours=3, seconds=14, milliseconds=838),
            1,
        ),
        _full_row(_ZERO_RESUMED_OPEN, 2),
        _full_row(_START + timedelta(hours=12), 3),
    ]
    second_page = [
        _partial_row(
            _SECOND_PARTIAL_OPEN,
            _SECOND_PARTIAL_OPEN + timedelta(hours=1, minutes=35, seconds=32, milliseconds=286),
            4,
        ),
        _full_row(_SECOND_RESUMED_OPEN, 5),
        _full_row(_START + timedelta(hours=28), 6),
        _full_row(_START + timedelta(hours=32), 7),
    ]
    return first_page, second_page


def _row_digest(row: list[object]) -> str:
    return hashlib.sha256(canonical_binance_row_bytes(row)).hexdigest()


def _closure(
    *,
    closure_id: str,
    row: list[object],
    resumed_open: datetime,
    fully_missing_count: int,
) -> ExchangeClosure:
    open_time = _datetime_from_milliseconds(row[0])
    actual_close = _datetime_from_milliseconds(row[6])
    return ExchangeClosure(
        closure_id=closure_id,
        canonical_gap_start=open_time,
        resumed_open=resumed_open,
        unavailable_candle_count=fully_missing_count + 1,
        fully_missing_start=open_time + _TIMEFRAME.duration,
        fully_missing_candle_count=fully_missing_count,
        reason_code="test_exchange_interruption",
        governance_reference="test-governance",
        partial_candle=PartialCandleDeclaration(
            open_time=open_time,
            actual_close_time=actual_close,
            expected_close_time=open_time + _TIMEFRAME.duration - timedelta(milliseconds=1),
            provider_row_sha256=_row_digest(row),
            exclusion_reason="exchange_closed_mid_candle",
        ),
    )


def _manifest(
    first_page: list[list[object]],
    second_page: list[list[object]],
) -> ExchangeClosureManifest:
    return ExchangeClosureManifest(
        schema_version="exchange-closure-manifest-v3",
        provider="binance_spot",
        instrument=_INSTRUMENT,
        timeframe=_TIMEFRAME,
        start_time=_START,
        end_time=_END,
        closures=(
            _closure(
                closure_id="test-zero-missing-interruption",
                row=first_page[1],
                resumed_open=_ZERO_RESUMED_OPEN,
                fully_missing_count=0,
            ),
            _closure(
                closure_id="test-one-missing-interruption",
                row=second_page[0],
                resumed_open=_SECOND_RESUMED_OPEN,
                fully_missing_count=1,
            ),
        ),
    )


def _raw_page(
    rows: list[list[object]],
    *,
    sequence: int,
    response_hash: str | None = None,
    run_id: str = "test-run",
) -> RawPage:
    body = (json.dumps(rows, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
    return RawPage(
        run_id=run_id,
        sequence=sequence,
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


def _pages(
    first_page: list[list[object]],
    second_page: list[list[object]],
    *,
    second_sequence: int = 2,
    second_run_id: str = "test-run",
) -> tuple[RawPage, RawPage]:
    return (
        _raw_page(first_page, sequence=1),
        _raw_page(second_page, sequence=second_sequence, run_id=second_run_id),
    )


def _match(
    first_page: list[list[object]],
    second_page: list[list[object]],
    *,
    pages: tuple[RawPage, RawPage] | None = None,
    manifest: ExchangeClosureManifest | None = None,
) -> CandleExclusionResult:
    raw_pages = _pages(first_page, second_page) if pages is None else pages
    normalized_pages = tuple(
        normalize_binance_klines(page.response_bytes, _INSTRUMENT, _TIMEFRAME) for page in raw_pages
    )
    return match_and_exclude_partial_candles(
        raw_pages,
        normalized_pages,
        _manifest(first_page, second_page) if manifest is None else manifest,
        server_time=_SERVER_TIME,
    )


def test_canonical_provider_row_digest_matches_approved_evidence() -> None:
    assert (
        hashlib.sha256(canonical_binance_row_bytes(_approved_partial_row())).hexdigest()
        == _APPROVED_ROW_SHA256
    )


def test_multiple_declared_partial_rows_across_pages_are_excluded_in_order() -> None:
    first_page, second_page = _page_rows()
    pages = _pages(first_page, second_page)
    original_bytes = tuple(page.response_bytes for page in pages)
    manifest = _manifest(first_page, second_page)

    result = _match(first_page, second_page, pages=pages, manifest=manifest)

    assert tuple(page.response_bytes for page in pages) == original_bytes
    assert tuple(candle.open_time for candle in result.candles) == (
        _START,
        _ZERO_RESUMED_OPEN,
        _START + timedelta(hours=12),
        _SECOND_RESUMED_OPEN,
        _START + timedelta(hours=28),
        _START + timedelta(hours=32),
    )
    assert all(candle.completed for candle in result.candles)
    assert tuple(item.closure_id for item in result.manifest.exclusions) == tuple(
        item.closure_id for item in manifest.closures
    )
    assert tuple(item.provider_row_sha256 for item in result.manifest.exclusions) == tuple(
        item.partial_candle.provider_row_sha256 for item in manifest.closures
    )
    assert tuple(
        (item.raw_page_sequence, item.row_index, item.canonical_index_before_removal)
        for item in result.manifest.exclusions
    ) == ((1, 1, 1), (2, 0, 4))


def test_zero_missing_interruption_requires_next_aligned_resumed_open() -> None:
    first_page, second_page = _page_rows()
    manifest = _manifest(first_page, second_page)
    assert manifest.closures[0].fully_missing_candle_count == 0
    assert manifest.closures[0].fully_missing_start == _ZERO_RESUMED_OPEN

    result = _match(first_page, second_page, manifest=manifest)
    assert _ZERO_RESUMED_OPEN in {candle.open_time for candle in result.candles}


def test_exclusion_manifest_round_trips_only_canonical_bytes() -> None:
    first_page, second_page = _page_rows()
    manifest = _match(first_page, second_page).manifest
    raw = serialize_candle_exclusion_manifest(manifest)
    assert load_candle_exclusion_manifest(raw) == manifest
    assert raw.endswith(b"\n")

    mapping = cast(dict[str, object], json.loads(raw))
    with pytest.raises(CandleValidationError, match="canonical"):
        load_candle_exclusion_manifest(json.dumps(mapping, indent=2).encode())
    mapping["unexpected"] = True
    with pytest.raises(CandleValidationError, match="fields"):
        load_candle_exclusion_manifest((json.dumps(mapping, separators=(",", ":")) + "\n").encode())


def test_manifest_rejects_invalid_provider_row_hash() -> None:
    first_page, second_page = _page_rows()
    manifest = _match(first_page, second_page).manifest
    with pytest.raises(CandleValidationError, match="SHA-256"):
        replace(manifest.exclusions[0], provider_row_sha256="abc")


def test_matching_rejects_altered_declared_partial_row_value() -> None:
    first_page, second_page = _page_rows()
    manifest = _manifest(first_page, second_page)
    second_page[0][4] = "999.00000000"
    with pytest.raises(CandleValidationError, match="provider-row SHA-256"):
        _match(first_page, second_page, manifest=manifest)


def test_matching_rejects_missing_declared_partial_row() -> None:
    first_page, second_page = _page_rows()
    manifest = _manifest(first_page, second_page)
    second_page.pop(0)
    with pytest.raises(CandleValidationError, match="missing"):
        _match(first_page, second_page, manifest=manifest)


def test_matching_rejects_duplicate_declared_partial_row() -> None:
    first_page, second_page = _page_rows()
    second_page.insert(1, list(second_page[0]))
    with pytest.raises(CandleValidationError, match="duplicate"):
        _match(first_page, second_page)


def test_matching_rejects_additional_undeclared_short_row() -> None:
    first_page, second_page = _page_rows()
    extra = _full_row(_START + timedelta(hours=28), 6)
    extra[6] = _milliseconds(_START + timedelta(hours=28, minutes=30))
    second_page[2] = extra
    with pytest.raises(CandleValidationError, match="undeclared partial"):
        _match(first_page, second_page)


def test_matching_rejects_additional_undeclared_overlong_row() -> None:
    first_page, second_page = _page_rows()
    extra = _full_row(_START + timedelta(hours=28), 6)
    extra[6] = _milliseconds(_START + timedelta(hours=33)) - 1
    second_page[2] = extra
    with pytest.raises(CandleValidationError, match="undeclared partial"):
        _match(first_page, second_page)


def test_matching_rejects_candle_inside_nonempty_missing_interval() -> None:
    first_page, second_page = _page_rows()
    second_page.insert(1, _full_row(_SECOND_MISSING_OPEN, 8))
    with pytest.raises(CandleValidationError, match="fully missing"):
        _match(first_page, second_page)


def test_matching_rejects_missing_resumed_candle() -> None:
    first_page, second_page = _page_rows()
    second_page.pop(1)
    with pytest.raises(CandleValidationError, match="resumed"):
        _match(first_page, second_page)


def test_matching_rejects_reordered_rows_across_page_boundary() -> None:
    first_page, second_page = _page_rows()
    manifest = _manifest(first_page, second_page)
    first_page[-1], second_page[0] = second_page[0], first_page[-1]
    with pytest.raises(CandleValidationError, match="out of order"):
        _match(first_page, second_page, manifest=manifest)


def test_matching_rejects_normalized_rows_not_derived_from_raw_page() -> None:
    first_page, second_page = _page_rows()
    pages = _pages(first_page, second_page)
    normalized_pages = [
        list(normalize_binance_klines(page.response_bytes, _INSTRUMENT, _TIMEFRAME))
        for page in pages
    ]
    normalized_pages[0][0] = replace(
        normalized_pages[0][0],
        close=normalized_pages[0][0].close + 1,
    )
    with pytest.raises(CandleValidationError, match="normalized candles"):
        match_and_exclude_partial_candles(
            pages,
            tuple(tuple(page) for page in normalized_pages),
            _manifest(first_page, second_page),
            server_time=_SERVER_TIME,
        )


def test_matching_rejects_raw_page_hash_mismatch() -> None:
    first_page, second_page = _page_rows()
    pages = (
        _raw_page(first_page, sequence=1),
        _raw_page(second_page, sequence=2, response_hash="0" * 64),
    )
    with pytest.raises(CandleValidationError, match="raw page SHA-256"):
        _match(first_page, second_page, pages=pages)


def test_matching_rejects_nonconsecutive_page_sequences() -> None:
    first_page, second_page = _page_rows()
    pages = _pages(first_page, second_page, second_sequence=3)
    with pytest.raises(CandleValidationError, match="sequence"):
        _match(first_page, second_page, pages=pages)


def test_matching_rejects_pages_from_different_runs() -> None:
    first_page, second_page = _page_rows()
    pages = _pages(first_page, second_page, second_run_id="other-run")
    with pytest.raises(CandleValidationError, match="retrieval run"):
        _match(first_page, second_page, pages=pages)
