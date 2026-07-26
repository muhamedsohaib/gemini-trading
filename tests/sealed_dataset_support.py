"""Shared fixed-scope v3 closure, exclusion, and segment evidence for sealed tests."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from gemini_trading.data.exchange_closures import load_fixed_btcusdt_closure_manifest
from gemini_trading.data.exclusions import (
    CandleExclusion,
    CandleExclusionManifest,
    serialize_candle_exclusion_manifest,
)
from gemini_trading.data.segments import (
    CandleSegment,
    CandleSegmentManifest,
    serialize_candle_segment_manifest,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_CLOSURE_ID = "binance-spot-system-upgrade-2018-02-08"
_PROVIDER_ROW_SHA256 = "6d0ed02c75960a3acf11073a2b7276e0bdc04f217fc99a488b15a5ff68e70775"


@dataclass(frozen=True, slots=True)
class FixedSupportFields:
    dataset_schema_version: str
    closure_manifest_path: str
    closure_manifest_sha256: str
    exclusion_manifest_path: str
    exclusion_manifest_sha256: str
    segment_manifest_path: str
    segment_manifest_sha256: str
    closure_count: int
    exclusion_count: int
    segment_count: int
    closure_ids: tuple[str, ...]
    excluded_provider_row_sha256: str
    segment_boundary_indices: tuple[int, ...]


def write_fixed_supporting_evidence(root: Path) -> FixedSupportFields:
    """Write canonical fixed-window supporting manifests and return handoff fields."""

    closure_manifest, closure_bytes = load_fixed_btcusdt_closure_manifest(_PROJECT_ROOT)
    exclusion_manifest = CandleExclusionManifest(
        schema_version="candle-exclusion-manifest-v1",
        exclusions=(
            CandleExclusion(
                closure_id=_CLOSURE_ID,
                raw_page_sequence=1,
                raw_page_sha256="1" * 64,
                row_index=228,
                provider_row_sha256=_PROVIDER_ROW_SHA256,
                open_time=datetime(2018, 2, 8, tzinfo=UTC),
                actual_close_time=datetime(2018, 2, 8, 0, 28, 14, 788000, tzinfo=UTC),
                expected_close_time=datetime(2018, 2, 8, 3, 59, 59, 999000, tzinfo=UTC),
                exclusion_reason="exchange_closed_mid_candle",
                canonical_index_before_removal=228,
            ),
        ),
    )
    exclusion_bytes = serialize_candle_exclusion_manifest(exclusion_manifest)
    segment_manifest = CandleSegmentManifest(
        schema_version="candle-segment-manifest-v1",
        segments=(
            CandleSegment(
                segment_number=1,
                start_index=0,
                end_exclusive=228,
                first_open_time=datetime(2018, 1, 1, tzinfo=UTC),
                last_open_time=datetime(2018, 2, 7, 20, tzinfo=UTC),
                candle_count=228,
                preceding_closure_id=None,
            ),
            CandleSegment(
                segment_number=2,
                start_index=228,
                end_exclusive=18_617,
                first_open_time=datetime(2018, 2, 9, 8, tzinfo=UTC),
                last_open_time=datetime(2026, 6, 30, 20, tzinfo=UTC),
                candle_count=18_389,
                preceding_closure_id=_CLOSURE_ID,
            ),
        ),
    )
    segment_bytes = serialize_candle_segment_manifest(segment_manifest)
    closure_path = root / "exchange-closures.json"
    exclusion_path = root / "candle-exclusions.json"
    segment_path = root / "candle-segments.json"
    closure_path.write_bytes(closure_bytes)
    exclusion_path.write_bytes(exclusion_bytes)
    segment_path.write_bytes(segment_bytes)
    return FixedSupportFields(
        dataset_schema_version="candle-dataset-v3",
        closure_manifest_path=closure_path.relative_to(root).as_posix(),
        closure_manifest_sha256=hashlib.sha256(closure_bytes).hexdigest(),
        exclusion_manifest_path=exclusion_path.relative_to(root).as_posix(),
        exclusion_manifest_sha256=hashlib.sha256(exclusion_bytes).hexdigest(),
        segment_manifest_path=segment_path.relative_to(root).as_posix(),
        segment_manifest_sha256=hashlib.sha256(segment_bytes).hexdigest(),
        closure_count=len(closure_manifest.closures),
        exclusion_count=len(exclusion_manifest.exclusions),
        segment_count=len(segment_manifest.segments),
        closure_ids=tuple(item.closure_id for item in closure_manifest.closures),
        excluded_provider_row_sha256=_PROVIDER_ROW_SHA256,
        segment_boundary_indices=segment_manifest.boundary_indices,
    )
