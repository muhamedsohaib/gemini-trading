"""Shared fixed-scope v2 closure and segment evidence for sealed tests."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from gemini_trading.data.exchange_closures import load_fixed_btcusdt_closure_manifest
from gemini_trading.data.segments import (
    CandleSegment,
    CandleSegmentManifest,
    serialize_candle_segment_manifest,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_CLOSURE_ID = "binance-spot-system-upgrade-2018-02-08"


@dataclass(frozen=True, slots=True)
class FixedSupportFields:
    dataset_schema_version: str
    closure_manifest_path: str
    closure_manifest_sha256: str
    segment_manifest_path: str
    segment_manifest_sha256: str
    closure_count: int
    segment_count: int
    closure_ids: tuple[str, ...]


def write_fixed_supporting_evidence(root: Path) -> FixedSupportFields:
    """Write canonical fixed-window supporting manifests and return handoff fields."""

    closure_manifest, closure_bytes = load_fixed_btcusdt_closure_manifest(_PROJECT_ROOT)
    segment_manifest = CandleSegmentManifest(
        schema_version="candle-segment-manifest-v1",
        segments=(
            CandleSegment(
                segment_number=1,
                start_index=0,
                end_exclusive=229,
                first_open_time=datetime(2018, 1, 1, tzinfo=UTC),
                last_open_time=datetime(2018, 2, 8, tzinfo=UTC),
                candle_count=229,
                preceding_closure_id=None,
            ),
            CandleSegment(
                segment_number=2,
                start_index=229,
                end_exclusive=18_618,
                first_open_time=datetime(2018, 2, 9, 8, tzinfo=UTC),
                last_open_time=datetime(2026, 6, 30, 20, tzinfo=UTC),
                candle_count=18_389,
                preceding_closure_id=_CLOSURE_ID,
            ),
        ),
    )
    segment_bytes = serialize_candle_segment_manifest(segment_manifest)
    closure_path = root / "exchange-closures.json"
    segment_path = root / "candle-segments.json"
    closure_path.write_bytes(closure_bytes)
    segment_path.write_bytes(segment_bytes)
    return FixedSupportFields(
        dataset_schema_version="candle-dataset-v2",
        closure_manifest_path=closure_path.relative_to(root).as_posix(),
        closure_manifest_sha256=hashlib.sha256(closure_bytes).hexdigest(),
        segment_manifest_path=segment_path.relative_to(root).as_posix(),
        segment_manifest_sha256=hashlib.sha256(segment_bytes).hexdigest(),
        closure_count=len(closure_manifest.closures),
        segment_count=len(segment_manifest.segments),
        closure_ids=tuple(item.closure_id for item in closure_manifest.closures),
    )
