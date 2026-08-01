"""Reusable immutable raw-page fixture for multi-closure ingestion tests."""

import hashlib
import json
from datetime import UTC, datetime, timedelta

from gemini_trading.data.exchange_closures import (
    ExchangeClosure,
    ExchangeClosureManifest,
    PartialCandleDeclaration,
    serialize_exchange_closure_manifest,
)
from gemini_trading.data.exclusions import canonical_binance_row_bytes
from gemini_trading.data.providers.base import HttpResponse, ProviderPage
from gemini_trading.domain.dataset import RetrievalRequest
from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.timeframe import Timeframe

INSTRUMENT = Instrument(symbol="BTCUSDT", base_asset="BTC", quote_asset="USDT")
TIMEFRAME = Timeframe.H4
START = datetime(2020, 1, 1, tzinfo=UTC)
END = START + timedelta(hours=48)
SERVER_TIME = datetime(2026, 7, 2, tzinfo=UTC)
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def milliseconds(value: datetime) -> int:
    return (value - _EPOCH) // timedelta(milliseconds=1)


def full_row(open_time: datetime, seed: int) -> list[object]:
    value = 10_000 + seed
    return [
        milliseconds(open_time),
        str(value),
        str(value + 10),
        str(value - 10),
        str(value + 2),
        "100.0",
        milliseconds(open_time + TIMEFRAME.duration) - 1,
        "1000.0",
        10,
        "50.0",
        "500.0",
        "0",
    ]


def partial_row(open_time: datetime, actual_close: datetime, seed: int) -> list[object]:
    row = full_row(open_time, seed)
    row[6] = milliseconds(actual_close)
    return row


def row_sha256(row: list[object]) -> str:
    return hashlib.sha256(canonical_binance_row_bytes(row)).hexdigest()


def closure(
    *,
    closure_id: str,
    row: list[object],
    actual_close: datetime,
    resumed_open: datetime,
    fully_missing_count: int,
) -> ExchangeClosure:
    open_value = row[0]
    if isinstance(open_value, bool) or not isinstance(open_value, int):
        raise TypeError("fixture row open time must be an integer")
    open_time = datetime.fromtimestamp(open_value / 1000, tz=UTC)
    return ExchangeClosure(
        closure_id=closure_id,
        canonical_gap_start=open_time,
        resumed_open=resumed_open,
        unavailable_candle_count=fully_missing_count + 1,
        fully_missing_start=open_time + TIMEFRAME.duration,
        fully_missing_candle_count=fully_missing_count,
        reason_code="test_exchange_interruption",
        governance_reference="test-governance",
        partial_candle=PartialCandleDeclaration(
            open_time=open_time,
            actual_close_time=actual_close,
            expected_close_time=open_time + TIMEFRAME.duration - timedelta(milliseconds=1),
            provider_row_sha256=row_sha256(row),
            exclusion_reason="exchange_closed_mid_candle",
        ),
    )


def manifest_and_rows() -> tuple[
    ExchangeClosureManifest,
    bytes,
    dict[datetime, list[object]],
]:
    first_open = START + timedelta(hours=4)
    first_close = first_open + timedelta(hours=3, minutes=1)
    second_open = START + timedelta(hours=16)
    second_close = second_open + timedelta(hours=2, minutes=5)
    first_row = partial_row(first_open, first_close, 1)
    second_row = partial_row(second_open, second_close, 2)
    manifest = ExchangeClosureManifest(
        schema_version="exchange-closure-manifest-v3",
        provider="binance_spot",
        instrument=INSTRUMENT,
        timeframe=TIMEFRAME,
        start_time=START,
        end_time=END,
        closures=(
            closure(
                closure_id="test-zero-missing-interruption",
                row=first_row,
                actual_close=first_close,
                resumed_open=START + timedelta(hours=8),
                fully_missing_count=0,
            ),
            closure(
                closure_id="test-one-missing-interruption",
                row=second_row,
                actual_close=second_close,
                resumed_open=START + timedelta(hours=24),
                fully_missing_count=1,
            ),
        ),
    )
    return (
        manifest,
        serialize_exchange_closure_manifest(manifest),
        {first_open: first_row, second_open: second_row},
    )


def retrieval_request(manifest: ExchangeClosureManifest) -> RetrievalRequest:
    return RetrievalRequest(
        instrument=manifest.instrument,
        timeframe=manifest.timeframe,
        start_time=manifest.start_time,
        end_time=manifest.end_time,
    )


class MultiClosureProvider:
    """Deterministic provider emitting immutable raw pages around two interruptions."""

    def __init__(
        self,
        manifest: ExchangeClosureManifest,
        partial_rows: dict[datetime, list[object]],
    ) -> None:
        self._manifest = manifest
        self._partial_rows = partial_rows
        self._page_number = 0

    def fetch_server_time(self) -> datetime:
        return SERVER_TIME

    def fetch_klines(
        self,
        request: RetrievalRequest,
        cursor: datetime,
        limit: int = 1000,
    ) -> ProviderPage:
        rows: list[list[object]] = []
        open_time = cursor
        page_limit = min(limit, 3)
        while open_time < request.end_time and len(rows) < page_limit:
            partial = self._partial_rows.get(open_time)
            if partial is not None:
                rows.append(partial)
                open_time += request.timeframe.duration
                continue

            skipped = False
            for item in self._manifest.closures:
                if item.fully_missing_start <= open_time < item.resumed_open:
                    open_time = item.resumed_open
                    skipped = True
                    break
            if skipped:
                continue

            rows.append(full_row(open_time, len(rows) + self._page_number * page_limit))
            open_time += request.timeframe.duration

        self._page_number += 1
        parameters = tuple(
            sorted(
                (
                    ("symbol", request.instrument.symbol),
                    ("interval", request.timeframe.value),
                    ("startTime", str(milliseconds(cursor))),
                    ("endTime", str(milliseconds(request.end_time) - 1)),
                    ("limit", str(limit)),
                )
            )
        )
        return ProviderPage(
            request_parameters=parameters,
            response=HttpResponse(
                status_code=200,
                headers=(),
                body=(json.dumps(rows, separators=(",", ":")) + "\n").encode(),
            ),
            retrieved_at=datetime(2026, 7, 1, tzinfo=UTC) + timedelta(seconds=self._page_number),
        )
