"""Version-isolated hourly Stage 1 dataset contract for Candidate v0.4."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

from gemini_trading.data.exchange_closures import (
    ExchangeClosure,
    ExchangeClosureManifest,
    PartialCandleDeclaration,
    load_fixed_btcusdt_closure_manifest,
    serialize_exchange_closure_manifest,
)
from gemini_trading.domain.timeframe import Timeframe
from gemini_trading.strategy.errors import DatasetHandoffError

V04_STAGE1_START = datetime(2018, 1, 1, tzinfo=UTC)
V04_STAGE1_END_EXCLUSIVE = datetime(2026, 8, 1, tzinfo=UTC)

_V04_CLOSURE_SCHEMA = "exchange-closure-manifest-v4"
_ONE_HOUR = timedelta(hours=1)
_ONE_MILLISECOND = timedelta(milliseconds=1)


def _hour_open(value: datetime) -> datetime:
    return value.replace(minute=0, second=0, microsecond=0)


def _derive_hourly_closure(source: ExchangeClosure) -> ExchangeClosure:
    partial = source.partial_candle
    if partial is None:
        raise DatasetHandoffError("v0.4 source closure lacks the frozen v3 partial evidence")

    containing_open = _hour_open(partial.actual_close_time)
    expected_close = containing_open + _ONE_HOUR - _ONE_MILLISECOND
    if partial.actual_close_time > expected_close:
        raise DatasetHandoffError("v0.4 source closure timestamp cannot map to an hourly slot")

    if partial.actual_close_time < expected_close:
        gap_start = containing_open
        derived_partial = PartialCandleDeclaration(
            open_time=containing_open,
            actual_close_time=partial.actual_close_time,
            expected_close_time=expected_close,
            provider_row_sha256=None,
            exclusion_reason=partial.exclusion_reason,
        )
        fully_missing_start = gap_start + _ONE_HOUR
    else:
        gap_start = containing_open + _ONE_HOUR
        derived_partial = None
        fully_missing_start = gap_start

    if source.resumed_open <= gap_start:
        raise DatasetHandoffError("v0.4 derived hourly closure interval is not positive")
    if source.resumed_open != _hour_open(source.resumed_open):
        raise DatasetHandoffError("v0.4 source resumption is not hourly aligned")

    unavailable = (source.resumed_open - gap_start) // _ONE_HOUR
    fully_missing = (source.resumed_open - fully_missing_start) // _ONE_HOUR
    return ExchangeClosure(
        closure_id=source.closure_id,
        canonical_gap_start=gap_start,
        resumed_open=source.resumed_open,
        unavailable_candle_count=unavailable,
        fully_missing_start=fully_missing_start,
        fully_missing_candle_count=fully_missing,
        reason_code=source.reason_code,
        governance_reference=source.governance_reference,
        partial_candle=derived_partial,
    )


def build_v0_4_closure_manifest(
    project_root: Path,
) -> tuple[ExchangeClosureManifest, bytes]:
    """Derive the exact hourly outage contract from frozen 4h source evidence."""

    source, source_raw = load_fixed_btcusdt_closure_manifest(project_root)
    if source.schema_version != "exchange-closure-manifest-v3":
        raise DatasetHandoffError("v0.4 requires the exact frozen v3 closure source")
    if source.timeframe is not Timeframe.H4:
        raise DatasetHandoffError("v0.4 closure source must remain the frozen 4h evidence")
    if source.start_time != V04_STAGE1_START:
        raise DatasetHandoffError("v0.4 Stage 1 start boundary changed")
    if source.end_time > V04_STAGE1_END_EXCLUSIVE:
        raise DatasetHandoffError("v0.4 source closure window exceeds the locked cutoff")

    manifest = ExchangeClosureManifest(
        schema_version=_V04_CLOSURE_SCHEMA,
        provider=source.provider,
        instrument=source.instrument,
        timeframe=Timeframe.H1,
        start_time=V04_STAGE1_START,
        end_time=V04_STAGE1_END_EXCLUSIVE,
        closures=tuple(_derive_hourly_closure(item) for item in source.closures),
        source_manifest_sha256=hashlib.sha256(source_raw).hexdigest(),
    )
    raw = serialize_exchange_closure_manifest(manifest)
    return manifest, raw


__all__ = [
    "V04_STAGE1_END_EXCLUSIVE",
    "V04_STAGE1_START",
    "build_v0_4_closure_manifest",
]
