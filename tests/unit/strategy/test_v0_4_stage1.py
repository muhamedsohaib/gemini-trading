"""Candidate v0.4 hourly Stage 1 dataset and closure contracts."""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, cast

from gemini_trading.data.exchange_closures import (
    ExchangeClosureManifest,
    load_exchange_closure_manifest,
    load_fixed_btcusdt_closure_manifest,
    serialize_exchange_closure_manifest,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[3]


class _Stage1Module(Protocol):
    V04_STAGE1_START: datetime
    V04_STAGE1_END_EXCLUSIVE: datetime

    def build_v0_4_closure_manifest(
        self,
        project_root: Path,
    ) -> tuple[ExchangeClosureManifest, bytes]: ...


def _stage1() -> _Stage1Module:
    module_name = "gemini_trading.strategy.v0_4_stage1"
    assert importlib.util.find_spec(module_name) is not None, (
        "Candidate v0.4 requires a version-isolated Stage 1 module"
    )
    return cast(_Stage1Module, importlib.import_module(module_name))


def test_v0_4_stage1_derives_exact_hourly_scope_from_frozen_source_evidence() -> None:
    source, source_raw = load_fixed_btcusdt_closure_manifest(_PROJECT_ROOT)
    stage1 = _stage1()
    hourly, hourly_raw = stage1.build_v0_4_closure_manifest(_PROJECT_ROOT)

    assert datetime(2018, 1, 1, tzinfo=UTC) == stage1.V04_STAGE1_START
    assert datetime(2026, 8, 1, tzinfo=UTC) == stage1.V04_STAGE1_END_EXCLUSIVE
    assert hourly.schema_version == "exchange-closure-manifest-v4"
    assert hourly.provider == "binance_spot"
    assert hourly.instrument == source.instrument
    assert hourly.timeframe.value == "1h"
    assert hourly.start_time == stage1.V04_STAGE1_START
    assert hourly.end_time == stage1.V04_STAGE1_END_EXCLUSIVE
    assert hourly.source_manifest_sha256 == hashlib.sha256(source_raw).hexdigest()
    assert tuple(item.closure_id for item in hourly.closures) == tuple(
        item.closure_id for item in source.closures
    )
    assert load_exchange_closure_manifest(hourly_raw) == hourly
    assert serialize_exchange_closure_manifest(hourly) == hourly_raw

    # The immutable source evidence itself must remain exact v3/4h bytes.
    assert source.schema_version == "exchange-closure-manifest-v3"
    assert source.timeframe.value == "4h"
    assert serialize_exchange_closure_manifest(source) == source_raw


def test_v0_4_hourly_derivation_excludes_only_the_actual_partial_hour() -> None:
    hourly, _ = _stage1().build_v0_4_closure_manifest(_PROJECT_ROOT)
    closure = hourly.closures[0]

    assert closure.closure_id == "binance-spot-infrastructure-maintenance-2018-01-04"
    assert closure.canonical_gap_start == datetime(2018, 1, 4, 3, tzinfo=UTC)
    assert closure.resumed_open == datetime(2018, 1, 4, 4, tzinfo=UTC)
    assert closure.unavailable_candle_count == 1
    assert closure.fully_missing_start == datetime(2018, 1, 4, 4, tzinfo=UTC)
    assert closure.fully_missing_candle_count == 0
    assert closure.partial_candle is not None
    assert closure.partial_candle.open_time == datetime(2018, 1, 4, 3, tzinfo=UTC)
    assert closure.partial_candle.actual_close_time == datetime(
        2018,
        1,
        4,
        3,
        0,
        14,
        838000,
        tzinfo=UTC,
    )
    assert closure.partial_candle.expected_close_time == datetime(
        2018,
        1,
        4,
        3,
        59,
        59,
        999000,
        tzinfo=UTC,
    )
    assert closure.partial_candle.provider_row_sha256 is None


def test_v0_4_hourly_derivation_does_not_fabricate_partial_after_complete_hour() -> None:
    hourly, _ = _stage1().build_v0_4_closure_manifest(_PROJECT_ROOT)
    closure = next(
        item
        for item in hourly.closures
        if item.closure_id == "binance-spot-system-upgrade-2018-06-26"
    )

    # Source interruption is exactly 01:59:59.999, so the 01:00 hourly candle is complete.
    assert closure.canonical_gap_start == datetime(2018, 6, 26, 2, tzinfo=UTC)
    assert closure.partial_candle is None
    assert closure.fully_missing_start == datetime(2018, 6, 26, 2, tzinfo=UTC)
    assert closure.resumed_open == datetime(2018, 6, 26, 12, tzinfo=UTC)
    assert closure.unavailable_candle_count == 10
    assert closure.fully_missing_candle_count == 10
